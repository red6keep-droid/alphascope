// 관리자 전용 운영 페이지 (Cloudflare Worker + GitHub 로그인, 2026-10-23 사용자).
//
// 보여 주는 것 — 날짜(KST) 하나에 대해:
//   1) 리포트별 발행 현황: 발행 · 갱신 · 이미 있음 · 미발행(이유) · 에러 중단 · 실행 없음(예약 누락)
//   2) AI 모델 사슬: 단계별 성공/시도, 예비 · 대체 전환, 한도, 검사 탈락, 전부 실패
//   3) 정보 수집 오류: 소스별 실패 줄 · 운영 알림(notify)
//   4) 그 밖의 워크플로 실패 (뉴스 · 시세 · 댓글)
// 자료: Cloudflare KV(OPS_KV) 의 운영 기록(experiments/ops_log.py 가 실행마다 씀) + GitHub Actions 실행 목록(API).
//
// 접근: GitHub OAuth 로그인 → ADMIN_GITHUB_LOGINS 의 계정만 통과 (Cloudflare Access 는 카드 등록이 필요해 쓰지 않는다, 2026-10-23 사용자).
// GITHUB_CLIENT_ID · GITHUB_CLIENT_SECRET · SESSION_SECRET · ADMIN_GITHUB_LOGINS 중 하나라도 없으면 아무것도 보여 주지 않는다.

const REPO = "red6keep-droid/alphascope";

// days: KST 요일(0=일) 가운데 실행이 예정된 날. 데일리는 뉴욕 월~금 장 마감 뒤 → KST 화~토 아침.
const REPORTS = [
  { key: "daily", name: "미국 증시 데일리", file: "test-daily-report.yml", wf: "Test Daily Report", at: "06:00", days: [2, 3, 4, 5, 6] },
  { key: "trump", name: "트럼프 트렌드", file: "trump-trend.yml", wf: "Trump Trend", at: "06:15", days: [0, 1, 2, 3, 4, 5, 6] },
  { key: "nvda", name: "NVDA 리포트", file: "nvda-report.yml", wf: "NVDA Report", at: "06:30", days: [0, 1, 2, 3, 4, 5, 6] },
  { key: "radar", name: "인물 발언 레이더", file: "people-radar.yml", wf: "People Radar", at: "07:00", days: [0, 1, 2, 3, 4, 5, 6] },
  { key: "media", name: "미디어 데일리", file: "media-daily.yml", wf: "Media Daily", at: "08:00 · 10:15", days: [1, 2, 3, 4, 5] },
];

// ---------------------------------------------------------------- 접근 (GitHub 로그인)
// /login → GitHub 인증 → /callback 에서 계정 이름을 ADMIN_GITHUB_LOGINS 와 대조 → HMAC 서명 세션 쿠키(12시간).
// GitHub 액세스 토큰은 계정 이름 확인에만 쓰고 저장하지 않는다. 범위(scope) 없이 요청 — 공개 프로필만 읽힌다.
const SESSION_COOKIE = "__Host-ops_s";
const STATE_COOKIE = "__Host-ops_state";
const SESSION_SECONDS = 12 * 3600;
const enc = new TextEncoder();
const b64url = (bytes) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const b64urlDecode = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0)));

function config(env) {
  const c = {
    clientId: (env.GITHUB_CLIENT_ID || "").trim(),
    clientSecret: (env.GITHUB_CLIENT_SECRET || "").trim(),
    sessionSecret: (env.SESSION_SECRET || "").trim(),
    admins: (env.ADMIN_GITHUB_LOGINS || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean),
  };
  const missing = [!c.clientId && "GITHUB_CLIENT_ID", !c.clientSecret && "GITHUB_CLIENT_SECRET", !c.sessionSecret && "SESSION_SECRET", !c.admins.length && "ADMIN_GITHUB_LOGINS"].filter(Boolean);
  return { c, missing };
}

async function hmac(secret, data) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64url(new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(data))));
}

function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

function cookie(req, name) {
  const m = (req.headers.get("Cookie") || "").match(new RegExp(`(?:^|;\\s*)${name.replace(/[-$]/g, "\\$&")}=([^;]+)`));
  return m ? m[1] : "";
}

const setCookie = (name, value, maxAge) => `${name}=${value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`;

async function makeSession(c, login) {
  const payload = b64url(enc.encode(JSON.stringify({ login, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS })));
  return `${payload}.${await hmac(c.sessionSecret, payload)}`;
}

