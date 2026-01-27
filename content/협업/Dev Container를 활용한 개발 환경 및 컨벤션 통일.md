
>[!info]
>본 문서는 FastAPI + Python 3.14 프로젝트를 위한 Dev Container 설정을 단계별로 안내하는 문서이다. 개발 환경과 코드 및 커밋 컨벤션을 통일하기 위한 내용이 포함되어있다. 코드 포매터는 ruff를 사용했고 package manager는 uv를 사용했다.

## 📋 전체 구조

```
project-root/
├── .devcontainer/
│   ├── devcontainer.json      # Dev Container 메인 설정
│   └── Dockerfile              # 컨테이너 이미지 정의
├── .husky/
│   └── commit-msg              # commitlint hook
├── pyproject.toml              # Python 프로젝트 설정
├── commitlint.config.js        # commitlint 설정
└── package.json                # Node.js 의존성
```

---

## 단계 1: 기본 파일 구조 생성

```bash
# 프로젝트 루트에서 실행
mkdir -p .devcontainer .husky
```

---

## 단계 2: Dockerfile 작성

**파일: `.devcontainer/Dockerfile`**

참고 문서:

- [Official Python Docker Images](https://hub.docker.com/_/python)
- [Dev Container Dockerfile](https://containers.dev/guide/dockerfile)

- python 3.14-slim 이미지 사용
- 가상 환경은 poetry 사용
- NodeSource 사용
	- commitlint, husky 용
	- https://github.com/nodesource/distributions 참고
	- Debian 기본 저장소 Node.js는 오래 됨
	- LTS 버전 사용 가능하며 보안 패치 및 정기적 업데이트 가능
	- npm 같이 설치 됨

```Dockerfile
FROM python:3.14-slim

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_VERSION=1.8.3

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    vim \
    wget \
    # Node.js 설치를 위한 사전 요구사항
    ca-certificates \
    gnupg

# Node.js 20.x LTS 설치 (commitlint, husky용)
# 참고: https://github.com/nodesource/distributions
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
    | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs

# 작업 디렉토리 설정
WORKDIR /workspace

# vscode 사용자 생성 (선택사항이지만 권한 문제 방지)
# 참고: https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/*

# vscode 사용자로 전환
USER $USERNAME

# uv 설치    
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# path 추가
ENV PATH="/home/$USERNAME/.local/bin:$PATH"

RUN uv python install 3.14

# 컨테이너 시작 시 실행될 명령 (기본값, 오버라이드 가능)
CMD ["/bin/bash"]
```

---

## 단계 3: devcontainer.json 작성

**파일: `.devcontainer/devcontainer.json`**

참고 문서:

- [Dev Container Specification](https://containers.dev/implementors/json_reference/)
- [VSCode Dev Container](https://code.visualstudio.com/docs/devcontainers/containers)

```json
{
    // 컨테이너 이름
    "name": "FastAPI Development",
    // Dockerfile 기반 빌드 설정
    "build": {
        // Dockerfile 경로
        "dockerfile": "Dockerfile",
        // 빌드 컨텍스트 (프로젝트 루트)
        "context": "..",
        // 빌드 인자
        "args": {
            "USERNAME": "vscode",
            "USER_UID": "1000",
            "USER_GID": "1000"
        }
    },
    // 컨테이너 실행 시 사용자
    "remoteUser": "vscode",
    // 호스트와 공유할 볼륨 마운트
    "mounts": [
        // Git 설정 공유 (커밋 작성자 정보 등)
        "source=${localEnv:USERPROFILE}${localEnv:HOME}/.gitconfig,target=/home/vscode/.gitconfig,type=bind,consistency=cached",
        // SSH 키 공유 (Git 인증용)
        "source=${localEnv:USERPROFILE}${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,readonly,type=bind,consistency=cached"
    ],
    // 포트 포워딩 설정
    "forwardPorts": [
        8000 // FastAPI 기본 포트
    ],
    // 포트별 레이블 설정 (VSCode UI에 표시)
    "portsAttributes": {
        "8000": {
            "label": "FastAPI Application",
            "onAutoForward": "notify"
        }
    },
    // 컨테이너 생성 후 실행할 명령어
    "postCreateCommand": "npm install && uv sync",
    // VSCode 설정 커스터마이징
    "customizations": {
        "vscode": {
            // 자동 설치할 확장 프로그램
            // 참고: https://code.visualstudio.com/docs/editor/extension-marketplace
            "extensions": [
                "ms-python.python", // Python 지원
                "ms-python.vscode-pylance", // Python 언어 서버 (타입 체킹, 자동완성)
                "ms-python.mypy-type-checker", // MyPy 타입 체커
                "charliermarsh.ruff", // Ruff (빠른 린터), black, flake8, isort 등등 다 통합 됨.
                "the0807.uv-toolkit", // uv 관련 도구
                "njpwerner.autodocstring", // Docstring 자동 생성
                "yzhang.markdown-all-in-one", // Markdown 지원
                "usernamehw.errorlens", // 에러를 인라인으로 표시
                "gruntfuggly.todo-tree", // TODO, FIXME 주석 하이라이트
                "wayou.vscode-todo-highlight", // TODO 하이라이트
                "littlefoxteam.vscode-python-test-adapter", // 테스트 어댑터, VS Code의 내장 테스트 탐색기 UI와 python 테스트 프레임워크를 연결 해줌.
                "redhat.vscode-yaml", // YAML 지원
                "mikestead.dotenv", // .env 파일 지원
                "tamasfe.even-better-toml", // TOML 지원
                "mhutchie.git-graph", // git graph view 지원
                "mtxr.sqltools", // VS Code 내에서 SQL 쿼리를 실행할 수 있게 해줌. DB에 맞는 드라이버 확장 프로그램은 별도 설치 필요.
                "mtxr.sqltools-driver-pg", // PostgreSQL 드라이버
                "mongodb.mongodb-vscode", // MongoDB
                "42Crunch.vscode-openapi", // OpenAPI/Swagger 지원
                "humao.rest-client" // REST API 테스트 postman 같은 별도의 외부 API 테스트 도구 없이 .http 파일로 테스트 하는 도구 
            ],
            // VSCode 설정
            "settings": {
                // Python 인터프리터
                "python.defaultInterpreterPath": "/usr/local/bin/python",
                // Pylance 설정
                "python.analysis.typeCheckingMode": "basic", // 또는 "strict"
                "python.analysis.autoImportCompletions": true,
                "python.analysis.completeFunctionParens": true,
                "python.analysis.diagnosticSeverityOverrides": {
                    "reportUnusedImport": "information",
                    "reportUnusedVariable": "warning"
                },
                // Python 린팅
                "python.linting.enabled": true,
                "python.linting.ruffEnabled": true,
                "python.linting.mypyEnabled": true,
                "python.linting.mypyArgs": [
                    "--ignore-missing-imports",
                    "--follow-imports=silent",
                    "--show-column-numbers",
                    "--strict"
                ],
                // 포매팅 설정
                "editor.formatOnSave": true, // 저장 시 자동 포맷
                "editor.formatOnPaste": false, // 붙여넣기 시 포맷 (선택)
                "editor.formatOnType": false, // 타이핑 시 포맷 (선택)
                // Ruff 설정
                "ruff.enable": true,
                "ruff.organizeImports": true,
                "ruff.fixAll": true,
                "ruff.lint.enable": true, // 명시적 린팅 활성화
                "ruff.format.enable": true, // 명시적 포맷팅 활성화
                // Python 포매터: ruff
                "[python]": {
                    "editor.defaultFormatter": "charliermarsh.ruff",
                    "editor.formatOnSave": true,
                    "editor.codeActionsOnSave": {
                        "source.organizeImports": "explicit", // Import 정리
                        "source.fixAll": "explicit" // 자동 수정
                    }
                },
                // 터미널 설정
                "terminal.integrated.defaultProfile.linux": "bash",
                "terminal.integrated.shell.linux": "/bin/bash",
                // 편집기 설정
                "editor.rulers": [
                    88,
                    120
                ],
                "editor.tabSize": 4,
                "editor.insertSpaces": true,
                "editor.wordWrap": "off",
                "editor.renderWhitespace": "boundary",
                "editor.suggestSelection": "first",
                // 테스트 설정
                "python.testing.pytestEnabled": true,
                "python.testing.unittestEnabled": false,
                "python.testing.pytestArgs": [
                    "tests",
                    "-v",
                    "--cov=.",
                    "--cov-report=html"
                ],
                // Git 설정
                "git.path": "/usr/bin/git",
                "gitlens.advanced.git": "/usr/bin/git",
                "git.autofetch": true,
                "git.confirmSync": false,
                "git.enableSmartCommit": true,
                // 자동 저장
                "files.autoSave": "afterDelay",
                "files.autoSaveDelay": 1000,
                // ErrorLens 설정
                "errorLens.enabledDiagnosticLevels": [
                    "error",
                    "warning"
                ],
                // Todo Tree 설정
                "todo-tree.general.tags": [
                    "TODO",
                    "FIXME",
                    "HACK",
                    "NOTE",
                    "XXX"
                ],
                // Trailing 공백 자동 제거
                "files.trimTrailingWhitespace": true,
                "files.insertFinalNewline": true,
                "files.trimFinalNewlines": true,
                // JSON 포맷팅
                "[json]": {
                    "editor.defaultFormatter": "vscode.json-language-features",
                    "editor.formatOnSave": true
                },
                // YAML 포맷팅
                "[yaml]": {
                    "editor.defaultFormatter": "redhat.vscode-yaml",
                    "editor.formatOnSave": true
                },
                // Markdown 포맷팅
                "[markdown]": {
                    "editor.wordWrap": "on",
                    "editor.quickSuggestions": {
                        "comments": "off",
                        "strings": "off",
                        "other": "off"
                    }
                }
            }
        }
    },
    // 환경 변수 설정
    "remoteEnv": {
        "PYTHONPATH": "/workspace",
        "ENVIRONMENT": "development"
    },
    // 호스트 요구사항
    "hostRequirements": {
        "cpus": 2,
        "memory": "4gb",
        "storage": "32gb"
    }
}

```

---
## 단계 4: Python 프로젝트 설정

**파일: `pyproject.toml`**

참고 문서:

- [ruff](https://docs.astral.sh/ruff/)

```toml
[project]
name = "convention-test"
version = "0.1.0"
description = "fast-api project"
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "fastapi[standard]>=0.121.1",
]

# ===== Ruff 설정 =====
# 참고: https://docs.astral.sh/ruff/
[tool.ruff]
line-length = 88
target-version = "py314"
exclude = [
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
]

# Linting 규칙
[tool.ruff.lint]
select = [
    "F",   # Pyflakes
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "I",   # isort (import 정렬)
    "N",   # pep8-naming
    "D",   # pydocstyle (docstring)
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
    "PTH", # flake8-use-pathlib
]

ignore = [
    "E501",    # line-too-long (formatter가 처리)
    "D203",    # one-blank-line-before-class
    "D213",    # multi-line-summary-second-line
    "D100",    # Missing docstring in public module
    "D104",    # Missing docstring in public package
    "ANN",     # 모든 타입 주석 경고 비활성화
    "ARG",     # 모든 함수 인수 관련 경고 비활성화
    "B007",    # 루프 제어 변수가 사용되지 않음
    "B009",    # getattr를 상수 속성 값으로 호출하지 않음
    "B011",    # False를 assert하지 않음
    "DTZ001",  # tzinfo 없이 datetime 호출
    "DTZ007",  # 시간대 없이 datetime.strptime 호출
    "DTZ011",  # date.today 호출
    "D405",    # 섹션 이름의 대문자 처리 (TODO 및 NOTE와 관련된 버그)
    "E501",    # 너무 긴 줄
    "G004",    # f-string에서 로깅 사용
    "PD013",   # pandas의 .stack 사용
    "PLR0913", # 너무 많은 인수
    "PTH103",  # os.makedirs
    "PTH110",  # os.path.exists
    "PTH113",  # os.path.isfile
    "PTH118",  # os.path.join
    "PTH123",  # builtin-open
    "RET504",  # 불필요한 변수 할당
    "S301",    # 의심스러운 pickle 사용
    "S603",    # shell=True 없이 subprocess 실행
    "S607",    # 잘못된 경로로 프로세스 시작
    "TC002",   # typing 전용 서드파티 import
    "E402",    # import가 파일 상단에 위치하지 않음
    "BLE001",  # except의 세부 사항을 모른상태에서 처리하기
    "E722",    # bare except허가해주기
]

# 파일별 예외
[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401", "D104"] # unused import, docstring
"tests/*" = ["D"]                # 테스트는 docstring 불필요
"scripts/*" = ["T201"]            # print 문 허용

# import 정렬 (isort 호환)
[tool.ruff.lint.isort]
known-first-party = ["app"]
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]
split-on-trailing-comma = true
force-single-line = false
force-wrap-aliases = false

[tool.ruff.lint.pydocstyle]
convention = "google"
# "google", "numpy", "pep257" 중 선택

# Formatting (Black 호환)
[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

# MyPy 설정 (타입 체킹)
# 참고: https://mypy.readthedocs.io/en/stable/config_file.html
[tool.mypy]
python_version = "3.14"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = false
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true
ignore_missing_imports = true

```

---

## 단계 5: Commitlint 설정

### 5-1. package.json
[[husky]]
위 문서 대로 설치 진행하면 package.json 및 package-lock.json이 생성 된다.
### 5-2. commitlint.config.js

[[Conventional Commits]]
위 문서 아래의 작성 내용 참고

---
## 📝 Dev Container 사용 방법

1. **사전 준비**

```bash
   # 설치 필요
   - VSCode
   - Docker Desktop
   - Dev Containers Extension
```

2. **프로젝트 클론**

```bash
   git clone <repo>
   code <project>
   # "Reopen in Container" 클릭
```

3. **Dev Container 실행**

```bash
# VSCode에서
1. 프로젝트 열기
2. F1 누르기
3. "Dev Containers: Reopen in Container" 선택
4. 초기 빌드 대기
```

