/* AlphaScope 봉차트 — 페이지 안에서 직접 그리는 실제 차트 (2026-11-13 사용자: "그림 말고 실제 차트 · 넘겨보기 · 주봉 · 손가락 확대 · 전체 화면 · 볼린저 · MACD").
   [data-candle] 요소마다 하나. 자료 = data-candle 속성의 JSON {name, dec, bars:[[날짜,시,고,저,종,거래량],...], avg?:{price,label}}.
   새 수집 · AI 0 — 페이지를 만들 때 이미 받은 일봉을 넣고, 주 · 월 · 분기 · 년봉과 지표는 브라우저가 계산한다.
   2026-11-14 사용자 "네이버랑 똑같이" (A6 B1 B3 B5 B6 B10 B11 C1 C3 C4 D3 D5 D6 D8 D11 D12):
     일 → 주 → 월 → 분기 → 년 순환 · 이동평균 범례(5 20 60 120, 숫자 = 선 색) + 닫기 · 일반/로그 축 · 보합 봉 회색 십자 · 최고 · 최저(현재가 대비 %) ·
     최신으로 버튼 · 세로 격자 · 거래량 범례 + 닫기 · 거래량 눈금 · 날짜 축(MM/DD, 달이 바뀌면 `N월` 굵게) ·
     머리 = 현재가 · 전날 대비 금액 · % · 오늘 거래량 · 시가 · 고가 · 저가 · 종가 · 누르면 위 · 아래 날짜 칸 · 이동평균 값 표 · 그날 거래량.
   매수 · 매도 같은 판단 말은 그리지 않는다(지표 교차 표시 없음). 테마로 옮길 수 있게 한 번만 돈다. */
