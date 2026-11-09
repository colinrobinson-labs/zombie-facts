#!/usr/bin/env python3
"""Zombie Facts data builder.

Finds every retracted paper (Retraction Watch database, published openly by
Crossref) that English Wikipedia still links to, then reads each citing
article to see whether the retraction is mentioned near the citation.

Output: data.json, consumed by index.html.
Stdlib only. Runs in GitHub Actions (see .github/workflows/zombie-facts.yml).
"""
import unicodedata
import csv, io, json, re, sys, time, gzip, os, html
import urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from collections import Counter, defaultdict

CONTACT = "tips@zombiefacts.org"  # a working inbox, so a source that has a problem with us can write instead of blocking
UA = f"ZombieFacts/1.1 (https://zombiefacts.org/; {CONTACT}) retraction tracker"
WP = "https://en.wikipedia.org/w/api.php"
OUT = os.path.join(os.path.dirname(__file__), "..", "data.json")
RW_URLS = [
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    "https://api.labs.crossref.org/data/retractionwatch?mailto=tips@zombiefacts.org",
]
MAX_PAGES_READ = int(os.environ.get("ZF_MAX_PAGES", "6000"))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def get(url, tries=7, raw=False):
    """GET with a descriptive User-Agent, honouring Retry-After and Wikipedia's maxlag.

    Being a good citizen keeps us from being blocked: every request names the
    project, a 429/503 waits as long as the server asks, and a maxlag reply
    (servers busy) backs off instead of hammering.
    """
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                if raw:
                    return b
                j = json.loads(b)
                err = j.get("error") if isinstance(j, dict) else None
                if isinstance(err, dict) and err.get("code") == "maxlag":
                    wait = int(r.headers.get("Retry-After") or 5) * (i + 1)
                    log("maxlag, waiting", wait, "s")
                    time.sleep(wait)
                    continue
                return j
        except Exception as e:
            code = getattr(e, "code", None)
            ra = getattr(e, "headers", None) and e.headers.get("Retry-After")
            wait = int(ra) if ra and str(ra).isdigit() else 2 * (i + 1) * (5 if code in (429, 503) else 1)
            log("retry", i, code or e, url[:120], "wait", wait)
            time.sleep(min(wait, 300))
    raise RuntimeError("failed: " + url)


