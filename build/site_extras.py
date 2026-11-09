"""Generated pages that come from the data: one page per case, the Results scoreboard,
the Atom feed and the sitemap. Called by make_pages.py; nothing here fetches anything.

A case page lives at /case/<slug>/ for every retracted paper we have ever opened a case
on. Slugs are kept in case/slugs.json and never reassigned, so a link shared once keeps
working after the case is fixed.
"""
import html, json, os, re, statistics, unicodedata
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE = "https://zombiefacts.org"

# Switches the owner can turn on once an account exists (all free). Empty means off.
GOATCOUNTER = "zombiefacts"  # e.g. "zombiefacts" for https://zombiefacts.goatcounter.com
NEWSLETTER = ""       # sign-up page of a free newsletter service, shown next to the feed
TIPS_EMAIL = "tips@zombiefacts.org"  # e.g. "tips@zombiefacts.org" (Porkbun email forwarding is free)

esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)

CAUSES = [
    ("Fabricated data", r"fabricat|falsif"), ("Manipulated images", r"image"),
    ("Paper mill or fake review", r"paper mill|fake peer|peer review|compromised|randomly generated|computer-aided"),
    ("Plagiarism", r"plagiar|euphemism"), ("Duplicate publication", r"duplicat"), ("Misconduct finding", r"misconduct"),
    ("Error or not reproducible", r"error|unreliable|reproduc|contamina|results not"),
    ("Ethics or consent", r"ethic|consent|irb|iacuc"),
    ("Authorship or legal", r"authorship|author unaware|legal|copyright|third party|objections")]
SUP = re.compile(r"out of date|retract and replace", re.I)
SUP_REPLACE = re.compile(r"retract and replace", re.I)


def causes_of(p):
    found = set()
    for r in p.get("reasons") or []:
        for name, rx in CAUSES:
            if re.search(rx, r, re.I):
                found.add(name)
                break
    out = [n for n, _ in CAUSES if n in found]
    if not out:
        out.append("Superseded by a newer version" if any(SUP.search(r) for r in p.get("reasons") or []) else "Reason not stated")
    return out


def superseded(p):
    return bool(p.get("superseded")) or (not any(n for n, _ in CAUSES if n in causes_of(p))
                                         and any(SUP.search(r) for r in p.get("reasons") or []))


def clean_title(t):
    return re.sub(r"\s+", " ", re.sub(r"^(RETRACTED( ARTICLE)?|WITHDRAWN|Retracted)\s*:\s*", "", t or "", flags=re.I)).strip()


LISTSEC = re.compile(r"^(references|further reading|bibliography|sources|notes|external links|citations|works cited|literature)", re.I)


def said(w, mx=260):
    """The sentence a citation supports, cleaned the same way assets/app.js cleans it."""
    if not w or LISTSEC.match(w.get("section") or "") or re.match(r"^\d{4} in ", w.get("page") or ""):
        return ""
    s = w.get("said") or ""
    s = re.sub(r"^.*\}\}\s*", "", s)
    s = re.sub(r"\{\{.*$", "", s)
    s = re.sub(r'^[\s|\]\[}"]+', "", s)
    s = re.sub(r"^[\s*#:;]+", "", s).strip()
    if re.search(r"https?:|\[|\]", re.sub(r"\[[^\[\]|]{1,40}\]", "", s)) or len(s.split()) < 8:
        return ""
    if re.search(r"\|\s*[\w-]+\s*=|^\W*title\s*=", s):
        return ""
    if len(s) < 25 or re.match(r"^[\W\d]+$", s) or re.match(r"^(doi|isbn|pmid)\b", s, re.I):
        return ""
    if len(s) > mx:
        s = "…" + re.sub(r"^\S*\s", "", s[-mx:])
    return s


# Home page lead quote. An editor's pick wins while it is an open case with a whole sentence;
# otherwise the most-read open zombie whose quote is a whole sentence.
PICK = {"doi": "10.1002/14651858.cd002766.pub3", "page": "List of pseudoscience topics"}


def whole(s):
    """A full sentence: starts with a capital (or a quote mark), ends with a stop, not cut off."""
    return bool(s) and not s.startswith("…") and bool(re.match(r'^["“‘(\[]?[A-Z0-9]', s)) and bool(re.search(r'[.!?]["”’)]?$', s))


def lead_quote(D, notes, mx=240):
    """(paper, citation, is_pick) for the home page, or None."""
    gone = {n["key"] for n in notes if n.get("status") == "dismissed" or n.get("hold")}
    def ok(p, w):
        q = said(w, 10000)
        return (w.get("status") == "zombie" and f'{p["doi"]}|{w["page"]}' not in gone and whole(q) and len(q) <= mx)
    papers = [p for p in D.get("papers", []) if not superseded(p)]
    for p in papers:
        if p["doi"] == PICK["doi"]:
            w = next((w for w in p.get("wiki", []) if w["page"] == PICK["page"]), None)
            if w and ok(p, w):
                return p, w, True
    best = None
    for p in papers:
        for w in p.get("wiki", []):
            if ok(p, w) and (best is None or (w.get("views") or 0) > (best[1].get("views") or 0)):
                best = (p, w, False)
    return best


def d(s):
    return date.fromisoformat(s[:10]) if s else None


def nice(s, year=True):
    x = d(s)
    if not x:
        return ""
    return f"{x:%b} {x.day}, {x.year}" if year else f"{x:%b} {x.day}"


def month(s):
    x = d(s)
    return f"{x:%B %Y}" if x else ""


