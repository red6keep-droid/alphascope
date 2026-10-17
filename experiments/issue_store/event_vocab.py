"""사건표 세부 종류 어휘 (2026-10-17 사용자 확정) — 세부 종류 21개, 세부 종류마다 대분류 하나.

사건표 events_curated.csv 의 subkind 는 이 어휘만 쓴다. 기사에서 온 원래 표현은 detail 칸에 남긴다.
대분류는 세부 종류가 정한다 (같은 세부 종류가 대분류 여럿에 흩어지면 같은 종류끼리 비교가 깨진다).

    .venv/bin/python experiments/issue_store/event_vocab.py   # 사건표에 적용 (여러 번 돌려도 같음)
"""
import os
import sys

import pandas as pd

# 세부 종류: (대분류, 묶은 원래 표현)
VOCAB = {
    "전쟁 · 테러": ("지정학", ["전쟁 발발", "테러", "테러 공격", "중동 사태 · 유가 급등"]),
    "휴전 · 종전": ("지정학", ["휴전 기대", "휴전", "전쟁 조기 종결 기대"]),
    "재난 · 팬데믹": ("지정학", ["팬데믹", "백신", "자연재해"]),
    "해외 금융위기": ("지정학", ["해외 위기", "해외 폭락", "외환위기 충격", "국가 부도", "해외 위기 · 유럽 재정위기",
                          "해외 위기 · 신흥국 통화 급락", "해외 위기 · 그리스 사태", "해외 재정 위기", "해외 재정",
                          "유로화 급락", "금 폭락 · 중국 GDP 부진", "유가 급락 · 해외 위기"]),
    "선거 · 정치": ("지정학", ["해외 정치", "해외 정치 · 이탈리아 총선", "미국 대선", "정치 충격", "미국 정치", "정권 교체"]),
    "미국 재정 · 부채한도": ("정책 · 규제", ["대선 · 재정절벽", "재정절벽 합의", "부채한도 협상", "정부 셧다운", "재정 정책",
                                  "신용등급 강등"]),
    "관세 · 무역": ("정책 · 규제", ["관세", "관세 유예"]),
    "규제 (수출 · 반독점)": ("정책 · 규제", ["수출 규제", "반독점"]),
    "환율 · 개입": ("정책 · 규제", ["G7 환율 성명", "환율 공동 개입", "환율 정책", "환율 개입", "환율 구두 개입", "환율 절하",
                              "엔화 약세", "아베노믹스 · 엔 약세", "원유 · 엔화 급변"]),
    "유가 충격": ("수급 · 변동성 충격", ["유가 급락", "유가 폭락", "유가 급등", "유가 급락 · OPEC 감산 거부", "원유 공급 충격",
                                "허리케인 공급 차질"]),
    "연준 긴축 신호": ("금리 · 중앙은행", ["긴축 신호", "금리 인상 우려", "긴축 우려", "금리 급등", "채권 매도 국면", "FOMC 의사록",
                                 "연준 의장 발언"]),
    "연준 완화": ("금리 · 중앙은행", ["금리 인하", "깜짝 완화", "양적완화 도입", "금리 인하 기대"]),
    "해외 중앙은행": ("금리 · 중앙은행", ["해외 금리 인상", "ECB 발언 · 원자재 급락", "해외 중앙은행", "ECB 완화 기대 미달"]),
    "경제지표 충격": ("경제지표", ["고용 충격", "임금 지표 둔화", "소비자신뢰 하락", "고용 · 제조업 충격", "제조업 지표 충격",
                            "금리 역전", "물가 충격"]),
    "금융기관 부실 · 신용경색": ("수급 · 변동성 충격", ["대형 파산", "은행 파산", "금융기관 구제", "구제 법안", "서브프라임 위기",
                                         "신용 경색", "금융위기", "금융 규제"]),
    "시장 구조 사고": ("수급 · 변동성 충격", ["플래시 크래시", "변동성 상품 붕괴", "밈 주식", "엔캐리 청산", "헤지펀드 붕괴",
                                   "안전자산 선호"]),
    "기술주 · 반도체 급락": ("수급 · 변동성 충격", ["거품 붕괴", "기술주 급락", "반도체 급락", "약세장 진입"]),
    "투매 뒤 반등 · 바닥": ("수급 · 변동성 충격", ["바닥", "급락 후 반등", "기술주 반등"]),
    "실적 · 전망": ("실적", ["실적 전망 상향", "실적 발표", "실적 경고", "대형 기술주 실적", "반도체 업황 · 실적 경고"]),
    "애널리스트 의견": ("기업", ["애널리스트 강등"]),
    "기업 사업 소식": ("기업", ["대형 공급 계약", "경쟁사 인수합병", "신제품 발표", "모바일 기대", "언론 보도", "기술 테마", "AI 경쟁"]),
}
ALIAS = {a: s for s, (_, al) in VOCAB.items() for a in al}


def check(ev: pd.DataFrame) -> None:
    """어휘 밖 세부 종류 · 어긋난 대분류가 있으면 멈춘다 (사람이 사건표를 고친 뒤 실수 방지)."""
    bad = ev[~ev.subkind.isin(VOCAB.keys())]
    if len(bad):
        raise SystemExit(f"사건표 세부 종류가 어휘 밖: {sorted(bad.subkind.unique())} — event_vocab.py 를 돌리거나 VOCAB 에 넣을 것")
    wrong = ev[ev.kind != ev.subkind.map(lambda s: VOCAB[s][0])]
    if len(wrong):
        raise SystemExit(f"대분류가 세부 종류와 어긋남: {wrong[['start', 'kind', 'subkind']].to_dict('records')}")


def main():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events_curated.csv")
    ev = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "detail" not in ev.columns:   # 원래 표현 보존 — subkind 바로 뒤
        ev.insert(ev.columns.get_loc("subkind") + 1, "detail", ev.subkind)
    unknown = sorted(set(ev.subkind) - set(VOCAB) - set(ALIAS))
    if unknown:
        sys.exit(f"어휘에 없는 표현: {unknown}")
    ev["subkind"] = ev.subkind.map(lambda s: s if s in VOCAB else ALIAS[s])
    ev["kind"] = ev.subkind.map(lambda s: VOCAB[s][0])
    check(ev)
    ev.to_csv(path, index=False)
    print(f"사건 {len(ev)}건 · 세부 종류 {ev.subkind.nunique()}개")
    print(ev.groupby(["kind", "subkind"]).size().to_string())


if __name__ == "__main__":
    main()
