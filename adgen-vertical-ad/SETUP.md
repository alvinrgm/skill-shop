# adgen-vertical-ad — setup

Generative vertical-ad pipeline (claymation / cinematic / CGI). Images = Google Gemini,
video = Higgsfield (seedance), voice = ElevenLabs, assembly = ffmpeg + Final Cut Pro.

---

## ⚡ One-paste install (do this first)

**You got a zip / folder?** Unzip it into `~/.claude/skills/` so it lives at
`~/.claude/skills/adgen-vertical-ad/`, then paste this into Claude Code:

> Onboard me into the `adgen-vertical-ad` skill at `~/.claude/skills/adgen-vertical-ad`: read its
> `SKILL.md` and run the first-run onboarding gate — set `ADGEN_HOME`, copy `runtime/` into it,
> run `doctor.sh`, then walk me through each missing dependency one at a time (give me the link and
> offer to install it / write my `.env` / connect the Higgsfield MCP and verify it). Mark
> `.onboarded` when everything's green and tell me the first command to run. Don't start making an
> ad until setup is green.

**You have repo access (GitHub account)?** Same thing, but clone first:

> Install `adgen-vertical-ad`: run
> `git clone --depth 1 https://github.com/alvinrgm/skill-shop ~/tmp/skill-shop && cp -R ~/tmp/skill-shop/adgen-vertical-ad ~/.claude/skills/`,
> then run its first-run onboarding gate (set ADGEN_HOME, copy runtime/, doctor.sh, walk each dep).

That's it — the agent does the rest. The manual steps below are a fallback.

---

## What you'll need (the agent walks you through these)
| Dependency | Powers | Get it | Where |
|---|---|---|---|
| Google Gemini key | all still images | https://aistudio.google.com/apikey | `$ADGEN_HOME/.env` → `GEMINI_API_KEY` |
| ElevenLabs key | character voices | https://elevenlabs.io/app/settings/api-keys (~$22/mo) | `$ADGEN_HOME/.env` → `ELEVENLABS_API_KEY` |
| Higgsfield MCP | all video (seedance) | https://higgsfield.ai → connect the MCP in Claude Code | MCP connection (per-user) |
| ffmpeg | stringout + ken-burns | `brew install ffmpeg` | CLI |
| Whisper | QA transcription | `pip install openai-whisper` | CLI |
| Final Cut Pro 12.2 | finish the cut | Mac App Store ($299) | desktop app |
| Suno (optional) | music bed | https://suno.com (subscription) | manual — generate track, drop into FCP |
| Python packages | image gen + assembly scripts | `pip install -r requirements.txt` | CLI |

## Manual setup (fallback)
1. Put this folder at `~/.claude/skills/adgen-vertical-ad/`.
2. `export ADGEN_HOME="$HOME/Claude/adgen"` (add to your shell profile).
3. `mkdir -p "$ADGEN_HOME" && cp -R runtime/lib runtime/CLIENTS.md runtime/requirements.txt "$ADGEN_HOME"/`
4. `cp runtime/.env.example "$ADGEN_HOME/.env"` then fill `GEMINI_API_KEY` + `ELEVENLABS_API_KEY`.
5. `pip install -r "$ADGEN_HOME/requirements.txt"` ; `brew install ffmpeg` ; `pip install openai-whisper`.
6. Connect the Higgsfield MCP in Claude Code; install Final Cut Pro.
7. `bash doctor.sh` until everything required is ✅, then `date > .onboarded`.

## Run it
In Claude Code: **"make a vertical ad for [brand]"** with a PDP URL or a brief. The skill drives
the 7-phase pipeline and stops for your sign-off before spending any generation credits.

**Note:** generation runs on YOUR keys/credits (Gemini, Higgsfield, ElevenLabs) — each is billed
to whoever's running it.
