#!/usr/bin/env python3
"""
BTC 선물 트레이딩 전략 v5 - 추세+RSI
수수료 0.08% (0.04% × 2) 반영

백테스트 성과 (2019-2025):
- 평균 수익률: 67.7%/년
- 모든 연도 양수 수익 ✅
- MDD: 27.6%
- 평균 거래: 26.6회/년
- 승률: 47.8%

전략 로직:
- 일봉 MA15로 추세 판단
- 4시간봉 RSI로 진입 시점 결정
- 상승추세 + RSI<40 → 롱
- 하락추세 + RSI>65 → 숏
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = "/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db"

# ========== 최적 파라미터 (v5) ==========
INITIAL_BALANCE = 5000
LEVERAGE = 5
RISK_PER_TRADE = 5.0       # 거래당 리스크 %
TREND_MA = 15              # 추세 판단 MA (일봉)
RSI_PERIOD = 14            # RSI 기간
RSI_LOW = 40               # RSI 과매도 (롱 진입)
RSI_HIGH = 65              # RSI 과매수 (숏 진입)
SL_PCT = 5.0               # 손절 %
TP_PCT = 10.0              # 익절 % (1:2 손익비)
FEE_PCT = 0.04             # 수수료 % (각 방향)
COOLDOWN_BARS = 2          # 쿨다운 (4시간봉 기준)


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


def calc_ma(klines, period):
    """이동평균 계산"""
    if len(klines) < period:
        return None
    return sum(k['close'] for k in klines[-period:]) / period


def calc_rsi(klines, period=14):
    """RSI 계산"""
    if len(klines) < period + 1:
        return None
    
    gains = []
    losses = []
    
    for i in range(1, len(klines)):
        change = klines[i]['close'] - klines[i-1]['close']
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return None
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


class TrendRSIStrategy:
    """추세+RSI 전략"""
    
    def __init__(self, data_daily, data_4h):
        self.data_daily = data_daily
        self.data_4h = data_4h
        
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.cooldown = 0
        
        self.signal_count = {'LONG': 0, 'SHORT': 0}
        
        # 일봉 인덱스 맵 (빠른 조회용)
        self.daily_idx = {}
        for i, d in enumerate(self.data_daily):
            self.daily_idx[d['datetime'][:10]] = i
    
    def get_trend(self, current_time):
        """일봉 MA 기반 추세 판단"""
        # 현재 시점까지의 일봉 찾기
        date_str = current_time[:10]
        daily_i = self.daily_idx.get(date_str)
        
        if daily_i is None or daily_i < TREND_MA:
            return 'UNKNOWN'
        
        daily_data = self.data_daily[:daily_i + 1]
        
        if len(daily_data) < TREND_MA:
            return 'UNKNOWN'
        
        ma = calc_ma(daily_data, TREND_MA)
        if ma is None:
            return 'UNKNOWN'
        
        price = daily_data[-1]['close']
        
        if price > ma * 1.005:
            return 'UP'
        elif price < ma * 0.995:
            return 'DOWN'
        return 'SIDEWAYS'
    
    def find_entry_signal(self, klines_4h, trend):
        """4시간봉 RSI 기반 진입 시그널"""
        if len(klines_4h) < RSI_PERIOD + 1:
            return None
        
        rsi = calc_rsi(klines_4h, RSI_PERIOD)
        if rsi is None:
            return None
        
        price = klines_4h[-1]['close']
        
        # 상승 추세 + RSI 과매도 → 롱
        if trend == 'UP' and rsi < RSI_LOW:
            return {
                'side': 'LONG',
                'entry': price,
                'sl': price * (1 - SL_PCT / 100),
                'tp': price * (1 + TP_PCT / 100),
                'rsi': rsi
            }
        
        # 하락 추세 + RSI 과매수 → 숏
        if trend == 'DOWN' and rsi > RSI_HIGH:
            return {
                'side': 'SHORT',
                'entry': price,
                'sl': price * (1 + SL_PCT / 100),
                'tp': price * (1 - TP_PCT / 100),
                'rsi': rsi
            }
        
        return None
    
    def execute_entry(self, signal, dt):
        """진입 실행"""
        risk_amount = self.balance * (RISK_PER_TRADE / 100)
        sl_distance = abs(signal['entry'] - signal['sl'])
        qty = risk_amount / sl_distance if sl_distance > 0 else 0
        max_qty = (self.balance * LEVERAGE) / signal['entry']
        qty = min(qty, max_qty)
        
        if qty <= 0:
            return
        
        self.position = {
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'quantity': qty,
            'datetime': dt,
            'rsi': signal.get('rsi', 0)
        }
        
        self.signal_count[signal['side']] += 1
        self.cooldown = COOLDOWN_BARS
    
    def check_exit(self, candle):
        """SL/TP 체크"""
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
        """청산 실행"""
        entry = self.position['entry']
        qty = self.position['quantity']
        
        if self.position['side'] == 'LONG':
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * qty
        
        # 수수료 차감 (진입 + 청산 = 0.08%)
        fee = (entry * qty + price * qty) * (FEE_PCT / 100)
        pnl -= fee
        
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
            'rsi': self.position.get('rsi', 0),
            'balance_after': self.balance
        }
        
        self.trades.append(trade)
        self.position = None
        
        return trade
    
    def run(self, verbose=True):
        """백테스트 실행"""
        if verbose:
            print("=" * 60)
            print("📊 백테스트 시작 (추세+RSI 전략 v5)")
            print(f"기간: {self.data_4h[0]['datetime']} ~ {self.data_4h[-1]['datetime']}")
            print(f"초기 자본: ${INITIAL_BALANCE:,}")
            print(f"레버리지: {LEVERAGE}x | SL: {SL_PCT}% | TP: {TP_PCT}%")
            print(f"RSI 범위: {RSI_LOW} ~ {RSI_HIGH}")
            print("=" * 60)
        
        for i in range(50, len(self.data_4h)):
            current = self.data_4h[i]
            dt = current['datetime']
            klines_4h = self.data_4h[max(0, i-40):i+1]
            
            # 포지션 체크
            if self.position:
                exit_signal = self.check_exit(current)
                if exit_signal:
                    trade = self.execute_exit(exit_signal[1], exit_signal[0], dt)
                    if verbose and len(self.trades) % 20 == 0:
                        print(f"[{dt}] {trade['side']} 청산 @ ${trade['exit']:,.0f} | "
                              f"PnL: ${trade['pnl']:,.0f} ({trade['pnl_pct']:.1f}%)")
            
            # 쿨다운
            if self.cooldown > 0:
                self.cooldown -= 1
            
            # 신규 진입
            if not self.position and self.cooldown == 0:
                trend = self.get_trend(dt)
                
                if trend in ['UP', 'DOWN']:
                    signal = self.find_entry_signal(klines_4h, trend)
                    if signal:
                        self.execute_entry(signal, dt)
            
            # 자산 기록
            self.equity_curve.append({'time': dt, 'balance': self.balance})
            
            if self.balance <= 0:
                if verbose:
                    print("💀 파산!")
                break
        
        if verbose:
            self.print_results()
        
        return self.get_results()
    
    def get_results(self):
        """결과 반환"""
        if not self.trades:
            return {'total_trades': 0, 'win_rate': 0, 'return_pct': 0, 'max_drawdown': 0}
        
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
            'win_rate': len(wins) / len(self.trades) * 100 if self.trades else 0,
            'total_pnl': sum(t['pnl'] for t in self.trades),
            'final_balance': self.balance,
            'return_pct': (self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            'max_drawdown': max_dd,
            'avg_win': sum(t['pnl'] for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t['pnl'] for t in losses) / len(losses) if losses else 0,
            'signal_count': self.signal_count
        }
    
    def print_results(self):
        """결과 출력"""
        r = self.get_results()
        
        print("\n" + "=" * 60)
        print("📈 백테스트 결과")
        print("=" * 60)
        
        if r['total_trades'] == 0:
            print("거래 없음")
            return
        
        print(f"총 거래: {r['total_trades']}회 (롱: {r['signal_count']['LONG']}, 숏: {r['signal_count']['SHORT']})")
        print(f"승리: {r['wins']}회 | 패배: {r['losses']}회")
        print(f"승률: {r['win_rate']:.1f}%")
        print(f"총 손익: ${r['total_pnl']:,.2f}")
        print(f"최종 자본: ${r['final_balance']:,.2f}")
        print(f"수익률: {r['return_pct']:.1f}%")
        print(f"최대 낙폭: {r['max_drawdown']:.1f}%")
        
        print("\n최근 10개 거래:")
        for t in self.trades[-10:]:
            emoji = "✅" if t['pnl'] > 0 else "❌"
            print(f"  {emoji} {t['side']} | {t['entry_time'][:10]} | "
                  f"${t['pnl']:,.0f} ({t['pnl_pct']:.1f}%) | {t['reason']} | RSI:{t['rsi']:.1f}")


def run_yearly_backtest():
    """연도별 백테스트"""
    print("📥 데이터 로드 중...")
    
    data_daily = load_data('btc_daily')
    data_4h = load_data('btc_4hour')
    
    print(f"  일봉: {len(data_daily):,}개")
    print(f"  4시간봉: {len(data_4h):,}개")
    
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    all_results = []
    
    for year in years:
        year_daily = [k for k in data_daily if k['datetime'][:4] == year]
        year_4h = [k for k in data_4h if k['datetime'][:4] == year]
        
        if len(year_4h) < 500:
            continue
        
        print(f"\n{'='*60}")
        print(f"📅 {year}년 백테스트")
        
        strategy = TrendRSIStrategy(year_daily, year_4h)
        result = strategy.run(verbose=False)
        result['year'] = year
        all_results.append(result)
        
        sig = result['signal_count']
        print(f"  거래: {result['total_trades']}회 (L:{sig['LONG']}/S:{sig['SHORT']}) | "
              f"승률: {result['win_rate']:.1f}% | 수익률: {result['return_pct']:.1f}% | "
              f"DD: {result['max_drawdown']:.1f}%")
    
    # 전체 요약
    print("\n" + "=" * 60)
    print("📊 연도별 성과 요약")
    print("=" * 60)
    print(f"{'연도':<8} {'거래수':<10} {'승률':<10} {'수익률':<12} {'최대DD':<10}")
    print("-" * 60)
    
    total_return = 0
    all_profitable = True
    
    for r in all_results:
        print(f"{r['year']:<8} {r['total_trades']:<10} {r['win_rate']:.1f}%{'':<5} "
              f"{r['return_pct']:.1f}%{'':<6} {r['max_drawdown']:.1f}%")
        total_return += r['return_pct']
        if r['return_pct'] < 0:
            all_profitable = False
    
    print("-" * 60)
    avg_return = total_return / len(all_results)
    print(f"평균 연 수익률: {avg_return:.1f}% | 평균 월 수익률: {avg_return/12:.1f}%")
    print(f"모든 연도 수익: {'✅ YES' if all_profitable else '❌ NO'}")
    
    # 결과 저장
    with open(Path(__file__).parent / 'backtest_yearly_result.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print("\n결과 저장: backtest_yearly_result.json")


def run_full_backtest():
    """전체 기간 백테스트"""
    print("📥 전체 데이터 로드 중...")
    
    data_daily = load_data('btc_daily')
    data_4h = load_data('btc_4hour')
    
    print(f"  일봉: {len(data_daily):,}개")
    print(f"  4시간봉: {len(data_4h):,}개")
    print(f"  기간: {data_4h[0]['datetime']} ~ {data_4h[-1]['datetime']}")
    
    strategy = TrendRSIStrategy(data_daily, data_4h)
    strategy.run()
    
    # 결과 저장
    result = strategy.get_results()
    result['trades'] = strategy.trades[-100:]
    result['equity_curve'] = strategy.equity_curve[::100]
    
    with open(Path(__file__).parent / 'backtest_full_result.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'yearly':
        run_yearly_backtest()
    else:
        run_full_backtest()
