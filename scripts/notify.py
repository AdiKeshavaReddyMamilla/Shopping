"""Send Telegram alerts for new deals — wishlist (⭐) items prioritized.

Credentials come from env vars (set as GitHub Secrets):
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
If unset, notifications are skipped gracefully.
"""
from __future__ import annotations

import os
import json
from urllib.request import Request, urlopen
from urllib.parse import urlencode

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_PER_RUN = 20


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
            return bool(json.loads(resp.read()).get("ok"))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Telegram send failed: {exc}")
        return False


def _format_deal(deal: dict) -> str:
    star = "⭐ " if deal.get("wishlist") else "🛍️ "
    title = _escape(deal.get("title", "Deal"))
    url = _escape(deal.get("url", ""))
    bits = []
    if deal.get("discount"):
        bits.append(f"{deal['discount']}% off")
    if deal.get("price") is not None:
        bits.append(f"${deal['price']:.2f}")
    if deal.get("store"):
        bits.append(deal["store"])
    bits.append(deal.get("source", ""))
    meta = " · ".join(b for b in bits if b)
    line = f'{star}<a href="{url}">{title}</a>'
    if meta:
        line += f"\n<i>{_escape(meta)}</i>"
    return line


def notify_new(new_alerts: list[dict]) -> int:
    """Alert on newly-seen candidates. Wishlist items sorted first."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("  · Telegram not configured (no token/chat id) — skipping alerts.")
        return 0
    if not new_alerts:
        print("  · No new deals to alert.")
        return 0

    ordered = sorted(new_alerts, key=lambda d: (not d.get("wishlist"), -d.get("score", 0)))
    batch = ordered[:MAX_PER_RUN]
    stars = sum(1 for d in batch if d.get("wishlist"))
    header = f"<b>🔔 {len(batch)} new deal(s) for you</b>"
    if stars:
        header += f"  · ⭐ {stars} from your list"
    body = "\n\n".join(_format_deal(d) for d in batch)
    ok = _send(token, chat_id, header + "\n\n" + body)
    extra = len(new_alerts) - len(batch)
    if extra > 0 and ok:
        _send(token, chat_id, f"…and {extra} more on your dashboard.")
    sent = len(batch) if ok else 0
    print(f"  · Telegram: alerted {sent} deal(s).")
    return sent
