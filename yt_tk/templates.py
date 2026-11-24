"""Formatvorlagen fuer Kurzvideos (Auftrag des Inhabers 23.11.2026: "andere Videos, nicht nur eine Art"): aus einer kurzen Beschreibung
(specs3d/<ID>.json) entsteht content3d/<ID>.json fuer den Szenenbaukasten (render3d.yml). Layout, Sicherheitszonen und Beats sind
fest, nur Inhalt und Farben wechseln.

    python3 -m yt_tk.templates build specs3d/Q001.json      # schreibt content3d/Q001.json und prueft mit kitcheck und textcheck

Typen:
  quiz        Frage, drei Antworten, Countdown, Aufloesung (Antwort gruen, Rest weg), Zahl zur Antwort
  ranking     Top 3: Platz 3, 2, 1 erscheinen von unten nach oben, Platz 1 hebt sich ab
  vergleich   2 bis 4 Balken im Groessenvergleich, wachsen nacheinander (Wert oben, Name unten)
Das Spezifikations-Feld "script" ist der gesprochene Text, "anchors" die Wortmuster (Ziffer und Zahlwort, Whisper schreibt Ziffern)."""
import json
import sys
import zlib
from pathlib import Path

from . import kitcheck, textcheck

ROOT = Path(__file__).resolve().parent.parent
# Farbwelten: Kulisse, Balken-/Akzentfarben, Figur. Wechseln je Video (nach Hash der ID), damit nicht jedes Video gleich aussieht.
LOOKS = [
    {"set": "studio", "a": "#ffb020", "b": "#5bc0eb", "c": "#7ee0a1", "shirt": "#e0603a", "pants": "#2d5a9a"},
    {"set": "night", "a": "#ffd24a", "b": "#ff6b9d", "c": "#7ee0f0", "shirt": "#7c4dff", "pants": "#263238"},
    {"set": "sunset", "a": "#ffe066", "b": "#ff8a5c", "c": "#9be37a", "shirt": "#1e88a8", "pants": "#4a2f6b"},
    {"set": "room", "a": "#ff7043", "b": "#42a5f5", "c": "#66bb6a", "shirt": "#fdd835", "pants": "#37474f"},
    {"set": "space", "a": "#ff8a5c", "b": "#a98bff", "c": "#7ee0f0", "shirt": "#26a69a", "pants": "#3949ab"},
    {"set": "ocean", "a": "#ffd24a", "b": "#7ee0f0", "c": "#9be37a", "shirt": "#ec407a", "pants": "#1b3a57"},
]


def look(spec: dict) -> dict:
    if spec.get("look") is not None:
        return LOOKS[spec["look"] % len(LOOKS)]
    return LOOKS[zlib.crc32(spec["id"].encode()) % len(LOOKS)]


def stamp(i, text, y, w=3.2, h=0.55, bg="#ffd24a", color="#12183a", x=0.0, size=110, z=1.4, **kw):
    d = {"id": i, "type": "stamp", "text": text, "w": w, "h": h, "size": size, "radius": 18, "color": color, "bg": bg, "pos": [x, y, z], "show": False}
    d.update(kw)
    return d


def at(pattern, **kw):
    """Anker: Muster als Text oder [Muster, n] (n-tes Treffer-Wort, z. B. beim zweiten Vorkommen von "drei")."""
    if isinstance(pattern, list):
        kw = dict(kw, n=pattern[1])
        pattern = pattern[0]
    return dict({"at": pattern}, **kw)


def base_kit(spec, L):
    return {"set": L["set"], "cams": {"start": {"pos": [-0.3, 4.3, 9.2], "look": [0, 4.3, 0]}, "nah": {"pos": [0.3, 4.4, 8.3], "look": [0, 4.4, 0]}}}


def fig(L):
    return {"id": "fig", "type": "figure", "pos": [-1.3, 0, 1.6], "rot": 0.4, "scale": 0.7, "shirt": L["shirt"], "pants": L["pants"]}


def build_quiz(spec):
    L, A = look(spec), spec["anchors"]
    letters = "ABC"
    ys = [5.0, 4.35, 3.7]
    props = [stamp("q", spec["question"], 6.0, w=3.5, h=0.62, bg=L["b"], size=100)]
    beats = [{"at": 0.2, "id": "q", "do": "pop"}]
    for k, o in enumerate(spec["options"]):
        props.append(stamp(f"o{k}", f"{letters[k]}   {o}", ys[k], w=3.2, h=0.55, bg=L["a"]))
        if k == spec["answer"]:
            props.append(stamp(f"r{k}", f"{letters[k]}   {o}", ys[k], w=3.2, h=0.55, bg="#43c463", color="#ffffff", z=1.7))
        beats.append(at(A["options"][k], fallback=0.2 + 0.1 * k, id=f"o{k}", do="pop"))
    props.append({"id": "cnt", "type": "counter", "fmt": "{n}", "from": 3, "w": 1.0, "h": 0.9, "size": 260, "color": "#ffffff", "pos": [0, 6.0, 1.4], "show": False})
    props.append(stamp("fact", spec["reveal_label"], 6.0, w=3.2, h=0.62, bg="#43c463", color="#ffffff", size=110))
    ans = spec["answer"]
    beats += [
        at(A["count"], fallback=0.5, id="q", do="out"),
        at(A["count"], fallback=0.5, id="cnt", do="pop"),
        at(A["count"], fallback=0.5, id="cnt", do="count", **{"from": 3, "to": 1, "dur": 2.2, "fmt": "{n}"}),
        at(A["count"], fallback=0.5, id="fig", do="pose", pose="think"),
        at(A["reveal"], fallback=0.62, id="cnt", do="out"),
        at(A["reveal"], fallback=0.62, id=f"r{ans}", do="pop"),
        at(A["reveal"], fallback=0.62, offset=0.1, id="fact", do="pop"),
        at(A["reveal"], fallback=0.62, id="fig", do="pose", pose="cheer"),
    ]
    for k in range(3):
        if k != ans:
            beats.append(at(A["reveal"], fallback=0.62, id=f"o{k}", do="out"))
    beats.append(at(A["reveal"], fallback=0.62, id=f"o{ans}", do="out"))
    beats += [at(A["end"], fallback=0.95, id="fig", do="pose", pose="wave"), {"at": 1.0, "do": "cam", "shot": "nah", "dur": 28}]
    kit = base_kit(spec, L)
    kit["props"], kit["beats"] = props + [fig(L)], beats
    return kit


