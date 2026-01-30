# CVE (Common Vulnerabilities and Exposures)

## 정의

CVE는 **공개적으로 알려진 보안 취약점에 대한 표준화된 식별자 시스템**이다. 미국 MITRE Corporation이 관리하며, 각 취약점에 고유한 CVE ID를 부여한다.

## CVE ID 형식

```
CVE-연도-일련번호
예: CVE-2024-12345
```

- **연도**: 취약점이 CVE에 할당된 연도 (발견 연도가 아님)
- **일련번호**: 4자리 이상의 숫자

## 목적

1. **표준화**: 동일한 취약점에 대해 전 세계적으로 통일된 명칭 사용
2. **상호운용성**: 서로 다른 보안 도구/데이터베이스 간 정보 교환
3. **추적성**: 취약점의 수명주기 추적 (발견 → 패치 → 완화)

## CVE 수명주기

```
취약점 발견 → CNA에 보고 → CVE ID 할당 → 공개 → NVD 등록 → 패치/완화
```

## 관련 용어

| 용어 | 설명 |
|------|------|
| **CNA** | CVE Numbering Authority, CVE ID 할당 권한 기관 |
| **NVD** | National Vulnerability Database, NIST 운영 |
| **CVSS** | Common Vulnerability Scoring System, 심각도 점수 |
| **[[CPE]]** | Common Platform Enumeration, 영향받는 제품 식별 |
| **CWE** | Common Weakness Enumeration, 취약점 유형 분류 |

## CVSS 점수

| 점수 범위 | 심각도 |
|----------|--------|
| 0.0 | None |
| 0.1 - 3.9 | Low |
| 4.0 - 6.9 | Medium |
| 7.0 - 8.9 | High |
| 9.0 - 10.0 | Critical |

## 예시

**CVE-2021-44228 (Log4Shell)**
- 영향: Apache Log4j 2.x
- CVSS: 10.0 (Critical)
- 유형: 원격 코드 실행 (RCE)
- 영향 범위: 수백만 개의 Java 애플리케이션

## 활용

- 보안 스캐너가 시스템의 취약점 식별
- 패치 관리 시스템에서 우선순위 결정
- 보안 연구에서 취약점 참조
- 컴플라이언스 감사

## 관련 개념

- [[CPE]]
- [[취약점 탐지]]
- [[정적 분석]]
- [[보안 감사]]
