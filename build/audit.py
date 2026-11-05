#!/usr/bin/env python3
"""Accuracy audit, run on feature-branch CI (Wikipedia and Europe PMC are not reachable elsewhere).

1. How many "flagged" citations are flagged only by a loose word match.

context_for() calls a citation "flagged" when words like "retract", "withdr" or
"removed" appear near it. Medical articles also say "drug withdrawal" and
"retractor", so some real zombies may be hidden. This re-reads every flagged
citation and reports the ones that carry no real retraction marker nearby
(Retracted template, "retracted"/"retraction", "expression of concern").

2. For every paper with a zombie citation, the text of its retraction notice from
Europe PMC, so "withdrawn as out of date" vs "retracted for cause" can be checked
by a person (NOTICE lines).

Read-only: prints a summary and AUDIT / NOTICE lines, writes nothing.
"""
import json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from build_data import OUT, get, log, read_pages  # noqa: E402

STRICT = re.compile(r"\{\{\s*retracted|\bretracted\b|\bretraction\b|expression of concern|\bwithdrawn\b(?! from)")


def windows(txt, doi):
    low = txt.lower()
    i = low.find(doi)
    if i < 0:
        i = low.find(urllib.parse.quote(doi, safe="/").lower())
    while i >= 0:
        rs = low.rfind("<ref", 0, i)
        re_ = low.find("</ref>", i)
        if rs < 0 or i - rs > 4000:
            rs = max(0, i - 300)
        yield low[max(0, rs - 600): (re_ + 400 if 0 <= re_ - i < 4000 else i + 900)]
        i = low.find(doi, i + len(doi))


def main():
    data = json.load(open(OUT))
    flagged = [(p, w) for p in data["papers"] for w in p["wiki"] if w["status"] == "flagged"]
    pages = read_pages(sorted({w["page"] for _, w in flagged}))
    loose, read = [], 0
    for p, w in flagged:
        txt = (pages.get(w["page"]) or {}).get("text")
        if not txt:
            continue
        read += 1
        ws = list(windows(txt, p["doi"]))
        if ws and not all(STRICT.search(x) for x in ws):
            hit = next(x for x in ws if not STRICT.search(x))
            m = re.search(r"retract\w*|withdr\w*|\w+ (?:\w+ )?removed\b|removed:", hit)
            loose.append({"doi": p["doi"], "page": w["page"], "section": w["section"], "views": w["views"],
                          "matched": m.group(0) if m else "?", "reasons": p["reasons"][:3]})
    log(f"flagged citations read {read}/{len(flagged)}; flagged only by a loose word: {len(loose)}")
    for x in sorted(loose, key=lambda x: -x["views"]):
        print("AUDIT", json.dumps(x, ensure_ascii=False))


def notice_text(doi):
    q = urllib.parse.urlencode({"query": f'DOI:"{doi}"', "resultType": "core", "format": "json", "pageSize": "1"})
    try:
        r = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + q, tries=2)
        res = (r.get("resultList") or {}).get("result") or []
        if res:
            x = res[0]
            return (x.get("title") or "") + " || " + re.sub(r"<[^>]+>", "", x.get("abstractText") or "")
    except Exception as e:
        return f"(lookup failed: {e})"
    return ""


def cochrane_reason(notice):
    """Withdrawal reason for a Cochrane review, from PubMed's record or the Cochrane Library page."""
    import urllib.request
    out = []
    try:
        ids = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(
            {"db": "pubmed", "term": notice + "[doi]", "retmode": "json"}), tries=2)["esearchresult"]["idlist"]
        if ids:
            x = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
                {"db": "pubmed", "id": ids[0], "rettype": "abstract", "retmode": "text"}), tries=2, raw=True)
            out.append("PUBMED " + re.sub(r"\s+", " ", x.decode("utf-8", "replace"))[:900])
    except Exception as e:
        out.append(f"pubmed failed {e}")
    try:
        req = urllib.request.Request(f"https://www.cochranelibrary.com/cdsr/doi/{notice}/full",
                                     headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
        hits = [t[max(0, m.start() - 200): m.start() + 400] for m in re.finditer(r"withdraw", t, re.I)][:3]
        out.append("COCHRANE " + " ... ".join(hits))
    except Exception as e:
        out.append(f"cochrane failed {e}")
    return " ## ".join(out)


def notices():
    data = json.load(open(OUT))
    for p in data["papers"]:
        if not p["zombies"]:
            continue
        t = notice_text(p["notice"]) if p.get("notice") else ""
        if not t.strip(" |"):
            t = notice_text(p["doi"])
        if p["doi"].startswith("10.1002/14651858") and p.get("notice"):
            print("COCHRANE", p["doi"], cochrane_reason(p["notice"]))
        print("NOTICE", json.dumps({"doi": p["doi"], "notice": p.get("notice"), "reasons": p["reasons"],
                                    "pages": [w["page"] for w in p["wiki"] if w["status"] == "zombie"],
                                    "text": t[:700]}, ensure_ascii=False))


if __name__ == "__main__":
    notices()
    main()