def days(a, b):
    return max(0, (d(b) - d(a)).days)


def wurl(page, sec=None):
    from urllib.parse import quote
    u = "https://en.wikipedia.org/wiki/" + quote(page.replace(" ", "_"), safe="")
    if sec and sec != "Lead":
        u += "#" + quote(sec.replace(" ", "_"), safe="")
    return u


def slugify(t, words=8, maxlen=64):
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if unicodedata.category(ch) != "Mn").lower()
    out = []
    for x in re.findall(r"[a-z0-9]+", t)[:words]:
        if out and len("-".join(out + [x])) > maxlen:
            break
        out.append(x[:maxlen])
    return "-".join(out) or "case"


def fmt_k(n):
    n = n or 0
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e4:
        return f"{round(n / 1e3)}K"
    return f"{n:,}"


# ───────────────────────── the model ─────────────────────────

def load():
    def j(name, default):
        try:
            return json.load(open(os.path.join(ROOT, name)))
        except (OSError, ValueError):
            return default
    return j("data.json", {}), j("outreach.json", {}).get("notes", []), j("news.json", {}), j("case/slugs.json", {})


TOLD = ("posted", "replied")


def model():
    """Every case, grouped by paper, with what happened to each citation."""
    D, notes, news, slugs = load()
    papers = {p["doi"]: p for p in D.get("papers", [])}
    note = {n["key"]: n for n in notes}
    ledger = (D.get("ledger") or {}).get("cases", {})
    today = (D.get("checked") or D.get("built") or date.today().isoformat())[:10]
    by = {}
    for k, c in ledger.items():
        doi, page = k.split("|", 1)
        p = papers.get(doi)
        if p and superseded(p) and doi not in slugs:
            continue  # never shown as a case; one that already had a page keeps it, marked reviewed
        if c.get("how") == "author" or (c.get("how") == "subject" and doi not in slugs):
            continue
        n = note.get(k)
        if c.get("how") == "subject":
            st = "ok"
            n = n or {"status": "dismissed", "auto": True, "reviewed": (c.get("c") or "")[:10] or "2026-11-09",
                      "verdict": "The Wikipedia article is about the retraction itself, so it lists the paper on purpose. Not a zombie."}
        elif p and superseded(p):
            st = "ok"
            n = n or {"status": "dismissed", "auto": True, "reviewed": "2026-11-09",  # the day this rule shipped
                      "verdict": ("The publisher retracted this paper and republished a corrected version, so it is out of date rather than discredited. Citing the newer version is the fix."
                                  if any(SUP_REPLACE.search(r) for r in p.get("reasons") or []) else
                                  "Withdrawn because a newer version replaced it, not because it was discredited.")}
        elif n and n.get("status") == "dismissed":
            st = "ok"
        elif c.get("c"):
            st = "fixed"
        else:
            st = "open"
        w = next((w for w in (p or {}).get("wiki", []) if w["page"] == page), None)
        by.setdefault(doi, []).append({"key": k, "page": page, "c": c, "n": n, "st": st, "w": w,
                                      "told": bool(n and n.get("status") in TOLD) or bool(n and n.get("posted")),
                                      "ours": bool(n and n.get("edited"))})
    cases = []
    for doi, cs in by.items():
        p = papers.get(doi) or {}
        c0 = cs[0]["c"]
        cs.sort(key=lambda x: ({"open": 0, "fixed": 1, "ok": 2}[x["st"]], -(x["c"].get("v") or 0)))
        st = "open" if any(x["st"] == "open" for x in cs) else "fixed" if any(x["st"] == "fixed" for x in cs) else "ok"
        lead = cs[0]
        quote_w = next((x["w"] for x in cs if x["st"] == lead["st"] and x["w"] and said(x["w"])), None)
        cases.append({
            "doi": doi, "title": clean_title(p.get("title") or c0.get("t")), "journal": p.get("journal"),
            "publisher": p.get("publisher"), "authors": p.get("authors") or [], "published": p.get("published"),
            "retracted": p.get("retracted") or c0.get("r"), "notice": p.get("notice"), "reasons": p.get("reasons") or [],
            "causes": causes_of(p) if p else [], "cites": p.get("cites"), "st": st, "cites_on": cs, "lead": lead,
            "quote": said(quote_w, 420) if quote_w else "", "quote_w": quote_w,
            "flagged": [w for w in p.get("wiki", []) if w.get("status") == "flagged"],
            "opened": min(x["c"]["o"] for x in cs), "reach": sum(x["c"].get("v") or 0 for x in cs if x["st"] == "open"),
            "views": sum(x["c"].get("v") or 0 for x in cs)})
    # stable slugs: keep every slug ever given, add new ones without collisions
    taken = set(slugs.values())
    for c in sorted(cases, key=lambda c: (c["opened"], c["doi"])):
        if c["doi"] in slugs:
            continue
        base = slugify(c["title"])
        s, i = base, 2
        while s in taken:
            s, i = f"{base}-{i}", i + 1
        slugs[c["doi"]] = s
        taken.add(s)
    for c in cases:
        c["slug"] = slugs[c["doi"]]
        c["url"] = f"{SITE}/case/{c['slug']}/"
    cases.sort(key=lambda c: ({"open": 0, "fixed": 1, "ok": 2}[c["st"]], -c["reach"], c["slug"]))
    return {"D": D, "notes": notes, "news": news, "slugs": slugs, "cases": cases, "today": today,
            "since": (D.get("ledger") or {}).get("since") or today}