def norm(doi):
    d = urllib.parse.unquote(doi or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = d.split("#")[0].split("?")[0]
    return d.rstrip(".,;)")


def mdy(s):
    s = (s or "").split(" ")[0]
    try:
        return datetime.strptime(s, "%m/%d/%Y").strftime("%Y-%m-%d")
    except Exception:
        return ""


def pmid_of(s):
    s = (s or "").strip()
    return s if s.isdigit() and s != "0" else ""


def positions(low, doi, pmid=""):
    """Every place lowercased wikitext cites the paper: its DOI (plain or URL-encoded) or its PubMed ID."""
    out = set()
    for needle in {doi, urllib.parse.quote(doi, safe="/").lower()}:
        j = low.find(needle)
        while j >= 0:
            out.add(j)
            j = low.find(needle, j + len(needle))
    if pmid:
        for m in re.finditer(r"(?:pmid\s*=\s*|\{\{\s*pmid\s*\|\s*|pubmed(?:\.ncbi\.nlm\.nih\.gov)?/(?:pubmed/)?)" + pmid + r"(?!\d)", low):
            out.add(m.start())
    return sorted(out)


# ---------------------------------------------------------------- 1. Retraction Watch
def load_rw():
    for u in RW_URLS:
        try:
            log("downloading", u)
            b = get(u, raw=True)
            break
        except Exception as e:
            log("rw source failed", e)
    else:
        raise SystemExit("no Retraction Watch source reachable")
    text = b.decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    log("rw rows", len(rows), "cols", list(rows[0].keys()))
    out = {}
    for r in rows:
        nat = (r.get("RetractionNature") or "").strip().lower()
        if nat != "retraction":
            continue
        d = norm(r.get("OriginalPaperDOI"))
        if not d.startswith("10.") or d in ("unavailable",):
            continue
        reasons = [x.strip().lstrip("+").strip() for x in (r.get("Reason") or "").split(";") if x.strip()]
        rec = {
            "doi": d,
            "title": (r.get("Title") or "").strip(),
            "journal": (r.get("Journal") or "").strip(),
            "publisher": (r.get("Publisher") or "").strip(),
            "authors": [a.strip() for a in (r.get("Author") or "").split(";") if a.strip()],
            "country": [c.strip() for c in (r.get("Country") or "").split(";") if c.strip()],
            "subject": [s.strip() for s in (r.get("Subject") or "").split(";") if s.strip()],
            "published": mdy(r.get("OriginalPaperDate")),
            "retracted": mdy(r.get("RetractionDate")),
            "notice": norm(r.get("RetractionDOI")) if (r.get("RetractionDOI") or "").startswith("10.") else "",
            "reasons": reasons,
            "type": (r.get("ArticleType") or "").strip(),
            "rwid": (r.get("Record ID") or "").strip(),
            "pmid": pmid_of(r.get("OriginalPaperPubMedID")),
        }
        prev = out.get(d)
        if not prev or rec["retracted"] > prev["retracted"]:
            out[d] = rec
    log("retracted DOIs", len(out))
    return out


# ---------------------------------------------------------------- 2. Wikipedia links
DUMPS = [
    "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-externallinks.sql.gz",
    "https://mirror.accum.se/mirror/wikimedia.org/dumps/enwiki/latest/enwiki-latest-externallinks.sql.gz",
]


def find_wiki_links(rw):
    """Stream the full enwiki externallinks table (official dump) and keep doi.org and PubMed links to retracted papers.

    Citation templates turn |doi= into a doi.org link and |pmid= into a PubMed link, so a paper cited
    only by its PubMed ID is caught too."""
    import subprocess
    pat = r"\([0-9]+,[0-9]+,'https?://(org\.doi\.(dx\.)?|gov\.nih\.nlm\.ncbi\.(www\.|pubmed\.)?)','[^']*'\)"
    rows = None
    for u in DUMPS:
        log("streaming dump", u)
        cmd = f"curl -sSfL --retry 3 -A '{UA}' '{u}' | zcat | grep -oE \"{pat}\""
        pr = subprocess.run(["bash", "-o", "pipefail", "-c", cmd], capture_output=True)
        if pr.returncode == 0 and pr.stdout:
            rows = pr.stdout.decode("utf-8", "replace").splitlines()
            break
        log("dump failed", pr.returncode, pr.stderr[-400:])
    if rows is None:
        raise SystemExit("no dump reachable")
    log("doi.org and PubMed links in enwiki", len(rows))
    rx = re.compile(r"\(([0-9]+),([0-9]+),'([^']*)','([^']*)'\)")
    by_pmid = {r["pmid"]: d for d, r in rw.items() if r.get("pmid")}
    by_page = defaultdict(set)
    for line in rows:
        m = rx.match(line)
        if not m:
            continue
        if ".doi." in m.group(3):
            d = norm(m.group(4).lstrip("/"))
        else:
            pm = re.match(r"^/(?:pubmed/)?(\d+)(?:[/?#]|$)", m.group(4))
            d = by_pmid.get(pm.group(1)) if pm else None
        if d and d in rw:
            by_page[int(m.group(2))].add(d)
    log("pages linking retracted DOIs (all namespaces)", len(by_page))
    # page ids -> titles, mainspace only
    ids = list(by_page)
    titles = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        try:
            j = get(WP + "?" + urllib.parse.urlencode({"action": "query", "pageids": "|".join(map(str, chunk)),
                                                         "format": "json", "formatversion": "2"}))
        except Exception as e:
            log("title lookup failed", e); continue
        for pg in j.get("query", {}).get("pages", []):
            if pg.get("ns") == 0 and "title" in pg:
                titles[pg["pageid"]] = pg["title"]
        time.sleep(0.2)
    hits = defaultdict(set)
    for pid, ds in by_page.items():
        if pid in titles:
            for d in ds:
                hits[d].add(titles[pid])
    log("retracted DOIs cited in articles", len(hits), "articles", len(titles))
    return hits, len(rows)


# ---------------------------------------------------------------- 3. read articles
WIKI_LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")


def plain(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    for _ in range(4):
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"^.*\}\}", "", s, flags=re.S)
    s = re.sub(r"\{\{.*$", "", s, flags=re.S)
    s = WIKI_LINK.sub(r"\1", s)
    s = re.sub(r"\[https?://\S+ ([^\]]+)\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


PROCEDURAL = re.compile(r"out of date|retract and replace|^removed$|temporary removal|limited or no information|"
                        r"date of (?:article|retraction)|notice unknown|upgrade/update", re.I)


REPLACED = re.compile(r"retract and replace", re.I)


def replaced(p):
    """Retracted and republished in corrected form ("retract and replace"): a newer version stands."""
    return any(REPLACED.search(r) for r in p.get("reasons") or [])


def superseded(p):
    """Not presented as a zombie, because a newer version of the work stands.

    1. Retract and replace, from any journal: the publisher retracted the paper and republished a
       corrected version (PREDIMED in NEJM, 2018, is the famous one). Citing it is out of date, not
       citing a dead fact; the case page says to cite the new version instead.
    2. A Cochrane review withdrawn for procedural reasons (out of date, handed to new authors).
       PubMed's withdrawal notices for these say e.g. "This review is to be passed onto a new group of
       authors". Withdrawals with any substantive reason (data concerns, conflict of interest,
       misconduct) are kept.
    """
    if replaced(p):
        return True
    if not p["doi"].startswith("10.1002/14651858"):
        return False
    rs = p.get("reasons") or []
    return bool(rs) and all(PROCEDURAL.search(r) for r in rs)


def clean_said(s):
    """The quoted sentence, or "" when it isn't a readable sentence (list rows, markup, cut-off fragments)."""
    s = re.sub(r"^[\s*#:;•\-–]+", "", s or "").strip()
    if not s or re.search(r"https?:|\[\[|\]\]|\[\S+\.\S+|\{|\}|\|", s):
        return ""
    if len(re.findall(r"[A-Za-z]{2,}", s)) < 6:
        return ""
    return s


def context_for(txt, low, i):
    """Sentence the citation supports, its section, and whether the retraction is mentioned."""
    rs = low.rfind("<ref", 0, i)
    re_ = low.find("</ref>", i)
    tag_end = low.find(">", rs) if rs >= 0 else -1
    # the DOI is inside this <ref> only if the ref is open (not self-closing, not closed) before it
    inside = rs >= 0 and i - rs <= 4000 and low[tag_end - 1] != "/" and low.find("</ref>", rs, i) < 0
    if not inside:
        # inline citation such as {{doi-inline}} in a list row: the text before it on the same line
        ls = low.rfind("\n", 0, i) + 1
        t0 = low.rfind("{{", ls, i)
        rs = t0 if t0 >= 0 else max(ls, i - 300)
        le = low.find("\n", i)
        row_end = le if le >= 0 else len(low)
    # first occurrence might be a named ref defined in a reference list
    a = max(0, rs - 1600)
    before = txt[a:rs]
    # cut to the start of the paragraph / sentence
    before = before.split("\n\n")[-1].split("\n")[-1]
    sent = plain(before)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", sent)
    sentence = parts[-1] if parts else sent
    if len(sentence) < 40 and len(parts) > 1:
        sentence = parts[-2] + " " + sentence
    sentence = clean_said(re.sub(r"\s*\([^()]{1,40}\)$", "", sentence[-420:]))
    sec = "Lead"
    for m in re.finditer(r"^(={2,4})\s*(.+?)\s*\1\s*$", txt[:i], flags=re.M):
        sec = plain(m.group(2))
    if inside:
        win = low[max(0, rs - 600): (re_ + 400 if 0 <= re_ - i < 4000 else i + 900)]
    else:  # an inline citation: only its own list row
        win = low[low.rfind("\n", 0, i) + 1: row_end]
    flagged = bool(re.search(r"retract|\{\{\s*retracted|expression of concern|withdr|\bremoved:|was (?:\w+ )?removed\b", win))
    return sentence, sec, flagged


def read_pages(titles):
    out = {}
    titles = list(titles)

    def batch(chunk):
        p = {"action": "query", "prop": "revisions|pageviews|info", "rvprop": "content|timestamp",
             "rvslots": "main", "pvipdays": "30", "titles": "|".join(chunk), "format": "json",
             "formatversion": "2", "maxlag": "5"}
        try:
            j = get(WP + "?" + urllib.parse.urlencode(p))
        except Exception as e:
            log("read failed", e); return {}
        r = {}
        for pg in j.get("query", {}).get("pages", []):
            rev = (pg.get("revisions") or [{}])[0]
            views = sum(v or 0 for v in (pg.get("pageviews") or {}).values())
            r[pg["title"]] = {"text": rev.get("slots", {}).get("main", {}).get("content", ""),
                               "ts": rev.get("timestamp", ""), "views": views}
        return r

    # content of many pages per request is limited; 10 is safe and fast enough.
    # One request at a time: Wikimedia's API etiquette asks clients not to run requests in parallel.
    chunks = [titles[i:i + 10] for i in range(0, len(titles), 10)]
    with ThreadPoolExecutor(1) as ex:
        for n, r in enumerate(ex.map(batch, chunks)):
            out.update(r)
            if n % 50 == 0:
                log(f"read {len(out)}/{len(titles)} pages")
    return out


def _nm(s):
    return re.sub(r"[^a-z ]", "", re.sub(r"\s*\(.*?\)", "", s.lower())).split()


def _fold(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def is_subject_page(txt, authors):
    """True when the article is about the retraction itself: its lead talks about a retraction or
    fraud and names one of the paper's authors (e.g. "Schön scandal", "When Contact Changes Minds").
    Such articles cite the paper on purpose, so it is not a zombie."""
    lead = re.split(r"\n==[^=]", txt or "", maxsplit=1)[0]
    lead = _fold(re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|\{\{[^{}]*\}\}", " ", lead, flags=re.S))
    if not re.search(r"retract|fabricat|falsif|fraud|misconduct", lead):
        return False
    for a in authors or []:
        last = re.sub(r"[^a-z\- ]", "", _fold(re.sub(r"\s*\(.*?\)", "", a))).split()
        if last and len(last[-1]) >= 3 and re.search(r"\b" + re.escape(last[-1]) + r"\b", lead):
            return True
    return False


def is_author_page(title, authors):
    """True when the article title is one of the paper's authors (first and last name match)."""
    t = _nm(title)
    if len(t) < 2:
        return False
    for a in authors:
        n = _nm(a)
        if len(n) >= 2 and n[0] == t[0] and n[-1] == t[-1]:
            return True
    return False


# ---------------------------------------------------------------- 4. Crossref extras
def crossref_counts(dois):
    out = {}
    dois = list(dois)

    def batch(chunk):
        f = ",".join("doi:" + d for d in chunk)
        u = "https://api.crossref.org/works?" + urllib.parse.urlencode(
            {"filter": f, "rows": len(chunk), "select": "DOI,is-referenced-by-count,title,container-title,issued",
             "mailto": CONTACT})
        try:
            return get(u)["message"]["items"]
        except Exception as e:
            log("crossref batch failed", e); return []

    chunks = [dois[i:i + 40] for i in range(0, len(dois), 40)]
    with ThreadPoolExecutor(2) as ex:  # Crossref's polite pool allows a few concurrent requests; stay under it
        for items in ex.map(batch, chunks):
            for w in items:
                out[w["DOI"].lower()] = w
    log("crossref enriched", len(out))
    return out


# ---------------------------------------------------------------- 5. correction ledger
def load_prev():
    try:
        with open(OUT) as f:
            return json.load(f)
    except Exception:
        return {}


def sanity_check(prev, papers, rw):
    """Refuse to publish a build that lost most of the record (a source outage, not real change)."""
    ps = (prev or {}).get("stats") or {}
    if len(rw) < 0.8 * (ps.get("retractions") or 0):
        raise SystemExit(f"Retraction Watch shrank from {ps['retractions']} to {len(rw)} records; not publishing")
    before = ps.get("cited") or 0
    if before and len(papers) < 0.6 * before:
        raise SystemExit(f"cited papers dropped from {before} to {len(papers)}; not publishing")

def update_ledger(prev, papers, hits, pages, today):
    """Carry every zombie citation forward as a case, week to week.

    A case is one retracted DOI cited on one article. It opens the first week the
    citation is seen with no warning nearby, and closes when a later build finds
    the article now flags it ("flagged") or no longer links the DOI ("removed").
    Pages we failed to read this run never close a case.
    """
    old = (prev.get("ledger") or {})
    cases = {k: dict(v) for k, v in (old.get("cases") or {}).items()}
    since = old.get("since") or today
    by_doi = {p["doi"]: p for p in papers}
    now_z, now_f = {}, {}
    for p in papers:
        for c in p["wiki"]:
            k = p["doi"] + "|" + c["page"]
            if c["status"] == "zombie":
                now_z[k] = (p, c)
            else:
                now_f[k] = c["status"]
    opened = closed = reopened = 0
    for k, (p, c) in now_z.items():
        rec = cases.get(k)
        if rec is None:
            cases[k] = {"o": today, "c": None, "how": None}
            opened += 1
        elif rec.get("c"):
            rec.update(c=None, how=None, re=(rec.get("re") or 0) + 1)
            reopened += 1
        cases[k].update(t=p["title"][:200], pg=c["page"], v=c["views"], r=p["retracted"])
    to_close = []
    for k, rec in cases.items():
        if rec.get("c") or k in now_z:
            continue
        doi, page = k.split("|", 1)
        if k in now_f:
            to_close.append((k, now_f[k]))
        elif page not in hits.get(doi, ()):
            to_close.append((k, "removed"))
        elif page in pages and pages[page].get("text"):
            # still linked and readable but neither zombie nor flagged: DOI text gone from wikitext
            to_close.append((k, "removed"))
        # else: page not read this run, leave open
    still_open = sum(1 for r in cases.values() if not r.get("c"))
    if still_open and len(to_close) > max(10, 0.5 * still_open):
        log("ledger: refusing to close", len(to_close), "of", still_open, "cases in one run (looks like a partial build)")
        to_close = []
    for k, how in to_close:
        cases[k].update(c=today, how=how)
        closed += 1
    log("ledger: opened", opened, "closed", closed, "reopened", reopened)
    return {"since": since, "cases": cases}


def main():
    started = time.time()
    rw = load_rw()
    hits, links_scanned = find_wiki_links(rw)
    # most-linked first so the page cap keeps the important ones
    titles = Counter(t for ts in hits.values() for t in ts)
    order = [t for t, _ in titles.most_common()]
    if len(order) > MAX_PAGES_READ:
        log("capping pages", len(order), "->", MAX_PAGES_READ)
        order = order[:MAX_PAGES_READ]
    pages = read_pages(order)
    cr = crossref_counts(hits.keys())

    papers = []
    for d, ts in hits.items():
        rec = dict(rw[d])
        w = cr.get(d, {})
        rec["cites"] = w.get("is-referenced-by-count")
        if not rec["title"] and w.get("title"):
            rec["title"] = w["title"][0]
        cites = []
        for t in sorted(ts):
            pg = pages.get(t)
            if not pg or not pg["text"]:
                continue
            txt = pg["text"]
            low = txt.lower()
            where = positions(low, d, rec.get("pmid"))
            if not where:
                continue
            # look at every occurrence: zombie if any is unflagged; quote the first one of that kind
            # that gives a readable sentence (a named ref's first use can be a bare list row)
            seen = [context_for(txt, low, j) for j in where]
            flagged_all = all(fl for _, _, fl in seen)
            pool = seen if flagged_all else [x for x in seen if not x[2]]
            sent, sec, _ = next((x for x in pool if x[0]), pool[0])
            status = "flagged" if flagged_all else "zombie"
            if status == "zombie" and is_author_page(t, rec["authors"]):
                status = "author"  # biography of an author: the citation is about the paper itself
            elif status == "zombie" and is_subject_page(txt, rec["authors"]):
                status = "subject"  # the article is about the retraction scandal itself
            cites.append({"page": t, "status": status, "said": sent,
                          "section": sec, "views": pg["views"], "rev": pg["ts"][:10]})
        if not cites:
            continue
        rec["superseded"] = superseded(rec)
        rec["replaced"] = replaced(rec)
        rec["wiki"] = sorted(cites, key=lambda c: (c["status"] != "zombie", -c["views"]))
        rec["zombies"] = sum(c["status"] == "zombie" for c in cites)
        rec["reach"] = sum(c["views"] for c in cites if c["status"] == "zombie")
        papers.append(rec)

    papers.sort(key=lambda p: (-p["reach"], -p["zombies"]))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prev = load_prev()
    sanity_check(prev, papers, rw)
    ledger = update_ledger(prev, papers, hits, pages, today)
    reasons = Counter(r for p in papers if p["zombies"] for r in p["reasons"])
    countries = Counter(c for p in papers if p["zombies"] for c in p["country"])
    years = Counter((p["retracted"] or "")[:4] for p in papers if p["zombies"])
    subjects = Counter(re.sub(r"^\(\w+\)\s*", "", s) for p in papers if p["zombies"] for s in p["subject"])
    data = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "seconds": round(time.time() - started),
        "stats": {
            "retractions": len(rw),
            "links_scanned": links_scanned,
            "cited": len(papers),
            "zombie_papers": sum(1 for p in papers if p["zombies"]),
            "zombie_citations": sum(p["zombies"] for p in papers),
            "flagged_citations": sum(len(p["wiki"]) - p["zombies"] for p in papers),
            "pages": len({c["page"] for p in papers for c in p["wiki"]}),
            "zombie_pages": len({c["page"] for p in papers for c in p["wiki"] if c["status"] == "zombie"}),
            "monthly_reach": sum(p["reach"] for p in papers),
        },
        "reasons": reasons.most_common(25),
        "countries": countries.most_common(25),
        "subjects": subjects.most_common(25),
        "years": sorted(years.items()),
        "papers": papers,
        "ledger": ledger,
    }
    with open(OUT, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log("wrote", OUT, os.path.getsize(OUT), "bytes", data["stats"])


if __name__ == "__main__":
    main()
