# 🛍️ My Deals & Coupons Hub

One place to check the **best deals** and **coupon codes** before you buy —
across shoes, dresses, movies, food delivery (DoorDash / Uber Eats / Grubhub),
electronics, and more. It runs **entirely on GitHub** (no laptop, no server, no
cost) and comes in two parts:

- **A website** (GitHub Pages) you open on your iPad to browse deals & coupons.
- **A Telegram bot** that pings you when a new deal matches your watchlist.

A scheduled GitHub Action refreshes everything every few hours automatically.

---

## How it works

```
GitHub Action (every 4h, or press "Run workflow")
  → pulls free public deal feeds (Slickdeals, Reddit, DealNews)
  → filters them to YOUR watchlist (watchlist.yaml)
  → rebuilds the website (docs/) and pushes it to GitHub Pages
  → sends a Telegram alert for anything new that matches
```

You control what shows up by editing three files — right here on GitHub from
your iPad (tap a file → the ✏️ pencil → Commit):

| File | What it does |
|------|--------------|
| `watchlist.yaml` | Your interests + keywords + minimum discount. **The main one.** |
| `coupons.yaml`   | Your personal list of coupon codes (shown on the Coupons tab). |
| `sources.yaml`   | Which deal feeds to pull from (already filled in). |

---

## One-time setup (about 5 minutes, all doable on iPad)

### 1. Turn on the website (GitHub Pages)
1. Go to this repo's **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Branch: **`claude/shopping-deals-coupons-bot-sfncbm`**, folder: **`/docs`**. Save.
4. After the first workflow run, your site is live at:
   `https://<your-username>.github.io/<repo-name>/`
   (GitHub shows the exact link on that Pages settings page.)

### 2. Turn on Telegram alerts
1. In Telegram, open a chat with **@BotFather**.
2. Send `/newbot`, pick a name and a username. BotFather replies with a
   **token** that looks like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxx`. Copy it.
3. Get your **chat id**: open a chat with **@userinfobot** and send any message —
   it replies with your numeric **Id**. (That's your `TELEGRAM_CHAT_ID`.)
4. **Send your new bot a “hi” message first** (a bot can't message you until you
   message it once).
5. In this repo, go to **Settings → Secrets and variables → Actions →
   New repository secret** and add **two** secrets:
   - `TELEGRAM_BOT_TOKEN` → the token from step 2
   - `TELEGRAM_CHAT_ID` → the id from step 3

That's it. If you skip this section, the website still works — you just won't get
Telegram alerts.

### 3. Run it once
Go to the **Actions** tab → **Update deals & coupons** → **Run workflow**.
When it finishes it will have built your dashboard and (if configured) sent your
first Telegram alert.

---

## Everyday use

- **Check before you buy:** open your Pages URL, browse the **Best Deals** and
  **Coupons** tabs, search, and filter by category.
- **Change what you track:** edit `watchlist.yaml` (add keywords, new categories,
  or change `min_discount_percent`). Saving it triggers a rebuild automatically.
- **Add a coupon you found:** add an entry to `coupons.yaml`. Expired ones hide
  themselves.
- **Refresh right now:** Actions tab → Run workflow.

### Editing the watchlist — quick reference
```yaml
min_discount_percent: 20        # hide weak deals; 0 = show everything
categories:
  shoes:   [nike, adidas, sneakers, running shoes]
  dresses: [dress, gown, maxi dress]
  # add your own category: [keyword1, keyword2, ...]
```

---

## Honest notes / limits

- **No live store APIs.** Amazon, DoorDash, Uber Eats, and Grubhub don't offer
  free public deal feeds, and scraping them is fragile and against their terms.
  So deals come from public **deal communities** that re-post those bargains and
  promo codes. You'll catch a lot — just not literally every store's live prices.
- **Coupons are curated by you** (in `coupons.yaml`) rather than scraped, because
  scraped coupon codes are usually dead within days. The starter list has
  examples — replace them with real codes as you find them.
- **Public repo** is required for free Pages + unlimited Actions. No secrets live
  in the code — your Telegram token stays in GitHub Secrets. The site only shows
  public deal info.

---

## Project layout

```
watchlist.yaml            your interests (edit this)
coupons.yaml              your coupon codes (edit this)
sources.yaml              deal feeds (prefilled)
requirements.txt          python deps
scripts/
  main.py                 orchestrator (fetch → filter → notify → build)
  fetch.py                pulls & normalizes feeds
  filter.py               watchlist matching, ranking, de-dupe
  build.py                generates the website
  notify.py               Telegram alerts
  common.py               shared helpers
  templates/index.html.jinja   the dashboard UI
docs/                     the generated website (served by GitHub Pages)
state/seen.json           remembers alerted deals (no duplicate pings)
.github/workflows/update.yml   the scheduler
```

## Run locally (optional — not needed on iPad)
```bash
pip install -r requirements.txt
python scripts/main.py --no-notify   # build the site without sending alerts
open docs/index.html
```
