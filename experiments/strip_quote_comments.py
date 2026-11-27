"""주석 속 결정 경위(날짜 + 사용자 + 인용)를 지운다. 주석 밖 코드는 건드리지 않는다.

    python experiments/strip_quote_comments.py index.html            # 바꿀 줄 수만 보기
    python experiments/strip_quote_comments.py index.html --write    # 고쳐 쓰기

HTML · CSS · JS 가 섞인 파일(테마 · 목업)용. 주석 = <!-- --> · <b:comment> · /* */ · 줄 끝 // .
확인: 고치기 전 · 뒤에서 주석을 모두 걷어 낸 나머지가 같아야 쓴다(다르면 멈춤).
"""
import re
import sys

DATE = r"(?:(?:20\d\d-)?\d\d-\d\d|같은 날)"
SP = r"[ \t]*"  # 같은 줄 안의 공백만 — 줄바꿈은 지우지 않는다
QUOTE = r'(?:[ \t]*[:：]?[ \t]*(?:"[^"\n]*"|“[^”\n]*”|「[^」\n]*」))*'
KIND = r"(?:[ \t]*(?:결정|지시|요청|지적|확정))?"
PATTERNS = [
    # (… 2026-10-15 사용자 …) 괄호째 — 괄호 안이 경위뿐이므로 통째로
    re.compile(SP + r"\((?:[^()\n]*?)" + DATE + r"[^()\n]*?사용자[^()\n]*\)"),
    re.compile(SP + r"\((?:[^()\n]*?)사용자[^()\n]*?" + DATE + r"[^()\n]*\)"),
    # — 2026-11-10 사용자: "…"  (괄호 없이)
    re.compile(r"(?:[ \t]+[—–-](?=[ \t]))?" + SP + DATE + SP + "사용자" + KIND + QUOTE),
    # (사용자) · 날짜 없는 사용자: "…"
    re.compile(SP + r"\(사용자\)"),
    re.compile(SP + r"\(?사용자" + KIND + SP + r"[:：]" + SP + r'(?:"[^"\n]*"|“[^”\n]*”)\)?'),
]

COMMENT = re.compile(
    r"<!--.*?-->"            # HTML
    r"|<b:comment>.*?</b:comment>"  # Blogger 테마 주석
    r"|/\*.*?\*/"            # CSS · JS 블록
    r"|(?<![:\\'\"\w/])//[^\n]*",  # JS 줄 끝 (https:// · 문자열 속 // 제외)
    re.S,
)


def clean_comment(c: str) -> str:
    for p in PATTERNS:
        c = p.sub("", c)
    return c


def strip_all(s: str) -> str:
    return COMMENT.sub("", s)


def main():
    path = sys.argv[1]
    write = "--write" in sys.argv
    src = open(path, encoding="utf-8", newline="").read()
    out = COMMENT.sub(lambda m: clean_comment(m.group(0)), src)
    if strip_all(src) != strip_all(out):
        sys.exit("멈춤: 주석 밖 내용이 달라짐")
    before = sum("사용자" in m.group(0) for m in COMMENT.finditer(src))
    after = [m.group(0) for m in COMMENT.finditer(out) if "사용자" in m.group(0)]
    changed = sum(a != b for a, b in zip(src.splitlines(), out.splitlines()))
    print(f"{path}: 바뀐 줄 {changed} · '사용자' 든 주석 {before} → {len(after)}")
    for c in after:
        for line in c.splitlines():
            if "사용자" in line:
                print("  남음:", line.strip()[:140])
    if write:
        open(path, "w", encoding="utf-8", newline="").write(out)


if __name__ == "__main__":
    main()
