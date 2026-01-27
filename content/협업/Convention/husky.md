## Husky란?

Husky는 Git hooks를 쉽게 관리하고 사용할 수 있게 해주는 npm 패키지 이며 Git hooks를 프로젝트에 공유하고, 팀원 모두가 동일한 hooks를 자동으로 설정할 수 있도록 도와준다.

---
## Husky의 장점

**1. 간편한 설정과 공유**
Git hooks를 `.husky` 폴더에서 관리하므로 버전 관리가 가능하고, 팀 전체가 동일한 hooks를 사용할 수 있다. `.git/hooks` 폴더는 Git에서 무시되지만, Husky는 git config core.hooksPath 값을 수정하여 이 문제를 해결한다.

**2. 자동 설치**
한번 레포지토리에 구성을 해두면 이후 팀원들은 `npm install` 시 자동으로 Git hooks가 설정되어 별도의 수동 작업이 필요 없다.

**3. 코드 품질 보장**
커밋 전에 linting, 테스트, 포맷팅 등을 자동으로 실행하여 잘못된 코드가 저장소에 들어가는 것을 방지한다.

**4. 다양한 도구와 통합**
ESLint, Prettier, Jest, commitlint 등 다양한 개발 도구와 쉽게 연동된다.

---
## Husky 설치 및 사용법

### 설치
```bash
npm install husky --save-dev
npx husky init
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

이후의 팀원들은 npm install 명령어만 사용해도 husky 이용 가능.

---
## 주요 기능

**1. pre-commit hook**
커밋하기 전에 실행됩니다. 가장 많이 사용되는 hook입니다.

```bash
# .husky/pre-commit
npm run lint
npm run test
```

**2. commit-msg hook**
커밋 메시지를 검증할 때 사용합니다. commitlint와 함께 사용하면 Conventional Commits 규칙을 강제할 수 있습니다.

```bash
# .husky/commit-msg
npx --no -- commitlint --edit $1
```

**3. pre-push hook**
push하기 전에 실행됩니다. 시간이 오래 걸리는 테스트나 빌드를 실행하기 좋습니다.

```bash
# .husky/pre-push
npm run test:e2e
npm run build
```

**4. post-merge hook**
브랜치 병합 후 실행됩니다. 의존성 업데이트나 데이터베이스 마이그레이션에 유용합니다.

```bash
# .husky/post-merge
npm install
```

**5. pre-rebase hook**
rebase 작업 전에 실행되어 안전 검사를 할 수 있습니다.

**6. lint-staged와 연동**
수정된 파일만 검사하여 속도를 높일 수 있습니다.

```bash
# .husky/pre-commit
npx lint-staged
```