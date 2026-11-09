#!/usr/bin/env python3
"""Daily check that the live site works. Prints one line per check; exits 1 if any fail.

Checks: pages load over HTTPS, data is fresh, the feed and sitemap parse, a case page
loads, www redirects, and the certificate has more than 14 days left.
"""
import json, socket, ssl, sys, urllib.request
from datetime import datetime, timezone
from xml.etree import ElementTree

SITE = "https://zombiefacts.org"
UA = {"User-Agent": "ZombieFacts-health/1.0 (https://zombiefacts.org/; tips@zombiefacts.org)"}
fails = []


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.status, r.geturl(), r.read()


def check(name, fn):
    try:
        msg = fn()
        print(f"ok    {name}{': ' + msg if msg else ''}")
    except Exception as e:
        print(f"FAIL  {name}: {e}")
        fails.append(f"{name}: {e}")


def pages():
    for p in ["/", "/register/", "/desk/", "/news/", "/results/", "/check/", "/method/", "/about/", "/report/", "/data/"]:
        s, _, b = get(SITE + p)
        assert s == 200 and b"Zombie Facts" in b, f"{p} returned {s}"
    return "10 pages"


def fresh():
    _, _, b = get(SITE + "/data.json")
    d = json.loads(b)
    t = datetime.fromisoformat((d.get("checked") or d["built"]).replace("Z", "+00:00"))
    h = (datetime.now(timezone.utc) - t).total_seconds() / 3600
    assert h < 50, f"data last checked {h:.0f} hours ago"
    assert d.get("papers"), "no papers in data.json"
    return f"checked {h:.0f} h ago, {len(d['papers'])} papers"


def feed_and_sitemap():
    _, _, f = get(SITE + "/feed.xml")
    ElementTree.fromstring(f)
    _, _, s = get(SITE + "/sitemap.xml")
    locs = [e.text for e in ElementTree.fromstring(s).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    case = next(u for u in locs if "/case/" in u)
    st, _, b = get(case)
    assert st == 200 and b"Case file" in b, f"{case} returned {st}"
    return f"{len(locs)} urls"


def www():
    _, final, _ = get("https://www.zombiefacts.org/")
    assert final.startswith(SITE), f"www ends at {final}"


def cert():
    ctx = ssl.create_default_context()
    with socket.create_connection(("zombiefacts.org", 443), timeout=20) as s, ctx.wrap_socket(s, server_hostname="zombiefacts.org") as t:
        end = datetime.strptime(t.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    days = (end - datetime.now(timezone.utc)).days
    assert days > 14, f"certificate expires in {days} days"
    return f"{days} days left"


if __name__ == "__main__":
    for n, f in [("pages load", pages), ("data is fresh", fresh), ("feed, sitemap and a case page", feed_and_sitemap),
                 ("www redirects", www), ("certificate", cert)]:
        check(n, f)
    if fails:
        open("health.txt", "w").write("\n".join(f"- {x}" for x in fails))
        sys.exit(1)
