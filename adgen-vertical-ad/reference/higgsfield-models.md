# Higgsfield models reference

Tested and validated as of May 2026 against the live Higgsfield MCP. Update if the MCP wrapper changes.

## Models we use

### nano_banana_2 (Google Nano Banana Pro) — image generation

> ⛔ **DO NOT USE THIS VIA THE HIGGSFIELD MCP (as of May 2026).** Image generation
> goes through Google Gemini "Nano Banana" directly, on your `GEMINI_API_KEY`
> (`google-genai` SDK, wired at `lib/keyframe.py`) — NOT the Higgsfield `generate_image`
> tool, which bills Higgsfield credits. See the image-gen HARD RULE in SKILL.md. This
> section is retained only to document params/quirks of the underlying model; the
> *route* is Gemini, not Higgsfield. (A past session burned the entire Higgsfield
> balance generating images through the MCP.)

**Use for:** character refs, environment refs, contact sheets, product hero composites.

**Params:**
- `aspect_ratio`: `9:16` for vertical content, `16:9` for contact sheets (horizontal grid layout), `1:1` for product flat shots
- `resolution`: `1k` (default, ~10 credits) for character refs and environment refs. `2k` (~30 credits) for product hero composites where text rendering matters. `4k` only when explicitly needed (rare).
- `count`: 1 unless A/B testing
- `medias`: pass image refs as `[{"role": "image", "value": "<job_id_or_uuid>"}]`

**Strengths:** strong text rendering (great for logos / product packaging), follows image refs faithfully when preserving brand identity.

**Quirks:** sometimes interprets style language ("claymation") differently than expected — produces "carved wood folk-art" for our claymation prompts. Often this happens to be GOOD; don't fight it on first try. Re-roll only if the result is genuinely off-brand.

**Queue time:** typically 15-30 sec. Occasionally one job hangs for 2-3+ min while sibling jobs finish in 30 sec. If a job is in_progress >2 min while others are done, kill (no cancel tool — abandon and re-roll with a slightly different prompt).

### seedance_2_0 (Bytedance Seedance 2.0) — video generation

**Use for:** all character video shots, including dialogue, action, lip-sync to external audio.

**Params (defaults that work):**
- `mode`: `"fast"` — much cheaper than std, quality difference is negligible for vertical 720p output. Always default to fast.
- `resolution`: `"720p"` — sufficient for 9:16 vertical, can upscale in post if needed.
- `aspect_ratio`: `"9:16"` for vertical
- `duration`: 4-15 sec. **Min 4, max 15. HARD CAP — server silently clamps anything outside range.** If you request 18s, you get 15s with no error (just an `adjustments` field in the response). Plan all clip lengths within 15s. To get more screen time for a beat, split into adjacent 15s shots.

**Dialogue density budget at 15s:** ≤9 turns, ≤60 spoken words. >4 words/sec → expect compression / dropped beats. Count words before firing.

**NSFW filter (`ip_detected`) is stochastic.** Same prompt may pass one time, get flagged another. When you hit ip_detected: (1) retry once with minor wording variation, (2) only after second failure apply full sanitization, (3) only after third failure pivot composition. Skipping the retry-once step burns credits.
- `genre`: `"auto"` (default) — works for most. Can override with `"drama"`, `"comedy"`, `"horror"`, etc. but rarely needed.
- `medias`:
  - `start_image`: `[{"role": "start_image", "value": "<image_job_id>"}]` — defines first frame
  - `end_image`: optional, for controlled motion arc
  - `image`: additional reference (e.g., character contact sheet for identity lock) — `[{"role": "image", "value": "<sheet_job_id>"}]`
  - `audio`: optional external audio for lip sync — `[{"role": "audio", "value": "<audio_media_id>"}]`
  - `video`: motion reference (rare)

**Native audio:** Seedance generates audio (voice + ambient + SFX) by default. The MCP wrapper sets `generate_audio: true` internally; there's no user-facing toggle to turn it off. To get a "silent" video, generate as normal then strip audio with `ffmpeg -an` in post.

**Voice quality:** good for general dialogue, accents, emotional tone. Weak for:
- Music / rap (use external audio ref instead — Suno → upload → audio role)
- Brand-specific or technical pronunciations (try phonetic spelling; if 2 attempts fail, switch to ElevenLabs)

**Lip sync:** when `role: audio` is provided, seedance lip-syncs visuals to that audio TIGHT within one clip. **This is why ElevenLabs is now the DEFAULT voice path** for any speaking character: pass a locked 11L voice segment as `role: audio` and seedance lip-syncs to it, giving a voice that's identical within-clip, across-clips, and across ads. Cross-clip drift is avoided by cutting the 11L track into CONTIGUOUS per-shot segments (never overlay one continuous track on independently-synced clips). Full method + decision tree in `audio-pipeline.md`.

**Cost (fast mode, 720p, 9:16):**
- 4-5 sec clip: ~10-15 credits
- 8 sec clip: ~25-35 credits
- 10 sec clip: ~40-50 credits
- 15 sec clip: ~50-60 credits

