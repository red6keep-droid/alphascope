#!/usr/bin/env bash
# 뉴스 분류 기록을 비공개 상태 저장소 news-records 브랜치에 쌓는다 (2026-11-24, experiments/news_records.py).
#
#   news_records_push.sh <source: quick|home> <처리 결과 json 경로>
#
# 환경: STATE_DEPLOY_KEY (없으면 건너뜀 — 경고만)
# 규칙(운영 지침 6절): 누적 기록은 부모 커밋을 잇는 일반 push 로만. 브랜치가 있는데 못 받으면 멈춘다(빈 폴더로 덮지 않게).
# 다른 실행과 같은 브랜치에 겹쳐 push 가 거부되면 받아서 다시 쌓고 최대 3번.
set -eu
SRC="$1"; STORE="$2"
if [ -z "${STATE_DEPLOY_KEY:-}" ]; then echo "::warning::STATE_DEPLOY_KEY 없음 — 뉴스 분류 기록 건너뜀"; exit 0; fi
mkdir -p ~/.ssh && printf '%s\n' "$STATE_DEPLOY_KEY" > ~/.ssh/news_rec_key && chmod 600 ~/.ssh/news_rec_key
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/news_rec_key -o IdentitiesOnly=yes"
REPO=git@github.com:red6keep-droid/alphascope-state.git
DIR=/tmp/news-records
HERE="$(pwd)"
STORE_ABS="$(cd "$(dirname "$STORE")" && pwd)/$(basename "$STORE")"

for try in 1 2 3; do
  rm -rf "$DIR"
  set +e; git ls-remote --exit-code --heads "$REPO" news-records >/dev/null; rc=$?; set -e
  if [ "$rc" = 0 ]; then
    git clone -q --depth 1 -b news-records "$REPO" "$DIR"
  elif [ "$rc" = 2 ]; then
    echo "news-records 브랜치 없음 — 처음"; mkdir -p "$DIR" && cd "$DIR" && git init -q && git checkout -q --orphan news-records && git remote add origin "$REPO" && cd "$HERE"
  else
    echo "::error::상태 저장소 확인 실패 ($rc)"; exit 1
  fi
  python "$HERE/experiments/news_records.py" --source "$SRC" --store "$STORE_ABS" --out "$DIR"
  cd "$DIR"
  git config user.name "github-actions[bot]" && git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add -A
  if git diff --cached --quiet; then echo "새 기록 없음"; cd "$HERE"; exit 0; fi
  git commit -q -m "news records $SRC $(date -u +%FT%H:%MZ) [skip ci]"
  if git push -q origin HEAD:news-records; then echo "기록 $(du -sh --exclude=.git records/$SRC | cut -f1)"; cd "$HERE"; exit 0; fi
  echo "push 거부 — 다시 받아서 ($try)"; cd "$HERE"; sleep $((try * 10))
done
echo "::error::news-records push 3번 실패"; exit 1
