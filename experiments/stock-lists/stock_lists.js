/* 하단 메뉴 `종목` 페이지 /p/stock-lists.html (2026-11-17 사용자 "1단계 구현 진행해") — 기획 비공개 기획/종목-탭-그룹-목록-기획.md, 목업 mock_stock_lists.py.
   본문(publish_stock_lists_page.py)에 탭 뼈대(h2 data-tab 여섯 개 + 빈 칸)가 있고, 테마가 페이지를 열 때 그 h2 로 탭을 만든다. 이 스크립트는 목록 파일을 받아 빈 칸을 채운다.
   - 나라 = 주소 ?m=us|kr(하단 메뉴가 붙임) → 고른 홈(as-home-mkt, 헤더 국기 스위치가 적음) → 미국. 페이지 안 나라 버튼 없음 (2026-11-17 사용자).
   - 목록 파일 = 간단 종목 실행이 매일 올리는 <시장>/_lists.json (build_lists.py). 읽는 순서 Cloudflare Pages → jsDelivr(quick-<시장> 브랜치) → GitHub 원본. 방문자 1명 = 요청 1번 · 압축 약 18KB.
   - 목록은 탭 · 묶음마다 10개까지, 접기 없음(2026-11-17 사용자). 줄 전체 = 종목 페이지(테마의 [data-row-link] 장치).
   - 관심 탭(1단계) = 이 기기에서 최근 본 종목(테마가 종목 페이지를 열 때 브라우저에 남기는 as-recent). 로그인 · ☆ 담기는 2단계.
   - 기준일 = 제목 줄 오른쪽(공유 버튼 앞).
   - 2026-11-18 목업 확정분(mock_stock_lists.py)을 옮김 (2026-11-19 사용자 "진행해"): 로고 ~ 이름 11 · 증감 17(삼각형 14) · 가격 = 증감 색 · 한국 보조 줄에 종목 코드 숫자 없음
     · 오늘 움직임 오른쪽 말 = 보조 줄 크기 회색 + 숫자 굵게 · 테마 · 업종 묶음 고르기 = 히트맵(칸 크기 = 시가총액 합의 제곱근, 색 = 묶음 평균 등락 4단계).
   목업(로컬): <div id="as-lists" data-local="lists/"> — 같은 폴더의 lists/<시장>/_lists.json 을 읽는다. */
