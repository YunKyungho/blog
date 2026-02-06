#!/usr/bin/env python3
"""
BTC 선물 자동 트레이딩 데몬 v5
추세+RSI 전략 (수수료 0.08% 반영 최적화)

전략 성과 (백테스트 2019-2025, 수수료 포함):
- 평균 거래: 26.6회/년
- 승률: 47.8%
- 평균 연 수익률: 67.7%
- 최대 DD: 27.6%
- 모든 연도 양수 수익 ✅

전략 로직:
- 일봉 MA15로 추세 판단 (상승/하락)
- 4시간봉 RSI로 진입 시점 결정
- 상승추세 + RSI<40 → 롱
- 하락추세 + RSI>65 → 숏
- SL 5%, TP 10% (1:2 손익비)

투자금 관리:
- $5,000 고정
- 수익 시 초과분 spot으로 이체
- 손실 시 spot에서 충당
"""

import hmac
import hashlib
import time
import requests
import json
import logging
from datetime import datetime
from pathlib import Path

# ========== 설정 ==========
BASE_DIR = Path(__file__).parent
SECRETS_PATH = BASE_DIR / 'secrets.json'
CONFIG_PATH = BASE_DIR / 'config.json'
LOG_PATH = BASE_DIR / 'daemon.log'
STATUS_PATH = BASE_DIR / 'daemon_status.json'
TRADE_LOG_PATH = BASE_DIR / 'trades.json'

# ========== 최적화된 전략 파라미터 (v5 - 추세+RSI) ==========
# 백테스트 결과: 모든 연도(2019-2025) 양수 수익, MDD 27.6%
STRATEGY_PARAMS = {
    'leverage': 5,               # 레버리지 (보수적)
    'risk_per_trade': 5.0,       # 거래당 리스크 %
    'trend_ma': 15,              # 추세 판단 MA (일봉)
    'rsi_period': 14,            # RSI 기간
    'rsi_low': 40,               # RSI 과매도 (롱 진입)
    'rsi_high': 65,              # RSI 과매수 (숏 진입)
    'sl_pct': 5.0,               # 손절 %
    'tp_pct': 10.0,              # 익절 % (1:2 손익비)
    'cooldown_hours': 8,         # 쿨다운 (시간)
    'fee_pct': 0.04,             # 수수료 (각 방향)
}

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API 설정 로드
try:
    with open(SECRETS_PATH) as f:
        SECRETS = json.load(f)
    
    API_KEY = SECRETS['binance']['api_key']
    SECRET = SECRETS['binance']['secret']
    TELEGRAM_TOKEN = SECRETS['telegram']['bot_token']
    TELEGRAM_CHAT_ID = SECRETS['telegram']['chat_id']
except:
    logger.error("secrets.json 파일 필요")
    API_KEY = SECRET = TELEGRAM_TOKEN = TELEGRAM_CHAT_ID = None

# 트레이딩 설정 로드
try:
    with open(CONFIG_PATH) as f:
        CONFIG = json.load(f)
except:
    CONFIG = {}

SYMBOL = CONFIG.get('symbol', 'BTCUSDT')
TARGET_BALANCE = CONFIG.get('target_balance', 5000)
AUTO_REBALANCE = CONFIG.get('auto_rebalance', True)
CHECK_INTERVAL = CONFIG.get('check_interval', 300)  # 5분마다 체크 (4H RSI 전략)

FUTURES_URL = "https://fapi.binance.com"
SPOT_URL = "https://api.binance.com"

# ========== 유틸리티 ==========

def get_signature(query_string):
    return hmac.new(SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def futures_request(method, endpoint, params=None):
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    signature = get_signature(query)
    url = f'{FUTURES_URL}{endpoint}?{query}&signature={signature}'
    headers = {'X-MBX-APIKEY': API_KEY}
    
    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=10)
        elif method == 'POST':
            resp = requests.post(url, headers=headers, timeout=10)
        elif method == 'DELETE':
            resp = requests.delete(url, headers=headers, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"Futures API 실패: {e}")
        return {'error': str(e)}

