"""Prueft die Beschreibung eines 3D-Videos im Szenenbaukasten (render3d/scenes/kit.js), bevor gerendert wird.

    python3 -m yt_tk.kitcheck content3d/K001.json [...]

Fehler (Exit 1): unbekannte Kulisse, Bauteil oder Aktion, doppelte oder fehlende IDs, fehlende Pflichtangaben, Beats ohne Bauteil,
Kamera-Einstellung nicht definiert. Warnungen: Anker passt auf kein gesprochenes Wort (nur mit Wortzeiten), Bauteil ausserhalb der
sicheren Zone. Format: render3d/KIT.md.
"""
import json
import re
import sys
from pathlib import Path

SETS = {"sunset", "night", "room", "studio"}
TYPES = {"text", "stamp", "bubble", "counter", "box", "sphere", "cylinder", "bar", "arrow", "monitor", "console", "calendar", "photo", "figure"}
ACTIONS = {"in", "pop", "out", "move", "grow", "spin", "pulse", "pose", "flip", "count", "cam", "shake"}
POSES = {"idle", "point", "wave", "think", "cheer", "shrug"}
NEEDS = {"move": ["to"], "grow": ["to"], "pose": ["pose"], "count": ["to"], "cam": ["shot"]}
ONLY = {"flip": {"calendar"}, "count": {"counter", "text"}, "pose": {"figure"}, "grow": None}
TEXTY = {"text", "stamp", "bubble", "counter"}
CAPTION_Y = 3.2   # darunter liegen die Untertitel (T003: y 2.95 verdeckt, T002: y 3.3 frei)
MAX_X = 1.85      # darueber ragen Beschriftungen aus dem Bild (T002: Germanium x 1.2 + w 1.9 / 2)
NUMWORDS = re.compile(r"(zig|ßig|ssig|hundert|zehn)", re.I)
SAFE_Y = (2.6, 6.3)  # sichtbarer, nicht von Untertiteln und Bedienelementen verdeckter Bereich (Weltkoordinaten, Standardkamera)


def norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower(), flags=re.UNICODE).replace("_", "")


def check(cfg: dict, words: list = None) -> tuple:
    """(fehler, warnungen)"""
    errs, warns = [], []
    k = cfg.get("kit")
    if not isinstance(k, dict):
        return ["kit fehlt"], []
    if k.get("set", "night") not in SETS:
        errs.append(f"Kulisse unbekannt: {k.get('set')}")
    ids = {}
    for p in k.get("props", []):
        i = p.get("id")
        if not i or i in ids:
            errs.append(f"Bauteil-ID fehlt oder doppelt: {i}")
            continue
        if p.get("type") not in TYPES:
            errs.append(f"{i}: Bauteil unbekannt: {p.get('type')}")
        if p.get("type") == "photo" and not p.get("image"):
            errs.append(f"{i}: photo braucht image (Bild-ID, siehe images.json)")
        if p.get("type") in ("text", "stamp") and not p.get("text"):
            errs.append(f"{i}: text fehlt")
        ids[i] = p
        pos = p.get("pos", [0, 0, 0])
        # Layout-Waechter (gemessene Fehler T002 und T003): Beschriftungen duerfen nicht auf den Untertiteln liegen und nicht ueber den
        # Bildrand ragen. Mit "free": true im Bauteil bewusst ausnehmen.
        if (p.get("type") in TEXTY and isinstance(pos, list) and len(pos) == 3 and not p.get("free")):
            if pos[1] < CAPTION_Y:
                errs.append(f"{i}: y={pos[1]} liegt auf den Untertiteln (Beschriftungen mindestens y={CAPTION_Y})")
            w = p.get("w", 1.4)
            if abs(pos[0]) + w / 2 > MAX_X:
                errs.append(f"{i}: ragt seitlich aus dem Bild (x={pos[0]}, w={w}, erlaubt bis +-{MAX_X})")
        if isinstance(pos, list) and len(pos) == 3 and p.get("type") not in ("figure",) and not (SAFE_Y[0] <= pos[1] <= SAFE_Y[1]) and p.get("show"):
            warns.append(f"{i}: y={pos[1]} ausserhalb der sicheren Zone {SAFE_Y}")
    shots = set(k.get("cams", {}))
    for n, c in k.get("cams", {}).items():
        if not (isinstance(c.get("pos"), list) and isinstance(c.get("look"), list)):
            errs.append(f"Kamera {n}: pos und look fehlen")
    for b in k.get("beats", []):
        a = b.get("do")
        if a not in ACTIONS:
            errs.append(f"Aktion unbekannt: {a}")
            continue
        if a not in ("cam", "shake"):
            i = b.get("id")
            if i not in ids:
                errs.append(f"Beat {a}: Bauteil unbekannt: {i}")
            else:
                only = ONLY.get(a)
                if only and ids[i].get("type") not in only:
                    errs.append(f"Beat {a}: gilt nur fuer {sorted(only)}, nicht fuer {ids[i].get('type')} ({i})")
        for need in NEEDS.get(a, []):
            if need not in b:
                errs.append(f"Beat {a}: {need} fehlt")
        if a == "cam" and b.get("shot") not in shots:
            errs.append(f"Kamera-Einstellung nicht definiert: {b.get('shot')}")
        if a == "pose" and b.get("pose") not in POSES:
            errs.append(f"Pose unbekannt: {b.get('pose')}")
        at = b.get("at")
        if at is None or not isinstance(at, (int, float, str)):
            errs.append(f"Beat {a}: at fehlt")
        elif isinstance(at, str):
            try:
                re.compile(at)
            except re.error:
                errs.append(f"Beat {a}: at ist kein gueltiges Muster: {at}")
                continue
            if NUMWORDS.search(at) and not re.search(r"[0-9]", at) and f"Anker {at}" not in " ".join(warns):
                warns.append(f"Anker {at}: Whisper schreibt Zahlen als Ziffern, Muster mit Ziffer ergaenzen (z. B. 1869|neunundsechzig)")
            if words is not None and not [w for w in words if re.search(at, norm(w["w"]), re.I)]:
                (warns if b.get("fallback") is not None else errs).append(f"Anker passt auf kein gesprochenes Wort: {at}")
    return errs, warns


def main(argv: list) -> int:
    bad = 0
    for a in argv:
        errs, warns = check(json.loads(Path(a).read_text(encoding="utf-8")))
        for w in warns:
            print(f"{a}: Warnung: {w}")
        if errs:
            bad += 1
            print(f"{a}: " + "; ".join(errs))
        else:
            print(f"{a}: ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
