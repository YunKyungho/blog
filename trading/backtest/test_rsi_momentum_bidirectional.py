"""
RSI 모멘텀 전략 - 양방향 (롱+숏)
- 롱 진입: RSI > entry_long
- 롱 청산: RSI < exit_long
- 숏 진입: RSI < entry_short
- 숏 청산: RSI > exit_short
"""

import pandas as pd
import numpy as np
from backtest_engine import (
    calculate_rsi, calculate_metrics, print_results,
    TAKER_FEE, SLIPPAGE, INITIAL_CAPITAL
)

def run_bidirectional_backtest(data_path, rsi_period=14, 
                                entry_long=70, exit_long=55,
                                entry_short=30, exit_short=45):
    """양방향 RSI 모멘텀 백테스트"""
    
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    df['rsi'] = calculate_rsi(df['close'], rsi_period)
    
    capital = INITIAL_CAPITAL
    position = 0  # 1=롱, -1=숏, 0=없음
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
        
        # === 롱 포지션 로직 ===
        # 롱 청산
        if position == 1 and rsi < exit_long:
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
                'capital': capital
            })
            position = 0
        
        # === 숏 포지션 로직 ===
        # 숏 청산
        elif position == -1 and rsi > exit_short:
            exit_price = current_price * (1 + SLIPPAGE)
            pnl = (entry_price - exit_price) / entry_price  # 숏은 반대
            pnl_after_fee = pnl - TAKER_FEE * 2
            capital *= (1 + pnl_after_fee)
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': df.index[i],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position': 'SHORT',
                'pnl_pct': pnl_after_fee * 100,
                'capital': capital
            })
            position = 0
        
        # === 진입 로직 ===
        # 롱 진입
        if position == 0 and rsi > entry_long:
            position = 1
            entry_price = current_price * (1 + SLIPPAGE)
            entry_time = df.index[i]
        
        # 숏 진입
        elif position == 0 and rsi < entry_short:
            position = -1
            entry_price = current_price * (1 - SLIPPAGE)
            entry_time = df.index[i]
        
        equity_curve.append(capital)
    
    return trades, equity_curve, df

def analyze_by_direction(trades):
    """롱/숏 별도 분석"""
    if not trades:
        return
    
    df = pd.DataFrame(trades)
    
    longs = df[df['position'] == 'LONG']
    shorts = df[df['position'] == 'SHORT']
    
    print("\n=== 방향별 분석 ===")
    print(f"\n[롱] 거래수: {len(longs)}")
    if len(longs) > 0:
        print(f"  승률: {(longs['pnl_pct'] > 0).mean() * 100:.1f}%")
        print(f"  평균 수익: {longs[longs['pnl_pct'] > 0]['pnl_pct'].mean():.2f}%")
        print(f"  평균 손실: {longs[longs['pnl_pct'] <= 0]['pnl_pct'].mean():.2f}%")
    
    print(f"\n[숏] 거래수: {len(shorts)}")
    if len(shorts) > 0:
        print(f"  승률: {(shorts['pnl_pct'] > 0).mean() * 100:.1f}%")
        print(f"  평균 수익: {shorts[shorts['pnl_pct'] > 0]['pnl_pct'].mean():.2f}%")
        print(f"  평균 손실: {shorts[shorts['pnl_pct'] <= 0]['pnl_pct'].mean():.2f}%")

if __name__ == "__main__":
    print("="*60)
    print("RSI 모멘텀 전략 - 양방향 (롱+숏)")
    print("="*60)
    
    # 기본 테스트 (롱온리 최적값 기반)
    trades, equity, df = run_bidirectional_backtest(
        'data/btcusdt_1d.csv',
        rsi_period=14,
        entry_long=70, exit_long=55,
        entry_short=30, exit_short=45
    )
    metrics = calculate_metrics(trades, equity)
    
    if metrics:
        print_results(metrics, "RSI(14) 양방향 - 롱70/55, 숏30/45")
        analyze_by_direction(trades)
    
    # 파라미터 최적화
    print("\n" + "="*60)
    print("파라미터 최적화")
    print("="*60)
    
    results = []
    for rsi_p in [7, 14, 21]:
        for entry_l in [65, 70, 75]:
            for exit_l in [50, 55, 60]:
                for entry_s in [25, 30, 35]:
                    for exit_s in [40, 45, 50]:
                        if exit_l >= entry_l or exit_s <= entry_s:
                            continue
                        
                        trades, equity, _ = run_bidirectional_backtest(
                            'data/btcusdt_1d.csv',
                            rsi_period=rsi_p,
                            entry_long=entry_l, exit_long=exit_l,
                            entry_short=entry_s, exit_short=exit_s
                        )
                        metrics = calculate_metrics(trades, equity)
                        if metrics and metrics['total_trades'] >= 20:
                            # 롱/숏 각각 분석
                            df_trades = pd.DataFrame(trades)
                            long_trades = len(df_trades[df_trades['position'] == 'LONG'])
                            short_trades = len(df_trades[df_trades['position'] == 'SHORT'])
                            
                            results.append({
                                'rsi': rsi_p,
                                'entry_long': entry_l,
                                'exit_long': exit_l,
                                'entry_short': entry_s,
                                'exit_short': exit_s,
                                'long_trades': long_trades,
                                'short_trades': short_trades,
                                **metrics
                            })
    
    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values('total_return', ascending=False)
        
        print("\n상위 10개 조합:")
        cols = ['rsi', 'entry_long', 'exit_long', 'entry_short', 'exit_short', 
                'long_trades', 'short_trades', 'win_rate', 'total_return', 'max_drawdown']
        print(df_results.head(10)[cols].to_string())
        
        df_results.to_csv('results/rsi_bidirectional_optimization.csv', index=False)
        print("\n결과 저장 완료")
