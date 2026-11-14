/* 간단 정보 고정 페이지 `stock-quick` — 주소 뒤 종목 코드(?s=UBER · ?s=259960)로 카드 조각을 받아 끼워 넣는다 (2026-11-14, 기획 6-3-1 · 6-6).
   카드 HTML 은 매일 파이썬이 만든다(experiments/stock-quick/render_quick.py) → 기록 없는 브랜치 quick-data.
   읽는 순서: @quick-data/version.json(매일 purge) → 커밋 번호 → @<커밋>/us/UBER.html. 커밋 번호 주소는 내용이 안 바뀌어 캐시를 지울 일이 없다.
   jsDelivr 가 안 되면 GitHub 원본 주소로 한 번 더. 방문자 한 명 = 요청 2번 · 압축 약 8KB.
   목업(로컬): <div id="as-quick" data-local="quick-data/" data-default="UBER"> — 커밋 번호 없이 같은 폴더에서 읽는다. */
(function () {
  var root = document.getElementById('as-quick');
  if (!root) return;
  var CDN = 'https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@';
  var RAW = 'https://raw.githubusercontent.com/red6keep-droid/alphascope/';
  var LIST = root.getAttribute('data-list') || '/p/all-stocks.html';
  var local = root.getAttribute('data-local');
  var q = '';
  try { q = new URLSearchParams(location.search).get('s') || ''; } catch (e) { q = ''; }
  var s = (q || root.getAttribute('data-default') || '').toUpperCase().replace(/\.(KS|KQ)$/, '').replace(/[^A-Z0-9\-]/g, '');

  function msg(t) {
    root.innerHTML = '<p style="font-size:17px;line-height:30px;color:#333;margin:12px 0;padding-left:6px;">' + t +
      ' <a href="' + LIST + '" style="color:#111;">전체 종목 목록</a>에서 찾아 주세요.</p>';
  }
  if (!s) { msg('종목을 고르지 않았습니다.'); return; }
  var path = (/^\d{6}$/.test(s) ? 'kr/' : 'us/') + s + '.html';

  function get(url) {
    return fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); });
  }
  function show(html) {
    root.innerHTML = html;
    var nm = root.querySelector('[data-quick-title]');
    if (nm) {
      document.title = nm.getAttribute('data-quick-title') + ' | ' + document.title.split(' | ').pop();
      var h = document.querySelector('.post-title, h1');
      if (h) h.textContent = nm.getAttribute('data-quick-title');
    }
  }
  function fail() { msg('이 종목의 간단 정보를 불러오지 못했습니다. 잠시 뒤 다시 열어 보거나,'); }

  root.innerHTML = '<p style="font-size:15px;color:#6B7280;margin:12px 0;padding-left:6px;">불러오는 중…</p>';
  if (local) { get(local + path).then(show).catch(fail); return; }
  get(CDN + 'quick-data/version.json')
    .then(function (t) { var v = JSON.parse(t); if (!v.commit) throw new Error('no commit'); return get(CDN + v.commit + '/' + path); })
    .then(show)
    .catch(function () {
      // jsDelivr 가 안 되거나 옛 커밋이 지워졌을 때 — GitHub 원본(브랜치 최신)으로 한 번 더
      get(RAW + 'quick-data/' + path).then(show).catch(fail);
    });
})();
