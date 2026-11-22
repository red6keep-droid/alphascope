// Newfact 토론 — 쓰기 API Worker (2026-11-22)
// 기획: alphascope-docs doc/기획/댓글-토론방-기획.md · 앱 대비: doc/운영/앱-대비-설계-원칙.md
//
// 읽기는 여기를 거치지 않는다. 쓰기가 들어오면 D1(원본)을 고치고, 그 자리 JSON 파일을 R2 에 다시 올린다.
// 방문자(블로그 · 앱)는 board.newfact.app/v1/… 파일을 Cloudflare 캐시(1분)로 읽는다 → 하루 방문객 10만이어도 한도에 안 묶인다.
//
// 로그인 = Firebase ID 토큰(Authorization: Bearer). 쿠키를 쓰지 않아 앱에서도 같다.
// 규칙(Firestore 새 판 73경우를 옮김): 별명 · 제목 40 · 내용 2,000 · 20초 · 하루 글 30 · 반응 30(한국 자정) · 링크 · 연락처 막기 ·
//   한 사람 한 표 · 신고 한 번(3명이면 바로 가림) · 쓰기 정지.

const enc = new TextEncoder();
const DAY = 86400e3;
const KST = 9 * 3600e3;
const PAGE = 20;      // index.json 의 최신 글 수
const CHUNK = 50;     // 묶음 파일 하나의 글 수(지난 글 전부 — 버리지 않는다)
const LIMIT_WRITES = 30;
const LIMIT_REACTS = 30;
const GAP_MS = 20e3;
const NICK_DAYS = 30;
const REPORT_HIDE = 3;
const REASONS = ["ad", "abuse", "privacy", "false", "etc"];
const OWNER_NICK = "Newfact";
const RESERVED = ["newfact", "뉴팩트", "운영자", "관리자", "admin", "owner", "운영진"];

// 열쇠 = Blogger 글 번호가 아닌, 블로그 · 앱 어디서나 통하는 영문 이름
const KEY_RE = /^(stock-[a-z0-9.-]{1,20}|p-[a-z0-9-]{1,70}|post-[a-z0-9-]{1,70}|market-kr|market-us|kr-report)$/;
const NICK_RE = /^[가-힣A-Za-z0-9]{2,12}$/;
const SYM_RE = /^[A-Z0-9][A-Z0-9.-]{0,11}$/;
const ID_RE = /^[a-z0-9]{8,24}$/;
// 오픈채팅 · 텔레그램 · 밴드 · 주소 · 휴대전화 번호(대소문자 · 줄바꿈 무관)
const BLOCK_RE = /(open\.kakao|kakao\.com\/o\/|t\.me\/|telegram|band\.us|https?:\/\/|www\.|01[016789][-. ]?[0-9]{3,4}[-. ]?[0-9]{4})/i;

// ---------------------------------------------------------------- 응답
class Fail extends Error {
  constructor(status, code, msg) { super(msg); this.status = status; this.code = code; }
}
const fail = (status, code, msg) => { throw new Fail(status, code, msg); };

function cors(req, env) {
  const origin = req.headers.get("Origin") || "";
  const ok = String(env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).includes(origin);
  return ok ? {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  } : { Vary: "Origin" };
}
function json(data, status, extra) {
  return new Response(JSON.stringify(data), { status: status || 200, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra } });
}

// ---------------------------------------------------------------- 로그인 (Firebase ID 토큰 — 운영 콘솔 Worker 와 같은 확인)
const FB_JWKS = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com";
let jwksCache = { at: 0, keys: [] };
const b64urlDecode = (s) => atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));

