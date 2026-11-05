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
import json, os, re, sys, time, urllib.parse
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


def loose_flags(data):
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
    return sorted(loose, key=lambda x: -x["views"]), read, len(flagged)


def offline_checks(data, outreach):
    """Consistency checks that need no network."""
    from build_data import clean_said, superseded
    issues = []
    cases = (data.get("ledger") or {}).get("cases") or {}
    for p in data["papers"]:
        if bool(p.get("superseded")) != superseded(p):
            issues.append(f"superseded flag out of date: {p['doi']}")
        if p["zombies"] != sum(w["status"] == "zombie" for w in p["wiki"]):
            issues.append(f"zombie count mismatch: {p['doi']}")
        for w in p["wiki"]:
            if w.get("said") and clean_said(w["said"]) != w["said"]:
                issues.append(f"unclean quote on {w['page']}: {w['said'][:60]!r}")
            if w["status"] == "zombie" and p["doi"] + "|" + w["page"] not in cases:
                issues.append(f"zombie without a case: {p['doi']} on {w['page']}")
    for n in outreach.get("notes", []):
        c = cases.get(n["key"])
        if n.get("status") in ("queued", "approved") and c and c.get("c"):
            issues.append(f"note still {n['status']} but case closed ({c.get('how')}): {n['page']}")
    return issues


PROCEDURAL_TEXT = re.compile(r"new group of authors|out of date|has been updated|superseded|update in ", re.I)


def report(path):
    data = json.load(open(OUT))
    try:
        outreach = json.load(open(os.path.join(os.path.dirname(OUT), "outreach.json")))
    except FileNotFoundError:
        outreach = {"notes": []}
    issues = offline_checks(data, outreach)
    loose, read, nflag = loose_flags(data)
    review = []
    for p in data["papers"]:
        if not p["zombies"] or p.get("superseded") or not p["doi"].startswith("10.1002/14651858") or not p.get("notice"):
            continue
        t = cochrane_reason(p["notice"])
        if PROCEDURAL_TEXT.search(t):
            review.append(f"`{p['doi']}` ({', '.join(p['reasons'][:3])}): PubMed notice reads as procedural. "
                          f"Check before reporting: {t[:300]}")
    live = [p for p in data["papers"] if p["zombies"] and not p.get("superseded")]
    lines = [f"Data built {data.get('built')}, checked {data.get('checked') or 'n/a'}.",
             f"**{sum(p['zombies'] for p in live)} zombie citations on {len(live)} papers** "
             f"({sum(1 for p in data['papers'] if p['zombies'] and p.get('superseded'))} superseded Cochrane reviews excluded).", "",
             f"### Flag check\nRe-read {read}/{nflag} flagged citations; {len(loose)} flagged only by a loose word."]
    lines += [f"- {x['page']} (`{x['doi']}`), matched \"{x['matched']}\", {x['views']} views/mo" for x in loose[:30]]
    lines += ["", f"### Consistency\n{len(issues)} issue(s)."] + [f"- {i}" for i in issues[:50]]
    lines += ["", f"### Cochrane reviews to re-check\n{len(review)} still counted as zombies but read as procedural."]
    lines += [f"- {r}" for r in review]
    bad = len(issues) + len(review) + max(0, len(loose) - 1)
    lines.insert(0, ("All clear." if not bad else f"{bad} item(s) need a look.") + "\n")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    log("audit report written", path, "items", bad)
    return bad


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
    """Withdrawal reason for a Cochrane review, from PubMed's record (NCBI E-utilities, <3 requests/s)."""
    out = []
    try:
        ids = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(
            {"db": "pubmed", "term": notice + "[doi]", "retmode": "json"}), tries=2)["esearchresult"]["idlist"]
        time.sleep(0.5)
        if ids:
            x = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
                {"db": "pubmed", "id": ids[0], "rettype": "abstract", "retmode": "text"}), tries=2, raw=True)
            time.sleep(0.5)
            out.append("PUBMED " + re.sub(r"\s+", " ", x.decode("utf-8", "replace"))[:900])
    except Exception as e:
        out.append(f"pubmed failed {e}")
    # The Cochrane Library blocks automated clients; we don't scrape it.
    return " ## ".join(out)


def notices():
    data = json.load(open(OUT))
    for p in data["papers"]:
        if not p["zombies"]:
            continue
        time.sleep(0.3)  # Europe PMC asks for modest request rates
        t = notice_text(p["notice"]) if p.get("notice") else ""
        if not t.strip(" |"):
            t = notice_text(p["doi"])
        if p["doi"].startswith("10.1002/14651858") and p.get("notice"):
            print("COCHRANE", p["doi"], cochrane_reason(p["notice"]))
        print("NOTICE", json.dumps({"doi": p["doi"], "notice": p.get("notice"), "reasons": p["reasons"],
                                    "pages": [w["page"] for w in p["wiki"] if w["status"] == "zombie"],
                                    "text": t[:700]}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--report":
        report(sys.argv[2])
    else:
        notices()
        for x in loose_flags(json.load(open(OUT)))[0]:
            print("AUDIT", json.dumps(x, ensure_ascii=False))
