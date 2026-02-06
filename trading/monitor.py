#!/usr/bin/env python3
"""
BTC 선물 트레이딩 모니터 - 쉽알남 전략 기반
자동으로 오더블록, FVG, 추세 분석 후 진입 신호 제공
"""

import requests
import json
from datetime import datetime
from pathlib import Path

SYMBOL = "BTCUSDT"
BASE_URL = "https://fapi.binance.com"

def get_klines(interval="15m", limit=50):
    """캔들 데이터 가져오기"""
    url = f"{BASE_URL}/fapi/v1/klines?symbol={SYMBOL}&interval={interval}&limit={limit}"
    resp = requests.get(url)
    data = resp.json()
    
    candles = []
    for d in data:
        candles.append({
            'time': datetime.fromtimestamp(d[0]/1000),
            'open': float(d[1]),
            'high': float(d[2]),
            'low': float(d[3]),
            'close': float(d[4]),
            'volume': float(d[5])
        })
    return candles

def get_current_price():
    """현재가 조회"""
    url = f"{BASE_URL}/fapi/v1/ticker/price?symbol={SYMBOL}"
    resp = requests.get(url)
    return float(resp.json()['price'])

def find_order_blocks(candles, count=3):
    """
    오더블록 찾기 (장악형 캔들)
    상승 장악형: 음봉을 완전히 감싸는 양봉 → 지지
    하락 장악형: 양봉을 완전히 감싸는 음봉 → 저항
    """
    order_blocks = []
    
    for i in range(1, len(candles)):
        prev = candles[i-1]
        curr = candles[i]
        
        prev_body_high = max(prev['open'], prev['close'])
        prev_body_low = min(prev['open'], prev['close'])
        curr_body_high = max(curr['open'], curr['close'])
        curr_body_low = min(curr['open'], curr['close'])
        
        # 상승 장악형 (Bullish Engulfing) - 지지 오더블록
        if prev['close'] < prev['open']:  # 이전 캔들 음봉
            if curr['close'] > curr['open']:  # 현재 캔들 양봉
                if curr_body_low <= prev_body_low and curr_body_high >= prev_body_high:
                    order_blocks.append({
                        'type': 'support',
                        'high': prev_body_high,
                        'low': prev_body_low,
                        'time': prev['time'],
                        'strength': 'strong' if curr['close'] > prev['high'] else 'normal'
                    })
        
        # 하락 장악형 (Bearish Engulfing) - 저항 오더블록
        if prev['close'] > prev['open']:  # 이전 캔들 양봉
            if curr['close'] < curr['open']:  # 현재 캔들 음봉
                if curr_body_low <= prev_body_low and curr_body_high >= prev_body_high:
                    order_blocks.append({
                        'type': 'resistance',
                        'high': prev_body_high,
                        'low': prev_body_low,
                        'time': prev['time'],
                        'strength': 'strong' if curr['close'] < prev['low'] else 'normal'
                    })
    
    return order_blocks[-count:] if len(order_blocks) > count else order_blocks

def find_fvg(candles, count=3):
    """
    FVG (Fair Value Gap) 찾기
    3개 캔들에서 1번과 3번 캔들이 겹치지 않는 구간
    """
    fvgs = []
    
    for i in range(2, len(candles)):
        c1 = candles[i-2]  # 첫 번째 캔들
        c2 = candles[i-1]  # 중간 캔들 (장대봉)
        c3 = candles[i]    # 세 번째 캔들
        
        # 상승 FVG: c1의 high < c3의 low
        if c1['high'] < c3['low']:
            fvgs.append({
                'type': 'support',
                'high': c3['low'],
                'low': c1['high'],
                'time': c2['time'],
                'gap': c3['low'] - c1['high']
            })
        
        # 하락 FVG: c1의 low > c3의 high
        if c1['low'] > c3['high']:
            fvgs.append({
                'type': 'resistance',
                'high': c1['low'],
                'low': c3['high'],
                'time': c2['time'],
                'gap': c1['low'] - c3['high']
            })
    
    return fvgs[-count:] if len(fvgs) > count else fvgs

def calculate_signal(price, candles_15m, candles_4h):
    """
    쉽알남 전략 기반 진입 신호 계산
    """
    ob_15m = find_order_blocks(candles_15m)
    ob_4h = find_order_blocks(candles_4h)
    fvg_15m = find_fvg(candles_15m)
    
    # 지지/저항 구간 수집
    support_levels = []
    resistance_levels = []
    
    for ob in ob_15m + ob_4h:
        if ob['type'] == 'support':
            support_levels.append(ob)
        else:
            resistance_levels.append(ob)
    
    for fvg in fvg_15m:
        if fvg['type'] == 'support':
            support_levels.append(fvg)
        else:
            resistance_levels.append(fvg)
    
    # 가장 가까운 지지/저항 찾기
    nearest_support = None
    nearest_resistance = None
    
    for s in support_levels:
        if s['high'] < price:
            if nearest_support is None or s['high'] > nearest_support['high']:
                nearest_support = s
    
    for r in resistance_levels:
        if r['low'] > price:
            if nearest_resistance is None or r['low'] < nearest_resistance['low']:
                nearest_resistance = r
    
    # 추세 판단 (4시간봉 기준)
    ma_7 = sum(c['close'] for c in candles_4h[-7:]) / 7
    ma_25 = sum(c['close'] for c in candles_4h[-25:]) / 25 if len(candles_4h) >= 25 else ma_7
    
    trend = 'bullish' if ma_7 > ma_25 else 'bearish'
    
    return {
        'price': price,
        'trend': trend,
        'ma_7': round(ma_7, 2),
        'ma_25': round(ma_25, 2),
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'order_blocks_15m': ob_15m,
        'order_blocks_4h': ob_4h,
        'fvg_15m': fvg_15m
    }

