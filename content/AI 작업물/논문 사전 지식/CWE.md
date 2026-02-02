# CWE (Common Weakness Enumeration)

## 정의

CWE는 **소프트웨어 및 하드웨어 보안 약점의 분류 체계**다. CVE가 개별 취약점 인스턴스라면, CWE는 그 취약점의 "유형"을 분류한다.

## CVE vs CWE

| 구분 | CVE | CWE |
|------|-----|-----|
| 의미 | 개별 취약점 사례 | 취약점 유형/패턴 |
| 예시 | CVE-2021-44228 | CWE-502 (역직렬화) |
| 비유 | "이 환자는 독감에 걸렸다" | "독감이란 이런 병이다" |

## CWE ID 형식

```
CWE-숫자
예: CWE-79 (XSS), CWE-89 (SQL Injection)
```

## 대표적인 CWE 목록

| CWE ID | 이름 | 설명 |
|--------|------|------|
| CWE-79 | XSS | Cross-Site Scripting |
| CWE-89 | SQL Injection | SQL 삽입 공격 |
| CWE-125 | Out-of-bounds Read | 버퍼 범위 초과 읽기 |
| CWE-787 | Out-of-bounds Write | 버퍼 범위 초과 쓰기 |
| CWE-416 | Use After Free | 해제된 메모리 사용 |
| CWE-502 | Deserialization | 신뢰할 수 없는 데이터 역직렬화 |
| CWE-22 | Path Traversal | 경로 조작 공격 |

## 계층 구조

CWE는 트리 형태의 계층 구조를 가진다:

```
CWE-707 (부적절한 중화)
  └── CWE-74 (인젝션)
        ├── CWE-79 (XSS)
        └── CWE-89 (SQL Injection)
```

## 활용

1. **취약점 분류**: CVE에 CWE 태그 부여
2. **개발자 교육**: 어떤 유형의 실수를 피해야 하는지
3. **코드 분석 도구**: 특정 CWE 패턴 탐지 규칙
4. **보안 요구사항**: "CWE Top 25 약점 제거 필수"

## CWE Top 25

MITRE가 매년 발표하는 가장 위험한 소프트웨어 약점 25개. 2023년 1위는 CWE-787 (Out-of-bounds Write).

## 관련 개념

- [[CVE]] - 개별 취약점 식별자
- [[CVSS]] - 취약점 심각도 점수
- [[정적 분석]] - CWE 탐지에 사용
- [[SBOM]] - 소프트웨어 구성 요소와 취약점 연결
