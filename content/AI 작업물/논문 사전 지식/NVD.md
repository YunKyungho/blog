---
title: "NVD"
aliases: [National Vulnerability Database, 국가취약점데이터베이스]
tags: [보안, 취약점, 데이터베이스]
---

## 정의

NVD(National Vulnerability Database)는 미국 NIST(국립표준기술연구소)가 관리하는 공식 취약점 데이터베이스로, CVE(Common Vulnerabilities and Exposures) 정보를 기반으로 추가적인 분석 정보를 제공한다.

## 상세 설명

### 주요 기능

1. **취약점 정보 저장소**: 알려진 소프트웨어 취약점의 중앙 저장소
2. **CVSS 점수 제공**: 취약점의 심각도를 수치화
3. **CPE 매핑**: 취약점이 영향을 미치는 제품 식별
4. **CWE 분류**: 취약점의 유형 분류

### NVD가 제공하는 정보

- **CVE ID**: 취약점 고유 식별자
- **CVSS 점수**: 취약점 심각도 (0.0~10.0)
- **영향받는 제품 (CPE)**: 취약한 소프트웨어/하드웨어 목록
- **취약점 설명**: 문제의 상세 내용
- **참조 링크**: 패치, 권고문 등 관련 정보
- **발표일/수정일**: 취약점 공개 및 업데이트 일자

### NVD의 한계

- **처리 지연**: CVE 발표 후 NVD 분석까지 시간 소요
- **불완전한 CPE**: 영향받는 제품 정보 누락
- **일관성 부족**: 취약점 설명의 품질 편차
- **패치 정보 부족**: 수정 커밋 링크 누락

### 활용 분야

- 취약점 관리 및 스캐닝
- 소프트웨어 구성 분석 (SCA)
- 보안 자동화
- 위험 평가

## 관련 개념

- [[CVE]]
- [[CPE]]
- [[CVSS]]

## 참고

- Julia Wunder et al., "On NVD Users' Attitudes, Experiences, Hopes and Hurdles" (arXiv, 2024)
- 웹사이트: https://nvd.nist.gov
