#!/usr/bin/env python3
"""Build the site's pages from src/.

Every page shares src/_head.html (meta, fonts), the masthead + nav below, the case
drawer (src/_drawer.html), /assets/site.css and /assets/app.js. Each page's body is
assembled from fragments in src/pages/. Run after editing anything in src/:

    python build/make_pages.py          # writes index.html, register/index.html, ...
    python build/make_pages.py --check  # exit 1 if the committed pages are stale (CI)
"""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC = os.path.join(ROOT, "src")
SITE = "https://zombiefacts.org"

PAGES = [  # slug, nav label, <title>, description, fragments, next slug
    ("", "Home", "Zombie Facts", "Retracted research that Wikipedia still cites as evidence, and the fight to fix it. Every retraction in the Retraction Watch database, checked against every DOI link on English Wikipedia.",
     ["_hero", "_worst", "_deskhome", "_explore"], "register"),
    ("register", "Register", "The register · Zombie Facts", "Search every retracted paper English Wikipedia still cites, with the exact sentences and the official retraction notices.",
     ["_register"], "desk"),
    ("desk", "Correction desk", "Correction desk · Zombie Facts", "Every zombie citation is a case: reviewed by hand, reported to Wikipedia editors, and tracked until it is fixed.",
     ["_desk"], "autopsy"),
    ("autopsy", "Autopsy", "Autopsy · Zombie Facts", "Why the papers Wikipedia still cites were retracted, and when.",
     ["_autopsy"], "check"),
    ("check", "Check a page", "Check a page · Zombie Facts", "Scan any Wikipedia article for retracted sources, live in your browser.",
     ["_check"], "method"),
    ("method", "Method", "How it works · Zombie Facts", "How Zombie Facts finds retracted research on Wikipedia, how cases are reviewed, and how corrections are tracked.",
     ["_method"], ""),
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
    c = live_counts()
    if not c or not c[0]:
        return ("Zombie Facts: Wikipedia still cites research that was retracted",
                "The study was retracted. The fact kept walking. We check every retraction on record against every source on English Wikipedia, and track each one until it's fixed.")
    cites, arts, reads = c
    r = f"{reads // 10000 * 10000:,}" if reads >= 20000 else f"{reads // 1000 * 1000:,}"
    return (f"Wikipedia still cites retracted research {cites} times, on pages read {r}+ times a month.",
            f"The study was retracted. The fact kept walking. Zombie Facts checks every retraction on record against every source on English Wikipedia, finds {cites} still cited with no warning across {arts} articles, and tracks each one until it's fixed.")


def href(slug):
    return "/" + (slug + "/" if slug else "")


def masthead(active):
    links = "".join(
        f'<a href="{href(s)}"{" aria-current=\"page\"" if s == active else ""}>{label}</a>'
        for s, label, *_ in PAGES)
    return f'''<header class="top">
    <a class="np" href="/" aria-label="Zombie Facts home">{MARK}<span>Zombie Facts</span></a>
    <span class="ed"><span>Vol. 1 · <b id="edDate">—</b></span><span>Retraction Watch × English Wikipedia</span></span>
    <button class="iconbtn" id="theme" aria-label="Switch light or dark">{NAV_ICON}</button>
  </header>
  <nav class="nav" aria-label="Sections"><div>{links}</div></nav>'''


def nextlink(slug):
    for s, label, *_ in PAGES:
        if s == slug and slug:
            return f'<a class="nextpage" href="{href(s)}"><span>Next</span>{label} →</a>'
    return '<a class="nextpage" href="/"><span>Back to</span>The most-read zombies →</a>'


def build():
    head = open(os.path.join(SRC, "_head.html")).read()
    drawer = open(os.path.join(SRC, "_drawer.html")).read()
    out = {}
    for slug, label, title, desc, frags, nxt in PAGES:
        url = SITE + href(slug)
        h = head
        h = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", h)
        h = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + (share_text()[1] if not slug else desc), h)
        h = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + url, h)
        st, sd = share_text()
        h = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + (st if not slug else title), h)
        h = re.sub(r'(<meta name="twitter:title" content=")[^"]*', lambda m: m.group(1) + (st if not slug else title), h)
        h = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + (sd if not slug else desc), h)
        h = re.sub(r'(<meta name="twitter:description" content=")[^"]*', lambda m: m.group(1) + (sd if not slug else desc), h)
        h = h.replace("</head>", "")
        body = "\n".join(open(os.path.join(SRC, "pages", f + ".html")).read().rstrip() for f in frags)
        page = (h + f'<link rel="canonical" href="{url}">\n<link rel="stylesheet" href="/assets/site.css">\n</head>\n'
                f'<body data-page="{slug or "home"}">\n<div class="wrap">\n  {masthead(slug)}\n\n{body}\n\n'
                f'  {nextlink(nxt)}\n'
                '  <footer>\n    <div><a class="np" href="/">' + MARK + '<span>Zombie Facts</span></a><br><span id="built">—</span></div>\n'
                '    <div class="fnav">' + "".join(f'<a href="{href(s)}">{l}</a>' for s, l, *_ in PAGES) + '</div>\n'
                '    <div style="max-width:60ch">Data: Retraction Watch database via Crossref (CC0), Wikipedia (CC BY-SA), Crossref REST API. '
                'Not affiliated with any of them. Built by Colin Robinson. <a href="https://github.com/colinrobinson-labs/zombie-facts">Source code</a>.</div>\n  </footer>\n</div>\n\n'
                f'{drawer}<script src="/assets/app.js" defer></script>\n</body>\n</html>\n')
        path = os.path.join(ROOT, slug, "index.html") if slug else os.path.join(ROOT, "index.html")
        out[path] = page
        if not slug:  # 404 reuses the home shell with its own body, nothing marked current
            nf = page.replace(body, open(os.path.join(SRC, "pages", "_404.html")).read().rstrip())
            nf = nf.replace(' aria-current="page"', "").replace("<title>Zombie Facts</title>", "<title>Not found · Zombie Facts</title>")
            nf = nf.replace(f'<link rel="canonical" href="{url}">\n', "").replace(nextlink(nxt), "")
            out[os.path.join(ROOT, "404.html")] = nf
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