def events(c):
    """The case log: what happened, oldest first."""
    ev = []
    for x in c["cites_on"]:
        cc, n, pg = x["c"], x["n"], x["page"]
        ev.append((cc["o"], "found", f"Found on <b>{esc(pg)}</b>: the citation is live and nothing near it mentions the retraction."))
        if n and n.get("reviewed"):
            ev.append((n["reviewed"], "rev", f"{'Rechecked under a stricter rule' if n.get('auto') else 'Read by hand'} ({esc(pg)}). {esc(n.get('verdict') or '')}"))
        if n and n.get("posted"):
            ev.append((n["posted"][:10], "post", f"Note posted on the talk page of <b>{esc(pg)}</b>."))
        if n and n.get("edited"):
            ev.append((n["edited"][:10], "post", f"We marked the citation on <b>{esc(pg)}</b> with Wikipedia's Retracted template ourselves."))
        for r in (n or {}).get("replies") or []:
            ev.append(((r.get("at") or n.get("posted") or "")[:10], "rep", f"{esc(r.get('user'))} replied: <q>{esc((r.get('said') or '')[-220:])}</q>"))
        if x["st"] == "fixed":
            how = ("our edit marked the citation as retracted" if x["ours"] else
                   "an editor marked the citation as retracted" if cc.get("how") == "flagged" else "the retracted source was removed")
            ev.append((cc["c"], "fix", f"Fixed on <b>{esc(pg)}</b>: {how}, {days(cc['o'], cc['c'])} days after we found it."))
    order = {"found": 0, "rev": 1, "post": 2, "rep": 3, "fix": 4}
    ev.sort(key=lambda e: (e[0], order[e[1]]))
    return ev


def headline(c):
    pg = c["lead"]["page"]
    others = len({x["page"] for x in c["cites_on"] if x["st"] == c["st"]}) - 1
    more = f" and {others} other article{'s' if others > 1 else ''}" if others > 0 else ""
    if c["st"] == "open":
        return f"Wikipedia still cites a retracted paper on “{pg}”{more}"
    if c["st"] == "fixed":
        if c["lead"]["c"].get("how") == "flagged":
            return f"Fixed: Wikipedia now warns readers on “{pg}”{more}"
        return f"Fixed: “{pg}”{more} no longer cites a retracted paper"
    return f"Reviewed: “{pg}” cites a retracted paper, and here that's fine"


def plain_title(c):
    """For <title>, search results and the share text."""
    pg = c["lead"]["page"]
    if c["st"] == "fixed":
        return f"Fixed: retracted paper removed from “{pg}” on Wikipedia"
    if c["st"] == "ok":
        return f"Reviewed: a retracted paper cited on “{pg}”"
    return f"Retracted paper still cited on Wikipedia’s “{pg}”"


def describe(c):
    q = c["quote"]
    if q and len(q) > 170:
        q = q[:168].rsplit(" ", 1)[0] + "…"
    src = f"Source: “{c['title'][:110]}{'…' if len(c['title']) > 110 else ''}”, retracted {month(c['retracted'])}."
    return (f"“{q.lstrip('…')}” {src}" if q else src)


# ───────────────────────── case pages ─────────────────────────

STATUS_LABEL = {"open": ("pill z", "Zombie"), "fixed": ("pill ok", "Fixed"), "ok": ("pill", "Reviewed · no fix needed")}


