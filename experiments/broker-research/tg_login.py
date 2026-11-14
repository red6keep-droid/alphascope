"""텔레그램 로그인 세션 만들기 — 처음 한 번만, 사용자가 터미널에서 직접 실행 (2026-11-14, 증권사 공식 텔레그램 리서치 채널 읽기용).

    .venv/bin/python experiments/broker-research/tg_login.py

- .env 의 TELEGRAM_API_ID · TELEGRAM_API_HASH 로 사용자 계정 로그인(봇은 관리자가 아닌 채널을 못 읽는다).
- 전화번호(+8210…) → 코드가 어디로 갔는지(앱 · 문자 · 이메일 · 전화) 보여 준다 → 코드 입력(`r` = 다른 방법으로 다시 받기) → (2단계 인증을 켰다면) 비밀번호.
  2026-11-14 사용자 "앱에 아무것도 안 온다" — 계정에 따라 코드가 이메일 · 문자로 가서, 보낸 곳을 화면에 알린다.
- 입력값은 화면 · 파일에 남기지 않는다. 세션 문자열은 .env 의 TELEGRAM_SESSION 한 줄로만(화면 출력 없음). 세션 = 계정 로그인과 같은 권한 — 공유 · 커밋 금지.
"""
import getpass
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV = os.path.join(ROOT, ".env")

WHERE = {   # 텔레그램이 코드를 보낸 곳 (SentCodeType…)
    "SentCodeTypeApp": "텔레그램 앱 — 대화 목록의 `Telegram`(파란 체크) 대화방",
    "SentCodeTypeSms": "문자(SMS)",
    "SentCodeTypeCall": "전화(음성으로 코드)",
    "SentCodeTypeFlashCall": "전화(걸려 오는 번호 끝자리가 코드)",
    "SentCodeTypeMissedCall": "부재중 전화(걸려 온 번호 끝자리가 코드)",
    "SentCodeTypeEmailCode": "이메일 — 텔레그램에 등록한 이메일함(스팸함도)",
    "SentCodeTypeSetUpEmailRequired": "이메일 등록이 먼저 필요 — 텔레그램 앱 설정에서 로그인 이메일을 등록한 뒤 다시",
    "SentCodeTypeFragmentSms": "Fragment(가상 번호) 쪽 문자",
    "SentCodeTypeFirebaseSms": "문자(SMS)",
    "SentCodeTypeSmsWord": "문자(SMS) — 단어로",
    "SentCodeTypeSmsPhrase": "문자(SMS) — 문장으로",
}


def env(name):
    for line in open(ENV, encoding="utf-8"):
        k, _, v = line.strip().partition("=")
        if k == name:
            return v.strip().strip("\"'")
    return ""


def save_session(value):
    lines = open(ENV, encoding="utf-8").read().splitlines()
    lines = [x for x in lines if not x.startswith("TELEGRAM_SESSION=")]
    lines.append(f"TELEGRAM_SESSION={value}")
    with open(ENV, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def where(sent):
    t = type(sent.type).__name__
    nxt = type(sent.next_type).__name__ if getattr(sent, "next_type", None) else None
    msg = f"→ 코드를 보낸 곳: {WHERE.get(t, t)}"
    if nxt:
        msg += f"\n  (안 오면 코드 칸에 r 을 넣으면 다음 방법으로 다시 보냅니다: {WHERE.get(nxt, nxt)})"
    if getattr(sent, "timeout", None):
        msg += f"\n  다시 보내기는 {sent.timeout}초 뒤부터"
    print(msg)


def main():
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon import errors, functions
    api_id, api_hash = env("TELEGRAM_API_ID"), env("TELEGRAM_API_HASH")
    if not re.fullmatch(r"\d+", api_id or "") or len(api_hash) != 32:
        sys.exit(".env 의 TELEGRAM_API_ID(숫자) · TELEGRAM_API_HASH(32자)를 확인해 주세요.")
    phone = re.sub(r"[\s\-]", "", input("전화번호 (010-1234-5678 → +821012345678): "))
    if phone.startswith("010"):
        phone = "+82" + phone[1:]   # 010 으로 넣어도 국제 형식으로 바꾼다
    print(f"보낼 번호: {phone[:5]}…{phone[-2:]}")
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    client.connect()
    try:
        try:
            sent = client.send_code_request(phone)
        except errors.PhoneNumberInvalidError:
            sys.exit("번호 형식이 맞지 않습니다. +8210 으로 시작하는지 확인해 주세요.")
        except errors.PhoneNumberBannedError:
            sys.exit("이 번호는 텔레그램에서 막혀 있습니다.")
        except errors.FloodWaitError as e:
            sys.exit(f"시도가 많아 텔레그램이 잠시 막았습니다. {e.seconds // 60}분 {e.seconds % 60}초 뒤 다시 해 주세요.")
        except errors.ApiIdInvalidError:
            sys.exit("api_id · api_hash 가 맞지 않습니다. my.telegram.org 의 값을 다시 확인해 주세요.")
        where(sent)
        while True:
            code = input("받은 코드 (안 오면 r): ").strip()
            if code.lower() == "r":
                try:
                    sent = client(functions.auth.ResendCodeRequest(phone, sent.phone_code_hash))
                    where(sent)
                except errors.RPCError as e:
                    print(f"다시 보내기 실패: {e.__class__.__name__} — 잠시 뒤 r 을 다시 넣거나 처음부터 다시 실행해 주세요.")
                continue
            try:
                client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
                break
            except errors.SessionPasswordNeededError:
                client.sign_in(password=getpass.getpass("2단계 인증 비밀번호: "))
                break
            except (errors.PhoneCodeInvalidError, errors.PhoneCodeEmptyError):
                print("코드가 맞지 않습니다. 다시 넣어 주세요.")
            except errors.PhoneCodeExpiredError:
                print("코드가 만료됐습니다. r 로 다시 받아 주세요.")
        me = client.get_me()
        save_session(client.session.save())
        print(f"로그인 완료: {me.first_name or ''} — 세션을 .env 의 TELEGRAM_SESSION 에 저장했습니다(화면에는 출력하지 않음).")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
