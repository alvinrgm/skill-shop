# Ad creative library: setup

A Figma system for static ads. Each brand gets one Figma file holding its brand kit, asset bank,
template shelf, shot list, testing roadmap, learnings and one page per batch. Every layer stays
editable; only the photo plates are generated (Gemini, on your own key).

You need two accounts of your own: **Figma** (connected to Claude Code through the Figma MCP)
and **a Gemini API key**. Everything else is optional.

---

## One-paste install

Get the folder. Claude Code only finds skills in `~/.claude/skills/` (or a project's
`.claude/skills/`), so copy it there:

```bash
git clone --depth 1 https://github.com/alvinrgm/skill-shop
mkdir -p ~/.claude/skills
cp -R skill-shop/ad-library ~/.claude/skills/ad-library
cd ~/.claude/skills/ad-library
```

(This skill is a folder you copy, not a `claude plugin install` package.) Open Claude Code in that
folder and paste:

```
Onboard me into the ad-library skill in this folder: read SKILL.md and dependencies.yml, run
`bash doctor.sh` (on Windows: powershell -ExecutionPolicy Bypass -File doctor.ps1), then walk
me through every missing dependency one at a time with its link, and offer to do the work:
install the Python packages into a .venv in this folder, copy .env.example to .env and fill in
its GEMINI_API_KEY= line with my key (do not echo it back), and help me connect the Figma MCP
with my own Figma account, then check the Figma tools are actually available and call whoami.
Run python3 scripts/selftest.py. When bash doctor.sh --figma-confirmed exits 0, write the
.onboarded marker and tell me the first line to type. Don't start the workflow until setup is
green.
```

Prefer to do it yourself:

```bash
python3 -m venv .venv                                  # Windows: python -m venv .venv
.venv/bin/pip install -r requirements.txt              # Windows: .venv\Scripts\pip install -r requirements.txt
cp .env.example .env
# edit .env: fill in the existing GEMINI_API_KEY= line with your key
python3 scripts/probe_gemini.py                        # a real (free) call that proves the key works
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin install figma@claude-plugins-official    # or the manual MCP command below
# in Claude Code: /mcp -> figma -> authenticate, then ask Claude to call whoami
bash doctor.sh --figma-confirmed                       # Windows: powershell -ExecutionPolicy Bypass -File doctor.ps1 -FigmaConfirmed
python3 scripts/selftest.py                            # offline test of every offline-testable script
date > .onboarded                                      # the skill's first-run gate: setup is done
```

The scripts use `.venv` automatically when it exists, so `python3 scripts/...` is fine. Without
`.onboarded`, the skill runs its onboarding check first instead of the workflow (that is the
gate in SKILL.md); `--figma-confirmed` is only honest once you have seen the Figma tools work.

---

## What you need

| What | Required? | Powers | Where to get it | Cost |
|---|---|---|---|---|
| Python 3.9+ with **Python packages** (Pillow, numpy) | yes | every local script | `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` | free |
| **Gemini API key** | yes | photo plates (Nano Banana 2 / Pro) and the print gate that catches garbled or invented print on a generated pack | <https://aistudio.google.com/apikey> | pay as you go: roughly $0.13 per 1K-2K plate, $0.24 per 4K plate |
| **Figma MCP**, on your own Figma account | yes | building every page, template and ad; uploading photos; 2x PNG exports | <https://www.figma.com/signup> then connect (below) | a paid plan with a Full or Dev seat |
| **curl** | yes | posting files to the upload URLs `upload_assets` returns | preinstalled on macOS, Linux, Windows 10+; else <https://curl.se/download.html> | free |
| **OpenCV + SciPy** (label repair) | no | `label_composite.py`: put the real label back on a generated pack | `.venv/bin/pip install -r requirements-repair.txt` | free |
| **Meta Marketing API read token** | no | `learn.py`: map every past ad onto the angle tree, read batch tests | <https://developers.facebook.com/tools/explorer/> | free |
| **Figma personal access token** (comments) | no | `figma_comments.py`: read and answer reviewer comments | <https://developers.figma.com/docs/rest-api/authentication/> | free |
| Optional overrides | no | renamed model ids (`AD_LIBRARY_VISION_MODEL`, `AD_LIBRARY_IMAGE_MODEL_PRO`, `AD_LIBRARY_IMAGE_MODEL_NB2`), comment reply prefix | <https://ai.google.dev/gemini-api/docs/models> | n/a |
| The brand's facts and real pack photos | yes | the truth ledger, the pack's printed strings, the cutouts every ad is built on | produced during ONBOARD by `init_brand.py`, `crawl_site.py`, `cutout.py` | n/a |

### Gemini API key (about 2 minutes)

1. Open <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key**. Image generation at volume needs billing enabled on that Google
   Cloud project.
3. Put it in `.env` (copy `.env.example` to `.env` first): fill in the existing
   `GEMINI_API_KEY=` line, `GEMINI_API_KEY=your-key-here`. Do not add a second line.
4. Verify for real: `python3 scripts/probe_gemini.py`. It lists the models your key can see and
   flags any model id this package uses that Google has renamed (override it in `.env`).

### Figma MCP (your own account)

The skill builds everything through Figma's official MCP server, signed in as you.

