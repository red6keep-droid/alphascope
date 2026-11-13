"""국민연금 기금운용본부 공시 게시판에서 주식 대량보유 내역(분기) · 국내주식 종목별 투자 현황(연말)을 받는다 (2026-11-13 사용자 "진행해줘").

    python experiments/kr-stocks/collect_nps.py          # 주 1회만 실제로 확인(data/nps.json 의 checked), 새 공시만 PDF 를 받는다
    python experiments/kr-stocks/collect_nps.py --force  # 지금 확인

- 게시판 fund.nps.or.kr/impa/edwmpblnt/getOHEF0001M0.do (cat=QUA 분기 · YEA 연간) → 글(getOHEF0006M0.do) → 첨부 PDF(fileDown.do).
  누리집 robots.txt 없음. 같은 자료가 공공데이터포털에 이용허락 `제한 없음` 으로 있다(사용자 확인 2026-11-13, 운영지침 D4-15-1).
- 분기 PDF 줄 = `번호 종목코드 발행기관명 보고서작성기준일 지분율` — 코드가 있어 이름 짝 맞추기가 필요 없다.
- 연간 PDF 줄 = `번호 종목명 평가액(억원) 자산군 내 비중 지분율` — 이름만(nps_holdings 가 우리 종목 이름 · 정식 이름으로 찾는다).
- 처음(nps.json 이 비었을 때)은 지난 공시를 BACKFILL_YEARS 년치 받는다. 요청 사이 GAP 초. AI 0.
- 결과 = data/nps.json (kr 상태 저장소에 같이 보관) + feed_log 두 줄(운영 대시보드 `주기 자료는 제때 받았나?`).
"""

import datetime
import io
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import feed_log  # noqa: E402

BASE = "https://fund.nps.or.kr"
LIST = BASE + "/impa/edwmpblnt/getOHEF0001M0.do"
DETAIL = BASE + "/impa/edwmpblnt/getOHEF0006M0.do"
FILE = BASE + "/fileDown.do"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
GAP = 2.0
CHECK_DAYS = 7
BACKFILL_YEARS = 3
PATH = os.path.join(HERE, "data", "nps.json")
FEED_Q, FEED_Y = "국민연금 대량보유 내역", "국민연금 국내주식 투자 현황"
T_Q = re.compile(r"주식 대량보유 내역\((\d{4})\.\s*(\d)분기\)")
T_Y = re.compile(r"국내주식 종목별 투자 현황\((\d{4})년 말\)")
ROW_Q = re.compile(r"^\d+\s+(\d{6})\s+(.+?)\s+(\d{4}-\d{2}-\d{2})\s+([\d.]+)\s*$")
ROW_Y = re.compile(r"^\d+\s+(.+?)\s+([\d,]+)\s+([\d.]+)%\s+([\d.]+)%\s*$")

_last = [0.0]


def _get(url, method="GET", data=None):
    wait = GAP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    r = requests.request(method, url, data=data, headers={"User-Agent": UA}, timeout=40)
    _last[0] = time.time()
    r.raise_for_status()
    return r


def list_posts(cat, pages):
    """게시판 목록 → [(글번호, 제목, 등록일)]."""
    out = []
    for pg in range(1, pages + 1):
        t = _get(LIST, "POST", {"cat": cat, "pageIndex": pg}).text
        rows = re.findall(r"fnc_goBbsDetail\('(\d+)'\);\"[^>]*>\s*([^<]+?)\s*<.*?(\d{4}/\d{2}/\d{2})", t, re.S)
        if not rows:
            break
        out += [(sn, title, day.replace("/", "-")) for sn, title, day in rows]
    return out


def attachment(sn, cat):
    t = _get(DETAIL, "POST", {"tmpltdataSn": sn, "cat": cat}).text
    m = re.search(r"fncAtchFileDownload\('([^']+)',\s*'(\d+)'\)", t)
    if not m:
        raise ValueError(f"첨부 파일 없음 (글 {sn})")
    return _get(f"{FILE}?atchFileId={m.group(1)}&atchFileSn={m.group(2)}").content


