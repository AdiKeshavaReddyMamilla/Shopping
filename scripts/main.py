"""Orchestrator: fetch -> annotate -> coupons -> notify -> build.

Usage:
    python scripts/main.py              # full run
    python scripts/main.py --no-notify  # skip Telegram (testing)
"""
from __future__ import annotations

import sys
import json

from common import load_yaml, SEEN_FILE, STATE
from fetch import fetch_all
from filter import annotate_deals, alert_candidates, split_new
from coupons_live import build_live_coupons
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
    SEEN_FILE.write_text(json.dumps(list(ids)[-8000:], indent=0))


def main(argv: list[str]) -> int:
    do_notify = "--no-notify" not in argv

    watchlist = load_yaml("watchlist.yaml")
    sources = load_yaml("sources.yaml")
    coupons = load_yaml("coupons.yaml")
    stores = load_yaml("stores.yaml")
    wishlist = load_yaml("wishlist.yaml")

    print("== Fetching sources ==")
    raw = fetch_all(sources)

    print("== Annotating & ranking deals ==")
    deals = annotate_deals(raw, watchlist, wishlist)
    print(f"  {len(deals)} deals kept · {sum(1 for d in deals if d['categories'])} match watchlist · {sum(1 for d in deals if d['wishlist'])} on your list")

    print("== Extracting live coupon codes ==")
    live_coupons = build_live_coupons(raw)

    print("== Notifying ==")
    seen = _load_seen()
    candidates = alert_candidates(deals, watchlist)
    new_alerts, all_ids = split_new(candidates, seen)
    print(f"  {len(new_alerts)} new alert-worthy deals since last run.")
    if do_notify:
        notify_new(new_alerts)
    else:
        print("  (skipped: --no-notify)")

    print("== Building dashboard ==")
    build_site(deals, live_coupons, coupons, stores, watchlist)

    # remember everything shown so we don't re-alert
    _, all_ids = split_new(deals, all_ids)
    _save_seen(all_ids)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
