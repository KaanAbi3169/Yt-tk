"""Zusammenschnitt-Langvideos (V-023): Vorrats-Shorts eines Themas werden zu einem 16:9-Video von mindestens 10 Minuten.

    python -m yt_tk.compile_long --all           # baut L001 bis L003 (schon vorhandene werden uebersprungen)
    python -m yt_tk.compile_long --id L002       # nur eines
    ... --dry                                    # bauen und pruefen, aber nichts ins Inventar schreiben

Je Kurzvideo: auf 1280x720 (scharfer Hochkant-Streifen vor unscharfem Hintergrund, Einblendung mit Nummer und Thema),
vorne eine Titelkarte, hinten zusammenfuegen. Pruefung: Dauer 600 bis 900 s, Datei unter 95 MB, Kapitel mindestens 10 s.
Die Kurzvideos bleiben im Vorrat und duerfen zusaetzlich als eigener Short laufen (Anweisung des Inhabers 17.11.2026)."""
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import config, inventory, transcribe

W, H, INTRO_S = 1280, 720, 3
MAX_MB, MIN_S, MAX_S = 95, 600, 900
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf"]
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]

LONGS = {
    "L001": {
        "title": "{n} Haushaltstricks, die wirklich funktionieren: Kennst du alle?", "topic": "Haushaltstricks", "label": "Trick",
        "intro": "{n} Haushaltstricks\ndie wirklich funktionieren",
        "lead": "Haushaltstricks vom Abfluss bis zum Wasserkocher, kurz erklärt. Mit den Kapiteln springst du direkt zu deinem Problem.",
        "tags": "#haushalt #tricks #putzen #wissen",
        "parts": [("D082", "Mikrowelle ohne Schrubben"), ("D081", "Abfluss frei bekommen"), ("D065", "Backofen mit Natron reinigen"),
                  ("D061", "Fenster ohne Streifen"), ("D073", "Schimmel in der Dusche vorbeugen"), ("D074", "Küchenschwamm frisch halten"),
                  ("D084", "Sportshirt ohne Geruch"), ("D062", "Flecken richtig behandeln"), ("D083", "Staub wirklich loswerden"),
                  ("D025", "Wasserkocher entkalken")],
        "extra": [("D017", "Geschirrspüler richtig einräumen"), ("D021", "Stosslüften statt Kippen")]},
    "L002": {
        "title": "{n} Mythen und Rätsel: Wie viele davon hast du falsch gewusst?", "topic": "Mythen und Rätsel", "label": "Thema",
        "intro": "{n} Mythen und Rätsel\nwie viele kennst du?",
        "lead": "Mythen und Rätsel aus Geschichte, Natur und Weltraum: Was stimmt, was nicht? Mit den Kapiteln springst du direkt zu deinem Lieblingsthema.",
        "tags": "#mythen #wissen #geschichte #faktencheck",
        "parts": [("D024", "Napoleon: wirklich klein?"), ("D032", "Wikinger mit Hörnerhelm?"), ("D023", "Hai älter als Bäume?"),
                  ("D028", "Kleopatra und die Mondlandung"), ("D022", "Fällt Toast auf die Butterseite?"), ("D040", "Der Emu-Krieg"),
                  ("D036", "Die Tanzwut von 1518"), ("D076", "Das Geisterschiff Mary Celeste"), ("D075", "Wächst der Eiffelturm?"),
                  ("D067", "Der Mond entfernt sich")],
        "extra": [("D027", "Warum Eisbären schwarze Haut haben"), ("D031", "Wie Glühwürmchen leuchten")]},
    "L003": {
        "title": "{n} Dinge, die dein Körper und dein Gehirn tun, ohne dass du es merkst", "topic": "Körper und Gehirn", "label": "Thema",
        "intro": "{n} Dinge\ndie dein Körper ohne dich tut",
        "lead": "Dinge, die dein Körper und dein Gehirn ständig tun, vom Gähnen bis zum Déjà-vu. Mit den Kapiteln springst du direkt zu deinem Thema.",
        "tags": "#körper #gehirn #wissen #psychologie",
        "parts": [("D035", "Warum Gähnen ansteckt"), ("D039", "Gänsehaut"), ("D043", "Schluckauf"),
                  ("D047", "Warum du dich nicht selbst kitzeln kannst"), ("D051", "Hirnfrost"), ("D055", "Schrumpelfinger im Bad"),
                  ("D064", "Schlafparalyse"), ("D068", "Gesichter in Dingen sehen"), ("D072", "Déjà-vu"), ("D016", "Der Spotlight-Effekt")],
        "extra": [("D030", "Warum der Spiegel beschlägt"), ("D019", "Warum Katzen auf den Pfoten landen")]},
    "L004": {
        "title": "{n} Küchen-Tricks und Alltagsrätsel: Wie viele kennst du?", "topic": "Küche und Alltag", "label": "Thema",
        "intro": "{n} Küchen-Tricks\nund Alltagsrätsel",
        "lead": "Küchen-Tricks und kleine Alltagsrätsel vom Brot bis zur Waschmaschine. Mit den Kapiteln springst du direkt zu deinem Thema.",
        "tags": "#küche #haushalt #alltag #wissen",
        "parts": [("D033", "Brot richtig lagern"), ("D034", "Wäsche bei Frost trocknen"), ("D045", "Eier-Frischetest"),
                  ("D049", "Nudelwasser aufheben"), ("D050", "Warum Eier platzen"), ("D041", "Warum Zwiebeln zum Weinen bringen"),
                  ("D057", "Gefrierbrand vermeiden"), ("D054", "Warum Kleidung einläuft"), ("D070", "Alufolie: welche Seite?"),
                  ("D037", "Bananen und Reifegas")],
        "extra": [("D078", "Warum der Wasserkocher leiser wird"), ("D058", "Wohin verschwinden Socken?")]},
    "L005": {
        "title": "{n} Geld- und Alltagsfallen: Tappst du in die Preisfalle?", "topic": "Geld und Konsum", "label": "Thema",
        "intro": "{n} Geld- und Alltagsfallen\nkennst du alle?",
        "lead": "Preise, Abos, Zinsen und Stromfresser: Alltagsfallen rund ums Geld. Mit den Kapiteln springst du direkt zu deinem Thema.",
        "tags": "#geld #sparen #konsum #alltag",
        "parts": [("D044", "Warum alles 9.99 kostet"), ("D048", "Supermarkt-Tricks"), ("D052", "Karte oder Bargeld?"),
                  ("D056", "Die Abo-Falle"), ("D060", "Zinseszins"), ("D077", "Standby-Strom"),
                  ("D029", "Was das Haltbarkeitsdatum bedeutet"), ("D058", "Wohin verschwinden Socken?"),
                  ("D078", "Warum der Wasserkocher leiser wird"), ("D079", "Warum es Schaltjahre gibt")],
        "extra": [("D030", "Warum der Spiegel beschlägt"), ("D019", "Warum Katzen auf den Pfoten landen")]},
    "L006": {
        "title": "{n} Rätsel der Natur und Physik: Weisst du die Antworten?", "topic": "Natur und Physik", "label": "Thema",
        "intro": "{n} Rätsel der Natur\nund Physik",
        "lead": "Rätsel aus Natur und Physik: vom blauen Himmel bis zum Glühwürmchen. Mit den Kapiteln springst du direkt zu deinem Thema.",
        "tags": "#natur #physik #wissen #rätsel",
        "parts": [("D038", "Wie Salz Eis schmelzen lässt"), ("D059", "Warum der Himmel blau ist"), ("D063", "Ein Tag auf der Venus"),
                  ("D071", "Wie schwer ist eine Wolke?"), ("D027", "Warum Eisbären schwarze Haut haben"),
                  ("D031", "Wie Glühwürmchen leuchten"), ("D019", "Warum Katzen auf den Pfoten landen"),
                  ("D030", "Warum der Spiegel beschlägt"), ("D017", "Geschirrspüler richtig einräumen"), ("D021", "Stosslüften statt Kippen")],
        "extra": [("D025", "Wasserkocher entkalken"), ("D082", "Mikrowelle ohne Schrubben")]},
}


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%H:%M:%S}] {msg}", flush=True)


