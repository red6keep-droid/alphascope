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
  return new Response(`접근 거부 — ${why}`, { status, headers: { ...HEADERS, "Content-Type": "text/plain; charset=utf-8" } });
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
    const label = { published: "발행됨", updated: "발행 · 갱신", already: "이미 발행됨" }[done.status];
    return { tone: "ok", label, url: done.url, why: exc ? `발행 뒤 에러: ${exc}` : "" };
  }
  if (running) return { tone: "info", label: "진행 중", why: `${toKst(running.created_at)} 시작` };
  if (exc) return { tone: "bad", label: "에러로 중단", why: exc };
  if (skip) return { tone: "warn", label: "미발행", why: skip.reason };
  if (failedRun) return { tone: "bad", label: "워크플로 실패", why: parts.length ? "파이썬 밖 단계에서 실패 — 실행 로그 확인" : "운영 기록 없이 실패 — 설치 · 체크아웃 단계일 수 있음, 실행 로그 확인" };
  if (dry) return { tone: "warn", label: "미발행 (dry-run)", why: "게시 모드가 꺼진 실행 — 저장소 변수 *_PUBLISH 또는 수동 실행의 publish 입력 확인" };
  if (runs.length) return { tone: "warn", label: "미발행", why: parts.length ? "게시 단계 기록 없음 — 실행 로그 확인" : "운영 기록 없음 (OPS_CF_* 비밀값 설정 전이거나 기록 전송 실패)" };
  if (!expected) return { tone: "muted", label: "예정 없음", why: "이 요일에는 돌지 않는다" };
  if (isToday) return { tone: "muted", label: "아직 안 돎", why: `예정 KST ${rep.at}경 — 지났다면 Cloudflare 트리거 · GitHub 예약 누락` };
  return { tone: "bad", label: "실행 없음", why: "예약 실행이 오지 않았다 (Cloudflare 트리거 · GitHub cron 모두 누락)" };
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

// ---------------------------------------------------------------- 화면
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (u) => (/^https:\/\/[\w.-]+\//.test(String(u || "")) ? String(u) : "");
const runLink = (id) => `https://github.com/${REPO}/actions/runs/${encodeURIComponent(id)}`;

function eventTone(k) {
  if (/^전부 실패/.test(k)) return "bad";
  if (/^(예비|대체|한도|검사 탈락)/.test(k)) return "warn";
  return "muted";
}

function renderReport(rep, runs, parts, day, isToday, runsError) {
  const v = verdict(rep, runs, parts, day, isToday);
  const { usage, events } = llmSummary(parts);
  const collect = parts.flatMap((p) => (p.warnings || []).filter((w) => w.cat === "collect").map((w) => w.text));
  const notes = parts.flatMap((p) => Object.entries(p.notify || {}).map(([k, n]) => (n > 1 ? `${k} ×${n}` : k)));
  const other = parts.flatMap((p) => (p.warnings || []).filter((w) => w.cat !== "collect").map((w) => w.text));
  const url = safeUrl(v.url);

  const usageRows = Object.entries(usage)
    .map(([k, u]) => `<tr><td>${esc(k)}</td><td class="num">${u.ok}/${u.ok + u.fail}</td><td>${u.fail ? `<span class="pill warn">실패 ${u.fail}</span>` : `<span class="pill ok">정상</span>`}</td></tr>`)
    .join("");
  const eventRows = Object.entries(events)
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => {
      const kind = (k.match(/^(검사 탈락|전부 실패|예비|대체|한도)/) || [k.split(" ")[0]])[0];
      return `<li><span class="pill ${eventTone(k)}">${esc(kind)}</span> ${esc(k.slice(kind.length).trim())}${n > 1 ? ` <span class="muted">×${n}</span>` : ""}</li>`;
    })
    .join("");
  const list = (xs) => (xs.length ? `<ul class="lines">${[...new Set(xs)].map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="muted">없음</p>`);
  const runRows = runs
    .map((r) => `<li><a href="${runLink(r.id)}" rel="noreferrer" target="_blank">${toKst(r.created_at)} · ${esc(r.event)}</a> — ${esc(r.conclusion || r.status)}</li>`)
    .join("");

  return `
<section class="card">
  <header class="card-head">
    <div><h2>${esc(rep.name)}</h2><p class="muted">예정 KST ${esc(rep.at)}경 · ${esc(rep.file)}</p></div>
    <span class="badge ${v.tone}">${esc(v.label)}</span>
  </header>
  ${url ? `<p><a href="${esc(url)}" rel="noreferrer" target="_blank">${esc(url)}</a></p>` : ""}
  ${v.why ? `<p class="why">${esc(v.why)}</p>` : ""}
  ${runsError ? `<p class="why">GitHub 실행 목록을 못 읽음: ${esc(runsError)}</p>` : ""}
  <details ${v.tone === "bad" || v.tone === "warn" ? "open" : ""}>
    <summary>AI 모델 사슬 ${Object.keys(events).length ? `<span class="pill warn">전환 · 경고 ${Object.keys(events).length}</span>` : ""}</summary>
    ${usageRows ? `<table><thead><tr><th>단계</th><th class="num">성공/시도</th><th></th></tr></thead><tbody>${usageRows}</tbody></table>` : `<p class="muted">AI 호출 기록 없음</p>`}
    ${eventRows ? `<ul class="events">${eventRows}</ul>` : ""}
  </details>
  <details ${collect.length || notes.length ? "open" : ""}>
    <summary>정보 수집 오류 ${collect.length + notes.length ? `<span class="pill warn">${collect.length + notes.length}</span>` : ""}</summary>
    ${notes.length ? `<h3>운영 알림</h3>${list(notes)}` : ""}
    <h3>수집 실패 줄</h3>${list(collect)}
  </details>
  ${other.length ? `<details><summary>그 밖의 경고 <span class="pill muted">${other.length}</span></summary>${list(other)}</details>` : ""}
  <details><summary>실행 ${runs.length}회</summary>${runRows ? `<ul class="lines">${runRows}</ul>` : `<p class="muted">없음</p>`}</details>
</section>`;
}

