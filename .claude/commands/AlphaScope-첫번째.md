---
description: 원격(태블릿) 작업 시작 준비 — git pull, 목업 서버 켜기
---

원격(태블릿 터널)에서 이어서 작업할 준비를 한다. 터널은 이미 연결된 상태이므로 터널 · tmux 는 건드리지 않는다. 아래 순서대로 실행하고 결과를 한국어로 짧게 보고한다. 묻지 말고 바로 진행한다.

1. **git pull**
   - `git pull` 을 현재 브랜치에서 실행한다. 새로 들어온 커밋은 `git log --oneline` 으로 한 줄씩 무엇인지 요약한다(파일 이름보다 내용 위주).
   - 커밋 안 된 로컬 파일(`git status --short`)이 있으면 그대로 두고, 충돌이 나면 멈추고 사용자에게 묻는다.

2. **목업 서버 켜기**
   - 먼저 `lsof -iTCP:8800 -sTCP:LISTEN` 으로 이미 켜져 있는지 본다. 켜져 있으면 주소만 다시 알린다.
   - 안 켜져 있으면 저장소 루트에서 `nohup python3 experiments/mock_server.py > <scratchpad>/mock_server.log 2>&1 &` 로 띄우고, `curl -s -o /dev/null -w "%{http_code}" http://localhost:8800/` 이 200 인지 확인한다.
   - 주소 둘을 알린다: http://gim-uhwans-Mac-mini.local:8800/ (즐겨찾기 추천) · 로그에 찍힌 와이파이 IP 주소.
   - 목업은 로컬 HTML 만 쓴다. 아티팩트로 올리지 않는다.

보고 형식: pull 로 들어온 커밋 목록 · 목업 서버 주소. 그 밖의 제안은 하지 않는다.

$ARGUMENTS
