"""주석 속 결정 경위(날짜 + 사용자 + 인용)를 지운다. 주석 밖 코드는 건드리지 않는다.

    python experiments/strip_quote_comments.py index.html            # 바꿀 줄 수만 보기
    python experiments/strip_quote_comments.py index.html --write    # 고쳐 쓰기
    python experiments/strip_quote_comments.py a.py b.yml c.js         # 여러 파일 · .py 는 # 주석과 docstring, .yml 은 # 주석

HTML · CSS · JS 가 섞인 파일(테마 · 목업)용. 주석 = <!-- --> · <b:comment> · /* */ · 줄 끝 // .
확인: 고치기 전 · 뒤에서 주석을 모두 걷어 낸 나머지가 같아야 쓴다(다르면 멈춤).
"""
import ast
import io
import os
import re
import tokenize
import sys

DATE = r"(?:(?:20\d\d-)?\d\d-\d\d|같은 날)"
SP = r"[ \t]*"  # 같은 줄 안의 공백만 — 줄바꿈은 지우지 않는다
QUOTE = r'(?:[ \t]*[:：]?[ \t]*(?:"[^"\n]*"|“[^”\n]*”|「[^」\n]*」))*'
KIND = r"(?:[ \t]*(?:결정|지시|요청|지적|확정))?"
PATTERNS = [
    # 괄호 안에 날짜와 '사용자'가 같이 있으면 괄호째 — 괄호 안이 경위뿐이므로
    re.compile(SP + r"\((?:[^()\n]*?)" + DATE + r"[^()\n]*?사용자[^()\n]*\)"),
    re.compile(SP + r"\((?:[^()\n]*?)사용자[^()\n]*?" + DATE + r"[^()\n]*\)"),
    # 괄호 없이 줄표 + 날짜 + '사용자' + 따옴표 인용
    re.compile(r"(?:[ \t]+[—–-](?=[ \t]))?" + SP + DATE + SP + "사용자" + KIND + QUOTE),
    # 괄호 안이 '사용자' 한 낱말뿐
    re.compile(SP + r"\(사용자\)"),
    # 괄호가 '사용자' + 따옴표 · 쌍점 · 결정 으로 시작하는 경위. 사용자별 · 사용자 로그인 같은 기능 설명은 안 걸림
    re.compile(SP + r'\(사용자(?=[ \t]*(?:[:："“]|결정|지시|요청|지적|확정))[^()\n]*\)'),
    re.compile(SP + r"\(?사용자" + KIND + SP + r"[:：]" + SP + r'(?:"[^"\n]*"|“[^”\n]*”)\)?'),
]

COMMENT = re.compile(
    r"<!--.*?-->"            # HTML
    r"|<b:comment>.*?</b:comment>"  # Blogger 테마 주석
    r"|/\*.*?\*/"            # CSS · JS 블록
    r"|(?<![:\\'\"\w/])//[^\n]*",  # JS 줄 끝 (https:// · 문자열 속 // 제외)
    re.S,
)


WEB_ONLY = re.compile(r"<!--.*?-->|<b:comment>.*?</b:comment>|/\*.*?\*/", re.S)  # 파이썬 문자열 속 (페이지로 나가는) 주석


def clean_comment(c: str) -> str:
    for p in PATTERNS:
        c = p.sub("", c)
    return c


def strip_all(s: str) -> str:
    return COMMENT.sub("", s)


def clean_web(src: str) -> str:
    out = COMMENT.sub(lambda m: clean_comment(m.group(0)), src)
    if strip_all(src) != strip_all(out):
        raise ValueError("주석 밖 내용이 달라짐")
    return out


def _docstring_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                yield body[0].value


def _ast_without_docstrings(src: str) -> str:
    """docstring 은 비우고, 다른 문자열은 그 안의 웹 주석(<!-- --> · /* */)만 걷어 낸 문법 트리."""
    tree = ast.parse(src)
    docs = {id(c) for c in _docstring_nodes(tree)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = "" if id(node) in docs else WEB_ONLY.sub("", node.value)
    return ast.dump(tree)


def clean_py(src: str) -> str:
    """# 주석 · docstring · 문자열 속 웹 주석(<!-- --> · /* */, 페이지로 나감) 안만 고친다."""
    lines = src.splitlines(keepends=True)
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln))
    off = lambda row, col: starts[row - 1] + col  # noqa: E731
    doc_pos = {(c.lineno, c.col_offset) for c in _docstring_nodes(ast.parse(src))}
    edits = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        a, b = off(*tok.start), off(*tok.end)
        if tok.type == tokenize.COMMENT:
            new = clean_comment(tok.string)
        elif tok.type == tokenize.STRING and tok.start in doc_pos:
            m = re.match(r"(?is)^([rbu]*)(\"\"\"|'''|\"|')(.*)\2$", tok.string)
            if not m:
                continue
            new = m.group(1) + m.group(2) + clean_comment(m.group(3)) + m.group(2)
        elif tok.type == tokenize.STRING and ("/*" in tok.string or "<!--" in tok.string or "<b:comment>" in tok.string):
            new = WEB_ONLY.sub(lambda w: clean_comment(w.group(0)), tok.string)
        else:
            continue
        if new != tok.string:
            edits.append((a, b, new))
    out = src
    for a, b, new in reversed(edits):
        out = out[:a] + new + out[b:]
    if _ast_without_docstrings(src) != _ast_without_docstrings(out):
        raise ValueError("주석 · docstring 밖 내용이 달라짐")
    return out


def clean_yml(src: str) -> str:
    """줄 끝 # 주석만. # 앞이 공백이거나 줄 처음이고, 앞쪽 따옴표가 짝이 맞을 때만 주석으로 본다."""
    out = []
    for line in src.splitlines(keepends=True):
        m = re.search(r"(^|\s)#", line)
        while m and (line[:m.start()].count('"') % 2 or line[:m.start()].count("'") % 2):
            m = re.compile(r"\s#").search(line, m.end())
        if m:
            k = m.end() - 1
            body = line[k:].rstrip("\r\n")
            line = line[:k] + clean_comment(body) + line[k + len(body):]
        out.append(line)
    return "".join(out)


def clean_file(path: str):
    src = open(path, encoding="utf-8", newline="").read()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        out = clean_py(src)
    elif ext in (".yml", ".yaml"):
        out = clean_yml(src)
    else:
        out = clean_web(src)
    return src, out


def main():
    write = "--write" in sys.argv
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    total_lines = total_files = 0
    stopped, left = [], []
    for path in paths:
        try:
            src, out = clean_file(path)
        except (ValueError, SyntaxError, tokenize.TokenError) as e:
            stopped.append(f"{path}: {e}")
            continue
        if src == out:
            continue
        changed = sum(a != b for a, b in zip(src.splitlines(), out.splitlines()))
        total_lines += changed
        total_files += 1
        for ln in out.splitlines():
            if "사용자" in ln and re.search(DATE + r"|사용자\s*[:：)]", ln):
                left.append(f"{path}: {ln.strip()[:130]}")
        if write:
            open(path, "w", encoding="utf-8", newline="").write(out)
    print(f"바뀐 파일 {total_files} · 바뀐 줄 {total_lines} · 멈춘 파일 {len(stopped)} · 경위로 보이는 남은 줄 {len(left)}")
    for s in stopped:
        print("  멈춤:", s)
    for s in left[:40]:
        print("  남음:", s)


if __name__ == "__main__":
    main()
