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
  "08:00": [{ workflow: "media-daily.yml", inputs: { scheduled: "true", phase: "1" }, when: WEEKDAY }],
  "10:15": [{ workflow: "media-daily.yml", inputs: { scheduled: "true", phase: "2" }, when: WEEKDAY }],
};

const JOBS = {
  // 데일리 리포트 (뉴욕 월~금) — 장 마감 1시간 뒤. KST 06:00 (EDT) / 07:00 (EST).
  "17:00": [{ workflow: "test-daily-report.yml", when: WEEKDAY }],
  // 트럼프 트렌드(매일). KST 06:15 / 07:15.
  "17:15": [{ workflow: "trump-trend.yml" }],
  // NVDA 리포트(매일) — 트럼프가 trump-state에 올린 결과를 읽으므로 15분 뒤. KST 06:30 / 07:30.
  "17:30": [{ workflow: "nvda-report.yml" }],
  // 인물 발언 레이더(매일) — trump-state · report-state 를 읽으므로 데일리 · 트럼프 뒤. KST 07:00 / 08:00 (2026-10-22).
  // 같은 날 글이 있으면 갱신만 하므로 두 번 돌아도 겹치지 않는다.
  "18:00": [{ workflow: "people-radar.yml" }],
  // 데일리 재시도(이미 게시됐으면 스스로 건너뜀). KST 07:30 / 08:30.
  "18:30": [{ workflow: "test-daily-report.yml", when: WEEKDAY }],
  // 홈 시세(update.yml) — 블로그는 종가 기준(doc/기획/블로그-목적과-방향.md 5절, 2026-10-22). 장 마감 20분 뒤 확정 1회 +
  // 장중 1시간 간격 (뉴욕 월~금). 15분 수집(하루 96회, 야후 ~3,400호출)은 가격 알림 성격이라 뺐다. scheduled 입력이 없어 inputs 없이 건다.
  "10:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
  "11:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
  "12:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
  "13:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
  "14:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
  "15:00": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
  "16:20": [{ workflow: "update.yml", inputs: null, when: WEEKDAY }],
};

// 간격 수집 (2026-10-22 사용자) — GitHub cron 만으로는 2시간 뉴스가 하루 12회 중 4회만 돌았다. UTC 분 · 시로 판단한다.
// 분을 리포트 · 시세 시각(:00 · :15 · :20 · :30)에서 비켜 둔다 — 모두 gh-pages 에 push 해서, 같은 분에 돌면 한쪽 push 가 거부된다.
const REPEAT = [
  { workflow: "news.yml", inputs: null, when: (u) => u.m === 45 && u.h % 2 === 0 },         // 뉴스 2시간마다 (UTC 짝수 시 :45)
];

async function dispatch(workflow, token, inputs = { scheduled: "true" }) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "alphascope-cron-trigger",
      },
      body: JSON.stringify(inputs ? { ref: REF, inputs } : { ref: REF }),
    },
  );
  if (res.status !== 204) {
    throw new Error(`${workflow}: HTTP ${res.status} ${await res.text()}`);
  }
  console.log(`dispatched ${workflow}`);
}

export default {
  async scheduled(event, env, ctx) {
    const at = new Date(event.scheduledTime);
    const ny = nyTime(at);
    const kst = kstTime(at);
    const utc = { h: at.getUTCHours(), m: at.getUTCMinutes() };
    const due = [
      ...(JOBS[ny.hm] || []).filter((j) => !j.when || j.when(ny)),
      ...(KST_JOBS[kst.hm] || []).filter((j) => !j.when || j.when(kst)),
      ...REPEAT.filter((j) => j.when(utc)),
    ];
    if (!due.length) return; // 할 일 없는 회차

    // 하나가 실패해도 나머지는 건다. 실패는 마지막에 던져 Cloudflare 대시보드에 남긴다.
    const results = await Promise.allSettled(
      due.map((j) => dispatch(j.workflow, env.GITHUB_TOKEN, j.inputs)),
    );
    const failed = results.filter((r) => r.status === "rejected").map((r) => r.reason.message);
    if (failed.length) throw new Error(failed.join("\n"));
  },
};
