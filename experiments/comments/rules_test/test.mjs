// **보류(2026-11-22 같은 날): 토론 저장소를 Cloudflare(D1 · R2 · Worker)로 바꿔 이 규칙은 게시하지 않는다.** 경우 표는 Worker 시험으로 옮긴다. 규칙 = 같은 폴더 firestore.next.rules
// 댓글 규칙 새 판 시험 (2026-11-22) — 공개 저장소 firestore.rules 를 에뮬레이터에 올려 막힘 · 통과 경우를 하나씩 확인한다.
//
//   실행(에뮬레이터 안에서):  firebase emulators:exec --only firestore --project demo-newfact "node experiments/comments/rules_test/test.mjs"
//   필요: Java 11+ · firebase-tools · @firebase/rules-unit-testing@3 · firebase@10 (전역 설치 없이 임시 폴더에 받아 NODE_PATH 로 써도 된다)
//
// 경우 표 = 아래 T(…) 줄. 기대(통과/막힘)와 실제가 다르면 끝에 실패 수를 내고 종료 코드 1.
import { readFileSync } from 'node:fs';
import { initializeTestEnvironment, assertSucceeds, assertFails } from '@firebase/rules-unit-testing';
import { doc, setDoc, getDoc, deleteDoc, writeBatch, serverTimestamp, increment, Timestamp,
         collectionGroup, query, where, getDocs, updateDoc } from 'firebase/firestore';

const RULES = readFileSync(process.env.RULES_FILE || new URL('./firestore.next.rules', import.meta.url), 'utf8');   // 임시 폴더로 옮겨 돌릴 때 RULES_FILE
const OWNER = 'u1vln4bbDgSgWQDe2F2FaNs81D43';
const env = await initializeTestEnvironment({
  projectId: 'demo-newfact',
  firestore: { rules: RULES, host: '127.0.0.1', port: 8080 },
});

const HOUR_AGO = Timestamp.fromMillis(Date.now() - 3600e3);
const kstDay = (ms) => Math.floor((ms + 9 * 3600e3) / 86400e3);
const TODAY = kstDay(Date.now());
const K = '1230658540885492397';           // 글 열쇠
const C = `posts/${K}/comments`;

// 규칙 밖에서 시작 상태 깔기
async function seed(fn) { await env.withSecurityRulesDisabled(async (ctx) => fn(ctx.firestore())); }
async function reset() {
  await env.clearFirestore();
  await seed(async (db) => {
    for (const [uid, nick] of [['alice', '앨리스'], ['bob', '밥'], [OWNER, '운영자']]) {
      await setDoc(doc(db, `users/${uid}`), { last: HOUR_AGO, nick, nickAt: Timestamp.fromMillis(Date.now() - 40 * 86400e3) });
      await setDoc(doc(db, `nicks/${nick}`), { uid });
    }
    await setDoc(doc(db, `users/carol`), { last: HOUR_AGO });   // 별명 없는 옛 회원
    await setDoc(doc(db, `${C}/c1`), { uid: 'bob', nick: '밥', title: '첫 글', text: '내용', created: HOUR_AGO, up: 0, down: 0, replies: 1 });
    await setDoc(doc(db, `${C}/c1/replies/r1`), { uid: 'alice', nick: '앨리스', text: '답글', created: HOUR_AGO, up: 0, down: 0 });
  });
}
const as = (uid) => env.authenticatedContext(uid).firestore();
const guest = () => env.unauthenticatedContext().firestore();

