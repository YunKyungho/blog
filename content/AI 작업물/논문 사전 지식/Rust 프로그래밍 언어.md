---
title: "Rust 프로그래밍 언어"
aliases: [Rust, 러스트]
tags: [프로그래밍, 시스템프로그래밍, 보안]
---

## 정의

Rust는 Mozilla에서 개발한 시스템 프로그래밍 언어로, 메모리 안전성과 동시성을 컴파일 타임에 보장하면서도 C/C++에 버금가는 성능을 제공한다.

## 상세 설명

### 핵심 특징

1. **메모리 안전성**: 가비지 컬렉터 없이 메모리 안전 보장
2. **제로 비용 추상화**: 고수준 추상화가 런타임 오버헤드 없음
3. **스레드 안전성**: 데이터 레이스를 컴파일 타임에 방지
4. **풍부한 타입 시스템**: 많은 버그를 컴파일 시점에 발견

### 소유권 시스템

Rust의 핵심 개념:

```rust
fn main() {
    let s1 = String::from("hello");
    let s2 = s1; // s1의 소유권이 s2로 이동
    // println!("{}", s1); // 컴파일 에러!
    println!("{}", s2); // OK
}
```

- **소유권 규칙**:
  1. 각 값은 하나의 소유자만 가짐
  2. 한 번에 하나의 소유자만 존재
  3. 소유자가 스코프를 벗어나면 값이 해제됨

### Safe vs Unsafe Rust

- **Safe Rust**: 컴파일러가 메모리 안전성 보장
- **Unsafe Rust**: `unsafe` 블록 내에서 저수준 연산 허용
  - 원시 포인터 역참조
  - unsafe 함수 호출
  - 가변 정적 변수 접근

### Rust CVE 분석 결과

연구에 따르면 Rust CVE의 주요 원인:
- **unsafe 블록 오용**: 가장 흔한 원인
- **논리 오류**: 메모리 무관 버그
- **의존성 문제**: 외부 라이브러리의 취약점

### 활용 분야

- 시스템 프로그래밍 (OS, 드라이버)
- 웹 서비스 (고성능 서버)
- 블록체인
- 게임 엔진
- CLI 도구

## 관련 개념

- [[메모리 안전성]]
- [[CVE]]

## 참고

- Hui Xu et al., "Memory-Safety Challenge Considered Solved? An In-Depth Study with All Rust CVEs" (arXiv, 2021)
- 공식 사이트: https://www.rust-lang.org
