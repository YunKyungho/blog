
## 1. uv란 무엇인가?

**uv**는 Rust로 작성된 초고속 Python 패키지 및 프로젝트 매니저입니다. pip, pip-tools, pipx, poetry, pyenv, twine, virtualenv 등 여러 도구를 하나로 대체하여 Python 버전 설치 및 관리, 가상 환경 생성, 프로젝트 의존성 효율적 처리, 작업 환경 재현, 프로젝트 빌드 및 배포까지 처리 할 수 있는 올인원 솔루션이다. 

---

## 2. 왜 uv를 사용해야 할까?

### 압도적인 속도

uv는 기존 pip보다 10-100배 빠르며, 패키지 설치와 의존성 해결을 몇 초만에 완료한다.

**속도 비교:**

| 작업      | pip | uv   | 속도 향상   |
| ------- | --- | ---- | ------- |
| 패키지 설치  | 60초 | 3초   | **20배** |
| 가상환경 생성 | 8초  | 0.1초 | **80배** |
| 의존성 해결  | 45초 | 2초   | **22배** |

### 통합된 워크플로우

**기존 방식:**

```bash
# Python 버전 관리
pyenv install 3.11

# 가상 환경 생성
python -m venv .venv

# 패키지 설치
pip install -r requirements.txt

# 의존성 잠금
pip-compile requirements.in
```

**uv 방식:**

```bash
# 모든 것을 하나의 명령으로!
uv init my-project
uv add requests pandas
```

### 디스크 효율성

전역 캐시를 활용한 의존성 중복 제거로 저장 공간을 절약한다.

---

## 3. 설치 방법

### 운영체제별 설치

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 설치 확인

```bash
uv --version
# 출력: uv 0.5.0 (또는 최신 버전)
```

---

## 4. 기본 사용법

### 프로젝트 초기화

uv init 명령으로 프로젝트를 생성하면 .gitignore, .python-version, README.md, main.py, pyproject.toml이 자동으로 생성된다.

```bash
# 새 프로젝트 생성
uv init my-project
cd my-project

# 프로젝트 구조
├── .gitignore
├── .python-version
├── README.md
├── main.py
└── pyproject.toml
```

### Python 버전 관리

```bash
# Python 설치
uv python install 3.11

# 여러 버전 한번에 설치
uv python install 3.10 3.11 3.12

# 설치된 버전 확인
uv python list

# 프로젝트에 특정 버전 설정
uv python pin 3.11
```

### 패키지 설치

```bash
# 패키지 추가
uv add requests pandas numpy

# 개발 의존성 추가
uv add --dev pytest black ruff

# 패키지 제거
uv remove requests

# requirements.txt로부터 설치
uv pip install -r requirements.txt

# 협업 시 기존 pyproject.toml 기반으로 의존성 설치
uv sync
```

### 코드 실행

```bash
# Python 스크립트 실행
uv run main.py

# 테스트 실행
uv run pytest

# 특정 Python 버전으로 실행
uv run --python 3.11 main.py
```

### CLI 도구 사용

```bash
# 도구 설치
uv tool install ruff
uv tool install black

# 임시로 도구 실행 (설치 없이)
uvx ruff check .
uvx black .

# 설치된 도구 목록
uv tool list
```