// 새 글 하나 쓰는 commit (테마가 할 일과 같은 꼴)
function newPost(db, uid, id, over = {}, userOver = {}, key = K) {
  const b = writeBatch(db);
  b.set(doc(db, `posts/${key}/comments/${id}`), { uid, nick: over.nick ?? null, title: '제목', text: '의견입니다', created: serverTimestamp(), up: 0, down: 0, replies: 0, ...over });
  b.set(doc(db, `users/${uid}`), { last: serverTimestamp(), lastC: id, day: TODAY, n: 1, ...userOver }, { merge: true });
  return b.commit();
}
function newReply(db, uid, rid, nick, { bump = true, userBump = true, n = 1 } = {}) {
  const b = writeBatch(db);
  b.set(doc(db, `${C}/c1/replies/${rid}`), { uid, nick, text: '답글입니다', created: serverTimestamp(), up: 0, down: 0 });
  if (bump) b.update(doc(db, `${C}/c1`), { replies: increment(1) });
  if (userBump) b.set(doc(db, `users/${uid}`), { last: serverTimestamp(), lastC: rid, day: TODAY, n }, { merge: true });
  return b.commit();
}
function react(db, uid, target, v, { mode = 'set', up = 0, down = 0, rn = 1 } = {}) {
  const b = writeBatch(db);
  if (mode === 'del') b.delete(doc(db, `${target}/reacts/${uid}`));
  else b.set(doc(db, `${target}/reacts/${uid}`), { v, created: serverTimestamp() });
  if (up || down) b.update(doc(db, target), { up: increment(up), down: increment(down) });
  if (mode !== 'del') b.set(doc(db, `users/${uid}`), { rlast: serverTimestamp(), rday: TODAY, rn }, { merge: true });
  return b.commit();
}

const rows = [];
async function T(group, name, expect, fn) {
  await reset();
  let got;
  try { await fn(); got = '통과'; } catch (e) { got = (String(e.code || e.message).includes('permission') ? '막힘' : '오류: ' + String(e.message).slice(0, 120)); }
  rows.push({ group, name, expect, got, ok: expect === got });
}

// ── 옛 테마(새 테마 붙여넣기 전까지) ─────────────────────────────
const legacy = (db, uid, text, extraSeed) => {
  const b = writeBatch(db);
  b.set(doc(db, `${C}/old1`), { uid, name: 'keep red9', photo: '', text, created: serverTimestamp() });
  b.set(doc(db, `users/${uid}`), { last: serverTimestamp() });
  return b.commit();
};
await T('옛 테마', '지금 블로그 꼴 댓글', '통과', () => legacy(as('carol'), 'carol', '분석글 좀더 올려주세요'));
await T('옛 테마', '텔레그램 주소', '막힘', () => legacy(as('carol'), 'carol', '여기로 t.me/abc'));
await T('옛 테마', '20초 안에 또', '막힘', async () => { await seed((db) => setDoc(doc(db, 'users/carol'), { last: Timestamp.now() })); await legacy(as('carol'), 'carol', '또'); });
await T('옛 테마', '쓰기 정지된 사람', '막힘', async () => { await seed((db) => setDoc(doc(db, 'bans/carol'), { why: '시험' })); await legacy(as('carol'), 'carol', '안녕'); });

// ── 별명 ─────────────────────────────────────────────────────
const setNick = (db, uid, nick, extra = {}) => {
  const b = writeBatch(db);
  b.set(doc(db, `nicks/${nick}`), { uid });
  b.set(doc(db, `users/${uid}`), { nick, nickAt: serverTimestamp(), ...extra }, { merge: true });
  return b.commit();
};
await T('별명', '처음 별명 정하기', '통과', () => setNick(as('carol'), 'carol', '주린이탈출'));
await T('별명', '남이 쓰는 별명', '막힘', () => setNick(as('carol'), 'carol', '밥'));
await T('별명', '한 글자', '막힘', () => setNick(as('carol'), 'carol', '가'));
await T('별명', '특수문자', '막힘', () => setNick(as('carol'), 'carol', '주린이!'));
await T('별명', '30일 지나 바꾸기(옛 별명 놓기)', '통과', () => { const db = as('alice'); const b = writeBatch(db); b.delete(doc(db, 'nicks/앨리스')); b.set(doc(db, 'nicks/새앨리스'), { uid: 'alice' }); b.set(doc(db, 'users/alice'), { nick: '새앨리스', nickAt: serverTimestamp() }, { merge: true }); return b.commit(); });
await T('별명', '30일 안에 또 바꾸기', '막힘', async () => { await seed((db) => setDoc(doc(db, 'users/alice'), { nickAt: Timestamp.now() }, { merge: true })); await setNick(as('alice'), 'alice', '또바꿈'); });
await T('별명', '소개만 고치기', '통과', () => setDoc(doc(as('alice'), 'users/alice'), { intro: '장기 투자합니다' }, { merge: true }));
await T('별명', '소개 101자', '막힘', () => setDoc(doc(as('alice'), 'users/alice'), { intro: 'ㄱ'.repeat(101) }, { merge: true }));
await T('별명', '남의 별명 문서 지우기', '막힘', () => deleteDoc(doc(as('alice'), 'nicks/밥')));
await T('별명', '남의 users 읽기', '막힘', () => getDoc(doc(as('alice'), 'users/bob')));
await T('별명', '내 users 읽기', '통과', () => getDoc(doc(as('alice'), 'users/alice')));

