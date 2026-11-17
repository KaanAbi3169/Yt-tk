"""Buffer-Schnittstelle (GraphQL, persoenlicher API-Key) ohne Claude.

Der Key steht NUR in der Umgebungsvariable BUFFER_API_KEY (GitHub-Secret), nie in Dateien oder Logs.

ACHTUNG: Die GraphQL-Texte unten sind bis zur Pruefung mit `python -m yt_tk.uploader --introspect`
NICHT verifiziert (Buffer-API ist Beta, die Feldnamen wurden aus Dokumentationsauszuegen abgeleitet).
Gepostet wird erst, wenn UPLOADER_LIVE=true gesetzt ist.
"""
import json
import os
import time
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("BUFFER_API_URL", "https://api.buffer.com")


class BufferError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("BUFFER_API_KEY", "")
    if not k:
        raise BufferError("BUFFER_API_KEY fehlt (GitHub-Secret setzen)")
    return k


def gql(query: str, variables: dict | None = None, retries: int = 2) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(ENDPOINT, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {_key()}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.loads(r.read())
            if res.get("errors"):
                raise BufferError("GraphQL: " + "; ".join(e.get("message", "?") for e in res["errors"])[:500])
            return res["data"]
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            last = BufferError(f"Buffer HTTP {e.code}: {msg}")
            if e.code in (400, 401, 403, 404):
                raise last
        except (urllib.error.URLError, TimeoutError) as e:
            last = BufferError(f"Buffer Netzwerkfehler: {e}")
        time.sleep(5 * (attempt + 1))
    raise last


# --- UNVERIFIZIERT: nach Introspektion anpassen -------------------------------------------------
Q_POSTS = """
query Posts($org: OrganizationId!, $channels: [ChannelId!], $after: String) {
  posts(first: 100, after: $after, input: {organizationId: $org, filter: {channelIds: $channels, status: [scheduled, sending, sent, draft]}}) {
    edges { node { id status text dueAt assets { source } } }
    pageInfo { hasNextPage endCursor }
  }
}"""

M_CREATE = """
mutation Create($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt status } }
    ... on MutationError { message }
  }
}"""
# ------------------------------------------------------------------------------------------------


def list_posts(org: str, channel: str, max_pages: int = 5) -> list:
    out, after = [], None
    for _ in range(max_pages):
        d = gql(Q_POSTS, {"org": org, "channels": [channel], "after": after})["posts"]
        out += [e["node"] for e in d["edges"]]
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def create_post(channel: str, text: str, due_iso: str, video_url: str, metadata: dict) -> str:
    """Plant ein Video als automatischen Post. Gibt die Post-ID zurueck."""
    inp = {"channelId": channel, "text": text, "schedulingType": "automatic", "mode": "customScheduled",
           "dueAt": due_iso, "assets": {"videos": [{"url": video_url}]}, "metadata": metadata}
    d = gql(M_CREATE, {"input": inp}, retries=0)["createPost"]  # nie blind wiederholen: Doppelpost-Gefahr
    if "post" not in d or not d["post"]:
        raise BufferError("createPost: " + (d.get("message") or "keine Post-ID zurueckgegeben"))
    return d["post"]["id"]
