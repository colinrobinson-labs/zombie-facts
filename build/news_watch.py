#!/usr/bin/env python3
"""Zombie Facts newsroom watcher.

Looks beyond Wikipedia for facts that are dead but still walking:

1. Fact-checks. Google's Data Commons publishes every ClaimReview (the markup
   fact-checkers attach to their verdicts) as one open feed. We keep recent
   English fact-checks that rated a claim false or misleading, and the places
   the fact-checker says the claim appeared. When one of those places is a
   news outlet, that is a candidate case.
2. News stories that name a retracted paper. GDELT's free DOC API searches the
   text of recent world news. We search for the exact titles of retracted
   papers that are still being cited, then read each story (only where
   robots.txt allows it) to see whether it mentions the retraction.

Everything found lands in news.json as "unreviewed". Nothing is public, and
nothing is sent to anyone, until a person has read it and marked it
"confirmed" (or "dismissed"). Reviews are kept from run to run.

Etiquette (Colin's rule: never get blocked): official feeds and APIs only, the
zombiefacts.org User-Agent, GDELT paced at one request per 6 s with long
back-off on 429, robots.txt honoured for every story we read, one request per
host at a time, no paywalled or anti-bot sites.

Stdlib only.
"""
import json, os, re, sys, time, html, gzip
import urllib.request, urllib.parse, urllib.robotparser
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from build_data import UA, get, log, norm, superseded  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
NEWS = os.path.join(ROOT, "news.json")
OUTLETS = os.path.join(ROOT, "outlets.json")
DATA = os.path.join(ROOT, "data.json")
CLAIMREVIEW = "https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_GAP = 6.0           # GDELT asks for at most one request every 5 s
MAX_TITLES = int(os.environ.get("ZF_NEWS_TITLES", "400"))
MAX_READS = int(os.environ.get("ZF_NEWS_READS", "150"))
FACTCHECK_DAYS = int(os.environ.get("ZF_FACTCHECK_DAYS", "730"))

FALSE_RX = re.compile(r"\b(false|fake|fabricated|misleading|incorrect|inaccurate|wrong|not true|untrue|debunked|"
                      r"pants on fire|four pinocchios|baseless|unsupported|unproven|no evidence|distort|mostly false|"
                      r"partly false|half true|missing context|out of context|outdated|exaggerat|altered)\b", re.I)
TRUE_RX = re.compile(r"^\s*(true|correct|accurate|mostly true)\s*$", re.I)
# hosts that are fact-checkers, social platforms or archives, not outlets to correct
NOT_OUTLETS = re.compile(r"(^|\.)(facebook|fb|instagram|twitter|x|tiktok|youtube|youtu|t|telegram|threads|reddit|"
                         r"whatsapp|archive|web\.archive|archive\.ph|archive\.today|perma|ghostarchive|google|bit|"
                         r"rumble|bitchute|truthsocial|gettr|vk|weibo|linkedin|pinterest|snopes|politifact|factcheck|"
                         r"fullfact|leadstories|afp|reuters\.com/fact-check)\.", re.I)


# Places a claim "appeared" that are not an outlet's own reporting: screenshots and image hosts, and
# transcripts (an outlet hosting a transcript of someone speaking did not make the claim itself).
NOT_REPORTING = re.compile(r"(^|\.)(awesomescreenshot|imgur|ibb|postimg|gyazo|prnt|tinypic|flickr|giphy|"
                           r"factbase|transcripts?)\.|transcript|/factbase/|\.(png|jpe?g|gif|webp|mp4|pdf)(\?|$)|"
                           r"/wp-content/uploads/", re.I)
# The public list of fresh debunks sticks to health and science, the site's beat.
SCIENCE_RX = re.compile(r"\b(vaccin\w*|jabs?|mmr|measles|covid\w*|coronavirus|virus\w*|pandemic|plague|cancers?|"
                        r"autism|stud(y|ies)|research\w*|scientists?|diseases?|medicines?|medical|cures?|"
                        r"health\w*|diet|nutrition\w*|obesity|diabet\w*|dna|genes?|genetic\w*|climate|"
                        r"global warming|fluorid\w*|tylenol|acetaminophen|ivermectin|hydroxychloroquine|5g|"
                        r"chemtrails?|pesticides?|microplastics?|fda|cdc|nih|epidemic|outbreak|infection)\b", re.I)
