"""Fetch deals from all configured sources and normalize them.

Every deal is normalized to a dict:
    {
      "id": str, "title": str, "url": str, "source": str,
      "price": float|None, "discount": int|None,
      "posted_at": ISO-8601 str, "summary": str,
    }
"""
from __future__ import annotations

import time
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import feedparser

from common import deal_id, extract_price, extract_discount, clean_text

USER_AGENT = "shopping-deals-hub/1.0 (personal deals aggregator)"
REQUEST_TIMEOUT = 20


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _struct_to_iso(struct_time) -> str:
    """Convert a feedparser time.struct_time to an ISO string, or 'now'."""
    if not struct_time:
        return _now_iso()
    try:
        dt = datetime.fromtimestamp(time.mktime(struct_time), tz=timezone.utc)
        return dt.isoformat()
    except (OverflowError, ValueError):
        return _now_iso()


def _http_get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read()


def fetch_rss(source: dict) -> list[dict]:
    """Fetch a standard RSS/Atom feed."""
    name = source.get("name", "RSS")
    url = source["url"]
    deals: list[dict] = []
    try:
        raw = _http_get(url)
    except Exception as exc:  # noqa: BLE001 - one bad feed shouldn't kill the run
        print(f"  ! {name}: fetch failed ({exc})")
        return deals
    parsed = feedparser.parse(raw)
    for entry in parsed.entries:
        title = clean_text(entry.get("title", ""))
        if not title:
            continue
        link = entry.get("link", "")
        summary = clean_text(entry.get("summary", ""))
        blob = f"{title} {summary}"
        deals.append(
            {
                "id": deal_id(link, title),
                "title": title,
                "url": link,
                "source": name,
                "price": extract_price(blob),
                "discount": extract_discount(blob),
                "posted_at": _struct_to_iso(entry.get("published_parsed")),
                "summary": summary[:300],
            }
        )
    print(f"  + {name}: {len(deals)} items")
    return deals


def fetch_reddit(source: dict) -> list[dict]:
    """Fetch a subreddit's public 'new' listing via its .json endpoint."""
    name = source.get("name", source.get("subreddit", "reddit"))
    sub = source["subreddit"]
    url = f"https://www.reddit.com/r/{sub}/new.json?limit=40"
    deals: list[dict] = []
    try:
        raw = _http_get(url)
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {name}: fetch failed ({exc})")
        return deals
    for child in payload.get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied"):
            continue
        title = clean_text(post.get("title", ""))
        if not title:
            continue
        # Prefer the outbound deal link; fall back to the reddit thread.
        link = post.get("url_overridden_by_dest") or (
            "https://www.reddit.com" + post.get("permalink", "")
        )
        selftext = clean_text(post.get("selftext", ""))
        blob = f"{title} {selftext}"
        created = post.get("created_utc")
        posted = (
            datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
            if created
            else _now_iso()
        )
        deals.append(
            {
                "id": deal_id(link, title),
                "title": title,
                "url": link,
                "source": name,
                "price": extract_price(blob),
                "discount": extract_discount(blob),
                "posted_at": posted,
                "summary": selftext[:300],
            }
        )
    print(f"  + {name}: {len(deals)} items")
    return deals


def fetch_all(sources_cfg: dict) -> list[dict]:
    """Fetch every configured source, de-duplicating by deal id."""
    seen_ids: set[str] = set()
    all_deals: list[dict] = []
    for source in sources_cfg.get("sources", []):
        stype = source.get("type")
        if stype == "rss":
            items = fetch_rss(source)
        elif stype == "reddit":
            items = fetch_reddit(source)
        else:
            print(f"  ? unknown source type: {stype}")
            items = []
        for deal in items:
            if deal["id"] in seen_ids:
                continue
            seen_ids.add(deal["id"])
            all_deals.append(deal)
        time.sleep(1)  # be polite to the feeds
    print(f"Fetched {len(all_deals)} unique deals from all sources.")
    return all_deals
