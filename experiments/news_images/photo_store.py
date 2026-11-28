"""뉴스 글 자료 사진 저장소 — Cloudflare Pages 프로젝트 `newfact-photo` (주소 https://photo.newfact.app, 예비 https://newfact-photo.pages.dev).

    python3 experiments/news_images/photo_store.py --dry   # 줄이기 · 목록만 (올리지 않음)
    python3 experiments/news_images/photo_store.py         # 줄이기 · 목록 · 올리기

- 원본 = Mac `~/Desktop/Newfact-그림-검수/완료/` (검수 끝난 사진 + 출처.csv). 검수가 Mac 에서 끝나므로 올리기도 Mac 에서.
- 강좌 그림 저장소(newfact-img, img_store.py)와 따로 둔다: Pages 배포는 전체 교체라 한 프로젝트에 섞으면 서로 지운다.
- 사진 = 가로 1000 · WebP 80 (11-28 한도 표: 평균 114KB · 751장 약 84MB). 파일 이름 = 원본 경로의 해시 10자리 → 원본 경로가 같으면 주소도 그대로.
- 목록 = `experiments/news_images/photo_index.json` (공개 저장소에 커밋, 발행기가 읽음): 사진 id · 폴더 · 종목 · 크기 · 저작자 · 이용 조건 · 조건 주소 · 원본 주소.
- 무료 한도: 계정 전체 한 달 배포 500회 · 배포당 파일 2만 · 파일당 25MB · 정적 파일 요청 · 전송량 무제한.
- 로그인: wrangler OAuth(red6keep, 배포 전 whoami).
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Desktop/Newfact-그림-검수/완료")
CACHE = os.path.expanduser("~/Desktop/Newfact-그림-검수/.webp-1000")   # 줄인 사진 보관(다시 줄이지 않게)
INDEX = os.path.join(HERE, "photo_index.json")
PROJECT = "newfact-photo"
BASE_URL = "https://photo.newfact.app/"   # 예비 = https://newfact-photo.pages.dev/ (11-28 사용자 도메인 연결)
ACCOUNT_ID = "a8718df7edc5f8f6ce88e75b6545e5cb"   # red6keep (블로그 계정)
WIDTH, QUALITY = 1000, 80
HEADERS = "/*\n  Cache-Control: public, max-age=2592000\n"   # 30일 — 같은 id 는 같은 사진(바뀌지 않음)

LIC_URL = {
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 2.0": "https://creativecommons.org/licenses/by-sa/2.0/",
    "CC BY-SA 3.0 pl": "https://creativecommons.org/licenses/by-sa/3.0/pl/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY 3.0 de": "https://creativecommons.org/licenses/by/3.0/de/",
    "CC BY 2.5": "https://creativecommons.org/licenses/by/2.5/",
    "CC BY 2.1 jp": "https://creativecommons.org/licenses/by/2.1/jp/",
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "KOGL Type 1": "https://www.kogl.or.kr/info/licenseType1.do",
}
LIC_SHORT = {"Public domain": "퍼블릭 도메인", "KOGL Type 1": "공공누리 1유형", "Attribution": "저작자 표시"}


def clean_artist(a):
    """출처 줄은 짧게 — 'X from 도시, 나라' → X · 'The original uploader was X at …' → X · 'User: X' → X."""
    a = " ".join(a.split())
    m = re.match(r"The original uploader was (.+?) at ", a)
    if m:
        a = m.group(1)
    m = re.match(r"No machine-readable author provided\. (\S+) assumed", a)
    if m:
        a = m.group(1)
    a = re.sub(r"^\S+\.(jpg|jpeg|png|JPG):\s*", "", a)
    a = re.sub(r"^User:?\s*(\(.*?\)\s*)?", "", a)
    a = re.split(r"\s+(at|on) (English Wikipedia|en\.wikipedia)", a)[0]
    a = a.split(" @ ")[0]
    m = re.search(r"by Wikipedia user (\w+)", a)
    if m:
        a = m.group(1)
    if a.startswith("This file is licensed"):   # 저작자 칸에 조건 글만 있음 → 원본 페이지에서 확인하게
        a = "원본 참조"
    a = re.sub(r" from [A-Z][\w .,'-]*$", "", a)
    a = re.sub(r"\s+at \w+ wiki\w*$", "", a)
    return a[:60] or "알 수 없음"


def pid(rel):
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]


def shrink(src, dst):
    im = Image.open(src)
    im = im.convert("RGB")
    if im.width > WIDTH:
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
    im.save(dst, "WEBP", quality=QUALITY, method=6)
    return im.size


def build():
    os.makedirs(CACHE, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(SRC, "출처.csv"), encoding="utf-8-sig")))
    out, seen, size = [], set(), 0
    for r in rows:
        rel = r["file"]
        f = os.path.join(SRC, rel)
        if not os.path.exists(f) or rel in seen:
            continue
        seen.add(rel)
        i = pid(rel)
        dst = os.path.join(CACHE, i + ".webp")
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(f):
            w, h = Image.open(dst).size
        else:
            w, h = shrink(f, dst)
        size += os.path.getsize(dst)
        group = os.path.dirname(rel)
        sym = os.path.basename(rel).split("_")[0] if rel.startswith("1_기업-사진/") else ""
        lic = r["license"].strip()
        out.append({
            "id": i, "group": group, "sym": sym, "w": w, "h": h,
            "artist": clean_artist(r["artist"]),
            "license": LIC_SHORT.get(lic, lic),
            "license_url": LIC_URL.get(lic, r["source"]),   # 조건 주소가 없는 것(퍼블릭 도메인 · 저작자 표시)은 원본 페이지
            "source": r["source"],
            "title": r["title"][:120],
        })
    # 파일만 있고 출처 줄이 없는 사진 = 올리지 않음(출처 없이 쓸 수 없음)
    orphan = [os.path.relpath(os.path.join(dp, n), SRC) for dp, _, fs in os.walk(SRC) for n in fs
              if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and os.path.relpath(os.path.join(dp, n), SRC) not in seen]
    return out, size, orphan


def main():
    dry = "--dry" in sys.argv
    items, size, orphan = build()
    if orphan:
        print(f"[자료 사진] 출처 줄 없음 {len(orphan)}장 — 올리지 않음: {orphan[:5]}")
    if len(items) > 20000:
        raise SystemExit("[자료 사진] 배포당 2만 개 한도 — R2 로 옮길 때")
    json.dump({"base": BASE_URL, "width": WIDTH, "photos": items}, open(INDEX, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"[자료 사진] {len(items)}장 · {size / 1048576:.1f}MB · 목록 {os.path.getsize(INDEX) / 1024:.0f}KB")
    if dry:
        return
    with tempfile.TemporaryDirectory() as tmp:
        for it in items:
            shutil.copy2(os.path.join(CACHE, it["id"] + ".webp"), os.path.join(tmp, it["id"] + ".webp"))
        open(os.path.join(tmp, "_headers"), "w").write(HEADERS)
        open(os.path.join(tmp, "404.html"), "w").write("")   # 없는 사진 = 404 (404.html 이 없으면 Pages 가 index 로 200 을 준다)
        env = dict(os.environ, CLOUDFLARE_ACCOUNT_ID=ACCOUNT_ID)
        subprocess.run(["npx", "--yes", "wrangler@4.162.0", "pages", "deploy", tmp, "--project-name", PROJECT,
                        "--branch", "main", "--commit-dirty=true"], check=True, env=env)


if __name__ == "__main__":
    main()
