// GitHub Actions 예약 실행 대리 트리거 (Cloudflare Worker Cron Trigger).
//
// GitHub의 schedule 이벤트는 보장되지 않는다 — 부하가 높으면 몇 시간 늦거나 통째로 빠진다
// (2026-10-13: 데일리·트럼프·NVDA 예약 실행이 전부 오지 않았다). 이 Worker가
// workflow_dispatch(scheduled=true)를 걸고, 워크플로는 그 실행을 스케줄과 똑같이 취급한다.
// GitHub cron도 그대로 둔다. 둘 다 도는 날은 뒤에 도는 쪽이 "오늘 글이 이미 있음"을 보고 건너뛴다.
//
// 시각은 뉴욕 현지 시각(미국장 마감 16:00 기준)으로 정한다 (2026-10-16). UTC로 고정하면 미국 서머타임이
// 끝나는 날(11월 첫 일요일) 데일리가 장 마감 순간에 돌아 종가가 확정되기 전 데이터로 쓴다.
// cron은 서머타임(EDT)·표준시(EST) 양쪽 후보 시각에 모두 깨어나고, 뉴욕 시각이 JOBS 키와 같을 때만 건다.
//   KST 환산: EDT(3월 둘째 일요일~11월 첫 일요일) = 뉴욕 + 13시간, EST = 뉴욕 + 14시간.

const REPO = "red6keep-droid/alphascope";
const REF = "main";

function nyTime(d) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour12: false,
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
    })
      .formatToParts(d)
      .map((x) => [x.type, x.value]),
  );
  return { hm: `${p.hour}:${p.minute}`, weekday: p.weekday };
}

const WEEKDAY = (ny) => !["Sat", "Sun"].includes(ny.weekday); // 뉴욕 월~금 = 미국장이 열린 날

function kstTime(d) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Seoul", hour12: false, weekday: "short", hour: "2-digit", minute: "2-digit" })
      .formatToParts(d).map((x) => [x.type, x.value]),
  );
  return { hm: `${p.hour}:${p.minute}`, weekday: p.weekday };
}

// 한국 시각 표 (2026-10-22): 한국 방송 시각에 묶인 작업 — 서머타임을 따르면 안 된다.
// 미디어 데일리: 08:00 1차 발행(밤사이 클립 + 당잠사) · 10:15 같은 글 갱신(Mad Money · 증시각도기). 평일만.
const KST_JOBS = {
  // 홈 주요 뉴스 — 하루 두 번 (2026-10-25 사용자): 미국 장 마감 뒤 아침 · 개장 전 저녁. 매일. 분은 :45 (gh-pages push 겹침 피하기)
  "06:45": [{ workflow: "news.yml", inputs: null }],
  "21:45": [{ workflow: "news.yml", inputs: null }],
  "08:00": [{ workflow: "media-daily.yml", inputs: { scheduled: "true", phase: "1" }, when: WEEKDAY }],
  "10:15": [{ workflow: "media-daily.yml", inputs: { scheduled: "true", phase: "2" }, when: WEEKDAY }],
  // 한국 종목 페이지 · 한국 증시 리포트 (2026-10-27) — 한국장 마감 15:30 뒤. GitHub cron(07:10 UTC)이 10-26 에 7시간 늦었다.
  // 둘 다 도는 날은 concurrency 로 줄 서고, 뒤 실행은 페이지 해시 같음 · 리포트 이미 게시됨으로 쓰지 않는다. 휴장일은 fresh.txt 가 막는다.
  "16:10": [{ workflow: "kr-stocks.yml", when: WEEKDAY }],
  "13:00": [{ workflow: "nvda-report.yml" }], // 낮 갱신 — 종목 페이지만 다시 그린다 (check.mode=refresh, 2026-11-04 P290). GitHub cron 04:00 UTC 는 예비
};