// ── 새 글 ────────────────────────────────────────────────────
await T('새 글', '별명 있는 회원 글', '통과', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }));
await T('새 글', '종목 · 쓴 날 주소 붙이기', '통과', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', sym: '000660', post: 'https://www.newfact.app/2026/11/x.html' }));
await T('새 글', '자리 열쇠(시황 한국)', '통과', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }, {}, 'place-market-kr'));
await T('새 글', '정해 두지 않은 열쇠', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }, {}, 'place-free'));
await T('새 글', '로그인 전', '막힘', () => setDoc(doc(guest(), `${C}/p1`), { uid: 'x', nick: 'x', title: 't', text: 't', created: serverTimestamp(), up: 0, down: 0, replies: 0 }));
await T('새 글', '별명 없는 회원', '막힘', () => newPost(as('carol'), 'carol', 'p1', { nick: 'carol' }));
await T('새 글', '별명 사칭(남의 별명)', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '밥' }));
await T('새 글', '제목 없음', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', title: '' }));
await T('새 글', '제목 41자', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', title: 'ㄱ'.repeat(41) }));
await T('새 글', '본문 2,001자', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', text: 'ㄱ'.repeat(2001) }));
await T('새 글', '오픈채팅 주소', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', text: '수익방 open.kakao.com/o/abc 로' }));
await T('새 글', '텔레그램(대문자)', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', text: 'TELEGRAM 으로 오세요' }));
await T('새 글', '휴대전화 번호', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', text: '연락 010-1234-5678' }));
await T('새 글', '줄바꿈 뒤 주소', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', text: '첫 줄\n둘째 줄 https://x.com' }));
await T('새 글', '제목에 주소', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', title: 'band.us 가입' }));
await T('새 글', '숫자만 든 보통 글(금액)', '통과', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', text: '목표가 120,000원, 3,500주 거래' }));
await T('새 글', '좋아요를 5로 시작', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', up: 5 }));
await T('새 글', '모르는 칸(hidden)', '막힘', () => newPost(as('alice'), 'alice', 'p1', { nick: '앨리스', hidden: false }));
await T('새 글', 'users 를 같이 안 고침', '막힘', () => setDoc(doc(as('alice'), `${C}/p1`), { uid: 'alice', nick: '앨리스', title: 't', text: 't', created: serverTimestamp(), up: 0, down: 0, replies: 0 }));
await T('새 글', '20초 안에 또', '막힘', async () => { await seed((db) => setDoc(doc(db, 'users/alice'), { last: Timestamp.now() }, { merge: true })); await newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }); });
await T('새 글', '오늘 31번째', '막힘', async () => { await seed((db) => setDoc(doc(db, 'users/alice'), { day: TODAY, n: 30 }, { merge: true })); await newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }, { n: 31 }); });
await T('새 글', '오늘 30번째', '통과', async () => { await seed((db) => setDoc(doc(db, 'users/alice'), { day: TODAY, n: 29 }, { merge: true })); await newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }, { n: 30 }); });
await T('새 글', '어제 30개 → 오늘 1번째', '통과', async () => { await seed((db) => setDoc(doc(db, 'users/alice'), { day: TODAY - 1, n: 30 }, { merge: true })); await newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }, { n: 1 }); });
await T('새 글', '하루 수를 속임(n 그대로)', '막힘', async () => { await seed((db) => setDoc(doc(db, 'users/alice'), { day: TODAY, n: 5 }, { merge: true })); await newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }, { n: 5 }); });
await T('새 글', '쓰기 정지', '막힘', async () => { await seed((db) => setDoc(doc(db, 'bans/alice'), { why: '시험' })); await newPost(as('alice'), 'alice', 'p1', { nick: '앨리스' }); });
await T('새 글', '남의 글 내용 고치기', '막힘', () => updateDoc(doc(as('alice'), `${C}/c1`), { text: '바꿈' }));
await T('새 글', '내 글 지우기', '통과', () => deleteDoc(doc(as('bob'), `${C}/c1`)));
await T('새 글', '남의 글 지우기', '막힘', () => deleteDoc(doc(as('alice'), `${C}/c1`)));
await T('새 글', '운영자가 지우기', '통과', () => deleteDoc(doc(as(OWNER), `${C}/c1`)));
await T('새 글', '운영자 가리기', '통과', () => updateDoc(doc(as(OWNER), `${C}/c1`), { hidden: true }));
await T('새 글', '회원이 가리기', '막힘', () => updateDoc(doc(as('alice'), `${C}/c1`), { hidden: true }));
await T('새 글', '로그인 전 읽기', '통과', () => getDocs(query(collectionGroup(guest(), 'comments'), where('uid', '==', 'bob'))));

