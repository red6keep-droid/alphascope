"""공개 저장소 커밋 검사 — 헌법 제11조(공개되는 곳에는 내부 사정을 남기지 않는다)를 커밋마다 기계로 본다.

    git config core.hooksPath .githooks        # 한 번만 (PC 마다)
    python .githooks/check_public.py diff      # 지금 고친 것(커밋 전)을 미리 검사

pre-commit  = 이번 커밋에 더해지는 줄만 본다(지난 이력은 고쳐 쓰지 않음 — 제11조 끝).
commit-msg  = 커밋 메시지를 본다.
걸리면 커밋을 멈추고 파일:줄 · 규칙 이름만 찍는다 — 찾은 값 자체는 찍지 않는다(비밀이 터미널 · 로그에 남지 않게).
"""
import re
import subprocess
import sys

# ① 비밀값 — 키 · 토큰 · 비밀번호
SECRET = [
    ("Google API 키", r"AIza[0-9A-Za-z_\-]{35}"),
    ("GitHub 토큰", r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{30,}|\bgithub_pat_[0-9A-Za-z_]{40,}"),
    ("Groq 키", r"\bgsk_[0-9A-Za-z]{30,}"),
    ("NVIDIA 키", r"\bnvapi-[0-9A-Za-z_\-]{30,}"),
    ("Anthropic · OpenAI 키", r"\bsk-(?:ant-)?[0-9A-Za-z_\-]{30,}"),
    ("Slack 토큰 · 웹훅", r"\bxox[abprs]-[0-9A-Za-z\-]{10,}|hooks\.slack\.com/services/[0-9A-Za-z/]+"),
    ("AWS 키", r"\bAKIA[0-9A-Z]{16}\b"),
    ("개인 키", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("Bearer 토큰 값", r"Bearer\s+[0-9A-Za-z._\-]{30,}"),
    ("비밀 이름에 값", r"(?i)\b[\w]*(?:SECRET|PASSWORD|API_KEY|_TOKEN)\b\s*[:=]\s*[\"'][^\"'\s$]{12,}[\"']"),
]
# ② 개인 정보 — 이메일 · 공인 IP
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
EMAIL_OK = re.compile(r"noreply|no-reply|@users\.noreply\.github\.com|@example\.(?:com|org)|@anthropic\.com$|@[\w.-]*\.iam\.gserviceaccount\.com$", re.I)
IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
# ③ 커밋 메시지 · 더한 줄 — 사용자 말 인용 · 결정 경위 (까닭 · 경위는 비공개 문서에)
QUOTE = [
    ("사용자 말 인용", r"사용자\s*[\"“'‘「]"),
    ("날짜 + 사용자 경위", r"20\d\d-\d\d-\d\d\s*사용자"),
]
MSG_ONLY = [
    ("계정 이름", r"\bred\d+keep\b"),
]
SKIP_PATH = re.compile(r"^\.githooks/|\.(?:png|jpe?g|webp|gif|ico|woff2?|ttf|otf|pdf|gz|zip)$", re.I)


def ip_ok(m):
    a, b, c, d = (int(x) for x in m.groups())
    if max(a, b, c, d) > 255:
        return True   # 버전 번호 등
    return (a in (0, 10, 127) or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31) or (a == 169 and b == 254)
            or (a, b, c, d) in ((8, 8, 8, 8), (1, 1, 1, 1), (255, 255, 255, 255))
            or (a < 10 and b < 50 and c < 50))   # 1.2.3.4 같은 버전 번호 · 예시


def scan_line(text, rules):
    hits = []
    for name, pat in rules:
        if re.search(pat, text):
            hits.append(name)
    for m in EMAIL.finditer(text):
        if not EMAIL_OK.search(m.group(0)):
            hits.append("이메일 주소")
            break
    for m in IPV4.finditer(text):
        if not ip_ok(m):
            hits.append("공인 IP 주소")
            break
    return hits


def added_lines(args):
    """git diff 의 더한 줄 → [(파일, 줄 번호, 글)]."""
    out = subprocess.run(["git", "diff", "--no-color", "-U0", *args], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    path, n, rows = None, 0, []
    for line in out.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            n = int(re.search(r"\+(\d+)", line).group(1))
        elif line.startswith("+") and path:
            rows.append((path, n, line[1:]))
            n += 1
    return rows


def check_diff(args):
    bad = []
    for path, n, text in added_lines(args):
        if SKIP_PATH.search(path):
            continue
        for h in scan_line(text, SECRET + QUOTE):
            bad.append(f"  {path}:{n}  {h}")
    return bad


def check_msg(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    body = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    bad = []
    for i, line in enumerate(body.splitlines(), 1):
        if line.startswith("Co-Authored-By:"):
            continue
        for h in scan_line(line, SECRET + QUOTE + MSG_ONLY):
            bad.append(f"  커밋 메시지 {i}째 줄  {h}")
    return bad


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mode = sys.argv[1] if len(sys.argv) > 1 else "diff"
    if mode == "pre-commit":
        bad = check_diff(["--cached"])
    elif mode == "commit-msg":
        bad = check_msg(sys.argv[2])
    else:
        bad = check_diff(["HEAD"])
    if bad:
        print("헌법 제11조 검사에 걸렸습니다 (값은 찍지 않음):")
        print("\n".join(bad))
        print("고친 뒤 다시 커밋하세요. 비밀값은 .env · GitHub 시크릿에, 경위 · 인용은 비공개 문서 저장소에.")
        sys.exit(1)
    if mode == "diff":
        print("걸린 것 없음")


if __name__ == "__main__":
    main()
