# Zombie Facts design system

The site is a public record of retracted research that is still being cited. People land on it from a shared link, a Wikipedia talk page or a news story, and they need to trust it quickly. So the design is meant to look like an evidence file rather than a horror zine: quiet paper, firm type, and colour only where it means something.

## Direction: the retraction stamp

Journals mark retracted papers with a red RETRACTED watermark. The site borrows that one gesture. A small red stamp (`.stamp`, `.cf-dead`) marks a retracted source, the sentence that still relies on it gets a lime highlighter band, and everything else stays black ink on bone paper. The zombie-head logo is the only playful element, and it stays animated (it blinks, its pupil moves and it drips).

What was removed in the redesign, and why:

| Removed | Reason |
|---|---|
| Paper-grain overlay, tilted hero letters, dripping wordmark, swinging toe-tag | Decoration competing with the evidence; the grain was a full-screen blend layer that cost paint time on phones |
| Scrolling quote ticker | Repeated the featured cards and moved constantly |
| Full acid highlight behind every quote | When everything is highlighted nothing is; a lower-third highlighter band reads as a marker, not a fill |
| "Vol. 1 · date" edition line | Ornamental |
| Eight 10px tabs in two rows on phones | Now a menu sheet with a one-line description per section |
| Green meaning both "zombie" and "fixed" | Fixed is now ink with a ✓; green only ever means "still cited" |

## Colour

All colours are tokens on `:root` in `assets/site.css`, redefined for dark mode under `prefers-color-scheme` and `[data-theme]`. The theme button saves the choice in `localStorage.zfTheme`, and an inline script in `src/_head.html` applies it before first paint.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `--bg` | `#f2f0e9` | `#0e100d` | Page |
| `--surface` | `#fbfaf6` | `#161914` | Raised: specimen card, case quote, inputs, panels |
| `--sunk` | `#e8e5db` | `#090a08` | Hover on secondary buttons |
| `--ink` | `#17181a` | `#ecebe4` | Text, primary buttons, rules, **fixed** |
| `--ink2` | `#3b3c3f` | `#cbcac1` | Body copy under headings |
| `--mute` | `#625f57` | `#9d9b91` | Meta, labels (5.6:1 on `--bg`) |
| `--live` | `#c8f031` | same | **Still cited / zombie**: fills, highlighter, focus dot. Never used as text on light |
| `--liveInk` | `#3a6500` | `#c8f031` | The same meaning as text |
| `--dead` | `#b3261e` | `#ff7d6e` | **Retracted**, cause of death, open cases, errors |
| `--flag` | `#2b5ca8` | `#8db8ff` | **Wikipedia already warns readers** (flagged), replies, focus ring |

Rules: one meaning per colour. If something isn't zombie, retracted or flagged, it's ink or mute. Every text pair above passes WCAG AA (checked: the lowest is `--mute` on `--bg` at 5.6:1).

Old names (`--paper`, `--card`, `--acid`, `--acidInk`, `--blood`) are aliases so older inline styles in `app.js` keep working. Don't use them in new code.

## Type

Loaded from Google Fonts in `src/_head.html`.

| Role | Face | Use |
|---|---|---|
| Display | **Archivo**, width 62–75%, weight 800–850 | Page titles, section titles, big numbers, wordmark |
| Text | **Source Serif 4** (optical sizes) | Body copy, quoted Wikipedia sentences (italic), paper titles (600) |
| UI | **Archivo** at 100% width, 600 | Buttons, nav, chips, inputs |
| Data and labels | **IBM Plex Mono** 400–600 | Dates, counts, sources, and the single small-caps label style |

Scale: hero title `clamp(48px, 7.4vw, 104px)` at 62% width; page title `clamp(40px, 6vw, 76px)`; section title `clamp(32px, 4.2vw, 54px)` at 70%; card quote 19px (featured lead up to 32px); body 18px/1.55 (17px on phones); labels 12px mono uppercase, +0.06em. Nothing smaller than 11px, and only pills go that small. Keep body copy under about 65 characters a line (`max-width: 62ch`).

## Layout