def pdf_lines(blob):
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(blob))
    return [ln.strip() for p in r.pages for ln in (p.extract_text() or "").splitlines()]


def parse_q(blob):
    rows = [[m.group(1), m.group(2), m.group(3), float(m.group(4))] for m in map(ROW_Q.match, pdf_lines(blob)) if m]
    if len(rows) < 10:
        raise ValueError(f"분기 PDF 줄이 {len(rows)}개뿐 — 형식이 바뀌었을 수 있음")
    return rows


def parse_y(blob):
    rows = [[m.group(1), float(m.group(4))] for m in map(ROW_Y.match, pdf_lines(blob)) if m]
    if len(rows) < 100:
        raise ValueError(f"연간 PDF 줄이 {len(rows)}개뿐 — 형식이 바뀌었을 수 있음")
    return rows


def load():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"checked": "", "major": {}, "annual": {}}


def save(d):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def _q_end(y, q):
    return datetime.date(y, q * 3, 31 if q in (1, 4) else 30)


def run(force=False):
    d = load()
    today = datetime.date.today()
    if not force and d.get("checked") and (today - datetime.date.fromisoformat(d["checked"])).days < CHECK_DAYS:
        print(f"[nps] {d['checked']} 에 확인함 — 건너뜀 (주 1회)")
        return d
    first = not d.get("major")
    since = today.year - BACKFILL_YEARS
    for cat, pat, key, parse, feed_name in (("QUA", T_Q, "major", parse_q, FEED_Q), ("YEA", T_Y, "annual", parse_y, FEED_Y)):
        new, err = 0, ""
        try:
            posts = list_posts(cat, 15 if first else 2)
            for sn, title, posted in posts:
                m = pat.search(title)
                if not m or sn in d[key] or int(m.group(1)) < since:
                    continue
                try:
                    rows = parse(attachment(sn, cat))
                    label = f"{m.group(1)}년 {m.group(2)}분기" if key == "major" else f"{m.group(1)}년 말"
                    d[key][sn] = {"title": title, "label": label, "posted": posted, "rows": rows,
                                  "end": (_q_end(int(m.group(1)), int(m.group(2))) if key == "major" else datetime.date(int(m.group(1)), 12, 31)).isoformat()}
                    new += 1
                    print(f"[nps] {title} — {len(rows)}줄")
                except Exception as e:  # noqa: BLE001 — 한 공시 실패가 나머지를 막지 않게
                    err = f"{title}: {str(e)[:120]}"
                    print(f"::warning::[nps] {err}")
        except Exception as e:  # noqa: BLE001
            err = f"게시판 목록 실패: {str(e)[:120]}"
            print(f"::warning::[nps] {err}")
        latest = max(d[key].values(), key=lambda x: x["end"], default=None)
        if latest:   # 다음 새 자료 기한 — 분기 = 다음 분기 끝 + 45일, 연간 = 다음 해 말 + 10개월(지난 공시가 9~10월)
            end = datetime.date.fromisoformat(latest["end"])
            if key == "major":
                nq = (end.month // 3) % 4 + 1
                ny = end.year + (1 if nq == 1 else 0)
                expect = (_q_end(ny, nq) + datetime.timedelta(days=45)).isoformat()
            else:   # 2025년 말 자료(2026년 가을 공시) 다음 = 2026년 말 자료, 2027-10-31 까지
                expect = datetime.date(end.year + 2, 10, 31).isoformat()
        else:
            expect = ""
        feed_log.feed(feed_name, ok=not err and latest is not None, label=latest["label"] if latest else "", data_date=latest["end"] if latest else "",
                      got_new=new > 0, error=err or ("받은 공시 없음" if latest is None else ""), every_days=CHECK_DAYS, expect_new=expect,
                      detail=f"{len(d[key])}건 보관 · 이번에 {new}건 새로")
    d["checked"] = today.isoformat()
    save(d)
    return d


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run(force="--force" in sys.argv)
