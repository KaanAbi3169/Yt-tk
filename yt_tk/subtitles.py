"""Wort-fuer-Wort animierte Untertitel (ASS) aus den ElevenLabs-Zeitstempeln."""
from . import config

MAX_WORDS = 3
MAX_CHARS = 18
GAP_BREAK = 0.35


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(w: str) -> str:
    return w.replace("\\", "").replace("{", "(").replace("}", ")")


def chunk(words: list, max_chars: int = MAX_CHARS, max_words: int = MAX_WORDS) -> list:
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        text_len = sum(len(x["word"]) + 1 for x in cur)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_punct = w["word"][-1] in ".,!?:;…–"
        gap = (nxt["start"] - w["end"]) if nxt else 0
        if len(cur) >= max_words or text_len >= max_chars or end_punct or gap > GAP_BREAK or nxt is None:
            chunks.append(cur)
            cur = []
    return chunks


def build_ass(words: list, fmt: str, total: float, path) -> None:
    f = config.FORMATS[fmt]
    W, H = config.dims(fmt)
    landscape = W > H
    size = 60 if landscape else {"wissen": 74, "horror": 82}.get(fmt, 80)
    margin_v = 70 if landscape else 600
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{f['font']},{size},{f['sub_primary']},{f['sub_highlight']},{f['sub_outline']},&H96000000,-1,0,0,0,100,100,0,0,1,7,3,2,70,70,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    chunks = chunk(words, 34, 6) if landscape else chunk(words, 15 if fmt == "wissen" else MAX_CHARS)
    for ci, c in enumerate(chunks):
        chunk_end = c[-1]["end"] + 0.12
        if ci + 1 < len(chunks):
            chunk_end = min(max(chunk_end, c[-1]["end"]), chunks[ci + 1][0]["start"])
        chunk_end = min(chunk_end, total)
        for wi, w in enumerate(c):
            start = w["start"]
            end = c[wi + 1]["start"] if wi + 1 < len(c) else chunk_end
            if end - start < 0.04:
                continue
            parts = []
            for j, x in enumerate(c):
                word = _esc(x["word"]).upper() if fmt == "wissen" else _esc(x["word"])
                if j == wi:
                    parts.append(r"{\c" + f["sub_highlight"] + r"&\fscx112\fscy112}" + word + r"{\c" + f["sub_primary"] + r"&\fscx100\fscy100}")
                else:
                    parts.append(word)
            pop = r"{\fad(40,0)}" if wi == 0 else ""
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Sub,,0,0,0,,{pop}{' '.join(parts)}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + "\n".join(lines) + "\n")
