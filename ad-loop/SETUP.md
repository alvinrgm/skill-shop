# ad-loop (Static ad loop): setup

## Get it

```bash
git clone --depth 1 https://github.com/alvinrgm/skill-shop
mkdir -p ~/.claude/skills
cp -R skill-shop/ad-loop ~/.claude/skills/ad-loop
cd ~/.claude/skills/ad-loop
```

Problems or questions: https://github.com/alvinrgm/skill-shop/issues

## One-paste install

Open Claude Code inside `~/.claude/skills/ad-loop` and paste:

```
Read SETUP.md and dependencies.yml in this folder, then set me up: create a .venv in this
folder and install the Python packages into it, install Node's static-kit dependencies and
the Playwright Chromium build, check ffmpeg, and help me create a Gemini API key and put it
in .env (never echo it back). Run `python3 config.py --init`, then `bash doctor.sh`, walk
me through anything it reports as missing, run `python3 loop-engine/selftest.py`, and when
everything required is green write .onboarded and ask me for a brand URL to start the
intake interview.
```

Prefer to do it yourself (needs Python 3.10+, Node.js 20+, ffmpeg):

```bash
# Python packages go in a virtual environment in this folder (PEP 668 systems refuse a
# global pip install). Once .venv exists, every script re-runs itself under it.
python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -r requirements.txt
cd runtime/static-kit && npm install && npx playwright install chromium && cd -
#   Linux: use `npx playwright install --with-deps chromium` to also get the system libraries
python3 -m playwright install chromium   # same pinned version: reuses the download above
cp .env.example .env          # set GEMINI_API_KEY
python3 config.py --init      # creates ~/ad-loop-work (override with AD_LOOP_HOME)
bash doctor.sh                # Windows: powershell -ExecutionPolicy Bypass -File doctor.ps1
python3 loop-engine/selftest.py
```

Both the Node renderer and the Python tools pin **Playwright 1.62.0**
(`runtime/static-kit/package.json`, `requirements.txt`), so they share **one** Chromium
download (about 150MB). If you change one pin, change the other, or you will download a
second browser.

---

## What you need

Everything below is declared in `dependencies.yml`; `doctor.sh` / `doctor.ps1` probe each
one.

| dependency | required | what it powers | get it |
|---|---|---|---|
| Python packages (`python_deps`) | yes | the instruments (pillow, numpy), Gemini vision (google-genai, python-dotenv), browser automation (playwright) | `python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -r requirements.txt` |
| Node.js 20+ (`node`) | yes | the static-kit renderer, how every ad becomes pixels | https://nodejs.org/ |
| npm (`npm`) | yes | installs the static-kit's playwright dependency | ships with Node.js |
| Chromium for the renderer (`chromium_node`) | yes | the headless browser `render.js` drives | `cd runtime/static-kit && npm install && npx playwright install chromium` (Linux: `--with-deps`) |
| Chromium for Python (`chromium_python`) | yes | the inspo harvester, the Ad Library page-id lookup, the in-feed mock | `python3 -m playwright install chromium` (reuses the same download) |
| ffmpeg and ffprobe (`ffmpeg`) | yes | the feed-gate: phone-chrome composites and ablations | https://ffmpeg.org/download.html (`brew install ffmpeg`, `apt install ffmpeg`) |
| Gemini API key (`gemini_key`, `GEMINI_API_KEY`) | yes | all plate generation and every vision instrument | https://aistudio.google.com/apikey |
| Client brand URL (`client_url`) | per run | the brand intake harvests from | you supply it in the launch interview |
| North Star ads (`north_stars`) | optional | the blind comparative lineup | 5-15 elite ad images in `<work>/north-stars/` |
| Meta Ads connector (`meta_ads`) | optional | PAUSED draft uploads only | any Meta Ads MCP connector in Claude Code |
| Vision model override (`vision_model`, `AD_LOOP_VISION_MODEL`) | optional | swap the vision-judge model | https://ai.google.dev/gemini-api/docs/models |
| Spend guard (`volume_cap`, `volume_size`, `winner_size`) | optional | `AD_LOOP_VOLUME_CAP` (15), `AD_LOOP_VOLUME_SIZE` (1K), `AD_LOOP_WINNER_SIZE` (4K) | https://ai.google.dev/gemini-api/docs/pricing |