(function () {
  'use strict';
  var root = document.getElementById('as-lists');
  if (!root) return;
  var PAGES = 'https://alpha-scope.pages.dev/';
  var CDN = 'https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@';
  var RAW = 'https://raw.githubusercontent.com/red6keep-droid/alphascope/';
  var LOGO = 'https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/logos/', LOGO_VER = '2';   // design_kit.LOGO_BASE · LOGO_VER
  var TOP = 10;                                  // 10개까지 (2026-11-17 사용자)
  var UP = 3, DOWN = -3, VOL = 2, NEAR = -2;     // 오늘 움직임 기준 (기획 2-3)
  var C_UP = '#d93025', C_DOWN = '#1a73e8', C_MUTED = '#9CA3AF', NOTE = '#6B7280';
  var LIST = 'display:block;margin:0 0 8px;border-bottom:1px solid #E2E8F0;';   // 카드 없이 구분선 목록 (2026-11-17 사용자) — 맨 위 선 없음 · 줄 사이 · 맨 끝
  var ROW = 'display:flex;justify-content:space-between;gap:12px;padding:16px 6px;white-space:nowrap;line-height:24px;align-items:flex-start;';   // 구분선 위아래 16(24 − 5 − 3), 첫 줄 위만 21(24 − 3) (2026-11-17 사용자), 좌우 = 왼쪽 기준선 6
  var SEP = 'border-top:1px solid #E2E8F0;';
  var GAP = 11, CHG = 17;                        // 로고 ~ 이름 6 → 11 · 증감 15 → 16 → 17 (2026-11-18 사용자)
  var NOTE_PX = 14;                              // 보조 줄 글자(dk.TINY)
  var BADGE = [['#2F6F68', '#FFFFFF'], ['#5B6B3A', '#FFFFFF'], ['#86683A', '#FFFFFF']];   // design_kit.BADGE_COLORS

  var m = '';
  try { m = (new URLSearchParams(location.search).get('m') || '').toLowerCase(); } catch (e) { m = ''; }
  if (m !== 'us' && m !== 'kr') { try { m = localStorage.getItem('as-home-mkt') || ''; } catch (e) { m = ''; } }
  if (m !== 'us' && m !== 'kr') m = 'us';
  root.setAttribute('data-m', m);

  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function box(id) { return document.getElementById('sl-' + id); }
  function put(id, html) { var b = box(id); if (b) b.innerHTML = html; }
  function note(t) { return '<p style="font-size:13px;line-height:19px;color:' + NOTE + ';margin:4px 0 12px;padding-left:6px;word-break:keep-all;">' + esc(t) + '</p>'; }
  function line(html) { return '<p style="font-size:15px;line-height:24px;color:#333;margin:0 0 10px;padding-left:6px;word-break:keep-all;">' + html + '</p>'; }

  function price(r) {
    if (m === 'us') return '$' + Number(r.p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return Math.round(r.p).toLocaleString('ko-KR') + '원';
  }
  function pct(v, bold) {
    if (v == null) return '<span style="color:' + C_MUTED + ';">—</span>';
    var col = v > 0 ? C_UP : v < 0 ? C_DOWN : C_MUTED, tri = v > 0 ? '▲' : v < 0 ? '▼' : '';
    return '<span style="color:' + col + ';white-space:nowrap;' + (bold === false ? '' : 'font-weight:700;') + '">' +
      (tri ? '<span style="font-size:' + Math.round(CHG * 0.8) + 'px;vertical-align:1px;margin-right:2px;">' + tri + '</span>' : '') + Math.abs(v).toFixed(2) + '%</span>';
  }
  function dirCol(v) { return v > 0 ? C_UP : v < 0 ? C_DOWN : '#111'; }   // 가격 = 증감과 같은 색 (2026-11-18 사용자)
  function subOf(r, tail) { return m === 'kr' ? esc(tail || '') : (tail ? esc(r.t) + ' · ' + esc(tail) : esc(r.t)); }   // 한국 = 종목 코드 숫자 넣지 않음 (2026-11-18 사용자)
  function capText(c) {
    if (!c) return '';
    if (m === 'us') return c >= 1e12 ? (c / 1e12).toFixed(2) + '조 달러' : Math.round(c / 1e8).toLocaleString('ko-KR') + '억 달러';
    if (c >= 1e12) return c >= 1e13 ? Math.round(c / 1e12).toLocaleString('ko-KR') + '조 원' : (c / 1e12).toFixed(1) + '조 원';
    return Math.round(c / 1e8).toLocaleString('ko-KR') + '억 원';
  }
  function logo(r) {
    var Z = 35;   // 로고 22 → 44 → 20% 작게 35, 이름 · 보조 줄 두 줄의 세로 가운데 (2026-11-17 사용자 "로고 2배 · 미들 정렬")
    var st = 'display:inline-block;width:' + Z + 'px;height:' + Z + 'px;border-radius:50%;vertical-align:0;margin-right:' + GAP + 'px;';
    if (r.lg) return '<img src="' + LOGO + esc(r.lg) + '?v=' + LOGO_VER + '" alt="" width="' + Z + '" height="' + Z + '" loading="lazy" style="' + st + 'background:#fff;object-fit:cover;outline:1px solid #E2E8F0;outline-offset:-1px;">';
    var k = String(r.t), n = 0; for (var i = 0; i < k.length; i++) n += k.charCodeAt(i);
    var c = BADGE[n % BADGE.length];
    return '<span aria-hidden="true" style="' + st + 'line-height:' + Z + 'px;background:' + c[0] + ';color:' + c[1] + ';font-size:15px;font-weight:700;text-align:center;letter-spacing:0;overflow:hidden;">' +
      esc(k.replace(/[-.]/g, '').slice(0, 2)) + '</span>';
  }
  function href(r) { return r.u || ('/p/stock.html?s=' + encodeURIComponent(r.t)); }
  function row(r, i, o) {
    o = o || {};
    var rank = o.rank ? '<span style="flex:none;width:26px;color:' + NOTE + ';font-weight:700;font-size:15px;line-height:24px;">' + o.rank + '</span>' : '';
    var sub = o.sub != null ? o.sub : subOf(r, r.s);
    var left = '<span style="display:flex;align-items:center;min-width:0;flex:1 1 auto;">' + rank +
      '<span style="flex:none;display:flex;align-items:center;">' + logo(r) + '</span>' +
      '<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + esc(r.n) + '</span>' +
      '<span style="display:block;font-size:' + NOTE_PX + 'px;line-height:20px;color:' + NOTE + ';white-space:nowrap;">' + sub + '</span></span></span>';
    var right = '<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;">' +
      '<span style="font-size:' + CHG + 'px;line-height:24px;">' + (o.right != null ? o.right : pct(r.r)) + '</span>' +
      '<span style="font-size:15px;line-height:20px;color:' + dirCol(r.r) + ';">' + esc(price(r)) + '</span></span>';   // 증감 위 · 가격 아래 (2026-11-17 사용자 규칙)
    return '<span data-row-link="1" data-href="' + esc(href(r)) + '" style="' + ROW + (i ? SEP : 'padding-top:21px;') + '">' + left + right + '</span>';   // 테마 줄 장치가 data-href 로 이동
  }
  function card(items, render) {
    if (!items.length) return '';
    return '<div data-cards="1" style="margin:0 0 8px;"><span data-list="1" style="' + LIST + '">' +
      items.slice(0, TOP).map(render).join('') + '</span></div>';
  }
  /* 묶음 줄 = 홈 `테마 종목` 아래 줄(#watch-tabs) 모양 — CSS 는 본문 <style> 의 .sl-joined */
  function pills(key, names) {
    return '<div class="seg-row sl-joined" role="tablist" data-sl-pills="' + key + '">' + names.map(function (n, i) {
      return '<button class="seg" type="button" role="tab" data-sl-pill="' + i + '" aria-selected="' + (i ? 'false' : 'true') + '">' + esc(n) + '</button>';
    }).join('') + '</div>';
  }
  function panels(key, bodies) {
    return bodies.map(function (b, i) { return '<div data-sl-panel="' + key + ':' + i + '"' + (i ? ' hidden' : '') + '>' + b + '</div>'; }).join('');
  }
  function bind() {
    [].forEach.call(document.querySelectorAll('[data-sl-pills]'), function (bar) {
      if (bar.getAttribute('data-bound')) return; bar.setAttribute('data-bound', '1');
      var k = bar.getAttribute('data-sl-pills');
      [].forEach.call(bar.querySelectorAll('[data-sl-pill]'), function (b) {
        b.addEventListener('click', function () {
          var i = b.getAttribute('data-sl-pill');
          [].forEach.call(bar.querySelectorAll('[data-sl-pill]'), function (x) { x.setAttribute('aria-selected', x === b ? 'true' : 'false'); });
          [].forEach.call(document.querySelectorAll('[data-sl-panel^="' + k + ':"]'), function (p) { p.hidden = p.getAttribute('data-sl-panel') !== k + ':' + i; });
        });
      });
    });
  }

  /* 히트맵 — 테마 · 업종 묶음 고르기 (2026-11-18 사용자 "네모난 히트맵이 상단에, 누르면 그 종목들"). 칸 = 알약과 같은 data-sl-pill(같은 탭 전환).
     칸 크기 = 묶음 시가총액 합의 제곱근(시총 값이 절반 넘게 없으면 종목 수, 한 판 안에서 잣대를 섞지 않음) · 최소 판의 4% · 큰 순.
     색 = 묶음 전 종목 하루 등락 단순 평균, 0.1% 미만 보합 · 1 · 2 · 3% 경계 4단계, 글자 = 같은 방향 색. 칸은 하나도 버리지 않는다. */
  var HEAT_W = 360;
  var HEAT_UP = ['#FFF7EE', '#FFECE0', '#FDDDD0', '#F9CBBD'], HEAT_DN = ['#EFF6FF', '#E2EEFE', '#D0E3FD', '#BCD6FB'], HEAT_FLAT = '#F8FAFC';
  var HEAT_FG_UP = [C_UP, C_UP, C_UP, '#B3261E'], HEAT_FG_DN = [C_DOWN, C_DOWN, C_DOWN, '#1558B0'];
  function heatColor(v) {
    if (v == null || Math.abs(v) < 0.1) return [HEAT_FLAT, '#333'];
    var a = Math.abs(v), k = a < 1 ? 0 : a < 2 ? 1 : a < 3 ? 2 : 3;
    return v > 0 ? [HEAT_UP[k], HEAT_FG_UP[k]] : [HEAT_DN[k], HEAT_FG_DN[k]];
  }
  function squarify(vals, x, y, w, h) {   // squarified treemap — vals 는 큰 순, 합 = w*h
    var out = [], i = 0;
    while (i < vals.length) {
      var shortSide = Math.min(w, h), row = [vals[i]];
      var worst = function (r) { var sm = 0, mx = 0; r.forEach(function (v) { sm += v; }); r.forEach(function (v) { mx = Math.max(mx, shortSide * shortSide * v / (sm * sm), (sm * sm) / (shortSide * shortSide * v)); }); return mx; };
      var best = worst(row), j = i + 1;
      while (j < vals.length) { var cand = row.concat([vals[j]]), wc = worst(cand); if (wc > best) break; row = cand; best = wc; j++; }
      var sm = row.reduce(function (t, v) { return t + v; }, 0);
      if (w >= h) { var cw = sm / h, yy = y; row.forEach(function (v) { out.push([x, yy, cw, v / cw]); yy += v / cw; }); x += cw; w -= cw; }
      else { var rh = sm / w, xx = x; row.forEach(function (v) { out.push([xx, y, v / rh, rh]); xx += v / rh; }); y += rh; h -= rh; }
      i = j;
    }
    return out;
  }
  function heatmap(key, groups) {   // groups = [[이름, 종목 줄들]] → {board, groups(큰 순), basis}
    var sized = groups.map(function (g) {
      var caps = g[1].filter(function (r) { return r.c; }).map(function (r) { return r.c; });
      var rs = g[1].filter(function (r) { return r.r != null; }).map(function (r) { return r.r; });
      var byCap = caps.length * 2 >= g[1].length;
      return { sz: byCap ? Math.sqrt(caps.reduce(function (t, v) { return t + v; }, 0)) : g[1].length, how: byCap ? 'cap' : 'n',
        n: g[0], xs: g[1], avg: rs.length ? rs.reduce(function (t, v) { return t + v; }, 0) / rs.length : null };
    });
    if (sized.some(function (t) { return t.how !== sized[0].how; })) sized.forEach(function (t) { t.sz = t.xs.length; t.how = 'n'; });
    var tot0 = sized.reduce(function (t, x) { return t + x.sz; }, 0), floor = 0.04 * tot0;   // 칸 최소 = 판의 4% (2026-11-18)
    sized.forEach(function (t) { t.sz = Math.max(t.sz, floor); });
    sized.sort(function (a, b) { return b.sz - a.sz; });
    var H = sized.length <= 8 ? 240 : 300, tot = sized.reduce(function (t, x) { return t + x.sz; }, 0);
    var rects = squarify(sized.map(function (t) { return t.sz * HEAT_W * H / tot; }), 0, 0, HEAT_W, H);
    var cells = sized.map(function (t, i) {
      var q = rects[i], w = q[2], h = q[3], c = heatColor(t.avg);
      var p = t.avg == null ? '' : (t.avg > 0 ? '▲' : t.avg < 0 ? '▼' : '') + Math.abs(t.avg).toFixed(2) + '%';
      var big = w >= 90 && h >= 64, px = big ? 15 : 13;
      var inner = '<span class="hm-n" style="font-size:' + px + 'px;line-height:' + (px + 5) + 'px;">' + esc(t.n) + '</span>' +
        (h >= 40 && w >= 40 ? '<span class="hm-p" style="font-size:' + (px - 1) + 'px;line-height:' + (px + 3) + 'px;">' + p + '</span>' : '');
      var pos = 'left:' + (q[0] / HEAT_W * 100).toFixed(3) + '%;top:' + (q[1] / H * 100).toFixed(3) + '%;width:' + (w / HEAT_W * 100).toFixed(3) + '%;height:' + (h / H * 100).toFixed(3) + '%;';
      return '<button type="button" class="hm-c" data-sl-pill="' + i + '" aria-selected="' + (i ? 'false' : 'true') + '" aria-label="' + esc(t.n + ' ' + p) + '" style="' +
        pos + 'background:' + c[0] + ';color:' + c[1] + ';--hm-fg:' + c[1] + ';">' + inner + '</button>';
    });
    return { board: '<div class="hm" data-sl-pills="' + key + '" data-sl-heat style="height:' + H + 'px;">' + cells.join('') + '</div>',
      groups: sized.map(function (t) { return [t.n, t.xs]; }),
      basis: (sized.length && sized[0].how === 'cap' ? '칸 크기 = 시가총액' : '칸 크기 = 종목 수') + ' · 색 = 묶음 평균 등락(마지막 종가)' };
  }

  function byDesc(f) { return function (a, b) { return (f(b) == null ? -1e18 : f(b)) - (f(a) == null ? -1e18 : f(a)); }; }

  function move(rows) {
    var xs = rows.filter(function (r) { return r.r != null; });
    var G = [
      ['상승 종목', function (r) { return r.r >= UP; }, function (r) { return r.r; }, UP + '% 넘게 오른 종목이 없어 많이 오른 순입니다.', null],
      ['하락 종목', function (r) { return r.r <= DOWN; }, function (r) { return -r.r; }, (-DOWN) + '% 넘게 내린 종목이 없어 많이 내린 순입니다.', null],
      ['거래 급증', function (r) { return (r.v || 0) >= VOL; }, function (r) { return r.v; }, '평소의 2배를 넘은 종목이 없어 많이 늘어난 순입니다.',
        function (r) { return '<span style="color:' + NOTE + ';font-size:' + NOTE_PX + 'px;">평소의 ' + r.v.toFixed(1) + '배 · </span>' + pct(r.r); }],   // 말 = 보조 줄 크기 · 색, 증감 = 굵게 (2026-11-18 사용자)
      ['52주 최고가 근처', function (r) { return r.h != null && r.h >= NEAR; }, function (r) { return r.h; }, '최고가 2% 안 종목이 없어 가까운 순입니다.',
        function (r) { return r.h >= 0 ? '<span style="color:' + C_UP + ';font-weight:700;">최고가</span>'
          : '<span style="color:' + NOTE + ';font-size:' + NOTE_PX + 'px;">최고가까지 </span><b style="color:' + C_DOWN + ';">' + Math.abs(r.h).toFixed(1) + '%</b>'; }]   // 최고가 = 빨강 굵게, 남은 % = 파랑 굵게 (2026-11-18 사용자)
    ];
    var bodies = G.map(function (g) {
      var pool = xs.filter(function (r) { return g[2](r) != null; }).sort(byDesc(g[2]));
      var hit = pool.filter(g[1]);
      var render = function (r, i) { return row(r, i, { right: g[4] ? g[4](r) : null }); };
      return hit.length ? card(hit, render) : card(pool, render) + note(g[3]);   // 탭 · 묶음 줄 바로 아래엔 정보 없음 — 안내는 목록 아래 (2026-11-17 사용자)
    });
    return pills('move', G.map(function (g) { return g[0]; })) + panels('move', bodies) +
      note('마지막 종가 기준 · 거래 급증 = 20일 평균의 2배 이상');   // 짧게 (2026-11-17 사용자)
  }
  function theme(doc, by) {
    var gs = (doc.themes || []).map(function (g) { return [g[0], g[1].map(function (t) { return by[t]; }).filter(Boolean)]; }).filter(function (g) { return g[1].length; });
    if (!gs.length) return note('묶음을 불러오지 못했습니다.');
    var hm = heatmap('theme', gs);
    gs = hm.groups;
    var bodies = gs.map(function (g) {
      var xs = g[1].slice().sort(byDesc(function (r) { return r.r; }));
      var link = (m === 'us' && ['AI 칩', '메모리', '칩 생산', '반도체 장비', '데이터 센터'].indexOf(g[0]) >= 0)   // 반도체를 넷으로 나눔 (2026-11-19)
        ? '<a href="/p/theme-ai-capex.html" style="display:block;margin:4px 0 12px;padding-left:6px;font-size:15px;line-height:24px;color:#111;font-weight:700;text-decoration:none;">AI 투자 자금 흐름 보기 →</a>' : '';
      return card(xs, function (r, i) { return row(r, i); }) + link;
    });
    return hm.board + panels('theme', bodies) + note(hm.basis);   // 히트맵이 묶음 줄 자리 (2026-11-18 사용자)
  }
  function sector(rows) {
    var by = {};
    rows.forEach(function (r) { (by[r.s] = by[r.s] || []).push(r); });
    var hm = heatmap('sec', Object.keys(by).map(function (k) { return [k, by[k]]; }));
    var bodies = hm.groups.map(function (g) {
      return card(g[1].slice().sort(byDesc(function (r) { return r.c; })), function (r, i) { return row(r, i, { sub: subOf(r, r.c ? capText(r.c) : '') }); });
    });
    return hm.board + panels('sec', bodies) + note(hm.basis);
  }
  function caps(rows) {
    var xs = rows.filter(function (r) { return r.c; }).sort(byDesc(function (r) { return r.c; }));
    return card(xs, function (r, i) { return row(r, i, { rank: i + 1, sub: subOf(r, capText(r.c)) }); }) +
      '<a href="/p/' + m + '-market-cap-top10.html" style="display:block;margin:4px 0 12px;padding-left:6px;font-size:15px;line-height:24px;color:#111;font-weight:700;text-decoration:none;">' +
      (m === 'us' ? '미국' : '한국') + ' 시가총액 상위 10 종목 페이지 →</a>';
  }
  function etf(doc) {
    return card(doc.etf || [], function (r, i) { return row(r, i, { sub: esc(r.s) }); }) + note('지수 · 업종을 따라가는 상품');
  }
  function watch(by) {
    var seen = [];
    try { seen = JSON.parse(localStorage.getItem('as-recent') || '[]') || []; } catch (e) { seen = []; }
    var xs = seen.filter(function (x) { return x && x.m === m && by[x.t]; }).map(function (x) { return by[x.t]; });
    var head = '<h3 style="font-size:17px;line-height:24px;font-weight:700;color:#111;margin:0 0 10px;padding-left:6px;">이 기기에서 최근 본 종목</h3>';
    if (!xs.length) return head + line('아직 본 종목이 없습니다. 종목 페이지를 열면 여기에 최근 본 순서로 남습니다.');
    return head + card(xs, function (r, i) { return row(r, i); }) + note('이 브라우저에만 남습니다');
  }
  function dayText(d) {
    var x = new Date(d + 'T00:00:00Z');
    if (isNaN(x)) return '';
    if (m === 'us') x = new Date(x.getTime() + 864e5);   // 미국 종가 = 한국 다음 날 새벽 (design_kit.kst_close_day)
    return (x.getUTCMonth() + 1) + '월 ' + x.getUTCDate() + '일' + (m === 'us' ? ' 새벽 마감 기준' : ' 종가 기준');
  }
  function stamp(d) {
    var t = dayText(d);
    if (!t) return;
    function go() {
      if (document.querySelector('.sl-title-day')) return;
      var meta = document.querySelector('.post-title .post-title-meta');
      var sp = document.createElement('span'); sp.className = 'sl-title-day'; sp.textContent = t;
      if (meta) meta.insertBefore(sp, meta.firstChild);
      else { var b = box('day'); if (b) { b.appendChild(sp); b.hidden = false; } }   // 제목 줄을 못 찾으면 본문 맨 위
    }
    if (document.readyState === 'complete') go(); else window.addEventListener('load', go);
  }

  /* 관심 탭 이름 앞 별 (2026-11-19 사용자) — 탭은 테마가 h2 글자로 만들므로(글자만) 만들어진 뒤 버튼 앞에 그림을 꽂는다.
     글자(textContent)는 그대로라 #tab-관심 이름 찾기에 영향 없음. 별 모양 · 색 = 종목 제목 옆 담긴 별(mock_stock_lists STAR · STAR_PATH) */
  (function tabStar() {
    var tries = 0;
    function go() {
      var hit = [].filter.call(document.querySelectorAll('.post-body .rt-tab'), function (b) { return b.textContent === '관심'; })[0];
      if (!hit) { if (++tries < 20) setTimeout(go, 150); return; }
      if (hit.querySelector('.sl-tab-star')) return;
      hit.insertAdjacentHTML('afterbegin', '<svg class="sl-tab-star" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
        '<path d="M12 3.2l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z" fill="#F5B400" stroke="#F5B400" stroke-width="1.8" stroke-linejoin="round"/></svg>');
    }
    if (document.readyState === 'complete') go(); else window.addEventListener('load', go);
  })();

  function render(doc) {
    var rows = doc.rows || [], by = {};
    rows.concat(doc.etf || []).forEach(function (r) { by[r.t] = r; });
    put('watch', watch(by));
    put('move', move(rows));
    put('theme', theme(doc, by));
    put('sector', sector(rows));
    put('cap', caps(rows));
    put('etf', etf(doc));
    bind();
    stamp(doc.d);
  }
  function fail() {
    var t = '<p style="font-size:17px;line-height:30px;color:#333;margin:12px 0;padding-left:6px;word-break:keep-all;">잠시 목록을 불러오지 못했습니다. ' +
      '<a href="/p/' + m + '-market-cap-top10.html" style="color:#111;">' + (m === 'us' ? '미국' : '한국') + ' 시가총액 상위 10 종목</a>을 먼저 보세요.</p>';
    ['watch', 'move', 'theme', 'sector', 'cap', 'etf'].forEach(function (k) { put(k, t); });
  }

  var local = root.getAttribute('data-local');
  var urls = local ? [local + m + '/_lists.json']
    : [PAGES + m + '/_lists.json', CDN + 'quick-' + m + '/' + m + '/_lists.json', RAW + 'quick-' + m + '/' + m + '/_lists.json'];
  (function next(i) {
    if (i >= urls.length) return fail();
    fetch(urls[i], { cache: 'default' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (doc) { if (!doc || !doc.rows || !doc.rows.length) throw new Error('empty'); render(doc); })
      .catch(function () { next(i + 1); });
  })(0);
})();
