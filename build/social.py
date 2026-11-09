#!/usr/bin/env python3
"""Post one case a day to Bluesky and Mastodon. Off until the accounts exist.

Switched on by repository secrets (never in code): BSKY_HANDLE + BSKY_APP_PASSWORD for
Bluesky, MASTODON_URL (e.g. https://mastodon.social) + MASTODON_TOKEN for Mastodon. With
neither set it prints "social: off" and does nothing. Each run posts at most one item:
a new fix first, otherwise the most-read open case with a whole-sentence quote that has
not been posted yet. social.json remembers what went out, so nothing posts twice.

    python build/social.py            # post the next item (if switched on)
    python build/social.py --dry      # print what would be posted
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import site_extras as X  # noqa: E402

STATE = os.path.join(X.ROOT, "social.json")
UA = "ZombieFacts/1.1 (https://zombiefacts.org/; tips@zombiefacts.org)"


def candidates(M):
    """(id, text, url, card path or None), best first."""
    out = []
    for c in M["cases"]:
        card = X.card_path(c) if X.card_exists(c) else None
        for x in c["cites_on"]:
            if x["st"] == "fixed" and not x["ours"]:
                d = X.days(x["c"]["o"], x["c"]["c"])
                out.append(((0, -d), f"fix:{x['key']}",
                            f"Fixed: the Wikipedia article “{x['page']}” no longer cites a retracted paper without warning, "
                            f"{d} days after we found it.", c["url"], card))
        q = re.sub(r'"([^"]*)"', "‘\\1’", c["quote"])
        if c["st"] == "open" and X.whole(c["quote"]) and len(q) <= 200:
            out.append(((1, -c["reach"]), f"case:{c['doi']}",
                        f"“{q}”\n\nStill on Wikipedia (“{c['lead']['page']}”). The paper behind it was retracted in {(c['retracted'] or '')[:4]}.",
                        c["url"], card))
    out.sort(key=lambda o: o[0])
    return [o[1:] for o in out]


def req(url, data=None, headers=None, raw=None):
    h = {"User-Agent": UA, **(headers or {})}
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    if data is not None and raw is None:
        h.setdefault("Content-Type", "application/json")
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method="POST" if body is not None else "GET"), timeout=30) as r:
        return json.loads(r.read() or b"{}")


def bluesky(text, url, card):
    pds = "https://bsky.social/xrpc/"
    s = req(pds + "com.atproto.server.createSession", {"identifier": os.environ["BSKY_HANDLE"], "password": os.environ["BSKY_APP_PASSWORD"]})
    auth = {"Authorization": "Bearer " + s["accessJwt"]}
    ext = {"uri": url, "title": "Zombie Facts", "description": "Retracted research, still cited as fact."}
    if card:
        blob = req(pds + "com.atproto.repo.uploadBlob", headers={**auth, "Content-Type": "image/png"}, raw=open(card, "rb").read())
        ext["thumb"] = blob["blob"]
    rec = {"$type": "app.bsky.feed.post", "text": text, "langs": ["en"],
           "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "embed": {"$type": "app.bsky.embed.external", "external": ext}}
    req(pds + "com.atproto.repo.createRecord", {"repo": s["did"], "collection": "app.bsky.feed.post", "record": rec}, headers=auth)


def mastodon(text, url):
    base = os.environ["MASTODON_URL"].rstrip("/")
    req(base + "/api/v1/statuses", {"status": f"{text}\n\n{url}", "visibility": "public", "language": "en"},
        headers={"Authorization": "Bearer " + os.environ["MASTODON_TOKEN"]})


def main():
    on_b = bool(os.environ.get("BSKY_HANDLE") and os.environ.get("BSKY_APP_PASSWORD"))
    on_m = bool(os.environ.get("MASTODON_URL") and os.environ.get("MASTODON_TOKEN"))
    dry = "--dry" in sys.argv
    if not (on_b or on_m or dry):
        print("social: off (no account secrets)")
        return
    try:
        state = json.load(open(STATE))
    except (OSError, ValueError):
        state = {"posted": {}}
    nxt = next(((i, t, u, c) for i, t, u, c in candidates(X.model()) if i not in state["posted"]), None)
    if not nxt:
        print("social: nothing new")
        return
    i, text, url, card = nxt
    text = text if len(text) <= 280 else text[:277].rsplit(" ", 1)[0] + "…"
    if dry:
        print("social would post:", i, "\n" + text, "\n" + url)
        return
    done = []
    for name, ok, fn in [("bluesky", on_b, lambda: bluesky(text, url, card)), ("mastodon", on_m, lambda: mastodon(text, url))]:
        if not ok:
            continue
        try:
            fn()
            done.append(name)
        except Exception as e:  # a failed post never breaks the daily run
            print("social:", name, "failed", e)
    if done:
        state["posted"][i] = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "on": done}
        with open(STATE, "w") as f:
            json.dump(state, f, indent=1, sort_keys=True)
            f.write("\n")
    print("social: posted", i, "to", ", ".join(done) or "nothing")


if __name__ == "__main__":
    main()
