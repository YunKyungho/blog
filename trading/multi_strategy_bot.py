#!/usr/bin/env python3
"""
멀티 전략 일봉 트레이딩 봇
- 1순위: RSI 모멘텀 (추세 추종)
- 2순위: Bollinger + RSI (평균 회귀)
- 매일 오전 9시 (UTC 0시, 일봉 마감) 체크
"""

import os
import hmac
import hashlib
import time
import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

# === 설정 ===
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / 'config.json'
STATUS_PATH = BASE_DIR / 'multi_strategy_status.json'
LOG_PATH = BASE_DIR / 'multi_strategy.log'

# Binance API
API_KEY = os.environ.get('BINANCE_API_KEY')
SECRET = os.environ.get('BINANCE_SECRET')
BASE_URL = "https://fapi.binance.com"
SPOT_URL = "https://api.binance.com"

# 전략 파라미터 (백테스트 최적화 결과)
STRATEGY_PARAMS = {
    # RSI 모멘텀 (1순위)
    'rsi_period': 14,
    'rsi_entry': 70,      # RSI > 70 진입
    'rsi_exit': 55,       # RSI < 55 청산
    
    # Bollinger + RSI (2순위)
    'bb_period': 20,
    'bb_std': 1.5,
    'bb_rsi_period': 7,
    'bb_rsi_oversold': 20,   # RSI < 20 진입
    'bb_rsi_overbought': 60, # RSI > 60 청산
}

# 리스크 관리
LEVERAGE = 1   # 레버리지 1배 (현물과 동일)
RISK_PER_TRADE = 1.0  # 전체 자산 사용

