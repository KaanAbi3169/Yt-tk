"""Schnitt mit ffmpeg: Kamerafahrten, Uebergaenge, Serien-Overlays, Untertitel, Musik."""
import subprocess
from pathlib import Path

from . import config

MOTIONS = ("zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "shake")


def _run(cmd: list) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg-Fehler:\n" + r.stderr[-3000:])


def _zoompan(motion: str, frames: int) -> str:
    D = max(frames - 1, 1)
    e = f"(3*pow(on/{D},2)-2*pow(on/{D},3))"  # weiches Ein-/Ausblenden der Bewegung
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z0 = 1.12
    if motion == "zoom_in":
        z, x, y = f"1+0.14*{e}", cx, cy
    elif motion == "zoom_out":
        z, x, y = f"1.14-0.14*{e}", cx, cy
    elif motion == "pan_left":
        z, x, y = str(z0), f"(iw-iw/zoom)*(1-{e})", cy
    elif motion == "pan_right":
        z, x, y = str(z0), f"(iw-iw/zoom)*{e}", cy
    elif motion == "pan_up":
        z, x, y = str(z0), cx, f"(ih-ih/zoom)*(1-{e})"
    elif motion == "pan_down":
        z, x, y = str(z0), cx, f"(ih-ih/zoom)*{e}"
    elif motion == "shake":
        z = f"1.08+0.04*{e}"
        x = f"iw/2-(iw/zoom/2)+10*sin(on*1.9)+6*sin(on*3.7)"
        y = f"ih/2-(ih/zoom/2)+8*cos(on*2.3)"
    else:
        raise ValueError(f"Unbekannte Bewegung {motion}")
    return (f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:"
            f"s={config.VIDEO_W}x{config.VIDEO_H}:fps={config.FPS}")


def scene_clip(png: Path, motion: str, seconds: float, out: Path) -> None:
    frames = max(int(round(seconds * config.FPS)), 2)
    vf = _zoompan(motion, frames) + ",format=yuv420p"
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(png), "-vf", vf, "-frames:v", str(frames),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-r", str(config.FPS), str(out)])


def _effects(kind: str) -> str:
    if kind == "horror":
        return ("eq=contrast=1.08:saturation=0.8:brightness='-0.02-0.05*between(mod(t,6.7),0,0.07)"
                "-0.04*between(mod(t,11.3),0,0.05)':eval=frame,"
                "noise=alls=9:allf=t+u,vignette=angle=PI/3.6")
    if kind == "dream":
        return "vignette=angle=PI/5,eq=saturation=1.05"
    return "vignette=angle=PI/7"


def assemble(script: dict, assets: dict, timing: dict, voice: Path, ass: Path, out: Path, workdir: Path) -> None:
    fmt = script["format"]
    f = config.FORMATS[fmt]
    starts, total = timing["scene_starts"], timing["total"]
    n = len(starts)
    T = config.XFADE
    clips = []
    for i in range(n):
        end = starts[i + 1] if i + 1 < n else total
        dur = end - starts[i] + (T if i + 1 < n else 0)
        clip = workdir / f"clip_{i:02d}.mp4"
        scene_clip(assets["scenes"][i], script["scenes"][i].get("motion", "zoom_in"), dur, clip)
        clips.append(clip)

    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]
    vi = len(clips)
    inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(assets["badge"])]
    inputs += ["-loop", "1", "-t", "2.6", "-i", str(assets["hook"])]
    inputs += ["-i", str(voice)]
    inputs += ["-stream_loop", "-1", "-i", str(config.ROOT / "assets" / "music" / f"{fmt}.mp3")]

    fc = []
    prev = "[0:v]"
    for k in range(1, n):
        lab = f"[x{k}]"
        fc.append(f"{prev}[{k}:v]xfade=transition={f['transition']}:duration={T}:offset={starts[k]:.3f}{lab}")
        prev = lab
    fc.append(f"{prev}{_effects(f['effects'])},format=yuva420p[base]")
    fc.append(f"[{vi}:v]format=rgba,fade=t=in:st=0:d=0.4:alpha=1[badge]")
    fc.append(f"[{vi + 1}:v]format=rgba,fade=t=out:st=2.1:d=0.45:alpha=1[hook]")
    ass_path = str(ass).replace("\\", "/").replace(":", "\\:")
    fc.append(f"[base][badge]overlay=0:0:format=auto[b1];[b1][hook]overlay=0:0:format=auto:eof_action=pass[b2];"
              f"[b2]ass='{ass_path}',format=yuv420p[vout]")
    a_voice, a_music = vi + 2, vi + 3
    fc.append(f"[{a_voice}:a]aresample=48000,apad,atrim=0:{total:.3f},asplit=2[v1][vkey]")
    fc.append(f"[{a_music}:a]aresample=48000,atrim=0:{total:.3f},volume={f['music_volume']},"
              f"afade=t=in:st=0:d=1,afade=t=out:st={max(total - 1.2, 0):.3f}:d=1.2[m]")
    fc.append("[m][vkey]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[mduck]")
    fc.append(f"[v1][mduck]amix=inputs=2:duration=first:normalize=0,"
              f"loudnorm=I={config.TARGET_LUFS}:TP=-1.5:LRA=11,aresample=48000[aout]")

    _run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
          "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
          "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
          "-r", str(config.FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
          "-movflags", "+faststart", str(out)])
