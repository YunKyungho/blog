## Conventional Commits란?

Conventional Commits은 커밋 메시지에 일관된 형식을 적용하여 프로젝트 히스토리를 읽기 쉽고 자동화하기 좋게 만드는 규칙이다. 이를 통해 자동으로 CHANGELOG를 생성하거나 시맨틱 버저닝을 관리할 수도 있다.

---
## 커밋 메시지 구조

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 1. Type (필수)

커밋의 종류를 나타내며, 다음 중 하나를 사용합니다:

- **feat**: 새로운 기능 추가
- **fix**: 버그 수정
- **docs**: 문서 변경 (코드 변경 없음)
- **style**: 코드 포맷팅, 세미콜론 누락 등 (기능 변경 없음)
- **refactor**: 코드 리팩토링 (기능 변경 없음)
- **perf**: 성능 개선
- **test**: 테스트 코드 추가 또는 수정
- **build**: 빌드 시스템 또는 외부 종속성 변경 (webpack, npm 등)
- **ci**: CI 설정 파일 및 스크립트 변경
- **chore**: 기타 변경사항 (빌드 프로세스, 도구 설정 등)
- **revert**: 이전 커밋 되돌리기

### 2. Scope (선택)

변경 사항이 영향을 미치는 범위를 나타냅니다.

예시: `auth`, `api`, `ui`, `database`, `parser` 등

### 3. Description (필수)

변경 사항에 대한 간단한 설명입니다.

**규칙:**

- 명령형 현재 시제 사용 ("changed" 또는 "changes"가 아닌 "change")
- 첫 글자는 소문자
- 마침표(.)로 끝나지 않음
- 50자 이내로 작성 권장

### 4. Body (선택)

변경 사항에 대한 상세한 설명입니다.

**규칙:**

- 헤더와 본문 사이에 빈 줄 추가
- 무엇을, 왜 변경했는지 설명
- 72자마다 줄바꿈 권장

### 5. Footer (선택)

Breaking changes나 이슈 참조를 작성합니다.

**규칙:**

- `BREAKING CHANGE:` - 중대한 변경 사항 명시
- `Closes #123` - 이슈 종료 참조
- `Refs #456` - 이슈 참조

---
## 커밋 메시지 예시

### 기본 예시

```
feat: 사용자 로그인 기능 추가
```

### Scope 포함

```
fix(auth): 토큰 만료 시 재로그인 오류 수정
```

### Body 포함

```
feat(api): 사용자 프로필 조회 API 추가

사용자 정보를 조회할 수 있는 GET /api/users/:id 엔드포인트를 추가했습니다.
인증된 사용자만 접근 가능하며, JWT 토큰 검증을 포함합니다.
```

### Footer 포함

```
fix(database): 트랜잭션 롤백 오류 수정

데이터베이스 연결이 끊어질 때 트랜잭션이 제대로 롤백되지 않던 문제를 수정했습니다.

Closes #234
```

### Breaking Change

```
feat(api): 인증 방식 변경

BREAKING CHANGE: 기존 API 키 인증 방식을 제거하고 OAuth 2.0으로 전환했습니다.
모든 클라이언트는 새로운 인증 방식으로 마이그레이션해야 합니다.
```

---
## 컨벤션 자동화

>[!info] husky + commitlint 사용 시 (node.js 20.X 버전 필요)

### 참고 자료
- [Commitlint Guides](https://commitlint.js.org/guides/getting-started.html)
- [Commitlint Rules](https://commitlint.js.org/reference/rules.html)

### commitlint.config.js 작성

- 구조(Rules의 명칭 별 의미)
```
<type>(<scope>): <subject>
│                  │
│                  └─ subject
└─ header (전체 첫 줄)

<body>

<footer>
```

- 
```javascript
module.exports = {
  extends: ['@commitlint/config-conventional'],
  
  rules: {
    // Type 규칙
    'type-enum': [
      2,
      'always',
      [
        'feat',
        'fix',
        'docs',
        'style',
        'refactor',
        'perf',
        'test',
        'build',
        'ci',
        'chore',
        'revert'
      ]
    ],
    'type-case': [2, 'always', 'lower-case'],
    'type-empty': [2, 'never'],
    
    // Scope 규칙
    'scope-case': [2, 'always', 'lower-case'],
    
    // Subject 규칙
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'], // 마침표 금지
    'subject-case': [0], // 대소문자 규칙 비활성화 (한글 지원)
    'subject-max-length': [2, 'always', 72],
    
    // Header 규칙
    'header-max-length': [2, 'always', 100],
    
    // Body 규칙
    'body-leading-blank': [2, 'always'],
    'body-max-line-length': [2, 'always', 100],
    
    // Footer 규칙
    'footer-leading-blank': [2, 'always'],
    'footer-max-line-length': [2, 'always', 100]
  }
};
```

### 명령어 실행
```bash
npm install --save-dev @commitlint/cli @commitlint/config-conventional husky

# Husky 초기화
npx husky init

# husky/commit-msg 파일 생성 후 아래 내용 추가
#!/usr/bin/env sh
npx --no -- commitlint --edit "$1"

# 실행 권한 부여
chmod +x .husky/commit-msg

# windows에서 사용 시 
git config --global core.shell "C:/Git/bin/bash.exe" # 개인 git bash 경로

# VS Code 사용 시 local git 경로 직접 설정해줘야 함.
```
### package.json에 다음 내용 추가
```json
// npm install 명령어 사용 후 아래 명령어도 실행 됨.
{
  "scripts": {
    "prepare": "husky"
  }
}
```

### 다른 팀원이 husky 사용 시
```bash
npm install
```

### git commit 해보고 잘 적용되나 확인
