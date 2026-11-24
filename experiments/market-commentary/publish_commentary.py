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
# 저녁 편은 그날 이 시각(KST) 뒤에 저장된 글만 낸다 (2026-11-20 사용자, News-doc 33절) — 한국장 마감 재료 없이 낮에 미리 써진 rev
# (11-20 12:58 rev 1)가 17:00 · 21:00 에 나가지 않게. 수집기는 저장할 때마다 createdAt 을 서버 시각으로 새로 찍는다(= 그 rev 를 쓴 시각)
PM_MIN_WRITTEN = (16, 30)

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


def read_lists(slot):
    """종목 모아보기 목록 파일(간단 종목 실행이 매일 올림) — 종목 줄 가격 · 로고 · 업종 · 주소. 읽는 순서 = stock_lists.js 와 같다. 실패해도 글은 낸다(배지 · 가격 없이)."""
    m = "us" if slot == "am" else "kr"
    for url in (f"https://alpha-scope.pages.dev/{m}/_lists.json",
                f"https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@quick-{m}/{m}/_lists.json"):
        try:
            rows = (_get_json(url) or {}).get("rows") or []
            if rows:
                log(f"종목 목록 {len(rows)}줄 — {url}")
                return {str(r.get("t") or "").upper(): r for r in rows}
        except Exception as e:  # noqa: BLE001
            log(f"종목 목록 못 받음 {url}: {e}")
    return {}


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
    for k in ("title", "overview"):   # market · oneLine 은 화면에 쓰지 않는다 (2026-11-19 새 틀: 숫자는 묶음 표 · 핵심 한 줄은 머리글과 같은 말) — 비어도 낸다
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
        # 그 편 날짜의 마감 시각과 비교 — 자정을 넘겨 온 예비(11-19 저녁 예비가 11-20 05:53)도 막는다
        deadline = datetime.datetime.fromisoformat(day).replace(hour=h, minute=mi, tzinfo=KST)
        if kst_now() > deadline:
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
    written = col.get("createdAt")
    if isinstance(written, datetime.datetime) and written.tzinfo is None:
        written = written.replace(tzinfo=datetime.timezone.utc)   # Firestore 시각은 UTC
    log(f"columns/{key} 읽음 — rev {col.get('rev')} · 저장 {written.astimezone(KST):%m-%d %H:%M} KST" if isinstance(written, datetime.datetime)
        else f"columns/{key} 읽음 — rev {col.get('rev')} · 저장 시각 없음")
    log(f"  모델 {col.get('model')} · 요청 {col.get('calls')}")
    if slot == "pm" and not a.column_json and os.environ.get("IS_SCHEDULED") == "true":   # 정시 · 예비만 — 사람이 손으로 돌릴 땐 막지 않음
        h, mi = PM_MIN_WRITTEN
        floor = datetime.datetime.fromisoformat(day).replace(hour=h, minute=mi, tzinfo=KST)
        if not isinstance(written, datetime.datetime) or written < floor:
            log(f"{key} — {h:02d}:{mi:02d} KST 전에 저장된 글(rev {col.get('rev')})이라 내지 않음 · 마감 뒤 수집기 1차를 기다림")
            return 0

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
    if not a.column_json and not a.redraw and _exists(f"{RAW}/{ref}"):   # 앞 실행(정시 · 예비 겹침)이 이미 그려 올렸으면 다시 그리지 않는다 — Workers AI 하루 1만 뉴런 지키기
        info = {"ref": None, "url": f"https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/{ref}", "source": "gh-pages 기존"}
        log(f"배너 이미 있음 — 다시 안 그림 ({ref})")
    else:
        info = BN.make(briefing, col, deploy, use_ai=not a.no_ai)   # deploy/images/commentary-{key}.webp
    banner_url = info["url"] if info else None
    if info:   # 글에 넣는 배너 = 그림 내용 해시가 든 이름(images/commentary-날짜-편-해시.webp) — 같은 이름에 다시 그리면 jsDelivr 가 브랜치 주소를
        # 몇 시간 붙잡아 옛 그림을 내주고(11-19 다시 그리기 때 확인 실패 → 배너 없이 나감), 브라우저도 7일 저장. 해시 이름은 늘 처음 보는 주소라 바로 새 그림.
        # 날짜 이름(commentary-날짜-편.webp)은 홈 시황 배너가 쓰므로 그대로 둔다. 이름에 날짜가 있어 30일 정리(image_prune) 대상 (2026-11-19 사용자)
        try:
            import hashlib
            raw = open(info["path"], "rb").read() if info.get("path") else urllib.request.urlopen(f"{RAW}/{ref}", timeout=30).read()
            vref = f"images/commentary-{key}-{hashlib.md5(raw).hexdigest()[:8]}.webp"
            if info.get("path") or not _exists(f"{RAW}/{vref}"):   # 이번에 그렸거나 해시 이름이 아직 없으면 올릴 묶음(deploy)에 넣는다 → 워크플로가 올리고 jsDelivr 확인
                os.makedirs(os.path.join(deploy, "images"), exist_ok=True)
                open(os.path.join(deploy, vref), "wb").write(raw)
                info["ref"] = vref
            banner_url = f"https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/{vref}"
        except Exception as e:  # noqa: BLE001 — 해시 이름을 못 만들면 날짜 이름 그대로
            log(f"배너 해시 이름 못 만듦: {str(e)[:80]}")
    alt = "AI 생성 이미지"
    if info:
        b = BN.banner_text(col)
        first = (b.get("titles") or [[]])[0] if b.get("titles") else (b.get("lines") or [])
        alt = "AI 생성 이미지 — " + " ".join(first) if first else alt
    if slot == "pm" and briefing and (briefing.get("close") or {}).get("sectors_basis") != "lists":
        # 묶음을 만들 때(16:40 무렵) 목록 파일이 아직 없었으면 지금 목록 파일로 업종 표를 다시 셈 — 업종 탭과 같은 숫자 (2026-11-20 사용자).
        # 검사(check)는 위에서 수집기 글과 묶음 원래 숫자로 이미 끝났다. 여기선 화면 표만 바꾼다
        import build_briefing as BB
        secs = BB.sectors_from_lists(BB.read_lists_doc("kr"), briefing.get("trade_date"))
        if secs:
            briefing["close"]["sectors"], briefing["close"]["sectors_basis"] = secs, "lists"
            log(f"업종 표 = 종목 모아보기 목록 전체 평균 ({len(secs)}개)")
        else:
            log("업종 표 = 묶음 그대로(대형주 묶음 평균) — 그날 목록 파일 없음")
    lists_live = True   # 종목 모아보기 페이지는 11-19 발행 뒤 늘 있다 — 확인 요청을 하지 않는다(GitHub 실행기에서는 블로그가 확인 요청에 정상 답을 주지 않아 '없음'으로 잘못 판단, 11-19 첫 발행)
    from story_render import MOOD_BASE
    mood_ok = _exists(MOOD_BASE + "market-up.webp")   # 장 분위기 아이콘이 gh-pages 에 아직 없으면 아이콘 없이 낸다(깨진 그림 대신)
    title, html, meta = render(col, briefing, banner_url=banner_url, banner_alt=alt, lists_live=lists_live, lists=read_lists(slot),
                               mood_base=MOOD_BASE if mood_ok else None)
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
            return p
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
        html = re.sub(r'<figure[^>]*><img [^>]*></figure>', "", html, count=1)   # 배너 figure 모양이 바뀌어도(화면 끝까지 data-bleed) 지워지게
        log("배너 CDN 확인 실패 — 배너 없이 낸다")
    blog_url = os.environ.get("BLOG_URL", PB.DEFAULT_BLOG_URL)
    creds = PB._credentials()
    blog_id = PB._blog_id(creds, blog_url)
    old = already(creds, blog_id, post["key"])
    newer = False
    if old:   # 수집기 2차(rev 가 오름) — 저녁 편 17:00 1차 뒤 21:00 에 저녁 방송을 보탠 rev 2 (2026-11-20 사용자, News-doc 31절)
        m = re.search(r'data-rev="(\d+)"', old.get("content") or "")
        old_rev = int(m.group(1)) if m else None
        try:
            new_rev = int(post.get("rev"))
        except (TypeError, ValueError):
            new_rev = None
        newer = old_rev is not None and new_rev is not None and new_rev > old_rev   # 표시 없는 옛 글은 고치지 않는다
        if newer:
            log(f"{post['key']} rev {old_rev} → {new_rev} — 같은 주소에 고쳐 쓴다")
    if old and not a.replace and not newer:
        log(f"{post['key']} 이미 발행됨 (rev 같음) — {old.get('url')}")
        return 0
    if old:   # 고쳐 쓰기 (rev 가 올랐거나 사람이 --replace 로 부를 때) — 주소 · 라벨은 그대로, 제목 · 본문만 새로
        r = PB._write("put", f"{PB.BLOGGER_API}/blogs/{blog_id}/posts/{old['id']}",
                      headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
                      json={"kind": "blogger#post", "id": old["id"], "title": post["title"], "content": html, "labels": old.get("labels") or post["labels"]}, timeout=60)
        r.raise_for_status()
        log(f"{post['key']} 고쳐 씀 — {old.get('url')}")
        return 0
    try:
        url = PB.publish(post["title"], html, labels=post["labels"], blog_url=blog_url)
    except Exception as ex:  # noqa: BLE001
        # 429 = Blogger 가 잠시 새 글을 막은 것(11-24 종목 페이지 몰아 만들기 뒤 4시간 넘게) — 워크플로가 30분 뒤 다시 부른다
        if getattr(getattr(ex, "response", None), "status_code", None) == 429:
            log("Blogger 429 — 새 글을 잠시 막음, 다시 시도 대기 (종료 코드 75)")
            return 75
        raise
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
    ap.add_argument("--redraw", action="store_true", help="prepare: 그 편 배너가 gh-pages 에 있어도 다시 그린다(사람이 손으로 부를 때만, Workers AI 1장)")
    ap.add_argument("--replace", action="store_true", help="publish: 같은 편이 이미 나갔으면 그 글을 고쳐 쓴다(사람이 손으로 부를 때만)")
    a = ap.parse_args()
    a.date = a.date or kst_now().date().isoformat()
    sys.exit(stage_prepare(a) if a.stage == "prepare" else stage_publish(a))


if __name__ == "__main__":
    main()
