/* 종목 고정 페이지 `stock`(독자에게 보이는 이름 = 종목 주가, 2026-11-14 사용자: 독자 화면에 `간단 정보` 말 금지) — 주소 뒤 종목 코드(?s=UBER · ?s=259960)로 카드 조각을 받아 끼워 넣는다 (2026-11-14, 기획 6-3-1 · 6-6).
   카드 HTML 은 매일 파이썬이 정식 종목 렌더러로 만든다(experiments/stock-quick/full_us.py · full_kr.py) → 기록 없는 브랜치 quick-us · quick-kr.
   읽는 순서: @quick-us/version.json(매일 purge) → 커밋 번호 → @<커밋>/us/UBER.html. 커밋 번호 주소는 내용이 안 바뀌어 캐시를 지울 일이 없다.
   **동기로 받는다** — 본문을 읽는 그 자리에서 끼워 넣어야 테마의 탭 · 봉차트 · 툴팁(페이지를 열 때 한 번 도는 스크립트)이 일반 글처럼 붙는다
   (2026-11-14 목업: 비동기로 나중에 끼우면 탭이 안 생기고 봉차트가 빈 칸). 방문자 한 명 = 요청 2번 · 압축 약 33KB.
   jsDelivr 가 안 되면 GitHub 원본 주소로 한 번 더, 그것도 안 되면 안내 한 줄.
   목업(로컬): <div id="as-quick" data-local="quick-data/" data-default="UBER"> — 커밋 번호 없이 같은 폴더에서 읽는다. */
(function () {
  var root = document.getElementById('as-quick');
  if (!root) return;
  var CDN = 'https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@';
  var RAW = 'https://raw.githubusercontent.com/red6keep-droid/alphascope/';
  var LIST_US = root.getAttribute('data-list-us') || '/p/us-market-cap-top10.html';
  var LIST_KR = root.getAttribute('data-list-kr') || '/p/kr-market-cap-top10.html';
  var local = root.getAttribute('data-local');
  var q = '';
  try { q = new URLSearchParams(location.search).get('s') || ''; } catch (e) { q = ''; }
  var s = (q || root.getAttribute('data-default') || '').toUpperCase().replace(/\.(KS|KQ)$/, '').replace(/[^A-Z0-9\-]/g, '').slice(0, 12);

  // 안내 — 독자에게 보이는 말. 상황마다 다르게: 종목을 안 고름 · 우리가 다루지 않는 코드 · 잠시 못 불러옴 (2026-11-14 사용자)
  function msg(t) {
    root.innerHTML = '<p style="font-size:17px;line-height:30px;color:#333;margin:12px 0;padding-left:6px;word-break:keep-all;">' + t + '</p>' +
      '<p style="font-size:17px;line-height:30px;margin:0 0 12px;padding-left:6px;">' +
      '<a href="' + LIST_US + '" style="color:#111;">미국 종목 목록</a> · <a href="' + LIST_KR + '" style="color:#111;">한국 종목 목록</a></p>';
  }
  if (!s) { msg('보고 싶은 종목을 종목 목록에서 골라 주세요.'); return; }
  var kr = /^\d{6}$/.test(s);
  var branch = kr ? 'quick-kr' : 'quick-us';
  var path = (kr ? 'kr/' : 'us/') + s + '.html';

  var notFound = false;   // 자료 서버가 응답했는데 그 종목 파일이 없다 = 우리가 다루지 않는 코드
  function getSync(url) {
    try {
      var x = new XMLHttpRequest();
      x.open('GET', url, false);
      x.send(null);
      if (x.status >= 200 && x.status < 300) return x.responseText;
      if (x.status === 404) notFound = true;
    } catch (e) { /* 막히면 다음 주소 */ }
    return null;
  }
  function show(html) {
    root.innerHTML = html;
    var go = root.querySelector('[data-redirect]');
    if (go && !local) { try { location.replace(go.getAttribute('data-redirect')); } catch (e) { /* 버튼이 남는다 */ } }   // 정식 종목 = 종목 분석 페이지로
    var nm = root.querySelector('[data-quick-title]');
    if (nm) {
      document.title = nm.getAttribute('data-quick-title') + ' | ' + document.title.split(' | ').pop();
      var h = document.querySelector('.post-title, h1');
      if (h) h.textContent = nm.getAttribute('data-quick-title');
    }
  }

  var html = null;
  if (local) {
    html = getSync(local + path);
  } else {
    var v = null;
    try { v = JSON.parse(getSync(CDN + branch + '/version.json') || 'null'); } catch (e) { v = null; }
    if (v && v.commit) html = getSync(CDN + v.commit + '/' + path);
    if (!html) html = getSync(RAW + branch + '/' + path);   // jsDelivr 가 안 되거나 옛 커밋이 지워졌을 때 — GitHub 원본(브랜치 최신)
  }
  if (html) show(html);
  else if (notFound) msg('종목 코드 ' + s + '에 해당하는 종목을 찾지 못했습니다. 미국 S&amp;P 500 · 코스피 200 · 코스닥 150 종목을 다룹니다. 종목 목록에서 찾아 주세요.');
  else msg('지금 종목 자료를 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요.');
})();
