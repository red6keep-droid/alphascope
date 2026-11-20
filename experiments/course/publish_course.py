"""주식 공부 글 발행 — 문서 저장소 초안(doc/기획/강좌/*.md) → Blogger 글 (2026-11-15 사용자: 정식 등록).

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
}


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
    """초안마다 (제목, 본문). urls = {파일 이름: 글 주소} — 없는 편은 # (다음 바퀴에서 채움)."""
    RC.IMG_BASE = IMG_BASE
    links = {os.path.basename(f): urls.get(os.path.basename(f), "#") for f in files}
    out = []
    for k, f in enumerate(files):
        nxt = links[os.path.basename(files[k + 1])] if k + 1 < len(files) else "#"
        title, body = RC.render(open(f, encoding="utf-8").read(), links, nxt)
        body = (RC.share_tag() + f'<span data-head-label="{RC.HEAD_LABEL}" data-head-sub="{RC.HEAD_SUB}" hidden></span><span data-list-url="{RC.LIST_URL}" data-nav="back" hidden></span>'
                + RC.title_block(title) + body)
        series, _, ep = title.partition(" — ")
        post_title = ep if " — " in title and not ep.startswith("들어가며") else series.split(" #")[0]
        assert "data:image" not in body, "목업 그림(data URI)이 남았다"
        out.append((os.path.basename(f), post_title, body))
    return out


def main(dry, published_only=False):
    _env()
    src = next((p for p in RC._SRC_CANDIDATES if os.path.isdir(p)), None)   # RC.SRC 는 명령 인자(--dry)를 폴더로 읽는다 — 여기선 후보 폴더만
    if not src:
        sys.exit(f"초안 폴더 없음: {RC._SRC_CANDIDATES}")
    files = sorted(glob.glob(os.path.join(src, "*.md")))
    if published_only:   # 이미 나간 편만 다시 그려 고쳐 쓴다 — 새 편은 올리지 않음(다음 편 카드는 `준비 중` 그대로) (2026-11-20 사용자: 바뀐 모양을 과거 글에 일괄 적용)
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
    urls = {}
    for name, t, body in posts:   # 1바퀴: 없으면 올린다
        found = NP.find_post_id(t, max_results=50)
        if found:
            urls[name] = found["url"]
            print(f"[있음] {t} → {found['url']}")
        elif published_only:
            sys.exit(f"이미 나간 편인데 Blogger 에서 못 찾음: {t} — 제목이 바뀌었는지 확인")
        else:
            urls[name] = PB.publish(t, body, labels=LABELS, slug_title=SLUGS[name])
    for name, t, body in build(files, urls):   # 2바퀴: 편끼리 링크를 채워 전부 갱신
        found = NP.find_post_id(t, max_results=50)
        url = NP.update_post(found["id"], t, body, LABELS)
        print(f"[갱신] {t} → {url}")
    if published_only:
        return
    with open(os.path.join(HERE, "published.json"), "w", encoding="utf-8") as f:   # 목록 페이지(render_list.py)가 읽는다 — 나온 편 = 링크
        json.dump(urls, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--images" in sys.argv:
        sys.exit(0 if upload_images() else 1)
    main("--dry" in sys.argv, "--published-only" in sys.argv)