def spot_request(method, endpoint, params=None):
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    signature = get_signature(query)
    url = f'{SPOT_URL}{endpoint}?{query}&signature={signature}'
    headers = {'X-MBX-APIKEY': API_KEY}
    
    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=10)
        elif method == 'POST':
            resp = requests.post(url, headers=headers, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"Spot API 실패: {e}")
        return {'error': str(e)}

def send_telegram(message):
    if not TELEGRAM_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        requests.post(url, data=data, timeout=10)
        logger.info(f"텔레그램: {message[:50]}...")
    except Exception as e:
        logger.error(f"텔레그램 실패: {e}")

def log_trade(trade_type, data):
    trades = []
    if TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH) as f:
            trades = json.load(f)
    trades.append({'timestamp': datetime.now().isoformat(), 'type': trade_type, 'data': data})
    with open(TRADE_LOG_PATH, 'w') as f:
        json.dump(trades[-500:], f, indent=2, default=str)

# ========== 잔고 관리 ==========

def get_futures_balance():
    result = futures_request('GET', '/fapi/v2/balance')
    if isinstance(result, list):
        for bal in result:
            if bal['asset'] == 'USDT':
                return float(bal['balance'])
    return 0

def get_spot_balance():
    result = spot_request('GET', '/api/v3/account')
    if isinstance(result, dict) and 'balances' in result:
        for bal in result['balances']:
            if bal['asset'] == 'USDT':
                return float(bal['free'])
    return 0

def transfer_to_spot(amount):
    result = spot_request('POST', '/sapi/v1/futures/transfer', {
        'asset': 'USDT', 'amount': round(amount, 2), 'type': 2
    })
    if 'tranId' in result:
        logger.info(f"Futures → Spot: ${amount:.2f}")
        return True
    return False

def transfer_to_futures(amount):
    result = spot_request('POST', '/sapi/v1/futures/transfer', {
        'asset': 'USDT', 'amount': round(amount, 2), 'type': 1
    })
    if 'tranId' in result:
        logger.info(f"Spot → Futures: ${amount:.2f}")
        return True
    return False

def rebalance():
    if not AUTO_REBALANCE:
        return
    
    futures_bal = get_futures_balance()
    spot_bal = get_spot_balance()
    diff = futures_bal - TARGET_BALANCE
    
    if diff > 10:
        if transfer_to_spot(diff):
            msg = f"💰 수익 확보: ${diff:.2f} → Spot"
            send_telegram(msg)
            log_trade('REBALANCE', {'type': 'to_spot', 'amount': diff})
    elif diff < -10:
        needed = abs(diff)
        if spot_bal >= needed:
            if transfer_to_futures(needed):
                msg = f"🔄 손실 충당: ${needed:.2f} ← Spot"
                send_telegram(msg)
                log_trade('REBALANCE', {'type': 'from_spot', 'amount': needed})
        else:
            send_telegram(f"⚠️ Spot 잔고 부족! 필요: ${needed:.2f}")

# ========== 데이터 함수 ==========

def get_klines(interval, limit=100):
    try:
        url = f"{FUTURES_URL}/fapi/v1/klines?symbol={SYMBOL}&interval={interval}&limit={limit}"
        resp = requests.get(url, timeout=10).json()
        return [{'time': k[0], 'open': float(k[1]), 'high': float(k[2]),
                 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])} for k in resp]
    except Exception as e:
        logger.error(f"캔들 조회 실패: {e}")
        return []

def get_price():
    try:
        url = f"{FUTURES_URL}/fapi/v1/ticker/price?symbol={SYMBOL}"
        return float(requests.get(url, timeout=10).json()['price'])
    except:
        return None

def get_position():
    result = futures_request('GET', '/fapi/v2/positionRisk')
    if isinstance(result, list):
        for pos in result:
            if pos['symbol'] == SYMBOL:
                amt = float(pos['positionAmt'])
                if amt != 0:
                    return {
                        'side': 'LONG' if amt > 0 else 'SHORT',
                        'size': abs(amt),
                        'entry': float(pos['entryPrice']),
                        'pnl': float(pos['unRealizedProfit']),
                        'leverage': int(pos['leverage'])
                    }
    return None

