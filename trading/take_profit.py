#!/usr/bin/env python3
"""
익절 실행 스크립트
하루가 차트 분석 후 익절 결정하면 이 스크립트 실행
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from auto_trader import get_position, close_position, cancel_all_orders
from datetime import datetime

def execute_take_profit(reason="차트 분석 기반 익절"):
    """익절 실행 및 기록"""
    pos = get_position()
    
    if not pos or pos['amount'] == 0:
        print("❌ 청산할 포지션이 없습니다")
        return None
    
    # 포지션 정보 저장
    result = {
        'timestamp': datetime.now().isoformat(),
        'side': 'LONG' if pos['amount'] > 0 else 'SHORT',
        'entry_price': pos['entry_price'],
        'size': abs(pos['amount']),
        'pnl_before_close': pos['unrealized_pnl'],
        'reason': reason
    }
    
    # 기존 주문 취소
    cancel_all_orders()
    print("🗑️ 기존 주문 취소")
    
    # 시장가 청산
    close_result = close_position()
    
    if close_result:
        result['status'] = 'success'
        print(f"\n{'='*50}")
        print(f"✅ 익절 완료!")
        print(f"📊 {result['side']} {result['size']} BTC @ ${result['entry_price']:,.2f}")
        print(f"💰 예상 손익: ${result['pnl_before_close']:,.2f}")
        print(f"📝 사유: {reason}")
        print(f"{'='*50}\n")
    else:
        result['status'] = 'failed'
    
    return result

if __name__ == "__main__":
    reason = sys.argv[1] if len(sys.argv) > 1 else "차트 분석 기반 익절"
    execute_take_profit(reason)