async function fbKeys() {
  if (Date.now() - jwksCache.at < 3600e3 && jwksCache.keys.length) return jwksCache.keys;
  const j = await fetch(FB_JWKS).then((r) => (r.ok ? r.json() : { keys: [] }));
  jwksCache = { at: Date.now(), keys: j.keys || [] };
  return jwksCache.keys;
}
async function verifyFirebase(token, project) {
  const [h, p, sig] = String(token || "").split(".");
  if (!h || !p || !sig) return null;
  let head, claims;
  try { head = JSON.parse(b64urlDecode(h)); claims = JSON.parse(b64urlDecode(p)); } catch { return null; }
  if (head.alg !== "RS256" || !head.kid) return null;
  const jwk = (await fbKeys()).find((k) => k.kid === head.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const raw = Uint8Array.from(b64urlDecode(sig), (x) => x.charCodeAt(0));
  if (!(await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, raw, enc.encode(`${h}.${p}`)))) return null;
  const now = Date.now() / 1000;
  if (claims.aud !== project || claims.iss !== `https://securetoken.google.com/${project}`) return null;
  if (!(claims.exp > now) || !(claims.iat <= now + 60) || !(claims.auth_time <= now + 60) || !claims.sub) return null;
  return String(claims.sub);
}

async function whoami(req, env) {
  if (env.TEST_MODE === "1" && req.headers.get("X-Test-Uid")) return req.headers.get("X-Test-Uid");   // 로컬 시험만
  const m = /^Bearer (.+)$/.exec(req.headers.get("Authorization") || "");
  const uid = m ? await verifyFirebase(m[1], env.FIREBASE_PROJECT_ID).catch(() => null) : null;
  return uid || fail(401, "login", "로그인이 필요합니다.");
}
function isAdmin(req, env) {
  const m = /^Bearer (.+)$/.exec(req.headers.get("Authorization") || "");
  return !!(env.ADMIN_KEY && m && m[1].length >= 32 && m[1] === env.ADMIN_KEY);
}

// ---------------------------------------------------------------- 검사
const kstDay = (ms) => Math.floor((ms + KST) / DAY);
const newId = () => [...crypto.getRandomValues(new Uint8Array(12))].map((b) => (b % 36).toString(36)).join("");
function str(v, name, min, max) {
  if (typeof v !== "string") fail(400, "bad", `${name} 이(가) 없습니다.`);
  const s = v.trim();
  if (s.length < min || s.length > max) fail(400, "length", `${name} 은(는) ${min}~${max}자입니다.`);
  return s;
}
function clean(s) {
  if (BLOCK_RE.test(s)) fail(400, "link", "오픈채팅 · 텔레그램 주소와 연락처, 인터넷 주소는 올릴 수 없습니다.");
  return s;
}
const keyOk = (k) => (typeof k === "string" && KEY_RE.test(k) ? k : fail(400, "key", "쓸 수 없는 자리입니다."));
const idOk = (v) => (typeof v === "string" && ID_RE.test(v) ? v : fail(400, "id", "없는 글입니다."));

async function body(req) {
  const t = await req.text();
  if (t.length > 20000) fail(413, "big", "너무 깁니다.");
  try { return t ? JSON.parse(t) : {}; } catch { return fail(400, "json", "형식이 틀렸습니다."); }
}

async function userRow(env, uid) {
  return (await env.DB.prepare("SELECT * FROM users WHERE uid = ?").bind(uid).first()) || null;
}
async function needWriter(env, uid, now, owner) {
  const u = await userRow(env, uid);
  if (owner) return u;
  if (!u || !u.nick) fail(403, "nick", "별명을 먼저 정해 주세요.");
  if (u.banned) fail(403, "banned", "글쓰기가 정지된 계정입니다.");
  if (u.last && now - u.last < GAP_MS) fail(429, "fast", "20초 뒤에 다시 써 주세요.");
  if (u.day === kstDay(now) && u.n >= LIMIT_WRITES) fail(429, "daily", `하루 ${LIMIT_WRITES}개까지 쓸 수 있습니다.`);
  return u;
}
// 하루 수 · 20초를 한 문장으로 올린다 — 동시에 두 번 들어와도 조건이 다시 걸린다(changes = 0 이면 거절)
async function bumpWrites(env, uid, now, owner) {
  if (owner) return;
  const d = kstDay(now);
  const r = await env.DB.prepare(
    `UPDATE users SET n = CASE WHEN day = ?1 THEN n + 1 ELSE 1 END, day = ?1, last = ?2
     WHERE uid = ?3 AND banned = 0 AND nick IS NOT NULL AND last <= ?4 AND (day <> ?1 OR n < ?5)`
  ).bind(d, now, uid, now - GAP_MS, LIMIT_WRITES).run();
  if (!r.meta.changes) fail(429, "daily", "잠시 뒤에 다시 써 주세요.");
}

