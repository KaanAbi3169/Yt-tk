"""V-032: Hook-Einblendung fuer die Vorrats-Shorts (Code, ffmpeg, ohne Claude, 0 EUR).

    python3 -m yt_tk.hook --test D016,D017,D082     # Standbilder (mit und ohne Einblendung) nach <Daten>/tests/hook/

Die Hook-Frage kommt aus dem vorhandenen TikTok-Titel: erster Satz bis zum Fragezeichen, ohne Emoji, in hoechstens
zwei Zeilen. Sie wird in den ersten 2,5 Sekunden im oberen Drittel eingeblendet. Das Original bleibt unveraendert.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from . import compile_long, config, inventory, transcribe

SHOW_S = 2.5
EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿️‍]")


def hook_text(title: str) -> str:
    t = EMOJI.sub("", title).strip()
    first = re.split(r"(?<=[?!])\s", t, maxsplit=1)[0].strip()
    return first if 2 <= len(first.split()) <= 9 else " ".join(first.split()[:7])


def wrap(text: str, width: int = 17) -> list:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return lines[:3]


def render(src: Path, dst: Path, text: str, tmp: Path) -> None:
    filters = []
    lines = wrap(text)
    for k, line in enumerate(lines):
        f = tmp / f"hook{k}.txt"
        f.write_text(line, encoding="utf-8")
        filters.append(f"drawtext=fontfile={compile_long.font()}:textfile={f}:x=(w-text_w)/2:y=h*0.20+{k}*h*0.058:"
                       f"fontsize=h/24:fontcolor=white:box=1:boxcolor=black@0.62:boxborderw=14:enable='lt(t,{SHOW_S})'")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", ",".join(filters), "-c:v", "libx264", "-crf", "20",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)], check=True)


def frame(video: Path, out: Path, t: float = 1.2) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1", str(out)], check=True)


def main(argv: list) -> int:
    if "--test" not in argv:
        print(__doc__)
        return 2
    ids = argv[argv.index("--test") + 1].split(",")
    inv = {v["id"]: v for v in inventory._load("inventory.json", {"videos": []})["videos"]}
    out = config.DATA / "tests" / "hook"
    for i in ids:
        v = inv[i]
        text = hook_text(v["title_tiktok"])
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "src.mp4"
            transcribe.download(v["video_url"], src)
            dst = tmp / "hook.mp4"
            render(src, dst, text, tmp)
            frame(src, out / f"{i}-original.jpg")
            frame(dst, out / f"{i}-hook.jpg")
        print(f"{i}: Hook = {text!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
