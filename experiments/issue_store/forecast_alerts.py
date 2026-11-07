"""증시 전망 Slack 알림 — 망가졌을 때만, 전부 한국어, 오류 원문 · 코드 없음 (2026-11-07 사용자 요청 · 운영지침 D6-3 · alert_ko 규칙).

보내는 것(이것만):
    자료 대기   시세를 하나도 못 받아 오늘 갱신 안 함 (전날 그대로)              → 바로
    자료 누락   어느 날 시세가 비어 그날을 건너뜀 (다음 실행에 채움)            → 모아서
    판정 오류   판정 계산이 멈춤 — 페이지 갱신 안 함                            → 바로
    등록 놓침   사전 등록할 사건을 실행 실패로 놓침 / 늦게 등록                 → 모아서
    상태        전망이 무효 · 보류가 됨 (일정 변경 · 결과 판정 불능)             → 모아서
    저장 실패   기록(상태 저장소) · 게시(Blogger) 실패                           → 바로
안 보내는 것: 맞음 · 틀림 · 조짐 같은 정상 결과, AI 예비 전환(llm_chain 규칙대로 Gemini 문제만), 외부 지수(GPR · EPU) 한 줄 생략.

쓰는 법 (forecast_daily.py 에서):
    import forecast_alerts as FA
    FA.no_prices()                      # 시세 전부 실패
    FA.missing_days(["2026-11-23"])     # 빈 날
    FA.judge_failed("반도체 급락, 반등할까 더 빠질까?", e)   # 예외 e 는 종류만 한국어로 (원문 X)
    FA.registration_missed("11.17 엔비디아 실적", late=False)
    FA.status_changed("FOMC 뒤 S&P 500 은?", "무효", "일정이 12.16 으로 바뀜")
    FA.save_failed("상태 저장소", e)
전부 notify 를 거치므로 SLACK_WEBHOOK_URL 없으면 print 만 한다. 알림이 죽어도 전망은 죽지 않는다.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
import alert_ko  # noqa: E402
import notify  # noqa: E402

NAME = "증시 전망"


def _why(e):
    """예외 → 한국어 원인 한 마디. 영어 원문 · 코드 이름은 쓰지 않는다 (원문은 실행 로그에)."""
    return alert_ko.reason(f"{type(e).__name__}: {e}") or "오류"


def _md(iso):
    p = str(iso).split("-")
    return f"{p[1]}.{p[2]}" if len(p) == 3 else str(iso)


def no_prices():
    notify.now(f"{NAME} — 시세를 하나도 받지 못해 오늘은 갱신하지 않습니다 (페이지는 전날 그대로). 다음 실행에서 다시 잽니다")


def missing_days(days):
    if days:
        notify.event("자료 누락", f"{NAME} — {' · '.join(_md(d) for d in days[:3])} 시세가 비어 그날은 건너뜀 (채워지면 다시 적음)")


def judge_failed(title, e):
    notify.now(f"{NAME} — ‘{title}’ 판정 계산이 멈춤 ({_why(e)}). 페이지는 갱신하지 않음")


def registration_missed(event, late=False):
    if late:
        notify.event("등록", f"{NAME} — {event} 전망을 늦게 등록함 (감지일 실행 실패, 등록일 = 오늘로 표시)")
    else:
        notify.event("등록 놓침", f"{NAME} — {event} 전망을 사전 등록하지 못함 (사건이 이미 지나 사후 등록 안 함)")


def status_changed(title, state, why=""):
    notify.event("상태", f"{NAME} — ‘{title}’ {state}" + (f" ({why})" if why else ""))


def save_failed(where, e):
    notify.now(f"{NAME} — {where} 저장 실패 ({_why(e)}). 기록은 다음 실행에서 다시 시도")


if __name__ == "__main__":   # 로컬 확인 — 웹훅 없이 print 만
    no_prices()
    missing_days(["2026-11-23", "2026-11-24"])
    judge_failed("반도체 급락, 반등할까 더 빠질까?", KeyError("line"))
    registration_missed("11.17 엔비디아 실적")
    status_changed("FOMC 뒤 S&P 500 은?", "무효", "일정이 12.16 으로 바뀜")
    save_failed("상태 저장소", ConnectionError("Max retries exceeded with url: github.com"))