def font() -> str:
    f = next((p for p in FONTS if Path(p).exists()), None)
    if not f:
        raise RuntimeError("Keine Schrift gefunden")
    return f


def run(cmd: list) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr[-500:])


def encode_clip(src: Path, dst: Path, label: str, crf: int, tmp: Path) -> None:
    txt = tmp / (dst.stem + ".txt")
    txt.write_text(label, encoding="utf-8")
    vf = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:5[bg];"
          f"[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,"
          f"drawtext=fontfile={font()}:textfile={txt}:x=40:y=40:fontsize=42:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=14:"
          f"enable='lt(t,4)'[v]")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0", "-crf", str(crf), *ENC, str(dst)])


def intro_card(text: str, dst: Path, crf: int, tmp: Path) -> None:
    txt = tmp / "intro.txt"
    txt.write_text(text, encoding="utf-8")
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x101820:s={W}x{H}:d={INTRO_S}", "-f", "lavfi",
         "-i", "anullsrc=r=44100:cl=stereo", "-t", str(INTRO_S),
         "-vf", f"drawtext=fontfile={font()}:textfile={txt}:x=(w-text_w)/2:y=(h-text_h)/2:fontsize=64:fontcolor=white:line_spacing=18",
         "-crf", str(crf), *ENC, str(dst)])


def stamp(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 60}:{s % 60:02d}"


def description(cfg: dict, names: list, starts: list) -> str:
    # Kapitel 1 beginnt bei 0:00 (Titelkarte inklusive), YouTube verlangt mindestens 10 s je Kapitel
    chap = [0.0] + list(starts[1:])
    lines = [f"{len(names)} {cfg['lead']}", "", "KAPITEL"]
    lines += [f"{stamp(t)} {i}. {name}" for i, (name, t) in enumerate(zip(names, chap), 1)]
    lines += ["", "Welches Thema kanntest du noch nicht? Schreib es in die Kommentare.", "",
              "Stimme und Grafiken mit KI erstellt. Zusammenschnitt aus unseren Kurzvideos.", "", cfg["tags"]]
    return "\n".join(lines)


