#!/usr/bin/env python3
"""Build the site's pages from src/.

Every page shares src/_head.html (meta, fonts), the masthead + nav below, the case
drawer (src/_drawer.html), /assets/site.css and /assets/app.js. Each page's body is
assembled from fragments in src/pages/. Run after editing anything in src/:

    python build/make_pages.py          # writes index.html, register/index.html, ...
    python build/make_pages.py --check  # exit 1 if the committed pages are stale (CI)
"""
import os, re, sys

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


def href(slug):
    return "/" + (slug + "/" if slug else "")


def masthead(active):
    links = "".join(
        f'<a href="{href(s)}"{" aria-current=\"page\"" if s == active else ""}>{label}</a>'
        for s, label, *_ in PAGES)
    return f'''<header class="top">
    <a class="np" href="/">Zombie Facts</a>
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
        h = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + desc, h)
        h = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + url, h)
        if slug:
            h = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + title, h)
            h = re.sub(r'(<meta name="twitter:title" content=")[^"]*', lambda m: m.group(1) + title, h)
        h = h.replace("</head>", "")
        body = "\n".join(open(os.path.join(SRC, "pages", f + ".html")).read().rstrip() for f in frags)
        page = (h + f'<link rel="canonical" href="{url}">\n<link rel="stylesheet" href="/assets/site.css">\n</head>\n'
                f'<body data-page="{slug or "home"}">\n<div class="wrap">\n  {masthead(slug)}\n\n{body}\n\n'
                f'  {nextlink(nxt)}\n'
                '  <footer>\n    <div><a class="np" href="/">Zombie Facts</a><br><span id="built">—</span></div>\n'
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
