# strategy-crystallizer — Setup

## What it does
Forces any brand, company, or business question through Richard Rumelt's
strategy kernel (diagnosis → guiding policy → coherent action) and outputs a
crystallized strategy: a falsifiable one-sentence thesis, 3–5 coherent
actions, explicit refusals, and a graded rubric out of 70. It refuses fluff,
demands diagnosis before action, and always grades honestly.

## Prerequisites
- **Claude Code** (this is a Claude Code skill).
- **Nothing else required.** No API keys, no accounts, no external services,
  no MCP servers. The skill is a pure reasoning method — everything it needs
  ships in this folder.
- Optional: web access, so the skill can research a named brand before asking
  questions (Step 2). Without it, the skill still works — it just asks more
  gap questions up front instead of researching first.

## Install
Copy this folder to your Claude Code skills directory:

```bash
cp -R strategy-crystallizer ~/.claude/skills/strategy-crystallizer
```

That's it. The skill auto-loads on the trigger phrases below (or `/strategy`).

## Environment variable (optional)
The skill reads and writes strategy docs under a working directory called
`WORK_HOME`. Set it to wherever you want strategy docs and any local client
context to live. If unset, treat the default as `~/work`.

```bash
# add to your shell profile (~/.zshrc or ~/.bashrc)
export WORK_HOME="$HOME/work"
```

The skill will create `${WORK_HOME}/strategy-docs/` on first save. It also
*optionally* reads prior context from these paths if they happen to exist —
none are required:

- `${WORK_HOME}/clients/<brand>/` — prior client context/notes
- `${WORK_HOME}/memory/*.md` — any standing memory files
- `${WORK_HOME}/strategy-docs/` — prior strategy docs for the same brand

If those directories don't exist, the skill simply skips them.

## How to invoke
Any of these (the skill triggers proactively on strategic brand talk):

- `/strategy`
- "build a strategy for `<brand>`"
- "what should `<brand>` do"
- "audit `<brand>`'s positioning"
- "grade this strategy: ..."
- "run `<brand>` through Rumelt"
- "stress-test this positioning"

## First-run expectation
1. The skill picks a **mode** (BUILD / AUDIT / COMPARE) and an **ambition
   posture** (EXPAND / HOLD / REDUCE) from your request.
2. If you named a real brand, it researches publicly available signals first.
3. It asks up to 4 sharp gap questions (or none if it has enough).
4. It fills the 8-slot template in order (Situation → Diagnosis → Choice →
   Mechanism → Actions → Refusals → Crystallization → Disconfirmation test).
5. It grades all 7 dimensions out of 70 with a letter grade, and lists the top
   3 improvements if the grade is below A.
6. It saves the doc to `${WORK_HOME}/strategy-docs/<brand>-<date>.md` and gives
   you the headline (grade + crystallization) in chat.

Expect a candid grade. Generous grading is a designed-against failure mode —
if the strategy is a C, it will say so and tell you why.
