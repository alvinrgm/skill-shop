# Add a client to ad-spend-monitor

~10 min per client. Most fields are auto-discoverable.

## Prerequisites

- Client already linked to your MCC (Google Ads) and/or your Business Manager (Meta)
- A Slack channel for the client (e.g. `#client-name`), if you want per-channel routing
- A budget sheet in Google Drive (only if the client has a monthly budget target)

## Steps

### 1. Find the IDs

**Google Ads customer ID:** the numeric account ID, no dashes (e.g. `1234567890`). Find it in the Google Ads UI, or list accounts under your MCC via the Google Ads API.

**Meta ad account ID:** the numeric account ID under your Business Manager, no `act_` prefix.

**Budget sheet ID:** open the sheet in Drive. The ID is the long string between `/d/` and `/edit` in the URL.
- Ensure sheet sharing is **"Anyone with the link → Viewer"** — the extractor uses the public gviz CSV endpoint. (If you can't make it public, a service-account fetch is a future upgrade — not yet implemented.)

### 2. Create the client config

Copy the roster template (default roster is `runtime/clients`; override with `AM_ROSTER_DIR`):

```bash
cp -r <package-root>/runtime/clients/_template <package-root>/runtime/clients/<slug>
```

Edit `runtime/clients/<slug>/account.md` and fill in the monitor's sections:

```markdown
## Config
- cid: <Google customer ID, no dashes>
- name: <Client display name>
- mcc: 0000000000                    # your agency's primary MCC; override only if the client is under a different MCC
- login_customer_id:                 # leave blank unless an override is needed
- timezone: America/New_York         # or wherever the client operates

## Stakeholders
- slack channel: #<channel name>

## Ad accounts (used by ad-spend-monitor)
- google_customer_id: <from step 1>
- meta_account_id: <from step 1, blank if you don't manage Meta>

## Budget tracking (used by ad-spend-monitor)
- budget_source: google_sheet        # or `none` if no monthly target
- budget_sheet_id: <from step 1>
- budget_extraction_hint: "Open the '<TAB NAME>' tab. Total monthly budget is in the row labeled '<ROW>' at the column matching the current month. IGNORE actual spend / % of budget / pacing rows — those are manually populated."
- budget_channel_split: per-channel  # or `combined` if one total budget is shared across channels

## Safety caps (used by ad-spend-monitor — optional)
- daily_google_max:                  # blank = rely on Layer 2 statistical guard
- daily_meta_max:                    # blank = rely on Layer 2
```

### 3. Smoke test

```bash
cd ad-spend-monitor
../.venv/bin/python monitor.py --client <slug>
```

Expected output:
```
→ <slug>
  google: yesterday=$X.XX  mtd=$X.XX  30d_avg=$X.XX  (history=31d)
  meta:   yesterday=$X.XX  mtd=$X.XX  30d_avg=$X.XX  (history=31d)
  google: 0 budget cap change(s) in last 24h
  → wrote <slug>-YYYY-MM.jsonl
```

Verify the JSONL record:
```bash
cat history/spend/<slug>-$(date +%Y-%m).jsonl | tail -1 | python3 -m json.tool
```

Should include:
- `accounts.google.yesterday` and/or `accounts.meta.yesterday` — non-zero unless the client truly didn't spend
- `budget` block with `meta_budget`, `google_budget`, `combined_budget`, `confidence ≥ 0.5` (if `budget_source: google_sheet`)
- `budget_changes` array (empty `[]` is fine; means no cap changes detected in the last 24h)

### 4. Done

The daily schedule picks it up automatically. Alerts route to `#<channel>` if you have a Slack bot token configured (see SETUP.md step 4), else to your fallback webhook with a `[<slug>]` prefix.

## Common issues

| Error | Cause | Fix |
|---|---|---|
| `invalid_grant: Bad Request` (Google) | OAuth refresh token expired | Re-mint the Google Ads refresh token (SETUP.md step 2) |
| `(#200) ads_management or ads_read permission` (Meta) | System user lacks access to this ad account | In Business Manager, add the ad account to the system user with "View performance" |
| Budget extractor returns `confidence: 0.0, source: none` | Sheet not publicly viewable, or tab name doesn't match the hint | Set sheet to "Anyone with the link → Viewer", or refine `budget_extraction_hint` |
| `CHANGE_DATE_RANGE_INFINITE` (Google Ads) | Should not occur — the cap-change query has both `>=` and `<=` date bounds. If it does, check `lib/fetchers/google.py:fetch_budget_changes` |
| Empty `by_day` from Google | Client hasn't spent in 31 days, or wrong customer_id | Verify the customer ID |