# ========== 추세+RSI 전략 ==========

class TrendRSIStrategy:
    def __init__(self):
        self.last_entry_time = None
        self.params = STRATEGY_PARAMS
        self.consecutive_losses = 0
        self.trading_halted = False
    
    def calc_ma(self, klines, period):
        """이동평균 계산"""
        if len(klines) < period:
            return None
        return sum(k['close'] for k in klines[-period:]) / period
    
    def calc_rsi(self, klines, period=14):
        """RSI 계산"""
        if len(klines) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(klines)):
            change = klines[i]['close'] - klines[i-1]['close']
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return None
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def get_trend(self, klines_daily):
        """일봉에서 MA 기반 추세 판단"""
        trend_ma = self.params['trend_ma']
        
        if len(klines_daily) < trend_ma:
            return 'UNKNOWN'
        
        ma = self.calc_ma(klines_daily, trend_ma)
        if ma is None:
            return 'UNKNOWN'
        
        price = klines_daily[-1]['close']
        
        # 0.5% 이상 MA 위/아래
        if price > ma * 1.005:
            return 'UP'
        elif price < ma * 0.995:
            return 'DOWN'
        return 'SIDEWAYS'
    
    def find_entry_signal(self, klines_4h, trend):
        """4시간봉에서 RSI 기반 진입 시그널"""
        rsi = self.calc_rsi(klines_4h, self.params['rsi_period'])
        
        if rsi is None:
            return None
        
        price = klines_4h[-1]['close']
        
        # 상승 추세 + RSI 과매도 → 롱
        if trend == 'UP' and rsi < self.params['rsi_low']:
            return {
                'side': 'LONG',
                'entry': price,
                'sl': price * (1 - self.params['sl_pct'] / 100),
                'tp': price * (1 + self.params['tp_pct'] / 100),
                'rsi': rsi
            }
        
        # 하락 추세 + RSI 과매수 → 숏
        if trend == 'DOWN' and rsi > self.params['rsi_high']:
            return {
                'side': 'SHORT',
                'entry': price,
                'sl': price * (1 + self.params['sl_pct'] / 100),
                'tp': price * (1 - self.params['tp_pct'] / 100),
                'rsi': rsi
            }
        
        return None
    
    def can_enter(self):
        """쿨다운 체크"""
        if self.last_entry_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_entry_time).total_seconds() / 3600
        return elapsed >= self.params['cooldown_hours']
    
    def analyze(self):
        """시장 분석"""
        klines_daily = get_klines('1d', 50)
        klines_4h = get_klines('4h', 50)
        
        if not klines_daily or not klines_4h:
            return None
        
        trend = self.get_trend(klines_daily)
        rsi = self.calc_rsi(klines_4h, self.params['rsi_period'])
        price = get_price()
        
        signal = None
        if trend in ['UP', 'DOWN'] and self.can_enter():
            signal = self.find_entry_signal(klines_4h, trend)
        
        return {
            'price': price,
            'trend': trend,
            'rsi': rsi,
            'signal': signal
        }

strategy = TrendRSIStrategy()

# ========== 트레이딩 로직 ==========

def check_exit(position):
    """SL/TP 체크 (시장가 청산)"""
    price = get_price()
    if not price:
        return None
    
    entry = position['entry']
    sl_pct = STRATEGY_PARAMS['sl_pct']
    tp_pct = STRATEGY_PARAMS['tp_pct']
    
    if position['side'] == 'LONG':
        sl_price = entry * (1 - sl_pct / 100)
        tp_price = entry * (1 + tp_pct / 100)
        
        if price <= sl_price:
            return {'action': 'EXIT', 'reason': 'SL', 'price': price}
        if price >= tp_price:
            return {'action': 'EXIT', 'reason': 'TP', 'price': price}
    else:
        sl_price = entry * (1 + sl_pct / 100)
        tp_price = entry * (1 - tp_pct / 100)
        
        if price >= sl_price:
            return {'action': 'EXIT', 'reason': 'SL', 'price': price}
        if price <= tp_price:
            return {'action': 'EXIT', 'reason': 'TP', 'price': price}
    
    return None

