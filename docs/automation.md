# How Zombie Facts runs itself

Everything below runs on GitHub's free tier. Nothing here costs money and nothing needs a
server. This page is the runbook: what runs, when, what it is allowed to do on its own, and
what still waits for a person.

## The loop

| Step | Job | When (UTC) | What it does without anyone |
|---|---|---|---|
| Find | `zombie-facts.yml` → `build/build_data.py` | Monday 09:00 | Downloads the Retraction Watch file and Wikipedia's link table, reads every citing article, opens a case for each retracted paper cited with no warning |
| Verify | same job | Monday 09:00 | Checks each paper against Crossref for a second source (the publisher's notice, or Retraction Watch's entry there). Papers that are only replaced by a newer version, biographies of the author and articles about the scandal itself are set aside by rule |
| Watch | `zombie-facts-watch.yml` → `build/recheck.py` | every 6 hours | Re-reads every article with an open case, closes the fixed ones, reads replies on talk pages |
| Newsroom | `news-watch.yml` → `build/news_watch.py` | Monday 10:30 | Reads the public fact-check feed and searches the news for retracted papers. Every lead lands as unreviewed |
| Publish | `build/publish.sh`, then `pages.yml` | after each job | Redraws share images, rebuilds every page, the feed, the sitemap and the CSV downloads, commits and deploys. Pings search engines |
| Report | `build/site_extras.py`, `build/social.py` | with each publish | Results page, case logs, feed entries, a weekly round-up in the feed, and one social post a day once the account secrets exist |
| Check itself | `health.yml`, `audit.yml` | daily 15:40, Sunday 15:00 | Checks the live site and that every job above is landing. Restarts a stalled job and looks again before it opens an issue. The audit re-reads flagged citations and lists papers with no second source |

## Safety rails

- A build that loses most of the record refuses to publish (`sanity_check`).
- No run may close more than half the open cases at once.
- A case closes as fixed only after the article is re-read and the citation is gone. A paper
  Retraction Watch no longer lists closes as `unlisted` and is never counted as a fix.
- Papers with no retraction on record at Crossref stay off the home page, social posts and notes.
- Every fetch names the project in its User-Agent, runs one request at a time against
  Wikipedia, and backs off when asked.

## What still needs a person, and why

| Step | Why it is not automatic |
|---|---|
| Posting a note on a Wikipedia talk page | Wikipedia does not allow unapproved automated editing. `build/post_notes.py` is ready; it runs only by hand until a bot request is approved |
| Emailing a news outlet | Naming an outlet is a judgment call. Every request is read and sent by the editor |
| Marking a news lead confirmed | Same reason. A lead is only public once someone has read the story |
| Creating accounts and adding secrets | Bluesky, Mastodon and Wikipedia credentials are added by the owner as repository secrets, never in code |

## Switches

Repository secrets turn features on. With a secret missing, the feature stays off and says so in the log.

| Secret | Turns on |
|---|---|
| `BSKY_HANDLE`, `BSKY_APP_PASSWORD` | One Bluesky post a day |
| `MASTODON_URL`, `MASTODON_TOKEN` | One Mastodon post a day |
| `MEDIACLOUD_API_KEY` | News search for retracted papers |
| `WIKI_USER`, `WIKI_PASS` | Posting approved notes, by hand, from the watch workflow |

## When something breaks

1. The health check restarts the stalled job and checks again seven minutes later.
2. If the site is still failing, an issue titled "Site health check failing" opens with the failing checks. It closes itself when they pass.
3. `build/publish.sh` fails loudly when it cannot commit or push, so a broken publish shows as a red run instead of a quiet one.

## Reviewing by hand

The weekly review covers what the rules cannot decide:

1. Read the audit issue ("Weekly accuracy audit") and act on anything it lists.
2. Read new open cases with the most readers; for each, read the article and the retraction notice, then draft a note with `python build/outreach.py draft "<doi>|<page>" --verdict "why"` or dismiss it with the reason.
3. Read unreviewed news leads in `news.json`; dismiss with a reason or mark one confirmed.
4. Add a line to the corrections log in `src/pages/_about.html` for every correction.
