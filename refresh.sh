#!/bin/bash
# Rescan git, summarise new commits via `claude -p`, rebuild dashboard.html.
# Safe for cron: absolute paths, minimal PATH, logs to refresh.log.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$(dirname "$0")" || exit 1
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') refresh start"
  python3 scan.py || exit 1
  python3 summarise.py || echo "summarise failed; new commits stay 'unsummarised'"
  python3 build.py
  echo "=== done"
} >> refresh.log 2>&1
