"""알파스코프 시황 해설 배너 — 글 맨 위 히어로 그림.

    python experiments/market-commentary/banner.py --briefing briefing.json [--column column.json] [--out DIR] [--no-ai]

발행기가 부른다: make(briefing, column, out_dir) → {"path", "ref", "url", "source", "scene"} 또는 None.

- 배경 = AI 실사 그림 ("미국 · 한국 경제의 하루"). 장면은 파이썬 틀이 고른다 — AI 글 모델 0.
    소재 = 그날 가장 크게 움직인 업종 → 7갈래 (날짜로 갈래 안 장면을 돌림) · 분위기 = 대표 지수 등락 5단계 · 장소 = am 미국 · pm 한국.
- 그림 사슬: Workers AI Lucid Origin → Workers AI FLUX schnell → Hugging Face FLUX schnell → 기본 배너(static/default/{분위기}.webp).
    Pollinations 는 쓰지 않는다 (11-17 무료 = IP 당 45초 1장 + 워터마크).
- 배치 = 주요 제목(흰색) · 강조 제목(방향 색) · 시장 요약 한 줄. `AI 생성 이미지` 는 그림에 쓰지 않고 img alt 에.
- 글자 = Pillow + 강원교육튼튼(fonts/GangwonEduPower.ttf, 강원특별자치도교육청 — 판매 · 유료 양도만 금지, 출처 표기 권장). 숫자 없음. 칸: 알약(브랜드 · 날짜 · 편) / 배너 제목 2줄 / 키워드 줄 / 오늘 볼 것 3칸 / `AI 생성 이미지`.
    글은 수집기 `banner` 칸: titles = 제목 후보 [[주요, 강조], …] 좋은 것부터 → 사양 크기에 들어가는 첫 후보, 다 길면 줄임. keys = 시장 요약.
    후보가 없으면 글 제목(그날 주제)의 숫자 없는 앞 구절. 글이 길면 칸에 들어갈 때까지 줄인다 — 빼지 않음.
- 규칙(운영지침 4-6): 로고 · 간판 · 랜드마크(거래소 정면 · 황소상) 없음, 사람은 멀리 · 뒷모습, `AI 생성 이미지` 는 alt 에.
- 출력 = {out}/images/commentary-{날짜}-{am|pm}.webp. 이름에 날짜가 있어 30일 정리(image_prune.py) 대상.
- 비밀 값: CF_ACCOUNT_ID · CF_AI_TOKEN · HF_TOKEN 환경 변수. 출력 · 로그에 쓰지 않는다 (오류는 상태 코드 + 응답 앞 160자).
"""
import argparse
import base64
import datetime as dt
import io
import json
import os
import re
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE, "fonts", "GangwonEduPower.ttf")   # 강원교육튼튼 하나만 — 배너 그림 글자에만, 블로그 본문 · 테마 폰트와 무관
DEFAULT_DIR = os.path.join(BASE, "static", "default")
REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "red6keep-droid/alphascope")
W, H = 1200, 630

CF_MODELS = [("@cf/leonardo/lucid-origin", {"width": W, "height": H}),
             ("@cf/black-forest-labs/flux-1-schnell", {"steps": 8})]   # schnell 은 정사각 1024 → 가운데 자름
HF_MODEL = "black-forest-labs/FLUX.1-schnell"

MASTER = ("cinematic editorial photograph for a premium business magazine, 35mm lens, natural light, realistic, "
          "wide establishing shot, people seen from a distance or from behind with faces not in focus, "
          "no recognizable landmarks, no brand logos, no signboards, no company names, no lettering on buildings, "
          "no readable signs, no text, no letters, no numbers, no watermark")
# 간판 · 글자 없음은 장면 바로 뒤에 긍정 표현으로도 — 그림 AI 는 설명 뒷부분 · 부정 표현을 약하게 따른다
CLEAN = "plain unbranded buildings with blank facades, every surface free of signage and lettering"
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
            "chg_pct": idx.get("chg_pct"), "prompt": f"{text} {PLACE[slot]}, {CLEAN}, {MOOD[mood]}, {MASTER}"}


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