const JOBS = {
  // 데일리 리포트 (뉴욕 월~금) — 장 마감 1시간 뒤. KST 06:00 (EDT) / 07:00 (EST).
  "17:00": [{ workflow: "test-daily-report.yml", when: WEEKDAY }],
  // 트럼프 트렌드(17:15)는 2026-11-04 중단 — 발언 → 주가 반응이 3개월 동안 확인되지 않음. 워크플로는 수동 실행만 남김.
  // NVDA 리포트(매일). KST 06:30 / 07:30. (trump_bridge 는 trump-state 가 멈춘 뒤 0건으로 조용히 지나간다)
  "17:30": [{ workflow: "nvda-report.yml" }],
  // 인물 발언 레이더(매일) — report-state 를 읽으므로 데일리 뒤. KST 07:00 / 08:00 (2026-10-22). 트럼프 게시물은 스스로 분류한다 (11-04).
  // 같은 날 글이 있으면 갱신만 하므로 두 번 돌아도 겹치지 않는다.
  "18:00": [{ workflow: "people-radar.yml" }],
  // 데일리 재시도(이미 게시됐으면 스스로 건너뜀). KST 07:30 / 08:30.
  "18:30": [{ workflow: "test-daily-report.yml", when: WEEKDAY }],
  // 홈 시세(update.yml) — 블로그는 종가 기준(doc/기획/블로그-목적과-방향.md 5절, 2026-10-22). 장 마감 20분 뒤 확정 1회 +
  // 장중 1시간 간격 (뉴욕 월~금). 15분 수집(하루 96회, 야후 ~3,400호출)은 가격 알림 성격이라 뺐다. scheduled 입력이 없어 inputs 없이 건다.
  "10:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY, watch: false }],
  "11:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY, watch: false }],
  "12:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY, watch: false }],
  "13:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY, watch: false }],
  "14:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY, watch: false }],
  "15:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY, watch: false }],
  "16:20": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
};

// 간격 수집 (2026-10-22 사용자) — GitHub cron 만으로는 2시간 뉴스가 하루 12회 중 4회만 돌았다. UTC 분 · 시로 판단한다.
// 분을 리포트 · 시세 시각(:00 · :15 · :20 · :30)에서 비켜 둔다 — 모두 gh-pages 에 push 해서, 같은 분에 돌면 한쪽 push 가 거부된다.
const REPEAT = [
  // 뉴스 2시간마다는 2026-10-25 KST_JOBS 하루 두 번으로 옮겼다 (피드가 며칠에 몇 개라 33번 연속 새 기사 0)
];

// 알림 (2026-11-12 사용자: "실패됐을 때 나한테 알림이 와야") — 11-12 GitHub 토큰 만료로 13:00 · 16:10 · 21:45 실행이
// 소리 없이 빠졌다(Worker 는 오류를 대시보드에만 남겼다). 두 겹:
//   ① 걸기 실패 → 그 자리에서 Slack
//   ② 감시: 건 지 60분 뒤 그 워크플로 실행이 있었나 · 성공했나 → 없거나 실패면 Slack (GitHub cron 예비가 대신 돌았으면 통과)
// 문구는 Slack 알림 규칙(한국어 이름 · 한국어 원인 한 마디 · 영어 원문 X · 실행 링크). 이름은 experiments/alert_ko.py NAMES 와 같게.
const NAMES = {
  "test-daily-report.yml": "미국 데일리 리포트",
  "nvda-report.yml": "엔비디아 · 시총 TOP 10 페이지",
  "kr-stocks.yml": "한국 종목 · 한국 증시 리포트",
  "people-radar.yml": "주요 인물 발언",
  "media-daily.yml": "방송 이슈 (미디어 데일리)",
  "news.yml": "뉴스 갱신 (하루 2회)",
  "update.yml": "홈 시세 갱신",
};
const WATCH_AFTER_MIN = 60;
const name = (wf) => NAMES[wf] || wf;

function reason(status) {
  if (status === 401) return "GitHub 토큰 만료 또는 잘못됨 — Worker 의 GITHUB_TOKEN 을 새로 넣어야 합니다";
  if (status === 403) return "GitHub 권한 또는 요청 한도 문제";
  if (status === 404) return "main 에서 워크플로를 찾지 못함";
  if (status === 422) return "실행 입력값이 워크플로와 맞지 않음";
  return `GitHub 응답 ${status}`;
}

function gh(path, token, init = {}) {
  return fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "alphascope-cron-trigger",
      ...(init.headers || {}),
    },
  });
}

async function slack(env, text) {
  if (!env.SLACK_WEBHOOK_URL) { console.log(`[알림 꺼짐] ${text}`); return; }
  try {
    await fetch(env.SLACK_WEBHOOK_URL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, unfurl_links: false }) });
  } catch (e) {
    console.log(`Slack 보내기 실패: ${e}`);
  }
}

