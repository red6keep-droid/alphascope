// GitHub Actions 예약 실행 대리 트리거 (Cloudflare Worker Cron Trigger).
//
// GitHub의 schedule 이벤트는 보장되지 않는다 — 부하가 높으면 몇 시간 늦거나 통째로 빠진다
// (2026-10-13: 데일리·트럼프·NVDA 예약 실행이 전부 오지 않았다). 같은 시각에 이 Worker가
// workflow_dispatch(scheduled=true)를 걸고, 워크플로는 그 실행을 스케줄과 똑같이 취급한다.
// GitHub cron도 그대로 둔다. 둘 다 도는 날은 뒤에 도는 쪽이 "오늘 글이 이미 있음"을 보고 건너뛴다.
//
// 시각은 wrangler.toml의 crons와 아래 JOBS 키가 정확히 같아야 한다 (event.cron이 그 문자열로 온다).

const REPO = "red6keep-droid/alphascope";
const REF = "main";

const WEEKDAY = (d) => d.getUTCDay() >= 1 && d.getUTCDay() <= 5; // UTC 월~금 = GitHub cron '1-5'

const JOBS = {
  // 21:00 UTC = 06:00 KST. 데일리 리포트 (월~금 UTC).
  "0 21 * * *": [{ workflow: "test-daily-report.yml", when: WEEKDAY }],
  // 22:30 UTC = 07:30 KST. 트럼프 트렌드(매일) + 데일리 재시도(월~금 UTC, 이미 게시됐으면 스스로 건너뜀).
  "30 22 * * *": [
    { workflow: "trump-trend.yml" },
    { workflow: "test-daily-report.yml", when: WEEKDAY },
  ],
  // 22:45 UTC = 07:45 KST. NVDA 리포트(매일) — 트럼프가 trump-state에 올린 결과를 읽으므로 15분 뒤.
  "45 22 * * *": [{ workflow: "nvda-report.yml" }],
};

async function dispatch(workflow, token) {
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
      body: JSON.stringify({ ref: REF, inputs: { scheduled: "true" } }),
    },
  );
  if (res.status !== 204) {
    throw new Error(`${workflow}: HTTP ${res.status} ${await res.text()}`);
  }
  console.log(`dispatched ${workflow}`);
}

export default {
  async scheduled(event, env, ctx) {
    const jobs = JOBS[event.cron];
    if (!jobs) throw new Error(`알 수 없는 cron: ${event.cron}`);
    const now = new Date(event.scheduledTime);
    const due = jobs.filter((j) => !j.when || j.when(now));

    // 하나가 실패해도 나머지는 건다. 실패는 마지막에 던져 Cloudflare 대시보드에 남긴다.
    const results = await Promise.allSettled(due.map((j) => dispatch(j.workflow, env.GITHUB_TOKEN)));
    const failed = results.filter((r) => r.status === "rejected").map((r) => r.reason.message);
    if (failed.length) throw new Error(failed.join("\n"));
  },
};
