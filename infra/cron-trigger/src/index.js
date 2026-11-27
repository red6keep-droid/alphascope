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
const KST_TUE_SAT = (k) => !["Sun", "Mon"].includes(k.weekday); // 한국 화~토 아침 = 미국 월~금 장 마감 뒤

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
  // 홈 주요 뉴스 — 하루 두 번: 미국 장 마감 뒤 아침 · 개장 전 저녁. 매일. 분은 :45 (gh-pages push 겹침 피하기)
  "06:45": [{ workflow: "news.yml", inputs: null }],
  "21:45": [{ workflow: "news.yml", inputs: null }],
  "08:00": [{ workflow: "media-daily.yml", inputs: { scheduled: "true", phase: "1" }, when: WEEKDAY }],
  "10:15": [{ workflow: "media-daily.yml", inputs: { scheduled: "true", phase: "2" }, when: WEEKDAY }],
  // 매드머니 기록 예비. 매드머니는 KST 09:30 ~ 10:30 게시 · 요약이 10:15 뒤로 밀리는 날(11-19 11:26)용.
  // 방송 기록만(AI 0 · 한국장 칸 X). 분은 Worker 가 깨는 분(:50) 가운데서. 새 회차를 기록하면 media-daily 가 people-radar mode=madmoney 를 건다. 화 ~ 토(미국 월 ~ 금 방송 다음 날)
  "11:50": [{ workflow: "media-daily.yml", inputs: { scheduled: "true", phase: "2", records_only: "true" }, when: KST_TUE_SAT }],
  // 한국 종목 페이지 · 한국 증시 리포트 (2026-10-27) — 한국장 마감 15:30 뒤. GitHub cron(07:10 UTC)이 10-26 에 7시간 늦었다.
  // 둘 다 도는 날은 concurrency 로 줄 서고, 뒤 실행은 페이지 해시 같음 · 리포트 이미 게시됨으로 쓰지 않는다. 휴장일은 fresh.txt 가 막는다.
  // 15:50: 마감 15:30 + 야후 지연 시세 20분. 워크플로 맨 앞 wait_close.py 가 종가 확정을 보고 늦으면 16:10 까지 기다린다
  // retry: 100분 뒤(17:30) 본 잡이 실패 · 취소면 한 번 자동으로 다시 건다
  "15:50": [{ workflow: "kr-stocks.yml", when: WEEKDAY, retry: { job: "kr-stocks", inputs: { scheduled: "true" } } }],
  // 간단 종목(853종목) — 미국 = 장 마감 뒤 아침(뉴스 06:40 → 화면 08:20, 정식 07:30 실행이 07:56~59 에 끝난 뒤), 한국 = 장 마감 뒤 17:40.
  // GitHub cron 도 그대로 — 둘 다 도는 날은 워크플로 check 잡이 '최근 6시간 안 같은 실행 성공' 을 보고 뒤 실행을 건너뛴다(뉴스 AI 두 번 X).
  // 미국 종목 뉴스 먼저 분류 — 장 마감 뒤 엔비디아 실행이 남은 기사만 분류하게. 화~토(= 미국 월~금). 늦게 오면 워크플로가 건너뜀
  // 한국 DART 새벽 받기 · 보고서 매출 · 수주 읽기 — GitHub 예약(03:25)이 11-21~24 나흘 내리 08:29~12:59 에 와
  // 워크플로 `Too late?`(06시 뒤 건너뜀)에 걸려 아무것도 못 받았다. Worker 가 걸면 workflow_dispatch 라 그 검사를 지난다. GitHub 예약은 예비로 둔다.
  // 입력 없는 워크플로(inputs: null) · 감시 알림 끔. 같은 줄(concurrency quick-data)의 간단 종목은 08:20 · 16:40 이라 안 겹침
  "03:20": [{ workflow: "quick-dart.yml", inputs: null, watch: false }],
  "04:30": [{ workflow: "radar-news-early.yml", inputs: { scheduled: "true" }, when: KST_TUE_SAT }],
  "06:20": [{ workflow: "quick-news.yml", when: KST_TUE_SAT }],   // 옛 06:40
  "08:20": [{ workflow: "quick-data.yml", inputs: { scheduled: "true", market: "us" }, when: KST_TUE_SAT }],
  "16:40": [{ workflow: "quick-data.yml", inputs: { scheduled: "true", market: "kr" }, when: WEEKDAY }],   // 옛 17:40 — 15:50 한국 종목 뒤 이어 붙이기의 예비
  "13:00": [{ workflow: "nvda-report.yml" }],
  // 집 IP 받기(미래에셋 TIGER 구성 · 버리 RSS, 집 공유기 VPN) — 유튜브 수집(News-sub)이 VPN 을 안 쓰는 12~17시.
  // 공유기 L2TP 는 동시 접속을 못 버텨, 워크플로가 News-sub 실행이 도는 중이면 기다린다. 매일.
  // 시황 해설 발행 — 수집기가 08:10 · 20:30 에 쓰고 08:30 · 20:40 마감, 블로그는 08:40 · 21:00 에 ready 글만 공개 발행. 매일
  // (수집기가 재료 없는 날은 skip 문서 → 발행기가 조용히 끝). 배너를 gh-pages 에 올린다 — :40 · :00 에 다른 gh-pages 푸시 실행 없음.
  "08:40": [{ workflow: "commentary.yml", inputs: { scheduled: "true", slot: "am" } }],
  "21:00": [{ workflow: "commentary.yml", inputs: { scheduled: "true", slot: "pm" } }],
  // 저녁 편 1차: 수집기가 16:40 에 1차, 20:30 에 rev 2. 블로그는 17:00 에 1차를 내고
  // 21:00 실행이 rev 가 올랐으면 같은 주소에 고쳐 쓴다(publish_commentary.py). 한국장 날만. :00 에 다른 gh-pages 푸시 없음(한국 종목 16:28 끝 · 간단 17:40)
  "17:00": [{ workflow: "commentary.yml", inputs: { scheduled: "true", slot: "pm" }, when: WEEKDAY }],
  "14:30": [{ workflow: "home-ip.yml" }], // 낮 갱신 — 종목 페이지만 다시 그린다 (check.mode=refresh, 2026-11-04 P290). GitHub cron 04:00 UTC 는 예비
  // 한국 기사 공용 저장소 — 뉴스 수집기 정기 실행 07:00 · 16:30 이 facts 를 쓴 뒤(07:46 · 17:1x 쯤). 매일.
  // gh-pages kr-facts.json 푸시 하루 2회 + 평일 장중 2회(아래, + 상태 저장소) — 09:20 · 18:20 에 다른 gh-pages 푸시 없음. 분 :20 은 Worker 가 깨는 분.
  "09:20": [{ workflow: "kr-facts.yml", inputs: { scheduled: "true" } }],
  "18:20": [{ workflow: "kr-facts.yml", inputs: { scheduled: "true" } }],
  // 장중 사실 — 뉴스 수집기 평일 가벼운 회차 11:40 · 14:40 에 사실 뽑기(보도 2곳 이상 사건 · 본문 20건, 수집기 31절)가 끝난 뒤.
  // 15:20 = 15:50 한국 증시 리포트 · 한국 종목 전에. :20 에 다른 gh-pages 푸시 없음(12:20 · 15:20 KST 표 · 미국 표 모두 빈 자리)
  "12:20": [{ workflow: "kr-facts.yml", inputs: { scheduled: "true" }, when: WEEKDAY }],
  "15:20": [{ workflow: "kr-facts.yml", inputs: { scheduled: "true" }, when: WEEKDAY }],
  // Newfact 뉴스 발행 — 수집기 글을 블로그 공개 글로(새 글 사이 10분) + 홈 카드 자료 gh-pages news-posts.json. 매일.
  // 수집기 07:00 · 16:30 실행이 글을 쓴 뒤(08시 · 17시 무렵). 분 :50 — 09:20 · 18:20 공용 저장소 gh-pages 푸시와 비킨다(:50 은 Worker 가 깨는 분, 다른 gh-pages 푸시 없음).
  "09:50": [{ workflow: "news-posts.yml", inputs: { scheduled: "true", stage: "publish", draft: "false" } }],
  "13:50": [{ workflow: "news-posts.yml", inputs: { scheduled: "true", stage: "publish", draft: "false" } }],
  "18:50": [{ workflow: "news-posts.yml", inputs: { scheduled: "true", stage: "publish", draft: "false" } }],
  "22:50": [{ workflow: "news-posts.yml", inputs: { scheduled: "true", stage: "publish", draft: "false" } }],
  // 아침 글 기준일 고치기 — 한국 장 마감(15:30) 뒤 그날 종가로 관련 종목 표를 고쳐 씀(같은 주소 PUT, gh-pages 안 씀). 평일만(휴장 · 주말은 기준일이 안 바뀌어 건드릴 글이 없다)
  "16:10": [{ workflow: "news-posts.yml", inputs: { scheduled: "true", stage: "refresh", draft: "false" }, when: WEEKDAY }],
  // 간단 종목 새 전용 페이지 — GitHub 예약(23:40)이 11-25 · 11-26 다음 날 08시대에 와
  // 워크플로 시간 창(23~06시)에 걸려 이틀 동안 새 페이지 0. Worker 가 걸면 제시각. 입력 없는 워크플로(inputs: null), GitHub 예약은 예비.
  // 하루 25쪽 상한 · 같은 날 두 번 돌아도 cache/shells_new_day.json 합계라 더 만들지 않는다. 매일.
  "23:40": [{ workflow: "quick-shells-new.yml", inputs: null }],
};

