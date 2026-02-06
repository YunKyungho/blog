#!/usr/bin/env python3
"""
하락장 공격적 전략 테스트
- 레버리지 10x~20x
- 더 빈번한 거래
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
TAKER_FEE = 0.0004

# ========== 데이터 ==========

def fetch_binance_klines(symbol, interval, start_time, end_time):
    url = f"{BINANCE_BASE}/api/v3/klines"
    all_data = []
    current = start_time
    
    while current < end_time:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current,
            'endTime': min(current + 1000 * 86400000, end_time),
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
            print(f"Error: {e}")
            break
    
    return all_data


def load_data_from_db(table, year):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM {table} WHERE datetime LIKE '{year}%' ORDER BY timestamp"
    cursor = conn.execute(query)
    data = [{'time': r[0], 'datetime': r[1], 'open': r[2], 'high': r[3], 
             'low': r[4], 'close': r[5], 'volume': r[6]} for r in cursor]
    conn.close()
    return data


def get_bear_market_data():
    data = {}
    print("📥 2018년 데이터 로딩...")
    start_2018 = int(datetime(2018, 1, 1).timestamp() * 1000)
    end_2018 = int(datetime(2018, 12, 31, 23, 59).timestamp() * 1000)
    data['2018'] = fetch_binance_klines('BTCUSDT', '1d', start_2018, end_2018)
    
    print("📥 2022년 데이터 로딩...")
    data['2022'] = load_data_from_db('btc_daily', '2022')
    
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

class AggressiveBacktester:
    def __init__(self, data, leverage=10, risk_pct=0.03):
        self.data = data
        self.leverage = leverage
        self.risk_pct = risk_pct
        self.reset()
    
    def reset(self):
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.peak = INITIAL_BALANCE
        self.max_dd = 0
    
    def calc_position_size(self, entry, sl_pct):
        risk_amount = self.balance * self.risk_pct
        sl_distance = entry * sl_pct / 100
        if sl_distance == 0: return 0
        qty = risk_amount / sl_distance
        max_qty = (self.balance * self.leverage) / entry
        return min(qty, max_qty)
    
    def open_position(self, side, entry, sl_pct, tp_pct, dt, reason=""):
        qty = self.calc_position_size(entry, sl_pct)
        if qty <= 0: return False
        
        if side == 'SHORT':
            sl = entry * (1 + sl_pct / 100)
            tp = entry * (1 - tp_pct / 100)
        else:
            sl = entry * (1 - sl_pct / 100)
            tp = entry * (1 + tp_pct / 100)
        
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
        
        pnl -= pos['entry'] * pos['qty'] * TAKER_FEE * 2
        
        pnl_pct = pnl / self.balance * 100
        self.balance += pnl
        
        # 청산 체크
        if self.balance <= 0:
            self.balance = 0
        
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
        
        self.equity_curve.append({'time': dt, 'equity': max(equity, 0)})
        if equity > self.peak: self.peak = equity
        dd = (self.peak - equity) / self.peak * 100 if self.peak > 0 else 0
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
            'final_balance': self.balance
        }


# ========== 공격적 전략 ==========

def strategy_aggressive_bear(bt, params=None):
    """
    공격적 하락장 전략
    - 고레버리지
    - 빈번한 진입
    - 타이트한 SL/TP
    """
    if params is None:
        params = {
            'sma_period': 50,
            'rsi_period': 10,
            'rsi_overbought': 60,
            'mom_threshold': -3,
            'adx_threshold': 20,
            'sl_pct': 1.5,
            'tp_pct': 2.5
        }
    
    data = bt.data
    
    for i in range(params['sma_period'] + 20, len(data)):
        if bt.balance <= 0:
            break
            
        candle = data[i]
        price = candle['close']
        dt = candle['datetime']
        
        bt.check_sltp(candle)
        bt.update_equity(price, dt)
        
        if bt.position: continue
        
        sma_val = sma(data, params['sma_period'], i)
        rsi_val = rsi(data, params['rsi_period'], i)
        mom_val = momentum(data, 10, i)
        adx_val = adx(data, 14, i)
        
        if not all([sma_val, rsi_val, mom_val, adx_val]): continue
        
        # 하락 추세 필터
        if price > sma_val:
            continue
        
        signal_strength = 0
        
        # RSI 과매수
        if rsi_val > params['rsi_overbought']:
            signal_strength += 1
        
        # 음의 모멘텀
        if mom_val < params['mom_threshold']:
            signal_strength += 1
        
        # 강한 추세
        if adx_val > params['adx_threshold']:
            signal_strength += 1
        
        # 2개 이상 신호
        if signal_strength >= 2:
            bt.open_position('SHORT', price, params['sl_pct'], params['tp_pct'], dt, 'AGG_SHORT')
    
    return bt.results()


def test_leverage_variations():
    """다양한 레버리지 테스트"""
    data_dict = get_bear_market_data()
    
    leverages = [5, 10, 15, 20]
    risk_pcts = [0.02, 0.03, 0.05]
    
    print("\n" + "=" * 70)
    print("📊 레버리지별 성과 비교")
    print("=" * 70)
    
    results = []
    
    for lev in leverages:
        for risk in risk_pcts:
            all_results = []
            
            for year, data in data_dict.items():
                if len(data) < 100:
                    continue
                
                bt = AggressiveBacktester(data, leverage=lev, risk_pct=risk)
                result = strategy_aggressive_bear(bt)
                result['year'] = year
                all_results.append(result)
            
            if all_results:
                total_return = sum(r['return_pct'] for r in all_results)
                avg_dd = sum(r['max_dd'] for r in all_results) / len(all_results)
                avg_wr = sum(r['win_rate'] for r in all_results) / len(all_results)
                
                results.append({
                    'leverage': lev,
                    'risk': risk * 100,
                    'total_return': total_return,
                    'avg_dd': avg_dd,
                    'avg_wr': avg_wr,
                    'years': all_results
                })
                
                print(f"  Lev {lev}x | Risk {risk*100}% | Return {total_return:>7.1f}% | MDD {avg_dd:>5.1f}% | WR {avg_wr:>5.1f}%")
    
    # 최고 조합 찾기
    print("\n" + "=" * 70)
    print("🏆 최고 레버리지/리스크 조합")
    print("=" * 70)
    
    # 수익률/DD 비율 기준
    best = max(results, key=lambda x: x['total_return'] / (x['avg_dd'] + 1))
    print(f"최고: Lev {best['leverage']}x | Risk {best['risk']}%")
    print(f"수익률: {best['total_return']:.1f}% | MDD: {best['avg_dd']:.1f}% | 승률: {best['avg_wr']:.1f}%")
    
    for r in best['years']:
        print(f"  {r['year']}: 수익률 {r['return_pct']:.1f}% | MDD {r['max_dd']:.1f}%")
    
    return results, best


def test_sl_tp_variations():
    """SL/TP 조합 테스트"""
    data_dict = get_bear_market_data()
    
    sl_pcts = [1.0, 1.5, 2.0, 2.5]
    tp_pcts = [2.0, 2.5, 3.0, 4.0]
    
    print("\n" + "=" * 70)
    print("📊 SL/TP 조합 테스트 (Lev 10x, Risk 3%)")
    print("=" * 70)
    
    results = []
    
    for sl in sl_pcts:
        for tp in tp_pcts:
            if tp <= sl:  # TP는 SL보다 커야 함
                continue
            
            all_results = []
            
            for year, data in data_dict.items():
                if len(data) < 100:
                    continue
                
                bt = AggressiveBacktester(data, leverage=10, risk_pct=0.03)
                result = strategy_aggressive_bear(bt, {'sma_period': 50, 'rsi_period': 10, 
                    'rsi_overbought': 60, 'mom_threshold': -3, 'adx_threshold': 20,
                    'sl_pct': sl, 'tp_pct': tp})
                result['year'] = year
                all_results.append(result)
            
            if all_results:
                total_return = sum(r['return_pct'] for r in all_results)
                avg_dd = sum(r['max_dd'] for r in all_results) / len(all_results)
                
                results.append({
                    'sl': sl, 'tp': tp,
                    'total_return': total_return,
                    'avg_dd': avg_dd
                })
                
                rr = tp / sl
                print(f"  SL {sl}% / TP {tp}% (1:{rr:.1f}) | Return {total_return:>7.1f}% | MDD {avg_dd:>5.1f}%")
    
    best = max(results, key=lambda x: x['total_return'] - x['avg_dd'])
    print(f"\n✅ 최적: SL {best['sl']}% / TP {best['tp']}%")
    
    return results, best


if __name__ == "__main__":
    print("=" * 70)
    print("🐻 하락장 공격적 전략 테스트")
    print("=" * 70)
    
    lev_results, best_lev = test_leverage_variations()
    sltp_results, best_sltp = test_sl_tp_variations()
    
    # 최종 결과 저장
    output = {
        'timestamp': datetime.now().isoformat(),
        'best_leverage': {
            'leverage': best_lev['leverage'],
            'risk_pct': best_lev['risk'],
            'total_return': best_lev['total_return'],
            'avg_dd': best_lev['avg_dd']
        },
        'best_sltp': {
            'sl_pct': best_sltp['sl'],
            'tp_pct': best_sltp['tp'],
            'total_return': best_sltp['total_return'],
            'avg_dd': best_sltp['avg_dd']
        }
    }
    
    with open(Path(__file__).parent / 'bear_aggressive_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 결과 저장: bear_aggressive_results.json")
