#!/usr/bin/env python3
"""
BTC 자동 트레이더 - 쉽알남 전략
- 전체 잔고를 마진으로 사용
- 20배 레버리지
- 마진 대비 10% 손실 기준 손절
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

# 설정 로드
CONFIG_PATH = Path(__file__).parent / 'config.json'
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

SYMBOL = CONFIG.get('symbol', 'BTCUSDT')
LEVERAGE = CONFIG.get('leverage', 20)
MAX_LOSS_PERCENT = CONFIG.get('risk', {}).get('max_loss_percent', 10)
MIN_RR_RATIO = CONFIG.get('min_rr_ratio', 2.0)

def get_signature(query_string):
    return hmac.new(SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def api_request(method, endpoint, params=None):
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = '&'.join(f"{k}={v}" for k, v in params.items())
    signature = get_signature(query)
    url = f"{BASE_URL}{endpoint}?{query}&signature={signature}"
    headers = {'X-MBX-APIKEY': API_KEY}
    
    if method == 'GET':
        resp = requests.get(url, headers=headers)
    elif method == 'POST':
        resp = requests.post(url, headers=headers)
    elif method == 'DELETE':
        resp = requests.delete(url, headers=headers)
    
    return resp.json()

def get_balance():
    """USDT 잔고 조회"""
    result = api_request('GET', '/fapi/v2/balance')
    for bal in result:
        if bal['asset'] == 'USDT':
            return float(bal['balance'])
    return 0

def get_current_price():
    """현재가 조회"""
    result = requests.get(f"{BASE_URL}/fapi/v1/ticker/price?symbol={SYMBOL}").json()
    return float(result['price'])

def get_position():
    """현재 포지션 조회"""
    result = api_request('GET', '/fapi/v2/positionRisk')
    for pos in result:
        if pos['symbol'] == SYMBOL:
            return {
                'amount': float(pos['positionAmt']),
                'entry_price': float(pos['entryPrice']),
                'unrealized_pnl': float(pos['unRealizedProfit']),
                'leverage': int(pos['leverage']),
                'mark_price': float(pos['markPrice'])
            }
    return None

def get_open_orders():
    """열린 주문 조회"""
    return api_request('GET', '/fapi/v1/openOrders', {'symbol': SYMBOL})

def set_leverage(leverage=LEVERAGE):
    """레버리지 설정"""
    return api_request('POST', '/fapi/v1/leverage', {
        'symbol': SYMBOL,
        'leverage': leverage
    })

def calculate_quantity(balance, price, leverage=LEVERAGE):
    """
    전체 잔고 기준 주문 수량 계산
    - 전체 잔고를 마진으로 사용
    - 레버리지 20배 적용
    """
    notional = balance * leverage
    quantity = notional / price
    # BTC는 소수점 3자리까지
    return round(quantity, 3)

def calculate_stop_loss(entry_price, side, leverage=LEVERAGE):
    """
    손절가 계산 (마진 대비 10% 손실 기준)
    - 레버리지 20배 → 가격 0.5% 변동 = 마진 10% 손실
    """
    sl_percent = MAX_LOSS_PERCENT / leverage  # 10% / 20 = 0.5%
    sl_distance = entry_price * (sl_percent / 100)
    
    if side == 'LONG':
        return round(entry_price - sl_distance, 1)
    else:  # SHORT
        return round(entry_price + sl_distance, 1)

def place_order(side, order_type, quantity, price=None, stop_price=None, reduce_only=False):
    """주문 실행"""
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

def cancel_all_orders():
    """모든 주문 취소"""
    return api_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': SYMBOL})

def close_position():
    """포지션 시장가 청산"""
    pos = get_position()
    if pos and pos['amount'] != 0:
        qty = abs(pos['amount'])
        side = 'SELL' if pos['amount'] > 0 else 'BUY'
        result = api_request('POST', '/fapi/v1/order', {
            'symbol': SYMBOL,
            'side': side,
            'type': 'MARKET',
            'quantity': qty,
            'reduceOnly': 'true'
        })
        print(f"✅ 포지션 청산: {side} {qty} BTC")
        return result
    return None

def set_stop_loss_order(pos):
    """손절 주문 설정"""
    qty = abs(pos['amount'])
    entry = pos['entry_price']
    side = 'LONG' if pos['amount'] > 0 else 'SHORT'
    
    sl_price = calculate_stop_loss(entry, side)
    sl_side = 'SELL' if side == 'LONG' else 'BUY'
    
    result = place_order(sl_side, 'STOP_MARKET', qty, stop_price=sl_price, reduce_only=True)
    return sl_price, result

def check_and_manage():
    """포지션 체크 및 관리"""
    pos = get_position()
    orders = get_open_orders()
    balance = get_balance()
    current_price = get_current_price()
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'balance': balance,
        'current_price': current_price,
        'position': None,
        'action': None
    }
    
    # 레버리지 확인 및 설정
    if pos and pos['leverage'] != LEVERAGE:
        set_leverage(LEVERAGE)
        print(f"⚙️ 레버리지 {LEVERAGE}x로 설정")
    
    if pos and pos['amount'] != 0:
        side = 'LONG' if pos['amount'] > 0 else 'SHORT'
        result['position'] = {
            'side': side,
            'size': abs(pos['amount']),
            'entry': pos['entry_price'],
            'pnl': pos['unrealized_pnl'],
            'pnl_percent': (pos['unrealized_pnl'] / balance) * 100 if balance > 0 else 0
        }
        
        # 손절 주문 확인
        has_sl = any(o['type'] in ['STOP_MARKET', 'STOP'] for o in orders)
        
        if not has_sl:
            sl_price, sl_result = set_stop_loss_order(pos)
            sl_percent = MAX_LOSS_PERCENT / pos['leverage']
            result['action'] = f"손절 설정: ${sl_price:,.1f} (진입가 대비 {sl_percent:.2f}%, 마진 대비 -{MAX_LOSS_PERCENT}%)"
            print(f"✅ 손절 주문 설정: ${sl_price:,.1f}")
        
        # 익절 분석 필요 플래그
        has_tp = any(o['type'] in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT'] for o in orders)
        if not has_tp:
            result['needs_exit_analysis'] = True
    
    else:
        result['position'] = None
        result['action'] = "포지션 없음 - 진입 대기 중"
        
        # 진입 시 사용할 수량 계산
        qty = calculate_quantity(balance, current_price)
        result['next_order'] = {
            'margin': balance,
            'leverage': LEVERAGE,
            'quantity': qty,
            'notional': balance * LEVERAGE
        }
    
    # 결과 저장
    result_path = Path(__file__).parent / 'position_status.json'
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    return result

def main():
    print(f"\n{'='*60}")
    print(f"📊 BTC 트레이더 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    if not API_KEY or not SECRET:
        print("❌ API 키 없음!")
        return
    
    result = check_and_manage()
    
    print(f"💰 잔고: ${result['balance']:,.2f} USDT")
    print(f"📈 BTC 현재가: ${result['current_price']:,.2f}")
    print(f"⚙️ 레버리지: {LEVERAGE}x | 최대 손실: {MAX_LOSS_PERCENT}%")
    
    if result['position']:
        p = result['position']
        pnl_sign = '+' if p['pnl'] >= 0 else ''
        print(f"\n📊 포지션: {p['side']} {p['size']} BTC @ ${p['entry']:,.2f}")
        print(f"💵 손익: {pnl_sign}${p['pnl']:,.2f} ({pnl_sign}{p['pnl_percent']:.2f}%)")
    else:
        print(f"\n⏳ 포지션 없음")
        if 'next_order' in result:
            n = result['next_order']
            print(f"📋 다음 주문 예상:")
            print(f"   - 마진: ${n['margin']:,.2f}")
            print(f"   - 레버리지: {n['leverage']}x")
            print(f"   - 포지션 크기: {n['quantity']} BTC (${n['notional']:,.2f})")
    
    if result.get('action'):
        print(f"\n🎯 액션: {result['action']}")
    
    # 열린 주문 표시
    orders = get_open_orders()
    if orders:
        print(f"\n📋 대기 주문 ({len(orders)}개):")
        for o in orders:
            price = o.get('price') or o.get('stopPrice')
            print(f"   - {o['side']} {o['type']} @ ${float(price):,.1f}")
    
    print(f"\n{'='*60}\n")
    
    return result

if __name__ == "__main__":
    main()
