"""고정 그림 저장소 — Cloudflare Pages 프로젝트 `newfact-img` (주소 https://img.newfact.app, 예비 https://newfact-img.pages.dev).

    python experiments/img_store.py          # 모아서 올리기
    python experiments/img_store.py --dry    # 모으기만 하고 개수 · 크기만 보기

- 무엇: 오래 쓰는 그림(강좌 · 캐릭터 · 소품 아이콘 · 배너). 날짜가 붙은 리포트 그림은 여기가 아니라 gh-pages(30일 정리, image_prune.py).
  (2026-11-22 사용자: 강좌 그림은 2~3년 쓰는 킬러 콘텐츠 → 휘발성 저장소와 나눔. 새 이름은 newfact — 기존 alphascope 이름은 그대로)
- 원본은 공개 저장소의 각 폴더 그대로. 이 스크립트가 SOURCES 를 한 폴더로 모아 통째로 올린다.
  **Pages 배포는 전체 교체**라 SOURCES 에 없는 파일은 올리는 순간 사라진다 → 새 그림 묶음은 SOURCES 에 줄을 더할 것.
- 다른 프로젝트(alpha-scope = 종목 주가 조각)와 섞지 않는다 — 같은 프로젝트에 따로 올리면 서로 지운다.
- 로그인: 로컬 = wrangler OAuth(red6keep, 배포 전 whoami), GitHub 실행 = Secret CF_PAGES_API_TOKEN 을 CLOUDFLARE_API_TOKEN 으로.
- 무료 한도: 계정 전체 한 달 배포 500회 · 배포당 파일 2만 · 파일당 25MB · 정적 파일 요청 · 전송량 무제한.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = "newfact-img"
BASE_URL = "https://img.newfact.app/"
ACCOUNT_ID = "a8718df7edc5f8f6ce88e75b6545e5cb"   # red6keep (블로그 계정)

# (올릴 폴더, 원본 글롭 목록) — 올린 주소 = BASE_URL + 폴더 + "/" + 파일 이름
SOURCES = [
    ("study", ["course/chars/*.webp", "course/icons/*.webp", "course/banner/*.webp", "course/banner/share_*.jpg"]),
]
HEADERS = "/*\n  Cache-Control: public, max-age=604800\n"   # 일주일 — 같은 이름으로 그림을 바꿔도 길어야 일주일 뒤 반영


def build(out):
    n, size = 0, 0
    for folder, pats in SOURCES:
        dst = os.path.join(out, folder)
        os.makedirs(dst, exist_ok=True)
        for pat in pats:
            for f in sorted(glob.glob(os.path.join(HERE, pat))):
                name = os.path.basename(f)
                if os.path.exists(os.path.join(dst, name)):
                    raise SystemExit(f"[그림 저장소] 이름 겹침: {folder}/{name}")
                shutil.copy2(f, os.path.join(dst, name))
                n += 1
                size += os.path.getsize(f)
                if os.path.getsize(f) > 25 * 1024 * 1024:
                    raise SystemExit(f"[그림 저장소] 25MB 넘음: {f}")
    if n > 20000:
        raise SystemExit(f"[그림 저장소] 파일 {n}개 — 배포당 2만 개 한도. R2 로 옮길 때")
    with open(os.path.join(out, "_headers"), "w", encoding="utf-8") as fh:
        fh.write(HEADERS)
    return n, size


def main():
    dry = "--dry" in sys.argv
    with tempfile.TemporaryDirectory() as out:
        n, size = build(out)
        print(f"[그림 저장소] {n}개 · {size / 1048576:.1f}MB")
        if dry:
            return
        env = dict(os.environ, CLOUDFLARE_ACCOUNT_ID=ACCOUNT_ID)
        if env.get("CF_PAGES_API_TOKEN") and not env.get("CLOUDFLARE_API_TOKEN"):
            env["CLOUDFLARE_API_TOKEN"] = env["CF_PAGES_API_TOKEN"]
        cmd = ["npx", "--yes", "wrangler", "pages", "deploy", out, "--project-name", PROJECT, "--branch", "main", "--commit-dirty=true"]
        r = subprocess.run(cmd, env=env, cwd=HERE)
        if r.returncode:
            raise SystemExit(f"[그림 저장소] 배포 실패 {r.returncode}")
        print(f"[그림 저장소] 올림 → {BASE_URL}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
