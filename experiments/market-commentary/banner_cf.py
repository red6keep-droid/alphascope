"""시황 배너 Workers AI 비교 — banner_mock2 의 6장면을 Cloudflare Workers AI 로.

    CF_ACCOUNT_ID=… CF_AI_TOKEN=… python experiments/market-commentary/banner_cf.py [--models flux-1-schnell,lucid-origin]

- 장면 설명은 banner_mock2.SAMPLES · prompt() 그대로 (Pollinations 목업과 같은 글).
- 모델마다 6장 → output/banner-cf/{모델}/{장면}.webp (1200×630 으로 가운데 자름) + 로그(걸린 초 · 크기 · 실패 사유).
- 블로그 · gh-pages 에는 아무것도 쓰지 않는다. 결과는 워크플로 artifact 로만.
- 비밀 값은 출력하지 않는다: 오류는 상태 코드 + 응답 앞 200자(응답에 토큰은 없음)만.
- 상한: 모델당 6장 · 실행당 최대 3모델 = 18장.
"""
import argparse
import base64
import io
import json
import os
import sys
import time

import requests
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banner_mock2 as M  # noqa: E402

OUT = os.path.join(M.OUT, "banner-cf")
MODELS = {   # 짧은 이름 → (모델 id, 요청 몸통 추가값)
    "flux-1-schnell": ("@cf/black-forest-labs/flux-1-schnell", {"steps": 8}),   # 정사각 1024 고정 · 단계 최대 8
    "lucid-origin": ("@cf/leonardo/lucid-origin", {"width": 1200, "height": 630}),
    "phoenix-1.0": ("@cf/leonardo/phoenix-1.0", {"width": 1200, "height": 630}),
}
MAX_MODELS = 3


def run(model_id, extra, prompt, account, token):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model_id}"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json={"prompt": prompt, **extra}, timeout=180)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    if ctype.startswith("image/"):
        return r.content
    data = r.json()
    img = (data.get("result") or {}).get("image")
    if not img:
        raise RuntimeError(f"그림 없음: {json.dumps(data, ensure_ascii=False)[:200]}")
    return base64.b64decode(img)


def fit(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    target = M.W / M.H
    if w / h > target:   # 너무 넓음 → 좌우 자름
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:                # 너무 높음(정사각) → 위아래 자름
        nh = int(w / target)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((M.W, M.H), Image.LANCZOS), (w, h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="flux-1-schnell,lucid-origin")
    a = ap.parse_args()
    account, token = os.environ.get("CF_ACCOUNT_ID", "").strip(), os.environ.get("CF_AI_TOKEN", "").strip()
    if not account or not token:
        sys.exit("CF_ACCOUNT_ID · CF_AI_TOKEN 이 없습니다 (GitHub Secrets).")
    names = [m.strip() for m in a.models.split(",") if m.strip()][:MAX_MODELS]
    log = []
    for name in names:
        if name not in MODELS:
            print(f"[건너뜀] 모르는 모델 {name} — {', '.join(MODELS)}")
            continue
        model_id, extra = MODELS[name]
        os.makedirs(os.path.join(OUT, name), exist_ok=True)
        for key, mk, sub, mood, *_ in M.SAMPLES:
            t = time.time()
            row = {"model": name, "scene": key}
            try:
                im, raw_size = fit(run(model_id, extra, M.prompt(mk, sub, mood), account, token))
                path = os.path.join(OUT, name, f"{key}.webp")
                im.save(path, "WEBP", quality=80)
                row.update(ok=True, sec=round(time.time() - t, 1), raw=f"{raw_size[0]}x{raw_size[1]}", kb=round(os.path.getsize(path) / 1024))
            except Exception as e:  # noqa: BLE001
                row.update(ok=False, sec=round(time.time() - t, 1), error=str(e)[:240])
            print(json.dumps(row, ensure_ascii=False))
            log.append(row)
            time.sleep(2)
    with open(os.path.join(OUT, "log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    ok = sum(r["ok"] for r in log)
    print(f"[끝] {ok}/{len(log)}장")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
