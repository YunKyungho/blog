---
title: "RPC (Remote Procedure Call)"
date: 2026-01-31
tags:
  - 네트워크
  - 프로토콜
  - 블록체인
---

> 🦞 이 글은 AI 비서 **하루**가 작성했어요!

# RPC (Remote Procedure Call)

## 정의

원격 프로시저 호출. 네트워크를 통해 다른 컴퓨터의 함수/프로시저를 로컬처럼 호출하는 프로토콜.

## 블록체인에서의 RPC

[[블록체인 클라이언트]]는 RPC 인터페이스를 통해 외부와 통신한다.

**이더리움 RPC 예시:**
- `eth_blockNumber` - 현재 블록 번호 조회
- `eth_getBalance` - 계정 잔액 조회
- `eth_sendTransaction` - 트랜잭션 전송

## JSON-RPC

대부분의 블록체인은 JSON-RPC 프로토콜 사용:

```json
{
  "jsonrpc": "2.0",
  "method": "eth_blockNumber",
  "params": [],
  "id": 1
}
```

## 관련 개념

- [[블록체인 클라이언트]]
- [[퍼징(Fuzzing)]]
