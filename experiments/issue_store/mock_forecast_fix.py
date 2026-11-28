"""증시 전망 고침 시안 — 6-23② 성적표 비교 대상(`기록대로라면`) · 6-26 `과거 기록에서 비슷한 때는?` (지금 · 바꾼 뒤를 위아래로).
(6-22 판정 기한 · 6-23① 성적표 안내 · 6-25 안내 문장은 11-28 적용 — 지금 · 바꾼 뒤 모두에 들어 있다.)

    python experiments/issue_store/mock_forecast_fix.py --state DIR

DIR = 상태 저장소 nvda-state 의 experiments/nvda-report/output/state 를 꺼낸 자리(records/hypotheses · records/forecasts 만 있으면 됨).
DIR 은 건드리지 않는다 — 임시 폴더에 복사해 forecast_daily.run 을 두 번(H.NEXT 끔 · 켬) 돌리고, 목록 · 전망 둘을 이어 붙인다.
결과 = output/mock_forecast_fix.html (목업 목록 `증시 전망` 칸).
"""
import argparse
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.join(_HERE, "..")]
import design_kit as dk  # noqa: E402
import forecast_daily as FD  # noqa: E402
import hypo_pages as H  # noqa: E402

PAGES = [("forecast-list", "목록", "6-23② `우리 전망 성적표` 를 펼치면 `기록대로라면` 줄 — 고를 때 적어 둔 기록상 비율로 센 기대 맞음과 실제 맞음"),
         ("forecast-2026-014", "에너지 업종 급락, 반등할까 더 빠질까? (지켜보는 중 · 기록 반반)", "6-26 접는 줄 묶음에 `과거 기록에서 비슷한 때는?` — 18번 중 10번 · 반반이면 반반이라고"),
         ("forecast-2026-009", "S&P 500 급락, 반등할까 더 빠질까? (끝남 · 맞음 · 기록 뚜렷)", "6-26 같은 카드 — 48번 중 38번"),
         ("forecast-2026-010", "엔비디아 급등, 조정 올까 더 오를까? (종목 · 고르지 않음)", "6-26 종목 전망에도 같은 카드 — 우리가 고르지 않아도 기록 횟수는 보여 줌")]


def render(state, fix):
    tmp = tempfile.mkdtemp()
    st = os.path.join(tmp, "state")
    os.makedirs(os.path.join(st, "records"))
    for sub in ("hypotheses", "forecasts"):
        shutil.copytree(os.path.join(state, "records", sub), os.path.join(st, "records", sub))
    out = os.path.join(tmp, "out")
    os.makedirs(os.path.join(out, "proof"))
    FD.OUT = out
    H.NEXT[0] = fix
    FD.run(st)
    H.NEXT[0] = False
    return {slug: open(os.path.join(out, f"{slug}.html"), encoding="utf-8").read() for slug, _, _ in PAGES}


def label(text, sub, top=36):
    return (f'<div style="margin:{top}px 0 4px;padding-top:12px;border-top:2px solid #111;font-size:18px;line-height:26px;font-weight:700;color:#111;">{dk.esc(text)}</div>'
            f'<div style="margin:0 0 8px;font-size:13px;line-height:19px;color:#6B7280;word-break:keep-all;">{dk.esc(sub)}</div>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    a = ap.parse_args()
    now, new = render(a.state, False), render(a.state, True)
    body = ('<p style="margin:16px 0 0;font-size:14px;line-height:21px;color:#6B7280;word-break:keep-all;">증시 전망 고침 시안 둘 — 페이지마다 '
            '`지금` 위 · `바꾼 뒤` 아래. 실제 등록 · 기록(11-27 종가까지)으로 그렸습니다.</p>')
    for k, (slug, name, what) in enumerate(PAGES):
        body += label(f"{name} — 지금", what, 16 if k == 0 else 48) + now[slug]
        body += label(f"{name} — 바꾼 뒤", what) + new[slug]
    print(dk.write_mock(dk.fix_colons(body), os.path.join(_HERE, "output", "mock_forecast_fix.html"), "증시 전망 고침 시안 — 성적표 비교 대상 · 과거 기록에서 비슷한 때는?"))


if __name__ == "__main__":
    main()
