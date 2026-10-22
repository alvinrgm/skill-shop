# fact-check — setup

A pre-send check for anything an AI wrote before it reaches another person. It lists
every checkable claim, re-checks each against its source, sends one fresh agent to try to
break them, fixes or labels what fails, and writes a receipt with a one-line footer.

## One-paste install
Paste this into Claude Code:

```
Install the fact-check skill: clone https://github.com/alvinrgm/skill-shop into a temp
folder, copy its fact-check/ folder to ~/.claude/skills/fact-check, then run
bash ~/.claude/skills/fact-check/doctor.sh and tell me how to use it.
```

## Manual install
```
git clone --depth 1 https://github.com/alvinrgm/skill-shop /tmp/skill-shop
cp -R /tmp/skill-shop/fact-check ~/.claude/skills/fact-check
```
Restart Claude Code (or reload skills).

## Dependencies
| what | needed? | why | get it |
|---|---|---|---|
| Python 3 | yes | runs `scripts/receipt.py` (standard library only) | https://www.python.org/downloads/ |
| fact-check-gate hook | optional | blocks long Slack/email sends with no fresh receipt | below |

Check anytime: Mac/Linux `bash doctor.sh` · Windows `powershell -ExecutionPolicy Bypass -File doctor.ps1`.

Receipts are saved to `~/.claude/fact-check/receipts/`. Change it with `FACT_CHECK_HOME`.

## Optional: block unchecked sends
The hook stops Claude from sending a long message (500+ characters) through a Slack or
email tool unless a fact-check receipt was written in the last 90 minutes. Short messages
pass. Add `[no-fact-check]` to a message to skip it on purpose.

1. `mkdir -p ~/.claude/hooks && cp ~/.claude/skills/fact-check/hooks/fact-check-gate.sh ~/.claude/hooks/ && chmod +x ~/.claude/hooks/fact-check-gate.sh`
2. Add to `~/.claude/settings.json` (merge into any existing `hooks` block). Put the
   names of YOUR send tools in the matcher; these are common ones:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*slack.*__.*(send|post).*|mcp__.*(gmail|mail).*__.*send.*",
        "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/fact-check-gate.sh" }]
      }
    ]
  }
}
```
Tune with `FACT_CHECK_MIN_CHARS` (default 500) and `FACT_CHECK_WINDOW_MIN` (default 90).
Hooks reference: https://docs.claude.com/en/docs/claude-code/hooks

## Use it
`/fact-check`, or "check this before I send it", "is this all true", "verify the claims".
Pairs with `bluf` (same shop): write it with bluf, check it with fact-check. For judgment
calls rather than facts, use `dialectical-debate`.

## Files
- `SKILL.md` — the method
- `reference/adversary-prompt.md` — the brief for the adversarial agent
- `scripts/receipt.py` — validates the claims file, writes the receipt and footer
- `hooks/fact-check-gate.sh` — optional send gate
- `doctor.sh` / `doctor.ps1` — health check
- `LICENSE.txt` — CC BY 4.0
