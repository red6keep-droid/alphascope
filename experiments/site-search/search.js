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
    var t = (v > 0 ? '+' : v < 0 ? MINUS : '') + Math.abs(v).toFixed(Math.abs(v) >= 100 ? 0 : 1) + '%';
    return plain ? t : '<span class="' + (v > 0 ? 'as-up' : v < 0 ? 'as-dn' : '') + '">' + t + '</span>';
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

  /* ---------- 답 조각 (질문 종류마다 한 문장 + 숫자 줄) ---------- */
  var PART = {
    price: function (s) {
      var p = s.p;
      return '<p class="as-say">' + label(s) + josa(s.n, '은', '는') + ' ' + md(p.d) + ' 종가 <b>' + money(s, p.c) + '</b>' + (s.m === 'us' ? '로' : '으로') + ', 전날보다 ' + pct(p.chg) + ' ' + moveWord(p.chg) + '.</p>';
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
      out += '<div class="as-bars">' + s.rev.map(function (x) {
        var mx = Math.max.apply(null, s.rev.map(function (y) { return y[1]; }));
        return '<div><i style="height:' + Math.max(6, Math.round(x[1] / mx * 56)) + 'px"></i><b>' + short(x[1]) + '</b><span>' + x[0] + '</span></div>';
      }).join('') + '</div>';
      if (c.opNet) out += '<p class="as-note">영업이익 · 순이익은 아직 검색 답에 넣지 않았습니다. 종목 페이지 실적 칸에서 보세요.</p>';
      return out + PART.earnDate(s);
    },
    valuation: function (s) {
      var out = '';
      if (s.eps) {
        out += row('올해 예상 EPS', money(s, s.eps[0]) + (s.eps[1] ? ' <small>(30일 전 ' + money(s, s.eps[1]) + ')</small>' : ''));
        out += row('예상 EPS로 본 PER', (s.p.c / s.eps[0]).toFixed(1) + '배 <small>(' + md(s.p.d) + ' 종가 ÷ 예상 EPS)</small>');
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
  var TITLE = { change: '기간별 등락', range: '52주 범위', volume: '거래량', cap: '시가총액', earnDate: '실적 발표일', earnings: '실적', valuation: 'EPS · PER · 목표가', tech: '기술 지표', company: '회사 정보', news: '최근 소식' };

  function card(s, c, compact) {
    var list = c.intents.slice();
    /* 맨 위 = 검색한 내용 (2026-11-10 사용자: "엔비디아 실적을 검색했는데 실적이 먼저 안 나온다 — 첫 번째는 검색한 내용, 부가 정보는 그 아래").
       묻은 칸(실적 · EPS …)을 먼저, 주가 한 줄은 그 아래 '오늘 주가'. 종목 이름만 · 주가를 물으면 주가가 곧 답이라 맨 위 */
    var asked = list.filter(function (x) { return x !== 'price'; });
    if (c.why) asked = ['news', 'change'];   // 왜 떨어졌어 → 최근 소식이 먼저
    if (asked.indexOf('earnings') >= 0) asked = asked.filter(function (x) { return x !== 'earnDate'; });
    var priceFirst = !asked.length;
    var extra = priceFirst ? (compact ? ['change'] : ['change', 'valuation', 'earnDate']) : [];   // 종목 이름만 → 요약
    var body = '';
    if (c.why) body += '<p class="as-note">AlphaScope는 등락 이유를 짐작해서 답하지 않습니다. 확인된 숫자와 최근 소식만 모았습니다.</p>';
    if (priceFirst) body += PART.price(s);
    asked.concat(extra).forEach(function (k, i) {
      body += '<div class="as-sec' + (!priceFirst && i === 0 ? ' as-first' : '') + '"><h4>' + TITLE[k] + '</h4>' + PART[k](s, c) + '</div>';
    });
    if (!priceFirst) body += '<div class="as-sec"><h4>오늘 주가</h4>' + PART.price(s) + '</div>';
    return '<article class="as-card">'
      + '<header><span class="as-mkt as-' + s.m + '">' + (s.m === 'us' ? '미국' : '한국') + '</span><h3>' + label(s) + '</h3><span class="as-day">' + md(s.p.d) + ' 종가 기준</span></header>'
      + body
      + '<a class="as-more" href="' + esc(s.u) + '">' + esc(s.n) + ' 종목 페이지에서 자세히 보기 →</a></article>';
  }

  function answer(doc, q, compact) {
    var c = classify(q), stocks = findStocks(doc, q), html = '';
    if (c.advice) html += '<div class="as-notice">AlphaScope는 개별 종목을 사라 · 팔라는 의견을 드리지 않습니다. 판단에 쓸 수 있는 숫자를 모아 드릴게요.</div>';
    if (stocks.length) {
      stocks.forEach(function (s) { html += card(s, c, compact); });
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
  function searchTerm(q, stocks) {   // "엔비디아 실적 알려줘" 를 그대로 넣으면 Blogger 가 못 찾는다 — 종목 이름으로
    if (stocks.length) return stocks[0].n.replace(/\(.*\)/, '');
    return q.replace(/알려\s*줘|알려\s*주세요|어때|뭐야|인가요|있어\??|[?？!]/g, ' ').trim();
  }
  function fillRelated(box, q, stocks, n) {
    var term = searchTerm(q, stocks), all = BLOG + '/search?q=' + encodeURIComponent(term);
    box.innerHTML = '<h4>관련 글 <small>“' + esc(term) + '”</small></h4><p class="as-note">불러오는 중…</p>';
    relatedPosts(term, n).then(function (rows) {
      box.innerHTML = '<h4>관련 글 <small>“' + esc(term) + '”</small></h4>'
        + (rows.length ? '<ul class="as-posts">' + rows.map(function (r) { return '<li><a href="' + esc(r.u) + '">' + esc(r.t) + '</a><span>' + r.d + '</span></li>'; }).join('') + '</ul>'
          : '<p class="as-note">이 말로 찾은 글이 없습니다.</p>')
        + '<a class="as-more" href="' + all + '">블로그에서 더 찾기 →</a>';
    }, function () {
      box.innerHTML = '<h4>관련 글</h4><p class="as-note">글 목록을 불러오지 못했습니다. <a href="' + all + '">블로그 검색으로 보기</a></p>';
    });
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
      + '<button type="button" class="as-x" aria-label="검색 닫기">닫기</button></form>'
      + '<div class="as-search-out">' + chips('as-chips') + '<p class="as-hint">주가 · 등락 · 실적 · EPS · 기술 지표 · 회사 정보를 바로 답하고, 관련 글을 함께 보여 줍니다.</p></div></div>';
    document.body.appendChild(layer);
    var form = layer.querySelector('form'), input = form.q, out = layer.querySelector('.as-search-out');

    function run(q) {
      q = q.trim();
      if (!q) return;
      input.value = q;
      out.innerHTML = '<p class="as-note">찾는 중…</p>';
      loadIndex().then(function (doc) {
        var a = answer(doc, q, false);
        out.innerHTML = '<section class="as-answer">' + a.html + '</section><section class="as-related"></section>';
        fillRelated(out.querySelector('.as-related'), q, a.stocks, 5);
      }, function () {
        out.innerHTML = '<p class="as-note">종목 자료를 불러오지 못했습니다.</p><section class="as-related"></section>';
        fillRelated(out.querySelector('.as-related'), q, [], 5);
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
    fab.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg><span>질문하기</span>';
    var pane = document.createElement('section');
    pane.className = 'as-chat';
    pane.hidden = true;
    pane.setAttribute('aria-label', '질문하기');
    pane.innerHTML = '<header><b>AlphaScope에 물어보기</b><button type="button" class="as-x" aria-label="닫기">닫기</button></header>'
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
    say('bot', '<p>종목 숫자를 물어보세요. 주가 · 등락 · 실적 · EPS · 기술 지표 · 회사 정보를 바로 답해 드립니다.</p>' + chips('as-chips'));

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
    fab.addEventListener('click', function () { pane.hidden = false; fab.hidden = true; loadIndex().catch(function () {}); form.q.focus(); });
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
    if (OPTS.chat !== false) buildChat();
    mountOnSearchPage();
    var q = new URLSearchParams(location.search).get('ask');   // 목업 시험용: ?ask=엔비디아 실적
    if (q) s.open(q);
  }
  window.ASSearch = { classify: classify, findStocks: findStocks, answer: answer, loadIndex: loadIndex };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
