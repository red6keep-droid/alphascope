"""같은 뉴스 묶기 (news_stories) — 방송 주제(media_feed.issues) 와 기사(news_store) 가운데 **같은 사건**을 다룬 것을 한 묶음으로 (2026-11-05 사용자 batch 8 ③ · ⑬).

왜 : 미국 데일리 뉴스 끝의 `방송 111건 더 보기` — 방송 13곳이 이틀 동안 다룬 주제가 전부 따로 줄이 되어 독자가 볼 수 없었다. 같은 사건은 한 줄로 합치고
     "몇 곳이 다뤘나"를 숫자로 붙인다 — 중복은 지울 대상이 아니라 정보다 (사용자: "어떤 기사가 중복되어 있는지는 아주 중요한 가치").
어떻게 : 낱말 겹침 규칙(media_feed._same)은 같은 선거 이야기를 세 줄로 쪼갰다(11-05 확인) → AI 가 묶는다. 한 번에 CHUNK 건씩 넘기며 "이미 있는 묶음에 넣거나 새 묶음" (점진 군집).
         사슬 = news-alt(Groq gpt-oss 먼저 — Gemini 는 아낀다). 실패하면 규칙 묶음(media_feed 묶음 + 낱말 겹침)으로 — 리포트는 나간다.
캐시 : cache_path(JSON) = {"assign": {항목 id: [묶음 번호, 이름, 짧은 이름, 시각]}} **항목별 누적** — 이미 묶인 항목은 그대로, 새 항목만 AI 에(기존 묶음 목록을 주고 점진 군집).
       아침 · 낮 실행이 재료를 대부분 공유하고 48시간 창이 흐르며 조금씩 바뀌므로 집합 해시로는 매번 빗나갔다(11-05). 7일 지난 항목은 지운다.
입력 항목 = {"id", "kind": "media" | "article", "text": 주제 또는 헤드라인(한국어), "theme", "published_at", "channels": [...](방송) , "n_videos"}.
출력 묶음 = {"id", "name"(사건 이름 명사형 ≤ 16자), "short"(카드 답용 ≤ 8자), "items": [id], "channels": [채널], "n_media", "n_articles", "themes": Counter, "latest"}.
"""

import datetime
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

CHUNK = 30          # 한 호출 항목 수 — 이름 40자 × 30 + 기존 묶음 이름 ≈ 3,000 토큰 (Groq 분당 8,000 안)
MAX_STORIES = 60    # 기존 묶음 목록이 너무 길어지면 프롬프트가 커진다 — 항목이 많은 순으로 이만큼만 보여 준다
KEEP_DAYS = 7
PROMPT = """You cluster Korean finance news items into STORIES (the same real-world event or development). Output JSON only.

Input: "stories" = clusters that already exist (id, name), "items" = new items (id, text, kind: media = a YouTube broadcast topic, article = a news article headline).
For each item decide: does it report the SAME EVENT as an existing story? Then give that story id. Otherwise create a new story.
Same event = same decision, same election result, same company announcement, same price move. Not just the same broad topic: "Fed rate cut in December" and "ECB holds rates" are different stories; "tech stocks fall on AI capex fears" items from different channels are one story.
Return: {"items": [{"id": "<item id>", "story": "<existing story id>" | null, "name": "<new story name, only when story is null>", "short": "<new story short label, only when story is null>"}]}
- name: Korean noun phrase, max 16 characters, the event itself (예: "중간선거 민주당 압승", "AI 데이터센터 규제 논란", "이란 긴장과 유가"). Never a verb ending (-다 · -요), no period, never "—".
- short: max 8 Korean characters, the shortest label of the same event (예: "중간선거", "AI 데이터센터", "이란 · 유가").
- Reuse a new story for later items in the same batch by repeating the exact same "name" (I merge identical names).
Every input item must appear exactly once.
"""


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


_WORD = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_STOP = {"기대", "전망", "우려", "논쟁", "강세", "약세", "상승", "하락", "증가", "감소", "영향", "관련", "지속", "확대", "축소", "가능성", "발표", "소식",
         "주가", "시장", "및", "AI", "ai", "성장", "투자", "급증", "미국", "트럼프"}


