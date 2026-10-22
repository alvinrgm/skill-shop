# prospect-sim — setup

Agents roleplay the buyer, the referrer, the technical evaluator and a rival bidder in a
real deal, then tell you where you are weak, what to say instead, and what to do in the
next 72 hours. Prep mode before a call, debrief mode after.

## One-paste install
Paste this into Claude Code:

```
Install the prospect-sim skill: clone https://github.com/alvinrgm/skill-shop into a temp
folder, copy its prospect-sim/ folder to ~/.claude/skills/prospect-sim, then run
bash ~/.claude/skills/prospect-sim/doctor.sh and walk me through its first-run setup.
```

## Manual install
```
git clone --depth 1 https://github.com/alvinrgm/skill-shop /tmp/skill-shop
cp -R /tmp/skill-shop/prospect-sim ~/.claude/skills/prospect-sim
```
Restart Claude Code (or reload skills).

## What you need
| what | needed? | why | get it |
|---|---|---|---|
| Claude Code | yes | runs the agents | https://claude.com/claude-code |
| Work folder + approved facts | recommended | where sims live; the only proof agents may quote | `mkdir -p ~/prospect-sims && cp reference/approved-facts-template.md ~/prospect-sims/approved-facts.md` |
| Call notes connector | optional | pulls transcripts for debriefs; otherwise paste them | https://claude.ai/settings/connectors |
| CRM or email connector | optional | adds deal history and past threads | https://claude.ai/settings/connectors |
| Web access | optional | prospect's site and LinkedIn, rival research | allow WebSearch / WebFetch when asked |

Change the work folder with `PROSPECT_SIM_HOME`. Check anytime: Mac/Linux `bash doctor.sh` ·
Windows `powershell -ExecutionPolicy Bypass -File doctor.ps1`.

## Use it
`/prospect-sim`, or "prep me for my call with <company>", "debrief my call with <company>".
It runs several agents in parallel, so a sim uses more tokens than a normal chat turn.

## Files
- `SKILL.md` — the method
- `reference/persona-briefs.md` — the briefs for each roleplay agent
- `reference/approved-facts-template.md` — fill this in with your real proof
- `doctor.sh` / `doctor.ps1` — health check
- `LICENSE.txt` — CC BY 4.0
