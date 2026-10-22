# media-daily — 미디어 데일리 · 방송이 본 미국장

유튜브 수집기(`red9keep/yutb-sub`)가 Firestore `summaries` 에 남기는 영상별 요약(이슈 분류 · 방향 · 예상 밖 · 종목 · 발언자)으로
"방송들이 밤사이 미국장을 어떻게 봤나" 를 쓴다. 기획 · 결정 · 틀: [doc/기획/유튜브-자막-기사-검토.md](../../doc/기획/유튜브-자막-기사-검토.md) 7 · 11절.

| 파일 | 하는 일 | LLM |
|---|---|---|
| `collect.py` | Firestore `summaries` (edition = 묶음 날짜, 1차는 07:55 컷) → `output/materials.json`. 요약 문장 · 자막은 받지 않는다 | 없음 |
| `cluster.py` | 이슈 묶기(분류 + 소주제 낱말 · 종목 겹침) · 한국 연결 · 언급 종목 · 필수 채널 줄 · **데일리 중복 표시**(report-state records) → `output/media.json` + 우리 기록 줄 | 없음 |
| `narrate.py` | 머리 한 줄 + 묶음마다 한 문장 (fact_check · 금지어) → `output/narrative.json`. 실패하면 파이썬 문장 | `json-backup-first` 1회 |
| `render_html.py` | 본문 · 미리보기 · 목업 | 없음 |
| `publish.py` | 같은 날 글 있으면 갱신, 없으면 새 글. 재료 5건 미만이면 안 냄 | — |
| `main.py` | 전체. `--phase 1/2` · `--fixture`(가짜 재료) · `--no-llm` · `--state` · `--publish` | |

```
python main.py --fixture --no-llm --phase 2       # Firestore · LLM 없이 틀 확인 → output/media_mock.html
python main.py --phase 1                            # 실제 재료 (YTB_FIRESTORE_KEY 또는 gcloud 기본 인증 red6keep)
```

워크플로 `media-daily.yml`: Worker 가 KST 08:00(phase 1) · 10:15(phase 2) 에 건다. 게시는 저장소 변수 `MEDIA_PUBLISH=true` 부터 — 그 전엔 그림자 모드(artifact 로 본문 확인).
기록은 `media-state` 브랜치 `records/issues`(source=ytb, 영상 × 이슈) · `records/verdicts`(그날 상위 이슈).
