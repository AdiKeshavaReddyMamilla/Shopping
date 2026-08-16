"""Orchestrator: fetch -> filter -> notify -> build. Run by the GitHub Action.

Usage:
    python scripts/main.py           # full run (fetch, build, alert)
    python scripts/main.py --no-notify   # skip Telegram (useful for testing)
"""
from __future__ import annotations

import sys
import json

from common import load_yaml, SEEN_FILE, STATE
from fetch import fetch_all
from filter import filter_deals, split_new
from build import build_site
from notify import notify_new


def _load_seen() -> set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text() or "[]"))
        except json.JSONDecodeError:
            return set()
    return set()


def _save_seen(ids: set[str]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    # Cap memory so the file doesn't grow forever.
    trimmed = list(ids)[-5000:]
    SEEN_FILE.write_text(json.dumps(trimmed, indent=0))


def main(argv: list[str]) -> int:
    do_notify = "--no-notify" not in argv

    watchlist = load_yaml("watchlist.yaml")
    sources = load_yaml("sources.yaml")
    coupons = load_yaml("coupons.yaml")

    print("== Fetching sources ==")
    raw_deals = fetch_all(sources)

    print("== Filtering against watchlist ==")
    deals = filter_deals(raw_deals, watchlist)
    print(f"  {len(deals)} deals match your watchlist.")

    seen = _load_seen()
    new_deals, all_ids = split_new(deals, seen)
    print(f"  {len(new_deals)} are new since last run.")

    if do_notify:
        print("== Notifying ==")
        notify_new(new_deals)
    else:
        print("== Notifying == (skipped: --no-notify)")

    print("== Building dashboard ==")
    build_site(deals, coupons, watchlist)

    _save_seen(all_ids)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
