"""
Bollinger Bands + RSI 평균회귀 전략
- 진입: 하단밴드 터치 + RSI < 30
- 청산: 중간밴드 도달 or RSI > 70
"""

import pandas as pd
import numpy as np
from backtest_engine import (
    calculate_rsi, calculate_sma,
    calculate_metrics, print_results,
    TAKER_FEE, SLIPPAGE, INITIAL_CAPITAL
)

def calculate_bollinger(prices, period=20, std_dev=2):
    """볼린저 밴드 계산"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return sma, upper, lower

def run_bollinger_rsi_backtest(data_path, bb_period=20, bb_std=2, rsi_period=14, 
                                rsi_oversold=30, rsi_overbought=70):
    """Bollinger + RSI 전략 백테스트"""
    
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # 지표 계산
    df['bb_mid'], df['bb_upper'], df['bb_lower'] = calculate_bollinger(df['close'], bb_period, bb_std)
    df['rsi'] = calculate_rsi(df['close'], rsi_period)
    
    # 백테스트 실행
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    entry_time = None
    trades = []
    equity_curve = [capital]
    
    for i in range(bb_period, len(df)):
        row = df.iloc[i]
        current_price = row['close']
        
        if pd.isna(row['rsi']) or pd.isna(row['bb_lower']):
            equity_curve.append(capital)
            continue
        
        # 롱 진입 조건: 하단밴드 터치 + RSI 과매도
        entry_long = (current_price <= row['bb_lower']) and (row['rsi'] < rsi_oversold)
        
        # 청산 조건: 중간밴드 도달 or RSI 과매수
        exit_long = (current_price >= row['bb_mid']) or (row['rsi'] > rsi_overbought)
        
        # 포지션 청산
        if position == 1 and exit_long:
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
        elif position == 0 and entry_long:
            position = 1
            entry_price = current_price * (1 + SLIPPAGE)
            entry_time = df.index[i]
        
        equity_curve.append(capital)
    
    return trades, equity_curve, df

if __name__ == "__main__":
    print("="*60)
    print("Bollinger Bands + RSI 평균회귀 전략 백테스트")
    print("="*60)
    
    # 기본 테스트
    trades, equity, df = run_bollinger_rsi_backtest('data/btcusdt_1d.csv')
    metrics = calculate_metrics(trades, equity)
    
    if metrics:
        print_results(metrics, "Bollinger + RSI - 일봉 (기본)")
    else:
        print("거래 없음 - 조건 완화 필요")
    
    # 파라미터 최적화
    print("\n파라미터 최적화 중...")
    results = []
    
    for bb_period in [10, 20, 30]:
        for bb_std in [1.5, 2, 2.5]:
            for rsi_period in [7, 14, 21]:
                for rsi_oversold in [20, 30, 40]:
                    for rsi_overbought in [60, 70, 80]:
                        trades, equity, _ = run_bollinger_rsi_backtest(
                            'data/btcusdt_1d.csv',
                            bb_period=bb_period,
                            bb_std=bb_std,
                            rsi_period=rsi_period,
                            rsi_oversold=rsi_oversold,
                            rsi_overbought=rsi_overbought
                        )
                        metrics = calculate_metrics(trades, equity)
                        if metrics and metrics['total_trades'] >= 5:
                            results.append({
                                'bb_period': bb_period,
                                'bb_std': bb_std,
                                'rsi_period': rsi_period,
                                'rsi_oversold': rsi_oversold,
                                'rsi_overbought': rsi_overbought,
                                **metrics
                            })
    
    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values('total_return', ascending=False)
        print("\n상위 10개 파라미터 조합:")
        cols = ['bb_period', 'bb_std', 'rsi_period', 'rsi_oversold', 'rsi_overbought', 
                'total_trades', 'win_rate', 'risk_reward', 'total_return', 'max_drawdown']
        print(df_results.head(10)[cols].to_string())
        
        df_results.to_csv('results/bollinger_rsi_optimization.csv', index=False)
    else:
        print("유효한 결과 없음")
