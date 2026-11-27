"""기사 자료 사진 후보에서 기사에 안 맞는 그림을 사용안함 폴더로 옮긴다.

기사 사진 = 현장 사진. 빼는 것 셋:
  흑백   — 채도 거의 없음(세피아 같은 한 색조 포함)
  야간   — 화면 대부분이 어두움. 파업 · 노동 폴더와 제목에 strike · protest 등이 있는 그림은 예외(야간 파업 현장은 씀)
  일러스트 — 사진이 아닌 그림: 제목(지도 · 도표 · 깃발 · 문장 · 그림 …) 또는 같은 색 면이 넓은 그림(색 수가 적음)
로고 폴더(2_기업-로고)는 원래 그림이라 보지 않는다.

옮기기만 하고 지우지 않는다: 사용안함/<원래 경로> + 사용안함/사용안함-목록.csv(원래 경로 · 이유 · 값).
되돌리기 = --restore (목록대로 제자리로).

    python sort_out.py            # 목록만(옮기지 않음) + 확인용 모아보기 그림
    python sort_out.py --move     # 옮기기
    python sort_out.py --restore  # 되돌리기
"""
import argparse, csv, os, re, shutil, sys
from PIL import Image, ImageDraw
import numpy as np

ROOT = os.path.expanduser("~/Desktop/Newfact-그림-검수")
TRASH = os.path.join(ROOT, "사용안함")   # 쓰지 않는 그림을 모으는 한 곳
LIST = os.path.join(TRASH, "사용안함-목록.csv")
SKIP_DIRS = {"2_기업-로고", "사용안함"}
NIGHT_OK_DIRS = ("파업",)
NIGHT_OK_WORDS = re.compile(r"strike|protest|rally|demonstrat|vigil|march|picket|파업|시위|집회", re.I)
# 제목만 봐도 그림인 말
ILLUST_STRONG = re.compile(
    r"diagram|schemat|infographic|coat of arms|illustration|\bdrawing\b|cartoon|caricature|clipart|\.svg\b|"
    r"\brender(ing)?\b|\b3d\b|engraving|\blithograph\b|woodcut|screenshot|cutaway|artist'?s (impression|concept)|concept art", re.I)
# 사진 제목에도 흔한 말(Flag 든 사람, 로고 붙은 건물, 그래프 인쇄물 위 동전) → 색 수까지 적을 때만
ILLUST_WEAK = re.compile(
    r"\bmaps?\b|locator|\bcharts?\b|\bgraphs?\b|\bflags?\b|emblem|\bseal\b|\blogos?\b|wordmark|\bicons?\b|"
    r"painting|\bposter\b|pictogram|blueprint", re.I)
KEEP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sort_out_keep.txt")   # 눈으로 보고 남기기로 한 파일


def norm(p):
    return p.replace(" ", "_")


