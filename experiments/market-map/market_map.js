/* Newfact 시장 지도 — 네모 칸 지도(업종 칸 안에 종목 칸)를 캔버스에 그리고 손가락으로 확대 · 축소 (2026-11-22 사용자: "3D 는 아니더라도 확대 · 축소 정도" → 목업 먼저).
   - 자료 = 종목 목록 파일 <시장>/_lists.json 의 rows(build_lists.py — 이미 매일 올리는 것). 새 수집 · AI 0. 방문자 1명 = 요청 1번(목업은 페이지 안에 넣어 둠).
   - 칸 크기 = 시가총액 · 색 = 고른 재료 하나(오늘 등락 / 지수 대비 / 거래량). 재료를 하나의 점수로 합치지 않는다(헌법 제1조 — 갈리면 갈린 채로, 누른 종목 창에 나란히).
   - 전체 화면 = 화면을 덮는 층(아이폰 사파리는 영상 밖 전체 화면이 없다 — 봉차트 전체 화면과 같은 방식). 뒤로 가기 = 닫기.
   쓰기: data-market-map 칸 안에 application/json 스크립트로 자료를 넣는다(정식 때는 data-src 주소로 받기). */
(function () {
  'use strict';
  var UP = '#d93025', DOWN = '#1a73e8', HOT = '#F59E0B', FLAT = '#E8ECF1', INK = '#111', SUB = '#6B7280';
  var LOGO = 'https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/logos/', LOGO_VER = '2';
  var BLOG = 'https://www.newfact.app';
  var FONT = "'AS Num','Noto Sans KR',system-ui,-apple-system,sans-serif";
  var LIMIT = 3, KMAX = 16, CHIP_H = 20, PREVIEW_H = 320;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function hex(c) { return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)]; }
  function mix(a, b, t) { a = hex(a); b = hex(b); return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * t); }).join(',') + ')'; }
  function sign(v, unit) { if (v == null) return ''; var a = Math.abs(v).toFixed(1); if (a === '0.0') return '0.0' + unit; return (v > 0 ? '▲' : '▼') + a + unit; }
  function dirColor(v) { return v == null || Math.abs(v) < 0.05 ? INK : v > 0 ? UP : DOWN; }

  /* ── 네모 칸 나누기(squarified treemap) ── items[].val 넓이 비율 → x · y · w · h */
  function squarify(items, x, y, w, h) {
    var total = 0, i;
    for (i = 0; i < items.length; i++) total += items[i].val;
    if (!(total > 0) || w <= 0 || h <= 0) return;
    var sc = w * h / total, list = items.map(function (it) { return { it: it, a: it.val * sc }; });
    function worst(row, side) {
      var s = 0, mx = 0, mn = Infinity;
      row.forEach(function (r) { s += r.a; if (r.a > mx) mx = r.a; if (r.a < mn) mn = r.a; });
      return Math.max(side * side * mx / (s * s), s * s / (side * side * mn));
    }
    function place(row) {
      var s = 0; row.forEach(function (r) { s += r.a; });
      if (w >= h) {
        var cw = s / h, cy = y;
        row.forEach(function (r) { var ch = r.a / cw; r.it.x = x; r.it.y = cy; r.it.w = cw; r.it.h = ch; cy += ch; });
        x += cw; w -= cw;
      } else {
        var rh = s / w, cx = x;
        row.forEach(function (r) { var c2 = r.a / rh; r.it.x = cx; r.it.y = y; r.it.w = c2; r.it.h = rh; cx += c2; });
        y += rh; h -= rh;
      }
    }
    var row = []; i = 0;
    while (i < list.length) {
      var side = Math.min(w, h), nx = list[i];
      if (!row.length || worst(row.concat([nx]), side) <= worst(row, side)) { row.push(nx); i++; }
      else { place(row); row = []; }
    }
    if (row.length) place(row);
  }

  /* ── 자료 정리 ── 업종마다 묶고 시가총액 가중 평균 */
  function prepare(data) {
    var by = {}, secs = [];
    data.rows.forEach(function (r) {
      if (!(r.c > 0) || r.r == null || !r.s) return;
      if (!by[r.s]) { by[r.s] = { name: r.s, rows: [], val: 0, sum: 0, up: 0, down: 0 }; secs.push(by[r.s]); }
      var g = by[r.s];
      r.val = r.c; r.sec = g; r.hi = r.h;   /* 칸 나누기가 x · y · w · h 를 덮어쓴다 — 52주 최고가 대비는 hi 로 옮겨 둔다 */ g.rows.push(r); g.val += r.c; g.sum += r.c * r.r;
      if (r.r > 0.05) g.up++; else if (r.r < -0.05) g.down++;
    });
    secs.forEach(function (g) { g.avg = g.sum / g.val; g.rows.sort(function (a, b) { return b.val - a.val; }); });
    secs.sort(function (a, b) { return b.val - a.val; });
    return secs;
  }

  var MODES = [
    { key: 'day', label: '오늘 등락', unit: '%', lo: '▼' + LIMIT + '%', hi: '▲' + LIMIT + '%', what: '전날 종가와 견준 오늘 등락률' },
    { key: 'rel', label: null, unit: '%p', lo: '▼' + LIMIT + '%p', hi: '▲' + LIMIT + '%p', what: null },
    { key: 'vol', label: '거래량', unit: '배', lo: '평소', hi: '3배', what: '직전 20거래일 평균 거래량과 견준 오늘 거래량' }
  ];

  function MarketMap(root, data) {
    this.root = root; this.data = data; this.secs = prepare(data);
    this.bench = data.bench || { n: '시장', r: 0 };
    this.mode = 'day'; this.sel = null; this.full = false;
    this.k = 1; this.tx = 0; this.ty = 0; this.W = 0; this.H = 0;
    this.tw = {}; this.raf = 0;
    MODES[1].label = this.bench.n + ' 대비'; MODES[1].what = this.bench.n + '(' + sign(this.bench.r, '%') + ')와 견준 차이';
    this.buildInline();
  }
  var P = MarketMap.prototype;

  P.value = function (r) { return this.mode === 'day' ? r.r : this.mode === 'rel' ? r.r - this.bench.r : r.v; };
  P.secValue = function (g) { return this.mode === 'rel' ? g.avg - this.bench.r : g.avg; };
  P.paint = function (r) {   // [바탕, 글자]
    var v = this.value(r), t;
    if (v == null) return [FLAT, INK];
    if (this.mode === 'vol') { t = Math.max(0, Math.min(1, (v - 1) / 2)); return [mix(FLAT, HOT, t), INK]; }
    if (Math.abs(v) < 0.05) return [FLAT, INK];
    t = Math.min(1, Math.abs(v) / LIMIT);
    return [mix(FLAT, v > 0 ? UP : DOWN, 0.18 + 0.82 * t), t > 0.42 ? '#fff' : INK];
  };
  P.cellText = function (r) { var v = this.value(r); if (v == null) return ''; return this.mode === 'vol' ? v.toFixed(1) + '배' : sign(v, this.mode === 'rel' ? '%p' : '%'); };

  /* ── 페이지 안 작은 지도 + 전체 화면 버튼 ── */
  P.buildInline = function () {
    var self = this, box = document.createElement('div');
    box.style.cssText = 'position:relative;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;background:#fff;';
    this.inlineBox = box;
    this.modeBar = this.makeModes(); this.modeBar.style.padding = '10px 10px 8px';
    this.cv = document.createElement('canvas');
    this.cv.style.cssText = 'display:block;width:100%;height:' + PREVIEW_H + 'px;cursor:pointer;touch-action:pan-y;';
    this.cv.setAttribute('role', 'img'); this.cv.setAttribute('aria-label', '업종과 종목을 시가총액 크기 칸으로 그린 지도. 아래 업종 목록에 같은 내용이 글로 있습니다.');
    this.legend = document.createElement('div');
    this.legend.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 10px;font-size:13px;line-height:19px;color:' + SUB + ';';
    this.fullBtn = document.createElement('button'); this.fullBtn.type = 'button';
    this.fullBtn.style.cssText = 'display:flex;justify-content:center;align-items:center;gap:6px;width:100%;min-height:44px;margin:8px 0 0;padding:8px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;color:#111;font:700 14px/20px ' + FONT + ';cursor:pointer;-webkit-tap-highlight-color:transparent;';
    this.fullBtn.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/></svg><span>전체 화면으로 크게 보기</span>';
    box.appendChild(this.modeBar); box.appendChild(this.cv); box.appendChild(this.legend);
    this.root.appendChild(box); this.root.appendChild(this.fullBtn);
    this.cv.addEventListener('click', function () { if (!self.full) self.open(); });
    this.fullBtn.addEventListener('click', function () { self.open(); });
    window.addEventListener('resize', function () { self.fit(); });
    window.addEventListener('popstate', function () { if (self.full) self.close(true); });
    this.bindGestures();
    this.syncModes(); this.fit();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { self.tw = {}; self.draw(); });
  };

  P.makeModes = function () {
    var self = this, bar = document.createElement('div');
    bar.style.cssText = 'display:flex;gap:6px;';
    MODES.forEach(function (m) {
      var b = document.createElement('button'); b.type = 'button'; b.setAttribute('data-mode', m.key); b.textContent = m.label;
      b.style.cssText = 'flex:1 1 0;min-width:0;min-height:36px;padding:6px 4px;border-radius:8px;border:1px solid #E2E8F0;background:#fff;color:#333;font:600 14px/20px ' + FONT + ';cursor:pointer;white-space:nowrap;-webkit-tap-highlight-color:transparent;';
      b.addEventListener('click', function (e) { e.stopPropagation(); self.mode = m.key; self.syncModes(); self.draw(); if (self.sel) self.showSheet(self.sel); });
      bar.appendChild(b);
    });
    return bar;
  };
  P.syncModes = function () {
    var self = this, m = MODES.filter(function (x) { return x.key === self.mode; })[0];
    [].forEach.call(this.modeBar.querySelectorAll('button'), function (b) {
      var on = b.getAttribute('data-mode') === self.mode;
      b.style.background = on ? '#111' : '#fff'; b.style.color = on ? '#fff' : '#333'; b.style.borderColor = on ? '#111' : '#E2E8F0';
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    var grad = this.mode === 'vol' ? 'linear-gradient(90deg,' + FLAT + ',' + HOT + ')' : 'linear-gradient(90deg,' + DOWN + ',' + FLAT + ',' + UP + ')';
    this.legend.innerHTML = '<span style="flex:none;white-space:nowrap;">' + m.lo + '</span><span style="flex:none;width:72px;height:8px;border-radius:4px;background:' + grad + ';"></span><span style="flex:none;white-space:nowrap;">' + m.hi + '</span>'
      + '<span style="flex:1 1 auto;min-width:0;text-align:right;word-break:keep-all;">칸 크기는 시가총액</span>';
    if (this.what) this.what.textContent = '색은 ' + m.what + '입니다.';
  };

  /* ── 크기 맞추기 · 칸 나누기 ── */
  P.fit = function () {
    var r = this.cv.getBoundingClientRect(), W = Math.round(r.width), H = Math.round(r.height), dpr = window.devicePixelRatio || 1;
    if (!W || !H) return;
    this.cv.width = W * dpr; this.cv.height = H * dpr; this.dpr = dpr;
    if (W !== this.W || H !== this.H) {
      this.W = W; this.H = H; this.k = 1; this.tx = 0; this.ty = 0;
      squarify(this.secs, 0, 0, W, H);
      this.secs.forEach(function (g) { squarify(g.rows, g.x, g.y, g.w, g.h); });
    }
    this.draw();
  };
  P.clamp = function () {
    this.k = Math.max(1, Math.min(KMAX, this.k));
    this.tx = Math.min(0, Math.max(this.W - this.W * this.k, this.tx));
    this.ty = Math.min(0, Math.max(this.H - this.H * this.k, this.ty));
  };
  P.zoomAt = function (px, py, f) {
    var k0 = this.k, k1 = Math.max(1, Math.min(KMAX, k0 * f));
    this.tx = px - (px - this.tx) * k1 / k0; this.ty = py - (py - this.ty) * k1 / k0; this.k = k1;
    this.clamp(); this.draw(); this.touched();
  };
  P.zoomTo = function (g) {   // 업종 하나가 화면에 꽉 차게
    var k = Math.max(1, Math.min(KMAX, Math.min(this.W / g.w, this.H / g.h) * 0.96));
    this.animate(k, this.W / 2 - (g.x + g.w / 2) * k, this.H / 2 - (g.y + g.h / 2) * k);
  };
  P.animate = function (k, tx, ty) {
    var self = this, k0 = this.k, x0 = this.tx, y0 = this.ty, t0 = null;
    function step(ts) {
      if (t0 === null) t0 = ts;
      var t = Math.min(1, (ts - t0) / 260), e = 1 - Math.pow(1 - t, 3);
      self.k = k0 + (k - k0) * e; self.tx = x0 + (tx - x0) * e; self.ty = y0 + (ty - y0) * e;
      self.clamp(); self.render();
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step); this.touched();
  };
  P.draw = function () { var self = this; if (this.raf) return; this.raf = requestAnimationFrame(function () { self.raf = 0; self.render(); }); };

  P.textW = function (ctx, s, fs) { var key = fs + '|' + s, w = this.tw[key]; if (w == null) { w = this.tw[key] = ctx.measureText(s).width; } return w; };
  P.fitText = function (ctx, s, fs, max) {
    if (this.textW(ctx, s, fs) <= max) return s;
    for (var n = s.length - 1; n >= 2; n--) { var t = s.slice(0, n) + '…'; if (this.textW(ctx, t, fs) <= max) return t; }
    return '';
  };

  P.render = function () {
    var ctx = this.cv.getContext('2d'), k = this.k, tx = this.tx, ty = this.ty, W = this.W, H = this.H, self = this;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H);
    ctx.textBaseline = 'middle';
    // 업종 이름표 자리 먼저 — 그 아래 칸은 글자를 이름표 밑으로 내린다
    this.secs.forEach(function (g) {
      var x0 = Math.round(g.x * k + tx), y0 = Math.round(g.y * k + ty), x1 = Math.round((g.x + g.w) * k + tx), y1 = Math.round((g.y + g.h) * k + ty);
      g.sx = x0; g.sy = y0; g.sw = x1 - x0; g.sh = y1 - y0; g.chip = null;
      if (x1 <= 0 || y1 <= 0 || x0 >= W || y0 >= H || g.sw < 44 || g.sh < CHIP_H + 4) return;
      ctx.font = '700 12px ' + FONT;
      var val = self.mode === 'vol' ? '' : sign(self.secValue(g), self.mode === 'rel' ? '%p' : '%'), nm = self.fitText(ctx, g.name, 12, g.sw - 14);
      if (!nm) return;
      var wn = self.textW(ctx, nm, 12), wv = self.textW(ctx, val, 12), withVal = !!val && wn + 6 + wv + 12 <= g.sw - 2;
      var cw = Math.ceil(wn + (withVal ? 6 + wv : 0) + 12);
      g.chip = { x: Math.max(x0, Math.min(0, x1 - cw - 2)), y: Math.max(y0, Math.min(0, y1 - CHIP_H - 2)), w: cw, h: CHIP_H, nm: nm, val: withVal ? val : '', wn: wn };
    });
    this.secs.forEach(function (g) {
      if (g.sx + g.sw <= 0 || g.sy + g.sh <= 0 || g.sx >= W || g.sy >= H) return;
      g.rows.forEach(function (r) {
        var x0 = Math.round(r.x * k + tx), y0 = Math.round(r.y * k + ty), x1 = Math.round((r.x + r.w) * k + tx), y1 = Math.round((r.y + r.h) * k + ty);
        if (x1 <= 0 || y1 <= 0 || x0 >= W || y0 >= H) return;
        var w = x1 - x0 - 1, h = y1 - y0 - 1;
        if (w < 1 || h < 1) { w = Math.max(w, 1); h = Math.max(h, 1); }
        var c = self.paint(r);
        ctx.fillStyle = c[0]; ctx.fillRect(x0, y0, w, h);
        // 글자 — 칸이 넉넉할 때만. 업종 이름표와 겹치면 그 아래로
        var ty0 = y0, th = h, ch = g.chip;
        if (ch && x0 < ch.x + ch.w && x0 + w > ch.x && y0 < ch.y + ch.h && y0 + h > ch.y) { ty0 = ch.y + ch.h; th = y0 + h - ty0; }
        // 크게 키워 칸이 화면 밖으로 나가면 보이는 부분의 가운데에 적는다
        var vx0 = Math.max(x0, 0), vx1 = Math.min(x0 + w, W), vy0 = Math.max(ty0, 0), vy1 = Math.min(ty0 + th, H), vw = vx1 - vx0, vh = vy1 - vy0;
        if (vw < 34 || vh < 16) return;
        var big = vw >= 120 && vh >= 64, mid = vw >= 60 && vh >= 38, fs = big ? 16 : mid ? 13 : 11, vs = big ? 14 : 12;
        ctx.font = '700 ' + fs + 'px ' + FONT;
        var nm = self.fitText(ctx, r.n, fs, vw - 8);
        if (!nm) return;
        var two = mid || big, cx = vx0 + vw / 2, cy = vy0 + vh / 2;
        ctx.fillStyle = c[1]; ctx.textAlign = 'center';
        ctx.fillText(nm, cx, two ? cy - Math.round(vs / 2) - 1 : cy);
        if (two) { ctx.font = '500 ' + vs + 'px ' + FONT; ctx.fillText(self.cellText(r), cx, cy + Math.round(fs / 2) + 2); }
      });
    });
    // 업종 경계(흰 3px) · 이름표
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 3;
    this.secs.forEach(function (g) { ctx.strokeRect(g.sx - 0.5, g.sy - 0.5, g.sw, g.sh); });
    ctx.textAlign = 'left';
    this.secs.forEach(function (g) {
      var ch = g.chip; if (!ch) return;
      ctx.fillStyle = 'rgba(17,17,17,0.86)'; ctx.fillRect(ch.x + 1, ch.y + 1, ch.w, ch.h);
      ctx.font = '700 12px ' + FONT; ctx.fillStyle = '#fff'; ctx.fillText(ch.nm, ch.x + 7, ch.y + 1 + ch.h / 2 + 1);
      if (ch.val) { ctx.font = '500 12px ' + FONT; ctx.fillStyle = '#E5E7EB'; ctx.fillText(ch.val, ch.x + 7 + ch.wn + 6, ch.y + 1 + ch.h / 2 + 1); }
    });
    if (this.sel && this.full) {
      var r = this.sel;
      ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
      ctx.strokeRect(Math.round(r.x * k + tx) + 1, Math.round(r.y * k + ty) + 1, Math.max(2, Math.round(r.w * k) - 3), Math.max(2, Math.round(r.h * k) - 3));
    }
    if (this.zoomLabel) this.zoomLabel.textContent = (Math.round(k * 10) / 10) + '배';
  };

  /* ── 손가락 · 마우스 ── 전체 화면에서만 */
  P.bindGestures = function () {
    var self = this, cv = this.cv, pts = {}, n = 0, start = null, pinch = null, moved = false;
    function pos(e) { var b = cv.getBoundingClientRect(); return { x: e.clientX - b.left, y: e.clientY - b.top }; }
    cv.addEventListener('pointerdown', function (e) {
      if (!self.full) return;
      cv.setPointerCapture(e.pointerId); pts[e.pointerId] = pos(e); n = Object.keys(pts).length;
      if (n === 1) { start = { x: pts[e.pointerId].x, y: pts[e.pointerId].y, tx: self.tx, ty: self.ty, t: Date.now() }; moved = false; }
      if (n === 2) { var a = Object.keys(pts).map(function (i) { return pts[i]; }); pinch = { d: Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y), k: self.k, tx: self.tx, ty: self.ty, mx: (a[0].x + a[1].x) / 2, my: (a[0].y + a[1].y) / 2 }; moved = true; }
    });
    cv.addEventListener('pointermove', function (e) {
      if (!self.full || !pts[e.pointerId]) return;
      pts[e.pointerId] = pos(e);
      var a = Object.keys(pts).map(function (i) { return pts[i]; });
      if (a.length >= 2 && pinch) {
        var d = Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y), mx = (a[0].x + a[1].x) / 2, my = (a[0].y + a[1].y) / 2;
        var k1 = Math.max(1, Math.min(KMAX, pinch.k * d / (pinch.d || 1)));
        self.k = k1; self.tx = mx - (pinch.mx - pinch.tx) * k1 / pinch.k; self.ty = my - (pinch.my - pinch.ty) * k1 / pinch.k;
        self.clamp(); self.draw(); self.touched();
      } else if (a.length === 1 && start) {
        var dx = a[0].x - start.x, dy = a[0].y - start.y;
        if (Math.abs(dx) + Math.abs(dy) > 8) moved = true;
        if (moved) { self.tx = start.tx + dx; self.ty = start.ty + dy; self.clamp(); self.draw(); }
      }
    });
    function up(e) {
      if (!pts[e.pointerId]) return;
      var p = pts[e.pointerId]; delete pts[e.pointerId]; n = Object.keys(pts).length;
      if (n === 1) { var id = Object.keys(pts)[0]; start = { x: pts[id].x, y: pts[id].y, tx: self.tx, ty: self.ty, t: 0 }; pinch = null; }
      if (n === 0) { if (!moved && start && Date.now() - start.t < 400 && e.type === 'pointerup') self.tap(p.x, p.y); start = null; pinch = null; }
    }
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('wheel', function (e) { if (!self.full) return; e.preventDefault(); var p = pos(e); self.zoomAt(p.x, p.y, Math.exp(-e.deltaY * 0.0022)); }, { passive: false });
  };
  P.tap = function (px, py) {
    var i, j, g, r, ch;
    for (i = 0; i < this.secs.length; i++) { ch = this.secs[i].chip; if (ch && px >= ch.x && px <= ch.x + ch.w + 8 && py >= ch.y && py <= ch.y + ch.h + 8) { this.hideSheet(); this.zoomTo(this.secs[i]); return; } }
    var wx = (px - this.tx) / this.k, wy = (py - this.ty) / this.k;
    for (i = 0; i < this.secs.length; i++) {
      g = this.secs[i]; if (wx < g.x || wx > g.x + g.w || wy < g.y || wy > g.y + g.h) continue;
      for (j = 0; j < g.rows.length; j++) { r = g.rows[j]; if (wx >= r.x && wx <= r.x + r.w && wy >= r.y && wy <= r.y + r.h) { this.showSheet(r); return; } }
    }
    this.hideSheet();
  };
  P.touched = function () { if (this.hint) { this.hint.style.display = 'none'; } };

  /* ── 전체 화면(덮는 층) ── */
  P.open = function () {
    if (this.full) return;
    var self = this, ov = document.createElement('div');
    this.full = true; this.ov = ov;
    ov.style.cssText = 'position:fixed;left:0;top:0;right:0;bottom:0;z-index:2147483000;background:#fff;display:flex;flex-direction:column;font-family:' + FONT + ';color:#111;';
    ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-label', this.data.title);
    var head = document.createElement('div');
    head.style.cssText = 'flex:none;display:flex;align-items:center;gap:8px;padding:8px 10px 0 14px;';
    head.innerHTML = '<b style="flex:1 1 auto;min-width:0;font-size:19px;line-height:28px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + esc(this.data.title) + '</b>'
      + '<span style="flex:none;font-size:13px;line-height:19px;color:' + SUB + ';white-space:nowrap;">' + esc(this.data.asof) + '</span>';
    var x = document.createElement('button'); x.type = 'button'; x.setAttribute('aria-label', '닫기');
    x.style.cssText = 'flex:none;display:flex;align-items:center;justify-content:center;width:32px;height:32px;margin:6px 0 6px 4px;padding:0;border:1px solid #CBD5E1;border-radius:6px;background:#fff;color:#111;cursor:pointer;';
    x.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></svg>';
    x.addEventListener('click', function () { self.close(); });
    head.appendChild(x);
    this.what = document.createElement('div');
    this.what.style.cssText = 'flex:none;padding:0 14px 8px;font-size:13px;line-height:19px;color:' + SUB + ';word-break:keep-all;';
    this.modeBar.style.padding = '0 10px 8px'; this.modeBar.style.flex = 'none';
    var stage = document.createElement('div');
    stage.style.cssText = 'position:relative;flex:1 1 auto;min-height:0;overflow:hidden;background:#fff;';
    this.cv.style.height = '100%'; this.cv.style.touchAction = 'none'; this.cv.style.cursor = 'grab';
    this.legend.style.flex = 'none';
    // 확대 · 축소 · 처음으로
    var ctl = document.createElement('div');
    ctl.style.cssText = 'position:absolute;right:10px;bottom:10px;display:flex;flex-direction:column;border:1px solid #CBD5E1;border-radius:8px;background:#fff;overflow:hidden;box-shadow:0 2px 8px rgba(15,23,42,.14);';
    [['확대', '<path d="M8 3.5v9M3.5 8h9"/>', function () { self.zoomAt(self.W / 2, self.H / 2, 1.6); }],
     ['축소', '<path d="M3.5 8h9"/>', function () { self.zoomAt(self.W / 2, self.H / 2, 1 / 1.6); }],
     ['처음 크기로', '<path d="M3 8a5 5 0 1 0 1.6-3.7M3 2.8v2.8h2.8"/>', function () { self.hideSheet(); self.animate(1, 0, 0); }]].forEach(function (d, i) {
      var b = document.createElement('button'); b.type = 'button'; b.setAttribute('aria-label', d[0]);
      b.style.cssText = 'display:flex;align-items:center;justify-content:center;width:44px;height:44px;padding:0;border:0;' + (i ? 'border-top:1px solid #E2E8F0;' : '') + 'background:#fff;color:#111;cursor:pointer;-webkit-tap-highlight-color:transparent;';
      b.innerHTML = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d[1] + '</svg>';
      b.addEventListener('click', d[2]); ctl.appendChild(b);
    });
    this.zoomLabel = document.createElement('div');
    this.zoomLabel.style.cssText = 'position:absolute;left:10px;bottom:10px;padding:2px 8px;border-radius:4px;background:rgba(255,255,255,.92);border:1px solid #E2E8F0;font-size:12px;line-height:18px;color:#333;';
    this.hint = document.createElement('div');
    this.hint.style.cssText = 'position:absolute;left:50%;bottom:64px;transform:translateX(-50%);padding:6px 12px;border-radius:8px;background:rgba(17,17,17,.86);color:#fff;font-size:13px;line-height:19px;white-space:nowrap;pointer-events:none;';
    this.hint.textContent = '두 손가락으로 벌리면 커집니다. 칸을 누르면 종목이 열립니다.';
    this.sheet = document.createElement('div');
    this.sheet.style.cssText = 'display:none;flex:none;max-height:56%;overflow:auto;border-top:1px solid #CBD5E1;background:#fff;box-shadow:0 -6px 18px rgba(15,23,42,.10);';
    this.holder = document.createComment('map'); this.inlineBox.insertBefore(this.holder, this.cv);
    stage.appendChild(this.cv); stage.appendChild(ctl); stage.appendChild(this.zoomLabel); stage.appendChild(this.hint);
    ov.appendChild(head); ov.appendChild(this.what); ov.appendChild(this.modeBar); ov.appendChild(stage); ov.appendChild(this.legend); ov.appendChild(this.sheet);
    document.body.appendChild(ov);
    this.scrollLock = document.documentElement.style.overflow; document.documentElement.style.overflow = 'hidden';
    try { history.pushState({ marketMap: 1 }, ''); this.pushed = true; } catch (e) { this.pushed = false; }
    this.syncModes(); this.W = 0; this.fit();
  };
  P.close = function (fromPop) {
    if (!this.full) return;
    if (!fromPop && this.pushed) { history.back(); return; }   // popstate 가 다시 부른다
    this.full = false; this.sel = null; this.what = null; this.zoomLabel = null; this.hint = null;
    this.cv.style.height = PREVIEW_H + 'px'; this.cv.style.touchAction = 'pan-y'; this.cv.style.cursor = 'pointer';
    this.modeBar.style.padding = '10px 10px 8px';
    this.inlineBox.insertBefore(this.modeBar, this.holder); this.inlineBox.insertBefore(this.cv, this.holder); this.inlineBox.insertBefore(this.legend, this.holder);
    this.inlineBox.removeChild(this.holder);
    this.ov.parentNode.removeChild(this.ov); this.ov = null;
    document.documentElement.style.overflow = this.scrollLock || '';
    this.W = 0; this.fit();
  };

  /* ── 누른 종목 창 — 재료를 합치지 않고 나란히, 줄마다 무엇과 견줬는지 ── */
  P.line = function (label, note, value, color) {
    return '<div style="display:flex;align-items:baseline;gap:8px;padding:7px 0;border-top:1px solid #EEF2F6;">'
      + '<span style="flex:1 1 auto;min-width:0;font-size:16px;line-height:24px;word-break:keep-all;">' + esc(label) + (note ? ' <span style="font-size:13px;line-height:19px;color:' + SUB + ';">' + esc(note) + '</span>' : '') + '</span>'
      + '<span style="flex:none;font-size:16px;line-height:24px;font-weight:700;white-space:nowrap;color:' + (color || INK) + ';">' + esc(value) + '</span></div>';
  };
  P.says = function (r) {   // 한 줄 풀이 — 틀로 만든 문장(원인은 말하지 않는다)
    var b = this.bench, rel = r.r - b.r, flat = Math.abs(r.r) < 0.05, t;
    if (flat) t = '오늘 종가는 전날과 거의 같습니다.';
    else if (Math.abs(rel) < 0.3) t = '오늘 ' + b.n + '와 비슷하게 ' + (r.r > 0 ? '올랐습니다.' : '내렸습니다.');
    else if (r.r > 0 && rel > 0) t = b.r >= 0 ? '오늘 ' + b.n + '보다 더 올랐습니다.' : b.n + '가 내린 날에 올랐습니다.';
    else if (r.r < 0 && rel < 0) t = b.r <= 0 ? '오늘 ' + b.n + '보다 더 내렸습니다.' : b.n + '가 오른 날에 내렸습니다.';
    else if (r.r < 0) t = '오늘 내렸지만 ' + b.n + '보다는 덜 내렸습니다.';
    else t = '오늘 올랐지만 ' + b.n + '보다는 덜 올랐습니다.';
    if (r.v != null && r.v >= 2) t += ' 거래량은 평소의 ' + r.v.toFixed(1) + '배였습니다.';
    return t;
  };
  P.showSheet = function (r) {
    if (!this.full) return;
    var self = this, b = this.bench, g = r.sec, rel = r.r - b.r, rs = r.r - g.avg;
    var price = this.data.m === 'kr' ? Math.round(r.p).toLocaleString('en-US') + '원' : '$' + Number(r.p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    var logo = r.lg ? '<img src="' + LOGO + esc(r.lg) + '?v=' + LOGO_VER + '" alt="" width="28" height="28" style="flex:none;width:28px;height:28px;border-radius:6px;background:#fff;object-fit:cover;outline:1px solid #E2E8F0;outline-offset:-1px;">' : '';
    this.sel = r;
    this.sheet.innerHTML = '<div style="padding:14px 14px 16px;">'
      + '<div style="display:flex;align-items:center;gap:8px;">' + logo
      + '<span style="flex:1 1 auto;min-width:0;"><b style="font-size:19px;line-height:28px;font-weight:700;word-break:keep-all;">' + esc(r.n) + '</b> <span style="font-size:13px;line-height:19px;color:' + SUB + ';white-space:nowrap;">' + esc(r.t) + ' · ' + esc(g.name) + '</span></span>'
      + '<button type="button" data-x="1" aria-label="닫기" style="flex:none;display:flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;border:1px solid #CBD5E1;border-radius:6px;background:#fff;color:#111;cursor:pointer;"><svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></svg></button></div>'
      + '<div style="margin:6px 0 8px;font-size:16px;line-height:24px;word-break:keep-all;">' + esc(this.says(r)) + '</div>'
      + this.line('오늘 등락', '종가 ' + price, sign(r.r, '%'), dirColor(r.r))
      + this.line(b.n + ' 대비', b.n + ' ' + sign(b.r, '%'), sign(rel, '%p'), dirColor(rel))
      + this.line(g.name + ' 업종 대비', '업종 평균 ' + sign(g.avg, '%'), sign(rs, '%p'), dirColor(rs))
      + (r.v != null ? this.line('거래량', '직전 20거래일 평균 대비', r.v.toFixed(1) + '배') : '')
      + (r.hi != null && r.hi <= 0.05 ? this.line('52주 최고가 대비', '', Math.abs(r.hi) < 0.05 ? '최고가' : sign(r.hi, '%'), dirColor(r.hi)) : '')
      + (r.u ? '<a href="' + esc(BLOG + r.u) + '" style="display:flex;justify-content:center;align-items:center;min-height:44px;margin:10px 0 0;padding:8px 12px;border:1px solid #E2E8F0;border-radius:8px;background:#fff;color:#111;font-size:14px;line-height:20px;font-weight:700;text-decoration:none;">' + esc(r.n) + ' 종목 페이지 보기</a>' : '')
      + '</div>';
    this.sheet.style.display = 'block';
    this.sheet.querySelector('[data-x]').addEventListener('click', function () { self.hideSheet(); });
    this.touched(); this.relayout();
  };
  P.hideSheet = function () { if (!this.sheet || this.sheet.style.display === 'none') { this.sel = null; return; } this.sheet.style.display = 'none'; this.sel = null; this.relayout(); };
  P.relayout = function () {   // 창이 열리고 닫히면 지도 칸 높이가 달라진다 — 보던 자리를 지키며 다시 맞춘다
    var r = this.cv.getBoundingClientRect(), H = Math.round(r.height), sel = this.sel;
    if (!H || !this.H) return;
    var k = this.k, cx = (this.W / 2 - this.tx) / k / this.W, cy = (this.H / 2 - this.ty) / k / this.H;
    this.W = 0; this.fit();
    if (sel) { cx = (sel.x + sel.w / 2) / this.W; cy = (sel.y + sel.h / 2) / this.H; }
    this.k = k; this.tx = this.W / 2 - cx * this.W * k; this.ty = this.H / 2 - cy * this.H * k; this.clamp(); this.draw();
  };

  function boot() {
    [].forEach.call(document.querySelectorAll('[data-market-map]'), function (root) {
      if (root.getAttribute('data-ready')) return;
      var s = root.querySelector('script[type="application/json"]');
      if (!s) return;
      root.setAttribute('data-ready', '1');
      try {
        var mp = root.__map = new MarketMap(root, JSON.parse(s.textContent));
        var h = /^#map(?:=(.+))?$/.exec(location.hash || '');   // 주소 끝 #map = 전체 화면으로 열기 · #map=코드 = 그 종목까지 (다른 화면에서 지도로 보내는 링크용)
        if (h) setTimeout(function () {
          mp.open();
          if (!h[1]) return;
          var code = decodeURIComponent(h[1]), hit = null;
          mp.secs.forEach(function (g) { g.rows.forEach(function (r) { if (r.t === code) hit = r; }); });
          if (hit) { mp.showSheet(hit); var kk = Math.max(1, Math.min(KMAX, Math.min(mp.W / (hit.w * 3), mp.H / (hit.h * 3)))); mp.animate(kk, mp.W / 2 - (hit.x + hit.w / 2) * kk, mp.H / 2 - (hit.y + hit.h / 2) * kk); }
        }, 60);
      } catch (e) { if (window.console) console.error('market-map', e); }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
