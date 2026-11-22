#!/bin/sh
# 로컬 시험 한 번에: 로컬 D1 · R2 비우기 → 표 만들기 → wrangler dev(시험 모드) → test/run.mjs → 끄기
set -e
cd "$(dirname "$0")/.."
rm -rf .wrangler/state
printf 'TEST_MODE=1\nADMIN_KEY=test-admin-key-0123456789abcdef0123456789\n' > .dev.vars
npx wrangler d1 execute newfact-board --local --file schema.sql >/dev/null
npx wrangler dev --local --port 8787 >/tmp/newfact-board-dev.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; rm -f .dev.vars' EXIT
for i in $(seq 1 60); do curl -sf http://127.0.0.1:8787/v1/health >/dev/null 2>&1 && break; sleep 1; done
node test/run.mjs