def _font(bold, px):   # bold 인자는 옛 호출 자리 — 폰트는 하나
    try:
        return ImageFont.truetype(FONT_FILE, px)
    except OSError:   # 파일이 없으면 Pillow 기본 글꼴(한글 안 나옴) — 로그로 알림
        log("폰트 파일 없음 — 기본 글꼴")
        return ImageFont.load_default(px)


def _shrink(d, text, bold, px, min_px, room):
    while px > min_px and d.textlength(text, font=_font(bold, px)) > room:
        px -= 1
    return px if d.textlength(text, font=_font(bold, px)) <= room else None


# 배너 배치 — 900×350, 사진 상자 917×463 왼쪽 위(넘치는 곳은 잘림).
# 폰트는 사양(Gayathri · Noto Sans KR) 대신 정한 강원교육튼튼, 색은 사양 그대로 + 강조 제목만 방향 색(오름 #F34032 · 내림 파랑, 사이트 증감 색 규칙).
OUT_W, OUT_H = 900, 374   # 높이 350 → 374 = 폰(390 폭)에서 +10px
PHOTO_W, PHOTO_H = 917, 463
CANVAS_BG = (6, 18, 26)                      # #06121A
LEFT = 68
MAX_TEXT_W = OUT_W - LEFT - 40               # 시장 요약 글자가 넘지 않을 오른쪽 끝 (792)
TITLE_MAX_W = 750   #  제목 글자 폭 상한 — 10자 제목이 오른쪽 끝까지 꽉 차 커 보이던 것(11-19 첫 발행), 넘는 제목만 줄인다(10자 제목 80 → 70px, 약 11%) · 짧은 제목은 그대로
LINE_H = 1.25
MAIN = {"top": 80, "px": 87, "spacing": -2.0, "color": (245, 246, 248)}      # 주요 제목 #F5F6F8, 그림자 0 2 3 rgba(0,0,0,.55)
EMPH = {"top": 162, "px": 88, "spacing": -2.0}   # 제목 79/80 → 87/88(+10%) · 자간 +2/+2.5 → −2 · 줄 위치는 높이 374 에 맞춤                               # 강조 제목 — 색은 방향
SUMMARY = {"top": 284, "px": 32, "spacing": 0.2, "color": (218, 225, 234)}  # 시장 요약 #DAE1EA
BIG_PX, BIG_SPACING = round(EMPH["px"] * 1.3), EMPH["spacing"] * 1.3   # 짧은 제목 한 줄 = 30% 크게
# 글자 수 제한 (수집기 Q25, 튼튼체 실측 — 한글 한 자 80px ≈ 76 · 104px ≈ 100 · 32px ≈ 30, 띄어쓰기 ≈ 0.27자):
#   띄어쓰기는 빼고 센다 — 두 줄 제목 줄마다 한글 10자 · 두 줄 합쳐 7자 안팎이면 저절로 한 줄 104px · 시장 요약 한글 20자(가운뎃점 별도)
# 강조 제목 색: 오름 = 주황이 살짝 도는 밝은 빨강 #FF6840 · 내림 = 하늘색이 섞인 밝은 파랑 #4AB0FF (옛 #F34032 · #549CFF — 사진에 묻힘)
# 보합 = 밝은 보라 #B794FF. 밝기는 내림 파랑과 비슷(어두운 바탕 대비 7.8)
EMPH_COLOR = {"strong_up": (255, 104, 64), "up": (255, 104, 64), "flat": (183, 148, 255),
              "down": (74, 176, 255), "plunge": (74, 176, 255)}
EMPH_GLOW, SHADE_MAX, PHOTO_DIM = 200, 190, 0.15   # 강조 제목 뒤 어두운 번짐 · 왼쪽 어둡게(옛 150) · 사진 전체 15% 어둡게 — 글자가 사진에 묻히지 않게 (같은 날 4번)


def _spaced_w(text, font, sp):
    return sum(font.getlength(c) for c in text) + sp * max(len(text) - 1, 0)


def _spaced(d, x, cy, text, font, sp, fill):
    for c in text:
        d.text((x, cy), c, font=font, fill=fill, anchor="lm")
        x += font.getlength(c) + sp


