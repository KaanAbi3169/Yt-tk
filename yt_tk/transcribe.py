"""Transkription der Vorrats-Videos ohne Text (V-018), ohne Claude und ohne Kosten.

    python -m yt_tk.transcribe                 # alle Vorrats-Videos ohne Text
    python -m yt_tk.transcribe --id D033       # nur eines
    python -m yt_tk.transcribe --limit 5       # hoechstens 5 (Test)
    python -m yt_tk.transcribe --list          # nur anzeigen, was dran waere

Ablauf je Video: Drive-Datei laden -> Ton mit ffmpeg abtrennen -> Whisper (faster-whisper, Modell small, Deutsch)
-> data/transcripts/<ID>.json {text, duration} schreiben, Dauer ins Inventar eintragen. Fertige Videos werden
uebersprungen, der Lauf ist wiederholbar. Titel, Beschreibung und Tags schreibt danach der Regie-Agent.
"""
import http.cookiejar
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from . import config, inventory

UA = {"User-Agent": "Mozilla/5.0"}


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%H:%M:%S}] {msg}", flush=True)


def targets() -> list:
    inv = inventory._load("inventory.json", {"videos": []})["videos"]
    return [v for v in inv if v["status"] == "backup" and not v.get("text_youtube") and v.get("video_url")]


def download(url: str, dest: Path) -> None:
    """Laedt eine oeffentliche Drive-Datei, auch wenn Drive die Viruswarnung-Seite davorschaltet."""
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    r = op.open(urllib.request.Request(url, headers=UA), timeout=120)
    if "text/html" in r.headers.get("Content-Type", ""):
        html = r.read().decode("utf-8", "ignore")
        fields = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', html))
        if "id" not in fields:
            raise RuntimeError("Drive liefert eine Seite statt der Datei (Freigabe prueffen)")
        fields.setdefault("confirm", "t")
        r = op.open(urllib.request.Request("https://drive.usercontent.google.com/download?" +
                                           urllib.parse.urlencode(fields), headers=UA), timeout=300)
        if "text/html" in r.headers.get("Content-Type", ""):
            raise RuntimeError("Drive liefert auch nach der Bestaetigung eine Seite statt der Datei")
    with dest.open("wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return round(float(out), 1)


def extract_audio(video: Path, wav: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                   check=True)


def load_model():
    from faster_whisper import WhisperModel  # erst hier, damit --list ohne Installation geht
    return WhisperModel("small", device="cpu", compute_type="int8")


def transcribe(model, wav: Path) -> str:
    segs, _ = model.transcribe(str(wav), language="de", beam_size=1)
    return " ".join(s.text.strip() for s in segs).strip()


def main(argv: list) -> int:
    todo = targets()
    if "--id" in argv:
        todo = [v for v in todo if v["id"] == argv[argv.index("--id") + 1]]
    outdir = inventory._p("transcripts")
    todo = [v for v in todo if not (outdir / f"{v['id']}.json").exists()]
    if "--limit" in argv:
        todo = todo[: int(argv[argv.index("--limit") + 1])]
    log(f"{len(todo)} Videos zu transkribieren.")
    if "--list" in argv or not todo:
        for v in todo:
            print(v["id"], v["topic"])
        return 0
    outdir.mkdir(parents=True, exist_ok=True)
    model = load_model()
    inv = inventory._load("inventory.json", {"videos": []})
    byid = {v["id"]: v for v in inv["videos"]}
    done, failed = 0, []
    for v in todo:
        try:
            with tempfile.TemporaryDirectory() as td:
                mp4, wav = Path(td) / "v.mp4", Path(td) / "v.wav"
                download(v["video_url"], mp4)
                dur = probe_duration(mp4)
                extract_audio(mp4, wav)
                text = transcribe(model, wav)
            (outdir / f"{v['id']}.json").write_text(json.dumps(
                {"id": v["id"], "topic": v["topic"], "duration": dur, "text": text}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            byid[v["id"]]["duration"] = dur
            done += 1
            log(f"{v['id']} ok ({dur} s, {len(text.split())} Woerter)")
        except Exception as e:  # ein Fehler stoppt nicht die anderen
            failed.append(f"{v['id']}: {e}")
            log(f"{v['id']} FEHLER {e}")
        if done and done % 10 == 0:
            inventory._save("inventory.json", inv)
            log(inventory.sync(f"Transkripte (Zwischenstand {done})"))
    inventory._save("inventory.json", inv)
    log(inventory.sync(f"Transkripte {done} neu, {len(failed)} Fehler"))
    for f in failed:
        print("FEHLER", f)
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
