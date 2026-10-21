# Setup

Step-by-step for getting ad-spend-monitor running. Paths below are relative to the **package root** (the directory that contains the `ad-spend-monitor/` folder).

## 1. Python environment

```bash
cd <package-root>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # includes google-ads + requests
```

## 2. Google Ads OAuth

The monitor reads Google Ads credentials from the package `.env` (or the file at `GOOGLE_ADS_ENV`). Copy `runtime/.env.example` to `.env` if you haven't, and fill in:

```
GOOGLE_ADS_DEVELOPER_TOKEN=<from Google Ads → API Center>
GOOGLE_ADS_CLIENT_ID=<from Google Cloud Console OAuth client>
GOOGLE_ADS_CLIENT_SECRET=<same>
GOOGLE_ADS_REFRESH_TOKEN=<minted in the next step>
GOOGLE_ADS_LOGIN_CUSTOMER_ID=0000000000   # your MCC / manager account, no dashes
```

Mint a refresh token using any standard Google Ads API OAuth flow (e.g. the official `generate_user_credentials` helper from the google-ads Python client). Sign in with the Google account that owns the MCC, grant the AdWords scope, and write the resulting refresh token into `.env`.

## 3. Meta system user token

In Meta Business Manager (business.facebook.com):
1. **Business Settings → Users → System Users** → Add → name it `Ad Spend Watchdog`, role `Employee`
2. **Add assets** → Apps → Marketing API → Full control
3. **Add assets** → Ad Accounts → pick every client account you want monitored → grant "View performance"
4. **Generate Token** → app: Marketing API → scope: `ads_read` → never expires
5. Copy the token

Save it to the package `.env` (or `ad-spend-monitor/.env`):
```
META_ACCESS_TOKEN=<paste>
```
Then `chmod 600` whichever env file holds it.

## 4. Slack delivery

Two options (you can do both — the bot token takes priority when a channel is set):

**A. Per-channel bot (preferred).** Alerts post in each client's Slack channel.
1. api.slack.com/apps → your app → OAuth & Permissions → add `chat:write` scope → reinstall workspace
2. Copy the Bot User OAuth Token (`xoxb-…`)
3. Add to `.env`: `SLACK_BOT_TOKEN=xoxb-...`
4. Invite the bot into each client channel

**B. Fallback webhook.** Used when no bot token (or no channel) is configured; posts to wherever the webhook is bound.
1. Create a Slack incoming webhook (api.slack.com/messaging/webhooks)
2. Add to `.env`: `SLACK_WEBHOOK=https://hooks.slack.com/services/...`

## 5. Daily schedule via launchd

Edit `launchd/com.ad-spend-monitor.plist` and replace every `__PACKAGE_DIR__` with the absolute path to the package root, and the python path with your venv's interpreter. Then:

```bash
cp launchd/com.ad-spend-monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.ad-spend-monitor.plist
launchctl list | grep ad-spend-monitor
```

The plist runs once a day at the `Hour` set inside it (local time). Change that integer to pick a different hour.

**Caveat:** launchd skips runs when the machine is asleep. For machine-closed reliability, port to GitHub Actions or a small always-on VM.

## 6. Smoke test

```bash
cd ad-spend-monitor
../.venv/bin/python monitor.py --client example-brand --skip-meta
```

Should print yesterday/MTD/30d-avg numbers and write a row to `history/spend/example-brand-<YYYY-MM>.jsonl`. If it errors on `invalid_grant`, your Google Ads refresh token expired — redo step 2.

## Per-client onboarding

After setup, see `ADD_CLIENT.md` to register each client you want monitored.
