"""이슈 모니터링 고정 페이지 게시 — 이슈마다 1장 (2026-11-13 사용자: 운영 연결 + 바로 공개).

    python experiments/issue_store/publish_issue.py --state "$STATE_DIR"          # 실제 게시
    python experiments/issue_store/publish_issue.py --state "$STATE_DIR" --dry    # 무엇을 만들고 / 갱신할지만

증시 전망 게시(publish_forecast.publish)를 그대로 쓴다 — 영문 주소(/p/issue-iran.html)로 만든 뒤 한글 제목(질문)으로 바꾸기,
바뀐 것이 없으면 쓰지 않기(해시), 429 백오프. 다른 것은 대상 · 본문 폴더 · 해시 파일뿐.
해시 = {state}/records/issues/page_hashes.json (상태 저장소에 같이 저장된다). AI 0.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish_forecast as PF  # noqa: E402
import mock_issue_watch as IW  # noqa: E402

OUT = os.path.join(HERE, "output", "issue")


def targets():
    out = []
    for iss in IW.ISSUES:
        slug = IW.CFG[iss["id"]]["slug"]
        path = os.path.join(OUT, f"{slug}.html")
        if os.path.exists(path):
            out.append((slug, iss["q"], slug, PF.H.page_url(slug), path))
        else:
            print(f"[issue-pages] {slug}: 본문 없음 — 건너뜀")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, "..", "..", ".env"))
    except ImportError:
        pass
    PF.targets = targets
    PF.HASHES = os.path.join(a.state, "records", "issues", "page_hashes.json")
    sys.exit(0 if PF.publish(dry=a.dry) else 1)
