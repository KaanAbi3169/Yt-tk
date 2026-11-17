"""Technische Pruefung (Stufe 1 des Pruef-Agenten) fuer Titel, Beschreibung und Tags eines Videos.

    python -m yt_tk.textcheck <datei.json> [...]    # Dateien im Format von inventory set_texts
Regeln aus docs/STIL.md ("Texte pro Plattform"). Exit 1, wenn eine Datei durchfaellt."""
import json
import re
import sys
from pathlib import Path

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆↔-↪⏩-⏺]")
HASHTAG = re.compile(r"#\w+", re.UNICODE)


def check(t: dict) -> list:
    errs = []
    for k in ("title_tiktok", "title_youtube", "text_tiktok", "text_youtube"):
        if not (t.get(k) or "").strip():
            errs.append(f"{k} fehlt")
    if errs:
        return errs
    if len(t["title_tiktok"]) > 90:
        errs.append(f"title_tiktok {len(t['title_tiktok'])} Zeichen (max 90)")
    joined = re.sub("\u200d[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", t["title_tiktok"])  # Zusammengesetzte Emojis (ZWJ) zaehlen einmal
    if len(EMOJI.findall(joined)) != 1:
        errs.append("title_tiktok braucht genau 1 Emoji")
    if len(t["title_youtube"]) > 100:
        errs.append(f"title_youtube {len(t['title_youtube'])} Zeichen (max 100)")
    if not t["title_youtube"].endswith(" #shorts"):
        errs.append("title_youtube muss auf ' #shorts' enden")
    tt, ty = HASHTAG.findall(t["text_tiktok"]), HASHTAG.findall(t["text_youtube"])
    if not 4 <= len(tt) <= 6:
        errs.append(f"text_tiktok {len(tt)} Hashtags (4 bis 6)")
    if not 4 <= len(ty) <= 6 or "#shorts" not in ty:
        errs.append(f"text_youtube {len(ty)} Hashtags (4 bis 6, inkl. #shorts)")
    if "Stimme und Grafiken mit KI erstellt." not in t["text_youtube"]:
        errs.append("text_youtube ohne KI-Hinweis")
    for k in ("text_tiktok", "text_youtube"):
        if "?" not in t[k]:
            errs.append(f"{k} ohne Frage")
    return errs


def main(argv: list) -> int:
    bad = 0
    for a in argv:
        errs = check(json.loads(Path(a).read_text(encoding="utf-8")))
        if errs:
            bad += 1
            print(Path(a).name, "FEHLER:", "; ".join(errs))
    print(f"{len(argv) - bad} von {len(argv)} bestanden")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