def case_body(c, M):
    lead, st = c["lead"], c["st"]
    kick = {"open": f"Case file · open since {nice(c['opened'])}",
            "fixed": f"Case file · fixed {nice(lead['c'].get('c'))}",
            "ok": f"Case file · reviewed {nice((lead['n'] or {}).get('reviewed'))}"}[st]
    quote = ""
    if c["quote"]:
        w = c["quote_w"]
        quote = (f'<blockquote class="cf-q"><p><mark>{esc(c["quote"])}</mark><sup>[source retracted]</sup></p>'
                 f'<footer>Wikipedia · <a href="{esc(wurl(w["page"], w.get("section")))}" target="_blank" rel="noopener">{esc(w["page"])}</a>'
                 f'{" › " + esc(w["section"]) if w.get("section") and w["section"] != "Lead" else ""}'
                 f'{" · " + format(w.get("views") or 0, ",") + " views in the last 30 days" if w.get("views") else ""}</footer></blockquote>')
    authors = ", ".join(c["authors"][:4]) + (" et al." if len(c["authors"]) > 4 else "")
    meta = " · ".join(x for x in [c["journal"], (c["published"] or "")[:4] and f"published {month(c['published'])}"] if x)
    reasons = "".join(f"<span>{esc(r)}</span>" for r in c["reasons"][:8])
    paper = (f'<div class="cf-paper"><h4>The source</h4><h2>{esc(c["title"])}</h2>'
             f'<p class="by">{esc(authors)}{"<br>" if authors else ""}{esc(meta)}'
             f'{" · cited " + format(c["cites"], ",") + " times by other papers" if c.get("cites") else ""}</p>'
             f'<p class="cf-dead">Retracted {esc(nice(c["retracted"]))}</p>'
             f'{"<div class=cause>" + reasons + "</div>" if reasons else ""}</div>')
    rows = []
    for x in c["cites_on"]:
        cls, lab = STATUS_LABEL[x["st"]]
        w, cc = x["w"] or {}, x["c"]
        sub = (f"{format(cc.get('v') or 0, ',')} views a month"
               + (f" · open since {nice(cc['o'], False)}" if x["st"] == "open" else "")
               + (f" · fixed in {days(cc['o'], cc['c'])} days" if x["st"] == "fixed" else "")
               + (" · editors told" if x["told"] and x["st"] == "open" else ""))
        rows.append(f'<li><div><a href="{esc(wurl(x["page"], w.get("section")))}" target="_blank" rel="noopener">{esc(x["page"])}</a>'
                    f'<span class="ca">{sub}</span></div><span class="{cls}">{lab}</span></li>')
    for w in c["flagged"]:
        rows.append(f'<li><div><a href="{esc(wurl(w["page"], w.get("section")))}" target="_blank" rel="noopener">{esc(w["page"])}</a>'
                    f'<span class="ca">already warns readers</span></div><span class="pill fl">Flagged</span></li>')
    log = "".join(f'<li><time datetime="{esc(e[0])}">{esc(nice(e[0]))}</time><span class="k {e[1]}">'
                  f'{ {"found": "Found", "rev": "Reviewed", "post": "Note posted", "rep": "Reply", "fix": "Fixed"}[e[1]] }</span><span>{e[2]}</span></li>'
                  for e in events(c))
    nxt = {"open": "We read every case by hand before telling editors, then check the article every day. This page updates when anything changes.",
           "fixed": "The fix is checked every day. If the citation comes back, the case reopens here.",
           "ok": "We read the article and the retraction notice and decided no change is needed. The reason is in the case log below."}[st]
    from urllib.parse import quote as q
    contest = "mailto:tips@zombiefacts.org?subject=" + q("Contest: " + lead["page"]) + "&body=" + q(f"Case: {c['url']}\n\nWhat's wrong with it:\n\nEvidence (links):\n")
    share_t = plain_title(c)
    acts = (f'<div class="acts">'
            f'<a class="p" href="https://doi.org/{esc(c["notice"] or c["doi"])}" target="_blank" rel="noopener">Retraction notice</a>'
            f'<a href="https://doi.org/{esc(c["doi"])}" target="_blank" rel="noopener">The paper</a>'
            f'<button type="button" class="cf-share" data-url="{esc(c["url"])}" data-text="{esc(share_t)}">Share</button>'
            f'<a href="{esc(contest)}">Contest this case</a></div>')
    return f'''  <article class="sec pagehead cf cf-{st}">
    <div class="kicker">{esc(kick)}</div>
    <h1 class="cf-h">{esc(headline(c))}</h1>
    {quote}
    <p class="cf-next">{esc(nxt)}</p>
    {acts}
    <div class="cf-grid">
      {paper}
      <div><h4>Where Wikipedia cites it</h4><ol class="cf-where">{"".join(rows)}</ol></div>
    </div>
    <div class="feedwrap"><h4>Case log</h4><ol class="feed">{log}</ol></div>
    <p class="cf-fine">A zombie is not an accusation. Some articles cite a retracted paper to discuss it, and some retractions don't touch the cited claim, which is why a person reads every case. <a href="/method/">How we decide</a> · <a href="/about/#contest">How to contest a case</a></p>
    <a class="golink" href="/desk/">All cases on the correction desk →</a>
  </article>'''


