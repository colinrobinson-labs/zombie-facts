#!/usr/bin/env bash
# Rebuild the pages from the data files, commit whatever changed and redeploy.
# Shared by every data workflow, so they cannot drift apart.
#
#   build/publish.sh "commit message"
#
# Files that do not exist yet (social.json before the first post) are skipped one by
# one: a single missing name used to make `git add` refuse the whole list, and the
# daily recheck then committed nothing for days without failing.
set -euo pipefail
msg="${1:?usage: build/publish.sh \"commit message\"}"

git config user.name "zombie-facts-bot"
git config user.email "actions@users.noreply.github.com"

python build/cards.py || echo "::warning::share images were not redrawn this run"
python build/make_pages.py

for p in data.json news.json outreach.json social.json index.html 404.html */index.html \
         case share data feed.xml sitemap.xml robots.txt; do
  if [ -e "$p" ]; then git add -A -- "$p"; fi
done
if git diff --cached --quiet; then
  echo "no change"
  exit 0
fi
git commit -q -m "$msg"

pushed=""
for i in 1 2 3 4 5; do
  if git pull -q --rebase origin main && git push -q origin HEAD:main; then pushed=1; break; fi
  git rebase --abort 2>/dev/null || true
  sleep $((i * 5))
done
if [ -z "$pushed" ]; then
  echo "::error::could not push to main after 5 tries; the next run starts from a fresh checkout"
  exit 1
fi
gh workflow run pages.yml --ref main
