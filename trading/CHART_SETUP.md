# 차트 설정 자동화 가이드

## 개요

바이낸스 선물 차트(TradingView 임베드)와 TradingView 직접 설정 방법 정리.
하루(AI)가 차트 분석 시 참고하는 설정 기준.

---

## 🔧 바이낸스 선물 차트 설정

### 접근 방법
```
URL: https://www.binance.com/en/futures/BTCUSDT
차트 영역: TradingView iframe 내부
```

### 타임프레임 전환
바이낸스 차트 상단에서 직접 선택 가능:
- `Time` | `1s` | `15m` | `1H` | `4H` | `1D` | `1W`

**자동화 ref:**
- 15분: `e435`
- 1시간: `e436`
- 4시간: `e437`
- 1일: `e438`
- 1주: `e439`

### 지표 추가 (TradingView iframe 내부)
1. 차트 클릭하여 포커스
2. `/` 키 → 지표 검색창 열림
3. 지표명 입력 후 선택

**필요한 지표:**
| 지표 | 검색어 | 설정 |
|------|--------|------|
| 거래량 | Volume | 차트 분리 (하단 패널) |
| 20 SMA | MA | Length: 20 |
| 20 EMA | EMA | Length: 20 |
| 볼린저밴드 | BB | 기본값 (20, 2) |
| RSI | RSI | Length: 14, MA 끄기 |

### 도구 위치 (좌측 툴바)
| 도구 | 버튼명 | ref |
|------|--------|-----|
| 추세선 | Trend Line | f3e28 |
| 추세선 도구들 | Trend line tools | f3e34 |
| 피보나치 | Fib Retracement | f3e42 |
| 패턴 도구 | XABCD Pattern | f3e59 |
| 롱 포지션 | Long Position | f3e73 |
| 도형 (박스) | Geometric shapes | f3e92 |

---

## 🎨 차트 설정 (쉽알남 스타일)

### 배경
- 색상: 솔리드, F1F1F1 (밝은 회색)
- 그리드: 끄기

### 캔들
- 바디: 기본 (녹색/빨간색)
- 경계선: 검정색
- 윅: 검정색

### 십자선
- 색상: 검정
- 불투명도: 15%
- 두께: 얇게
- 스타일: 점선

### 오더블록 박스 템플릿
```
지지 오더블록 (녹색):
- 배경: 녹색, 불투명도 35%
- 테두리: 검정색, 얇게
- 텍스트: "OB" 또는 "오더블록"
- 확장: 오른쪽으로 연장

저항 오더블록 (빨간색):
- 배경: 빨간색, 불투명도 35%
- 테두리: 검정색, 얇게
- 텍스트: "OB" 또는 "오더블록"
- 확장: 오른쪽으로 연장
```

### FVG 박스 템플릿
```
지지 FVG (파란색):
- 배경: 파란색, 불투명도 20%
- 테두리: 파란색, 얇게
- 확장: 오른쪽으로 연장

저항 FVG (주황색):
- 배경: 주황색, 불투명도 20%
- 테두리: 주황색, 얇게
- 확장: 오른쪽으로 연장
```

---

## 🤖 하루(AI) 자동화 절차

### 1. 차트 접근
```javascript
browser.open("https://www.binance.com/en/futures/BTCUSDT")
// 5초 대기 (로딩)
```

### 2. 타임프레임 전환
```javascript
// 4시간봉으로 전환
browser.act({kind: "click", ref: "e437"})
```

### 3. TradingView 포커스 & 지표 추가
```javascript
// iframe 내부 클릭
browser.act({kind: "click", ref: "e490"})
// 지표 메뉴 열기
browser.act({kind: "press", key: "/"})
// 지표명 입력
browser.act({kind: "type", text: "Volume"})
// Enter로 선택
browser.act({kind: "press", key: "Enter"})
```

### 4. 스크린샷 캡처
```javascript
browser.screenshot()
```

---

## 📝 분석 워크플로우

### Step 1: 큰 추세 확인 (1D, 1W)
1. 1D 차트로 전환
2. 주요 오더블록/FVG 확인
3. 추세 방향 판단

### Step 2: 중간 추세 확인 (4H, 1H)
1. 4H 차트로 전환
2. 지지/저항 구간 작도
3. 패턴 확인

### Step 3: 진입 타점 탐색 (15m, 5m)
1. 15m 차트로 전환
2. 오더블록 + FVG 겹치는 구간 확인
3. 진입 조건 체크

### Step 4: 스크린샷 & 분석 기록
1. 각 타임프레임별 스크린샷
2. 분석 내용 journal에 기록

---

## ⚠️ 제한사항

### 바이낸스 내장 TradingView
- iframe으로 임베드되어 직접 제어 제한적
- 설정 저장이 브라우저 세션에 의존
- 로그인 필요 시 API 설정 불가

### 권장 대안
1. **TradingView 직접 사용**: https://www.tradingview.com/chart/
   - 설정 저장 가능 (계정 연동)
   - 더 많은 기능
   
2. **바이낸스 API + 로컬 차트**:
   - Python matplotlib/plotly로 캔들 차트 생성
   - 완전한 자동화 가능

---

## 🔗 참고

- 전략 문서: `./STRATEGY.md`
- 투자일지 폴더: `./journal/`
- 포지션 상태: `./position.json`

---

*마지막 업데이트: 2026-02-02*
