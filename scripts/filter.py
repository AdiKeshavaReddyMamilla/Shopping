"""Match deals against the watchlist, apply thresholds, rank, and de-dupe."""
from __future__ import annotations

from datetime import datetime, timezone


def _match_categories(text: str, categories: dict) -> list[str]:
    """Return every watchlist category whose keywords appear in the text."""
    low = text.lower()
    matched = []
    for category, keywords in (categories or {}).items():
        for kw in keywords or []:
            if str(kw).lower() in low:
                matched.append(category)
                break
    return matched


def _score(deal: dict) -> float:
    """Rank deals: bigger discount and more recent = higher score."""
    score = 0.0
    if deal.get("discount"):
        score += deal["discount"]
    try:
        posted = datetime.fromisoformat(deal["posted_at"])
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - posted).total_seconds() / 3600
        # Newer deals get a boost that decays over ~3 days.
        score += max(0.0, 72 - age_hours) / 2
    except (ValueError, KeyError):
        pass
    return score


def filter_deals(deals: list[dict], watchlist: dict) -> list[dict]:
    """Keep only deals that match the watchlist and clear the discount floor.

    Adds 'categories' (list) and 'score' (float) to each kept deal, and
    returns them sorted best-first, capped at watchlist['max_deals'].
    """
    categories = watchlist.get("categories", {})
    min_discount = int(watchlist.get("min_discount_percent", 0) or 0)
    max_deals = int(watchlist.get("max_deals", 120) or 120)

    kept: list[dict] = []
    for deal in deals:
        blob = f"{deal.get('title', '')} {deal.get('summary', '')}"
        matched = _match_categories(blob, categories)
        if not matched:
            continue
        # Discount floor: keep if it clears the bar, OR if we can't read a
        # discount at all (many great deals don't say "% off" in the title).
        disc = deal.get("discount")
        if disc is not None and disc < min_discount:
            continue
        deal = {**deal, "categories": matched, "score": round(_score(deal), 1)}
        kept.append(deal)

    kept.sort(key=lambda d: d["score"], reverse=True)
    return kept[:max_deals]


def split_new(deals: list[dict], seen_ids: set[str]) -> tuple[list[dict], set[str]]:
    """Split deals into ones we've never seen (for alerts) vs. all ids to remember."""
    new = [d for d in deals if d["id"] not in seen_ids]
    all_ids = seen_ids | {d["id"] for d in deals}
    return new, all_ids
