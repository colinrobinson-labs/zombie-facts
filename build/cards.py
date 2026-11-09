#!/usr/bin/env python3
"""Draw the 1200x630 share image for every case page (case/<slug>/card.png).

A card is redrawn only when what it shows changes (case/cards.json keeps a hash per
slug), so the daily run usually draws nothing. Needs a Chrome or Chromium binary
(GitHub's ubuntu runners have google-chrome); without one it says so and exits 0, and
the case pages fall back to the site-wide og.png. Run it before make_pages.py.

    python build/cards.py            # draw new or changed cards
    python build/cards.py --all      # redraw every card
    python build/cards.py --only SLUG
"""
import hashlib, html, json, os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
import site_extras as X  # noqa: E402

ROOT = X.ROOT
VERSION = "2"  # bump to redraw every card after a design change

from make_pages import MARK  # noqa: E402  the same zombie-head svg the site uses

CSS = """*{box-sizing:border-box}html,body{margin:0}
body{width:1200px;height:630px;overflow:hidden;background:#f2f0e9;color:#17181a;position:relative;padding:42px 60px 0}
.top{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #17181a;padding-bottom:14px}
.np{display:flex;align-items:center;gap:12px;font:850 34px/1 Archivo;font-stretch:62%;text-transform:uppercase;letter-spacing:.01em}
.np svg{width:48px;height:48px;overflow:visible}
.mark .hd{fill:#c8f031;stroke:#17181a;stroke-width:2;stroke-linejoin:round}.mark .ln{fill:none;stroke:#17181a;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.mark .wh{fill:#fbfaf6;stroke:#17181a;stroke-width:2}.mark .pu{fill:#17181a}.mark .dr{fill:#c8f031;stroke:#17181a;stroke-width:1.2}
.tg{color:#b3261e;border:3px solid currentColor;padding:7px 12px 6px;font:700 16px 'IBM Plex Mono';letter-spacing:.12em;text-transform:uppercase;transform:rotate(-3deg)}
.ok .tg{color:#17181a}
.kick{margin:24px 0 0;font:600 17px 'IBM Plex Mono';letter-spacing:.06em;text-transform:uppercase;color:#625f57;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kick b{color:#17181a}
#q{margin:12px 0 0;height:300px;display:flex;align-items:center}
#q p{margin:0;font:italic 400 54px/1.3 'Source Serif 4';max-width:1080px}
#q mark{background:linear-gradient(transparent 62%,#c8f031 62% 94%,transparent 94%);color:#17181a;padding:0 .04em;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.ok #q mark{background:none;text-decoration:line-through;text-decoration-color:#b3261e;text-decoration-thickness:4px}
#q h1{margin:0;font:850 88px/.95 Archivo;font-stretch:62%;max-width:1080px}
#q h1 mark{background:linear-gradient(transparent 60%,#c8f031 60% 95%,transparent 95%);color:#17181a}
.src{position:absolute;left:60px;right:60px;bottom:0;height:150px;border-top:2px solid #17181a;padding-top:18px;display:flex;justify-content:space-between;gap:30px}
.src .t{font:600 26px/1.25 'Source Serif 4';max-height:66px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.src .m{margin-top:8px;font:600 16px 'IBM Plex Mono';letter-spacing:.06em;text-transform:uppercase;color:#b3261e}
.src .u{flex:none;align-self:flex-start;font:600 18px 'IBM Plex Mono';color:#17181a;background:#c8f031;padding:7px 11px}
.stamp{position:absolute;right:70px;top:150px;transform:rotate(-6deg);border:4px solid #17181a;color:#17181a;font:850 50px/1 Archivo;font-stretch:62%;text-transform:uppercase;padding:10px 18px 8px;background:#fbfaf6}
"""

FIT = """<script>document.fonts.ready.then(()=>{const b=document.getElementById('q'),e=b.firstElementChild;
let s=parseFloat(getComputedStyle(e).fontSize);while(e.scrollHeight>b.clientHeight&&s>26){s-=2;e.style.fontSize=s+'px'}
document.body.dataset.done=1})</script>"""


def card_html(c):
    i = X.card_input(c)
    e = html.escape
    ok = i["st"] == "fixed"
    tag = {"open": "Source retracted " + i["retracted"], "fixed": "Fixed", "ok": "Reviewed"}[i["st"]]
    if i["quote"]:
        body = f'<p>“<mark>{e(i["quote"])}</mark>”</p>'
    else:
        body = f'<h1>Wikipedia still cites a <mark>retracted paper</mark> on “{e(i["page"])}”</h1>'
    stamp = (f'<div class="stamp">Fixed in {i["fixdays"]} day{"s" if i["fixdays"] != 1 else ""}</div>' if ok else "")
    kick = ("Was on Wikipedia · " if ok else "Still on Wikipedia · ") + f'<b>{e(i["page"])}</b>'
    meta = " · ".join(x for x in [f'Retracted {i["retracted"]}', i["journal"]] if x)
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            '<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..100,500..900&family=Source+Serif+4:ital,opsz,wght@0,8..60,600;1,8..60,400'
            '&family=IBM+Plex+Mono:wght@600;700&display=block" rel="stylesheet">'
            f'<style>{CSS}</style></head><body class="{"ok" if ok else ""}">'
            f'<div class="top"><div class="np">{MARK}<span>Zombie Facts</span></div><div class="tg">{e(tag)}</div></div>'
            f'<div class="kick">{kick}</div><div id="q">{body}</div>{stamp}'
            f'<div class="src"><div><div class="t">{e(i["title"])}</div><div class="m">{e(meta[:90])}</div></div>'
            f'<div class="u">zombiefacts.org</div></div>{FIT}</body></html>')


