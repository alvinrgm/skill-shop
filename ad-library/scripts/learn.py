#!/usr/bin/env python3
"""ad-library LEARN: keep a brand's creative learnings current. Read-only. Zero Figma calls.

usage: learn.py <brand> [--days 7] [--no-meta]

What it does, in order:
 1. Pulls every ad with lifetime spend from your Meta ad account (GET only, never writes)
                                                                   -> roadmap/meta_ads_all.json
 2. Maps every ad onto the angle tree (roadmap/angles.json: each sub-angle carries a `match`
    regex run against the ad NAME), KEEPING the verdicts already recorded  -> roadmap/tracker.json
    Status per sub-angle: greenfield (no ads) / light (under the light-test spend line) /
    tested / live (an ad is running now).
 3. Reads each launched batch over the last N days: spend, Meta-reported purchases, purchases
    per $1k against the batch's keep and kill lines. Batch ads are found by name: every ad whose
    name contains the batch's `ad_name_tag` (default: the batch id, e.g. "B01").
    This is a PROXY. Your keep/kill verdict comes from your own source of truth (your attribution
    tool's new-customer read, a matched-spend test), never from this number or from CTR.
 4. Writes learnings/refresh-<date>.md (what changed) and prints it.

It never edits Figma, traits.json verdicts, or an ad account. A verdict change is a PROPOSAL in
the refresh note. The Roadmap and Creative learnings pages are re-synced from these files in the
next interactive session (sync_payload.py, one use_figma call per page).

--no-meta: skip the pull and build the tracker from angles.json alone (every sub-angle
greenfield). Use it at onboarding, or if you do not want to connect Meta.

Env: META_ACCESS_TOKEN (a token with ads_read on YOUR ad account), META_AD_ACCOUNT_ID
(the number, with or without act_), optional META_GRAPH_VERSION (default v24.0).
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brand_dir  # noqa: E402

args = sys.argv[1:]
if args and args[0] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0)
if not args or args[0].startswith("-"):
    print(__doc__, file=sys.stderr)
    sys.exit(2)
LIB = brand_dir(args[0])
DAYS = int(args[args.index("--days") + 1]) if "--days" in args else 7
NO_META = "--no-meta" in args
state = json.loads((LIB / "state.json").read_text())
angles = json.loads((LIB / "roadmap/angles.json").read_text())
LIGHT = float(angles.get("thresholds", {}).get("light_below_spend", 500))
today = dt.date.today().isoformat()
GV = os.environ.get("META_GRAPH_VERSION", "v24.0")
TOK = os.environ.get("META_ACCESS_TOKEN", "").strip()
ACCT = (os.environ.get("META_AD_ACCOUNT_ID") or state.get("meta_ad_account_id") or "").strip()
ACCT = ACCT[4:] if ACCT.startswith("act_") else ACCT
lines, changes = [], []


def graph(path, params):
    params = dict(params, access_token=TOK)
    url = f"https://graph.facebook.com/{GV}/{path}?" + urllib.parse.urlencode(params)
    out = []
    while url:
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                j = json.load(r)
        except urllib.error.HTTPError as e:  # never print the URL: it carries the token
            try:
                msg = json.load(e).get("error", {}).get("message", "")[:200]
            except Exception:
                msg = ""
            sys.exit(f"Meta API error {e.code}: {msg}")
        out += j.get("data", [])
        url = j.get("paging", {}).get("next")
    return out


def purchases(a, names=("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase")):
    for n in names:  # priority-pick, never sum (the same purchase appears under several names)
        for x in a.get("actions", []) or []:
            if x.get("action_type") == n:
                return float(x["value"])
    return 0.0


# ------------------------------------------------------------------ 1: pull
ads = []
if not NO_META:
    if not (TOK and ACCT):
        sys.exit("META_ACCESS_TOKEN and META_AD_ACCOUNT_ID are needed for the Meta pull "
                 "(see SETUP.md), or pass --no-meta.")
    ins = graph(f"act_{ACCT}/insights", {"level": "ad", "fields": "ad_id,ad_name,spend",
                                         "date_preset": "maximum", "limit": 500})
    meta = {a["id"]: a for a in graph(f"act_{ACCT}/ads", {
        "fields": "id,effective_status,created_time", "limit": 500,
        "filtering": json.dumps([{"field": "ad.effective_status", "operator": "IN", "value":
                                  ["ACTIVE", "PAUSED", "ARCHIVED", "CAMPAIGN_PAUSED", "ADSET_PAUSED",
                                   "WITH_ISSUES", "IN_PROCESS", "DISAPPROVED", "PENDING_REVIEW"]}])})}
    ads = [{"id": r["ad_id"], "name": r["ad_name"],
            "created": (meta.get(r["ad_id"], {}).get("created_time") or "")[:10] or None,
            "status": meta.get(r["ad_id"], {}).get("effective_status", "UNKNOWN"),
            "spend": round(float(r["spend"]), 2)}
           for r in ins if float(r.get("spend", 0)) > 0]
    (LIB / "roadmap/meta_ads_all.json").write_text(json.dumps(ads, indent=1))

# ------------------------------------------------------------------ 2: map onto the angle tree
tp = LIB / "roadmap/tracker.json"
old = json.loads(tp.read_text()) if tp.exists() else {"subs": [], "unmapped": []}
keep = {s["id"]: {k: s.get(k) for k in ("verdict", "verdict_note")} for s in old["subs"]}
subs, mapped = [], set()
for ang in angles.get("angles", []):
    for sub in ang.get("subs", []):
        rx = re.compile(sub["match"], re.I) if sub.get("match") else None
        hit = [a for a in ads if rx and rx.search(a["name"])]
        mapped |= {a["id"] for a in hit}
        spend = round(sum(a["spend"] for a in hit), 2)
        status = ("greenfield" if not hit else "live" if any(a["status"] == "ACTIVE" for a in hit)
                  else "light" if spend < LIGHT else "tested")
        top = sorted(hit, key=lambda a: -a["spend"])[:5]
        row = {"id": sub["id"], "name": sub["name"], "angle": ang["id"], "status": status,
               "verdict": None, "verdict_note": None, "spend": spend, "creatives": len(hit),
               "top": [{"name": a["name"], "spend": a["spend"]} for a in top]}
        row.update({k: v for k, v in keep.get(sub["id"], {}).items() if v})
        subs.append(row)
unmapped = sorted([[a["spend"], a["name"]] for a in ads if a["id"] not in mapped], reverse=True)
new = {"generated": today, "n_ads": len(ads),
       "source": "angles.json only (--no-meta)" if NO_META else f"Meta ads, all time ({len(ads)} with spend)",
       "subs": subs, "unmapped": unmapped}
tp.write_text(json.dumps(new, indent=1))
o = {s["id"]: s for s in old["subs"]}
for s in subs:
    p = o.get(s["id"], {})
    if p and p.get("status") != s["status"]:
        changes.append(f"{s['id']} {s['name']}: {p.get('status')} -> {s['status']}")
    d = s["spend"] - (p.get("spend") or 0)
    if p and d >= 250:
        changes.append(f"{s['id']} {s['name']}: +${d:,.0f} spend since last refresh")
old_un = {x[1] for x in old.get("unmapped", [])}
new_un = [n for _, n in unmapped if n not in old_un]
lines.append(f"Tracker: {len(ads)} ads with spend mapped onto {len(subs)} sub-angles. {len(changes)} changes. "
             f"{len(unmapped)} ads fit no sub-angle" + (f" ({len(new_un)} new, e.g. {new_un[0]})." if new_un else "."))

# ------------------------------------------------------------------ 3: batch reads
batch_lines = []
for bid, b in (state.get("batches") or {}).items():
    if not b.get("launched"):
        batch_lines.append(f"{bid}: not launched yet (set batches.{bid}.launched = true once the ads run).")
        continue
    if NO_META:
        continue
    tag = b.get("ad_name_tag") or bid
    since = (dt.date.today() - dt.timedelta(days=DAYS)).isoformat()
    rows = graph(f"act_{ACCT}/insights", {
        "level": "ad", "fields": "ad_id,ad_name,spend,actions", "limit": 200,
        "time_range": json.dumps({"since": since, "until": today}),
        "filtering": json.dumps([{"field": "ad.name", "operator": "CONTAIN", "value": tag}])})
    if not rows:
        batch_lines.append(f"{bid}: no spend in the last {DAYS} days on ads named with '{tag}'.")
    for r in rows:
        sp = float(r["spend"])
        pu = purchases(r)
        per = pu / sp * 1000 if sp else 0
        kill, keepbar = b.get("kill_below", 0), b.get("keep_at", 0)
        flag = ("too early" if sp < b.get("read_after_spend", 0) else
                "on track" if keepbar and per >= keepbar else
                "kill zone" if per < kill else "middle")
        batch_lines.append(f"{bid} {r['ad_name']}: ${sp:,.0f} last {DAYS}d, {pu:.0f} Meta purchases, "
                           f"{per:.1f} per $1k ({flag}; a proxy, your own read decides).")

# ------------------------------------------------------------------ 4: write + report
note = [f"# Learnings refresh · {state.get('brand_name', args[0])} · {today}", "", *lines, ""]
if changes:
    note += ["## Tracker changes", *[f"- {c}" for c in changes], ""]
if batch_lines:
    note += ["## Batch tests", *[f"- {c}" for c in batch_lines], ""]
if unmapped[:10]:
    note += ["## Biggest ads that fit no sub-angle (add a sub-angle or widen a `match`)",
             *[f"- ${sp:,.0f} {n}" for sp, n in unmapped[:10]], ""]
note += ["Verdicts in traits.json and the tracker were NOT changed. Change a verdict only on evidence",
         "(your attribution read or a finished batch test), then re-sync the Roadmap and Creative",
         "learnings pages in Figma."]
(LIB / "learnings").mkdir(exist_ok=True)
out = LIB / "learnings" / f"refresh-{today}.md"
out.write_text("\n".join(note) + "\n")
print("\n".join(note))
print(f"\nwrote {out}")
