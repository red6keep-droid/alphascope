"""뉴팩트 개성 있는 아이 찾기 게임 — 다른 PC(집)에서 이어 갈 때 한 번 돌리는 준비 (2026-11-24 사용자 "집에서 꼭 이어서 할 수 있게 해. 누락시키는 요소 없이").

깃에 없는 것(자료 · 만든 화면)을 순서대로 채운다. 이미 있는 것은 건너뛴다.

    python experiments/stock-character/prepare_home.py            # 없는 것만 채우고 화면 두 장을 만든다
    python experiments/stock-character/prepare_home.py --refresh  # 일봉을 오늘 기준으로 다시 받는다(약 5분)

하는 일
  1. 일봉 data/store/character/bars_us.pkl — 없으면 야후에서 받는다(미국 S&P 500 + 견줄 지수, 2005 ~, 약 5분 · 키 필요 없음).
     check_stage1.py 를 그대로 돌리면 비공개 문서의 1단계 검증 글을 덮어쓰므로, 여기서는 그 스크립트의 받기 함수만 부른다.
  2. 실적일 data/store/character/earn_days_us.csv — 없거나 옛 판(main 열 없음)이면 collect_earn_days.py --market us 로 다시 만든다.
     받아 둔 원본(earn_raw/us)이 있으면 부름 0, 없으면 SEC 에서 받는다(약 20분, .env 의 EDGAR_USER_AGENT 필요 — 값은 길잡이 문서 8절).
  3. 화면 — make_band_b.py(시안 틀) → look_band.py → output/mock_band.html(원본) · mock_band_b.html(그래프 시안).
  4. 끝에 기준일 · 아이 수를 찍는다. 회사 PC 에서 마지막으로 만든 값(2026-11-24): 기준일 2026-11-20 · 아이 499명 · 20일 간격 37구간.
     기준일이 다르면 구간 경계가 달라져 "설정으로 나온 답"의 명수 · 이름이 조금 달라진다(틀린 것이 아니다).

그 뒤: python experiments/mock_server.py → http://localhost:8800/ 의 `개성 있는 아이 찾기 게임`.
길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md (0-0 · 0-4 먼저).
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
DOC = os.path.abspath(os.path.join(ROOT, "..", "alphascope-docs", "doc", "기획", "종목-그래프-패턴-분류-목적.md"))
REF = {"last": "2026-11-20", "kids": 499, "pieces20": 37}   # 회사 PC 2026-11-24 밤에 만든 화면의 값 — 견줘 보라고 찍는다


def run(*args):
    print("  $ python " + " ".join(os.path.relpath(a, ROOT) if os.path.isabs(a) else a for a in args))
    r = subprocess.run([sys.executable, *args], cwd=ROOT)
    if r.returncode:
        raise SystemExit(f"멈춤 — 위 명령이 실패했습니다(코드 {r.returncode}). 메시지를 보고 고친 뒤 다시 돌리세요.")


def main():
    refresh = "--refresh" in sys.argv
    for mod in ("pandas", "numpy", "yfinance", "requests", "matplotlib", "pyarrow"):
        try:
            __import__(mod)
        except ImportError:
            raise SystemExit(f"파이썬 꾸러미 {mod} 가 없습니다 — pip install pandas numpy yfinance requests matplotlib pyarrow")
    import pandas as pd

    print("1. 일봉")
    bars_path = os.path.join(STORE, "bars_us.pkl")
    if os.path.exists(bars_path) and not refresh:
        print("  있음 — 그대로 씁니다(오늘 기준으로 다시 받으려면 --refresh)")
    else:
        sys.path.insert(0, HERE)
        import check_stage1 as C1   # 받기 함수만 쓴다 — main() 은 부르지 않는다(비공개 문서의 검증 글을 덮어쓴다)
        uni = C1.universe()["us"]
        C1.load_bars("us", list(uni) + sorted({v["bench"] for v in uni.values()}), refresh)
    bars = pd.read_pickle(bars_path)
    last = max(d.index.max() for s, d in bars.items() if not s.startswith("^") and len(d))
    print(f"  종목 {len(bars)}개 · 마지막 날 {last.date()}")

    print("2. 실적일")
    earn_path = os.path.join(STORE, "earn_days_us.csv")
    need = not os.path.exists(earn_path)
    if not need and "main" not in pd.read_csv(earn_path, nrows=1).columns:
        need = True
        print("  옛 판(본 발표 · 곁 공시를 가르기 전) — 다시 만듭니다")
    if need:
        if not os.path.isdir(os.path.join(STORE, "earn_raw", "us")):
            print("  받아 둔 원본이 없어 SEC 에서 받습니다(약 20분). .env 에 EDGAR_USER_AGENT 가 있어야 합니다 — 값은 길잡이 문서 8절")
        run(os.path.join(HERE, "collect_earn_days.py"), "--market", "us")
    else:
        print("  있음 — 그대로 씁니다")

    print("3. 화면")
    run(os.path.join(HERE, "make_band_b.py"))
    run(os.path.join(HERE, "look_band.py"))
    for name in ("mock_band.html", "mock_band_b.html"):
        p = os.path.join(HERE, "output", name)
        print(f"  {'만듦' if os.path.exists(p) else '없음 !!'}  {os.path.relpath(p, ROOT)}")

    print("4. 견주기")
    print(f"  회사 PC(2026-11-24) = 기준일 {REF['last']} · 아이 {REF['kids']}명 · 20일 간격 {REF['pieces20']}구간")
    print(f"  이 PC             = 기준일 {last.date()} (아이 수 · 구간 수는 위 look_band.py 가 찍은 줄)")
    if str(last.date()) != REF["last"]:
        print("  기준일이 달라 '설정으로 나온 답'의 명수 · 이름이 조금 다를 수 있습니다 — 틀린 것이 아닙니다.")
    print("\n다음: python experiments/mock_server.py  →  http://localhost:8800/ 의 `개성 있는 아이 찾기 게임`")
    print(f"길잡이 문서(0-0 · 0-4 먼저): {DOC}{'' if os.path.exists(DOC) else '  ← 없음! 비공개 저장소 alphascope-docs 를 이 저장소 옆 폴더에 받으세요'}")


if __name__ == "__main__":
    main()
