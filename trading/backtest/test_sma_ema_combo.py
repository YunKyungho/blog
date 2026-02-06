"""
SMA + EMA + RSI/ADX 콤보 전략 백테스트
- 진입: Close > SMA(50), Close > EMA(7), RSI(2) > ADX(2)
- 청산: RSI(2) < 기준값
"""

import pandas as pd
import numpy as np
from backtest_engine import (
    calculate_rsi, calculate_sma, calculate_ema, calculate_adx,
    calculate_metrics, print_results,
    TAKER_FEE, SLIPPAGE, INITIAL_CAPITAL
)

def run_combo_backtest(data_path, sma_period=50, ema_period=7, rsi_period=2, adx_period=2, exit_rsi=30):
    """SMA/EMA/RSI/ADX 콤보 전략 백테스트"""
    
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # 지표 계산
    df['sma'] = calculate_sma(df['close'], sma_period)
    df['ema'] = calculate_ema(df['close'], ema_period)
    df['rsi'] = calculate_rsi(df['close'], rsi_period)
    df['adx'] = calculate_adx(df['high'], df['low'], df['close'], adx_period)
    
    # 백테스트 실행
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    entry_time = None
    trades = []
    equity_curve = [capital]
    
    for i in range(sma_period, len(df)):
        row = df.iloc[i]
        current_price = row['close']
        
        if pd.isna(row['rsi']) or pd.isna(row['adx']) or pd.isna(row['sma']):
            equity_curve.append(capital)
            continue
        
        # 진입 조건
        entry_condition = (
            current_price > row['sma'] and
            current_price > row['ema'] and
            row['rsi'] > row['adx']
        )
        
        # 청산 조건
        exit_condition = row['rsi'] < exit_rsi
        
        # 포지션 청산
        if position == 1 and exit_condition:
            exit_price = current_price * (1 - SLIPPAGE)
            pnl = (exit_price - entry_price) / entry_price
            pnl_after_fee = pnl - TAKER_FEE * 2
            capital *= (1 + pnl_after_fee)
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': df.index[i],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position': 'LONG',
                'pnl_pct': pnl_after_fee * 100,
                'capital': capital,
                'holding_days': (df.index[i] - entry_time).days
            })
            position = 0
        
        # 포지션 진입
        elif position == 0 and entry_condition:
            position = 1
            entry_price = current_price * (1 + SLIPPAGE)
            entry_time = df.index[i]
        
        equity_curve.append(capital)
    
    return trades, equity_curve, df

if __name__ == "__main__":
    print("="*60)
    print("SMA + EMA + RSI/ADX 콤보 전략 백테스트")
    print("="*60)
    
    # 기본 테스트
    trades, equity, df = run_combo_backtest('data/btcusdt_1d.csv')
    metrics = calculate_metrics(trades, equity)
    
    if metrics:
        print_results(metrics, "SMA/EMA/RSI/ADX 콤보 - 일봉 (기본)")
    
    # 파라미터 최적화
    print("\n파라미터 최적화 중...")
    results = []
    
    for sma in [20, 50, 100]:
        for ema in [5, 7, 10, 14]:
            for rsi_p in [2, 3, 5]:
                for exit_rsi in [20, 30, 40, 50]:
                    trades, equity, _ = run_combo_backtest(
                        'data/btcusdt_1d.csv',
                        sma_period=sma,
                        ema_period=ema,
                        rsi_period=rsi_p,
                        exit_rsi=exit_rsi
                    )
                    metrics = calculate_metrics(trades, equity)
                    if metrics and metrics['total_trades'] >= 10:
                        results.append({
                            'sma': sma,
                            'ema': ema,
                            'rsi_period': rsi_p,
                            'exit_rsi': exit_rsi,
                            **metrics
                        })
    
    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values('total_return', ascending=False)
        print("\n상위 10개 파라미터 조합:")
        print(df_results.head(10)[['sma', 'ema', 'rsi_period', 'exit_rsi', 'win_rate', 'risk_reward', 'total_return', 'max_drawdown']].to_string())
        
        df_results.to_csv('results/sma_ema_combo_optimization.csv', index=False)
