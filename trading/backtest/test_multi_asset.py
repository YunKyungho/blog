"""
멀티 자산 테스트 - 동일 전략을 BTC, ETH, SOL에 적용
"""

import pandas as pd
import numpy as np
from backtest_engine import (
    calculate_rsi, calculate_metrics, print_results,
    TAKER_FEE, SLIPPAGE, INITIAL_CAPITAL
)

def calculate_bollinger(prices, period=20, std_dev=2):
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return sma, upper, lower

def run_multi_strategy(df, rsi_period=14, entry_rsi=70, exit_rsi=55,
                       bb_period=20, bb_std=1.5, bb_rsi_period=7,
                       bb_rsi_oversold=20, bb_rsi_overbought=60):
    
    df = df.copy()
    df['rsi_momentum'] = calculate_rsi(df['close'], rsi_period)
    df['rsi_bb'] = calculate_rsi(df['close'], bb_rsi_period)
    df['bb_mid'], df['bb_upper'], df['bb_lower'] = calculate_bollinger(df['close'], bb_period, bb_std)
    
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    entry_time = None
    entry_strategy = None
    trades = []
    equity_curve = [capital]
    
    start_idx = max(rsi_period, bb_period) + 1
    
    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        current_price = row['close']
        
        if pd.isna(row['rsi_momentum']) or pd.isna(row['bb_lower']):
            equity_curve.append(capital)
            continue
        
        rsi_entry = row['rsi_momentum'] > entry_rsi
        rsi_exit = row['rsi_momentum'] < exit_rsi
        bb_entry = (current_price <= row['bb_lower']) and (row['rsi_bb'] < bb_rsi_oversold)
        bb_exit = (current_price >= row['bb_mid']) or (row['rsi_bb'] > bb_rsi_overbought)
        
        if position == 1:
            should_exit = False
            if entry_strategy == 'RSI_MOMENTUM' and rsi_exit:
                should_exit = True
            elif entry_strategy == 'BOLLINGER_RSI' and bb_exit:
                should_exit = True
            
            if should_exit:
                exit_price = current_price * (1 - SLIPPAGE)
                pnl = (exit_price - entry_price) / entry_price
                pnl_after_fee = pnl - TAKER_FEE * 2
                capital *= (1 + pnl_after_fee)
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': df.index[i],
                    'strategy': entry_strategy,
                    'pnl_pct': pnl_after_fee * 100,
                    'capital': capital
                })
                position = 0
                entry_strategy = None
        
        if position == 0:
            if rsi_entry:
                position = 1
                entry_price = current_price * (1 + SLIPPAGE)
                entry_time = df.index[i]
                entry_strategy = 'RSI_MOMENTUM'
            elif bb_entry:
                position = 1
                entry_price = current_price * (1 + SLIPPAGE)
                entry_time = df.index[i]
                entry_strategy = 'BOLLINGER_RSI'
        
        equity_curve.append(capital)
    
    return trades, equity_curve

def test_asset(filepath, name):
    """자산별 테스트"""
    df = pd.read_csv(filepath, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    print(f"\n{'='*60}")
    print(f"{name} 테스트")
    print(f"기간: {df.index[0].date()} ~ {df.index[-1].date()}")
    print(f"{'='*60}")
    
    # 고정 파라미터
    params = {
        'rsi_period': 14, 'entry_rsi': 70, 'exit_rsi': 55,
        'bb_period': 20, 'bb_std': 1.5, 'bb_rsi_period': 7,
        'bb_rsi_oversold': 20, 'bb_rsi_overbought': 60
    }
    
    trades, equity = run_multi_strategy(df, **params)
    metrics = calculate_metrics(trades, equity)
    
    if metrics:
        print_results(metrics, name)
        
        # 전략별 분석
        df_trades = pd.DataFrame(trades)
        for strategy in df_trades['strategy'].unique():
            strat = df_trades[df_trades['strategy'] == strategy]
            wins = len(strat[strat['pnl_pct'] > 0])
            print(f"  [{strategy}] 거래: {len(strat)}, 승률: {wins/len(strat)*100:.1f}%, 기여: {strat['pnl_pct'].sum():.1f}%")
    
    return metrics

if __name__ == "__main__":
    print("="*60)
    print("멀티 자산 테스트 - 동일 전략 적용")
    print("="*60)
    
    results = {}
    
    # BTC
    results['BTC'] = test_asset('data/btcusdt_1d.csv', 'BTC/USDT')
    
    # ETH
    results['ETH'] = test_asset('data/ethusdt_1d.csv', 'ETH/USDT')
    
    # SOL
    results['SOL'] = test_asset('data/solusdt_1d.csv', 'SOL/USDT')
    
    # 비교 테이블
    print("\n" + "="*60)
    print("자산별 성과 비교")
    print("="*60)
    
    print(f"\n{'자산':<10} {'거래수':>8} {'승률':>8} {'손익비':>8} {'수익률':>12} {'최대DD':>10}")
    print("-"*60)
    
    for asset, m in results.items():
        if m:
            print(f"{asset:<10} {m['total_trades']:>8} {m['win_rate']:>7.1f}% {m['risk_reward']:>8.2f} {m['total_return']:>11.1f}% {m['max_drawdown']:>9.1f}%")
