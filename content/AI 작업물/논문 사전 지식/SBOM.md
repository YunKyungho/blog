# SBOM (Software Bill of Materials)

## 정의

SBOM은 **소프트웨어 구성 요소의 목록**이다. 제조업의 BOM(Bill of Materials)처럼, 소프트웨어가 어떤 라이브러리, 모듈, 의존성으로 구성되어 있는지 명세한다.

## 왜 필요한가

현대 소프트웨어는 수백 개의 오픈소스 라이브러리에 의존한다. Log4Shell(CVE-2021-44228) 사태처럼 하나의 취약점이 발견되면, 영향받는 시스템을 빠르게 파악해야 한다. SBOM 없이는 "우리 시스템에 Log4j가 있나?"라는 질문에 답하기 어렵다.

## 포함 정보

| 항목 | 설명 |
|------|------|
| 컴포넌트 이름 | 라이브러리, 패키지명 |
| 버전 | 정확한 버전 번호 |
| 공급자 | 개발사/유지보수자 |
| 해시값 | 무결성 검증용 |
| 라이선스 | 오픈소스 라이선스 정보 |
| 의존성 관계 | 직접/간접 의존성 트리 |

## 주요 표준 형식

1. **SPDX** (Software Package Data Exchange): Linux Foundation 주도
2. **CycloneDX**: OWASP에서 개발, 보안 중심
3. **SWID** (Software Identification Tags): ISO/IEC 표준

## 생성 도구

- **Syft**: 컨테이너/파일시스템에서 SBOM 생성
- **Trivy**: 취약점 스캐닝 + SBOM
- **SPDX Tools**: 공식 SPDX 도구
- **cdxgen**: CycloneDX 생성기

## 활용 사례

```
새로운 CVE 발표
    ↓
SBOM에서 해당 컴포넌트 검색
    ↓
영향받는 시스템 즉시 파악
    ↓
우선순위 기반 패치 적용
```

## 규제 동향

- **미국 행정명령 14028** (2021): 연방 정부 납품 소프트웨어에 SBOM 의무화
- **EU Cyber Resilience Act**: SBOM 제공 요구 예정

## 한계

- SBOM 생성 도구마다 결과가 다를 수 있음
- 동적으로 로드되는 의존성 탐지 어려움
- 취약점 매핑([[CVE]], [[CPE]])의 정확도 문제

## 관련 개념

- [[CVE]]
- [[CPE]]
- [[NVD]]
- [[그래프 신경망]] - SBOM을 그래프로 모델링하여 분석
