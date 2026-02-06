#!/usr/bin/env python3
"""
🐻 하락장 전용 BTC 숏 트레이딩 봇

사용법:
    python3 bear_market_bot.py           # 실시간 실행
    python3 bear_market_bot.py --test    # 테스트 모드 (주문 안함)
    python3 bear_market_bot.py --signal  # 신호만 확인

전략: Combined Bear (RSI + 모멘텀 + BB + ADX 복합 신호)
"""

import json
import time
import hashlib
import hmac
import requests
from datetime import datetime
from pathlib import Path
import sys

# ========== 설정 ==========

CONFIG = {
    # 전략 파라미터
    'sma_period': 50,
    'rsi_period': 10,
    'rsi_overbought': 60,
    'bb_period': 20,
    'atr_period': 14,
    'adx_threshold': 25,
    'atr_sl_mult': 1.5,
    'atr_tp_mult': 4.0,
    
    # 리스크 관리
    'leverage': 5,
    'risk_per_trade': 0.02,
    'max_position_size': 5000,  # USDT
    
    # 거래 설정
    'symbol': 'BTCUSDT',
    'timeframe': '1d',
    'min_signal_strength': 2,   # 최소 2개 신호
    
    # 체크 간격 (초)
    'check_interval': 3600,     # 1시간
}

BASE_URL = "https://fapi.binance.com"

# ========== API 클라이언트 ==========

class BinanceFutures:
    def __init__(self, api_key, secret):
        self.api_key = api_key
        self.secret = secret
    
    def _sign(self, params):
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        signature = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        return query + f"&signature={signature}"
    
    def _request(self, method, endpoint, params=None, signed=False):
        url = f"{BASE_URL}{endpoint}"
        headers = {'X-MBX-APIKEY': self.api_key}
        
        if params is None:
            params = {}
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            query = self._sign(params)
            url = f"{url}?{query}"
            params = None
        
        try:
            if method == 'GET':
                resp = requests.get(url, params=params, headers=headers, timeout=10)
            else:
                resp = requests.post(url, params=params, headers=headers, timeout=10)
            return resp.json()
        except Exception as e:
            print(f"API 에러: {e}")
            return None
    
    def get_klines(self, symbol, interval, limit=100):
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        data = self._request('GET', '/fapi/v1/klines', params)
        if not data:
            return []
        
        return [{
            'time': k[0],
            'datetime': datetime.fromtimestamp(k[0]/1000).strftime('%Y-%m-%d %H:%M:%S'),
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
            'volume': float(k[5])
        } for k in data]
    
    def get_account(self):
        return self._request('GET', '/fapi/v2/account', signed=True)
    
    def get_position(self, symbol):
        account = self.get_account()
        if not account:
            return None
        for pos in account.get('positions', []):
            if pos['symbol'] == symbol:
                return {
                    'size': float(pos['positionAmt']),
                    'entry': float(pos['entryPrice']),
                    'pnl': float(pos['unrealizedProfit'])
                }
        return None
    
    def set_leverage(self, symbol, leverage):
        params = {'symbol': symbol, 'leverage': leverage}
        return self._request('POST', '/fapi/v1/leverage', params, signed=True)
    
    def place_order(self, symbol, side, quantity, order_type='MARKET', price=None, sl=None, tp=None):
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity
        }
        if price:
            params['price'] = price
        
        result = self._request('POST', '/fapi/v1/order', params, signed=True)
        
        # SL/TP 주문
        if result and sl:
            self.place_sl_order(symbol, 'BUY' if side == 'SELL' else 'SELL', quantity, sl)
        if result and tp:
            self.place_tp_order(symbol, 'BUY' if side == 'SELL' else 'SELL', quantity, tp)
        
        return result
    
    def place_sl_order(self, symbol, side, quantity, stop_price):
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'STOP_MARKET',
            'stopPrice': round(stop_price, 1),
            'quantity': quantity,
            'closePosition': 'true'
        }
        return self._request('POST', '/fapi/v1/order', params, signed=True)
    
    def place_tp_order(self, symbol, side, quantity, price):
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'TAKE_PROFIT_MARKET',
            'stopPrice': round(price, 1),
            'quantity': quantity,
            'closePosition': 'true'
        }
        return self._request('POST', '/fapi/v1/order', params, signed=True)


# ========== 지표 계산 ==========

def sma(data, period, idx):
    if idx < period:
        return None
    return sum(d['close'] for d in data[idx-period:idx]) / period

def atr(data, period, idx):
    if idx < period + 1:
        return None
    tr_list = []
    for i in range(idx - period, idx):
        h, l = data[i]['high'], data[i]['low']
        pc = data[i-1]['close'] if i > 0 else data[i]['open']
        tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(tr_list) / period