## The Gemini key (set this up first)

The key is what lets the loop generate plates and *see* them: the letter-perfect print
check, the global-illumination check, the feed-gate and the live selftest all call it.

1. Open https://aistudio.google.com/apikey
2. Sign in with a Google account and click **Create API key**.
3. `cp .env.example .env`, then set `GEMINI_API_KEY=<your key>`. The `.env` lives in this
   folder and is git-ignored.
4. Verify for real: `python3 loop-engine/selftest.py --live` (one vision call).

**Cost.** Google bills image generation per image, and higher resolutions cost more (see
https://ai.google.dev/gemini-api/docs/pricing). The spend guard in `config.py` caps a
volume batch at 15 plates at 1K by default and only re-generates the locked winner at 4K.
`python3 -c 'import config; print(f"${config.plate_spend(15)} USD")'` prints a batch's
estimated cost in US dollars (e.g. `$2.01 USD` for 15 plates at 1K) before you run it. Raise the caps deliberately.

## The work root

`python3 config.py --init` creates `~/ad-loop-work/` (set `AD_LOOP_HOME` in `.env` to put
it elsewhere) with an empty loop-state: `learnings.md`, the verdict-bank README, the
orchestrator marker, the ledger and a live copy of the rubric. Client folders appear there
when you run intake. It never overwrites anything that exists.

```
~/ad-loop-work/
├── loop-state/        learnings.md, RUBRIC.md, verdict-bank/, ORCHESTRATOR.md
├── north-stars/       your hand-picked bar (optional)
├── inspo/             corpus built by runtime/static-kit/tools/harvest_inspo.py
├── ledger.jsonl
└── <client>/          brand/, personas/, library/, statics/
```

## Fonts

No font files ship. For each brand, put its own licensed web fonts in
`runtime/static-kit/fonts/` under the names `runtime/static-kit/tokens.css` documents, and
set the palette there by hand from the colour candidates intake writes to
`brand/palette-CANDIDATES.md` (font names and any downloaded files are listed in
`brand/fonts/INDEX.md`). Without font files the
templates fall back to system fonts and still render.

## Meta uploads (optional, draft-only)

The loop is recommend-only: a shipped concept becomes an upload packet in
`<work>/<client>/statics/loop-<concept>/ship/` that you upload yourself. If you connect a
Meta Ads connector and explicitly say "upload <concept> as a paused draft", Claude follows
`reference/meta-upload.md`: PAUSED only, claims gate first, previews verified before it
reports success. It never activates ads or changes budgets, bids or targeting.

## Troubleshooting

| symptom | fix |
|---|---|
| `GEMINI_API_KEY not set` | `.env` must sit in this folder (next to `config.py`); `python3 config.py` shows where it looked |
| live selftest fails | wrong key, no access to the vision model (set `AD_LOOP_VISION_MODEL`), quota, or region |
| `render.js` cannot find playwright | `cd runtime/static-kit && npm install && npx playwright install chromium` |
| Chromium launches fail on Linux (missing shared libraries) | `cd runtime/static-kit && npx playwright install --with-deps chromium` |
| `pip install` says "externally-managed-environment" | use the `.venv` in this folder: `python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -r requirements.txt` |
| harvester or intake page-id lookup fails to launch a browser | `python3 -m playwright install chromium` |
| feed-gate errors mentioning ffmpeg/ffprobe | install ffmpeg; both binaries must be on PATH |
| renders use the wrong fonts | add the brand's font files to `runtime/static-kit/fonts/` |
| intake refuses with "live, curated client layer" | intended: pass `--force` to add to an existing client, or `--root DIR` for a scratch run |

Re-check your setup anytime with `bash doctor.sh` (`--offline` skips the live call).
Re-audit the package itself with `python3 verify_portable.py .`

---

Built by Rise Growth Marketing: https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=ad-loop
