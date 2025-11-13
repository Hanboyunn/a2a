# 📦 Git 커밋 가이드

## 1. Git 설치 확인

Git이 설치되어 있는지 확인:
```bash
git --version
```

설치되어 있지 않다면:
- **Windows**: https://git-scm.com/download/win 에서 다운로드
- 설치 후 PowerShell을 재시작

## 2. Git 저장소 초기화 (처음 한 번만)

프로젝트 디렉토리에서:
```bash
git init
```

## 3. .gitignore 파일 생성

Python 프로젝트에 적합한 `.gitignore` 파일을 생성하세요:

```bash
# .gitignore 파일 내용
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# 로그 파일
*.log
logs/
monitor/*.jsonl
monitor/*.png

# 키 파일 (보안상 제외)
tools/*.pem
tools/private.pem
tools/public.pem

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# 임시 파일
*.tmp
*.bak
msg-captured.json
```

## 4. 파일 추가 및 커밋

### 기본 커밋 과정

```bash
# 1. 변경된 파일 확인
git status

# 2. 모든 파일 추가 (또는 특정 파일만)
git add .
# 또는
git add agents/ monitor/ common/ tools/ *.md *.py *.bat

# 3. 커밋 메시지와 함께 커밋
git commit -m "Initial commit: A2A 통신 시스템 구현"
```

### 단계별 커밋 예시

```bash
# 첫 번째 커밋: 기본 구조
git add agents/ common/ monitor/ tools/
git commit -m "feat: A2A 통신 시스템 기본 구조 구현"

# 두 번째 커밋: 문서 추가
git add *.md
git commit -m "docs: README, USAGE, ARCHITECTURE 문서 추가"

# 세 번째 커밋: 실행 스크립트
git add run_all_agents.* stop_agents.py
git commit -m "chore: agent 실행 및 종료 스크립트 추가"

# 네 번째 커밋: Trust Score 검증 기능
git add agents/base_agent.py
git commit -m "feat: High-risk action에 Trust Score 검증 추가"
```

## 5. 커밋 메시지 컨벤션

좋은 커밋 메시지 형식:
```
<type>: <subject>

<body> (선택사항)

<footer> (선택사항)
```

### Type 종류:
- `feat`: 새로운 기능 추가
- `fix`: 버그 수정
- `docs`: 문서 수정
- `style`: 코드 포맷팅 (기능 변경 없음)
- `refactor`: 코드 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드 설정, 패키지 관리 등

### 예시:
```bash
git commit -m "feat: Agent 간 직접 A2A 통신 구현"
git commit -m "fix: Trust Score 검증 로직 수정"
git commit -m "docs: ARCHITECTURE.md에 시스템 다이어그램 추가"
git commit -m "refactor: BaseAgentServer 클래스 구조 개선"
```

## 6. 원격 저장소 연결 (GitHub 등)

### GitHub에 새 저장소 생성 후:

```bash
# 원격 저장소 추가
git remote add origin https://github.com/사용자명/a2a2.git

# 브랜치 이름 확인/변경
git branch -M main

# 첫 푸시
git push -u origin main
```

### 이후 업데이트:
```bash
# 변경사항 커밋
git add .
git commit -m "커밋 메시지"

# 원격 저장소에 푸시
git push
```

## 7. 유용한 Git 명령어

```bash
# 변경사항 확인
git status

# 변경된 파일 내용 확인
git diff

# 커밋 히스토리 확인
git log --oneline

# 특정 파일만 커밋에서 제외
git reset HEAD 파일명

# 마지막 커밋 메시지 수정
git commit --amend -m "새로운 메시지"

# 커밋 취소 (파일은 유지)
git reset --soft HEAD~1

# 브랜치 생성
git checkout -b feature/new-feature

# 브랜치 목록
git branch
```

## 8. 현재 프로젝트 커밋 예시

```bash
# 1. Git 초기화 (아직 안 했다면)
git init

# 2. .gitignore 생성 (위 내용 사용)

# 3. 모든 파일 추가
git add .

# 4. 첫 커밋
git commit -m "feat: A2A Agent-to-Agent 통신 시스템 구현

- Agent 간 직접 통신 기능 구현
- Trust Score 기반 보안 검증
- 실시간 모니터링 대시보드
- High-risk action 차단 기능
- 문서화 (README, USAGE, ARCHITECTURE)"

# 5. GitHub에 푸시 (선택사항)
git remote add origin https://github.com/사용자명/a2a2.git
git push -u origin main
```

## 9. 주의사항

⚠️ **절대 커밋하지 말아야 할 것:**
- `tools/*.pem` (개인키/공개키 파일)
- `logs/` 디렉토리
- `__pycache__/` 디렉토리
- `.env` 파일 (환경 변수)
- 개인 정보가 포함된 파일

✅ **반드시 커밋해야 할 것:**
- 소스 코드 (`.py` 파일)
- 설정 파일 (`*.md`, `*.bat`, `*.sh`)
- 문서 파일
- `.gitignore` 파일

---

## 빠른 시작 (한 번에)

```bash
# Git 초기화
git init

# .gitignore 생성 (위 내용 복사)

# 모든 파일 추가
git add .

# 커밋
git commit -m "Initial commit: A2A 통신 시스템"

# GitHub에 푸시 (선택)
git remote add origin https://github.com/사용자명/a2a2.git
git push -u origin main
```

