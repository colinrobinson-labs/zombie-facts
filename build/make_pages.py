#!/usr/bin/env python3
"""Build the site's pages from src/.

Every page shares src/_head.html (meta, fonts), the masthead + nav below, the case
drawer (src/_drawer.html), /assets/site.css and /assets/app.js. Each page's body is
assembled from fragments in src/pages/. Run after editing anything in src/:

    python build/make_pages.py          # writes index.html, register/index.html, ...
    python build/make_pages.py --check  # exit 1 if the committed pages are stale (CI)
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
import site_extras as X  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC = os.path.join(ROOT, "src")
SITE = "https://zombiefacts.org"

PAGES = [  # slug, nav label, <title>, description, fragments, next slug
    ("", "Home", "Zombie Facts", "Retracted, debunked and outdated facts that are still in circulation, and the fight to fix them. Starting with every retraction on record, checked against every source on English Wikipedia.",
     ["_hero", "_worst", "_deskhome", "_explore"], "register"),
    ("register", "Register", "The register · Zombie Facts", "Search every retracted paper English Wikipedia still cites, with the exact sentences and the official retraction notices.",
     ["_register"], "desk"),
    ("desk", "Correction desk", "Correction desk · Zombie Facts", "Every zombie citation is a case: reviewed by hand, reported to Wikipedia editors, and tracked until it is fixed.",
     ["_desk"], "news"),
    ("news", "Newsroom", "Newsroom · Zombie Facts", "Retracted research and debunked claims still circulating in the news, and what happens when we ask outlets to fix them.",
     ["_newsroom"], "results"),
    ("results", "Results", "Results · Zombie Facts", "@results",
     ["@results"], "autopsy"),
    ("autopsy", "Autopsy", "Autopsy · Zombie Facts", "Why the papers Wikipedia still cites were retracted, and when.",
     ["_autopsy"], "check"),
    ("check", "Check a page", "Check a page · Zombie Facts", "Scan any Wikipedia article for retracted sources, live in your browser.",
     ["_check"], "method"),
    ("method", "Method", "How it works · Zombie Facts", "How Zombie Facts finds retracted and debunked facts still in circulation, how cases are reviewed, and how corrections are tracked.",
     ["_method"], "about"),
]

# Pages linked from the footer (and from other pages), not the top nav.
EXTRA = [
    ("about", "About", "About · Zombie Facts", "Who runs Zombie Facts, how it is paid for, how we correct our own mistakes, and how to contest a case.",
     ["_about"], "report"),
    ("report", "Report a zombie", "Report a zombie · Zombie Facts", "Seen a retracted, debunked or outdated fact still in circulation? Send it in. Every tip is read by a person.",
     ["_report"], ""),
]

NAV_ICON = '<svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1.5a6.5 6.5 0 0 1 0 13z" fill="currentColor"/></svg>'


MARK = ('<svg class="mark" viewBox="0 0 40 40" aria-hidden="true">'
        '<path class="hd" d="M8 9.5C10 4.5 17 3 23 3.6c7.4.8 11.6 5.3 11.3 12.6-.2 4.7.9 8.7-.6 13.2-1.6 4.7-6.3 7.4-12.6 7.6-6.9.2-12.4-2.2-14-7.6C5.6 24.6 6 14.3 8 9.5z"/>'
        '<path class="ln" d="M12 8.6l9.8-1.4M14.2 6.6l.7 3.4M17.6 6.1l.6 3.3M20.6 5.7l.6 3.3"/>'
        '<path class="ln" d="M11 15.2l5.6 5.4M16.6 15.2L11 20.6"/>'
        '<g class="eye"><circle cx="26.4" cy="17.6" r="4.6" class="wh"/><circle cx="27.6" cy="18.4" r="1.9" class="pu"/></g>'
        '<path class="ln" d="M12.6 28.2c2.6 1.2 5.2-.8 7.8.2s4.6 1.4 7.4-.4"/>'
        '<path class="ln" d="M15.4 26.6l.4 3.2M19.6 27.2l.2 3M23.8 27.8l.2 3"/>'
        '<path class="dr" d="M21 36.9c.3 1.6.4 2.4 0 2.8-.5.4-1.3.1-1.2-.8 0-.7.5-1.2.7-2.1z"/>'
        '</svg>')

CAUSE_RE = re.compile(r"fabricat|falsif|image|paper mill|fake peer|peer review|compromised|randomly generated|computer-aided|plagiar|euphemism|duplicat|misconduct|error|unreliable|reproduc|contamina|results not|ethic|consent|irb|iacuc|authorship|author unaware|legal|copyright|third party|objections", re.I)
SUP_RE = re.compile(r"out of date|retract and replace", re.I)


def live_counts():
    """Zombie citations, articles and monthly readers, counted the way the page counts them."""
    try:
        d = json.load(open(os.path.join(ROOT, "data.json")))
        notes = json.load(open(os.path.join(ROOT, "outreach.json"))).get("notes", [])
    except (OSError, ValueError):
        return None
    dismissed = {n["key"] for n in notes if n.get("status") == "dismissed"}
    cites, pages = 0, {}
    for p in d.get("papers", []):
        rs = p.get("reasons") or []
        if p.get("superseded") or (not any(CAUSE_RE.search(r) for r in rs) and any(SUP_RE.search(r) for r in rs)):
            continue
        for w in p.get("wiki", []):
            if w.get("status") == "zombie" and f'{p["doi"]}|{w["page"]}' not in dismissed:
                cites += 1
                pages[w["page"]] = w.get("views") or 0
    return cites, len(pages), sum(pages.values())


def share_text():
    """Home-page link preview. The headline stays general; the live count is the proof."""
    title = "The study was retracted. The fact is still out there."
    c = live_counts()
    if not c or not c[0]:
        return (title, "Zombie Facts hunts down retracted, debunked and outdated facts that are still in circulation, "
                       "and tracks each one until it's fixed.")
    cites, arts, reads = c
    r = f"{reads // 10000 * 10000:,}" if reads >= 20000 else f"{reads // 1000 * 1000:,}"
    return (title, f"Zombie Facts hunts down retracted, debunked and outdated facts that are still in circulation. "
                   f"On Wikipedia alone: {cites} citations of retracted research with no warning, on pages read {r}+ times a month.")


def href(slug):
    return "/" + (slug + "/" if slug else "")


SHORT = {"Correction desk": "Desk", "Newsroom": "News", "Check a page": "Check"}


def navlabel(label):
    if label not in SHORT:
        return label
    return f'<span class="lg">{label}</span><span class="sm">{SHORT[label]}</span>'


def masthead(active):
    links = "".join(
        f'<a href="{href(s)}"{" aria-current=\"page\"" if s == active else ""}>{navlabel(label)}</a>'
        for s, label, *_ in PAGES)
    return f'''<header class="top">
    <a class="np" href="/" aria-label="Zombie Facts home">{MARK}<span>Zombie Facts</span></a>
    <span class="ed"><span>Vol. 1 · <b id="edDate">—</b></span><span>Retracted · Debunked · Out of date</span></span>
    <button class="iconbtn" id="theme" aria-label="Switch light or dark">{NAV_ICON}</button>
  </header>
  <nav class="nav" aria-label="Sections"><div>{links}</div></nav>'''


def nextlink(slug):
    for s, label, *_ in PAGES + EXTRA:
        if s == slug and slug:
            return f'<a class="nextpage" href="{href(s)}"><span>Next</span>{label} →</a>'
    return '<a class="nextpage" href="/"><span>Back to</span>The most-read zombies →</a>'


BUILT = "—"
FOOT_LINKS = [(s, l) for s, l, *_ in PAGES] + [(s, l) for s, l, *_ in EXTRA]


def shell(head, drawer, slug, active, title, desc, og_title, og_desc, body, nxt, image=None, extra_head=""):
    """One page: shared head with its own meta, masthead, body, footer, drawer and script."""
    url = SITE + (f"/{slug}" if slug else "/")
    h = head
    h = re.sub(r"<title>.*?</title>", lambda m: f"<title>{X.esc(title)}</title>", h)
    sub = lambda pat, val: (lambda hh: re.sub(pat, lambda m: m.group(1) + X.esc(val), hh))
    for pat, val in [(r'(<meta name="description" content=")[^"]*', desc), (r'(<meta property="og:url" content=")[^"]*', url),
                     (r'(<meta property="og:title" content=")[^"]*', og_title), (r'(<meta name="twitter:title" content=")[^"]*', og_title),
                     (r'(<meta property="og:description" content=")[^"]*', og_desc), (r'(<meta name="twitter:description" content=")[^"]*', og_desc)]:
        h = sub(pat, val)(h)
    if image:
        h = re.sub(r'(<meta (?:property="og:image"|name="twitter:image") content=")[^"]*', lambda m: m.group(1) + X.esc(image), h)
        h = h.replace('<meta property="og:image:alt" content="Zombie Facts: Retracted. Debunked. Out of date. Still out there.">',
                      f'<meta property="og:image:alt" content="{X.esc(og_title)}">')
    if slug.startswith("case/"):
        h = h.replace('<meta property="og:type" content="website">', '<meta property="og:type" content="article">')
    h = h.replace("</head>", "")
    if X.GOATCOUNTER:
        extra_head += f'<script data-goatcounter="https://{X.GOATCOUNTER}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>\n'
    return (h + f'<link rel="canonical" href="{url}">\n'
            '<link rel="alternate" type="application/atom+xml" title="Zombie Facts: new cases and fixes" href="/feed.xml">\n'
            '<link rel="apple-touch-icon" href="/assets/icon.png">\n'
            f'<link rel="stylesheet" href="/assets/site.css">\n{extra_head}</head>\n'
            f'<body data-page="{slug.split("/")[0] or "home"}">\n<div class="wrap">\n  {masthead(active)}\n\n{body}\n\n'
            f'  {nextlink(nxt) if nxt is not None else ""}\n'
            '  <footer>\n    <div><a class="np" href="/">' + MARK + f'<span>Zombie Facts</span></a><br><span id="built">{X.esc(BUILT)}</span></div>\n'
            '    <div class="fnav">' + "".join(f'<a href="{href(s)}">{l}</a>' for s, l in FOOT_LINKS) + '<a href="/feed.xml">Feed</a>'
            + (f'<a href="{X.esc(X.NEWSLETTER)}">By email</a>' if X.NEWSLETTER else "") + '</div>\n'
            '    <div style="max-width:60ch">Data: Retraction Watch database via Crossref (CC0), Wikipedia (CC BY-SA), Crossref REST API, fact-checkers\' ClaimReview data via Data Commons. '
            'Not affiliated with any of them. Built by <a href="/about/">Colin Robinson</a>. <a href="https://github.com/colinrobinson-labs/zombie-facts">Source code</a>.</div>\n  </footer>\n</div>\n\n'
            f'{drawer}<script src="/assets/app.js" defer></script>\n</body>\n</html>\n')


def build():
    head = open(os.path.join(SRC, "_head.html")).read()
    drawer = open(os.path.join(SRC, "_drawer.html")).read()
    M = X.model()
    global BUILT
    BUILT = "data rebuilt " + (M["D"].get("built") or "").replace("T", " ").replace("Z", " UTC") if M["D"].get("built") else "—"
    out, urls = {}, []
    lastmod = (M["D"].get("checked") or M["D"].get("built") or M["today"])[:10]
    for slug, label, title, desc, frags, nxt in PAGES + EXTRA:
        if desc == "@results":
            desc = X.results_desc(M)
        body = "\n".join(X.results_body(M) if f == "@results" else open(os.path.join(SRC, "pages", f + ".html")).read().rstrip() for f in frags)
        if X.TIPS_EMAIL:
            body = body.replace('<p class="rs-fine" id="tipMail" hidden></p>',
                                f'<p class="rs-fine" id="tipMail">No GitHub account? Email the same three things to <a href="mailto:{X.esc(X.TIPS_EMAIL)}">{X.esc(X.TIPS_EMAIL)}</a>.</p>')
        st, sd = share_text()
        page = shell(head, drawer, slug + "/" if slug else "", slug, title, sd if not slug else desc,
                     st if not slug else title, sd if not slug else desc, body, nxt)
        path = os.path.join(ROOT, slug, "index.html") if slug else os.path.join(ROOT, "index.html")
        out[path] = page
        urls.append((SITE + href(slug), lastmod if slug in ("", "register", "desk", "results", "news") else None))
        if not slug:  # 404 reuses the home shell with its own body, nothing marked current
            nf = page.replace(body, open(os.path.join(SRC, "pages", "_404.html")).read().rstrip())
            nf = nf.replace(' aria-current="page"', "").replace("<title>Zombie Facts</title>", "<title>Not found · Zombie Facts</title>")
            nf = nf.replace(f'<link rel="canonical" href="{SITE}/">\n', "").replace(nextlink(nxt), "")
            out[os.path.join(ROOT, "404.html")] = nf
    for c in M["cases"]:
        slug = f"case/{c['slug']}/"
        img = X.card_url(c) if X.card_exists(c) else None
        t = X.plain_title(c)
        page = shell(head, '<div class="toast" id="toast"></div>\n', slug, "desk", f"{t} · Zombie Facts", X.describe(c), t, X.describe(c),
                     X.case_body(c, M), None, image=img, extra_head=X.case_jsonld(c, M) + "\n")
        out[os.path.join(ROOT, "case", c["slug"], "index.html")] = page
        last = max([c["opened"]] + [x["c"].get("c") or "" for x in c["cites_on"]] + [((x["n"] or {}).get("posted") or "")[:10] for x in c["cites_on"]])
        urls.append((c["url"], last))
    out[os.path.join(ROOT, "case", "slugs.json")] = json.dumps(M["slugs"], indent=1, sort_keys=True) + "\n"
    out[os.path.join(ROOT, "case", "index.json")] = json.dumps(
        {c["doi"]: {"s": c["slug"], "st": c["st"]} for c in M["cases"]}, separators=(",", ":"), sort_keys=True) + "\n"
    out[os.path.join(ROOT, "feed.xml")] = X.feed(M)
    out[os.path.join(ROOT, "sitemap.xml")] = X.sitemap(urls)
    out[os.path.join(ROOT, "robots.txt")] = f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"
    return out


if __name__ == "__main__":
    pages = build()
    stale = [p for p, c in pages.items() if not os.path.exists(p) or open(p).read() != c]
    if "--check" in sys.argv:
        if stale:
            sys.exit("stale pages, run build/make_pages.py: " + ", ".join(os.path.relpath(p, ROOT) for p in stale))
        print("pages up to date")
    else:
        for p, c in pages.items():
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(c)
        print("wrote", len(pages), "pages")
