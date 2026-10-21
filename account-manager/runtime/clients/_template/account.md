# {Client Name} — Account

> **Operating objective**: maximize conversion value (revenue) subject to a ROAS floor. ROAS is a constraint, not a target. The action queue scales winners until they approach the floor and cuts/fixes campaigns that fall below it.

## Config
- cid: 0000000000
- name: Client Name
- mcc: 0000000000
- login_customer_id:               # set ONLY if account is under a different MCC than your agency's primary
- timezone: America/New_York  # your account's tz
- currency: USD
- brand_terms: [brandname, alt-spelling]
- vertical: e-commerce / saas / etc
- monthly_budget: $0
- roas_floor: 2.0                  # constraint — below this, campaigns must be fixed or cut. Default 2.0; override per-client when margin profile is known.
- target_aov: $0                   # informational, used for context not optimization
- primary_kpi: conv_value          # what we maximize
- channels: [SEARCH, SHOPPING, PMAX, DEMAND_GEN]
- key_categories: []

## Stakeholders
- account manager:
- strategist:
- client contact:
- slack channel:

## Ad accounts (used by ad-spend-monitor)
- google_customer_id:                        # numeric CID, no dashes — same as `cid` above
- meta_account_id:                           # Meta act_xxx ID, numeric only (no "act_" prefix). Blank if we don't manage Meta.

## Budget tracking (used by ad-spend-monitor)
- budget_source: none                        # one of: google_sheet | none
- budget_sheet_id:                           # Google Sheet ID (the long string between /d/ and /edit in the URL)
- budget_extraction_hint:                    # one-line nudge for the LLM extractor — which tab, which row/cell
- budget_channel_split: combined             # combined | per-channel — does the budget split Meta vs Google or is it one total?

## Safety caps (used by ad-spend-monitor — optional)
- daily_google_max:                          # hard $ ceiling per day on Google. Blank = rely on Layer 2 statistical guard.
- daily_meta_max:                            # hard $ ceiling per day on Meta. Blank = rely on Layer 2.

## Notes
{Anything that's true about this account that doesn't change week-to-week.}