async function readSession(req, c) {
  const raw = cookie(req, SESSION_COOKIE);
  const [payload, sig] = raw.split(".");
  if (!payload || !sig || !safeEqual(sig, await hmac(c.sessionSecret, payload))) return null;
  try {
    const s = JSON.parse(b64urlDecode(payload));
    if (!(s.exp > Date.now() / 1000) || !c.admins.includes(String(s.login).toLowerCase())) return null;
    return s;
  } catch {
    return null;
  }
}

const redirect = (to, cookies = []) => {
  const h = new Headers({ Location: to, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" });
  for (const x of cookies) h.append("Set-Cookie", x);
  return new Response(null, { status: 302, headers: h });
};

function startLogin(url, c) {
  const state = b64url(crypto.getRandomValues(new Uint8Array(24)));
  const q = new URLSearchParams({ client_id: c.clientId, redirect_uri: `${url.origin}/callback`, state, scope: "", allow_signup: "false" });
  return redirect(`https://github.com/login/oauth/authorize?${q}`, [setCookie(STATE_COOKIE, state, 600)]);
}

async function finishLogin(req, url, c) {
  const state = url.searchParams.get("state") || "";
  const code = url.searchParams.get("code") || "";
  if (!code || !safeEqual(state, cookie(req, STATE_COOKIE))) return deny("로그인 요청이 맞지 않습니다. 다시 시도하세요.", 400);
  const tok = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json", "User-Agent": "alphascope-ops-console" },
    body: JSON.stringify({ client_id: c.clientId, client_secret: c.clientSecret, code, redirect_uri: `${url.origin}/callback` }),
  }).then((r) => r.json()).catch(() => ({}));
  if (!tok.access_token) return deny("GitHub 인증에 실패했습니다.", 403);
  const user = await fetch("https://api.github.com/user", {
    headers: { Authorization: `Bearer ${tok.access_token}`, Accept: "application/vnd.github+json", "User-Agent": "alphascope-ops-console" },
  }).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  const login = String(user.login || "");
  if (!login || !c.admins.includes(login.toLowerCase())) return deny("관리자 계정이 아닙니다.", 403);
  return redirect("/", [setCookie(SESSION_COOKIE, await makeSession(c, login), SESSION_SECONDS), setCookie(STATE_COOKIE, "", 0)]);
}

function deny(why, status = 403) {
  return new Response(simplePage("접근 거부", why, status === 400 || /관리자|인증/.test(why)), { status, headers: HEADERS });
}

// ---------------------------------------------------------------- 자료
const kstToday = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const shiftDay = (d, n) => new Date(Date.parse(`${d}T00:00:00Z`) + n * 86400e3).toISOString().slice(0, 10);
const kstWeekday = (d) => new Date(`${d}T00:00:00Z`).getUTCDay();
const toKst = (iso) => (iso ? new Date(Date.parse(iso) + 9 * 3600e3).toISOString().slice(11, 16) : "");

async function gh(env, path) {
  const headers = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "alphascope-ops-console" };
  if (env.GITHUB_TOKEN) headers.Authorization = `Bearer ${env.GITHUB_TOKEN}`;
  const r = await fetch(`https://api.github.com/repos/${REPO}${path}`, { headers });
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  return r.json();
}

async function loadRuns(env, day) {
  // KST 하루 = UTC 전날 15:00 ~ 당일 14:59
  const range = `${shiftDay(day, -1)}T15:00:00Z..${day}T14:59:59Z`;
  const q = `created=${encodeURIComponent(range)}&per_page=50`;
  const per = await Promise.all(
    REPORTS.map((r) => gh(env, `/actions/workflows/${r.file}/runs?${q}`).then((j) => j.workflow_runs || []).catch((e) => ({ error: String(e.message || e) }))),
  );
  const failed = await gh(env, `/actions/runs?status=failure&${q}`).then((j) => j.workflow_runs || []).catch(() => []);
  return { per, failed };
}

async function loadParts(env, day) {
  if (!env.OPS_KV) return [];
  const out = [];
  let cursor;
  do {
    const page = await env.OPS_KV.list({ prefix: `ops:${day}:`, cursor });
    out.push(...page.keys.map((k) => k.name));
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor && out.length < 500);
  const vals = await Promise.all(out.map((k) => env.OPS_KV.get(k, "json").catch(() => null)));
  return vals.filter(Boolean);
}

