"""알파스코프 시황 해설 배너 — 글 맨 위 히어로 그림 (2026-11-17 사용자: Lucid Origin · 권장대로).

    python experiments/market-commentary/banner.py --briefing briefing.json [--column column.json] [--out DIR] [--no-ai]

발행기가 부른다: make(briefing, column, out_dir) → {"path", "ref", "url", "source", "scene"} 또는 None.

- 배경 = AI 실사 그림 ("미국 · 한국 경제의 하루"). 장면은 파이썬 틀이 고른다 — AI 글 모델 0.
    소재 = 그날 가장 크게 움직인 업종 → 7갈래 (날짜로 갈래 안 장면을 돌림) · 분위기 = 대표 지수 등락 5단계 · 장소 = am 미국 · pm 한국.
- 그림 사슬: Workers AI Lucid Origin → Workers AI FLUX schnell → Hugging Face FLUX schnell → 기본 배너(static/default/{분위기}.webp).
    Pollinations 는 쓰지 않는다 (11-17 무료 = IP 당 45초 1장 + 워터마크).
- 글자 = Pillow + 강원교육튼튼(fonts/GangwonEduPower.ttf, 강원특별자치도교육청 — 판매 · 유료 양도만 금지, 출처 표기 권장) · 작은 글씨 Pretendard(OFL). 숫자 없음. 칸: 알약(브랜드 · 날짜 · 편) / 배너 제목 2줄 / 키워드 줄 / 오늘 볼 것 3칸 / `AI 생성 이미지`.
    글은 수집기 `banner` 칸(News-doc 20절 Q25)에서. 없으면 알약 · 표시만 (머리글 · 본문은 글에 다 있다).
    칸에 안 들어가면 글자를 줄이고(최소 크기), 그래도 넘치면 그 칸을 그리지 않고 로그에 남긴다 — 글 본문에는 전부 있다.
- 규칙(운영지침 4-6): 로고 · 간판 · 랜드마크(거래소 정면 · 황소상) 없음, 사람은 멀리 · 뒷모습, `AI 생성 이미지` 표시.
- 출력 = {out}/images/commentary-{날짜}-{am|pm}.webp (1200×630, 약 60~90KB). 이름에 날짜가 있어 30일 정리(image_prune.py) 대상.
- 비밀 값: CF_ACCOUNT_ID · CF_AI_TOKEN · HF_TOKEN 환경 변수. 출력 · 로그에 쓰지 않는다 (오류는 상태 코드 + 응답 앞 160자).
"""
import argparse
import base64
import datetime as dt
import io
import json
import os
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
FONTS = {   # 이름 → (굵게, 보통). 강원교육튼튼 = 굵기 하나(ExtraBold) — 두 칸 다 같은 파일 (2026-11-17 사용자 "강원교육튼튼 적용 가능해?")
    "pretendard": (os.path.join(BASE, "fonts", "Pretendard-Bold.otf"), os.path.join(BASE, "fonts", "Pretendard-Regular.otf")),
    "gangwon": (os.path.join(BASE, "fonts", "GangwonEduPower.ttf"), os.path.join(BASE, "fonts", "Pretendard-Regular.otf")),
}
# 기본 = 강원교육튼튼 (2026-11-17 사용자) — 배너 그림 글자에만. 블로그 본문 · 테마 폰트와 무관. 작은 표시 글씨는 Pretendard 보통
FONT_BOLD, FONT_REG = FONTS.get(os.environ.get("BANNER_FONT", "gangwon"), FONTS["gangwon"])
if not os.path.exists(FONT_BOLD):   # 파일이 없으면 Pretendard 로 (배너가 빠지지 않게)
    FONT_BOLD, FONT_REG = FONTS["pretendard"]
DEFAULT_DIR = os.path.join(BASE, "static", "default")
REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "red6keep-droid/alphascope")
W, H = 1200, 630

CF_MODELS = [("@cf/leonardo/lucid-origin", {"width": W, "height": H}),
             ("@cf/black-forest-labs/flux-1-schnell", {"steps": 8})]   # schnell 은 정사각 1024 → 가운데 자름
HF_MODEL = "black-forest-labs/FLUX.1-schnell"

MASTER = ("cinematic editorial photograph for a premium business magazine, 35mm lens, natural light, realistic, "
          "wide establishing shot, people seen from a distance or from behind with faces not in focus, "
          "no recognizable landmarks, no brand logos, no readable signs, no text, no letters, no numbers, no watermark")
