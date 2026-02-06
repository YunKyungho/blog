#!/usr/bin/env python3
"""
백테스팅 v5 - 종합 전략 테스트
다양한 전략 유형과 수백 개 파라미터 조합 테스트

목표:
- 거래수: 300-400회/년 (현재 828회 - 줄여야 함!)
- 승률: 40%+
- 월 수익률: 40%+
- 최대 DD: 40% 이하
- 모든 연도 수익
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from itertools import product
import math

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"
INITIAL_BALANCE = 5000

# ========== 데이터 로드 ==========

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


# ========== 기술적 지표 ==========

def calc_sma(closes, period):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def calc_ema(closes, period):
    if len(closes) < period:
        return None
    mult = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = (price * mult) + (ema * (1 - mult))
    return ema

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    if len(gains) < period:
        return None
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_bollinger(closes, period=20, std_mult=2):
    if len(closes) < period:
        return None, None, None
    
    sma = sum(closes[-period:]) / period
    variance = sum((c - sma) ** 2 for c in closes[-period:]) / period
    std = math.sqrt(variance)
    
    upper = sma + (std * std_mult)
    lower = sma - (std * std_mult)
    
    return upper, sma, lower

def calc_atr(klines, period=14):
    if len(klines) < period + 1:
        return None
    
    trs = []
    for i in range(1, len(klines)):
        high = klines[i]['high']
        low = klines[i]['low']
        prev_close = klines[i-1]['close']
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    
    if len(trs) < period:
        return None
    
    return sum(trs[-period:]) / period

def calc_macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None, None, None
    
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    
    if ema_fast is None or ema_slow is None:
        return None, None, None
    
    macd_line = ema_fast - ema_slow
    
    # 간단한 시그널 라인 (실제로는 MACD 히스토리의 EMA)
    signal_line = macd_line * 0.9  # 근사값
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calc_adx(klines, period=14):
    if len(klines) < period * 2:
        return None
    
    plus_dm = []
    minus_dm = []
    tr_list = []
    
    for i in range(1, len(klines)):
        high = klines[i]['high']
        low = klines[i]['low']
        prev_high = klines[i-1]['high']
        prev_low = klines[i-1]['low']
        prev_close = klines[i-1]['close']
        
        up_move = high - prev_high
        down_move = prev_low - low
        
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    
    if len(tr_list) < period:
        return None
    
    atr = sum(tr_list[-period:]) / period
    plus_di = 100 * sum(plus_dm[-period:]) / period / atr if atr > 0 else 0
    minus_di = 100 * sum(minus_dm[-period:]) / period / atr if atr > 0 else 0
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
    
    return dx


# ========== 전략 클래스들 ==========

class BaseStrategy:
    def __init__(self, params):
        self.params = params
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.cooldown = 0
        self.signal_count = {'LONG': 0, 'SHORT': 0}
    
    def execute_entry(self, signal, dt):
        leverage = self.params.get('leverage', 10)
        risk_pct = self.params.get('risk_per_trade', 2.0)
        
        risk_amount = self.balance * (risk_pct / 100)
        sl_distance = abs(signal['entry'] - signal['sl'])
        qty = risk_amount / sl_distance if sl_distance > 0 else 0
        max_qty = (self.balance * leverage) / signal['entry']
        qty = min(qty, max_qty)
        
        self.position = {
            'side': signal['side'], 'entry': signal['entry'],
            'sl': signal['sl'], 'tp': signal['tp'],
            'quantity': qty, 'datetime': dt
        }
        
        self.signal_count[signal['side']] += 1
        self.cooldown = self.params.get('cooldown_bars', 4)
    
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
        
        self.balance += pnl
        
        self.trades.append({
            'side': self.position['side'], 'entry': entry, 'exit': price,
            'pnl': pnl, 'reason': reason, 'balance_after': self.balance
        })
        
        self.position = None
    
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


# ========== 전략 1: 풀백 (기존, 파라미터 조정) ==========

class PullbackStrategy(BaseStrategy):
    def get_trend(self, klines, ma_period):
        if len(klines) < ma_period:
            return 'UNKNOWN'
        
        closes = [k['close'] for k in klines[-ma_period:]]
        ma = sum(closes) / len(closes)
        current = klines[-1]['close']
        threshold = self.params.get('trend_threshold', 0.5)
        
        if current > ma * (1 + threshold/100):
            return 'UP'
        elif current < ma * (1 - threshold/100):
            return 'DOWN'
        return 'SIDEWAYS'
    
    def find_signal(self, klines_trend, klines_entry, trend):
        if len(klines_entry) < 20:
            return None
        
        curr = klines_entry[-1]
        prev = klines_entry[-2]
        
        pullback_min = self.params.get('pullback_min', 0.15)
        pullback_max = self.params.get('pullback_max', 3.0)
        min_body = self.params.get('min_body_ratio', 0.5)
        
        body = abs(curr['close'] - curr['open'])
        total = curr['high'] - curr['low']
        if total == 0 or body / total < min_body:
            return None
        
        price = curr['close']
        sl_pct = self.params.get('sl_pct', 0.5)
        tp_pct = self.params.get('tp_pct', 0.8)
        
        if trend == 'UP':
            if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                recent_high = max(k['high'] for k in klines_entry[-10:-1])
                pullback = (recent_high - curr['low']) / recent_high * 100
                
                if pullback_min < pullback < pullback_max:
                    return {
                        'side': 'LONG', 'entry': price,
                        'sl': price * (1 - sl_pct / 100),
                        'tp': price * (1 + tp_pct / 100)
                    }
        
        elif trend == 'DOWN':
            if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                recent_low = min(k['low'] for k in klines_entry[-10:-1])
                bounce = (curr['high'] - recent_low) / recent_low * 100
                
                if pullback_min < bounce < pullback_max:
                    return {
                        'side': 'SHORT', 'entry': price,
                        'sl': price * (1 + sl_pct / 100),
                        'tp': price * (1 - tp_pct / 100)
                    }
        
        return None
    
    def run(self, data_trend, data_entry):
        ma_period = self.params.get('trend_ma', 50)
        
        for i in range(200, len(data_entry)):
            current = data_entry[i]
            dt = current['datetime']
            
            klines_trend = [k for k in data_trend if k['time'] <= current['time']][-100:]
            klines_entry = data_entry[max(0, i-50):i+1]
            
            if len(klines_trend) < ma_period:
                continue
            
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            if self.cooldown > 0:
                self.cooldown -= 1
            
            if not self.position and self.cooldown == 0:
                trend = self.get_trend(klines_trend, ma_period)
                if trend in ['UP', 'DOWN']:
                    signal = self.find_signal(klines_trend, klines_entry, trend)
                    if signal:
                        self.execute_entry(signal, dt)
            
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()


# ========== 전략 2: RSI 역추세 ==========

class RSIStrategy(BaseStrategy):
    def find_signal(self, klines):
        if len(klines) < 30:
            return None
        
        closes = [k['close'] for k in klines]
        rsi = calc_rsi(closes, self.params.get('rsi_period', 14))
        
        if rsi is None:
            return None
        
        price = klines[-1]['close']
        oversold = self.params.get('rsi_oversold', 30)
        overbought = self.params.get('rsi_overbought', 70)
        sl_pct = self.params.get('sl_pct', 1.0)
        tp_pct = self.params.get('tp_pct', 1.5)
        
        # 추세 필터 (선택적)
        if self.params.get('use_trend_filter', True):
            ma = calc_sma(closes, self.params.get('trend_ma', 50))
            if ma is None:
                return None
            
            # 상승 추세에서만 롱, 하락 추세에서만 숏
            if rsi < oversold and price > ma:
                return {
                    'side': 'LONG', 'entry': price,
                    'sl': price * (1 - sl_pct / 100),
                    'tp': price * (1 + tp_pct / 100)
                }
            elif rsi > overbought and price < ma:
                return {
                    'side': 'SHORT', 'entry': price,
                    'sl': price * (1 + sl_pct / 100),
                    'tp': price * (1 - tp_pct / 100)
                }
        else:
            if rsi < oversold:
                return {
                    'side': 'LONG', 'entry': price,
                    'sl': price * (1 - sl_pct / 100),
                    'tp': price * (1 + tp_pct / 100)
                }
            elif rsi > overbought:
                return {
                    'side': 'SHORT', 'entry': price,
                    'sl': price * (1 + sl_pct / 100),
                    'tp': price * (1 - tp_pct / 100)
                }
        
        return None
    
    def run(self, data):
        for i in range(100, len(data)):
            current = data[i]
            dt = current['datetime']
            
            klines = data[max(0, i-100):i+1]
            
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            if self.cooldown > 0:
                self.cooldown -= 1
            
            if not self.position and self.cooldown == 0:
                signal = self.find_signal(klines)
                if signal:
                    self.execute_entry(signal, dt)
            
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()


# ========== 전략 3: 볼린저 밴드 ==========

class BollingerStrategy(BaseStrategy):
    def find_signal(self, klines):
        if len(klines) < 30:
            return None
        
        closes = [k['close'] for k in klines]
        period = self.params.get('bb_period', 20)
        std_mult = self.params.get('bb_std', 2.0)
        
        upper, middle, lower = calc_bollinger(closes, period, std_mult)
        
        if upper is None:
            return None
        
        price = klines[-1]['close']
        prev_price = klines[-2]['close']
        sl_pct = self.params.get('sl_pct', 1.0)
        tp_pct = self.params.get('tp_pct', 1.5)
        
        # 하단 밴드 터치 후 반등 → 롱
        if prev_price <= lower and price > lower:
            return {
                'side': 'LONG', 'entry': price,
                'sl': price * (1 - sl_pct / 100),
                'tp': middle  # 중간 밴드까지
            }
        
        # 상단 밴드 터치 후 하락 → 숏
        if prev_price >= upper and price < upper:
            return {
                'side': 'SHORT', 'entry': price,
                'sl': price * (1 + sl_pct / 100),
                'tp': middle
            }
        
        return None
    
    def run(self, data):
        for i in range(100, len(data)):
            current = data[i]
            dt = current['datetime']
            
            klines = data[max(0, i-100):i+1]
            
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            if self.cooldown > 0:
                self.cooldown -= 1
            
            if not self.position and self.cooldown == 0:
                signal = self.find_signal(klines)
                if signal:
                    self.execute_entry(signal, dt)
            
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()


# ========== 전략 4: 브레이크아웃 ==========

class BreakoutStrategy(BaseStrategy):
    def find_signal(self, klines):
        lookback = self.params.get('breakout_period', 20)
        
        if len(klines) < lookback + 5:
            return None
        
        # 최근 N봉의 고점/저점
        recent = klines[-(lookback+1):-1]
        highest = max(k['high'] for k in recent)
        lowest = min(k['low'] for k in recent)
        
        price = klines[-1]['close']
        prev_close = klines[-2]['close']
        sl_pct = self.params.get('sl_pct', 1.0)
        tp_pct = self.params.get('tp_pct', 2.0)
        
        # 고점 돌파 → 롱
        if prev_close < highest and price > highest:
            return {
                'side': 'LONG', 'entry': price,
                'sl': price * (1 - sl_pct / 100),
                'tp': price * (1 + tp_pct / 100)
            }
        
        # 저점 하향 돌파 → 숏
        if prev_close > lowest and price < lowest:
            return {
                'side': 'SHORT', 'entry': price,
                'sl': price * (1 + sl_pct / 100),
                'tp': price * (1 - tp_pct / 100)
            }
        
        return None
    
    def run(self, data):
        for i in range(100, len(data)):
            current = data[i]
            dt = current['datetime']
            
            klines = data[max(0, i-100):i+1]
            
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            if self.cooldown > 0:
                self.cooldown -= 1
            
            if not self.position and self.cooldown == 0:
                signal = self.find_signal(klines)
                if signal:
                    self.execute_entry(signal, dt)
            
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()


# ========== 전략 5: EMA 크로스 ==========

class EMACrossStrategy(BaseStrategy):
    def find_signal(self, klines):
        if len(klines) < 100:
            return None
        
        closes = [k['close'] for k in klines]
        fast_period = self.params.get('ema_fast', 12)
        slow_period = self.params.get('ema_slow', 26)
        
        # 현재 EMA
        ema_fast = calc_ema(closes, fast_period)
        ema_slow = calc_ema(closes, slow_period)
        
        # 이전 EMA
        ema_fast_prev = calc_ema(closes[:-1], fast_period)
        ema_slow_prev = calc_ema(closes[:-1], slow_period)
        
        if None in [ema_fast, ema_slow, ema_fast_prev, ema_slow_prev]:
            return None
        
        price = klines[-1]['close']
        sl_pct = self.params.get('sl_pct', 1.0)
        tp_pct = self.params.get('tp_pct', 1.5)
        
        # 골든 크로스 → 롱
        if ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow:
            return {
                'side': 'LONG', 'entry': price,
                'sl': price * (1 - sl_pct / 100),
                'tp': price * (1 + tp_pct / 100)
            }
        
        # 데드 크로스 → 숏
        if ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow:
            return {
                'side': 'SHORT', 'entry': price,
                'sl': price * (1 + sl_pct / 100),
                'tp': price * (1 - tp_pct / 100)
            }
        
        return None
    
    def run(self, data):
        for i in range(100, len(data)):
            current = data[i]
            dt = current['datetime']
            
            klines = data[max(0, i-150):i+1]
            
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            if self.cooldown > 0:
                self.cooldown -= 1
            
            if not self.position and self.cooldown == 0:
                signal = self.find_signal(klines)
                if signal:
                    self.execute_entry(signal, dt)
            
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()


# ========== 전략 6: ADX 추세 강도 + MA ==========

class ADXTrendStrategy(BaseStrategy):
    def get_trend(self, klines, ma_period):
        if len(klines) < ma_period:
            return 'UNKNOWN'
        
        closes = [k['close'] for k in klines[-ma_period:]]
        ma = sum(closes) / len(closes)
        current = klines[-1]['close']
        
        if current > ma:
            return 'UP'
        elif current < ma:
            return 'DOWN'
        return 'SIDEWAYS'
    
    def find_signal(self, klines):
        if len(klines) < 50:
            return None
        
        adx = calc_adx(klines, self.params.get('adx_period', 14))
        min_adx = self.params.get('min_adx', 25)
        
        if adx is None or adx < min_adx:
            return None  # 추세가 약함
        
        trend = self.get_trend(klines, self.params.get('trend_ma', 50))
        
        if trend == 'UNKNOWN':
            return None
        
        price = klines[-1]['close']
        sl_pct = self.params.get('sl_pct', 1.0)
        tp_pct = self.params.get('tp_pct', 2.0)
        
        # 풀백 확인
        curr = klines[-1]
        prev = klines[-2]
        
        if trend == 'UP':
            if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                return {
                    'side': 'LONG', 'entry': price,
                    'sl': price * (1 - sl_pct / 100),
                    'tp': price * (1 + tp_pct / 100)
                }
        
        elif trend == 'DOWN':
            if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                return {
                    'side': 'SHORT', 'entry': price,
                    'sl': price * (1 + sl_pct / 100),
                    'tp': price * (1 - tp_pct / 100)
                }
        
        return None
    
    def run(self, data):
        for i in range(100, len(data)):
            current = data[i]
            dt = current['datetime']
            
            klines = data[max(0, i-100):i+1]
            
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            if self.cooldown > 0:
                self.cooldown -= 1
            
            if not self.position and self.cooldown == 0:
                signal = self.find_signal(klines)
                if signal:
                    self.execute_entry(signal, dt)
            
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()


# ========== 테스트 실행 ==========

def run_strategy_test(strategy_class, params, data_trend, data_entry, strategy_type='pullback'):
    """전략 테스트 실행"""
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    results = []
    
    for year in years:
        if strategy_type == 'pullback':
            year_trend = [k for k in data_trend if k['datetime'][:4] == year]
            year_entry = [k for k in data_entry if k['datetime'][:4] == year]
            
            if len(year_entry) < 1000:
                continue
            
            strategy = strategy_class(params)
            result = strategy.run(year_trend, year_entry)
        else:
            year_data = [k for k in data_entry if k['datetime'][:4] == year]
            
            if len(year_data) < 1000:
                continue
            
            strategy = strategy_class(params)
            result = strategy.run(year_data)
        
        result['year'] = year
        results.append(result)
    
    return results


def evaluate_results(results):
    """결과 평가"""
    if not results:
        return None
    
    all_profitable = all(r['return_pct'] > 0 for r in results)
    min_wr = min(r['win_rate'] for r in results if r['total_trades'] > 0) if any(r['total_trades'] > 0 for r in results) else 0
    max_dd = max(r['max_drawdown'] for r in results)
    avg_return = sum(r['return_pct'] for r in results) / len(results)
    avg_trades = sum(r['total_trades'] for r in results) / len(results)
    
    # 점수 계산
    score = avg_return
    
    # 목표 조건 충족 보너스
    if all_profitable:
        score += 500
    if min_wr >= 40:
        score += 200
    if max_dd <= 40:
        score += 300
    
    # 거래 수 목표 (300-400회)
    if 250 <= avg_trades <= 450:
        score += 200
    elif 200 <= avg_trades <= 500:
        score += 100
    elif avg_trades > 500:
        score -= (avg_trades - 500) * 0.5  # 너무 많으면 감점
    
    return {
        'all_profitable': all_profitable,
        'min_wr': min_wr,
        'max_dd': max_dd,
        'avg_return': avg_return,
        'avg_trades': avg_trades,
        'score': score
    }


def comprehensive_test():
    """종합 테스트"""
    print("📥 데이터 로드 중...")
    data_1h = load_data('btc_1hour')
    data_4h = load_data('btc_4hour')
    data_15m = load_data('btc_15min')
    
    print(f"  1시간봉: {len(data_1h):,}개")
    print(f"  4시간봉: {len(data_4h):,}개")
    print(f"  15분봉: {len(data_15m):,}개")
    
    all_results = []
    
    # ========== 1. 풀백 전략 그리드 서치 (거래 빈도 줄이기) ==========
    print("\n" + "=" * 80)
    print("🔍 전략 1: 풀백 매매 (거래 빈도 최적화)")
    print("=" * 80)
    
    # 거래 빈도를 줄이기 위한 파라미터
    pullback_params = []
    
    for leverage in [8, 10, 12]:
        for sl_pct in [0.8, 1.0, 1.2, 1.5]:
            for tp_pct in [1.2, 1.5, 2.0, 2.5]:
                for pullback_min in [0.3, 0.5, 0.7, 1.0]:
                    for pullback_max in [2.0, 3.0, 4.0]:
                        for trend_ma in [50, 100, 200]:
                            for cooldown in [8, 12, 16, 24]:  # 더 긴 쿨다운
                                for trend_threshold in [0.5, 1.0, 1.5]:
                                    pullback_params.append({
                                        'leverage': leverage,
                                        'sl_pct': sl_pct,
                                        'tp_pct': tp_pct,
                                        'pullback_min': pullback_min,
                                        'pullback_max': pullback_max,
                                        'trend_ma': trend_ma,
                                        'cooldown_bars': cooldown,
                                        'trend_threshold': trend_threshold,
                                        'min_body_ratio': 0.5,
                                        'risk_per_trade': 2.0
                                    })
    
    print(f"  테스트할 파라미터 조합: {len(pullback_params)}개")
    
    tested = 0
    for params in pullback_params:
        results = run_strategy_test(PullbackStrategy, params, data_4h, data_15m, 'pullback')
        eval_result = evaluate_results(results)
        
        if eval_result:
            eval_result['strategy'] = 'pullback'
            eval_result['params'] = params
            eval_result['results'] = results
            all_results.append(eval_result)
        
        tested += 1
        if tested % 500 == 0:
            print(f"  진행: {tested}/{len(pullback_params)} ({tested/len(pullback_params)*100:.1f}%)")
    
    print(f"  완료: {tested}개 테스트")
    
    # ========== 2. 1시간봉 기반 풀백 (거래 빈도 낮춤) ==========
    print("\n" + "=" * 80)
    print("🔍 전략 2: 1시간봉 풀백 (더 낮은 빈도)")
    print("=" * 80)
    
    hourly_params = []
    
    for leverage in [10, 12, 15]:
        for sl_pct in [1.0, 1.5, 2.0]:
            for tp_pct in [1.5, 2.0, 3.0]:
                for pullback_min in [0.5, 1.0, 1.5]:
                    for pullback_max in [3.0, 5.0]:
                        for trend_ma in [50, 100]:
                            for cooldown in [4, 8, 12]:
                                hourly_params.append({
                                    'leverage': leverage,
                                    'sl_pct': sl_pct,
                                    'tp_pct': tp_pct,
                                    'pullback_min': pullback_min,
                                    'pullback_max': pullback_max,
                                    'trend_ma': trend_ma,
                                    'cooldown_bars': cooldown,
                                    'trend_threshold': 1.0,
                                    'min_body_ratio': 0.4,
                                    'risk_per_trade': 2.0
                                })
    
    print(f"  테스트할 파라미터 조합: {len(hourly_params)}개")
    
    tested = 0
    for params in hourly_params:
        results = run_strategy_test(PullbackStrategy, params, data_4h, data_1h, 'pullback')
        eval_result = evaluate_results(results)
        
        if eval_result:
            eval_result['strategy'] = 'pullback_1h'
            eval_result['params'] = params
            eval_result['results'] = results
            all_results.append(eval_result)
        
        tested += 1
        if tested % 200 == 0:
            print(f"  진행: {tested}/{len(hourly_params)}")
    
    print(f"  완료: {tested}개 테스트")
    
    # ========== 3. RSI 전략 ==========
    print("\n" + "=" * 80)
    print("🔍 전략 3: RSI 역추세")
    print("=" * 80)
    
    rsi_params = []
    
    for leverage in [8, 10, 12]:
        for rsi_period in [7, 14, 21]:
            for oversold in [20, 25, 30]:
                for overbought in [70, 75, 80]:
                    for sl_pct in [1.0, 1.5, 2.0]:
                        for tp_pct in [1.5, 2.0, 3.0]:
                            for cooldown in [8, 16, 24]:
                                for use_filter in [True, False]:
                                    rsi_params.append({
                                        'leverage': leverage,
                                        'rsi_period': rsi_period,
                                        'rsi_oversold': oversold,
                                        'rsi_overbought': overbought,
                                        'sl_pct': sl_pct,
                                        'tp_pct': tp_pct,
                                        'cooldown_bars': cooldown,
                                        'use_trend_filter': use_filter,
                                        'trend_ma': 50,
                                        'risk_per_trade': 2.0
                                    })
    
    print(f"  테스트할 파라미터 조합: {len(rsi_params)}개")
    
    tested = 0
    for params in rsi_params:
        results = run_strategy_test(RSIStrategy, params, None, data_1h, 'single')
        eval_result = evaluate_results(results)
        
        if eval_result:
            eval_result['strategy'] = 'rsi'
            eval_result['params'] = params
            eval_result['results'] = results
            all_results.append(eval_result)
        
        tested += 1
        if tested % 500 == 0:
            print(f"  진행: {tested}/{len(rsi_params)}")
    
    print(f"  완료: {tested}개 테스트")
    
    # ========== 4. 볼린저 밴드 전략 ==========
    print("\n" + "=" * 80)
    print("🔍 전략 4: 볼린저 밴드")
    print("=" * 80)
    
    bb_params = []
    
    for leverage in [8, 10, 12]:
        for bb_period in [20, 30, 50]:
            for bb_std in [1.5, 2.0, 2.5]:
                for sl_pct in [1.0, 1.5, 2.0]:
                    for cooldown in [8, 16, 24]:
                        bb_params.append({
                            'leverage': leverage,
                            'bb_period': bb_period,
                            'bb_std': bb_std,
                            'sl_pct': sl_pct,
                            'tp_pct': 0,  # 중간 밴드로
                            'cooldown_bars': cooldown,
                            'risk_per_trade': 2.0
                        })
    
    print(f"  테스트할 파라미터 조합: {len(bb_params)}개")
    
    tested = 0
    for params in bb_params:
        results = run_strategy_test(BollingerStrategy, params, None, data_1h, 'single')
        eval_result = evaluate_results(results)
        
        if eval_result:
            eval_result['strategy'] = 'bollinger'
            eval_result['params'] = params
            eval_result['results'] = results
            all_results.append(eval_result)
        
        tested += 1
    
    print(f"  완료: {tested}개 테스트")
    
    # ========== 5. 브레이크아웃 전략 ==========
    print("\n" + "=" * 80)
    print("🔍 전략 5: 브레이크아웃")
    print("=" * 80)
    
    breakout_params = []
    
    for leverage in [8, 10, 12]:
        for period in [20, 50, 100]:
            for sl_pct in [1.0, 1.5, 2.0]:
                for tp_pct in [2.0, 3.0, 4.0]:
                    for cooldown in [12, 24, 48]:
                        breakout_params.append({
                            'leverage': leverage,
                            'breakout_period': period,
                            'sl_pct': sl_pct,
                            'tp_pct': tp_pct,
                            'cooldown_bars': cooldown,
                            'risk_per_trade': 2.0
                        })
    
    print(f"  테스트할 파라미터 조합: {len(breakout_params)}개")
    
    tested = 0
    for params in breakout_params:
        results = run_strategy_test(BreakoutStrategy, params, None, data_1h, 'single')
        eval_result = evaluate_results(results)
        
        if eval_result:
            eval_result['strategy'] = 'breakout'
            eval_result['params'] = params
            eval_result['results'] = results
            all_results.append(eval_result)
        
        tested += 1
    
    print(f"  완료: {tested}개 테스트")
    
    # ========== 6. EMA 크로스 전략 ==========
    print("\n" + "=" * 80)
    print("🔍 전략 6: EMA 크로스")
    print("=" * 80)
    
    ema_params = []
    
    for leverage in [8, 10, 12]:
        for fast in [8, 12, 20]:
            for slow in [21, 26, 50]:
                if fast >= slow:
                    continue
                for sl_pct in [1.0, 1.5, 2.0]:
                    for tp_pct in [1.5, 2.0, 3.0]:
                        for cooldown in [12, 24, 48]:
                            ema_params.append({
                                'leverage': leverage,
                                'ema_fast': fast,
                                'ema_slow': slow,
                                'sl_pct': sl_pct,
                                'tp_pct': tp_pct,
                                'cooldown_bars': cooldown,
                                'risk_per_trade': 2.0
                            })
    
    print(f"  테스트할 파라미터 조합: {len(ema_params)}개")
    
    tested = 0
    for params in ema_params:
        results = run_strategy_test(EMACrossStrategy, params, None, data_1h, 'single')
        eval_result = evaluate_results(results)
        
        if eval_result:
            eval_result['strategy'] = 'ema_cross'
            eval_result['params'] = params
            eval_result['results'] = results
            all_results.append(eval_result)
        
        tested += 1
    
    print(f"  완료: {tested}개 테스트")
    
    # ========== 7. ADX 추세 강도 전략 ==========
    print("\n" + "=" * 80)
    print("🔍 전략 7: ADX 추세 강도")
    print("=" * 80)
    
    adx_params = []
    
    for leverage in [8, 10, 12]:
        for adx_period in [14, 20]:
            for min_adx in [20, 25, 30]:
                for trend_ma in [50, 100]:
                    for sl_pct in [1.0, 1.5, 2.0]:
                        for tp_pct in [2.0, 3.0, 4.0]:
                            for cooldown in [12, 24]:
                                adx_params.append({
                                    'leverage': leverage,
                                    'adx_period': adx_period,
                                    'min_adx': min_adx,
                                    'trend_ma': trend_ma,
                                    'sl_pct': sl_pct,
                                    'tp_pct': tp_pct,
                                    'cooldown_bars': cooldown,
                                    'risk_per_trade': 2.0
                                })
    
    print(f"  테스트할 파라미터 조합: {len(adx_params)}개")
    
    tested = 0
    for params in adx_params:
        results = run_strategy_test(ADXTrendStrategy, params, None, data_1h, 'single')
        eval_result = evaluate_results(results)
        
        if eval_result:
            eval_result['strategy'] = 'adx_trend'
            eval_result['params'] = params
            eval_result['results'] = results
            all_results.append(eval_result)
        
        tested += 1
    
    print(f"  완료: {tested}개 테스트")
    
    # ========== 결과 분석 ==========
    print("\n" + "=" * 80)
    print("📊 결과 분석")
    print("=" * 80)
    
    # 목표 조건 필터링
    target_results = [
        r for r in all_results
        if r['all_profitable'] and r['min_wr'] >= 40 and r['max_dd'] <= 40 and 250 <= r['avg_trades'] <= 450
    ]
    
    print(f"\n전체 테스트: {len(all_results)}개")
    print(f"목표 조건 충족: {len(target_results)}개")
    
    # 점수순 정렬
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n" + "=" * 80)
    print("🏆 TOP 20 전략")
    print("=" * 80)
    
    for i, r in enumerate(all_results[:20]):
        profit = "✅" if r['all_profitable'] else "❌"
        wr = f"{r['min_wr']:.1f}%"
        dd = f"{r['max_dd']:.1f}%"
        trades = f"{r['avg_trades']:.0f}"
        ret = f"{r['avg_return']:.1f}%"
        
        print(f"\n#{i+1} {r['strategy']}")
        print(f"   Score: {r['score']:.0f} | 수익: {profit} | WR≥{wr} | DD≤{dd} | 거래 {trades}회/년 | 수익 {ret}/년")
        
        # 파라미터 출력
        key_params = ['leverage', 'sl_pct', 'tp_pct', 'cooldown_bars']
        params_str = ", ".join(f"{k}={r['params'].get(k)}" for k in key_params if k in r['params'])
        print(f"   Params: {params_str}")
    
    # 목표 조건 충족 전략들
    if target_results:
        print("\n" + "=" * 80)
        print("🎯 목표 조건 충족 전략들")
        print("=" * 80)
        
        target_results.sort(key=lambda x: x['score'], reverse=True)
        
        for i, r in enumerate(target_results[:10]):
            print(f"\n#{i+1} {r['strategy']}")
            print(f"   Score: {r['score']:.0f}")
            print(f"   거래: {r['avg_trades']:.0f}회/년 | 승률: {r['min_wr']:.1f}%+ | DD: {r['max_dd']:.1f}% | 수익: {r['avg_return']:.1f}%/년")
            print(f"   Params: {r['params']}")
            
            print("   연도별:")
            for yr in r['results']:
                print(f"     {yr['year']}: {yr['total_trades']}회 | {yr['win_rate']:.1f}% | {yr['return_pct']:.1f}%")
    
    # 결과 저장
    save_results = []
    for r in all_results[:100]:
        save_result = {
            'strategy': r['strategy'],
            'score': r['score'],
            'all_profitable': r['all_profitable'],
            'min_wr': r['min_wr'],
            'max_dd': r['max_dd'],
            'avg_return': r['avg_return'],
            'avg_trades': r['avg_trades'],
            'params': r['params']
        }
        save_results.append(save_result)
    
    with open(Path(__file__).parent / 'v5_comprehensive_results.json', 'w') as f:
        json.dump(save_results, f, indent=2, default=str)
    
    print(f"\n결과 저장: v5_comprehensive_results.json")
    
    return all_results, target_results


if __name__ == "__main__":
    comprehensive_test()
