#!/usr/bin/env python3
"""
실시간 가격 모니터링 + 다중 타임프레임 분석
1분마다 실행, AI 호출 없이 가격/조건만 체크
조건 충족 시 플래그 설정 → 별도 분석 트리거
"""

import os
import hmac
import hashlib
import time
import requests
import json
from datetime import datetime
from pathlib import Path

API_KEY = os.environ.get('BINANCE_API_KEY')
SECRET = os.environ.get('BINANCE_SECRET')
BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"

# 설정
CONFIG_PATH = Path(__file__).parent / 'config.json'
STATUS_PATH = Path(__file__).parent / 'monitor_status.json'
ALERT_PATH = Path(__file__).parent / 'alert_trigger.json'

with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

LEVERAGE = CONFIG.get('leverage', 20)
MAX_LOSS_PERCENT = CONFIG.get('risk', {}).get('max_loss_percent', 10)

def get_signature(query_string):
    return hmac.new(SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def api_request(endpoint, params=None):
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    signature = get_signature(query)
    url = f'{BASE_URL}{endpoint}?{query}&signature={signature}'
    headers = {'X-MBX-APIKEY': API_KEY}
    return requests.get(url, headers=headers).json()

def get_klines(interval, limit=100):
    """캔들 데이터 조회 (서명 불필요)"""
    url = f"{BASE_URL}/fapi/v1/klines?symbol={SYMBOL}&interval={interval}&limit={limit}"
    resp = requests.get(url).json()
    return [{
        'time': k[0],
        'open': float(k[1]),
        'high': float(k[2]),
        'low': float(k[3]),
        'close': float(k[4]),
        'volume': float(k[5])
    } for k in resp]

def get_current_price():
    """현재가 조회"""
    url = f"{BASE_URL}/fapi/v1/ticker/price?symbol={SYMBOL}"
    return float(requests.get(url).json()['price'])

def get_position():
    """포지션 조회"""
    result = api_request('/fapi/v2/positionRisk')
    for pos in result:
        if pos['symbol'] == SYMBOL:
            amt = float(pos['positionAmt'])
            if amt != 0:
                return {
                    'side': 'LONG' if amt > 0 else 'SHORT',
                    'size': abs(amt),
                    'entry': float(pos['entryPrice']),
                    'pnl': float(pos['unRealizedProfit']),
                    'leverage': int(pos['leverage'])
                }
    return None

def find_order_blocks(klines, lookback=50):
    """오더블록 자동 탐지"""
    blocks = []
    for i in range(2, min(lookback, len(klines)-1)):
        curr = klines[i]
        prev = klines[i-1]
        
        # 상승 장악형 (Bullish Engulfing) → 지지 오더블록
        if prev['close'] < prev['open']:  # 이전: 음봉
            if curr['close'] > curr['open']:  # 현재: 양봉
                if curr['close'] > prev['open'] and curr['open'] < prev['close']:
                    blocks.append({
                        'type': 'support',
                        'high': prev['open'],
                        'low': prev['close'],
                        'strength': curr['volume']
                    })
        
        # 하락 장악형 (Bearish Engulfing) → 저항 오더블록
        if prev['close'] > prev['open']:  # 이전: 양봉
            if curr['close'] < curr['open']:  # 현재: 음봉
                if curr['close'] < prev['open'] and curr['open'] > prev['close']:
                    blocks.append({
                        'type': 'resistance',
                        'high': prev['close'],
                        'low': prev['open'],
                        'strength': curr['volume']
                    })
    
    return blocks

def find_fvg(klines, lookback=50):
    """FVG (Fair Value Gap) 탐지"""
    gaps = []
    for i in range(2, min(lookback, len(klines))):
        prev2 = klines[i-2]
        curr = klines[i]
        
        # 상승 FVG: 2봉전 고가 < 현재봉 저가
        if prev2['high'] < curr['low']:
            gaps.append({
                'type': 'support',
                'high': curr['low'],
                'low': prev2['high'],
                'size': curr['low'] - prev2['high']
            })
        
        # 하락 FVG: 2봉전 저가 > 현재봉 고가
        if prev2['low'] > curr['high']:
            gaps.append({
                'type': 'resistance',
                'high': prev2['low'],
                'low': curr['high'],
                'size': prev2['low'] - curr['high']
            })
    
    return gaps

def analyze_multi_timeframe():
    """다중 타임프레임 분석"""
    timeframes = {
        '1M': '1M',    # 월봉
        '1w': '1w',    # 주봉
        '1d': '1d',    # 일봉
        '4h': '4h',    # 4시간
        '1h': '1h',    # 1시간
        '15m': '15m',  # 15분
        '5m': '5m',    # 5분
        '1m': '1m'     # 1분
    }
    
    analysis = {}
    support_zones = []
    resistance_zones = []
    
    for name, interval in timeframes.items():
        try:
            klines = get_klines(interval, limit=100)
            if not klines:
                continue
                
            # 현재 추세
            ma20 = sum(k['close'] for k in klines[-20:]) / 20
            current = klines[-1]['close']
            trend = 'UP' if current > ma20 else 'DOWN'
            
            # 오더블록 탐지
            obs = find_order_blocks(klines)
            for ob in obs:
                zone = {
                    'tf': name,
                    'type': ob['type'],
                    'high': ob['high'],
                    'low': ob['low']
                }
                if ob['type'] == 'support':
                    support_zones.append(zone)
                else:
                    resistance_zones.append(zone)
            
            # FVG 탐지
            fvgs = find_fvg(klines)
            for fvg in fvgs:
                zone = {
                    'tf': name,
                    'type': fvg['type'],
                    'high': fvg['high'],
                    'low': fvg['low']
                }
                if fvg['type'] == 'support':
                    support_zones.append(zone)
                else:
                    resistance_zones.append(zone)
            
            analysis[name] = {
                'trend': trend,
                'ma20': ma20,
                'close': current,
                'high': max(k['high'] for k in klines[-20:]),
                'low': min(k['low'] for k in klines[-20:]),
                'order_blocks': len(obs),
                'fvg': len(fvgs)
            }
        except Exception as e:
            analysis[name] = {'error': str(e)}
    
    return {
        'analysis': analysis,
        'support_zones': support_zones,
        'resistance_zones': resistance_zones
    }

def find_entry_zones(price, mtf_data):
    """현재가 근처의 진입 구간 찾기"""
    nearby_supports = []
    nearby_resistances = []
    
    threshold = price * 0.02  # 현재가 ±2% 이내
    
    for zone in mtf_data['support_zones']:
        if abs(zone['high'] - price) < threshold or abs(zone['low'] - price) < threshold:
            nearby_supports.append(zone)
    
    for zone in mtf_data['resistance_zones']:
        if abs(zone['high'] - price) < threshold or abs(zone['low'] - price) < threshold:
            nearby_resistances.append(zone)
    
    return nearby_supports, nearby_resistances

def check_exit_conditions(position, price, mtf_data):
    """익절 조건 체크"""
    if not position:
        return None
    
    entry = position['entry']
    pnl_percent = ((price - entry) / entry) * 100
    if position['side'] == 'SHORT':
        pnl_percent = -pnl_percent
    
    reasons = []
    
    # 손익비 2:1 도달 체크
    sl_distance = entry * (MAX_LOSS_PERCENT / LEVERAGE / 100)
    tp_target = sl_distance * 2
    
    if position['side'] == 'LONG':
        if price >= entry + tp_target:
            reasons.append(f"손익비 2:1 도달 (목표가 ${entry + tp_target:,.0f})")
    else:
        if price <= entry - tp_target:
            reasons.append(f"손익비 2:1 도달 (목표가 ${entry - tp_target:,.0f})")
    
    # 저항/지지 오더블록 도달 체크
    for zone in mtf_data['resistance_zones']:
        if position['side'] == 'LONG' and zone['low'] <= price <= zone['high']:
            reasons.append(f"저항 오더블록 도달 ({zone['tf']})")
    
    for zone in mtf_data['support_zones']:
        if position['side'] == 'SHORT' and zone['low'] <= price <= zone['high']:
            reasons.append(f"지지 오더블록 도달 ({zone['tf']})")
    
    if reasons:
        return {
            'should_exit': True,
            'pnl_percent': pnl_percent,
            'reasons': reasons
        }
    
    return None

def main():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 현재가
    price = get_current_price()
    
    # 포지션 확인
    position = get_position()
    
    # 다중 타임프레임 분석
    mtf_data = analyze_multi_timeframe()
    
    # 상태 저장
    status = {
        'timestamp': timestamp,
        'price': price,
        'position': position,
        'mtf_summary': {
            tf: {'trend': data.get('trend'), 'ma20': data.get('ma20')}
            for tf, data in mtf_data['analysis'].items()
            if 'trend' in data
        },
        'support_count': len(mtf_data['support_zones']),
        'resistance_count': len(mtf_data['resistance_zones'])
    }
    
    alert = None
    
    if position:
        # 포지션 있음 → 익절 조건 체크
        exit_check = check_exit_conditions(position, price, mtf_data)
        if exit_check and exit_check['should_exit']:
            alert = {
                'type': 'EXIT_SIGNAL',
                'timestamp': timestamp,
                'price': price,
                'position': position,
                'reasons': exit_check['reasons'],
                'pnl_percent': exit_check['pnl_percent']
            }
            status['alert'] = 'EXIT_SIGNAL'
    else:
        # 포지션 없음 → 진입 구간 체크
        nearby_supports, nearby_resistances = find_entry_zones(price, mtf_data)
        
        if nearby_supports:
            # 지지 구간 근처 → 롱 기회
            alert = {
                'type': 'LONG_OPPORTUNITY',
                'timestamp': timestamp,
                'price': price,
                'zones': nearby_supports[:3],  # 상위 3개
                'zone_count': len(nearby_supports)
            }
            status['alert'] = 'LONG_OPPORTUNITY'
        
        if nearby_resistances:
            # 저항 구간 근처 → 숏 기회
            alert = {
                'type': 'SHORT_OPPORTUNITY',
                'timestamp': timestamp,
                'price': price,
                'zones': nearby_resistances[:3],
                'zone_count': len(nearby_resistances)
            }
            status['alert'] = 'SHORT_OPPORTUNITY'
    
    # 상태 저장
    with open(STATUS_PATH, 'w') as f:
        json.dump(status, f, indent=2, default=str)
    
    # 알림 필요시 저장
    if alert:
        with open(ALERT_PATH, 'w') as f:
            json.dump(alert, f, indent=2, default=str)
        print(f"🚨 ALERT: {alert['type']}")
        print(json.dumps(alert, indent=2, default=str))
    else:
        # 알림 파일 삭제
        if ALERT_PATH.exists():
            ALERT_PATH.unlink()
        print(f"✅ {timestamp} | ${price:,.2f} | Pos: {position['side'] if position else 'None'} | Waiting...")

if __name__ == "__main__":
    main()