def build(cfg: dict, crf: int, tmp: Path, local: str = "") -> tuple:
    inv = {v["id"]: v for v in inventory._load("inventory.json", {"videos": []})["videos"]}
    parts, extra = list(cfg["parts"]), list(cfg["extra"])
    clips, starts, names, t = [], [], [], float(INTRO_S)
    i = 0
    while parts:
        vid, name = parts.pop(0)
        i += 1
        v = inv.get(vid)
        if not v or not v.get("video_url") or v["status"] == "failed":
            raise RuntimeError(f"{vid} ist nicht verfuegbar")
        src = tmp / f"s{vid}.mp4"
        if local and (Path(local) / f"{vid}.mp4").exists():
            src = Path(local) / f"{vid}.mp4"
        else:
            transcribe.download(v["video_url"], src)
        dst = tmp / f"c{i:02d}.mp4"
        encode_clip(src, dst, f"{cfg['label']} {i}: {name}", crf, tmp)
        starts.append(t)
        names.append(name)
        t += transcribe.probe_duration(dst)
        clips.append(dst)
        log(f"Teil {i} {vid} ok, Ende bei {stamp(t)}")
        if not parts and t < MIN_S + 5 and extra:  # zu kurz: naechsten Reserve-Teil anhaengen
            parts.append(extra.pop(0))
    intro = tmp / "c00.mp4"
    intro_card(cfg["intro"].format(n=len(names)), intro, crf, tmp)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in [intro, *clips]), encoding="utf-8")
    out = tmp / "out.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])
    return out, starts, names, transcribe.probe_duration(out)


def make_one(vid: str, dry: bool, local: str) -> bool:
    cfg = LONGS[vid]
    inv = inventory._load("inventory.json", {"videos": []})
    if any(v["id"] == vid for v in inv["videos"]):
        log(f"{vid} ist schon im Inventar.")
        return True
    for crf in (23, 27, 31, 35):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out, starts, names, dur = build(cfg, crf, tmp, local)
            mb = out.stat().st_size / 1e6
            log(f"{vid} CRF {crf}: {dur} s, {mb:.1f} MB, {len(names)} Teile")
            if mb <= MAX_MB:
                break
    else:
        print(f"FEHLER {vid}: Datei bleibt ueber {MAX_MB} MB")
        return False
    title = cfg["title"].format(n=len(names))
    errs = []
    if not MIN_S <= dur <= MAX_S:
        errs.append(f"Dauer {dur} s ausserhalb {MIN_S} bis {MAX_S} s")
    if len(title) > 100:
        errs.append("Titel zu lang")
    chap = [0.0] + list(starts[1:]) + [dur]
    if any(b - a < 10 for a, b in zip(chap, chap[1:])):
        errs.append("Kapitel kuerzer als 10 s")
    if errs:
        print(f"FEHLER {vid}:", "; ".join(errs))
        return False
    desc = description(cfg, names, starts)
    if dry:
        print(title, "\n", desc)
        return True
    dest = config.DATA / "videos" / f"{vid}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out.read_bytes())
    parts = [p for p, _ in cfg["parts"]][:len(names)] + [p for p, _ in cfg["extra"]][:max(0, len(names) - len(cfg["parts"]))]
    inv["videos"].append({
        "id": vid, "format": "lang", "status": "ready", "created": inventory.now().isoformat(), "source": "zusammenschnitt",
        "topic": cfg["topic"], "hook_type": "Liste + Frage", "series": None, "episode": None, "duration": dur,
        "video_url": f"{config.RAW_BASE}/videos/{vid}.mp4", "title_tiktok": "", "title_youtube": title, "text_tiktok": "",
        "text_youtube": desc, "scenes": len(names), "parts": parts, "buffer": {}})
    inventory._save("inventory.json", inv)
    log(inventory.sync(f"{vid}: Zusammenschnitt {cfg['topic']} ({dur} s, {mb:.0f} MB)"))
    print(title, "\n", desc)
    return True


def next_auto() -> list:
    """Ohne Claude: Ist der Vorrat an fertigen Langvideos kleiner als 3, wird das naechste definierte gebaut (hoechstens eins pro Lauf)."""
    inv = inventory._load("inventory.json", {"videos": []})["videos"]
    ready = sum(1 for v in inv if v["format"] == "lang" and v["status"] == "ready")
    have = {v["id"] for v in inv}
    todo = [i for i in LONGS if i not in have]
    if ready >= 3:
        log(f"{ready} Langvideos bereit, nichts zu bauen.")
        return []
    if not todo:
        print("WARN: Alle definierten Zusammenschnitte sind gebaut, neue Langvideos brauchen neue Inhalte (Claude).")
        return []
    return todo[:1]


def main(argv: list) -> int:
    if "--auto" in argv:
        ids = next_auto()
    else:
        ids = list(LONGS) if "--all" in argv else [argv[argv.index("--id") + 1]] if "--id" in argv else ["L001"]
    ok = [make_one(i, "--dry" in argv, os.environ.get("COMPILE_LOCAL", "")) for i in ids]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
