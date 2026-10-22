---
name: fact-check
description: >-
  Pre-send adversarial fact-check for any AI-made report, summary, analysis, update or
  message before it reaches another person (a teammate, a client, a channel). Pulls out
  every checkable claim, re-checks each against its source, sends one fresh adversarial
  agent to try to break them, fixes or labels whatever fails, and writes a receipt.
  Use BEFORE sending anything substantive to someone else, and whenever the user says
  "fact-check this", "pre-audit", "check this before I send it", "is this all true",
  "verify the claims", "/fact-check". Required by the optional fact-check-gate hook for
  long Slack posts and emails. Lighter than `dialectical-debate` (judgment calls);
  escalate to that when this one says so.
---

# Fact-check (pre-send gate)

## FIRST RUN: onboarding gate
If `.onboarded` does NOT exist in this folder, run `bash doctor.sh` first (Windows:
`powershell -ExecutionPolicy Bypass -File doctor.ps1`). The only required dependency is
**Python 3** (`python3`, for `scripts/receipt.py`); if it's missing, give the link
<https://www.python.org/downloads/> and offer to install it (`brew install python` on a
Mac). Then mention the optional **send gate hook** (`gate_hook`) once, with the steps in
`SETUP.md`, and install it only if they say yes. When doctor.sh passes, write
`.onboarded` (`date > .onboarded`) and carry on with the user's request.

---

**Why this exists.** AI reports read as finished and checked when they aren't. Half the
claims are true, a quarter are inferences dressed as facts, and the reader inherits the
job of checking them. This skill moves that job back to the author, before sending, in
about 5-10 minutes.

**The rule it enforces:** every load-bearing claim in a message to another person is
either *verified against its source this session*, *corrected*, *labeled as inference*,
or *cut*. Nothing ships in the "sounds right" state.

## Step 0. Triage (10 seconds)
- Going to another human? If it's only for the user, a self-check is enough (Steps 1-2).
- Short and claim-free (a ping, a thanks, a scheduling note)? Skip. Say "no claims to check".
- High stakes (client deliverable, money, legal, a board, production)? Run this, then
  have a second person or a second, independent multi-round review look at it. Is the
  open question a judgment call ("which option is better") rather than a fact? Use the
  `dialectical-debate` skill (same shop) for that question.

## Step 1. Extract the claims
Read the final draft (the version about to be sent, not an earlier one) and list every
**atomic, checkable** claim. One fact per claim. Write them to a claims file:

```json
{"draft": "<path or short title>", "audience": "<who receives it>",
 "claims": [
  {"id": "c1", "text": "Weekly support tickets doubled after the checkout redesign",
   "type": "number", "load_bearing": true,
   "source": "helpdesk export, two weeks before vs two weeks after the Mar 3 release"}
 ]}
```

Types: `number` (metrics, money, counts, dates), `state` (X is live / broken / done /
configured), `quote` (someone said or decided X), `source` (according to doc / study / page
X), `causal` (X happened because of Y), `recommendation` (we should do X).

`load_bearing: true` = the reader would act differently if this claim were wrong.
Mark honestly: most numbers, every state claim, every quote, and the recommendation itself.

**Missing claims count too.** Note any absence claims ("no errors", "nothing else changed",
"all clients") — they're the most often wrong, because nobody checks what isn't there.

## Step 2. Self-check against the source of truth
For each load-bearing claim, go to where the truth lives and re-derive it **this session**:
run the query, open the file, fetch the page, read the thread, call the API. Not memory,
not an earlier message, not another agent's summary.

Evidence rules:
- **An empty result is evidence; an error is not.** `200 []` proves absence. A 400,
  a timeout, or a permission error proves only that the check failed. Mark `unverifiable`.
- **A connector's error describes the connector, not the platform.** Probe directly
  before claiming something "can't be done" or "isn't available".
