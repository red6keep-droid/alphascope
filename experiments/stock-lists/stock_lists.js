/* 하단 메뉴 `종목` 페이지 /p/stock-lists.html — 기획 비공개 기획/종목-탭-그룹-목록-기획.md, 목업 mock_stock_lists.py.
   본문(publish_stock_lists_page.py)에 탭 뼈대(h2 data-tab 여섯 개 + 빈 칸)가 있고, 테마가 페이지를 열 때 그 h2 로 탭을 만든다. 이 스크립트는 목록 파일을 받아 빈 칸을 채운다.
   - 나라 = 주소 ?m=us|kr(하단 메뉴가 붙임) → 고른 홈(as-home-mkt, 헤더 국기 스위치가 적음) → 미국. 페이지 안 나라 버튼 없음.
   - 목록 파일 = 간단 종목 실행이 매일 올리는 <시장>/_lists.json (build_lists.py). 읽는 순서 Cloudflare Pages → jsDelivr(quick-<시장> 브랜치) → GitHub 원본. 방문자 1명 = 요청 1번 · 압축 약 18KB.
   - 목록은 탭 · 묶음마다 10개 펼침 + 나머지 전부 `n개 더 보기` 접기 (: 하락 12위 SK텔레콤 −13%가 시황엔 있고 여기선 잘려 안 보임.
     옛 11-17 `10개까지, 접기 없음`은 CLAUDE.md `상위 n개만으로 버리지 않는다`와 어긋나 바꿈). 나머지 줄은 버튼을 누를 때 그린다(줄 수천 개를 처음부터 만들지 않게). 줄 전체 = 종목 페이지(테마의 [data-row-link] 장치).
   - 관심 탭 = 이 브라우저에 담은 종목(as-watch, 종목 페이지 제목 옆 ☆ · 검색해서 담기), 없으면 최근 본 종목(as-recent). 로그인 · 서버 없음.
   - 기준일 = 제목 줄 오른쪽(공유 버튼 앞).
   - 2026-11-18 목업 확정분(mock_stock_lists.py)을 옮김: 로고 ~ 이름 11 · 증감 17(삼각형 14) · 가격 = 증감 색 · 한국 보조 줄에 종목 코드 숫자 없음
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
  var TOP = 10;                                  // 10개까지
  var UP = 3, DOWN = -3, VOL = 2, NEAR = -2;     // 오늘 움직임 기준 (기획 2-3)
  var C_UP = '#d93025', C_DOWN = '#1a73e8', C_MUTED = '#9CA3AF', NOTE = '#6B7280';
  var LIST = 'display:block;margin:0 0 8px;border-bottom:1px solid #E2E8F0;';   // 카드 없이 구분선 목록 — 맨 위 선 없음 · 줄 사이 · 맨 끝
  var ROW = 'display:flex;justify-content:space-between;gap:12px;padding:16px 6px;white-space:nowrap;line-height:24px;align-items:flex-start;';   // 구분선 위아래 16(24 − 5 − 3), 첫 줄 위만 21(24 − 3), 좌우 = 왼쪽 기준선 6
  var SEP = 'border-top:1px solid #E2E8F0;';
  var GAP = 11, CHG = 17;                        // 로고 ~ 이름 6 → 11 · 증감 15 → 16 → 17
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
  function dirCol(v) { return v > 0 ? C_UP : v < 0 ? C_DOWN : '#111'; }   // 가격 = 증감과 같은 색
  function subOf(r, tail) { return m === 'kr' ? esc(tail || '') : (tail ? esc(r.t) + ' · ' + esc(tail) : esc(r.t)); }   // 한국 = 종목 코드 숫자 넣지 않음
  function capText(c) {
    if (!c) return '';
    if (m === 'us') return c >= 1e12 ? (c / 1e12).toFixed(2) + '조 달러' : Math.round(c / 1e8).toLocaleString('ko-KR') + '억 달러';
    if (c >= 1e12) return c >= 1e13 ? Math.round(c / 1e12).toLocaleString('ko-KR') + '조 원' : (c / 1e12).toFixed(1) + '조 원';
    return Math.round(c / 1e8).toLocaleString('ko-KR') + '억 원';
  }
  function logo(r) {
    var Z = 35;   // 로고 22 → 44 → 20% 작게 35, 이름 · 보조 줄 두 줄의 세로 가운데
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
      '<span style="font-size:15px;line-height:20px;color:' + dirCol(r.r) + ';">' + esc(price(r)) + '</span></span>';   // 증감 위 · 가격 아래
    return '<span data-row-link="1" data-href="' + esc(href(r)) + '" style="' + ROW + (i ? SEP : 'padding-top:21px;') + '">' + left + right + '</span>';   // 테마 줄 장치가 data-href 로 이동
  }
  var MORE = [], STEP = 10;   // 더 보기 = 누를 때마다 10개씩   // 접힌 나머지 줄 [items, render] — 버튼을 누를 때 그린다
  var MORE_BTN = 'cursor:pointer;display:flex;width:100%;justify-content:center;align-items:center;gap:6px;padding:12px;margin:0;border:0;' + SEP +
    'background:none;color:#111;font:inherit;font-size:14px;line-height:20px;font-weight:700;';   // = design_kit.FOLD_IN_CARD (카드 안 `n개 더 보기 ⌄`)
  var CHEV = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex:none;transition:transform .15s;"><path d="M4 6l4 4 4-4"/></svg>';
  function card(items, render) {
    if (!items.length) return '';
    var more = '';
    if (items.length > TOP) {
      MORE.push([items, render]);
      more = '<span data-sl-rest="' + (MORE.length - 1) + '" style="display:none;"></span>' +
        '<button type="button" data-sl-more="' + (MORE.length - 1) + '" style="' + MORE_BTN + '"><span>' +
        Math.min(STEP, items.length - TOP) + '개 더 보기</span>' + CHEV + '</button>';   // 숫자 = 다음에 펼칠 수(10개씩)
    }
    return '<div data-cards="1" style="margin:0 0 8px;"><span data-list="1" style="' + LIST + '">' +
      items.slice(0, TOP).map(render).join('') + more + '</span></div>';
  }
  document.addEventListener('click', function (e) {   // 목록 칸(#sl-…)은 #as-lists 밖이라 문서에서 받는다 · n개 더 보기 ⌄ ↔ 접기 ⌃ — 펼친 줄은 버튼 위, 버튼은 늘 맨 아래
    var b = e.target.closest && e.target.closest('[data-sl-more]');
    if (!b) return;
    var k = b.getAttribute('data-sl-more'), rest = b.parentNode.querySelector('[data-sl-rest="' + k + '"]');
    if (!rest) return;
    // 누를 때마다 10개씩 그려 붙이고, 끝까지 펴면 `접기` → 처음 TOP 개로
    var x = MORE[+k], total = x[0].length - TOP, n = +(rest.getAttribute('data-n') || 0);
    if (n >= total) {
      rest.innerHTML = ''; rest.setAttribute('data-n', '0'); rest.style.display = 'none';
      b.firstChild.textContent = Math.min(STEP, total) + '개 더 보기'; b.lastChild.style.transform = '';
      var top = b.closest('[data-cards]'); if (top && top.getBoundingClientRect().top < 0) top.scrollIntoView({ block: 'start' });
      return;
    }
    rest.insertAdjacentHTML('beforeend', x[0].slice(TOP + n, TOP + n + STEP).map(function (r, i) { return x[1](r, TOP + n + i); }).join(''));
    n = Math.min(total, n + STEP); rest.setAttribute('data-n', String(n)); rest.style.display = 'block';
    b.firstChild.textContent = n < total ? Math.min(STEP, total - n) + '개 더 보기' : '접기';
    b.lastChild.style.transform = n < total ? '' : 'rotate(180deg)';
  });
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

  /* 히트맵 — 테마 · 업종 묶음 고르기. 칸 = 알약과 같은 data-sl-pill(같은 탭 전환).
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
  function heatmap(key, groups, fix) {   // groups = [[이름, 종목 줄들]] → {board, groups(큰 순), basis}. fix = {묶음 이름: 등락} — 있으면 평균 대신 그 값(미국 업종 = 섹터 ETF)
    var sized = groups.map(function (g) {
      var caps = g[1].filter(function (r) { return r.c; }).map(function (r) { return r.c; });
      var rs = g[1].filter(function (r) { return r.r != null; }).map(function (r) { return r.r; });
      var byCap = caps.length * 2 >= g[1].length;
      return { sz: byCap ? Math.sqrt(caps.reduce(function (t, v) { return t + v; }, 0)) : g[1].length, how: byCap ? 'cap' : 'n',
        n: g[0], xs: g[1], avg: fix && fix[g[0]] != null ? fix[g[0]] : rs.length ? rs.reduce(function (t, v) { return t + v; }, 0) / rs.length : null };
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
      basis: (sized.length && sized[0].how === 'cap' ? '칸 크기 = 시가총액' : '칸 크기 = 종목 수') +
        (fix ? ' · 색 = 업종 ETF 등락률(마지막 종가)' : ' · 색 = 묶음 평균 등락률(마지막 종가)') };
  }

  function byDesc(f) { return function (a, b) { return (f(b) == null ? -1e18 : f(b)) - (f(a) == null ? -1e18 : f(a)); }; }

  function move(rows) {
    var xs = rows.filter(function (r) { return r.r != null; });
    var G = [
      ['상승 종목', function (r) { return r.r >= UP; }, function (r) { return r.r; }, UP + '% 넘게 오른 종목이 없어 많이 오른 순입니다.', null],
      ['하락 종목', function (r) { return r.r <= DOWN; }, function (r) { return -r.r; }, (-DOWN) + '% 넘게 내린 종목이 없어 많이 내린 순입니다.', null],
      ['거래 급증', function (r) { return (r.v || 0) >= VOL; }, function (r) { return r.v; }, '평소의 2배를 넘은 종목이 없어 많이 늘어난 순입니다.',
        function (r) { return '<span style="color:' + NOTE + ';font-size:' + NOTE_PX + 'px;">평소의 ' + r.v.toFixed(1) + '배 · </span>' + pct(r.r); }],   // 말 = 보조 줄 크기 · 색, 증감 = 굵게
      ['52주 최고가 근처', function (r) { return r.h != null && r.h >= NEAR; }, function (r) { return r.h; }, '최고가 2% 안 종목이 없어 가까운 순입니다.',
        function (r) { return r.h >= 0 ? '<span style="color:' + C_UP + ';font-weight:700;">최고가</span>'
          : '<span style="color:' + NOTE + ';font-size:' + NOTE_PX + 'px;">최고가까지 </span><b style="color:' + C_DOWN + ';">' + Math.abs(r.h).toFixed(1) + '%</b>'; }]   // 최고가 = 빨강 굵게, 남은 % = 파랑 굵게
    ];
    var bodies = G.map(function (g) {
      var pool = xs.filter(function (r) { return g[2](r) != null; }).sort(byDesc(g[2]));
      var hit = pool.filter(g[1]);
      var render = function (r, i) { return row(r, i, { right: g[4] ? g[4](r) : null }); };
      return hit.length ? card(hit, render) : card(pool, render) + note(g[3]);   // 탭 · 묶음 줄 바로 아래엔 정보 없음 — 안내는 목록 아래
    });
    return pills('move', G.map(function (g) { return g[0]; })) + panels('move', bodies) +
      note('마지막 종가 기준 · 거래 급증 = 20일 평균의 2배 이상');   // 짧게
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
    return hm.board + panels('theme', bodies) + note(hm.basis);   // 히트맵이 묶음 줄 자리
  }
  function sector(rows, etfs) {   // etfs = 목록 파일 sec_etf(미국만, 업종 11개 ETF 등락) — 증시 시황 업종 줄과 같은 숫자
    var by = {};
    rows.forEach(function (r) { (by[r.s] = by[r.s] || []).push(r); });
    var hm = heatmap('sec', Object.keys(by).map(function (k) { return [k, by[k]]; }), etfs && Object.keys(etfs).length ? etfs : null);
    var bodies = hm.groups.map(function (g) {
      return card(g[1].slice().sort(byDesc(function (r) { return r.c; })), function (r, i) { return row(r, i, { sub: subOf(r, r.c ? capText(r.c) : '') }); });
    });
    return hm.board + panels('sec', bodies) + note(hm.basis);
  }
  function caps(rows) {
    var xs = rows.filter(function (r) { return r.c; }).sort(byDesc(function (r) { return r.c; }));
    return card(xs, function (r, i) { return row(r, i, { rank: i + 1, sub: subOf(r, capText(r.c)) }); });   // `시가총액 상위 10 종목 페이지 →` 줄 삭제 — 여기서 다 본다
  }
  function etf(doc) {
    return card(doc.etf || [], function (r, i) { return row(r, i, { sub: esc(r.s) }); }) + note('지수 · 업종을 따라가는 상품');
  }
  /* ===== 관심 탭 — 로그인 없이 이 브라우저에만 저장(localStorage as-watch). 목업 mock_stock_lists.py 확정분.
     as-watch = [{m:'us'|'kr', t:티커}] 담은 순서 그대로, 미국 · 한국 합쳐 100개. 종목 페이지 제목 옆 ☆(테마 JS)도 같은 칸을 쓴다.
     이 화면 = 들어온 나라(m) 종목만. 담은 것이 없으면 빈 화면 + 이 기기에서 최근 본 종목(as-recent). 서버 · 로그인 · AI 0. */
  var WKEY = 'as-watch', WMAX = 100;
  var INAPP = /KAKAOTALK|NAVER\(inapp|Instagram|FBAN|FBAV|Line\/|DaumApps|everytimeApp|; wv\)/i.test(navigator.userAgent);
  function wLoad() {
    try { var a = JSON.parse(localStorage.getItem(WKEY) || '[]'); return Array.isArray(a) ? a.filter(function (x) { return x && x.t && (x.m === 'us' || x.m === 'kr'); }) : []; }
    catch (e) { return []; }
  }
  function wSave(a) { try { localStorage.setItem(WKEY, JSON.stringify(a)); } catch (e) {} }
  function wKeep() { try { if (navigator.storage && navigator.storage.persist) navigator.storage.persist(); } catch (e) {} }   // 저장 공간이 모자랄 때 지우지 말아 달라는 요청
  var RM = '<button type="button" data-sl-rm aria-label="빼기" style="display:none;flex:none;align-self:center;width:24px;height:24px;margin:0 10px 0 0;padding:0;border:1px solid #F3A6A3;border-radius:50%;box-sizing:border-box;background:#fff;cursor:pointer;"><svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true"><path d="M7 11h8" stroke="#E5484D" stroke-width="1.6" stroke-linecap="round"/></svg></button>';
  var GRIP = '<span data-sl-grip aria-label="끌어서 순서 바꾸기" style="display:none;flex:none;align-self:center;width:32px;height:32px;margin:0 -6px 0 0;align-items:center;justify-content:center;color:#9CA3AF;cursor:grab;touch-action:none;"><svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M4 6.5h12M4 10h12M4 13.5h12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></span>';
  var PLUS = '<span aria-hidden="true" style="flex:none;display:inline-flex;width:22px;height:22px;border-radius:50%;background:#E5E7EB;align-items:center;justify-content:center;"><svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 1.5v9M1.5 6h9" stroke="#4B5563" stroke-width="1.6" stroke-linecap="round"/></svg></span>';
  var LOUPE = '<svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" style="flex:none;display:block;"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>';
  var STAR_PATH = 'M12 3.2l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z';
  function wRow(r) {   // 다른 탭 줄과 같은 모양 + 편집 모드의 빼기(−) · 끌기(≡)
    var h = row(r, 1).replace('<span data-row-link="1"', '<span data-row-link="1" data-sym="' + esc(r.t) + '"');
    h = h.replace('">', '">' + RM.replace('aria-label="빼기"', 'aria-label="' + esc(r.n) + ' 빼기"'));
    h = h.replace('<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;">', '<span data-sl-price style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;">');
    return h.slice(0, -'</span>'.length) + GRIP + '</span>';
  }
  function recentHtml(by) {
    var seen = [];
    try { seen = JSON.parse(localStorage.getItem('as-recent') || '[]') || []; } catch (e) { seen = []; }
    var xs = seen.filter(function (x) { return x && x.m === m && by[x.t]; }).map(function (x) { return by[x.t]; });
    if (!xs.length) return '';
    /* 제목 = 기본형 아이콘(시계, 회색 원 22) + 15/22 굵게, 글자와 6 (가이드라인 8절) · 제목 아래 구분선 · 첫 줄 위아래 16 */
    return '<h3 style="display:flex;align-items:center;gap:6px;font-size:15px;line-height:22px;font-weight:700;color:#111;margin:8px 0 0;padding:0 0 12px 6px;border-bottom:1px solid #E2E8F0;">' +
      '<span aria-hidden="true" style="flex:none;display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#E5E7EB;color:#4B5563;">' +
      '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="display:block;"><circle cx="8" cy="8" r="6"/><path d="M8 4.8V8l2.2 1.4"/></svg></span>' +
      '이 기기에서 최근 본 종목</h3>' + card(xs, function (r, i) { return row(r, i); }).replace('padding-top:21px;', '');
  }
  function a2hsDone() {   // 홈 화면에 추가한 사람 = 홈 화면 앱으로 열었거나(standalone), 설치 창에서 설치함(테마가 as-a2hs-until 을 10년 뒤로 적음). 브라우저 데이터를 지우면 표시도 지워져 안내가 다시 나온다
    try { if ((window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true) return true; } catch (e) {}
    try { return Number(localStorage.getItem('as-a2hs-until') || 0) > Date.now() + 365 * 864e5; } catch (e) { return false; }
  }
  function saveNote() {   // 저장 안내 = 목록 아래 작은 회색 + 아주 작은 `홈 화면에 추가`(테마 window.asA2hs 가 있을 때만). 앱 안 브라우저는 다른 말
    if (a2hsDone()) return '';
    var t = INAPP ? '관심 종목은 이 앱 안에서만 저장됩니다. 브라우저에서 열면 더 오래 남습니다.' : '관심 종목은 이 브라우저에만 저장됩니다. 홈 화면에 추가해 두면 더 오래 남습니다.';
    return '<p data-sl-save style="font-size:13px;line-height:19px;color:' + NOTE + ';margin:4px 0 12px;padding-left:6px;word-break:keep-all;">' + esc(t) +
      '<button type="button" data-sl-a2hs hidden style="display:inline-block;margin:0 0 0 6px;padding:0 7px;border:1px solid #CBD5E1;border-radius:6px;background:#fff;font:inherit;font-size:12px;line-height:18px;font-weight:700;color:#111;vertical-align:baseline;cursor:pointer;">홈 화면에 추가</button></p>';
  }
  function watch(by) {
    var mine = wLoad().filter(function (x) { return x.m === m && by[x.t]; }).map(function (x) { return by[x.t]; });
    var empty = '<div style="text-align:center;padding:32px 6px 24px;"><div style="font-size:17px;line-height:26px;font-weight:400;color:' + NOTE + ';">담은 종목이 없습니다</div>' +
      '<div style="font-size:15px;line-height:24px;color:' + NOTE + ';margin:4px 0 0;word-break:keep-all;">종목을 검색해서 바로 담거나, 종목 페이지 제목 옆 <span style="color:#F5B400;">★</span> 를 누르면 여기에 모입니다.</div>' +
      '<button type="button" data-sl-add style="cursor:pointer;display:flex;justify-content:center;align-items:center;gap:6px;padding:8px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;color:#111;width:100%;box-sizing:border-box;margin:16px 0 0;font:inherit;font-size:15px;line-height:22px;font-weight:700;">' + LOUPE + '종목 검색해서 담기</button></div>';
    var foot = '<div data-sl-foot style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:6px 6px 12px;">' +
      '<button type="button" data-sl-add style="display:inline-flex;align-items:center;gap:8px;padding:8px 0;border:0;background:none;font:inherit;font-size:16px;line-height:24px;font-weight:700;color:#111;cursor:pointer;">' + PLUS + '종목 추가</button>' +
      '<button type="button" data-sl-edit style="padding:8px 0 8px 12px;border:0;background:none;font:inherit;font-size:15px;line-height:22px;color:' + NOTE + ';cursor:pointer;">편집</button></div>';
    var bar = '<div data-sl-bar role="toolbar" aria-label="관심 종목 편집"><button type="button" data-sl-clear class="sl-bar-btn">전체 삭제</button><button type="button" data-sl-done class="sl-bar-btn sl-bar-main">완료</button></div>';
    return '<div data-sl-watch="1"><div data-sl-comp></div>' +
      '<div data-sl-has' + (mine.length ? '' : ' hidden') + '><div data-cards="1" style="margin:0 0 8px;"><span data-list="1" data-sl-list style="' + LIST + '">' + mine.map(wRow).join('') + '</span></div>' + foot + '</div>' +
      '<div data-sl-empty' + (mine.length ? ' hidden' : '') + '>' + empty + recentHtml(by) + '</div>' + saveNote() + '</div>' + bar;
  }
  function watchBind(by) {
    var W = document.querySelector('[data-sl-watch]');
    if (!W || W.getAttribute('data-bound')) return;
    W.setAttribute('data-bound', '1');
    var L = W.querySelector('[data-sl-list]'), body = document.body, cur = '';
    function rowsEl() { return [].slice.call(L.children); }
    function save() {   // 이 나라 줄 순서대로 + 다른 나라 것은 그대로 뒤에
      var here = rowsEl().map(function (x) { return { m: m, t: x.getAttribute('data-sym') }; });
      wSave(here.concat(wLoad().filter(function (x) { return x.m !== m; })));
    }
    function secOf(x) { var r = by[x.getAttribute('data-sym')]; return (r && r.s) || '기타'; }
    function comp() {   // 업종 묶음 줄 `전체 · 기술 · …` (담은 개수 많은 순) — 목업과 같다
      var bx = W.querySelector('[data-sl-comp]'), cnt = {}, ks = [], n = rowsEl().length;
      rowsEl().forEach(function (x) { var k = secOf(x); if (!cnt[k]) { cnt[k] = 0; ks.push(k); } cnt[k]++; });
      ks.sort(function (a, b) { return cnt[b] - cnt[a]; }); if (cur && !cnt[cur]) cur = '';
      if (ks.length < 2) { cur = ''; bx.innerHTML = ''; return; }   // 업종이 둘 이상일 때만 묶음 줄 — 하나뿐이면 `전체`와 같은 목록
      function pill(k, t) { return '<button class="seg" type="button" data-comp="' + esc(k) + '" aria-selected="' + (cur === k) + '">' + t + '</button>'; }
      bx.innerHTML = '<div class="seg-row sl-joined">' + pill('', '전체') + ks.map(function (k) { return pill(k, esc(k)); }).join('') + '</div>';
    }
    function seps() {
      comp();
      var vis = rowsEl().filter(function (x) { var on = !cur || secOf(x) === cur; x.style.display = on ? 'flex' : 'none'; return on; });
      vis.forEach(function (x, i) { x.style.borderTop = i ? '1px solid #E2E8F0' : '0'; x.style.paddingTop = (i ? 16 : 21) + 'px'; });
      var n = rowsEl().length;
      W.querySelector('[data-sl-has]').hidden = !n; W.querySelector('[data-sl-empty]').hidden = !!n;
      if (!n) edit(false);
    }
    W.addEventListener('click', function (e) { var b = e.target.closest('[data-comp]'); if (!b) return; cur = b.getAttribute('data-comp'); seps(); });
    function edit(on) { if (on) body.setAttribute('data-sl-editing', ''); else body.removeAttribute('data-sl-editing'); }
    document.addEventListener('click', function (e) { if (e.target.closest && e.target.closest('.rt-tab')) edit(false); }, true);   // 다른 탭으로 가면 편집 끝
    function toast(msg) { var o = document.querySelector('.sl-toast'); if (o) o.remove(); var d = document.createElement('div'); d.className = 'sl-toast'; d.innerHTML = '<span>' + msg + '</span>'; body.appendChild(d); setTimeout(function () { d.remove(); }, 2600); }
    function held(t) { return wLoad().some(function (x) { return x.m === m && x.t === t; }); }
    function add(t) {
      var r = by[t]; if (!r || held(t)) return;
      if (wLoad().length >= WMAX) { toast('관심 종목은 ' + WMAX + '개까지 담을 수 있습니다'); return; }
      L.insertAdjacentHTML('beforeend', wRow(r)); save(); wKeep(); seps(); toast('관심 종목에 담았습니다');
    }
    function drop(t) { var x = L.querySelector('[data-sym="' + t + '"]'); if (x) x.remove(); save(); seps(); }
    seps();
    /* 길게 누르기(0.5초) · 목록 끝 `편집` = 편집 모드 */
    var T = 0, sx = 0, sy = 0, eat = false;
    W.addEventListener('pointerdown', function (e) {
      if (body.hasAttribute('data-sl-editing')) return; var r = e.target.closest('[data-sl-list] [data-row-link]'); if (!r) return;
      sx = e.clientX; sy = e.clientY; clearTimeout(T);
      T = setTimeout(function () { T = 0; eat = true; r.classList.remove('is-pressed'); edit(true); if (navigator.vibrate) navigator.vibrate(12); }, 500);
    });
    W.addEventListener('pointermove', function (e) { if (T && (Math.abs(e.clientX - sx) > 8 || Math.abs(e.clientY - sy) > 8)) { clearTimeout(T); T = 0; } });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (k) { W.addEventListener(k, function () { if (T) { clearTimeout(T); T = 0; } }); });
    W.addEventListener('contextmenu', function (e) { if (e.target.closest('[data-sl-list]')) e.preventDefault(); });
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (eat && t.closest('[data-sl-list]')) { eat = false; e.preventDefault(); e.stopPropagation(); return; } eat = false;
      var x = t.closest('[data-sl-rm]'); if (x) { e.preventDefault(); e.stopPropagation(); drop(x.closest('[data-sym]').getAttribute('data-sym')); return; }
      if (body.hasAttribute('data-sl-editing') && t.closest('[data-sl-list] [data-row-link]')) { e.preventDefault(); e.stopPropagation(); }
    }, true);
    [].forEach.call(W.querySelectorAll('[data-sl-edit]'), function (b) { b.addEventListener('click', function () { edit(true); }); });
    document.querySelector('[data-sl-done]').addEventListener('click', function () { edit(false); });
    /* 끌어서 순서 바꾸기(≡) */
    L.addEventListener('pointerdown', function (e) {
      var g = e.target.closest('[data-sl-grip]'); if (!g || !body.hasAttribute('data-sl-editing')) return; e.preventDefault();
      var r = g.closest('[data-row-link]'); r.classList.add('sl-drag'); try { g.setPointerCapture(e.pointerId); } catch (_) {}
      function mv(ev) { var after = null, rs = rowsEl(); for (var i = 0; i < rs.length; i++) { if (rs[i] === r) continue; var b = rs[i].getBoundingClientRect(); if (ev.clientY < b.top + b.height / 2) { after = rs[i]; break; } }
        if (after !== r.nextSibling || !after) { L.insertBefore(r, after); seps(); } }
      function up() { r.classList.remove('sl-drag'); save(); g.removeEventListener('pointermove', mv); g.removeEventListener('pointerup', up); g.removeEventListener('pointercancel', up); }
      g.addEventListener('pointermove', mv); g.addEventListener('pointerup', up); g.addEventListener('pointercancel', up);
    });
    /* 팝업 틀 (가이드라인 팝업: 흰 상자 12 · 가림막 · 닫기 네모 32 · 바깥 · Esc) */
    var X = '<svg viewBox="0 0 14 14" width="14" height="14" aria-hidden="true"><path d="M2 2l10 10M12 2 2 12" stroke="#111" stroke-width="2" stroke-linecap="round"/></svg>';
    function pop(title, inner, cls) {
      var o = document.createElement('div'); o.className = 'sl-pop ' + (cls || '');
      o.innerHTML = '<div role="dialog" aria-modal="true"><div class="sl-pop-head"><span>' + title + '</span><button type="button" class="sl-x" aria-label="닫기">' + X + '</button></div><div class="sl-pop-body">' + inner + '</div></div>';
      function close() { o.remove(); document.removeEventListener('keydown', k); } function k(e) { if (e.key === 'Escape') close(); }
      o.addEventListener('click', function (e) { if (e.target === o || e.target.closest('.sl-x')) close(); }); document.addEventListener('keydown', k); body.appendChild(o); o.close = close; return o;
    }
    document.querySelector('[data-sl-clear]').addEventListener('click', function () {
      var n = rowsEl().length; if (!n) return;
      var o = pop('관심 종목을 모두 뺄까요?', '<p style="margin:0 0 18px;font-size:16px;line-height:26px;color:#333;word-break:keep-all;">이 화면 관심 종목 ' + n + '개가 목록에서 빠집니다.</p>' +
        '<div style="display:flex;gap:10px;"><button type="button" class="sl-bar-btn" data-c>취소</button><button type="button" class="sl-bar-btn sl-bar-main" data-ok>모두 빼기</button></div>', 'sl-short');
      o.querySelector('[data-c]').onclick = o.close;
      o.querySelector('[data-ok]').onclick = function () { L.innerHTML = ''; save(); seps(); o.close(); toast('관심 종목을 모두 뺐습니다'); };
    });
    /* 종목 추가 = 검색 팝업(이 나라 목록 파일 안에서), 줄 누르면 ☆ ↔ ★ */
    function star(on) { return '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="' + STAR_PATH + '" fill="' + (on ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>'; }
    function res(r) { var on = held(r.t);
      return '<div class="sl-res" data-s="' + esc(r.t) + '"><span style="flex:none;display:flex;align-items:center;">' + logo(r).replace(/width="35" height="35"/, 'width="28" height="28"').replace(/width:35px;height:35px/g, 'width:28px;height:28px').replace(/line-height:35px/, 'line-height:28px') + '</span>' +
        '<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + esc(r.n) + '</span>' +
        '<span style="display:block;font-size:14px;line-height:20px;color:' + NOTE + ';white-space:nowrap;">' + subOf(r, r.s) + '</span></span>' +
        '<span class="sl-res-star" role="button" aria-pressed="' + on + '" aria-label="' + (on ? '관심 종목에서 빼기' : '관심 종목에 담기') + '">' + star(on) + '</span></div>'; }
    var pool = Object.keys(by).map(function (k) { return by[k]; });
    function find(q) { q = q.trim().toLowerCase(); if (!q) return null; var a = [], b = [];
      pool.forEach(function (r) { var n = String(r.n).toLowerCase(), c = String(r.t).toLowerCase(); if (n.indexOf(q) === 0 || c.indexOf(q) === 0) a.push(r); else if (n.indexOf(q) > 0 || c.indexOf(q) > 0) b.push(r); });
      var k = function (x, y) { return (y.c || 0) - (x.c || 0); }; return a.sort(k).concat(b.sort(k)).slice(0, 30); }
    W.addEventListener('click', function (e) {
      if (!e.target.closest('[data-sl-add]')) return;
      var o = pop('관심 종목 추가', '<input class="sl-q" type="search" placeholder="종목 이름 · 코드" autocomplete="off" enterkeyhint="search"><div data-out></div>', 'sl-top-pop'), q = o.querySelector('.sl-q'), out = o.querySelector('[data-out]');
      function draw() { var xs = find(q.value);
        if (xs === null) { var rc = []; try { rc = (JSON.parse(localStorage.getItem('as-recent') || '[]') || []).filter(function (x) { return x && x.m === m && by[x.t]; }).map(function (x) { return by[x.t]; }); } catch (_) {}
          out.innerHTML = rc.length ? '<div class="sl-res-h">최근 본 종목</div>' + rc.map(res).join('') : ''; return; }
        out.innerHTML = xs.length ? '<div style="height:6px;"></div>' + xs.map(res).join('') : '<p style="margin:18px 0 0;font-size:15px;line-height:22px;color:' + NOTE + ';">찾는 종목이 없습니다.</p>'; }
      q.addEventListener('input', draw); draw(); setTimeout(function () { q.focus(); }, 30);
      out.addEventListener('click', function (ev) { var r = ev.target.closest('.sl-res'); if (!r) return; var t = r.getAttribute('data-s');
        if (held(t)) { drop(t); toast('관심 종목에서 뺐습니다'); } else add(t);
        var now = held(t), st = r.querySelector('.sl-res-star'); st.setAttribute('aria-pressed', now); st.innerHTML = star(now); });
    });
    /* `홈 화면에 추가` — 테마 홈 화면 추가 안내가 있을 때만(폰 · 홈 화면 앱 아님) */
    function a2hs() { var b = W.querySelector('[data-sl-a2hs]'); if (!b || !window.asA2hs || INAPP) return; b.hidden = false; b.onclick = function () { window.asA2hs(); }; }
    if (document.readyState === 'complete') a2hs(); else window.addEventListener('load', a2hs);
    window.addEventListener('appinstalled', function () { var n = W.querySelector('[data-sl-save]'); if (n) n.remove(); });   // 이 화면에서 설치하면 바로 안내를 거둔다
  }
  function dayText(d) {   // 날짜 = 증시 시황 기준 줄과 같은 꼴 `11.19 한국 종가` · `11.18 미국 종가`(미국 = 미국 장 날짜)
    var x = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(d || ''));
    if (!x) return '';
    return Number(x[2]) + '.' + x[3] + (m === 'us' ? ' 미국 종가' : ' 한국 종가');
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

  /* 관심 탭 이름 앞 별 — 탭은 테마가 h2 글자로 만들므로(글자만) 만들어진 뒤 버튼 앞에 그림을 꽂는다.
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
    put('sector', sector(rows, doc.sec_etf));
    put('cap', caps(rows));
    put('etf', etf(doc));
    bind();
    watchBind(by);
    stamp(doc.d);
  }
  function fail() {
    var t = '<p style="font-size:17px;line-height:30px;color:#333;margin:12px 0;padding-left:6px;word-break:keep-all;">잠시 목록을 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요.</p>';   // 옛 안내 = 시총 상위 10 페이지로 — 그 페이지를 없애며 뺌
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
