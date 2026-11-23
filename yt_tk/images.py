"""Echte Bilder mit gesicherter Lizenz (Auftrag des Inhabers 19.11.2026): suchen, laden, Quelle klein am Rand einblenden.

    python3 -m yt_tk.images search "Gehirn Magnetresonanz" [--n 8]      # Kandidaten mit Lizenz anzeigen (nur erlaubte Lizenzen)
    python3 -m yt_tk.images search "Voyager Raumsonde" --src openverse  # zweite Quelle (Openverse: NASA u. a.), Titel "ov:<id>"
    python3 -m yt_tk.images fetch "File:Beispiel.jpg" IMG001            # laden (Wikimedia) bzw. "ov:<id>" (Openverse) (max. 1600 px breit) und Quelle in data/images.json eintragen

Erlaubt (frei nutzbar, auch mit Werbeeinnahmen): Public Domain, CC0, CC BY (Namensnennung = Quelle am Rand).
Nicht erlaubt: CC BY-SA (Weitergabe unter gleichen Bedingungen), NC, ND, GFDL, "Fair Use", Bilder mit Hinweis auf Rechte
Dritter (Marken, Persoenlichkeitsrechte). Keine erkennbaren Privatpersonen. Quelle: Wikimedia Commons (api.php).
Laeuft in der Action `images` (von der Sandbox ist Wikimedia nicht erreichbar).
"""
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from . import config, inventory

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "yt-tk-image-fetch/1.0 (automatisierter Bildabruf, keine Kontaktdaten)"}
OK_LICENSES = re.compile(r"^(public domain|pd\b|cc0|cc[- ]by[- ]\d|cc by \d|no restrictions|pdm)", re.I)
BAD = re.compile(r"(\bsa\b|-sa\b|\bnc\b|-nc\b|\bnd\b|-nd\b|gfdl|fair use|non-?commercial|no derivatives|share ?alike)", re.I)


def _get(url: str) -> bytes:
    """Mit Wiederholung: Wikimedia antwortet auf geteilten Runner-Adressen manchmal mit 429 (zu viele Anfragen)."""
    import time
    for k in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or k == 3:
                raise
            wait = int(e.headers.get("Retry-After") or 0) if e.headers else 0
            time.sleep(min(max(wait, 15 * (k + 1)), 90))


def _meta(v: dict) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", v or "")).strip()


def usable(em: dict) -> tuple:
    """(ok, grund). Prueft die Lizenzangaben aus extmetadata."""
    lic = _meta(em.get("LicenseShortName", {}).get("value"))
    if not lic:
        return False, "keine Lizenzangabe"
    if BAD.search(lic) or not OK_LICENSES.search(lic):
        return False, f"Lizenz nicht erlaubt: {lic}"
    if _meta(em.get("Restrictions", {}).get("value")):
        return False, "Hinweis auf Rechte Dritter: " + _meta(em["Restrictions"]["value"])[:60]
    return True, lic


def info(titles=None, query=None, n=8) -> list:
    params = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": "1600"}
    if query:
        params.update({"generator": "search", "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": "6", "gsrlimit": str(n * 3)})
    else:
        params["titles"] = titles
    data = json.loads(_get(API + "?" + urllib.parse.urlencode(params)))
    out = []
    for p in (data.get("query", {}).get("pages", {})).values():
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii or ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        em = ii.get("extmetadata", {})
        ok, why = usable(em)
        out.append({"title": p["title"], "ok": ok, "why": why, "license": _meta(em.get("LicenseShortName", {}).get("value")),
                    "author": _meta(em.get("Artist", {}).get("value")) or _meta(em.get("Credit", {}).get("value")),
                    "page": ii.get("descriptionurl"), "thumb": ii.get("thumburl") or ii.get("url"), "w": ii.get("width"), "h": ii.get("height")})
    return out


OV_API = "https://api.openverse.org/v1/images/"
OV_LICENSES = {"cc0": "CC0", "pdm": "Public Domain Mark", "by": "CC BY"}  # nur diese (kein sa, nc, nd)


