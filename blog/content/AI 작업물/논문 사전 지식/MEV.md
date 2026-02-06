---
title: "MEV"
aliases: [Maximal Extractable Value, Miner Extractable Value, 최대 추출 가능 가치]
tags: [블록체인, 보안, 탈중앙화 금융]
---

## 정의

MEV(Maximal Extractable Value)는 블록 생산자(채굴자 또는 검증자)가 블록 내 트랜잭션의 순서를 조작하거나, 트랜잭션을 추가/제외함으로써 얻을 수 있는 최대 이익을 말한다.

## 상세 설명

### MEV 추출 방식

1. **프론트러닝(Front-running)**: 수익성 있는 트랜잭션을 먼저 실행
2. **백러닝(Back-running)**: 특정 트랜잭션 직후에 실행하여 이익 획득
3. **샌드위치 공격(Sandwich Attack)**: 타겟 트랜잭션 전후로 자신의 거래 삽입
4. **차익거래(Arbitrage)**: DEX 간 가격 차이 이용

### [[탈중앙화 금융]]에서의 영향

- 일반 사용자에게 불리한 가격으로 거래 체결
- 네트워크 혼잡 및 가스비 상승
- 중앙화 우려 (대형 MEV 서치의 등장)

### 완화 방안

- **프라이빗 트랜잭션 풀**: Flashbots Protect
- **공정 순서 프로토콜**: First-Come-First-Served
- **암호화 멤풀**: 트랜잭션 내용 숨김
- **MEV 재분배**: 사용자에게 MEV 이익 환원

## 관련 개념

- [[블록체인]]
- [[스마트 컨트랙트]]
- [[탈중앙화 금융]]
- [[합의 알고리즘]]

## 참고

- MEV 탐지 및 완화 관련 서베이 논문
