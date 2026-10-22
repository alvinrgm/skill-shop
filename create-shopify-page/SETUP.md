# create-shopify-page — setup

Builds a Shopify landing page end to end: verified facts, two audience versions in Figma,
a 4-agent review, v2 plus mobile, theme code on an unpublished test theme, and launch only
on your typed yes.

## One-paste install
Paste this into Claude Code:

```
Install the create-shopify-page plugin: clone https://github.com/alvinrgm/skill-shop into a
temp folder, copy its create-shopify-page/ folder to ~/.claude/skills/create-shopify-page,
then run bash ~/.claude/skills/create-shopify-page/doctor.sh and walk me through its
first-run setup one step at a time.
```

## Manual install
```
git clone --depth 1 https://github.com/alvinrgm/skill-shop /tmp/skill-shop
cp -R /tmp/skill-shop/create-shopify-page ~/.claude/skills/create-shopify-page
```
Restart Claude Code (or reload skills).

## What you need
| what | needed? | why | get it |
|---|---|---|---|
| Node.js 22+ | yes | runs Shopify CLI | https://nodejs.org/ |
| Shopify CLI | yes | theme pull and push to a test theme | `npm install -g @shopify/cli@latest` · https://shopify.dev/docs/api/shopify-cli |
| Store access | yes | staff or collaborator access with the Themes permission | https://help.shopify.com/en/manual/your-account/staff-accounts |
| Figma MCP server | yes | designs the page in Figma and reads it back for code | `claude plugin install figma@claude-plugins-official` · https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/ |
| Figma edit seat | yes | write access to the brand's design file | https://www.figma.com/pricing/ |
| Shopify connector | optional | reads products, prices and reviews | https://claude.ai/settings/connectors |

Check anytime: Mac/Linux `bash doctor.sh` · Windows `powershell -ExecutionPolicy Bypass -File doctor.ps1`.

## Safety by design
- Code goes only to an unpublished test theme. Pages are created hidden.
- Nothing is pushed live, unhidden or ordered without your typed yes in the chat.
- Live pushes list exact files (`--only`, `--nodelete`), then live is pulled again and diffed.

## Use it
`/create-shopify-page`, or "build a landing page for <brand>". It runs several review
agents in parallel, so a full run uses more tokens than a normal chat.

## Files
- `SKILL.md` — the loop, steps 0 to 7
- `reference/reviewer-briefs.md` — the four reviewer prompts
- `reference/shopify-safety-checklist.md` — the build and launch checklist
- `doctor.sh` / `doctor.ps1` — health check
- `LICENSE.txt` — CC BY 4.0
