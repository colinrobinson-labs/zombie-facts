#!/usr/bin/env python3
"""One-off: GDELT pacing + ClaimReview feed size from Actions."""
import urllib.request, urllib.parse, time, json, sys
UA = "ZombieFacts/1.0 (https://zombiefacts.org/; retraction tracker)"
def go(u, n=600):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40)
        b = r.read(n); print("PROBE", r.status, u[:140], "|", r.headers.get("Content-Length"), "|", b.decode("utf8","replace").replace("\n"," ")[:n], flush=True)
    except Exception as e:
        print("PROBE FAIL", u[:140], getattr(e, "code", ""), str(e)[:150], flush=True)
r = urllib.request.urlopen(urllib.request.Request("https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json", method="HEAD", headers={"User-Agent": UA}), timeout=40)
print("CLAIMREVIEW size", r.headers.get("Content-Length"), r.headers.get("Last-Modified"), flush=True)
go("https://api.gdeltproject.org/robots.txt", 400)
for q in ['"Ileal-lymphoid-nodular hyperplasia"', '"retracted" "study" sourcelang:english', '"Hydroxychloroquine and azithromycin as a treatment of COVID-19"']:
    time.sleep(8)
    go("https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode({"query": q, "mode": "artlist", "format": "json", "maxrecords": 5, "timespan": "3months"}), 1500)
