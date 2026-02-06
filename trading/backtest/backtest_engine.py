"""
BTC Futures Backtesting Engine
- 수수료 반영
- 다양한 전략 테스트 가능
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

# 설정
TAKER_FEE = 0.0004  # 0.04%
MAKER_FEE = 0.0002  # 0.02%
SLIPPAGE = 0.0001   # 0.01%
INITIAL_CAPITAL = 5000  # USD

def load_btc_data(filepath):
    """BTC OHLCV 데이터 로드"""
    df = pd.read_csv(filepath, parse_dates=['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df

def calculate_rsi(prices, period):
    """RSI 계산"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_sma(prices, period):
    """SMA 계산"""
    return prices.rolling(window=period).mean()

def calculate_ema(prices, period):
    """EMA 계산"""
    return prices.ewm(span=period, adjust=False).mean()

def calculate_adx(high, low, close, period):
    """ADX 계산"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    return adx

def backtest_strategy(df, signals, fee=TAKER_FEE):
    """
    백테스트 실행
    signals: DataFrame with 'position' column (1=long, -1=short, 0=flat)
    """
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0
    trades = []
    equity_curve = []
    
    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        signal = signals['position'].iloc[i]
        
        # 포지션 청산
        if position != 0 and signal != position:
            exit_price = current_price * (1 - SLIPPAGE if position > 0 else 1 + SLIPPAGE)
            pnl = (exit_price - entry_price) / entry_price * position
            pnl_after_fee = pnl - fee * 2  # 진입 + 청산 수수료
            capital *= (1 + pnl_after_fee)
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': df.index[i],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position': 'LONG' if position > 0 else 'SHORT',
                'pnl_pct': pnl_after_fee * 100,
                'capital': capital
            })
            position = 0
        
        # 새 포지션 진입
        if signal != 0 and position == 0:
            position = signal
            entry_price = current_price * (1 + SLIPPAGE if signal > 0 else 1 - SLIPPAGE)
            entry_time = df.index[i]
        
        equity_curve.append(capital)
    
    return trades, equity_curve

def calculate_metrics(trades, equity_curve, initial_capital=INITIAL_CAPITAL):
    """성과 지표 계산"""
    if not trades:
        return None
    
    df_trades = pd.DataFrame(trades)
    
    wins = df_trades[df_trades['pnl_pct'] > 0]
    losses = df_trades[df_trades['pnl_pct'] <= 0]
    
    win_rate = len(wins) / len(df_trades) * 100 if len(df_trades) > 0 else 0
    avg_win = wins['pnl_pct'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['pnl_pct'].mean()) if len(losses) > 0 else 0
    profit_factor = (wins['pnl_pct'].sum() / abs(losses['pnl_pct'].sum())) if len(losses) > 0 and losses['pnl_pct'].sum() != 0 else float('inf')
    
    # 드로우다운
    equity = pd.Series(equity_curve)
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    # 총 수익률
    total_return = (equity_curve[-1] - initial_capital) / initial_capital * 100
    
    # 손익비
    risk_reward = avg_win / avg_loss if avg_loss > 0 else float('inf')
    
    return {
        'total_trades': len(df_trades),
        'win_rate': round(win_rate, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'risk_reward': round(risk_reward, 2),
        'profit_factor': round(profit_factor, 2),
        'max_drawdown': round(max_drawdown, 2),
        'total_return': round(total_return, 2),
        'final_capital': round(equity_curve[-1], 2)
    }

def print_results(metrics, strategy_name):
    """결과 출력"""
    print(f"\n{'='*50}")
    print(f"전략: {strategy_name}")
    print(f"{'='*50}")
    print(f"총 거래 수: {metrics['total_trades']}")
    print(f"승률: {metrics['win_rate']}%")
    print(f"평균 수익: {metrics['avg_win']}%")
    print(f"평균 손실: {metrics['avg_loss']}%")
    print(f"손익비: {metrics['risk_reward']}")
    print(f"Profit Factor: {metrics['profit_factor']}")
    print(f"최대 드로우다운: {metrics['max_drawdown']}%")
    print(f"총 수익률: {metrics['total_return']}%")
    print(f"최종 자본: ${metrics['final_capital']}")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    print("Backtest Engine Ready")
    print(f"수수료: {TAKER_FEE*100}% (테이커)")
    print(f"초기 자본: ${INITIAL_CAPITAL}")