// ---------------------------------------------------------------- 파일 (R2 · 공개 · 1분 캐시)
const FILE_HEAD = { contentType: "application/json; charset=utf-8", cacheControl: "public, max-age=0, s-maxage=60" };

function view(row, owner) {
  if (row.deleted) return { id: row.id, deleted: true, replies: row.replies || 0, created: row.created, seq: row.seq ?? undefined };
  if (row.hidden) return { id: row.id, hidden: true, replies: row.replies || 0, created: row.created, seq: row.seq ?? undefined };
  const v = {
    id: row.id, nick: row.uid === owner ? OWNER_NICK : (row.nick || "회원"), owner: row.uid === owner || undefined,
    text: row.text, created: row.created, up: row.up, down: row.down,
  };
  if (row.kind === "post") Object.assign(v, { seq: row.seq, title: row.title, replies: row.replies });
  if (row.sym) v.sym = row.sym;
  if (row.where_url) v.where = { url: row.where_url, label: row.where_label || "" };
  return v;
}
const SEL = "SELECT i.*, u.nick FROM items i LEFT JOIN users u ON u.uid = i.uid";

async function put(env, path, data) {
  await env.FILES.put(path, JSON.stringify(data), { httpMetadata: FILE_HEAD });
}
// 글 목록에서 뺄 것 = 지운 글 중 답글이 없는 것(답글이 있으면 "삭제된 글입니다" 로 남겨 답글을 지킨다)
const LISTED = "kind = 'post' AND NOT (deleted = 1 AND replies = 0)";

async function writeIndex(env, key) {
  const place = (await env.DB.prepare("SELECT posts, last_seq FROM places WHERE key = ?").bind(key).first()) || { posts: 0, last_seq: 0 };
  const rows = (await env.DB.prepare(`${SEL} WHERE i.key = ? AND ${LISTED} ORDER BY i.seq DESC LIMIT ${PAGE}`).bind(key).all()).results;
  const chunks = Math.ceil(place.last_seq / CHUNK);
  await put(env, `v1/${key}/index.json`, {
    v: 1, key, posts: place.posts, chunk_size: CHUNK, chunks,   // 묶음 파일 = b/0.json(1~50번) … b/{chunks-1}.json
    items: rows.map((r) => view(r, env.OWNER_UID)), updated: Date.now(),
  });
}
async function writeChunk(env, key, seq) {
  const n = Math.floor((seq - 1) / CHUNK);
  const rows = (await env.DB.prepare(`${SEL} WHERE i.key = ? AND i.kind = 'post' AND i.seq BETWEEN ? AND ? AND NOT (i.deleted = 1 AND i.replies = 0) ORDER BY i.seq DESC`)
    .bind(key, n * CHUNK + 1, (n + 1) * CHUNK).all()).results;
  await put(env, `v1/${key}/b/${n}.json`, { v: 1, key, chunk: n, items: rows.map((r) => view(r, env.OWNER_UID)), updated: Date.now() });
}
async function writeThread(env, key, postId) {
  const post = await env.DB.prepare(`${SEL} WHERE i.id = ?`).bind(postId).first();
  if (!post) return;
  const reps = (await env.DB.prepare(`${SEL} WHERE i.parent = ? AND i.kind = 'reply' AND i.deleted = 0 ORDER BY i.created`).bind(postId).all()).results;
  await put(env, `v1/${key}/t/${postId}.json`, { v: 1, key, post: view(post, env.OWNER_UID), replies: reps.map((r) => view(r, env.OWNER_UID)), updated: Date.now() });
}
// 글 하나가 바뀌면: 목록 · 그 글의 묶음 · 그 글 화면
async function refresh(env, post) {
  await Promise.all([writeIndex(env, post.key), writeChunk(env, post.key, post.seq), writeThread(env, post.key, post.id)]);
}
async function postOf(env, item) {
  return item.kind === "post" ? item : await env.DB.prepare("SELECT * FROM items WHERE id = ?").bind(item.parent).first();
}

