#!/usr/bin/env python3
"""
SL/TP 최적화 - 수수료 반영
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

# 고정 설정
LEVERAGE = 12
INITIAL_BALANCE = 5000
RISK_PER_TRADE = 2.0
FEE_PCT = 0.04  # Taker 수수료

# 풀백 전략 파라미터
PULLBACK_PCT = 0.15
MAX_PULLBACK_PCT = 3.0
MIN_BODY_RATIO = 0.5
VOLUME_MULT = 1.0
COOLDOWN_BARS = 4
TREND_MA = 50

def load_data(table):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table} ORDER BY timestamp"
    cursor = conn.execute(query)
    data = [{'time': r[0], 'datetime': r[1], 'open': r[2], 'high': r[3], 
             'low': r[4], 'close': r[5], 'volume': r[6]} for r in cursor]
    conn.close()
    return data

class Backtest:
    def __init__(self, data_4h, data_15m, sl_pct, tp_pct):
        self.data_4h = data_4h
        self.data_15m = data_15m
        self.sl_pct = sl_pct
        self.tp_pct = tp_pct
        self.reset()
    
    def reset(self):
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.cooldown = 0
    
    def get_trend(self, idx_4h):
        if idx_4h < TREND_MA:
            return 'UNKNOWN'
        closes = [k['close'] for k in self.data_4h[idx_4h-TREND_MA:idx_4h]]
        ma = sum(closes) / len(closes)
        current = self.data_4h[idx_4h-1]['close']
        if current > ma * 1.005:
            return 'UP'
        elif current < ma * 0.995:
            return 'DOWN'
        return 'SIDEWAYS'
    
    def find_signal(self, idx_15m, trend):
        if idx_15m < 20 or self.cooldown > 0:
            return None
        
        curr = self.data_15m[idx_15m-1]
        prev = self.data_15m[idx_15m-2]
        
        # 거래량
        avg_vol = sum(k['volume'] for k in self.data_15m[idx_15m-20:idx_15m]) / 20
        if curr['volume'] < avg_vol * VOLUME_MULT:
            return None
        
        # 바디 비율
        body = abs(curr['close'] - curr['open'])
        total = curr['high'] - curr['low']
        if total == 0 or body / total < MIN_BODY_RATIO:
            return None
        
        price = curr['close']
        
        if trend == 'UP':
            if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                recent_high = max(k['high'] for k in self.data_15m[idx_15m-10:idx_15m-1])
                pullback = (recent_high - curr['low']) / recent_high * 100
                if PULLBACK_PCT < pullback < MAX_PULLBACK_PCT:
                    return {
                        'side': 'LONG', 'entry': price,
                        'sl': price * (1 - self.sl_pct / 100),
                        'tp': price * (1 + self.tp_pct / 100)
                    }
        
        elif trend == 'DOWN':
            if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                recent_low = min(k['low'] for k in self.data_15m[idx_15m-10:idx_15m-1])
                bounce = (curr['high'] - recent_low) / recent_low * 100
                if PULLBACK_PCT < bounce < MAX_PULLBACK_PCT:
                    return {
                        'side': 'SHORT', 'entry': price,
                        'sl': price * (1 + self.sl_pct / 100),
                        'tp': price * (1 - self.tp_pct / 100)
                    }
        
        return None
    
    def run_year(self, year):
        self.reset()
        
        year_4h = [k for k in self.data_4h if k['datetime'][:4] == year]
        year_15m = [k for k in self.data_15m if k['datetime'][:4] == year]
        
        if len(year_15m) < 1000:
            return None
        
        for i in range(100, len(year_15m)):
            curr = year_15m[i-1]
            curr_time = curr['time']
            
            # 4H 인덱스
            idx_4h = len([k for k in year_4h if k['time'] <= curr_time])
            if idx_4h < TREND_MA:
                continue
            
            self.cooldown = max(0, self.cooldown - 1)
            
            # 포지션 체크
            if self.position:
                candle = curr
                side = self.position['side']
                
                if side == 'LONG':
                    if candle['low'] <= self.position['sl']:
                        self._exit(self.position['sl'], 'SL')
                    elif candle['high'] >= self.position['tp']:
                        self._exit(self.position['tp'], 'TP')
                else:
                    if candle['high'] >= self.position['sl']:
                        self._exit(self.position['sl'], 'SL')
                    elif candle['low'] <= self.position['tp']:
                        self._exit(self.position['tp'], 'TP')
            
            # 진입 체크
            if not self.position:
                trend = self.get_trend(idx_4h)
                signal = self.find_signal(i, trend)
                if signal:
                    self._enter(signal)
            
            if self.balance <= 0:
                break
        
        if not self.trades:
            return None
        
        wins = len([t for t in self.trades if t['pnl'] > 0])
        
        # MDD
        peak = INITIAL_BALANCE
        max_dd = 0
        bal = INITIAL_BALANCE
        for t in self.trades:
            bal += t['pnl']
            if bal > peak:
                peak = bal
            dd = (peak - bal) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return {
            'trades': len(self.trades),
            'win_rate': wins / len(self.trades) * 100,
            'return_pct': (self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            'max_dd': max_dd
        }
    
    def _enter(self, signal):
        risk_amount = self.balance * (RISK_PER_TRADE / 100)
        sl_dist = abs(signal['entry'] - signal['sl'])
        qty = risk_amount / sl_dist if sl_dist > 0 else 0
        max_qty = (self.balance * LEVERAGE) / signal['entry']
        qty = min(qty, max_qty)
        
        self.position = {
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'qty': qty
        }
        self.cooldown = COOLDOWN_BARS
    
    def _exit(self, price, reason):
        entry = self.position['entry']
        qty = self.position['qty']
        
        if self.position['side'] == 'LONG':
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * qty
        
        # 수수료
        fee = (entry * qty + price * qty) * (FEE_PCT / 100)
        pnl -= fee
        
        self.balance += pnl
        self.trades.append({'pnl': pnl, 'reason': reason})
        self.position = None


def main():
    print("📥 데이터 로드 중...")
    data_4h = load_data('btc_4hour')
    data_15m = load_data('btc_15min')
    print(f"  4H: {len(data_4h):,}개 | 15M: {len(data_15m):,}개")
    
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    # SL/TP 그리드
    sl_range = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    tp_range = [1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    
    results = []
    
    print(f"\n🔍 {len(sl_range) * len(tp_range)}개 조합 테스트 중...\n")
    
    for sl in sl_range:
        for tp in tp_range:
            if tp <= sl:  # TP가 SL보다 커야 함
                continue
            
            bt = Backtest(data_4h, data_15m, sl, tp)
            
            yearly = {}
            all_positive = True
            
            for year in years:
                r = bt.run_year(year)
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
    
    # 정렬 (수익률 기준)
    results.sort(key=lambda x: x['avg_return'], reverse=True)
    
    print("=" * 70)
    print("📊 상위 10개 SL/TP 조합 (수수료 반영)")
    print("=" * 70)
    print(f"{'SL%':<6} {'TP%':<6} {'수익률':<10} {'거래수':<8} {'승률':<8} {'MDD':<8} {'전년도+':<8}")
    print("-" * 70)
    
    for r in results[:10]:
        all_pos = "✅" if r['all_positive'] else "❌"
        print(f"{r['sl']:<6} {r['tp']:<6} {r['avg_return']:>7.1f}%  {r['avg_trades']:>6.0f}  {r['avg_wr']:>6.1f}%  {r['max_dd']:>6.1f}%  {all_pos}")
    
    # 모든 연도 수익인 것만 필터
    positive_results = [r for r in results if r['all_positive']]
    
    if positive_results:
        print("\n" + "=" * 70)
        print("✅ 모든 연도 수익 달성 조합")
        print("=" * 70)
        for r in positive_results[:5]:
            print(f"\nSL: {r['sl']}% | TP: {r['tp']}%")
            print(f"평균 수익률: {r['avg_return']:.1f}% | 평균 거래: {r['avg_trades']:.0f}회 | MDD: {r['max_dd']:.1f}%")
            print("연도별:", end=" ")
            for y, d in r['yearly'].items():
                print(f"{y}:{d['return_pct']:+.0f}%", end=" ")
            print()
    else:
        print("\n⚠️ 모든 연도 수익 달성 조합 없음")
    
    # 결과 저장
    with open(Path(__file__).parent / 'sltp_optimization.json', 'w') as f:
        json.dump(results[:20], f, indent=2, default=str)
    
    print("\n결과 저장: sltp_optimization.json")

if __name__ == "__main__":
    main()