const JOBS = {
  // 데일리 리포트 (뉴욕 월~금) — 장 마감 1시간 뒤. KST 06:00 (EDT) / 07:00 (EST).
  // 미국 실행 한 줄로: 리포트 16:40 NY(장 마감 40분 뒤 — 장 마감 뒤 실적 발표가 16:05~16:30 에 몰림) → 엔비디아 · 미국 종목(이어 붙이기)
  // → 인물 발언 · 간단 종목(이어 붙이기). 아래 17:00 · 17:30 · 18:00 · 18:30 은 예비 — 이미 했으면 각 워크플로가 건너뛴다
  "16:40": [{ workflow: "test-daily-report.yml", when: WEEKDAY }],
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

// 간격 수집 — GitHub cron 만으로는 2시간 뉴스가 하루 12회 중 4회만 돌았다. UTC 분 · 시로 판단한다.
// 분을 리포트 · 시세 시각(:00 · :15 · :20 · :30)에서 비켜 둔다 — 모두 gh-pages 에 push 해서, 같은 분에 돌면 한쪽 push 가 거부된다.
const REPEAT = [
  // 뉴스 2시간마다는 2026-10-25 KST_JOBS 하루 두 번으로 옮겼다 (피드가 며칠에 몇 개라 33번 연속 새 기사 0)
  // 한국 간단 종목 뉴스 매체 시험(RSS 제목) — 2시간마다 UTC 짝수 시 :10. GitHub cron 이 24시간에 2번만 돌았다.
  // 시험 끝(11-21 KST) 뒤엔 걸지 않는다. gh-pages 에 안 써서 다른 실행과 push 겹침 없음.
  { workflow: "kr-rss-probe.yml", inputs: { scheduled: "true" }, when: (u) => u.m === 10 && u.h % 2 === 0 && u.day <= "2026-11-21" },
  // 운영 대시보드 · 발행 시간(/ontime) — 매시 :50 UTC. GitHub cron 이 11-22~24 이틀 동안 3번만 돌았다.
  // 입력 없는 워크플로(inputs: null). 감시 알림은 끈다 — 한 시간 늦어도 다음 시각에 다시 만들고, 매시 실패 알림은 소음. gh-pages 에 안 써서 push 겹침 없음.
  // GitHub cron(같은 :50)은 예비로 그대로 — 겹치면 워크플로 concurrency 가 앞 실행을 취소한다.
  { workflow: "ops-dashboard.yml", inputs: null, watch: false, when: (u) => u.m === 50 },
];

// 알림 — 11-12 GitHub 토큰 만료로 13:00 · 16:10 · 21:45 실행이
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
  "quick-news.yml": "간단 종목 뉴스",
  "quick-data.yml": "간단 종목 주가 (853종목)",
  "kr-rss-probe.yml": "한국 간단 종목 뉴스 매체 시험",
  "home-ip.yml": "집 IP 받기 (미래에셋 · 버리)",
  "commentary.yml": "증시 시황 발행 (아침 · 저녁)",
  "radar-news-early.yml": "미국 종목 뉴스 먼저 분류",
  "kr-facts.yml": "한국 기사 공용 저장소",
  "ops-dashboard.yml": "운영 대시보드 · 발행 시간",
  "quick-dart.yml": "한국 DART 새벽 받기",
  "news-posts.yml": "Newfact 뉴스 발행",
  "quick-shells-new.yml": "간단 종목 새 전용 페이지",
};
const WATCH_AFTER_MIN = 60;
const RETRY_AGAIN_MIN = 170;   // 한 번 더 본다(18:40) — 다시 건 실행도 실패했으면 알림, 100분 때 아직 돌다가 그 뒤 끊겼으면 그때 다시 건다
const RETRY_AFTER_MIN = 100;   // retry 가 붙은 일만 — 60분 감시는 도는 중이면 통과라 그 뒤 끊긴 실행을 여기서 잡는다. 100 = 종가 대기 20 + 본 잡 상한 65 + 여유 (15:50 → 17:30)
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
  const utc = { h: at.getUTCHours(), m: at.getUTCMinutes(), day: at.toISOString().slice(0, 10) };
  return [
    ...(JOBS[ny.hm] || []).filter((j) => !j.when || j.when(ny)),
    ...(KST_JOBS[kst.hm] || []).filter((j) => !j.when || j.when(kst)),
    ...REPEAT.filter((j) => j.when(utc)),
  ];
}

