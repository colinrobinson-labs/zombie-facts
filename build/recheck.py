#!/usr/bin/env python3
"""Zombie Facts daily watcher.

Runs between the weekly full builds. It does three cheap things:

1. Re-reads every article with an open case and closes the case when the
   retracted DOI is gone ("removed") or now carries a warning ("flagged").
2. Reads the talk page of every article where a note was posted and records
   replies from editors (who, when, a short excerpt).
3. Updates data.json and outreach.json so the site shows it the same day.

Stdlib only. Never writes anything to Wikipedia.
"""
import json, os, re, sys, urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from build_data import OUT, log, read_pages, context_for, is_author_page, clean_said, superseded  # noqa: E402

OUTREACH = os.path.join(os.path.dirname(__file__), "..", "outreach.json")
CONTEXT_DUMP = os.environ.get("ZF_DUMP_CONTEXT")  # optional path: write raw wikitext around each open citation

SIG = re.compile(
    r"\[\[\s*(?:(?:User|User talk)\s*:|Special:Contributions\s*/)\s*([^|\]/#]+)[^\]]*\]\]"  # user or IP link
    r"(?:(?!\[\[\s*(?:User|User talk)\s*:).){0,240}?"                               # rest of signature
    r"(\d{1,2}:\d{2}, \d{1,2} [A-Z][a-z]+ \d{4} \(UTC\))", re.S)


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, obj, pretty=False):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


# ---------------------------------------------------------------- talk pages
def find_section(text, title):
    """Return the body of the level-2 section whose heading equals title, or None."""
    want = re.sub(r"\s+", " ", title).strip().lower()
    heads = list(re.finditer(r"^(==+)\s*(.+?)\s*\1\s*$", text, flags=re.M))
    for n, m in enumerate(heads):
        if re.sub(r"\s+", " ", m.group(2)).strip().lower() == want:
            end = len(text)
            for m2 in heads[n + 1:]:
                if len(m2.group(1)) <= len(m.group(1)):
                    end = m2.start()
                    break
            return text[m.end():end]
    return None


