---
title: "RLHF"
aliases: [Reinforcement Learning from Human Feedback, 인간 피드백 강화학습]
tags: [인공지능, 강화학습, LLM]
---

## 정의
RLHF(Reinforcement Learning from Human Feedback)는 인간의 선호도 피드백을 사용하여 AI 모델을 미세조정하는 학습 기법이다. 인간이 직접 설계하기 어려운 복잡한 목표를 학습할 수 있게 한다.

## 상세 설명

### 학습 과정
1. **사전학습된 LLM 준비**: GPT 등 기본 모델
2. **지도 미세조정(SFT)**: 양질의 예시로 학습
3. **보상 모델(RM) 학습**: 인간 선호도로 점수 예측
4. **강화학습(PPO)**: 보상 최대화 정책 학습

### 보상 모델 학습
- 인간이 여러 응답을 비교/순위화
- 선호도 쌍으로 분류 모델 학습
- 출력: 응답 품질 점수

### PPO (Proximal Policy Optimization)
- 정책 업데이트 크기 제한
- 안정적인 학습 보장
- KL 페널티로 원본 모델 유지

### 대안적 방법
- **DPO(Direct Preference Optimization)**: 보상 모델 없이 직접 최적화
- **GRPO**: 그룹 상대 정책 최적화
- **ORPO**: 오즈 비율 기반 최적화
- **Constitutional AI**: 원칙 기반 자기 개선

### 효과
- 유해 출력 감소
- 지시 따르기 개선
- 인간 가치 정렬
- 사실성 향상

### 한계
- 비용과 시간 소모
- 인간 편향 전이
- 보상 해킹 가능성

## 관련 개념
- [[대규모 언어 모델]]
- [[강화학습]]
- [[딥러닝]]

## 참고
- "LLMOrbit: A Circular Taxonomy of Large Language Models" (arXiv, 2026)
- "InstructGPT" (OpenAI, 2022)
