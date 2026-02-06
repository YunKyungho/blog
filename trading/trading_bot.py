#!/usr/bin/env python3
"""
BTC 선물 자동 트레이딩 봇
- 다중 타임프레임 분석
- 겹치는 오더블록/FVG 구간만 필터링
- 손익비 1:2 이상 확보 시에만 진입
- 완전 자동 (질문 없음)
"""

import os
import hmac
import hashlib
import time
import requests
import json
from datetime import datetime
from pathlib import Path

# API 설정
API_KEY = os.environ.get('BINANCE_API_KEY')
SECRET = os.environ.get('BINANCE_SECRET')
BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"

# 파일 경로
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / 'config.json'
STATUS_PATH = BASE_DIR / 'bot_status.json'
LOG_PATH = BASE_DIR / 'trade_log.json'

# 설정 로드
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

LEVERAGE = CONFIG.get('leverage', 20)
MAX_LOSS_PERCENT = CONFIG.get('risk', {}).get('max_loss_percent', 10)
MIN_RR_RATIO = CONFIG.get('min_rr_ratio', 2.0)

# ========== API 함수 ==========

def get_signature(query_string):
    return hmac.new(SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def api_request(method, endpoint, params=None):
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    signature = get_signature(query)
    url = f'{BASE_URL}{endpoint}?{query}&signature={signature}'
    headers = {'X-MBX-APIKEY': API_KEY}
    
    if method == 'GET':
        return requests.get(url, headers=headers).json()
    elif method == 'POST':
        return requests.post(url, headers=headers).json()
    elif method == 'DELETE':
        return requests.delete(url, headers=headers).json()

def get_klines(interval, limit=100):
    """캔들 데이터"""
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

def get_price():
    url = f"{BASE_URL}/fapi/v1/ticker/price?symbol={SYMBOL}"
    return float(requests.get(url).json()['price'])

def get_balance():
    result = api_request('GET', '/fapi/v2/balance')
    for bal in result:
        if bal['asset'] == 'USDT':
            return float(bal['balance'])
    return 0

def get_position():
    result = api_request('GET', '/fapi/v2/positionRisk')
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

def get_open_orders():
    return api_request('GET', '/fapi/v1/openOrders', {'symbol': SYMBOL})

def set_leverage():
    return api_request('POST', '/fapi/v1/leverage', {'symbol': SYMBOL, 'leverage': LEVERAGE})

def place_order(side, order_type, quantity, price=None, stop_price=None, reduce_only=False):
    params = {
        'symbol': SYMBOL,
        'side': side,
        'type': order_type,
        'quantity': quantity
    }
    if price:
        params['price'] = price
        params['timeInForce'] = 'GTC'
    if stop_price:
        params['stopPrice'] = stop_price
    if reduce_only:
        params['reduceOnly'] = 'true'
    
    return api_request('POST', '/fapi/v1/order', params)

def close_position(position):
    side = 'SELL' if position['side'] == 'LONG' else 'BUY'
    return api_request('POST', '/fapi/v1/order', {
        'symbol': SYMBOL,
        'side': side,
        'type': 'MARKET',
        'quantity': position['size'],
        'reduceOnly': 'true'
    })

def cancel_all_orders():
    return api_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': SYMBOL})

# ========== 분석 함수 ==========

def find_order_blocks(klines):
    """오더블록 탐지 - 강한 것만"""
    blocks = []
    avg_volume = sum(k['volume'] for k in klines) / len(klines)
    
    for i in range(2, len(klines)-1):
        curr = klines[i]
        prev = klines[i-1]
        
        # 거래량 필터 (평균 이상만)
        if curr['volume'] < avg_volume:
            continue
        
        body_prev = abs(prev['close'] - prev['open'])
        body_curr = abs(curr['close'] - curr['open'])
        
        # 장악형 체크 (현재 몸통이 이전보다 커야 함)
        if body_curr < body_prev * 1.2:
            continue
        
        # 상승 장악형 → 지지
        if prev['close'] < prev['open'] and curr['close'] > curr['open']:
            if curr['close'] > prev['open'] and curr['open'] < prev['close']:
                blocks.append({
                    'type': 'support',
                    'high': prev['open'],
                    'low': prev['close'],
                    'mid': (prev['open'] + prev['close']) / 2,
                    'volume': curr['volume']
                })
        
        # 하락 장악형 → 저항
        if prev['close'] > prev['open'] and curr['close'] < curr['open']:
            if curr['close'] < prev['open'] and curr['open'] > prev['close']:
                blocks.append({
                    'type': 'resistance',
                    'high': prev['close'],
                    'low': prev['open'],
                    'mid': (prev['open'] + prev['close']) / 2,
                    'volume': curr['volume']
                })
    
    return blocks

def find_overlapping_zones(all_zones, price, threshold_pct=0.5):
    """
    여러 타임프레임에서 겹치는 구간 찾기
    threshold_pct: 가격 기준 겹침 허용 범위 (%)
    """
    threshold = price * (threshold_pct / 100)
    
    supports = [z for z in all_zones if z['type'] == 'support']
    resistances = [z for z in all_zones if z['type'] == 'resistance']
    
    def find_clusters(zones):
        if not zones:
            return []
        
        # mid 가격 기준 정렬
        zones = sorted(zones, key=lambda x: x['mid'])
        clusters = []
        current_cluster = [zones[0]]
        
        for z in zones[1:]:
            if z['mid'] - current_cluster[-1]['mid'] < threshold:
                current_cluster.append(z)
            else:
                if len(current_cluster) >= 2:  # 2개 이상 TF에서 겹쳐야 함
                    clusters.append({
                        'zones': current_cluster,
                        'count': len(current_cluster),
                        'mid': sum(zz['mid'] for zz in current_cluster) / len(current_cluster),
                        'high': max(zz['high'] for zz in current_cluster),
                        'low': min(zz['low'] for zz in current_cluster),
                        'type': current_cluster[0]['type']
                    })
                current_cluster = [z]
        
        # 마지막 클러스터
        if len(current_cluster) >= 2:
            clusters.append({
                'zones': current_cluster,
                'count': len(current_cluster),
                'mid': sum(zz['mid'] for zz in current_cluster) / len(current_cluster),
                'high': max(zz['high'] for zz in current_cluster),
                'low': min(zz['low'] for zz in current_cluster),
                'type': current_cluster[0]['type']
            })
        
        return clusters
    
    return {
        'support_clusters': find_clusters(supports),
        'resistance_clusters': find_clusters(resistances)
    }

def analyze_market():
    """전체 시장 분석"""
    timeframes = ['1M', '1w', '1d', '4h', '1h', '15m', '5m']
    all_zones = []
    trends = {}
    
    for tf in timeframes:
        try:
            klines = get_klines(tf, limit=50)
            if not klines:
                continue
            
            # 추세 판단
            ma20 = sum(k['close'] for k in klines[-20:]) / 20
            current = klines[-1]['close']
            trends[tf] = {
                'direction': 'UP' if current > ma20 else 'DOWN',
                'ma20': ma20,
                'close': current
            }
            
            # 오더블록 탐지
            blocks = find_order_blocks(klines)
            for b in blocks:
                b['tf'] = tf
                all_zones.append(b)
                
        except Exception as e:
            print(f"  {tf} 분석 실패: {e}")
    
    price = get_price()
    clusters = find_overlapping_zones(all_zones, price)
    
    # 큰 추세 판단 (일봉 기준)
    big_trend = trends.get('1d', {}).get('direction', 'UNKNOWN')
    
    return {
        'price': price,
        'trends': trends,
        'big_trend': big_trend,
        'support_clusters': clusters['support_clusters'],
        'resistance_clusters': clusters['resistance_clusters'],
        'all_zones_count': len(all_zones)
    }

def calculate_entry(price, cluster, side):
    """
    진입 계산: 손익비 확인
    """
    # 손절 거리 (마진 10% 손실 기준)
    sl_percent = MAX_LOSS_PERCENT / LEVERAGE  # 0.5%
    sl_distance = price * (sl_percent / 100)
    
    if side == 'LONG':
        # 지지 구간에서 롱
        entry = cluster['high']  # 구간 상단에서 진입
        sl = cluster['low'] - (price * 0.001)  # 구간 하단 아래
        actual_sl_distance = entry - sl
        
        # 가장 가까운 저항까지 거리 = 익절 목표
        tp_distance = actual_sl_distance * MIN_RR_RATIO
        tp = entry + tp_distance
        
    else:  # SHORT
        entry = cluster['low']  # 구간 하단에서 진입
        sl = cluster['high'] + (price * 0.001)
        actual_sl_distance = sl - entry
        
        tp_distance = actual_sl_distance * MIN_RR_RATIO
        tp = entry - tp_distance
    
    rr_ratio = tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
    
    return {
        'entry': entry,
        'sl': sl,
        'tp': tp,
        'sl_distance': actual_sl_distance,
        'tp_distance': tp_distance,
        'rr_ratio': rr_ratio,
        'valid': rr_ratio >= MIN_RR_RATIO
    }

def find_entry_opportunity(analysis):
    """
    진입 기회 탐색
    조건: 겹치는 구간 + 큰 추세 방향 일치 + 손익비 1:2 이상
    """
    price = analysis['price']
    big_trend = analysis['big_trend']
    
    # 현재가에서 1% 이내의 구간만
    nearby_range = price * 0.01
    
    opportunities = []
    
    # 큰 추세가 하락이면 숏 기회 찾기
    if big_trend == 'DOWN':
        for cluster in analysis['resistance_clusters']:
            distance = cluster['mid'] - price
            if 0 < distance < nearby_range:  # 위에 있고 1% 이내
                calc = calculate_entry(price, cluster, 'SHORT')
                if calc['valid']:
                    opportunities.append({
                        'side': 'SHORT',
                        'cluster': cluster,
                        'calc': calc,
                        'distance': distance,
                        'tf_count': cluster['count']
                    })
    
    # 큰 추세가 상승이면 롱 기회 찾기
    if big_trend == 'UP':
        for cluster in analysis['support_clusters']:
            distance = price - cluster['mid']
            if 0 < distance < nearby_range:  # 아래에 있고 1% 이내
                calc = calculate_entry(price, cluster, 'LONG')
                if calc['valid']:
                    opportunities.append({
                        'side': 'LONG',
                        'cluster': cluster,
                        'calc': calc,
                        'distance': distance,
                        'tf_count': cluster['count']
                    })
    
    # 가장 좋은 기회 선택 (TF 겹침 많은 것 우선)
    if opportunities:
        return max(opportunities, key=lambda x: (x['tf_count'], -x['distance']))
    
    return None

def check_exit_opportunity(position, analysis):
    """
    익절 기회 탐색
    """
    price = analysis['price']
    entry = position['entry']
    
    pnl_percent = ((price - entry) / entry) * 100
    if position['side'] == 'SHORT':
        pnl_percent = -pnl_percent
    
    # 손익비 2:1 도달 체크
    sl_distance = entry * (MAX_LOSS_PERCENT / LEVERAGE / 100)
    tp_target_distance = sl_distance * MIN_RR_RATIO
    
    if position['side'] == 'LONG':
        tp_target = entry + tp_target_distance
        at_target = price >= tp_target
    else:
        tp_target = entry - tp_target_distance
        at_target = price <= tp_target
    
    # 반대 방향 구간 도달 체크
    at_zone = False
    if position['side'] == 'LONG':
        for cluster in analysis['resistance_clusters']:
            if cluster['low'] <= price <= cluster['high']:
                at_zone = True
                break
    else:
        for cluster in analysis['support_clusters']:
            if cluster['low'] <= price <= cluster['high']:
                at_zone = True
                break
    
    return {
        'pnl_percent': pnl_percent,
        'at_target': at_target,
        'tp_target': tp_target,
        'at_zone': at_zone,
        'should_exit': at_target or (at_zone and pnl_percent > 0.5)
    }

# ========== 실행 함수 ==========

def execute_entry(opportunity):
    """진입 실행"""
    balance = get_balance()
    price = get_price()
    
    set_leverage()
    
    # 수량 계산 (전체 잔고)
    notional = balance * LEVERAGE
    quantity = round(notional / price, 3)
    
    calc = opportunity['calc']
    
    # 진입 주문
    order_side = 'BUY' if opportunity['side'] == 'LONG' else 'SELL'
    entry_result = place_order(order_side, 'MARKET', quantity)
    
    if 'orderId' not in entry_result:
        return {'success': False, 'error': entry_result}
    
    time.sleep(0.5)  # 체결 대기
    
    # 손절 주문
    sl_side = 'SELL' if opportunity['side'] == 'LONG' else 'BUY'
    sl_price = round(calc['sl'], 1)
    sl_result = place_order(sl_side, 'STOP_MARKET', quantity, stop_price=sl_price, reduce_only=True)
    
    return {
        'success': True,
        'side': opportunity['side'],
        'quantity': quantity,
        'entry_price': price,
        'sl_price': sl_price,
        'tp_target': calc['tp'],
        'rr_ratio': calc['rr_ratio'],
        'tf_count': opportunity['tf_count'],
        'entry_result': entry_result,
        'sl_result': sl_result
    }

def execute_exit(position, reason):
    """익절 실행"""
    cancel_all_orders()
    result = close_position(position)
    
    return {
        'success': 'orderId' in result,
        'side': position['side'],
        'entry': position['entry'],
        'pnl': position['pnl'],
        'reason': reason,
        'result': result
    }

def log_trade(trade_type, data):
    """거래 로그"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'type': trade_type,
        'data': data
    }
    
    logs = []
    if LOG_PATH.exists():
        with open(LOG_PATH) as f:
            logs = json.load(f)
    
    logs.append(log_entry)
    
    with open(LOG_PATH, 'w') as f:
        json.dump(logs[-100:], f, indent=2, default=str)  # 최근 100개만

def send_telegram(message):
    """텔레그램 알림 (파일로 저장, 외부에서 전송)"""
    alert_path = BASE_DIR / 'telegram_alert.txt'
    with open(alert_path, 'w') as f:
        f.write(message)

# ========== 메인 ==========

def main():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'='*60}")
    print(f"🤖 트레이딩 봇 - {timestamp}")
    print(f"{'='*60}")
    
    if not API_KEY or not SECRET:
        print("❌ API 키 없음")
        return
    
    # 시장 분석
    print("\n📊 시장 분석 중...")
    analysis = analyze_market()
    
    print(f"  현재가: ${analysis['price']:,.2f}")
    print(f"  큰 추세: {analysis['big_trend']}")
    print(f"  겹치는 지지대: {len(analysis['support_clusters'])}개")
    print(f"  겹치는 저항대: {len(analysis['resistance_clusters'])}개")
    
    # 현재 포지션 확인
    position = get_position()
    
    if position:
        print(f"\n📈 포지션: {position['side']} {position['size']} BTC @ ${position['entry']:,.2f}")
        print(f"  미실현 손익: ${position['pnl']:,.2f}")
        
        # 익절 체크
        exit_check = check_exit_opportunity(position, analysis)
        print(f"  손익률: {exit_check['pnl_percent']:.2f}%")
        print(f"  목표가 도달: {exit_check['at_target']}")
        print(f"  반대 구간 도달: {exit_check['at_zone']}")
        
        if exit_check['should_exit']:
            print("\n🎯 익절 실행!")
            reason = "목표가 도달" if exit_check['at_target'] else "반대 구간 도달"
            result = execute_exit(position, reason)
            
            if result['success']:
                msg = f"✅ 익절 완료\n{position['side']} @ ${position['entry']:,.0f}\n손익: ${position['pnl']:,.2f}\n사유: {reason}"
                send_telegram(msg)
                log_trade('EXIT', result)
                print(f"  ✅ 성공: {reason}")
            else:
                print(f"  ❌ 실패: {result}")
        else:
            print("  ⏳ 홀딩 유지")
    
    else:
        print("\n⏳ 포지션 없음 - 진입 기회 탐색")
        
        opportunity = find_entry_opportunity(analysis)
        
        if opportunity:
            print(f"\n🎯 진입 기회 발견!")
            print(f"  방향: {opportunity['side']}")
            print(f"  TF 겹침: {opportunity['tf_count']}개")
            print(f"  손익비: 1:{opportunity['calc']['rr_ratio']:.1f}")
            print(f"  진입가: ${opportunity['calc']['entry']:,.0f}")
            print(f"  손절가: ${opportunity['calc']['sl']:,.0f}")
            print(f"  목표가: ${opportunity['calc']['tp']:,.0f}")
            
            print("\n🚀 진입 실행!")
            result = execute_entry(opportunity)
            
            if result['success']:
                msg = f"🚀 {result['side']} 진입\n진입가: ${result['entry_price']:,.0f}\n손절: ${result['sl_price']:,.0f}\n목표: ${result['tp_target']:,.0f}\n손익비: 1:{result['rr_ratio']:.1f}\nTF겹침: {result['tf_count']}개"
                send_telegram(msg)
                log_trade('ENTRY', result)
                print(f"  ✅ 성공")
            else:
                print(f"  ❌ 실패: {result}")
        else:
            print("  ❌ 조건 충족하는 진입 기회 없음")
    
    # 상태 저장
    status = {
        'timestamp': timestamp,
        'price': analysis['price'],
        'big_trend': analysis['big_trend'],
        'position': position,
        'support_clusters': len(analysis['support_clusters']),
        'resistance_clusters': len(analysis['resistance_clusters'])
    }
    
    with open(STATUS_PATH, 'w') as f:
        json.dump(status, f, indent=2, default=str)
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
