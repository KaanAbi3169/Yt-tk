"""Sprachausgabe ueber ElevenLabs mit Zeichen-Zeitstempeln + Budget-Waechter.

Der API-Schluessel wird vom Netzwerk-Proxy der Claude-Umgebung eingesetzt
(Header xi-api-key). Lokal kann ELEVENLABS_API_KEY gesetzt werden.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import config

API = "https://api.elevenlabs.io/v1"


def _key() -> str:
    return os.environ.get("ELEVENLABS_API_KEY", "proxy-injected")


def _request(method: str, path: str, body=None, timeout=180, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("xi-api-key", _key())
    if data is not None:
        req.add_header("Content-Type", "application/json")
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = r.read()
                return payload if raw else json.loads(payload)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            last = RuntimeError(f"ElevenLabs {e.code}: {msg}")
            if e.code in (400, 401, 402, 403, 404, 422):
                raise last  # nicht wiederholbar
        except (urllib.error.URLError, TimeoutError) as e:
            last = RuntimeError(f"ElevenLabs Netzwerkfehler: {e}")
        time.sleep(2 ** attempt * 3)
    raise last


def subscription() -> dict:
    return _request("GET", "/user/subscription")


def budget_status() -> dict:
    s = subscription()
    used, limit = s["character_count"], s["character_limit"]
    reset = datetime.fromtimestamp(s["next_character_count_reset_unix"], tz=timezone.utc)
    days_left = max(1, (reset - datetime.now(timezone.utc)).days + 1)
    remaining = limit - used
    return {
        "used": used, "limit": limit, "remaining": remaining,
        "reset": reset.isoformat(), "days_to_reset": days_left,
        "per_day_available": remaining // days_left,
    }


def check_budget(chars_needed: int) -> None:
    b = budget_status()
    reserve = config.ELEVEN_DAILY_RESERVE * (b["days_to_reset"] - 1)
    if b["remaining"] - chars_needed < reserve * 0.5:
        raise RuntimeError(
            f"ElevenLabs-Budget knapp: {b['remaining']} Credits uebrig, {b['days_to_reset']} Tage bis Reset. "
            f"Benoetigt {chars_needed}. Skripte kuerzen oder Produktion drosseln.")


def synthesize(text: str, fmt: str, out_mp3) -> dict:
    """Erzeugt MP3 und gibt Wort-Timings zurueck: [{word,start,end,char_start,char_end}]."""
    f = config.FORMATS[fmt]
    check_budget(len(text))
    body = {
        "text": text,
        "model_id": config.ELEVEN_MODEL,
        "language_code": "de",
        "voice_settings": f["voice_settings"],
    }
    res = _request("POST", f"/text-to-speech/{f['voice_id']}/with-timestamps?output_format=mp3_44100_128", body)
    with open(out_mp3, "wb") as fh:
        fh.write(base64.b64decode(res["audio_base64"]))
    # "alignment" bezieht sich auf den Originaltext -> Szenengrenzen per Zeichenindex
    al = res.get("alignment") or res["normalized_alignment"]
    return {"words": words_from_alignment(al), "chars": al}


def words_from_alignment(al: dict) -> list:
    chars = al["characters"]
    st = al["character_start_times_seconds"]
    en = al["character_end_times_seconds"]
    words, cur, cs = [], "", None
    for i, ch in enumerate(chars):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": st[cs], "end": en[i - 1], "char_start": cs, "char_end": i - 1})
                cur, cs = "", None
            continue
        if cs is None:
            cs = i
        cur += ch
    if cur:
        words.append({"word": cur, "start": st[cs], "end": en[len(chars) - 1], "char_start": cs, "char_end": len(chars) - 1})
    return words


def generate_music(prompt: str, seconds: int, out_mp3) -> None:
    """Einmal pro Serie: instrumentaler Track (wird danach wiederverwendet)."""
    body = {"prompt": prompt, "music_length_ms": seconds * 1000, "force_instrumental": True}
    audio = _request("POST", "/music?output_format=mp3_44100_128", body, timeout=600, raw=True)
    with open(out_mp3, "wb") as fh:
        fh.write(audio)
