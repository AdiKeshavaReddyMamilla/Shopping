"""Generate the static dashboard: docs/data.json and docs/index.html."""
from __future__ import annotations

import json
from datetime import datetime, timezone, date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from common import DOCS, time_ago

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _active_coupons(coupons_cfg: dict) -> list[dict]:
    """Drop expired personal coupons; keep the rest in file order."""
    today = date.today()
    out = []
    for c in coupons_cfg.get("coupons", []):
        exp = c.get("expires")
        if exp:
            try:
                if datetime.strptime(str(exp), "%Y-%m-%d").date() < today:
                    continue
            except ValueError:
                pass
        out.append(c)
    return out


def _dedupe_stores(stores_cfg: dict) -> list[dict]:
    seen, out = set(), []
    for s in stores_cfg.get("stores", []):
        key = (s.get("name", "").lower(), s.get("domain", "").lower())
        if key in seen or not s.get("domain"):
            continue
        seen.add(key)
        out.append(s)
    out.sort(key=lambda s: s.get("name", "").lower())
    return out


def build_site(
    deals: list[dict],
    live_coupons: list[dict],
    coupons_cfg: dict,
    stores_cfg: dict,
    watchlist: dict,
) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    # add human 'time ago' to deals + live coupons
    for d in deals:
        d["ago"] = time_ago(d.get("posted_at", ""))
    for c in live_coupons:
        c["ago"] = time_ago(c.get("posted_at", ""))

    stores = _dedupe_stores(stores_cfg)
    my_coupons = _active_coupons(coupons_cfg)
    categories = sorted(watchlist.get("categories", {}).keys())
    sources = sorted({d.get("source", "") for d in deals if d.get("source")})
    store_cats = sorted({s.get("category", "") for s in stores if s.get("category")})
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    wishlist_deals = [d for d in deals if d.get("wishlist")]

    data = {
        "updated": updated,
        "deals": deals,
        "wishlist_deals": wishlist_deals,
        "live_coupons": live_coupons,
        "my_coupons": my_coupons,
        "stores": stores,
        "categories": categories,
        "store_categories": store_cats,
        "sources": sources,
        "stats": {
            "deals": len(deals),
            "coupons": len(live_coupons) + len(my_coupons),
            "stores": len(stores),
            "wishlist": len(wishlist_deals),
        },
    }

    with open(DOCS / "data.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.jinja")
    data_embed = json.dumps(data, ensure_ascii=False, default=str).replace(
        "<", "\\u003c"
    )
    html = template.render(stats=data["stats"], updated=updated, data_json=data_embed)
    with open(DOCS / "index.html", "w", encoding="utf-8") as fh:
        fh.write(html)

    (DOCS / ".nojekyll").touch()
    print(
        f"Built dashboard: {len(deals)} deals, "
        f"{len(live_coupons)} live coupons, {len(my_coupons)} personal, "
        f"{len(stores)} stores, {len(wishlist_deals)} wishlist hits."
    )
