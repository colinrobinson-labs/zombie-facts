#!/usr/bin/env python3
"""Post approved correction notes to Wikipedia talk pages.

Only notes in outreach.json with status "approved" are posted, at most
ZF_POST_LIMIT per run (default 3), and only when the account's credentials are
present as environment variables (GitHub secrets):

  WIKI_USER  bot-password login of Colin's personal account, e.g. "ColinRobinson@poster"
  WIKI_PASS  bot password

Without them the script does nothing. Policy: never scheduled. Colin starts each
run by hand (workflow_dispatch) for notes he has read and approved, posted from his
own account, with a plain edit summary and no site credit.
Each note is re-checked against the live article first, so a citation fixed in
the meantime is never reported.
"""
import http.cookiejar, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from build_data import UA, WP, log  # noqa: E402
from recheck import OUTREACH, load, save  # noqa: E402

LIMIT = int(os.environ.get("ZF_POST_LIMIT", "3"))
USER, PASS = os.environ.get("WIKI_USER"), os.environ.get("WIKI_PASS")
DRY = os.environ.get("ZF_DRY_RUN") == "1"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def api(params, post=False):
    params = dict(params, format="json", formatversion="2", maxlag="5")
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(WP if post else WP + "?" + data.decode(), data=data if post else None,
                                 headers={"User-Agent": UA})
    with opener.open(req, timeout=60) as r:
        return json.load(r)


def login():
    tok = api({"action": "query", "meta": "tokens", "type": "login"})["query"]["tokens"]["logintoken"]
    r = api({"action": "login", "lgname": USER, "lgpassword": PASS, "lgtoken": tok}, post=True)
    if r.get("login", {}).get("result") != "Success":
        sys.exit("Wikipedia login failed: " + json.dumps(r.get("login", {}))[:200])
    return api({"action": "query", "meta": "tokens"})["query"]["tokens"]["csrftoken"]


def talk_has_section(page, title):
    r = api({"action": "parse", "page": "Talk:" + page, "prop": "sections"})
    if "error" in r:
        return False  # talk page doesn't exist yet
    return any(x.get("line", "").strip().lower() == title.strip().lower() for x in r.get("parse", {}).get("sections", []))


def still_cited(page, doi):
    r = api({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": page})
    pg = (r.get("query", {}).get("pages") or [{}])[0]
    txt = ((pg.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content") or "").lower()
    return doi in txt


def main():
    out = load(OUTREACH, {"version": 1, "notes": []})
    queue = [n for n in out["notes"] if n.get("status") == "approved"][:LIMIT]
    if not queue:
        log("nothing approved to post"); return
    if not (USER and PASS) and not DRY:
        log("WIKI_USER / WIKI_PASS not set; not posting", len(queue), "approved notes"); return
    csrf = None if DRY else login()
    account = (USER or "dry-run").split("@")[0]
    for n in queue:
        if not still_cited(n["page"], n["doi"]):
            n["status"] = "skipped"; n["why_skipped"] = "citation already gone before posting"
            log("skip, already fixed:", n["page"]); continue
        if talk_has_section(n["page"], n["section"]):
            n["status"] = "posted"; n.setdefault("by", "unknown"); n.setdefault("posted", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"))
            save(OUTREACH, out, pretty=True); log("already on talk page, marking posted:", n["page"]); continue
        if DRY:
            log("DRY RUN would post to Talk:" + n["page"], "|", n["section"]); continue
        r = api({"action": "edit", "title": "Talk:" + n["page"], "section": "new", "sectiontitle": n["section"],
                 "text": n["text"], "summary": "Cited source was retracted; see note",
                 "token": csrf}, post=True)
        e = r.get("edit", {})
        if e.get("result") != "Success":
            log("post failed", n["page"], json.dumps(r)[:300]); n["status"] = "error"; n["error"] = json.dumps(r)[:300]
            continue
        n.update(status="posted", by=account, posted=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                 diff=f"https://en.wikipedia.org/w/index.php?diff={e.get('newrevid')}")
        save(OUTREACH, out, pretty=True)  # persist after every post so a later failure can't cause a repost
        log("posted", n["page"], e.get("newrevid"))
        time.sleep(12)  # stay well under any editing rate limit
    save(OUTREACH, out, pretty=True)


if __name__ == "__main__":
    main()
