#!/usr/bin/env python3
"""One-off: check which free news/fact-check sources answer from GitHub Actions."""
import urllib.request, time, json
UA = "ZombieFacts/1.0 (https://zombiefacts.org/; retraction tracker)"
URLS = [
 "https://api.eventdata.crossref.org/v1/events?mailto=zombiefacts@users.noreply.github.com&obj-id=10.1016/S0140-6736(97)11096-0&rows=5",
 "https://api.eventdata.crossref.org/v1/events?mailto=zombiefacts@users.noreply.github.com&source=newsfeed&rows=2",
 "https://api.altmetric.com/v1/doi/10.1016/S0140-6736(97)11096-0",
 "https://api.gdeltproject.org/api/v2/doc/doc?query=%22retracted%20study%22&mode=artlist&format=json&maxrecords=3",
 "https://api.openalex.org/works/doi:10.1016/S0140-6736(97)11096-0?mailto=zombiefacts@users.noreply.github.com",
 "https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json",
 "https://www.datacommons.org/factcheck/download",
 "https://news.google.com/rss/search?q=%22retracted%22+study&hl=en-US&gl=US&ceid=US:en",
]
for u in URLS:
    t = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60)
        b = r.read(400000)
        print("PROBE", r.status, round(time.time()-t,1), u, "|", r.headers.get("Content-Type"), "|", b[:600].decode("utf8","replace").replace("\n"," "))
    except Exception as e:
        print("PROBE FAIL", u, getattr(e, "code", ""), str(e)[:200], (getattr(e,"read",lambda:b"")()[:300]).decode("utf8","replace"))
    time.sleep(2)
