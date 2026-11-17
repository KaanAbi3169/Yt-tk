"""Taegliches Einplanen OHNE Claude (laeuft als GitHub Action).

    python -m yt_tk.uploader                 # Trockenlauf: zeigt nur, was gepostet wuerde (Standard)
    UPLOADER_LIVE=true python -m yt_tk.uploader   # plant wirklich in Buffer
    python -m yt_tk.uploader --day 2026-11-18     # anderes Datum
    python -m yt_tk.uploader --introspect         # GraphQL-Schema von Buffer anzeigen (zum Pruefen)

Logik wie docs/ROUTINE_PLANUNG.md: Plan aus dem Inventar, Doppelschutz ueber die ganze Kanal-Historie,
Buffer-Limit (max. 10 geplante Posts), Wiederholung nie blind, Status zurueck ins Inventar (media-Branch).
Exit-Code: 0 ok, 1 Fehler bei mindestens einem Post (GitHub meldet den fehlgeschlagenen Lauf aufs Handy).
"""
import json
import os
import sys
from datetime import datetime

from . import buffer_api, config, inventory

ORG = config.BUFFER["organization_id"]
CHANNELS = {"tiktok": config.BUFFER["tiktok_channel_id"], "youtube": config.BUFFER["youtube_channel_id"]}
BUFFER_LIMIT = 10


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def find_existing(posts: list, entry: dict, platform: str):
    """Doppelschutz: gleiche Video-Datei oder gleicher Text-Anfang irgendwo in der Kanal-Historie."""
    vid_file = entry["video_url"].rsplit("/", 1)[-1].split("?")[0]
    drive_id = entry["video_url"].split("id=")[-1] if "drive.google.com" in entry["video_url"] else None
    head = (entry[platform]["text"] or "")[:60]
    for p in posts:
        srcs = " ".join((a.get("source") or "") for a in (p.get("assets") or []))
        if vid_file in srcs or (drive_id and drive_id in srcs) or (head and (p.get("text") or "").startswith(head)):
            return p
    return None


def run(day: str, live: bool) -> int:
    if config.paused():
        log("PAUSE/STOP vorhanden - nichts zu tun.")
        return 0
    plan = inventory.plan(day)
    if not plan:
        log("Plan leer (nichts faellig oder kein Vorrat).")
        return 0
    errors = 0
    history = {pf: buffer_api.list_posts(ORG, ch) for pf, ch in CHANNELS.items()}
    scheduled = sum(1 for pf in history for p in history[pf] if p.get("status") in ("scheduled", "sending"))
    for e in plan:
        if e.get("needs_texts"):
            log(f"{e['id']}: Titel/Texte fehlen - uebersprungen (Notvorrat auffuellen).")
            continue
        ids = {}
        for pf in e["platforms"]:
            hit = find_existing(history[pf], e, pf)
            if hit:
                log(f"{e['id']} {pf}: schon vorhanden (Post {hit['id']}, {hit.get('status')}) - kein neuer Post.")
                ids[pf] = hit["id"]
                continue
            if scheduled >= BUFFER_LIMIT:
                log(f"{e['id']} {pf}: Buffer-Limit {BUFFER_LIMIT} erreicht - spaeter.")
                continue
            payload = e[pf]
            if not live:
                log(f"TROCKENLAUF {e['id']} {pf} {e['dueAt']}: {payload['metadata'].get(pf, {}).get('title')}")
                continue
            try:
                ids[pf] = buffer_api.create_post(payload["channelId"], payload["text"], e["dueAt"], e["video_url"],
                                                 payload["metadata"])
                scheduled += 1
                log(f"{e['id']} {pf}: geplant {e['dueAt']} (Post {ids[pf]})")
            except Exception as ex:  # nie blind wiederholen
                errors += 1
                log(f"FEHLER {e['id']} {pf}: {ex}")
                inventory.fail(e["id"], f"{pf}: {ex}"[:300])
        if live and ids and set(ids) == set(e["platforms"]):
            inventory.mark(e["id"], ids.get("tiktok", ""), ids.get("youtube", ""), e["dueAt"])
    if live:
        log(inventory.sync(f"Uploader {day}"))
    return 1 if errors else 0


def introspect() -> int:
    q = "{ __schema { queryType { name } mutationType { name } types { name kind } } }"
    d = buffer_api.gql(q)["__schema"]
    print("Query:", d["queryType"]["name"], "| Mutation:", (d["mutationType"] or {}).get("name"))
    print(", ".join(sorted(t["name"] for t in d["types"] if not t["name"].startswith("__"))))
    for tname in ("CreatePostInput", "PostsInput", "PostFilter", "PostsFilter"):
        r = buffer_api.gql('query($n:String!){ __type(name:$n){ name inputFields { name type { kind name ofType { kind name ofType { name } } } } } }',
                           {"n": tname})["__type"]
        if r:
            print(tname, json.dumps([(f["name"], f["type"]) for f in r["inputFields"]], ensure_ascii=False)[:1500])
    return 0


def main(argv: list) -> int:
    if "--introspect" in argv:
        return introspect()
    day = argv[argv.index("--day") + 1] if "--day" in argv else datetime.now(inventory.TZ).date().isoformat()
    live = os.environ.get("UPLOADER_LIVE", "").lower() in ("1", "true", "yes")
    log(f"Uploader {day} · {'LIVE' if live else 'TROCKENLAUF'}")
    return run(day, live)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
