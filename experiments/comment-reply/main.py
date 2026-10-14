"""댓글 자동 답글 — 완전 자동 (감지 → Gemini 답글 → Firestore 에 직접 게시 → Slack 알림)

2026-10-14 댓글이 블로거에서 우리 것(Firebase)으로 옮겨 가면서 바뀌었다 (사용자: "완전자동으로 해").
예전에는 블로거 API 에 댓글 쓰기가 없어 Slack 으로 답글을 보내고 사람이 붙여넣었다.

흐름:
  1. Firestore 컬렉션 그룹 질의로 모든 글의 댓글을 읽는다 (firestore_client)
  2. 주인 댓글 · 처리한 댓글 · 주인이 이미 그 뒤에 답한 스레드는 건너뛴다
  3. Gemini 로 답글 생성 — 글 제목은 블로거 API 에서
  4. 답글을 주인 UID 로 Firestore 에 쓴다 (화면에는 AlphaScope · 로고)
     Gemini 가 SPAM 이라 하면 그 댓글을 지운다
  5. 한 일을 Slack 으로 알린다 (실패해도 게시는 그대로)

처리 이력은 output/state.json 의 "fs_processed" (CI 는 comment-state 브랜치). 이 키가 없으면
첫 실행으로 보고 지금 있는 댓글을 모두 '처리됨'으로만 등록한다 — 옛 댓글에 뒤늦게 답하지 않게.

사용법 (리포 루트에서):
    python experiments/comment-reply/main.py                         # dry-run (게시 · 삭제 · 알림 없이 미리보기)
    python experiments/comment-reply/main.py --send                  # 실제 게시 · 삭제 · Slack
    python experiments/comment-reply/main.py --baseline              # 지금 댓글을 모두 '처리됨'으로 등록만
    python experiments/comment-reply/main.py --test-notification     # Slack 테스트 메시지
    python experiments/comment-reply/main.py --test-comment "안녕하세요!"   # 가상 댓글로 답글 생성만 확인 (게시 안 함)
"""

import argparse
import datetime
import sys

from dotenv import load_dotenv

import blogger_client
import firestore_client
import generate_reply
import notify_slack
import state

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

KST = datetime.timezone(datetime.timedelta(hours=9))


def _now():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def format_message(kind, comment, post, reply):
    head = {"reply": "💬 댓글에 자동 답글을 올렸습니다", "spam": "🗑 스팸으로 보고 댓글을 지웠습니다",
            "preview": "👀 [dry-run] 올릴 답글 미리보기"}[kind]
    lines = [
        f"{head} ({_now()} KST)",
        "",
        f"👤 작성자: {comment.get('name') or '익명'}",
        f"📝 게시글: {post.get('title', '')}",
        f"💬 댓글: {comment.get('text', '').strip()}",
    ]
    if kind != "spam":
        lines += ["", f"🤖 답글:\n{reply}"]
    if post.get("url"):
        lines += ["", f"🔗 {post['url']}#c{comment['id']}"]
    return "\n".join(lines)


def threads_answered(comments, owner_uid):
    """주인이 그 댓글 뒤에 같은 스레드에 쓴 적이 있으면 이미 답한 것으로 본다 (사람이 먼저 답한 경우)."""
    last_owner = {}
    for c in comments:
        if c["uid"] == owner_uid:
            key = c["parent"] or c["id"]
            last_owner[key] = max(last_owner.get(key, ""), c["created"])
    return lambda c: last_owner.get(c["parent"] or c["id"], "") > c["created"]


def main():
    parser = argparse.ArgumentParser(description="댓글 자동 답글 (Firestore, 완전 자동)")
    parser.add_argument("--send", action="store_true", help="실제 게시 · 삭제 · Slack (기본은 dry-run)")
    parser.add_argument("--baseline", action="store_true", help="지금 댓글을 처리됨으로 등록만")
    parser.add_argument("--test-notification", action="store_true", help="Slack 테스트 메시지 발송")
    parser.add_argument("--test-comment", metavar="TEXT", help="가상 댓글로 답글 생성만 확인 (게시 안 함)")
    parser.add_argument("--max", type=int, default=10, help="1회 최대 처리 댓글 수 (기본 10)")
    args = parser.parse_args()

    load_dotenv()

    if args.test_notification:
        notify_slack.send(f"✅ 알파스코프 댓글 알림 테스트 ({_now()} KST)\nSlack 연동이 정상입니다.")
        print("[Slack] 테스트 메시지 전송 완료")
        return

    blogger = blogger_client.BloggerClient()

    if args.test_comment:
        post = blogger.get_latest_post()
        reply = generate_reply.generate_reply(post["title"], args.test_comment, "테스트 사용자")
        print(format_message("preview", {"id": "test", "name": "테스트 사용자", "text": args.test_comment}, post, reply))
        return

    fs = firestore_client.FirestoreClient()
    comments = fs.list_comments()
    processed = state.load()

    if args.baseline or processed is None:
        state.save([c["id"] for c in comments])
        print(f"[baseline] 지금 댓글 {len(comments)}건을 '처리됨'으로 등록했습니다. 답글 없음.")
        return

    answered = threads_answered(comments, fs.owner_uid)
    done = set(processed)
    new = [c for c in comments if c["id"] not in done and c["uid"] != fs.owner_uid]
    skipped = [c for c in new if answered(c)]
    todo = [c for c in new if not answered(c)][: args.max]
    print(f"댓글 {len(comments)}건 | 새 댓글 {len(new)}건 (주인이 이미 답함 {len(skipped)}건) | 이번에 처리 {len(todo)}건")

    handled = [c["id"] for c in skipped]
    posts = {}
    for c in todo:
        try:
            if c["post_id"] not in posts:
                posts[c["post_id"]] = blogger.get_post(c["post_id"])
            post = posts[c["post_id"]]
            reply = generate_reply.generate_reply(post.get("title", ""), c["text"], c["name"])
            spam = reply.strip().upper() == "SPAM"
            if not args.send:
                print("=" * 60)
                print(("[dry-run] 스팸 판정 — 실제로는 지운다\n" if spam else "") + format_message("spam" if spam else "preview", c, post, reply))
                continue
            if spam:
                fs.delete_comment(c["post_id"], c["id"])
            else:
                fs.add_reply(c["post_id"], c["parent"] or c["id"], reply)
            print(f"[게시] comment={c['id']} → {'삭제(스팸)' if spam else '답글'}")
            handled.append(c["id"])
            try:
                notify_slack.send(format_message("spam" if spam else "reply", c, post, reply))
            except Exception as e:
                print(f"[Slack] 알림 실패 (게시는 끝남): {e}")
        except Exception as e:
            print(f"[오류] comment={c['id']} 처리 실패 (다음 실행에 다시): {e}")

    if handled and args.send:
        state.save(sorted(done | set(handled)))
        print(f"[state] 처리됨 {len(handled)}건 저장 -> {state.STATE_FILE}")


if __name__ == "__main__":
    main()
