"""Extract fresh promo codes from coupon-oriented feed posts.

Honest by design: we surface community-posted codes with the post's date and
source so you can judge freshness, and pair them with the store's official
coupon page in the UI. We do not claim any code is verified/working.
"""
from __future__ import annotations

import re

from common import store_from_text

# "code: SAVE20", "use code SAVE20", "promo code SAVE20", "coupon SAVE20"
_LABELLED = re.compile(
    r"(?:promo\s*code|coupon\s*code|coupon|code|use\s*code|use)\s*[:\-]?\s*"
    r"([A-Z0-9][A-Z0-9\-]{3,14})",
    re.IGNORECASE,
)
# Standalone code-looking token: has letters AND digits, 4-15 chars, caps-ish.
_STANDALONE = re.compile(r"\b([A-Z0-9]{4,15})\b")

_STOPWORDS = {
    "FREE", "SALE", "DEAL", "DEALS", "CODE", "CODES", "SAVE", "OFF", "SHIP",
    "SHIPPING", "ONLY", "TODAY", "NEW", "GIFT", "CARD", "HTTP", "HTTPS", "WWW",
    "COM", "USD", "AMAZON", "REDDIT", "PROMO", "COUPON", "ORDER", "ITEMS",
}


def _looks_like_code(tok: str) -> bool:
    if tok in _STOPWORDS:
        return False
    has_digit = any(c.isdigit() for c in tok)
    has_alpha = any(c.isalpha() for c in tok)
    # Accept mixed alnum codes, or clearly promo-caps tokens with a digit.
    return has_alpha and (has_digit or (tok.isupper() and len(tok) >= 5))


def extract_codes(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for m in _LABELLED.finditer(text):
        c = m.group(1).upper()
        if _looks_like_code(c):
            found.append(c)
    if not found:  # only fall back to loose matching when nothing labelled
        for m in _STANDALONE.finditer(text):
            c = m.group(1).upper()
            if _looks_like_code(c):
                found.append(c)
    # de-dupe, preserve order, cap
    seen, out = set(), []
    for c in found:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:3]


def build_live_coupons(items: list[dict], limit: int = 80) -> list[dict]:
    """From coupon-role feed items, produce dated coupon entries with codes."""
    out: list[dict] = []
    for it in items:
        if it.get("role") != "coupons":
            continue
        text = f"{it.get('title','')} {it.get('summary','')}"
        codes = extract_codes(text)
        if not codes:
            continue
        out.append(
            {
                "store": it.get("store") or store_from_text(text) or "",
                "codes": codes,
                "title": it.get("title", ""),
                "url": it.get("url", ""),
                "source": it.get("source", ""),
                "posted_at": it.get("posted_at", ""),
            }
        )
    # newest first
    out.sort(key=lambda c: c.get("posted_at", ""), reverse=True)
    print(f"  · Extracted {len(out)} live coupon posts with codes.")
    return out[:limit]
