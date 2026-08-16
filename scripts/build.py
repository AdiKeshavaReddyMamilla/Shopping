"""Generate the static dashboard: docs/data.json and docs/index.html."""
from __future__ import annotations

import json
from datetime import datetime, timezone, date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from common import DOCS

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _active_coupons(coupons_cfg: dict) -> list[dict]:
    """Drop expired coupons; keep the rest in file order."""
    today = date.today()
    out = []
    for c in coupons_cfg.get("coupons", []):
        exp = c.get("expires")
        if exp:
            try:
                if datetime.strptime(str(exp), "%Y-%m-%d").date() < today:
                    continue  # expired
            except ValueError:
                pass  # unparseable date -> keep it, don't lose a coupon
        out.append(c)
    return out


def build_site(deals: list[dict], coupons_cfg: dict, watchlist: dict) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    coupons = _active_coupons(coupons_cfg)
    categories = sorted(watchlist.get("categories", {}).keys())
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    data = {
        "updated": updated,
        "deals": deals,
        "coupons": coupons,
        "categories": categories,
    }

    # Machine-readable data (the page fetches this; also handy for other tools).
    with open(DOCS / "data.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)

    # Render the dashboard. Data is embedded so the page works even when
    # opened directly (no fetch/CORS needed), and data.json stays available.
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.jinja")
    # Escape '<' so a deal title containing '</script>' can't break the embed.
    data_embed = json.dumps(data, ensure_ascii=False, default=str).replace(
        "<", "\\u003c"
    )
    html = template.render(
        updated=updated,
        deals=deals,
        coupons=coupons,
        categories=categories,
        data_json=data_embed,
    )
    with open(DOCS / "index.html", "w", encoding="utf-8") as fh:
        fh.write(html)

    # Ensure GitHub Pages serves the folder as-is (no Jekyll processing).
    (DOCS / ".nojekyll").touch()

    print(f"Built dashboard: {len(deals)} deals, {len(coupons)} coupons.")
