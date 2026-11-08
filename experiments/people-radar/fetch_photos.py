"""인물 얼굴 사진 — 위키백과 대표 이미지(위키미디어 공용, 자유 라이선스만)를 받아 output/images/people 에 두고 gh-pages images/people 로 올린다.
2026-10-21 공직자만 → 2026-11-08 사용자 결정으로 민간인(투자자 · CEO · 해설자)도 자유 라이선스 사진. 퍼블리시티권은 남는다는 점은 사용자 인지.
CC BY · BY-SA 는 출처 표기 의무 → render_html.photo_credit 이 사진 쓴 글 아래에 표기. 메타(라이선스 · 작성자)는 ref/people_photos.json.

    python fetch_photos.py          # 메타에 없는 인물만 받는다 (있는 건 그대로)
    python fetch_photos.py --all    # 전부 다시
    # 그 뒤 gh-pages 에 images/people/* 복사 · 푸시 (수동)
"""
import json, os, re, sys, urllib.request, urllib.parse
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "images", "people")
META = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref", "people_photos.json")
PAGES = {"trump": "Donald_Trump", "bessent": "Scott_Bessent", "lutnick": "Howard_Lutnick", "greer": "Jamieson_Greer", "fed": "Federal_Reserve",
         "burry": "Michael_Burry", "wood": "Cathie_Wood", "ackman": "Bill_Ackman", "cramer": "Jim_Cramer", "timiraos": "Nick_Timiraos",
         "musk": "Elon_Musk", "altman": "Sam_Altman", "huang": "Jensen_Huang"}
FREE = re.compile(r"^(CC BY(-SA)? [\d.]+|CC0|Public domain|PD.*)", re.I)   # 이것만 쓴다 — NC · ND · 비자유(공정 이용) 이미지는 건너뜀
UA = {"User-Agent": "AlphaScope-people-radar/0.1 (redkeep@futechsoft.com)"}
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
try:
    meta = json.load(open(META, encoding="utf-8"))
    if "--all" in sys.argv:   # 다시 받기 — 사용자가 직접 준 사진(manual)은 남긴다 (버리 · 티미라오스, 2026-11-08)
        meta = {k: v for k, v in meta.items() if v.get("manual")}
except (OSError, ValueError):
    meta = {}
for key, page in PAGES.items():
    if key in meta:
        continue
    try:
        q = ("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&piprop=name|thumbnail&pithumbsize=160&titles=" + page)
        pg = list(json.loads(get(q))["query"]["pages"].values())[0]
        name = pg.get("pageimage"); thumb = (pg.get("thumbnail") or {}).get("source")
        if not name or not thumb:
            print(key, "no image"); continue
        ii = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=extmetadata|url&titles=File:" + urllib.parse.quote(name))
        info = list(json.loads(get(ii))["query"]["pages"].values())[0]
        em = ((info.get("imageinfo") or [{}])[0].get("extmetadata") or {})
        lic = (em.get("LicenseShortName") or {}).get("value", ""); artist = (em.get("Artist") or {}).get("value", "")
        artist = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", artist)).strip()[:80]
        if not FREE.match(lic.strip()):
            print(key, "SKIP 자유 라이선스 아님:", lic or "(없음)", name); continue
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        path = os.path.join(OUT, key + (".png" if ext == ".png" else ".jpg"))
        open(path, "wb").write(get(thumb))
        meta[key] = {"file": os.path.basename(path), "source_file": name, "license": lic, "author": artist, "page": "https://commons.wikimedia.org/wiki/File:" + name.replace(" ", "_")}
        print(key, os.path.basename(path), lic, "|", artist)
    except Exception as e:
        print(key, "ERR", str(e)[:100])
os.makedirs(os.path.dirname(META), exist_ok=True)
json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
