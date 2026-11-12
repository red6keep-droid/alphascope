/* AlphaScope 검색 즉답 · 질문하기 (2026-11-10 사용자 목업).
 * AI 호출 0 — 질문에서 종목(별명표) · 질문 종류(낱말표)를 코드로 찾고, 색인 값으로 정해진 문장을 만든다.
 * 색인: 목업은 window.AS_SEARCH_INDEX(파일에 넣어 둠), 블로그는 INDEX_BASE(jsDelivr gh-pages search/us.json · kr.json)를 처음 열 때 한 번만 읽는다.
 * 블로그 테마에는 build_theme.py 가 이 파일과 search.css 를 그대로 넣는다 — 고치면 build_theme.py 다시.
 * 관련 글: Blogger 공개 피드 검색(JSONP) — 서버 없이 블로그 글을 찾는다.
 * 지킬 것: 값마다 기준일("10-30 종가") · 사라/팔라 의견 없음 · 등락 이유를 지어내지 않음 · 다루지 않는 종목은 솔직하게.
 */
(function () {
  'use strict';
  var BLOG = 'https://alpha-scope.blogspot.com';
  /* 색인 = 시장마다 한 파일 (2026-11-11): 미국은 nvda-report 실행, 한국은 kr-stocks 실행이 gh-pages 에 올린다.
     둘 중 하나만 받아도 그 시장으로 답한다 — 둘 다 실패해야 "불러오지 못했습니다" */
  var INDEX_BASE = 'https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/search/';
  var INDEX_FILES = ['us.json', 'kr.json'];
  var OPTS = window.AS_SEARCH_OPTS || {};   // 테마: { chat: false } — 질문하기 버튼은 목업에서만 (2026-11-11 검색만 반영)
  var MINUS = '−';

  /* ---------- 색인 ---------- */
  var indexP = null;
  function fetchJson(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function fetchIndex() {
    var got = INDEX_FILES.map(function (f) { return fetchJson(INDEX_BASE + f).catch(function () { return null; }); });
    return Promise.all(got).then(function (docs) {
      docs = docs.filter(Boolean);
      if (!docs.length) throw new Error('index');
      return { built: docs.map(function (d) { return d.built; }).sort().pop(), stocks: [].concat.apply([], docs.map(function (d) { return d.stocks || []; })) };
    });
  }
  function loadIndex() {
    if (!indexP) {
      indexP = window.AS_SEARCH_INDEX ? Promise.resolve(window.AS_SEARCH_INDEX) : fetchIndex();
      indexP = indexP.then(prep, function (e) { indexP = null; throw e; });
    }
    return indexP;
  }
  function prep(doc) {
    var alias = [];
    doc.stocks.forEach(function (s) { s.a.forEach(function (a) { alias.push([a, s]); }); });
    alias.sort(function (x, y) { return y[0].length - x[0].length; });   // 긴 별명 먼저 — "삼성sdi" 가 "삼성" 보다 먼저
    doc.alias = alias;
    ['us', 'kr'].forEach(function (m) {   // 시총 순위 (다루는 종목 안에서)
      doc.stocks.filter(function (s) { return s.m === m && s.cap; })
        .sort(function (a, b) { return b.cap - a.cap; })
        .forEach(function (s, i) { s.rank = i + 1; });
    });
    return doc;
  }

  /* ---------- 판별 ---------- */
  var INTENTS = [   // [이름, 낱말] — 여러 개 걸리면 모두 보인다
    ['price', /주가|현재가|얼마|가격|종가|시세|price/],
    ['change', /등락|수익률|올랐|내렸|떨어|상승률|하락률|몇\s*(%|프로|퍼)|1\s*주일?|한\s*달|1\s*년|연초|올해/],
    ['range', /52\s*주|신고가|신저가|최고가|최저가|고점|저점/],
    ['volume', /거래량|거래\s*대금/],
    ['cap', /시가\s*총액|시총|덩치/],
    ['earnDate', /실적\s*발표|발표\s*일|어닝\s*발표|언제\s*발표|발표\s*언제/],
    ['earnings', /실적|매출|영업\s*이익|순이익|이익|분기|어닝|revenue/],
    ['valuation', /\bper\b|피이알|\beps\b|주당\s*순이익|목표\s*(가|주가)|컨센|애널|밸류|적정\s*주가/],
    ['tech', /\brsi\b|\bmacd\b|\badx\b|이동\s*평균|이평|기술\s*(적\s*)?지표|지표|과매수|과매도|골든|데드|추세/],
    ['company', /회사|기업\s*정보|\bceo\b|대표|사장|직원|본사|홈페이지|설립|상장|업종|뭐\s*하는/],
    ['news', /뉴스|소식|기사|이슈/],
  ];
  var ADVICE = /사도\s*(돼|될|되)|살까|사야|팔까|팔아야|매수|매도|추천|들어가도|손절|익절|물타|존버|사면\s*(돼|될)|팔면|살\s*만|사\s*말아/;
  var WHY = /왜|이유|원인|무슨\s*일|급등|급락|폭락|폭등/;
  var MARKET = /코스피|코스닥|나스닥|s&p|에스앤피|다우|지수|환율|금리|시장|증시|장\s*분위기/;

  function findStocks(doc, q) {
    var low = q.toLowerCase(), flat = low.replace(/[\s·,!?~'"()]/g, '');
    var hit = [], used = [];
    doc.alias.forEach(function (p) {
      var a = p[0], s = p[1], pos;
      if (hit.some(function (h) { return h.s === s; })) return;
      if (/^[a-z0-9.\-]+$/.test(a) && a.length <= 3) {   // 짧은 영문 티커는 낱말 그대로일 때만
        var m = new RegExp('(^|[^a-z0-9])' + a.replace(/[.\-]/g, '\\$&') + '(?![a-z0-9])').exec(low);
        if (!m) return;
        pos = m.index;
      } else {
        pos = flat.indexOf(a);
        if (pos < 0) return;
      }
      if (used.some(function (u) { return u.indexOf(a) >= 0; })) return;   // 더 긴 별명에 포함된 짧은 별명(삼성 ⊂ 삼성sdi)
      if (a === 'ma' && hit.length) return;   // "엔비디아 MA" 의 MA 는 이동평균 — 다른 종목이 있으면 마스터카드로 보지 않는다
      used.push(a);
      hit.push({ s: s, pos: pos });
    });
    hit.sort(function (x, y) { return x.pos - y.pos; });
    return hit.slice(0, 3).map(function (h) { return h.s; });
  }

  function classify(q) {
    var low = q.toLowerCase();
    return {
      advice: ADVICE.test(low), why: WHY.test(low), market: MARKET.test(low),
      intents: INTENTS.filter(function (x) { return x[1].test(low); }).map(function (x) { return x[0]; }),
      opNet: /영업\s*이익|순이익/.test(low),
      dir: /떨어|하락|빠졌|빠져|빠지|내렸|내려|급락|폭락/.test(low) ? -1 : /올랐|올라|오른|상승|급등|폭등|뛰었/.test(low) ? 1 : 0,   // 왜 떨어졌어 · 왜 올랐어 — 질문의 전제 방향
    };
  }

  /* ---------- 글자 모양 ---------- */
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function md(d) { return d ? d.slice(5) : ''; }
  function money(s, v) {
    if (v == null) return '—';
    return s.m === 'us' ? '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : Math.round(v).toLocaleString('ko-KR') + '원';
  }
  function big(n) {   // 4941442065261 → 4조 9,414억
    n = Math.round(n);
    var jo = Math.floor(n / 1e12), eok = Math.floor(n % 1e12 / 1e8), man = Math.floor(n % 1e8 / 1e4);
    if (jo) return jo.toLocaleString('ko-KR') + '조' + (eok ? ' ' + eok.toLocaleString('ko-KR') + '억' : '');
    if (eok) return eok.toLocaleString('ko-KR') + '억' + (man ? ' ' + man.toLocaleString('ko-KR') + '만' : '');
    if (man) return man.toLocaleString('ko-KR') + '만';
    return n.toLocaleString('ko-KR');
  }
  function bigMoney(s, v) { return v == null ? '—' : big(v) + (s.m === 'us' ? ' 달러' : ' 원'); }
  function pct(v, plain) {
    if (v == null) return '—';
    /* 증감 = ▲ · ▼ + 절댓값 + 증감 색, 0 은 부호 없이 (2026-11-12 사용자: "증감 표시는 삼각형으로" — 옛 + · −). 삼각형 = 숫자의 80% · 위로 1 (.as-tri) */
    var n = Math.abs(v).toFixed(Math.abs(v) >= 100 ? 0 : 1) + '%';
    if (plain) return (v > 0 ? '▲ ' : v < 0 ? '▼ ' : '') + n;
    return '<span class="' + (v > 0 ? 'as-up' : v < 0 ? 'as-dn' : '') + '">' + (v ? '<span class="as-tri">' + (v > 0 ? '▲' : '▼') + '</span> ' : '') + n + '</span>';
  }
  function josa(word, a, b) {   // 받침 있으면 a(은 · 으로), 없으면 b(는 · 로)
    var ch = word.charCodeAt(word.length - 1);
    if (ch < 0xAC00 || ch > 0xD7A3) return /[0-9]$/.test(word) ? a : b;
    var jong = (ch - 0xAC00) % 28;
    return jong && !(b === '로' && jong === 8) ? a : b;   // ㄹ 받침 + 로 → '로'
  }
  function short(n) {   // 막대 밑 숫자 — 962억 · 1.3조
    return n >= 1e12 ? (n / 1e12).toFixed(n >= 1e13 ? 0 : 1) + '조' : Math.round(n / 1e8).toLocaleString('ko-KR') + '억';
  }
  function moveWord(v) { return v > 0 ? '올랐습니다' : v < 0 ? '내렸습니다' : '같았습니다'; }
  function label(s) { return esc(s.n) + ' <span class="as-tk">' + esc(s.s.replace(/\.(KS|KQ)$/, '')) + '</span>'; }
  function row(k, v) { return '<div class="as-row"><span class="as-k">' + k + '</span><span class="as-v">' + v + '</span></div>'; }
  function cur(s) { return s.m === 'us' ? '달러' : '원'; }

  /* 분기 매출 = 시간 순서 값 → 선 그래프 (가이드라인 9절 `선 그래프` · dk.trend_card 점이 적을 때와 같은 모양, 2026-11-12 사용자: "우리가 쓰는 그래프 스타일").
     주인공 주황 #F5B971 선 2 · 속 빈 점 3/2 · 최신 점 5/4 · 최신 값만 13 굵게 #111(나머지 12 보통 회색) · 최신 가로축 이름 #111 · 세로축 = 오른쪽 12px · 가로 눈금선 #ECF0F5.
     점이 적으면(250px 아래) 카드 폭에 고르게 편다 — 선은 SVG(굵기 고정), 점 · 숫자 · 이름은 % 위치 */
  var CHART_MAIN = '#F5B971', GRID_LINE = '#ECF0F5', NOTE = '#6B7280';
  function niceStep(span) {
    var raw = span / 3 || 1, e = Math.pow(10, Math.floor(Math.log10(raw)));
    return [1, 2, 5, 10].map(function (m) { return m * e; }).filter(function (v) { return raw <= v; })[0];
  }
  function revChart(s) {
    var rows = s.rev.filter(function (x) { return x[1] != null; });
    if (rows.length < 2) return '';
    var unit = Math.max.apply(null, rows.map(function (x) { return x[1]; })) >= 1e12 ? 1e12 : 1e8;
    var uName = (unit === 1e12 ? '조' : '억') + ' ' + cur(s);
    var vals = rows.map(function (x) { return x[1] / unit; });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), st = niceStep(hi - lo);
    var t0 = Math.floor(lo / st) * st, t1 = Math.ceil(hi / st) * st;
    if (t1 === t0) t1 = t0 + st;
    var ticks = [];
    for (var t = t0; t <= t1 + st / 2; t += st) ticks.push(+t.toFixed(6));
    var n = rows.length, H = 120, top = 26, bot = 8;
    function Y(v) { return top + (t1 - v) / (t1 - t0) * (H - top - bot); }
    function P(i) { return (i + 0.5) / n * 100; }
    function num(v) { return v >= 100 ? Math.round(v).toLocaleString('ko-KR') : v.toFixed(1); }
    function qName(q) { var m = /^(\d{4})Q(\d)$/.exec(q); return m ? [m[1].slice(2) + '년', m[2] + '분기'] : [q]; }
    var grid = ticks.map(function (t) { return '<line x1="0" x2="1000" y1="' + Y(t).toFixed(1) + '" y2="' + Y(t).toFixed(1) + '" stroke="' + GRID_LINE + '" stroke-width="1" vector-effect="non-scaling-stroke"/>'; }).join('');
    var d = vals.map(function (v, i) { return (i ? 'L' : 'M') + (P(i) * 10).toFixed(1) + ',' + Y(v).toFixed(1); }).join('');
    var svg = '<svg viewBox="0 0 1000 ' + H + '" preserveAspectRatio="none" width="100%" height="' + H + '" style="position:absolute;left:0;top:0;display:block;" aria-hidden="true">' + grid
      + '<path d="' + d + '" fill="none" stroke="' + CHART_MAIN + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>';
    var marks = vals.map(function (v, i) {
      var last = i === n - 1, r = last ? 5 : 3, b = last ? 4 : 2;
      return '<span class="as-dot" style="left:calc(' + P(i).toFixed(2) + '% - ' + r + 'px);top:' + (Y(v) - r).toFixed(1) + 'px;width:' + 2 * r + 'px;height:' + 2 * r + 'px;border-width:' + b + 'px"></span>'
        /* 마지막 날 값 = 점 오른쪽(점 ~ 숫자 8, 점과 같은 높이) — 선 그래프 규칙 (2026-11-12 사용자, 가이드라인 9절). 나머지는 점 위 가운데 */
        + (last ? '<span class="as-val as-last as-end" style="left:calc(' + P(i).toFixed(2) + '% + ' + (r + 8) + 'px);top:' + (Y(v) - 7).toFixed(1) + 'px">' + num(v) + '</span>'
          : '<span class="as-val" style="left:' + P(i).toFixed(2) + '%;top:' + (Y(v) - 8 - r - 14).toFixed(1) + 'px">' + num(v) + '</span>');
    }).join('');
    var endW = 13 + String(num(vals[n - 1])).length * 8;   // 끝 숫자 자리 — 그림을 그만큼 좁혀 세로축 숫자와 겹치지 않게
    var axis = ticks.map(function (t) { return '<span style="top:' + (Y(t) - 9).toFixed(1) + 'px">' + (t % 1 ? num(t) : t.toLocaleString('ko-KR')) + '</span>'; }).join('');   // 정수 눈금은 소수점 없이
    var xl = rows.map(function (x, i) { return '<span class="' + (i === n - 1 ? 'as-last' : '') + '" style="left:' + P(i).toFixed(2) + '%">' + qName(x[0]).join('<br>') + '</span>'; }).join('');
    return '<div class="as-line"><div class="as-line-unit">(단위 : ' + uName + ')</div><div class="as-line-box"><div class="as-line-plot" style="height:' + H + 'px;margin-right:' + endW + 'px">' + svg + marks + '</div>'
      + '<div class="as-line-x" style="margin-right:' + endW + 'px">' + xl + '</div><div class="as-line-y" style="height:' + H + 'px">' + axis + '</div></div></div>';
  }

  /* ---------- 답 조각 (질문 종류마다 한 문장 + 숫자 줄) ---------- */
  var PART = {
    price: function (s, compact) {
      var p = s.p;
      return '<p class="as-say">' + (compact ? esc(s.n) : label(s)) + josa(s.n, '은', '는') + ' ' + md(p.d) + ' 종가 <b>' + money(s, p.c) + '</b>' + (s.m === 'us' ? '로' : '으로') + ', 전날보다 ' + pct(p.chg) + ' ' + moveWord(p.chg) + '.</p>';
    },
    change: function (s) {
      var r = s.p.r;
      return '<div class="as-grid">' + [['1주', r['1w']], ['1달', r['1m']], ['3달', r['3m']], ['올해', r.ytd], ['1년', r['1y']]]
        .map(function (x) { return '<div><span>' + x[0] + '</span><b>' + pct(x[1]) + '</b></div>'; }).join('') + '</div>';
    },
    range: function (s) {
      var p = s.p, off = (p.c / p.h52[0] - 1) * 100;
      return row('52주 최고', money(s, p.h52[0]) + ' <small>(' + md(p.h52[1]) + ')</small>') + row('52주 최저', money(s, p.l52[0]) + ' <small>(' + md(p.l52[1]) + ')</small>')
        + '<p class="as-note">' + md(p.d) + ' 종가는 52주 최고가보다 ' + Math.abs(off).toFixed(1) + '% ' + (off < -0.05 ? '아래' : '근처') + '입니다.</p>';
    },
    volume: function (s) {
      var p = s.p;
      if (!p.v) return '<p class="as-note">거래량 자료가 없습니다.</p>';
      return row(md(p.d) + ' 거래량', big(p.v) + ' 주') + (p.va ? row('직전 20일 평균', big(p.va) + ' 주 <small>(' + (p.v / p.va).toFixed(1) + '배)</small>') : '');
    },
    cap: function (s) {
      return row('시가총액', bigMoney(s, s.cap)) + (s.rank ? row('순위', 'AlphaScope가 다루는 ' + (s.m === 'us' ? '미국' : '한국') + ' 종목 중 ' + s.rank + '위') : '');
    },
    earnDate: function (s) {
      return row('다음 실적 발표', s.ne ? s.ne + ' <small>(예정)</small>' : '아직 잡힌 날짜가 없습니다');
    },
    earnings: function (s, c) {
      if (!s.rev || !s.rev.length) return '<p class="as-note">분기 매출 자료가 없습니다.</p>';
      var q = s.rev[s.rev.length - 1];
      var out = '<p class="as-say">최근 분기(' + q[0] + ') 매출은 <b>' + bigMoney(s, q[1]) + '</b>' + (q[2] != null ? ', 1년 전보다 ' + pct(q[2]) + ' ' + (q[2] >= 0 ? '늘었습니다' : '줄었습니다') : '') + '.</p>';
      out += revChart(s);
      if (c.opNet) out += '<p class="as-note">영업이익 · 순이익은 아직 검색 답에 넣지 않았습니다. 종목 페이지 실적 칸에서 보세요.</p>';
      return out + PART.earnDate(s);
    },
    valuation: function (s) {
      var out = '';
      /* ef = [다음 회계연도 예상 EPS, 30일 전, 결산월 'YYYY-MM'] — 올해 것이 아니다 (2026-11-12 사용자: `올해 예상 EPS` 라벨 오류).
         종목 페이지 card_eps 와 같은 말: `다음 회계연도(2027년 12월 결산)` */
      if (s.ef) {
        var fy = s.ef[2] ? (+s.ef[2].slice(0, 4)) + '년 ' + (+s.ef[2].slice(5, 7)) + '월 결산' : '';
        out += row('다음 회계연도 예상 EPS', money(s, s.ef[0]) + ' <small>(' + (fy ? fy + ' · ' : '') + (s.ef[1] ? '30일 전 ' + money(s, s.ef[1]) : '애널리스트 평균') + ')</small>');
        if (s.ef[0] > 0) out += row('다음 회계연도 예상 PER', (s.p.c / s.ef[0]).toFixed(1) + '배 <small>(' + md(s.p.d) + ' 종가 ÷ 다음 회계연도 예상 EPS)</small>');
      }
      if (s.pt) out += row('애널리스트 목표가 평균', money(s, s.pt[0]) + ' <small>(' + money(s, s.pt[1]) + ' ~ ' + money(s, s.pt[2]) + (s.pt[3] ? ', ' + s.pt[3] + '명' : '') + ')</small>');
      return out || '<p class="as-note">EPS · 목표가 자료가 없습니다.</p>';
    },
    tech: function (s) {
      var t = s.t, out = '';
      ['rsi', 'macd', 'adx'].forEach(function (k) { if (t[k]) out += row(esc(t[k][0]), esc(t[k][1]).replace(/-/g, MINUS) + ' <small>' + esc(t[k][2]) + '</small>'); });
      if (t.ma && t.ma.length) {
        var up = t.ma.filter(function (m) { return m[2]; }).map(function (m) { return m[0]; });
        var dn = t.ma.filter(function (m) { return !m[2]; }).map(function (m) { return m[0]; });
        out += row('이동평균선', (up.length ? up.join(' · ') + '일선 위' : '') + (up.length && dn.length ? ', ' : '') + (dn.length ? dn.join(' · ') + '일선 아래' : ''));
      }
      return out + '<p class="as-note">' + md(s.p.d) + ' 종가로 계산. 지표는 지난 가격을 요약한 값이며 앞으로의 방향을 알려 주지 않습니다.</p>';
    },
    company: function (s) {
      var c = s.co || {};
      return [['회사', c.nm], ['대표', c.ceo], ['업종', s.sec], ['본사', c.hq], ['시장', c.ex], ['설립', c.est], ['상장', c.listed],
        ['직원', c.emp ? c.emp.toLocaleString('ko-KR') + '명' : null], ['홈페이지', c.web]]
        .filter(function (x) { return x[1]; }).map(function (x) { return row(x[0], esc(x[1])); }).join('');
    },
    news: function (s) {
      if (!s.news || !s.news.length) return '<p class="as-note">' + (s.m === 'kr' ? '한국 종목 소식은 종목 페이지 방송 · 뉴스 칸에 모아 둡니다.' : '최근 모은 소식이 없습니다.') + '</p>';
      return '<ul class="as-news">' + s.news.map(function (n) { return '<li><span>' + md(n[0]) + '</span>' + esc(n[1]) + ' <small>' + esc(n[2]) + '</small></li>'; }).join('') + '</ul>';
    },
  };
  /* 구획 제목 아이콘 = 기본형(회색 면 원 22 · #E5E7EB, 그림 #4B5563 = 원의 0.55) — 가이드라인 8절 `아이콘`, 그림 원본 = design_kit.ICON_GLYPHS (2026-11-12 사용자) */
  var ICONS = {
    price: '<path d="M1.5 8.5h3l1.5-4 3 8 1.5-4h4"/>',
    change: '<path d="M2 11.5l4-4 3 3 5-6"/><path d="M10.5 4.5H14v3.5"/>',
    range: '<path d="M5 3v10M3 5l2-2 2 2M11 13V3M9 11l2 2 2-2"/>',
    volume: '<path d="M3 13V10M6 13V7M9 13V9M12 13V5"/>',
    cap: '<circle cx="8" cy="8" r="5.5"/><path d="M8 2.5V8h5.5"/>',
    earnDate: '<rect x="2.5" y="3.5" width="11" height="10" rx="1.5"/><path d="M2.5 7h11M5.5 2v3M10.5 2v3"/>',
    earnings: '<path d="M2.5 13.5h11M4.5 11V8M8 11V5M11.5 11V3"/>',
    valuation: '<circle cx="8" cy="8" r="5.5"/><circle cx="8" cy="8" r="2.5"/>',
    tech: '<path d="M2.8 11.5a5.2 5.2 0 1 1 10.4 0"/><path d="M8 11.5l2.6-3"/>',
    company: '<path d="M3.5 14V3h6v11M9.5 7h3v7M2 14h12M5.5 5.5h2M5.5 8h2M5.5 10.5h2"/>',
    news: '<path d="M3 3h8v10H4a1 1 0 0 1-1-1V3z"/><path d="M11 6h2v6a1 1 0 0 1-1 1"/><path d="M5 6h4M5 9h4"/>'
  };
  function ico(k) {
    return ICONS[k] ? '<span class="as-ico" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + ICONS[k] + '</svg></span>' : '';
  }
  var EXCL = '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.6v4.4" stroke-linecap="round"/><circle cx="8" cy="11.2" r=".9" fill="currentColor" stroke="none"/></svg>';
  /* ---------- 왜 떨어졌어 · 왜 올랐어 (2026-11-12 사용자: "엔비디아 왜 떨어졌어? 답변 가능해? 샘플 목업").
     이유는 짐작하지 않는다(가이드라인 1절 4-2 단일 변수 단언 금지). 대신 독자가 스스로 판단할 세 가지:
     ① 전제 확인 — 그날 정말 내렸나, 아니면 내린 건 어느 기간인가  ② 같은 기간 시장 · 같은 업종과 비교 — 혼자 내렸나, 다 같이 내렸나
     ③ 그 기간 안에 나온 소식만 — 기간 밖의 옛 소식은 이유처럼 읽혀 보이지 않는다 ---------- */
  var WIN = [['1d', '그날', 1], ['1w', '최근 1주', 7], ['1m', '최근 1달', 31], ['3m', '최근 3달', 92]];
  function moveOf(p, k) { return k === '1d' ? p.chg : p.r[k]; }
  function peerEtfs(doc, s) {   // 비교 대상 = 시장 + 같은 업종 ETF (색인 etfs)
    var E = {}; (doc.etfs || []).forEach(function (e) { E[e.s] = e; });
    var out = [];
    if (s.m === 'us') {
      if (E.SPY) out.push(['S&P 500', E.SPY]);
      if (/반도체/.test(s.sec) && E.SMH) out.push(['반도체 업종', E.SMH]);
      else if (/기술|빅테크/.test(s.sec) && E.XLK) out.push(['기술 업종', E.XLK]);
    } else {
      if (/반도체/.test(s.sec) && E['091160.KS']) out.push(['반도체 업종', E['091160.KS']]);
      if (/2차전지|배터리/.test(s.sec) && E['305720.KS']) out.push(['2차전지 업종', E['305720.KS']]);
    }
    return out;
  }
  function pickWindow(s, dir) {   // 질문 방향과 같은 쪽으로 움직인 가장 짧은 기간
    if (!dir) return WIN[0];
    for (var i = 0; i < WIN.length; i++) { var v = moveOf(s.p, WIN[i][0]); if (v != null && v * dir > 0) return WIN[i]; }
    return null;
  }
  function me0(p, w) { return w ? moveOf(p, w[0]) : p.chg; }
  function whyPart(s, c, doc) {
    var p = s.p, dir = c.dir, w = pickWindow(s, dir), d1 = p.chg, out = '';
    var word = function (v) { return v > 0 ? '올랐습니다' : v < 0 ? '내렸습니다' : '그대로였습니다'; };
    // ① 전제 확인
    if (!dir || (w && w[0] === '1d')) {
      out += '<p class="as-say">' + esc(s.n) + josa(s.n, '은', '는') + ' ' + md(p.d) + ' 종가 <b>' + money(s, p.c) + '</b>' + (s.m === 'us' ? '로' : '으로') + ', 전날보다 ' + pct(d1) + ' ' + word(d1) + '.</p>';
    } else if (w) {
      out += '<p class="as-say">' + md(p.d) + ' 종가는 전날보다 ' + pct(d1) + ' ' + word(d1) + '. ' + (dir < 0 ? '내린' : '오른') + ' 것은 ' + w[1] + ' ' + pct(moveOf(p, w[0])) + '입니다.</p>';
    } else {
      out += '<p class="as-say">최근 3달 안에 ' + (dir < 0 ? '내린' : '오른') + ' 기간이 없습니다. ' + md(p.d) + ' 종가는 전날보다 ' + pct(d1) + ' ' + word(d1) + '.</p>';
      w = WIN[0];
    }
    /* 칸 이름 = 이유를 좁히는 질문 (2026-11-12 사용자: "같은 기간 소식 · 같은 기간 비교가 무슨 얘기인지 모르겠다, 왜 떨어졌는지의 근거를 설명해야").
       이유를 단정하지 않는다(가이드라인 1절 4-2). 대신 ② 시장 · 업종 탓인지 이 종목만의 일인지 ③ 그때 무슨 일이 있었는지 ④ 어디까지 움직인 자리인지 — 근거를 보이고 답은 사실 문장으로 */
    var down = (dir || me0(p, w)) < 0, mv = down ? '내렸' : '올랐';
    var me = moveOf(p, w[0]), peers = peerEtfs(doc, s);
    // ② 무엇이 이유로 꼽혔나? — 증시 전망 이유 카드와 같은 재료 · 같은 제목 (forecast_register.side_news · 애널리스트, 색인 why)
    var from = new Date(p.d); from.setDate(from.getDate() - w[2] - (w[0] === '1d' ? 1 : 0));
    var f = from.toISOString().slice(0, 10);
    var W = s.why || {}, inWin = function (r) { return r[0] >= f && r[0] <= p.d; };
    var mine = (W[down ? 'bad' : 'good'] || []).filter(inWin), other = (W[down ? 'good' : 'bad'] || []).filter(inWin), open = (W.open || []).filter(inWin);
    var an = (W.an || []).filter(inWin), cnt = function (k) { return an.filter(function (a) { return a[1] === k; }).length; };
    var anTxt = down ? [cnt('down') ? '목표가 내림 ' + cnt('down') + '곳' : '', cnt('cut') ? '의견 낮춤 ' + cnt('cut') + '곳' : ''] : [cnt('up') ? '목표가 올림 ' + cnt('up') + '곳' : ''];
    anTxt = anTxt.filter(Boolean).join(' · ');
    var line = function (r) { return '<li><span>' + md(r[0]) + '</span>' + esc(r[1]) + (r[2] ? ' <small>' + esc(r[2]) + '</small>' : '') + (r[3] === 2 ? ' <em class="as-lv">업종</em>' : '') + '</li>'; };
    out += '<div class="as-sec"><h4>' + ico('news') + '무엇이 이유로 꼽혔나? <small>(' + w[1] + ')</small></h4>';
    if (mine.length || anTxt || open.length) {
      out += '<ul class="as-news">' + mine.slice(0, 3).map(line).join('')
        + (anTxt ? '<li><span>' + md(an[an.length - 1][0]) + '</span>애널리스트 ' + anTxt + '</li>' : '')
        + open.slice(0, 1).map(function (r) { return line(r).replace('<li>', '<li><em class="as-open">향방미정</em> '); }).join('') + '</ul>';
      if (mine.length > 3) out += '<p class="as-note">' + (down ? '하락' : '상승') + ' 쪽 기사 ' + (mine.length - 3) + '건 더는 종목 페이지에 있습니다.</p>';
    } else {
      out += '<p class="as-say">' + w[1] + '(' + md(f) + ' ~ ' + md(p.d) + ') 사이에 ' + (down ? '하락' : '상승') + ' 쪽으로 꼽힌 기사 · 애널리스트 변경이 없습니다.</p>';
    }
    if (other.length) out += '<p class="as-note">같은 기간 ' + (down ? '좋은' : '나쁜') + ' 소식도 ' + other.length + '건 있었습니다.</p>';
    out += (mine.length || anTxt || open.length ? '<p class="as-note">기사 · 애널리스트에서 모은 것입니다. 원인을 판단한 것은 아닙니다.</p>' : '') + '</div>';   // 빈 칸엔 안내를 붙이지 않는다
    // ③ 시장 · 업종도 같이 움직였나 — 화면 순서는 `무엇이 이유로 꼽혔나?` 다음 (2026-11-12 제안 순서)
    var cmpHtml = '';
    if (peers.length && me != null) {
      var mkt = peers[0], sec = peers[1], vm = moveOf(mkt[1].p, w[0]), vs = sec ? moveOf(sec[1].p, w[0]) : null;
      var worse = function (a, b) { return down ? a < b : a > b; };   // a 가 b 보다 더 크게 움직였나 (질문 방향 기준)
      var say;
      if (Math.abs(me - vm) <= 1) say = '시장 전체(' + esc(mkt[0]) + ')와 비슷하게 ' + mv + '습니다. ' + esc(s.n) + '만의 일보다 시장 흐름에 가깝습니다.';
      else if (sec && vs != null && worse(vs, vm) && (Math.abs(me - vs) <= 1.5 || worse(vs, me)))
        say = esc(sec[0]) + josa(sec[0], '이', '가') + ' 함께 ' + mv + '습니다. ' + esc(s.n) + '만의 일보다 업종 흐름에 가깝습니다.';
      else if (worse(me, vm - (down ? 1.5 : -1.5)) && (!sec || vs == null || worse(me, vs - (down ? 1.5 : -1.5))))
        say = '시장' + (sec ? ' · 업종' : '') + '보다 크게 ' + mv + '습니다. ' + esc(s.n) + '만의 소식이 있었는지 아래에서 보세요.';
      else say = '시장보다 조금 더 ' + mv + '습니다.';
      cmpHtml = '<div class="as-sec"><h4>' + ico('change') + '시장 · 업종도 같이 ' + (down ? '내렸나?' : '올랐나?') + ' <small>(' + w[1] + ')</small></h4>'
        + '<p class="as-say">' + say + '</p>' + row(esc(s.n), pct(me)) + row(esc(mkt[0]), pct(vm)) + (sec && vs != null ? row(esc(sec[0]), pct(vs)) : '') + '</div>';
    }
    out += cmpHtml;
    // ④ 알파스코프 신호 — 종목 페이지 판정 가운데 질문 방향과 같은 쪽 (증시 전망 갈래 근거와 같은 나눔: 단기 · 중기)
    if (W.sig && W.sig.rows && W.sig.rows.length) {
      var want = down ? -1 : 1, same = W.sig.rows.filter(function (r) { return r[2] === want; }), opp = W.sig.rows.filter(function (r) { return r[2] === -want; });
      out += '<div class="as-sec"><h4>' + ico('tech') + (down ? '하락' : '상승') + ' 쪽 알파스코프 신호 <small>(' + md(W.sig.d) + ' 종목 페이지)</small></h4>';
      if (same.length) {
        ['단기', '중기'].forEach(function (hz) {
          var rs = same.filter(function (r) { return r[3] === hz; });
          if (rs.length) out += '<p class="as-hz">' + hz + '</p>' + rs.map(function (r) { return row(esc(r[0]), '<span class="' + (want < 0 ? 'as-dn' : 'as-up') + '">' + esc(r[1]) + '</span>'); }).join('');
        });
      } else out += '<p class="as-say">' + (down ? '하락' : '상승') + ' 쪽으로 켜진 신호가 없습니다.</p>';
      if (opp.length) out += '<p class="as-note">반대(' + (down ? '상승' : '하락') + ') 쪽 신호도 ' + opp.length + '개 있습니다.</p>';
      out += '</div>';
    }
    // ⑤ 어디까지 움직인 자리인가 — 기술 지표는 이유가 아니라 위치라서 따로
    var h = p.h52, l = p.l52, ma = (s.t && s.t.ma) || [];
    var rows = '';
    if (w[0] === '1d' && W.sd) rows += row('그날 움직임', '평소 하루 움직임의 ' + (Math.abs(p.chg) / W.sd).toFixed(1) + '배 <small>(직전 60거래일)</small>');
    if (down && h) rows += row('52주 최고가 대비', pct((p.c / h[0] - 1) * 100) + ' <small>(' + md(h[1]) + ' ' + money(s, h[0]) + ')</small>');
    if (!down && l) rows += row('52주 최저가 대비', pct((p.c / l[0] - 1) * 100) + ' <small>(' + md(l[1]) + ' ' + money(s, l[0]) + ')</small>');
    if (ma.length) {
      var up = ma.filter(function (m) { return m[2]; }).map(function (m) { return m[0]; }), dn = ma.filter(function (m) { return !m[2]; }).map(function (m) { return m[0]; });
      rows += row('이동평균선', (dn.length ? dn.join(' · ') + '일선 아래' : '') + (dn.length && up.length ? ', ' : '') + (up.length ? up.join(' · ') + '일선 위' : ''));
    }
    if (rows) out += '<div class="as-sec"><h4>' + ico('range') + '어디까지 ' + (down ? '내린' : '오른') + ' 자리인가?</h4>' + rows
      + '<p class="as-note">지난 가격으로 잰 위치입니다. 움직인 이유나 앞으로의 방향을 알려 주지 않습니다.</p></div>';
    return out;
  }
  var TITLE = { change: '기간별 등락', range: '52주 범위', volume: '거래량', cap: '시가총액', earnDate: '실적 발표일', earnings: '실적', valuation: 'EPS · PER · 목표가', tech: '기술 지표', company: '회사 정보', news: '최근 소식' };

  function card(s, c, compact, doc) {
    var list = c.intents.slice();
    /* 맨 위 = 검색한 내용 (2026-11-10 사용자: "엔비디아 실적을 검색했는데 실적이 먼저 안 나온다 — 첫 번째는 검색한 내용, 부가 정보는 그 아래").
       묻은 칸(실적 · EPS …)을 먼저, 주가 한 줄은 그 아래 '오늘 주가'. 종목 이름만 · 주가를 물으면 주가가 곧 답이라 맨 위 */
    var asked = list.filter(function (x) { return x !== 'price'; });
    if (asked.indexOf('earnings') >= 0) asked = asked.filter(function (x) { return x !== 'earnDate'; });
    var priceFirst = !asked.length;
    /* 종목 이름만 → 요약 = 주가 한 문장 · 기간별 등락 · 다음 실적 발표 (2026-11-12 사용자: "요약이 독자가 원하는 내용이 맞아?").
       EPS · PER · 목표가는 물을 때만 — 이름만 친 독자에게는 어려운 숫자이고 목표가는 사라는 말처럼 읽힌다. 자세한 것은 종목 페이지로 */
    var extra = priceFirst ? (compact ? ['change'] : ['change', 'earnDate']) : [];
    var body = '';
    if (c.why) {   // 왜 떨어졌어 → 전제 확인 · 같은 기간 비교 · 같은 기간 소식 (오늘 주가 칸은 첫 문장과 겹쳐 두지 않는다)
      body += '<p class="as-note as-why-note">AlphaScope는 등락 이유를 짐작해서 답하지 않습니다. 증시 전망과 같은 기준으로 꼽힌 이유와 숫자를 모았습니다.</p>' + whyPart(s, c, doc);
    } else {
    if (priceFirst) body += PART.price(s, compact);
    asked.concat(extra).forEach(function (k, i) {
      body += '<div class="as-sec' + (!priceFirst && i === 0 ? ' as-first' : '') + '"><h4>' + ico(k) + TITLE[k] + '</h4>' + PART[k](s, c) + '</div>';
    });
    if (!priceFirst) body += '<div class="as-sec as-today"><h4>' + ico('price') + '오늘 주가</h4>' + PART.price(s, compact) + '</div>';
    }
    return '<article class="as-card">'
      /* 질문하기(compact) = 시장 라벨 · 티커 · 종목 코드 없이 이름만 (2026-11-12 사용자: "한국 라벨 빼 · 옆에 숫자 빼") */
      + '<header>' + (compact ? '' : '<span class="as-mkt as-' + s.m + '">' + (s.m === 'us' ? '미국' : '한국') + '</span>') + '<h3>' + (compact ? esc(s.n) : label(s)) + '</h3><span class="as-day">' + md(s.p.d) + ' 종가 기준</span></header>'
      + body
      /* 독자가 실제로 가야 할 곳 = 종목 페이지 → 카드 끝 흰 버튼(가이드라인 10절 흰 버튼: 외곽선 · 검은 글씨, 2026-11-12 사용자 — 처음 검은 버튼에서 바꿈) */
      + '<a class="as-go" href="' + esc(s.u) + '">' + esc(s.n) + ' 종목 페이지 보기</a>'
      + '<p class="as-go-note"><span>' + EXCL + '</span><span>주가 차트 · 실적 · 애널리스트 의견 · 기술 지표 · 뉴스를 한 페이지에 모았습니다.</span></p></article>';
  }

  function answer(doc, q, compact) {
    var c = classify(q), stocks = findStocks(doc, q), html = '';
    if (c.advice) html += '<div class="as-notice">AlphaScope는 개별 종목을 사라 · 팔라는 의견을 드리지 않습니다. 판단에 쓸 수 있는 숫자를 모아 드릴게요.</div>';
    if (stocks.length) {
      stocks.forEach(function (s) { html += card(s, c, compact, doc); });
    } else if (c.market) {
      html += '<div class="as-empty">지수 · 환율 · 금리는 홈의 시장 칸과 <a href="' + BLOG + '/search/label/데일리%20브리핑">데일리 리포트</a>에서 매일 정리합니다.</div>';
    } else {
      html += '<div class="as-empty">질문에서 AlphaScope가 다루는 종목을 찾지 못했습니다. 미국 주요 ' + doc.stocks.filter(function (s) { return s.m === 'us'; }).length
        + '종목 · 한국 주요 ' + doc.stocks.filter(function (s) { return s.m === 'kr'; }).length + '종목의 주가 · 등락 · 실적 · EPS · 기술 지표 · 회사 정보를 답할 수 있어요.'
        // 선정 기준 — stock-radar/universe.py · kr-stocks/universe_kr.py (2026-11-10 사용자: "주요" 표시 + 기준 짧게)
        + '<p class="as-basis"><span aria-hidden="true">ⓘ</span>주요 종목 = 미국은 S&amp;P 500 시가총액 상위 · 섹터 대표 · 이슈 종목, 한국은 시가총액 상위 · 반도체 · 2차전지 · 바이오 · 방산 테마 대표 종목입니다.</p></div>';
    }
    return { html: html, stocks: stocks, c: c };
  }

  /* ---------- 관련 글 (Blogger 공개 피드 검색, JSONP) ---------- */
  var seq = 0;
  function relatedPosts(term, n) {
    return new Promise(function (ok, no) {
      var cb = '__asFeed' + (++seq), sc = document.createElement('script');
      var t = setTimeout(function () { clean(); no(new Error('timeout')); }, 6000);
      function clean() { clearTimeout(t); delete window[cb]; sc.remove(); }
      window[cb] = function (j) {
        clean();
        ok(((j.feed && j.feed.entry) || []).map(function (e) {
          var link = (e.link || []).filter(function (l) { return l.rel === 'alternate'; })[0];
          return { t: e.title.$t, d: (e.published.$t || '').slice(0, 10), u: link ? link.href : BLOG };
        }));
      };
      sc.onerror = function () { clean(); no(new Error('load')); };
      sc.src = BLOG + '/feeds/posts/summary?alt=json-in-script&max-results=' + (n || 5) + '&q=' + encodeURIComponent(term) + '&callback=' + cb;
      document.head.appendChild(sc);
    });
  }
  /* 함께 보는 페이지 (2026-11-12 사용자: "관련 글이 삼성전자와 어떤 관련인지 모르겠다 · 블로그에서 더 찾기가 옛 리포트로 간다").
     Blogger 피드 검색은 고정 페이지(종목 페이지)를 못 찾고, 종목 이름이 한 번 나온 날짜별 리포트만 돌려준다 → 종목을 찾았으면 쓰지 않는다.
     종목을 찾았으면 = 그 시장 시총 TOP 10 · 그 시장 증시 리포트(이름 · 주소 = design_kit.REPORT_LINKS).
     못 찾았으면 = 그 말이 나온 글(피드 검색, 최대 3) + 두 시장 리포트. `블로그에서 더 찾기`(Blogger /search)는 없앤다 — 그 화면이 옛 글 하나만 보인다 */
  var LINKS = {
    us: ['미국 증시 리포트', BLOG + '/search/label/%EB%8D%B0%EC%9D%BC%EB%A6%AC%20%EB%B8%8C%EB%A6%AC%ED%95%91'],
    kr: ['한국 증시 리포트', BLOG + '/search/label/%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8'],
    us_top: ['미국 시가총액 상위 10개 종목 주가', BLOG + '/p/us-market-cap-top10.html'],
    kr_top: ['한국 시가총액 상위 10개 종목 주가', BLOG + '/p/kr-market-cap-top10.html'],
  };
  var OUT_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5"/></svg>';
  function outBtn(name, url, sub) {
    return '<a class="as-out" href="' + esc(url) + '"><span>' + esc(name) + (sub ? '<small>' + esc(sub) + '</small>' : '') + '</span>' + OUT_ICON + '</a>';
  }
  function searchTerm(q) {
    return q.replace(/알려\s*줘|알려\s*주세요|어때|뭐야|인가요|있어\??|[?？!]/g, ' ').trim();
  }
  function fillRelated(box, q, stocks) {
    var head = '<h4>함께 보는 페이지</h4>';
    if (stocks.length) {
      var m = stocks[0].m;
      box.innerHTML = head + outBtn(LINKS[m][0], LINKS[m][1]) + outBtn(LINKS[m + '_top'][0], LINKS[m + '_top'][1]);   // 증시 리포트 → 시총 TOP 10 (2026-11-12 사용자)
      return;
    }
    var fixed = outBtn(LINKS.us[0], LINKS.us[1]) + outBtn(LINKS.kr[0], LINKS.kr[1]);
    var term = searchTerm(q);
    box.innerHTML = head + fixed;
    if (!term) return;
    relatedPosts(term, 3).then(function (rows) {
      if (!rows.length) return;
      box.innerHTML = '<h4>‘' + esc(term) + '’이 나온 글</h4>' + rows.map(function (r) { return outBtn(r.t, r.u, r.d.replace(/-/g, '.')); }).join('')
        + '<h4 class="as-h-next">함께 보는 페이지</h4>' + fixed;
    }, function () {});
  }

  /* ---------- 검색 창 (헤더 아이콘) ---------- */
  var EXAMPLES = ['엔비디아 주가', '삼성전자 실적', '테슬라 RSI', '애플 시총', '하이닉스 목표가', '엔비디아 왜 떨어졌어?'];
  function chips(cls) { return '<div class="' + cls + '">' + EXAMPLES.map(function (e) { return '<button type="button" data-q="' + esc(e) + '">' + esc(e) + '</button>'; }).join('') + '</div>'; }

  function buildSearch() {
    var layer = document.createElement('div');
    layer.className = 'as-search-layer';
    layer.hidden = true;
    layer.innerHTML = '<div class="as-search-box" role="dialog" aria-modal="true" aria-label="검색">'
      + '<form class="as-search-form" role="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>'
      + '<input type="search" name="q" placeholder="종목 이름이나 궁금한 것 (예: 엔비디아 실적)" autocomplete="off" enterkeyhint="search">'
      + '<button type="button" class="as-clear" aria-label="검색어 지우기" hidden><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10"/><path d="M7 7l6 6M13 7l-6 6"/></svg></button>'
      + '<button type="button" class="as-x" aria-label="검색 닫기"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16"/><path d="M11.5 11.5l9 9M20.5 11.5l-9 9"/></svg></button></form>'
      + '<div class="as-search-out">' + chips('as-chips') + '<p class="as-hint">주가 · 등락 · 실적 · EPS · 기술 지표 · 회사 정보를 바로 답하고, 종목 페이지로 안내합니다.</p></div></div>';
    document.body.appendChild(layer);
    var form = layer.querySelector('form'), input = form.q, out = layer.querySelector('.as-search-out'), clr = layer.querySelector('.as-clear');
    function syncClear() { clr.hidden = !input.value; }
    input.addEventListener('input', syncClear);
    clr.addEventListener('click', function () { input.value = ''; syncClear(); input.focus(); });

    function run(q) {
      q = q.trim();
      if (!q) return;
      input.value = q;
      syncClear();
      out.innerHTML = '<p class="as-note">찾는 중…</p>';
      loadIndex().then(function (doc) {
        var a = answer(doc, q, false);
        out.innerHTML = '<section class="as-answer">' + a.html + '</section><section class="as-related"></section>';
        fillRelated(out.querySelector('.as-related'), q, a.stocks);
      }, function () {
        out.innerHTML = '<p class="as-note">종목 자료를 불러오지 못했습니다.</p><section class="as-related"></section>';
        fillRelated(out.querySelector('.as-related'), q, []);
      });
    }
    form.addEventListener('submit', function (e) { e.preventDefault(); run(input.value); });
    layer.addEventListener('click', function (e) {
      if (e.target === layer || e.target.closest('.as-x')) close();
      var chip = e.target.closest('[data-q]');
      if (chip) run(chip.getAttribute('data-q'));
    });
    function open(q) { layer.hidden = false; document.documentElement.classList.add('as-lock'); loadIndex().catch(function () {}); setTimeout(function () { input.focus(); }, 30); if (q) run(q); }
    function close() { layer.hidden = true; document.documentElement.classList.remove('as-lock'); }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !layer.hidden) close();
      if (e.key === '/' && layer.hidden && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); open(); }
    });
    return { open: open };
  }

  /* ---------- 질문하기 (블로그 챗봇) ---------- */
  function buildChat() {
    var fab = document.createElement('button');
    fab.type = 'button';
    fab.className = 'as-chat-fab';
    /* 반짝임 아이콘(큰 별 + 작은 별, 선 1.5) — 포인트 색 C5 (2026-11-12 사용자) */
    fab.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 3l1.8 5.2L18 10l-5.2 1.8L11 17l-1.8-5.2L4 10l5.2-1.8z"/><path d="M18.5 14.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/></svg><span>질문하기</span>';
    var pane = document.createElement('section');
    pane.className = 'as-chat';
    pane.hidden = true;
    pane.setAttribute('aria-label', '질문하기');
    /* 머리 = 블로그 로고(그림 + 로고 글꼴 900) + `에 물어보기` 보통 굵기 (2026-11-12 사용자) */
    pane.innerHTML = '<header><span class="as-chat-title"><svg class="as-chat-logo" viewBox="0 0 313 286" aria-hidden="true"><path d="M313 134L164.968 286H35L189.03 134H313Z" fill="#DD0000"/><path d="M164.519 0H287L128.954 147H0L164.519 0Z" fill="#000"/></svg><span><span class="as-chat-word">AlphaScope</span>에 물어보기</span></span><button type="button" class="as-x" aria-label="닫기"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16"/><path d="M11.5 11.5l9 9M20.5 11.5l-9 9"/></svg></button></header>'
      + '<div class="as-log" aria-live="polite"></div>'
      + '<form><input name="q" placeholder="예: 삼성전자 실적 알려줘" autocomplete="off" enterkeyhint="send"><button type="submit">보내기</button></form>'
      + '<footer>AI가 아니라 AlphaScope가 모은 자료로 답합니다 · 투자 권유가 아닙니다</footer>';
    document.body.appendChild(fab);
    document.body.appendChild(pane);
    var log = pane.querySelector('.as-log'), form = pane.querySelector('form');

    function say(who, html) {
      var b = document.createElement('div');
      b.className = 'as-msg as-' + who;
      b.innerHTML = html;
      log.appendChild(b);
      log.scrollTop = log.scrollHeight;
      return b;
    }
    say('bot', '<p>궁금한 종목을 물어보세요. 주가 · 등락 · 실적 · 기술 지표 · 회사 정보를 바로 답해 드립니다.</p>' + chips('as-chips'));   // 옛 `종목 숫자를 물어보세요` — 숫자를 아는 독자는 없다 (2026-11-12 사용자)

    function ask(q) {
      q = q.trim();
      if (!q) return;
      say('me', esc(q));
      form.q.value = '';
      loadIndex().then(function (doc) {
        var a = answer(doc, q, true), b = say('bot', a.html);
        if (!a.stocks.length && !a.c.market) {   // 종목을 못 찾으면 블로그 글로
          var box = document.createElement('div');
          box.className = 'as-related';
          b.appendChild(box);
          fillRelated(box, q, [], 3);
        }
      }, function () { say('bot', '<p>자료를 불러오지 못했습니다. 잠시 뒤 다시 물어봐 주세요.</p>'); });
    }
    form.addEventListener('submit', function (e) { e.preventDefault(); ask(form.q.value); });
    pane.addEventListener('click', function (e) {
      var chip = e.target.closest('[data-q]');
      if (chip) ask(chip.getAttribute('data-q'));
      if (e.target.closest('.as-x')) { pane.hidden = true; fab.hidden = false; }
    });
    function open(q) { pane.hidden = false; fab.hidden = true; loadIndex().catch(function () {}); form.q.focus(); if (q) ask(q); }
    fab.addEventListener('click', function () { open(); });
    return { open: open };
  }

  /* ---------- Blogger 검색 결과 화면 (/search?q=) — 적용 때 테마가 #as-search-answer 자리를 둔다 ---------- */
  function mountOnSearchPage() {
    var slot = document.getElementById('as-search-answer');
    var q = new URLSearchParams(location.search).get('q');
    if (!slot || !q) return;
    loadIndex().then(function (doc) {
      var a = answer(doc, q, false);
      if (a.stocks.length) slot.innerHTML = '<section class="as-answer">' + a.html + '</section>';
    }).catch(function () {});
  }

  function init() {
    var s = buildSearch();
    /* 검색 아이콘 = 국기 스위치 왼쪽 (2026-11-10 사용자). 스위치 줄(.menu-quick)은 테마 JS 가 만든다 — 그 맨 앞으로 옮긴다 */
    var quick = document.querySelector('.menu-quick'), sbtn = document.querySelector('.as-search-btn');
    if (quick && sbtn) quick.insertBefore(sbtn, quick.firstChild);
    document.querySelectorAll('[data-as-search]').forEach(function (b) { b.addEventListener('click', function () { s.open(); }); });
    var chat = OPTS.chat !== false ? buildChat() : null;
    mountOnSearchPage();
    var q = new URLSearchParams(location.search).get('ask');   // 목업 시험용: ?ask=엔비디아 실적
    if (q) s.open(q);
    var cq = new URLSearchParams(location.search).get('chat');   // 목업 시험용: ?chat=삼성전자 실적 — 질문하기 창을 그 질문으로 연다
    if (cq && chat) chat.open(cq);
  }
  window.ASSearch = { classify: classify, findStocks: findStocks, answer: answer, loadIndex: loadIndex };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
