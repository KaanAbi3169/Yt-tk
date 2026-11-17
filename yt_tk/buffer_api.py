"""Buffer-Schnittstelle (GraphQL, persoenlicher API-Key) ohne Claude.

Der Key steht NUR in der Umgebungsvariable BUFFER_API_KEY (GitHub-Secret), nie in Dateien oder Logs.

Schema: per Introspektion geprueft (17.11.2026, `python -m yt_tk.uploader --introspect`). Noch NICHT geprueft:
die erste echte, angemeldete Abfrage (braucht einen gueltigen Key). Gepostet wird erst, wenn UPLOADER_LIVE=true gesetzt ist.
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
    """Key aus dem Secret. Entfernt beim Einfuegen mitkopierte Sonderzeichen (typografische Anfuehrungszeichen,
    unsichtbare Zeichen, Leerzeichen, Zeilenumbrueche). Gibt nie den Wert aus, nur ob etwas entfernt wurde."""
    raw = os.environ.get("BUFFER_API_KEY", "")
    k = "".join(ch for ch in raw if "!" <= ch <= "~").strip("\"'")
    if not k:
        raise BufferError("BUFFER_API_KEY fehlt oder ist leer (GitHub-Secret neu anlegen)")
    removed = len(raw) - len(k)
    if removed > 6 or len(k) < 20:
        # Ein echter Key ist ASCII und lang. Viele Sonderzeichen = falscher Inhalt im Secret.
        raise BufferError(f"BUFFER_API_KEY ist kein gueltiger Key (Laenge {len(raw)}, davon {removed} Sonderzeichen, "
                          f"{len(k)} brauchbar). Secret loeschen und den Key neu einfuegen.")
    if removed:
        print(f"Hinweis: {removed} Sonderzeichen im Secret wurden ignoriert.", flush=True)
    return k


def gql_public(query: str, variables: dict | None = None) -> dict:
    """Wie gql, aber ohne gueltigen Key (Schema-Abfrage ist bei Buffer ohne Anmeldung moeglich)."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.loads(r.read())
    if res.get("errors"):
        raise BufferError("GraphQL: " + "; ".join(e.get("message", "?") for e in res["errors"])[:500])
    return res["data"]


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


# Schema geprueft am 17.11.2026 per Introspektion (Actions-Lauf 3): posts(first, after, input: PostsInput!),
# createPost(input: CreatePostInput!) mit Pflichtfeldern channelId, mode, schedulingType, needsApproval, assets.
Q_POSTS = """
query Posts($input: PostsInput!, $after: String) {
  posts(first: 100, after: $after, input: $input) {
    edges { node { id status text dueAt assets { source } } }
    pageInfo { hasNextPage endCursor }
  }
}"""

M_CREATE = """
mutation Create($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id dueAt status } }
    ... on MutationError { message }
  }
}"""
HISTORY_STATUS = ["scheduled", "sending", "sent", "draft"]
# ------------------------------------------------------------------------------------------------


def list_posts(org: str, channel: str, max_pages: int = 5) -> list:
    out, after = [], None
    for _ in range(max_pages):
        inp = {"organizationId": org, "filter": {"channelIds": [channel], "status": HISTORY_STATUS}}
        d = gql(Q_POSTS, {"input": inp, "after": after})["posts"]
        out += [e["node"] for e in (d["edges"] or [])]
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def create_post_input(channel: str, text: str, due_iso: str, video_url: str, metadata: dict) -> dict:
    return {"channelId": channel, "text": text, "schedulingType": "automatic", "mode": "customScheduled",
            "dueAt": due_iso, "needsApproval": False, "assets": [{"video": {"url": video_url}}],
            "metadata": metadata}


def create_post(channel: str, text: str, due_iso: str, video_url: str, metadata: dict) -> str:
    """Plant ein Video als automatischen Post. Gibt die Post-ID zurueck."""
    inp = create_post_input(channel, text, due_iso, video_url, metadata)
    d = gql(M_CREATE, {"input": inp}, retries=0)["createPost"]  # nie blind wiederholen: Doppelpost-Gefahr
    if d.get("__typename") != "PostActionSuccess" or not d.get("post"):
        raise BufferError(f"createPost {d.get('__typename')}: {d.get('message') or 'keine Post-ID zurueckgegeben'}")
    return d["post"]["id"]
