#!/usr/bin/env python3
"""
백테스팅 v4 - 최종 최적화
목표: 수익률 높이기 (현재 444% → 목표 480%+)
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

INITIAL_BALANCE = 5000

class StrategyParams:
    def __init__(self):
        self.leverage = 10
        self.risk_per_trade = 2.0
        self.trend_ma = 50
        self.entry_tf = '15m'
        self.pullback_pct = 0.2
        self.min_body_ratio = 0.5
        self.sl_pct = 0.7
        self.tp_pct = 1.0
        self.cooldown_bars = 2
        self.volume_filter = True
        self.volume_mult = 1.0


def load_data(table):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table} ORDER BY timestamp"
    cursor = conn.execute(query)
    data = []
    for row in cursor:
        data.append({
            'time': row[0], 'datetime': row[1], 'open': row[2],
            'high': row[3], 'low': row[4], 'close': row[5], 'volume': row[6]
        })
    conn.close()
    return data


class BacktestV4:
    def __init__(self, data_4h, data_1h, data_15m, params=None):
        self.data_4h = data_4h
        self.data_1h = data_1h
        self.data_15m = data_15m
        self.params = params or StrategyParams()
        
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.cooldown = 0
        self.signal_count = {'LONG': 0, 'SHORT': 0}
    
    def get_trend(self, klines, ma_period):
        if len(klines) < ma_period:
            return 'UNKNOWN'
        
        closes = [k['close'] for k in klines[-ma_period:]]
        ma = sum(closes) / len(closes)
        current = klines[-1]['close']
        
        if current > ma * 1.005:
            return 'UP'
        elif current < ma * 0.995:
            return 'DOWN'
        return 'SIDEWAYS'
    
    def find_pullback_entry(self, klines, trend):
        if len(klines) < 10:
            return None
        
        curr = klines[-1]
        prev = klines[-2]
        
        if self.params.volume_filter:
            avg_vol = sum(k['volume'] for k in klines[-20:]) / 20
            if curr['volume'] < avg_vol * self.params.volume_mult:
                return None
        
        body = abs(curr['close'] - curr['open'])
        total = curr['high'] - curr['low']
        if total == 0 or body / total < self.params.min_body_ratio:
            return None
        
        price = curr['close']
        
        if trend == 'UP':
            if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                recent_high = max(k['high'] for k in klines[-10:-1])
                pullback = (recent_high - curr['low']) / recent_high * 100
                
                if self.params.pullback_pct < pullback < 3.0:
                    return {
                        'side': 'LONG',
                        'entry': price,
                        'sl': price * (1 - self.params.sl_pct / 100),
                        'tp': price * (1 + self.params.tp_pct / 100)
                    }
        
        elif trend == 'DOWN':
            if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                recent_low = min(k['low'] for k in klines[-10:-1])
                bounce = (curr['high'] - recent_low) / recent_low * 100
                
                if self.params.pullback_pct < bounce < 3.0:
                    return {
                        'side': 'SHORT',
                        'entry': price,
                        'sl': price * (1 + self.params.sl_pct / 100),
                        'tp': price * (1 - self.params.tp_pct / 100)
                    }
        
        return None
    
    def execute_entry(self, signal, dt):
        risk_amount = self.balance * (self.params.risk_per_trade / 100)
        sl_distance = abs(signal['entry'] - signal['sl'])
        qty = risk_amount / sl_distance if sl_distance > 0 else 0
        max_qty = (self.balance * self.params.leverage) / signal['entry']
        qty = min(qty, max_qty)
        
        self.position = {
            'side': signal['side'], 'entry': signal['entry'],
            'sl': signal['sl'], 'tp': signal['tp'],
            'quantity': qty, 'datetime': dt
        }
        
        self.signal_count[signal['side']] += 1
        self.cooldown = self.params.cooldown_bars
    
    def check_exit(self, candle):
        if not self.position:
            return None
        
        side = self.position['side']
        sl = self.position['sl']
        tp = self.position['tp']
        
        if side == 'LONG':
            if candle['low'] <= sl:
                return ('SL', sl)
            if candle['high'] >= tp:
                return ('TP', tp)
        else:
            if candle['high'] >= sl:
                return ('SL', sl)
            if candle['low'] <= tp:
                return ('TP', tp)
        
        return None
    
    def execute_exit(self, price, reason, dt):
        entry = self.position['entry']
        qty = self.position['quantity']
        
        if self.position['side'] == 'LONG':
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * qty
        
        pnl_pct = (pnl / self.balance) * 100
        self.balance += pnl
        
        self.trades.append({
            'side': self.position['side'], 'entry': entry, 'exit': price,
            'entry_time': self.position['datetime'], 'exit_time': dt,
            'pnl': pnl, 'pnl_pct': pnl_pct, 'reason': reason,
            'balance_after': self.balance
        })
        
        self.position = None
    
    def run(self, check_interval=1):
        for i in range(200, len(self.data_15m), check_interval):
            current = self.data_15m[i]
            dt = current['datetime']
            
            klines_4h = [k for k in self.data_4h if k['time'] <= current['time']][-100:]
            klines_15m = self.data_15m[max(0, i-50):i+1]
            
            if len(klines_4h) < self.params.trend_ma or len(klines_15m) < 20:
                continue
            
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            if self.cooldown > 0:
                self.cooldown -= 1
            
            if not self.position and self.cooldown == 0:
                trend = self.get_trend(klines_4h, self.params.trend_ma)
                
                if trend in ['UP', 'DOWN']:
                    signal = self.find_pullback_entry(klines_15m, trend)
                    if signal:
                        self.execute_entry(signal, dt)
            
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()
    
    def get_results(self):
        if not self.trades:
            return {'total_trades': 0, 'win_rate': 0, 'return_pct': 0, 'max_drawdown': 0, 'signal_count': self.signal_count}
        
        wins = [t for t in self.trades if t['pnl'] > 0]
        
        peak = INITIAL_BALANCE
        max_dd = 0
        for e in self.equity_curve:
            if e['balance'] > peak:
                peak = e['balance']
            dd = (peak - e['balance']) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return {
            'total_trades': len(self.trades),
            'wins': len(wins),
            'losses': len(self.trades) - len(wins),
            'win_rate': len(wins) / len(self.trades) * 100,
            'total_pnl': sum(t['pnl'] for t in self.trades),
            'final_balance': self.balance,
            'return_pct': (self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            'max_drawdown': max_dd,
            'signal_count': self.signal_count
        }


def run_yearly_test(params):
    data_4h = load_data('btc_4hour')
    data_1h = load_data('btc_1hour')
    data_15m = load_data('btc_15min')
    
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    results = []
    
    for year in years:
        year_4h = [k for k in data_4h if k['datetime'][:4] == year]
        year_1h = [k for k in data_1h if k['datetime'][:4] == year]
        year_15m = [k for k in data_15m if k['datetime'][:4] == year]
        
        if len(year_15m) < 1000:
            continue
        
        bt = BacktestV4(year_4h, year_1h, year_15m, params)
        result = bt.run()
        result['year'] = year
        results.append(result)
    
    return results


def print_results(results, title=""):
    print(f"\n{'='*80}")
    print(f"📊 {title}")
    print("=" * 80)
    print(f"{'연도':<6} {'거래':<8} {'승률':<8} {'수익률':<12} {'DD':<10} {'롱/숏':<12} {'최종자산':<12}")
    print("-" * 80)
    
    all_profitable = True
    min_wr = 100
    max_dd = 0
    total_return = 0
    total_trades = 0
    
    for r in results:
        sig = r.get('signal_count', {'LONG': 0, 'SHORT': 0})
        print(f"{r['year']:<6} {r['total_trades']:<8} {r['win_rate']:.1f}%{'':<3} "
              f"{r['return_pct']:.1f}%{'':<6} {r['max_drawdown']:.1f}%{'':<5} "
              f"{sig['LONG']}/{sig['SHORT']:<6} ${r.get('final_balance', 0):,.0f}")
        
        if r['return_pct'] < 0:
            all_profitable = False
        if r['win_rate'] > 0 and r['win_rate'] < min_wr:
            min_wr = r['win_rate']
        if r['max_drawdown'] > max_dd:
            max_dd = r['max_drawdown']
        total_return += r['return_pct']
        total_trades += r['total_trades']
    
    print("-" * 80)
    avg_trades = total_trades / len(results) if results else 0
    avg_return = total_return / len(results) if results else 0
    monthly_return = avg_return / 12
    print(f"평균: {avg_trades:.0f}회/년 | 승률≥{min_wr:.1f}% | 연 {avg_return:.1f}% | 월 {monthly_return:.1f}% | DD≤{max_dd:.1f}%")
    print(f"모든 연도 수익: {'✅ YES' if all_profitable else '❌ NO'}")
    
    return all_profitable, min_wr, max_dd, avg_trades, avg_return


def final_optimization():
    """수익률 최적화"""
    print("📥 최종 최적화 시작...")
    
    # 더 높은 수익률을 위한 파라미터
    param_grid = [
        # 레버리지 높이기
        {'leverage': 12, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.2, 'cooldown': 2},
        {'leverage': 15, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.2, 'cooldown': 2},
        # TP 높이기
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.2, 'pullback_pct': 0.2, 'cooldown': 2},
        {'leverage': 12, 'sl_pct': 0.7, 'tp_pct': 1.2, 'pullback_pct': 0.2, 'cooldown': 2},
        # 쿨다운 줄이기
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.2, 'cooldown': 1},
        {'leverage': 12, 'sl_pct': 0.6, 'tp_pct': 0.9, 'pullback_pct': 0.2, 'cooldown': 1},
        # 공격적 설정
        {'leverage': 15, 'sl_pct': 0.6, 'tp_pct': 0.9, 'pullback_pct': 0.15, 'cooldown': 1},
        {'leverage': 12, 'sl_pct': 0.5, 'tp_pct': 0.8, 'pullback_pct': 0.15, 'cooldown': 1},
    ]
    
    best_result = None
    best_score = 0
    
    for pg in param_grid:
        params = StrategyParams()
        params.leverage = pg['leverage']
        params.sl_pct = pg['sl_pct']
        params.tp_pct = pg['tp_pct']
        params.pullback_pct = pg['pullback_pct']
        params.cooldown_bars = pg['cooldown']
        
        results = run_yearly_test(params)
        name = f"lev{pg['leverage']}_sl{pg['sl_pct']}_tp{pg['tp_pct']}_pb{pg['pullback_pct']}_cd{pg['cooldown']}"
        
        all_profitable, min_wr, max_dd, avg_trades, avg_return = print_results(results, name)
        
        # 점수: 수익률 최대화 + 조건 충족
        score = avg_return
        if not all_profitable:
            score -= 1000
        if min_wr < 40:
            score -= 200
        if max_dd > 40:
            score -= 100
        
        if score > best_score:
            best_score = score
            best_result = {
                'name': name,
                'params': pg,
                'results': results,
                'all_profitable': all_profitable,
                'min_wr': min_wr,
                'max_dd': max_dd,
                'avg_return': avg_return
            }
    
    if best_result:
        print("\n" + "=" * 80)
        print("🏆 최종 최적 전략")
        print("=" * 80)
        print(f"전략: {best_result['name']}")
        print(f"파라미터: {best_result['params']}")
        print(f"모든연도수익: {best_result['all_profitable']}")
        print(f"승률: {best_result['min_wr']:.1f}%+")
        print(f"최대DD: {best_result['max_dd']:.1f}%")
        print(f"연 수익률: {best_result['avg_return']:.1f}%")
        print(f"월 수익률: {best_result['avg_return']/12:.1f}%")
        
        # 저장
        with open(Path(__file__).parent / 'final_strategy.json', 'w') as f:
            json.dump(best_result, f, indent=2, default=str)
    
    return best_result


if __name__ == "__main__":
    final_optimization()