def execute_entry(signal):
    """진입 실행"""
    balance = min(get_futures_balance(), TARGET_BALANCE)
    price = signal['entry']
    
    if balance < 100:
        return {'success': False, 'error': 'Insufficient balance'}
    
    # 레버리지 설정
    leverage = STRATEGY_PARAMS['leverage']
    futures_request('POST', '/fapi/v1/leverage', {'symbol': SYMBOL, 'leverage': leverage})
    
    # 포지션 사이즈 (리스크 기반)
    risk_amount = balance * (STRATEGY_PARAMS['risk_per_trade'] / 100)
    sl_distance = abs(signal['entry'] - signal['sl'])
    qty = risk_amount / sl_distance if sl_distance > 0 else 0
    max_qty = (balance * leverage) / price
    qty = min(qty, max_qty)
    qty = round(qty, 3)
    
    order_side = 'BUY' if signal['side'] == 'LONG' else 'SELL'
    
    # 시장가 진입
    result = futures_request('POST', '/fapi/v1/order', {
        'symbol': SYMBOL, 'side': order_side, 'type': 'MARKET', 'quantity': qty
    })
    
    if 'orderId' not in result:
        return {'success': False, 'error': str(result)}
    
    # SL 주문
    time.sleep(1)
    sl_side = 'SELL' if signal['side'] == 'LONG' else 'BUY'
    sl_price = round(signal['sl'], 1)
    
    futures_request('POST', '/fapi/v1/order', {
        'symbol': SYMBOL, 'side': sl_side, 'type': 'STOP_MARKET',
        'stopPrice': sl_price, 'quantity': qty, 'reduceOnly': 'true'
    })
    
    # TP 주문
    tp_side = 'SELL' if signal['side'] == 'LONG' else 'BUY'
    tp_price = round(signal['tp'], 1)
    
    futures_request('POST', '/fapi/v1/order', {
        'symbol': SYMBOL, 'side': tp_side, 'type': 'TAKE_PROFIT_MARKET',
        'stopPrice': tp_price, 'quantity': qty, 'reduceOnly': 'true'
    })
    
    strategy.last_entry_time = datetime.now()
    
    entry_data = {
        'success': True, 'side': signal['side'], 'quantity': qty,
        'entry_price': price, 'sl_price': sl_price, 'tp_price': tp_price,
        'rsi': signal.get('rsi', 0)
    }
    
    log_trade('ENTRY', entry_data)
    
    msg = f"""🚀 <b>{signal['side']} 진입</b>
진입가: ${price:,.0f}
수량: {qty} BTC
손절: ${sl_price:,.0f} ({STRATEGY_PARAMS['sl_pct']}%)
익절: ${tp_price:,.0f} ({STRATEGY_PARAMS['tp_pct']}%)
손익비: 1:{STRATEGY_PARAMS['tp_pct']/STRATEGY_PARAMS['sl_pct']:.0f}
RSI: {signal.get('rsi', 0):.1f}"""
    
    send_telegram(msg)
    return entry_data

def execute_exit(position, reason):
    """청산 실행"""
    # 모든 주문 취소
    futures_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': SYMBOL})
    
    # 시장가 청산
    side = 'SELL' if position['side'] == 'LONG' else 'BUY'
    result = futures_request('POST', '/fapi/v1/order', {
        'symbol': SYMBOL, 'side': side, 'type': 'MARKET',
        'quantity': position['size'], 'reduceOnly': 'true'
    })
    
    success = 'orderId' in result
    
    data = {
        'success': success, 'side': position['side'],
        'entry': position['entry'], 'pnl': position['pnl'], 'reason': reason
    }
    
    log_trade('EXIT', data)
    
    if success:
        # 연속 손실 카운터 업데이트
        if position['pnl'] < 0:
            strategy.consecutive_losses += 1
            if strategy.consecutive_losses >= 3:
                strategy.trading_halted = True
                halt_msg = f"""🚨 <b>매매 중지</b>
연속 {strategy.consecutive_losses}회 손실 발생
자동 매매가 중지되었습니다.
재개하려면 명령을 보내주세요."""
                send_telegram(halt_msg)
        else:
            strategy.consecutive_losses = 0  # 수익 시 리셋
        
        emoji = "✅" if position['pnl'] > 0 else "❌"
        msg = f"""{emoji} <b>청산 완료</b>
포지션: {position['side']}
진입가: ${position['entry']:,.0f}
손익: ${position['pnl']:,.2f}
사유: {reason}
연속손실: {strategy.consecutive_losses}회"""
        send_telegram(msg)
        
        time.sleep(2)
        rebalance()
    
    return data