SCIENCE_CASED = re.compile(r"\bWHO\b")   # the World Health Organization, not the word "who"


def now():
    return datetime.now(timezone.utc)


def today():
    return now().strftime("%Y-%m-%d")


def host(u):
    try:
        h = urllib.parse.urlsplit(u).hostname or ""
    except ValueError:
        return ""
    return h.lower().removeprefix("www.").removeprefix("m.").removeprefix("amp.")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def outlet_for(h, outlets):
    """The outlets.json entry whose domain is h or a parent of h."""
    for o in outlets:
        d = o["domain"]
        if h == d or h.endswith("." + d):
            return o
    return None


# ---------------------------------------------------------------- 1. fact-checks
def _first(x):
    return x[0] if isinstance(x, list) and x else x


def _urls(x):
    out = []
    for a in x if isinstance(x, list) else [x]:
        if isinstance(a, str):
            out.append(a)
        elif isinstance(a, dict):
            u = a.get("url") or a.get("@id") or ""
            if isinstance(u, list):
                out += [v for v in u if isinstance(v, str)]
            elif u:
                out.append(u)
    return [u for u in out if u.startswith("http")]


LEAD_RATING = re.compile(r"(?:(?:mostly|partly|partially|largely|half)\s+\w+|missing context|out of context|"
                         r"pants on fire|four pinocchios|\w+)", re.I)


def tidy_verdict(v):
    """'DW Fact check: Unproven There is no evidence...' -> 'Unproven'. Short ratings pass through."""
    v = re.sub(r"^(?:[\w .]+ )?fact[ -]?check\s*:\s*", "", v, flags=re.I)
    v = re.split(r"(?<=\w)[.;:]\s|\s[-–—]\s", v)[0].strip()
    if len(v) > 30:
        m = LEAD_RATING.match(v)
        v = m.group(0) if m else v[:30]
    return v


def parse_claimreviews(feed, since):
    """Recent English ClaimReviews that rated a claim false-ish, with where the claim appeared."""
    out = []
    for el in feed.get("dataFeedElement", []):
        for cr in el.get("item") or []:
            if not isinstance(cr, dict) or cr.get("@type") != "ClaimReview":
                continue
            date = (cr.get("datePublished") or el.get("dateCreated") or "")[:10]
            if date < since or date > today():   # some feeds carry typo'd years like 2923
                continue
            lang = (cr.get("inLanguage") or "")
            lang = (lang.get("name") or lang.get("alternateName") or "") if isinstance(lang, dict) else str(lang)
            claim = re.sub(r"\s+", " ", html.unescape(cr.get("claimReviewed") or "")).strip()
            if not claim or (lang and not lang.lower().startswith(("en", "english"))):
                continue
            if lang == "" and len(re.findall(r"[a-zA-Z]", claim)) < 0.7 * len(claim):
                continue
            rating = _first(cr.get("reviewRating")) or {}
            rating = rating if isinstance(rating, dict) else {}
            verdict = re.sub(r"\s+", " ", str(rating.get("alternateName") or rating.get("name") or "")).strip()
            verdict = tidy_verdict(verdict)
            if not verdict or TRUE_RX.match(verdict) or not FALSE_RX.search(verdict):
                continue
            author = _first(cr.get("author")) or {}
            item = _first(cr.get("itemReviewed")) or {}
            item = item if isinstance(item, dict) else {}
            said_by = _first(item.get("author")) or {}
            seen = _urls(item.get("appearance") or []) + _urls(item.get("firstAppearance") or [])
            out.append({
                "claim": claim[:400],
                "verdict": verdict[:80],
                "checker": str((author.get("name") if isinstance(author, dict) else author) or host(str(author.get("url") or "") if isinstance(author, dict) else ""))[:80],
                "url": cr.get("url") or "",
                "date": date,
                "claimant": str((said_by.get("name") if isinstance(said_by, dict) else said_by) or "")[:120],
                "seen": sorted(set(seen))[:20],
            })
    return out


