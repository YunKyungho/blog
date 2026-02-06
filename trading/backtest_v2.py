#!/usr/bin/env python3
"""
BTC 트레이딩 전략 v2 - 리스크 관리 강화

핵심 변경:
1. 포지션 사이징: 거래당 2% 리스크 제한
2. 손절폭 기준 포지션 크기 계산
3. 추세 추종 + 풀백 진입
4. 4시간봉 기준 (더 많은 거래 기회)
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

# 설정
INITIAL_BALANCE = 10000
RISK_PER_TRADE = 0.02  # 거래당 리스크 2%
MAX_LEVERAGE = 5  # 최대 레버리지

# ========== 데이터 로드 ==========

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

def donchian(data, period, idx):
    if idx < period: return None, None
    return max(d['high'] for d in data[idx-period:idx]), min(d['low'] for d in data[idx-period:idx])

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
    """ADX 계산"""
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


# ========== 백테스트 엔진 ==========

class Backtester:
    def __init__(self, data):
        self.data = data
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.peak = INITIAL_BALANCE
        self.max_dd = 0
    
    def reset(self):
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.peak = INITIAL_BALANCE
        self.max_dd = 0
    
    def calc_position_size(self, entry, sl):
        """리스크 기반 포지션 사이징"""
        risk_amount = self.balance * RISK_PER_TRADE
        sl_distance = abs(entry - sl)
        if sl_distance == 0: return 0
        
        qty = risk_amount / sl_distance
        max_qty = (self.balance * MAX_LEVERAGE) / entry
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
            return {'trades': 0, 'win_rate': 0, 'return_pct': 0, 'max_dd': 0}
        
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
            'avg_win': sum(t['pnl'] for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t['pnl'] for t in losses) / len(losses) if losses else 0
        }


# ========== 전략들 ==========

def strategy_trend_following_pullback(bt, lookback=200):
    """
    추세 추종 + 풀백 진입
    - 200일 SMA 위에서 롱만
    - RSI 과매도 + 20일 SMA 지지에서 진입
    - ATR 2배 손절, 3배 익절
    """
    data = bt.data
    
    for i in range(lookback + 50, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma200 = sma(data, 200, i)
        sma20 = sma(data, 20, i)
        rsi14 = rsi(data, 14, i)
        atr14 = atr(data, 14, i)
        
        if not all([sma200, sma20, rsi14, atr14]): continue
        
        # 롱 조건: 가격 > SMA200, 가격 근처 SMA20 (풀백), RSI < 40
        if price > sma200 and price < sma20 * 1.02 and price > sma20 * 0.98 and rsi14 < 40:
            sl = price - atr14 * 2
            tp = price + atr14 * 3
            bt.open_position('LONG', price, sl, tp, dt, 'PULLBACK')
    
    return bt.results()


def strategy_dual_momentum(bt, lookback=100):
    """
    듀얼 모멘텀
    - 20일 모멘텀 > 0 (절대 모멘텀)
    - 가격 > SMA100 (추세 필터)
    """
    data = bt.data
    
    for i in range(lookback + 50, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma100 = sma(data, 100, i)
        mom20 = momentum(data, 20, i)
        atr14 = atr(data, 14, i)
        
        if not all([sma100, mom20, atr14]): continue
        
        # 롱: 모멘텀 > 5%, SMA100 위
        if mom20 > 5 and price > sma100:
            sl = price - atr14 * 2
            tp = price + atr14 * 3
            bt.open_position('LONG', price, sl, tp, dt, 'MOM_LONG')
    
    return bt.results()


def strategy_donchian_trend(bt, entry_period=20, exit_period=10):
    """
    돈치안 브레이크아웃 + 추세 필터
    """
    data = bt.data
    
    for i in range(100, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        upper, _ = donchian(data, entry_period, i - 1)
        sma50 = sma(data, 50, i)
        atr14 = atr(data, 14, i)
        
        if not all([upper, sma50, atr14]): continue
        
        # 롱: SMA50 위 + 돈치안 상단 돌파
        if price > sma50 and candle['high'] > upper:
            sl = price - atr14 * 2
            tp = price + atr14 * 3
            bt.open_position('LONG', price, sl, tp, dt, 'DONCHIAN_BREAK')
    
    return bt.results()


def strategy_rsi_reversal(bt):
    """
    RSI 반전 + 추세 필터
    - 강한 추세에서 과매도 반등
    """
    data = bt.data
    
    for i in range(100, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma50 = sma(data, 50, i)
        rsi14 = rsi(data, 14, i)
        atr14 = atr(data, 14, i)
        mom10 = momentum(data, 10, i)
        
        if not all([sma50, rsi14, atr14, mom10]): continue
        
        # 롱: 추세 위, RSI 과매도에서 반등
        if price > sma50 and rsi14 < 30 and mom10 > -10:
            sl = price - atr14 * 1.5
            tp = price + atr14 * 2.5
            bt.open_position('LONG', price, sl, tp, dt, 'RSI_REVERSAL')
    
    return bt.results()


def strategy_bb_squeeze(bt):
    """
    볼린저 밴드 스퀴즈 브레이크아웃
    """
    data = bt.data
    
    prev_width = None
    squeeze_count = 0
    
    for i in range(50, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        upper, mid, lower = bbands(data, 20, i)
        sma50 = sma(data, 50, i)
        atr14 = atr(data, 14, i)
        
        if not all([upper, mid, lower, sma50, atr14]): continue
        
        width = (upper - lower) / mid
        
        # 스퀴즈 감지 (밴드폭 축소)
        if prev_width and width < prev_width * 0.8:
            squeeze_count += 1
        else:
            squeeze_count = 0
        
        prev_width = width
        
        # 스퀴즈 후 상단 돌파
        if squeeze_count >= 5 and price > upper and price > sma50:
            sl = mid
            tp = price + (price - mid) * 2
            bt.open_position('LONG', price, sl, tp, dt, 'BB_BREAKOUT')
            squeeze_count = 0
    
    return bt.results()


def strategy_adaptive_momentum(bt):
    """
    적응형 모멘텀 전략
    - 시장 상태에 따라 전략 변경
    - 강한 상승: 브레이크아웃
    - 약한 상승: 풀백
    """
    data = bt.data
    
    for i in range(200, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma200 = sma(data, 200, i)
        sma50 = sma(data, 50, i)
        sma20 = sma(data, 20, i)
        rsi14 = rsi(data, 14, i)
        atr14 = atr(data, 14, i)
        mom20 = momentum(data, 20, i)
        adx14 = adx(data, 14, i)
        
        if not all([sma200, sma50, sma20, rsi14, atr14, mom20, adx14]): continue
        
        # 시장 상태 판단
        trend_strength = (price - sma200) / sma200 * 100
        
        if trend_strength > 20 and adx14 > 25:
            # 강한 상승 추세: 풀백 매수
            if rsi14 < 40 and price > sma50:
                sl = price - atr14 * 2
                tp = price + atr14 * 4
                bt.open_position('LONG', price, sl, tp, dt, 'STRONG_PULLBACK')
        
        elif trend_strength > 5:
            # 약한 상승: 지지선 매수
            if price > sma200 and price < sma20 * 1.01 and rsi14 < 45:
                sl = sma50
                tp = price + atr14 * 3
                bt.open_position('LONG', price, sl, tp, dt, 'SUPPORT_BUY')
        
        elif trend_strength > -5:
            # 횡보: 볼린저 밴드 하단 매수
            upper, mid, lower = bbands(data, 20, i)
            if lower and price < lower * 1.01:
                sl = price - atr14 * 1.5
                tp = mid
                bt.open_position('LONG', price, sl, tp, dt, 'BB_LOWER')
    
    return bt.results()


def strategy_multi_timeframe(bt):
    """
    멀티 타임프레임 전략
    - 일봉 추세 + 4시간봉 진입
    """
    data = bt.data
    
    for i in range(200, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        # 장기 추세 (일봉 대용)
        sma200 = sma(data, 200, i)  # ~50일
        sma100 = sma(data, 100, i)  # ~25일
        
        # 중기 추세
        sma50 = sma(data, 50, i)
        sma20 = sma(data, 20, i)
        
        # 지표
        rsi14 = rsi(data, 14, i)
        atr14 = atr(data, 14, i)
        mom10 = momentum(data, 10, i)
        
        if not all([sma200, sma100, sma50, sma20, rsi14, atr14, mom10]): continue
        
        # 롱 조건:
        # 1. 장기 상승 (SMA100 > SMA200)
        # 2. 중기 상승 (SMA20 > SMA50)
        # 3. RSI 과매도 아님 (30-60)
        # 4. 모멘텀 양수
        if (sma100 > sma200 and sma20 > sma50 and 
            30 < rsi14 < 60 and mom10 > 0 and price > sma20):
            sl = price - atr14 * 2
            tp = price + atr14 * 3
            bt.open_position('LONG', price, sl, tp, dt, 'MTF_LONG')
    
    return bt.results()


def strategy_conservative_trend(bt):
    """
    보수적 추세 추종
    - 매우 강한 조건만
    - 낮은 빈도, 높은 승률 목표
    """
    data = bt.data
    
    for i in range(250, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma200 = sma(data, 200, i)
        sma50 = sma(data, 50, i)
        sma20 = sma(data, 20, i)
        rsi14 = rsi(data, 14, i)
        atr14 = atr(data, 14, i)
        adx14 = adx(data, 14, i)
        mom30 = momentum(data, 30, i)
        
        if not all([sma200, sma50, sma20, rsi14, atr14, adx14, mom30]): continue
        
        # 매우 강한 롱 조건
        conditions = [
            price > sma200,           # 장기 상승
            sma50 > sma200,           # 골든크로스 유지
            price > sma20,            # 단기 상승
            35 < rsi14 < 65,          # 중립 RSI
            adx14 > 20,               # 추세 존재
            mom30 > 5,                # 양의 모멘텀
        ]
        
        if all(conditions):
            sl = min(sma20, price - atr14 * 2)
            tp = price + atr14 * 4
            bt.open_position('LONG', price, sl, tp, dt, 'CONSERVATIVE')
    
    return bt.results()


# ========== 테스트 실행 ==========

def test_strategy(strategy_func, timeframe='btc_4hour', years=None):
    """전략 테스트"""
    if years is None:
        years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    print(f"\n📊 {strategy_func.__name__}")
    print("-" * 70)
    
    all_results = []
    
    for year in years:
        data = load_data(timeframe, year)
        if len(data) < 200:
            continue
        
        bt = Backtester(data)
        result = strategy_func(bt)
        result['year'] = year
        all_results.append(result)
        
        print(f"  {year}: 거래 {result['trades']:>3} | 승률 {result['win_rate']:>5.1f}% | "
              f"수익률 {result['return_pct']:>7.1f}% | MDD {result['max_dd']:>5.1f}%")
    
    # 요약
    if all_results:
        avg_return = sum(r['return_pct'] for r in all_results) / len(all_results)
        avg_dd = sum(r['max_dd'] for r in all_results) / len(all_results)
        avg_wr = sum(r['win_rate'] for r in all_results) / len(all_results)
        total_trades = sum(r['trades'] for r in all_results)
        loss_years = sum(1 for r in all_results if r['return_pct'] < 0)
        
        print(f"  ─────────────────────────────────────────────────────────────────")
        print(f"  평균: 거래 {total_trades/len(all_results):>3.0f} | 승률 {avg_wr:>5.1f}% | "
              f"수익률 {avg_return:>7.1f}% | MDD {avg_dd:>5.1f}% | 손실연도: {loss_years}")
        
        # 점수 계산
        score = sum(r['return_pct'] for r in all_results) - avg_dd * 2 - loss_years * 100
        print(f"  점수: {score:.1f}")
    
    return all_results


def run_all_tests():
    """모든 전략 테스트"""
    print("=" * 70)
    print("🔍 BTC 트레이딩 전략 백테스트 v2")
    print("=" * 70)
    print(f"초기자본: ${INITIAL_BALANCE:,} | 거래당 리스크: {RISK_PER_TRADE*100}% | 최대 레버리지: {MAX_LEVERAGE}x")
    
    strategies = [
        strategy_trend_following_pullback,
        strategy_dual_momentum,
        strategy_donchian_trend,
        strategy_rsi_reversal,
        strategy_bb_squeeze,
        strategy_adaptive_momentum,
        strategy_multi_timeframe,
        strategy_conservative_trend,
    ]
    
    best_score = float('-inf')
    best_strategy = None
    all_scores = []
    
    for strategy in strategies:
        results = test_strategy(strategy)
        if results:
            avg_return = sum(r['return_pct'] for r in results)
            avg_dd = sum(r['max_dd'] for r in results) / len(results)
            loss_years = sum(1 for r in results if r['return_pct'] < 0)
            score = avg_return - avg_dd * 2 - loss_years * 100
            
            all_scores.append((strategy.__name__, score, results))
            
            if score > best_score:
                best_score = score
                best_strategy = (strategy, results)
    
    # 랭킹
    all_scores.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "=" * 70)
    print("🏆 전략 랭킹")
    print("=" * 70)
    for i, (name, score, results) in enumerate(all_scores[:5]):
        total_return = sum(r['return_pct'] for r in results)
        avg_dd = sum(r['max_dd'] for r in results) / len(results)
        loss_years = sum(1 for r in results if r['return_pct'] < 0)
        print(f"{i+1}. {name}")
        print(f"   총수익률: {total_return:.1f}% | 평균MDD: {avg_dd:.1f}% | 손실연도: {loss_years} | 점수: {score:.1f}")
    
    return best_strategy, all_scores


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        strategy_map = {
            'pullback': strategy_trend_following_pullback,
            'momentum': strategy_dual_momentum,
            'donchian': strategy_donchian_trend,
            'rsi': strategy_rsi_reversal,
            'bb': strategy_bb_squeeze,
            'adaptive': strategy_adaptive_momentum,
            'mtf': strategy_multi_timeframe,
            'conservative': strategy_conservative_trend,
        }
        
        name = sys.argv[1]
        if name in strategy_map:
            test_strategy(strategy_map[name])
        elif name == 'all':
            run_all_tests()
        else:
            print(f"Available: {list(strategy_map.keys())} or 'all'")
    else:
        run_all_tests()
