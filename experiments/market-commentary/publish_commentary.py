"""AlphaScope 시황 해설 발행기 (2026-11-19 사용자 "커밋하고 발행기 만들어", 처음부터 공개 발행).

수집기가 쓴 글 columns/{날짜}-{am|pm}(status ready, format story — News-doc 23절)을 읽어 검사하고, 배너를 그려 Blogger 에 공개 발행한다.
블로그 AI 0 — 글은 수집기가 쓰고, 여기서는 읽기 · 검사 · 그리기 · 발행만.

두 단계 (워크플로 commentary.yml 이 사이에 배너를 gh-pages 에 올린다):
    python experiments/market-commentary/publish_commentary.py prepare --slot am     # 읽기 · 검사 · 배너 · 본문 → output/publish/
    python experiments/market-commentary/publish_commentary.py publish --slot am     # 이미 발행됐나 확인 → Blogger 공개 발행

시험 (Firestore · Blogger 없이):
    python experiments/market-commentary/publish_commentary.py prepare --slot am --date 2026-11-18 --column-json 글.json --no-ai

멈추는 규칙:
- 글이 없거나 status 가 ready 가 아니면(draft-test · skip) 조용히 끝 (exit 0, 수집기가 skip 이유를 남긴다).
- 발행 시각이 한참 지난 글은 내지 않는다(아침 12:00 · 저녁 23:59 KST 뒤) — 늦은 예비 실행이 지난 글을 뒤늦게 내지 않게(11-19 수집기 24절).
- 검사에 걸리면 내지 않고 exit 1 (워크플로가 Slack 으로 알린다) — 독자가 먼저 보지 않게.
- 배너는 실패해도 글은 나간다(banner.py 가 기본 배너로 대신, 그것도 실패하면 배너 없이).
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "..", "daily-report"))

KST = datetime.timezone(datetime.timedelta(hours=9))
RAW = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages"
OUT = os.path.join(BASE, "output", "publish")
LATE = {"am": (12, 0), "pm": (23, 59)}   # 이 시각(KST) 뒤엔 그 편을 내지 않는다

# 검사 낱말 — 수집기도 거르지만 독자에게 나가기 전 마지막 한 번 (요청 문서 12절 Q13 · Q14, 메모 no-buy-sell-labels-computed)
ADVICE = re.compile(r"(?:매수|매도|사|팔|담으)세요|(?:매수|매도|투자|손절)하(?:세요|십시오|라)|비중을? ?(?:늘리|줄이)(?:세요|십시오)|추천합니다|권합니다|권유합니다|지금이 기회")
BAD_TITLE = re.compile(r"(폭망|대폭락 임박|무조건|100% 확실|확정적 상승|떡상|떡락)")


def log(msg):
    print(f"[시황 발행] {msg}", flush=True)


def kst_now():
    return datetime.datetime.now(KST)


def _get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "alphascope"}), timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"못 받음 {url.rsplit('/', 1)[-1]} — {str(e)[:120]}")
        return None


def _exists(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "alphascope"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def read_column(key):
    """수집기 Firestore columns/{key} — media_feed 와 같은 읽기 전용 키(YTB_FIRESTORE_KEY). 읽기 1건."""
    import media_feed
    snap = media_feed._client().collection("columns").document(key).get()
    return snap.to_dict() if snap.exists else None


# ── 검사 ────────────────────────────────────────────────────────────

def _num(s):
    return float(s.replace(",", ""))


def check(col, briefing, day, slot):
    """문제 목록(빈 목록 = 통과). 숫자는 묶음에 있는 것만 대조한다(Q9) — 지수 줄 · 업종 표."""
    bad = []
    if col.get("format") != "story":
        bad.append(f"format {col.get('format')!r} — story 만 낸다")
    if col.get("date") != day or col.get("slot") != slot:
        bad.append(f"날짜 · 편이 다름 {col.get('date')}-{col.get('slot')}")
    for k in ("title", "overview", "market", "oneLine"):
        if not str(col.get(k) or "").strip():
            bad.append(f"빈 칸 {k}")
    if not [d for d in col.get("drivers") or [] if d.get("heading") and d.get("body")]:
        bad.append("장을 움직인 변수 없음")
    if not briefing:
        bad.append("묶음 파일 없음 — 지수 칸 · 숫자 대조 불가")

    texts = [("제목", col.get("title")), ("핵심 한 줄", col.get("oneLine")), ("요약", col.get("summary")),
             ("한눈에 보기", col.get("overview")), ("지수 · 업종 흐름", col.get("market"))]
    texts += [(f"변수 {i}", f'{d.get("heading", "")} {d.get("body", "")}') for i, d in enumerate(col.get("drivers") or [], 1)]
    texts += [("관전 포인트", " ".join(col.get("points") or []))]
    for where, t in texts:
        t = str(t or "")
        if ADVICE.search(t):
            bad.append(f"권유 말투 ({where}): {ADVICE.search(t).group(0)}")
    for where, t in texts[:2]:
        if BAD_TITLE.search(str(t or "")):
            bad.append(f"제목 금지 낱말 ({where}): {BAD_TITLE.search(t).group(0)}")

    close = (briefing or {}).get("close") or {}
    idx = {x["name"]: x for x in close.get("indices") or [] if x.get("chg_pct") is not None}
    line = str(col.get("indexLine") or "")
    for name, x in idx.items():
        m = re.search(re.escape(name) + r"\s+(\d+(?:\.\d+)?)%\s*(하락|상승)", line)
        if m:
            v = _num(m.group(1)) * (-1 if m.group(2) == "하락" else 1)
            if abs(v - x["chg_pct"]) > 0.011:
                bad.append(f"지수 숫자 다름 {name}: 글 {v:+.2f} · 묶음 {x['chg_pct']:+.2f}")
    sec = {x["name"]: x["chg_pct"] for x in close.get("sectors") or [] if x.get("chg_pct") is not None}
    for s in col.get("sectors") or []:
        if s.get("name") in sec and s.get("chg_pct") is not None and abs(s["chg_pct"] - sec[s["name"]]) > 0.011:
            bad.append(f"업종 숫자 다름 {s['name']}: 글 {s['chg_pct']:+.2f} · 묶음 {sec[s['name']]:+.2f}")
    return bad


# ── 단계 ────────────────────────────────────────────────────────────

def stage_prepare(a):
    import banner as BN
    from story_render import render
    day, slot = a.date, a.slot
    key = f"{day}-{slot}"
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):   # 지난 실행의 결과가 남아 다음 단계가 옛 글을 내지 않게
        p = os.path.join(OUT, f)
        if os.path.isfile(p):
            os.remove(p)

    if not a.column_json and os.environ.get("IS_SCHEDULED") == "true":   # 정시 · 예비 실행만 — 사람이 손으로 돌릴 땐 시각 상관없이 준비
        h, mi = LATE[slot]
        now = kst_now()
        if now.date().isoformat() == day and (now.hour, now.minute) > (h, mi):
            log(f"{key} — 발행 시각이 지나 내지 않음 ({h:02d}:{mi:02d} KST 뒤)")
            return 0
    col = json.load(open(a.column_json, encoding="utf-8")) if a.column_json else read_column(key)
    if not col:
        log(f"columns/{key} 없음 — 수집기가 아직 안 썼거나 skip 문서도 없음")
        return 0
    status = col.get("status") or ("ready" if a.column_json else "")
    if status != "ready":
        log(f"columns/{key} status {status!r} — 내지 않음" + (f" (이유: {col.get('reason')})" if col.get("reason") else ""))
        return 0
    log(f"columns/{key} 읽음 — rev {col.get('rev')} · 모델 {col.get('model')} · 요청 {col.get('calls')}")

    briefing = (json.load(open(a.briefing_json, encoding="utf-8")) if a.briefing_json
                else _get_json(f"{RAW}/briefing/{key}.json"))
    bad = check(col, briefing, day, slot)
    if bad:
        for b in bad:
            log(f"검사 걸림: {b}")
        json.dump({"key": key, "problems": bad}, open(os.path.join(OUT, "blocked.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return 1

    deploy = os.path.join(OUT, "deploy")
    ref = f"images/commentary-{key}.webp"
    if not a.column_json and _exists(f"{RAW}/{ref}"):   # 앞 실행(정시 · 예비 겹침)이 이미 그려 올렸으면 다시 그리지 않는다 — Workers AI 하루 1만 뉴런 지키기
        info = {"ref": None, "url": f"https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/{ref}", "source": "gh-pages 기존"}
        log(f"배너 이미 있음 — 다시 안 그림 ({ref})")
    else:
        info = BN.make(briefing, col, deploy, use_ai=not a.no_ai)   # deploy/images/commentary-{key}.webp
    banner_url = info["url"] if info else None
    alt = "AI 생성 이미지"
    if info:
        b = BN.banner_text(col)
        first = (b.get("titles") or [[]])[0] if b.get("titles") else (b.get("lines") or [])
        alt = "AI 생성 이미지 — " + " ".join(first) if first else alt
    title, html, meta = render(col, briefing, banner_url=banner_url, banner_alt=alt)
    post = {"key": key, "title": title, "labels": meta["labels"], "banner_ref": info["ref"] if info else None,
            "banner_source": info["source"] if info else None, "linked": meta["linked"], "model": col.get("model"), "rev": col.get("rev")}
    open(os.path.join(OUT, "body.html"), "w", encoding="utf-8").write(html)
    json.dump(post, open(os.path.join(OUT, "post.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if info and info.get("ref"):
        open(os.path.join(OUT, "banner_ref.txt"), "w").write(info["ref"])
    log(f"준비 끝 — {title} · 배너 {post['banner_source']} · 종목 링크 {', '.join(meta['linked']) or '없음'}")
    return 0


def already(creds, blog_id, key):
    """같은 편이 이미 나갔나 — `증시 시황` 라벨 최근 글 본문의 data-commentary 표시로 (제목은 수집기가 고쳐 쓰면 바뀔 수 있어 쓰지 않는다)."""
    import requests
    import publish_blogger as PB
    r = requests.get(f"{PB.BLOGGER_API}/blogs/{blog_id}/posts", params={"labels": "증시 시황", "maxResults": 6, "fetchBodies": "true", "fetchImages": "false"},
                     headers={"Authorization": f"Bearer {creds.token}"}, timeout=30)
    r.raise_for_status()
    for p in r.json().get("items", []):
        if f'data-commentary="{key}"' in (p.get("content") or ""):
            return p.get("url")
    return None


def stage_publish(a):
    import publish_blogger as PB
    pj = os.path.join(OUT, "post.json")
    if not os.path.exists(pj):
        log("낼 글 없음 (준비 단계에서 멈춤)")
        return 0
    post = json.load(open(pj, encoding="utf-8"))
    html = open(os.path.join(OUT, "body.html"), encoding="utf-8").read()
    if post.get("banner_ref") and a.banner_failed:   # CDN 확인 실패 — 깨진 그림 대신 배너 없이
        html = re.sub(r'<figure style="margin:0 0 16px;"><img [^>]*></figure>', "", html, count=1)
        log("배너 CDN 확인 실패 — 배너 없이 낸다")
    blog_url = os.environ.get("BLOG_URL", PB.DEFAULT_BLOG_URL)
    creds = PB._credentials()
    blog_id = PB._blog_id(creds, blog_url)
    url = already(creds, blog_id, post["key"])
    if url:
        log(f"{post['key']} 이미 발행됨 — {url}")
        return 0
    url = PB.publish(post["title"], html, labels=post["labels"], blog_url=blog_url)
    json.dump({**post, "url": url, "published_at": kst_now().isoformat(timespec="seconds")},
              open(os.path.join(OUT, "post_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"발행 끝 — {url}")
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prepare", "publish"])
    ap.add_argument("--slot", choices=["am", "pm"], required=True)
    ap.add_argument("--date", help="KST 날짜 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--column-json", help="시험: 수집기 글 JSON 파일 (Firestore 대신)")
    ap.add_argument("--briefing-json", help="시험: 묶음 파일 (gh-pages 대신)")
    ap.add_argument("--no-ai", action="store_true", help="배너를 AI 없이 기본 그림으로")
    ap.add_argument("--banner-failed", action="store_true", help="publish: 배너 CDN 확인 실패 — 배너 빼고 낸다")
    a = ap.parse_args()
    a.date = a.date or kst_now().date().isoformat()
    sys.exit(stage_prepare(a) if a.stage == "prepare" else stage_publish(a))


if __name__ == "__main__":
    main()
