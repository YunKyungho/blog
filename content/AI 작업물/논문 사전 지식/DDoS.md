---
title: "DDoS"
aliases: [Distributed Denial of Service, 분산 서비스 거부 공격, DDoS 공격]
tags: [보안, 사이버공격, 네트워크보안]
---

## 정의

DDoS(Distributed Denial of Service, 분산 서비스 거부)는 다수의 시스템에서 동시에 대량의 트래픽을 발생시켜 대상 서버나 네트워크의 정상적인 서비스를 방해하는 사이버 공격이다.

## 상세 설명

### 공격 원리

1. **봇넷 구성**: 악성코드에 감염된 다수의 컴퓨터(좀비)를 확보
2. **명령 전달**: C&C(Command & Control) 서버를 통해 공격 지시
3. **동시 공격**: 수천~수백만 대의 봇이 동시에 대상에 트래픽 전송
4. **서비스 장애**: 대상 시스템의 리소스 고갈로 정상 사용자 접근 불가

### DDoS 공격 유형

**볼륨 기반 공격:**
- UDP 플러드
- ICMP 플러드
- 증폭 공격 (DNS, NTP 등)

**프로토콜 공격:**
- SYN 플러드
- Ping of Death
- Smurf 공격

**애플리케이션 계층 공격:**
- HTTP 플러드
- Slowloris
- DNS 쿼리 플러드

### 방어 기법

- **트래픽 필터링**: 악성 트래픽 차단
- **레이트 리미팅**: 요청 속도 제한
- **CDN 활용**: 트래픽 분산
- **스크러빙 센터**: 전용 DDoS 완화 서비스
- **AI 기반 탐지**: 머신러닝으로 이상 트래픽 패턴 식별

### 피해 규모

- 서비스 중단에 따른 매출 손실
- 평판 손상
- 복구 비용
- 랜섬 DDoS의 경우 금전 요구

## 관련 개념

- [[이상 탐지]]
- [[딥러닝]]
- [[침입 탐지 시스템]]

## 참고

- Alexandru Apostu et al., "Detecting and Mitigating DDoS Attacks with AI: A Survey" (arXiv, 2025)
