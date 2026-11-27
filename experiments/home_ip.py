"""집 IP(집 공유기 VPN)로만 받는 곳 — GitHub 실행기(해외 데이터센터 주소)는 막고 한국 가정 주소는 받는 사이트.

막힌 곳(11-17 시험, News-sub trial run 44086583552 — 바로 = GitHub 주소, 집 = VPN):
  - 미래에셋 TIGER 상품 페이지 · 구성 JSON   바로 403 · 집 200
  - 마이클 버리 substack RSS                 바로 403 · 집 200
  - 비즈니스포스트 RSS                       바로 약 85% 403(CloudFront, 실행기 IP 마다 다름) · 집 200
  (국민연금 공시는 바로도 200 — 11-16 실패는 일시적, 집 IP 에 넣지 않는다)

흐름: 하루 한 번 14:30 KST `.github/workflows/home-ip.yml` 이 VPN 을 열어 이 곳들만 받아 비공개 상태 저장소
`homeip-state` 브랜치(experiments/home-ip/data/)에 둔다 → 한국 종목(16:10) · 인물 발언(08:00) 실행은 그 파일만 읽는다.
GitHub 실행 중에는 이 곳들에 직접 요청하지 않는다(어차피 403).

지킬 것:
  - 집 IP 로 가는 요청은 여기 적힌 곳만 — 유튜브 수집이 같은 집 IP 를 쓴다(늘리면 그쪽 차단 위험).
  - 공유기 L2TP 는 동시 접속을 못 버틴다(11-17 시험: 둘째 접속이 곧 끊김) → 유튜브 수집이 비는 12~17시에만, 도는 중이면 기다림.
"""

import os

import requests
from requests.adapters import HTTPAdapter

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.environ.get("HOMEIP_DIR") or os.path.join(HERE, "home-ip", "data")

# 집 IP 로 받아 파일로 두는 RSS — 주소 → 파일 이름
FEEDS = {
    "https://michaeljburry.substack.com/feed": "burry_feed.xml",
    "https://www.businesspost.co.kr/rss/Article.xml": "businesspost_feed.xml",   # 한국 기사 공용 저장소(만들기 전)가 읽을 곳 — 피드 약 5일치 · 약 480KB
}
MIRAE_FILE = "mirae.json"   # 미래에셋 TIGER 구성 · 보수 — {sym: kr_holdings._mirae 결과 + got}


def on_github():
    return os.environ.get("GITHUB_ACTIONS") == "true"


class _SourceAdapter(HTTPAdapter):
    """나가는 연결을 VPN(ppp0) 주소에 묶는다 → 정책 경로(table 100)가 집 공유기로 보낸다."""

    def __init__(self, ip, **kw):
        self._ip = ip
        super().__init__(**kw)

    def init_poolmanager(self, *a, **kw):
        kw["source_address"] = (self._ip, 0)
        return super().init_poolmanager(*a, **kw)


def session(headers=None):
    """집 IP 로 나가는 Session. HOME_SOURCE_ADDRESS(VPN 주소)가 없으면 예외 — 몰래 GitHub 주소로 나가지 않게."""
    ip = os.environ.get("HOME_SOURCE_ADDRESS", "").strip()
    if not ip:
        raise RuntimeError("집 IP(VPN) 주소 없음")
    s = requests.Session()
    a = _SourceAdapter(ip)
    s.mount("https://", a)
    s.mount("http://", a)
    if headers:
        s.headers.update(headers)
    return s


def path(name):
    return os.path.join(DIR, name)


def feed_bytes(url):
    """집 IP 로 받아 둔 RSS 내용. 없으면 None."""
    f = FEEDS.get(url)
    if not f or not os.path.exists(path(f)):
        return None
    with open(path(f), "rb") as fh:
        return fh.read()
