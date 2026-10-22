"""공직자(+기관) 얼굴 사진 — 위키백과 대표 이미지(위키미디어 공용, 공공 영역)를 받아 output/images/people 에 두고 gh-pages images/people 로 올린다.
운영지침 4-6: 인물 사진은 공직자만(2026-10-21 사용자 결정). 민간인은 글자 동그라미 — 이 목록에 넣지 말 것. 메타(라이선스 · 작성자)는 ref/people_photos.json.

    python fetch_photos.py   # 그 뒤 gh-pages 에 images/people/*.jpg 복사 · 푸시 (수동)
"""
import json, os, sys, urllib.request, urllib.parse
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "images", "people")
META = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref", "people_photos.json")
PAGES = {"trump": "Donald_Trump", "bessent": "Scott_Bessent", "lutnick": "Howard_Lutnick", "greer": "Jamieson_Greer", "fed": "Federal_Reserve"}   # 공직자 · 기관만
UA = {"User-Agent": "AlphaScope-people-radar/0.1 (redkeep@futechsoft.com)"}
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
meta = {}
for key, page in PAGES.items():
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
        import re; artist = re.sub(r"<[^>]+>", "", artist)[:80]
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        path = os.path.join(OUT, key + (".png" if ext == ".png" else ".jpg"))
        open(path, "wb").write(get(thumb))
        meta[key] = {"file": os.path.basename(path), "source_file": name, "license": lic, "author": artist, "page": "https://commons.wikimedia.org/wiki/File:" + name.replace(" ", "_")}
        print(key, os.path.basename(path), lic, "|", artist)
    except Exception as e:
        print(key, "ERR", str(e)[:100])
os.makedirs(os.path.dirname(META), exist_ok=True)
json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
