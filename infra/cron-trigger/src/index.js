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
};

// 고빈도 수집 (2026-10-22 사용자) — GitHub cron 만으로는 하루 15분 시세 96회 중 7회, 2시간 뉴스 12회 중 4회만 돌았다.
// 시각이 아니라 간격이라 UTC 분 · 시로 판단한다. 두 워크플로는 scheduled 입력이 없다 → inputs 없이 건다.
const REPEAT = [
  { workflow: "update.yml", inputs: null, when: (u) => u.m % 15 === 0 },                 // 시세 15분마다
  { workflow: "news.yml", inputs: null, when: (u) => u.m === 0 && u.h % 2 === 0 },        // 뉴스 2시간마다 (UTC 짝수 시)
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
    const utc = { h: at.getUTCHours(), m: at.getUTCMinutes() };
    const due = [
      ...(JOBS[ny.hm] || []).filter((j) => !j.when || j.when(ny)),
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