def log(msg):
    """로그 기록"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def get_signature(query_string):
    return hmac.new(SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def api_request(method, endpoint, params=None, base_url=BASE_URL):
    """Binance API 요청"""
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = '&'.join(f"{k}={v}" for k, v in params.items())
    signature = get_signature(query)
    url = f"{base_url}{endpoint}?{query}&signature={signature}"
    headers = {'X-MBX-APIKEY': API_KEY}
    
    if method == 'GET':
        resp = requests.get(url, headers=headers)
    elif method == 'POST':
        resp = requests.post(url, headers=headers)
    elif method == 'DELETE':
        resp = requests.delete(url, headers=headers)
    
    return resp.json()

def get_klines(symbol='BTCUSDT', interval='1d', limit=100):
    """캔들 데이터 조회 (공개 API)"""
    url = f"{SPOT_URL}/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    
    df.set_index('timestamp', inplace=True)
    return df

def calculate_rsi(prices, period):
    """RSI 계산"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger(prices, period, std_dev):
    """볼린저 밴드 계산"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return sma, upper, lower

def analyze_market():
    """시장 분석 및 신호 생성"""
    df = get_klines('BTCUSDT', '1d', 100)
    
    # 지표 계산
    df['rsi_momentum'] = calculate_rsi(df['close'], STRATEGY_PARAMS['rsi_period'])
    df['rsi_bb'] = calculate_rsi(df['close'], STRATEGY_PARAMS['bb_rsi_period'])
    df['bb_mid'], df['bb_upper'], df['bb_lower'] = calculate_bollinger(
        df['close'], 
        STRATEGY_PARAMS['bb_period'], 
        STRATEGY_PARAMS['bb_std']
    )
    
    # 최신 캔들 (완성된 마지막 캔들 = -2번째, -1은 현재 진행중)
    latest = df.iloc[-2]
    current_price = df.iloc[-1]['close']
    
    result = {
        'timestamp': str(latest.name),
        'price': current_price,
        'rsi_momentum': round(latest['rsi_momentum'], 2),
        'rsi_bb': round(latest['rsi_bb'], 2),
        'bb_mid': round(latest['bb_mid'], 2),
        'bb_upper': round(latest['bb_upper'], 2),
        'bb_lower': round(latest['bb_lower'], 2),
        'signal': None,
        'strategy': None,
        'action': None
    }
    
    # === 1순위: RSI 모멘텀 신호 ===
    if latest['rsi_momentum'] > STRATEGY_PARAMS['rsi_entry']:
        result['signal'] = 'LONG'
        result['strategy'] = 'RSI_MOMENTUM'
        result['action'] = 'ENTER'
    elif latest['rsi_momentum'] < STRATEGY_PARAMS['rsi_exit']:
        result['signal'] = 'EXIT'
        result['strategy'] = 'RSI_MOMENTUM'
        result['action'] = 'EXIT'
    
    # === 2순위: Bollinger + RSI 신호 (1순위 없을 때만) ===
    if result['signal'] is None:
        if current_price <= latest['bb_lower'] and latest['rsi_bb'] < STRATEGY_PARAMS['bb_rsi_oversold']:
            result['signal'] = 'LONG'
            result['strategy'] = 'BOLLINGER_RSI'
            result['action'] = 'ENTER'
        elif current_price >= latest['bb_mid'] or latest['rsi_bb'] > STRATEGY_PARAMS['bb_rsi_overbought']:
            result['signal'] = 'EXIT'
            result['strategy'] = 'BOLLINGER_RSI'
            result['action'] = 'EXIT'
    
    return result

def get_balance():
    """USDT 잔고 조회"""
    result = api_request('GET', '/fapi/v2/balance')
    if isinstance(result, list):
        for bal in result:
            if bal['asset'] == 'USDT':
                return float(bal['balance'])
    return 0

def get_position():
    """현재 포지션 조회"""
    result = api_request('GET', '/fapi/v2/positionRisk')
    if isinstance(result, list):
        for pos in result:
            if pos['symbol'] == 'BTCUSDT':
                amt = float(pos['positionAmt'])
                if amt != 0:
                    return {
                        'side': 'LONG' if amt > 0 else 'SHORT',
                        'amount': abs(amt),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit']),
                        'mark_price': float(pos['markPrice'])
                    }
    return None

def set_leverage():
    """레버리지 설정"""
    return api_request('POST', '/fapi/v1/leverage', {
        'symbol': 'BTCUSDT',
        'leverage': LEVERAGE
    })

def place_order(side, quantity, reduce_only=False):
    """시장가 주문"""
    params = {
        'symbol': 'BTCUSDT',
        'side': side,
        'type': 'MARKET',
        'quantity': quantity
    }
    if reduce_only:
        params['reduceOnly'] = 'true'
    
    return api_request('POST', '/fapi/v1/order', params)

def close_position(position):
    """포지션 청산"""
    side = 'SELL' if position['side'] == 'LONG' else 'BUY'
    return place_order(side, position['amount'], reduce_only=True)

def open_position(balance, price):
    """포지션 진입"""
    # 포지션 크기 계산 (잔고 * 레버리지 / 가격)
    notional = balance * LEVERAGE * RISK_PER_TRADE
    quantity = round(notional / price, 3)
    
    if quantity < 0.001:
        log(f"⚠️ 수량 부족: {quantity}")
        return None
    
    return place_order('BUY', quantity)

def load_status():
    """상태 로드"""
    if STATUS_PATH.exists():
        with open(STATUS_PATH) as f:
            return json.load(f)
    return {
        'position_strategy': None,  # 현재 포지션이 어떤 전략으로 진입했는지
        'last_check': None,
        'last_signal': None
    }

def save_status(status):
    """상태 저장"""
    with open(STATUS_PATH, 'w') as f:
        json.dump(status, f, indent=2, default=str)

def run():
    """메인 실행"""
    log("=" * 50)
    log("멀티 전략 봇 실행")
    
    # API 키 확인
    if not API_KEY or not SECRET:
        log("❌ API 키 없음. 환경변수 설정 필요.")
        return
    
    # 상태 로드
    status = load_status()
    
    # 시장 분석
    analysis = analyze_market()
    log(f"📊 분석 결과:")
    log(f"   가격: ${analysis['price']:,.2f}")
    log(f"   RSI(14): {analysis['rsi_momentum']}")
    log(f"   RSI(7): {analysis['rsi_bb']}")
    log(f"   BB: {analysis['bb_lower']:.0f} / {analysis['bb_mid']:.0f} / {analysis['bb_upper']:.0f}")
    
    # 잔고 및 포지션 확인
    balance = get_balance()
    position = get_position()
    
    log(f"💰 잔고: ${balance:,.2f}")
    if position:
        log(f"📈 포지션: {position['side']} {position['amount']} BTC @ ${position['entry_price']:,.2f}")
        log(f"   손익: ${position['unrealized_pnl']:,.2f}")
    else:
        log("📈 포지션: 없음")
    
    # === 거래 로직 ===
    
    # 포지션 있을 때
    if position:
        # 해당 전략의 청산 조건 확인
        should_exit = False
        
        if status.get('position_strategy') == 'RSI_MOMENTUM':
            if analysis['rsi_momentum'] < STRATEGY_PARAMS['rsi_exit']:
                should_exit = True
                log(f"🔴 RSI 모멘텀 청산 신호: RSI {analysis['rsi_momentum']} < {STRATEGY_PARAMS['rsi_exit']}")
        
        elif status.get('position_strategy') == 'BOLLINGER_RSI':
            if analysis['price'] >= analysis['bb_mid'] or analysis['rsi_bb'] > STRATEGY_PARAMS['bb_rsi_overbought']:
                should_exit = True
                log(f"🔴 볼린저 청산 신호: 가격 {analysis['price']:.0f} >= BB중간 {analysis['bb_mid']:.0f} or RSI {analysis['rsi_bb']} > {STRATEGY_PARAMS['bb_rsi_overbought']}")
        
        if should_exit:
            log("🔴 포지션 청산 실행")
            result = close_position(position)
            log(f"   결과: {result}")
            status['position_strategy'] = None
    
    # 포지션 없을 때
    else:
        # 1순위: RSI 모멘텀
        if analysis['rsi_momentum'] > STRATEGY_PARAMS['rsi_entry']:
            log(f"🟢 RSI 모멘텀 진입 신호: RSI {analysis['rsi_momentum']} > {STRATEGY_PARAMS['rsi_entry']}")
            set_leverage()
            result = open_position(balance, analysis['price'])
            if result and 'orderId' in result:
                log(f"   주문 성공: {result}")
                status['position_strategy'] = 'RSI_MOMENTUM'
            else:
                log(f"   주문 실패: {result}")
        
        # 2순위: 볼린저 + RSI
        elif analysis['price'] <= analysis['bb_lower'] and analysis['rsi_bb'] < STRATEGY_PARAMS['bb_rsi_oversold']:
            log(f"🟢 볼린저 진입 신호: 가격 {analysis['price']:.0f} <= BB하단 {analysis['bb_lower']:.0f}, RSI {analysis['rsi_bb']} < {STRATEGY_PARAMS['bb_rsi_oversold']}")
            set_leverage()
            result = open_position(balance, analysis['price'])
            if result and 'orderId' in result:
                log(f"   주문 성공: {result}")
                status['position_strategy'] = 'BOLLINGER_RSI'
            else:
                log(f"   주문 실패: {result}")
        
        else:
            log("⏸️ 신호 없음. 대기.")
    
    # 상태 저장
    status['last_check'] = datetime.now().isoformat()
    status['last_signal'] = analysis
    save_status(status)
    
    log("=" * 50)

if __name__ == "__main__":
    run()