// ---------------------------------------------------------------- 판정
function verdict(rep, runs, parts, day, isToday) {
  const pubs = parts.flatMap((p) => p.publish || []);
  const done = pubs.find((x) => x.status === "published" || x.status === "updated") || pubs.find((x) => x.status === "already");
  const running = runs.find((r) => r.status !== "completed");
  const exc = parts.map((p) => p.exit && p.exit.exception).find(Boolean);
  const skip = pubs.find((x) => x.status === "skipped");
  const dry = pubs.find((x) => x.status === "dry-run");
  const failedRun = runs.find((r) => r.conclusion === "failure");
  const expected = rep.days.includes(kstWeekday(day));

  if (done) {
    const label = { published: "발행", updated: "발행 · 갱신", already: "이미 발행" }[done.status];
    return { tone: "ok", label, url: done.url, why: exc ? `발행 뒤 에러 : ${exc}` : "" };
  }
  if (running) return { tone: "info", label: "진행 중", why: `${toKst(running.created_at)} 시작` };
  if (exc) return { tone: "bad", label: "에러로 중단", why: exc };
  if (skip) return { tone: "warn", label: "미발행", why: skip.reason };
  if (failedRun) return { tone: "bad", label: "워크플로 실패", why: parts.length ? "파이썬 밖 단계에서 실패했습니다. 실행 기록을 확인하세요." : "운영 기록 없이 실패했습니다. 설치 · 체크아웃 단계일 수 있으니 실행 기록을 확인하세요." };
  if (dry) return { tone: "warn", label: "미발행", why: "게시 모드가 꺼진 실행(dry-run)입니다. 저장소 변수 *_PUBLISH 또는 수동 실행의 publish 입력을 확인하세요." };
  if (runs.length) return { tone: "warn", label: "미발행", why: parts.length ? "게시 단계 기록이 없습니다. 실행 기록을 확인하세요." : "운영 기록이 없습니다 (기록 기능 전 실행이거나 전송 실패)." };
  if (!expected) return { tone: "muted", label: "예정 없음", why: "" };
  if (isToday) return { tone: "muted", label: "실행 전", why: `예정 KST ${rep.at}경입니다. 시각이 지났다면 예약 실행이 누락된 것입니다.` };
  return { tone: "bad", label: "실행 없음", why: "예약 실행이 오지 않았습니다 (Cloudflare 트리거 · GitHub 예약 모두 누락)." };
}

function llmSummary(parts) {
  const usage = {};
  const events = {};
  for (const p of parts) {
    for (const [k, v] of Object.entries((p.llm && p.llm.usage) || {})) {
      usage[k] = usage[k] || { ok: 0, fail: 0 };
      usage[k].ok += v.ok || 0;
      usage[k].fail += v.fail || 0;
    }
    for (const [k, n] of Object.entries((p.llm && p.llm.events) || {})) events[k] = (events[k] || 0) + n;
  }
  return { usage, events };
}

// ---------------------------------------------------------------- 화면 — 블로그 디자인 가이드라인(디자인-가이드라인.md) 적용, 10-10절
// 본문 19px · 행간 34, 구획 제목 22px(폰 20), 카드 안 행간 24, 안내 ⓘ 14px #6B7280, 라벨 외곽선 알약 14px,
// 가로 구분선 카드 보이는 위아래 22px · 65/35, 흰 버튼, ":" · "·" 앞뒤 띄움, 줄표 금지, 날짜 점 표기, 여백 정수 px.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (u) => (/^https:\/\/[\w.-]+\//.test(String(u || "")) ? String(u) : "");
const runLink = (id) => `https://github.com/${REPO}/actions/runs/${encodeURIComponent(id)}`;

// 보이는 글 다듬기 (가이드라인 1절 5 · 9, 2-6): 줄표 → 쉼표, ":" · "·" 앞뒤 한 칸. 시각 09:30 · 비율 35:2 · 주소 :// 는 그대로
function fixText(s) {
  return String(s ?? "")
    .replace(/[ \t]+—[ \t]+/g, ", ")
    // 붙어 있는 콜론 뒤가 숫자면(시각 · 비율 · 코드 위치 narrate.py:124) 그대로
    .replace(/[ \t]*:[ \t]*/g, (m, i, t) => ((m === ":" && /\d/.test(t[i + 1] || "")) || t.slice(i + m.length, i + m.length + 2) === "//" ? m : " : "))
    .replace(/[ \t]*·[ \t]*/g, " · ");
}
const T = (s) => esc(fixText(s));
const dotDate = (d) => String(d).replace(/^(\d{4})-(\d{2})-(\d{2})$/, (_, y, m, dd) => `${+y}.${+m}.${+dd}`);

