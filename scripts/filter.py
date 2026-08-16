"""Tag, score, and rank deals. v2: keep EVERYTHING, just highlight matches."""
from __future__ import annotations

from datetime import datetime, timezone

# Sources we trust a bit more (curated) get a small ranking nudge.
_SOURCE_TRUST = {
    "Slickdeals Frontpage": 8,
    "Slickdeals Popular": 6,
    "DealNews": 6,
    "Woot": 4,
    "r/buildapcsales": 4,
    "r/GameDeals": 4,
}


def _match_categories(text: str, categories: dict) -> list[str]:
    low = text.lower()
    out = []
    for category, keywords in (categories or {}).items():
        for kw in keywords or []:
            if str(kw).lower() in low:
                out.append(category)
                break
    return out


def _match_wishlist(text: str, items: list) -> list[str]:
    low = text.lower()
    return [str(it) for it in (items or []) if str(it).lower() in low]


def _freshness(posted_at: str) -> float:
    try:
        posted = datetime.fromisoformat(posted_at)
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - posted).total_seconds() / 3600
        return max(0.0, 96 - age_h) / 2  # decays over ~4 days
    except (ValueError, KeyError, TypeError):
        return 0.0


def _score(deal: dict) -> float:
    s = 0.0
    if deal.get("discount"):
        s += deal["discount"] * 1.2
    if deal.get("price") is not None:
        s += 6  # concrete price = a real, actionable deal
    if deal.get("image"):
        s += 3
    s += _freshness(deal.get("posted_at", ""))
    s += _SOURCE_TRUST.get(deal.get("source", ""), 0)
    if deal.get("categories"):
        s += 10  # matches something you care about
    if deal.get("wishlist"):
        s += 1000  # your shopping list always wins
    return s


def annotate_deals(deals: list[dict], watchlist: dict, wishlist: dict) -> list[dict]:
    """Tag every deal with categories/wishlist/score and sort best-first.

    Nothing is dropped — the whole feed is kept so the site feels full.
    """
    categories = watchlist.get("categories", {})
    wl_items = (wishlist or {}).get("items", [])
    max_deals = int(watchlist.get("max_deals", 400) or 400)

    out = []
    for deal in deals:
        blob = f"{deal.get('title','')} {deal.get('summary','')}"
        cats = _match_categories(blob, categories)
        stars = _match_wishlist(blob, wl_items)
        d = {**deal, "categories": cats, "wishlist": stars}
        d["score"] = round(_score(d), 1)
        out.append(d)

    out.sort(key=lambda d: d["score"], reverse=True)
    return out[:max_deals]


def alert_candidates(deals: list[dict], watchlist: dict) -> list[dict]:
    """Deals worth a Telegram ping: wishlist stars, or watchlist matches that
    clear the alert discount floor (deals with no readable discount still
    qualify if they match the watchlist)."""
    floor = int(watchlist.get("alert_min_discount_percent", 15) or 0)
    picks = []
    for d in deals:
        if d.get("wishlist"):
            picks.append(d)
        elif d.get("categories"):
            disc = d.get("discount")
            if disc is None or disc >= floor:
                picks.append(d)
    return picks


def split_new(deals: list[dict], seen_ids: set[str]) -> tuple[list[dict], set[str]]:
    """Split into never-seen (for alerts) vs. all ids to remember."""
    new = [d for d in deals if d["id"] not in seen_ids]
    all_ids = seen_ids | {d["id"] for d in deals}
    return new, all_ids