def rsi(data, period, idx):
    if idx < period + 1:
        return None
    gains, losses = [], []
    for i in range(idx - period, idx):
        change = data[i+1]['close'] - data[i]['close']
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def momentum(data, period, idx):
    if idx < period:
        return None
    prev = data[idx - period]['close']
    return (data[idx]['close'] - prev) / prev * 100 if prev else 0

def bbands(data, period, idx, std_mult=2):
    if idx < period:
        return None, None, None
    closes = [d['close'] for d in data[idx-period:idx]]
    mid = sum(closes) / period
    std = (sum((c - mid)**2 for c in closes) / period) ** 0.5
    return mid + std * std_mult, mid, mid - std * std_mult

def adx(data, period, idx):
    if idx < period * 2 + 1:
        return None
    plus_dm, minus_dm, tr_vals = [], [], []
    for i in range(idx - period * 2, idx):
        if i < 1:
            continue
        h, l = data[i]['high'], data[i]['low']
        ph, pl, pc = data[i-1]['high'], data[i-1]['low'], data[i-1]['close']
        up = h - ph
        down = pl - l
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
        tr_vals.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not tr_vals or sum(tr_vals[-period:]) == 0:
        return 0
    smooth_plus = sum(plus_dm[-period:])
    smooth_minus = sum(minus_dm[-period:])
    smooth_tr = sum(tr_vals[-period:])
    plus_di = 100 * smooth_plus / smooth_tr
    minus_di = 100 * smooth_minus / smooth_tr
    if plus_di + minus_di == 0:
        return 0
    return 100 * abs(plus_di - minus_di) / (plus_di + minus_di)


# ========== 신호 분석 ==========

def analyze_signal(data, config):
    """Combined Bear 전략 신호 분석"""
    idx = len(data) - 1
    price = data[idx]['close']
    
    # 지표 계산
    sma_val = sma(data, config['sma_period'], idx)
    rsi_val = rsi(data, config['rsi_period'], idx)
    atr_val = atr(data, config['atr_period'], idx)
    mom_val = momentum(data, 14, idx)
    adx_val = adx(data, 14, idx)
    upper, mid, lower = bbands(data, config['bb_period'], idx)
    
    if not all([sma_val, rsi_val, atr_val, mom_val, adx_val, mid]):
        return None
    
    result = {
        'datetime': data[idx]['datetime'],
        'price': price,
        'sma': sma_val,
        'rsi': rsi_val,
        'momentum': mom_val,
        'adx': adx_val,
        'atr': atr_val,
        'bb_mid': mid,
        'signal': 'NONE',
        'signal_strength': 0,
        'reasons': [],
        'sl': None,
        'tp': None
    }
    
    # 하락 추세 필터
    trend_filter = price < sma_val * 0.98
    if not trend_filter:
        result['reasons'].append('추세 필터 미통과 (가격 > SMA × 0.98)')
        return result
    
    # 신호 카운트
    signals = []
    
    # RSI 과매수
    if rsi_val > config['rsi_overbought']:
        signals.append(f'RSI 과매수 ({rsi_val:.1f} > {config["rsi_overbought"]})')
    
    # 음의 모멘텀
    if mom_val < -5:
        signals.append(f'강한 하락 모멘텀 ({mom_val:.1f}%)')
    
    # BB 상단 근처 (반등 후)
    if price > mid:
        signals.append(f'BB 중간선 위 (반등 후 숏 적기)')
    
    # ADX 강한 추세
    if adx_val > config['adx_threshold']:
        signals.append(f'강한 추세 (ADX {adx_val:.1f} > {config["adx_threshold"]})')
    
    result['signal_strength'] = len(signals)
    result['reasons'] = signals
    
    # 진입 조건
    if len(signals) >= config['min_signal_strength']:
        result['signal'] = 'SHORT'
        result['sl'] = price + atr_val * config['atr_sl_mult']
        result['tp'] = price - atr_val * config['atr_tp_mult']
    
    return result


def detect_market_regime(data, period=100):
    """시장 상태 감지 (BULL/BEAR/NEUTRAL)"""
    if len(data) < period:
        return 'UNKNOWN'
    
    sma_val = sum(d['close'] for d in data[-period:]) / period
    current = data[-1]['close']
    pct = (current - sma_val) / sma_val * 100
    
    if pct > 10:
        return 'BULL'
    elif pct < -10:
        return 'BEAR'
    else:
        return 'NEUTRAL'


# ========== 메인 ==========

