---
name: trading-system
description: BTC 선물 트레이딩 시스템. TradingView 차트 분석 + Binance API 주문 + 투자일지 관리
metadata: {"clawdbot":{"emoji":"📊","always":false}}
---

# Trading System 📊

BTC 선물 트레이딩 자동화 시스템

## 워크플로우

```
1. 차트 분석 (TradingView on Binance)
   ↓
2. 진입 판단 (STRATEGY.md 기준)
   ↓
3. 주문 실행 (Binance API)
   ↓
4. 포지션 관리
   ↓
5. 청산
   ↓
6. 투자일지 작성 (로컬 + Notion)
   ↓
7. 전략 개선
```

## 핵심 파일

| 파일 | 위치 | 용도 |
|------|------|------|
| 전략 문서 | `/Users/yunkyeongho/.openclaw/workspace/trading/STRATEGY.md` | 투자 기준 및 전략 |
| 투자일지 | `/Users/yunkyeongho/.openclaw/workspace/trading/journal/` | 매매 기록 |
| 포지션 상태 | `/Users/yunkyeongho/.openclaw/workspace/trading/position.json` | 현재 포지션 |

## 1. 차트 분석 (쉽알남 방식)

### 참고 문서
**반드시 STRATEGY.md 숙지 후 분석 시작**
→ `/Users/yunkyeongho/.openclaw/workspace/trading/STRATEGY.md`

### TradingView 세팅
```
지표: 거래량(차트 분리), 20 SMA, 20 EMA, 볼린저밴드(기본), RSI(MA끄기)
도구: 오더블록 박스(빨강/녹색), FVG 박스, 추세선, 채널
```

### 타임프레임 다중 분석 (핵심!)
```
1단계: 월봉/주봉/일봉 → 큰 추세 파악, 주요 오더블록/FVG 체크
2단계: 4시간/1시간봉 → 중간 규모 추세, 지지저항 구간 작도
3단계: 15분/5분/1분봉 → 실제 진입 타점 탐색
```

### 겹치는 구간 찾기 (가장 강력)
- 월봉 오더블록 + 주봉 FVG → 매우 강력
- 1시간 오더블록 + 15분 오더블록 → 강력
- 여러 타임프레임에서 겹칠수록 신뢰도 ↑

### 체크할 것
- [ ] 오더블록 구간 (상승장악형/하락장악형)
- [ ] FVG 구간 (장대봉 양옆 꼬리 포함 안 겹치는 구간)
- [ ] 추세선 (2개 고점/저점 연결)
- [ ] 채널 (상승채널은 하락으로, 하락채널은 상승으로 깨지는 경향)
- [ ] 패턴 (하락웨지, 쌍바닥, 삼각수렴 등)

## 2. 주문 실행 (Binance Futures API)

### 환경변수
```bash
BINANCE_API_KEY
BINANCE_SECRET
```

### 잔고 확인
```bash
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
QUERY="timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s "https://fapi.binance.com/fapi/v2/balance?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}" | jq '[.[] | select(.balance != "0")]'
```

### 현재 포지션 확인
```bash
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
QUERY="timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s "https://fapi.binance.com/fapi/v2/positionRisk?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}" | jq '.[] | select(.symbol=="BTCUSDT")'
```

### 레버리지 설정
```bash
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
LEVERAGE=10
QUERY="symbol=BTCUSDT&leverage=${LEVERAGE}&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s -X POST "https://fapi.binance.com/fapi/v1/leverage?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
```

### 시장가 롱 진입
```bash
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
QUANTITY=0.001  # BTC 수량
QUERY="symbol=BTCUSDT&side=BUY&type=MARKET&quantity=${QUANTITY}&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s -X POST "https://fapi.binance.com/fapi/v1/order?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
```

### 시장가 숏 진입
```bash
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
QUANTITY=0.001
QUERY="symbol=BTCUSDT&side=SELL&type=MARKET&quantity=${QUANTITY}&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s -X POST "https://fapi.binance.com/fapi/v1/order?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
```

### 손절/익절 주문 (롱 포지션)
```bash
# 손절 (STOP_MARKET)
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
STOP_PRICE=95000
QUERY="symbol=BTCUSDT&side=SELL&type=STOP_MARKET&stopPrice=${STOP_PRICE}&closePosition=true&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s -X POST "https://fapi.binance.com/fapi/v1/order?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"

# 익절 (TAKE_PROFIT_MARKET)
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
TP_PRICE=100000
QUERY="symbol=BTCUSDT&side=SELL&type=TAKE_PROFIT_MARKET&stopPrice=${TP_PRICE}&closePosition=true&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s -X POST "https://fapi.binance.com/fapi/v1/order?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
```

