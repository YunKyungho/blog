#!/usr/bin/env python3
"""
백테스팅 스크립트
동일한 전략으로 과거 데이터 테스트
"""

import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"

# 설정
LEVERAGE = 20
MAX_LOSS_PERCENT = 10
MIN_RR_RATIO = 2.0
INITIAL_BALANCE = 1000

# ========== 데이터 수집 ==========

def fetch_klines(interval, start_time, end_time, limit=1000):
    """캔들 데이터 수집"""
    all_klines = []
    current_start = start_time
    
    while current_start < end_time:
        url = f"{BASE_URL}/fapi/v1/klines"
        params = {
            'symbol': SYMBOL,
            'interval': interval,
            'startTime': current_start,
            'endTime': end_time,
            'limit': limit
        }
        
        resp = requests.get(url, params=params)
        data = resp.json()
        
        if not data:
            break
        
        for k in data:
            all_klines.append({
                'time': k[0],
                'datetime': datetime.fromtimestamp(k[0]/1000).strftime('%Y-%m-%d %H:%M'),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            })
        
        current_start = data[-1][0] + 1
        
        if len(data) < limit:
            break
    
    return all_klines

# ========== 분석 함수 (데몬과 동일) ==========

def find_order_blocks(klines):
    if len(klines) < 10:
        return []
    
    blocks = []
    avg_volume = sum(k['volume'] for k in klines) / len(klines)
    
    for i in range(2, len(klines)-1):
        curr = klines[i]
        prev = klines[i-1]
        
        if curr['volume'] < avg_volume * 1.2:
            continue
        
        body_prev = abs(prev['close'] - prev['open'])
        body_curr = abs(curr['close'] - curr['open'])
        
        if body_curr < body_prev * 1.1 or body_prev == 0:
            continue
        
        if prev['close'] < prev['open'] and curr['close'] > curr['open']:
            if curr['close'] > prev['open'] and curr['open'] < prev['close']:
                blocks.append({
                    'type': 'support',
                    'high': prev['open'],
                    'low': prev['close'],
                    'mid': (prev['open'] + prev['close']) / 2,
                    'time': curr['time']
                })
        
        if prev['close'] > prev['open'] and curr['close'] < curr['open']:
            if curr['close'] < prev['open'] and curr['open'] > prev['close']:
                blocks.append({
                    'type': 'resistance',
                    'high': prev['close'],
                    'low': prev['open'],
                    'mid': (prev['open'] + prev['close']) / 2,
                    'time': curr['time']
                })
    
    return blocks

def find_clusters(zones, price, threshold_pct=0.3):
    threshold = price * (threshold_pct / 100)
    
    supports = sorted([z for z in zones if z['type'] == 'support'], key=lambda x: x['mid'])
    resistances = sorted([z for z in zones if z['type'] == 'resistance'], key=lambda x: x['mid'])
    
    def cluster(zones_list):
        if not zones_list:
            return []
        
        clusters = []
        current = [zones_list[0]]
        
        for z in zones_list[1:]:
            if z['mid'] - current[-1]['mid'] < threshold:
                current.append(z)
            else:
                if len(current) >= 2:
                    clusters.append({
                        'count': len(current),
                        'mid': sum(zz['mid'] for zz in current) / len(current),
                        'high': max(zz['high'] for zz in current),
                        'low': min(zz['low'] for zz in current),
                        'type': current[0]['type']
                    })
                current = [z]
        
        if len(current) >= 2:
            clusters.append({
                'count': len(current),
                'mid': sum(zz['mid'] for zz in current) / len(current),
                'high': max(zz['high'] for zz in current),
                'low': min(zz['low'] for zz in current),
                'type': current[0]['type']
            })
        
        return clusters
    
    return cluster(supports), cluster(resistances)

# ========== 백테스트 엔진 ==========