// ── 답글 ─────────────────────────────────────────────────────
await T('답글', '답글 + 답글 수 +1', '통과', () => newReply(as('bob'), 'bob', 'r2', '밥'));
await T('답글', '답글 수를 안 올림', '막힘', () => newReply(as('bob'), 'bob', 'r2', '밥', { bump: false }));
await T('답글', '답글 없이 답글 수만 +1', '막힘', () => updateDoc(doc(as('bob'), `${C}/c1`), { replies: increment(1) }));
await T('답글', '답글 수 +2', '막힘', () => { const db = as('bob'); const b = writeBatch(db); b.set(doc(db, `${C}/c1/replies/r2`), { uid: 'bob', nick: '밥', text: 'x', created: serverTimestamp(), up: 0, down: 0 }); b.update(doc(db, `${C}/c1`), { replies: increment(2) }); b.set(doc(db, 'users/bob'), { last: serverTimestamp(), lastC: 'r2', day: TODAY, n: 1 }, { merge: true }); return b.commit(); });
await T('답글', '없는 글에 답글', '막힘', () => { const db = as('bob'); const b = writeBatch(db); b.set(doc(db, `${C}/none/replies/r2`), { uid: 'bob', nick: '밥', text: 'x', created: serverTimestamp(), up: 0, down: 0 }); b.set(doc(db, 'users/bob'), { last: serverTimestamp(), lastC: 'r2', day: TODAY, n: 1 }, { merge: true }); return b.commit(); });
await T('답글', '답글에 텔레그램', '막힘', () => { const db = as('bob'); const b = writeBatch(db); b.set(doc(db, `${C}/c1/replies/r2`), { uid: 'bob', nick: '밥', text: 't.me/x', created: serverTimestamp(), up: 0, down: 0 }); b.update(doc(db, `${C}/c1`), { replies: increment(1) }); b.set(doc(db, 'users/bob'), { last: serverTimestamp(), lastC: 'r2', day: TODAY, n: 1 }, { merge: true }); return b.commit(); });
await T('답글', '내 답글 지우기 + 답글 수 −1', '통과', () => { const db = as('alice'); const b = writeBatch(db); b.delete(doc(db, `${C}/c1/replies/r1`)); b.update(doc(db, `${C}/c1`), { replies: increment(-1) }); b.set(doc(db, 'users/alice'), { lastD: 'r1' }, { merge: true }); return b.commit(); });
await T('답글', '안 지우고 답글 수만 −1', '막힘', () => { const db = as('alice'); const b = writeBatch(db); b.update(doc(db, `${C}/c1`), { replies: increment(-1) }); b.set(doc(db, 'users/alice'), { lastD: 'r1' }, { merge: true }); return b.commit(); });