def build_ranking(spec):
    L, A = look(spec), spec["anchors"]
    items = spec["items"]  # Platz 3, 2, 1 in dieser Reihenfolge der Nennung
    ys = {3: 3.75, 2: 4.55, 1: 5.35}
    cols = {3: L["b"], 2: L["c"], 1: L["a"]}
    props = [stamp("head", spec["headline"], 6.3, w=3.4, h=0.6, bg="#12183a", color="#ffffff", size=100)]
    beats = [{"at": 0.2, "id": "head", "do": "pop"}]
    for k, it in enumerate(items):
        place = 3 - k
        props.append(stamp(f"p{place}", f"{place}   {it['name']}  ·  {it['value']}", ys[place], w=3.5, h=0.62, bg=cols[place], size=100))
        beats.append(at(A["places"][k], fallback=0.18 + 0.28 * k, id=f"p{place}", do="pop"))
        beats.append(at(A["places"][k], fallback=0.18 + 0.28 * k, id="fig", do="pose", pose=("think", "point", "cheer")[k]))
    beats.append(at(A["places"][2], fallback=0.64, offset=0.4, id="p1", do="pulse", dur=0.6))
    beats += [at(A["end"], fallback=0.95, id="fig", do="pose", pose="wave"), {"at": 1.0, "do": "cam", "shot": "nah", "dur": 28}]
    kit = base_kit(spec, L)
    kit["props"], kit["beats"] = props + [fig(L)], beats
    return kit


def build_vergleich(spec):
    L, A = look(spec), spec["anchors"]
    items = spec["items"]
    n = len(items)
    top = max(i["value"] for i in items)
    xs = {2: [-0.7, 0.7], 3: [-1.1, 0.0, 1.1], 4: [-1.3, -0.45, 0.45, 1.3]}[n]
    w = {2: 0.9, 3: 0.75, 4: 0.6}[n]
    cols = [L["a"], L["b"], L["c"], "#ff8a8a"]
    props = [stamp("head", spec["headline"], 6.3, w=3.4, h=0.6, bg="#12183a", color="#ffffff", size=100)]
    beats = [{"at": 0.2, "id": "head", "do": "pop"}]
    for k, it in enumerate(items):
        h = max(0.12, 1.25 * it["value"] / top)
        props.append({"id": f"b{k}", "type": "bar", "w": w, "d": 0.5, "color": cols[k], "h": 0.02, "pos": [xs[k], 3.95, 0.4], "show": True})
        props.append(stamp(f"n{k}", it["name"], 3.5, w=min(1.6, 3.4 / n), h=0.42, bg="#12183a", color="#ffffff", x=xs[k], size=90))
        props.append(stamp(f"v{k}", it["label"], 3.95 + h + 0.4, w=min(1.6, 3.4 / n), h=0.45, bg="#ffffff", color="#12183a", x=xs[k], size=100))
        beats += [at(A["items"][k], fallback=0.15 + 0.2 * k, id=f"n{k}", do="pop"),
                  at(A["items"][k], fallback=0.15 + 0.2 * k, id=f"b{k}", do="grow", to=h, dur=1.2),
                  at(A["items"][k], fallback=0.15 + 0.2 * k, offset=1.0, id=f"v{k}", do="pop")]
    beats += [at(A["end"], fallback=0.95, id="fig", do="pose", pose="wave"), {"at": 1.0, "do": "cam", "shot": "nah", "dur": 28}]
    kit = base_kit(spec, L)
    kit["props"], kit["beats"] = props + [fig(L)], beats
    return kit


BUILD = {"quiz": build_quiz, "ranking": build_ranking, "vergleich": build_vergleich}


def make(spec: dict) -> dict:
    cfg = {k: spec[k] for k in ("id", "format", "group", "topic", "hook_type", "title_tiktok", "title_youtube", "text_tiktok", "text_youtube",
                                 "highlight", "sources", "script", "status") if k in spec}
    cfg.setdefault("format", "wissen")
    cfg.setdefault("status", "ready")
    cfg["scene"] = "kit"
    cfg["kit"] = BUILD[spec["type"]](spec)
    return cfg


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[0] == "build":
        spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        cfg = make(spec)
        errs = kitcheck.check(cfg)[0] + textcheck.check(cfg)
        if errs:
            print("FEHLER: " + "; ".join(errs))
            return 1
        out = ROOT / "content3d" / f"{spec['id']}.json"
        out.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{out.name} geschrieben ({spec['type']}, Kulisse {cfg['kit']['set']})")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
