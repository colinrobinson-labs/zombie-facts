#!/usr/bin/env python3
"""Print what a reviewer needs for every open case that has no verdict yet.

Runs on feature-branch CI after recheck.py has written the wikitext around each open
citation (ZF_DUMP_CONTEXT). One REVIEW line per case, most-read first: the paper, why it
was retracted, who else confirms it, and the wikitext the citation sits in. Read-only.

    python build/review_queue.py /tmp/contexts.json
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from build_data import OUT, superseded  # noqa: E402


def main(path):
    try:
        ctx = json.load(open(path))
    except (OSError, ValueError):
        print("review: no contexts file")
        return
    data = json.load(open(OUT))
    try:
        notes = json.load(open(os.path.join(os.path.dirname(OUT), "outreach.json"))).get("notes", [])
    except (OSError, ValueError):
        notes = []
    seen = {n["key"] for n in notes}
    papers = {p["doi"]: p for p in data["papers"]}
    rows = []
    for k, c in ((data.get("ledger") or {}).get("cases") or {}).items():
        doi, page = k.split("|", 1)
        p = papers.get(doi)
        if c.get("c") or k in seen or not p or superseded(p):
            continue
        x = ctx.get(k) or {}
        w = next((w for w in p["wiki"] if w["page"] == page), {})
        rows.append({"key": k, "views": c.get("v") or 0, "section": x.get("section") or w.get("section"),
                     "title": p["title"][:160], "journal": p.get("journal"), "retracted": p.get("retracted"),
                     "reasons": p.get("reasons"), "notice": p.get("notice"), "confirm": p.get("confirm"),
                     "authors": (p.get("authors") or [])[:3], "said": w.get("said"),
                     "wikitext": (x.get("wikitext") or "")[-1300:]})
    rows.sort(key=lambda r: -r["views"])
    print(f"review: {len(rows)} open cases with no verdict")
    for r in rows:
        print("REVIEW", json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/contexts.json")