function page(day, body, who) {
  const today = kstToday();
  return `<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>운영 현황</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1b1f24;--muted:#667085;--line:#e4e7ec;--ok:#067647;--ok-bg:#ecfdf3;--warn:#b54708;--warn-bg:#fffaeb;--bad:#b42318;--bad-bg:#fef3f2;--info:#175cd3;--info-bg:#eff8ff;--link:#175cd3}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--fg:#e6e8eb;--muted:#98a2b3;--line:#2a2f3a;--ok:#47cd89;--ok-bg:#0b2e1f;--warn:#fdb022;--warn-bg:#33240a;--bad:#f97066;--bad-bg:#3a1210;--info:#84caff;--info-bg:#0b2540;--link:#84caff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 48px}a{color:var(--link)}
.top{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:16px}
h1{font-size:22px;margin:0}h2{font-size:17px;margin:0}h3{font-size:13px;margin:12px 0 4px;color:var(--muted)}
.nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.nav a,.nav button,.nav input{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);text-decoration:none}
.grid{display:grid;gap:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;overflow-wrap:anywhere}
.card-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.card-head p{margin:2px 0 0;font-size:13px}
.badge{white-space:nowrap;font-weight:600;font-size:13px;padding:4px 10px;border-radius:999px}
.ok{color:var(--ok);background:var(--ok-bg)}.warn{color:var(--warn);background:var(--warn-bg)}.bad{color:var(--bad);background:var(--bad-bg)}.info{color:var(--info);background:var(--info-bg)}.muted{color:var(--muted)}
.badge.muted,.pill.muted{background:var(--bg)}
.pill{font-size:12px;padding:1px 8px;border-radius:999px;margin-left:4px}
.why{margin:8px 0;padding:8px 10px;border-left:3px solid var(--line);background:var(--bg);border-radius:4px;font-size:14px}
details{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}summary{cursor:pointer;font-weight:600;font-size:14px}
table{border-collapse:collapse;width:100%;margin-top:8px;font-size:14px}th,td{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line)}.num{text-align:right;font-variant-numeric:tabular-nums}
ul.lines,ul.events{margin:6px 0 0;padding-left:18px;font-size:13px}ul.lines li{font-family:ui-monospace,Consolas,monospace;font-size:12px;margin:2px 0}
.foot{margin-top:20px;font-size:12px;color:var(--muted)}
</style></head><body><main>
<div class="top"><h1>운영 현황 <span class="muted" style="font-size:15px">${esc(day)} (KST)</span></h1>
<form class="nav" method="get"><a href="?date=${shiftDay(day, -1)}">← 전날</a>${day < today ? `<a href="?date=${shiftDay(day, 1)}">다음 날 →</a>` : ""}<a href="?">오늘</a>
<input type="date" name="date" value="${esc(day)}" max="${today}"><button type="submit">보기</button></form></div>
${body}
<p class="foot">관리자 ${esc(who || "")} (<a href="/logout">로그아웃</a>) ·자료: 운영 기록(Cloudflare KV, 180일) + GitHub Actions 실행 목록 · 새로고침하면 다시 읽는다</p>
</main></body></html>`;
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
    if (url.pathname === "/signed-out") return new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>로그아웃</title><p style="font:16px system-ui;padding:24px">로그아웃했습니다. <a href="/login">다시 로그인</a></p>`, { headers: HEADERS });
    const session = await readSession(req, c);
    if (!session) return redirect("/login");
    const auth = { email: session.login };
    if (url.pathname !== "/") return new Response("없음", { status: 404, headers: HEADERS });

    const today = kstToday();
    const q = url.searchParams.get("date");
    const day = /^\d{4}-\d{2}-\d{2}$/.test(q || "") && q <= today ? q : today;

    const [{ per, failed }, parts] = await Promise.all([loadRuns(env, day), loadParts(env, day)]);
    const cards = REPORTS.map((rep, i) => {
      const runs = Array.isArray(per[i]) ? per[i] : [];
      const ids = new Set(runs.map((r) => String(r.id)));
      const mine = parts.filter((p) => ids.has(String(p.run_id)) || (p.workflow === rep.wf && !p.run_id));
      // 목록 밖 실행(전날 밤 시작 등)의 기록은 워크플로 이름으로 붙인다
      for (const p of parts) if (p.workflow === rep.wf && !ids.has(String(p.run_id)) && !mine.includes(p)) mine.push(p);
      return renderReport(rep, runs, mine, day, day === today, per[i] && per[i].error);
    });

    const reportFiles = new Set(REPORTS.map((r) => r.file));
    const others = failed.filter((r) => !reportFiles.has(String(r.path || "").split("/").pop()));
    const otherCard = `<section class="card"><header class="card-head"><div><h2>그 밖의 워크플로 실패</h2><p class="muted">뉴스 · 시세 · 댓글 등</p></div>
<span class="badge ${others.length ? "bad" : "ok"}">${others.length ? `${others.length}건` : "없음"}</span></header>
${others.length ? `<ul class="lines">${others.map((r) => `<li><a href="${runLink(r.id)}" rel="noreferrer" target="_blank">${toKst(r.created_at)} · ${esc(r.name)}</a></li>`).join("")}</ul>` : ""}</section>`;

    return new Response(page(day, `<div class="grid">${cards.join("")}${otherCard}</div>`, auth.email), { headers: HEADERS });
  },
};
