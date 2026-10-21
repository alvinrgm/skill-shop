---
name: adgen-vertical-ad
description: End-to-end vertical ad production using Higgsfield (seedance + nano_banana_2) + ffmpeg + FCPXML. Triggered when the operator wants to produce a video ad for a brand from a PDP URL or brief. Encodes the full 7-phase pipeline (discovery, script, character + product refs, scene start-frames, video gen, audio stems, FCPXML deliverable) plus all hard-won pitfalls and recipes.
---

<!-- ═══════════════ FIRST-RUN ONBOARDING GATE ═══════════════ -->
## ⚙️ First run? Onboard before making any ad

**Gate:** if `.onboarded` does NOT exist in this skill's folder, do NOT start the ad workflow —
onboard first. If it exists, skip this section. (Re-onboard anytime: delete `.onboarded`.)

### Onboarding flow
1. **Pick the data root.** Ask the user for `ADGEN_HOME` (where their client work + `.env` + `lib`
   live); e.g. `~/adgen`. Suggest adding `export ADGEN_HOME=...` to their shell profile.
2. **Place the runtime.** Copy this package's `runtime/` into `$ADGEN_HOME`:
   `mkdir -p "$ADGEN_HOME" && cp -R runtime/lib runtime/CLIENTS.md runtime/requirements.txt "$ADGEN_HOME"/`
   then create their `.env`: `cp runtime/.env.example "$ADGEN_HOME/.env"` (only if absent).