const INFO_ICON = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" class="ic" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4" stroke-linecap="round"/><circle cx="8" cy="5" r=".9" fill="currentColor" stroke="none"/></svg>';
const LINK_ICON = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h4v4"/><path d="M13 3 7 9"/><path d="M11 9v4H3V5h4"/></svg>';
const CHEV = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6l4 4 4-4"/></svg>';

// 상태 → 라벨 종류 (가이드라인 5절 색): 정상 녹색 · 미발행 주황(불확실) · 문제 빨강 · 진행 중 파랑 · 그 밖 회색
const PILL_KIND = { ok: "good", warn: "uncertain", bad: "positive", info: "negative", muted: "neutral" };
const pill = (text, tone) => `<span class="pill ${PILL_KIND[tone] || "neutral"}">${T(text)}</span>`;
const link = (href, label) => `<a class="lnk" href="${esc(href)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(label)}" title="${esc(label)}">${LINK_ICON}</a>`;
const EVENT_TONE = { "전부 실패": "bad", "예비": "warn", "한도": "warn", "검사 탈락": "warn", "대체": "muted" };
const RUN_EVENT = { schedule: "GitHub 예약", workflow_dispatch: "트리거 · 수동" };
const RUN_STATE = { success: ["성공", "ok"], failure: ["실패", "bad"], cancelled: ["취소", "muted"], skipped: ["건너뜀", "muted"] };

const dotList = (items) => (items.length ? `<ul class="dots">${items.map((x) => `<li><span class="dot"></span><span>${x}</span></li>`).join("")}</ul>` : "");
const muted = (t) => `<p class="muted-line">${INFO_ICON}${T(t)}</p>`;

// H 아코디언 줄 (가이드라인 2-1 H): 접힌 줄 = 구분명 16px 굵게 왼쪽 · 값 오른쪽 굵게 · 28px 화살표 버튼
function accRow(name, valueHtml, inner, open) {
  return `<details class="acc"${open ? " open" : ""}><summary class="row"><span class="row-l name">${T(name)}</span><span class="row-r val">${valueHtml}</span><span class="chev">${CHEV}</span></summary><div class="acc-body">${inner}</div></details>`;
}

