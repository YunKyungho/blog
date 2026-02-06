# TOOLS.md - 도구 활용 가이드

## 🔧 OpenClaw Skills 시스템

OpenClaw은 MCP 대신 **Skills** 시스템 사용. ClawHub에서 설치/관리.

### 스킬 경로
- 번들: `/Users/yunkyeongho/.nvm/versions/node/v24.13.0/lib/node_modules/openclaw/skills/`
- 추가 설치: `/Users/yunkyeongho/skills/`
- 워크스페이스: `./skills/` (가장 높은 우선순위)

### 현재 활성 스킬
**번들 (주요)**
- `github` - GitHub CLI 연동 (gh)
- `notion` - Notion API (API 키 설정됨 ✅)
- `summarize` - URL/동영상/파일 요약/트랜스크립트
- `weather` - 날씨 조회
- `gemini` - Gemini CLI
- `obsidian` - Obsidian 볼트 작업
- `camsnap` - RTSP/ONVIF 카메라 캡처
- `nano-pdf` - PDF 편집
- `peekaboo` - macOS UI 자동화

**ClawHub 설치됨**
- `Humanizer` - AI 글 자연스럽게
- `claude-code-usage` - Claude Code 사용량 확인
- `gsd` - 프로젝트 플래닝/실행
- `self-reflection` - 자기 성찰/메모리
- `skillcraft` - 스킬 제작

## ⚠️ 설정 필요

### 1. Brave Search API (우선!)
```bash
openclaw configure --section web
```
또는 `~/.openclaw/openclaw.json`에:
```json
{
  "web": {
    "braveApiKey": "YOUR_BRAVE_API_KEY"
  }
}
```
→ 이거 설정하면 `web_search` 사용 가능

### 2. Gemini API (gemini 스킬용)
```bash
export GEMINI_API_KEY="your_key"
```

## 📦 추가 추천 스킬

### 생산성
- `apple-reminders` - 애플 미리알림 연동
- `apple-notes` - 애플 노트 연동
- `things-mac` - Things 3 연동

### 개발
- `tmux` - tmux 세션 관리
- `coding-agent` - Codex/Claude Code 연동

### 미디어
- `gifgrep` - GIF 검색
- `video-frames` - 비디오 프레임 추출
- `sag` - ElevenLabs TTS (음성 스토리텔링!)

---

*스킬 설치: `clawhub install <skill-name>`*
*스킬 목록: `clawhub search`*