def case_jsonld(c, M):
    j = {"@context": "https://schema.org", "@type": "Article", "headline": plain_title(c)[:110],
         "description": describe(c), "url": c["url"], "datePublished": c["opened"],
         "dateModified": (M["D"].get("checked") or M["D"].get("built") or M["today"])[:10],
         "author": {"@type": "Organization", "name": "Zombie Facts", "url": f"{SITE}/about/"},
         "publisher": {"@type": "Organization", "name": "Zombie Facts", "url": SITE + "/"},
         "about": {"@type": "ScholarlyArticle", "name": c["title"], "sameAs": f"https://doi.org/{c['doi']}"}}
    if card_exists(c):
        j["image"] = card_url(c)
    return '<script type="application/ld+json">' + json.dumps(j, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def card_path(c):
    return os.path.join(ROOT, "case", c["slug"], "card.png")


def card_exists(c):
    return os.path.exists(card_path(c))


def card_url(c):
    v = (load_cards().get(c["slug"]) or "")[:8]
    return f"{SITE}/case/{c['slug']}/card.png" + (f"?v={v}" if v else "")


_cards = None


def load_cards():
    global _cards
    if _cards is None:
        try:
            _cards = json.load(open(os.path.join(ROOT, "case", "cards.json")))
        except (OSError, ValueError):
            _cards = {}
    return _cards


def card_input(c):
    """What the share image shows; cards.py redraws a card when this changes."""
    w = c["quote_w"] or {}
    return {"st": c["st"], "page": c["lead"]["page"], "quote": said(w, 230) if w else "", "title": c["title"],
            "retracted": (c["retracted"] or "")[:4], "journal": c["journal"] or "",
            "fixdays": days(c["lead"]["c"]["o"], c["lead"]["c"]["c"]) if c["st"] == "fixed" else None,
            "how": c["lead"]["c"].get("how")}


# ───────────────────────── results ─────────────────────────

def median(xs):
    return statistics.median(xs) if xs else None


def results_numbers(M):
    cites = [x for c in M["cases"] for x in c["cites_on"]]
    open_ = [x for x in cites if x["st"] == "open"]
    fixed = [x for x in cites if x["st"] == "fixed"]
    ok = [x for x in cites if x["st"] == "ok"]
    ours = [x for x in fixed if x["ours"]]   # fixed by our own edit: counted, but kept out of the note test
    told = [x for x in cites if x["told"] and not x["ours"]]
    told_fixed = [x for x in told if x["st"] == "fixed"]
    untold = [x for x in cites if not x["told"] and not x["ours"] and x["st"] != "ok"]
    untold_fixed = [x for x in untold if x["st"] == "fixed"]
    replies = sum(len((x["n"] or {}).get("replies") or []) for x in told)
    posted_notes = [n for n in M["notes"] if n.get("posted")]
    after_note = [days(x["n"]["posted"][:10], x["c"]["c"]) for x in told_fixed if x["n"].get("posted")]
    return {"cites": cites, "open": open_, "fixed": fixed, "ours": ours,
            "reviewed": [n for n in M["notes"] if n.get("reviewed")], "ok": ok, "told": told, "told_fixed": told_fixed,
            "untold": untold, "untold_fixed": untold_fixed, "replies": replies, "posted": posted_notes,
            "med_fix": median([days(x["c"]["o"], x["c"]["c"]) for x in fixed]),
            "med_after_note": median(after_note),
            "clean_reads": sum(x["c"].get("v") or 0 for x in fixed),
            "open_reads": sum(x["c"].get("v") or 0 for x in open_)}


def pct(a, b):
    return f"{round(100 * a / b)}%" if b else "—"


def weeks(M):
    """Activity per week (weeks start Monday) since tracking began."""
    start = d(M["since"])
    start -= timedelta(days=start.weekday())
    end = d(M["today"])
    out = []
    w = start
    while w <= end:
        we = w + timedelta(days=7)
        inw = lambda s: bool(s) and w <= d(s) < we
        cs = [x for c in M["cases"] for x in c["cites_on"]]
        out.append({"w": w.isoformat(),
                    "found": sum(inw(x["c"]["o"]) for x in cs),
                    "notes": sum(inw((n.get("posted") or "")[:10]) for n in M["notes"]),
                    "fixed": sum(inw(x["c"].get("c")) for x in cs if x["st"] == "fixed")})
        w = we
    return out


def results_body(M):
    R = results_numbers(M)
    news = M["news"] or {}
    items = news.get("items") or []
    confirmed = [i for i in items if i.get("review") == "confirmed"]
    drafted = [i for i in items if i.get("review") == "drafted"]
    sent = [i for i in confirmed if i.get("outcome")]
    nfixed = [i for i in confirmed if i.get("outcome") == "fixed"]
    med = lambda v: "—" if v is None else (f"{v:g} d")
    first_note = min((n["posted"][:10] for n in M["notes"] if n.get("posted")), default=None)
    ours_txt = f" · {len(R['ours'])} by our own edit" if R["ours"] else ""
    rep = f" · {R['replies']} repl{'ies' if R['replies'] > 1 else 'y'}" if R["replies"] else ""
    clean = f" · {fmt_k(R['clean_reads'])} reads a month now clean" if R["clean_reads"] else ""
    board = (f'<div class="board">'
             f'<div><b>{len(R["cites"]):,}</b><span>Zombie citations opened as cases</span></div>'
             f'<div><b>{len(R["posted"]):,}</b><span>Notes posted to Wikipedia editors{rep}</span></div>'
             + (f'<div class="fx"><b>{len(R["fixed"]):,}</b><span>Fixed{ours_txt}{clean}</span></div>'
                f'<div><b>{med(R["med_fix"])}</b><span>Median time to fix</span></div></div>' if R["fixed"] else
                f'<div><b>{len(R["reviewed"]):,}</b><span>Cases read by hand</span></div>'
                f'<div><b>{days(first_note, M["today"]) if first_note else "—"}{" d" if first_note else ""}</b><span>Since the first note · editors often take weeks</span></div></div>'))

    def bar(label, a, b, note):
        w = 0 if not b else max(2, round(100 * a / b)) if a else 0
        return (f'<li><div class="rs-l"><b>{esc(label)}</b><span>{a:,} of {b:,} fixed · {pct(a, b)}</span></div>'
                f'<div class="rs-bar"><i style="width:{w}%"></i></div><p>{note}</p></li>')
    told_note = (f"No fixes yet on cases where we told editors. The first notes went up {nice(first_note)}; editors usually take days to weeks."
                 if R["told"] and not R["told_fixed"] else "Cases where a note is on the article's talk page.")
    if not R["told"]:
        told_note = "The first notes go up this week."
    rate = (f'<ol class="rs-rates">'
            f'{bar("After a note to editors", len(R["told_fixed"]), len(R["told"]), told_note)}'
            f'{bar("With no note (the baseline)", len(R["untold_fixed"]), len(R["untold"]), "Cases nobody has told editors about yet. If notes work, the top bar beats this one.")}'
            f'</ol>')
    W = weeks(M)
    mx = max([max(x["found"], x["notes"], x["fixed"]) for x in W] + [1])
    wk = "".join(
        f'<li><time>Week of {esc(nice(x["w"], False))}</time>'
        f'<span class="rs-w"><i class="f" style="width:{100 * x["found"] / mx:.1f}%"></i></span><span class="n">{x["found"]} found</span>'
        f'<span class="rs-w"><i class="p" style="width:{100 * x["notes"] / mx:.1f}%"></i></span><span class="n">{x["notes"]} notes</span>'
        f'<span class="rs-w"><i class="x" style="width:{100 * x["fixed"] / mx:.1f}%"></i></span><span class="n">{x["fixed"]} fixed</span></li>'
        for x in reversed(W[-12:]))

    def caselist(cs, right, empty):
        if not cs:
            return f'<li class="nil">{empty}</li>'
        return "".join(f'<li><a class="cp" href="/case/{esc(c["slug"])}/">{esc(c["lead"]["page"])}</a>'
                       f'<span class="cd{" ok" if c["st"] == "fixed" else ""}">{right(c)}</span>'
                       f'<span class="ca">{esc(c["title"][:90])}{"…" if len(c["title"]) > 90 else ""}</span></li>' for c in cs)
    fixed_c = sorted([c for c in M["cases"] if c["st"] == "fixed"], key=lambda c: c["lead"]["c"]["c"], reverse=True)[:8]
    standing, seen = [], set()
    for c in M["cases"]:
        if c["st"] == "open" and c["lead"]["page"] not in seen and len(standing) < 8:
            standing.append(c)
            seen.add(c["lead"]["page"])
    fixes = caselist(fixed_c, lambda c: f'{"Flagged" if c["lead"]["c"].get("how") == "flagged" else "Removed"}<small>{esc(nice(c["lead"]["c"]["c"], False))} · {days(c["lead"]["c"]["o"], c["lead"]["c"]["c"])} d</small>',
                     "Nothing fixed yet. Every fix lands here with the date and how it was made.")
    stand = caselist(standing, lambda c: f'{fmt_k(c["reach"])}<small>reads a month</small>', "No open cases.")

    outlets = {}
    for i in confirmed:
        o = outlets.setdefault(i.get("outlet") or i.get("domain") or "?", {"n": 0, "sent": 0, "fixed": 0, "declined": 0, "silent": 0})
        o["n"] += 1
        oc = i.get("outcome")
        o["sent"] += bool(oc)
        o["fixed"] += oc == "fixed"
        o["declined"] += oc == "declined"
        o["silent"] += oc == "no-reply"
    if outlets:
        orows = "".join(f'<tr><th scope="row">{esc(k)}</th><td>{v["n"]}</td><td>{v["sent"]}</td><td>{v["fixed"]}</td><td>{pct(v["fixed"], v["sent"])}</td></tr>'
                        for k, v in sorted(outlets.items(), key=lambda kv: (-kv[1]["sent"], kv[0])))
        otable = (f'<table class="rs-t"><thead><tr><th scope="col">Outlet</th><th scope="col">Cases</th><th scope="col">Asked</th>'
                  f'<th scope="col">Fixed</th><th scope="col">Fix rate</th></tr></thead><tbody>{orows}</tbody></table>')
    else:
        otable = (f'<p class="nil">No outlet has been asked for a correction yet. '
                  f'{"The first request is drafted and waiting for a final read." if drafted else "Every news lead is read in full before any outlet hears from us."} '
                  f'Each outlet shows up here with how many cases, how many were fixed and how fast.</p>')
    nboard = (f'<div class="board"><div><b>{len(confirmed):,}</b><span>Confirmed news cases</span></div>'
              f'<div><b>{len(sent):,}</b><span>Correction requests sent</span></div>'
              f'<div class="fx"><b>{len(nfixed):,}</b><span>Corrected by the outlet</span></div>'
              f'<div><b>{pct(len(nfixed), len(sent))}</b><span>Outlet fix rate</span></div></div>')
    built = (M["D"].get("checked") or M["D"].get("built") or "")
    return f'''  <section class="sec pagehead" id="results">
    <div class="sh"><h1>Results</h1><p>Finding zombie facts is the easy part. This is the scoreboard for getting them fixed: every case we open, every note we send and every fix, counted from the same files the rest of the site runs on. It updates every day. Tracking began {esc(nice(M["since"]))}.</p></div>
    {board}
    <div class="desk">
      <div class="dcol"><h4>Do notes work?</h4>{rate}
        <p class="rs-fine">A case is fixed when the retracted source is removed or Wikipedia marks it as retracted. The daily check closes cases on its own, so these numbers don't depend on anyone's say-so.{f" Median time from note to fix: {med(R['med_after_note'])}." if R["med_after_note"] is not None else ""}</p></div>
      <div class="dcol"><h4>Week by week</h4><ol class="rs-weeks">{wk}</ol></div>
    </div>
    <div class="desk rs-lists">
      <div class="dcol"><h4>Latest fixes</h4><ol class="cases">{fixes}</ol></div>
      <div class="dcol"><h4>Still standing <span class="mono dim">· most read</span></h4><ol class="cases">{stand}</ol>
        <a class="golink" href="/desk/">Every case on the desk →</a></div>
    </div>
  </section>
  <section class="sec" id="outlets">
    <div class="sh"><h2>News outlets</h2><p>When a story repeats a retracted or debunked claim, we ask the outlet to correct it and log the answer. Fixed, declined or no reply, it goes on the record.</p></div>
    {nboard}
    {otable}
    <p class="rs-fine">Raw data: <a href="/data.json">data.json</a>, <a href="/outreach.json">outreach.json</a>, <a href="/news.json">news.json</a>. New fixes and cases also go out on the <a href="/feed.xml">feed</a>. Numbers as of {esc(built.replace("T", " ").replace("Z", " UTC"))}.</p>
  </section>'''


def results_desc(M):
    R = results_numbers(M)
    return (f"The Zombie Facts scoreboard: {len(R['cites'])} cases opened, {len(R['posted'])} notes to Wikipedia editors, "
            f"{len(R['fixed'])} fixed so far. Fix rates, time to fix and outlet corrections, updated daily.")


# ───────────────────────── feed + sitemap ─────────────────────────

def stamp(s):
    s = s or ""
    if len(s) <= 10:
        return (s or "2026-11-05") + "T12:00:00Z"
    s = s.replace(" ", "T")
    if re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\dZ$", s):
        s = s[:-1] + ":00Z"
    return s


def feed(M):
    E = []
    slug = {c["doi"]: c for c in M["cases"]}
    for c in M["cases"]:
        for x in c["cites_on"]:
            if x["st"] == "fixed":
                how = "an editor marked the citation as retracted" if x["c"].get("how") == "flagged" else "the retracted source was removed"
                E.append((stamp(x["c"]["c"]), f"fix:{x['key']}", f"Fixed: {x['page']}",
                          c["url"], f"On “{x['page']}”, {how}, {days(x['c']['o'], x['c']['c'])} days after we found it. Source: {c['title']}, retracted {month(c['retracted'])}."))
    for n in M["notes"]:
        c = slug.get(n.get("doi"))
        if n.get("posted") and c:
            E.append((stamp(n["posted"]), f"note:{n['key']}", f"Note posted: {n['page']}", c["url"],
                      f"We told Wikipedia's editors that “{n['page']}” cites a retracted paper. {n.get('verdict') or ''}"))
        for r in (n.get("replies") or []) if c else []:
            E.append((stamp(r.get("at")), f"reply:{n['key']}:{r.get('at')}", f"Editors replied: {n['page']}", c["url"],
                      f"{r.get('user')} wrote: “{(r.get('said') or '')[-300:]}”"))
    found = {}
    for c in M["cases"]:
        for x in c["cites_on"]:
            found.setdefault(x["c"]["o"], []).append((c, x))
    for day, xs in found.items():
        xs.sort(key=lambda cx: -(cx[1]["c"].get("v") or 0))
        top = ", ".join(f"“{x['page']}”" for _, x in xs[:6]) + (f" and {len(xs) - 6} more" if len(xs) > 6 else "")
        body = "".join(f'<li><a href="{esc(c["url"])}">{esc(x["page"])}</a>: {esc(c["title"])}</li>' for c, x in xs[:60])
        E.append((stamp(day), f"found:{day}", f"{len(xs)} new zombie citation{'s' if len(xs) > 1 else ''} found on Wikipedia",
                  f"{SITE}/desk/", f"Retracted papers still cited with no warning on {top}.", f"<ul>{body}</ul>"))
    for i in (M["news"] or {}).get("items") or []:
        if i.get("review") == "confirmed":
            E.append((stamp(i.get("first")), f"news:{i.get('key') or i.get('url')}", f"News case: {i.get('outlet') or i.get('domain')}",
                      f"{SITE}/news/", i.get("claim") or i.get("headline") or ""))
            if i.get("outcome") == "fixed":
                E.append((stamp(i.get("fixed") or i.get("last")), f"newsfix:{i.get('key') or i.get('url')}",
                          f"Corrected: {i.get('outlet') or i.get('domain')}", f"{SITE}/news/", i.get("claim") or ""))
    E.sort(key=lambda e: e[0], reverse=True)
    E = E[:60]
    updated = E[0][0] if E else stamp(M["today"])
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<?xml-stylesheet type="text/css" href="/assets/feed.css"?>',
           '<feed xmlns="http://www.w3.org/2005/Atom">',
           '  <title>Zombie Facts</title>',
           '  <subtitle>Retracted, debunked and outdated facts still in circulation, and the fixes.</subtitle>',
           f'  <link href="{SITE}/feed.xml" rel="self" type="application/atom+xml"/>',
           f'  <link href="{SITE}/" rel="alternate" type="text/html"/>',
           f'  <id>{SITE}/</id>', f'  <updated>{updated}</updated>',
           '  <author><name>Zombie Facts</name><uri>https://zombiefacts.org/about/</uri></author>',
           f'  <icon>{SITE}/assets/icon.png</icon>']
    for e in E:
        ts, key, title, link, summ = e[:5]
        content = e[5] if len(e) > 5 else ""
        out += ['  <entry>', f'    <title>{esc(title)}</title>', f'    <link href="{esc(link)}"/>',
                f'    <id>tag:zombiefacts.org,2026:{esc(key)}</id>', f'    <updated>{ts}</updated>',
                f'    <summary>{esc(summ.strip())}</summary>']
        if content:
            out.append(f'    <content type="html">{esc(content)}</content>')
        out.append('  </entry>')
    out.append('</feed>')
    return "\n".join(out) + "\n"