function renderReport(rep, runs, parts, day, isToday, runsError) {
  const v = verdict(rep, runs, parts, day, isToday);
  const { usage, events } = llmSummary(parts);
  const collect = parts.flatMap((p) => (p.warnings || []).filter((w) => w.cat === "collect").map((w) => w.text));
  const notes = parts.flatMap((p) => Object.entries(p.notify || {}).map(([k, n]) => (n > 1 ? `${k} ×${n}` : k)));
  const other = parts.flatMap((p) => (p.warnings || []).filter((w) => w.cat !== "collect").map((w) => w.text));
  const url = safeUrl(v.url);

  // 결과 카드 — 발행이면 글 링크, 아니면 이유. 색 배경은 상태(가이드라인 2절 강조 카드 방향 색)
  const head = url || v.why
    ? `<div class="card state-${v.tone}">${url ? `<p class="lead">${T(v.label === "이미 발행" ? "오늘 글이 이미 있습니다" : "오늘 글을 발행했습니다")} ${link(url, "발행된 글 열기")}</p>` : ""}${v.why ? `<p class="lead${url ? " sub" : ""}">${T(v.why)}</p>` : ""}${runsError ? `<p class="lead sub">${T(`GitHub 실행 목록을 읽지 못했습니다 : ${runsError}`)}</p>` : ""}</div>`
    : "";

  // AI 모델 — 단계별 성공/시도 줄 + 예비 · 대체 · 한도 · 검사 탈락 · 전부 실패
  const steps = Object.entries(usage);
  const evs = Object.entries(events).sort((a, b) => b[1] - a[1]);
  const fails = steps.reduce((n, [, u]) => n + u.fail, 0);
  const aiValue = !steps.length ? `<span class="none">없음</span>` : evs.length ? `전환 ${evs.length}` : "정상";
  const aiInner = steps.length
    ? steps.map(([k, u]) => `<div class="sub-row"><span class="row-l">${esc(k)}${u.fail ? `<span class="subline warn-t">실패 ${u.fail}</span>` : ""}</span><span class="row-r val">${u.ok} / ${u.ok + u.fail}</span></div>`).join("") +
      dotList(evs.map(([k, n]) => {
        const kind = (k.match(/^(검사 탈락|전부 실패|예비|대체|한도)/) || [k.split(" ")[0]])[0];
        return `${T(k.slice(kind.length).trim())}${n > 1 ? ` <span class="sub-t">×${n}</span>` : ""}${pill(kind, EVENT_TONE[kind] || "muted")}`;
      }))
    : muted("이 날 AI 호출 기록이 없습니다.");

  // 정보 수집 — 운영 알림(notify) + 수집 실패 줄
  const nCollect = new Set([...notes, ...collect]).size;
  const collectInner = nCollect ? dotList([...new Set([...notes, ...collect])].map(T)) : muted("수집 오류가 없습니다.");
  const otherInner = dotList([...new Set(other)].map(T));

  // 실행 기록 — 시각 · 계기 · 결과 · GitHub 링크
  const runInner = runs.length
    ? runs.map((r) => {
        const [lab, tone] = RUN_STATE[r.conclusion] || ["진행 중", "info"];
        return `<div class="sub-row"><span class="row-l">${toKst(r.created_at)} · ${T(RUN_EVENT[r.event] || r.event)}</span><span class="row-r">${pill(lab, tone)}${link(runLink(r.id), "GitHub 실행 기록 열기")}</span></div>`;
      }).join("")
    : muted("이 날 실행이 없습니다.");

  const rows = [
    accRow("AI 모델", aiValue === "정상" ? "정상" : steps.length ? `<span class="warn-t">${T(aiValue)}</span>` : aiValue, aiInner, fails > 0 && v.tone !== "ok"),
    accRow("정보 수집", nCollect ? `<span class="warn-t">오류 ${nCollect}</span>` : "정상", collectInner, nCollect > 0),
    other.length ? accRow("그 밖의 경고", `${new Set(other).size}`, otherInner, false) : "",
    accRow("실행 기록", `${runs.length}회`, runInner, false),
  ].join("");

  return `<section class="rep">
<h2>${T(rep.name)}<span class="h2-sum">${INFO_ICON}${T(`예정 KST ${rep.at}경`)}</span>${pill(v.label, v.tone)}</h2>
${head}<div class="card multi">${rows}</div></section>`;
}

