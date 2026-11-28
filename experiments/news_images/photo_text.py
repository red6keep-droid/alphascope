"""자료 사진 속 읽히는 글자 찾기 — macOS 내장 글자 인식(Vision). 결과 = ~/Desktop/Newfact-그림-검수/글자.json

    <pyobjc-framework-Vision 이 있는 파이썬> -I experiments/news_images/photo_text.py

- 왜(11-28 사용자): 한국 회사 · 한국 기사에 외국 간판 · 상품 글자가 보이면 안 맞는다(홈플러스 글에 노르웨이 마트 글자).
- 화면 기준: 글 폭 390 · 높이 200 띠(가운데, 세로에 가까운 사진은 위 30%)에 들어오고 글자 높이 7px 이상인 것만 = 독자 눈에 읽히는 글자.
- 남기는 것 = 글자가 든 줄 전부(로마자 2글자 이상 · 한자 · 가나 · 한글 2글자 이상). photo_store.py 가 목록 `text` 칸에 넣는다.
  photo_pick: 업종 · 사건 분류(여러 회사 · 기사가 같이 쓰는 사진) = 글자 있는 사진 X — 글자가 특정 회사 · 상표를 가리킴(11-28 사용자: 크래프톤 글에 BLACKPINK).
  회사 · 기관 · 인물 · 시장 사진은 글자 괜찮음(그 대상 자신). 한국 기사 · 회사엔 외국 글자 사진 X.
- 맥 전용 · 바깥 요청 0. pyobjc 는 프로젝트 venv 에 없다 — 따로 만든 venv 로 돌린다(python3 -m venv … && pip install pyobjc-framework-Vision pyobjc-framework-Quartz).
"""
import csv
import json
import os
import re

import Quartz
import Vision
from Foundation import NSURL

ROOT = os.path.expanduser("~/Desktop/Newfact-그림-검수")
SRCS = [os.path.join(ROOT, "완료"), os.path.join(ROOT, "AI_코스피")]
OUT = os.path.join(ROOT, "글자.json")
W, BAND, MIN_PX = 390, 200, 6
LETTERS = re.compile(r"[A-Za-z]{2,}|[\u3040-\u30ff\u4e00-\u9fff]|[\uac00-\ud7a3]{2,}")   # 글자(로마자 · 가나 · 한자 · 한글) — 숫자 · 기호만 있는 줄은 뺌


def read(f):
    src = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(f), None)
    if not src:
        return None, []
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    w, h = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(0)
    req.setRecognitionLanguages_(["en-US", "ko-KR", "zh-Hans", "ja-JP"])
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([req], None)
    dh = W * h / w
    top = max(0, (dh - BAND) * (0.3 if h > w * 0.8 else 0.5))
    hits = []
    for o in req.results() or []:
        c = o.topCandidates_(1)
        if not c or c[0].confidence() <= 0.3:
            continue
        b = o.boundingBox()
        px, ycen = b.size.height * dh, (1 - b.origin.y - b.size.height / 2) * dh
        s = str(c[0].string())
        if px >= MIN_PX and top <= ycen <= top + BAND and LETTERS.search(s):
            hits.append(s)
    return (w, h), hits


def main():
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    out = {}
    for base in SRCS:
        for dp, _, fs in os.walk(base):
            for n in fs:
                if not n.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                f = os.path.join(dp, n)
                key = os.path.relpath(f, ROOT)
                st = os.path.getmtime(f)
                if key in old and old[key].get("mtime") == st and old[key].get("v") == 2:
                    out[key] = old[key]
                    continue
                _, hits = read(f)
                out[key] = {"mtime": st, "v": 2, "text": hits}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(out), "장 · 외국 글자 보임", sum(1 for v in out.values() if v["text"]))


if __name__ == "__main__":
    main()