// 본 일을 한 실행인가 — 확인 잡(when · check)만 돌고 본 잡이 건너뛴 실행은 GitHub 에 `성공`으로 남는다(예비 중복 · 이어 붙이기가 이미 함 · 수능일 게이트).
// → 'ok'(본 잡 성공) · 'skipped'(확인 잡만) · 'unknown'(못 읽음 — 잘못 알리지 않게 통과로 본다)
const GUARD_JOBS = new Set(["when", "check", "gate"]);   // gate = 인물 발언 이어 붙이기 문 (2026-11-20)
async function realRun(r, env) {
  const jr = await gh(`/actions/runs/${r.id}/jobs?per_page=50`, env.GITHUB_TOKEN);
  if (jr.status !== 200) return "unknown";
  return ((await jr.json()).jobs || []).some((x) => !GUARD_JOBS.has(x.name) && x.conclusion === "success") ? "ok" : "skipped";
}

// 감시 — at 에 걸었어야 할 실행이 그 뒤로 있었나. 돌고 있으면 통과(긴 실행), 본 잡이 성공한 실행이 있으면 통과.
// 건너뛴 실행뿐이면 그 전 6시간 안에 같은 일을 한 실행(이어 붙이기 · 사람 실행 포함)이 있었나 본다
const LOOKBACK_H = 6;
async function watch(at, env) {
  const jobs = dueAt(at).filter((j) => j.watch !== false);
  const since = new Date(at.getTime() - 5 * 60 * 1000).toISOString().slice(0, 19) + "Z";
  const lines = [];
  for (const wf of [...new Set(jobs.map((j) => j.workflow))]) {
    const res = await gh(`/actions/workflows/${wf}/runs?created=%3E%3D${since}&per_page=20`, env.GITHUB_TOKEN);
    if (res.status !== 200) { lines.push(`• ${name(wf)} — 확인 못 함: ${reason(res.status)}`); continue; }
    const runs = ((await res.json()).workflow_runs || []).filter((r) => r.event === "workflow_dispatch" || r.event === "schedule");
    if (!runs.length) { lines.push(`• ${name(wf)} — ${WATCH_AFTER_MIN}분이 지나도 실행이 없습니다`); continue; }
    if (runs.some((r) => r.status !== "completed")) continue;
    const succ = runs.filter((r) => r.conclusion === "success").slice(0, 5);
    if (!succ.length) { lines.push(`• ${name(wf)} — 실패했습니다\n🔗 ${runs[0].html_url}`); continue; }
    let ok = false;
    for (const r of succ) { if ((await realRun(r, env)) !== "skipped") { ok = true; break; } }
    if (ok) continue;
    const from = new Date(at.getTime() - LOOKBACK_H * 3600 * 1000).toISOString().slice(0, 19) + "Z";
    const rb = await gh(`/actions/workflows/${wf}/runs?created=%3E%3D${from}&status=success&per_page=20`, env.GITHUB_TOKEN);
    if (rb.status === 200) {
      const seen = new Set(succ.map((r) => r.id));
      for (const r of ((await rb.json()).workflow_runs || []).filter((x) => !seen.has(x.id)).slice(0, 5)) {
        if ((await realRun(r, env)) !== "skipped") { ok = true; break; }
      }
    } else ok = true;   // 확인 못 하면 잘못 알리지 않는다
    if (!ok) lines.push(`• ${name(wf)} — 실행은 본 일을 건너뛰었고, 그 전 ${LOOKBACK_H}시간 안에 같은 일을 한 실행도 없습니다\n🔗 ${succ[0].html_url}`);
  }
  if (lines.length) {
    const t = kstTime(at).hm;
    await slack(env, `🚨 정기 실행 확인 (${t} 예정분)\n${lines.join("\n")}`);
  }
}

