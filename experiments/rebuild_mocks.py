"""목업 전체 다시 그리기 — 목업과 블로그가 늘 같은 코드 · 같은 테마로 보이게 (2026-11-15 사용자: "최신 목업 기준으로 항상 블로그랑 목업이 일치되게. 두 번 일을 하면 안 된다").

목업은 만들 때 저장소 index.html(테마) CSS · JS 와 그때의 렌더러 코드를 복사해 굳는다(dk.write_mock).
공통 디자인(design_kit · index.html · 렌더러)을 고친 뒤 이 스크립트를 돌리면 쓰는 목업이 모두 최신 코드로 다시 그려진다.
AI 호출 0 · 인터넷은 ETF 시세 읽기만 — 나머지는 받아 둔 자료(data/*.json · output/*.json · 상태 브랜치 사본)로 그리기만. 블로그 게시 · 상태 브랜치 쓰기 없음.

    .venv/bin/python experiments/rebuild_mocks.py            # 전부
    .venv/bin/python experiments/rebuild_mocks.py 전망 종목   # 이름에 그 말이 든 묶음만

묶음 = 블로그에 발행 중인 페이지 + 발행 직전 진행 중인 기능. 쓰지 않는 목업(목업 서버 /archive)은 넣지 않는다.
새 목업 묶음을 만들면 JOBS 에 한 줄 추가한다 — 여기 없는 목업은 공통 디자인이 바뀌어도 옛 모양으로 남는다.
운영 대시보드(ops.html)는 GitHub · Cloudflare 를 읽어 만들어 여기서 빼고, 필요할 때 build_ops.py 를 직접 돌린다.
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable

THEME_INLINE = ("import sys, json; sys.path[:0] = ['experiments/theme-monitor', 'experiments/stock-radar']; import theme_render as R; "
                "a = json.load(open('experiments/theme-monitor/output/themes_analysis.json', encoding='utf-8')); "
                "print(len(R.write_all(a, 'experiments/theme-monitor/output')), '쪽')")

QUICK_INLINE = ("import shutil, subprocess, sys, tempfile, os; src = 'experiments/stock-quick/output/quick-data'; "
                "tmp = tempfile.mkdtemp(); shutil.copytree(src, os.path.join(tmp, 'd')); "
                "sys.exit(subprocess.run([sys.executable, 'experiments/stock-quick/mock_quick_page.py', '--data', os.path.join(tmp, 'd')]).returncode)")   # mock_quick_page 가 quick-data 를 지우고 다시 채워 사본에서 읽는다

# (묶음 이름, 명령) — 명령은 저장소 맨 위에서 돈다
JOBS = [
    ("미국 종목 · 목록", ["experiments/stock-radar/main.py", "--cached"]),
    ("한국 종목 · 목록", ["experiments/kr-stocks/main_kr.py", "--cached"]),
    ("ETF · 미국", ["experiments/stock-etf/etf_pages.py", "--market", "us"]),   # 발행 코드 그대로(mock_etf.py 는 옛 A안 시안 4개 — 같은 파일 이름을 덮어써서 쓰지 않는다)
    ("ETF · 한국", ["experiments/stock-etf/etf_pages.py", "--market", "kr"]),   # ETF 만 야후 시세 · 운용사 구성을 읽는다(읽기만 · 쓰기 · AI 0)
    ("간단 종목", ["-c", QUICK_INLINE]),   # 카드 조각은 collect_quick(인터넷)이 만든다 — 여기선 받아 둔 조각(output/quick-data)으로 겉 페이지만 다시 감싼다
    ("미국 증시 리포트", ["experiments/daily-report/render_html.py"]),
    ("한국 증시 리포트", ["experiments/kr-market-report/main.py", "--cached"]),
    ("인물 발언", ["experiments/people-radar/render_html.py"]),
    ("테마", ["-c", THEME_INLINE]),
    ("증시 전망 · 페이지 · 목록", ["experiments/issue_store/hypo_pages.py"]),
    ("증시 전망 · 경우의 수", ["experiments/issue_store/forecast_cases.py"]),
    ("증시 전망 · 한국 근거", ["experiments/issue_store/mock_kr_why.py"]),
    ("증시 전망 · 홈 카드", ["experiments/issue_store/home_mock.py"]),
    ("Hot Issue", ["experiments/issue_store/mock_issue_watch.py"]),
    ("종목 새 카드 · 실적 예상 · 업종 순위", ["experiments/stock-radar/mock_earn_mom.py"]),   # 스페이스X · 엔비디아 (2026-11-20, 받아 둔 data/mock_earn_mom.json 으로)
    ("Hot Issue · 종목 이슈", ["experiments/issue_store/mock_stock_issue.py"]),   # 엔비디아 CEO 사임 시안 (2026-11-15)
    ("디자인 샘플 · 그래프", ["experiments/design-samples/build_graphs.py"]),
    ("디자인 샘플 · 팝업", ["experiments/design-samples/build_popups.py"]),
    ("디자인 샘플 · 아이콘 라벨", ["experiments/design-samples/build_samples.py"]),
    ("디자인 샘플 · 브랜드", ["experiments/design-samples/build_brand.py"]),
    ("내 종목", ["experiments/my-stocks/mock_my_stocks.py"]),
    ("검색 · 질문하기", ["experiments/site-search/mock_search.py"]),
    ("주식 공부", ["experiments/course/render_course.py"]),
    ("주식 공부 · 목록", ["experiments/course/render_list.py"]),
    ("홈 나누기", ["experiments/home-split/mock_home_split.py"]),   # 테마 미리보기(build_theme --preview) → 미국 · 한국 홈 — 주식 공부 배너 포함 (2026-11-15)
    ("홈 증시시황 C안", ["experiments/market-commentary/mock_home_commentary.py"]),   # 테마(index.html) 복사 → 미국 · 한국 홈 C안 (2026-11-17, 11-18 JOBS 추가)
    ("종목별 토론방", ["experiments/stock-board/mock_board.py"]),   # 엔비디아 목업 뒤에 돌아야 한다(미국 종목 · 목록 다음) (2026-11-20)
    ("시장 지도", ["experiments/market-map/mock_map.py"]),   # 받아 둔 목록 파일(output/lists_*.json)로 다시 그림 — 인터넷 0 (2026-11-22)
]


def main(words):
    jobs = [j for j in JOBS if not words or any(w in j[0] for w in words)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        import certifi   # 맥 파이썬 인증서 — 혹시 읽기 요청이 있어도 막히지 않게
        env.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass
    bad = []
    t0 = time.time()
    for name, args in jobs:
        if args[0] != "-c" and not os.path.exists(os.path.join(ROOT, args[0])):
            print(f"[건너뜀] {name}: {args[0]} 없음")
            bad.append(name)
            continue
        t = time.time()
        r = subprocess.run([PY, *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        took = time.time() - t
        if r.returncode:
            tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
            print(f"[실패] {name} ({took:.0f}초): {tail[0][:160]}")
            bad.append(name)
        else:
            print(f"[완료] {name} ({took:.0f}초)")
    print(f"\n{len(jobs) - len(bad)}/{len(jobs)} 묶음 다시 그림 · {time.time() - t0:.0f}초" + (f" · 실패 {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
