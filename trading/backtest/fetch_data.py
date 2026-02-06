"""
Binance에서 BTC 히스토리 데이터 가져오기
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os

def fetch_binance_klines(symbol='BTCUSDT', interval='1d', start_date='2020-01-01', end_date=None):
    """
    Binance API에서 캔들 데이터 가져오기
    """
    base_url = 'https://api.binance.com/api/v3/klines'
    
    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_ts = int(datetime.now().timestamp() * 1000) if end_date is None else int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
    
    all_data = []
    current_start = start_ts
    
    while current_start < end_ts:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start,
            'endTime': end_ts,
            'limit': 1000
        }
        
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if not data:
            break
            
        all_data.extend(data)
        current_start = data[-1][0] + 1
        time.sleep(0.1)  # Rate limit
        
        print(f"Fetched {len(all_data)} candles...")
    
    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    return df

def save_data(df, filepath):
    """데이터 저장"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df.to_csv(filepath, index=False)
    print(f"Saved to {filepath}")

if __name__ == "__main__":
    print("Fetching BTC/USDT daily data...")
    
    # 일봉 데이터 (2020-현재)
    df_daily = fetch_binance_klines('BTCUSDT', '1d', '2020-01-01')
    save_data(df_daily, 'data/btcusdt_1d.csv')
    
    # 4시간봉 데이터 (2023-현재)
    print("\nFetching BTC/USDT 4h data...")
    df_4h = fetch_binance_klines('BTCUSDT', '4h', '2023-01-01')
    save_data(df_4h, 'data/btcusdt_4h.csv')
    
    # 1시간봉 데이터 (2024-현재)
    print("\nFetching BTC/USDT 1h data...")
    df_1h = fetch_binance_klines('BTCUSDT', '1h', '2024-01-01')
    save_data(df_1h, 'data/btcusdt_1h.csv')
    
    print("\nDone!")