SUBJECT = {   # 7갈래 × 장면 몇 개 — 날짜로 돌린다
    "finance": ["a financial district street between glass skyscrapers with office workers walking",
                "a trading floor with rows of monitors and people working, seen from behind"],
    "corporate": ["a modern glass office lobby and meeting room seen through windows, business people working",
                  "office workers crossing a wide plaza in front of corporate towers"],
    "industry": ["a large factory production line with engineers inspecting machines",
                 "an energy plant with pipes and towers and workers in safety gear"],
    "tech": ["a semiconductor cleanroom and data center corridor with engineers in protective suits",
             "rows of servers in a large data center with an engineer walking between them"],
    "consumer": ["a busy commercial shopping street with people carrying bags",
                 "a large supermarket aisle with shoppers and carts"],
    "logistics": ["a container port with cranes, trucks and workers",
                  "a huge logistics warehouse with shelves, forklifts and workers"],
    "city": ["a wide city skyline with streets and traffic",
             "a busy city crosswalk with commuters and traffic"],
}
SECTOR_SUBJECT = [   # 업종 이름에 든 낱말 → 소재 (미국 11업종 · 한국 업종 이름 둘 다)
    (("기술", "반도체", "IT", "전기전자", "소프트웨어", "인터넷"), "tech"),
    (("금융", "은행", "증권", "보험"), "finance"),
    (("커뮤니케이션", "미디어", "통신", "부동산", "헬스", "제약", "바이오"), "corporate"),
    (("산업", "소재", "에너지", "화학", "철강", "조선", "기계", "자동차", "유틸리티", "건설"), "industry"),
    (("소비", "유통", "음식", "화장품"), "consumer"),
    (("운송", "물류", "해운", "항공"), "logistics"),
]
MOOD = {   # 대표 지수 등락(%) → 분위기
    "strong_up": "clear bright morning, strong sunlight reflecting on glass buildings, fast moving energetic crowd",
    "up": "warm early light returning over the city, people moving with steady energy",
    "flat": "light fog between buildings, people busy but the far end of the scene hazy",
    "down": "soft overcast light, muted cool colors, calm and heavy atmosphere",
    "plunge": "dark evening, building lights still on, streets quieter than usual, cool blue tones, heavy mood",
}
PLACE = {"am": "in an American city", "pm": "in Seoul, Korea"}
ACCENT = {"strong_up": (244, 67, 54), "up": (244, 67, 54), "flat": (148, 163, 184),
          "down": (84, 156, 255), "plunge": (84, 156, 255)}
DIR_WORDS = ("강세", "약세", "오름", "내림", "상승", "하락", "반등", "관망", "급락", "급등", "보합")
WEEKDAY = "월화수목금토일"


def log(msg):
    print(f"[banner] {msg}")


# ── 장면 고르기 (파이썬 틀) ─────────────────────────────────────────

def mood_of(chg):
    if chg is None:
        return "flat"
    if chg >= 1.0:
        return "strong_up"
    if chg >= 0.3:
        return "up"
    if chg > -0.3:
        return "flat"
    if chg > -1.5:
        return "down"
    return "plunge"


def subject_of(sectors, day):
    movers = sorted((s for s in sectors or [] if isinstance(s.get("chg_pct"), (int, float))),
                    key=lambda s: -abs(s["chg_pct"]))
    for s in movers[:1]:
        for words, sub in SECTOR_SUBJECT:
            if any(w in str(s.get("name", "")) for w in words):
                return sub
    return ("finance", "corporate", "city")[day.toordinal() % 3]   # 업종이 없거나 못 맞추면 날짜로 돌림


def scene(briefing):
    slot = briefing.get("slot") if briefing.get("slot") in PLACE else "am"
    day = dt.date.fromisoformat(str(briefing.get("date"))[:10])
    close = briefing.get("close") or {}
    idx = (close.get("indices") or [{}])[0]
    mood = mood_of(idx.get("chg_pct"))
    sub = subject_of(close.get("sectors"), day)
    variants = SUBJECT[sub]
    text = variants[day.toordinal() % len(variants)]
    return {"slot": slot, "date": day.isoformat(), "mood": mood, "subject": sub, "index": idx.get("name"),
            "chg_pct": idx.get("chg_pct"), "prompt": f"{text} {PLACE[slot]}, {MOOD[mood]}, {MASTER}"}


# ── 그림 받기 ───────────────────────────────────────────────────────

