# dialectical-debate — setup

Stress-test a claim by spawning opposing/complementary sub-agents that investigate,
cross-examine across rounds, and end with a confidence-rated verdict.

## Install
Drop this folder into your skills directory:
```
git clone --depth 1 <repo-url> ~/.claude/skills/dialectical-debate
```
(or copy the folder to `~/.claude/skills/dialectical-debate`)

Restart Claude Code (or reload skills). Invoke with `/dialectical-debate` or
"stress-test this" / "red team this" / "double-check that answer".

## Dependencies
**None.** No API keys, no `.env`, no external accounts. It only uses Claude Code's
built-in sub-agent (Task) capability, which every Claude Code install already has.

## Files
- `SKILL.md` — the skill (trigger rules + method)
- `references/agent-prompts.md` — the debater/judge agent prompts it spawns
