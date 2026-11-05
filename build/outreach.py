#!/usr/bin/env python3
"""Draft correction notes for outreach.json.

  python build/outreach.py draft "<doi>|<page>" --status queued --verdict "why"

A note's lifecycle: queued (reviewed, waiting its turn) -> approved (next to post)
-> posted -> replied, or dismissed (reviewed: not a problem, with the reason).
recheck.py fills in replies; the weekly build and recheck close the case itself.
"""
import argparse, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from build_data import OUT  # noqa: E402
from recheck import OUTREACH, load, save  # noqa: E402

SITE = "https://zombiefacts.org/"


def fmt(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%-d %B %Y")
    except ValueError:
        return d


def short(t, n=70):
    t = re.sub(r"^(RETRACTED( ARTICLE)?|WITHDRAWN|REMOVED)\s*:\s*", "", t, flags=re.I).strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def where(sec):
    if sec == "Lead":
        return "lead"
    if sec.lower() in ("references", "notes", "citations", "sources", "footnotes", "bibliography"):
        return "article"
    return "section " + chr(34) + sec + chr(34)


def note_text(p, w, why):
    notice = f" ([https://doi.org/{p['notice']} retraction notice])" if p.get("notice") else ""
    sec = w.get("section") or "Lead"
    said = (w.get("said") or "").strip().replace('"', "'")
    support = f' It is cited for: "{said}"' if said and not said.startswith("|") else ""
    return (
        f"The {where(sec)} cites ''{short(p['title'], 200)}'' "
        f"([https://doi.org/{p['doi']} doi:{p['doi']}]), which was retracted on {fmt(p['retracted'])}{notice}."
        f"{support} {why} "
        "Suggest replacing the source or marking it with {{tl|Retracted}}; if it is cited on purpose to discuss the retraction, "
        f"please disregard. (Found by [{SITE} Zombie Facts], which tracks retracted papers still cited on Wikipedia.) ~~~~"
    )


def draft(key, status, verdict):
    data = load(OUT, None)
    doi, page = key.split("|", 1)
    p = next(x for x in data["papers"] if x["doi"] == doi)
    w = next(x for x in p["wiki"] if x["page"] == page)
    out = load(OUTREACH, {"version": 1, "notes": []})
    out["notes"] = [n for n in out["notes"] if n["key"] != key]
    n = {"key": key, "doi": doi, "page": page, "status": status, "verdict": verdict,
         "reviewed": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    if status != "dismissed":
        n["section"] = "Retracted source: " + short(p["title"], 60)
        n["text"] = note_text(p, w, verdict)
    out["notes"].append(n)
    save(OUTREACH, out, pretty=True)
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["draft"])
    ap.add_argument("key")
    ap.add_argument("--status", default="queued", choices=["queued", "approved", "dismissed"])
    ap.add_argument("--verdict", required=True)
    a = ap.parse_args()
    print(json.dumps(draft(a.key, a.status, a.verdict), indent=1, ensure_ascii=False))
