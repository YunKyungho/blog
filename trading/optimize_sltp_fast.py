#!/usr/bin/env python3
"""
SL/TP 최적화 - 빠른 버전 (1시간봉 기준)
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

LEVERAGE = 12
INITIAL_BALANCE = 5000
RISK_PER_TRADE = 2.0
FEE_PCT = 0.04
TREND_MA = 50

def load_data(table):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table} ORDER BY timestamp"
    cursor = conn.execute(query)
    data = [{'time': r[0], 'datetime': r[1], 'open': r[2], 'high': r[3], 
             'low': r[4], 'close': r[5], 'volume': r[6]} for r in cursor]
    conn.close()
    return data

def backtest_year(data_4h, data_1h, sl_pct, tp_pct, year):
    year_4h = [k for k in data_4h if k['datetime'][:4] == year]
    year_1h = [k for k in data_1h if k['datetime'][:4] == year]
    
    if len(year_1h) < 500:
        return None
    
    balance = INITIAL_BALANCE
    position = None
    trades = []
    cooldown = 0
    
    for i in range(100, len(year_1h)):
        curr = year_1h[i-1]
        curr_time = curr['time']
        
        idx_4h = len([k for k in year_4h if k['time'] <= curr_time])
        if idx_4h < TREND_MA:
            continue
        
        cooldown = max(0, cooldown - 1)
        
        # 추세
        closes = [k['close'] for k in year_4h[max(0,idx_4h-TREND_MA):idx_4h]]
        if len(closes) < TREND_MA:
            continue
        ma = sum(closes) / len(closes)
        price = curr['close']
        
        if price > ma * 1.005:
            trend = 'UP'
        elif price < ma * 0.995:
            trend = 'DOWN'
        else:
            trend = 'SIDEWAYS'
        
        # 포지션 체크
        if position:
            if position['side'] == 'LONG':
                if curr['low'] <= position['sl']:
                    pnl = (position['sl'] - position['entry']) * position['qty']
                    fee = (position['entry'] + position['sl']) * position['qty'] * FEE_PCT / 100
                    balance += pnl - fee
                    trades.append({'pnl': pnl - fee})
                    position = None
                elif curr['high'] >= position['tp']:
                    pnl = (position['tp'] - position['entry']) * position['qty']
                    fee = (position['entry'] + position['tp']) * position['qty'] * FEE_PCT / 100
                    balance += pnl - fee
                    trades.append({'pnl': pnl - fee})
                    position = None
            else:
                if curr['high'] >= position['sl']:
                    pnl = (position['entry'] - position['sl']) * position['qty']
                    fee = (position['entry'] + position['sl']) * position['qty'] * FEE_PCT / 100
                    balance += pnl - fee
                    trades.append({'pnl': pnl - fee})
                    position = None
                elif curr['low'] <= position['tp']:
                    pnl = (position['entry'] - position['tp']) * position['qty']
                    fee = (position['entry'] + position['tp']) * position['qty'] * FEE_PCT / 100
                    balance += pnl - fee
                    trades.append({'pnl': pnl - fee})
                    position = None
        
        # 진입 체크
        if not position and cooldown == 0 and i >= 10:
            prev = year_1h[i-2]
            
            # 거래량
            avg_vol = sum(k['volume'] for k in year_1h[i-20:i]) / 20
            if curr['volume'] < avg_vol:
                continue
            
            # 바디
            body = abs(curr['close'] - curr['open'])
            total = curr['high'] - curr['low']
            if total == 0 or body / total < 0.5:
                continue
            
            signal = None
            
            if trend == 'UP' and prev['close'] < prev['open'] and curr['close'] > curr['open']:
                recent_high = max(k['high'] for k in year_1h[i-10:i-1])
                pullback = (recent_high - curr['low']) / recent_high * 100
                if 0.3 < pullback < 5:
                    signal = {'side': 'LONG', 'entry': price,
                              'sl': price * (1 - sl_pct/100), 'tp': price * (1 + tp_pct/100)}
            
            elif trend == 'DOWN' and prev['close'] > prev['open'] and curr['close'] < curr['open']:
                recent_low = min(k['low'] for k in year_1h[i-10:i-1])
                bounce = (curr['high'] - recent_low) / recent_low * 100
                if 0.3 < bounce < 5:
                    signal = {'side': 'SHORT', 'entry': price,
                              'sl': price * (1 + sl_pct/100), 'tp': price * (1 - tp_pct/100)}
            
            if signal:
                risk = balance * RISK_PER_TRADE / 100
                sl_dist = abs(signal['entry'] - signal['sl'])
                qty = risk / sl_dist if sl_dist > 0 else 0
                max_qty = (balance * LEVERAGE) / signal['entry']
                qty = min(qty, max_qty)
                
                position = {
                    'side': signal['side'], 'entry': signal['entry'],
                    'sl': signal['sl'], 'tp': signal['tp'], 'qty': qty
                }
                cooldown = 4
        
        if balance <= 0:
            break
    
    if not trades:
        return None
    
    wins = len([t for t in trades if t['pnl'] > 0])
    
    # MDD
    peak = INITIAL_BALANCE
    max_dd = 0
    bal = INITIAL_BALANCE
    for t in trades:
        bal += t['pnl']
        if bal > peak:
            peak = bal
        dd = (peak - bal) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
    
    return {
        'trades': len(trades),
        'win_rate': wins / len(trades) * 100,
        'return_pct': (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
        'max_dd': max_dd
    }

def main():
    print("📥 데이터 로드 중...")
    data_4h = load_data('btc_4hour')
    data_1h = load_data('btc_1hour')
    print(f"  4H: {len(data_4h):,}개 | 1H: {len(data_1h):,}개")
    
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    sl_range = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    tp_range = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    
    results = []
    total = sum(1 for sl in sl_range for tp in tp_range if tp > sl)
    count = 0
    
    print(f"\n🔍 {total}개 조합 테스트 중...\n")
    
    for sl in sl_range:
        for tp in tp_range:
            if tp <= sl:
                continue
            
            count += 1
            yearly = {}
            all_positive = True
            
            for year in years:
                r = backtest_year(data_4h, data_1h, sl, tp, year)
                if r:
                    yearly[year] = r
                    if r['return_pct'] < 0:
                        all_positive = False
            
            if not yearly:
                continue
            
            avg_return = sum(y['return_pct'] for y in yearly.values()) / len(yearly)
            avg_trades = sum(y['trades'] for y in yearly.values()) / len(yearly)
            avg_wr = sum(y['win_rate'] for y in yearly.values()) / len(yearly)
            max_dd = max(y['max_dd'] for y in yearly.values())
            
            results.append({
                'sl': sl, 'tp': tp,
                'avg_return': avg_return,
                'avg_trades': avg_trades,
                'avg_wr': avg_wr,
                'max_dd': max_dd,
                'all_positive': all_positive,
                'yearly': yearly
            })
            
            if count % 10 == 0:
                print(f"  진행: {count}/{total}")
    
    results.sort(key=lambda x: x['avg_return'], reverse=True)
    
    print("\n" + "=" * 70)
    print("📊 상위 10개 SL/TP 조합 (수수료 반영)")
    print("=" * 70)
    print(f"{'SL%':<6} {'TP%':<6} {'수익률':<10} {'거래수':<8} {'승률':<8} {'MDD':<8} {'전년도+':<8}")
    print("-" * 70)
    
    for r in results[:10]:
        all_pos = "✅" if r['all_positive'] else "❌"
        print(f"{r['sl']:<6} {r['tp']:<6} {r['avg_return']:>7.1f}%  {r['avg_trades']:>6.0f}  {r['avg_wr']:>6.1f}%  {r['max_dd']:>6.1f}%  {all_pos}")
    
    positive_results = [r for r in results if r['all_positive']]
    
    if positive_results:
        print("\n" + "=" * 70)
        print("✅ 모든 연도 수익 달성 조합")
        print("=" * 70)
        for r in positive_results[:5]:
            print(f"\nSL: {r['sl']}% | TP: {r['tp']}%")
            print(f"평균 수익률: {r['avg_return']:.1f}% | 거래: {r['avg_trades']:.0f}회 | MDD: {r['max_dd']:.1f}%")
            print("연도별:", end=" ")
            for y, d in sorted(r['yearly'].items()):
                print(f"{y}:{d['return_pct']:+.0f}%", end=" ")
            print()
    else:
        print("\n⚠️ 모든 연도 수익 달성 조합 없음")
    
    with open(Path(__file__).parent / 'sltp_optimization.json', 'w') as f:
        json.dump(results[:20], f, indent=2, default=str)
    
    print("\n결과 저장: sltp_optimization.json")

if __name__ == "__main__":
    main()
