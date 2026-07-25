#!/bin/bash
# Periodically rebuilds maximize_database.csv from the latest scrape progress
# and pushes it to GitHub, so a Google Sheet using IMPORTDATA on the raw URL
# stays up to date without any manual steps.
cd "$(dirname "$0")/.."

LAST_HASH=""

while true; do
  if [ -f db/maximize_scrape_progress.json ]; then
    /usr/local/bin/python3.11 scripts/build_maximize_master.py > /dev/null 2>&1
    /usr/local/bin/python3.11 scripts/maximize_to_csv.py > /dev/null 2>&1

    CUR_HASH=$(shasum maximize_database.csv 2>/dev/null | awk '{print $1}')
    if [ -n "$CUR_HASH" ] && [ "$CUR_HASH" != "$LAST_HASH" ]; then
      git add maximize_database.csv db/maximize_master.json > /dev/null 2>&1
      if ! git diff --cached --quiet; then
        git commit -m "Auto-update maximize_database.csv ($(date '+%Y-%m-%d %H:%M'))" > /dev/null 2>&1
        git push origin main > /dev/null 2>&1
        echo "$(date '+%H:%M:%S') pushed update — $(wc -l < maximize_database.csv) rows"
      fi
      LAST_HASH="$CUR_HASH"
    fi
  fi
  sleep 120
done