class Backtest:
    def __init__(self, data_1d, data_1h, data_15m, data_5m):
        self.data_1d = data_1d  # 일봉 추가
        self.data_1h = data_1h
        self.data_15m = data_15m
        self.data_5m = data_5m
        
        self.balance = INITIAL_BALANCE
        self.position = None
        self.trades = []
        self.equity_curve = []
    
    def get_trend(self, klines, idx, lookback=20):
        """추세 판단 (20MA 기준)"""
        if idx < lookback:
            return 'UNKNOWN'
        
        ma = sum(k['close'] for k in klines[idx-lookback:idx]) / lookback
        return 'UP' if klines[idx]['close'] > ma else 'DOWN'
    
    def analyze_at(self, idx_5m):
        """특정 시점 분석"""
        # 5분봉 기준 시간
        current_time = self.data_5m[idx_5m]['time']
        price = self.data_5m[idx_5m]['close']
        
        # 각 TF에서 해당 시점까지의 데이터
        klines_1d = [k for k in self.data_1d if k['time'] <= current_time][-30:]  # 일봉 추가
        klines_1h = [k for k in self.data_1h if k['time'] <= current_time][-50:]
        klines_15m = [k for k in self.data_15m if k['time'] <= current_time][-50:]
        klines_5m = self.data_5m[max(0, idx_5m-50):idx_5m]
        
        if len(klines_1d) < 20 or len(klines_1h) < 20 or len(klines_15m) < 20:
            return None
        
        # 추세 - 일봉 기준으로 변경
        trend_daily = self.get_trend(klines_1d, len(klines_1d)-1)
        
        # 오더블록 탐지
        all_zones = []
        for b in find_order_blocks(klines_1h):
            b['tf'] = '1h'
            all_zones.append(b)
        for b in find_order_blocks(klines_15m):
            b['tf'] = '15m'
            all_zones.append(b)
        for b in find_order_blocks(klines_5m):
            b['tf'] = '5m'
            all_zones.append(b)
        
        support_clusters, resistance_clusters = find_clusters(all_zones, price)
        
        return {
            'price': price,
            'time': current_time,
            'datetime': self.data_5m[idx_5m]['datetime'],
            'big_trend': trend_daily,  # 일봉 추세 사용
            'support_clusters': support_clusters,
            'resistance_clusters': resistance_clusters
        }
    
    def check_entry(self, analysis):
        """진입 조건 체크"""
        price = analysis['price']
        big_trend = analysis['big_trend']
        nearby_range = price * 0.008
        
        if big_trend == 'DOWN':
            for c in analysis['resistance_clusters']:
                dist = c['mid'] - price
                if 0 < dist < nearby_range:
                    sl = c['high'] + (price * 0.001)
                    sl_dist = sl - price
                    tp = price - (sl_dist * MIN_RR_RATIO)
                    
                    if sl_dist > 0:
                        return {
                            'side': 'SHORT',
                            'entry': price,
                            'sl': sl,
                            'tp': tp,
                            'cluster': c
                        }
        
        if big_trend == 'UP':
            for c in analysis['support_clusters']:
                dist = price - c['mid']
                if 0 < dist < nearby_range:
                    sl = c['low'] - (price * 0.001)
                    sl_dist = price - sl
                    tp = price + (sl_dist * MIN_RR_RATIO)
                    
                    if sl_dist > 0:
                        return {
                            'side': 'LONG',
                            'entry': price,
                            'sl': sl,
                            'tp': tp,
                            'cluster': c
                        }
        
        return None
    
    def check_exit(self, price):
        """청산 조건 체크"""
        if not self.position:
            return None
        
        entry = self.position['entry']
        sl = self.position['sl']
        tp = self.position['tp']
        
        if self.position['side'] == 'LONG':
            if price <= sl:
                return 'STOP_LOSS'
            if price >= tp:
                return 'TAKE_PROFIT'
        else:
            if price >= sl:
                return 'STOP_LOSS'
            if price <= tp:
                return 'TAKE_PROFIT'
        
        return None
    
    def execute_entry(self, signal, analysis):
        """진입 실행"""
        qty = (self.balance * LEVERAGE) / signal['entry']
        
        self.position = {
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'quantity': qty,
            'time': analysis['time'],
            'datetime': analysis['datetime']
        }
    
    def execute_exit(self, price, reason, dt):
        """청산 실행"""
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
            'entry': self.position['entry'],
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
    
    def run(self):
        """백테스트 실행"""
        print("=" * 60)
        print("📊 백테스트 시작")
        print(f"초기 자본: ${INITIAL_BALANCE:,}")
        print(f"레버리지: {LEVERAGE}x")
        print(f"최대 손실: {MAX_LOSS_PERCENT}%")
        print(f"최소 손익비: 1:{MIN_RR_RATIO}")
        print("=" * 60)
        
        check_interval = 12  # 5분봉 12개 = 1시간마다 체크
        
        for i in range(100, len(self.data_5m), check_interval):
            current = self.data_5m[i]
            price = current['close']
            dt = current['datetime']
            
            # 포지션 있으면 청산 조건 체크
            if self.position:
                # 매 캔들마다 SL/TP 체크
                for j in range(max(0, i-check_interval), i+1):
                    candle = self.data_5m[j]
                    
                    # 고가/저가로 SL/TP 체크
                    if self.position['side'] == 'LONG':
                        if candle['low'] <= self.position['sl']:
                            self.execute_exit(self.position['sl'], 'STOP_LOSS', candle['datetime'])
                            break
                        if candle['high'] >= self.position['tp']:
                            self.execute_exit(self.position['tp'], 'TAKE_PROFIT', candle['datetime'])
                            break
                    else:
                        if candle['high'] >= self.position['sl']:
                            self.execute_exit(self.position['sl'], 'STOP_LOSS', candle['datetime'])
                            break
                        if candle['low'] <= self.position['tp']:
                            self.execute_exit(self.position['tp'], 'TAKE_PROFIT', candle['datetime'])
                            break
            
            # 포지션 없으면 진입 체크
            if not self.position:
                analysis = self.analyze_at(i)
                if analysis:
                    signal = self.check_entry(analysis)
                    if signal:
                        self.execute_entry(signal, analysis)
                        print(f"[{dt}] {signal['side']} 진입 @ ${signal['entry']:,.0f}")
            
            # 자본 기록
            self.equity_curve.append({
                'time': dt,
                'balance': self.balance,
                'position': self.position['side'] if self.position else None
            })
            
            # 파산 체크
            if self.balance <= 0:
                print("💀 파산!")
                break
        
        self.print_results()
    
    def print_results(self):
        """결과 출력"""
        print("\n" + "=" * 60)
        print("📈 백테스트 결과")
        print("=" * 60)
        
        if not self.trades:
            print("거래 없음")
            return
        
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        win_rate = len(wins) / len(self.trades) * 100
        
        print(f"총 거래: {len(self.trades)}회")
        print(f"승리: {len(wins)}회 | 패배: {len(losses)}회")
        print(f"승률: {win_rate:.1f}%")
        print(f"총 손익: ${total_pnl:,.2f}")
        print(f"최종 자본: ${self.balance:,.2f}")
        print(f"수익률: {((self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100):.1f}%")
        
        if wins:
            avg_win = sum(t['pnl'] for t in wins) / len(wins)
            print(f"평균 수익: ${avg_win:,.2f}")
        
        if losses:
            avg_loss = sum(t['pnl'] for t in losses) / len(losses)
            print(f"평균 손실: ${avg_loss:,.2f}")
        
        # 최대 낙폭
        peak = INITIAL_BALANCE
        max_dd = 0
        for e in self.equity_curve:
            if e['balance'] > peak:
                peak = e['balance']
            dd = (peak - e['balance']) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        print(f"최대 낙폭: {max_dd:.1f}%")
        
        print("\n" + "-" * 60)
        print("최근 10개 거래:")
        for t in self.trades[-10:]:
            emoji = "✅" if t['pnl'] > 0 else "❌"
            print(f"  {emoji} {t['side']} | {t['entry_time']} | PnL: ${t['pnl']:,.2f} ({t['pnl_pct']:.1f}%) | {t['reason']}")
        
        # 결과 저장
        result = {
            'total_trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'final_balance': self.balance,
            'return_pct': (self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            'max_drawdown': max_dd,
            'trades': self.trades
        }
        
        with open(Path(__file__).parent / 'backtest_result.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print("\n결과 저장: backtest_result.json")

def main():
    # 과거 60일 데이터 수집 (일봉 20MA 계산을 위해 확장)
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)
    
    print("📥 데이터 수집 중...")
    
    print("  일봉 수집...")
    data_1d = fetch_klines('1d', start_time, end_time)
    print(f"    → {len(data_1d)}개")
    
    print("  1시간봉 수집...")
    data_1h = fetch_klines('1h', start_time, end_time)
    print(f"    → {len(data_1h)}개")
    
    print("  15분봉 수집...")
    data_15m = fetch_klines('15m', start_time, end_time)
    print(f"    → {len(data_15m)}개")
    
    print("  5분봉 수집...")
    data_5m = fetch_klines('5m', start_time, end_time)
    print(f"    → {len(data_5m)}개")
    
    if not data_1d or not data_1h or not data_15m or not data_5m:
        print("데이터 수집 실패")
        return
    
    # 백테스트 실행
    bt = Backtest(data_1d, data_1h, data_15m, data_5m)
    bt.run()

if __name__ == "__main__":
    main()
