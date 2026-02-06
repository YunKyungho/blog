"""
RSI(5) 모멘텀 전략 백테스트
- 진입: RSI(5) > 70
- 청산: RSI(5) < 50
"""

import pandas as pd
import numpy as np
from backtest_engine import (
    calculate_rsi, calculate_metrics, print_results,
    TAKER_FEE, SLIPPAGE, INITIAL_CAPITAL
)

def run_rsi_momentum_backtest(data_path, rsi_period=5, entry_threshold=70, exit_threshold=50):
    """RSI 모멘텀 전략 백테스트"""
    
    # 데이터 로드
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # RSI 계산
    df['rsi'] = calculate_rsi(df['close'], rsi_period)
    
    # 시그널 생성
    df['signal'] = 0
    df.loc[df['rsi'] > entry_threshold, 'signal'] = 1  # 롱 진입 신호
    df.loc[df['rsi'] < exit_threshold, 'signal'] = -1  # 청산 신호
    
    # 백테스트 실행
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    entry_time = None
    trades = []
    equity_curve = [capital]
    
    for i in range(1, len(df)):
        current_price = df['close'].iloc[i]
        rsi = df['rsi'].iloc[i]
        
        if pd.isna(rsi):
            equity_curve.append(capital)
            continue
        
        # 포지션 있고 청산 조건
        if position == 1 and rsi < exit_threshold:
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
        
        # 포지션 없고 진입 조건
        elif position == 0 and rsi > entry_threshold:
            position = 1
            entry_price = current_price * (1 + SLIPPAGE)
            entry_time = df.index[i]
        
        equity_curve.append(capital)
    
    return trades, equity_curve, df

def analyze_trades(trades):
    """거래 분석"""
    if not trades:
        print("거래 없음")
        return
    
    df_trades = pd.DataFrame(trades)
    
    print(f"\n거래 상세:")
    print(f"총 거래 수: {len(trades)}")
    print(f"평균 보유 기간: {df_trades['holding_days'].mean():.1f}일")
    print(f"\n최근 10개 거래:")
    print(df_trades.tail(10)[['entry_time', 'exit_time', 'pnl_pct', 'holding_days']].to_string())

if __name__ == "__main__":
    print("="*60)
    print("RSI(5) 모멘텀 전략 백테스트")
    print("진입: RSI > 70 | 청산: RSI < 50")
    print("="*60)
    
    # 일봉 테스트
    trades, equity, df = run_rsi_momentum_backtest('data/btcusdt_1d.csv')
    metrics = calculate_metrics(trades, equity)
    
    if metrics:
        print_results(metrics, "RSI(5) 모멘텀 - 일봉")
        analyze_trades(trades)
    
    # 다른 파라미터 테스트
    print("\n" + "="*60)
    print("파라미터 최적화 테스트")
    print("="*60)
    
    results = []
    for rsi_period in [3, 5, 7, 14]:
        for entry in [60, 65, 70, 75]:
            for exit in [40, 45, 50, 55]:
                if entry <= exit:
                    continue
                trades, equity, _ = run_rsi_momentum_backtest(
                    'data/btcusdt_1d.csv',
                    rsi_period=rsi_period,
                    entry_threshold=entry,
                    exit_threshold=exit
                )
                metrics = calculate_metrics(trades, equity)
                if metrics and metrics['total_trades'] >= 10:
                    results.append({
                        'rsi_period': rsi_period,
                        'entry': entry,
                        'exit': exit,
                        **metrics
                    })
    
    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values('total_return', ascending=False)
        print("\n상위 10개 파라미터 조합:")
        print(df_results.head(10)[['rsi_period', 'entry', 'exit', 'win_rate', 'risk_reward', 'total_return', 'max_drawdown']].to_string())
        
        # 결과 저장
        df_results.to_csv('results/rsi_momentum_optimization.csv', index=False)
        print("\n결과 저장: results/rsi_momentum_optimization.csv")
