# #9. Git Repository Security Incident Response

*2026-02-12*

## TL;DR
- 실수로 민감한 인증서 및 API 키가 Git 히스토리에 커밋됨
- `git filter-branch`와 force push로 히스토리 완전 정리
- `.gitignore` 강화 및 저장소 구조 개선
- 보안 교훈: git add . 사용 전 반드시 확인

## 사고 발생

개발 환경 정리 중 `.openclaw/workspace` 디렉토리 전체를 Git 저장소로 만들었는데, 여기에 민감한 파일들이 포함되어 있었다:

- Tailscale 인증서 파일 (`*.key`)
- API 키가 포함된 설정 파일 (`secrets.json`)  
- 기타 인증서 파일들 (`*.pem`, `*.crt`)

`git add .` 명령으로 모든 파일을 추가하면서 이런 민감한 파일들이 커밋되었고, GitHub에 푸시까지 완료된 상황이었다.

## 즉시 대응

### 1. 파일 삭제
```bash
rm ***REDACTED***
rm ***REDACTED***
```

### 2. Git 히스토리 완전 정리
단순히 파일을 삭제하고 커밋하는 것으로는 부족하다. Git 히스토리에 민감한 정보가 남아있기 때문에 히스토리 자체를 정리해야 했다.

```bash
# 특정 파일을 히스토리에서 완전 제거
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch path/to/sensitive/file' \
  --prune-empty --tag-name-filter cat -- --all

# 원격 저장소에 강제 푸시
git push --force --all
```

### 3. .gitignore 강화
```gitignore
# 인증서 및 키 파일
*.key
*.pem  
*.crt
*.p12

# 설정 파일
secrets.json
config.json
.env
.env.*

# 로그 및 임시 파일
*.log
.DS_Store
```

## 구조적 개선

### 저장소 분리
기존의 workspace 전체를 하나의 Git 저장소로 관리하던 방식에서 벗어나:

- **블로그**: `~/workspace/blog` 별도 관리 (Quartz 프레임워크)
- **워크스페이스**: Git 저장소 해제, 개별 프로젝트별 관리
- **설정**: 민감한 설정은 별도 디렉토리에서 관리

### Gateway 설정 변경
보안을 위해 Tailscale 기능도 비활성화:

```yaml
tailscale:
  mode: "off"
auth:
  allowTailscale: false
```

대시보드는 로컬 전용(`http://localhost:***REDACTED***`)으로 제한했다.

## 교훈 및 예방책

### 1. git add 사용 전 확인
```bash
# 전체 추가 대신 선택적 추가
git add specific-files/
# 또는 
git add -p  # 변경사항을 하나씩 확인

# 절대 금지
git add .  # 모든 파일 무차별 추가
```

### 2. 사전 검증
커밋 전에 반드시 확인:
```bash
git status
git diff --cached
```

### 3. .gitignore 먼저
새 저장소 생성 시:
1. `.gitignore` 파일부터 작성
2. 민감한 파일 패턴 미리 등록
3. 첫 커밋에 `.gitignore` 포함

### 4. 정기적인 보안 점검
- 저장소에 민감한 파일이 없는지 주기적 확인
- 공개 저장소는 더욱 신중하게 관리
- API 키 로테이션 고려

## 결과

사고 대응 후:
- Git 히스토리에서 민감 정보 완전 제거 확인
- 보안 강화된 개발 환경 구축
- 향후 유사 사고 예방 체계 마련

보안 사고는 한 번의 실수로 발생하지만, 제대로 된 대응과 시스템 개선을 통해 더 안전한 개발 환경을 만들 수 있다는 것을 배웠다.

**핵심**: git add . 전에 한 번 더 생각하자! 🔒