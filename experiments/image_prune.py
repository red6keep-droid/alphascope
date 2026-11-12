"""오래된 날짜 그림 정리 — 30일 지난 그림은 글에서 그래프 칸을 빼고 gh-pages 에서 지운다 (2026-11-12 사용자: "30일 정도만 키워줘. 칸까지도 다 빼야지").

    python experiments/image_prune.py                # 미리 보기 — 고칠 글 · 지울 그림 목록만 (아무것도 안 바꿈)
    python experiments/image_prune.py --apply        # 글 고침(Blogger PATCH) → 그림 지움(gh-pages 커밋 · 푸시)
    python experiments/image_prune.py --days 30 --max-posts 100

- 대상 = 파일 이름에 날짜(YYYY-MM-DD)가 있는 그림만 (가격 그래프 · 데일리 커버 · 트럼프 반응). 로고 · 인물 사진 · radar-* 고정 이름은 건드리지 않는다.
  기준 = 이름의 날짜가 오늘(KST) − days 보다 이전.
- 글 = 공개 · 초안 · 예약 글과 고정 페이지 전부. 그 그림의 칸 = `<a href="그림">…</a>`(확대 링크 + 돋보기) 통째, 링크가 없으면 `<img>` 태그.
  본문 글은 그대로. 제목 · 라벨 · 발행일은 PATCH 라 그대로.
- 지우기 = 글 고치기가 다 성공한 그림만. 한 글이라도 실패하면 그 글이 쓰는 그림은 남긴다 (깨진 그림을 만들지 않게).
- kr-images 는 휘발성 브랜치(매일 덮어씀)라 지울 파일은 없고, 거기를 가리키는 지난 날짜 칸만 뺀다 (이미 404).
- 그림은 data/store 가격 자료로 다시 그릴 수 있어 기록 데이터가 아니다 (자료 보관 기준 = 재수집 가능).
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "experiments", "daily-report"))

IMG = re.compile(r"https://cdn\.jsdelivr\.net/gh/[^\"'\s]+?@(gh-pages|kr-images)/(images/[^\"'\s?]*?(20\d\d-\d\d-\d\d)[^\"'\s?]*)")
BRANCH = "gh-pages"


def cutoff(days):
    today = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date()
    return (today - dt.timedelta(days=days)).isoformat()


def api():
    import requests
    import publish_blogger as pb
    creds = pb._credentials()
    blog_id = pb._blog_id(creds, os.environ.get("BLOG_URL", pb.DEFAULT_BLOG_URL))
    return requests, f"{pb.BLOGGER_API}/blogs/{blog_id}", {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def all_items(requests, base, headers):
    out = []
    for kind, statuses in (("posts", ("LIVE", "DRAFT", "SCHEDULED")), ("pages", ("LIVE", "DRAFT"))):
        for st in statuses:
            tok = None
            while True:
                p = {"maxResults": 100, "fetchBodies": "true", "status": st}
                if tok:
                    p["pageToken"] = tok
                r = requests.get(f"{base}/{kind}", params=p, headers=headers, timeout=60)
                r.raise_for_status()
                d = r.json()
                for it in d.get("items", []):
                    it["_kind"] = kind
                    out.append(it)
                tok = d.get("nextPageToken")
                if not tok:
                    break
    return out


def strip_images(html, old):
    """old(그림 경로 집합)를 가리키는 칸을 뺀 본문, 뺀 칸 수."""
    n = 0

    def drop_a(m):
        nonlocal n
        g = IMG.search(m.group(1))
        if g and g.group(2) in old:
            n += 1
            return ""
        return m.group(0)
    html = re.sub(r'<a href="([^"]+)"[^>]*>(?:(?!<a[ >]).)*?</a>', drop_a, html, flags=re.S)   # 확대 링크 + 그림 + 돋보기 통째 (링크 안에 다른 링크 없음)

    def drop_img(m):
        nonlocal n
        g = IMG.search(m.group(0))
        if g and g.group(2) in old:
            n += 1
            return ""
        return m.group(0)
    html = re.sub(r"<img\b[^>]*>", drop_img, html)   # 링크 없이 놓인 그림(데일리 커버)
    return html, n


def branch_files(branch=BRANCH):
    subprocess.run(["git", "-C", ROOT, "fetch", "-q", "origin", branch], check=True)
    ls = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", f"origin/{branch}"], capture_output=True, text=True, check=True).stdout
    return [f for f in ls.splitlines() if f.startswith("images/")]


def delete_files(paths):
    """gh-pages 에서 paths 를 지우는 커밋 하나 · 푸시 (임시 worktree). 다른 워크플로가 먼저 밀었으면 rebase 뒤 다시."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = os.path.join(tmp, "ghp")
        subprocess.run(["git", "-C", ROOT, "worktree", "add", "-q", "--detach", wt, f"origin/{BRANCH}"], check=True)
        try:
            for i in range(0, len(paths), 200):
                subprocess.run(["git", "-C", wt, "rm", "-q", "--"] + paths[i:i + 200], check=True)
            subprocess.run(["git", "-C", wt, "commit", "-q", "-m", f"오래된 날짜 그림 {len(paths)}개 정리 (image_prune.py) [skip ci]"], check=True)
            for _ in range(3):
                if subprocess.run(["git", "-C", wt, "push", "-q", "origin", f"HEAD:{BRANCH}"]).returncode == 0:
                    return True
                subprocess.run(["git", "-C", wt, "pull", "-q", "--rebase", "origin", BRANCH], check=True)
            return False
        finally:
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", wt])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-posts", type=int, default=150, help="한 실행에 고치는 글 수 상한")
    a = ap.parse_args()
    cut = cutoff(a.days)
    print(f"[정리] 기준 {cut} 이전 날짜 그림 ({a.days}일) · {'적용' if a.apply else '미리 보기'}")

    have = {b: set(branch_files(b)) for b in ("gh-pages", "kr-images")}   # 이미 없는 그림(휘발성 kr-images 의 지난 날짜 등)은 날짜와 상관없이 칸을 뺀다 — 지금 깨져 보이는 칸
    requests, base, headers = api()
    items = all_items(requests, base, headers)
    old_refs = {}   # 경로 → 브랜치
    plan = []       # (글, 새 본문, 뺀 칸 수)
    for it in items:
        refs = {(m.group(1), m.group(2)) for m in IMG.finditer(it.get("content", "")) if m.group(3) < cut or m.group(2) not in have[m.group(1)]}
        if not refs:
            continue
        for b, p in refs:
            old_refs[p] = b
        new, n = strip_images(it["content"], {p for _, p in refs})
        left = {m.group(2) for m in IMG.finditer(new) if m.group(3) < cut or m.group(2) not in have[m.group(1)]}
        plan.append((it, new, n, left))

    files = [f for f in have[BRANCH] if (m := re.search(r"20\d\d-\d\d-\d\d", f)) and m.group(0) < cut]
    print(f"[정리] 고칠 글 {len(plan)}개 · 뺄 칸 {sum(n for _, _, n, _ in plan)}개 · 지울 gh-pages 그림 {len(files)}개")
    for it, _, n, left in sorted(plan, key=lambda x: x[0].get("published", "")):
        print(f"  {it.get('published', '')[:10]} {it['_kind'][:-1]:4} 칸 {n}{' · 남은 참조 ' + str(len(left)) if left else ''}  {it['title'][:50]}")
    if any(left for *_, left in plan):
        print("[정리] ⚠ 칸 모양을 몰라 못 뺀 참조가 있다 — 그 그림은 지우지 않는다")
    if not a.apply:
        print("[정리] 미리 보기 끝 — 적용은 --apply")
        return

    failed = set()
    for k, (it, new, n, left) in enumerate(plan):
        if k >= a.max_posts:
            failed |= {p for p in old_refs}   # 이번에 못 고친 글이 남으면 이번엔 지우지 않는다
            print(f"[정리] 상한 {a.max_posts}개 — 나머지는 다음 실행")
            break
        r = requests.patch(f"{base}/{it['_kind']}/{it['id']}", json={"content": new}, headers=headers, timeout=60)
        if r.status_code != 200:
            failed |= {m.group(2) for m in IMG.finditer(it["content"])}
            print(f"[정리] 글 고침 실패 {r.status_code} {it['title'][:40]}")
        failed |= left
    keep = [f for f in files if f in failed]
    gone = [f for f in files if f not in failed]
    print(f"[정리] 글 고침 끝 · 그림 지움 {len(gone)}개 · 남김 {len(keep)}개")
    if gone and not delete_files(gone):
        print("[정리] gh-pages 푸시 실패 — 다음 실행에서 다시")
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass
    main()