def load_titles():
    t = {}
    path = os.path.join(ROOT, "출처.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                t[norm(r["file"])] = f'{r.get("title","")} {r.get("note","")}'
    return t


def features(path):
    im = Image.open(path)
    alpha = 0.0
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        a = np.asarray(im.getchannel("A"), dtype=np.float32)
        alpha = float((a < 250).mean())
    im = im.convert("RGB")
    im.thumbnail((256, 256))
    x = np.asarray(im, dtype=np.float32)
    mx, mn = x.max(2), x.min(2)
    chroma = mx - mn
    ycc = np.asarray(im.convert("YCbCr"), dtype=np.float32)
    y = ycc[..., 0]
    # 색 수: 채널당 32 단계로 줄여 가장 많은 16색이 덮는 비율
    q = (x // 8).astype(np.int32)
    keys = (q[..., 0] << 10) | (q[..., 1] << 5) | q[..., 2]
    _, cnt = np.unique(keys, return_counts=True)
    top16 = float(np.sort(cnt)[::-1][:16].sum() / keys.size)
    xi = x.astype(np.int32)
    uniq = len(np.unique((xi[..., 0] << 16) | (xi[..., 1] << 8) | xi[..., 2])) / (xi.shape[0] * xi.shape[1])
    g = np.abs(np.diff(xi.sum(2), axis=1))
    nz = g[g > 6]
    return dict(
        uniq=uniq, sharp=float((nz > 90).mean()) if nz.size else 0.0,
        white=float((xi > 235).all(2).mean()),
        chroma=float(chroma.mean()), chroma95=float(np.percentile(chroma, 95)),
        cbstd=float(ycc[..., 1].std()), crstd=float(ycc[..., 2].std()),
        ymean=float(y.mean()), dark=float((y < 50).mean()),
        alpha=alpha,
    )


def judge(rel, f, title):
    # 흑백 먼저 (테두리 있는 옛 흑백 사진이 '그림'으로 잘못 가지 않게)
    if f["chroma"] < 10 and f["chroma95"] < 28:
        return "흑백", f"채도 {f['chroma']:.1f}"
    if f["cbstd"] < 4 and f["crstd"] < 4:
        return "흑백", f"한 색조(세피아) {f['cbstd']:.1f}/{f['crstd']:.1f}"
    if f["alpha"] > 0.05:
        return "일러스트", "투명 배경"
    m = ILLUST_STRONG.search(title) or (f["uniq"] < 0.2 and ILLUST_WEAK.search(title))
    if m:
        return "일러스트", f"제목 '{m.group(0)}'"
    # 색 수 적음 + (흰 바탕 넓음 또는 날카로운 경계) = 지도 · 도표 · 화면 캡처 · 로고. 하늘 사진은 경계가 부드러워 빠짐
    if f["uniq"] < 0.08 and (f["white"] > 0.4 or f["sharp"] > 0.15):
        return "일러스트", f"색 {f['uniq']:.2f} · 흰 바탕 {f['white']:.0%} · 경계 {f['sharp']:.2f}"
    if f["ymean"] < 70 and f["dark"] > 0.5:
        if any(k in rel for k in NIGHT_OK_DIRS) or NIGHT_OK_WORDS.search(title):
            return None, "야간 파업 · 시위 예외"
        return "야간", f"어두움 {f['dark']:.0%}"
    return None, ""


def sheet(items, out, cols=6, size=220):
    if not items:
        return
    rows = (len(items) + cols - 1) // cols
    W = Image.new("RGB", (cols * size, rows * (size + 28)), "white")
    d = ImageDraw.Draw(W)
    for i, (rel, why) in enumerate(items):
        try:
            im = Image.open(os.path.join(ROOT, rel)).convert("RGB")
            im.thumbnail((size - 6, size - 6))
            cx, cy = (i % cols) * size, (i // cols) * (size + 28)
            W.paste(im, (cx + 3, cy + 3))
            d.text((cx + 3, cy + size), str(i), fill="black")
        except Exception:
            pass
    W.save(out, quality=80)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--sheets", default="")
    a = ap.parse_args()

    if a.restore:
        with open(LIST, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            src = os.path.join(TRASH, r["file"])
            if os.path.exists(src):
                os.makedirs(os.path.dirname(os.path.join(ROOT, r["file"])), exist_ok=True)
                shutil.move(src, os.path.join(ROOT, r["file"]))
        os.remove(LIST)
        print("되돌림", len(rows))
        return

    titles = load_titles()
    keep = set()
    if os.path.exists(KEEP):
        keep = {norm(l.split("#")[0].strip()) for l in open(KEEP, encoding="utf-8") if l.split("#")[0].strip()}
    out, kept_sample = [], []
    for dp, dns, fns in os.walk(ROOT):
        rel_dir = os.path.relpath(dp, ROOT)
        if rel_dir.split(os.sep)[0] in SKIP_DIRS:
            dns[:] = []
            continue
        for fn in sorted(fns):
            if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            rel = os.path.normpath(os.path.join(rel_dir, fn))
            if norm(rel) in keep:
                continue
            try:
                f = features(os.path.join(dp, fn))
            except Exception as e:
                print("읽기 실패", rel, e, file=sys.stderr)
                continue
            why, val = judge(rel, f, titles.get(norm(rel), ""))
            if why:
                out.append((rel, why, val))
            elif val:
                print("예외로 남김:", rel, val)

    by = {}
    for rel, why, val in out:
        by.setdefault(why, []).append((rel, val))
    for k, v in by.items():
        print(f"{k}: {len(v)}")
    print("합계", len(out))

    if a.sheets:
        os.makedirs(a.sheets, exist_ok=True)
        for k, v in by.items():
            for j in range(0, len(v), 60):
                sheet([(r, f"{why}") for r, why in v[j:j + 60]], os.path.join(a.sheets, f"{k}_{j // 60}.jpg"))
        with open(os.path.join(a.sheets, "목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "reason", "value"])
            w.writerows(out)

    if a.move:
        os.makedirs(TRASH, exist_ok=True)
        new = not os.path.exists(LIST)
        with open(LIST, "a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["file", "reason", "value", "title"])
            for rel, why, val in out:
                dst = os.path.join(TRASH, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(os.path.join(ROOT, rel), dst)
                w.writerow([rel, why, val, titles.get(norm(rel), "")])
        print("옮김", len(out), "→", TRASH)


if __name__ == "__main__":
    main()