const CSS = `
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:#fff;color:#333;font-family:'Noto Sans KR',-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;font-size:19px;line-height:34px;word-break:keep-all;-webkit-tap-highlight-color:transparent}
main{max-width:860px;margin:0 auto;padding:12px 20px 48px}
a{color:#1a73e8}
.top{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 12px;margin:0 0 14px}
h1{margin:0;color:#111;font-size:35px;line-height:44px;font-weight:700}
.h1-date{font-size:14px;line-height:20px;color:#7A7A7A;font-weight:400;white-space:nowrap}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.btn{display:inline-flex;align-items:center;justify-content:center;background:#fff;border:1px solid #B5BAC0;border-radius:8px;color:#111;font:inherit;font-size:16px;font-weight:700;line-height:24px;padding:11px 12px;text-decoration:none;cursor:pointer}
.btn:hover{border-color:#111}.btn:active{opacity:.55}
input.btn{font-weight:400;min-width:0}
.caps{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px}
.cap{display:inline-flex;align-items:center;gap:4px;padding:4px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:999px;font-size:14px;line-height:20px;white-space:nowrap}
.cap .k{color:#6B7280}.cap b{color:#111}
h2{position:relative;display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;margin:28px 0 11px;padding:0;color:#111;font-size:22px;line-height:28px;font-weight:700}
.h2-sum{flex:1 1 160px;font-size:14px;line-height:20px;font-weight:400;color:#6B7280}
.ic{vertical-align:-2px;margin-right:4px}
.pill{display:inline-block;border:1px solid;border-radius:4px;padding:3px 5px 2px;margin:0 5px;font-size:14px;font-weight:400;line-height:1;white-space:nowrap;vertical-align:middle;position:relative;top:-1px}
h2 .pill{order:3;margin:0 0 0 auto;top:0}
.pill.good{border-color:#86EFAC;color:#15803D;background:#F0FDF4}
.pill.positive{border-color:#FCA5A5;color:#B91C1C;background:#FEF2F2}
.pill.negative{border-color:#93C5FD;color:#1D4ED8;background:#EFF6FF}
.pill.uncertain{border-color:#FDBA74;color:#C2410C;background:#fff}
.pill.neutral{border-color:#CBD5E1;color:#64748B;background:#fff}
.card{margin:0 0 8px;border:1px solid #E2E8F0;border-radius:10px;line-height:24px;min-width:0}
.card p.lead{margin:0;padding:12px 14px;overflow-wrap:anywhere}
.card p.lead.sub{padding-top:0;font-size:14px;line-height:20px;color:#7A7A7A}
.state-ok,.state-muted{background:#F8FAFC}
.state-warn{background:#FFFBEB;border-color:#FDE68A}
.state-bad{background:#FFF7ED;border-color:#FED7AA}
.state-info{background:#EFF6FF;border-color:#BFDBFE}
.lnk{display:inline-flex;vertical-align:-1px;margin-left:4px;color:#1a73e8;white-space:nowrap}
.multi{background:#fff;border-radius:8px}
.acc+.acc{border-top:1px solid #E2E8F0}
.row{display:flex;align-items:center;gap:12px;padding:19px 12px;cursor:pointer;list-style:none}
.row::-webkit-details-marker{display:none}
.row:active{background:#EEF2F7}
.row-l{flex:0 0 65%;max-width:65%;min-width:0}
.row-r{flex:1 1 0;min-width:0;text-align:right;word-break:keep-all}
.name{font-size:16px;font-weight:700;color:#111}
.val{font-weight:700;color:#111;white-space:nowrap}
.none{color:#999;font-weight:400}
.warn-t{color:#e8710a}
.chev{flex:none;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:1px solid #E2E8F0;border-radius:6px;color:#111;margin-right:-4px}
.chev svg{transition:transform .15s}
details[open] .chev svg{transform:rotate(180deg)}
.acc-body{padding:0 12px 19px}
.sub-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-top:1px solid #F1F5F9;font-size:16px}
.sub-row:first-child{border-top:1px solid #E2E8F0}
.sub-row .row-l{font-weight:700;color:#111;overflow-wrap:anywhere}
.subline{display:block;font-size:14px;line-height:20px;font-weight:400}
.sub-t{color:#7A7A7A;font-size:14px}
ul.dots{list-style:none;margin:8px 0 0;padding:0}
ul.dots li{display:flex;align-items:flex-start;gap:7px;margin:8px 0;font-size:14px;line-height:20px;color:#333;overflow-wrap:anywhere;word-break:break-word}
ul.dots .dot{flex:none;width:2px;height:2px;border-radius:50%;background:#333;margin-top:9px}
.muted-line{margin:8px 0 0;font-size:14px;line-height:20px;color:#6B7280}
.foot{margin:28px 0 0;padding:2px 0 0 12px;border-top:1px solid #f3f3f3;font-size:14px;line-height:20px;color:#6B7280}
.foot p{margin:6px 0}
@media (max-width:900px){h1{font-size:27px;line-height:36px}}
@media (max-width:680px){main{padding:5px 14px 40px}h1{font-size:23px;line-height:32px}h2{font-size:20px;line-height:26px}.h2-sum{order:4;flex-basis:100%}}
`;

function capsules(verdicts) {
  const n = (f) => verdicts.filter(f).length;
  const items = [["발행", n((v) => v.tone === "ok")], ["미발행", n((v) => v.tone === "warn")], ["문제", n((v) => v.tone === "bad")], ["진행 중 · 실행 전", n((v) => v.tone === "info" || v.label === "실행 전")]];
  return `<div class="caps">${items.map(([k, x]) => `<span class="cap"><span class="k">${T(k)} : </span><b>${x}</b></span>`).join("")}</div>`;
}