def strip_wiki(s):
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"^[:*#]+", "", s, flags=re.M)
    s = re.sub(r"'''?", "", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_replies(body, ours):
    """Signed comments in a talk section, excluding our own account."""
    out, prev = [], 0
    ours_l = {o.strip().lower().replace("_", " ") for o in ours if o}
    first = SIG.search(body)  # our note opens the section, so its signer is us
    if first:
        ours_l.add(first.group(1).strip().replace("_", " ").lower())
    for m in SIG.finditer(body):
        user = m.group(1).strip().replace("_", " ")
        chunk = body[prev:m.start()]
        prev = m.end()
        if user.lower() in ours_l:
            continue
        try:
            ts = datetime.strptime(m.group(2), "%H:%M, %d %B %Y (UTC)").strftime("%Y-%m-%dT%H:%MZ")
        except ValueError:
            ts = ""
        text = strip_wiki(chunk)
        out.append({"user": user, "at": ts, "said": text[-280:]})
    return out


# ---------------------------------------------------------------- main
def recheck_cases(data, pages, now):
    ledger = data.get("ledger") or {}
    cases = ledger.get("cases") or {}
    by_doi = {p["doi"]: p for p in data["papers"]}
    closed, dumped = [], {}
    for k, c in cases.items():
        if c.get("c"):
            continue
        doi, page = k.split("|", 1)
        pg = pages.get(page)
        if not pg or not pg.get("text"):
            continue  # not read: leave open
        txt = pg["text"]
        low = txt.lower()
        i = low.find(doi)
        if i < 0:
            i = low.find(urllib.parse.quote(doi, safe="/").lower())
        p = by_doi.get(doi)
        if i < 0:
            how = "removed"
        else:
            flagged_all, j = True, i
            while j >= 0:
                s, sec, fl = context_for(txt, low, j)
                if CONTEXT_DUMP and k not in dumped:
                    dumped[k] = {"page": page, "section": sec, "wikitext": txt[max(0, j - 1500): j + 300]}
                if not fl:
                    flagged_all = False
                j = low.find(doi, j + len(doi))
            how = "flagged" if flagged_all else None
            if not how and p and is_author_page(page, p.get("authors") or []):
                how = "author"
        c["v"] = pg.get("views", c.get("v"))
        if how:
            c.update(c=now, how=how)
            closed.append((k, how))
            if p:
                for w in p["wiki"]:
                    if w["page"] == page:
                        w["status"] = "flagged" if how == "flagged" else ("author" if how == "author" else "removed")
                p["wiki"] = [w for w in p["wiki"] if w["status"] != "removed"]
                p["zombies"] = sum(w["status"] == "zombie" for w in p["wiki"])
                p["reach"] = sum(w["views"] for w in p["wiki"] if w["status"] == "zombie")
    if CONTEXT_DUMP:
        save(CONTEXT_DUMP, dumped, pretty=True)
    return closed


def watch_outreach(outreach, pages, now_ts):
    events = 0
    for n in outreach.get("notes", []):
        if n.get("status") not in ("posted", "replied"):
            continue
        pg = pages.get("Talk:" + n["page"])
        if not pg or not pg.get("text"):
            continue
        body = find_section(pg["text"], n.get("section") or "")
        n["checked"] = now_ts
        if body is None:
            n["archived"] = True  # moved to an archive page or removed; keep last known replies
            continue
        n.pop("archived", None)
        replies = parse_replies(body, [n.get("by", "")])
        if len(replies) > len(n.get("replies") or []):
            events += 1
        n["replies"] = replies
        if replies and n["status"] == "posted":
            n["status"] = "replied"
    return events


def retire_notes(outreach, cases, now):
    """A note still waiting to go out whose case has closed is no longer needed."""
    n_ = 0
    for n in outreach.get("notes", []):
        c = cases.get(n.get("key"))
        if n.get("status") in ("queued", "approved") and c and c.get("c"):
            n.update(status="skipped", why_skipped=f"fixed before we posted ({c.get('how')}, {c['c']})")
            n_ += 1
    return n_


def main():
    data = load(OUT, None)
    if not data or not data.get("papers"):
        sys.exit("no data.json to recheck")
    outreach = load(OUTREACH, {"version": 1, "notes": []})
    cases = (data.get("ledger") or {}).get("cases") or {}
    open_pages = sorted({k.split("|", 1)[1] for k, c in cases.items() if not c.get("c")})
    talk_pages = sorted({"Talk:" + n["page"] for n in outreach.get("notes", []) if n.get("status") in ("posted", "replied")})
    want = open_pages + talk_pages
    log("rechecking", len(open_pages), "articles and", len(talk_pages), "talk pages")
    pages = read_pages(want) if want else {}
    got = sum(1 for t in want if pages.get(t, {}).get("text") is not None)
    if want and got < 0.5 * len(want):
        sys.exit(f"read only {got}/{len(want)} pages; Wikipedia unreachable? leaving data unchanged")
    now = today()
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    still_open = len([1 for c in cases.values() if not c.get("c")])
    closed = recheck_cases(data, pages, now)
    if still_open and len(closed) > max(10, 0.5 * still_open):
        sys.exit(f"would close {len(closed)} of {still_open} cases in one day; refusing (looks broken)")
    replies = watch_outreach(outreach, pages, now_ts)
    retire_notes(outreach, cases, now)
    for p in data["papers"]:  # older builds stored list rows and markup as quotes
        p["superseded"] = superseded(p)
        for w in p["wiki"]:
            w["said"] = clean_said(w.get("said"))
    data["checked"] = now_ts
    s = data["stats"]
    s["zombie_citations"] = sum(p["zombies"] for p in data["papers"])
    s["zombie_papers"] = sum(1 for p in data["papers"] if p["zombies"])
    s["monthly_reach"] = sum(p["reach"] for p in data["papers"])
    s["flagged_citations"] = sum(len(p["wiki"]) - p["zombies"] for p in data["papers"])
    s["zombie_pages"] = len({w["page"] for p in data["papers"] for w in p["wiki"] if w["status"] == "zombie"})
    s["pages"] = len({w["page"] for p in data["papers"] for w in p["wiki"]})
    save(OUT, data)
    if outreach.get("notes"):
        save(OUTREACH, outreach, pretty=True)
    log("closed", closed, "new reply events", replies)


if __name__ == "__main__":
    main()