(function () {
  if (window.__asCandle) return;
  window.__asCandle = 1;
  var VIO = '#6D28D9', UP = '#d93025', DN = '#1a73e8', UPL = '#F2A9A3', DNL = '#9DC2F2', FLAT = '#9CA3AF', GRID = '#ECF0F5', NOTE = '#6B7280', INK = '#111';
  var MA_COL = { 5: '#5BB450', 20: '#E5534B', 60: '#F08C2E', 120: '#9B59D0', 200: '#E879A6' };   // 네이버와 같은 색 (2026-11-14 사용자)
  var UNITS = ['D', 'W', 'M', 'Q', 'Y'], UNIT_KO = { D: '일', W: '주', M: '월', Q: '분기', Y: '년' };
  var VIEW = { D: 60, W: 52, M: 36, Q: 24, Y: 15 }, MIN_SLOT = 7, AXIS_W = 66, FS = 13, TOPS = 22, XH = 22;   // MIN_SLOT = 봉 한 칸 최소 폭(몸통 5) · TOPS = 위 띠(범례 · 축 방식 · 위 날짜 칸)

  function qkey(s) { return s.slice(0, 4) + 'Q' + (Math.floor((+s.slice(5, 7) - 1) / 3) + 1); }
  function agg(d, u) {
    if (u === 'D') return d;
    var out = [], cur = null, key = function (s) {
      if (u === 'M') return s.slice(0, 7);
      if (u === 'Q') return qkey(s);
      if (u === 'Y') return s.slice(0, 4);
      var t = new Date(s + 'T00:00:00Z'), w = (t.getUTCDay() + 6) % 7; t.setUTCDate(t.getUTCDate() - w); return t.toISOString().slice(0, 10);
    };
    d.forEach(function (b) {
      var k = key(b[0]);
      if (!cur || cur.k !== k) { cur = { k: k, b: b.slice() }; out.push(cur.b); }
      else { cur.b[0] = b[0]; cur.b[2] = Math.max(cur.b[2], b[2]); cur.b[3] = Math.min(cur.b[3], b[3]); cur.b[4] = b[4]; cur.b[5] += b[5]; }
    });
    return out;
  }
  function sma(c, n) { var o = [], s = 0; for (var i = 0; i < c.length; i++) { s += c[i]; if (i >= n) s -= c[i - n]; o.push(i >= n - 1 ? s / n : null); } return o; }
  function ema(c, n) { var o = [], k = 2 / (n + 1), e = null; for (var i = 0; i < c.length; i++) { e = e === null ? c[i] : c[i] * k + e * (1 - k); o.push(i >= n - 1 ? e : null); } return o; }
  function boll(c, n, m) {
    var mid = sma(c, n), up = [], lo = [];
    for (var i = 0; i < c.length; i++) {
      if (mid[i] === null) { up.push(null); lo.push(null); continue; }
      var s = 0; for (var j = i - n + 1; j <= i; j++) s += (c[j] - mid[i]) * (c[j] - mid[i]);
      var sd = Math.sqrt(s / n); up.push(mid[i] + m * sd); lo.push(mid[i] - m * sd);
    }
    return { mid: mid, up: up, lo: lo };
  }
  function macd(c) {
    var a = ema(c, 12), b = ema(c, 26), line = c.map(function (_, i) { return a[i] === null || b[i] === null ? null : a[i] - b[i]; });
    var first = line.findIndex(function (v) { return v !== null; }), sig = line.map(function () { return null; });
    if (first >= 0) { var s = ema(line.slice(first), 9); s.forEach(function (v, i) { sig[first + i] = v; }); }
    return { line: line, sig: sig, hist: line.map(function (v, i) { return v === null || sig[i] === null ? null : v - sig[i]; }) };
  }
  function rsi(c, n) {
    var o = [null], g = 0, l = 0;
    for (var i = 1; i < c.length; i++) {
      var ch = c[i] - c[i - 1], up = Math.max(ch, 0), dn = Math.max(-ch, 0);
      if (i <= n) { g += up; l += dn; o.push(i === n ? 100 - 100 / (1 + (g / n) / ((l / n) || 1e-9)) : null); if (i === n) { g /= n; l /= n; } }
      else { g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n; o.push(100 - 100 / (1 + g / (l || 1e-9))); }
    }
    return o;
  }
  function fmt(v, dec) { return v.toLocaleString('ko-KR', { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
  function sgnPct(v) { return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2) + '%'; }
  function tri(v) { return v > 0 ? '▲' : v < 0 ? '▼' : ''; }
  function fmtVol(v) { return v >= 1e6 ? (v / 1e6).toFixed(2).replace(/\.?0+$/, '') + 'm' : v >= 1e3 ? Math.round(v / 1e3) + 'k' : String(Math.round(v)); }
  function ticks(lo, hi, n) {
    var span = hi - lo || Math.abs(hi) || 1, raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), st = [1, 2, 2.5, 5, 10].map(function (k) { return k * p; }).find(function (k) { return k >= raw; });
    var o = []; for (var t = Math.ceil(lo / st) * st; t <= hi + 1e-9; t += st) o.push(+t.toFixed(10)); return o;
  }
  function el(tag, css, html) { var e = document.createElement(tag); if (css) e.style.cssText = css; if (html !== undefined) e.innerHTML = html; return e; }
  function btn(txt, on) {
    return el('button', 'font:inherit;font-size:14px;line-height:20px;padding:4px 10px;border-radius:6px;cursor:pointer;border:1px solid ' + (on ? '#111' : '#E2E8F0') +
      ';background:' + (on ? '#111' : '#fff') + ';color:' + (on ? '#fff' : '#111') + ';', txt);
  }
  var X_SVG = '<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#9CA3AF" stroke-width="1.5" stroke-linecap="round"><path d="M2 2l6 6M8 2L2 8"/></svg>';
  var CHIP = 'display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;background:#F1F5F9;border:0;padding:0;cursor:pointer;margin-left:6px;';

  function Chart(root) {
    var self = this;
    this.root = root; this.d = JSON.parse(root.getAttribute('data-candle')); this.dec = this.d.dec || 0;
    this.unit = 'D'; this.full = false; this.log = false; this.maOn = true;
    this.on = { ma: { 5: true, 20: true, 60: true, 120: true }, boll: false, lower: 'vol' };
    root.innerHTML = '';
    // 머리 — 1줄: 현재가 · 전날 대비 금액 · % | 버튼, 2줄: 오늘 거래량, 3줄: 시가 · 고가 · 저가 · 종가(누른 날이면 그날)
    this.top = el('div', 'display:flex;align-items:center;gap:6px;margin:0 0 4px;');
    this.price = el('div', 'flex:1;min-width:0;white-space:nowrap;font-variant-numeric:tabular-nums;');
    this.btns = el('div', 'display:flex;gap:6px;flex:none;');
    this.top.appendChild(this.price); this.top.appendChild(this.btns);
    this.sub = el('div', 'font-size:13px;line-height:19px;color:' + NOTE + ';margin:0 0 2px;font-variant-numeric:tabular-nums;');
    this.ohlc = el('div', 'display:grid;grid-template-columns:repeat(4,auto);justify-content:space-between;gap:0 8px;font-size:13px;line-height:19px;margin:0 0 6px;font-variant-numeric:tabular-nums;');
    this.menuBox = el('div', '');
    this.wrap = el('div', 'position:relative;');
    this.cv = el('canvas', 'display:block;width:100%;touch-action:pan-y;cursor:crosshair;');
    this.legend = el('div', 'position:absolute;left:0;top:0;font-size:13px;line-height:20px;color:' + INK + ';display:flex;align-items:center;flex-wrap:wrap;max-width:70%;pointer-events:auto;');
    this.scaleB = el('button', 'position:absolute;right:0;top:0;font:inherit;font-size:13px;line-height:20px;border:0;background:transparent;color:' + INK + ';cursor:pointer;padding:0 2px;');
    this.latest = el('button', 'position:absolute;width:30px;height:28px;border:1px solid #E2E8F0;border-radius:6px;background:#fff;cursor:pointer;display:none;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,.12);',
      '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#111" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l4 4-4 4M8 3l4 4-4 4"/></svg>');
    this.latest.setAttribute('aria-label', '최신으로');
    this.volLeg = el('div', 'position:absolute;left:0;font-size:13px;line-height:20px;color:' + INK + ';display:flex;align-items:center;');
    this.restore = el('div', 'display:flex;gap:6px;margin:6px 0 0;');
    [this.cv, this.legend, this.scaleB, this.latest, this.volLeg].forEach(function (e) { self.wrap.appendChild(e); });
    [this.top, this.sub, this.ohlc, this.menuBox, this.wrap, this.restore].forEach(function (e) { root.appendChild(e); });
    this.scaleB.onclick = function () { self.log = !self.log; self.draw(); };
    this.latest.onclick = function () { self.end = self.bars.length; self.cross = null; self.draw(); };
    this.build();
    this.bind();
    var lastW = 0, again = function () { var w = root.clientWidth; if (w && w !== lastW) { lastW = w; requestAnimationFrame(function () { self.draw(); }); } };
    if (window.ResizeObserver) new ResizeObserver(again).observe(root);
    else window.addEventListener('resize', function () { self.draw(); });
  }
  Chart.prototype.build = function () {
    var self = this;
    this.bars = agg(this.d.bars, this.unit);
    var c = this.bars.map(function (b) { return b[4]; });
    this.ma = {}; [5, 20, 60, 120, 200].forEach(function (n) { self.ma[n] = sma(c, n); });
    this.bb = boll(c, 20, 2); this.mc = macd(c); this.rs = rsi(c, 14);
    this.n = Math.min(VIEW[this.unit], this.bars.length); this.end = this.bars.length; this.cross = null;
    this.topBar();
  };
  Chart.prototype.minN = function () { return Math.min(10, this.bars.length); };
  Chart.prototype.maxN = function () { return Math.max(this.minN(), Math.floor((this.root.clientWidth - (this.axisW || AXIS_W)) / MIN_SLOT)); };
  Chart.prototype.topBar = function () {
    var self = this, t = this.btns; t.innerHTML = '';
    // 일 → 주 → 월 → 분기 → 년 → 일 한 버튼 (2026-11-13 · 11-14 사용자)
    var cyc = btn(UNIT_KO[this.unit], false); cyc.style.minWidth = '44px'; cyc.setAttribute('aria-label', '일봉 · 주봉 · 월봉 · 분기봉 · 년봉 바꾸기');
    cyc.onclick = function () { self.unit = UNITS[(UNITS.indexOf(self.unit) + 1) % UNITS.length]; self.build(); self.draw(); }; t.appendChild(cyc);
    if (this.full) { var ind = btn('지표', this.menu); ind.onclick = function () { self.menu = !self.menu; self.topBar(); self.draw(); }; t.appendChild(ind); }
    var fs = el('button', 'font:inherit;width:32px;height:30px;border:1px solid #E2E8F0;border-radius:6px;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;',
      this.full ? '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#111" stroke-width="1.6" stroke-linecap="round"><path d="M3 3l10 10M13 3L3 13"/></svg>'
                : '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#111" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/></svg>');
    fs.setAttribute('aria-label', this.full ? '닫기' : '전체 화면');
    fs.onclick = function () { self.toggleFull(); }; t.appendChild(fs);
    var m = this.menuBox; m.innerHTML = ''; m.style.cssText = '';
    if (this.full && this.menu) {
      m.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;padding:4px 0 8px;';
      var u = this.unit === 'D' ? '일' : this.unit === 'W' ? '주' : '';
      [5, 20, 60, 120, 200].forEach(function (n) {
        var b = btn(n + u, !!self.on.ma[n] && self.maOn); b.onclick = function () { self.maOn = true; self.on.ma[n] = !self.on.ma[n]; self.topBar(); self.draw(); }; m.appendChild(b);
      });
      var bb = btn('볼린저 밴드', this.on.boll); bb.onclick = function () { self.on.boll = !self.on.boll; self.topBar(); self.draw(); }; m.appendChild(bb);
      m.appendChild(el('span', 'flex-basis:100%;height:0;'));
      [['vol', '거래량'], ['macd', 'MACD'], ['rsi', 'RSI'], ['none', '없음']].forEach(function (x) {
        var b = btn('아래 : ' + x[1], self.on.lower === x[0]); b.onclick = function () { self.on.lower = x[0]; self.topBar(); self.draw(); }; m.appendChild(b);
      });
    }
  };
  Chart.prototype.toggleFull = function () {
    if (!this.full) {
      this.ph = document.createComment('candle');
      this.root.parentNode.insertBefore(this.ph, this.root);
      this.ov = el('div', 'position:fixed;inset:0;z-index:2147483000;background:#fff;display:flex;flex-direction:column;padding:12px 12px max(12px,env(safe-area-inset-bottom));box-sizing:border-box;overflow:auto;');
      this.ov.appendChild(el('div', 'font-size:17px;line-height:24px;font-weight:700;color:#111;margin:0 0 6px;', this.d.name));
      this.ov.appendChild(this.root);
      document.body.appendChild(this.ov); document.documentElement.style.overflow = 'hidden';
      this.full = true; this.on.ma[200] = this.on.ma[200] || false; this.n = Math.min(this.unit === 'D' ? 120 : VIEW[this.unit] * 2, this.bars.length);
    } else {
      this.ph.parentNode.insertBefore(this.root, this.ph); this.ph.remove(); this.ov.remove(); document.documentElement.style.overflow = '';
      this.full = false; this.menu = false; this.n = Math.min(VIEW[this.unit], this.bars.length); this.end = this.bars.length;
    }
    this.cross = null; this.topBar(); this.draw();
  };
  Chart.prototype.bind = function () {
    // 옆으로 밀기 = 넘겨보기 · 두 손가락 = 확대 · 축소 · 짧게 누르기 = 그날 십자선(다시 누르면 끔) · 꾹 누르고 움직이기 = 십자선이 따라감
    var self = this, cv = this.cv, pts = {}, start = null, moved = false, timer = null, crossMode = false;
    function at(e) {
      var r = cv.getBoundingClientRect(), pw = r.width - (self.axisW || AXIS_W);
      return { i: Math.max(0, Math.min(self.n - 1, Math.floor((e.clientX - r.left) / (pw / self.n)))) + self.end - self.n, y: e.clientY - r.top };
    }
    cv.addEventListener('pointerdown', function (e) {
      pts[e.pointerId] = e.clientX; cv.setPointerCapture(e.pointerId); moved = false;
      var ids = Object.keys(pts);
      clearTimeout(timer);
      if (ids.length === 2) { start = { pinch: Math.abs(pts[ids[0]] - pts[ids[1]]), n: self.n, end: self.end }; crossMode = false; self.cross = null; return; }
      start = { x: e.clientX, end: self.end };
      if (e.pointerType !== 'mouse') timer = setTimeout(function () { if (!moved) { crossMode = true; self.cross = at(e); self.draw(); } }, 280);
    });
    cv.addEventListener('pointermove', function (e) {
      if (!(e.pointerId in pts)) { if (e.pointerType === 'mouse') { self.cross = at(e); self.draw(); } return; }
      pts[e.pointerId] = e.clientX;
      if (crossMode) { self.cross = at(e); self.draw(); return; }
      var ids = Object.keys(pts), slot = (cv.getBoundingClientRect().width - (self.axisW || AXIS_W)) / self.n;
      if (ids.length === 2 && start.pinch) {
        var d = Math.abs(pts[ids[0]] - pts[ids[1]]) || 1;
        self.n = Math.max(self.minN(), Math.min(self.maxN(), self.bars.length, Math.round(start.n * start.pinch / d))); self.end = Math.max(self.end, self.n); moved = true;
      } else if (start && start.x !== undefined) {
        var dx = e.clientX - start.x;
        if (Math.abs(dx) > 4) { moved = true; clearTimeout(timer); }
        self.end = Math.max(self.n, Math.min(self.bars.length, start.end - Math.round(dx / slot)));
      }
      if (moved) self.cross = null;
      self.draw();
    });
    cv.addEventListener('touchmove', function (e) { if (crossMode) e.preventDefault(); }, { passive: false });
    function up(e) {
      clearTimeout(timer);
      if (!moved && !crossMode && e.type === 'pointerup' && e.pointerType !== 'mouse') { var a = at(e); self.cross = self.cross && self.cross.i === a.i ? null : a; }
      crossMode = false;
      delete pts[e.pointerId]; start = Object.keys(pts).length ? { x: pts[Object.keys(pts)[0]], end: self.end } : null; self.draw();
    }
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse' && !(e.pointerId in pts)) { self.cross = null; self.draw(); } });
    cv.addEventListener('wheel', function (e) {
      if (!self.full && !e.ctrlKey) return;
      e.preventDefault(); self.n = Math.max(self.minN(), Math.min(self.maxN(), self.bars.length, Math.round(self.n * (e.deltaY > 0 ? 1.15 : 0.87)))); self.end = Math.max(self.end, self.n); self.draw();
    }, { passive: false });
  };
  Chart.prototype.dateText = function (s, full) {
    if (this.unit === 'Y') return s.slice(0, 4) + '년';
    if (this.unit === 'Q') return s.slice(0, 4) + '년 ' + qkey(s).slice(5) + '분기';
    if (this.unit === 'M') return s.slice(0, 4) + '-' + s.slice(5, 7);
    if (this.unit === 'W') { var x = new Date(s + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() - (x.getUTCDay() + 6) % 7); return x.toISOString().slice(0, 10) + ' 주'; }
    return full ? s : s.slice(5).replace('-', '/');
  };
  Chart.prototype.draw = function () {
    var self = this, cv = this.cv, W = Math.floor(this.root.clientWidth); if (!W) return;
    // 작은 화면 = 그림을 카드 오른쪽 · 아래 안쪽 여백만큼 넓혀 종가 칸이 카드 외곽선에 붙게 (2026-11-14 사용자)
    var box = getComputedStyle(this.root.parentNode), padR = this.full ? 0 : Math.round(parseFloat(box.paddingRight) || 0), padB = this.full ? 0 : Math.round(parseFloat(box.paddingBottom) || 0);
    this.wrap.style.marginRight = -padR + 'px'; this.root.style.marginBottom = -padB + 'px'; W += padR;
    if (this.n > this.maxN()) { this.n = Math.min(this.maxN(), this.bars.length); this.end = Math.max(this.end, this.n); }
    var lowerH = this.on.lower === 'none' || !this.full ? 0 : 90, priceH = 264, gap = lowerH ? 26 : 0;   // gap = 거래량 범례 줄
    if (this.full) {
      var rest = window.innerHeight - this.wrap.getBoundingClientRect().top - this.restore.offsetHeight - 16;
      priceH = Math.max(200, Math.floor(rest - TOPS - lowerH - gap - XH));
    }
    var H = TOPS + priceH + gap + lowerH + XH, dpr = window.devicePixelRatio || 1;
    cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + 'px';
    var g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    var font = getComputedStyle(this.root).fontFamily, s = this.end - this.n, B = this.bars.slice(s, this.end), pw, slot, X;
    var last = this.bars[this.bars.length - 1], prevL = this.bars[this.bars.length - 2];
    var maShow = function (n) { return self.maOn && self.on.ma[n]; };
    // 가격 범위 = 봉 + 켜진 선 (+ 최고 · 최저 글자 자리 위아래 22)
    var lo = Infinity, hi = -Infinity, look = function (v) { if (v !== null && v !== undefined) { lo = Math.min(lo, v); hi = Math.max(hi, v); } };
    B.forEach(function (b) { look(b[2]); look(b[3]); });
    for (var i = s; i < this.end; i++) { for (var n in this.on.ma) if (maShow(n)) look(this.ma[n][i]); if (this.on.boll) { look(this.bb.up[i]); look(this.bb.lo[i]); } }
    // 오른쪽 가격 칸 폭 — 전체 화면 66 고정, 작은 화면 = 가장 긴 숫자 + 왼쪽 9 · 오른쪽 3 (2026-11-14 사용자 "0 기준 우측 여백 최대한 좁게")
    var TX = this.full ? 10 : 9, TFS = this.full ? FS : 10, AFS = TFS;   // 작은 화면 = 종가 칸 · 오른쪽 눈금 · 아래 날짜 모두 10 (2026-11-14 사용자)
    if (this.full) this.axisW = AXIS_W;
    else {
      var mw = 0; g.font = AFS + 'px ' + font; ticks(lo, hi, 5).forEach(function (t) { mw = Math.max(mw, g.measureText(fmt(t, self.dec)).width); });
      g.font = '600 ' + TFS + 'px ' + font; [lo, hi, this.bars[this.end - 1][4]].forEach(function (v) { mw = Math.max(mw, g.measureText(fmt(v, self.dec)).width); });
      this.axisW = TX + Math.ceil(mw) + 3;
    }
    pw = W - this.axisW; slot = pw / this.n; X = function (i) { return Math.floor((i - s) * slot + slot / 2) + 0.5; };
    var avg = this.d.avg, avgIn = avg && avg.price >= lo - (hi - lo) * 0.3 && avg.price <= hi + (hi - lo) * 0.3;
    if (avgIn) look(avg.price);
    if (this.log && lo <= 0) this.log = false;
    var useLog = this.full && this.log;   // 작은 화면 = Linear · Log 버튼 없음
    var T = useLog ? Math.log : function (v) { return v; }, iT = useLog ? Math.exp : function (v) { return v; };
    var tlo = T(lo), thi = T(hi), y0p = TOPS + 22, y1p = TOPS + priceH - 22;
    var Y = function (v) { return Math.round(y0p + (thi - T(v)) / ((thi - tlo) || 1) * (y1p - y0p)) + 0.5; };
    var vOf = function (y) { return iT(thi - (y - y0p) / (y1p - y0p) * (thi - tlo)); };
    // 날짜 축 칸 — 달이 바뀌는 첫 봉 `N월`(1월은 `YYYY년`) 굵게, 사이엔 주의 첫 봉 `MM/DD` (일봉) — 세로 격자도 이 자리
    var labs = [], placed = [], add = function (j, txt, bold, minGap) {
      var x = X(s + j); if (placed.some(function (p) { return Math.abs(p - x) < minGap; })) return; placed.push(x); labs.push([x, txt, bold]);
    };
    B.forEach(function (b, j) {
      var p = j ? B[j - 1][0] : (self.bars[s - 1] || [''])[0]; if (!p) return;
      if (!self.full && (self.unit === 'D' || self.unit === 'W')) return;   // 작은 화면 = 달 표시 없이 날짜만
      if (self.unit === 'D' || self.unit === 'W') {
        if (b[0].slice(0, 4) !== p.slice(0, 4)) add(j, b[0].slice(0, 4) + '년', true, 50);
        else if (b[0].slice(0, 7) !== p.slice(0, 7)) add(j, +b[0].slice(5, 7) + '월', true, 50);
      } else if (b[0].slice(0, 4) !== p.slice(0, 4)) add(j, b[0].slice(0, 4) + '년', true, 50);
    });
    if (!this.full && this.unit === 'W') B.forEach(function (b, j) { if (j) add(j, b[0].slice(5).replace('-', '.'), false, 62); });
    if (this.unit === 'D') B.forEach(function (b, j) {
      if (!j) return; var a = new Date(B[j - 1][0] + 'T00:00:00Z'), c = new Date(b[0] + 'T00:00:00Z');
      if ((c - a) / 864e5 > 1 && c.getUTCDay() <= 2) add(j, b[0].slice(5).replace('-', '.'), false, 62);
    });
    if (this.unit === 'M') B.forEach(function (b, j) { if (/-(04|07|10)$/.test(b[0].slice(0, 7))) add(j, +b[0].slice(5, 7) + '월', false, 46); });
    labs.forEach(function (l) { g.strokeStyle = GRID; g.lineWidth = 1; g.beginPath(); g.moveTo(Math.round(l[0]) + 0.5, TOPS); g.lineTo(Math.round(l[0]) + 0.5, H - XH); g.stroke(); });
    // 가로 격자 · 오른쪽 눈금
    g.font = AFS + 'px ' + font; g.textBaseline = 'middle';
    var tagB = this.bars[this.end - 1], tagY = tagB ? Y(tagB[4]) : -99;
    var tk = ticks(lo, hi, this.full ? 6 : 5);
    tk.forEach(function (t) {
      var y = Y(t); if (y < TOPS || y > TOPS + priceH) return;
      g.strokeStyle = GRID; g.lineWidth = 1; g.beginPath(); g.moveTo(0, y); g.lineTo(pw, y); g.stroke();
      if (Math.abs(y - tagY) < 14) return;
      g.fillStyle = NOTE; g.textAlign = 'left'; g.fillText(fmt(t, self.dec), pw + TX, y);
    });
    g.strokeStyle = '#E2E8F0'; g.beginPath(); g.moveTo(pw + 0.5, TOPS); g.lineTo(pw + 0.5, H - XH); g.stroke();
    var tag = function (y, txt, bg) {
      y = Math.round(y); g.fillStyle = bg; g.beginPath(); g.moveTo(pw + 1, y); g.lineTo(pw + 8, y - 10); g.lineTo(W, y - 10); g.lineTo(W, y + 10); g.lineTo(pw + 8, y + 10); g.closePath(); g.fill();
      g.fillStyle = '#fff'; g.font = '600 ' + TFS + 'px ' + font; g.textAlign = 'left'; g.fillText(txt, pw + TX, y + 0.5); g.font = FS + 'px ' + font;
    };
    // 볼린저 · 이동평균
    var line = function (arr, col, w) {
      g.strokeStyle = col; g.lineWidth = w; g.beginPath(); var on = false;
      for (var i = s; i < self.end; i++) { var v = arr[i]; if (v === null || v === undefined) { on = false; continue; } if (!on) { g.moveTo(X(i), Y(v)); on = true; } else g.lineTo(X(i), Y(v)); }
      g.stroke();
    };
    g.save(); g.beginPath(); g.rect(0, TOPS, pw, priceH); g.clip();
    if (this.on.boll) { line(this.bb.up, '#94A3B8', 1); line(this.bb.lo, '#94A3B8', 1); line(this.bb.mid, '#CBD5E1', 1); }
    [200, 120, 60, 20, 5].forEach(function (k) { if (maShow(k)) line(self.ma[k], MA_COL[k], 1); });
    // 봉 — 보합(시가 = 종가)은 회색 십자
    var bw = Math.max(5, Math.min(Math.floor(slot) - 2, Math.floor(slot * 0.7))); if (bw % 2 === 0) bw -= 1;
    B.forEach(function (b, j) {
      var i = s + j, x = X(i), flat = b[4] === b[1], col = flat ? FLAT : b[4] > b[1] ? UP : DN;
      g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x, Y(b[2])); g.lineTo(x, Y(b[3])); g.stroke();
      if (flat) { g.beginPath(); g.moveTo(Math.round(x - bw / 2), Y(b[4])); g.lineTo(Math.round(x + bw / 2) + 1, Y(b[4])); g.stroke(); return; }
      var y0 = Y(Math.max(b[1], b[4])), y1 = Y(Math.min(b[1], b[4]));
      g.fillRect(Math.round(x - bw / 2), Math.round(y0), bw, Math.max(1, Math.round(y1 - y0)));
    });
    g.restore();
    // 최고 · 최저 — 점 + `최고 235,000 (−26.13%)` (현재가가 그보다 몇 % 아래 · 위인지)
    if (B.length) {
      var hiI = 0, loI = 0; B.forEach(function (b, j) { if (b[2] > B[hiI][2]) hiI = j; if (b[3] < B[loI][3]) loI = j; });
      [[hiI, B[hiI][2], '최고', -1], [loI, B[loI][3], '최저', 1]].forEach(function (m) {
        var x = X(s + m[0]), y = Y(m[1]) + m[3] * 4, d = (last[4] / m[1] - 1) * 100;
        g.fillStyle = d > 0 ? UP : d < 0 ? DN : INK; g.beginPath(); g.arc(x, y, 2.5, 0, 6.3); g.fill();   // 증감 색 (2026-11-14 사용자)
        g.font = FS + 'px ' + font; var txt = m[2] + '  ' + fmt(m[1], self.dec) + ' (' + sgnPct(d) + ')', tw = g.measureText(txt).width;
        var tx = Math.min(Math.max(x - tw / 2, 2), pw - tw - 2);
        g.textAlign = 'left'; g.fillText(txt, Math.round(tx), Math.round(y + m[3] * 12) + 0.5);
      });
    }
    // 내 평단 — 보라 점선 + `내 평단 15,893 ▲3.10%`(차이 = 증감 색)
    if (avg) {
      var ya = avgIn ? Y(avg.price) : (avg.price > hi ? TOPS + 8 : TOPS + priceH - 8), diff = (last[4] / avg.price - 1) * 100;
      if (avgIn) { g.strokeStyle = VIO; g.lineWidth = 1; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(0, ya); g.lineTo(pw, ya); g.stroke(); g.setLineDash([]); }
      g.font = '12px ' + font; g.textAlign = 'left';
      var lab = (avg.label || '내 평단') + ' ' + fmt(avg.price, self.dec) + ' ', dtx = tri(diff) + Math.abs(diff).toFixed(2) + '%' + (avgIn ? '' : avg.price > hi ? ' ↑' : ' ↓');
      var w1 = Math.ceil(g.measureText(lab).width), w2 = Math.ceil(g.measureText(dtx).width), ly2 = Math.round(ya + (avgIn ? -9 : 0));
      g.fillStyle = 'rgba(255,255,255,.85)'; g.fillRect(2, ly2 - 9, w1 + w2 + 6, 18);
      g.fillStyle = VIO; g.fillText(lab, 5, ly2);
      g.fillStyle = diff > 0 ? UP : diff < 0 ? DN : INK; g.fillText(dtx, 5 + w1, ly2);
    }
    // 오른쪽 가격 칸 = 보이는 맨 오른쪽 봉 종가(삼각형 머리), 색 = 그 봉의 전날 대비
    if (tagB) { var tp = this.bars[this.end - 2]; tag(tagY, fmt(tagB[4], self.dec), !tp || tagB[4] >= tp[4] ? UP : DN); }
    // 거래량 칸 — 범례(`거래량 987,136` + 닫기) · 막대 · 오른쪽 눈금(250k · 1.5m)
    var top2 = TOPS + priceH + gap;
    if (lowerH) {
      g.strokeStyle = '#E2E8F0'; g.beginPath(); g.moveTo(0, TOPS + priceH + 0.5); g.lineTo(W, TOPS + priceH + 0.5); g.stroke();
      g.font = FS + 'px ' + font;
      if (this.on.lower === 'vol') {
        var vm = Math.max.apply(null, B.map(function (b) { return b[5]; })) || 1, vt = ticks(0, vm, 3).filter(function (v) { return v > 0; });
        var YV = function (v) { return Math.round(top2 + lowerH - v / vm * (lowerH - 4)) + 0.5; };
        vt.forEach(function (v) { g.strokeStyle = GRID; g.beginPath(); g.moveTo(0, YV(v)); g.lineTo(pw, YV(v)); g.stroke(); g.fillStyle = NOTE; g.textAlign = 'left'; g.fillText(fmtVol(v), pw + 10, YV(v)); });
        B.forEach(function (b, j) { var x = X(s + j), h = Math.round(b[5] / vm * (lowerH - 4)); g.fillStyle = b[4] > b[1] ? UPL : b[4] < b[1] ? DNL : '#D1D5DB'; g.fillRect(Math.round(x - bw / 2), top2 + lowerH - h, bw, h); });
      } else {
        var ser = this.on.lower === 'macd' ? [this.mc.line, this.mc.sig, this.mc.hist] : [this.rs], l2 = Infinity, h2 = -Infinity;
        for (var i2 = s; i2 < this.end; i2++) ser.forEach(function (a) { if (a[i2] !== null) { l2 = Math.min(l2, a[i2]); h2 = Math.max(h2, a[i2]); } });
        if (this.on.lower === 'rsi') { l2 = 0; h2 = 100; }
        if (l2 === Infinity) { l2 = -1; h2 = 1; }
        var Y2 = function (v) { return Math.round(top2 + 2 + (h2 - v) / (h2 - l2 || 1) * (lowerH - 4)) + 0.5; };
        (this.on.lower === 'rsi' ? [30, 70] : [0]).forEach(function (r) { g.strokeStyle = '#CBD5E1'; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(0, Y2(r)); g.lineTo(pw, Y2(r)); g.stroke(); g.setLineDash([]); g.fillStyle = NOTE; g.textAlign = 'left'; g.fillText(String(r), pw + 10, Y2(r)); });
        if (this.on.lower === 'macd') for (var i3 = s; i3 < this.end; i3++) { var hv = this.mc.hist[i3]; if (hv === null) continue; var yb0 = Y2(0), yb1 = Y2(hv); g.fillStyle = hv >= 0 ? UPL : DNL; g.fillRect(Math.round(X(i3) - bw / 2), Math.min(yb0, yb1), bw, Math.max(1, Math.abs(yb1 - yb0))); }
        var line2 = function (arr, col) { g.strokeStyle = col; g.lineWidth = 1; g.beginPath(); var on = false; for (var i = s; i < self.end; i++) { var v = arr[i]; if (v === null) { on = false; continue; } if (!on) { g.moveTo(X(i), Y2(v)); on = true; } else g.lineTo(X(i), Y2(v)); } g.stroke(); };
        if (this.on.lower === 'macd') { line2(this.mc.line, '#F08C2E'); line2(this.mc.sig, '#9B59D0'); } else line2(this.rs, '#5FBFAF');
      }
    }
    // 날짜 축
    if (this.full) { g.fillStyle = '#F1F5F9'; g.fillRect(0, H - XH, W, XH); }   // 작은 화면 = 회색 면 없음
    g.font = AFS + 'px ' + font; g.textAlign = 'center';
    labs.forEach(function (l) { g.font = (l[2] ? '600 ' : '') + AFS + 'px ' + font; g.fillStyle = l[2] ? INK : NOTE; g.fillText(l[1], Math.min(Math.max(l[0], 20), pw - 20), H - XH / 2 + 0.5); });
    // 누른 날 — 검은 점선 십자선 + 위 · 아래 날짜 칸 + 오른쪽 가격 칸
    var cr = this.cross, sel = cr && cr.i >= s && cr.i < this.end ? cr.i : null;
    if (sel !== null) {
      g.strokeStyle = INK; g.lineWidth = 1; g.setLineDash([2, 3]);
      g.beginPath(); g.moveTo(X(sel), TOPS); g.lineTo(X(sel), H - XH); g.stroke();
      var cy = Math.max(TOPS + 6, Math.min(TOPS + priceH - 6, cr.y));
      g.beginPath(); g.moveTo(0, Math.round(cy) + 0.5); g.lineTo(pw, Math.round(cy) + 0.5); g.stroke(); g.setLineDash([]);
      tag(cy, fmt(vOf(cy), self.dec), INK);
      var dl = this.dateText(this.bars[sel][0], true);
      g.font = AFS + 'px ' + font; var dw = Math.ceil(g.measureText(dl).width) + 14, dx = Math.round(Math.min(Math.max(X(sel) - dw / 2, 0), pw - dw));
      [[H - XH, XH], [0, TOPS]].forEach(function (r) { g.fillStyle = INK; g.fillRect(dx, r[0], dw, r[1]); g.fillStyle = '#fff'; g.textAlign = 'center'; g.fillText(dl, dx + dw / 2, r[0] + r[1] / 2 + 0.5); });
    }
    // 머리 — 현재가 · 전날 대비 금액 · % (늘 최신), 오늘 거래량, 시가 · 고가 · 저가 · 종가(누른 날이면 그날)
    var dch = prevL ? last[4] - prevL[4] : 0, dp = prevL ? dch / prevL[4] * 100 : 0, cc = dch > 0 ? UP : dch < 0 ? DN : INK;
    this.price.innerHTML = '<b style="font-size:20px;line-height:28px;color:' + INK + ';">' + fmt(last[4], this.dec) + '</b> <span style="font-size:14px;color:' + cc + ';">' + tri(dch) + fmt(Math.abs(dch), this.dec) + ' ' + sgnPct(dp) + '</span>';
    var volTxt = '거래량 <span style="color:' + INK + ';">' + fmt(last[5], 0) + '</span>';
    if (this.full) this.sub.innerHTML = volTxt;
    else this.price.innerHTML += ' <span style="font-size:13px;color:' + NOTE + ';">' + volTxt + '</span>';   // 작은 화면 = 증감 옆 한 줄
    this.sub.style.display = this.full ? '' : 'none'; this.ohlc.style.display = this.full ? '' : 'none';   // 작은 화면 = 시가 · 고가 · 저가 · 종가 없음
    var ob = this.bars[sel === null ? this.bars.length - 1 : sel], obp = this.bars[(sel === null ? this.bars.length - 1 : sel) - 1], ref = obp ? obp[4] : ob[1];
    this.ohlc.innerHTML = [['시가', 1], ['고가', 2], ['저가', 3], ['종가', 4]].map(function (k) {
      var v = ob[k[1]], c = v > ref ? UP : v < ref ? DN : INK;
      return '<span style="white-space:nowrap;"><span style="color:' + NOTE + ';">' + k[0] + '</span> <span style="color:' + c + ';">' + fmt(v, self.dec) + '</span></span>';
    }).join('');
    // 왼쪽 위 = 이동평균 범례(숫자 = 선 색) + 닫기 — 누르면 그날 이동평균 값 표
    var mas = [5, 20, 60, 120, 200].filter(function (n) { return maShow(n); });
    if (sel !== null && mas.length) {
      this.legend.style.top = (TOPS + 2) + 'px'; this.legend.style.display = 'block';
      this.legend.innerHTML = mas.map(function (n) { var v = self.ma[n][sel]; return '<div style="display:flex;gap:10px;"><span style="min-width:26px;">' + n + '</span><span style="color:' + MA_COL[n] + ';font-variant-numeric:tabular-nums;">' + (v === null ? '-' : fmt(v, self.dec)) + '</span></div>'; }).join('');
    } else if (mas.length) {
      this.legend.style.top = '0px'; this.legend.style.display = 'flex';
      this.legend.innerHTML = '<span style="color:' + INK + ';margin-right:5px;">이동평균</span>' + mas.map(function (n) { return '<span style="color:' + MA_COL[n] + ';margin-right:4px;">' + n + '</span>'; }).join('') +
        '<button type="button" aria-label="이동평균 끄기" data-x="ma" style="' + CHIP + '">' + X_SVG + '</button>';
      this.legend.querySelector('[data-x]').onclick = function () { self.maOn = false; self.draw(); };
    } else { this.legend.style.display = 'none'; }
    this.scaleB.innerHTML = (this.log ? 'Log' : 'Linear') + ' <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#111" stroke-width="1.3" stroke-linecap="round" style="vertical-align:0;"><path d="M2 4l3 3 3-3"/></svg>';
    this.scaleB.setAttribute('aria-label', '가격축 일반 · 로그 바꾸기'); this.scaleB.style.right = '4px'; this.scaleB.style.display = this.full ? '' : 'none';
    // 최신으로 (넘겨본 뒤에만)
    this.latest.style.display = this.end < this.bars.length ? 'flex' : 'none';
    this.latest.style.left = (pw - 36) + 'px'; this.latest.style.top = (TOPS + priceH - 34) + 'px';
    // 거래량 범례 — 누르면 그날 거래량
    if (lowerH && this.on.lower === 'vol') {
      var vb = this.bars[sel === null ? this.end - 1 : sel];
      this.volLeg.style.display = 'flex'; this.volLeg.style.top = (TOPS + priceH + 3) + 'px';
      this.volLeg.innerHTML = '<span style="color:' + NOTE + ';margin-right:5px;">거래량</span><span style="font-variant-numeric:tabular-nums;">' + fmt(vb[5], 0) + '</span><button type="button" aria-label="거래량 끄기" data-x="vol" style="' + CHIP + '">' + X_SVG + '</button>';
      this.volLeg.querySelector('[data-x]').onclick = function () { self.on.lower = 'none'; self.topBar(); self.draw(); };
    } else if (lowerH) {
      this.volLeg.style.display = 'flex'; this.volLeg.style.top = (TOPS + priceH + 3) + 'px';
      this.volLeg.innerHTML = '<span style="color:' + NOTE + ';">' + (this.on.lower === 'macd' ? 'MACD' : 'RSI') + '</span>';
    } else this.volLeg.style.display = 'none';
    // 닫은 것 다시 켜기
    var rs = [];
    if (!this.maOn) rs.push(['ma', '+ 이동평균']);
    this.restore.innerHTML = ''; this.restore.style.display = rs.length ? 'flex' : 'none';
    rs.forEach(function (r) {
      var b = el('button', 'font:inherit;font-size:13px;line-height:19px;padding:2px 8px;border:1px solid #E2E8F0;border-radius:6px;background:#fff;color:' + NOTE + ';cursor:pointer;', r[1]);
      b.onclick = function () { if (r[0] === 'ma') self.maOn = true; else self.on.lower = 'vol'; self.topBar(); self.draw(); };
      self.restore.appendChild(b);
    });
  };
  function init() { document.querySelectorAll('[data-candle]').forEach(function (r) { if (!r.__c) r.__c = new Chart(r); }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
