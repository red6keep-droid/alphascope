// newfact-board 로컬 시험 (2026-11-22) — Firestore 규칙 새 판 73경우를 Worker 로 옮기고, 파일(R2) · 캐시 머리말까지 본다.
//
//   cd infra/board && sh test/run.sh        (로컬 D1 · R2 를 비우고 wrangler dev 를 띄운 뒤 이 파일을 돌린다)
//   또는 wrangler dev 가 떠 있으면:  BASE=http://127.0.0.1:8787 node test/run.mjs
//
// .dev.vars 의 TEST_MODE=1 일 때만 X-Test-Uid(로그인 대신) · X-Test-Now(시계) · /__file(R2 읽기)이 열린다.
const BASE = process.env.BASE || "http://127.0.0.1:8787";
const ADMIN = process.env.ADMIN_KEY || "test-admin-key-0123456789abcdef0123456789";
const OWNER = "u1vln4bbDgSgWQDe2F2FaNs81D43";
const DAY = 86400e3;
let clock = Date.parse("2026-11-22T03:00:00Z");   // 한국 12:00
const tick = (ms = 25e3) => (clock += ms);

async function call(method, path, { uid, body, now, admin, origin } = {}) {
  const h = { "Content-Type": "application/json" };
  if (uid) h["X-Test-Uid"] = uid;
  h["X-Test-Now"] = String(now ?? tick());
  if (admin) h.Authorization = `Bearer ${ADMIN}`;
  if (origin) h.Origin = origin;
  const r = await fetch(BASE + path, { method, headers: h, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text();
  let j; try { j = JSON.parse(t); } catch { j = t; }
  return { status: r.status, body: j, headers: r.headers };
}
const file = async (p) => { const r = await fetch(`${BASE}/__file?p=${encodeURIComponent(p)}`); return { status: r.status, body: r.status === 200 ? await r.json() : null, cache: r.headers.get("X-Cache-Control") }; };

const rows = [];
let group = "";
async function T(name, expect, fn) {
  let got;
  try { got = await fn(); } catch (e) { got = "오류: " + String(e.message || e).slice(0, 140); }
  rows.push({ group, name, expect, got: String(got), ok: String(expect) === String(got) });
}
const st = (r) => r.status;   // 기대 = 상태 번호(201 · 200 · 400 · 401 · 403 · 409 · 429)

// 사람 준비: 별명 정하기
const nick = (uid, n) => call("PUT", "/v1/profile", { uid, body: { nick: n } });
const post = (uid, over = {}) => call("POST", "/v1/post", { uid, body: { key: "stock-nvda", title: "제목", text: "의견입니다", ...over } });

// ── 로그인 · 주소 ─────────────────────────────
group = "로그인";
await T("로그인 없이 글쓰기", 401, async () => st(await call("POST", "/v1/post", { body: { key: "stock-nvda", title: "t", text: "t" } })));
await T("로그인 없이 내 정보", 401, async () => st(await call("GET", "/v1/me")));
await T("운영 주소 키 없이", 403, async () => st(await call("GET", "/v1/admin/new")));
await T("상태 확인", 200, async () => st(await call("GET", "/v1/health")));
await T("우리 블로그 CORS 허용", "https://www.newfact.app", async () => (await call("OPTIONS", "/v1/post", { origin: "https://www.newfact.app" })).headers.get("access-control-allow-origin"));
await T("남의 사이트 CORS 안 줌", "null", async () => String((await call("OPTIONS", "/v1/post", { origin: "https://evil.example" })).headers.get("access-control-allow-origin")));

// ── 별명 ─────────────────────────────────────
group = "별명";
await T("처음 별명 정하기", 200, async () => st(await nick("alice", "앨리스")));
await T("남이 쓰는 별명", 409, async () => st(await nick("bob", "앨리스")));
await T("대소문자만 다른 별명", 409, async () => { await nick("eve", "Trader"); return st(await nick("bob", "trader")); });
await T("예약어(Newfact)", 409, async () => st(await nick("bob", "newfact")));
await T("한 글자", 400, async () => st(await nick("bob", "가")));
await T("특수문자", 400, async () => st(await nick("bob", "밥!")));
await T("13자", 400, async () => st(await nick("bob", "가나다라마바사아자차카타파")));
await T("밥돌이 별명", 200, async () => st(await nick("bob", "밥돌이")));
await T("30일 안에 바꾸기", 429, async () => st(await nick("alice", "새앨리스")));
await T("30일 지나 바꾸기", 200, async () => st(await call("PUT", "/v1/profile", { uid: "alice", body: { nick: "새앨리스" }, now: tick(31 * DAY) })));
await T("옛 별명 다시 쓸 수 있음", 200, async () => st(await nick("carl", "앨리스")));
await T("소개만 고치기", 200, async () => st(await call("PUT", "/v1/profile", { uid: "bob", body: { intro: "장기 투자합니다" } })));
await T("소개 101자", 400, async () => st(await call("PUT", "/v1/profile", { uid: "bob", body: { intro: "ㄱ".repeat(101) } })));
await T("소개에 텔레그램", 400, async () => st(await call("PUT", "/v1/profile", { uid: "bob", body: { intro: "t.me/abc" } })));
await T("내 정보 = 별명 · 남은 수 30", "밥돌이/30/30", async () => { const r = (await call("GET", "/v1/me", { uid: "bob" })).body; return `${r.nick}/${r.left.writes}/${r.left.reacts}`; });

// ── 새 글 ────────────────────────────────────
group = "새 글";
let P1;
await T("별명 있는 회원 글", 201, async () => { const r = await post("bob", { title: "반도체 두 종목만 오른 날", sym: "000660" }); P1 = r.body.item; return r.status; });
await T("돌려준 글 = 별명 · 번호 1", "밥돌이/1", async () => `${P1.nick}/${P1.seq}`);
await T("자리 열쇠(시황 한국) + 쓴 날 꼬리표", 201, async () => st(await call("POST", "/v1/post", { uid: "bob", body: { key: "market-kr", title: "t", text: "t", where: { url: "https://www.newfact.app/2026/11/1118-market.html", label: "11.18 증시 시황" } } })));
await T("우리 블로그 밖 주소 꼬리표", 400, async () => st(await call("POST", "/v1/post", { uid: "bob", body: { key: "market-kr", title: "t", text: "t", where: { url: "https://evil.example/x", label: "x" } } })));
await T("정해 두지 않은 열쇠", 400, async () => st(await post("bob", { key: "free-talk" })));
await T("Blogger 글 번호 열쇠", 400, async () => st(await post("bob", { key: "1230658540885492397" })));
await T("별명 없는 회원", 403, async () => st(await post("nobody")));
await T("제목 없음", 400, async () => st(await post("bob", { title: "" })));
await T("제목 41자", 400, async () => st(await post("bob", { title: "ㄱ".repeat(41) })));
await T("내용 2,001자", 400, async () => st(await post("bob", { text: "ㄱ".repeat(2001) })));
await T("오픈채팅 주소", 400, async () => st(await post("bob", { text: "수익방 open.kakao.com/o/abc" })));
await T("텔레그램(대문자)", 400, async () => st(await post("bob", { text: "TELEGRAM 으로" })));
await T("휴대전화 번호", 400, async () => st(await post("bob", { text: "연락 010-1234-5678" })));
await T("줄바꿈 뒤 주소", 400, async () => st(await post("bob", { text: "첫 줄\n둘째 https://x.com" })));
await T("제목에 주소", 400, async () => st(await post("bob", { title: "band.us 가입" })));
await T("금액 숫자는 통과", 201, async () => st(await post("bob", { text: "목표가 120,000원, 3,500주" })));
await T("스티커 글자는 통과", 201, async () => st(await post("bob", { text: "찾았습니다[:mid_proof:]" })));
await T("종목 코드 틀림", 400, async () => st(await post("bob", { sym: "nvda!" })));
await T("20초 안에 또", 429, async () => { await nick("dan", "단단"); const n = tick(); await call("POST", "/v1/post", { uid: "dan", body: { key: "stock-nvda", title: "a", text: "a" }, now: n }); return st(await call("POST", "/v1/post", { uid: "dan", body: { key: "stock-nvda", title: "b", text: "b" }, now: n + 5e3 })); });
await T("오늘 30개까지 · 31번째 막힘", "30/429", async () => {
  await nick("fay", "페이"); let ok = 0;
  for (let i = 0; i < 30; i++) if ((await post("fay", { title: `글${i}` })).status === 201) ok++;
  return `${ok}/${st(await post("fay"))}`;
});
await T("다음 날(한국 자정 뒤) 다시 1번째", 201, async () => st(await call("POST", "/v1/post", { uid: "fay", body: { key: "stock-nvda", title: "새날", text: "x" }, now: tick(DAY) })));
await T("내 정보 남은 글 29", 29, async () => (await call("GET", "/v1/me", { uid: "fay" })).body.left.writes);

// ── 파일(읽기) ─────────────────────────────────
group = "파일";
await T("목록 파일 = 최신 20개", 20, async () => (await file("v1/stock-nvda/index.json")).body.items.length);
await T("목록 맨 위 = 가장 최근 글", "새날", async () => (await file("v1/stock-nvda/index.json")).body.items[0].title);
await T("묶음 파일 수 = ceil(글 수/50)", "ok", async () => { const b = (await file("v1/stock-nvda/index.json")).body; return b.chunks === Math.ceil(b.posts / 50) || b.chunks >= Math.ceil(b.posts / 50) ? "ok" : `${b.chunks}/${b.posts}`; });
await T("1번 글은 b/0 묶음에 있음", true, async () => (await file("v1/stock-nvda/b/0.json")).body.items.some((x) => x.id === P1.id));
await T("캐시 머리말 1분", "public, max-age=0, s-maxage=60", async () => (await file("v1/stock-nvda/index.json")).cache);
await T("글 화면 파일", "반도체 두 종목만 오른 날", async () => (await file(`v1/stock-nvda/t/${P1.id}.json`)).body.post.title);
await T("파일에 uid 없음", false, async () => JSON.stringify((await file("v1/stock-nvda/index.json")).body).includes('"uid"'));
await T("자리 꼬리표 파일에 실림", "11.18 증시 시황", async () => (await file("v1/market-kr/index.json")).body.items[0].where.label);

// ── 답글 ────────────────────────────────────
group = "답글";
let R1;
await T("답글", 201, async () => { const r = await call("POST", "/v1/reply", { uid: "alice", body: { post: P1.id, text: "저도 궁금했습니다" } }); R1 = r.body.item; return r.status; });
await T("답글 수 +1 이 목록에", 1, async () => (await file("v1/stock-nvda/b/0.json")).body.items.find((x) => x.id === P1.id).replies);
await T("글 화면에 답글", "저도 궁금했습니다", async () => (await file(`v1/stock-nvda/t/${P1.id}.json`)).body.replies[0].text);
await T("없는 글에 답글", 404, async () => st(await call("POST", "/v1/reply", { uid: "alice", body: { post: "zzzzzzzzzzzz", text: "x" } })));
await T("답글에 텔레그램", 400, async () => st(await call("POST", "/v1/reply", { uid: "alice", body: { post: P1.id, text: "t.me/x" } })));
await T("답글도 하루 수에 셈", 29, async () => (await call("GET", "/v1/me", { uid: "alice" })).body.left.writes);
await T("남의 답글 지우기", 403, async () => st(await call("DELETE", "/v1/item", { uid: "bob", body: { item: R1.id } })));
await T("내 답글 지우기 → 답글 수 0", "200/0", async () => { const r = await call("DELETE", "/v1/item", { uid: "alice", body: { item: R1.id } }); return `${r.status}/${(await file(`v1/stock-nvda/t/${P1.id}.json`)).body.post.replies}`; });
await T("운영자 답글(이름 Newfact)", "Newfact", async () => (await call("POST", "/v1/admin/reply", { admin: true, body: { post: P1.id, text: "리포트에 있습니다" } })).body.item.nick);

// ── 좋아요 · 싫어요 ───────────────────────────
group = "반응";
const react = (uid, item, v, now) => call("POST", "/v1/react", { uid, body: { item, v }, now });
await T("좋아요", "200/1", async () => { const r = await react("alice", P1.id, "up"); return `${r.status}/${r.body.up}`; });
await T("같은 좋아요 두 번", 409, async () => st(await react("alice", P1.id, "up")));
await T("좋아요 → 싫어요", "0/1", async () => { const r = (await react("alice", P1.id, "down")).body; return `${r.up}/${r.down}`; });
await T("취소", "0/0", async () => { const r = (await react("alice", P1.id, null)).body; return `${r.up}/${r.down}`; });
await T("누른 적 없는데 취소", 409, async () => st(await react("alice", P1.id, null)));
await T("목록 파일 숫자 맞음", "0/0", async () => { const x = (await file("v1/stock-nvda/b/0.json")).body.items.find((i) => i.id === P1.id); return `${x.up}/${x.down}`; });
await T("이상한 값", 400, async () => st(await react("alice", P1.id, "love")));
await T("내 정보에 내 표", "up", async () => { await react("bob", P1.id, "up"); return (await call("GET", "/v1/me?key=stock-nvda", { uid: "bob" })).body.reacts[P1.id]; });
await T("오늘 30번까지 · 31번째 막힘(취소는 안 돌려줌)", "429", async () => {
  await nick("gus", "거스");
  for (let i = 0; i < 15; i++) { await react("gus", P1.id, "up"); await react("gus", P1.id, "down"); }   // 30번 씀
  await react("gus", P1.id, null);
  return String(st(await react("gus", P1.id, "up")));
});
await T("별명 없어도 반응은 됨", 200, async () => st(await react("visitor1", P1.id, "up")));

// ── 신고 · 가림 ───────────────────────────────
group = "신고";
let BAD;
await T("신고", 200, async () => { BAD = (await post("bob", { title: "가릴 글" })).body.item; return st(await call("POST", "/v1/report", { uid: "alice", body: { item: BAD.id, why: "ad" } })); });
await T("한 사람 두 번", 409, async () => st(await call("POST", "/v1/report", { uid: "alice", body: { item: BAD.id, why: "etc" } })));
await T("없는 이유", 400, async () => st(await call("POST", "/v1/report", { uid: "carl", body: { item: BAD.id, why: "hate" } })));
await T("내 글 신고", 400, async () => st(await call("POST", "/v1/report", { uid: "bob", body: { item: BAD.id, why: "ad" } })));
await T("3명째 → 바로 가림", true, async () => { await call("POST", "/v1/report", { uid: "carl", body: { item: BAD.id, why: "ad" } }); return (await call("POST", "/v1/report", { uid: "dan", body: { item: BAD.id, why: "abuse" } })).body.hidden; });
await T("파일에서 가려짐(내용 없음)", "true/undefined", async () => { const x = (await file(`v1/stock-nvda/t/${BAD.id}.json`)).body.post; return `${x.hidden}/${x.title}`; });
await T("운영 · 가려진 글 목록", true, async () => (await call("GET", "/v1/admin/hidden", { admin: true })).body.items.some((x) => x.id === BAD.id));
await T("운영자 되살리기", "가릴 글", async () => { await call("POST", "/v1/admin/restore", { admin: true, body: { item: BAD.id } }); return (await file(`v1/stock-nvda/t/${BAD.id}.json`)).body.post.title; });

// ── 지우기 · 운영 ───────────────────────────────
group = "지우기 · 운영";
await T("남의 글 지우기", 403, async () => st(await call("DELETE", "/v1/item", { uid: "alice", body: { item: BAD.id } })));
await T("답글 있는 글 지우기 → '삭제됨'으로 남음", true, async () => { await call("DELETE", "/v1/item", { uid: "bob", body: { item: P1.id } }); return (await file(`v1/stock-nvda/t/${P1.id}.json`)).body.post.deleted; });
await T("답글 없는 글 지우기 → 목록에서 빠짐", false, async () => { await call("DELETE", "/v1/item", { uid: "bob", body: { item: BAD.id } }); return (await file("v1/stock-nvda/b/0.json")).body.items.some((x) => x.id === BAD.id); });
await T("운영자(블로그 주인)가 남의 글 지우기", 200, async () => { const x = (await post("alice", { title: "주인이 지울 글" })).body.item; return st(await call("DELETE", "/v1/item", { uid: OWNER, body: { item: x.id } })); });
await T("쓰기 정지 → 글 막힘", 403, async () => { await call("POST", "/v1/admin/ban", { admin: true, body: { uid: "carl", on: true } }); return st(await post("carl")); });
await T("쓰기 정지 → 반응도 막힘", 403, async () => st(await react("carl", P1.id === undefined ? "x" : (await post("alice", { title: "r" })).body.item.id, "up")));
await T("운영 · 새 글 목록", true, async () => (await call("GET", `/v1/admin/new?since=0`, { admin: true })).body.items.length > 0);
await T("옛 댓글 옮기기", "분석글 좀더 올려주세요", async () => { const r = (await call("POST", "/v1/admin/import", { admin: true, body: { key: "p-forecast-nvda-2026q3", uid: "pLBlvk", text: "분석글 좀더 올려주세요", created: Date.parse("2026-11-22T01:09:26Z") } })).body; return (await file(`v1/p-forecast-nvda-2026q3/t/${r.id}.json`)).body.post.text; });
await T("별명 바꾸면 지난 글도 새 별명", "새밥", async () => {
  await nick("hal", "할할"); const p = (await call("POST", "/v1/post", { uid: "hal", body: { key: "stock-tsla", title: "t", text: "t" } })).body.item;
  await call("PUT", "/v1/profile", { uid: "hal", body: { nick: "새밥" }, now: tick(31 * DAY) });
  return (await file(`v1/stock-tsla/t/${p.id}.json`)).body.post.nick;
});
await T("내가 쓴 글 목록", true, async () => (await call("GET", "/v1/me/items", { uid: "fay" })).body.items.length === 20);

// 결과 표
let fail = 0, last = "";
for (const r of rows) {
  if (r.group !== last) { console.log(`\n[${r.group}]`); last = r.group; }
  if (!r.ok) fail++;
  console.log(`${r.ok ? " ok " : "FAIL"}  ${r.name}  — 기대 ${r.expect} · 실제 ${r.got}`);
}
console.log(`\n${rows.length}건 중 ${rows.length - fail}건 맞음 · ${fail}건 다름`);
process.exit(fail ? 1 : 0);
