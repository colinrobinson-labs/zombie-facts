#!/usr/bin/env python3
"""Branch-only diagnostic: for open zombie citations with no quoted sentence, print the wikitext
just before the citation, so the sentence finder can be improved. Reads ZF_DUMP_CONTEXT output."""
import json, os, re, sys

ctx = json.load(open(sys.argv[1]))
data = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data.json")))
said = {(p["doi"], w["page"]): w.get("said") for p in data["papers"] for w in p["wiki"]}
for k, v in ctx.items():
    doi, page = k.split("|", 1)
    if said.get((doi, page)):
        continue
    t = v["wikitext"]
    i = t.lower().find(doi)
    before = re.sub(r"\s+", " ", t[max(0, i - 700):i])
    print("NOQ", json.dumps({"k": k, "sec": v["section"], "before": before}, ensure_ascii=False))
