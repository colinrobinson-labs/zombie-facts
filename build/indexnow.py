#!/usr/bin/env python3
"""Tell search engines (Bing, Yandex, Seznam, Naver via IndexNow) which pages changed.

Runs after each deploy. Sends the sitemap URLs whose lastmod is today or yesterday in
one request; with --all, every URL (use once, after a big change). The key is public by
design: it is the file /ee8da208609e1901be467ab8288cbf94.txt on the site, which proves we own the domain.
"""
import json, re, sys, urllib.request
from datetime import date, timedelta

HOST = "zombiefacts.org"
KEY = "ee8da208609e1901be467ab8288cbf94"


def main():
    xml = open("sitemap.xml").read()
    rows = re.findall(r"<loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?", xml)
    since = (date.today() - timedelta(days=1)).isoformat()
    urls = [u for u, m in rows if "--all" in sys.argv or (m and m >= since)][:1000]
    if not urls:
        print("indexnow: nothing changed")
        return
    body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8",
                                          "User-Agent": "ZombieFacts/1.1 (https://zombiefacts.org/; tips@zombiefacts.org)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("indexnow:", r.status, len(urls), "urls")
    except Exception as e:  # never fail a deploy over this
        print("indexnow: failed", e)


if __name__ == "__main__":
    main()
