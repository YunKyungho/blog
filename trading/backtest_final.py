#!/usr/bin/env python3
"""
BTC 트레이딩 전략 FINAL - 최적화 버전

최고 전략 2개 결합 + 파라미터 최적화:
1. Adaptive Momentum (수익률 최고)
2. Dual Momentum (안정성 최고)

목표:
- 거래수: 연 300-400회
- 승률: 40%+
- 월 수익률: 40%+
- 최대낙폭: 40% 이하
- 모든 연도 안정적
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from itertools import product

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

INITIAL_BALANCE = 10000
RISK_PER_TRADE = 0.02
MAX_LEVERAGE = 5

def load_data(table, year=None):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table}"
    if year:
        query += f" WHERE datetime LIKE '{year}%'"
    query += " ORDER BY timestamp"
    cursor = conn.execute(query)
    data = [{'time': r[0], 'datetime': r[1], 'open': r[2], 'high': r[3], 
             'low': r[4], 'close': r[5], 'volume': r[6]} for r in cursor]
    conn.close()
    return data

# ========== 지표 ==========

def sma(data, period, idx):
    if idx < period: return None
    return sum(d['close'] for d in data[idx-period:idx]) / period

def ema(data, period, idx):
    if idx < period: return None
    mult = 2 / (period + 1)
    e = data[0]['close']
    for i in range(1, idx + 1):
        e = (data[i]['close'] - e) * mult + e
    return e

def atr(data, period, idx):
    if idx < period + 1: return None
    tr_list = []
    for i in range(idx - period, idx):
        h, l = data[i]['high'], data[i]['low']
        pc = data[i-1]['close'] if i > 0 else data[i]['open']
        tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(tr_list) / period

def rsi(data, period, idx):
    if idx < period + 1: return None
    gains, losses = [], []
    for i in range(idx - period, idx):
        change = data[i+1]['close'] - data[i]['close']
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0: return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def momentum(data, period, idx):
    if idx < period: return None
    prev = data[idx - period]['close']
    return (data[idx]['close'] - prev) / prev * 100 if prev else 0

def bbands(data, period, idx, std_mult=2):
    if idx < period: return None, None, None
    closes = [d['close'] for d in data[idx-period:idx]]
    mid = sum(closes) / period
    std = (sum((c - mid)**2 for c in closes) / period) ** 0.5
    return mid + std * std_mult, mid, mid - std * std_mult

def adx(data, period, idx):
    if idx < period * 2 + 1: return None
    plus_dm, minus_dm, tr_vals = [], [], []
    for i in range(idx - period * 2, idx):
        if i < 1: continue
        h, l = data[i]['high'], data[i]['low']
        ph, pl, pc = data[i-1]['high'], data[i-1]['low'], data[i-1]['close']
        up = h - ph
        down = pl - l
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
        tr_vals.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not tr_vals or sum(tr_vals[-period:]) == 0: return 0
    smooth_plus = sum(plus_dm[-period:])
    smooth_minus = sum(minus_dm[-period:])
    smooth_tr = sum(tr_vals[-period:])
    plus_di = 100 * smooth_plus / smooth_tr
    minus_di = 100 * smooth_minus / smooth_tr
    if plus_di + minus_di == 0: return 0
    return 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

def donchian(data, period, idx):
    if idx < period: return None, None
    return max(d['high'] for d in data[idx-period:idx]), min(d['low'] for d in data[idx-period:idx])


# ========== 백테스터 ==========

class Backtester:
    def __init__(self, data, risk_pct=RISK_PER_TRADE, max_lev=MAX_LEVERAGE):
        self.data = data
        self.risk_pct = risk_pct
        self.max_lev = max_lev
        self.reset()
    
    def reset(self):
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.peak = INITIAL_BALANCE
        self.max_dd = 0
    
    def calc_position_size(self, entry, sl):
        risk_amount = self.balance * self.risk_pct
        sl_distance = abs(entry - sl)
        if sl_distance == 0: return 0
        qty = risk_amount / sl_distance
        max_qty = (self.balance * self.max_lev) / entry
        return min(qty, max_qty)
    
    def open_position(self, side, entry, sl, tp, dt, reason=""):
        qty = self.calc_position_size(entry, sl)
        if qty <= 0: return False
        self.position = {
            'side': side, 'entry': entry, 'sl': sl, 'tp': tp,
            'qty': qty, 'time': dt, 'reason': reason
        }
        return True
    
    def close_position(self, price, dt, reason):
        if not self.position: return
        pos = self.position
        if pos['side'] == 'LONG':
            pnl = (price - pos['entry']) * pos['qty']
        else:
            pnl = (pos['entry'] - price) * pos['qty']
        pnl_pct = pnl / self.balance * 100
        self.balance += pnl
        self.trades.append({
            'side': pos['side'], 'entry': pos['entry'], 'exit': price,
            'entry_time': pos['time'], 'exit_time': dt,
            'pnl': pnl, 'pnl_pct': pnl_pct, 'reason': reason,
            'balance': self.balance
        })
        self.position = None
    
    def update_equity(self, price, dt):
        equity = self.balance
        if self.position:
            if self.position['side'] == 'LONG':
                equity += (price - self.position['entry']) * self.position['qty']
            else:
                equity += (self.position['entry'] - price) * self.position['qty']
        self.equity_curve.append({'time': dt, 'equity': equity})
        if equity > self.peak: self.peak = equity
        dd = (self.peak - equity) / self.peak * 100
        if dd > self.max_dd: self.max_dd = dd
    
    def check_sltp(self, candle):
        if not self.position: return
        pos = self.position
        if pos['side'] == 'LONG':
            if candle['low'] <= pos['sl']:
                self.close_position(pos['sl'], candle['datetime'], 'SL')
            elif candle['high'] >= pos['tp']:
                self.close_position(pos['tp'], candle['datetime'], 'TP')
        else:
            if candle['high'] >= pos['sl']:
                self.close_position(pos['sl'], candle['datetime'], 'SL')
            elif candle['low'] <= pos['tp']:
                self.close_position(pos['tp'], candle['datetime'], 'TP')
    
    def results(self):
        if not self.trades:
            return {'trades': 0, 'win_rate': 0, 'return_pct': 0, 'max_dd': 0, 'profit_factor': 0}
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        return {
            'trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(self.trades) * 100,
            'total_pnl': sum(t['pnl'] for t in self.trades),
            'return_pct': (self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            'max_dd': self.max_dd,
            'profit_factor': abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0,
        }


# ========== 최적화된 전략들 ==========

def strategy_adaptive_optimized(bt, params=None):
    """
    적응형 모멘텀 전략 - 최적화 버전
    
    파라미터:
    - sma_long: 장기 추세 (기본: 200)
    - sma_mid: 중기 추세 (기본: 50)
    - sma_short: 단기 추세 (기본: 20)
    - rsi_period: RSI 기간 (기본: 14)
    - atr_period: ATR 기간 (기본: 14)
    - atr_sl_mult: 손절 배수 (기본: 2.0)
    - atr_tp_mult: 익절 배수 (기본: 3.0)
    - trend_threshold: 추세 강도 임계값 (기본: 10, 5)
    """
    if params is None:
        params = {
            'sma_long': 200, 'sma_mid': 50, 'sma_short': 20,
            'rsi_period': 14, 'atr_period': 14,
            'atr_sl_mult': 2.0, 'atr_tp_mult': 3.0,
            'strong_trend': 20, 'weak_trend': 5
        }
    
    data = bt.data
    
    for i in range(params['sma_long'] + 50, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma_l = sma(data, params['sma_long'], i)
        sma_m = sma(data, params['sma_mid'], i)
        sma_s = sma(data, params['sma_short'], i)
        rsi_val = rsi(data, params['rsi_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        mom20 = momentum(data, 20, i)
        adx_val = adx(data, 14, i)
        
        if not all([sma_l, sma_m, sma_s, rsi_val, atr_val, mom20, adx_val]): continue
        
        trend_strength = (price - sma_l) / sma_l * 100
        
        # 강한 상승 추세
        if trend_strength > params['strong_trend'] and adx_val > 25:
            if rsi_val < 40 and price > sma_m:
                sl = price - atr_val * params['atr_sl_mult']
                tp = price + atr_val * params['atr_tp_mult'] * 1.5
                bt.open_position('LONG', price, sl, tp, dt, 'STRONG_UP')
        
        # 약한 상승 추세
        elif trend_strength > params['weak_trend']:
            if price > sma_l and price < sma_s * 1.01 and rsi_val < 45:
                sl = sma_m
                tp = price + atr_val * params['atr_tp_mult']
                bt.open_position('LONG', price, sl, tp, dt, 'WEAK_UP')
        
        # 횡보/약한 하락
        elif trend_strength > -params['weak_trend']:
            upper, mid, lower = bbands(data, 20, i)
            if lower and price < lower * 1.01:
                sl = price - atr_val * params['atr_sl_mult']
                tp = mid
                bt.open_position('LONG', price, sl, tp, dt, 'BB_LOWER')
    
    return bt.results()


def strategy_dual_momentum_optimized(bt, params=None):
    """
    듀얼 모멘텀 전략 - 최적화 버전
    
    파라미터:
    - mom_period: 모멘텀 기간 (기본: 20)
    - sma_period: 추세 필터 기간 (기본: 100)
    - mom_threshold: 모멘텀 임계값 (기본: 5%)
    - atr_sl_mult: 손절 배수 (기본: 2.0)
    - atr_tp_mult: 익절 배수 (기본: 3.0)
    """
    if params is None:
        params = {
            'mom_period': 20, 'sma_period': 100,
            'mom_threshold': 5, 'atr_period': 14,
            'atr_sl_mult': 2.0, 'atr_tp_mult': 3.0
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 50, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma_val = sma(data, params['sma_period'], i)
        mom_val = momentum(data, params['mom_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        
        if not all([sma_val, mom_val, atr_val]): continue
        
        # 롱: 모멘텀 > 임계값, SMA 위
        if mom_val > params['mom_threshold'] and price > sma_val:
            sl = price - atr_val * params['atr_sl_mult']
            tp = price + atr_val * params['atr_tp_mult']
            bt.open_position('LONG', price, sl, tp, dt, 'MOM_LONG')
    
    return bt.results()


def strategy_combined(bt, params=None):
    """
    결합 전략: Adaptive + Dual Momentum
    
    - 강한 추세: Adaptive 사용
    - 약한 추세: Dual Momentum 사용
    - 하락장: 관망
    """
    if params is None:
        params = {
            'sma_long': 200, 'sma_mid': 50, 'sma_short': 20,
            'mom_period': 20, 'mom_threshold': 5,
            'rsi_period': 14, 'atr_period': 14,
            'atr_sl_mult': 2.0, 'atr_tp_mult': 3.0,
            'adx_threshold': 20
        }
    
    data = bt.data
    
    for i in range(params['sma_long'] + 50, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        # 지표 계산
        sma_l = sma(data, params['sma_long'], i)
        sma_m = sma(data, params['sma_mid'], i)
        sma_s = sma(data, params['sma_short'], i)
        rsi_val = rsi(data, params['rsi_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        mom_val = momentum(data, params['mom_period'], i)
        adx_val = adx(data, 14, i)
        upper, mid, lower = bbands(data, 20, i)
        
        if not all([sma_l, sma_m, sma_s, rsi_val, atr_val, mom_val, adx_val, mid]): continue
        
        trend_strength = (price - sma_l) / sma_l * 100
        
        # 하락 추세 회피 (SMA200 아래 + 음의 모멘텀)
        if price < sma_l and mom_val < -10:
            continue
        
        signal = None
        
        # 1. 강한 상승 + ADX 강함: Adaptive 전략
        if trend_strength > 15 and adx_val > params['adx_threshold']:
            if rsi_val < 40 and price > sma_m:
                sl = price - atr_val * params['atr_sl_mult']
                tp = price + atr_val * params['atr_tp_mult'] * 1.5
                signal = ('LONG', sl, tp, 'ADAPTIVE_STRONG')
        
        # 2. 중간 상승: Dual Momentum
        elif trend_strength > 5 and mom_val > params['mom_threshold']:
            if price > sma_l:
                sl = price - atr_val * params['atr_sl_mult']
                tp = price + atr_val * params['atr_tp_mult']
                signal = ('LONG', sl, tp, 'DUAL_MOM')
        
        # 3. 약한 추세/횡보: 볼린저 밴드 하단
        elif trend_strength > -5:
            if price < lower * 1.01 and rsi_val < 35:
                sl = price - atr_val * params['atr_sl_mult']
                tp = mid
                signal = ('LONG', sl, tp, 'BB_REVERSAL')
        
        if signal:
            bt.open_position(signal[0], price, signal[1], signal[2], dt, signal[3])
    
    return bt.results()


def strategy_high_frequency(bt, params=None):
    """
    고빈도 전략: 1시간봉 기준
    - 더 많은 거래 기회
    - 작은 이익 목표
    """
    if params is None:
        params = {
            'sma_period': 50, 'rsi_period': 7,
            'atr_period': 14, 'atr_sl_mult': 1.5, 'atr_tp_mult': 2.0,
            'rsi_oversold': 30, 'rsi_overbought': 70
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 30, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma_val = sma(data, params['sma_period'], i)
        rsi_val = rsi(data, params['rsi_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        mom10 = momentum(data, 10, i)
        
        if not all([sma_val, rsi_val, atr_val, mom10]): continue
        
        # 롱: SMA 위 + RSI 과매도에서 반등
        if price > sma_val and rsi_val < params['rsi_oversold'] and mom10 > -5:
            sl = price - atr_val * params['atr_sl_mult']
            tp = price + atr_val * params['atr_tp_mult']
            bt.open_position('LONG', price, sl, tp, dt, 'HF_LONG')
    
    return bt.results()


# ========== 파라미터 그리드 서치 ==========

def grid_search_strategy(strategy_func, param_grid, timeframe='btc_4hour', years=None):
    """파라미터 그리드 서치"""
    if years is None:
        years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    # 파라미터 조합 생성
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(product(*param_values))
    
    print(f"🔍 {strategy_func.__name__} 그리드 서치")
    print(f"   총 {len(combinations)}개 파라미터 조합 테스트")
    
    best_score = float('-inf')
    best_params = None
    best_results = None
    
    for combo in combinations:
        params = dict(zip(param_names, combo))
        
        all_results = []
        for year in years:
            data = load_data(timeframe, year)
            if len(data) < 200:
                continue
            
            bt = Backtester(data)
            result = strategy_func(bt, params)
            result['year'] = year
            all_results.append(result)
        
        if not all_results:
            continue
        
        # 점수 계산
        total_return = sum(r['return_pct'] for r in all_results)
        avg_dd = sum(r['max_dd'] for r in all_results) / len(all_results)
        loss_years = sum(1 for r in all_results if r['return_pct'] < 0)
        avg_wr = sum(r['win_rate'] for r in all_results) / len(all_results)
        
        score = total_return - avg_dd * 2 - loss_years * 100
        
        if score > best_score:
            best_score = score
            best_params = params
            best_results = all_results
    
    return best_params, best_results, best_score


def test_strategy(strategy_func, params, timeframe='btc_4hour', years=None, verbose=True):
    """전략 테스트"""
    if years is None:
        years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    all_results = []
    
    for year in years:
        data = load_data(timeframe, year)
        if len(data) < 200:
            continue
        
        bt = Backtester(data)
        result = strategy_func(bt, params)
        result['year'] = year
        all_results.append(result)
        
        if verbose:
            print(f"  {year}: 거래 {result['trades']:>3} | 승률 {result['win_rate']:>5.1f}% | "
                  f"수익률 {result['return_pct']:>7.1f}% | MDD {result['max_dd']:>5.1f}%")
    
    if verbose and all_results:
        total_return = sum(r['return_pct'] for r in all_results)
        avg_dd = sum(r['max_dd'] for r in all_results) / len(all_results)
        avg_wr = sum(r['win_rate'] for r in all_results) / len(all_results)
        loss_years = sum(1 for r in all_results if r['return_pct'] < 0)
        
        print(f"  ─────────────────────────────────────────────────────────────────")
        print(f"  총: 수익률 {total_return:.1f}% | 평균MDD {avg_dd:.1f}% | 승률 {avg_wr:.1f}% | 손실연도 {loss_years}")
    
    return all_results


def run_optimization():
    """최적화 실행"""
    print("=" * 70)
    print("🚀 BTC 트레이딩 전략 최적화")
    print("=" * 70)
    
    # 1. Adaptive 전략 그리드 서치
    print("\n📊 1. Adaptive Momentum 최적화")
    adaptive_grid = {
        'sma_long': [150, 200],
        'sma_mid': [50],
        'sma_short': [20],
        'rsi_period': [14],
        'atr_period': [14],
        'atr_sl_mult': [1.5, 2.0],
        'atr_tp_mult': [3.0, 4.0],
        'strong_trend': [15, 20],
        'weak_trend': [5]
    }
    
    best_adaptive, results_adaptive, score_adaptive = grid_search_strategy(
        strategy_adaptive_optimized, adaptive_grid
    )
    
    print(f"\n   최적 파라미터: {best_adaptive}")
    print(f"   점수: {score_adaptive:.1f}")
    print("\n   연도별 결과:")
    for r in results_adaptive:
        print(f"     {r['year']}: 수익률 {r['return_pct']:.1f}% | MDD {r['max_dd']:.1f}%")
    
    # 2. Dual Momentum 그리드 서치
    print("\n📊 2. Dual Momentum 최적화")
    dual_grid = {
        'mom_period': [15, 20, 30],
        'sma_period': [50, 100],
        'mom_threshold': [3, 5, 7],
        'atr_period': [14],
        'atr_sl_mult': [1.5, 2.0],
        'atr_tp_mult': [2.5, 3.0]
    }
    
    best_dual, results_dual, score_dual = grid_search_strategy(
        strategy_dual_momentum_optimized, dual_grid
    )
    
    print(f"\n   최적 파라미터: {best_dual}")
    print(f"   점수: {score_dual:.1f}")
    print("\n   연도별 결과:")
    for r in results_dual:
        print(f"     {r['year']}: 수익률 {r['return_pct']:.1f}% | MDD {r['max_dd']:.1f}%")
    
    # 3. Combined 전략 테스트
    print("\n📊 3. Combined 전략 테스트")
    combined_params = {
        'sma_long': 200, 'sma_mid': 50, 'sma_short': 20,
        'mom_period': 20, 'mom_threshold': 5,
        'rsi_period': 14, 'atr_period': 14,
        'atr_sl_mult': 2.0, 'atr_tp_mult': 3.0,
        'adx_threshold': 20
    }
    
    test_strategy(strategy_combined, combined_params)
    
    # 4. 1시간봉 고빈도 테스트
    print("\n📊 4. 1시간봉 고빈도 전략 테스트")
    hf_params = {
        'sma_period': 50, 'rsi_period': 7,
        'atr_period': 14, 'atr_sl_mult': 1.5, 'atr_tp_mult': 2.0,
        'rsi_oversold': 30, 'rsi_overbought': 70
    }
    
    test_strategy(strategy_high_frequency, hf_params, timeframe='btc_1hour')
    
    # 최종 결과
    print("\n" + "=" * 70)
    print("🏆 최종 결과")
    print("=" * 70)
    
    if score_adaptive > score_dual:
        print("✅ 최적 전략: Adaptive Momentum")
        print(f"   파라미터: {best_adaptive}")
        return best_adaptive, strategy_adaptive_optimized
    else:
        print("✅ 최적 전략: Dual Momentum")
        print(f"   파라미터: {best_dual}")
        return best_dual, strategy_dual_momentum_optimized


def save_best_strategy(params, strategy_name):
    """최적 전략 저장"""
    config = {
        'strategy': strategy_name,
        'params': params,
        'risk_per_trade': RISK_PER_TRADE,
        'max_leverage': MAX_LEVERAGE,
        'timeframe': 'btc_4hour'
    }
    
    with open(Path(__file__).parent / 'best_strategy.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n💾 설정 저장: best_strategy.json")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # 기본 전략 테스트
        print("📊 Combined 전략 테스트")
        test_strategy(strategy_combined, None)
    else:
        # 최적화 실행
        best_params, best_func = run_optimization()
        save_best_strategy(best_params, best_func.__name__)
