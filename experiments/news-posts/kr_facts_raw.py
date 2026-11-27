"""한국 기사 원본 기록 — 수집기 블로그 저장소의 facts · headlines 문서를 실행마다 그대로 남긴다.

    FIREBASE_SERVICE_ACCOUNT=<블로그 서비스 계정 키> python experiments/news-posts/kr_facts_raw.py --out store
    python experiments/news-posts/kr_facts_raw.py --out store --gcloud <계정>        # 로컬 시험

왜: kr_facts_store.py 의 날짜 파일은 그날 가장 늦은 실행 하나만 남긴다(16:30 실행이 같은 날 07:00 을 덮음).
    수집기는 30일 뒤 문서를 지운다. 헌법 제4조 4항 — 다시 모을 수 없는 자료(그날의 사건 묶음 · 기사 제목)를 먼저 지킨다.
무엇을: --out/kr/raw/facts/{문서id}.json.gz · --out/kr/raw/headlines/{문서id}.json.gz — 받은 그대로(거르지 않음, 1곳 보도 사건 포함).
    이미 있는 파일은 다시 쓰지 않는다(지우지 않고 · 덮지 않고 쌓기). 비공개 상태 저장소(kr-facts 브랜치)에만 — gh-pages 에 올리지 않는다.
크기: 실행당 facts 약 14KB · headlines 약 40KB(gzip, 11-24 실측) → 하루 약 150KB · 1년 약 55MB.
"""
import argparse
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def save(out, col, docs):
    d = os.path.join(out, "kr", "raw", col)
    os.makedirs(d, exist_ok=True)
    new = 0
    for x in docs:
        p = os.path.join(d, f'{x["id"]}.json.gz')
        if os.path.exists(p):
            continue
        with gzip.open(p, "wt", encoding="utf-8") as f:
            json.dump(x, f, ensure_ascii=False)
        new += 1
    return new, len(os.listdir(d))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--gcloud", metavar="ACCOUNT")
    a = ap.parse_args()
    import fetch_samples as F
    c = F.gcloud_token(a.gcloud) if a.gcloud else F.creds()
    for col in ("facts", "headlines"):
        new, total = save(a.out, col, F.docs(c, col))
        print(f"원본 {col}: 새로 {new}개 · 모두 {total}개")


if __name__ == "__main__":
    main()
