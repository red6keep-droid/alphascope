/* AlphaScope 봉차트 — 페이지 안에서 직접 그리는 실제 차트 (2026-11-13 사용자: "그림 말고 실제 차트 · 넘겨보기 · 주봉 · 손가락 확대 · 전체 화면 · 볼린저 · MACD").
   [data-candle] 요소마다 하나. 자료 = data-candle 속성의 JSON {name, dec, bars:[[날짜,시,고,저,종,거래량],...], avg?:{price,label}}.
   새 수집 · AI 0 — 페이지를 만들 때 이미 받은 일봉을 넣고, 주봉 · 월봉 · 지표는 브라우저가 계산한다.
   디자인 규칙: 증감 색(빨강 상승 · 파랑 하락) · 비교 = 얇은 실선 · 기준선(평단 · 0 · RSI 30/70) = 점선 · 마지막 값 = 오른쪽 · 정수 px.
   매수 · 매도 같은 판단 말은 그리지 않는다(지표 교차 표시 없음). 테마로 옮길 수 있게 한 번만 돈다. */
(function () {
  if (window.__asCandle) return;
  window.__asCandle = 1;
  var VIO = '#6D28D9', UP = '#d93025', DN = '#1a73e8', UPL = '#F5B5AF', DNL = '#A9C9F5', GRID = '#ECF0F5', NOTE = '#6B7280', INK = '#111';
  var MA_COL = { 5: '#9CA3AF', 20: '#5FBFAF', 60: '#BFA2E8', 120: '#F5B971', 200: '#E879A6' };
  var VIEW = { D: 60, W: 52, M: 36 }, MIN_N = 15, MAX_N = 400, AXIS_W = 58;

  function agg(d, u) {
    if (u === 'D') return d;
    var out = [], cur = null, key = function (s) {
      if (u === 'M') return s.slice(0, 7);
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
  function pct(v) { return (v > 0 ? '▲' : v < 0 ? '▼' : '') + Math.abs(v).toFixed(2) + '%'; }
  function md(s) { return s.slice(5, 7).replace(/^0/, '') + '.' + s.slice(8, 10); }
  function ticks(lo, hi, n) {
    var span = hi - lo || Math.abs(hi) || 1, raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), st = [1, 2, 2.5, 5, 10].map(function (k) { return k * p; }).find(function (k) { return k >= raw; });
    var o = []; for (var t = Math.ceil(lo / st) * st; t <= hi + 1e-9; t += st) o.push(+t.toFixed(10)); return o;
  }
  function el(tag, css, html) { var e = document.createElement(tag); if (css) e.style.cssText = css; if (html !== undefined) e.innerHTML = html; return e; }
  function btn(txt, on) {
    return el('button', 'font:inherit;font-size:14px;line-height:20px;padding:4px 10px;border-radius:6px;cursor:pointer;border:1px solid ' + (on ? '#111' : '#E2E8F0') +
      ';background:' + (on ? '#111' : '#fff') + ';color:' + (on ? '#fff' : '#111') + ';', txt);
  }

  function Chart(root) {
    var self = this;
    this.root = root; this.d = JSON.parse(root.getAttribute('data-candle')); this.dec = this.d.dec || 0;
    this.unit = 'D'; this.full = false;
    this.on = { ma: { 20: true, 60: true }, boll: false, lower: 'none' };   // 페이지 안 = 아래 칸 없음(가격 칸을 크게, 2026-11-13 사용자) · 전체 화면 = 거래량부터
    root.innerHTML = '';
    this.top = el('div', 'display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 8px;');
    this.val = el('span', 'font-size:15px;line-height:22px;white-space:nowrap;font-variant-numeric:tabular-nums;');   // 종가 + 증감만 (누른 날이면 그날)
    this.cv = el('canvas', 'display:block;width:100%;touch-action:pan-y;cursor:crosshair;');
    root.appendChild(this.top); root.appendChild(this.cv);
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
    this.n = Math.min(VIEW[this.unit], this.bars.length); this.end = this.bars.length; this.hover = null;
    this.topBar();
  };
  Chart.prototype.topBar = function () {
    var self = this, t = this.top; t.innerHTML = '';
    // 일 → 주 → 월 → 일 한 버튼으로 돌아간다 (2026-11-13 사용자)
    var cyc = btn({ D: '일', W: '주', M: '월' }[this.unit], false); cyc.style.minWidth = '40px';
    cyc.setAttribute('aria-label', '일봉 · 주봉 · 월봉 바꾸기');
    cyc.onclick = function () { self.unit = { D: 'W', W: 'M', M: 'D' }[self.unit]; self.build(); self.draw(); }; t.appendChild(cyc);
    t.appendChild(el('span', 'flex:1;'));
    t.appendChild(this.val);
    if (this.full) {
      var ind = btn('지표', this.menu); ind.onclick = function () { self.menu = !self.menu; self.topBar(); self.draw(); }; t.appendChild(ind);
    }
    var fs = el('button', 'font:inherit;width:32px;height:30px;border:1px solid #E2E8F0;border-radius:6px;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;',
      this.full ? '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#111" stroke-width="1.6" stroke-linecap="round"><path d="M3 3l10 10M13 3L3 13"/></svg>'
                : '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#111" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/></svg>');
    fs.setAttribute('aria-label', this.full ? '닫기' : '전체 화면');
    fs.onclick = function () { self.toggleFull(); }; t.appendChild(fs);
    if (this.full && this.menu) {
      var m = el('div', 'flex-basis:100%;display:flex;flex-wrap:wrap;gap:6px;padding:8px 0 2px;');
      [5, 20, 60, 120, 200].forEach(function (n) {
        var b = btn(n + (self.unit === 'D' ? '일' : self.unit === 'W' ? '주' : '달'), !!self.on.ma[n]); b.onclick = function () { self.on.ma[n] = !self.on.ma[n]; self.topBar(); self.draw(); }; m.appendChild(b);
      });
      var bb = btn('볼린저 밴드', this.on.boll); bb.onclick = function () { self.on.boll = !self.on.boll; self.topBar(); self.draw(); }; m.appendChild(bb);
      m.appendChild(el('span', 'flex-basis:100%;height:0;'));
      [['vol', '거래량'], ['macd', 'MACD'], ['rsi', 'RSI']].forEach(function (x) {
        var b = btn('아래 : ' + x[1], self.on.lower === x[0]); b.onclick = function () { self.on.lower = x[0]; self.topBar(); self.draw(); }; m.appendChild(b);
      });
      t.appendChild(m);
    }
  };
  Chart.prototype.toggleFull = function () {
    var self = this;
    if (!this.full) {
      this.ph = document.createComment('candle');
      this.root.parentNode.insertBefore(this.ph, this.root);
      this.ov = el('div', 'position:fixed;inset:0;z-index:2147483000;background:#fff;display:flex;flex-direction:column;padding:12px 12px max(12px,env(safe-area-inset-bottom));box-sizing:border-box;');
      this.ov.appendChild(el('div', 'font-size:17px;line-height:24px;font-weight:700;color:#111;margin:0 0 8px;', this.d.name));
      this.ov.appendChild(this.root);
      document.body.appendChild(this.ov); document.documentElement.style.overflow = 'hidden';
      this.full = true; this.on.lower = 'vol'; this.on.ma = { 5: false, 20: true, 60: true, 120: false, 200: true }; this.n = Math.min(this.unit === 'D' ? 120 : VIEW[this.unit] * 2, this.bars.length);
    } else {
      this.ph.parentNode.insertBefore(this.root, this.ph); this.ph.remove(); this.ov.remove(); document.documentElement.style.overflow = '';
      this.full = false; this.menu = false; this.on = { ma: { 20: true, 60: true }, boll: false, lower: 'none' }; this.n = Math.min(VIEW[this.unit], this.bars.length); this.end = this.bars.length;
    }
    this.topBar(); this.draw();
  };
  Chart.prototype.bind = function () {
    var self = this, cv = this.cv, pts = {}, start = null, moved = false;
    function idx(x) { var r = cv.getBoundingClientRect(), pw = r.width - AXIS_W; return Math.max(0, Math.min(self.n - 1, Math.floor((x - r.left) / (pw / self.n)))) + self.end - self.n; }
    cv.addEventListener('pointerdown', function (e) {
      pts[e.pointerId] = e.clientX; cv.setPointerCapture(e.pointerId); moved = false;
      var ids = Object.keys(pts);
      start = ids.length === 2 ? { pinch: Math.abs(pts[ids[0]] - pts[ids[1]]), n: self.n, end: self.end } : { x: e.clientX, end: self.end };
    });
    cv.addEventListener('pointermove', function (e) {
      if (!(e.pointerId in pts)) { if (e.pointerType === 'mouse') { self.hover = idx(e.clientX); self.draw(); } return; }
      pts[e.pointerId] = e.clientX;
      var ids = Object.keys(pts), slot = (cv.getBoundingClientRect().width - AXIS_W) / self.n;
      if (ids.length === 2 && start.pinch) {   // 두 손가락 = 확대 · 축소 (오른쪽 끝 기준)
        var d = Math.abs(pts[ids[0]] - pts[ids[1]]) || 1;
        self.n = Math.max(MIN_N, Math.min(MAX_N, self.bars.length, Math.round(start.n * start.pinch / d))); moved = true;
      } else if (start && start.x !== undefined) {   // 옆으로 밀기 = 넘겨보기
        var dx = e.clientX - start.x;
        if (Math.abs(dx) > 4) moved = true;
        self.end = Math.max(self.n, Math.min(self.bars.length, start.end - Math.round(dx / slot)));
      }
      self.hover = null; self.draw();
    });
    function up(e) {
      if (!moved && e.type === 'pointerup') { var i = idx(e.clientX); self.hover = self.hover === i ? null : i; }
      delete pts[e.pointerId]; start = Object.keys(pts).length ? { x: pts[Object.keys(pts)[0]], end: self.end } : null; self.draw();
    }
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse' && !(e.pointerId in pts)) { self.hover = null; self.draw(); } });
    cv.addEventListener('wheel', function (e) {   // PC 휠 = 확대 · 축소 — 페이지 안에서는 Ctrl 을 누를 때만(페이지 내리기를 막지 않게)
      if (!self.full && !e.ctrlKey) return;
      e.preventDefault(); self.n = Math.max(MIN_N, Math.min(MAX_N, self.bars.length, Math.round(self.n * (e.deltaY > 0 ? 1.15 : 0.87)))); self.end = Math.max(self.end, self.n); self.draw();
    }, { passive: false });
  };
  Chart.prototype.draw = function () {
    var self = this, cv = this.cv, W = Math.floor(this.root.clientWidth); if (!W) return;
    var lowerH = this.on.lower === 'none' ? 0 : this.full ? 90 : 46, priceH = 264;
    if (this.full) {   // 전체 화면 = 남은 높이를 가격 칸이 다 쓴다
      var rest = window.innerHeight - this.cv.getBoundingClientRect().top - 16;
      priceH = Math.max(200, Math.floor(rest - lowerH - 8 - 20));
    }
    var xH = 20, gap = lowerH ? 8 : 0, H = priceH + gap + lowerH + xH, dpr = window.devicePixelRatio || 1;
    cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + 'px';
    var g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    var font = getComputedStyle(this.root).fontFamily, pw = W - AXIS_W, s = this.end - this.n, B = this.bars.slice(s, this.end), slot = pw / this.n;
    var X = function (i) { return Math.floor((i - s) * slot + slot / 2) + 0.5; };
    // 가격 범위 = 봉 + 켜진 선
    var lo = Infinity, hi = -Infinity, look = function (v) { if (v !== null && v !== undefined) { lo = Math.min(lo, v); hi = Math.max(hi, v); } };
    B.forEach(function (b) { look(b[2]); look(b[3]); });
    for (var i = s; i < this.end; i++) { for (var n in this.on.ma) if (this.on.ma[n]) look(this.ma[n][i]); if (this.on.boll) { look(this.bb.up[i]); look(this.bb.lo[i]); } }
    var avg = this.d.avg, avgIn = avg && avg.price >= lo - (hi - lo) * 0.3 && avg.price <= hi + (hi - lo) * 0.3;
    if (avgIn) look(avg.price);
    var pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
    var Y = function (v) { return Math.round(6 + (hi - v) / (hi - lo) * (priceH - 12)) + 0.5; };
    g.font = '12px ' + font; g.textBaseline = 'middle';
    ticks(lo, hi, this.full ? 6 : 4).forEach(function (t) {
      g.strokeStyle = GRID; g.lineWidth = 1; g.beginPath(); g.moveTo(0, Y(t)); g.lineTo(pw, Y(t)); g.stroke();
      g.fillStyle = NOTE; g.textAlign = 'left'; g.fillText(fmt(t, self.dec), pw + 6, Y(t));
    });
    // 볼린저 밴드 · 이동평균 (비교 = 얇은 실선)
    var line = function (arr, col, w, dash) {
      g.strokeStyle = col; g.lineWidth = w; g.setLineDash(dash || []); g.beginPath(); var on = false;
      for (var i = s; i < self.end; i++) { var v = arr[i]; if (v === null || v === undefined) { on = false; continue; } if (!on) { g.moveTo(X(i), Y(v)); on = true; } else g.lineTo(X(i), Y(v)); }
      g.stroke(); g.setLineDash([]);
    };
    if (this.on.boll) { line(this.bb.up, '#94A3B8', 1); line(this.bb.lo, '#94A3B8', 1); line(this.bb.mid, '#CBD5E1', 1); }
    for (var k in this.on.ma) if (this.on.ma[k]) line(this.ma[k], MA_COL[k], 1);
    // 봉
    var bw = Math.max(1, Math.floor(slot * 0.66)); if (bw > 2 && bw % 2 === 0) bw -= 1;
    B.forEach(function (b, j) {
      var i = s + j, x = X(i), col = b[4] >= b[1] ? UP : DN;
      g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x, Y(b[2])); g.lineTo(x, Y(b[3])); g.stroke();
      var y0 = Y(Math.max(b[1], b[4])), y1 = Y(Math.min(b[1], b[4]));
      g.fillRect(Math.round(x - bw / 2), Math.round(y0), bw, Math.max(1, Math.round(y1 - y0)));
    });
    // 최고 · 최저 (보이는 기간)
    if (this.full && B.length) {
      var hiI = 0, loI = 0; B.forEach(function (b, j) { if (b[2] > B[hiI][2]) hiI = j; if (b[3] < B[loI][3]) loI = j; });
      g.font = '12px ' + font;
      [[hiI, B[hiI][2], UP, -9, '최고'], [loI, B[loI][3], DN, 9, '최저']].forEach(function (m) {
        var x = X(s + m[0]), txt = m[4] + ' ' + fmt(m[1], self.dec) + ' (' + md(B[m[0]][0]) + ')', right = x < pw / 2;
        g.fillStyle = m[2]; g.textAlign = right ? 'left' : 'right'; g.fillText((right ? '← ' : '') + txt + (right ? '' : ' →'), x + (right ? 4 : -4), Y(m[1]) + m[3]);
      });
    }
    // 내 평단 (기준선 = 점선)
    if (avg) {
      var ya = avgIn ? Y(avg.price) : (avg.price > hi ? 7.5 : priceH - 7.5), last = this.bars[this.bars.length - 1][4], diff = (last / avg.price - 1) * 100;
      if (avgIn) { g.strokeStyle = VIO; g.lineWidth = 1; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(0, ya); g.lineTo(pw, ya); g.stroke(); g.setLineDash([]); }
      // `내 평단 15,893 ▲3.10%` — 이름 · 가격 = 보라(중립 강조), 차이 = 증감 색 (2026-11-13 사용자)
      g.font = '12px ' + font; g.textAlign = 'left';
      var lab = (avg.label || '내 평단') + ' ' + fmt(avg.price, self.dec) + ' ', dtx = pct(diff) + (avgIn ? '' : avg.price > hi ? ' ↑' : ' ↓');
      var w1 = Math.ceil(g.measureText(lab).width), w2 = Math.ceil(g.measureText(dtx).width), ly2 = Math.round(ya + (avgIn ? -9 : 0));
      g.fillStyle = 'rgba(255,255,255,.85)'; g.fillRect(2, ly2 - 9, w1 + w2 + 6, 18);   // 글자 뒤 흰 바탕 — 봉과 겹쳐도 읽히게
      g.fillStyle = VIO; g.fillText(lab, 5, ly2);
      g.fillStyle = diff > 0 ? UP : diff < 0 ? DN : INK; g.fillText(dtx, 5 + w1, ly2);
    }
    // 마지막 종가 = 오른쪽 칸 (점과 같은 높이)
    if (this.end === this.bars.length && B.length) {
      var lb = B[B.length - 1], prev = this.bars[this.bars.length - 2], ch = prev ? (lb[4] / prev[4] - 1) * 100 : 0, ly = Y(lb[4]), tc = ch >= 0 ? UP : DN;
      g.fillStyle = tc; g.fillRect(pw + 1, Math.round(ly - 9), AXIS_W - 1, 18);
      g.fillStyle = '#fff'; g.font = '700 12px ' + font; g.textAlign = 'left'; g.fillText(fmt(lb[4], self.dec), pw + 5, ly);
    }
    // 아래 칸
    var top2 = priceH + gap, Y2;
    if (lowerH) { g.strokeStyle = '#E2E8F0'; g.beginPath(); g.moveTo(0, top2 - gap / 2 + 0.5); g.lineTo(W, top2 - gap / 2 + 0.5); g.stroke(); }
    g.font = '12px ' + font;
    if (!lowerH) { /* 페이지 안 = 아래 칸 없음 */ } else if (this.on.lower === 'vol') {
      var vm = Math.max.apply(null, B.map(function (b) { return b[5]; })) || 1;
      B.forEach(function (b, j) { var x = X(s + j), h = Math.round(b[5] / vm * (lowerH - 4)); g.fillStyle = b[4] >= b[1] ? UPL : DNL; g.fillRect(Math.round(x - bw / 2), top2 + lowerH - h, bw, h); });
      g.fillStyle = NOTE; g.textAlign = 'left'; g.fillText('거래량', pw + 6, top2 + 8);
    } else {
      var ser = this.on.lower === 'macd' ? [this.mc.line, this.mc.sig, this.mc.hist] : [this.rs], l2 = Infinity, h2 = -Infinity;
      for (var i2 = s; i2 < this.end; i2++) ser.forEach(function (a) { if (a[i2] !== null) { l2 = Math.min(l2, a[i2]); h2 = Math.max(h2, a[i2]); } });
      if (this.on.lower === 'rsi') { l2 = 0; h2 = 100; }
      if (l2 === Infinity) { l2 = -1; h2 = 1; }
      Y2 = function (v) { return Math.round(top2 + 2 + (h2 - v) / (h2 - l2 || 1) * (lowerH - 4)) + 0.5; };
      var ref = this.on.lower === 'rsi' ? [30, 70] : [0];
      ref.forEach(function (r) { g.strokeStyle = '#CBD5E1'; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(0, Y2(r)); g.lineTo(pw, Y2(r)); g.stroke(); g.setLineDash([]); g.fillStyle = NOTE; g.textAlign = 'left'; g.fillText(String(r), pw + 6, Y2(r)); });
      if (this.on.lower === 'macd') {
        for (var i3 = s; i3 < this.end; i3++) { var hv = this.mc.hist[i3]; if (hv === null) continue; var y0b = Y2(0), y1b = Y2(hv); g.fillStyle = hv >= 0 ? UPL : DNL; g.fillRect(Math.round(X(i3) - bw / 2), Math.min(y0b, y1b), bw, Math.max(1, Math.abs(y1b - y0b))); }
      }
      var line2 = function (arr, col) { g.strokeStyle = col; g.lineWidth = 1; g.beginPath(); var on = false; for (var i = s; i < self.end; i++) { var v = arr[i]; if (v === null) { on = false; continue; } if (!on) { g.moveTo(X(i), Y2(v)); on = true; } else g.lineTo(X(i), Y2(v)); } g.stroke(); };
      if (this.on.lower === 'macd') { line2(this.mc.line, '#F5B971'); line2(this.mc.sig, '#BFA2E8'); } else line2(this.rs, '#5FBFAF');
      g.fillStyle = NOTE; g.textAlign = 'left'; g.fillText(this.on.lower === 'macd' ? 'MACD' : 'RSI', pw + 6, top2 + 8);
    }
    // 가로축 — 달(주봉 · 일봉) 또는 해(월봉)가 바뀌는 첫 봉
    g.fillStyle = NOTE; g.textAlign = 'center'; var lastX = -99;
    B.forEach(function (b, j) {
      var p = j ? B[j - 1][0] : (self.bars[s - 1] || [''])[0], key = self.unit === 'M' ? 4 : 7;
      if (p && b[0].slice(0, key) !== p.slice(0, key)) {
        var x = X(s + j); if (x - lastX < 46) return; lastX = x;
        g.fillText(self.unit === 'M' ? b[0].slice(0, 4) : b[0].slice(2, 4) + '.' + b[0].slice(5, 7).replace(/^0/, ''), Math.min(Math.max(x, 18), pw - 18), H - xH / 2);
      }
    });
    // 누른 날
    var hi_ = this.hover, sel = hi_ !== null && hi_ >= s && hi_ < this.end ? hi_ : null, b = this.bars[sel === null ? this.end - 1 : sel], pb = this.bars[(sel === null ? this.end - 1 : sel) - 1];
    if (sel !== null) {   // 누른 날 = 세로선 + 가로축 날짜 칸
      g.strokeStyle = '#94A3B8'; g.lineWidth = 1; g.beginPath(); g.moveTo(X(sel), 0); g.lineTo(X(sel), H - xH); g.stroke();
      var dl = this.unit === 'M' ? b[0].slice(0, 4) + '.' + b[0].slice(5, 7).replace(/^0/, '') : this.unit === 'W' ? (function () { var x = new Date(b[0] + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() - (x.getUTCDay() + 6) % 7); return md(x.toISOString()) + ' 주'; })() : md(b[0]);
      g.font = '12px ' + font; var dw = Math.ceil(g.measureText(dl).width) + 10, dx = Math.min(Math.max(X(sel) - dw / 2, 0), pw - dw);
      g.fillStyle = '#4B5563'; g.fillRect(Math.round(dx), H - xH + 1, dw, xH - 2); g.fillStyle = '#fff'; g.textAlign = 'center'; g.fillText(dl, Math.round(dx + dw / 2), H - xH / 2);
    }
    if (b) {   // 맨 위 = 종가 + 증감만 (2026-11-13 사용자)
      var c1 = pb ? (b[4] / pb[4] - 1) * 100 : 0, cc = c1 > 0 ? UP : c1 < 0 ? DN : INK;
      this.val.innerHTML = '<b style="color:' + INK + ';font-weight:700;">' + fmt(b[4], this.dec) + '</b> <span style="color:' + cc + ';">' + pct(c1) + '</span>';
    }
  };
  function init() { document.querySelectorAll('[data-candle]').forEach(function (r) { if (!r.__c) r.__c = new Chart(r); }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
