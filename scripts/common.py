"""Shared helpers: paths, config loading, price/discount parsing, small utils."""
from __future__ import annotations

import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import yaml

# Repo root = one level up from this scripts/ directory.
ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
STATE = ROOT / "state"
SEEN_FILE = STATE / "seen.json"


def load_yaml(name: str) -> dict:
    """Load a YAML config file from the repo root (e.g. 'watchlist.yaml')."""
    path = ROOT / name
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def deal_id(url: str, title: str) -> str:
    """Stable id for a deal, used for de-duplication across runs."""
    basis = (url or "").strip().lower() or (title or "").strip().lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Price / discount parsing
# ---------------------------------------------------------------------------
_MONEY = r"\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
_PRICE_RE = re.compile(_MONEY)
_PCT_RE = re.compile(r"(\d{1,3})\s?%\s?(?:off|discount)", re.IGNORECASE)
# "was $120 now $80", "$120 -> $80", "reg $120 sale $80", "$120 | $80"
_WAS_NOW_RE = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:->|→|\bto\b|/|\|)\s*\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
_REG_SALE_RE = re.compile(
    r"(?:was|reg\.?|orig\.?|list|msrp)\s*\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?).{0,20}?"
    r"(?:now|sale|for|only)?\s*\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
_SAVE_RE = re.compile(r"save\s*\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)


def _to_float(s: str):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def extract_price(text: str):
    """Best-effort: the (sale) price mentioned. Returns float or None.

    If a 'high -> low' pair is present, returns the lower (sale) price.
    """
    if not text:
        return None
    m = _WAS_NOW_RE.search(text)
    if m:
        hi, lo = _to_float(m.group(1)), _to_float(m.group(2))
        if hi and lo:
            return min(hi, lo)
    m = _PRICE_RE.search(text)
    return _to_float(m.group(1)) if m else None


def extract_discount(text: str):
    """Best-effort discount percent (int) from many phrasings, else None.

    Handles: 'NN% off', 'was $X now $Y', '$X -> $Y', 'reg $X sale $Y',
    and 'save $Z' when a base price is also present.
    """
    if not text:
        return None

    # 1) explicit percent
    m = _PCT_RE.search(text)
    if m:
        pct = _to_float(m.group(1))
        if pct and 0 < pct <= 100:
            return int(round(pct))

    # 2) high -> low price pair
    for rx in (_WAS_NOW_RE, _REG_SALE_RE):
        m = rx.search(text)
        if m:
            hi, lo = _to_float(m.group(1)), _to_float(m.group(2))
            if hi and lo and hi > lo > 0:
                pct = (hi - lo) / hi * 100
                if 0 < pct <= 100:
                    return int(round(pct))

    # 3) "save $Z" against the first price seen
    m = _SAVE_RE.search(text)
    if m:
        save = _to_float(m.group(1))
        base_m = _PRICE_RE.search(text)
        base = _to_float(base_m.group(1)) if base_m else None
        if save and base and base > save > 0:
            pct = save / (base + save) * 100  # base looks like the sale price
            if 0 < pct <= 100:
                return int(round(pct))
    return None


def clean_text(text: str) -> str:
    """Strip HTML tags and collapse whitespace from a feed snippet."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&#?[a-z0-9]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def time_ago(iso_ts: str) -> str:
    """Human 'time ago' from an ISO timestamp (e.g. '3h ago')."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return ""
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 0:
        return "just now"
    for limit, div, unit in (
        (60, 1, "s"),
        (3600, 60, "m"),
        (86400, 3600, "h"),
        (604800, 86400, "d"),
    ):
        if secs < limit:
            n = int(secs // div)
            return "just now" if n <= 0 and unit == "s" else f"{n}{unit} ago"
    return f"{int(secs // 604800)}w ago"


# Known merchants -> used to tag a deal/coupon with a store when the text
# mentions it. Extend freely.
_KNOWN_STORES = [
    "Amazon", "Walmart", "Target", "eBay", "Costco", "Best Buy", "Nike",
    "Adidas", "DoorDash", "Uber Eats", "Grubhub", "Instacart", "Sephora",
    "Ulta", "Kohl's", "Macy's", "Nordstrom", "Old Navy", "Gap", "H&M",
    "Lululemon", "Newegg", "Dell", "HP", "Lenovo", "Apple", "Samsung",
    "GameStop", "Steam", "PlayStation", "Xbox", "Nintendo", "Home Depot",
    "Lowe's", "Wayfair", "IKEA", "Chewy", "REI", "Dick's", "Zappos", "DSW",
    "Foot Locker", "Domino's", "Pizza Hut", "CVS", "Walgreens", "Expedia",
]


def store_from_text(text: str):
    """Guess a store name if one is clearly mentioned in the text, else None."""
    if not text:
        return None
    low = text.lower()
    for store in _KNOWN_STORES:
        if store.lower() in low:
            return store
    return None
