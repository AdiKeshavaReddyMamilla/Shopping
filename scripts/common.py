"""Shared helpers: paths, config loading, small utilities."""
from __future__ import annotations

import os
import re
import hashlib
from pathlib import Path

import yaml

# Repo root = one level up from this scripts/ directory.
ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
STATE = ROOT / "state"
SEEN_FILE = STATE / "seen.json"


def load_yaml(name: str) -> dict:
    """Load a YAML config file from the repo root (e.g. 'watchlist.yaml')."""
    path = ROOT / name
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def deal_id(url: str, title: str) -> str:
    """Stable id for a deal, used for de-duplication across runs."""
    basis = (url or "").strip().lower() or (title or "").strip().lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


_PRICE_RE = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_PCT_RE = re.compile(r"(\d{1,3})\s?%\s?(?:off|discount)", re.IGNORECASE)


def extract_price(text: str):
    """Best-effort: pull the first dollar price out of a title. Returns float or None."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def extract_discount(text: str):
    """Best-effort: pull a 'NN% off' discount out of a title. Returns int or None."""
    if not text:
        return None
    m = _PCT_RE.search(text)
    if not m:
        return None
    try:
        pct = int(m.group(1))
        return pct if 0 < pct <= 100 else None
    except ValueError:
        return None


def clean_text(text: str) -> str:
    """Strip HTML tags and collapse whitespace from a feed snippet."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()