def factchecks():
    log("downloading ClaimReview feed")
    b = get(CLAIMREVIEW, raw=True)
    feed = json.loads(b)
    since = (now() - timedelta(days=FACTCHECK_DAYS)).strftime("%Y-%m-%d")
    fc = parse_claimreviews(feed, since)
    log("fact-checks kept", len(fc), "since", since)
    return fc


def outlet_hits(fcs, outlets):
    """Fact-checked claims that a website published, per the fact-checker's own list of where it appeared.

    Social platforms, archives and fact-checkers themselves are left out: the lead is a site with an
    editor who can correct it. Known outlets get their name and corrections page from outlets.json.
    """
    out = []
    for f in fcs:
        for u in f["seen"]:
            h = host(u)
            if (not h or NOT_OUTLETS.search(h + ".") or NOT_REPORTING.search(h + ".") or NOT_REPORTING.search(u)
                    or h == host(f["url"])):
                continue
            o = outlet_for(h, outlets) or {"name": h, "domain": h}
            out.append({"kind": "factcheck", "url": u, "outlet": o["name"], "domain": o["domain"],
                        "claim": f["claim"], "verdict": f["verdict"], "checker": f["checker"],
                        "checkUrl": f["url"], "checked": f["date"], "known": "page" in o})
    return out


def public_checks(fcs, n=60, per_checker=6):
    """Newest health and science debunks, no more than a few from any one fact-checker."""
    out, per = [], {}
    for f in sorted(fcs, key=lambda f: f["date"], reverse=True):
        if not (SCIENCE_RX.search(f["claim"]) or SCIENCE_CASED.search(f["claim"])) or per.get(f["checker"], 0) >= per_checker:
            continue
        per[f["checker"]] = per.get(f["checker"], 0) + 1
        out.append({k: f[k] for k in ("claim", "verdict", "checker", "url", "date")})
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- 2. news naming retracted papers
_last_gdelt = [0.0]
_gdelt_fails = [0]
_gdelt_ok = [0]       # searches GDELT actually answered, so the site never overstates coverage
GDELT_GIVE_UP = 3   # GDELT often refuses shared cloud IPs; after 3 straight refusals stop asking this run


def gdelt(query, timespan="3months", n=50):
    """GDELT DOC search, paced and patient. Returns [] when GDELT keeps saying no."""
    if _gdelt_fails[0] >= GDELT_GIVE_UP:
        return []
    for i in range(2):
        wait = _last_gdelt[0] + GDELT_GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_gdelt[0] = time.time()
        u = GDELT + "?" + urllib.parse.urlencode({"query": query, "mode": "artlist", "format": "json",
                                                  "maxrecords": n, "timespan": timespan, "sort": "datedesc"})
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            _gdelt_fails[0] = 0
            _gdelt_ok[0] += 1
            if not b.strip():
                return []
            try:
                return json.loads(b).get("articles") or []
            except ValueError:  # GDELT answers bad queries with plain text
                log("gdelt said", b[:160])
                return []
        except Exception as e:
            code = getattr(e, "code", None)
            pause = 30 * (i + 1) if code == 429 else 10 * (i + 1)
            log("gdelt retry", i, code or e, "wait", pause)
            time.sleep(pause)
    _gdelt_fails[0] += 1
    if _gdelt_fails[0] >= GDELT_GIVE_UP:
        log("gdelt keeps refusing; skipping news search this run")
    return []


MEDIACLOUD = "https://search.mediacloud.org/api/search/story-list"
MC_KEY = os.environ.get("MEDIACLOUD_API_KEY", "").strip()
MC_GAP = 2.0
_last_mc = [0.0]
_mc_ok = [0]


