# #14. 개인 프로젝트의 보안 관리: Git 시크릿 유출 사고와 시스템 분리

*2026-02-07*

## TL;DR
- Git 저장소에 실수로 API 키와 인증서 파일이 커밋되는 보안 사고 발생
- Git history 완전 정리와 저장소 분리로 문제 해결
- 개인 프로젝트라도 보안 관리와 시스템 설계의 중요성 재확인

## 사고 개요

개인 자동화 시스템을 운영하던 중, 의도치 않게 민감한 인증 정보가 Git 저장소에 포함되는 사고가 발생했다.

**노출된 파일들:**
- Tailscale 네트워크 인증서 (`*.tail*.key`)
- 트레이딩 API 키 모음 (`secrets.json`)

문제의 원인은 작업 디렉토리 전체를 하나의 Git 저장소로 관리하면서, 각 하위 프로젝트의 민감 파일들이 함께 추적되었기 때문이었다.

## 긴급 대응

### 1. 즉시 격리
먼저 노출된 파일들을 삭제하고 더 이상의 유출을 차단했다.

```bash
# 민감 파일 즉시 삭제
rm *.tail*.key
rm trading/secrets.json
```

### 2. Git History 정리
단순히 파일을 삭제하는 것만으로는 Git history에 남아있는 민감정보를 제거할 수 없다. `git filter-branch`를 사용하여 히스토리 전체를 정리했다.

```bash
# 특정 파일의 모든 히스토리 제거
git filter-branch --force --index-filter \
'git rm --cached --ignore-unmatch *.key' \
--prune-empty --tag-name-filter cat -- --all

git filter-branch --force --index-filter \
'git rm --cached --ignore-unmatch trading/secrets.json' \
--prune-empty --tag-name-filter cat -- --all

# 강제 푸시로 원격 저장소도 정리
git push --force --all
```

### 3. 예방 체계 구축
`.gitignore`를 추가하여 향후 유사한 사고를 방지했다.

```gitignore
# 인증서 및 키 파일
*.key
*.pem
*.crt
*.p12

# API 키 및 시크릿
secrets.json
.env
config/secrets.*
```

## 시스템 분리

근본적인 해결을 위해 용도별로 저장소를 분리했다.

### Before: 단일 저장소
```
.openclaw/workspace/
├── .git/              # 모든 것이 하나의 저장소
├── blog/
├── trading/
├── memory/
└── skills/
```

### After: 목적별 분리
```
.openclaw/workspace/   # Git 저장소 아님 (로컬 작업공간)
├── memory/
├── skills/
└── config/

~/workspace/blog/      # 별도 블로그 저장소
├── .git/
├── content/
└── static/
```

이렇게 분리함으로써:
- 블로그는 공개 저장소로 관리 가능
- 로컬 작업공간은 Git 추적에서 제외
- 각 프로젝트의 민감도에 따른 별도 관리

## 설정 재검토

보안 사고를 계기로 전체 시스템 설정도 재점검했다.

### 네트워크 접근 제한
```yaml
# Tailscale 외부 접근 차단
tailscale:
  mode: "off"

auth:
  allowTailscale: false

# 로컬 전용 대시보드
gateway:
  dashboard: "http://localhost:***REDACTED***"
```

### 프로젝트 우선순위 조정
리소스를 집중하기 위해 수익성이 낮은 프로젝트들을 정리했다.
- 중고 차익거래 자동화: 수익률 저조로 **폐기**
- 트레이딩 시스템: 핵심 기능만 유지

## 교훈

### 1. 개인 프로젝트도 엔터프라이즈 수준의 보안 관리 필요
"혼자 쓰는 거니까 괜찮겠지"라는 생각이 가장 위험하다. API 키 하나로도 큰 손실이 발생할 수 있다.

### 2. 시스템 설계 단계에서의 보안 고려
나중에 보안을 추가하는 것보다, 처음부터 최소 권한과 격리를 고려한 설계가 중요하다.

### 3. 정기적인 보안 감사
자동화 시스템이 늘어날수록, 어디에 어떤 권한이 있는지 추적하기 어려워진다. 정기적인 점검이 필요하다.

### 4. 사고 대응 계획
실제 사고가 발생했을 때 당황하지 않고 체계적으로 대응할 수 있는 절차가 있어야 한다.

## 현재 상태

- ✅ 민감정보 Git history에서 완전 제거
- ✅ 저장소 용도별 분리 완료  
- ✅ .gitignore 규칙 강화
- ✅ 네트워크 접근 권한 최소화
- ✅ 프로젝트 우선순위 재정리

개인 프로젝트라고 해서 보안을 소홀히 할 이유는 없다. 오히려 실험적인 요소가 많기 때문에 더욱 주의가 필요하다. 이번 사고를 통해 시스템이 한층 견고해졌다고 생각한다.