def _cover(bg, w, h):
    iw, ih = bg.size
    s = max(w / iw, h / ih)
    im = bg.resize((round(iw * s), round(ih * s)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def compose(bg, sc, banner, emph_rgb=None, emph_glow=EMPH_GLOW, shade_max=SHADE_MAX, photo_dim=PHOTO_DIM, text_max=None):
    """사진 + 글자. 짧은 글은 사양 크기 그대로(키우지 않음), 긴 글은 칸에 들어갈 때까지 줄인다.
    읽히게: emph_rgb = 강조 제목 색 바꿈 · emph_glow = 강조 제목 뒤 어두운 번짐 진하기(0 ~ 255) ·
    shade_max = 왼쪽 어둡게 정도 · photo_dim = 사진 전체를 이만큼 어둡게(0 ~ 1). 기본값 = 확정값."""
    emph_col = emph_rgb or EMPH_COLOR[sc["mood"]]
    MAX_W = text_max or TITLE_MAX_W   # 제목 글자가 넘지 않을 폭 — 시장 요약은 MAX_TEXT_W 그대로
    glow = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    canvas = Image.new("RGB", (OUT_W, OUT_H), CANVAS_BG)
    photo = _cover(bg.convert("RGB"), PHOTO_W, PHOTO_H)
    if photo_dim:
        from PIL import ImageEnhance
        photo = ImageEnhance.Brightness(photo).enhance(1 - photo_dim)
    canvas.paste(photo, (0, 0))
    # 글자 쪽(왼쪽)만 옅게 어둡게 — 밝은 사진(크게 오른 날)에서도 읽히게
    shade = Image.new("L", (OUT_W, OUT_H))
    sd = ImageDraw.Draw(shade)
    for x in range(OUT_W):
        sd.line([(x, 0), (x, OUT_H)], fill=int(shade_max * max(0.0, 1 - x / (OUT_W * 0.72))))
    im = Image.composite(Image.new("RGB", (OUT_W, OUT_H), CANVAS_BG), canvas, shade).convert("RGBA")
    banner = banner if isinstance(banner, dict) else {}
    txt = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(txt), ImageDraw.Draw(shadow)

    # ① 제목 — 후보(titles, 좋은 것부터) 중 사양 크기 그대로 들어가는 첫 후보. 다 길면 가장 덜 줄여도 되는 후보를 칸에 들어갈 때까지 줄임(빼지 않음)
    cands = []
    for c in (banner.get("titles") or []) + ([banner["lines"]] if banner.get("lines") else []):
        ln = [str(x).strip() for x in (c if isinstance(c, list) else [c]) if str(x).strip()][:2]
        if ln:
            cands.append(ln)
    best = None
    for ln in cands:
        styles = [MAIN, EMPH] if len(ln) == 2 else [EMPH]
        scale = min([1.0] + [MAX_W / _spaced_w(t, _font(True, st["px"]), st["spacing"]) for t, st in zip(ln, styles)])
        if best is None or scale > best[1] + 1e-9:
            best = (ln, scale, styles)
        if scale >= 1.0:
            break
    big = _font(True, BIG_PX)
    one = " ".join(best[0]) if best else ""
    if best and _spaced_w(one, big, BIG_SPACING) <= MAX_W:
        # 짧은 제목 = 한 줄 · 30% 크게(104px), 제목 칸 가운데. 두 줄이 왔으면 앞은 흰색 · 뒤는 방향 색
        lines = best[0]
        if len(cands) > 1:
            log(f"제목 후보 {len(cands)}개 중 {cands.index(lines) + 1}번째: {lines}")
        cy = (MAIN["top"] + EMPH["top"] + EMPH["px"] * LINE_H) / 2
        parts = [(lines[0] + " ", MAIN["color"]), (lines[1], emph_col)] if len(lines) == 2 else [(lines[0], emph_col)]
        x = LEFT
        for t, color in parts:
            if color == MAIN["color"]:
                _spaced(ds, x, cy + 2, t, big, BIG_SPACING, (0, 0, 0, 140))
            elif emph_glow:
                _spaced(dg, x, cy + 2, t, big, BIG_SPACING, (0, 0, 0, emph_glow))
            _spaced(d, x, cy, t, big, BIG_SPACING, color)
            x += _spaced_w(t, big, BIG_SPACING) + BIG_SPACING
        log(f"짧은 제목 — 한 줄 {BIG_PX}px")
        best = None
    if best:
        lines, scale, styles = best
        if len(cands) > 1:
            log(f"제목 후보 {len(cands)}개 중 {cands.index(lines) + 1}번째: {lines}")
        gap = (EMPH["top"] - MAIN["top"]) * scale
        tops = [MAIN["top"], MAIN["top"] + gap] if len(lines) == 2 else [MAIN["top"] + gap / 2]
        for ln, st, top in zip(lines, styles, tops):
            px = max(12, int(st["px"] * scale))
            f = _font(True, px)
            cy = top + px * LINE_H / 2
            color = st.get("color") or emph_col
            if st is MAIN:
                _spaced(ds, LEFT, cy + 2, ln, f, st["spacing"] * scale, (0, 0, 0, 140))
            elif emph_glow:
                _spaced(dg, LEFT, cy + 2, ln, f, st["spacing"] * scale, (0, 0, 0, emph_glow))
            _spaced(d, LEFT, cy, ln, f, st["spacing"] * scale, color)
        if scale < 1:
            log(f"제목 줄임 ×{scale:.2f} ({int(EMPH['px'] * scale)}px)")

    # ② 시장 요약 — keys 를 ' · ' 로 잇고, 길면 칸에 들어갈 때까지 줄임(빼지 않음)
    keys = [str(k).strip() for k in (banner.get("keys") or []) if str(k).strip()]
    if keys:
        line = " · ".join(keys)
        px = SUMMARY["px"]
        while px > 12 and _spaced_w(line, _font(True, px), SUMMARY["spacing"]) > MAX_TEXT_W:
            px -= 1
        _spaced(d, LEFT, SUMMARY["top"] + SUMMARY["px"] * LINE_H / 2, line, _font(True, px), SUMMARY["spacing"], SUMMARY["color"])
        if px < SUMMARY["px"]:
            log(f"요약 줄임 {SUMMARY['px']} → {px}px")

    # ③ `AI 생성 이미지` 글자는 그리지 않는다 — 표시는 img alt 에 (운영지침 4-6)
    im = Image.alpha_composite(im, shadow.filter(ImageFilter.GaussianBlur(1.5)))
    if emph_glow:   # 강조 제목 뒤 넓은 어두운 번짐 — 두 번 겹쳐 진하게
        g = glow.filter(ImageFilter.GaussianBlur(10))
        im = Image.alpha_composite(Image.alpha_composite(im, g), g)
    return Image.alpha_composite(im, txt).convert("RGB")


def banner_text(column, sc=None):
    """배너 글 — 제목은 반드시 있다. AI 0.
    제목 순서: ① 수집기 banner.titles(좋은 것부터) · lines ② 글 제목(그날 주제)의 숫자 없는 앞 구절 ③ 글 제목 전체 ④ 편 이름 `11.17 미국 증시시황`."""
    column = column or {}
    b = dict(column.get("banner") or {})
    if not b.get("titles") and not b.get("lines"):
        title = str(column.get("title") or "").split(" — ")[-1].strip()
        parts = [p.strip() for p in re.split(r"[,，]", title) if p.strip() and not re.search(r"\d", p)]
        if parts:
            b["titles"] = [[parts[0]]]
            log(f"제목 후보 없음 — 글 제목 앞 구절: {parts[0]}")
        elif title:
            b["titles"] = [[title]]
            log(f"제목 후보 없음 — 글 제목 전체: {title}")
        elif sc:
            day = dt.date.fromisoformat(sc["date"])
            b["titles"] = [[f"{day.month}.{day.day:02d} {'미국' if sc['slot'] == 'am' else '한국'} 증시시황"]]
            log("글 제목도 없음 — 편 이름으로")
    return b


# ── 한 번에 ─────────────────────────────────────────────────────────

def make(briefing, column=None, out_dir=".", use_ai=True):
    """배너 한 장을 만들고 경로 · gh-pages 주소를 돌려준다. 실패하면 None (글은 배너 없이 나간다)."""
    try:
        sc = scene(briefing)
        bg, source = background(sc, use_ai)
        im = compose(bg, sc, banner_text(column, sc))
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