// ── 좋아요 · 싫어요 ───────────────────────────────────────────
const P = `${C}/c1`, R = `${C}/c1/replies/r1`;
await T('반응', '좋아요', '통과', () => react(as('alice'), 'alice', P, 'up', { up: 1 }));
await T('반응', '답글에 싫어요', '통과', () => react(as('bob'), 'bob', R, 'down', { down: 1 }));
await T('반응', '숫자 칸을 안 올림', '막힘', () => react(as('alice'), 'alice', P, 'up'));
await T('반응', '좋아요 +5', '막힘', () => react(as('alice'), 'alice', P, 'up', { up: 5 }));
await T('반응', '표 없이 숫자 칸만 +1', '막힘', () => updateDoc(doc(as('alice'), P), { up: increment(1) }));
await T('반응', '같은 좋아요 두 번', '막힘', async () => { await seed(async (db) => { await setDoc(doc(db, `${P}/reacts/alice`), { v: 'up', created: HOUR_AGO }); await updateDoc(doc(db, P), { up: 1 }); }); await react(as('alice'), 'alice', P, 'up', { up: 1, rn: 2 }); });
await T('반응', '좋아요 → 싫어요로 바꾸기', '통과', async () => { await seed(async (db) => { await setDoc(doc(db, `${P}/reacts/alice`), { v: 'up', created: HOUR_AGO }); await updateDoc(doc(db, P), { up: 1 }); await setDoc(doc(db, 'users/alice'), { rday: TODAY, rn: 1 }, { merge: true }); }); await react(as('alice'), 'alice', P, 'down', { up: -1, down: 1, rn: 2 }); });
await T('반응', '좋아요 취소', '통과', async () => { await seed(async (db) => { await setDoc(doc(db, `${P}/reacts/alice`), { v: 'up', created: HOUR_AGO }); await updateDoc(doc(db, P), { up: 1 }); }); await react(as('alice'), 'alice', P, 'up', { mode: 'del', up: -1 }); });
await T('반응', '취소하며 숫자 칸 그대로', '막힘', async () => { await seed(async (db) => { await setDoc(doc(db, `${P}/reacts/alice`), { v: 'up', created: HOUR_AGO }); await updateDoc(doc(db, P), { up: 1 }); }); await deleteDoc(doc(as('alice'), `${P}/reacts/alice`)); });
await T('반응', '오늘 31번째', '막힘', async () => { await seed((db) => setDoc(doc(db, 'users/alice'), { rday: TODAY, rn: 30 }, { merge: true })); await react(as('alice'), 'alice', P, 'up', { up: 1, rn: 31 }); });
await T('반응', '남의 표 읽기', '막힘', async () => { await seed((db) => setDoc(doc(db, `${P}/reacts/bob`), { v: 'up', created: HOUR_AGO })); await getDoc(doc(as('alice'), `${P}/reacts/bob`)); });
await T('반응', '내 표 읽기', '통과', async () => { await seed((db) => setDoc(doc(db, `${P}/reacts/alice`), { v: 'up', created: HOUR_AGO })); await getDoc(doc(as('alice'), `${P}/reacts/alice`)); });

// ── 신고 ─────────────────────────────────────────────────────
await T('신고', '신고하기', '통과', () => setDoc(doc(as('alice'), `${P}/reports/alice`), { why: 'ad', created: serverTimestamp() }));
await T('신고', '답글 신고', '통과', () => setDoc(doc(as('bob'), `${R}/reports/bob`), { why: 'abuse', created: serverTimestamp() }));
await T('신고', '한 사람이 두 번', '막힘', async () => { await seed((db) => setDoc(doc(db, `${P}/reports/alice`), { why: 'ad', created: HOUR_AGO })); await setDoc(doc(as('alice'), `${P}/reports/alice`), { why: 'etc', created: serverTimestamp() }); });
await T('신고', '남의 이름으로 신고', '막힘', () => setDoc(doc(as('alice'), `${P}/reports/bob`), { why: 'ad', created: serverTimestamp() }));
await T('신고', '없는 이유', '막힘', () => setDoc(doc(as('alice'), `${P}/reports/alice`), { why: 'hate', created: serverTimestamp() }));
await T('신고', '신고 목록 읽기', '막힘', () => getDoc(doc(as('alice'), `${P}/reports/alice`)));

await env.cleanup();

// 결과 표
let fail = 0, last = '';
for (const r of rows) {
  if (r.group !== last) { console.log(`\n[${r.group}]`); last = r.group; }
  if (!r.ok) fail++;
  console.log(`${r.ok ? ' ok ' : 'FAIL'}  ${r.name.padEnd(24)}  기대 ${r.expect} · 실제 ${r.got}`);
}
console.log(`\n${rows.length}건 중 ${rows.length - fail}건 맞음 · ${fail}건 다름`);
process.exit(fail ? 1 : 0);