def _fit(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    t = W / H
    if w / h > t:
        nw = int(h * t)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / t)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((W, H), Image.LANCZOS)


def _cloudflare(prompt):
    account, token = os.environ.get("CF_ACCOUNT_ID", "").strip(), os.environ.get("CF_AI_TOKEN", "").strip()
    if not account or not token:
        raise RuntimeError("CF_ACCOUNT_ID · CF_AI_TOKEN 없음")
    errors = []
    for model, extra in CF_MODELS:
        try:
            r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}",
                              headers={"Authorization": f"Bearer {token}"}, json={"prompt": prompt, **extra}, timeout=180)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:160]}")
            if r.headers.get("content-type", "").startswith("image/"):
                return _fit(r.content), f"workers-ai:{model.rsplit('/', 1)[-1]}"
            img = ((r.json() or {}).get("result") or {}).get("image")
            if not img:
                raise RuntimeError("응답에 그림 없음")
            return _fit(base64.b64decode(img)), f"workers-ai:{model.rsplit('/', 1)[-1]}"
        except Exception as e:  # noqa: BLE001
            errors.append(f"{model.rsplit('/', 1)[-1]}: {str(e)[:160]}")
            log(f"Workers AI 실패 — {errors[-1]}")
    raise RuntimeError(" / ".join(errors))


def _huggingface(prompt):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN 없음")
    from huggingface_hub import InferenceClient
    im = InferenceClient(HF_MODEL, token=token).text_to_image(prompt, width=1216, height=640)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return _fit(buf.getvalue()), "huggingface:flux-1-schnell"


def background(sc, use_ai=True):
    if use_ai:
        for fn in (_cloudflare, _huggingface):
            try:
                return fn(sc["prompt"])
            except Exception as e:  # noqa: BLE001
                log(f"{fn.__name__[1:]} 못 씀 — {str(e)[:200]}")
    path = os.path.join(DEFAULT_DIR, f"{sc['mood']}.webp")
    log(f"기본 배너 사용 — {os.path.basename(path)}")
    return Image.open(path).convert("RGB").resize((W, H)), f"default:{sc['mood']}"


# ── 글자 얹기 ───────────────────────────────────────────────────────

def _font(bold, px):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, px)


def _shrink(d, text, bold, px, min_px, room):
    while px > min_px and d.textlength(text, font=_font(bold, px)) > room:
        px -= 1
    return px if d.textlength(text, font=_font(bold, px)) <= room else None


