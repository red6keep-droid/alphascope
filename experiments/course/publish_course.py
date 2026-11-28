"""주식 공부 글 발행 — 문서 저장소 초안(doc/기획/강좌/*.md) → Blogger 글.

    .venv/bin/python experiments/course/publish_course.py --images     # 캐릭터 · 아이콘 · 홈 배너 → gh-pages images/study/ (바뀐 것만 커밋 · 푸시)
    .venv/bin/python experiments/course/publish_course.py --dry        # 올릴 제목 · 주소 · 그림 주소만 확인
    .venv/bin/python experiments/course/publish_course.py              # 글 게시 · 갱신 (제목이 같으면 고쳐 씀)
    .venv/bin/python experiments/course/publish_course.py --published-only [--dry]   # 이미 나간 편만 다시 그려 고쳐 씀(새 편 안 올림) — 모양 · 이름 바뀐 뒤 일괄 적용

- 글 제목 = 편 제목(검색어), 0편은 연재 이름. 머리 줄은 테마가 `주식 공부`(data-head-label)로 보인다.
- 주소 = 처음 올릴 때 영문 이름(SLUGS)으로 정한 뒤 한글 제목으로(publish_blogger.publish slug_title) — 검색 노출 규칙.
- 다음 편 카드 · 편끼리 링크는 다른 편 주소가 있어야 해서 두 바퀴: 1) 없으면 올림 2) 모든 주소를 알고 다시 그려 전부 갱신.
- 라벨 `주식 공부` 하나. AI · 수집 0. Blogger 쓰기 = 편 수 × 2 이하(손으로 실행할 때만).
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "experiments", "daily-report"))
sys.path.insert(0, os.path.join(ROOT, "experiments", "nvda-report"))

import render_course as RC  # noqa: E402

BRANCH = "gh-pages"
IMG_DIR = "images/study"
IMG_BASE = f"https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@{BRANCH}/{IMG_DIR}/"
LABELS = ["주식 공부"]
SLUGS = {   # 초안 파일 이름 → 영문 주소 이름 (한 번 정하면 바꾸지 않는다 — 주소가 바뀌면 검색 · 공유 링크가 끊긴다)
    "착각-00-들어가며.md": "stock myths for beginners intro",
    "착각-01-실적.md": "stock myths 01 good earnings stock falls",
    "착각-02-물림.md": "stock myths 02 how long underwater after buying",
    "착각-03-공포매도.md": "stock myths 03 selling on big drop days",
    "착각-04-되사기.md": "stock myths 04 buying back at sell price",
    "착각-05-분할매수.md": "stock myths 05 waiting for the dip when buying monthly",
    "착각-06-과열.md": "stock myths 06 overbought does it fall",
    "착각-07-볼린저.md": "stock myths 07 bollinger lower band not bottom",
    "착각-08-골든크로스.md": "stock myths 08 golden cross dead cross",
    "착각-09-파동.md": "stock myths 09 waves appear even in coin flips",
    "착각-10-마치며.md": "stock myths 10 indicators measure size not direction",
    "착각-기준.md": "stock myths how we check 15 stocks two periods",   # 기준 페이지(편 번호 없음, 2026-11-21)
}
# 입문 과정 `주식 처음 시작하기`(도토리 숲 이야기, 2026-11-22) — `--intro` 로 실행. 초안 = 강좌-입문/, 그림 = Pages newfact-img(img_store.py 로 먼저 올림)
INTRO_SRC = [os.path.expanduser("~/Desktop/alphascope-docs/doc/기획/강좌-입문"), "D:/alphascope-docs/doc/기획/강좌-입문"]
INTRO_IMG_BASE = "https://img.newfact.app/study/"
INTRO_SLUGS = {
    "입문-01-주식이란.md": "stock basics 01 what is a stock and why price changes",
    "입문-02-얼마로-시작.md": "stock basics 02 how much money to start and what if price falls",
    "입문-03-계좌와-주문.md": "stock basics 03 how to open an account and place an order",
    "입문-04-화면-읽기.md": "stock basics 04 how to read numbers and colors on the app",
    "입문-05-수수료와-세금.md": "stock basics 05 fees and taxes when buying and selling",
    "입문-06-종목과-시장.md": "stock basics 06 single stock or the whole market",
    "입문-07-한국과-미국.md": "stock basics 07 korean stocks versus us stocks",
    "입문-08-회사-소식.md": "stock basics 08 what news a company sends to shareholders",
    "입문-09-금리와-환율.md": "stock basics 09 why news explains stocks with interest rates and exchange rates",
    "입문-10-비싼가-싼가.md": "stock basics 10 is this stock expensive or cheap",
    "입문-11-차트와-지표.md": "stock basics 11 what chart lines and indicators tell you",
    "입문-12-정보와-리딩방.md": "stock basics 12 where to get information and whom to trust",
}
ORDER_RE = r"착각-\d"


def use_intro():
    """입문 과정으로 바꿔 끼움 — 초안 폴더 · 주소 이름 · 다음 편 순서 · 그림 주소. 기준 페이지 조각(팝업)은 없음."""
    global SLUGS, IMG_BASE, ORDER_RE
    SLUGS, IMG_BASE, ORDER_RE = INTRO_SLUGS, INTRO_IMG_BASE, r"입문-\d"
    RC._SRC_CANDIDATES = INTRO_SRC
    RC.SRC = next((p for p in INTRO_SRC if os.path.isdir(p)), INTRO_SRC[-1])


def _env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.split(" #")[0].strip().strip('"').strip("'"))


def upload_images():
    """chars/*.webp · icons/*.webp · banner/*.webp(홈 배너 · 목록 맨 위 그림) → gh-pages images/study/ — 내용이 같으면 커밋 안 함."""
    src = sorted(glob.glob(os.path.join(HERE, "chars", "*.webp")) + glob.glob(os.path.join(HERE, "icons", "*.webp"))
                 + glob.glob(os.path.join(HERE, "banner", "*.webp")) + glob.glob(os.path.join(HERE, "banner", "share_*.jpg")))   # share_*.jpg = 공유 썸네일(카카오톡 · og:image, 2026-11-15)
    subprocess.run(["git", "-C", ROOT, "fetch", "-q", "origin", BRANCH], check=True)
    with tempfile.TemporaryDirectory() as tmp:
        wt = os.path.join(tmp, "ghp")
        subprocess.run(["git", "-C", ROOT, "worktree", "add", "-q", "--detach", wt, f"origin/{BRANCH}"], check=True)
        try:
            os.makedirs(os.path.join(wt, IMG_DIR), exist_ok=True)
            for f in src:
                shutil.copyfile(f, os.path.join(wt, IMG_DIR, os.path.basename(f)))
            subprocess.run(["git", "-C", wt, "add", IMG_DIR], check=True)
            if subprocess.run(["git", "-C", wt, "diff", "--cached", "--quiet"]).returncode == 0:
                print(f"[그림] 바뀐 것 없음 ({len(src)}개)")
                return True
            subprocess.run(["git", "-C", wt, "commit", "-q", "-m", f"주식 공부 그림 {len(src)}개 (publish_course.py) [skip ci]"], check=True)
            for _ in range(3):
                if subprocess.run(["git", "-C", wt, "push", "-q", "origin", f"HEAD:{BRANCH}"]).returncode == 0:
                    print(f"[그림] gh-pages {IMG_DIR}/ 에 {len(src)}개 올림 → {IMG_BASE}")
                    return True
                subprocess.run(["git", "-C", wt, "pull", "-q", "--rebase", "origin", BRANCH], check=True)
            return False
        finally:
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", wt])


def build(files, urls):
    """초안마다 (제목, 본문). urls = {파일 이름: 글 주소} — 없는 편은 # (다음 바퀴에서 채움).
    목업(render_course.main)과 같은 순서: 기준 페이지 조각 → 각 편 본문 팝업(쓴 조각만 글 끝에 숨은 글) · 기준 페이지는 다음 편 사슬에 안 낌 (2026-11-21)."""
    import re
    RC.IMG_BASE = IMG_BASE
    names = sorted(set(SLUGS) | {os.path.basename(f) for f in files})
    links = {n: urls.get(n, "#") for n in names}
    pieces = RC.load_pieces(links)
    order = sorted(n for n in SLUGS if re.match(ORDER_RE, n))   # 다음 편 = 번호 순 다음 편(이번에 안 올리는 편이어도 주소가 있으면 연결)
    out = []
    for f in files:
        name = os.path.basename(f)
        k = order.index(name) if name in order else -1
        nxt = links.get(order[k + 1], "#") if 0 <= k < len(order) - 1 else "#"
        RC.CUR_FILE = name
        is_basis = name == RC.PIECE_SRC
        used = set()
        title, body = RC.render(open(f, encoding="utf-8").read(), links, nxt, pieces=None if is_basis else pieces, used=used)
        body += RC.piece_bodies(pieces, used, links)
        body = (RC.share_tag() + f'<span data-head-label="{RC.HEAD_LABEL}" data-head-sub="{RC.HEAD_SUB}" hidden></span><span data-list-url="{RC.LIST_URL}" data-nav="back" hidden></span>'
                + RC.title_block(title) + body)
        series, _, ep = title.partition(" — ")
        post_title = ep if " — " in title and not ep.startswith("들어가며") else series.split(" #")[0]
        assert "data:image" not in body, "목업 그림(data URI)이 남았다"
        out.append((name, post_title, body))
    return out


def _find(NP, t, url=None):
    """같은 제목 글 — 최근 50건 안에서, 없으면 발행 때 적어 둔 주소로(posts/bypath). 뉴스 글이 많아 지난 편은 50건 밖으로 밀린다."""
    found = NP.find_post_id(t, max_results=50)
    if found or not url:
        return found
    import urllib.parse
    requests, base, headers = NP._api()
    r = requests.get(f"{base}/posts/bypath", params={"path": urllib.parse.urlparse(url).path, "fetchBodies": "false"}, headers=headers, timeout=30)
    return {"id": r.json()["id"], "url": r.json().get("url")} if r.ok else None


def main(dry, published_only=False):
    _env()
    src = next((p for p in RC._SRC_CANDIDATES if os.path.isdir(p)), None)   # RC.SRC 는 명령 인자(--dry)를 폴더로 읽는다 — 여기선 후보 폴더만
    if not src:
        sys.exit(f"초안 폴더 없음: {RC._SRC_CANDIDATES}")
    files = sorted(sorted(glob.glob(os.path.join(src, "*.md"))), key=lambda f: os.path.basename(f) != RC.PIECE_SRC)   # 기준 페이지 먼저 — 모든 편 팝업 끝 링크가 이 페이지로 간다
    if published_only:   # 이미 나간 편만 다시 그려 고쳐 쓴다 — 새 편은 올리지 않음(다음 편 카드는 `준비 중` 그대로)
        done = json.load(open(os.path.join(HERE, "published.json"), encoding="utf-8"))
        files = [f for f in files if os.path.basename(f) in done]
    missing = [os.path.basename(f) for f in files if os.path.basename(f) not in SLUGS]
    if missing:
        sys.exit(f"SLUGS 에 영문 주소 이름이 없음: {missing}")
    import publish_blogger as PB
    import publish as NP   # nvda-report: find_post · update_post (같은 제목 글 고쳐 쓰기)
    posts = build(files, {})
    if dry:
        for name, t, body in posts:
            print(f"[dry] {name} → 제목 `{t}` · 주소 이름 `{SLUGS[name]}` · 본문 {len(body) // 1024}KB · 그림 {body.count(IMG_BASE)}개")
        return
    pj = os.path.join(HERE, "published.json")
    urls = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else {}
    blocked = False
    for name, t, body in posts:   # 1바퀴: 없으면 올린다 — 새 글이 거절되면(429 등) 거기서 새 글만 멈추고, 올라간 편까지 2바퀴 (2026-11-21: 11-20 4편 429)
        found = _find(NP, t, urls.get(name))
        if found:
            urls[name] = found["url"]
            print(f"[있음] {t} → {found['url']}")
        elif published_only:
            sys.exit(f"이미 나간 편인데 Blogger 에서 못 찾음: {t} — 제목이 바뀌었는지 확인")
        elif blocked:
            print(f"[다음에] {t} — 새 글 거절 뒤라 이번엔 안 올림")
        else:
            try:
                urls[name] = PB.publish(t, body, labels=LABELS, slug_title=SLUGS[name])
                print(f"[새 글] {t} → {urls[name]}")
                json.dump(urls, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)   # 목록 페이지(render_list.py)가 읽는다 — 나온 편 = 링크
                time.sleep(20)
            except Exception as e:   # noqa: BLE001
                blocked = True
                print(f"[거절] {t} — {e}")
    done = [f for f in files if os.path.basename(f) in urls]
    for name, t, body in build(done, urls):   # 2바퀴: 편끼리 링크를 채워 올라간 편 전부 갱신
        found = _find(NP, t, urls.get(name))
        url = NP.update_post(found["id"], t, body, LABELS)
        print(f"[갱신] {t} → {url}")
    json.dump(urls, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if blocked:
        sys.exit("새 글 일부가 거절됨 — 내일 같은 명령을 다시 실행하면 남은 편부터 올린다")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--images" in sys.argv:
        sys.exit(0 if upload_images() else 1)
    if "--intro" in sys.argv:
        use_intro()
    main("--dry" in sys.argv, "--published-only" in sys.argv)