### 포지션 종료 (시장가)
```bash
# 롱 청산
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
QUERY="symbol=BTCUSDT&side=SELL&type=MARKET&quantity=${QUANTITY}&reduceOnly=true&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s -X POST "https://fapi.binance.com/fapi/v1/order?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
```

### 모든 주문 취소
```bash
TIMESTAMP=$(python3 -c "import time; print(int(time.time() * 1000))")
QUERY="symbol=BTCUSDT&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$QUERY" | openssl dgst -sha256 -hmac "$BINANCE_SECRET" | cut -d' ' -f2)

curl -s -X DELETE "https://fapi.binance.com/fapi/v1/allOpenOrders?${QUERY}&signature=${SIGNATURE}" \
  -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
```

## 3. 투자일지 작성

### 로컬 저장
파일: `/Users/yunkyeongho/.openclaw/workspace/trading/journal/YYYY-MM-DD_HHmm.md`

### 일지 템플릿
```markdown
# 투자일지 - {날짜} {시간}

## 📊 거래 정보
- **종목**: BTCUSDT
- **방향**: 롱/숏
- **진입가**: $XX,XXX
- **청산가**: $XX,XXX
- **수량**: X.XXX BTC
- **레버리지**: Xx
- **손절가**: $XX,XXX
- **익절가**: $XX,XXX

## 📈 결과
- **손익**: +$XX.XX (+X.X%)
- **보유시간**: Xh Xm

## 🎯 진입 근거
1. (근거 1)
2. (근거 2)
3. (근거 3)

## 📉 청산 근거
- (청산 이유)

## 🔍 차트 분석
- (진입 시점 차트 상황)
- (스크린샷 경로)

## 💡 회고
### 잘한 점
- 

### 개선할 점
- 

### 다음에 적용할 것
- 

## 🏷️ 태그
#BTC #롱/숏 #승리/패배
```

### Notion 동기화
notion skill 사용하여 투자일지 페이지에 동일 내용 작성

## 4. 전략 개선

매 거래 후:
1. 투자일지 회고 분석
2. 패턴 파악 (어떤 조건에서 성공/실패?)
3. STRATEGY.md 업데이트
4. 개선 이력 기록

주간 리뷰:
1. 주간 수익률 계산
2. 승률/손익비 분석
3. 전략 효과성 평가
4. 다음 주 개선 사항 도출

## 리스크 관리 (쉽알남 핵심!)

### 진입 물량 계산 공식
```
진입 물량 = 감수할 손실금액 ÷ 손절까지의 거리
```

**예시**: 
- 최대 손실 $100, 손절까지 $600 → 0.16 BTC
- 최대 손실 $1000, 손절까지 $2 → 500 SOL

### 이중 방어막
1. **1차**: 하루 총 손실 = 시드의 1% → 달성 시 매매 중단
2. **2차**: 물량 계산에 손절가 필수 → 손절 없이 진입 불가

### 목표
- 하루 목표: $1,500~$2,000
- 목표 달성 시 과감히 차트 끄기

## 금기사항

1. **풀 레버리지, 풀 시드 진입 금지**
2. **손절가 없이 진입 금지**
3. **손실 한 번에 메꾸려 하지 말 것**
4. **평소 하던 대로 하기**
5. **자리 안 주면 매매 안 하면 그만**
6. **평단보다 위에서 추매 금지**

## 진입/익절 체크리스트

### 진입 전
- [ ] 큰 타임프레임 추세 확인
- [ ] 오더블록/FVG 구간 체크
- [ ] 여러 타임프레임에서 겹치는 구간 확인
- [ ] 감수할 손실금액 결정
- [ ] 손절가까지 거리 계산
- [ ] **진입 물량 계산** (핵심!)
- [ ] 분할 매수 계획 수립

### 익절 타이밍
- 거래량이 터질 때 → 과감히 익절
- 저항 오더블록 도달 → 분할/전량 익절
- 하락 패턴 발생 (하락장악형 등) → 전량 익절
- 직전 고점/저점 유동성 먹을 때

### 손절
- 스톱은 올리면 올렸지 내리지 않는다
- 오더블록 저점/고점 기준
- 패턴 무효화 지점
