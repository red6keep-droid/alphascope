"""댓글 자동 답글 — 반자동(감지 → Gemini 답글 생성 → Slack 알림) 파이프라인

흐름:
  1. comments.listByBlog 로 새 댓글 감지 (중복 방지 state 는 output/state.json)
  2. 내가(블로그 소유자) 단 댓글과 스팸은 건너뜀
  3. Gemini 로 답글 생성
  4. 답글 + 원글/관리자 링크를 Slack 으로 전송
  5. 관리자가 링크에서 답글을 복사/붙여넣기해 등록 (반자동)

사용법 (리포 루트에서):
    python experiments/comment-reply/main.py                                  # dry-run (알림 없음, 감지+생성만)
    python experiments/comment-reply/main.py --send                           # Slack 실제 발송
    python experiments/comment-reply/main.py --baseline                       # 현재 댓글을 모두 '처리됨'으로 등록(알림 없음)
    python experiments/comment-reply/main.py --test-notification              # Slack 테스트 메시지 발송
    python experiments/comment-reply/main.py --test-comment "안녕하세요!"       # 가상 댓글로 감지~생성 흐름 확인
    python experiments/comment-reply/main.py --test-comment "안녕하세요!" --send
"""

import argparse
import datetime
import os
import sys

from dotenv import load_dotenv

import blogger_client
import generate_reply
import notify_slack
import state

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

KST = datetime.timezone(datetime.timedelta(hours=9))
ALLOWED_STATUS = {"live"}


def _now():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def format_message(comment, post, reply, blog_id):
    content = (comment.get("content") or "").strip()
    author = (comment.get("author") or {}).get("displayName") or "익명"
    return (
        f"🆕 새 댓글 감지 ({_now()} KST)\n"
        f"\n"
        f"👤 작성자: {author}\n"
        f"📝 게시글: {post.get('title', '')}\n"
        f"💬 댓글: {content}\n"
        f"\n"
        f"🤖 자동 생성 답글:\n{reply}\n"
        f"\n"
        f"🔗 원글: {post.get('url')}\n"
        f"🛠 댓글 관리: https://www.blogger.com/blog/comments/{blog_id}\n"
        f"\n"
        f"답글을 복사해 블로그 댓글에 붙여넣어 등록하세요."
    )


def main():
    parser = argparse.ArgumentParser(description="댓글 자동 답글 (반자동) 파이프라인")
    parser.add_argument("--send", action="store_true", help="Slack 실제 발송 (기본은 dry-run)")
    parser.add_argument("--baseline", action="store_true", help="현재 댓글을 처리됨으로 등록만 (알림 없음)")
    parser.add_argument("--test-notification", action="store_true", help="Slack 테스트 메시지 발송")
    parser.add_argument("--test-comment", metavar="TEXT", help="가상 댓글 텍스트로 감지~생성 흐름 테스트")
    parser.add_argument("--include-pending", action="store_true", help="승인 대기(PENDING) 댓글도 처리")
    parser.add_argument("--max", type=int, default=10, help="1회 최대 처리 댓글 수 (기본 10)")
    args = parser.parse_args()

    load_dotenv()

    if args.test_notification:
        notify_slack.send(
            f"✅ 알파스코프 댓글 알림 테스트 ({_now()} KST)\n"
            "Slack 연동이 정상입니다."
        )
        print("[Slack] 테스트 메시지 전송 완료")
        return

    client = blogger_client.BloggerClient()
    self_id = client.self_id()
    processed = state.load()

    if args.test_comment:
        post = client.get_latest_post()
        fake = {
            "id": "test-comment",
            "author": {"displayName": "테스트 사용자"},
            "content": args.test_comment,
            "status": "live",
            "post": {"id": post["id"]},
        }
        if args.send:
            reply = generate_reply.generate_reply(post["title"], fake["content"], "테스트 사용자")
            msg = format_message(fake, post, reply, client.blog_id)
            notify_slack.send(msg)
            print("[Slack] 발송 완료")
        else:
            print("=" * 60)
            print("[테스트 dry-run] 생성될 메시지 미리보기")
            print("=" * 60)
            print(f"[Gemini] 답글 생성 (가상 댓글: {args.test_comment!r})")
            reply = generate_reply.generate_reply(post["title"], fake["content"], "테스트 사용자")
            print(format_message(fake, post, reply, client.blog_id))
        return

    comments = client.list_comments()
    first_run = not os.path.exists(state.STATE_FILE)
    if args.baseline or first_run:
        processed = [str(c["id"]) for c in comments]
        state.save(processed)
        print(f"[baseline] 현재 댓글 {len(processed)}건을 '처리됨'으로 등록했습니다. 알림 없음.")
        return

    allowed = set(ALLOWED_STATUS)
    if args.include_pending:
        allowed.add("pending")

    new_comments = [
        c for c in comments
        if str(c["id"]) not in processed
        and c.get("author", {}).get("id") != self_id
        and str(c.get("status", "")).lower() in allowed
    ]
    new_comments = new_comments[: args.max]

    print(f"댓글 총 {len(comments)}건 | new {len(new_comments)}건 (자기/중복/스팸 제외)")

    if not new_comments:
        print("새 댓글 없음. 완료.")
        return

    handled = []
    for c in new_comments:
        cid = str(c["id"])
        try:
            post = client.get_post(c["post"]["id"])
            reply = generate_reply.generate_reply(
                post.get("title", ""), (c.get("content") or ""), c.get("author", {}).get("displayName", "")
            )
            msg = format_message(c, post, reply, client.blog_id)
            if args.send:
                notify_slack.send(msg)
                print(f"[Slack] 발송 완료 (comment={cid})")
            else:
                print("=" * 60)
                print(f"[dry-run] 미리보기 — comment={cid}")
                print("=" * 60)
                print(msg)
            handled.append(cid)
        except Exception as e:
            print(f"[오류] comment={cid} 처리 실패 (재시도 대상으로 남김): {e}")

    if handled:
        processed.extend(handled)
        state.save(sorted(set(processed)))
        print(f"[state] 처리됨 {len(handled)}건 저장 완료 -> {state.STATE_FILE}")


if __name__ == "__main__":
    main()