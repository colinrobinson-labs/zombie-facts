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
VERSION = "1"  # bump to redraw every card after a design change

from make_pages import MARK  # noqa: E402  the same zombie-head svg the site uses

CSS = """*{box-sizing:border-box}html,body{margin:0}
body{width:1200px;height:630px;overflow:hidden;background:#ece7da;color:#141412;position:relative;padding:44px 60px 0}
.top{display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #141412;padding-bottom:14px}
.np{display:flex;align-items:center;gap:12px;font:400 34px/1 Anton;text-transform:uppercase;letter-spacing:.02em}
.np svg{width:48px;height:48px;overflow:visible}
.mark .hd{fill:#c6f432;stroke:#141412;stroke-width:2;stroke-linejoin:round}.mark .ln{fill:none;stroke:#141412;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.mark .wh{fill:#f6f2e8;stroke:#141412;stroke-width:2}.mark .pu{fill:#141412}.mark .dr{fill:#c6f432;stroke:#141412;stroke-width:1.2}
.tg{font:600 17px 'IBM Plex Mono';letter-spacing:.1em;text-transform:uppercase;color:#b42318}
.ok .tg{color:#3c6b00}
.kick{margin:26px 0 0;font:600 17px 'IBM Plex Mono';letter-spacing:.1em;text-transform:uppercase;color:#6c675b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kick b{color:#141412}
#q{margin:14px 0 0;height:300px;display:flex;align-items:center}
#q p{margin:0;font:italic 400 56px/1.28 Newsreader;max-width:1080px}
#q mark{background:#c6f432;color:#141412;padding:0 .08em;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.ok #q mark{background:none;text-decoration:line-through;text-decoration-color:#b42318;text-decoration-thickness:4px}
#q h1{margin:0;font:400 76px/1.04 Anton;text-transform:uppercase;max-width:1080px}
#q h1 mark{background:#c6f432;color:#141412;padding:0 .06em}
.src{position:absolute;left:60px;right:60px;bottom:0;height:150px;border-top:2px dashed #141412;padding-top:18px;display:flex;justify-content:space-between;gap:30px}
.src .t{font:500 26px/1.25 Newsreader;max-height:66px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.src .m{margin-top:8px;font:600 16px 'IBM Plex Mono';letter-spacing:.06em;text-transform:uppercase;color:#b42318}
.src .u{flex:none;align-self:flex-start;font:600 16px 'IBM Plex Mono';letter-spacing:.06em;color:#141412;background:#c6f432;padding:8px 12px}
.stamp{position:absolute;right:70px;top:140px;transform:rotate(-8deg);border:5px solid #3c6b00;color:#3c6b00;font:400 54px/1 Anton;text-transform:uppercase;padding:10px 18px 6px;background:#ece7dacc}
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
            '<link href="https://fonts.googleapis.com/css2?family=Anton&family=Newsreader:ital,opsz,wght@0,6..72,500;1,6..72,400'
            '&family=IBM+Plex+Mono:wght@600&display=block" rel="stylesheet">'
            f'<style>{CSS}</style></head><body class="{"ok" if ok else ""}">'
            f'<div class="top"><div class="np">{MARK}<span>Zombie Facts</span></div><div class="tg">{e(tag)}</div></div>'
            f'<div class="kick">{kick}</div><div id="q">{body}</div>{stamp}'
            f'<div class="src"><div><div class="t">{e(i["title"])}</div><div class="m">{e(meta[:90])}</div></div>'
            f'<div class="u">zombiefacts.org</div></div>{FIT}</body></html>')


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
    with open(os.path.join(ROOT, "case", "cards.json"), "w") as f:
        json.dump(dict(sorted(manifest.items())), f, indent=1)
        f.write("\n")
    print(f"cards: drew {drawn}, {len(manifest)} on file")


if __name__ == "__main__":
    main()