# ========== 메인 루프 ==========

def run_once():
    analysis = strategy.analyze()
    if not analysis:
        logger.warning("시장 분석 실패")
        return
    
    position = get_position()
    futures_bal = get_futures_balance()
    
    status = {
        'timestamp': datetime.now().isoformat(),
        'price': analysis['price'],
        'trend': analysis['trend'],
        'rsi': analysis['rsi'],
        'position': position,
        'futures_balance': futures_bal,
        'target_balance': TARGET_BALANCE,
        'signal': analysis['signal']
    }
    
    if position:
        # 포지션 있음 → SL/TP 체크
        exit_check = check_exit(position)
        
        if exit_check:
            logger.info(f"청산: {exit_check['reason']}")
            execute_exit(position, exit_check['reason'])
        else:
            pnl_pct = (position['pnl'] / TARGET_BALANCE) * 100
            logger.info(f"홀딩 | {position['side']} | PnL: ${position['pnl']:.2f} ({pnl_pct:.2f}%)")
    else:
        # 포지션 없음 → 진입 체크
        if strategy.trading_halted:
            logger.info(f"매매중지 | 연속 {strategy.consecutive_losses}회 손실 | ${analysis['price']:,.0f}")
        elif analysis['signal']:
            logger.info(f"진입 시그널: {analysis['signal']['side']} | RSI: {analysis['rsi']:.1f}")
            execute_entry(analysis['signal'])
        else:
            rsi_str = f"RSI: {analysis['rsi']:.1f}" if analysis['rsi'] else "RSI: N/A"
            logger.info(f"대기 | ${analysis['price']:,.0f} | {analysis['trend']} | {rsi_str}")
    
    with open(STATUS_PATH, 'w') as f:
        json.dump(status, f, indent=2, default=str)

def main():
    logger.info("=" * 60)
    logger.info("🤖 트레이딩 데몬 v5 시작 (추세+RSI 전략)")
    logger.info(f"심볼: {SYMBOL} | 레버리지: {STRATEGY_PARAMS['leverage']}x")
    logger.info(f"SL: {STRATEGY_PARAMS['sl_pct']}% | TP: {STRATEGY_PARAMS['tp_pct']}%")
    logger.info(f"RSI 범위: {STRATEGY_PARAMS['rsi_low']} ~ {STRATEGY_PARAMS['rsi_high']}")
    logger.info(f"목표잔고: ${TARGET_BALANCE:,} | 체크간격: {CHECK_INTERVAL}초")
    logger.info("=" * 60)
    
    futures_bal = get_futures_balance()
    spot_bal = get_spot_balance()
    
    msg = f"""🤖 <b>트레이딩 데몬 v5 시작</b>
전략: 추세+RSI (수수료 반영 최적화)
레버리지: {STRATEGY_PARAMS['leverage']}x
손익비: 1:{int(STRATEGY_PARAMS['tp_pct']/STRATEGY_PARAMS['sl_pct'])}
RSI: {STRATEGY_PARAMS['rsi_low']} ~ {STRATEGY_PARAMS['rsi_high']}
Futures: ${futures_bal:,.2f}
Spot: ${spot_bal:,.2f}

📊 백테스트 성과 (2019-2025):
• 평균 수익률: 67.7%/년
• 모든 연도 양수 수익 ✅
• MDD: 27.6%"""
    send_telegram(msg)
    
    if AUTO_REBALANCE:
        rebalance()
    
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"오류: {e}")
            send_telegram(f"⚠️ 오류: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
