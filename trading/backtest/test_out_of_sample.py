"""
Out-of-Sample 검증 테스트
훈련: 2020-2023
테스트: 2024-2026
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
    """멀티 전략 실행"""
    
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
                    'entry_price': entry_price,
                    'exit_price': exit_price,
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

if __name__ == "__main__":
    # 전체 데이터 로드
    df = pd.read_csv('data/btcusdt_1d.csv', parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # 기간 분리
    train_df = df[df.index < '2024-01-01']
    test_df = df[df.index >= '2024-01-01']
    
    print("="*60)
    print("Out-of-Sample 검증 테스트")
    print("="*60)
    print(f"\n훈련 기간: {train_df.index[0].date()} ~ {train_df.index[-1].date()} ({len(train_df)}일)")
    print(f"테스트 기간: {test_df.index[0].date()} ~ {test_df.index[-1].date()} ({len(test_df)}일)")
    
    # 고정 파라미터 (이미 최적화된 값 사용)
    params = {
        'rsi_period': 14, 'entry_rsi': 70, 'exit_rsi': 55,
        'bb_period': 20, 'bb_std': 1.5, 'bb_rsi_period': 7,
        'bb_rsi_oversold': 20, 'bb_rsi_overbought': 60
    }
    
    # === 훈련 기간 성과 ===
    print("\n" + "="*60)
    print("훈련 기간 성과 (2020-2023) - In-Sample")
    print("="*60)
    
    train_trades, train_equity = run_multi_strategy(train_df, **params)
    train_metrics = calculate_metrics(train_trades, train_equity)
    if train_metrics:
        print_results(train_metrics, "훈련 기간")
    
    # === 테스트 기간 성과 ===
    print("\n" + "="*60)
    print("테스트 기간 성과 (2024-2026) - Out-of-Sample ⭐")
    print("="*60)
    
    test_trades, test_equity = run_multi_strategy(test_df, **params)
    test_metrics = calculate_metrics(test_trades, test_equity)
    if test_metrics:
        print_results(test_metrics, "테스트 기간 (검증)")
    
    # === 비교 ===
    print("\n" + "="*60)
    print("In-Sample vs Out-of-Sample 비교")
    print("="*60)
    
    print(f"\n{'기간':<20} {'거래수':>8} {'승률':>8} {'손익비':>8} {'수익률':>10} {'최대DD':>10}")
    print("-"*70)
    if train_metrics:
        print(f"{'훈련 (2020-2023)':<20} {train_metrics['total_trades']:>8} {train_metrics['win_rate']:>7.1f}% {train_metrics['risk_reward']:>8.2f} {train_metrics['total_return']:>9.1f}% {train_metrics['max_drawdown']:>9.1f}%")
    if test_metrics:
        print(f"{'테스트 (2024-2026)':<20} {test_metrics['total_trades']:>8} {test_metrics['win_rate']:>7.1f}% {test_metrics['risk_reward']:>8.2f} {test_metrics['total_return']:>9.1f}% {test_metrics['max_drawdown']:>9.1f}%")
    
    # 연환산 수익률 계산
    if train_metrics and test_metrics:
        train_years = len(train_df) / 365
        test_years = len(test_df) / 365
        
        train_annual = ((1 + train_metrics['total_return']/100) ** (1/train_years) - 1) * 100
        test_annual = ((1 + test_metrics['total_return']/100) ** (1/test_years) - 1) * 100
        
        print(f"\n연환산 수익률:")
        print(f"  훈련 기간: {train_annual:.1f}%/년")
        print(f"  테스트 기간: {test_annual:.1f}%/년")
    
    # 전략별 분석
    if test_trades:
        print("\n" + "="*60)
        print("테스트 기간 전략별 분석")
        print("="*60)
        
        df_trades = pd.DataFrame(test_trades)
        for strategy in df_trades['strategy'].unique():
            strat = df_trades[df_trades['strategy'] == strategy]
            wins = len(strat[strat['pnl_pct'] > 0])
            print(f"\n[{strategy}]")
            print(f"  거래: {len(strat)}회, 승률: {wins/len(strat)*100:.1f}%")
            print(f"  수익 합계: {strat['pnl_pct'].sum():.2f}%")
