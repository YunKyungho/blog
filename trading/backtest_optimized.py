#!/usr/bin/env python3
"""
최적화된 BTC 선물 트레이딩 전략 백테스트
목표: 모든 연도(2019-2025) 안정적 수익

전략 1: 롱 온리 추세 추종 (Reddit 기반)
- Close > SMA(50) + Close > EMA(7) + RSI(2) > ADX(2)

전략 2: 듀얼 모멘텀
- 절대 모멘텀 + 상대 모멘텀

전략 3: ATR 기반 동적 손절 브레이크아웃
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
import math

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

# 설정
LEVERAGE = 10  # 레버리지 낮춤
INITIAL_BALANCE = 5000
RISK_PER_TRADE = 0.02  # 거래당 리스크 2%

# ========== 데이터 로드 ==========

def load_data(table, start_date=None, end_date=None):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table}"
    conditions = []
    if start_date:
        conditions.append(f"datetime >= '{start_date}'")
    if end_date:
        conditions.append(f"datetime <= '{end_date}'")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY timestamp"
    
    cursor = conn.execute(query)
    data = []
    for row in cursor:
        data.append({
            'time': row[0], 'datetime': row[1],
            'open': row[2], 'high': row[3], 'low': row[4], 
            'close': row[5], 'volume': row[6]
        })
    conn.close()
    return data

# ========== 지표 계산 ==========

def calc_sma(data, period, idx):
    """단순 이동평균"""
    if idx < period:
        return None
    return sum(d['close'] for d in data[idx-period:idx]) / period

def calc_ema(data, period, idx):
    """지수 이동평균"""
    if idx < period:
        return None
    multiplier = 2 / (period + 1)
    ema = data[0]['close']
    for i in range(1, idx + 1):
        ema = (data[i]['close'] - ema) * multiplier + ema
    return ema

def calc_rsi(data, period, idx):
    """RSI"""
    if idx < period + 1:
        return None
    gains = []
    losses = []
    for i in range(idx - period, idx):
        change = data[i + 1]['close'] - data[i]['close']
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_atr(data, period, idx):
    """ATR (Average True Range)"""
    if idx < period + 1:
        return None
    
    tr_list = []
    for i in range(idx - period, idx):
        high = data[i]['high']
        low = data[i]['low']
        prev_close = data[i - 1]['close'] if i > 0 else data[i]['open']
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    
    return sum(tr_list) / period

def calc_adx(data, period, idx):
    """ADX (Average Directional Index)"""
    if idx < period * 2:
        return None
    
    plus_dm_list = []
    minus_dm_list = []
    tr_list = []
    
    for i in range(idx - period * 2, idx):
        if i == 0:
            continue
        high = data[i]['high']
        low = data[i]['low']
        prev_high = data[i - 1]['high']
        prev_low = data[i - 1]['low']
        prev_close = data[i - 1]['close']
        
        up_move = high - prev_high
        down_move = prev_low - low
        
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)
    
    if not tr_list or sum(tr_list[-period:]) == 0:
        return 0
    
    smooth_plus_dm = sum(plus_dm_list[-period:])
    smooth_minus_dm = sum(minus_dm_list[-period:])
    smooth_tr = sum(tr_list[-period:])
    
    plus_di = 100 * smooth_plus_dm / smooth_tr if smooth_tr > 0 else 0
    minus_di = 100 * smooth_minus_dm / smooth_tr if smooth_tr > 0 else 0
    
    if plus_di + minus_di == 0:
        return 0
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return dx

def calc_donchian(data, period, idx):
    """돈치안 채널"""
    if idx < period:
        return None, None
    
    high_max = max(d['high'] for d in data[idx-period:idx])
    low_min = min(d['low'] for d in data[idx-period:idx])
    return high_max, low_min

def calc_momentum(data, period, idx):
    """모멘텀 (ROC)"""
    if idx < period:
        return None
    prev_close = data[idx - period]['close']
    if prev_close == 0:
        return 0
    return (data[idx]['close'] - prev_close) / prev_close * 100


# ========== 전략 클래스 ==========

class Strategy:
    def __init__(self, name):
        self.name = name
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.peak_balance = INITIAL_BALANCE
        self.max_drawdown = 0
    
    def reset(self):
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.peak_balance = INITIAL_BALANCE
        self.max_drawdown = 0


class LongOnlyTrendFollowing(Strategy):
    """
    전략 1: 롱 온리 추세 추종
    - SMA(50) 위에서만 롱
    - EMA(7) 위일 때 진입
    - RSI(2) > ADX(2) 필터
    - ATR 기반 손절
    """
    
    def __init__(self, sma_period=50, ema_period=7, rsi_period=14, atr_period=14, atr_mult=2.0, rr_ratio=2.0):
        super().__init__("LongOnly_TrendFollow")
        self.sma_period = sma_period
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.rr_ratio = rr_ratio
    
    def check_entry(self, data, idx):
        """진입 조건 체크"""
        if idx < max(self.sma_period, self.rsi_period, self.atr_period) + 10:
            return None
        
        price = data[idx]['close']
        sma = calc_sma(data, self.sma_period, idx)
        ema = calc_ema(data, self.ema_period, idx)
        rsi = calc_rsi(data, self.rsi_period, idx)
        atr = calc_atr(data, self.atr_period, idx)
        
        if sma is None or ema is None or rsi is None or atr is None:
            return None
        
        # 롱 진입 조건: 가격 > SMA(50), 가격 > EMA(7), RSI < 70
        if price > sma and price > ema and rsi < 70 and rsi > 30:
            sl = price - (atr * self.atr_mult)
            tp = price + (atr * self.atr_mult * self.rr_ratio)
            
            return {
                'side': 'LONG',
                'entry': price,
                'sl': sl,
                'tp': tp,
                'atr': atr
            }
        
        return None
    
    def check_exit(self, data, idx):
        """청산 조건 체크"""
        if self.position is None:
            return None
        
        price = data[idx]['close']
        sma = calc_sma(data, self.sma_period, idx)
        
        # SMA 아래로 떨어지면 청산
        if sma and price < sma:
            return 'TREND_BREAK'
        
        return None


class DualMomentum(Strategy):
    """
    전략 2: 듀얼 모멘텀
    - 절대 모멘텀: 20일 수익률 > 0
    - 추세 필터: SMA(100) 위
    - ATR 기반 손절
    """
    
    def __init__(self, mom_period=20, sma_period=100, atr_period=14, atr_mult=2.0, rr_ratio=2.0):
        super().__init__("Dual_Momentum")
        self.mom_period = mom_period
        self.sma_period = sma_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.rr_ratio = rr_ratio
    
    def check_entry(self, data, idx):
        if idx < max(self.sma_period, self.mom_period, self.atr_period) + 10:
            return None
        
        price = data[idx]['close']
        sma = calc_sma(data, self.sma_period, idx)
        momentum = calc_momentum(data, self.mom_period, idx)
        atr = calc_atr(data, self.atr_period, idx)
        
        if sma is None or momentum is None or atr is None:
            return None
        
        # 롱: 가격 > SMA, 모멘텀 > 0
        if price > sma and momentum > 0:
            sl = price - (atr * self.atr_mult)
            tp = price + (atr * self.atr_mult * self.rr_ratio)
            
            return {
                'side': 'LONG',
                'entry': price,
                'sl': sl,
                'tp': tp,
                'momentum': momentum
            }
        
        return None
    
    def check_exit(self, data, idx):
        if self.position is None:
            return None
        
        momentum = calc_momentum(data, self.mom_period, idx)
        
        # 모멘텀이 음수로 전환되면 청산
        if momentum is not None and momentum < -5:  # 5% 하락
            return 'MOMENTUM_NEGATIVE'
        
        return None


class DonchianBreakout(Strategy):
    """
    전략 3: 돈치안 채널 브레이크아웃
    - 20일 고가 돌파 시 롱
    - 10일 저가 이탈 시 청산
    """
    
    def __init__(self, entry_period=20, exit_period=10, atr_period=14, atr_mult=2.0, sma_period=50):
        super().__init__("Donchian_Breakout")
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.sma_period = sma_period
    
    def check_entry(self, data, idx):
        if idx < max(self.entry_period, self.atr_period, self.sma_period) + 10:
            return None
        
        price = data[idx]['close']
        prev_high = data[idx - 1]['high']
        
        upper, lower = calc_donchian(data, self.entry_period, idx - 1)  # 이전 기간 기준
        sma = calc_sma(data, self.sma_period, idx)
        atr = calc_atr(data, self.atr_period, idx)
        
        if upper is None or sma is None or atr is None:
            return None
        
        # 추세 필터 + 돌파
        if price > sma and data[idx]['high'] > upper:
            sl = price - (atr * self.atr_mult)
            tp = price + (atr * self.atr_mult * 2.0)
            
            return {
                'side': 'LONG',
                'entry': price,
                'sl': sl,
                'tp': tp,
                'breakout_level': upper
            }
        
        return None
    
    def check_exit(self, data, idx):
        if self.position is None:
            return None
        
        _, lower = calc_donchian(data, self.exit_period, idx - 1)
        
        if lower and data[idx]['low'] < lower:
            return 'DONCHIAN_EXIT'
        
        return None


class AdaptiveStrategy(Strategy):
    """
    전략 4: 적응형 전략
    - 상승 추세: 롱 온리
    - 하락 추세: 관망 또는 숏
    - 횡보: 평균회귀
    """
    
    def __init__(self, trend_sma=100, fast_sma=20, rsi_period=14, atr_period=14, atr_mult=1.5, rr_ratio=2.5):
        super().__init__("Adaptive")
        self.trend_sma = trend_sma
        self.fast_sma = fast_sma
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.rr_ratio = rr_ratio
    
    def get_regime(self, data, idx):
        """시장 레짐 판단"""
        if idx < self.trend_sma + 20:
            return 'UNKNOWN'
        
        price = data[idx]['close']
        sma_long = calc_sma(data, self.trend_sma, idx)
        sma_short = calc_sma(data, self.fast_sma, idx)
        
        # 추세 강도 계산
        if sma_long is None or sma_short is None:
            return 'UNKNOWN'
        
        trend_strength = (price - sma_long) / sma_long * 100
        
        if trend_strength > 10:
            return 'STRONG_UP'
        elif trend_strength > 0:
            return 'UP'
        elif trend_strength > -10:
            return 'DOWN'
        else:
            return 'STRONG_DOWN'
    
    def check_entry(self, data, idx):
        if idx < max(self.trend_sma, self.rsi_period, self.atr_period) + 20:
            return None
        
        regime = self.get_regime(data, idx)
        price = data[idx]['close']
        rsi = calc_rsi(data, self.rsi_period, idx)
        atr = calc_atr(data, self.atr_period, idx)
        sma_long = calc_sma(data, self.trend_sma, idx)
        sma_short = calc_sma(data, self.fast_sma, idx)
        
        if rsi is None or atr is None or sma_long is None or sma_short is None:
            return None
        
        signal = None
        
        # 상승 추세: 풀백에서 롱
        if regime in ['STRONG_UP', 'UP']:
            if rsi < 40 and price > sma_long:  # RSI 과매도 + 추세 위
                sl = price - (atr * self.atr_mult)
                tp = price + (atr * self.atr_mult * self.rr_ratio)
                signal = {'side': 'LONG', 'entry': price, 'sl': sl, 'tp': tp, 'regime': regime}
        
        # 하락 추세: 관망 (현재는 롱만)
        elif regime in ['STRONG_DOWN', 'DOWN']:
            # 강한 과매도에서만 반등 롱
            if rsi < 25:
                sl = price - (atr * self.atr_mult * 1.5)
                tp = price + (atr * self.atr_mult * 1.5)
                signal = {'side': 'LONG', 'entry': price, 'sl': sl, 'tp': tp, 'regime': regime}
        
        return signal
    
    def check_exit(self, data, idx):
        if self.position is None:
            return None
        
        rsi = calc_rsi(data, self.rsi_period, idx)
        
        # RSI 과매수시 청산
        if rsi and rsi > 75:
            return 'RSI_OVERBOUGHT'
        
        return None


# ========== 백테스트 엔진 ==========

class BacktestEngine:
    def __init__(self, strategy, data, leverage=LEVERAGE):
        self.strategy = strategy
        self.data = data
        self.leverage = leverage
        self.strategy.reset()
    
    def run(self, check_interval=1, verbose=False):
        """백테스트 실행"""
        data = self.data
        strategy = self.strategy
        
        for i in range(100, len(data), check_interval):
            current = data[i]
            price = current['close']
            dt = current['datetime']
            
            # 포지션 있으면 SL/TP/Exit 체크
            if strategy.position:
                # SL/TP 체크
                for j in range(max(0, i - check_interval), i + 1):
                    if j >= len(data):
                        break
                    candle = data[j]
                    
                    if strategy.position['side'] == 'LONG':
                        if candle['low'] <= strategy.position['sl']:
                            self._close_position(strategy.position['sl'], 'SL', candle['datetime'])
                            break
                        if candle['high'] >= strategy.position['tp']:
                            self._close_position(strategy.position['tp'], 'TP', candle['datetime'])
                            break
                    else:  # SHORT
                        if candle['high'] >= strategy.position['sl']:
                            self._close_position(strategy.position['sl'], 'SL', candle['datetime'])
                            break
                        if candle['low'] <= strategy.position['tp']:
                            self._close_position(strategy.position['tp'], 'TP', candle['datetime'])
                            break
                
                # 전략별 청산 조건
                if strategy.position:
                    exit_reason = strategy.check_exit(data, i)
                    if exit_reason:
                        self._close_position(price, exit_reason, dt)
            
            # 포지션 없으면 진입 체크
            if not strategy.position:
                signal = strategy.check_entry(data, i)
                if signal:
                    self._open_position(signal, dt)
                    if verbose:
                        print(f"[{dt}] {signal['side']} @ ${price:,.0f}")
            
            # 자본 기록
            current_equity = strategy.balance
            if strategy.position:
                if strategy.position['side'] == 'LONG':
                    unrealized = (price - strategy.position['entry']) * strategy.position['quantity']
                else:
                    unrealized = (strategy.position['entry'] - price) * strategy.position['quantity']
                current_equity += unrealized
            
            strategy.equity_curve.append({'time': dt, 'balance': current_equity})
            
            # 최대 낙폭 업데이트
            if current_equity > strategy.peak_balance:
                strategy.peak_balance = current_equity
            dd = (strategy.peak_balance - current_equity) / strategy.peak_balance * 100
            if dd > strategy.max_drawdown:
                strategy.max_drawdown = dd
            
            # 파산 체크
            if strategy.balance <= 0:
                break
        
        return self._get_results()
    
    def _open_position(self, signal, dt):
        """포지션 오픈"""
        qty = (self.strategy.balance * self.leverage) / signal['entry']
        
        self.strategy.position = {
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'quantity': qty,
            'datetime': dt
        }
    
    def _close_position(self, price, reason, dt):
        """포지션 청산"""
        pos = self.strategy.position
        entry = pos['entry']
        qty = pos['quantity']
        
        if pos['side'] == 'LONG':
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * qty
        
        pnl_pct = (pnl / self.strategy.balance) * 100
        self.strategy.balance += pnl
        
        self.strategy.trades.append({
            'side': pos['side'],
            'entry': entry,
            'exit': price,
            'entry_time': pos['datetime'],
            'exit_time': dt,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'balance_after': self.strategy.balance
        })
        
        self.strategy.position = None
    
    def _get_results(self):
        """결과 반환"""
        trades = self.strategy.trades
        if not trades:
            return {'total_trades': 0, 'win_rate': 0, 'return_pct': 0, 'max_drawdown': 0}
        
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        
        return {
            'total_trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'total_pnl': sum(t['pnl'] for t in trades),
            'final_balance': self.strategy.balance,
            'return_pct': (self.strategy.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            'max_drawdown': self.strategy.max_drawdown,
            'avg_win': sum(t['pnl'] for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t['pnl'] for t in losses) / len(losses) if losses else 0,
            'profit_factor': abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0
        }


def run_strategy_test(StrategyClass, params, data, name=""):
    """전략 테스트"""
    strategy = StrategyClass(**params)
    engine = BacktestEngine(strategy, data)
    result = engine.run()
    result['strategy'] = name or strategy.name
    return result


def grid_search():
    """파라미터 그리드 서치"""
    print("📥 데이터 로드 중...")
    data_daily = load_data('btc_daily')
    print(f"  일봉: {len(data_daily):,}개")
    print(f"  기간: {data_daily[0]['datetime']} ~ {data_daily[-1]['datetime']}")
    
    # 테스트할 파라미터 조합
    param_grids = {
        'LongOnlyTrendFollowing': [
            {'sma_period': 50, 'ema_period': 7, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.0},
            {'sma_period': 50, 'ema_period': 10, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 1.5, 'rr_ratio': 2.5},
            {'sma_period': 100, 'ema_period': 20, 'rsi_period': 14, 'atr_period': 20, 'atr_mult': 2.0, 'rr_ratio': 2.0},
            {'sma_period': 200, 'ema_period': 50, 'rsi_period': 14, 'atr_period': 20, 'atr_mult': 1.5, 'rr_ratio': 3.0},
        ],
        'DualMomentum': [
            {'mom_period': 20, 'sma_period': 100, 'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.0},
            {'mom_period': 30, 'sma_period': 50, 'atr_period': 14, 'atr_mult': 1.5, 'rr_ratio': 2.5},
            {'mom_period': 10, 'sma_period': 100, 'atr_period': 20, 'atr_mult': 2.0, 'rr_ratio': 2.0},
        ],
        'DonchianBreakout': [
            {'entry_period': 20, 'exit_period': 10, 'atr_period': 14, 'atr_mult': 2.0, 'sma_period': 50},
            {'entry_period': 55, 'exit_period': 20, 'atr_period': 20, 'atr_mult': 1.5, 'sma_period': 100},
            {'entry_period': 20, 'exit_period': 10, 'atr_period': 14, 'atr_mult': 1.5, 'sma_period': 100},
        ],
        'AdaptiveStrategy': [
            {'trend_sma': 100, 'fast_sma': 20, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 1.5, 'rr_ratio': 2.5},
            {'trend_sma': 50, 'fast_sma': 10, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.0},
            {'trend_sma': 200, 'fast_sma': 50, 'rsi_period': 14, 'atr_period': 20, 'atr_mult': 1.5, 'rr_ratio': 3.0},
        ]
    }
    
    strategy_classes = {
        'LongOnlyTrendFollowing': LongOnlyTrendFollowing,
        'DualMomentum': DualMomentum,
        'DonchianBreakout': DonchianBreakout,
        'AdaptiveStrategy': AdaptiveStrategy
    }
    
    all_results = []
    
    for strategy_name, param_list in param_grids.items():
        print(f"\n{'='*60}")
        print(f"📊 {strategy_name} 테스트")
        print("=" * 60)
        
        StrategyClass = strategy_classes[strategy_name]
        
        for params in param_list:
            result = run_strategy_test(StrategyClass, params, data_daily)
            result['params'] = params
            all_results.append(result)
            
            print(f"  {params}")
            print(f"    → 거래: {result['total_trades']} | 승률: {result['win_rate']:.1f}% | "
                  f"수익률: {result['return_pct']:.1f}% | MDD: {result['max_drawdown']:.1f}%")
    
    # 결과 정렬 (수익률 기준)
    all_results.sort(key=lambda x: x['return_pct'], reverse=True)
    
    print("\n" + "=" * 80)
    print("🏆 상위 5개 전략")
    print("=" * 80)
    for i, r in enumerate(all_results[:5]):
        print(f"{i+1}. {r['strategy']}")
        print(f"   거래: {r['total_trades']} | 승률: {r['win_rate']:.1f}% | "
              f"수익률: {r['return_pct']:.1f}% | MDD: {r['max_drawdown']:.1f}%")
        print(f"   파라미터: {r['params']}")
    
    return all_results


def run_yearly_test(StrategyClass, params, verbose=True):
    """연도별 백테스트"""
    if verbose:
        print("📥 데이터 로드 중...")
    
    data_daily = load_data('btc_daily')
    
    if verbose:
        print(f"  일봉: {len(data_daily):,}개")
    
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    all_results = []
    
    for year in years:
        year_data = [k for k in data_daily if k['datetime'][:4] == year]
        
        if len(year_data) < 100:
            continue
        
        result = run_strategy_test(StrategyClass, params, year_data, f"{StrategyClass.__name__}")
        result['year'] = year
        all_results.append(result)
        
        if verbose:
            print(f"  {year}: 거래 {result['total_trades']:>3} | 승률 {result['win_rate']:>5.1f}% | "
                  f"수익률 {result['return_pct']:>8.1f}% | MDD {result['max_drawdown']:>5.1f}%")
    
    return all_results


def find_best_strategy():
    """최적 전략 찾기"""
    print("🔍 최적 전략 탐색 시작")
    print("=" * 80)
    
    strategies_to_test = [
        (LongOnlyTrendFollowing, {'sma_period': 50, 'ema_period': 7, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.0}),
        (LongOnlyTrendFollowing, {'sma_period': 100, 'ema_period': 20, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 1.5, 'rr_ratio': 2.5}),
        (LongOnlyTrendFollowing, {'sma_period': 200, 'ema_period': 50, 'rsi_period': 14, 'atr_period': 20, 'atr_mult': 2.0, 'rr_ratio': 3.0}),
        (DualMomentum, {'mom_period': 20, 'sma_period': 100, 'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.0}),
        (DualMomentum, {'mom_period': 10, 'sma_period': 50, 'atr_period': 14, 'atr_mult': 1.5, 'rr_ratio': 2.5}),
        (DonchianBreakout, {'entry_period': 20, 'exit_period': 10, 'atr_period': 14, 'atr_mult': 2.0, 'sma_period': 50}),
        (DonchianBreakout, {'entry_period': 55, 'exit_period': 20, 'atr_period': 20, 'atr_mult': 1.5, 'sma_period': 100}),
        (AdaptiveStrategy, {'trend_sma': 100, 'fast_sma': 20, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 1.5, 'rr_ratio': 2.5}),
        (AdaptiveStrategy, {'trend_sma': 200, 'fast_sma': 50, 'rsi_period': 14, 'atr_period': 20, 'atr_mult': 2.0, 'rr_ratio': 3.0}),
    ]
    
    best_strategy = None
    best_score = float('-inf')
    best_results = None
    
    for StrategyClass, params in strategies_to_test:
        print(f"\n📊 {StrategyClass.__name__} 테스트")
        print(f"   파라미터: {params}")
        
        yearly_results = run_yearly_test(StrategyClass, params, verbose=True)
        
        # 점수 계산: 모든 연도 수익률 합 - 최대낙폭 페널티 - 손실 연도 페널티
        total_return = sum(r['return_pct'] for r in yearly_results)
        avg_drawdown = sum(r['max_drawdown'] for r in yearly_results) / len(yearly_results)
        loss_years = sum(1 for r in yearly_results if r['return_pct'] < 0)
        avg_win_rate = sum(r['win_rate'] for r in yearly_results) / len(yearly_results)
        
        # 점수: 총수익률 - 낙폭 - 손실연도*100
        score = total_return - avg_drawdown - (loss_years * 200)
        
        print(f"   → 총수익률: {total_return:.1f}% | 평균MDD: {avg_drawdown:.1f}% | 손실연도: {loss_years} | 점수: {score:.1f}")
        
        if score > best_score:
            best_score = score
            best_strategy = (StrategyClass, params)
            best_results = yearly_results
    
    print("\n" + "=" * 80)
    print("🏆 최적 전략 발견!")
    print("=" * 80)
    if best_strategy:
        StrategyClass, params = best_strategy
        print(f"전략: {StrategyClass.__name__}")
        print(f"파라미터: {params}")
        print(f"점수: {best_score:.1f}")
        print("\n연도별 성과:")
        for r in best_results:
            print(f"  {r['year']}: 거래 {r['total_trades']:>3} | 승률 {r['win_rate']:>5.1f}% | "
                  f"수익률 {r['return_pct']:>8.1f}% | MDD {r['max_drawdown']:>5.1f}%")
    
    return best_strategy, best_results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'grid':
            grid_search()
        elif sys.argv[1] == 'best':
            find_best_strategy()
        elif sys.argv[1] == 'yearly':
            # 특정 전략 연도별 테스트
            strategy_name = sys.argv[2] if len(sys.argv) > 2 else 'LongOnlyTrendFollowing'
            strategies = {
                'long': (LongOnlyTrendFollowing, {'sma_period': 50, 'ema_period': 7, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.0}),
                'dual': (DualMomentum, {'mom_period': 20, 'sma_period': 100, 'atr_period': 14, 'atr_mult': 2.0, 'rr_ratio': 2.0}),
                'donchian': (DonchianBreakout, {'entry_period': 20, 'exit_period': 10, 'atr_period': 14, 'atr_mult': 2.0, 'sma_period': 50}),
                'adaptive': (AdaptiveStrategy, {'trend_sma': 100, 'fast_sma': 20, 'rsi_period': 14, 'atr_period': 14, 'atr_mult': 1.5, 'rr_ratio': 2.5}),
            }
            if strategy_name in strategies:
                StrategyClass, params = strategies[strategy_name]
                run_yearly_test(StrategyClass, params)
            else:
                print(f"Available: {list(strategies.keys())}")
    else:
        find_best_strategy()