- **No Figma account yet:** <https://www.figma.com/signup>.
- **Recommended:** add the official plugin marketplace, then install Figma's plugin (it adds the
  MCP and Figma's own skills, including `figma-use`, which must be loaded before any `use_figma`
  call). A fresh Claude Code has no marketplace configured, so the first line is needed:
  ```bash
  claude plugin marketplace add anthropics/claude-plugins-official
  claude plugin install figma@claude-plugins-official
  ```
- **Manual:** `claude mcp add --transport http figma https://mcp.figma.com/mcp`, then type `/mcp`
  in Claude Code, pick **figma**, and authenticate in the browser. Guide:
  <https://help.figma.com/hc/en-us/articles/35281350665623-Figma-MCP-collection-How-to-set-up-the-Figma-remote-MCP-server>
- **Verify:** ask Claude to call `whoami`. The tools `use_figma`, `create_new_file`,
  `upload_assets` and `download_assets` must be listed. `doctor.sh` cannot see MCP tools, so it
  shows Figma MCP as ❌ until then; once confirmed, `bash doctor.sh --figma-confirmed`.
- **Seat and limits:** a Full or Dev seat on a paid plan. Professional allows 200 MCP tool calls a
  day and 10 a minute; Enterprise 600 a day. Starter plans and View/Collab seats get 6 calls a
  month, which cannot build a library. A new brand's library takes about 12-20 calls (more with a
  large photo crawl and a full template shelf); a routine batch about 4-10. Current limits:
  <https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/>, plans:
  <https://www.figma.com/pricing/>.
- New files land in your drafts. Move the file into a team project so teammates can edit and
  comment.

### Meta read token (optional)

`learn.py` only reads. Create a token on YOUR OWN ad account:
- Quick, short-lived: <https://developers.facebook.com/tools/explorer/> → choose your app → add
  the `ads_read` permission → **Generate Access Token**.
- Lasting: Meta Business Settings → Users → System users → add one, assign your ad account,
  **Generate new token** with `ads_read`. Docs:
  <https://developers.facebook.com/docs/marketing-api/get-started/authorization/>

Put `META_ACCESS_TOKEN` and `META_AD_ACCOUNT_ID` (the number after `act_` in Ads Manager) in
`.env`. Without them, `learn.py --no-meta` builds the roadmap from your angle tree alone.

### Figma personal access token (optional)

Figma → Settings → Security → **Personal access tokens** → Generate new token, scopes File
content: read and Comments: write. Put it in `.env` as `FIGMA_TOKEN`. Tokens expire (90 days at
most); regenerate when `figma_comments.py` says 403.

### OpenCV + SciPy (optional)

`.venv/bin/pip install -r requirements-repair.txt` (into the same `.venv`). Only
`label_composite.py` uses them.

---

## Where your data lives

`AD_LIBRARY_HOME` (default `~/ad-library`) holds one folder per brand, created by
`python3 scripts/init_brand.py <brand> --name "Brand Name"`:

```
~/ad-library/<brand>/
  state.json              every id the Figma file returned, batches, call counts, lessons
  brand/                  truth-ledger.jsonl, pack-strings.json, copy-rules.json, packs/, site-photography/
  library/                the asset Library (library.json + product/ location/ plate/ ...)
  roadmap/                angles.json, tracker.json
  learnings/              traits.json, refresh-<date>.md
  shotlist/               shotlist.json
  copy/                   one copy file per batch
  runs/b01/ ...           2x exports, contact sheet, qa.json
```

`examples/example-state.json` shows what `state.json` looks like after setup and one batch.

## First run

In Claude Code: *"build the ad library for <brand>, site <url>"*. The skill scaffolds the brand
folder, fills the truth ledger and pack strings with you, crawls the site's photography, makes
the pack cutouts, then builds the Figma file page by page.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `GEMINI_API_KEY is not set` | add it to `.env` next to SKILL.md, or to `$AD_LIBRARY_HOME/.env` |
| `pip install` says "externally-managed-environment" | your system Python refuses global installs: use the `.venv` commands above |
| probe says the key is invalid (HTTP 400/403) | create or replace the key at <https://aistudio.google.com/apikey> and put it on the `GEMINI_API_KEY=` line in `.env` |
| probe says a model id is not listed | Google renamed it: pick the current id from the probe's list, set `AD_LIBRARY_VISION_MODEL` / `AD_LIBRARY_IMAGE_MODEL_PRO` / `AD_LIBRARY_IMAGE_MODEL_NB2` |
| `claude plugin install figma@...` says the plugin or marketplace is not found | run `claude plugin marketplace add anthropics/claude-plugins-official` first, or use the manual `claude mcp add` command |
| Figma tools missing in Claude Code | run `/mcp`, re-authenticate figma, restart Claude Code |
| Figma says rate limited | check your seat (Full or Dev on a paid plan); the daily budget resets daily; see the limits page above |
| An export is tiny (under 800 KB) | the image fill had not loaded yet: export again a minute later |
| `qa_export.py` fails a plate on resolution | regenerate the winning plate at 4K (`--model pro --size 4K`) |
| print gate `wrong > 0` | repair with `label_composite.py`, or regenerate; never blur the print to pass |
| `figma_comments.py` HTTP 403 | the token expired or lacks the Comments scope: make a new one |

Re-check your setup anytime with `bash doctor.sh` (Windows: `powershell -ExecutionPolicy Bypass -File doctor.ps1`).
Re-audit the package itself with `python3 verify_portable.py .`
