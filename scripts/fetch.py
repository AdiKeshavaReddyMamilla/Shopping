"""Fetch deals from all configured sources and normalize them.

Each normalized deal:
    {
      "id","title","url","source","role","store",
      "price"(float|None),"discount"(int|None),
      "image"(str|None),"posted_at"(ISO),"summary"
    }
"""
from __future__ import annotations

import time
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import feedparser

from common import (
    deal_id,
    extract_price,
    extract_discount,
    clean_text,
    store_from_text,
)

USER_AGENT = "shopping-deals-hub/2.0 (personal deals aggregator)"
REQUEST_TIMEOUT = 20
REDDIT_LIMIT = 60
_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _struct_to_iso(struct_time) -> str:
    if not struct_time:
        return _now_iso()
    try:
        return datetime.fromtimestamp(
            time.mktime(struct_time), tz=timezone.utc
        ).isoformat()
    except (OverflowError, ValueError):
        return _now_iso()


def _http_get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read()


def _rss_image(entry) -> str | None:
    # media:content / media:thumbnail / enclosure / <img> in summary.
    for key in ("media_content", "media_thumbnail"):
        media = entry.get(key)
        if media and isinstance(media, list) and media and media[0].get("url"):
            return media[0]["url"]
    for enc in entry.get("enclosures", []) or []:
        href = enc.get("href", "")
        if href and (href.lower().endswith(_IMG_EXT) or "image" in enc.get("type", "")):
            return href
    return None


def _mk(title, url, source, role, blob, image, posted, summary) -> dict:
    return {
        "id": deal_id(url, title),
        "title": title,
        "url": url,
        "source": source,
        "role": role,
        "store": store_from_text(blob),
        "price": extract_price(blob),
        "discount": extract_discount(blob),
        "image": image,
        "posted_at": posted,
        "summary": summary[:400],
    }


def fetch_rss(source: dict) -> list[dict]:
    name = source.get("name", "RSS")
    role = source.get("role", "deals")
    deals: list[dict] = []
    try:
        parsed = feedparser.parse(_http_get(source["url"]))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {name}: fetch failed ({exc})")
        return deals
    for entry in parsed.entries:
        title = clean_text(entry.get("title", ""))
        if not title:
            continue
        summary = clean_text(entry.get("summary", ""))
        blob = f"{title} {summary}"
        deals.append(
            _mk(
                title,
                entry.get("link", ""),
                name,
                role,
                blob,
                _rss_image(entry),
                _struct_to_iso(entry.get("published_parsed")),
                summary,
            )
        )
    print(f"  + {name}: {len(deals)} items")
    return deals


def _reddit_image(post: dict) -> str | None:
    url = post.get("url_overridden_by_dest", "") or ""
    if url.lower().endswith(_IMG_EXT):
        return url
    try:
        imgs = post["preview"]["images"]
        if imgs:
            return imgs[0]["source"]["url"].replace("&amp;", "&")
    except (KeyError, IndexError, TypeError):
        pass
    thumb = post.get("thumbnail", "")
    return thumb if thumb.startswith("http") else None


def fetch_reddit(source: dict) -> list[dict]:
    name = source.get("name", source.get("subreddit", "reddit"))
    role = source.get("role", "deals")
    sub = source["subreddit"]
    url = f"https://www.reddit.com/r/{sub}/new.json?limit={REDDIT_LIMIT}"
    deals: list[dict] = []
    try:
        payload = json.loads(_http_get(url))
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
        link = post.get("url_overridden_by_dest") or (
            "https://www.reddit.com" + post.get("permalink", "")
        )
        selftext = clean_text(post.get("selftext", ""))
        flair = clean_text(post.get("link_flair_text", ""))
        blob = f"{title} {flair} {selftext}"
        created = post.get("created_utc")
        posted = (
            datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
            if created
            else _now_iso()
        )
        deals.append(
            _mk(title, link, name, role, blob, _reddit_image(post), posted, selftext)
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
    print(f"Fetched {len(all_deals)} unique items from all sources.")
    return all_deals
