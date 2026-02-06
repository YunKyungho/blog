"""
멀티 전략 시스템 백테스트
1순위: RSI 모멘텀 (추세 추종)
2순위: Bollinger + RSI (평균 회귀)
"""

import pandas as pd
import numpy as np
from backtest_engine import (
    calculate_rsi, calculate_sma, calculate_ema,
    calculate_metrics, print_results,
    TAKER_FEE, SLIPPAGE, INITIAL_CAPITAL
)

def calculate_bollinger(prices, period=20, std_dev=2):
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return sma, upper, lower

def run_multi_strategy_backtest(data_path,
                                 # RSI 모멘텀 파라미터 (1순위)
                                 rsi_period=14, entry_rsi=70, exit_rsi=55,
                                 # Bollinger+RSI 파라미터 (2순위)
                                 bb_period=20, bb_std=1.5, bb_rsi_period=7,
                                 bb_rsi_oversold=20, bb_rsi_overbought=60):
    
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # 지표 계산
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
    
    for i in range(max(rsi_period, bb_period) + 1, len(df)):
        row = df.iloc[i]
        current_price = row['close']
        
        if pd.isna(row['rsi_momentum']) or pd.isna(row['bb_lower']):
            equity_curve.append(capital)
            continue
        
        # === 1순위: RSI 모멘텀 신호 ===
        rsi_entry = row['rsi_momentum'] > entry_rsi
        rsi_exit = row['rsi_momentum'] < exit_rsi
        
        # === 2순위: Bollinger + RSI 신호 ===
        bb_entry = (current_price <= row['bb_lower']) and (row['rsi_bb'] < bb_rsi_oversold)
        bb_exit = (current_price >= row['bb_mid']) or (row['rsi_bb'] > bb_rsi_overbought)
        
        # === 청산 로직 ===
        if position == 1:
            # 각 전략에 맞는 청산 조건
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
        
        # === 진입 로직 (우선순위 적용) ===
        if position == 0:
            # 1순위: RSI 모멘텀
            if rsi_entry:
                position = 1
                entry_price = current_price * (1 + SLIPPAGE)
                entry_time = df.index[i]
                entry_strategy = 'RSI_MOMENTUM'
            # 2순위: Bollinger + RSI (1순위 신호 없을 때만)
            elif bb_entry:
                position = 1
                entry_price = current_price * (1 + SLIPPAGE)
                entry_time = df.index[i]
                entry_strategy = 'BOLLINGER_RSI'
        
        equity_curve.append(capital)
    
    return trades, equity_curve, df

def analyze_by_strategy(trades):
    """전략별 분석"""
    if not trades:
        return
    
    df = pd.DataFrame(trades)
    
    print("\n" + "="*50)
    print("전략별 성과 분석")
    print("="*50)
    
    for strategy in df['strategy'].unique():
        strat_trades = df[df['strategy'] == strategy]
        wins = strat_trades[strat_trades['pnl_pct'] > 0]
        losses = strat_trades[strat_trades['pnl_pct'] <= 0]
        
        print(f"\n[{strategy}]")
        print(f"  거래 수: {len(strat_trades)}")
        print(f"  승률: {len(wins)/len(strat_trades)*100:.1f}%")
        if len(wins) > 0:
            print(f"  평균 수익: +{wins['pnl_pct'].mean():.2f}%")
        if len(losses) > 0:
            print(f"  평균 손실: {losses['pnl_pct'].mean():.2f}%")
        print(f"  총 수익: {strat_trades['pnl_pct'].sum():.2f}%")

if __name__ == "__main__":
    print("="*60)
    print("멀티 전략 시스템 백테스트")
    print("1순위: RSI 모멘텀 | 2순위: Bollinger + RSI")
    print("="*60)
    
    # 기본 테스트 (각 전략의 최적 파라미터 사용)
    trades, equity, df = run_multi_strategy_backtest(
        'data/btcusdt_1d.csv',
        # RSI 모멘텀 최적값
        rsi_period=14, entry_rsi=70, exit_rsi=55,
        # Bollinger+RSI 최적값
        bb_period=20, bb_std=1.5, bb_rsi_period=7,
        bb_rsi_oversold=20, bb_rsi_overbought=60
    )
    
    metrics = calculate_metrics(trades, equity)
    if metrics:
        print_results(metrics, "멀티 전략 (RSI 모멘텀 + Bollinger RSI)")
        analyze_by_strategy(trades)
    
    # 단일 전략과 비교
    print("\n" + "="*60)
    print("단일 전략 vs 멀티 전략 비교")
    print("="*60)
    
    # RSI 모멘텀 단독
    from test_rsi_momentum import run_rsi_momentum_backtest
    rsi_trades, rsi_equity, _ = run_rsi_momentum_backtest(
        'data/btcusdt_1d.csv', rsi_period=14, entry_threshold=70, exit_threshold=55
    )
    rsi_metrics = calculate_metrics(rsi_trades, rsi_equity)
    
    # Bollinger 단독
    from test_bollinger_rsi import run_bollinger_rsi_backtest
    bb_trades, bb_equity, _ = run_bollinger_rsi_backtest(
        'data/btcusdt_1d.csv', bb_period=20, bb_std=1.5, rsi_period=7,
        rsi_oversold=20, rsi_overbought=60
    )
    bb_metrics = calculate_metrics(bb_trades, bb_equity)
    
    print(f"\n{'전략':<25} {'거래수':>8} {'승률':>8} {'수익률':>10} {'최대DD':>10}")
    print("-"*65)
    print(f"{'RSI 모멘텀 단독':<25} {rsi_metrics['total_trades']:>8} {rsi_metrics['win_rate']:>7.1f}% {rsi_metrics['total_return']:>9.1f}% {rsi_metrics['max_drawdown']:>9.1f}%")
    print(f"{'Bollinger+RSI 단독':<25} {bb_metrics['total_trades']:>8} {bb_metrics['win_rate']:>7.1f}% {bb_metrics['total_return']:>9.1f}% {bb_metrics['max_drawdown']:>9.1f}%")
    print(f"{'멀티 전략 (조합)':<25} {metrics['total_trades']:>8} {metrics['win_rate']:>7.1f}% {metrics['total_return']:>9.1f}% {metrics['max_drawdown']:>9.1f}%")
