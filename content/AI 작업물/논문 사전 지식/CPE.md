# CPE (Common Platform Enumeration)

## 정의

CPE는 IT 시스템, 소프트웨어, 패키지를 **식별하기 위한 표준화된 명명 체계**이다. [[CVE]] 취약점이 어떤 제품에 영향을 미치는지 정확히 명시하는 데 사용된다.

## CPE 형식

### CPE 2.3 형식

```
cpe:2.3:part:vendor:product:version:update:edition:language:sw_edition:target_sw:target_hw:other
```

### 예시

```
cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*
     │  │      │      │
     │  │      │      └── 버전
     │  │      └── 제품명
     │  └── 벤더
     └── 파트 (a=application, o=OS, h=hardware)
```

## 파트 유형

| 파트 | 설명 | 예시 |
|------|------|------|
| `a` | Application | Apache Log4j, OpenSSL |
| `o` | Operating System | Windows, Linux |
| `h` | Hardware | Cisco Router |

## 활용

### 1. NVD 취약점 매칭
- CVE에 CPE 목록이 포함됨
- "이 CVE는 이 CPE들에 해당하는 제품에 영향"

### 2. 자산 관리
- 조직의 소프트웨어 인벤토리를 CPE로 표현
- 새 CVE 발표 시 영향받는 자산 자동 식별

### 3. 보안 스캐너
- 설치된 소프트웨어의 CPE 식별
- NVD의 CVE-CPE 매핑과 비교

## CPE Dictionary

NIST가 관리하는 공식 CPE 목록:
- https://nvd.nist.gov/products/cpe

## 한계점

1. **명명 불일치**: 같은 제품도 다른 CPE로 등록될 수 있음
2. **버전 표현**: 버전 범위 표현이 복잡함
3. **업데이트 지연**: 새 소프트웨어의 CPE 등록이 늦을 수 있음

## 관련 개념

- [[CVE]]
- [[NVD]]
- [[취약점 관리]]
- [[자산 관리]]