- **Quotes need the original.** Paraphrase in a quote's clothing is the most common
  half-truth. Find the actual words or turn it into a paraphrase.
- **Causal claims are inferences** unless there's a controlled comparison. Label them
  `(my read)` or show the comparison.
- **Re-do the arithmetic** on every derived number (percent changes, totals, averages).

Record per claim: `status` and `evidence` (what you ran or read, and what it showed).

## Step 3. Adversarial pass (one fresh agent)
Spawn ONE fresh agent (two if more than 15 load-bearing claims or the audience is a client)
with execution tools (`general-purpose`, so it has Bash and web). Brief it with the
template in `reference/adversary-prompt.md`: the final draft, the claims file, and where
each source lives. **Do not** give it your reasoning or Step 2 results: it should check
from scratch, or it will just agree with you.

Its job: assume at least a third of the claims are wrong and try to prove it. For each
claim it returns `holds` / `broken` / `unverifiable` with the evidence it saw, plus any
claim you missed and any place the draft implies more than the evidence supports.

## Step 4. Reconcile
- **Re-derive every `broken` finding yourself** before changing the draft. Adversaries
  are confidently wrong at a real rate.
- **When you and the adversary disagree, find the reason** (different date range, filter,
  definition). Don't pick the better-argued side; run the check that settles it.
- **Where you both agree, ask if you share a premise** (same wrong source, same
  definition). Agreement from a shared assumption is not evidence.

## Step 5. Fix the draft
Final status per claim, and what it does to the text:

| status | meaning | what happens in the draft |
|---|---|---|
| `verified` | checked this session against the source | stays as written |
| `corrected` | was wrong; now fixed | text changed to the checked value |
| `labeled` | inference, judgment or prediction | tagged `(my read)` or `(estimate)` |
| `unverifiable` | couldn't be checked | tagged `(unverified)`, or cut if load-bearing |
| `cut` | wrong or unsupported, and not worth fixing | removed |

If the bottom line or recommendation rests on a claim that was corrected or cut, rewrite
the bottom line. Don't send a conclusion whose support just changed.

## Step 6. Write the receipt
Add the final statuses and evidence to the claims file, then run:

```bash
python3 ~/.claude/skills/fact-check/scripts/receipt.py <claims.json>
```

The script **refuses** (exit 1) if any load-bearing claim has no status, no evidence, or
is still `unverified`/`broken`. On success it saves the receipt to
`${FACT_CHECK_HOME:-~/.claude/fact-check}/receipts/` and prints a one-line footer, e.g.:

> Fact-checked: 9 claims (7 verified, 1 corrected, 1 labeled as estimate). Receipt on request.

Put that footer at the bottom of the message. It tells the reader what was and wasn't
checked, so they don't have to redo it.

The `fact-check-gate` hook (if installed) blocks long Slack posts and emails when no
receipt was written in the last 90 minutes. Short messages pass.

## Step 7. Report to the user
Before sending, show the user: what changed (corrected / cut / labeled, one line each)
and the footer. If nothing changed, say "all N claims checked out" in one line.

## Anti-patterns
- **Checking the draft against itself or your memory** → the source of truth is outside the draft.
- **Treating an error as "not found"** → that's how wrong "doesn't exist" claims get made.
- **Handing the adversary your conclusions** → it will agree with you.
- **Fixing a number but not the conclusion built on it** → re-read the bottom line after fixes.
- **Checking the earlier draft** → check the exact text being sent.
- **Ceremony on a two-line ping** → triage first; no claims means no check.

## Reference
- `reference/adversary-prompt.md` — the brief for the adversarial agent
- `scripts/receipt.py` — validates the claims file and writes the receipt + footer
- `hooks/fact-check-gate.sh` — optional pre-send gate for Slack and email tools

---
Free from Rise Growth Marketing (risegm.com/skills). CC BY 4.0, see `LICENSE.txt`.
Feedback or bugs: open an issue at github.com/alvinrgm/skill-shop.
