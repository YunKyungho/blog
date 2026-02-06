#!/usr/bin/env python3
"""2020년 백테스트 상세 분석"""

import sqlite3
from collections import defaultdict

DB_PATH = '/Users/yunkyeongho/workspace/trading-strategies/data/btc_history.db'

LEVERAGE = 20
MAX_LOSS_PERCENT = 10
MIN_RR_RATIO = 2.0
INITIAL_BALANCE = 5000

def load_data(table, year):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(f'''
        SELECT timestamp, datetime, open, high, low, close, volume 
        FROM {table} 
        WHERE datetime LIKE "{year}%"
        ORDER BY timestamp
    ''')
    data = [{'time': r[0], 'datetime': r[1], 'open': r[2], 'high': r[3], 
             'low': r[4], 'close': r[5], 'volume': r[6]} for r in cursor]
    conn.close()
    return data

def find_order_blocks(klines):
    if len(klines) < 10:
        return []
    blocks = []
    avg_volume = sum(k['volume'] for k in klines) / len(klines)
    
    for i in range(2, len(klines)-1):
        curr, prev = klines[i], klines[i-1]
        if curr['volume'] < avg_volume * 1.2:
            continue
        body_prev = abs(prev['close'] - prev['open'])
        body_curr = abs(curr['close'] - curr['open'])
        if body_curr < body_prev * 1.1 or body_prev == 0:
            continue
        
        if prev['close'] < prev['open'] and curr['close'] > curr['open']:
            if curr['close'] > prev['open'] and curr['open'] < prev['close']:
                blocks.append({'type': 'support', 'mid': (prev['open'] + prev['close']) / 2,
                              'high': prev['open'], 'low': prev['close']})
        
        if prev['close'] > prev['open'] and curr['close'] < curr['open']:
            if curr['close'] < prev['open'] and curr['open'] > prev['close']:
                blocks.append({'type': 'resistance', 'mid': (prev['open'] + prev['close']) / 2,
                              'high': prev['close'], 'low': prev['open']})
    return blocks

def find_clusters(zones, price):
    threshold = price * 0.003
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

def get_trend(klines, idx, lookback=20):
    if idx < lookback:
        return 'UNKNOWN'
    ma = sum(k['close'] for k in klines[idx-lookback:idx]) / lookback
    return 'UP' if klines[idx]['close'] > ma else 'DOWN'

def analyze_year(year):
    print(f"\n{'='*60}")
    print(f"📊 {year}년 상세 분석")
    print(f"{'='*60}")
    
    data_4h = load_data('btc_4hour', year)
    data_1h = load_data('btc_1hour', year)
    data_15m = load_data('btc_15min', year)
    
    print(f"데이터: 4h={len(data_4h)}, 1h={len(data_1h)}, 15m={len(data_15m)}")
    
    # 가격 변동
    start_price = data_1h[0]['close']
    end_price = data_1h[-1]['close']
    print(f"가격: ${start_price:,.0f} → ${end_price:,.0f} ({(end_price-start_price)/start_price*100:+.1f}%)")
    
    balance = INITIAL_BALANCE
    position = None
    trades = []
    long_count = 0
    short_count = 0
    
    # 매매 시뮬레이션
    for i in range(100, len(data_15m), 4):  # 1시간마다
        current = data_15m[i]
        price = current['close']
        
        # 포지션 체크
        if position:
            if position['side'] == 'LONG':
                if current['low'] <= position['sl']:
                    pnl = (position['sl'] - position['entry']) * position['qty']
                    balance += pnl
                    trades.append({'side': 'LONG', 'pnl': pnl, 'reason': 'SL', 'price': price})
                    position = None
                elif current['high'] >= position['tp']:
                    pnl = (position['tp'] - position['entry']) * position['qty']
                    balance += pnl
                    trades.append({'side': 'LONG', 'pnl': pnl, 'reason': 'TP', 'price': price})
                    position = None
            else:  # SHORT
                if current['high'] >= position['sl']:
                    pnl = (position['entry'] - position['sl']) * position['qty']
                    balance += pnl
                    trades.append({'side': 'SHORT', 'pnl': pnl, 'reason': 'SL', 'price': price})
                    position = None
                elif current['low'] <= position['tp']:
                    pnl = (position['entry'] - position['tp']) * position['qty']
                    balance += pnl
                    trades.append({'side': 'SHORT', 'pnl': pnl, 'reason': 'TP', 'price': price})
                    position = None
        
        # 진입 체크
        if not position:
            # 분석
            klines_4h = [k for k in data_4h if k['time'] <= current['time']][-50:]
            klines_1h = [k for k in data_1h if k['time'] <= current['time']][-50:]
            klines_15m = data_15m[max(0, i-50):i]
            
            if len(klines_4h) < 20:
                continue
            
            trend = get_trend(klines_4h, len(klines_4h)-1)
            
            all_zones = []
            for b in find_order_blocks(klines_4h):
                b['tf'] = '4h'
                all_zones.append(b)
            for b in find_order_blocks(klines_1h):
                b['tf'] = '1h'
                all_zones.append(b)
            for b in find_order_blocks(klines_15m):
                b['tf'] = '15m'
                all_zones.append(b)
            
            support_clusters, resistance_clusters = find_clusters(all_zones, price)
            nearby_range = price * 0.008
            
            if trend == 'DOWN':
                for c in resistance_clusters:
                    dist = c['mid'] - price
                    if 0 < dist < nearby_range:
                        sl = c['high'] + (price * 0.001)
                        sl_dist = sl - price
                        tp = price - (sl_dist * MIN_RR_RATIO)
                        qty = (balance * LEVERAGE) / price
                        position = {'side': 'SHORT', 'entry': price, 'sl': sl, 'tp': tp, 'qty': qty}
                        short_count += 1
                        break
            
            elif trend == 'UP':
                for c in support_clusters:
                    dist = price - c['mid']
                    if 0 < dist < nearby_range:
                        sl = c['low'] - (price * 0.001)
                        sl_dist = price - sl
                        tp = price + (sl_dist * MIN_RR_RATIO)
                        qty = (balance * LEVERAGE) / price
                        position = {'side': 'LONG', 'entry': price, 'sl': sl, 'tp': tp, 'qty': qty}
                        long_count += 1
                        break
        
        if balance <= 0:
            print("파산!")
            break
    
    # 결과
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    
    long_trades = [t for t in trades if t['side'] == 'LONG']
    short_trades = [t for t in trades if t['side'] == 'SHORT']
    
    print(f"\n총 거래: {len(trades)}회")
    print(f"롱: {len(long_trades)}회 | 숏: {len(short_trades)}회")
    
    if long_trades:
        long_wins = len([t for t in long_trades if t['pnl'] > 0])
        print(f"  롱 승률: {long_wins/len(long_trades)*100:.1f}%")
    
    if short_trades:
        short_wins = len([t for t in short_trades if t['pnl'] > 0])
        print(f"  숏 승률: {short_wins/len(short_trades)*100:.1f}%")
    
    print(f"\n최종 잔고: ${balance:,.0f} (수익률: {(balance-INITIAL_BALANCE)/INITIAL_BALANCE*100:.1f}%)")
    
    # SL/TP 비율
    sl_count = len([t for t in trades if t['reason'] == 'SL'])
    tp_count = len([t for t in trades if t['reason'] == 'TP'])
    print(f"SL 청산: {sl_count}회 | TP 청산: {tp_count}회")

# 분석 실행
for year in ['2020', '2022']:
    analyze_year(year)
