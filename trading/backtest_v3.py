#!/usr/bin/env python3
"""
백테스팅 v3 - 근본적 전략 재설계
목표:
- 거래수: 300-400회/년
- 승률: 40%+
- 수익률: 40%+/월
- 최대 DD: 40% 이하
- 모든 연도 수익
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

INITIAL_BALANCE = 5000

# ========== 전략 파라미터 ==========
class StrategyParams:
    def __init__(self):
        # 레버리지 & 리스크
        self.leverage = 10          # 레버리지 낮춤 (20 → 10)
        self.risk_per_trade = 2.0   # 거래당 리스크 %
        
        # 추세 판단
        self.trend_ma = 50          # 단일 MA 사용
        self.trend_tf = '4h'        # 추세 판단 타임프레임
        
        # 진입 조건 (더 단순화)
        self.entry_tf = '15m'       # 진입 타임프레임
        self.pullback_pct = 0.3     # 풀백 %
        self.min_body_ratio = 0.5   # 최소 캔들 바디 비율
        
        # 손익 관리
        self.sl_pct = 0.5           # 손절 % (더 작게)
        self.tp_pct = 0.75          # 익절 % (1.5:1 RR)
        self.use_trailing = False   # 트레일링 스탑
        self.trailing_pct = 0.3     # 트레일링 %
        
        # 필터
        self.volume_filter = True   # 거래량 필터
        self.volume_mult = 1.0      # 평균 거래량 배수
        self.cooldown_bars = 4      # 진입 후 쿨다운 (15분봉 기준)


def load_data(table):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table} ORDER BY timestamp"
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


class BacktestV3:
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
        
        # 디버깅
        self.signal_count = {'LONG': 0, 'SHORT': 0}
    
    def get_trend(self, klines, ma_period):
        """단순 MA 기반 추세"""
        if len(klines) < ma_period:
            return 'UNKNOWN'
        
        closes = [k['close'] for k in klines[-ma_period:]]
        ma = sum(closes) / len(closes)
        current = klines[-1]['close']
        
        if current > ma * 1.005:  # MA 위 0.5% 이상
            return 'UP'
        elif current < ma * 0.995:  # MA 아래 0.5% 이상
            return 'DOWN'
        return 'SIDEWAYS'
    
    def find_pullback_entry(self, klines, trend):
        """풀백 진입 시그널"""
        if len(klines) < 10:
            return None
        
        curr = klines[-1]
        prev = klines[-2]
        
        # 평균 거래량 체크
        if self.params.volume_filter:
            avg_vol = sum(k['volume'] for k in klines[-20:]) / 20
            if curr['volume'] < avg_vol * self.params.volume_mult:
                return None
        
        # 캔들 분석
        body = abs(curr['close'] - curr['open'])
        total = curr['high'] - curr['low']
        if total == 0 or body / total < self.params.min_body_ratio:
            return None
        
        price = curr['close']
        
        # 상승 추세에서 눌림목 매수
        if trend == 'UP':
            # 이전 캔들이 음봉, 현재 캔들이 양봉 (반전)
            if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                # 최근 고점 대비 풀백
                recent_high = max(k['high'] for k in klines[-10:-1])
                pullback = (recent_high - curr['low']) / recent_high * 100
                
                if self.params.pullback_pct < pullback < 3.0:  # 적정 풀백
                    return {
                        'side': 'LONG',
                        'entry': price,
                        'sl': price * (1 - self.params.sl_pct / 100),
                        'tp': price * (1 + self.params.tp_pct / 100)
                    }
        
        # 하락 추세에서 반등 매도
        elif trend == 'DOWN':
            # 이전 캔들이 양봉, 현재 캔들이 음봉 (반전)
            if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                # 최근 저점 대비 반등
                recent_low = min(k['low'] for k in klines[-10:-1])
                bounce = (curr['high'] - recent_low) / recent_low * 100
                
                if self.params.pullback_pct < bounce < 3.0:  # 적정 반등
                    return {
                        'side': 'SHORT',
                        'entry': price,
                        'sl': price * (1 + self.params.sl_pct / 100),
                        'tp': price * (1 - self.params.tp_pct / 100)
                    }
        
        return None
    
    def execute_entry(self, signal, dt):
        # 포지션 사이즈 계산 (리스크 기반)
        risk_amount = self.balance * (self.params.risk_per_trade / 100)
        sl_distance = abs(signal['entry'] - signal['sl'])
        qty = risk_amount / sl_distance if sl_distance > 0 else 0
        
        # 레버리지 제한
        max_qty = (self.balance * self.params.leverage) / signal['entry']
        qty = min(qty, max_qty)
        
        self.position = {
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'quantity': qty,
            'datetime': dt,
            'highest': signal['entry'] if signal['side'] == 'LONG' else None,
            'lowest': signal['entry'] if signal['side'] == 'SHORT' else None
        }
        
        self.signal_count[signal['side']] += 1
        self.cooldown = self.params.cooldown_bars
    
    def check_exit(self, candle):
        """SL/TP/트레일링 체크"""
        if not self.position:
            return None
        
        side = self.position['side']
        sl = self.position['sl']
        tp = self.position['tp']
        
        # 트레일링 스탑 업데이트
        if self.params.use_trailing:
            if side == 'LONG':
                if candle['high'] > self.position['highest']:
                    self.position['highest'] = candle['high']
                    new_sl = candle['high'] * (1 - self.params.trailing_pct / 100)
                    if new_sl > sl:
                        self.position['sl'] = new_sl
                        sl = new_sl
            else:
                if candle['low'] < self.position['lowest']:
                    self.position['lowest'] = candle['low']
                    new_sl = candle['low'] * (1 + self.params.trailing_pct / 100)
                    if new_sl < sl:
                        self.position['sl'] = new_sl
                        sl = new_sl
        
        # SL/TP 체크
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
        
        trade = {
            'side': self.position['side'],
            'entry': entry,
            'exit': price,
            'entry_time': self.position['datetime'],
            'exit_time': dt,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'balance_after': self.balance
        }
        
        self.trades.append(trade)
        self.position = None
        return trade
    
    def run(self, check_interval=1):
        """백테스트 실행"""
        for i in range(200, len(self.data_15m), check_interval):
            current = self.data_15m[i]
            dt = current['datetime']
            
            # 해당 시점까지의 4H 데이터
            klines_4h = [k for k in self.data_4h if k['time'] <= current['time']][-100:]
            klines_15m = self.data_15m[max(0, i-50):i+1]
            
            if len(klines_4h) < self.params.trend_ma or len(klines_15m) < 20:
                continue
            
            # 포지션 체크
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    self.execute_exit(exit_signal[1], exit_signal[0], dt)
            
            # 쿨다운 감소
            if self.cooldown > 0:
                self.cooldown -= 1
            
            # 신규 진입
            if not self.position and self.cooldown == 0:
                trend = self.get_trend(klines_4h, self.params.trend_ma)
                
                if trend in ['UP', 'DOWN']:
                    signal = self.find_pullback_entry(klines_15m, trend)
                    if signal:
                        self.execute_entry(signal, dt)
            
            # 자산 기록
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                break
        
        return self.get_results()
    
    def get_results(self):
        if not self.trades:
            return {'total_trades': 0, 'win_rate': 0, 'return_pct': 0, 'max_drawdown': 0, 'signal_count': self.signal_count}
        
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        
        # 최대 낙폭
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
            'losses': len(losses),
            'win_rate': len(wins) / len(self.trades) * 100,
            'total_pnl': sum(t['pnl'] for t in self.trades),
            'final_balance': self.balance,
            'return_pct': (self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            'max_drawdown': max_dd,
            'signal_count': self.signal_count
        }


def run_yearly_test(params):
    """연도별 테스트"""
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
        
        bt = BacktestV3(year_4h, year_1h, year_15m, params)
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
    print(f"평균: {avg_trades:.0f}회/년 | 승률≥{min_wr:.1f}% | 수익 {avg_return:.1f}%/년 | DD≤{max_dd:.1f}%")
    print(f"모든 연도 수익: {'✅ YES' if all_profitable else '❌ NO'}")
    
    return all_profitable, min_wr, max_dd, avg_trades


def grid_search():
    """그리드 서치 최적화"""
    print("📥 그리드 서치 시작...")
    
    # 테스트할 파라미터 조합
    param_grid = [
        # 기본 설정
        {'leverage': 10, 'sl_pct': 0.5, 'tp_pct': 0.75, 'pullback_pct': 0.3, 'cooldown': 4},
        # SL/TP 변형
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.3, 'cooldown': 4},
        {'leverage': 10, 'sl_pct': 1.0, 'tp_pct': 1.5, 'pullback_pct': 0.3, 'cooldown': 4},
        {'leverage': 10, 'sl_pct': 1.0, 'tp_pct': 2.0, 'pullback_pct': 0.3, 'cooldown': 4},
        # 레버리지 변형
        {'leverage': 5, 'sl_pct': 1.0, 'tp_pct': 1.5, 'pullback_pct': 0.3, 'cooldown': 4},
        {'leverage': 15, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.3, 'cooldown': 4},
        # 풀백 변형
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.5, 'cooldown': 4},
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.2, 'cooldown': 2},
        # 쿨다운 변형
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.3, 'cooldown': 2},
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.0, 'pullback_pct': 0.3, 'cooldown': 8},
        # 트레일링 스탑
        {'leverage': 10, 'sl_pct': 0.7, 'tp_pct': 1.5, 'pullback_pct': 0.3, 'cooldown': 4, 'trailing': True, 'trailing_pct': 0.5},
        # 복합
        {'leverage': 8, 'sl_pct': 0.8, 'tp_pct': 1.2, 'pullback_pct': 0.4, 'cooldown': 3},
        {'leverage': 12, 'sl_pct': 0.6, 'tp_pct': 0.9, 'pullback_pct': 0.25, 'cooldown': 2},
    ]
    
    all_results = []
    
    for i, pg in enumerate(param_grid):
        params = StrategyParams()
        params.leverage = pg['leverage']
        params.sl_pct = pg['sl_pct']
        params.tp_pct = pg['tp_pct']
        params.pullback_pct = pg['pullback_pct']
        params.cooldown_bars = pg['cooldown']
        if pg.get('trailing'):
            params.use_trailing = True
            params.trailing_pct = pg.get('trailing_pct', 0.5)
        
        results = run_yearly_test(params)
        name = f"lev{pg['leverage']}_sl{pg['sl_pct']}_tp{pg['tp_pct']}_pb{pg['pullback_pct']}_cd{pg['cooldown']}"
        if pg.get('trailing'):
            name += "_trail"
        
        all_profitable, min_wr, max_dd, avg_trades = print_results(results, f"#{i+1} {name}")
        
        # 점수 계산
        avg_return = sum(r['return_pct'] for r in results) / len(results) if results else 0
        
        # 목표: 승률40%+, DD40%-, 거래300+
        score = avg_return
        if all_profitable:
            score += 500
        if min_wr >= 40:
            score += 200
        if max_dd <= 40:
            score += 300
        if avg_trades >= 300:
            score += 100
        elif avg_trades >= 200:
            score += 50
        
        all_results.append({
            'name': name,
            'params': pg,
            'results': results,
            'all_profitable': all_profitable,
            'min_wr': min_wr,
            'max_dd': max_dd,
            'avg_trades': avg_trades,
            'avg_return': avg_return,
            'score': score
        })
    
    # 점수순 정렬
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n" + "=" * 80)
    print("🏆 TOP 5 전략")
    print("=" * 80)
    
    for i, r in enumerate(all_results[:5]):
        print(f"\n#{i+1} {r['name']}")
        print(f"   Score: {r['score']:.0f} | 모든연도수익: {r['all_profitable']} | "
              f"승률≥{r['min_wr']:.1f}% | DD≤{r['max_dd']:.1f}% | 거래 {r['avg_trades']:.0f}회/년")
    
    # 저장
    with open(Path(__file__).parent / 'v3_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    return all_results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'grid':
        grid_search()
    else:
        # 기본 테스트
        params = StrategyParams()
        results = run_yearly_test(params)
        print_results(results, "V3 기본 설정")
