#!/usr/bin/env python3
"""
포지션 진입 스크립트
- 전체 잔고를 마진으로 사용
- 20배 레버리지
- 손절가 자동 설정 (마진 대비 10% 손실)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from auto_trader import (
    get_balance, get_current_price, get_position,
    calculate_quantity, calculate_stop_loss, set_leverage,
    place_order, SYMBOL, LEVERAGE, MAX_LOSS_PERCENT, MIN_RR_RATIO
)
from datetime import datetime
import json

def enter_market(side, reason="차트 분석 기반 진입"):
    """
    시장가 진입
    side: 'LONG' 또는 'SHORT'
    """
    # 기존 포지션 확인
    pos = get_position()
    if pos and pos['amount'] != 0:
        print(f"❌ 이미 포지션 보유 중: {pos['amount']} BTC")
        return None
    
    # 잔고 및 가격 조회
    balance = get_balance()
    price = get_current_price()
    
    # 레버리지 설정
    set_leverage(LEVERAGE)
    
    # 수량 계산 (전체 잔고 기준)
    quantity = calculate_quantity(balance, price)
    
    # 손절가 계산
    sl_price = calculate_stop_loss(price, side)
    
    # 진입 주문
    order_side = 'BUY' if side == 'LONG' else 'SELL'
    entry_result = place_order(order_side, 'MARKET', quantity)
    
    if 'orderId' not in entry_result:
        print(f"❌ 진입 실패: {entry_result}")
        return None
    
    # 손절 주문
    sl_side = 'SELL' if side == 'LONG' else 'BUY'
    sl_result = place_order(sl_side, 'STOP_MARKET', quantity, stop_price=sl_price, reduce_only=True)
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'side': side,
        'entry_price': price,
        'quantity': quantity,
        'margin': balance,
        'leverage': LEVERAGE,
        'notional': balance * LEVERAGE,
        'stop_loss': sl_price,
        'max_loss_percent': MAX_LOSS_PERCENT,
        'reason': reason
    }
    
    print(f"\n{'='*60}")
    print(f"✅ {side} 포지션 진입 완료")
    print(f"{'='*60}")
    print(f"📊 진입가: ${price:,.2f}")
    print(f"📦 수량: {quantity} BTC")
    print(f"💰 마진: ${balance:,.2f} (레버리지 {LEVERAGE}x)")
    print(f"📈 포지션 가치: ${balance * LEVERAGE:,.2f}")
    print(f"🛑 손절가: ${sl_price:,.1f} (마진 대비 -{MAX_LOSS_PERCENT}%)")
    print(f"📝 사유: {reason}")
    print(f"{'='*60}\n")
    
    return result


def enter_limit(side, price, reason="차트 분석 기반 진입"):
    """
    지정가 진입
    side: 'LONG' 또는 'SHORT'
    price: 진입 희망가
    """
    # 기존 포지션 확인
    pos = get_position()
    if pos and pos['amount'] != 0:
        print(f"❌ 이미 포지션 보유 중: {pos['amount']} BTC")
        return None
    
    # 잔고 조회
    balance = get_balance()
    
    # 레버리지 설정
    set_leverage(LEVERAGE)
    
    # 수량 계산 (전체 잔고 기준)
    quantity = calculate_quantity(balance, price)
    
    # 손절가 계산
    sl_price = calculate_stop_loss(price, side)
    
    # 진입 주문
    order_side = 'BUY' if side == 'LONG' else 'SELL'
    entry_result = place_order(order_side, 'LIMIT', quantity, price=price)
    
    if 'orderId' not in entry_result:
        print(f"❌ 주문 실패: {entry_result}")
        return None
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'side': side,
        'entry_price': price,
        'quantity': quantity,
        'margin': balance,
        'leverage': LEVERAGE,
        'notional': balance * LEVERAGE,
        'stop_loss': sl_price,
        'max_loss_percent': MAX_LOSS_PERCENT,
        'reason': reason,
        'order_type': 'LIMIT'
    }
    
    print(f"\n{'='*60}")
    print(f"📝 {side} 지정가 주문 등록")
    print(f"{'='*60}")
    print(f"📊 진입가: ${price:,.2f}")
    print(f"📦 수량: {quantity} BTC")
    print(f"💰 마진: ${balance:,.2f} (레버리지 {LEVERAGE}x)")
    print(f"📈 포지션 가치: ${balance * LEVERAGE:,.2f}")
    print(f"🛑 체결 시 손절가: ${sl_price:,.1f} (마진 대비 -{MAX_LOSS_PERCENT}%)")
    print(f"📝 사유: {reason}")
    print(f"{'='*60}\n")
    
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법:")
        print("  시장가: python enter_position.py LONG|SHORT [사유]")
        print("  지정가: python enter_position.py LONG|SHORT 가격 [사유]")
        sys.exit(1)
    
    side = sys.argv[1].upper()
    if side not in ['LONG', 'SHORT']:
        print("❌ side는 LONG 또는 SHORT")
        sys.exit(1)
    
    if len(sys.argv) >= 3:
        try:
            price = float(sys.argv[2])
            reason = sys.argv[3] if len(sys.argv) > 3 else "차트 분석 기반 진입"
            enter_limit(side, price, reason)
        except ValueError:
            reason = sys.argv[2]
            enter_market(side, reason)
    else:
        enter_market(side)
