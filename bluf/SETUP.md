# bluf — setup

Turns any long output, report or thread into a Minto pyramid: the answer first, 2-4
reasons under it, evidence one layer down, in plain words with no filler.

## One-paste install
Paste this into Claude Code:

```
Install the bluf skill: clone https://github.com/alvinrgm/skill-shop into a temp folder,
copy its bluf/ folder to ~/.claude/skills/bluf, then run bash ~/.claude/skills/bluf/doctor.sh
and tell me how to use it.
```

## Manual install
```
git clone --depth 1 https://github.com/alvinrgm/skill-shop /tmp/skill-shop
cp -R /tmp/skill-shop/bluf ~/.claude/skills/bluf
```
Restart Claude Code (or reload skills).

## Dependencies
**None.** No API keys, no accounts, no MCP servers.

Check anytime: Mac/Linux `bash doctor.sh` · Windows `powershell -ExecutionPolicy Bypass -File doctor.ps1`.

## Use it
`/bluf`, or say "minto this", "bluf", "tl;dr", "eli5", "package this up", "turn this into
an email for <person>".

Pairs with the `fact-check` skill (same shop): bluf shapes the message, fact-check
checks every claim in it before it goes to someone else.

## Files
- `SKILL.md` — the method, output shapes and an example
- `doctor.sh` / `doctor.ps1` — health check
- `LICENSE.txt` — CC BY 4.0
