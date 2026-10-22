# system-diagram — setup

Draws any system, funnel or workflow as an editable FigJam board, colored by status
(green built, yellow waiting on someone, gray not started), from the system's real files.

## One-paste install
Paste this into Claude Code:

```
Install the system-diagram skill: clone https://github.com/alvinrgm/skill-shop into a temp
folder, copy its system-diagram/ folder to ~/.claude/skills/system-diagram, then run
bash ~/.claude/skills/system-diagram/doctor.sh and walk me through its first-run setup.
```

## Manual install
```
git clone --depth 1 https://github.com/alvinrgm/skill-shop /tmp/skill-shop
cp -R /tmp/skill-shop/system-diagram ~/.claude/skills/system-diagram
```
Restart Claude Code (or reload skills).

## What you need
| what | needed? | why | get it |
|---|---|---|---|
| Figma account | yes | owns the boards (free works for drafts) | https://www.figma.com/ |
| Figma MCP server | yes | `generate_diagram` draws the board | `claude mcp add --transport http figma https://mcp.figma.com/mcp` · guide: https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/ |
| Plan key | optional | send boards to a specific team | `cp config.example.json config.local.json` |

Easiest: `claude plugin install figma@claude-plugins-official` (adds the server and Figma's
skills). After adding it either way, restart Claude Code, run `/mcp`, pick figma and authenticate.
Check anytime: Mac/Linux `bash doctor.sh` · Windows `powershell -ExecutionPolicy Bypass -File doctor.ps1`.

## Use it
`/system-diagram <system>` for one overview diagram, `/system-diagram <system> full` for
the overview plus zoom-ins. Point it at the project folder or describe the system.

## Files
- `SKILL.md` — the method and rules
- `reference/example.mmd` — an invented example source
- `config.example.json` — optional plan key
- `doctor.sh` / `doctor.ps1` — health check
- `LICENSE.txt` — CC BY 4.0
