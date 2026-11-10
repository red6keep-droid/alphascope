#!/usr/bin/env bash
# jsDelivr 캐시를 지우고, CDN 이 내주는 파일이 방금 올린 파일과 같은지 확인한다.
#
#   jsd_purge.sh <gh-pages 안 경로> <로컬 파일>
#   예) jsd_purge.sh cards/report.json deploy-cards/cards/report.json
#
# 왜: gh-pages 푸시 직후 바로 퍼지하면 jsDelivr 가 아직 옛 커밋을 보고 옛 파일을 다시 붙잡는다
#     (s-maxage 12시간). 11-05 stocks.json, 11-10 미국 리포트 카드가 11-07 글로 연결된 일,
#     같은 날 07:00 표지 이미지 404 로 게시 실패.
# 어떻게: 기다렸다 퍼지 → 받아서 로컬 파일과 sha256 비교 → 다르면 다시. 최대 5번(약 2분).
# 끝내 다르면 exit 1 — 막을지 경고만 할지는 부르는 쪽이 정한다.
set -u

REPO_PATH="$1"
LOCAL="$2"
CDN="https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/${REPO_PATH}"
PURGE="https://purge.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/${REPO_PATH}"
TRIES=5

if [ ! -f "$LOCAL" ]; then
  echo "::warning::로컬 파일이 없습니다: $LOCAL"; exit 1
fi
WANT="$(sha256sum "$LOCAL" | cut -d' ' -f1)"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

sleep 10   # 푸시가 jsDelivr 에 보이기까지
for i in $(seq 1 "$TRIES"); do
  curl -sS -o /dev/null "$PURGE" || true
  sleep 5
  if curl -sS -f -o "$TMP" "$CDN" 2>/dev/null \
     && [ "$(sha256sum "$TMP" | cut -d' ' -f1)" = "$WANT" ]; then
    echo "jsDelivr 확인 완료 (${i}번째): ${REPO_PATH}"
    exit 0
  fi
  echo "jsDelivr 가 아직 옛 파일 또는 없음 (${i}/${TRIES}): ${REPO_PATH}"
  [ "$i" -lt "$TRIES" ] && sleep 15
done
echo "::warning::jsDelivr 가 ${TRIES}번 안에 새 파일을 내주지 않았습니다: ${REPO_PATH}"
exit 1