def _ov_rec(r: dict) -> dict:
    """Openverse-Treffer in dieselbe Form wie die Wikimedia-Treffer bringen. Nur cc0, pdm und by sind erlaubt."""
    lic = (r.get("license") or "").lower()
    ok = lic in OV_LICENSES and not r.get("mature")
    ver = r.get("license_version") or ""
    label = f"{OV_LICENSES.get(lic, lic.upper() or '?')} {ver}".strip() if lic != "pdm" else OV_LICENSES["pdm"]
    return {"title": "ov:" + str(r.get("id")), "ok": ok, "why": "" if ok else f"Lizenz nicht erlaubt: {lic or '?'}",
            "license": label, "author": _meta(r.get("creator") or ""), "page": r.get("foreign_landing_url") or r.get("url"),
            "thumb": r.get("url"), "w": r.get("width"), "h": r.get("height"), "provider": r.get("provider") or r.get("source") or "Openverse"}


def ov_info(query=None, oid=None, n=8) -> list:
    """Zweite freie Bildquelle (Openverse, bündelt u. a. NASA, Smithsonian, Flickr Commons). Nur Lizenzen cc0, pdm, by."""
    if oid:
        return [_ov_rec(json.loads(_get(OV_API + urllib.parse.quote(oid) + "/")))]
    q = urllib.parse.urlencode({"q": query, "license": "cc0,pdm,by", "page_size": str(n * 2), "mature": "false", "extension": "jpg"})
    return [_ov_rec(r) for r in json.loads(_get(OV_API + "?" + q)).get("results", [])]


def credit_text(rec: dict) -> str:
    who = rec["author"][:40] if rec.get("author") else "unbekannt"
    return f"Bild: {who} / {rec['license']} / {rec.get('provider') or 'Wikimedia Commons'}"


def fetch(title: str, img_id: str) -> dict:
    if title.lower().startswith("ov:"):
        found = ov_info(oid=title[3:])
    else:
        found = [x for x in info(titles=title) if x["title"].lower() == title.lower()]
    if not found:
        raise SystemExit("Datei nicht gefunden")
    rec = found[0]
    if not rec["ok"]:
        raise SystemExit(f"Nicht verwendbar: {rec['why']}")
    dest = config.DATA / "images" / f"{img_id}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = _get(rec["thumb"])
    if rec["thumb"].lower().endswith(".png") or rec.get("provider"):  # PNG -> JPEG, Originale (Openverse) auf 1600 px verkleinern
        import io

        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((1600, 1600))
        im.save(dest, "JPEG", quality=90)
    else:
        dest.write_bytes(raw)
    entry = {"id": img_id, "file": f"images/{img_id}.jpg", "title": rec["title"], "author": rec["author"], "license": rec["license"],
             "page": rec["page"], "credit": credit_text(rec)}
    if rec.get("provider"):
        entry["provider"] = rec["provider"]
    db = inventory._load("images.json", {"images": []})
    db["images"] = [x for x in db["images"] if x["id"] != img_id] + [entry]
    inventory._save("images.json", db)
    return entry


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[0] == "search":
        n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 8
        res = ov_info(query=argv[1], n=n) if "--src" in argv and argv[argv.index("--src") + 1] == "openverse" else info(query=argv[1], n=n)
        shown = 0
        for r in res:
            if shown >= n:
                break
            print(("OK   " if r["ok"] else "NEIN ") + f"{r['title']} | {r['license'] or '?'} | {r['author'][:40]} | {r['w']}x{r['h']} | {r['why'] if not r['ok'] else r['page']}")
            shown += 1
        return 0
    if len(argv) >= 3 and argv[0] == "fetch":
        e = fetch(argv[1], argv[2])
        print(json.dumps(e, ensure_ascii=False, indent=1))
        print(inventory.sync(f"Bild {argv[2]}: {e['title']} ({e['license']})"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