def _words(t):
    return {w.lower() for w in _WORD.findall(str(t or "")) if w not in _STOP}


def _clean(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).replace("—", " · ").strip().rstrip(".")
    s = re.sub(r"(다|요)$", "", s)
    return s[:n]


def _rule_group(items):
    """AI 없이 — 낱말 두 개 이상 겹치면 같은 묶음(같은 분야 안에서). media_feed._same 과 비슷하지만 기사 · 방송을 같이 본다."""
    groups = []
    for it in sorted(items, key=lambda x: str(x.get("published_at") or ""), reverse=True):
        w = _words(it["text"])
        g = next((g for g in groups if g["theme"] == it.get("theme") and len(w & g["words"]) >= max(1, min(2, min(len(w), len(g["words"])) // 2))), None)
        if g is None:
            groups.append({"theme": it.get("theme"), "words": set(w), "ids": [it["id"]], "name": _clean(it["text"], 16), "short": _clean(it["text"], 8)})
        else:
            g["ids"].append(it["id"])
            g["words"] |= w
    return {it_id: (i, g["name"], g["short"]) for i, g in enumerate(groups) for it_id in g["ids"]}


def _ai_group(items, label, known=None):
    """점진 군집 — {item id: (story 번호, name, short)}. known = 이미 묶인 {id: (번호, 이름, 짧은 이름)} — 그 묶음 목록을 주고 새 항목만 넣는다. 사슬이 전부 실패하면 None."""
    from llm_chain import LLMPool, usage_line
    try:
        pool = LLMPool("news-alt", label=label)
    except RuntimeError as e:
        print(f"[stories] {e}")
        return None
    stories = []   # [{"id": "s1", "name", "short", "n", "k"}]
    assign = {}
    by_k = {}
    for it_id, (k, name, short) in (known or {}).items():   # 기존 묶음 — 번호 k 그대로, 모델에는 s<k> 로
        st = by_k.get(k)
        if st is None:
            st = by_k[k] = {"id": f"s{k}", "name": name, "short": short, "n": 0, "k": k}
            stories.append(st)
        st["n"] += 1
    next_k = max([s["k"] for s in stories] + [-1]) + 1
    items = sorted(items, key=lambda x: str(x.get("published_at") or ""), reverse=True)   # 최근 것부터 — 큰 사건이 먼저 묶음이 된다
    for i in range(0, len(items), CHUNK):
        part = items[i:i + CHUNK]
        shown = sorted(stories, key=lambda s: -s["n"])[:MAX_STORIES]
        payload = {"stories": [{"id": s["id"], "name": s["name"]} for s in shown],
                   "items": [{"id": x["id"], "kind": x["kind"], "text": _clean(x["text"], 60)} for x in part]}
        want = {x["id"] for x in part}

        def valid(r):
            rows = (r or {}).get("items") if isinstance(r, dict) else None
            if not isinstance(rows, list):   # 탈락은 예외로 — 돌려준 값은 llm_chain 이 답으로 쓴다 (news_summary 와 같은 결함, 2026-11-12)
                raise ValueError("items 아님")
            got = {str(x.get("id")) for x in rows if isinstance(x, dict)}
            if got != want:
                raise ValueError(f"항목 불일치 {len(got & want)}/{len(want)}")
            return None

        try:
            res = pool.generate_json(PROMPT + json.dumps(payload, ensure_ascii=False), temperature=0.0, validate=valid)
        except RuntimeError as e:
            print(f"[stories] 묶기 실패 — 남은 {len(items) - i}건은 규칙으로 : {str(e)[:120]}")
            return None if not assign else _finish(assign, stories, items, i)
        by_id = {s["id"]: s for s in stories}
        new_by_name = {}
        for row in res["items"]:
            sid = row.get("story")
            if sid in by_id:
                s = by_id[sid]
            else:
                name = _clean(row.get("name") or "", 16) or _clean(next(x["text"] for x in part if x["id"] == row["id"]), 16)
                s = new_by_name.get(name)
                if s is None:
                    s = {"id": f"s{next_k}", "name": name, "short": _clean(row.get("short") or name, 8), "n": 0, "k": next_k}
                    next_k += 1
                    stories.append(s)
                    by_id[s["id"]] = s
                    new_by_name[name] = s
            s["n"] += 1
            assign[row["id"]] = s["id"]
        print(f"[stories] {min(i + CHUNK, len(items))}/{len(items)} → 묶음 {len(stories)} ({pool.last_model})", flush=True)
    print(f"[stories] {usage_line()}")
    idx = {s["id"]: (s["k"], s["name"], s["short"]) for s in stories}
    return {it_id: idx[sid] for it_id, sid in assign.items()}


def _finish(assign, stories, items, done):
    """중간에 사슬이 끊기면 — 묶인 것은 살리고 나머지는 규칙으로 붙인다."""
    idx = {s["id"]: (s["k"], s["name"], s["short"]) for s in stories}
    out = {it_id: idx[sid] for it_id, sid in assign.items()}
    base = max([s["k"] for s in stories] + [-1]) + 1
    for it_id, (k, name, short) in _rule_group(items[done:]).items():
        out[it_id] = (base + k, name, short)
    return out


def group(items, cache_path=None, label="stories"):
    """항목 → 묶음 목록 (방송 수 순 · 항목 수 순). 캐시에 있는 항목은 그대로, 새 항목만 AI(기존 묶음 이어서) — NEWS_NO_AI=1 이면 새 항목은 규칙으로(저장 안 함)."""
    items = [x for x in items if x.get("id") and x.get("text")]
    if not items:
        return []
    cache = _load(cache_path) if cache_path else {}
    saved = cache.get("assign") or {}
    known = {x["id"]: tuple(saved[x["id"]][:3]) for x in items if x["id"] in saved}
    new = [x for x in items if x["id"] not in known]
    assign = dict(known)
    if new:
        got = None if os.environ.get("NEWS_NO_AI") else _ai_group(new, label, known)
        if got is None:
            base = max([v[0] for v in known.values()] + [-1]) + 1
            got = {it_id: (base + k, name, short) for it_id, (k, name, short) in _rule_group(new).items()}
            how = "rule"
        else:
            how = "ai"
        assign.update(got)
        print(f"[stories] 이미 묶인 {len(known)} · 새로 {len(new)} ({how}) → 묶음 {len({v[0] for v in assign.values()})}")
        if cache_path and how == "ai":
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            saved = {k: v for k, v in saved.items() if len(v) > 3 and v[3] >= (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=KEEP_DAYS)).isoformat()}
            saved.update({it_id: [k, name, short, now] for it_id, (k, name, short) in got.items()})
            cache = {"assign": saved, "at": now}
            os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)
    else:
        print(f"[stories] 캐시 사용 — 전부 묶여 있음 ({len(known)})")
    by = {}
    for it in items:
        k, name, short = assign.get(it["id"]) or (f"x{it['id']}", _clean(it["text"], 16), _clean(it["text"], 8))
        g = by.setdefault(k, {"id": str(k), "name": name, "short": short, "items": [], "channels": [], "n_media": 0, "n_articles": 0, "themes": Counter(), "latest": ""})
        g["items"].append(it)
        if it["kind"] == "media":
            g["n_media"] += 1
            g["channels"] = sorted(set(g["channels"]) | set(it.get("channels") or []))
        else:
            g["n_articles"] += 1
        if it.get("theme"):
            g["themes"][it["theme"]] += 1
        g["latest"] = max(g["latest"], str(it.get("published_at") or ""))
    out = list(by.values())
    for g in out:
        g["n_channels"] = len(g["channels"])
        g["theme"] = g["themes"].most_common(1)[0][0] if g["themes"] else "기타"
        g["items"].sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
    out.sort(key=lambda g: g["latest"], reverse=True)   # 같은 수면 최근 사건이 위
    out.sort(key=lambda g: (-g["n_channels"], -(g["n_media"] + g["n_articles"])))   # 방송 수 → 항목 수
    return out