- Content width 1200px (`--max`), side gutter `clamp(16px, 4vw, 40px)` (`--pad`).
- Breakpoints actually used: 520 (small phone), 640, 760, 860–980 (two-column to one), 1100 (inline nav vs menu), 1280 (short vs long nav labels).
- Sections start with a 2px ink rule and a title/intro pair (`.sh`); the first section of a page (`.pagehead`) drops the rule and uses the page `h1`.
- Grids are separated by 1px hairlines (`gap:1px` on a `--rule` background), not by boxes. Only three things get a border box: the home specimen, the case quote and the Check panels.
- **No horizontal scrolling.** Chip rows wrap, tables are narrow, long titles use `overflow-wrap:anywhere`. Every page is checked at 390, 768 and 1440 with `scrollWidth == innerWidth`.

## Components

| Component | Class | Notes |
|---|---|---|
| Masthead | `.mast` | Sticky, 64px. Logo, inline nav at ≥1100px, "Report a zombie" button, theme button, menu button below 1100px |
| Phone menu | `.nav` + `body.menu-on` | Full-height sheet, large labels with a one-line note each; Esc and link taps close it; focus moves to the first link |
| Buttons | `.btn` / `.go` / `.more` / `.tipgo` (primary, ink fill), `.acts a`, `.wfix a` (secondary, outline; add `.p` for primary) | 44px minimum height, 3px radius, Archivo 600 15px |
| Text link with arrow | `.golink` | Underlined with a 2px rule; the rule turns lime on hover |
| Status pills | `.pill.z` zombie, `.pill.fl` flagged, `.pill.r` retraction cause, `.pill.ok` fixed | Mono 11.5px, fully rounded. The only fully rounded things besides chips and icon buttons |
| Stamp | `.stamp`, `.cf-dead` | Red outlined, mono caps, rotated −2.5°. One per view at most |
| Highlighted claim | `mark` inside `.quote` / `.cf-q` | Lime band across the lower third; struck through in red once a case is fixed |
| Stat board | `.board`, `.vitals` | Archivo numbers at 62% width, mono labels under them |
| Case lists | `.cases`, `.reg`, `.feed` | Hairline rows; status on the right in mono (red open, ink fixed with ✓, mute reviewed) |
| Drawer | `.drawer` | Side sheet on desktop, bottom sheet (swipe down to close) on phones |
| Focus | `:focus-visible` | 2.5px `--focus` outline, 2px offset, everywhere |

## Motion

Kept small and meaningful: the logo blinks, the hero EKG draws published → retracted → still cited, counters count up once, autopsy bars grow once in view, the live-count dot pulses. `prefers-reduced-motion` turns all of it off.

## Share images

| Image | Source | How it's made |
|---|---|---|
| `/og.png` (site-wide) | `build/og-card.html` | Render at 1200×630 with any headless Chrome, save over `og.png`, bump `?v=` in `src/_head.html` |
| `/case/<slug>/card.png` | `build/cards.py` (`CSS`, `card_html`) | `python build/cards.py --all`; bump `VERSION` after a design change |
| "Save share image" in the drawer | `shareCard()` in `assets/app.js` | Drawn on a canvas in the browser, 1080×1350 |

All three use the same paper, ink, lime and red, the Archivo wordmark, and `zombiefacts.org` on a lime tab.

## Feed

`/feed.xml` links `assets/feed.css`, so a browser shows a readable page with a short "paste this into a feed reader" note instead of raw XML. Feed readers ignore it.

## Coverage (Nov 2026 redesign)

Checked in Chromium at 390, 768 and 1440, light and dark: home, Register (search, cause chips, sort, options), Correction desk, Newsroom, Results, Autopsy, Check a page, Method, About, Report a zombie (including its error state), 404, case pages (open case with and without a quote), the case drawer (desktop side sheet and phone bottom sheet), the phone menu, the feed and all share images.

Not checked: real iOS Safari and Android Chrome (only Chromium device emulation), the live Check-a-page scan (it calls Crossref and Wikipedia from the browser), a fixed case page (there are none yet), and a screen reader pass.

## Adding a page

1. Add a fragment in `src/pages/`, start it with `<section class="sec pagehead" id="…"><div class="sh"><h1>Title</h1><p>One or two plain sentences.</p></div>`.
2. Register it in `PAGES` or `EXTRA` in `build/make_pages.py` (and `NAV_NOTE` if it goes in the nav, `FOOT_GROUPS` for the footer).
3. Use existing classes before writing new CSS. If you need a colour, it must be one of the four meanings above or ink/mute.
4. Run `python build/make_pages.py`, then check the page at 390px for horizontal overflow.