def mediacloud(query, days=365, n=100):
    """Media Cloud online-news search (free account). Returns GDELT-shaped rows: url, title, seendate.

    Used instead of GDELT when the MEDIACLOUD_API_KEY repo secret is set. Paced at one request per 2 s,
    Retry-After honoured, gives up quietly so a Media Cloud outage never breaks the weekly run.
    """
    if not MC_KEY:
        return None
    end = now().date()
    params = {"q": query, "start": str(end - timedelta(days=days)), "end": str(end),
              "platform": "onlinenews-mediacloud", "page_size": n}
    for i in range(3):
        wait = _last_mc[0] + MC_GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_mc[0] = time.time()
        try:
            req = urllib.request.Request(MEDIACLOUD + "?" + urllib.parse.urlencode(params),
                                         headers={"User-Agent": UA, "Authorization": "Token " + MC_KEY,
                                                  "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                j = json.loads(r.read())
            _mc_ok[0] += 1
            rows = j.get("stories") if isinstance(j, dict) else j
            return [{"url": x.get("url") or "", "title": x.get("title") or "",
                     "seendate": re.sub(r"\D", "", str(x.get("publish_date") or x.get("indexed_date") or ""))[:8]}
                    for x in rows or [] if isinstance(x, dict)]
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (401, 403):
                log("mediacloud refused the key", code)
                return None
            ra = getattr(e, "headers", None) and e.headers.get("Retry-After")
            pause = int(ra) if ra and str(ra).isdigit() else 15 * (i + 1)
            log("mediacloud retry", i, code or e, "wait", pause)
            time.sleep(min(pause, 120))
    return []


def title_query(t):
    """An exact-phrase query from a paper title, or None if the title is too generic to search."""
    t = re.sub(r"^(RETRACTED( ARTICLE)?|WITHDRAWN)\s*:\s*", "", t or "", flags=re.I)
    t = re.sub(r"<[^>]+>", "", html.unescape(t))
    t = re.split(r"[:?;]", t)[0]
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", t)
    if len(words) < 6:
        return None
    return '"' + " ".join(words[:8]) + '"'   # GDELT rejects longer phrases


def papers_to_search(data):
    """Retracted papers worth searching for: the ones still cited, most-read first."""
    ps = [p for p in data.get("papers", []) if not p.get("superseded") and not superseded(p)]
    ps.sort(key=lambda p: -(p.get("reach") or 0))
    return ps[:MAX_TITLES]


def news_mentions(data, outlets):
    out = []
    for n, p in enumerate(papers_to_search(data)):
        q = title_query(p.get("title"))
        if not q:
            continue
        arts = mediacloud(q)
        if arts is None:   # no Media Cloud key (or it was refused): fall back to GDELT
            arts = gdelt(q + " sourcelang:english")
        for a in arts:
            u = a.get("url") or ""
            seen = (a.get("seendate") or "")[:8]
            out.append({"kind": "paper", "url": u, "domain": host(u), "headline": (a.get("title") or "")[:200],
                        "seen": f"{seen[:4]}-{seen[4:6]}-{seen[6:8]}" if len(seen) == 8 else "",
                        "doi": p["doi"], "paper": p.get("title", "")[:300], "retracted": p.get("retracted", ""),
                        "notice": p.get("notice", "")})
            o = outlet_for(host(u), outlets)
            if o:
                out[-1]["outlet"] = o["name"]
        if n % 25 == 0:
            log(f"searched {n + 1} titles, {len(out)} stories so far")
    return out


# ---------------------------------------------------------------- 3. read a story (politely)
_robots, _host_t = {}, {}


def allowed(u):
    h = urllib.parse.urlsplit(u)
    base = f"{h.scheme}://{h.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (401, 403):
                rp.disallow_all = True       # the site doesn't want bots: stay out
            else:
                rp.allow_all = True          # no robots.txt: allowed
        _robots[base] = rp
    return _robots[base].can_fetch(UA, u)


def read_story(u):
    """Plain text of a news story, or None if we may not or could not read it."""
    if not u.startswith("http") or not allowed(u):
        return None
    h = host(u)
    wait = _host_t.get(h, 0) + 2 - time.time()
    if wait > 0:
        time.sleep(wait)
    _host_t[h] = time.time()
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read(3_000_000)
            if r.headers.get("Content-Encoding") == "gzip":
                b = gzip.decompress(b)
    except Exception as e:
        log("story unreadable", getattr(e, "code", "") or e, u[:100])
        return None
    t = b.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", t)
    links = re.findall(r'(?i)href="([^"]+)"', t)
    text = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", text), links


def judge(item, story):
    """What the story says about the paper: 'mentions retraction', 'no mention', or None if the paper isn't there."""
    text, links = story
    text = " ".join(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text))   # same tokens as the query
    low = text.lower()
    tq = (title_query(item.get("paper")) or "").strip('"').lower()
    linked = any(norm(l).endswith(item["doi"]) or item["doi"] in urllib.parse.unquote(l).lower() for l in links)
    named = bool(tq) and tq in low
    if not (linked or named):
        return None, ""
    i = low.find(tq) if named else 0
    win = low[max(0, i - 1500): i + 1500] if named else low
    says = bool(re.search(r"retract|withdrawn|expression of concern|discredited|debunked", win))
    ctx = text[max(0, i - 200): i + len(tq) + 200].strip() if named else ""
    return ("mentions retraction" if says else "no mention"), ctx[:500]


# ---------------------------------------------------------------- 4. merge with reviews
def key(it):
    return f'{it["kind"]}|{it.get("doi") or it.get("checkUrl")}|{it["url"]}'


def merge(prev, found):
    """Keep every reviewed item and its review; add new ones as unreviewed; refresh 'last seen'."""
    items = {i["key"]: i for i in prev.get("items", [])}
    for it in found:
        k = key(it)
        if k in items:
            items[k].update({x: v for x, v in it.items() if x not in ("review", "note", "first")})
            items[k]["last"] = today()
        else:
            it.update({"key": k, "review": "unreviewed", "first": today(), "last": today()})
            items[k] = it
    return sorted(items.values(), key=lambda i: (i["review"] != "confirmed", i.get("first", "")), reverse=False)


def main():
    probe = "--probe" in sys.argv
    if probe:
        global MAX_TITLES, MAX_READS
        MAX_TITLES, MAX_READS = 12, 10
    outlets = load(OUTLETS, {}).get("outlets", [])
    data = load(DATA, {})
    prev = load(NEWS, {})
    t0 = time.time()

    try:
        fcs = factchecks()
    except Exception as e:
        log("fact-check feed failed", e); fcs = prev.get("factchecks", [])
    hits = outlet_hits(fcs, outlets)
    log("fact-checked claims published by tracked outlets", len(hits))

    stories = news_mentions(data, outlets)
    log("stories naming a retracted paper", len(stories))
    reads = 0
    for s in stories:
        if reads >= MAX_READS:
            s["verdict"] = "unread"; continue
        if s["domain"] and NOT_OUTLETS.search(s["domain"] + "."):
            s["verdict"] = "skipped"; continue
        story = read_story(s["url"]); reads += 1
        if story is None:
            s["verdict"] = "unread"; continue
        v, ctx = judge(s, story)
        s["verdict"] = v or "paper not found in story"
        if ctx:
            s["context"] = ctx
    for s in stories:
        if probe:
            print("STORY", json.dumps(s, ensure_ascii=False)[:600], flush=True)
    for h in hits[:300] if probe else []:
        print("FCHIT", json.dumps({k: h[k] for k in ("url", "outlet", "claim", "verdict", "checker", "checkUrl", "checked")}, ensure_ascii=False)[:700], flush=True)

    found = [s for s in stories if s["verdict"] in ("no mention", "unread")] + hits
    items = merge(prev, found)
    out = {
        "built": now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds": round(time.time() - t0),
        "stats": {
            "factchecks": len(fcs),
            "days": FACTCHECK_DAYS,
            "checkers": len({f["checker"] for f in fcs}),
            "titlesSearched": _gdelt_ok[0] + _mc_ok[0],
            "newsSource": "Media Cloud" if _mc_ok[0] else ("GDELT" if _gdelt_ok[0] else ""),
            "stories": len(stories),
            "storiesMentionRetraction": sum(s["verdict"] == "mentions retraction" for s in stories),
            "unreviewed": sum(i["review"] == "unreviewed" for i in items),
            "confirmed": sum(i["review"] == "confirmed" for i in items),
        },
        # the latest debunks, for the newsroom page: claim, verdict, who checked it
        "factchecks": public_checks(fcs),
        "items": items,
    }
    if probe:
        print("STATS", json.dumps(out["stats"]), flush=True)
        for f in out["factchecks"][:15]:
            print("FC", json.dumps({k: f[k] for k in ("date", "checker", "verdict", "claim")}, ensure_ascii=False)[:500], flush=True)
    save(NEWS, out)
    log("news.json written", out["stats"])


if __name__ == "__main__":
    main()