def section_inputs(M):
    """Share images for the section pages: a live number in the headline. slug -> (kicker, headline html, foot)."""
    from make_pages import live_counts
    c = live_counts() or (0, 0, 0)
    R = X.results_numbers(M)
    unread = ((M["news"] or {}).get("stats") or {}).get("unreviewed") or 0
    out = {
        "register": ("The register", f"<mark>{c[0]:,}</mark> citations of retracted research on Wikipedia, with no warning",
                     f"On {c[1]:,} articles read {X.fmt_k(c[2])} times a month · searchable by topic, journal and cause"),
        "desk": ("Correction desk", f"Every zombie citation is a case: <mark>{len(R['open']):,} open</mark>, tracked until fixed",
                 "Read by hand, reported to the people who can fix it, logged when it's done"),
        "news": ("Newsroom", "Retracted research, <mark>still in the news</mark>",
                 (f"{unread:,} stories being read by hand · " if unread else "") + "what happens when we ask outlets to fix them"),
        "results": ("Results", (f"<mark>{len(R['fixed']):,} fixed</mark> of {len(R['cites']):,} zombie citations found" if R["fixed"] else
                                f"<mark>{len(R['cites']):,}</mark> zombie citations found. The fixes start here"),
                    "Fix rates, days to fix, and whether telling editors makes a difference"),
        "check": ("Check a page", "Scan any Wikipedia article for <mark>retracted sources</mark>", "Live in your browser, in a few seconds"),
        "autopsy": ("Autopsy", "Why the papers Wikipedia still cites <mark>were retracted</mark>", "Fabricated data, manipulated images, paper mills and more"),
    }
    return out


def section_html(kick, head, foot):
    e = html.escape
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            '<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..100,500..900&family=Source+Serif+4:ital,opsz,wght@0,8..60,600;1,8..60,400'
            '&family=IBM+Plex+Mono:wght@600;700&display=block" rel="stylesheet">'
            f'<style>{CSS}</style></head><body>'
            f'<div class="top"><div class="np">{MARK}<span>Zombie Facts</span></div><div class="tg">{e(kick)}</div></div>'
            f'<div id="q"><h1>{head}</h1></div>'
            f'<div class="src"><div><div class="t">{e(foot)}</div></div><div class="u">zombiefacts.org</div></div>{FIT}</body></html>')


def section_path(slug):
    return os.path.join(ROOT, "share", slug + ".png")


def chrome():
    for b in [os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "/opt/pw-browsers/chromium"]:
        if b and shutil.which(b):
            return shutil.which(b)
    return None


def shoot(binary, src, out):
    subprocess.run([binary, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--window-size=1200,630", "--virtual-time-budget=15000", "--run-all-compositor-stages-before-draw",
                    f"--screenshot={out}", "file://" + src], check=True, capture_output=True, timeout=90)


def main():
    M = X.model()
    manifest = X.load_cards()
    binary = chrome()
    if not binary:
        print("cards: no Chrome found, skipping (case pages use og.png)")
        return
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    drawn = 0
    with tempfile.TemporaryDirectory() as tmp:
        for c in M["cases"]:
            if only and c["slug"] != only:
                continue
            h = hashlib.sha1((VERSION + json.dumps(X.card_input(c), sort_keys=True)).encode()).hexdigest()
            out = X.card_path(c)
            if manifest.get(c["slug"]) == h and os.path.exists(out) and "--all" not in sys.argv and not only:
                continue
            src = os.path.join(tmp, "card.html")
            open(src, "w").write(card_html(c))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            try:
                shoot(binary, src, out)
            except (subprocess.SubprocessError, OSError) as ex:
                print("cards: failed", c["slug"], ex)
                continue
            manifest[c["slug"]] = h
            drawn += 1
        for slug, (kick, head, foot) in section_inputs(M).items():
            h = hashlib.sha1((VERSION + kick + head + foot).encode()).hexdigest()
            out = section_path(slug)
            key = "_section/" + slug
            if manifest.get(key) == h and os.path.exists(out) and "--all" not in sys.argv:
                continue
            src = os.path.join(tmp, "card.html")
            open(src, "w").write(section_html(kick, head, foot))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            try:
                shoot(binary, src, out)
            except (subprocess.SubprocessError, OSError) as ex:
                print("cards: failed", slug, ex)
                continue
            manifest[key] = h
            drawn += 1
    with open(os.path.join(ROOT, "case", "cards.json"), "w") as f:
        json.dump(dict(sorted(manifest.items())), f, indent=1)
        f.write("\n")
    print(f"cards: drew {drawn}, {len(manifest)} on file")


if __name__ == "__main__":
    main()
