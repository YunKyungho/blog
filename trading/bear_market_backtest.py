#!/usr/bin/env python3
"""
하락장 전용 BTC 트레이딩 전략 백테스트

테스트 기간:
- 2018년 (1월~12월): $20K → $3K (약 85% 하락)
- 2022년 (1월~12월): $69K → $15K (약 78% 하락)

테스트 전략:
1. Short Only (기존 롱 전략 반대)
2. RSI 역추세 (과매수에서 숏)
3. BB 하단 이탈 숏
4. MA 데드크로스 숏
5. 모멘텀 역전 숏
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
import requests
import time

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"
BINANCE_BASE = "https://api.binance.com"

INITIAL_BALANCE = 10000
RISK_PER_TRADE = 0.02
MAX_LEVERAGE = 5
TAKER_FEE = 0.0004  # 0.04%

# ========== 데이터 로딩 ==========

def fetch_binance_klines(symbol, interval, start_time, end_time):
    """Binance에서 캔들 데이터 가져오기"""
    url = f"{BINANCE_BASE}/api/v3/klines"
    all_data = []
    current = start_time
    
    while current < end_time:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current,
            'endTime': min(current + 1000 * 86400000, end_time),  # 1000일
            'limit': 1000
        }
        
        try:
            resp = requests.get(url, params=params)
            data = resp.json()
            if not data:
                break
            
            for k in data:
                all_data.append({
                    'time': k[0],
                    'datetime': datetime.fromtimestamp(k[0]/1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                })
            
            current = data[-1][0] + 1
            time.sleep(0.1)
        except Exception as e:
            print(f"Error fetching: {e}")
            break
    
    return all_data


def load_data_from_db(table, year):
    """DB에서 데이터 로드"""
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table} WHERE datetime LIKE '{year}%' ORDER BY timestamp"
    cursor = conn.execute(query)
    data = [{'time': r[0], 'datetime': r[1], 'open': r[2], 'high': r[3], 
             'low': r[4], 'close': r[5], 'volume': r[6]} for r in cursor]
    conn.close()
    return data


def get_bear_market_data():
    """하락장 데이터 로드"""
    data = {}
    
    # 2018년 - API에서 가져오기
    print("📥 2018년 데이터 로딩 (Binance API)...")
    start_2018 = int(datetime(2018, 1, 1).timestamp() * 1000)
    end_2018 = int(datetime(2018, 12, 31, 23, 59).timestamp() * 1000)
    data['2018'] = fetch_binance_klines('BTCUSDT', '1d', start_2018, end_2018)
    print(f"   2018: {len(data['2018'])}개 캔들 로드")
    
    # 2022년 - DB에서 가져오기
    print("📥 2022년 데이터 로딩 (DB)...")
    data['2022'] = load_data_from_db('btc_daily', '2022')
    print(f"   2022: {len(data['2022'])}개 캔들 로드")
    
    return data


# ========== 지표 계산 ==========

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
        else:  # SHORT
            pnl = (pos['entry'] - price) * pos['qty']
        
        # 수수료 적용
        pnl -= pos['entry'] * pos['qty'] * TAKER_FEE * 2
        
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
        else:  # SHORT
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
            'final_balance': self.balance
        }


# ========== 하락장 전략들 ==========

def strategy_short_only_trend(bt, params=None):
    """
    전략 1: 숏 온리 추세 추종
    - MA 아래에서만 숏
    - 모멘텀이 음수일 때 진입
    """
    if params is None:
        params = {
            'sma_period': 50,
            'mom_period': 14,
            'atr_period': 14,
            'atr_sl_mult': 2.0,
            'atr_tp_mult': 3.0,
            'mom_threshold': -3
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 20, len(data)):
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
        
        # 숏 조건: 가격 < SMA, 모멘텀 < 임계값
        if price < sma_val and mom_val < params['mom_threshold']:
            sl = price + atr_val * params['atr_sl_mult']
            tp = price - atr_val * params['atr_tp_mult']
            bt.open_position('SHORT', price, sl, tp, dt, 'TREND_SHORT')
    
    return bt.results()


def strategy_rsi_overbought_short(bt, params=None):
    """
    전략 2: RSI 과매수 역추세 숏
    - RSI > 70에서 숏 진입
    - 하락 추세 필터 적용
    """
    if params is None:
        params = {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'sma_period': 100,
            'atr_period': 14,
            'atr_sl_mult': 1.5,
            'atr_tp_mult': 2.5
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 20, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        rsi_val = rsi(data, params['rsi_period'], i)
        sma_val = sma(data, params['sma_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        
        if not all([rsi_val, sma_val, atr_val]): continue
        
        # 숏 조건: RSI 과매수 + 가격 < SMA (하락 추세)
        if rsi_val > params['rsi_overbought'] and price < sma_val:
            sl = price + atr_val * params['atr_sl_mult']
            tp = price - atr_val * params['atr_tp_mult']
            bt.open_position('SHORT', price, sl, tp, dt, 'RSI_SHORT')
    
    return bt.results()


def strategy_bb_breakdown_short(bt, params=None):
    """
    전략 3: 볼린저 밴드 하단 이탈 숏
    - BB 하단 이탈 시 숏 (추세 지속)
    - 강한 하락 추세 필터
    """
    if params is None:
        params = {
            'bb_period': 20,
            'bb_std': 2,
            'sma_period': 50,
            'atr_period': 14,
            'atr_sl_mult': 2.0,
            'atr_tp_mult': 2.5,
            'trend_strength': -5
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 20, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        upper, mid, lower = bbands(data, params['bb_period'], i, params['bb_std'])
        sma_val = sma(data, params['sma_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        mom_val = momentum(data, 20, i)
        
        if not all([lower, sma_val, atr_val, mom_val]): continue
        
        trend_pct = (price - sma_val) / sma_val * 100
        
        # 숏 조건: BB 하단 이탈 + 강한 하락 추세
        if price < lower and trend_pct < params['trend_strength']:
            sl = mid  # 중간선으로 손절
            tp = price - atr_val * params['atr_tp_mult']
            bt.open_position('SHORT', price, sl, tp, dt, 'BB_SHORT')
    
    return bt.results()


def strategy_ma_death_cross_short(bt, params=None):
    """
    전략 4: MA 데드크로스 숏
    - 단기 MA가 장기 MA 하향 돌파 시 숏
    - ADX로 추세 강도 확인
    """
    if params is None:
        params = {
            'ma_short': 20,
            'ma_long': 50,
            'adx_period': 14,
            'adx_threshold': 20,
            'atr_period': 14,
            'atr_sl_mult': 2.0,
            'atr_tp_mult': 3.0
        }
    
    data = bt.data
    prev_short_above = None
    
    for i in range(params['ma_long'] + 30, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        ma_s = sma(data, params['ma_short'], i)
        ma_l = sma(data, params['ma_long'], i)
        adx_val = adx(data, params['adx_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        
        if not all([ma_s, ma_l, adx_val, atr_val]): continue
        
        short_above = ma_s > ma_l
        
        # 데드크로스 감지
        if prev_short_above is not None and prev_short_above and not short_above:
            if not bt.position and adx_val > params['adx_threshold']:
                sl = price + atr_val * params['atr_sl_mult']
                tp = price - atr_val * params['atr_tp_mult']
                bt.open_position('SHORT', price, sl, tp, dt, 'DEATH_CROSS')
        
        prev_short_above = short_above
    
    return bt.results()


def strategy_momentum_reversal_short(bt, params=None):
    """
    전략 5: 모멘텀 역전 숏
    - 양에서 음으로 모멘텀 전환 시 숏
    - 하락 추세 필터
    """
    if params is None:
        params = {
            'mom_period': 10,
            'sma_period': 100,
            'atr_period': 14,
            'atr_sl_mult': 1.5,
            'atr_tp_mult': 2.5,
            'mom_threshold': 0
        }
    
    data = bt.data
    prev_mom = None
    
    for i in range(params['sma_period'] + 20, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        mom_val = momentum(data, params['mom_period'], i)
        sma_val = sma(data, params['sma_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        
        if not all([mom_val, sma_val, atr_val]): continue
        
        # 모멘텀 역전 감지 (양 → 음)
        if prev_mom is not None and prev_mom > params['mom_threshold'] and mom_val < params['mom_threshold']:
            if not bt.position and price < sma_val:
                sl = price + atr_val * params['atr_sl_mult']
                tp = price - atr_val * params['atr_tp_mult']
                bt.open_position('SHORT', price, sl, tp, dt, 'MOM_REV_SHORT')
        
        prev_mom = mom_val
    
    return bt.results()


def strategy_combined_bear(bt, params=None):
    """
    전략 6: 결합 하락장 전략
    - 여러 신호 결합
    - 강도에 따른 포지션 크기 조절
    """
    if params is None:
        params = {
            'sma_period': 50,
            'rsi_period': 14,
            'rsi_overbought': 65,
            'bb_period': 20,
            'atr_period': 14,
            'atr_sl_mult': 2.0,
            'atr_tp_mult': 3.0,
            'adx_threshold': 20
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 30, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        # 지표 계산
        sma_val = sma(data, params['sma_period'], i)
        rsi_val = rsi(data, params['rsi_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        mom_val = momentum(data, 14, i)
        adx_val = adx(data, 14, i)
        upper, mid, lower = bbands(data, params['bb_period'], i)
        
        if not all([sma_val, rsi_val, atr_val, mom_val, adx_val, mid]): continue
        
        # 하락 추세 필터
        if price > sma_val * 0.98:
            continue
        
        signal_strength = 0
        reason = []
        
        # RSI 과매수
        if rsi_val > params['rsi_overbought']:
            signal_strength += 1
            reason.append('RSI')
        
        # 음의 모멘텀
        if mom_val < -5:
            signal_strength += 1
            reason.append('MOM')
        
        # BB 상단 근처 (역추세)
        if price > mid:
            signal_strength += 1
            reason.append('BB')
        
        # ADX 강한 추세
        if adx_val > params['adx_threshold']:
            signal_strength += 1
            reason.append('ADX')
        
        # 2개 이상 신호 시 진입
        if signal_strength >= 2:
            sl = price + atr_val * params['atr_sl_mult']
            tp = price - atr_val * params['atr_tp_mult']
            bt.open_position('SHORT', price, sl, tp, dt, '_'.join(reason))
    
    return bt.results()


def strategy_pullback_short(bt, params=None):
    """
    전략 7: 풀백 후 숏 (하락 추세 중 반등에서 숏)
    - 하락 추세 중 일시적 반등 후 다시 하락 시 진입
    """
    if params is None:
        params = {
            'sma_period': 50,
            'pullback_pct': 3,  # 최소 풀백 %
            'max_pullback': 10, # 최대 풀백 %
            'atr_period': 14,
            'atr_sl_mult': 1.5,
            'atr_tp_mult': 2.5,
            'lookback': 10
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 20, len(data)):
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma_val = sma(data, params['sma_period'], i)
        atr_val = atr(data, params['atr_period'], i)
        
        if not all([sma_val, atr_val]): continue
        
        # 하락 추세 확인
        if price > sma_val:
            continue
        
        # 최근 저점 찾기
        lookback = params['lookback']
        recent_low = min(d['low'] for d in data[i-lookback:i])
        recent_high = max(d['high'] for d in data[i-lookback:i])
        
        # 풀백 계산 (저점에서 얼마나 반등했나)
        pullback_pct = (price - recent_low) / recent_low * 100
        
        # 풀백 조건: 적당한 반등 후 음봉
        if params['pullback_pct'] < pullback_pct < params['max_pullback']:
            if candle['close'] < candle['open']:  # 음봉
                sl = recent_high
                tp = price - atr_val * params['atr_tp_mult']
                bt.open_position('SHORT', price, sl, tp, dt, 'PULLBACK_SHORT')
    
    return bt.results()


# ========== 파라미터 최적화 ==========

def optimize_strategy(strategy_func, param_grid, data_dict, verbose=False):
    """파라미터 최적화"""
    from itertools import product
    
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(product(*param_values))
    
    best_score = float('-inf')
    best_params = None
    best_results = None
    
    for combo in combinations:
        params = dict(zip(param_names, combo))
        
        all_results = []
        for year, data in data_dict.items():
            if len(data) < 100:
                continue
            
            bt = Backtester(data)
            result = strategy_func(bt, params)
            result['year'] = year
            all_results.append(result)
        
        if not all_results:
            continue
        
        # 점수 계산: 수익률 - DD - 손실 패널티
        total_return = sum(r['return_pct'] for r in all_results)
        avg_dd = sum(r['max_dd'] for r in all_results) / len(all_results)
        loss_years = sum(1 for r in all_results if r['return_pct'] < 0)
        
        score = total_return - avg_dd * 1.5 - loss_years * 50
        
        if score > best_score:
            best_score = score
            best_params = params
            best_results = all_results
            
            if verbose:
                print(f"   New best: {params}")
                print(f"   Score: {score:.1f}, Return: {total_return:.1f}%")
    
    return best_params, best_results, best_score


# ========== 메인 실행 ==========

def run_bear_market_backtest():
    """하락장 백테스트 실행"""
    print("=" * 70)
    print("🐻 BTC 하락장 전용 전략 백테스트")
    print("=" * 70)
    
    # 데이터 로드
    data_dict = get_bear_market_data()
    
    if not data_dict.get('2018') and not data_dict.get('2022'):
        print("❌ 데이터를 로드할 수 없습니다.")
        return
    
    strategies = [
        ("Short Only Trend", strategy_short_only_trend),
        ("RSI Overbought Short", strategy_rsi_overbought_short),
        ("BB Breakdown Short", strategy_bb_breakdown_short),
        ("MA Death Cross Short", strategy_ma_death_cross_short),
        ("Momentum Reversal Short", strategy_momentum_reversal_short),
        ("Combined Bear", strategy_combined_bear),
        ("Pullback Short", strategy_pullback_short),
    ]
    
    results_all = {}
    
    for name, func in strategies:
        print(f"\n📊 {name}")
        print("-" * 50)
        
        year_results = []
        for year, data in data_dict.items():
            if len(data) < 100:
                continue
            
            bt = Backtester(data)
            result = func(bt)
            result['year'] = year
            year_results.append(result)
            
            print(f"  {year}: 거래 {result['trades']:>3} | 승률 {result['win_rate']:>5.1f}% | "
                  f"수익률 {result['return_pct']:>7.1f}% | MDD {result['max_dd']:>5.1f}%")
        
        if year_results:
            total_return = sum(r['return_pct'] for r in year_results)
            avg_dd = sum(r['max_dd'] for r in year_results) / len(year_results)
            avg_wr = sum(r['win_rate'] for r in year_results) / len(year_results)
            
            print(f"  ────────────────────────────────────────────────")
            print(f"  총합: 수익률 {total_return:.1f}% | 평균MDD {avg_dd:.1f}% | 승률 {avg_wr:.1f}%")
            
            results_all[name] = {
                'years': year_results,
                'total_return': total_return,
                'avg_dd': avg_dd,
                'avg_wr': avg_wr
            }
    
    # 최고 전략 선정
    print("\n" + "=" * 70)
    print("🏆 전략 순위")
    print("=" * 70)
    
    sorted_results = sorted(results_all.items(), 
                           key=lambda x: x[1]['total_return'] - x[1]['avg_dd'] * 1.5, 
                           reverse=True)
    
    for i, (name, res) in enumerate(sorted_results, 1):
        score = res['total_return'] - res['avg_dd'] * 1.5
        print(f"{i}. {name}")
        print(f"   수익률: {res['total_return']:.1f}% | MDD: {res['avg_dd']:.1f}% | 승률: {res['avg_wr']:.1f}% | 점수: {score:.1f}")
    
    return results_all, sorted_results


def optimize_best_strategy(data_dict):
    """최고 전략 파라미터 최적화"""
    print("\n" + "=" * 70)
    print("🔧 Combined Bear 전략 최적화")
    print("=" * 70)
    
    param_grid = {
        'sma_period': [30, 50, 75],
        'rsi_period': [10, 14],
        'rsi_overbought': [60, 65, 70],
        'bb_period': [20],
        'atr_period': [14],
        'atr_sl_mult': [1.5, 2.0, 2.5],
        'atr_tp_mult': [2.5, 3.0, 4.0],
        'adx_threshold': [15, 20, 25]
    }
    
    print(f"총 {len(list(__import__('itertools').product(*param_grid.values())))}개 조합 테스트...")
    
    best_params, best_results, best_score = optimize_strategy(
        strategy_combined_bear, param_grid, data_dict, verbose=True
    )
    
    print(f"\n✅ 최적 파라미터:")
    print(json.dumps(best_params, indent=2))
    print(f"\n📊 최적 결과:")
    for r in best_results:
        print(f"   {r['year']}: 수익률 {r['return_pct']:.1f}% | MDD {r['max_dd']:.1f}%")
    
    return best_params, best_results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'optimize':
        data_dict = get_bear_market_data()
        optimize_best_strategy(data_dict)
    else:
        results, ranking = run_bear_market_backtest()
        
        # 결과 저장
        output = {
            'timestamp': datetime.now().isoformat(),
            'results': {},
            'ranking': []
        }
        
        for name, res in results.items():
            output['results'][name] = {
                'total_return': res['total_return'],
                'avg_dd': res['avg_dd'],
                'avg_wr': res['avg_wr']
            }
        
        for name, res in ranking:
            output['ranking'].append({
                'name': name,
                'score': res['total_return'] - res['avg_dd'] * 1.5
            })
        
        with open(Path(__file__).parent / 'bear_market_results.json', 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 결과 저장: bear_market_results.json")