**Cost (std mode, same params):** roughly 2-3x fast mode. Not worth it for vertical 720p output.

**Queue time:**
- 5 sec clip: ~1-2 min
- 8 sec clip: ~2-3 min
- 15 sec clip: ~3-5 min

**Failure modes:**
- `nsfw` status: prompt triggered the content filter. NOT charged. Sanitize prompt and re-roll.
- `failed` status: technical error. NOT charged in observed cases. Re-roll once; if it fails again, simplify the prompt.

## NSFW trigger words to avoid

Observed triggers (sanitize even when used metaphorically):

**War / weapons:**
- "bombs" (any context, even "bombs of '45")
- "weapons", "guns", "shoot"
- "war", "battle", "kill"
- Specific WWII references: "'45", "1945", "Hitler", "Nazi"

**Violence:**
- "cut" (especially "cut me down", "cut into")
- "stab", "wound", "blood"
- "destroy" (sometimes, depends on context)

**Drugs / medical horror:**
- "pumped me full of"
- "injected" (less reliable; sometimes OK in clear medical context like "the doctor injected the syringe", but risky)
- "drugged", "high", "needle"
- "addict", "addiction"

**Sexual content:**
- Any explicit anatomy
- Innuendo even in cartoonish context
- Phrases like "stripped", "naked" (even of objects)

**Replacements that worked:**
| Triggered | Replacement |
|---|---|
| "they cut me down to half my size" | "they shrunk me down to half my size" |
| "pumped me full of nitrogen" | "fed me factory nitrogen" |
| "from the bombs of '45" | "short and dense is all they prize" (rewrote the line) |
| "Roundup ready" | "Chemical-ready" |
| "spraying glyphosate mist" | "leaving a trail of pale mist" |
| "crop duster spraying" | "agricultural plane flying" |

## Pre-flight checklist before any video gen

```
[ ] Audited existing assets in $ADGEN_HOME/<brand>/brand/ + concepts/*/ — no generic invention
[ ] Start frame composed (character + environment + props) and approved
[ ] Character contact sheet ready and passed as image ref (identity lock)
[ ] Audio ref uploaded if needed (Suno music or ElevenLabs VO)
[ ] Voice prompt language matches every other shot for that character (consistency)
[ ] Prompt scanned for NSFW trigger words (rewrote if any found)
[ ] Duration is 4-15 sec
[ ] mode: "fast", resolution: "720p", aspect_ratio: "9:16"
[ ] Higgsfield balance checked — sufficient credits for this gen + buffer
```

## Polling cadence

For checking job status:
- Image gens: every 20-30 sec
- 4-5 sec video: every 60 sec
- 8 sec video: every 90 sec
- 15 sec video: every 120 sec

Don't poll faster — wastes context and adds noise. The harness blocks long sleeps; chain shorter ones (`sleep 20; sleep 20; sleep 20`).

## Workspace selection

If the user is on a team plan with multiple workspaces, call `list_workspaces` first and confirm `is_selected: true` on the right one. If not, call `select_workspace` with the correct UUID. Otherwise generations go to the wrong account.

## Other models in the Higgsfield MCP (when to use)

**Don't default to these. They exist but aren't the workflow's primary tools:**

- `soul_2` — Higgsfield's portrait/UGC model. Better for realistic human portraits and fashion. Not great for cartoon/claymation characters.
- `marketing_studio_image` / `marketing_studio_video` — one-click product ads. Designed for fast e-commerce shots. Less control than nano_banana_2 + seedance pipeline. Use for very simple product-focused creative if the brand is e-commerce-only.
- `wan2_7`, `kling3_0`, `veo3_1`, `grok_video` — alternate video models with different audio behaviors. Don't switch mid-project (continuity rule). Evaluate at project start ONLY.

## When to escalate to a different model

- **Need exact celebrity-style voice → ElevenLabs voice clone** (external, then audio ref to seedance)
- **Need photorealistic human portrait → soul_2** (rare in our generative ad work)
- **Need the rap to sound like an actual rap → Suno** (external, then audio ref to seedance)

## Balance management

Check `balance` at the start of each phase:
- If credits < 200 at start of Phase 5 → warn the operator, offer to defer non-essential shots
- If credits < 50 mid-generation → STOP and surface; don't burn the buffer

Failed jobs (NSFW, technical) don't charge in observed cases. Confirmed by checking balance before/after a flagged job.

## What NOT to do

- ❌ Use std mode for cost-sensitive vertical work — fast is fine
- ❌ Generate at 4k for vertical 720p output — wasted resolution
- ❌ Default to soul_2 for character work — it's for portrait realism, not claymation
- ❌ Use seedance for static product shots — ffmpeg ken-burns is free
- ❌ Pass the same start_image to 5 different shots without varying — looks repetitive
- ❌ Skip the contact sheet step — it's the cheapest insurance against character drift