// 늦은 감시 + 자동 다시 걸기 — retry 가 붙은 일만, 하루 한 번까지 (at 뒤 실행이 둘 이상이면 이미 다시 건 것)
async function retryWatch(at, env) {
  const jobs = dueAt(at).filter((j) => j.retry);
  const since = new Date(at.getTime() - 5 * 60 * 1000).toISOString().slice(0, 19) + "Z";
  for (const j of jobs) {
    const wf = j.workflow;
    const res = await gh(`/actions/workflows/${wf}/runs?created=%3E%3D${since}&per_page=20`, env.GITHUB_TOKEN);
    if (res.status !== 200) continue;
    const runs = ((await res.json()).workflow_runs || []).filter((r) => r.event === "workflow_dispatch" || r.event === "schedule");
    if (!runs.length || runs.some((r) => r.status !== "completed")) continue;   // 없음은 60분 감시가 알렸다 · 도는 중이면 기다림
    // 본 잡이 실제로 돈 실행만 센다 — GitHub 예비 실행은 `성공(본 잡 건너뜀)`으로 남아 실행 수로 세면 '이미 다시 걸었다'로 잘못 본다 (11-18 · 11-19 기록)
    let jobOk = false, tried = 0, unknown = false, bad = null;   // bad = 본 잡이 돌았는데 성공하지 못한 가장 최근 실행
    for (const r of runs) {
      const jr = await gh(`/actions/runs/${r.id}/jobs?per_page=50`, env.GITHUB_TOKEN);
      if (jr.status !== 200) { unknown = true; continue; }
      const mine = ((await jr.json()).jobs || []).filter((x) => x.name === j.retry.job && x.conclusion && x.conclusion !== "skipped");
      if (mine.length) { tried++; if (!bad && !mine.some((x) => x.conclusion === "success")) bad = r; }
      if (mine.some((x) => x.conclusion === "success")) jobOk = true;   // 뒤 잡만 실패한 것은 60분 감시 · 워크플로 알림이 맡음
    }
    if (jobOk || unknown || !tried || !bad) continue;   // 성공 · 확인 못 함(잘못 다시 걸지 않게) · 본 잡이 돈 적 없음(수능일 게이트 등)
    const t = kstTime(at).hm;
    if (tried >= 2) {
      await slack(env, `🚨 ${name(wf)} (${t} 예정분) — 자동으로 다시 건 실행도 실패했습니다. 직접 확인해 주세요\n🔗 ${bad.html_url}`);
      continue;
    }
    try {
      await dispatch(wf, env.GITHUB_TOKEN, j.retry.inputs);
      await slack(env, `⚠️ ${name(wf)} (${t} 예정분) — ${bad.conclusion === "cancelled" ? "시간 초과 · 취소" : "실패"}로 끝나 자동으로 한 번 다시 걸었습니다\n🔗 ${bad.html_url}`);
    } catch (e) {
      await slack(env, `🚨 ${name(wf)} (${t} 예정분) — 실패했고 다시 걸기도 실패했습니다 (${e.status ? reason(e.status) : "연결 실패"})\n🔗 ${bad.html_url}`);
    }
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
    for (const min of [RETRY_AFTER_MIN, RETRY_AGAIN_MIN]) {
      ctx.waitUntil(retryWatch(new Date(at.getTime() - min * 60 * 1000), env).catch((e) => console.log(`다시 걸기 감시 오류: ${e}`)));
    }
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
