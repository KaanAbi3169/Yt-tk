"""Taegliches Einplanen OHNE Claude (laeuft als GitHub Action).

    python -m yt_tk.uploader                 # Trockenlauf: zeigt nur, was gepostet wuerde (Standard)
    UPLOADER_LIVE=true python -m yt_tk.uploader   # plant wirklich in Buffer
    python -m yt_tk.uploader --day 2026-11-18     # anderes Datum
    python -m yt_tk.uploader --introspect         # GraphQL-Schema von Buffer anzeigen (zum Pruefen)
    python -m yt_tk.uploader --selftest-draft --day 2026-11-18   # legt nur ENTWUERFE an (zum Testen von createPost)

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
    is_drive = "drive.google.com" in entry["video_url"]
    # Drive-Links enden auf "uc?...": der Dateiname waere dann "uc" und wuerde jeden Drive-Post treffen
    vid_file = None if is_drive else entry["video_url"].rsplit("/", 1)[-1].split("?")[0]
    drive_id = entry["video_url"].split("id=")[-1].split("&")[0] if is_drive else None
    head = (entry[platform]["text"] or "")[:60]
    for p in posts:
        srcs = " ".join((a.get("source") or "") for a in (p.get("assets") or []))
        if (vid_file and vid_file in srcs) or (drive_id and drive_id in srcs) or (head and (p.get("text") or "").startswith(head)):
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


def _t(t: dict) -> str:
    if not t:
        return "?"
    if t["kind"] == "NON_NULL":
        return _t(t["ofType"]) + "!"
    if t["kind"] == "LIST":
        return "[" + _t(t["ofType"]) + "]"
    return t["name"]


TREF = "kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } }"
DEFAULT_TYPES = ["Query", "Mutation", "PostsFiltersInput", "PostSortInput", "PostsResults", "PostsEdge", "Post", "Asset",
                 "VideoAsset", "AssetInput", "VideoAssetInput", "PostInputMetaData", "YoutubePostMetadataInput",
                 "TikTokPostMetadataInput", "ShareMode", "SchedulingType", "PostStatus", "PostActionPayload",
                 "PostActionSuccess", "MutationError", "PaginationPageInfo", "PostSortableKey"]


def describe(name: str) -> None:
    q = ("query($n:String!){ __type(name:$n){ name kind "
         f"fields {{ name args {{ name type {{ {TREF} }} }} type {{ {TREF} }} }} "
         f"inputFields {{ name type {{ {TREF} }} }} enumValues {{ name }} possibleTypes {{ name }} }} }}")
    r = buffer_api.gql_public(q, {"n": name})["__type"]
    if not r:
        print(f"## {name}: nicht vorhanden")
        return
    out = []
    for f in r.get("fields") or []:
        if name == "Mutation" and "ost" not in f["name"]:
            continue
        args = ", ".join(f"{a['name']}: {_t(a['type'])}" for a in f["args"])
        out.append(f"{f['name']}({args}): {_t(f['type'])}" if args else f"{f['name']}: {_t(f['type'])}")
    out += [f"{f['name']}: {_t(f['type'])}" for f in r.get("inputFields") or []]
    if r.get("enumValues"):
        out.append("ENUM " + ", ".join(v["name"] for v in r["enumValues"]))
    if r.get("possibleTypes"):
        out.append("UNION " + ", ".join(v["name"] for v in r["possibleTypes"]))
    print(f"## {name} ({r['kind']}): " + " | ".join(out), flush=True)


def introspect(argv: list) -> int:
    names = DEFAULT_TYPES
    if "--types" in argv:
        names = argv[argv.index("--types") + 1].split(",")
    for n in names:
        describe(n)
    return 0


def selftest_draft(day: str) -> int:
    """Legt je Plattform einen ENTWURF an (nie veroeffentlicht), um createPost mit echtem Key zu pruefen."""
    plan = [e for e in inventory.plan(day) if not e.get("needs_texts")]
    if not plan:
        log("Kein Eintrag fuer den Selbsttest.")
        return 1
    e, rc = plan[0], 0
    for pf in e["platforms"]:
        pl = e[pf]
        try:
            pid = buffer_api.create_post(pl["channelId"], pl["text"], e["dueAt"], e["video_url"], pl["metadata"], draft=True)
            log(f"SELFTEST-ENTWURF {e['id']} {pf}: Post {pid} (bitte loeschen)")
        except Exception as ex:
            rc = 1
            log(f"SELFTEST-FEHLER {e['id']} {pf}: {ex}")
    return rc


def main(argv: list) -> int:
    if "--introspect" in argv:
        return introspect(argv)
    day = argv[argv.index("--day") + 1] if "--day" in argv else datetime.now(inventory.TZ).date().isoformat()
    live = os.environ.get("UPLOADER_LIVE", "").lower() in ("1", "true", "yes")
    if "--selftest-draft" in argv:
        return selftest_draft(day)
    log(f"Uploader {day} · {'LIVE' if live else 'TROCKENLAUF'}")
    return run(day, live)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