def sitemap(urls):
    rows = "".join(f"  <url><loc>{esc(u)}</loc>{f'<lastmod>{m}</lastmod>' if m else ''}</url>\n" for u, m in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n'


# ───────────────────────── open data ─────────────────────────

DATA_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
CITE_COLS = ["doi", "title", "journal", "published", "retracted", "retraction_notice", "reasons", "superseded",
             "wikipedia_article", "section", "status", "quoted_sentence", "monthly_views"]
CASE_COLS = ["case_url", "doi", "title", "wikipedia_article", "state", "opened", "closed", "how_closed", "note_posted"]


def _csv(cols, rows):
    import csv, io
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(cols)
    w.writerows(rows)
    return b.getvalue()


def data_files(M):
    """CSV downloads: every Wikipedia citation of a retracted paper, and every case."""
    cites = []
    gone = {n["key"] for n in M["notes"] if n.get("status") == "dismissed"}
    for p in M["D"].get("papers", []):
        for w in p.get("wiki", []):
            st = "superseded" if superseded(p) else "reviewed" if f'{p["doi"]}|{w["page"]}' in gone and w.get("status") == "zombie" else w.get("status") or ""
            cites.append([p["doi"], clean_title(p.get("title")), p.get("journal") or "", p.get("published") or "",
                          p.get("retracted") or "", p.get("notice") or "", "; ".join(p.get("reasons") or []),
                          "yes" if superseded(p) else "no", w["page"], w.get("section") or "", st,
                          said(w, 10000), w.get("views") or 0])
    cites.sort(key=lambda r: (r[10] != "zombie", -r[12], r[0], r[8]))
    cases = []
    for c in M["cases"]:
        for x in c["cites_on"]:
            cc, n = x["c"], x["n"] or {}
            cases.append([c["url"], c["doi"], c["title"], x["page"], x["st"], cc.get("o") or "", (cc.get("c") or "")[:10],
                          cc.get("how") or ("dismissed" if n.get("status") == "dismissed" else ""), (n.get("posted") or "")[:10]])
    cases.sort(key=lambda r: (r[0], r[3]))
    return {"data/citations.csv": _csv(CITE_COLS, cites), "data/cases.csv": _csv(CASE_COLS, cases)}, len(cites), len(cases)


def data_body(M):
    files, nc, nk = data_files(M)
    size = lambda k: f"{max(1, round(len(files[k].encode()) / 1024)):,} KB"
    cols = lambda rows: "".join(f"<li><code>{esc(a)}</code> {esc(b)}</li>" for a, b in rows)
    when = nice((M["D"].get("checked") or M["D"].get("built") or "")[:10])
    return f'''  <section class="sec pagehead" id="data">
    <div class="sh"><h1>Download the data</h1><p>Everything on this site comes from open data, and everything we add is open too. Use it for research, reporting or your own tools. Updated daily; last update {esc(when)}.</p></div>
    <div class="ab">
      <div class="ab-main">
        <h3>Files</h3>
        <ul class="dl">
          <li><a class="golink" href="/data/citations.csv" download>citations.csv</a><span>{nc:,} rows · {size("data/citations.csv")}</span><p>Every citation of a retracted paper we found on English Wikipedia, with the sentence it supports and whether the article warns readers.</p></li>
          <li><a class="golink" href="/data/cases.csv" download>cases.csv</a><span>{nk:,} rows · {size("data/cases.csv")}</span><p>Every case on the correction desk: when we found it, whether editors were told, and when and how it was fixed.</p></li>
          <li><a class="golink" href="/data.json">data.json</a><span>full record</span><p>The file the site itself reads, with authors, subjects and scholarly citation counts.</p></li>
        </ul>
        <h3>citations.csv columns</h3>
        <ul class="cols">{cols([("doi", "the retracted paper"), ("retraction_notice", "DOI of the official notice"), ("reasons", "Retraction Watch's reason codes"),
                                ("superseded", "yes when the paper was only replaced by a newer version (out of date, not discredited)"),
                                ("status", "zombie: no warning near it · flagged: the article mentions the retraction · reviewed: read by hand, cited on purpose · author or subject: the article is about the author or the scandal · superseded: replaced by a newer version"),
                                ("quoted_sentence", "the sentence the citation supports, when it is readable"), ("monthly_views", "article views in the last 30 days")])}</ul>
        <h3>cases.csv columns</h3>
        <ul class="cols">{cols([("state", "open, fixed, or ok (reviewed, no fix needed)"), ("how_closed", "flagged: the citation was marked as retracted · removed: the source was taken out · dismissed: reviewed and kept on purpose"),
                                ("note_posted", "the day a note went up on the article's talk page")])}</ul>
      </div>
      <aside class="ab-side">
        <h4>License</h4>
        <p class="rs-fine">Our data is free to reuse under <a href="{DATA_LICENSE}" target="_blank" rel="noopener">CC BY 4.0</a>. Credit “Zombie Facts (zombiefacts.org)”.</p>
        <p class="rs-fine">The quoted sentences come from Wikipedia and stay under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a>, credited to Wikipedia's contributors. Retraction records come from the Retraction Watch database, released by Crossref under CC0.</p>
        <h4 class="h4b">Found a mistake?</h4>
        <p class="rs-fine">Tell us at <a href="mailto:tips@zombiefacts.org">tips@zombiefacts.org</a>. Fixes go in the <a href="/about/#corrections">corrections log</a>.</p>
      </aside>
    </div>
  </section>'''


def dataset_jsonld(M):
    when = (M["D"].get("checked") or M["D"].get("built") or M["today"])[:10]
    return '<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "Dataset", "name": "Zombie Facts: retracted research still cited on Wikipedia",
        "description": "Every citation of a retracted paper on English Wikipedia, the sentence it supports, whether readers are warned, and what happened after editors were told.",
        "url": f"{SITE}/data/", "license": DATA_LICENSE, "isAccessibleForFree": True, "dateModified": when,
        "creator": {"@type": "Organization", "name": "Zombie Facts", "url": SITE + "/"},
        "isBasedOn": ["https://gitlab.com/crossref/retraction-watch-data", "https://en.wikipedia.org/"],
        "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{SITE}/data/citations.csv"},
                         {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{SITE}/data/cases.csv"},
                         {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}/data.json"}]},
        ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def website_jsonld():
    return '<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "WebSite", "name": "Zombie Facts", "url": SITE + "/",
        "description": "Retracted, debunked and outdated facts that are still in circulation, and the fight to fix them.",
        "publisher": {"@type": "Organization", "name": "Zombie Facts", "url": SITE + "/", "logo": f"{SITE}/assets/icon.png", "email": TIPS_EMAIL}},
        ensure_ascii=False, separators=(",", ":")) + "</script>"