def run_bot(test_mode=False, signal_only=False):
    """봇 실행"""
    # 설정 로드
    secrets_path = Path(__file__).parent / 'secrets.json'
    with open(secrets_path) as f:
        secrets = json.load(f)
    
    api_key = secrets['binance']['api_key']
    api_secret = secrets['binance']['secret']
    
    client = BinanceFutures(api_key, api_secret)
    
    print("=" * 60)
    print("🐻 하락장 전용 BTC 숏 트레이딩 봇")
    print("=" * 60)
    print(f"모드: {'테스트' if test_mode else '신호확인' if signal_only else '실거래'}")
    print(f"전략: Combined Bear (복합 신호)")
    print(f"레버리지: {CONFIG['leverage']}x")
    print(f"리스크/거래: {CONFIG['risk_per_trade']*100}%")
    print("=" * 60)
    
    # 레버리지 설정
    if not test_mode and not signal_only:
        client.set_leverage(CONFIG['symbol'], CONFIG['leverage'])
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 분석 중...")
            
            # 데이터 로드
            data = client.get_klines(CONFIG['symbol'], CONFIG['timeframe'], 200)
            if not data:
                print("❌ 데이터 로드 실패")
                time.sleep(60)
                continue
            
            # 시장 상태
            regime = detect_market_regime(data)
            print(f"시장 상태: {regime}")
            
            if regime != 'BEAR':
                print("⚠️ 하락장 아님 - 숏 전략 비활성")
                if signal_only:
                    break
                time.sleep(CONFIG['check_interval'])
                continue
            
            # 현재 포지션
            position = client.get_position(CONFIG['symbol'])
            has_position = position and abs(position['size']) > 0.001
            
            if has_position:
                side = 'SHORT' if position['size'] < 0 else 'LONG'
                print(f"현재 포지션: {side} {abs(position['size'])} BTC @ ${position['entry']:.2f}")
                print(f"미실현 손익: ${position['pnl']:.2f}")
            
            # 신호 분석
            signal = analyze_signal(data, CONFIG)
            
            if not signal:
                print("신호 분석 실패 (데이터 부족)")
            else:
                print(f"\n📊 신호 분석 결과:")
                print(f"  가격: ${signal['price']:.2f}")
                print(f"  SMA{CONFIG['sma_period']}: ${signal['sma']:.2f}")
                print(f"  RSI: {signal['rsi']:.1f}")
                print(f"  모멘텀: {signal['momentum']:.1f}%")
                print(f"  ADX: {signal['adx']:.1f}")
                print(f"  신호 강도: {signal['signal_strength']}/4")
                
                if signal['reasons']:
                    print(f"  조건:")
                    for r in signal['reasons']:
                        print(f"    ✓ {r}")
                
                if signal['signal'] == 'SHORT':
                    print(f"\n🚨 숏 신호 발생!")
                    print(f"  진입가: ${signal['price']:.2f}")
                    print(f"  손절가: ${signal['sl']:.2f} ({(signal['sl']/signal['price']-1)*100:.1f}%)")
                    print(f"  익절가: ${signal['tp']:.2f} ({(1-signal['tp']/signal['price'])*100:.1f}%)")
                    
                    # 주문 실행
                    if not test_mode and not signal_only and not has_position:
                        account = client.get_account()
                        if account:
                            balance = float(account['totalWalletBalance'])
                            risk_amount = balance * CONFIG['risk_per_trade']
                            sl_distance = abs(signal['sl'] - signal['price'])
                            qty = min(risk_amount / sl_distance, CONFIG['max_position_size'] / signal['price'])
                            qty = round(qty, 3)
                            
                            print(f"\n💰 주문 실행:")
                            print(f"  수량: {qty} BTC (${qty * signal['price']:.2f})")
                            
                            result = client.place_order(
                                CONFIG['symbol'], 'SELL', qty,
                                sl=signal['sl'], tp=signal['tp']
                            )
                            
                            if result and 'orderId' in result:
                                print(f"  ✅ 주문 성공: {result['orderId']}")
                            else:
                                print(f"  ❌ 주문 실패: {result}")
                else:
                    print(f"\n⏳ 대기 중 (신호 없음)")
            
            # 신호 확인 모드면 종료
            if signal_only:
                break
            
            # 대기
            print(f"\n다음 체크: {CONFIG['check_interval']}초 후")
            time.sleep(CONFIG['check_interval'])
            
        except KeyboardInterrupt:
            print("\n\n봇 종료")
            break
        except Exception as e:
            print(f"에러: {e}")
            time.sleep(60)


if __name__ == "__main__":
    test_mode = '--test' in sys.argv
    signal_only = '--signal' in sys.argv
    
    run_bot(test_mode=test_mode, signal_only=signal_only)
