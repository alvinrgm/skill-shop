# ad-spend-monitor

Daily watchdog for client ad spend. Checks every client's Meta + Google ad accounts once a day, posts Slack alerts (in the client's channel, or via a fallback webhook) if anything looks anomalous.

**Fresh setup:** `SETUP.md`
**Add a new client:** `ADD_CLIENT.md`

## What it watches (any one trips an alert)

1. **Layer 1 — Budget pacing.** Projected EOM > 102% of monthly budget (red), > 101% (yellow); or < 85% (red), < 90% (yellow). Only fires for clients with `budget_source: google_sheet`.
2. **Layer 2 — Day-over-day rate.** Yesterday's spend > 1.25× (yellow) / 2.0× (red) the trailing 30-day daily average. Fires for everyone.
3. **Layer 3 — Manual safety cap.** Yesterday's spend > `daily_{platform}_max`. Optional per-client hard ceiling.
4. **Layer 4 — Cap-change leading indicator.** Any campaign whose daily/lifetime budget cap was raised >50% / >25% in the last 24h (Google only in v1; Meta is a TODO).

## Client config

Reads from the client roster — by default `runtime/clients/{slug}/account.md` (override the roster location with the `AM_ROSTER_DIR` env var). Required sections:
- `## Ad accounts` — `google_customer_id`, `meta_account_id`
- `## Budget tracking` — `budget_source` (google_sheet | none), `budget_sheet_id`, `budget_extraction_hint`, `budget_channel_split`
- `## Safety caps` — `daily_google_max`, `daily_meta_max` (optional)
- `## Stakeholders` — `slack channel`

## Hard rule

Budget sheets are TARGET only. Actual spend, MTD, projected EOM, pacing — always computed by this code from ad platform APIs. Never trust calc'd cells in the sheet.

## Run

```bash
cd ad-spend-monitor
python monitor.py                                        # full daily run
python monitor.py --client example-brand --dry-run       # one client, no Slack send
```

Scheduled via launchd: `launchd/com.ad-spend-monitor.plist` (see "Install" below).

## Configuration (env)

Credentials and webhooks are read from the environment / the package `.env` — nothing is hardcoded.

| Variable | Powers | Notes |
|---|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` / `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET` / `GOOGLE_ADS_REFRESH_TOKEN` / `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Google Ads spend + cap-change fetch | Standard Google Ads API OAuth + your MCC login id. From the package `.env` or `GOOGLE_ADS_ENV`. |
| `META_ACCESS_TOKEN` | Meta Ads spend fetch | A long-lived System User token with `ads_read` across the accounts you monitor. From the package `.env`, `META_ENV`, or the environment. |
| `SLACK_BOT_TOKEN` | Per-channel alert routing (preferred) | `xoxb-…` bot token with `chat:write`; the bot must be invited to each client channel. Optional. |
| `SLACK_WEBHOOK` | Fallback alert delivery | Slack incoming-webhook URL. Used when no bot token (or no channel) is configured. `SLACK_WEBHOOK` / `SLACK_WEBHOOK` also accepted. |
| `AM_ROSTER_DIR` | Where client configs live | Defaults to `runtime/clients`. |

## Dependencies

- **Google Ads API** (OAuth) — daily spend + Layer 4 cap-change detection.
- **Meta Marketing API** (Graph API, direct token) — daily Meta spend.
- **Google Sheets** (public gviz CSV) — monthly budget target extraction (budget sheets must be "Anyone with the link → Viewer").
- **Slack** (bot token and/or incoming webhook) — alert delivery.
- Python libs: see the package `requirements.txt` (`google-ads`, `requests`).

## Layout

```
ad-spend-monitor/
├── README.md
├── monitor.py                    entry — daily loop
├── clients_loader.py             parses account.md sections
├── lib/
│   ├── fetchers/{meta,google}.py
│   ├── layers/{pacing,rate,caps,changes}.py
│   ├── budget_extractor.py
│   ├── slack.py
│   ├── health.py                 Google auth pre-flight
│   └── state.py                  history JSONL + suppression list
├── history/{spend,budgets,alerts}/   one JSONL/JSON per client per month
├── state/{slug}.json             active suppression list
└── launchd/com.ad-spend-monitor.plist
```

## Install (schedule a daily run)

The plist runs `monitor.py` once a day at a fixed local hour. Edit the placeholder paths in `launchd/com.ad-spend-monitor.plist` first (see comments in that file), then:

```bash
cp launchd/com.ad-spend-monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.ad-spend-monitor.plist
```

**Uninstall:**
```bash
launchctl unload ~/Library/LaunchAgents/com.ad-spend-monitor.plist
rm ~/Library/LaunchAgents/com.ad-spend-monitor.plist
```

**CAVEAT:** launchd only fires when the machine is awake. Asleep at run time = run skipped. For machine-closed reliability, port to GitHub Actions or a small always-on VM.