def compose(bg, sc, banner):
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(205 * max(0.0, 1 - x / (W * 0.78))))
    im = Image.composite(Image.new("RGB", (W, H), (8, 14, 30)), bg, shade.filter(ImageFilter.GaussianBlur(6)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    acc = ACCENT[sc["mood"]]
    day = dt.date.fromisoformat(sc["date"])
    banner = banner if isinstance(banner, dict) else {}

    # ① 알약 — 화면 제목 줄과 같은 말 (`11.17 미국 증시시황`, 19절)
    pill = f"알파스코프 시황 해설   |   {day.month}.{day.day:02d} ({WEEKDAY[day.weekday()]}) {'미국' if sc['slot'] == 'am' else '한국'} 증시시황"
    pf = _font(True, 24)
    pw = d.textlength(pill, font=pf)
    d.rounded_rectangle((48, 40, 48 + pw + 48, 92), 26, fill=(10, 20, 45, 200), outline=(255, 255, 255, 90), width=2)
    d.text((72, 64), pill, font=pf, fill=(235, 240, 250), anchor="lm")

    # ② 배너 제목 2줄 — 둘째 줄 = 방향 색
    lines = [str(x).strip() for x in (banner.get("lines") or []) if str(x).strip()][:2]
    if lines:
        px = min(_shrink(d, ln, True, 74, 52, W * 0.66) or 0 for ln in lines)
        if px:
            for i, ln in enumerate(lines):
                d.text((48, 120 + i * (px + 16)), ln, font=_font(True, px),
                       fill="white" if i == 0 and len(lines) > 1 else acc, stroke_width=2, stroke_fill=(0, 0, 0, 120))
        else:
            log(f"배너 제목이 길어 그리지 않음: {lines}")

    # ③ 키워드 줄 — 방향 낱말은 노랑
    keys = [str(k).strip() for k in (banner.get("keys") or []) if str(k).strip()]
    if keys:
        kf = _font(True, 32)
        total = d.textlength(" · ".join(keys), font=kf)
        if total <= W - 100:
            x = 52
            for i, k in enumerate(keys):
                if i:
                    d.text((x, 318), " · ", font=kf, fill=(235, 238, 245))
                    x += d.textlength(" · ", font=kf)
                head, _, tail = k.rpartition(" ")
                if tail in DIR_WORDS and head:
                    d.text((x, 318), head + " ", font=kf, fill=(235, 238, 245))
                    x += d.textlength(head + " ", font=kf)
                    d.text((x, 318), tail, font=kf, fill=(255, 214, 64))
                    x += d.textlength(tail, font=kf)
                else:
                    d.text((x, 318), k, font=kf, fill=(255, 214, 64) if k in DIR_WORDS else (235, 238, 245))
                    x += d.textlength(k, font=kf)
        else:
            log(f"키워드 줄이 길어 그리지 않음: {keys}")

    # ④ 오늘 볼 것 3칸
    pts = [p for p in (banner.get("points") or []) if isinstance(p, dict) and p.get("what")][:3]
    if pts:
        top, h = 400, 130
        cw = (W - 40 - 250) / len(pts)
        px = min(_shrink(d, str(p["what"]), True, 27, 18, cw - 96) or 0 for p in pts)
        if px:
            d.rounded_rectangle((40, top, W - 40, top + h), 22, fill=(10, 22, 50, 190), outline=(120, 160, 255, 110), width=2)
            d.rounded_rectangle((60, top + 22, 230, top + h - 22), 18, fill=acc + (235,))
            lf = _font(True, 30)
            d.text((145, top + h / 2 - 20), "오늘", font=lf, fill="white", anchor="mm")
            d.text((145, top + h / 2 + 18), "볼 것", font=lf, fill="white", anchor="mm")
            for i, p in enumerate(pts):
                cx = 250 + i * cw
                if i:
                    d.line([(cx, top + 26), (cx, top + h - 26)], fill=(255, 255, 255, 70), width=2)
                d.ellipse((cx + 24, top + 30, cx + 60, top + 66), fill=acc + (255,))
                d.text((cx + 42, top + 48), str(i + 1), font=_font(True, 22), fill="white", anchor="mm")
                d.text((cx + 76, top + 30), str(p.get("when", "")), font=_font(True, 24), fill=(255, 214, 64))
                d.text((cx + 76, top + 66 + (27 - px) / 2), str(p["what"]), font=_font(True, px), fill="white")
        else:
            log(f"볼 것 칸이 길어 그리지 않음: {[p['what'] for p in pts]}")

    # ⑤ 표시 (운영지침 4-6)
    d.text((48, H - 34), "AI 생성 이미지 · 알파스코프", font=_font(False, 18), fill=(200, 205, 215), anchor="lm")
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


# ── 한 번에 ─────────────────────────────────────────────────────────

def make(briefing, column=None, out_dir=".", use_ai=True):
    """배너 한 장을 만들고 경로 · gh-pages 주소를 돌려준다. 실패하면 None (글은 배너 없이 나간다)."""
    try:
        sc = scene(briefing)
        bg, source = background(sc, use_ai)
        im = compose(bg, sc, (column or {}).get("banner"))
        ref = f"images/commentary-{sc['date']}-{sc['slot']}.webp"
        path = os.path.join(out_dir, ref)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        im.save(path, "WEBP", quality=80, method=6)
        info = {"path": path, "ref": ref, "url": f"https://cdn.jsdelivr.net/gh/{REPO_SLUG}@gh-pages/{ref}",
                "source": source, "kb": round(os.path.getsize(path) / 1024),
                "scene": {k: sc[k] for k in ("slot", "mood", "subject", "index", "chg_pct")}}
        log(json.dumps(info, ensure_ascii=False))
        return info
    except Exception as e:  # noqa: BLE001
        log(f"실패 — 배너 없이: {str(e)[:200]}")
        return None


def _load(src):
    if src.startswith("http"):
        r = requests.get(src, timeout=30)
        r.raise_for_status()
        return r.json()
    with open(src, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefing", required=True, help="묶음 파일 경로 또는 주소")
    ap.add_argument("--column", help="수집기 글 JSON (banner 칸)")
    ap.add_argument("--out", default=os.path.join(BASE, "output"))
    ap.add_argument("--no-ai", action="store_true", help="AI 없이 기본 배너로")
    a = ap.parse_args()
    ok = make(_load(a.briefing), _load(a.column) if a.column else None, a.out, use_ai=not a.no_ai)
    sys.exit(0 if ok else 1)
