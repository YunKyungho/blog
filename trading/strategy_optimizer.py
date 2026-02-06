#!/usr/bin/env python3
"""
전략 최적화 - 그리드 서치
목표: 모든 연도에서 안정적인 전략 찾기
"""

import sqlite3
import json
import itertools
from datetime import datetime
from pathlib import Path

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"
RESULTS_PATH = Path(__file__).parent / 'optimization_results.json'

# 고정 설정
LEVERAGE = 20
INITIAL_BALANCE = 5000

def load_data(table, start_date=None, end_date=None):
    """데이터베이스에서 캔들 로드"""
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
            'time': row[0],
            'datetime': row[1],
            'open': row[2],
            'high': row[3],
            'low': row[4],
            'close': row[5],
            'volume': row[6]
        })
    
    conn.close()
    return data

# ========== 지표 계산 ==========

def calc_sma(data, period, idx):
    """단순이동평균"""
    if idx < period:
        return None
    return sum(d['close'] for d in data[idx-period:idx]) / period

def calc_ema(data, period, idx, prev_ema=None):
    """지수이동평균"""
    if idx < period:
        return None
    if prev_ema is None:
        return calc_sma(data, period, idx)
    k = 2 / (period + 1)
    return data[idx-1]['close'] * k + prev_ema * (1 - k)

def calc_rsi(data, period, idx):
    """RSI"""
    if idx < period + 1:
        return None
    
    gains = []
    losses = []
    
    for i in range(idx - period, idx):
        change = data[i]['close'] - data[i-1]['close']
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
    
    trs = []
    for i in range(idx - period, idx):
        high = data[i]['high']
        low = data[i]['low']
        prev_close = data[i-1]['close']
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    
    return sum(trs) / period

def calc_donchian(data, period, idx):
    """돈치안 채널 (고점/저점)"""
    if idx < period:
        return None, None
    
    highs = [d['high'] for d in data[idx-period:idx]]
    lows = [d['low'] for d in data[idx-period:idx]]
    
    return max(highs), min(lows)

def calc_bollinger(data, period, idx, std_dev=2):
    """볼린저 밴드"""
    if idx < period:
        return None, None, None
    
    closes = [d['close'] for d in data[idx-period:idx]]
    sma = sum(closes) / period
    
    variance = sum((c - sma) ** 2 for c in closes) / period
    std = variance ** 0.5
    
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    
    return upper, sma, lower

# ========== 전략 클래스 ==========

