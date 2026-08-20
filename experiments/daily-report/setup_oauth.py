"""OAuth 2.0 1회 승인 → refresh token 발급 (Blogger 게시용)

Google Cloud Console에서 "데스크톱 앱" OAuth 클라이언트로 만든 client_secret.json 을
이용해 브라우저에서 1회 승인하고, 아래 3개 값을 출력한다.
    BLOGGER_CLIENT_ID
    BLOGGER_CLIENT_SECRET
    BLOGGER_REFRESH_TOKEN

사용법 (리포 루트에서):
  방식 A (브라우저 자동 승인, 로컬 데스크톱):
    python experiments/daily-report/setup_oauth.py <client_secret.json 경로>

  방식 B (원격/헤드리스 — URL + 코드 2단계):
    python experiments/daily-report/setup_oauth.py <client_secret.json 경로> --auth-url
    # 1) 출력된 URL을 브라우저에서 열어 블로그 소유자 계정으로 승인
    # 2) 'All set' 화면에 표시된 인증 코드(또는 리다이렉트 URL 전체) 복사
    python experiments/daily-report/setup_oauth.py --exchange <CODE> [--save-env]

  --save-env : 발급된 3개 값을 리포 루트 .env 에 자동 기록

주의:
- OAuth consent screen이 "Testing" 상태면 refresh token이 7일마다 만료된다.
  Google Cloud Console > OAuth consent screen 에서 앱을 Publishing(Production)으로 전환할 것.
- 발급된 값 3종은 절대 커밋하지 말 것. client_secret.json 은 repo 밖에 보관하고,
  값 추출 후에는 삭제하는 것을 권장한다.
"""

import argparse
import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCOPES = ["https://www.googleapis.com/auth/blogger"]
LOOPBACK_REDIRECT = "http://localhost"
DEFAULT_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env")
PENDING_FILE = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), ".blogger-oauth", "pending_flow.pkl")
ENV_KEYS = ["BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN"]


def _load_client_info(client_secret_path):
    with open(client_secret_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    installed = data.get("installed", {})
    client_id = installed.get("client_id")
    client_secret = installed.get("client_secret")
    if not client_id or not client_secret:
        raise RuntimeError(
            f"'{client_secret_path}' 에서 client_id/client_secret 을 찾지 못했습니다. "
            "데스크톱 OAuth 클라이언트의 client_secret.json 을 사용하세요."
        )
    return client_id, client_secret


def _write_env(env_path, values):
    env_path = os.path.abspath(env_path)
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    filtered = [
        ln for ln in lines
        if "=" in ln and ln.split("=", 1)[0].strip() not in ENV_KEYS
    ]
    for key, val in values.items():
        filtered.append(f"{key}={val}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered) + "\n")
    print(f"[기록 완료] {env_path}")


def _print_values(values):
    print("=" * 60)
    print("[발급 성공] 아래 3개 값을 .env / GitHub Secrets 에 등록하세요.")
    print("=" * 60)
    for key, val in values.items():
        print(f"{key}={val}")


def main():
    parser = argparse.ArgumentParser(description="Blogger OAuth 1회 승인 → refresh token 발급")
    parser.add_argument("client_secret", nargs="?", help="client_secret.json 경로 (auth-url 모드에서 필요)")
    parser.add_argument("--auth-url", action="store_true", help="방식 B: 1단계 승인 URL 생성")
    parser.add_argument("--exchange", metavar="CODE", help="방식 B: 2단계 인증 코드로 교환")
    parser.add_argument(
        "--save-env",
        nargs="?",
        const=DEFAULT_ENV_FILE,
        help="발급된 3개 값을 .env에 기록 (기본: 리포 루트 .env)",
    )
    args = parser.parse_args()

    if args.auth_url:
        if not args.client_secret or not os.path.exists(args.client_secret):
            print(f"[오류] client_secret.json 경로가 필요합니다: {args.client_secret}")
            sys.exit(1)
        client_id, client_secret = _load_client_info(args.client_secret)
        flow = InstalledAppFlow.from_client_secrets_file(
            args.client_secret, SCOPES, redirect_uri=LOOPBACK_REDIRECT
        )
        url, _ = flow.authorization_url(
            access_type="offline", prompt="consent", include_granted_scopes="true"
        )
        os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
        with open(args.client_secret, "r", encoding="utf-8") as _f:
            _full_config = json.load(_f)
        pending = {
            "client_config": _full_config,
            "scopes": SCOPES,
            "redirect_uri": flow.redirect_uri,
            "code_verifier": flow.code_verifier,
        }
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(pending, f)
        print("=" * 60)
        print("1) 아래 URL을 브라우저에서 열어 블로그 소유자 계정으로 승인하세요.")
        print("2) 승인 후 'All set' 화면에 표시된 인증 코드를 복사하세요.")
        print("3) 아래 명령으로 코드를 교환하세요.")
        print("=" * 60)
        print(url)
        print("=" * 60)
        print(f"다음 실행: python experiments/daily-report/setup_oauth.py --exchange <CODE>")

    elif args.exchange:
        if not os.path.exists(PENDING_FILE):
            print("[오류] 저장된 승인 세션이 없습니다. --auth-url 을 먼저 실행하세요.")
            sys.exit(1)
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            pending = json.load(f)
        flow = InstalledAppFlow.from_client_config(
            pending["client_config"],
            pending["scopes"],
            redirect_uri=pending["redirect_uri"],
            code_verifier=pending.get("code_verifier"),
            autogenerate_code_verifier=False,
        )
        code = args.exchange.strip()
        if code.startswith("http"):
            code = code.split("code=")[-1].split("&")[0]
        try:
            flow.fetch_token(code=code)
        except Exception as e:
            print(f"[오류] 코드 교환 실패: {e}")
            print("코드가 잘렸는지, URL 전체가 아니라 'code=...' 값 뒤의 문자만 붙였는지 확인하세요.")
            sys.exit(1)
        os.remove(PENDING_FILE)
        creds = flow.credentials
        if not creds.refresh_token:
            print("[오류] refresh token 을 받지 못했습니다. --auth-url 을 다시 실행하세요 (prompt=consent 적용).")
            sys.exit(1)
        cfg = flow.client_config
        values = {
            "BLOGGER_CLIENT_ID": cfg["client_id"],
            "BLOGGER_CLIENT_SECRET": cfg["client_secret"],
            "BLOGGER_REFRESH_TOKEN": creds.refresh_token,
        }
        _print_values(values)
        if args.save_env:
            _write_env(args.save_env, values)

    else:
        if not args.client_secret or not os.path.exists(args.client_secret):
            print(f"[오류] client_secret.json 경로가 필요합니다: {args.client_secret}")
            sys.exit(1)
        client_id, client_secret = _load_client_info(args.client_secret)
        flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        if not creds.refresh_token:
            print("[오류] refresh token 을 받지 못했습니다.")
            sys.exit(1)
        values = {
            "BLOGGER_CLIENT_ID": client_id,
            "BLOGGER_CLIENT_SECRET": client_secret,
            "BLOGGER_REFRESH_TOKEN": creds.refresh_token,
        }
        _print_values(values)
        if args.save_env:
            _write_env(args.save_env, values)
        else:
            print("\n자동 기록을 원하면 --save-env 옵션을 붙여 다시 실행하세요.")


if __name__ == "__main__":
    main()