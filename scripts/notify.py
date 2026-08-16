"""Send Telegram alerts for new deals (and an optional daily digest).

Reads credentials from environment variables (set as GitHub Secrets):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

If those aren't set, notifications are skipped gracefully (e.g. during a
local/dry-run) so the rest of the pipeline still works.
"""
from __future__ import annotations

import os
import json
from urllib.request import Request, urlopen
from urllib.parse import urlencode

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_PER_RUN = 15  # don't flood on the first run / big batches


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _send(token: str, chat_id: str, text: str) -> bool:
    data = urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        }
    ).encode("utf-8")
    req = Request(TELEGRAM_API.format(token=token), data=data)
    try:
        with urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())
            return bool(payload.get("ok"))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Telegram send failed: {exc}")
        return False


def _format_deal(deal: dict) -> str:
    title = _escape(deal.get("title", "Deal"))
    url = deal.get("url", "")
    cats = ", ".join(deal.get("categories", []))
    bits = []
    if deal.get("discount"):
        bits.append(f"{deal['discount']}% off")
    if deal.get("price") is not None:
        bits.append(f"${deal['price']:.2f}")
    bits.append(deal.get("source", ""))
    meta = " · ".join(b for b in bits if b)
    line = f"🛍️ <a href=\"{_escape(url)}\">{title}</a>"
    if meta:
        line += f"\n<i>{_escape(meta)}</i>"
    if cats:
        line += f"  #{_escape(cats.replace(', ', ' #'))}"
    return line


def notify_new(new_deals: list[dict]) -> int:
    """Send an alert message for newly-seen matching deals. Returns count sent."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("  · Telegram not configured (no token/chat id) — skipping alerts.")
        return 0
    if not new_deals:
        print("  · No new deals to alert.")
        return 0

    batch = new_deals[:MAX_PER_RUN]
    header = f"<b>🔥 {len(batch)} new deal(s) match your watchlist</b>\n"
    body = "\n\n".join(_format_deal(d) for d in batch)
    ok = _send(token, chat_id, header + "\n" + body)
    extra = len(new_deals) - len(batch)
    if extra > 0 and ok:
        _send(token, chat_id, f"…and {extra} more on your dashboard.")
    sent = len(batch) if ok else 0
    print(f"  · Telegram: alerted {sent} deal(s).")
    return sent