class Strategy:
    def __init__(self, params):
        self.params = params
        self.position = None
        self.trades = []
        self.balance = INITIAL_BALANCE
    
    def reset(self):
        self.position = None
        self.trades = []
        self.balance = INITIAL_BALANCE
    
    def get_trend(self, data_daily, idx):
        """일봉 추세 판단"""
        ma_period = self.params.get('trend_ma_period', 20)
        ma_type = self.params.get('trend_ma_type', 'sma')
        
        if ma_type == 'sma':
            ma = calc_sma(data_daily, ma_period, idx)
        else:
            ma = calc_ema(data_daily, ma_period, idx)
        
        if ma is None:
            return 'UNKNOWN'
        
        return 'UP' if data_daily[idx-1]['close'] > ma else 'DOWN'
    
    def check_entry(self, data, idx, trend, strategy_type):
        """진입 조건 체크"""
        price = data[idx-1]['close']
        
        if strategy_type == 'trend_follow':
            return self._check_trend_follow(data, idx, trend, price)
        elif strategy_type == 'breakout':
            return self._check_breakout(data, idx, trend, price)
        elif strategy_type == 'mean_reversion':
            return self._check_mean_reversion(data, idx, trend, price)
        elif strategy_type == 'rsi_trend':
            return self._check_rsi_trend(data, idx, trend, price)
        
        return None
    
    def _check_trend_follow(self, data, idx, trend, price):
        """추세추종 전략"""
        fast_ma = calc_ema(data, self.params.get('fast_ma', 10), idx)
        slow_ma = calc_ema(data, self.params.get('slow_ma', 30), idx)
        
        if fast_ma is None or slow_ma is None:
            return None
        
        # 추세 방향으로만 진입
        if trend == 'UP' and fast_ma > slow_ma:
            atr = calc_atr(data, 14, idx)
            if atr is None:
                return None
            sl_dist = atr * self.params.get('atr_sl_mult', 2)
            rr = self.params.get('rr_ratio', 2)
            return {
                'side': 'LONG',
                'entry': price,
                'sl': price - sl_dist,
                'tp': price + sl_dist * rr
            }
        
        if trend == 'DOWN' and fast_ma < slow_ma:
            atr = calc_atr(data, 14, idx)
            if atr is None:
                return None
            sl_dist = atr * self.params.get('atr_sl_mult', 2)
            rr = self.params.get('rr_ratio', 2)
            return {
                'side': 'SHORT',
                'entry': price,
                'sl': price + sl_dist,
                'tp': price - sl_dist * rr
            }
        
        return None
    
    def _check_breakout(self, data, idx, trend, price):
        """돈치안 채널 브레이크아웃"""
        period = self.params.get('donchian_period', 20)
        upper, lower = calc_donchian(data, period, idx)
        
        if upper is None:
            return None
        
        atr = calc_atr(data, 14, idx)
        if atr is None:
            return None
        
        sl_dist = atr * self.params.get('atr_sl_mult', 2)
        rr = self.params.get('rr_ratio', 2)
        
        # 상단 돌파 + 상승 추세
        if trend == 'UP' and price > upper:
            return {
                'side': 'LONG',
                'entry': price,
                'sl': price - sl_dist,
                'tp': price + sl_dist * rr
            }
        
        # 하단 돌파 + 하락 추세
        if trend == 'DOWN' and price < lower:
            return {
                'side': 'SHORT',
                'entry': price,
                'sl': price + sl_dist,
                'tp': price - sl_dist * rr
            }
        
        return None
    
    def _check_mean_reversion(self, data, idx, trend, price):
        """볼린저 밴드 평균회귀"""
        upper, mid, lower = calc_bollinger(data, 20, idx, 2)
        
        if upper is None:
            return None
        
        atr = calc_atr(data, 14, idx)
        if atr is None:
            return None
        
        sl_dist = atr * self.params.get('atr_sl_mult', 1.5)
        
        # 하단 터치 + 상승 추세 → 롱 (평균으로 회귀 기대)
        if trend == 'UP' and price <= lower:
            return {
                'side': 'LONG',
                'entry': price,
                'sl': price - sl_dist,
                'tp': mid  # 중심선까지
            }
        
        # 상단 터치 + 하락 추세 → 숏
        if trend == 'DOWN' and price >= upper:
            return {
                'side': 'SHORT',
                'entry': price,
                'sl': price + sl_dist,
                'tp': mid
            }
        
        return None
    
    def _check_rsi_trend(self, data, idx, trend, price):
        """RSI + 추세 필터"""
        rsi = calc_rsi(data, self.params.get('rsi_period', 14), idx)
        
        if rsi is None:
            return None
        
        oversold = self.params.get('rsi_oversold', 30)
        overbought = self.params.get('rsi_overbought', 70)
        
        atr = calc_atr(data, 14, idx)
        if atr is None:
            return None
        
        sl_dist = atr * self.params.get('atr_sl_mult', 2)
        rr = self.params.get('rr_ratio', 2)
        
        # RSI 과매도 + 상승 추세
        if trend == 'UP' and rsi < oversold:
            return {
                'side': 'LONG',
                'entry': price,
                'sl': price - sl_dist,
                'tp': price + sl_dist * rr
            }
        
        # RSI 과매수 + 하락 추세
        if trend == 'DOWN' and rsi > overbought:
            return {
                'side': 'SHORT',
                'entry': price,
                'sl': price + sl_dist,
                'tp': price - sl_dist * rr
            }
        
        return None
    
    def execute_trade(self, signal, dt):
        """거래 실행"""
        qty = (self.balance * LEVERAGE) / signal['entry']
        
        self.position = {
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'quantity': qty,
            'datetime': dt
        }
    
    def check_exit(self, candle):
        """청산 조건 체크"""
        if not self.position:
            return None
        
        if self.position['side'] == 'LONG':
            if candle['low'] <= self.position['sl']:
                return ('SL', self.position['sl'])
            if candle['high'] >= self.position['tp']:
                return ('TP', self.position['tp'])
        else:
            if candle['high'] >= self.position['sl']:
                return ('SL', self.position['sl'])
            if candle['low'] <= self.position['tp']:
                return ('TP', self.position['tp'])
        
        return None
    
    def close_position(self, price, reason, dt):
        """포지션 청산"""
        entry = self.position['entry']
        qty = self.position['quantity']
        
        if self.position['side'] == 'LONG':
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * qty
        
        self.balance += pnl
        
        self.trades.append({
            'side': self.position['side'],
            'entry': entry,
            'exit': price,
            'pnl': pnl,
            'pnl_pct': (pnl / (self.balance - pnl)) * 100,
            'reason': reason,
            'entry_time': self.position['datetime'],
            'exit_time': dt
        })
        
        self.position = None
    
    def get_results(self):
        """결과 계산"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'return_pct': 0,
                'max_drawdown': 0
            }
        
        wins = [t for t in self.trades if t['pnl'] > 0]
        
        # 최대 낙폭
        peak = INITIAL_BALANCE
        max_dd = 0
        balance = INITIAL_BALANCE
        
        for t in self.trades:
            balance += t['pnl']
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak * 100
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
            'max_drawdown': max_dd
        }


def run_backtest(data_daily, data_1h, params, strategy_type, year):
    """단일 백테스트 실행"""
    strategy = Strategy(params)
    
    check_interval = params.get('check_interval', 4)  # 1시간봉 기준
    
    for i in range(100, len(data_1h), check_interval):
        current = data_1h[i]
        current_time = current['time']
        dt = current['datetime']
        
        # 일봉 인덱스 찾기
        daily_idx = None
        for j, d in enumerate(data_daily):
            if d['time'] <= current_time:
                daily_idx = j
            else:
                break
        
        if daily_idx is None or daily_idx < 30:
            continue
        
        # 포지션 있으면 청산 체크
        if strategy.position:
            for j in range(max(0, i - check_interval), i + 1):
                if j >= len(data_1h):
                    break
                exit_result = strategy.check_exit(data_1h[j])
                if exit_result:
                    strategy.close_position(exit_result[1], exit_result[0], data_1h[j]['datetime'])
                    break
        
        # 포지션 없으면 진입 체크
        if not strategy.position:
            trend = strategy.get_trend(data_daily, daily_idx)
            signal = strategy.check_entry(data_1h, i, trend, strategy_type)
            
            if signal:
                strategy.execute_trade(signal, dt)
        
        # 파산 체크
        if strategy.balance <= 0:
            break
    
    return strategy.get_results()


def optimize():
    """그리드 서치 최적화"""
    print("=" * 60)
    print("🔍 전략 최적화 시작")
    print("=" * 60)
    
    # 데이터 로드
    print("📥 데이터 로드 중...")
    data_daily = load_data('btc_daily')
    data_1h = load_data('btc_1hour')
    
    print(f"  일봉: {len(data_daily):,}개")
    print(f"  1시간봉: {len(data_1h):,}개")
    
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    # 파라미터 그리드
    param_grid = {
        'trend_ma_period': [10, 20, 50],
        'trend_ma_type': ['sma', 'ema'],
        'fast_ma': [5, 10, 20],
        'slow_ma': [20, 30, 50],
        'rr_ratio': [1.5, 2.0, 2.5, 3.0],
        'atr_sl_mult': [1.5, 2.0, 2.5],
        'donchian_period': [10, 20, 30],
        'rsi_period': [7, 14, 21],
        'rsi_oversold': [20, 30],
        'rsi_overbought': [70, 80],
        'check_interval': [1, 4]  # 1시간봉 기준
    }
    
    strategy_types = ['trend_follow', 'breakout', 'rsi_trend']
    
    best_results = []
    test_count = 0
    
    # 전략 타입별 테스트
    for strategy_type in strategy_types:
        print(f"\n{'='*60}")
        print(f"📊 전략: {strategy_type}")
        print("=" * 60)
        
        # 해당 전략에 관련된 파라미터만 선택
        if strategy_type == 'trend_follow':
            keys = ['trend_ma_period', 'trend_ma_type', 'fast_ma', 'slow_ma', 'rr_ratio', 'atr_sl_mult', 'check_interval']
        elif strategy_type == 'breakout':
            keys = ['trend_ma_period', 'trend_ma_type', 'donchian_period', 'rr_ratio', 'atr_sl_mult', 'check_interval']
        else:  # rsi_trend
            keys = ['trend_ma_period', 'trend_ma_type', 'rsi_period', 'rsi_oversold', 'rsi_overbought', 'rr_ratio', 'atr_sl_mult', 'check_interval']
        
        # 조합 생성
        values = [param_grid[k] for k in keys]
        combinations = list(itertools.product(*values))
        
        print(f"테스트할 조합: {len(combinations)}개")
        
        for combo in combinations:
            params = dict(zip(keys, combo))
            test_count += 1
            
            # 연도별 테스트
            yearly_results = {}
            all_pass = True
            
            for year in years:
                # 해당 연도 데이터 필터링
                year_daily = [k for k in data_daily if k['datetime'][:4] == year]
                year_1h = [k for k in data_1h if k['datetime'][:4] == year]
                
                if len(year_1h) < 1000 or len(year_daily) < 30:
                    continue
                
                result = run_backtest(year_daily, year_1h, params, strategy_type, year)
                yearly_results[year] = result
                
                # 목표 체크
                days_in_year = len(year_daily)
                trades_per_day = result['total_trades'] / days_in_year if days_in_year > 0 else 0
                monthly_return = result['return_pct'] / 12 if result['return_pct'] > 0 else result['return_pct']
                
                # 기준: 거래 0.5회/일 이상, 승률 40%+, 낙폭 40% 이하
                if (trades_per_day < 0.5 or 
                    result['win_rate'] < 40 or 
                    result['max_drawdown'] > 40 or
                    result['return_pct'] < 0):
                    all_pass = False
            
            if all_pass and yearly_results:
                avg_return = sum(r['return_pct'] for r in yearly_results.values()) / len(yearly_results)
                avg_win_rate = sum(r['win_rate'] for r in yearly_results.values()) / len(yearly_results)
                max_dd = max(r['max_drawdown'] for r in yearly_results.values())
                
                best_results.append({
                    'strategy_type': strategy_type,
                    'params': params,
                    'avg_return': avg_return,
                    'avg_win_rate': avg_win_rate,
                    'max_drawdown': max_dd,
                    'yearly_results': yearly_results
                })
                
                print(f"  ✅ 발견! 평균수익: {avg_return:.1f}% | 승률: {avg_win_rate:.1f}% | MDD: {max_dd:.1f}%")
            
            if test_count % 100 == 0:
                print(f"  진행: {test_count}개 테스트 완료, {len(best_results)}개 후보 발견")
    
    # 결과 정렬 및 저장
    best_results.sort(key=lambda x: x['avg_return'], reverse=True)
    
    print("\n" + "=" * 60)
    print(f"📈 최적화 완료: {test_count}개 테스트, {len(best_results)}개 후보")
    print("=" * 60)
    
    if best_results:
        print("\n🏆 상위 5개 전략:")
        for i, r in enumerate(best_results[:5]):
            print(f"\n{i+1}. {r['strategy_type']}")
            print(f"   파라미터: {r['params']}")
            print(f"   평균 수익률: {r['avg_return']:.1f}%")
            print(f"   평균 승률: {r['avg_win_rate']:.1f}%")
            print(f"   최대 낙폭: {r['max_drawdown']:.1f}%")
    else:
        print("\n❌ 조건을 만족하는 전략을 찾지 못했습니다.")
        print("   조건 완화 후 재시도 필요")
    
    # 결과 저장
    with open(RESULTS_PATH, 'w') as f:
        json.dump({
            'test_count': test_count,
            'results': best_results[:20]  # 상위 20개만 저장
        }, f, indent=2, default=str)
    
    print(f"\n결과 저장: {RESULTS_PATH}")
    
    return best_results


if __name__ == "__main__":
    optimize()