def generate_trade_signal(analysis):
    """
    매매 신호 생성
    """
    price = analysis['price']
    trend = analysis['trend']
    support = analysis['nearest_support']
    resistance = analysis['nearest_resistance']
    
    signal = {
        'action': 'WAIT',
        'reason': '',
        'entry': None,
        'stop_loss': None,
        'take_profit': None,
        'risk_reward': None
    }
    
    # 지지 근처에서 롱 신호
    if support and price < support['high'] * 1.005:  # 지지선 0.5% 이내
        if trend == 'bullish':
            signal['action'] = 'LONG'
            signal['reason'] = f"지지 오더블록 {support['high']:.0f} 근처 + 상승 추세"
            signal['entry'] = support['high']
            signal['stop_loss'] = support['low'] * 0.995
            signal['take_profit'] = price * 1.02  # 2% 목표
        else:
            signal['action'] = 'WAIT'
            signal['reason'] = f"지지 근처지만 하락 추세 - 확인 필요"
    
    # 저항 근처에서 숏 신호
    elif resistance and price > resistance['low'] * 0.995:  # 저항선 0.5% 이내
        if trend == 'bearish':
            signal['action'] = 'SHORT'
            signal['reason'] = f"저항 오더블록 {resistance['low']:.0f} 근처 + 하락 추세"
            signal['entry'] = resistance['low']
            signal['stop_loss'] = resistance['high'] * 1.005
            signal['take_profit'] = price * 0.98  # 2% 목표
        else:
            signal['action'] = 'WAIT'
            signal['reason'] = f"저항 근처지만 상승 추세 - 확인 필요"
    
    else:
        signal['action'] = 'WAIT'
        signal['reason'] = f"명확한 지지/저항 구간 아님. 다음 구간 대기"
        if support:
            signal['reason'] += f" | 지지: {support['high']:.0f}"
        if resistance:
            signal['reason'] += f" | 저항: {resistance['low']:.0f}"
    
    # 손익비 계산
    if signal['entry'] and signal['stop_loss'] and signal['take_profit']:
        risk = abs(signal['entry'] - signal['stop_loss'])
        reward = abs(signal['take_profit'] - signal['entry'])
        signal['risk_reward'] = round(reward / risk, 2) if risk > 0 else 0
    
    return signal

def run_monitor():
    """모니터 실행"""
    print(f"\n{'='*60}")
    print(f"🔍 BTC 트레이딩 모니터 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # 데이터 수집
    price = get_current_price()
    candles_15m = get_klines('15m', 50)
    candles_4h = get_klines('4h', 30)
    
    # 분석
    analysis = calculate_signal(price, candles_15m, candles_4h)
    signal = generate_trade_signal(analysis)
    
    # 출력
    print(f"📊 현재가: ${price:,.2f}")
    print(f"📈 추세: {analysis['trend'].upper()}")
    print(f"📉 MA7: ${analysis['ma_7']:,.2f} | MA25: ${analysis['ma_25']:,.2f}")
    print()
    
    print("🔷 15분봉 오더블록:")
    for ob in analysis['order_blocks_15m']:
        t = '지지' if ob['type'] == 'support' else '저항'
        print(f"   - {t}: ${ob['low']:,.0f} ~ ${ob['high']:,.0f} ({ob['strength']})")
    
    print("\n🔷 4시간봉 오더블록:")
    for ob in analysis['order_blocks_4h']:
        t = '지지' if ob['type'] == 'support' else '저항'
        print(f"   - {t}: ${ob['low']:,.0f} ~ ${ob['high']:,.0f} ({ob['strength']})")
    
    print("\n🔷 15분봉 FVG:")
    for fvg in analysis['fvg_15m']:
        t = '지지' if fvg['type'] == 'support' else '저항'
        print(f"   - {t}: ${fvg['low']:,.0f} ~ ${fvg['high']:,.0f} (갭: ${fvg['gap']:,.0f})")
    
    print(f"\n{'='*60}")
    print(f"🎯 매매 신호: {signal['action']}")
    print(f"📝 이유: {signal['reason']}")
    
    if signal['entry']:
        print(f"\n   진입가: ${signal['entry']:,.0f}")
        print(f"   손절가: ${signal['stop_loss']:,.0f}")
        print(f"   익절가: ${signal['take_profit']:,.0f}")
        print(f"   손익비: 1:{signal['risk_reward']}")
    
    print(f"{'='*60}\n")
    
    # 결과 저장
    result = {
        'timestamp': datetime.now().isoformat(),
        'price': price,
        'analysis': {
            'trend': analysis['trend'],
            'ma_7': analysis['ma_7'],
            'ma_25': analysis['ma_25']
        },
        'signal': signal
    }
    
    result_path = Path(__file__).parent / 'latest_signal.json'
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    return signal

if __name__ == "__main__":
    run_monitor()