async function dispatch(workflow, token, inputs = { scheduled: "true" }) {
  const res = await gh(`/actions/workflows/${workflow}/dispatches`, token, {
    method: "POST",
    body: JSON.stringify(inputs ? { ref: REF, inputs } : { ref: REF }),
  });
  if (res.status !== 204) {
    const err = new Error(`${workflow}: HTTP ${res.status} ${await res.text()}`);
    err.workflow = workflow;
    err.status = res.status;
    throw err;
  }
  console.log(`dispatched ${workflow}`);
}

function dueAt(at) {
  const ny = nyTime(at);
  const kst = kstTime(at);
  const utc = { h: at.getUTCHours(), m: at.getUTCMinutes() };
  return [
    ...(JOBS[ny.hm] || []).filter((j) => !j.when || j.when(ny)),
    ...(KST_JOBS[kst.hm] || []).filter((j) => !j.when || j.when(kst)),
    ...REPEAT.filter((j) => j.when(utc)),
  ];
}

// 감시 — at 에 걸었어야 할 실행이 그 뒤로 있었나. 돌고 있으면 통과(긴 실행), 하나라도 성공이면 통과.
async function watch(at, env) {
  const jobs = dueAt(at).filter((j) => j.watch !== false);
  const since = new Date(at.getTime() - 5 * 60 * 1000).toISOString().slice(0, 19) + "Z";
  const lines = [];
  for (const wf of [...new Set(jobs.map((j) => j.workflow))]) {
    const res = await gh(`/actions/workflows/${wf}/runs?created=%3E%3D${since}&per_page=20`, env.GITHUB_TOKEN);
    if (res.status !== 200) { lines.push(`• ${name(wf)} — 확인 못 함: ${reason(res.status)}`); continue; }
    const runs = ((await res.json()).workflow_runs || []).filter((r) => r.event === "workflow_dispatch" || r.event === "schedule");
    if (!runs.length) { lines.push(`• ${name(wf)} — ${WATCH_AFTER_MIN}분이 지나도 실행이 없습니다`); continue; }
    if (runs.some((r) => r.status !== "completed" || r.conclusion === "success")) continue;
    lines.push(`• ${name(wf)} — 실패했습니다\n🔗 ${runs[0].html_url}`);
  }
  if (lines.length) {
    const t = kstTime(at).hm;
    await slack(env, `🚨 정기 실행 확인 (${t} 예정분)\n${lines.join("\n")}`);
  }
}

// 토큰 만료 미리 알림 — 하루 한 번(KST 09:00) 남은 날이 7일 이하면. fine-grained 토큰은 응답 머리에 만료 시각이 온다.
async function tokenCheck(env) {
  const res = await gh("", env.GITHUB_TOKEN);
  if (res.status === 401) { await slack(env, `🚨 정기 실행 Worker\n• ${reason(401)}`); return; }
  const exp = res.headers.get("github-authentication-token-expiration");
  if (!exp) return;
  const days = Math.floor((Date.parse(exp.replace(" UTC", "Z").replace(" ", "T")) - Date.now()) / 86400000);
  if (days <= 7) await slack(env, `⚠️ 정기 실행 Worker\n• GitHub 토큰이 ${days}일 뒤 만료됩니다 — 새로 발급해 GITHUB_TOKEN 에 넣어 주세요`);
}

export default {
  async scheduled(event, env, ctx) {
    const at = new Date(event.scheduledTime);
    const due = dueAt(at);
    const watchAt = new Date(at.getTime() - WATCH_AFTER_MIN * 60 * 1000);
    ctx.waitUntil(watch(watchAt, env).catch((e) => console.log(`감시 오류: ${e}`)));
    if (kstTime(at).hm === "09:00") ctx.waitUntil(tokenCheck(env).catch((e) => console.log(`토큰 확인 오류: ${e}`)));
    if (!due.length) return; // 할 일 없는 회차

    // 하나가 실패해도 나머지는 건다. 실패는 Slack 으로 알리고, 마지막에 던져 Cloudflare 대시보드에도 남긴다.
    const results = await Promise.allSettled(
      due.map((j) => dispatch(j.workflow, env.GITHUB_TOKEN, j.inputs).catch((e) => { e.workflow = e.workflow || j.workflow; throw e; })),
    );
    const failed = results.filter((r) => r.status === "rejected").map((r) => r.reason);
    if (failed.length) {
      const t = kstTime(at).hm;
      await slack(env, `🚨 정기 실행 걸기 실패 (${t})\n${failed.map((e) => `• ${name(e.workflow)} — ${e.status ? reason(e.status) : "연결 실패"}`).join("\n")}`);
      throw new Error(failed.map((e) => e.message).join("\n"));
    }
  },
};