// ---------------------------------------------------------------- 쓰기
async function createPost(env, uid, now, b) {
  const owner = uid === env.OWNER_UID;
  const key = keyOk(b.key);
  const title = clean(str(b.title, "제목", 1, 40));
  const text = clean(str(b.text, "내용", 1, 2000));
  const sym = b.sym == null || b.sym === "" ? null : (SYM_RE.test(b.sym) ? b.sym : fail(400, "sym", "종목 코드가 틀렸습니다."));
  let wurl = null, wlabel = null;
  if (b.where) {
    wurl = str(b.where.url, "글 주소", 1, 300);
    if (!/^https:\/\/(www\.)?newfact\.app\//.test(wurl)) fail(400, "where", "우리 블로그 글 주소만 됩니다.");
    wlabel = str(b.where.label || "", "꼬리표", 0, 40);
  }
  await needWriter(env, uid, now, owner);
  await bumpWrites(env, uid, now, owner);
  const id = newId();
  // 번호는 자리 칸(places)에서 한 문장으로 올려 받는다 — D1 은 쓰기를 하나씩 처리하므로 겹치지 않는다
  const [, placeRow] = await env.DB.batch([
    env.DB.prepare("INSERT INTO places (key, posts, last_seq) VALUES (?1, 1, 1) ON CONFLICT(key) DO UPDATE SET posts = posts + 1, last_seq = last_seq + 1").bind(key),
    env.DB.prepare("SELECT last_seq FROM places WHERE key = ?").bind(key),
  ]);
  const seq = placeRow.results[0].last_seq;
  await env.DB.prepare(`INSERT INTO items (id, key, kind, seq, uid, title, text, sym, where_url, where_label, created) VALUES (?, ?, 'post', ?, ?, ?, ?, ?, ?, ?, ?)`)
    .bind(id, key, seq, uid, title, text, sym, wurl, wlabel, now).run();
  const row = { id, key, kind: "post", seq };
  await refresh(env, row);
  return { item: view(await env.DB.prepare(`${SEL} WHERE i.id = ?`).bind(id).first(), env.OWNER_UID) };
}

async function createReply(env, uid, now, b) {
  const owner = uid === env.OWNER_UID;
  const post = await env.DB.prepare("SELECT * FROM items WHERE id = ? AND kind = 'post'").bind(idOk(b.post)).first();
  if (!post || post.deleted) fail(404, "gone", "없는 글입니다.");
  const text = clean(str(b.text, "답글", 1, 2000));
  const sym = b.sym == null || b.sym === "" ? null : (SYM_RE.test(b.sym) ? b.sym : fail(400, "sym", "종목 코드가 틀렸습니다."));
  await needWriter(env, uid, now, owner);
  await bumpWrites(env, uid, now, owner);
  const id = newId();
  await env.DB.batch([
    env.DB.prepare("INSERT INTO items (id, key, kind, parent, uid, text, sym, created) VALUES (?, ?, 'reply', ?, ?, ?, ?, ?)").bind(id, post.key, post.id, uid, text, sym, now),
    env.DB.prepare("UPDATE items SET replies = replies + 1 WHERE id = ?").bind(post.id),
  ]);
  await refresh(env, post);
  return { item: view(await env.DB.prepare(`${SEL} WHERE i.id = ?`).bind(id).first(), env.OWNER_UID) };
}

// v = 'up' | 'down' | null(취소). 바꾸기 · 새 표는 하루 30번을 쓰고, 취소는 돌려주지 않는다(11-21 확정)
async function react(env, uid, now, b) {
  const item = await env.DB.prepare("SELECT * FROM items WHERE id = ?").bind(idOk(b.item)).first();
  if (!item || item.deleted) fail(404, "gone", "없는 글입니다.");
  const v = b.v === null ? null : (b.v === "up" || b.v === "down" ? b.v : fail(400, "v", "좋아요 · 싫어요만 됩니다."));
  const u = await userRow(env, uid);
  if (u && u.banned) fail(403, "banned", "정지된 계정입니다.");
  const old = await env.DB.prepare("SELECT v FROM reacts WHERE item = ? AND uid = ?").bind(item.id, uid).first();
  const was = old ? old.v : null;
  if (was === v) fail(409, "same", v ? "이미 눌렀습니다." : "누른 적이 없습니다.");
  if (v) {
    const d = kstDay(now);
    await env.DB.prepare("INSERT INTO users (uid) VALUES (?) ON CONFLICT(uid) DO NOTHING").bind(uid).run();
    const r = await env.DB.prepare(
      "UPDATE users SET rn = CASE WHEN rday = ?1 THEN rn + 1 ELSE 1 END, rday = ?1 WHERE uid = ?2 AND banned = 0 AND (rday <> ?1 OR rn < ?3)"
    ).bind(d, uid, LIMIT_REACTS).run();
    if (!r.meta.changes) fail(429, "daily", `좋아요 · 싫어요는 하루 ${LIMIT_REACTS}번까지입니다.`);
  }
  const du = (v === "up" ? 1 : 0) - (was === "up" ? 1 : 0);
  const dd = (v === "down" ? 1 : 0) - (was === "down" ? 1 : 0);
  await env.DB.batch([
    v ? env.DB.prepare("INSERT INTO reacts (item, uid, v, created) VALUES (?1, ?2, ?3, ?4) ON CONFLICT(item, uid) DO UPDATE SET v = ?3, created = ?4").bind(item.id, uid, v, now)
      : env.DB.prepare("DELETE FROM reacts WHERE item = ? AND uid = ?").bind(item.id, uid),
    env.DB.prepare("UPDATE items SET up = MAX(0, up + ?), down = MAX(0, down + ?) WHERE id = ?").bind(du, dd, item.id),
  ]);
  await refresh(env, await postOf(env, item));
  const after = await env.DB.prepare("SELECT up, down FROM items WHERE id = ?").bind(item.id).first();
  return { item: item.id, v, up: after.up, down: after.down };
}

async function report(env, uid, now, b) {
  const item = await env.DB.prepare("SELECT * FROM items WHERE id = ?").bind(idOk(b.item)).first();
  if (!item || item.deleted) fail(404, "gone", "없는 글입니다.");
  if (!REASONS.includes(b.why)) fail(400, "why", "신고 이유를 골라 주세요.");
  if (item.uid === uid) fail(400, "self", "내 글은 신고할 수 없습니다.");
  const r = await env.DB.prepare("INSERT INTO reports (item, uid, why, created) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING").bind(item.id, uid, b.why, now).run();
  if (!r.meta.changes) fail(409, "same", "이미 신고했습니다.");
  const n = (await env.DB.prepare("SELECT COUNT(*) AS n FROM reports WHERE item = ?").bind(item.id).first()).n;
  let hidden = !!item.hidden;
  if (n >= REPORT_HIDE && !item.hidden) {   // 3명째 = 그 자리에서 바로 가린다(봇을 기다리지 않음)
    await env.DB.prepare("UPDATE items SET hidden = 1 WHERE id = ?").bind(item.id).run();
    await refresh(env, await postOf(env, item));
    hidden = true;
  }
  return { item: item.id, reported: true, hidden };
}

async function removeItem(env, uid, b, admin) {
  const item = await env.DB.prepare("SELECT * FROM items WHERE id = ?").bind(idOk(b.item)).first();
  if (!item || item.deleted) fail(404, "gone", "없는 글입니다.");
  if (!admin && item.uid !== uid && uid !== env.OWNER_UID) fail(403, "not-mine", "내 글만 지울 수 있습니다.");
  const st = [env.DB.prepare("UPDATE items SET deleted = 1, text = '', title = NULL, sym = NULL WHERE id = ?").bind(item.id)];
  if (item.kind === "reply") st.push(env.DB.prepare("UPDATE items SET replies = MAX(0, replies - 1) WHERE id = ?").bind(item.parent));
  else st.push(env.DB.prepare("UPDATE places SET posts = MAX(0, posts - 1) WHERE key = ?").bind(item.key));
  await env.DB.batch(st);
  await refresh(env, await postOf(env, item));
  return { item: item.id, deleted: true };
}

async function setProfile(env, uid, now, b) {
  const u = (await userRow(env, uid)) || {};
  const st = [env.DB.prepare("INSERT INTO users (uid) VALUES (?) ON CONFLICT(uid) DO NOTHING").bind(uid)];
  let nick = u.nick || null;
  if (b.nick !== undefined && b.nick !== u.nick) {
    nick = typeof b.nick === "string" ? b.nick.trim() : "";
    if (!NICK_RE.test(nick)) fail(400, "nick", "별명은 한글 · 영문 · 숫자 2~12자입니다.");
    if (RESERVED.includes(nick.toLowerCase())) fail(409, "taken", "쓸 수 없는 별명입니다.");
    if (u.nick_at && now - u.nick_at < NICK_DAYS * DAY) fail(429, "nick-wait", `별명은 ${NICK_DAYS}일에 한 번 바꿀 수 있습니다.`);
    const taken = await env.DB.prepare("SELECT uid FROM nicks WHERE nick = ?").bind(nick.toLowerCase()).first();
    if (taken && taken.uid !== uid) fail(409, "taken", "이미 쓰는 분이 있는 별명입니다.");
    if (u.nick) st.push(env.DB.prepare("DELETE FROM nicks WHERE nick = ? AND uid = ?").bind(u.nick.toLowerCase(), uid));
    st.push(env.DB.prepare("INSERT INTO nicks (nick, uid) VALUES (?, ?)").bind(nick.toLowerCase(), uid));
    st.push(env.DB.prepare("UPDATE users SET nick = ?, nick_at = ? WHERE uid = ?").bind(nick, now, uid));
  }
  if (b.intro !== undefined) st.push(env.DB.prepare("UPDATE users SET intro = ? WHERE uid = ?").bind(clean(str(b.intro, "소개", 0, 100)), uid));
  try { await env.DB.batch(st); } catch (e) {
    if (/UNIQUE/i.test(String(e))) fail(409, "taken", "이미 쓰는 분이 있는 별명입니다.");
    throw e;
  }
  // 별명이 바뀌면 그 사람이 글을 쓴 자리 목록 · 글 화면에 새 별명이 보이게 다시 만든다
  if (nick !== u.nick && u.nick) {
    const posts = (await env.DB.prepare(
      "SELECT DISTINCT p.id, p.key, p.seq, p.kind FROM items i JOIN items p ON p.id = CASE WHEN i.kind = 'post' THEN i.id ELSE i.parent END WHERE i.uid = ? AND i.deleted = 0 ORDER BY i.created DESC LIMIT 200"
    ).bind(uid).all()).results;
    for (const p of posts) await refresh(env, p);
  }
  return me(env, uid, now, null);
}

async function me(env, uid, now, key) {
  const u = (await userRow(env, uid)) || {};
  const d = kstDay(now);
  const out = {
    uid, nick: uid === env.OWNER_UID ? OWNER_NICK : (u.nick || null), intro: u.intro || "", owner: uid === env.OWNER_UID || undefined,
    banned: !!u.banned, nick_change_at: u.nick_at ? u.nick_at + NICK_DAYS * DAY : null,
    left: { writes: u.day === d ? Math.max(0, LIMIT_WRITES - u.n) : LIMIT_WRITES, reacts: u.rday === d ? Math.max(0, LIMIT_REACTS - u.rn) : LIMIT_REACTS },
  };
  if (key) {
    keyOk(key);
    const rows = (await env.DB.prepare("SELECT r.item, r.v FROM reacts r JOIN items i ON i.id = r.item WHERE r.uid = ? AND i.key = ?").bind(uid, key).all()).results;
    out.reacts = Object.fromEntries(rows.map((r) => [r.item, r.v]));
  }
  return out;
}
async function myItems(env, uid, before) {
  const rows = (await env.DB.prepare(
    "SELECT id, key, title, replies, created, where_label FROM items WHERE uid = ? AND kind = 'post' AND deleted = 0 AND created < ? ORDER BY created DESC LIMIT 20"
  ).bind(uid, before || 9e15).all()).results;
  return { items: rows };
}

// ---------------------------------------------------------------- 운영 (댓글 봇 · 운영 콘솔 — ADMIN_KEY)
async function admin(env, req, path, now) {
  const url = new URL(req.url);
  if (req.method === "GET" && path === "/v1/admin/new") {
    const since = Number(url.searchParams.get("since") || 0);
    const rows = (await env.DB.prepare(`${SEL} WHERE i.created > ? ORDER BY i.created LIMIT 200`).bind(since).all()).results;
    return { items: rows.map((r) => ({ ...view(r, env.OWNER_UID), key: r.key, kind: r.kind, parent: r.parent, uid: r.uid, title: r.title, text: r.text })) };
  }
  if (req.method === "GET" && path === "/v1/admin/hidden") {
    const rows = (await env.DB.prepare(`${SEL} WHERE i.hidden = 1 AND i.deleted = 0 ORDER BY i.created DESC LIMIT 200`).all()).results;
    return { items: rows.map((r) => ({ id: r.id, key: r.key, kind: r.kind, uid: r.uid, nick: r.nick, title: r.title, text: r.text, created: r.created })) };
  }
  const b = await body(req);
  if (path === "/v1/admin/reply") return createReply(env, env.OWNER_UID, now, b);
  if (path === "/v1/admin/remove") return removeItem(env, env.OWNER_UID, b, true);
  if (path === "/v1/admin/restore" || path === "/v1/admin/hide") {
    const item = await env.DB.prepare("SELECT * FROM items WHERE id = ?").bind(idOk(b.item)).first() || fail(404, "gone", "없는 글입니다.");
    const h = path === "/v1/admin/hide" ? 1 : 0;
    await env.DB.batch([
      env.DB.prepare("UPDATE items SET hidden = ? WHERE id = ?").bind(h, item.id),
      ...(h ? [] : [env.DB.prepare("DELETE FROM reports WHERE item = ?").bind(item.id)]),   // 되살린 글은 신고를 비워 다시 셀 수 있게
    ]);
    await refresh(env, await postOf(env, item));
    return { item: item.id, hidden: !!h };
  }
  if (path === "/v1/admin/ban") {
    if (typeof b.uid !== "string" || !b.uid) fail(400, "uid", "uid 가 없습니다.");
    await env.DB.prepare("INSERT INTO users (uid, banned) VALUES (?1, ?2) ON CONFLICT(uid) DO UPDATE SET banned = ?2").bind(b.uid, b.on ? 1 : 0).run();
    return { uid: b.uid, banned: !!b.on };
  }
  // 옛 댓글 옮기기(Firestore → D1) — 제목이 없던 옛 글은 내용 앞 40자를 제목으로
  if (path === "/v1/admin/import") {
    const key = keyOk(b.key);
    const text = str(b.text, "내용", 1, 2000);
    const created = Number(b.created) || now;
    await env.DB.prepare("INSERT INTO users (uid, nick) VALUES (?, ?) ON CONFLICT(uid) DO NOTHING").bind(String(b.uid), null).run();
    const [, placeRow] = await env.DB.batch([
      env.DB.prepare("INSERT INTO places (key, posts, last_seq) VALUES (?1, 1, 1) ON CONFLICT(key) DO UPDATE SET posts = posts + 1, last_seq = last_seq + 1").bind(key),
      env.DB.prepare("SELECT last_seq FROM places WHERE key = ?").bind(key),
    ]);
    const id = newId(), seq = placeRow.results[0].last_seq;
    await env.DB.prepare("INSERT INTO items (id, key, kind, seq, uid, title, text, created) VALUES (?, ?, 'post', ?, ?, ?, ?, ?)")
      .bind(id, key, seq, String(b.uid), (b.title || text.replace(/\s+/g, " ")).slice(0, 40), text, created).run();
    await refresh(env, { id, key, seq, kind: "post" });
    return { id, key, seq };
  }
  return fail(404, "none", "없는 주소입니다.");
}

// ---------------------------------------------------------------- 길 찾기
async function route(req, env) {
  const url = new URL(req.url);
  const path = url.pathname.replace(/\/+$/, "");
  const now = env.TEST_MODE === "1" && req.headers.get("X-Test-Now") ? Number(req.headers.get("X-Test-Now")) : Date.now();

  if (env.TEST_MODE === "1" && path === "/__file") {   // 로컬 시험만 — 배포에선 board.newfact.app 이 이 일을 한다
    const o = await env.FILES.get(url.searchParams.get("p") || "");
    return o ? new Response(o.body, { headers: { "Content-Type": "application/json; charset=utf-8", "X-Cache-Control": o.httpMetadata?.cacheControl || "" } }) : json({ error: "none" }, 404);
  }
  if (path.startsWith("/v1/admin/")) {
    if (!isAdmin(req, env)) fail(403, "admin", "운영 키가 없습니다.");
    return json(await admin(env, req, path, now));
  }
  if (path === "/v1/health") return json({ ok: true });

  const uid = await whoami(req, env);
  if (req.method === "GET" && path === "/v1/me") return json(await me(env, uid, now, url.searchParams.get("key")));
  if (req.method === "GET" && path === "/v1/me/items") return json(await myItems(env, uid, Number(url.searchParams.get("before")) || 0));
  if (req.method === "PUT" && path === "/v1/profile") return json(await setProfile(env, uid, now, await body(req)));
  if (req.method === "POST" && path === "/v1/post") return json(await createPost(env, uid, now, await body(req)), 201);
  if (req.method === "POST" && path === "/v1/reply") return json(await createReply(env, uid, now, await body(req)), 201);
  if (req.method === "POST" && path === "/v1/react") return json(await react(env, uid, now, await body(req)));
  if (req.method === "POST" && path === "/v1/report") return json(await report(env, uid, now, await body(req)));
  if (req.method === "DELETE" && path === "/v1/item") return json(await removeItem(env, uid, await body(req), false));
  return fail(404, "none", "없는 주소입니다.");
}

export default {
  async fetch(req, env) {
    const h = cors(req, env);
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
    try {
      const res = await route(req, env);
      for (const [k, v] of Object.entries(h)) res.headers.set(k, v);
      return res;
    } catch (e) {
      if (e instanceof Fail) return json({ error: e.code, message: e.message }, e.status, h);
      console.error(e && e.stack || e);
      return json({ error: "server", message: "잠시 뒤 다시 시도해 주세요." }, 500, h);
    }
  },
};