function page(day, body, who) {
  const today = kstToday();
  const nav = `<form class="nav" method="get" action="/">
<a class="btn" href="?date=${shiftDay(day, -1)}">전날</a>${day < today ? `<a class="btn" href="?date=${shiftDay(day, 1)}">다음 날</a>` : ""}<a class="btn" href="/">오늘</a>
<input class="btn" type="date" name="date" value="${esc(day)}" max="${today}" aria-label="날짜 고르기"><button class="btn" type="submit">보기</button></form>`;
  return `<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>운영 현황</title><style>${CSS}</style></head><body><main>
<div class="top"><h1>운영 현황</h1><span class="h1-date">${dotDate(day)} (KST)</span></div>
${nav}${body}
<div class="foot"><p>${INFO_ICON}${T("자료 : 운영 기록 (Cloudflare KV · 180일 보관) · GitHub Actions 실행 목록. 새로고침하면 다시 읽습니다.")}</p>
<p>${INFO_ICON}${T(`관리자 : ${who || ""}`)} · <a href="/logout">로그아웃</a></p></div>
</main></body></html>`;
}

// 로그인 밖 화면(거부 · 로그아웃)도 같은 모양 — 문구 + 검은 테마 버튼(가이드라인 2-3)
function simplePage(title, msg, withLogin) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>${esc(title)}</title><style>${CSS}
.solo{max-width:480px;margin:40px auto}.dark{display:inline-block;background:#111;border:1px solid #111;color:#fff;border-radius:8px;font-size:16px;font-weight:700;line-height:24px;padding:12px 42px;text-decoration:none}.dark:active{opacity:.55}</style></head>
<body><main><div class="solo"><h1>${T(title)}</h1><p>${T(msg)}</p>${withLogin ? `<p><a class="dark" href="/login">GitHub로 로그인</a></p>` : ""}</div></main></body></html>`;
}

const HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex, nofollow",
};

export default {
  async fetch(req, env) {
    const { c, missing } = config(env);
    if (missing.length) return deny(`로그인 설정이 없습니다 (${missing.join(" · ")}).`);
    const url = new URL(req.url);
    if (req.method !== "GET") return deny("허용되지 않는 요청입니다.", 405);
    if (url.pathname === "/login") return startLogin(url, c);
    if (url.pathname === "/callback") return finishLogin(req, url, c);
    if (url.pathname === "/logout") return redirect("/signed-out", [setCookie(SESSION_COOKIE, "", 0)]);
    if (url.pathname === "/signed-out") return new Response(simplePage("로그아웃", "로그아웃했습니다.", true), { headers: HEADERS });
    const session = await readSession(req, c);
    if (!session) return redirect("/login");
    if (url.pathname !== "/") return new Response(simplePage("없는 페이지", "주소를 확인하세요.", false), { status: 404, headers: HEADERS });

    const today = kstToday();
    const q = url.searchParams.get("date");
    const day = /^\d{4}-\d{2}-\d{2}$/.test(q || "") && q <= today ? q : today;

    const [{ per, failed }, parts] = await Promise.all([loadRuns(env, day), loadParts(env, day)]);
    const verdicts = [];
    const sections = REPORTS.map((rep, i) => {
      const runs = Array.isArray(per[i]) ? per[i] : [];
      const ids = new Set(runs.map((r) => String(r.id)));
      const mine = parts.filter((p) => ids.has(String(p.run_id)) || (p.workflow === rep.wf && !p.run_id));
      // 목록 밖 실행(전날 밤 시작 등)의 기록은 워크플로 이름으로 붙인다
      for (const p of parts) if (p.workflow === rep.wf && !ids.has(String(p.run_id)) && !mine.includes(p)) mine.push(p);
      verdicts.push(verdict(rep, runs, mine, day, day === today));
      return renderReport(rep, runs, mine, day, day === today, per[i] && per[i].error);
    });

    const reportFiles = new Set(REPORTS.map((r) => r.file));
    const others = failed.filter((r) => !reportFiles.has(String(r.path || "").split("/").pop()));
    const otherSec = `<section class="rep"><h2>그 밖의 작업<span class="h2-sum">${INFO_ICON}${T("뉴스 · 시세 · 댓글 등의 실패")}</span>${pill(others.length ? `실패 ${others.length}` : "정상", others.length ? "bad" : "ok")}</h2>
${others.length ? `<div class="card multi">${others.map((r) => `<div class="row" style="cursor:default"><span class="row-l name">${T(r.name)}</span><span class="row-r">${toKst(r.created_at)}${link(runLink(r.id), "GitHub 실행 기록 열기")}</span></div>`).join('<div style="border-top:1px solid #E2E8F0"></div>')}</div>` : ""}</section>`;

    return new Response(page(day, capsules(verdicts) + sections.join("") + otherSec, session.login), { headers: HEADERS });
  },
};
