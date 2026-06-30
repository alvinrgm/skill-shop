#!/usr/bin/env python3
"""weekly-report orchestrator CLI — the deterministic half of Module B.

The JUDGMENT half (reading the data, writing the BLUF observations + next
steps + action items) is done by Claude at skill-run time and handed to this
script as a payload JSON. This script does the deterministic, riskier work:
freshness gate, deck prepend (additive, verified, rollback), notify, audit.

Subcommands:
  check  <client>                          freshness gate — exit 0 if fresh
  append <client> --payload P.json [opts]  prepend a period block into the deck
  roster                                   list reporting-configured clients

append options:
  --staging      operate on a COPY of the deck (safe preview); prints copy URL
  --no-notify    skip the Slack DM
  --insert-index N   override the configured insert index
"""
import argparse
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lib import clients, sheets_data, deck, slack, audit, bridge, context  # noqa: E402


def cmd_check(args):
    cfg = clients.load(args.client)
    ok, issues, reports = sheets_data.check_client(cfg)
    for r in reports:
        print(f"  {r['name']}: {r['age_days']}d old, tabs={[t['title'] for t in r['tabs']]}")
    if ok:
        print(f"FRESH — {cfg['name']} data within {cfg['freshness_sla_days']}d SLA")
        return 0
    print("STALE:\n  " + "\n  ".join(issues))
    return 2


def cmd_append(args):
    cfg = clients.load(args.client)
    with open(args.payload) as f:
        payload = json.load(f)
    if not cfg.get("deck_id"):
        print(f"ERROR: {cfg['slug']} has no deck_id in account.md (## AM reporting). "
              f"Create the reporting deck first, then add deck_id.")
        return 2

    deck_id = cfg["deck_id"]
    insert_index = args.insert_index if args.insert_index is not None else cfg["deck_insert_index"]

    if args.staging:
        copy = bridge.copy_file(deck_id, f"STAGING — {cfg['name']} weekly ({payload.get('period_label','')})")
        deck_id = copy["newFileId"]
        print(f"staging copy: {copy['url']}")

    res = deck.prepend_period(deck_id, payload, insert_index=insert_index)
    audit.log("deck_append", client=cfg["slug"], staging=args.staging,
              deck_id=deck_id, slides_added=res["slides_added"], url=res["url"])
    print(json.dumps(res, indent=2))

    # BLUF for the notification = first observation title, else divider
    obs = (payload.get("observations") or [])
    bluf = obs[0]["title"] if obs else payload.get("period_label", "")
    n_actions = len(payload.get("action_items") or [])
    if not args.no_notify and not args.staging:   # staging never DMs you
        msg = (f":bar_chart: *{cfg['name']} weekly deck updated*\n"
               f"BLUF: {bluf}\n"
               f"{res['slides_added']} slides added · {n_actions} action items\n"
               f"{res['url']}\n"
               f"_Review before sending to the client._")
        code = slack.notify(msg)
        audit.log("deck_notify", client=cfg["slug"], http=code)
        print(f"notify -> {code}")
    return 0


def cmd_thumbnail(args):
    import urllib.request
    ids = bridge.slide_object_ids(args.deck_id)
    if args.slide >= len(ids):
        print(f"deck has {len(ids)} slides; slide {args.slide} out of range")
        return 2
    b = bridge.gapi("slides", f"/v1/presentations/{args.deck_id}/pages/{ids[args.slide]}/thumbnail",
                    query={"thumbnailProperties.mimeType": "PNG",
                           "thumbnailProperties.thumbnailSize": "MEDIUM"})
    out = args.out or f"/tmp/deck_{args.deck_id[:8]}_s{args.slide}.png"
    urllib.request.urlretrieve(b["contentUrl"], out)
    print(out)
    return 0


def cmd_rm_staging(args):
    r = bridge.call("delete_file", fileId=args.deck_id, permanent=args.permanent)
    print(r)
    return 0


def cmd_context(args):
    print(context.render(args.client))
    return 0


def cmd_roster(args):
    for c in clients.roster():
        print(f"  {c['slug']:18s} deck={'yes' if c['deck_id'] else 'NO ':3s} "
              f"metric={c['headline_metric']:12s} split={c['observation_split']:9s} "
              f"window={c['comparison_window']}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="weekly_report")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("client"); c.set_defaults(fn=cmd_check)
    a = sub.add_parser("append"); a.add_argument("client")
    a.add_argument("--payload", required=True)
    a.add_argument("--staging", action="store_true")
    a.add_argument("--no-notify", action="store_true")
    a.add_argument("--insert-index", type=int, default=None)
    a.set_defaults(fn=cmd_append)
    r = sub.add_parser("roster"); r.set_defaults(fn=cmd_roster)
    cx = sub.add_parser("context"); cx.add_argument("client"); cx.set_defaults(fn=cmd_context)
    t = sub.add_parser("thumbnail"); t.add_argument("deck_id")
    t.add_argument("--slide", type=int, default=1); t.add_argument("--out", default=None)
    t.set_defaults(fn=cmd_thumbnail)
    rm = sub.add_parser("rm-staging"); rm.add_argument("deck_id")
    rm.add_argument("--permanent", action="store_true"); rm.set_defaults(fn=cmd_rm_staging)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