3. **Health check.** Run `bash doctor.sh`. Read the ❌ list, then walk each **one at a time**:
   - **GEMINI_API_KEY** (images) → key at https://aistudio.google.com/apikey → paste it; write
     `GEMINI_API_KEY=…` into `$ADGEN_HOME/.env` (never echo it back).
   - **ELEVENLABS_API_KEY** (voice) → https://elevenlabs.io/app/settings/api-keys → same.
   - **python deps** → offer to run `pip install -r "$ADGEN_HOME/requirements.txt"`.
   - **ffmpeg** → offer `brew install ffmpeg`.  **whisper** → offer `pip install openai-whisper`.
   - **Higgsfield MCP** (video — the one doctor can't verify) → sign up https://higgsfield.ai,
     connect the Higgsfield MCP in Claude Code, then **verify by checking `generate_video` is
     actually callable**. If not, help them retry.
   - **Final Cut Pro 12.2** → manual (Mac App Store); only needed to finish the cut.
4. **Confirm green & mark done.** Re-run `bash doctor.sh`; with the MCP tools confirmed, write
   `.onboarded` (`date > .onboarded`). Then tell them: *"You're set — kick off with: make a vertical
   ad for [brand] (with a PDP URL or brief)."*

Keep it warm and one-dependency-at-a-time. Goal: a teammate who's never seen this is generating
their first frame in minutes.
<!-- ═══════════════════════════ END ONBOARDING GATE ═══════════════════════════ -->

# adgen-vertical-ad

End-to-end vertical ad production. Optimized for a claymation-mascot creative model. Produces a rough-cut linear stringout + an FCPXML project ready for the operator to finish in FCP 12.2 (mix music, layer captions, reframe to 4:5, ship).

## HARD RULES (read before doing ANYTHING)

→ **IMAGE GENERATION = Gemini "Nano Banana" via your Gemini key, NEVER Higgsfield.** Every image in this pipeline (character hero refs, contact sheets, environment sheets, scene start-frames, product hero composites) is generated through Google Gemini "Nano Banana" (Nano Banana **Pro** preferred) via the `google-genai` SDK + `GEMINI_API_KEY` (your key, in `$ADGEN_HOME/.env`). The canonical generator is **`scripts/gen_image.py`** (Gemini Nano Banana Pro via REST, supports the 4K size param the SDK doesn't) — it is aesthetic-NEUTRAL (passes your prompt verbatim), supports `--ref IMG` for the locked hero/contact-sheet, and is what you use for ALL stylized/claymation/cinematic/product work. **Do NOT use `lib/keyframe.py` for this pipeline, and do NOT hand-roll a one-off google-genai script.** `lib/keyframe.py` is the UGC iPhone-selfie SPECIALIST from a legacy UGC pipeline — it force-prepends an "amateur iPhone selfie, authentic UGC" style to EVERY prompt, which is wrong for claymation/cinematic. Reaching for keyframe.py, finding it's UGC-tuned, and then writing a one-off to escape it is a known trap (it created `gen_x_v4.py`-style sprawl) — `gen_image.py` already covers prompt + refs + size + aspect, so there's nothing a one-off buys you. **DO NOT call the Higgsfield MCP `generate_image` / `nano_banana_*` for images** — that bills scarce Higgsfield credits and is the wrong path (this rule exists because a past session burned the whole Higgsfield balance generating character heroes through the MCP). Higgsfield (`seedance_2_0`) is the **VIDEO** path only. Where any phase below says "Model: `nano_banana_2`", that means the **Gemini Nano Banana Pro path**, NOT the Higgsfield MCP. Exception: only if the operator explicitly says "use Higgsfield for this image."
→ **REAL-PRODUCT LOCK GATE — never invent a real product; match it from a photo ON DISK.** A real branded product (a bag, a bottle, a specific label) CANNOT be reproduced from a text description — Gemini invents a plausible-but-wrong package every time, and no amount of "explicit instructions about the packaging" fixes it. It MUST be matched from the actual product photo passed as `--ref` to `gen_image.py`. Enforce:
  → **A pasted/attached chat image is NOT a usable reference.** `--ref` needs a FILE PATH. If the user drops the product image into chat, SAVE it to `brand/refs/scraped/<name>.png` FIRST, then pass that path. (`gen_image.py` now hard-errors if a `--ref` path doesn't exist, and prints `⚠️ NO --ref` when it generates ref-less.)
  → **Verify the PDP scrape actually captured the product.** Many DTC/Shopify PDPs are JS-rendered, so crawling `<img>` in the static HTML returns nothing or just the logo. After Phase 0, `ls brand/refs/scraped/` and confirm a REAL product image landed. If it's empty/wrong, SAY SO and ask the user to drop the product photo — do NOT proceed to invent one.
  → **If `gen_image.py` prints `⚠️ NO --ref` for a product or any locked asset, STOP** — it's being invented. Get the real image on disk and re-fire with `--ref`. This is the Phase-3 product-contact-sheet discipline (`prompts/product-contact-sheet.md`): lock the package from the real photo ONCE, reference everywhere. Don't freelance product visuals from text. (Encoded after a fresh-operator run produced an invented package because no real product image ever reached `--ref`.)

→ **CORE REFERENCE SHOTS = 4K, highest quality (permanent).** Every locked reference — character hero refs, character/product/environment contact sheets, product hero composites — MUST be generated at **4K** (`scripts/gen_image.py --size 4K`, which is the default). These are the assets everything else is built from; they get the best quality. Lower res (1K/2K) is acceptable ONLY for throwaway/scratch frames, never for a locked reference. (4K needs the REST path in `gen_image.py` — the google-genai 1.47 SDK rejects `image_size`.)
→ **Folder discipline — ONE folder per brand, two levels deep.** Read the "Folder structure — the two-level law" section below BEFORE creating any files. There is exactly one `$ADGEN_HOME/<brand>/` folder; brand-global assets live in `<brand>/brand/`, each ad concept lives in its own `<brand>/concepts/<slug>/`. Never spawn sibling top-level folders for the same brand (e.g. `acme-parody/`, `acme-higgsfield/`). Run Phase 0 (folder bootstrap) FIRST, before any scraping or generation.
→ **ElevenLabs is the DEFAULT voice source (read fully):**
  → **For any character that SPEAKS, default to an ElevenLabs voice lip-synced inside seedance** via a `role: audio` ref. This is verified: seedance_2_0 accepts external audio and lip-syncs the mouth to it tight within a clip. A locked 11L voice stays identical within-clip, across-clips, AND across ads — which kills seedance native audio's #1 weakness (per-clip voice drift, mascot sounding different shot-to-shot). This is Strategy B and it is the norm now, not the exception.
  → **The method that keeps it drift-free (do this, don't overlay):** generate the full 11L track for the spot → cut into CONTIGUOUS non-overlapping per-shot segments at breath gaps (each ≥4s) → generate each seedance clip with `role: audio` = its own segment → concat. Each clip lip-syncs to exactly the audio it plays; assembled audio is continuous. NEVER overlay one continuous track on top of independently-synced clips (that's the old drift trap).
  → **Decide it at Phase 2**, surfaced from the breakdown.md voice columns. Pick/clone ONE locked voice per character. Use the operator's house narrator voice from the `reference/voice-consistency.md` registry (it ships empty: on the first spot, ask them to pick one and log its voice_id there); ask before picking a new one. NEVER use stock library voices (Brian/Aria/Roger) — they sound generic.
  → **Strategy A (seedance native voice) is now the EXCEPTION** — use only when no character speaks (pure visual + music + SFX), or when the operator explicitly wants a fast/cheap throwaway test cut and accepts the voice drift. Don't reach for 11L as a Phase-5 RESCUE for one bad seedance clip mid-spot (re-fire seedance instead) — but DO architect 11L upfront at Phase 2 as the default voice path.
  → See `reference/audio-pipeline.md` (decision tree + contiguous-segment method) and `reference/voice-consistency.md`.
  → **MANDATORY: `reference/elevenlabs-dialogue-emotion.md` — apply its pre-flight checklist to EVERY 11L generation.** For any shot with 2+ characters talking, use the **Text to Dialogue** endpoint (`lib/elevenlabs.py` → `dialogue()`), NOT concatenated single-voice clips — it models conversational flow (reactions, timing). Every line MUST carry ≥1 audio tag (`[nervous]`, `[deadpan]`, `[sighs]`, `[strong Brooklyn accent]`, etc.) matched to the character bible's `emotional_range`. Lock v3 expressive settings (stability 0.35-0.45, style 0.1-0.15, NEVER Robust), lock voice+seed per character (+ `previous_request_ids`), generate 2-3 takes and pick best. Enforced at generation time, not optional.
→ **SEEDANCE IP-FILTER STACKING — never name studios, films, archetypes, or iconic-imagery vocabulary in video prompts.** Higgsfield's `ip_detected` moderation runs a CLIP-style image+text matcher against an IP database. **Signals STACK** — one IP-coded word usually doesn't trip, but multiple stacking signals (studio + character + iconic setting + iconic palette) cross the threshold and block the job (and credits are charged on the failed attempt with no auto-refund). Discovered across two parallel sessions; ~225 credits burned diagnosing it. **NEVER include in seedance prompts:**
  → **Studios** — Aardman, Pixar, Disney, DreamWorks, Studio Ghibli, Laika, Sony Pictures Animation, Illumination
  → **Films / shows** — Wallace and Gromit, Toy Story, Yellowstone, Grapes of Wrath, Of Mice and Men, etc.
  → **Real people / actor archetypes** — Sam Elliott, John Dutton, "Most Interesting Man," Sheriff Woody, etc.
  → **Iconic-imagery vocabulary** — "Dust Bowl" (signals Grapes of Wrath / Dorothea Lange), "sepia" combined with character + dramatic setting (old-film register), "Western cowboy" stacking (cowboy hat + plaid + bandana + prairie + golden hour reads as cinematic Western and stacks)
  → **Brand mascots / licensed characters by name**
  **Replacements that pass:**
  → "Aardman / Pixar / Laika style" → "hand-thumbed plasticine clay surface with visible fingerprint impressions and slight frame-to-frame judder" (claymation)
  → "the claymation sponge-sheriff character" → "the clay character from the start frame" / "the figure from the reference image" — the start_image is the identity lock; don't restate identity in text
  → "sepia Dust Bowl plain" → "open parched plain" / "dim brown-tan plain"
  → "cowboy hat" → "wide-brim hat" / "brimmed hat"
  → "old-Western drawl" → "deep slow drawl"
  → "plaid flannel" → "checked shirt"
  → "bandana" → "neckerchief"
  → "prairie" → "open field"
  **Decision rule for prompts:** describe ACTION (what the character does) + ENVIRONMENT (where), NOT IDENTITY (who) or STYLE-BY-NAME. The start_image carries identity; the contact-sheet ref carries on-model lock; the text should be neutral physical description only.
  **PROACTIVE, not reactive — construct clean, don't write-then-scrub.** The seedance prompt is BUILT physical-description-only from the start, using the translation table in `prompts/seedance-shot.md`. Do not write a studio-named prompt and then try to fix it. **Gemini image prompts are EXEMPT** — naming "Aardman/Laika stop-motion style" in a Gemini Nano Banana image prompt is FINE and often useful (Gemini has no ip_detected filter). The ban applies ONLY to the seedance VIDEO prompt. When you adapt a Gemini start-frame prompt into a seedance prompt, TRANSLATE the studio/style language into physical description as a deliberate construction step. As a final tripwire before EVERY `generate_video` call, pipe the prompt through `scripts/lint_seedance_prompt.sh` — it blocks on banned vocab, music language, or a missing NO-MUSIC clause. The lint is insurance against a slip, not the mechanism; the mechanism is constructing it clean.
  **If a clip flags `ip_detected`:** don't wait (no cancel tool — the job sits forever). Audit the prompt for studio names, film names, iconic-coded vocabulary; resubmit immediately with neutral language. Credits on the flagged job are abandoned (no auto-refund observed). Brand-name lines in 11L audio are SAFE to attach — the brand name alone tested clean (a brand-name 1.6s clip passed seedance with a known-good start image). The trigger is text-prompt vocabulary stacking, NOT audio content.
→ **"Stringout" defaults to CONCAT EXISTING FILES, never fire new gens.** When the operator asks for a stringout or to see the cut → ffmpeg concat what's already on disk in the project's `clips/` folder, in script order. Do NOT interpret as "go generate the missing shots and then concat." If shots are missing from the cut, surface that as "we have N of M clips done, here's the partial stringout" and ask whether to fire the missing gens. Batch-firing gens without per-clip review burns credits on clips that won't survive the next review pass.
→ **FCPXML DELIVERABLE MUST HAVE EVERY AUDIO + VIDEO TRACK ON THE TIMELINE — never just imported as event assets.** The operator's hard rule: when they open `final/project.fcpxml` in FCP 12.2, **every clip and every audio file must already be placed on the timeline spine at the correct offset.** Narrator VO on lane -1, music bed on lane -2, per-clip audio stems on lane -3, etc. The whole point of the FCPXML workflow is that they don't manually drag anything from the event browser to the timeline — opening the project should show a complete, playable cut with all tracks audible.
  ❌ Wrong: import audio as an `<asset>` but only add video to the `<spine>`. Audio sits in the event browser, FCP plays silent video.
  ✓ Right: every audio file referenced in the project goes on the spine as a connected `<asset-clip lane="-N">` under the V1 clips (or as a long connected clip spanning the whole timeline for a continuous narrator/music bed).
  Per skill spec: A1 = per-clip native audio (on the asset-clip's primary lane); A2 (lane=-1) = narrator VO if Strategy B; A3 (lane=-2) = music bed; A4 (lane=-3) = per-clip stems if separately mixed. Use `scripts/fcpxml_gen.py` with `--narrator <path>` and `--music <path>` flags — those flags exist specifically to enforce this rule and place the audio on the timeline automatically. NEVER hand-author an FCPXML that omits any audio file from the spine. If the project has 11L narrator, music bed, AND per-clip stems → all three go on the spine, never just imported.
  **Why:** if the narrator or music bed exists only as a separate file on disk, the project opens as silent video and someone has to hand-patch the FCPXML to add it. Wire every audio file onto the spine at generation time.
→ **CTA must be SPOKEN VO**, not text-overlay-only. Bake the closing tagline into a character or narrator line. Text overlay is reinforcement, not primary delivery.
→ **15s max per seedance clip** (fast mode). Server silently clamps anything higher. Dialogue budget: ≤9 turns / ≤60 words per 15s.
→ **PRODUCT / LABEL hero shots → ken-burns over the locked 4K product composite, NOT seedance.** Seedance warps typography and packaging geometry even WITH product contact sheets passed as refs — product packaging can flip or mirror between shots, on-pack text comes out wrong, and structural details (seams, panels, closures) drift, even with heavy stability prompting and full-angle contact sheets. The contact sheet locks what the product LOOKS like for the model, but seedance still re-renders (and mangles) fine text + structure every gen. So for any shot whose job is "show the product / label clearly," skip seedance: take the locked 4K product hero composite (perfect text, generated via Gemini at Phase 4) and do a slow centered ken-burns push-in (see `reference/ffmpeg-cookbook.md` — pans IN toward a CENTERED product, zoom so slow it's near-imperceptible, product never leaves frame). Reserve seedance for shots where the product is in motion/handled and minor label imperfection is acceptable.
→ **When seedance blocks (ip_detected / nsfw twice), SURFACE it — never silently swap to a static ken-burns fallback.** A silently substituted static pan reads as an unexplained creative downgrade on review. If a shot can't pass seedance after the retry sequence, STOP and tell the operator: "shot N is blocked after retries; options are (a) re-storyboard the composition, (b) ken-burns over the start frame as a deliberate static shot, (c) drop it. Which?" Let them choose. A static substitute is a creative decision, not a silent fallback.
→ **Every recurring on-screen asset needs a contact sheet at Phase 3** (character OR product). Without locked refs, the asset's appearance drifts across shots. See `prompts/product-contact-sheet.md`.
→ **Locked-camera shots need the scene stability clause** in the prompt. See `prompts/scene-stability-clause.md`. Without it, the model adds props mid-shot.
→ **Do the work, don't summarize.** When the operator asks for a script, storyboard, dialogue table, or full breakdown — write it OUT, completely. No "[5 features stacked]" placeholders, no shorthand tables. If something is in the brief, spell it out. Tables with truncated descriptions are not deliverables.
→ **Pre-surface QA before claiming "done."** For every shot you intend to deliver: whisper-transcribe the audio to verify dialogue landed; extract frames at t=1, t=mid, t=end to verify no pop-ins and continuity matches prior shot. If any check fails → re-fire BEFORE telling the operator it's good.
→ **Agitate first, then benefit-drop.** Every script follows pain → product → benefit. The first 1-2 shots agitate the actual customer pain points using brand-native vocabulary and biological/sensory specifics (pinching, itching, brittle, cracked, dull-bladed, etc — pull these from the brief, never invent generic). The product-reveal shot drops named features as VO beats timed to product visuals (each beat = one feature). The closing shot has characters experience the benefits in real-time, then deliver the spoken CTA. NEVER write a script where pain is implicit or features are never named — the operator will reject it. Default first draft to this structure unless they explicitly override.
→ **ALWAYS surface generated assets two ways: a clickable link AND an auto-opened Finder window.** Every time you surface generated assets (image, video, audio stem, doc, sheet) for the operator to review:
  1. **Push the actual files via `SendUserFile`** so they're clickable directly in their chat client. (Plain markdown `file://` links may not render as clickable in the chat client — use SendUserFile for the files themselves; per the operator's standing rule this OVERRIDES generic relative-path link advice.) For multi-asset surfaces, send the set.
  2. **Auto-open a Finder window at the deliverables folder** with `open "$ADGEN_HOME/<brand>/concepts/<slug>/<subdir>"` (e.g. the `clips/`, `final/`, or `refs/scenes/` folder being reviewed). They asked for this explicitly — they want the folder popped open so they can browse siblings, not hunt for it.
  Do NOT just describe the asset, do NOT just say "saved to refs/", do NOT rely on a bare path they have to copy. They review on their laptop; the click + the open Finder window are the fastest paths to seeing the work. Audio files still open via QuickTime, never Music.app (`open -a "QuickTime Player" <path>`).
→ **AUDIO playback uses QuickTime, NEVER Music.app.** When you `open` an audio file (`.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`) for the operator to review, use `open -a "QuickTime Player" /path/to/file.mp3`. macOS routes audio files to Music.app by default, which auto-adds them to their music library — that's pollution they didn't ask for. QuickTime Player handles audio cleanly with no library side-effects. Apply this to every audio open command, including in shell scripts and helpers.
→ **BLUF / Minto surface style — show only what needs sign-off. Applies to EVERY surface, not just phase gates.** This includes mid-session status recaps, progress updates, "where are we" answers — not only the formal phase-end deliverables. Long explanation blocks don't get read — keep surfaces short, blunt, and scannable. Every surface follows this structure:
  → **Top line:** the decision or deliverable, 1-2 sentences
  → **What they must sign off on:** a numbered list of 2-4 concrete y/n or pick-one questions. NEVER more than 4. Each item phrased so they can answer in 1-3 words.
  → **What's next on "go":** 1 line telling them what I'll do once they approve
  → **Hide:** my thinking, alternatives I considered and rejected, justifications, my drafts, my reasoning chains, my exploration notes. These go to disk in the project folder (brief.md, breakdown.md, etc.) where they can read if they want — but they don't pollute the chat surface.
  Do NOT surface full deliverable text, observation lists, playback checklists, cost accounting, or multi-path comparison tables at every stage — sign-off requests get lost in the noise. The chat surface is for decisions, not for showing the work.

## Folder structure — the two-level law (READ BEFORE creating any files)

**Past mistake (since corrected):** this skill used to dump everything for a brand into one flat `$ADGEN_HOME/<brand>/` folder — brand bible, logo, product photos, refs, clips, and final all interleaved at the root. Running four concepts for one brand produced four sibling top-level folders (`acme/`, `acme-higgsfield/`, `acme-parody/`, `acme-identity-preserved/`) with the brand kit duplicated and scattered across them. The operator had to manually untangle it. Never again. There is exactly ONE folder per brand: brand-global assets are shared at the top, and each concept is isolated in its own subfolder.

**Canonical layout:**
```
$ADGEN_HOME/<brand>/
├── brand/                      # GLOBAL — shared across every concept. concept-agnostic.
│   ├── bible.md                # brand voice / positioning
│   ├── logo.png  font.png      # brand kit
│   ├── product-images/         # real product photography (front / back / lifestyle)
│   ├── reference-photos/       # founder / real-world reference shots
│   ├── moodboard/              # brand-level aesthetic board (only if reusable across concepts)
│   ├── refs/scraped/           # PDP-scraped images (durable — every concept can reuse)
│   ├── characters/             # OPTIONAL — recurring brand-mascot bibles + sheets (see promotion rule)
│   └── asset_inventory.md      # index of the brand kit
└── concepts/
    └── <YYYY-MM>-<slug>/        # ONE per ad concept. everything generated FOR this spot lives here.
        ├── brief.md
        ├── reference-spot-analysis.md   # Phase 1.5 (if a reference spot was given)
        ├── breakdown.md                 # Phase 2 — script + audio architecture
        ├── storyboard.md                # Phase 2 — visual composition
        ├── refs/
        │   ├── asset-lock.yml
        │   ├── characters/     # concept-specific character refs + bibles
        │   ├── environments/   # env contact sheets + single env refs
        │   ├── scenes/         # composed scene start-frames
        │   └── product/        # product hero composites for this concept
        ├── clips/              # shot_NN_<name>.mp4 (+ _silent.mp4)
        ├── audio/              # extracted stems + external VO / music
        ├── tmp/                # scratch
        ├── final/              # stringout.mp4, project.fcpxml, manifest.yml
        └── handoff/            # Phase 7 FCP-ready handoff bundle
```

**brand/ vs concept/ — the sorting rule:** if an asset is reusable by the NEXT concept for this brand without modification → `brand/`. If it was generated FOR this specific spot → the concept folder. Brand kit (logo, font, bible, real product photography, founder photos, scraped PDP imagery) is brand-global. Everything the pipeline generates (character refs, scene start-frames, environment sheets, product composites, clips, audio, stringout, fcpxml) is concept-local.

**Character promotion rule:** characters default to concept-level (`concepts/<slug>/refs/characters/`). The moment a character recurs in a 2nd concept as a brand mascot, promote its contact sheet + bible to `brand/characters/<name>/` and have both concepts reference it there. Don't duplicate a mascot's refs across concept folders — lock once, reference everywhere (same principle as the asset-lock spec).

**Concept slug convention:** `<YYYY-MM-DD>-<angle>-<protagonist>`, all lowercase kebab, NO spaces. e.g. `2025-03-14-sink-showdown-suds`, `2025-02-27-office-safari-otto`, `2025-03-14-city-launch-mom`.
- **`<YYYY-MM-DD>`** = the day the concept was first started (its origin date) — full date, so threads sort chronologically AND you can see when each began.
- **`<angle>`** = the creative archetype / hook (`origin-story`, `manifesto`, `sink-showdown`, `office-safari`, `city-launch`).
- **`<protagonist>`** = the character / POV carrying the spot (`suds`, `otto`, `mom`).
`init_concept.sh` enforces this (date + ≥2 descriptor tokens). Pick angle + protagonist from the concept, not the brand (the brand is already the parent folder). **Don't rename pre-convention concepts in place** — renaming breaks FCP's path-based asset uids and manifest refs (track grandfathered slugs in CLIENTS.md).

**Path convention for the rest of this skill:** unless a path is explicitly prefixed `brand/` (brand-global) or written as an absolute `$ADGEN_HOME/<brand>/...`, every relative path in the phases below (`refs/`, `clips/`, `audio/`, `final/`, `handoff/`, `breakdown.md`, etc.) is relative to the **current concept folder** `$ADGEN_HOME/<brand>/concepts/<slug>/`. That is the working root from Phase 1 onward.

### Phase 0 — folder bootstrap (do this FIRST, before Phase 1 scraping)

0. **Read `$ADGEN_HOME/CLIENTS.md` FIRST.** It is the canonical brand → folder-slug map. Do NOT infer the folder name from the full brand name (past bug: looked for `acme-widget-co/` when the folder is `acme/`). **Normalize the brand name at message 1** using the table there — e.g. "Acme" / "acme.example" → canonical **Acme Co** → folder `acme/`. If the client isn't in CLIENTS.md, it's new — add a row.
1. Resolve `<brand>` from CLIENTS.md (or kebab-case a genuinely new brand: "Example Pet Co" → `example-pet-co`).
2. **Create the concept with the helper — do NOT hand-`mkdir`:**
   ```
   ~/.claude/skills/adgen-vertical-ad/scripts/init_concept.sh <brand> <YYYY-MM-DD>-<angle>-<protagonist>
   ```
   It validates the naming convention, refuses spaces/missing-date/too-few-tokens, bootstraps the `brand/` skeleton if the client is new, REFUSES if the client folder is flat/legacy (tells you to migrate first), and creates the full concept skeleton (`refs/{characters,environments,scenes,product}`, `clips`, `audio`, `tmp`, `final`, `handoff`). This makes the folder law + naming convention PROACTIVE — you can't create a malformed slug or a sibling-folder mess.
3. **If the client folder is flat/legacy** (init_concept.sh will tell you), STOP and surface to the operator: "the `<brand>` folder is still flat/legacy-style — want me to migrate it to brand/ + concepts/ first?" Migrate before proceeding.
4. From here on: brand-global assets → `<brand>/brand/...`; everything this concept generates → `<brand>/concepts/<slug>/...`.

## Trigger

- "make a vertical ad for [brand] from [PDP url]"
- "produce a Higgsfield spot for [client]"
- "build me a video ad for [product]"
- Any context where the operator wants a finished generative video ad with rough cut delivered.

## Required reading order

When activated, read these in order:

1. This SKILL.md (you're here) — especially the HARD RULES section above.
2. `reference/PITFALLS.md` — actually-made mistakes. Read FIRST among references. (Note: 11L is now the DEFAULT voice source, not forbidden — see the audio HARD RULE above and `audio-pipeline.md`.)
3. `reference/voice-consistency.md` — how to keep character voices consistent across shots WITHOUT 11L.
4. `reference/audio-pipeline.md` — per-clip vs overlay drift rules. The biggest source of past iteration loops.
5. `reference/elevenlabs-dialogue-emotion.md` — **MANDATORY pre-flight for ANY 11L generation.** Text to Dialogue for multi-character shots, an audio tag on every line, expressive v3 settings, voice-lock continuity. APPLY the checklist, don't just read it.
6. `reference/asset-audit.md` — the audit-first hard rule AND the Phase 3 contact-sheet requirement (character + product).
7. `reference/asset-lock-spec.md` — per-project visual asset lock template.
8. `reference/higgsfield-models.md` — model params, costs, the 15s cap, NSFW trigger words, ip_detected retry rule.
9. `reference/ffmpeg-cookbook.md` — every command pattern the pipeline uses.
10. `reference/fcpxml-template.md` — schema + asset mapping + timeline structure for FCP 12.2.

Prompt templates live in `prompts/`. Required-use templates:
→ `prompts/breakdown-template.md` — Phase 2 combined script + audio track production document (the canonical Phase 2 deliverable; replaces the older split script.md + audio-mixed-in-cells approach)
→ `prompts/reference-spot-deconstruction.md` — Phase 1.5 5-axis analysis of any reference spot the operator shares
→ `prompts/handoff-manifest-template.md` — Phase 7 (and Phase 1 deliverable plan) FCP-ready handoff folder structure
→ `prompts/product-contact-sheet.md` — Phase 3 product packaging + bare product contact sheets
→ `prompts/character-contact-sheet.md` — Phase 3 per-character contact sheet
→ `prompts/environment-contact-sheet.md` — Phase 3 master-set environment contact sheet (any setting in 2+ shots)
→ `prompts/scene-stability-clause.md` — required for locked-camera seedance shots

Reusable scripts live in `scripts/`.

## Voice + brand rules carry over

If the operator keeps voice/writing rules in their `CLAUDE.md`, those apply to ALL prose output (brief writeups, script writing, surface messages). An example of the kind of house style this covers:
- All lowercase
- → arrows for lists, not bullets
- No em dashes (—). Use ellipses (...) or new sentences.
- No AI-isms ("here's the thing", "let me break it down", etc.)
- Lead with a number or sharp claim
- Educate before selling

For ad scripts specifically: characters can speak in any voice/dialect that fits the spot. **The brand voice rules apply to YOUR prose (brief writeups, surface messages, internal docs) — NOT to in-script character dialogue.** In-script dialogue uses normal capitalization, em dashes if natural for the character, whatever the character would actually say. House-style rules (e.g. lowercase-only) are for your messages to the operator, not for what a character says on screen.

## Image-prompt methodology carries over

Every STILL image in this pipeline is generated with `gen_image.py` (Gemini Nano Banana) — Phase 3 character/product bibles, Phase 4 environment + product refs, contact sheets, start-frames. For AUTHORING those prompts, use this still-image methodology: the Recipe (Subject → Background/Scene → Photography Style → Lens → Lighting → Mood), affirmative avoid-clauses (Gemini has no `--no` flag), precise materials, the **Object-Lock + Fail-Conditions** pattern for character/product consistency across frames, one-edit-at-a-time chaining, and Nano-Banana-Pro escalation for readable text / spatial work. That is the still-image authoring layer; seedance VIDEO prompts keep their own rules below (IP-safe, `NO MUSIC`).

**Before writing ANY contact sheet (Phase 3/4) or seedance prompt (Phase 5), reason through `reference/scene-dimensions.md`** — the generalized shot grammar (subject · optics · lighting · composition · environment · material · style-register · mood · consistency, plus the video-only layer: camera move · action · audio+NO-MUSIC · stability · IP-safe translation). Every dimension you leave blank, the model fills with its generic default. This is the "think through all the details" checklist; the still-image recipe above is its subset.

## The 7-phase pipeline

### Phase 1 — Discovery + asset audit

**Goal:** understand what we're selling and what we already have to work with. (Phase 0 folder bootstrap must already be done — `brand/` and `concepts/<slug>/` exist.)

Steps:
1. WebFetch the PDP. Parse: product name, ingredients/features, hero claims, price, target voice cues.
2. **LINK 1 — get the REAL product imagery on disk (enforced, do NOT skip).** Run
   `python3 scripts/pdp_scrape.py --url <PDP_URL> --brand <slug>`. It scaffolds the brand folder
   hierarchy and downloads via a reliability cascade: **Shopify product JSON → JSON-LD → og:image
   → `<img>`/srcset** (naive `<img>` crawling alone fails on JS-rendered DTC/Shopify pages — that's
   why this script exists). Images land in `<brand>/brand/refs/scraped/` (brand-global, every
   concept reuses them).
   → **If `pdp_scrape.py` exits non-zero (couldn't auto-download), STOP.** It has already created
   `<brand>/brand/product-images/` and printed exactly where to drop files. Ask the user to save the
   real product photos (front/back/hero) there, confirm they landed (`ls`), THEN continue.
   → **Never proceed to a product contact sheet or any product gen without a verified real product
   image on disk.** No real image → the product gets invented (the whole failure this prevents).
   This is the upstream half of the REAL-PRODUCT LOCK GATE; `gen_image.py --ref` is the downstream half.
3. Audit `$ADGEN_HOME/<brand>/brand/` for existing brand-global assets, AND skim `$ADGEN_HOME/<brand>/concepts/*/` for reusable refs from prior concepts (locked characters, product composites):
   - logo files (.png, .svg) — `brand/`
   - product images (front/back/lifestyle) — `brand/product-images/`
   - moodboard — `brand/moodboard/`
   - brand bible / voice docs — `brand/bible.md`
   - prior ad scripts / videos / locked characters — `concepts/*/` (candidates for the character-promotion rule)
4. Reverse-engineer the ICP from PDP language + price + claims. Cross-reference any analytics if available.
5. Write `brief.md` (in the concept folder: `concepts/<slug>/brief.md`) with sections:
   - Product summary
   - Hero claims (the 3-5 sellable benefits)
   - **Claim sourcing — REQUIRED for any factual or historical claim.** If the spot rests on a fact (an origin story, a founding date, a performance stat, a "made without Y" line), cite where it's verified BEFORE writing the script around it. Fact-check it now, not after the operator asks — everything in a brand video has to be legitimate and true. Flag claims you couldn't verify as ⚠ unverified so they don't get scripted as fact. Encode legal-safe phrasing here too (e.g. "made without added sulfates" not "sulfate-free" when trace amounts can't be ruled out; never assert a production technique that isn't true — e.g. don't claim "wood-fired roast" when the brand drum-roasts).
   - ICP (target audience, motivations, blockers)
   - Brand voice notes
   - Existing assets inventory
   - Missing assets (what we'd need to generate)
   - **Product-benefit → asset coverage matrix — REQUIRED.** List every product-led functional benefit (from Hero claims) in a table, mapped to which shot/asset delivers it. A benefit with no asset covering it is a gap — surface it. This prevents the campaign-asset failure where emotional/brand beats got covered but specific product benefits ("the ingredient quality," "the process," "the end result") were tackled by no video or static. Columns: `Benefit | Delivered by (shot # / static / none) | Notes`.
   - **Handoff plan** → the structure of the final FCP-handoff folder, locked at Phase 1 not invented at Phase 7. Required sub-sections:
     - Target duration (e.g., "30s / 45s / 60s")
     - Number of shots planned
     - Audio architecture (Strategy A per-clip / Strategy B continuous-narrator / hybrid — see `reference/audio-pipeline.md`)
     - Voice cast: per-character voice source (seedance vs 11L vs hand-recorded)
     - Music plan (Suno bed in FCP / per-clip seedance / none)
     - Captions plan (Captionator pass in FCP / baked in / none)
     - Reframe plan (9:16 first → then 4:5 / 1:1 / 16:9)
     - Deliverables folder structure (see `prompts/handoff-manifest-template.md`)

**Stop. Get the operator's sign-off before any generation.**

### Phase 1.5 — Reference-spot deconstruction (when applicable)

If the operator references a real spot, sketch, ad, or video as tonal/structural inspiration (e.g., "do it like a wildlife documentary" / "tonally like a late-night infomercial" / "structure like that Apple Vision Pro spot"), STOP at Phase 1.5 and write a `reference-spot-analysis.md` artifact.

Deconstruct the reference across 5 axes:
1. **Narrator architecture** — who carries the through-line? (testimonial first-person? omniscient narrator? in-scene-only dialogue?)
2. **In-scene moments** — what dialogue is lip-synced to on-screen characters?
3. **Music role** — score / source / silent / one continuous bed / per-scene shifts?
4. **Format-mimicry beats** — what genre conventions does it borrow (wildlife-doc hush, sportscaster register, infomercial cadence, etc.)?
5. **Punchline structure** — where does the joke / reveal / emotional landing happen? what supports it?

The reference-spot-analysis.md becomes input to Phase 2's breakdown. It locks the audio architecture decision BEFORE we get to generation. Without this step, we tend to copy the reference's visual tone but miss its structural backbone. Picking the wrong audio architecture (e.g. per-clip Strategy A when the reference is carried by a continuous narrator, Strategy B) is the expensive miss: it is only discovered at stringout and forces a rebuild.

See `prompts/reference-spot-deconstruction.md` for the template.

### Phase 2 — Concept + script + storyboard

**Goal:** lock the creative AND the visual frames before spending credits.

Steps:
1. Propose 2-3 wild concepts. Each should:
   - Have a clear narrative archetype (e.g., "kitchen sponge as a small-town sheriff", "pompous grease villain vs plant-based soap")
   - Reference visual aesthetics (claymation, lego, pixar, etc.)
   - Include a 6-8 shot outline
   - Have a clear hook and CTA
2. Use `prompts/concept-ideation.md` as the template.
3. The operator picks one (or rejects all and you propose more).
4. Write the full **breakdown**. Save to `breakdown.md` (this replaces the older split `script.md` + `storyboard.md` structure). **REQUIRED FORMAT: markdown table.** One row per shot. The breakdown is the Hollywood-studio-style pre-production document → it locks visual AND audio AND track sources in one place, so audio architecture cannot drift mid-production.

   Required columns:

   | # | Sec | Visual | In-scene dialogue (seedance) | Narrator VO (11L) | Music + SFX | Char refs | Env refs |

   - `#` — shot number
   - `Sec` — target duration in seconds
   - `Visual` — what happens on screen, including camera, characters present, action, key props. One paragraph max per row. Use `<br><br>` for line breaks within a cell.
   - `In-scene dialogue (seedance)` — dialogue lip-synced to on-screen characters, generated by seedance with native audio. Speaker labels in CAPS. Empty if no in-scene dialogue.
   - `Narrator VO (11L)` — voice-over delivered as overlay, not lip-synced. Generated separately (your locked 11L narrator voice) and mixed in. Empty if no VO.
   - `Music + SFX` — what music bed plays (Suno track / single swell / room tone only / silence), ambient/SFX descriptions in parens.
   - `Char refs` — which character refs (otto_sheet, coworker_extras, etc.) feed into this shot's start frame + seedance call.
   - `Env refs` — which environment refs (office_sheet, kitchenette, etc.) feed in.

   **Forcing functions baked into the columns:**
   → If a row has BOTH `In-scene dialogue` AND `Narrator VO` populated → flag in the row: hybrid audio shot, plan the overlay timing now.
   → If a row has ONLY `Narrator VO` and no in-scene dialogue → that shot is a silent-visual + VO overlay → can be ffmpeg ken-burns over a still instead of seedance video gen. Save credits.
   → If multiple rows share the same `Narrator VO` voice (e.g., the 11L narrator on rows 1, 2, 4, 6) → that's a Strategy B spot per `reference/audio-pipeline.md`. Generate the 11L track FIRST, before any seedance gens. Lock voice consistency upstream.

   See `prompts/breakdown-template.md` for the full template with worked examples.

   After the table, list the voice cast with source-of-truth per voice (seedance prompt language verbatim / 11L voice_id / hand-recorded).

   **STRUCTURAL DEFAULT — pain-agitate → product-feature-drop → benefit-embody → CTA.** Every script defaults to this arc unless the operator explicitly directs otherwise. Apply it shot-by-shot:

   - **Opening shots (~first 40-50% of runtime):** agitate the actual customer pain. Pull the pain vocabulary directly from `brief.md` — the brand's own language, not generic copywriting verbs. Get specific, biological, sensory. Examples that work: *"the elastic digs in. by noon there's a trench around your calf."* (compression socks: skin bite). *"the pan's still greasy after the second scrub. again."* (dish soap: stuck-on grease). *"the leaves are yellow at the tips. every week, more of them."* (houseplant food: a struggling plant). Each opening shot stacks 1-2 distinct pain notes. NEVER state the pain abstractly ("uncomfortable socks" / "greasy dishes" / "sad plants") — agitate it concretely.

   - **Product-reveal shot (~middle of spot):** product visible, characters absent or in VO. Each beat of the visible product reveal carries one named feature in the VO. If the product rotates 4 times, that's 4 feature beats. **Drop ≥2 distinct named benefits in the reveal — one differentiator is not enough.** The quality story needs multiple concrete claims, not a single attribute. Use the brand's exact feature claims from `brief.md` ("100% combed cotton", "double-reinforced heel", "seam-free toe"), not paraphrases. Storyboard for this shot MUST list the visual beats with their VO mapping (Beat 1: cotton ripple → "hundred percent combed cotton"; Beat 2: heel close-up → "double-reinforced heel"; etc). Cross-check against the brief's product-benefit → asset coverage matrix: the benefits you promised to cover here should actually be named here.

   - **Closing shot (~final 15-25%):** the same characters from opening, but the benefits are now physically embodied — what was pinched/loose, greasy/clean, dull/sharp, cracked/whole. Dialogue names the reversal in plain brand-voice ("no trench. no itch. forgot I had them on."). Final line of the spot is the spoken CTA with the brand URL or tagline ("[brand] dot com... your feet will thank you").

   **BRIDGE BEAT — required when the pain arc has a villain / historical-loss peak.** If the spot's pain arc isn't just "product is annoying" but "something was taken / lost / industrialized away" (lost-recipe revival spots, craft-revival spots, anti-corporate-villain spots, brand-as-survivor spots), the script MUST include a **"but I'm still here" bridge beat** between the loss-peak and the product reveal. Without it, the jump from "the big chains moved in / the old shop went dark / nobody made it by hand anymore" straight to "[product]. made the slow way." reads as a non sequitur — the audience doesn't yet know HOW the protagonist survived to be in the product. Specifically:

   - The bridge beat is 1-2 lines of VO at the end of the loss-peak shot, OR a dedicated transition shot before the product reveal
   - The beat names *survival + mechanism* — what kept the thing alive across the lost decades. Examples: *"they closed the old workshop. one family kept the recipe in a shoebox."* / *"they tried to replace us. a few of us kept doing it the slow way."* / *"everyone forgot it. then one stubborn shop started again."*
   - The beat is brand-narrative-true, not generic. For a brand-as-survivor story, find the real survival path (who actually kept the method or craft alive) and name it.
   - Without the bridge, the loss-peak → product-reveal cut reads as jarring: the viewer can't tell how the protagonist got from the loss to the product. The bridge must state that the thing still exists AND briefly how.

   This rule applies *in addition to* the pain → product → benefit arc, not instead of it. The bridge is an extra beat inserted between pain-peak and product-reveal whenever the pain peak involves loss/extinction/historical-villain framing.

   **Anti-patterns that get rejected:**
   - Cute / coy dialogue that doesn't name actual pain → rejected
   - Feature list dumped as text overlay only (no VO) → rejected, CTA-must-be-spoken extends to feature naming
   - Generic peril that could apply to any product → rejected, peril must be product-specific
   - Closing without a felt benefit reversal (characters just say "great product!") → rejected
   - Skipping pain because the product is "aspirational" → still rejected; even aspirational products need a "before" state to make the after meaningful
   - Loss-peak → product-reveal with no "but I'm still here" bridge → rejected per BRIDGE BEAT rule above

   First-draft heuristic: open every script writing session by jotting the pain → product → benefit → CTA arc as a 4-row sketch before writing the full table. That way the structure is locked before line-level word choice.

5. Write the FULL STORYBOARD. Save to `storyboard.md` (this stays a separate file alongside `breakdown.md` — the breakdown is for audio architecture + production planning; storyboard is for visual composition). **Required, not optional. REQUIRED FORMAT: markdown table.** One row per shot. Required columns:

   | # | Composition | Foreground / Mid / Background | Product variant | Lighting + Color | Camera + Action | 9:16 zones + Anti |

   - `Composition` — frame type (wide / medium / close / extreme close + angle: eye-level / low / high)
   - `Foreground / Mid / Background` — literal contents of each plane, named characters, props, setting details. Use **FG:**, **MID:**, **BG:** labels.
   - `Product variant` — **REQUIRED column.** The EXACT product SKU/variant visible in this shot (e.g. "Lemon 16oz bottle" vs "Unscented 16oz bottle" vs "refill pouch"). Empty if no product on screen. This is a per-shot pre-flight: past bug put the wrong variant in a shot that needed the regular one, caught only after the start-frame was generated. Naming the variant per row forces the check before the start-frame fires.
   - `Lighting + Color` — light direction + quality + mood, then color palette as `/`-separated list.
   - `Camera + Action` — camera move + speed + what happens during the shot.
   - `9:16 zones + Anti` — where elements sit vertically (upper-third, mid, lower-third), plus anti-instructions (NO captions / NO logo bake-in / etc.) and any reference brand asset that should anchor the frame.

6. Each storyboard row must be detailed enough to feed directly into `nano_banana_2` as a scene start-frame prompt in Phase 4. If a row is too vague to generate from, it's not a finished storyboard — go back and add detail.

**Stop. Get script + storyboard approval together before generating refs.**

**Format note (HARD):** both deliverables MUST be tables. Prose-paragraph format was rejected (the operator caught the gap on a dry run — paragraphs aren't scannable, tables are). Don't revert to prose even if it feels "richer" — the operator reads tables, not prose.

**Surface to the operator INLINE.** Don't link to the .md files and ask them to open them. Paste both tables directly in chat. They need to read them in-context, not file-hop. The .md files are persistent record; the chat surface is for review.

**Why storyboard is required:** without it, the next step (Phase 3 character refs and Phase 4 scene start-frames) is guessing at composition. The storyboard locks visual decisions before you spend credits. A skipped storyboard = expensive re-rolls when the generated frames don't match the imagined scene.

### Phase 3 — Character + product bibles (visual + voice unified)

**Goal:** build a complete identity map for each character AND each recurring on-screen product so seedance never has to guess. **The bible is the single source of truth — visual AND voice locked together.** Past mistake: visual ref and voice description lived in different files, and every shot's prompt drifted because nobody enforced the link. Fix: per-character bibles + per-product lock sheets.

**Product contact sheets are now REQUIRED at Phase 3** (added after a product drifted across shots, ~100 credits in re-fires). For every product or recurring physical asset that appears in 2+ shots, generate:
1. Packaging contact sheet (front / back / 3/4 / hero pull) — see `prompts/product-contact-sheet.md`
2. Bare product contact sheet (flat / in-hand / in-use / texture macro) — same template

Upload both to Higgsfield, store the media_ids in `refs/asset-lock.yml` per `reference/asset-lock-spec.md`, paste the locked `description_for_prompts` paragraph into every Phase 5 shot prompt that features the product. Same workflow as character contact sheets — locked once, referenced everywhere, no drift.

**Environment contact sheets are also REQUIRED at Phase 3 for any master set** (a master set that appears in several shots at different angles and times of day can't be locked by a single Phase 4 env ref). Decision rule:

→ Setting appears in **2+ shots** → generate an environment contact sheet at Phase 3.
→ Setting appears in **1 shot only** → single env ref at Phase 4 is fine (per the existing Phase 4 spec).

The environment contact sheet locks the room's geometry, materials, fixtures, and time-of-day variants so seedance has a complete spatial map — not just one camera angle. See `prompts/environment-contact-sheet.md` for the template. Generate one sheet per master set, upload to Higgsfield, store the media_id in `refs/asset-lock.yml`, pass it as `role: image` ref to every Phase 4 scene start-frame and every Phase 5 video gen that takes place in that setting.

Without environment contact sheets, master sets drift across shots → cabinets reposition, counter materials change, lamps shift, wall colors vary. Same drift problem character and product contact sheets solve. Catching this at Phase 3 saves an estimated 100+ credits in Phase 5 re-fires per master set.

**ALSO REQUIRED for any master set reused across 2+ cuts: a single LOCKED PLATE.** The multi-angle contact sheet TEACHES the model the space — it does NOT lock cut-to-cut continuity. Generating each start-frame independently against the sheet's many angles makes the model re-invent the room every gen (geometry shifts, on-screen text/digits render differently shot-to-shot). The fix: generate ONE canonical EMPTY plate at the hero camera + one lighting state (`refs/environments/<setting>_plate.png`, 4K, shot aspect), then composite EVERY start-frame into it by passing the plate as the **primary `--ref`** ("use this EXACT room, place characters inside"). Pin any on-screen text/digit/label in WORDS per shot. Record as `canonical_plate:` in `asset-lock.yml`. Full method + the division of labor (plate=geometry, word-spec=text, character sheets=faces) → `prompts/environment-contact-sheet.md`. (Without it, on-screen text such as a sign or clock tends to render differently in every frame.)

**Where character artifacts live:** concept-level by default → `concepts/<slug>/refs/characters/`. If this character already exists as a locked brand mascot in `brand/characters/<name>/` (from a prior concept), DON'T regenerate it — reference the brand-level bible + sheet directly. If a character you generate here later recurs in a 2nd concept, apply the character-promotion rule: move its bible + contact sheet up to `brand/characters/<name>/` and reference from both concepts.

For each named character, produce **THREE artifacts**:

1. **Hero ref** (1 image): `refs/characters/<name>_hero.png`
   - Gemini Nano Banana Pro via `scripts/gen_image.py`, **4K** (core reference shot), aspect 9:16
   - Use `prompts/character-ref.md` template
   - For evolved/related characters (e.g., a villain built from the hero's own world), pass the OG character image as `role: image` ref. Lineage preserved.

2. **Contact sheet** (1 image): `refs/characters/<name>_sheet.png`
   - Gemini Nano Banana Pro via `scripts/gen_image.py`, **4K** (core reference shot), aspect 16:9 (horizontal layout for the grid)
   - Use `prompts/character-contact-sheet.md` template
   - 3x3 grid: front, 3/4 left, side, 3/4 right, back, 3 expression close-ups, 1 detail study
   - Persistent identity reference passed to seedance for every shot featuring this character.

3. **Character bible** (1 YAML doc): `refs/characters/<name>.yml`
   - **REQUIRED, not optional.** Without this, voice drifts every shot.
   - Schema:
     ```yaml
     name: <character name>
     role: <one-line role in the spot>
     visual:
       hero: refs/characters/<name>_hero.png
       contact_sheet: refs/characters/<name>_sheet.png
       description: |
         <2-3 sentence visual description matching the contact sheet.
         Used in shot prompts as character description so seedance has
         identity anchor in TEXT in addition to the image refs.>
     voice:
       prompt_language: |
         <THE EXACT STRING used in every seedance shot prompt that features
         this character, verbatim. e.g., "gravelly Brooklyn dirt-creature voice,
         like a tired old building super, slightly drunk on his own importance".
         Never paraphrase across shots.>
       seedance_audio_anchor: |
         <Path to an mp3 extracted from the best seedance clip of this character's voice.
         Once locked, this audio is passed as `role: audio` ref to every future shot
         featuring this character so the voice timbre stays stable. Empty until first
         shot is generated and the operator approves the voice — then extract audio from that
         shot and lock it here.>
       accent: <e.g., "Brooklyn / outer-borough NYC", "small-town Western", "British academic">
       pitch: <deep / medium / high>
       pace: <slow / measured / fast / variable>
     emotional_range:
       default: <e.g., "gruff, self-important">
       angry: <e.g., "yelling, mouth wide, eyes narrowed">
       scared: <e.g., "trembling, voice cracks">
       defeated: <e.g., "slumped, weary">
       happy: <e.g., "beaming, tail wags">
     verbal_tics:
       - <e.g., "drops 'g' on -ing words: 'experimentin', talkin'">
       - <e.g., "starts complaints with 'oh you have GOT to'">
       - <e.g., "interrupts Fern with 'nobody asked, Fern'">
     ```

**Generation flow within Phase 3:**

a) Generate hero ref → surface, get approval.
b) Generate contact sheet using hero ref as image input → surface, get approval.
c) Write the YAML bible using all decisions made so far. Include voice prompt language. Leave `elevenlabs_voice_id` blank initially — surface to the operator to lock the voice.
d) Once the operator locks voice IDs, fill them in. The bible is now complete.
e) For evolved/related characters, pass the OG character's contact sheet AND OG character's bible's voice description to anchor lineage in both visual and voice.

**Surface all character bibles to the operator together** (visual refs + YAML). **Stop for approval of the full bible — visual + voice — before any video gen.** Iterate on character design AND voice IDs before Phase 4.

**Why this matters:** every Phase 5 video gen prompt for a character pulls the voice description verbatim from the bible. No "summary" or paraphrase. The bible is loaded → voice prompt language is inserted into the seedance prompt → consistency across shots is guaranteed by file, not by memory.

### Phase 4 — Environment + product refs

**Goal:** generate scene start-frames that compose character + setting + props.

**STEP 0 — classify every shot boundary as NEW SCENE or CONTINUATION before generating ANY start-frame.** A start-frame is generated ONLY for a NEW SCENE. A CONTINUATION shot does NOT get a generated start-frame at all — its start frame is the PREVIOUS clip's extracted last frame, produced at Phase 5 (continuity chaining). Generating an independent start-frame for a continuation shot is what causes the "characters teleported" hard cut, AND it's wasted gen spend. Classify:
   - **NEW SCENE** (generate a start-frame here): the opening shot; any cut to a new location, new time, or new camera/angle that isn't a smooth continuation (e.g. the product void, a later "after" beat). 
   - **CONTINUATION** (do NOT generate — chain at Phase 5): the next shot is the same scene, same moment, characters mid-motion from where the previous shot ended (the beat just keeps rolling).
   Record the classification per shot in the storyboard/breakdown (a `Boundary: NEW | CONT (chains shot N)` note) and in `asset-lock.yml`. Then generate start-frames for the NEW-scene shots only.

1. **Environment refs** (one per setting in the script):
   - **For master sets (2+ shots): use the Phase 3 environment contact sheet directly. Skip generating a separate single env ref — the contact sheet already locks the geometry.**
   - **For single-shot settings only:** generate a single env ref:
     - `nano_banana_2`, 1k, 9:16
     - Pure environment, no character
     - Save to `refs/environments/<setting>.png`

2. **Composed scene start-frames** (one per NEW-SCENE shot ONLY — skip CONTINUATION shots per Step 0):
   - `nano_banana_2`, 1k, 9:16
   - Combine character + environment + props for a specific shot's opening frame
   - Pass character contact sheet as `role: image`
   - Save to `refs/scenes/shot_NN_start.png`
   - **Do NOT generate one for a CONTINUATION shot.** That shot's start frame is the previous clip's last frame, extracted at Phase 5 (`ffmpeg -sseof -0.1 ... -frames:v 1`). At Phase 4 just note "shot N+1 start = shot N last frame (chained at Phase 5)."

3. **Product hero composites** (for CTA shots):
   - Gemini Nano Banana Pro via `scripts/gen_image.py`, **4K** (core reference shot), 9:16
   - Pass actual product image as a reference (`--ref <path>`). **PRESERVE THE PRODUCT EXACTLY.** Do not invent generic versions.
   - Place product in branded scene (sunlit bathroom shelf, workshop bench, etc.)
   - Leave clean negative space top + bottom for text overlay (added in FCP, not baked in)
   - Save to `refs/product/hero.png`

Surface all start-frames. **Stop for approval before video gen.**

### Phase 5 — Video clip generation

**Goal:** produce numbered video clips, each 4-15 sec, with locked character identity.

For each shot in the script:

1. Build seedance call:
   - Model: `seedance_2_0`
   - `mode: "fast"` (cheap, sufficient quality for vertical)
   - `resolution: "720p"`
   - `aspect_ratio: "9:16"`
   - `duration`: per shot need (4-15 sec)
   - `medias`:
     - `start_image`: the composed scene start-frame from Phase 4 — **EXCEPT when this shot is a continuous beat following the previous one (see CONTINUITY CHAINING below): then start_image = the previous clip's extracted LAST FRAME, not an independently-generated frame.**
     - `image` (additional ref): the character contact sheet (identity lock) — keep passing this even when chaining, to hold facial identity through motion.
     - `audio`: only if music/lip-sync sync is needed (rap, jingle). Otherwise omit.
   - `prompt`: visual + AUDIO description with EXACT character voice prompt language (consistent across all shots for that character)

   **CONTINUITY CHAINING (do this for any two consecutive shots in ONE continuous scene — prevents the "characters teleported" hard cut).** The locked plate keeps the ROOM identical across shots but does NOT keep the PEOPLE in continuous poses — independently-generated start-frames re-pose everyone, so the cut jumps. Fix: after shot N renders and is approved, extract its final frame (`ffmpeg -sseof -0.1 -i clips/shot_0N.mp4 -frames:v 1 -update 1 refs/scenes/shot_0M_start_chained.png`), upload it, and use it as shot N+1's `start_image`. Open shot N+1's prompt with "DIRECT CONTINUATION — the start frame IS the previous clip's final frame; continue their motion, do NOT re-arrange anyone," and write the action as forward motion (confetti settles, eyebrows rise, counter ticks down). Only generate an INDEPENDENT start-frame when the boundary is a deliberate hard cut to a new time/angle/location (e.g. cutting to the product void). Decide per shot-boundary which are "continuous" (chain) vs "hard cut" (independent). See `reference/PITFALLS.md` → "Consecutive shots ... chain the previous clip's LAST FRAME."

2. **Static product/food shots AND any product/label hero shot: SKIP seedance entirely.** Use ffmpeg ken-burns over the locked 4K product composite. Per the HARD RULE: seedance warps on-pack text + packaging geometry even with contact-sheet refs, so any shot whose job is "show the product/label clearly" goes ken-burns (centered, near-imperceptible slow push-in) over the Gemini composite that has perfect text. See `reference/ffmpeg-cookbook.md` for the recipe (it pans IN toward a centered product; product never leaves frame).

3. **NSFW sanitization:** Before sending the prompt, scan for trigger words (war, drugs, violence — see `reference/PITFALLS.md` for the full list). Rephrase any flagged language.

4. **Pre-surface QA checklist (MANDATORY before showing the operator).** Do every check yourself first. If any fails → re-fire BEFORE telling the operator it's good.
   - **Audio (whisper transcript):** extract audio with ffmpeg, run whisper, verify every scripted line landed. No dropped beats, no garbled words, no stage directions read as dialogue.
   - **Visual continuity:** extract frames at t=1, t=mid, t=end. Verify (a) no objects appear mid-shot that weren't in the start frame, (b) environment matches the prior shot.
   - **CTA check (if this is the CTA shot):** confirm the CTA tagline is delivered as SPOKEN VO, not just text overlay.
   - **Voice diff (if 2+ characters):** spot-check pitch contrast via the analysis pattern in `reference/voice-consistency.md`. If voices are >85% identical, that's a known seedance limitation — surface as a tradeoff, do NOT propose 11L.
   - **Asset match:** if the shot features a locked product/character, verify the on-screen appearance matches the contact sheet.

5. Surface each clip individually for the operator to review with a "things to listen/look for" checklist:
   - Voice match (does character sound consistent with prior shots?)
   - Lip sync quality
   - Visual fidelity to the character / product refs
   - Action / camera move landed
   - Any drift, glitch, or off-model details

6. Save raw clip with native audio: `clips/shot_NN_<name>.mp4`

Iterate per-shot until each is approved. Don't batch all shots → composite → review — that's an iteration trap. Approve each shot first.

### Phase 6 — Audio stem extraction

**Goal:** give the operator separate video + audio so they can mix in FCP.

For each approved clip:

1. Extract video-only:
   ```bash
   ffmpeg -i clips/shot_NN_<name>.mp4 -an -c:v copy clips/shot_NN_<name>_silent.mp4
   ```

2. Extract audio stem:
   ```bash
   ffmpeg -i clips/shot_NN_<name>.mp4 -vn -acodec libmp3lame -b:a 192k audio/shot_NN_<name>_audio.mp3
   ```

3. If a shot has external audio (ElevenLabs VO, Suno music) saved separately, those go alongside in `audio/` with descriptive names (e.g., `shot_03_rap_suno.mp3`, `shot_05_vo_narrator.mp3`).

### Phase 7 — Deliverables

**Goal:** package everything for the operator to finish in FCP 12.2.

1. **Linear stringout** (`final/stringout.mp4`):
   - ffmpeg concat all numbered clips in script order, WITH their native audio
   - NO crossfades, NO smoothing, NO color grading
   - Hard cuts only — preserves the operator's ability to edit cleanly in FCP
   - See `reference/ffmpeg-cookbook.md` for the exact concat command

2. **FCPXML project** (`final/project.fcpxml`):
   - Generate per `reference/fcpxml-template.md` (FCP 12.2) using `scripts/fcpxml_gen.py`.
   - Reference all clips by absolute path: `$ADGEN_HOME/<brand>/concepts/<slug>/clips/...`
   - Place clips on V1 timeline in script order at correct in-points.
   - Audio on A1 (per-clip native), A2 (separate VO stems if any), A3 (placeholder for music).
   - Project settings: 720x1280, 30fps (or whatever the seedance output is — verify with ffprobe).
   - **FCP library/event/project conventions (the operator's setup — apply EVERY time):**
     → Hierarchy on the operator's FCP side is FLAT: library → event → project. FCPXML's DTD does NOT permit project-grouping folders at either level — past sessions burned import attempts with DTD errors trying `<folder>` inside `<library>` AND inside `<event>`. The script's `--folder` flag is deprecated/warn-and-ignore.
     → **Library = your master ads library** (e.g. `Client ads`). Have it active in FCP before importing.
     → **Event = client name** — `Acme Co`, `Example Brand`, etc. ONE event per client. Re-imports with the same event name merge in place instead of spawning duplicates.
     → **Project = concept name** — `Sink Showdown`, `Office Safari v4`, etc. Multiple concepts per client = multiple sibling projects within the same client event.
     → **Timeline iterations** of one concept (cut variants, aspect-ratio reframes) use project-name suffixes: `Sink Showdown — v1`, `Sink Showdown — 9x16`, `Sink Showdown — 4x5`.
     → **Canonical CLI:** `python3 scripts/fcpxml_gen.py --output final/project.fcpxml --project-name "<Concept>" --event "<Client>" clips/shot_*.mp4`
     → **Manifest field for posterity:** `event: "<Client>"` and `project_name: "<Concept>"` in the concept's `manifest.yml`.
     → **If an old event name gets stuck in the operator's library** (e.g. from a prior import with a different convention), don't re-rename in the FCPXML — fix it FCP-side: drag the orphan event's contents into the canonical event (same-library drag = move, not copy), then right-click → Delete Event on the now-empty orphan.

3. **Manifest** (`final/manifest.yml`):
   ```yaml
   brand: <name>
   created: <iso timestamp>
   total_duration: <seconds>
   credits_used: <higgsfield credits this run>
   clips:
     - id: shot_01_intro
       file: clips/shot_01_intro.mp4
       duration: 5.04
       character: amber
       audio_source: seedance_native
       prompt: "..."
       reference_refs:
         - refs/characters/amber_sheet.png
         - refs/scenes/shot_01_start.png
     - id: shot_02_lab
       ...
   characters:
     - name: amber
       hero_ref: refs/characters/amber_hero.png
       sheet_ref: refs/characters/amber_sheet.png
       voice_prompt: "dry, steady, small-town sheriff voice with a slow drawl"
   open_issues:
     - <anything you flagged>
   ```

4. Surface deliverables to the operator with:
   - Path to .fcpxml
   - Total duration
   - Total credits used
   - Anything left manual (music, captions, reframe to 4:5)
   - Manifest summary

## Phase boundaries — non-negotiable

Each phase ends with a STOP. Surface deliverables, wait for approval. Do not auto-proceed to the next phase.

The skill is built for many small approval gates, not one big delivery. Iteration cost compounds — catching wrong character design at Phase 3 saves 10x credits vs catching it at Phase 5.

## Cost expectations

For a 50-60 sec ad with 6-8 shots:
- Discovery + script: $0
- Character refs (2 chars × hero + sheet): ~50-80 credits
- Scene start-frames (6-8 shots × ~10 credits): ~60-80 credits
- Product hero: ~15-30 credits
- Video gens (6-8 shots × 10-50 credits each, fast mode 720p): ~80-300 credits
- Buffer for re-rolls: ~100-200 credits
- **Total: ~300-700 credits per ad** ($12-28 at current pricing)

For brand-consistent series (same characters): credits go down per ad after the first because character refs are reusable.

## ElevenLabs is the DEFAULT voice source

**Superseded the old "11L is forbidden" rule.** For any speaking character, default to
an ElevenLabs voice lip-synced inside seedance (`role: audio`), per the HARD RULE near the top and
the Strategy B decision tree in `reference/audio-pipeline.md`. The reason: seedance native audio
drifts in timbre clip-to-clip; a locked 11L voice is identical within-clip, across-clips, and across
ads. The ElevenLabs client is wired at `lib/elevenlabs.py` (key in `$ADGEN_HOME/.env`); usage
patterns are in `reference/audio-pipeline.md`; your locked voice ids live in `reference/voice-consistency.md`.

The one thing 11L is still NOT for: a Phase-5 RESCUE of a single bad seedance clip mid-spot. If a
clip's voice is off, re-fire that clip (with its locked audio segment) — don't bolt on a different
toolchain mid-production. Architect the 11L voice path UPFRONT at Phase 2, not as a late patch.

Make the voice drift-free with the contiguous-segment method (full track → contiguous per-shot
segments → lip-sync each clip to its segment → concat). NEVER overlay one continuous track on top of
independently-synced clips. NEVER use stock library voices (Brian/Aria/Roger) for brand work.

## Honesty rules

→ Don't claim "verified" for anything you didn't actually look at / listen to.
→ When you can't watch a video back (no audio capability), surface it: "the operator needs to listen to clip X for [aspect]."
→ When you waste credits, state it plainly with cost + cause.
→ When you change approach mid-iteration, call out the continuity break and ask before doing it.
→ When the model produces unexpected output that's actually good, surface and ask "should we lean into this?" before discarding.

## Hand-off to manual phases

The deliverable handoff message should look like:

```
Ad rough cut ready. Open final/project.fcpxml in FCP 12.2.

Linear stringout: final/stringout.mp4 (NN seconds)
Total credits used: NNN of [starting balance]
Concept files: $ADGEN_HOME/<brand>/concepts/<slug>/
Shared brand kit: $ADGEN_HOME/<brand>/brand/

Still manual on your side:
→ Music in Suno (suggested prompt: <one-line music prompt fitting the spot's tone>)
→ Captions in Captionator
→ Reframe to 4:5 in FCP (after 9:16 approval)
→ Final mix + export

Open issues: <any>
```

## Prompt templates

See `prompts/`:
- `concept-ideation.md` — generates 2-3 ad concepts from brief
- `script-writer.md` — shot-by-shot script format
- `character-ref.md` — single character hero shot
- `character-contact-sheet.md` — 3x3 grid identity reference
- `seedance-shot.md` — video gen template with all defaults
- `elevenlabs-vo.md` — VO generation with inline tags

## Scripts

See `scripts/`:
- `init_concept.sh` — **Phase 0 concept creator.** `init_concept.sh <brand> <YYYY-MM-DD>-<angle>-<protagonist>`. Validates the naming convention, bootstraps the `brand/` skeleton for new clients, refuses flat/legacy clients, creates the full concept skeleton. The ONLY sanctioned way to start a concept — do not hand-`mkdir`.
- `gen_image.py` — **canonical image generator.** Google Gemini Nano Banana Pro (`gemini-3-pro-image-preview`) via REST on your `GEMINI_API_KEY`. Defaults to **4K** (core-reference quality). `--out PATH --prompt "..." [--prompt-file F] [--size 1K|2K|4K] [--aspect 9:16|16:9] [--ref IMG ...]`. This is the ONLY sanctioned image path — never the Higgsfield MCP.
- `lint_seedance_prompt.sh` — **final tripwire before every `generate_video`.** `lint_seedance_prompt.sh prompt.txt` (or pipe via stdin). Blocks on IP-coded studio/film vocab, music-generation language, or a missing NO-MUSIC clause; warns on NSFW triggers. Insurance against a slip — the real fix is constructing the prompt clean (physical description only). Exit nonzero = do not submit.
- `pdp_scrape.py` — fetch PDP HTML, parse product details, download all images
- `fcpxml_gen.py` — build FCPXML 1.13 from clips + audio. **Use `--auto-audio <concept>/audio/`** to auto-discover and PLACE every audio stem on the timeline (narrator → lane -1, music → lane -2, per-shot stems → lane -3); it warns about any file it can't classify so nothing silently drops off the spine. Explicit `--narrator/--music/--stems` override.
- `stringout.sh` — ffmpeg concat → stringout.mp4

## Modesty

Most ads should follow the pipeline as written. Don't reinvent the structure per project. The script changes, the characters change, the product changes — the pipeline doesn't.

If you're tempted to skip a phase or merge two ("we don't need separate character ref + contact sheet for this simple ad"), DON'T. Skipping the contact sheet is exactly what made shot 3 of a past spot drift. The pipeline phases exist because each one prevented a specific past failure.

If you genuinely need to deviate, surface to the operator first with the reason. They'll either approve the shortcut or remind you why we have the rule.


---
Built and battle-tested at [Rise Growth Marketing](https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=adgen-vertical-ad). More free skills, and the story of the systems behind them, at that link.
