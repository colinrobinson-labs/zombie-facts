# Zombie Facts

**https://zombiefacts.org** tracks retracted research that English Wikipedia still cites as evidence. It also follows the fixes.

| Piece | What it does | When |
|---|---|---|
| `build/build_data.py` | Checks every retraction in the Retraction Watch database (via Crossref) against every DOI link on English Wikipedia, reads each citing article, and updates the case ledger | Weekly, Monday 09:00 UTC (`zombie-facts.yml`) |
| `build/recheck.py` | Re-reads articles with open cases and closes the fixed ones, then reads talk-page replies to our notes | Daily, 14:15 UTC (`zombie-facts-watch.yml`) |
| `build/outreach.py` | Drafts a sourced talk-page note for a reviewed case into `outreach.json` | By hand |
| `build/post_notes.py` | Posts approved notes, at most 3 per run. Needs the `WIKI_USER` and `WIKI_PASS` repo secrets | Manual run of the watch workflow with `post` ticked |
| `index.html`, `register/`, `desk/`, `news/`, `results/`, `autopsy/`, `check/`, `method/`, `about/`, `report/`, `404.html` | The pages. Generated from `src/` by `build/make_pages.py`; edit `src/`, never the output | Deployed by `pages.yml` |
| `build/site_extras.py` | Case pages (`/case/<slug>/`, slugs kept forever in `case/slugs.json`), the Results scoreboard, `feed.xml`, `sitemap.xml`. Called by `make_pages.py`. Switches for GoatCounter analytics, a newsletter link and a tips email are at the top | Every page build |
| `build/cards.py` | Draws each case's 1200×630 share image with headless Chrome; redraws only cards whose content changed (`case/cards.json`) | Before `make_pages.py` in the data workflows |
| `.github/ISSUE_TEMPLATE/` | "Report a zombie" and "Contest a case" forms; the site's Report page pre-fills the first | |
| `assets/site.css`, `assets/app.js` | Shared styles and script; the script reads `data.json` and `outreach.json`. Colours, type and components are documented in `docs/design-system.md` | |
| `build/og-card.html`, `assets/feed.css` | Source of the site-wide share image `og.png`, and the stylesheet that makes `feed.xml` readable in a browser | |

A note in `outreach.json` moves through these statuses: `queued` → `approved` → `posted` → `replied`, or ends as `dismissed`, which means we reviewed it and no fix is needed.

Tests: `python -m unittest discover build/tests`. The code uses only the Python standard library.

Data: Retraction Watch database via Crossref (CC0), Wikipedia (CC BY-SA), Crossref REST API. Not affiliated with any of them.
