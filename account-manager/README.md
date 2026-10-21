# AI Account Manager

A **recommend-only AI account manager** for paid-media agencies, built as [Claude Code](https://claude.com/claude-code) skills.

It does the standing work of a paid-media account manager — weekly client reporting, account
optimization analysis, creative teardowns, strategy upkeep — and stops at your desk for review.
It **never** messages a client or changes an ad account unattended. Every output is a draft or a
recommendation; you approve and execute.

```
weekly data  ──►  BLUF/Minto analysis  ──►  live Slides deck (in place)  ──►  Slack DM to you
                  account-ops queue                                           (review → you act)
                  creative-intel
```

## What it does (6 skills)
| Skill | Does |
|-------|------|
| **weekly-report** | Pulls the week's ad data, writes a BLUF analysis, prepends a house-style period block into the client's LIVE reporting deck (additive, never rebuilds), DMs you to review. |
| **weekly-am-cycle** | The full recurring weekly cycle orchestrator — context → serving/freshness checks → data → analysis → deck → memory → DM. Scheduled or run by hand. |
| **account-ops** | Google account-ops recommender: a prioritized scale/cut/fix/test action queue scored against "maximize conversion value subject to a ROAS floor," filtered through the client's strategy refusals. |
| **creative-intel** | Meta creative intelligence: per-second video CV → retention alignment → cross-video regression → proposed A/B experiments. Honest about correlation vs causation. |
| **meta-ops** | Full Meta account audit across 7 dimensions (structure, audiences, bidding, placements, measurement, signals, creative) scored against a rubric + opportunity score + strategy. |
| **strategy-review** | The living strategy/positioning spine: BACKFILL from history, weekly DRIFT checks, quarterly QBR. The layer the reporting + creative work operates against. |

Plus **ad-spend-monitor** — a daily Google + Meta spend anomaly monitor (4 layers: pacing, rate,
hard caps, cap-change) that alerts you when a client's spend goes sideways.

## Install
New here? Skim **[onboarding-deck.pdf](onboarding-deck.pdf)** (7-slide visual walkthrough) first.

See **[SETUP.md](SETUP.md)** — there's a one-paste install block at the top that hands the whole
setup to Claude Code, plus a manual fallback. TL;DR:

```bash
git clone --depth 1 <REPO-URL> skill-shop && cd skill-shop/account-manager
pip install -r requirements.txt
cp -R skills/* ~/.claude/skills/
cp runtime/.env.example runtime/.env     # fill it in
bash doctor.sh                            # tells you exactly what's left
```

## Build-your-own-infra
This was extracted from one operator's private stack, so anything you wouldn't already have is
shipped as **either vendored code or a setup process** — never a dependency on someone else's
accounts:
- **Deck engine** (`deck-engine/`) — vendored, runs locally.
- **The Slides/Docs bridge** (`bridge/`) — you deploy your own tiny Apps Script web app (it runs as
  your Google account). Walkthrough in [`bridge/SETUP.md`](bridge/SETUP.md).
- **Client roster** (`runtime/clients/`) — you create your own from the commented `_template`.
- **Data sources + API keys** — bring your own (Google Ads, Meta, Triple Whale, Gemini); each is
  optional and documented in `runtime/.env.example`. The manifest is `dependencies.yml`.

## Safety stance
Recommend-only by design. The only outbound channel is a Slack DM **to you**. It never sends to a
client and never mutates an ad account without you executing the specific approved change
interactively. Live decks are edited additively (never wiped-and-rebuilt).

## License
[CC BY 4.0](LICENSE.txt). Build on it freely; attribution appreciated.


---
Built and battle-tested at [Rise Growth Marketing](https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=account-manager). More free skills, and the story of the systems behind them, at that link.
