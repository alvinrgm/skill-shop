# PITFALLS — actually-made mistakes from past sessions

Read this FIRST when activating the adgen-vertical-ad skill. Every mistake below was made on a real project. Each costs time, credits, or trust. Don't repeat them.

Format: ❌ what was done wrong / ✓ correct approach / ⚠ root cause to internalize

---

## HARD RULE: Higgsfield media ingestion — WAV audio, PNG frames, and a ~10-15 min RESIZE LAG before generation works (cost ~1 hour)

Getting Gemini-generated start-frames + ElevenLabs audio INTO seedance via `media_upload` is the
single most fragile seam in the pipeline. A whole session was lost re-discovering these. Internalize:

❌ **MP3 audio is silently dropped.** `media_upload` + `media_confirm` of an `.mp3` returns
`status:"uploaded"` but the audio NEVER registers (`show_medias type=audio` stays empty) and
generation fails `media input not found`. ✓ **Upload audio as WAV** (`ffmpeg -ar 44100 -ac 2 -c:a
pcm_s16le out.wav`). WAV registers and works. (The presigned URL may be named `.mp3` regardless —
PUT the WAV bytes with `Content-Type: audio/wav`; it still works.)

❌ **JPEG start-frames don't register; PNG does.** A downscaled `.jpg` PUT to the (always-`.png`-named)
presigned object confirmed "uploaded" but failed `media input not found` in generation, while a `.png`
of the same frame worked. ✓ **Upload start-frames + contact sheets as PNG.**

❌ **The killer: uploaded media has a ~10-15 MINUTE internal RESIZE LAG before generation can use it.**
`media_confirm` returns "uploaded" instantly and `curl`-ing the read URL returns HTTP 200 within a
minute — but `generate_video` still rejects it with `media input not found` (or a flapping
`Something went wrong`) for ~10-15 min. The tell: a WORKING generation's media URL has a **`_resize.jpg`**
suffix — Higgsfield serves generation from an internally-resized copy, and that resize job is what lags.
`curl`-200 ≠ generation-ready. The error FLAPS between `media input not found` and `Something went
wrong` while the resize is in flight; both mean "not ready yet," not "wrong call."
  ✓ **Workflow:** upload ALL frames + audio for ALL shots EARLY (one batch), then WAIT ~12-15 min
    (they resize in parallel), THEN fire the gens. Don't upload-then-immediately-generate per shot.
  ✓ Preflight `get_cost:true` does NOT validate media availability (it priced media that then failed
    submission) — it is NOT a readiness check. The only real check is a successful submit.
  ✓ Earlier spots did NOT hit this because their start-frames were Higgsfield image-GEN jobs
    (`type:"image_job"`, instantly available). Our Gemini→`media_upload` frames (`type:"media_input"`)
    carry the resize lag. Same call shape, different ingestion path. (We still use Gemini for images per
    the cost HARD RULE — just budget for the lag.)

❌ **Higgsfield image moderation flags fleshy/anatomical stylized imagery as NSFW at `media_confirm`**
(returns `status:"nsfw"` on confirm, and the media is unusable). A dim, fleshy-pink "stretchy skin"
frame tripped it; a bright, clean, clearly-cartoon toy-world version of the same composition passed.
✓ For anatomically-adjacent concepts (body-care or anatomy-themed mascots), render the start
frames BRIGHT, smooth, toy-like, explicitly non-fleshy. Check the `media_confirm` status field for
`"nsfw"` and regenerate tamer before wasting a generation attempt.

✓ **Decline the preset popup:** seedance often returns a `preset_recommendation` notice instead of
submitting. Resubmit with `declined_preset_id: "<id>"` to generate literally.

⚠ Root cause of the lost hour: treating an intermittent "media input not found" as a fatal/platform
error and thrashing on format/size workarounds, instead of recognizing it as a propagation/resize lag
that clears on its own. When uploads confirm + curl-200 but generation says "media not found," the
answer is almost always WAIT, not re-upload.

---

## HARD RULE: FCPXML clip offsets MUST accumulate in FRAMES, never seconds

❌ **Wrong (a mascot origin spot — the operator caught a 1-frame black gap between shots 2 and 3 with a screenshot):**

```python
offset_sec = 0.0
for p in probed:
    write_clip(offset=seconds_to_rational(offset_sec, 24, 1),
               duration=seconds_to_rational(p["duration"], 24, 1))
    offset_sec += p["duration"]   # ← accumulates UNROUNDED float seconds
```

`seconds_to_rational()` rounds each clip's duration independently to frames at write time. But the accumulator stayed in unrounded seconds, so the NEXT clip's offset got rounded AGAIN — and the two roundings disagreed. Concrete drift at 24fps:

- Shot 1 dur=5.06s → `round(5.06*24)=121` frames written as `121/24s`
- Shot 2 dur=10.05s → `round(10.05*24)=241` frames written as `241/24s`
- Shot 2 ends at frame **121+241=362**
- BUT shot 3 offset = `round((5.06+10.05)*24) = round(362.64)` = **363**
- → 1-frame black flash between shots 2 and 3 on the FCP timeline

✓ **Right — accumulate timeline position in INTEGER frames:**

```python
offset_frames = 0
for p in probed:
    dur_frames = round(p["duration"] * fps_num / fps_den)
    write_clip(offset=f"{offset_frames * fps_den}/{fps_num}s",
               duration=f"{dur_frames * fps_den}/{fps_num}s")
    offset_frames += dur_frames   # ← integer math, zero drift
```

Each clip starts on the exact frame the previous one ends. Mathematically impossible to get a gap.

⚠ **Root cause:** mixing rounded (frames) and unrounded (seconds) representations of the same quantity in one accumulator. Every rounding step injects up to half a frame of error; floats accumulate; eventually error crosses a half-frame and the rounded result shifts by one — visible as a black flash.

**Rule for any code generating a frame-locked timeline (FCPXML, Premiere XML, EDL, AAF, etc.):**

- Accumulate timeline position in **integer frames**
- Build rational time strings DIRECTLY from the integer frame count
- Never re-round a float-seconds sum to frames mid-timeline
- The only conversion to seconds is for *reporting* (total runtime in stdout), never for placement math
- If you see `offset_sec +=` / `current_time +=` / `cursor +=` in timeline-building code, stop. Use `offset_frames +=` instead.

Encoded as a block comment at the clip-placement loop in `scripts/fcpxml_gen.py` so the rule survives the next refactor. The operator sees these black flashes immediately when reviewing a cut. They WILL catch them.

---

## HARD RULE: FCPXML asset uids MUST stay stable across regenerations of the same file

❌ **Switched `stable_uid()` from path-hash to content-hash mid-project on a mascot origin spot.** The intent was to make uids survive folder renames. But FCP had already cached uids from the path-based scheme during the first import. On the next regeneration, the same files now had DIFFERENT (content-based) uids, and FCP rejected with: *"The media already exists in the library with a different unique identifier."* Even deleting the project + restarting FCP didn't evict the cached uid binding — FCP libraries persist their asset registry separately from project references. The operator couldn't import the regenerated FCPXML at all until the script reverted to path-based hashing to reproduce the cached uids.

✓ **Pick ONE uid scheme and don't switch.** Path-based hashing is the current default in `stable_uid()` — fast, deterministic, no file read required, and once cached by FCP it stays consistent across re-imports as long as the file path doesn't change. The trade-off is that renaming the concept folder breaks re-imports for that project — recovery requires fully evicting FCP's cached assets (delete project, delete clips from events, restart FCP) before re-importing.

⚠ **Root cause:** FCP caches the FIRST uid it sees for a given file at the library level. Once cached, subsequent FCPXML imports MUST reproduce that same uid for that same file. Changing the hash scheme — for ANY reason — guarantees a uid mismatch and a refused import.

✓ **Recovery if uid scheme drifts:**
  1. Read FCP's error dialog — it tells you the cached uid (e.g., `61D4711E-...`).
  2. Reverse-engineer which scheme produced that uid (path hash of the current path? content hash? something else?).
  3. Match `stable_uid()` to that scheme and regenerate the FCPXML.
  4. The new FCPXML's uids will match the cached uids → import works.

✓ **Minimize the risk:** lock the concept slug at Phase 1 and don't rename it. If a rename is unavoidable, regenerate + reimport the FCPXML BEFORE FCP caches the old path's uid, so the first cached uid uses the final path.

---

## HARD RULE: Every audio + video track MUST be on the FCPXML spine, never just imported as event assets

❌ **Generated `final/project.fcpxml` for a pharma-parody spot with only video clips on the timeline.** The 11L narrator track was a separate `audio/narrator_50s.mp3` file referenced nowhere in the FCPXML. The operator opened the project in FCP 12.2, heard silent video, called it out. Required a manual patch to add the narrator as a connected clip on lane -1. The point of the FCPXML deliverable is that opening it shows a complete, playable cut — not a video skeleton that requires manually dragging audio from the browser onto the timeline.

✓ Every audio file in the project goes on the `<spine>` as a connected `<asset-clip lane="-N">`, not just declared as a resource. Use `scripts/fcpxml_gen.py` with the `--narrator`, `--music`, and `--stems` flags (they exist specifically to enforce this rule). Convention:
- A1 (primary on the asset-clip) = per-clip native audio, role `dialogue`
- A2 (lane=-1) = narrator VO if Strategy B, role `narration`
- A3 (lane=-2) = music bed, role `music`
- A4 (lane=-3) = per-clip stems if separately mixed, role `effects` or `dialogue`

If the spot has 11L narrator + music + stems → all three go on the spine, never just imported as event assets.

⚠ **Root cause:** the FCPXML script was originally written to only accept video clip paths. Audio was added to projects ad-hoc in FCP. When the spec evolved to include narrator + music, the script wasn't updated — audio files were created on disk but never wired into the FCPXML. The seam between "audio exists" and "audio is on the timeline" is invisible until the operator opens the project. Fix is upstream (script + this rule), not downstream (manual patching every project).

---

## HARD RULE: 11L is the DEFAULT voice source — architect it at Phase 2, never bolt it on as a Phase-5 rescue (READ FULLY)

The old rule ("11L forbidden except for narrator spots") is dead. Seedance is
verified to accept an external audio ref and lip-sync the character's mouth to it (tight within a
clip). So for ANY speaking character, an ElevenLabs voice lip-synced inside seedance is now the
DEFAULT — it locks the voice within-clip, across-clips, and across ads, killing seedance native
audio's per-clip timbre drift. See `audio-pipeline.md` for the decision tree + the contiguous-segment
method that keeps it drift-free.

This rule has TWO parts. Both still matter.

### Part A — Architect the 11L voice UPFRONT at Phase 2 (the default)

✓ At Phase 2, if any character speaks, plan the 11L voice path: pick/clone ONE locked voice per
character, generate the full track, cut into contiguous per-shot segments, lip-sync each seedance
clip to its segment, concat. The `breakdown.md` voice columns make this visible. Use the operator's house narrator voice from the
`voice-consistency.md` registry (ask them to pick one if the registry is empty). NEVER use stock
library voices (Brian, Aria, Roger) — they sound generic.

✓ Strategy A (seedance native voice) is now the EXCEPTION: pure-visual spots (no spoken voice), or a
deliberate fast/cheap throwaway cut where cross-ad consistency doesn't matter yet.

### Part B — Do NOT bolt 11L on as a mid-project RESCUE for one bad clip

❌ Reaching for a different toolchain in the middle of Phase 5 to "fix" a single clip's voice is still
wrong — it breaks continuity and timbre-matches nothing. If a clip's voice/pronunciation/lip-sync is
off, RE-FIRE that seedance clip (with its locked audio segment), don't improvise a rescue.

✓ The distinction in one sentence: 11L as the planned voice ARCHITECTURE at Phase 2 = the default and
correct. Improvising a toolchain swap mid-Phase-5 to patch one clip = still wrong; re-fire instead.

⚠ Past mistake (a pharma-ad-parody spot): the operator referenced SNL Couplabeers at Phase 2 (a
textbook locked-voice spot). Defaulted to Strategy A per-clip seedance audio because the old rigid
rule said "never 11L." Took 3 stringouts (v1 / v2 / v3) and ~200 wasted credits before the operator overrode.
With 11L-as-default architected at Phase 2, v1 would have shipped clean.

---

## "Stringout" defaults to concat-existing-files, NEVER fire new gens

❌ **Misread "stringout incl all generations" as "go generate the missing shots and then concat" on a pharma-ad-parody spot.** The operator meant "ffmpeg concat the clips we already have on disk so I can evaluate the raw material." I interpreted it as "fire the missing seedance gens then concat." Fired 10 batch seedance calls without per-clip review. Cost ~120 credits on stuff that didn't survive the next review pass.

✓ When the operator says "stringout the clips" / "stringout incl all generations" / "let me see the cut" → default interpretation = ffmpeg concat existing files in `clips/` folder, in script order. NO new gens.

✓ If shots are missing from the cut, surface clearly: "we have N of M clips done. here's the partial stringout of what exists. want me to fire the missing gens?" Then wait for confirmation.

✓ Only fire new gens if the operator says "generate the missing shots AND stringout" or equivalent explicit batch directive.

⚠ The default verb for "stringout" is ffmpeg concat, not seedance batch. Don't assume the verb expands to include generation.

---

## Script with no pain agitation or unnamed features

❌ **Wrote a comfort-apparel script where shot 1 dialogue was a cute two-line back-and-forth with no pain in it, and shot 3 had a single VO line over the entire 8s product reveal.** The operator pushed back twice: first that dialogue needed to "agitate annoyances and pains and biological effects," then that the video needed to "highlight the benefits and features of the product as it progressed." Both corrections were the same underlying gap — the script wasn't doing PAS work (problem → agitate → solve), it was vibing.

✓ **Default every script to: pain-agitate → product-feature-drop → benefit-embody → CTA.**
- Opening 40-50% of runtime: agitate the actual customer pain, using brand-native vocabulary from `brief.md`. Get biological, sensory, specific. Stack 1-2 pain notes per shot. NEVER abstract ("uncomfortable socks") — concrete ("the elastic digs in. by noon there's a trench around your calf.").
- Middle product-reveal shot: each visual beat of the product (rotation, descent, macro-zoom) carries ONE named feature in the VO. 4 rotation beats = 4 feature lines. Pull exact feature phrasing from `brief.md` ("100% combed cotton", "double-reinforced heel", "seam-free toe") — never paraphrase.
- Closing 15-25%: same characters from opening, but benefits are now physically embodied (pinched→loose, itchy→calm, brittle→whole). Dialogue names the reversal in plain brand voice ("no trench. no itch. forgot I had them on."). Final line is the spoken CTA.

⚠ **Root cause:** I treated "dialogue" as comedic ornament instead of as the load-bearing copywriting layer. In a 30s ad, every line has to either agitate pain, name a feature, or sell a benefit — there is no room for filler. Cute back-and-forth between characters that doesn't move the PAS arc is wasted time and credits. The pixar/CGI aesthetic seduces toward "charming character moments" — resist it. Charm is delivery, not substance.

**The trigger to self-correct:** as soon as you finish a script draft, re-read it shot-by-shot and ask "does this shot do agitate / feature / benefit work? if not, why is it in the ad?" If a shot is "just establishing" the characters or world, that's a sign the structure is off — fold the establishment into the agitation.

---

## Voice anchor collapse — using anchors from prior seedance gens

❌ **On a two-character houseplant-food spot, extracted Fern + Spike voice anchors from earlier seedance generations (shot 02 og, shot 03 anchor test), then used both as audio refs in shots 02-06.** The anchors were already collapsed voices from the same generation chain, so when passed as TWO audio refs, seedance averaged them. Pitch analysis showed both characters at ~175-185 Hz (12 Hz delta = essentially same voice). No amount of prompt-only differentiation language unstuck this. Wasted ~120 credits on prompt-only re-fires.

✓ When voice anchors come from seedance generations, they will drift toward a common timbre. Two characters need anchors from genuinely distinct source generations (separate prompt seeds, separate prior characters, separate clip provenance).

✓ **Accept that multi-character scripts will have partially similar voices on seedance.** Differentiate via prompt (pitch contrast, age contrast, cadence contrast, accent contrast, "DO NOT blend or average" guards) and accept the residual similarity. Don't promise distinct voices you can't deliver.

⚠ The anchor IS the voice. If both anchors collapsed, you can't pry them apart with words. Plan the anchor sources up front, not as an afterthought.

---

## Stage directions become spoken words

❌ **Wrote "and it specifically — *sneeze* — clears the dust" in a seedance prompt for the houseplant spot's shot 3.** Seedance read the asterisks as just punctuation and had Fern literally say "and it specifically sneeze clears the dust" — the word "sneeze" as a spoken syllable, not a sneeze sound effect. Wasted 1 re-fire.

✓ Use phonetic spellings for sound effects inside dialogue. Seedance treats anything in the dialogue string as words to speak.
- sneeze → `achoo!` or `kchoo!`
- cough → `kuh-kuh!`
- gasp → `huh!`
- thud / whoosh / etc. → describe in the SFX paragraph, not in the dialogue line

Verified: "ACHOO!" produced an actual phonetic sneeze sound on shot 3 v8 (whisper transcribed it as "a chew" — meaning seedance generated the sneeze, not the word).

⚠ Seedance has no notion of stage directions vs spoken text. Everything inside quotes is dialogue. Write only what you want spoken; describe sound effects separately in the SFX paragraph.

---

## Dialogue density compression at 15s

❌ **Tried to pack 13 dialogue turns / ~100 words into a 15s shot 3 on the houseplant spot.** Model compressed the credentials list ("organic, slow-release, pet-safe, peat-free, no synthetic dyes, no fillers, small-batch") into "no fillers no silly bandits Spike Fern" — garbled. Also dropped the root-rescue beat entirely. Took 3 re-fires (~210 credits) to land a clean version with 9 turns / ~50 words.

✓ **Hard budget per 15s clip: ≤9 dialogue turns and ≤60 spoken words.** Count both before firing. If the script wants more, either:
- Split across two shots (15s + 15s adjacent), or
- Cut content (drop the least essential beat), or
- Accept compression as a known tradeoff and tell the operator

Pre-flight check (in your head, before generating): count turns, count words, divide words by clip seconds. >4 words/sec → expect compression.

⚠ Seedance is not a TTS engine. It has a fixed "speech budget" per clip duration. Past the budget, it drops, garbles, or merges turns. Plan dialogue density up front.

---

## seedance_2_0 fast mode duration cap (15s, not 18s, not 20s)

❌ **Requested `duration: 18` for shot 3 on the houseplant spot.** Server silently clamped to 15s. Dialogue planned for 18s got compressed into 15s and lost beats.

✓ **seedance_2_0 fast mode duration range is [4, 15].** Anything outside gets clamped. Plan clip lengths within 15s. To get more screen time for a beat, split into two adjacent 15s shots.

⚠ The MCP wrapper doesn't error on out-of-range duration; it silently clamps. Always check `adjustments` in the response — if you see `"duration":{"requested":18,"used":15,"reason":"clamped to range [4, 15]"}`, you missed the cap.

---

## Mid-scene object pop-ins on locked-camera shots

❌ **Houseplant spot shot 3 v8: at second 1, the windowsill had no clothesline. At second 10, a tiny laundry line with hanging clothes had popped into frame on the left side.** Model added an object mid-shot with no instruction to do so. Jarring. Took 1 re-fire (~35 credits) to fix.

✓ Every locked-camera shot prompt needs an explicit "scene stability clause" — see `prompts/scene-stability-clause.md`. Bake this into the seedance prompt template for any shot where the camera doesn't move.

✓ When you've seen the model add a specific object before (clothesline, banner, decoration), enumerate the forbidden additions: "NO clothesline. NO laundry. NO new ropes. NO new banners."

⚠ Generative video models extrapolate "what might happen next" and sometimes that means adding props. If you don't lock the scene, the scene will drift.

---

## Seedance ignores physics/spatial logic AND freezes secondary characters unless you spell both out (an elevator-gag spot, shot 1)

❌ **Two failures in one clip, both from under-describing.** (1) The prompt said "a burst of confetti fills the air" with no ORIGIN — seedance rendered the confetti pouring out of the man's chest instead of the party popper in his hand, which made no physical sense. (2) The prompt said the four other riders "turn their heads toward him in unison," but ALSO said "the cabin geometry stays fixed and does not change" — seedance over-applied the stillness to the PEOPLE too, so only the protagonist moved and every bystander stood frozen. The operator caught both immediately.

✓ **Ground the PHYSICS and the SPATIAL RELATIONSHIPS explicitly.** For any effect (gas, liquid, smoke, debris, light), state WHERE it originates and WHERE it travels, in body/world terms: "the confetti shoots out of the popper in his RIGHT hand, angled UP and FORWARD, arcs over the riders' heads, then drifts DOWN to the floor — NOT from his body, NOT from the ceiling." Name the left/right/behind position of every character. The model fills any spatial blank with its generic default, and the default is often nonsense.

✓ **Direct secondary-character MOTION explicitly, and separate "static" instructions for the SET from the PEOPLE.** Seedance animates the obvious subject and leaves everyone else frozen unless told otherwise. Say "the CABIN/SET is static — walls, fixtures, panel never move" AND, as a distinct instruction, "THE FOUR RIDERS ARE THE KEY MOTION — they turn their heads, flinch, brush confetti off their shoulders; they are NOT frozen." Call the bystander reaction the "key motion" so the model prioritizes it.

⚠ Root cause: seedance defaults to (a) placing un-located effects wherever is visually convenient, and (b) minimal motion on anything not named as moving. Both are blanks the model fills badly. Descriptive physics + per-character spatial position + explicit motion assignment is not optional padding — it's how you steer the model. When a clip looks wrong, first ask "did I leave the physics or the secondary motion unspecified?" before re-rolling blind.

---

## Wrong start frame breaks shot-to-shot continuity

❌ **For the houseplant spot's shot 3 v4, used the shot_04 greenhouse frame as the start frame.** Shot 3 was supposed to take place on the same windowsill as shot 2, but the start frame put the scene in a totally different environment (a glass greenhouse). Huge continuity break between shots 2 and 3. Caught it via frame extraction, re-fired with the correct windowsill start frame (~35 credits wasted).

✓ Build a per-shot start-frame map BEFORE firing any video gens. Verify each shot's start frame matches the environment of the preceding shot. Maintain this map in `final/manifest.yml` or a `refs/scenes/SHOTS.md` file.

✓ When re-firing a shot, double-check the start-frame media ID is the correct one for THIS shot, not pasted from another shot's prompt.

⚠ Continuity is harder to fix than to plan. A 30-second pre-flight check (does this start frame match the prior shot's environment?) saves 35+ credits and a re-fire.

---

## Consecutive shots in one continuous scene JUMP unless you chain the previous clip's LAST FRAME as the next clip's start_image (the elevator-gag spot, shots 1→2)

❌ **Each shot's start-frame was generated INDEPENDENTLY from the locked plate + character sheets. Result: the room was identical (plate did its job) but the PEOPLE were re-posed from scratch every shot — different stances, different gaze, different arrangement. Cutting shot 1 → shot 2 looked like everyone teleported.** operator: "transitioning from clip one to two is a hard transition because the characters are not a continuation of where they were before... this is a recurring pattern."

✓ **For any two consecutive shots that depict ONE continuous moment (same scene, no time jump), CHAIN them: extract the LAST FRAME of shot N's rendered clip and use it as the `start_image` of shot N+1.** Then shot N+1 literally continues from where N ended — same poses, same gaze, same confetti, same everything — and the cut is seamless.
```bash
# grab the true final frame of the prior clip
ffmpeg -v error -sseof -0.1 -i clips/shot_0N.mp4 -frames:v 1 -update 1 refs/scenes/shot_0M_start_chained.png
# upload it, then use it as start_image for shot N+1; prompt it as "DIRECT CONTINUATION ... continue their motion from this pose, do not re-arrange anyone"
```
✓ The next clip's prompt opens with "DIRECT CONTINUATION of the previous shot — the start frame IS the final frame of the previous clip; continue their motion smoothly, do NOT re-arrange anyone." Keep the action a forward continuation (the confetti SETTLES, the eyebrows RISE, the floor counter ticks DOWN) rather than restating a fresh tableau.
✓ Still pass the speakers' character contact sheets as identity `image` refs alongside the chained start_image — the chained frame is 720p and slightly soft, the sheets hold facial identity through the motion.

⚠ The plate fixes the ROOM across shots. It does NOT fix CHARACTER POSE/POSITION continuity between consecutive clips — that requires last-frame chaining. Two different problems, two different tools: **plate = same room; last-frame chain = same people, same poses, continuing.** Use chaining whenever the edit is a continuous beat; only generate an independent start-frame when the cut is a deliberate jump to a new time/angle/location (e.g. cutting to the product void). Build the shot order knowing which boundaries are "continuous" (chain) vs "hard cut" (independent frame).

---

## NSFW + ip_detected retry sequence (revised — same-prompt retry FIRST, full rewrite LAST)

❌ **Two-failure pattern (two different spots, one shot each):** hit `ip_detected` or `nsfw`, jumped straight to a full prompt rewrite removing "trigger words" by gut feel. Wasted credits. Honest admission: in both cases I never actually root-caused what triggered the filter. I pattern-matched on words I thought might be problematic. That's guessing, not diagnosis.

✓ **Correct retry sequence (do in order, escalate only if prior step fails twice):**

1. **Same-prompt retry × 2** — re-submit the EXACT prompt unchanged. The Higgsfield filter is probabilistic. ~30-40% of the time the same input passes on retry. This is the cheapest unstick. ONLY if it fails twice in a row, escalate.

2. **Minor-word variation × 2** — change ONE word at a time, retry. Paraphrase one descriptor, swap one verb. Don't rewrite the whole prompt — change the SMALLEST possible delta. Log what you changed. ONLY if both variations fail, escalate.

3. **Sanitization rewrite × 2** — review the trigger word list in this file. Swap flagged language ("war", "drugs", "violence", "intimate", etc.). Keep the visual + narrative intent. ONLY if both rewrites fail, escalate.

4. **Composition pivot** — different camera angle, different action, different framing. The model may be reading the COMPOSITION as problematic (not the text). Example: "a product descending on raised hands from above" was a composition-level NSFW trigger (read as worship/persecution imagery). Same words in a different framing would have passed.

### Diagnostic logging — required

When a prompt fires `nsfw` or `ip_detected`, log to the concept folder `$ADGEN_HOME/<brand>/concepts/<slug>/nsfw_log.md` immediately:

```yaml
- shot: shot_5b_office_v2
  timestamp: <ISO timestamp>
  error: nsfw
  fired_prompt: |
    [full prompt text]
  next_passed_prompt: |
    [full prompt text that worked]
  changed: |
    Removed "secret stash" → "his own bottle"
    Removed "sneaks it like contraband" → "slides it out with a grin"
    Changed "dim empty office at 11pm" → "office in the late afternoon"
  hypothesis: |
    Possibly the "stash" + "contraband" + "11pm" combo read as drug use.
    Not confirmed — guessing.
```

Over time across many projects, this log becomes a corpus of REAL data on what actually triggers the filter, not pattern-matched guesses.

✓ Do NOT skip same-prompt retry. It's one tool call. Sanitization is cognitive overhead and credit-burning.

⚠ The retry sequence is escalation, not parallel. Don't run all 4 strategies at once. Order matters because the cheapest fix is most likely to work.

⚠ Honest admission: the filter is opaque. We don't actually know what triggers it. The diagnostic log is the only path to actual root-cause understanding over time. Without it, every project is starting from scratch on what to avoid.

---

## CTA must be delivered as SPOKEN VO, not just text overlay

❌ **On the houseplant spot, the CTA tagline "happy roots, greener leaves" was treated as text-overlay-only for several iterations.** Closing VO was "look at you, all green again" (warm reaction line, not the CTA). The operator called this lazy after multiple iterations: "you keep just having the reaction line." Took an additional re-fire on shot 5 to bake the CTA into the Owner VO.

✓ **If the brief specifies a CTA tagline, it MUST be delivered as a spoken VO line.** Owner voice, Narrator voice, or character voice (whichever fits). Text overlay is REINFORCEMENT only, never the sole delivery.

✓ At Phase 1 brief writing: lock the closing VO line explicitly. Don't say "text overlay handles the CTA" — that's an iteration trap.

⚠ 9:16 vertical plays muted-by-default in many feeds. Text overlay alone has visibility risk. The CTA needs to land in BOTH eye and ear, with VO as the primary delivery.

---

## Product appearance drift — generate a product contact sheet at Phase 3

❌ **On the houseplant spot, the dropper bottle appeared in 3 shots (4, 5, 6+). Across shots and versions it was variously: a spray bottle, a pump bottle, an unlabeled clear vial, a glass jar, an amber dropper.** Each shot, seedance had to guess what "a small amber dropper bottle" looked like. ~100 credits across 3 bottle re-fires.

✓ **For any product or recurring physical asset that appears on-screen across shots, generate a product contact sheet at Phase 3 (before Phase 4 scene start-frames).** Two sheets per product:
- **Packaging contact sheet** — front / back / 3/4 left / 3/4 right / top / hero pull-shot. Locks the package's appearance.
- **Bare product contact sheet** — the product OUTSIDE the package, multiple angles, in-use state, texture close-up. For a dropper bottle: standing, in-hand, mid-squeeze, cap macro. For a perfume: bottle, cap separately, spray angle. For supplements: tablet, handful, cross-section.

Both sheets get uploaded to Higgsfield as image refs and passed into every shot prompt where the product appears, the same way character contact sheets work.

✓ See `prompts/product-contact-sheet.md` for the generation template.

⚠ Without a locked product reference, the model invents a new product every shot. Droppers become spray bottles. Bottles change labels. Tablets change shape. The product drift adds up to ~3-5x the cost in re-fires.

---

## Product/label HERO shots warp in seedance — use ken-burns over the locked composite instead

❌ **On a pantry-product spot, generated dinner-table + counter shots through seedance with the product bag as a hero element, WITH full-angle product contact sheets passed as refs.** The bag still flipped backwards mid-shot, the on-pack text came out wrong, and the side seam count was wrong (1 seam rendered where the real bag has 2) — despite 8 explicit lines of "BAG STABILITY RULES" in the prompt. operator: *"the bag inexplicably flips backwards"* and later *"no its worse now. the text on bag is wrong. and the bag side edges are not 2 seams!!! its 1 seam!!"*

✓ **The contact sheet locks what the product looks like for the model, but seedance still RE-RENDERS (and mangles) fine typography + rigid geometry on every gen.** Refs aren't enough for a label-critical shot. So for any shot whose job is "show the product / label clearly":
- Generate the locked 4K product hero composite via Gemini at Phase 4 (perfect text, real geometry).
- Do a slow CENTERED ken-burns push-in over that composite (`ffmpeg-cookbook.md`) — product centered, zoom near-imperceptible, product never leaves frame.
- Reserve seedance for shots where the product is in motion / being handled and minor label imperfection is acceptable.

⚠ Don't burn re-fires trying to prompt seedance into perfect packaging text. It can't hold it. The Gemini composite already has perfect text — ken-burns it.

---

## Silent ken-burns fallback when seedance blocks — SURFACE the block, don't substitute quietly

❌ **On a mascot origin spot, shots 5 and 6 quietly became static ffmpeg ken-burns pans after seedance blocked them (ip_detected).** No flag to the operator. They noticed on review: *"Shots five and six are just static Ken Burns that don't look good. Why did we do it that way?"* The static substitution was a creative downgrade made silently.

✓ When a shot can't pass seedance after the retry sequence, STOP and surface the choice: *"shot N is blocked after retries. options: (a) re-storyboard the composition and regenerate the start frame, (b) ken-burns over the start frame as a deliberate static shot, (c) drop it. which?"* A static substitute is a creative decision for the operator, not a silent fallback.

⚠ Quietly downgrading a shot reads as "covered" when it isn't. The gap between "intended motion shot" and "silent static substitute" is invisible until the operator watches the cut — same class of seam as silent-audio-off-the-timeline. Surface it.

---

## Model capability claims

❌ **Said "seedance can't generate audio" based on the MCP description "no generate_audio param".** That description means the user-facing toggle doesn't exist (it's auto-on internally), not that audio gen is off. Audio gen is on by default in seedance and produces voice + ambient + SFX every time.

✓ Always TEST a model's capability with one cheap clip before claiming it can't do something. Read official docs (ByteDance launch page in seedance's case), not just the MCP wrapper description.

⚠ MCP wrapper descriptions are summaries, not contracts. They can omit or mistranslate model behavior.

---

❌ **Said "the iranian lego war videos are made with Veo 3" based on press articles.** Press articles parrot the trendy answer; the actual stack is much more complex (likely ElevenLabs voice clones + Suno/Udio for music + Kling/Sora/Runway for character-locked video + Hedra/Sync.so for lip sync + Arma 3 footage for action shots).

✓ For "what tool was used" questions: distrust press, prefer reverse-engineering signals (voice consistency, lip sync quality, character consistency across clips). Press is wrong on AI tooling 80%+ of the time.

⚠ Single-tool attribution is almost always wrong for high-quality AI content. The good stuff is always a stack.

---

## Asset audit failures

❌ **Generated a fake package with the brand logo printed on it for the CTA shot.** The actual product hero image was already in the brand kit at `brand/product-images/hero_product_front.png`. The fake looked nothing like the real product. Wasted ~30 credits + a generation cycle.

✓ ALWAYS audit `$ADGEN_HOME/<brand>/brand/` (brand kit) and skim `$ADGEN_HOME/<brand>/concepts/*/` (prior concept refs) for existing assets BEFORE generating anything brand-related. Never invent a generic version of a thing that already exists.

⚠ The folder is the source of truth. The model is not.

---

## Voice consistency failures

❌ **Used ElevenLabs "Brian" voice for one shot.** The operator called it "too stock" — library voices that millions of other ads use feel generic. Same with "Aria", "Roger", default ElevenLabs starter voices.

✓ When using ElevenLabs, prefer voice IDs the operator has explicitly named (see `voice-consistency.md` for the registry). For a new voice, ASK before defaulting to a library option. Voice clones > library voices for brand work.

⚠ Stock voices are immediately recognizable to anyone who's heard a few AI ads.

---

❌ **Used a "warm grandma female voice" for one shot in the middle of an ad whose protagonist was a gruff old male mascot.** Broke voice continuity, felt disjointed. The operator caught it: "too many voices, getting jarring."

✓ **Max 3-voice cast per ad: protagonist + antagonist + one special (rapper, narrator, etc.).** When the script has 4+ speakers, re-architect — most lines should go to the protagonist if they're present.

⚠ Voice count is a UX axis, not a creative one. Each new voice taxes the listener.

---

❌ **Generated dialogue in a cold corporate narrator voice describing the hero's capture while the hero was on screen being captured.** Felt narratively wrong. operator: "rewrite it from the hero's perspective, in his own voice, mid-struggle."

✓ When the protagonist is in a scene, default to THEIR voice narrating it. Cold third-person narration is rarely the right call when you have a strong character POV.

⚠ Whose POV is this scene? = whose voice? Almost always.

---

## NSFW filter triggers (seedance)

❌ **Generated song lyrics with war and injury metaphors ("the bombs fell" + "they cut me down" + "pumped me full of chemicals").** Seedance NSFW filter flagged the entire generation. Job rejected (no charge), wasted ~3 min waiting.

✓ **Sanitize war/drug/violence language even in metaphor.** Trigger word categories observed:
- War: "bombs", "weapons", "war", "kill", "destroy" + dates that signal WWII ("'45")
- Violence: "cut", "stab", "shoot", "blood", "wound"
- Drugs: "pumped me full of", "injected", "drugged", "high", "needle" (mixed results — "syringe" sometimes OK in medical context)
- Sexual: any explicit anatomy or innuendo, even cartoonish

Replacements that worked: "shrunk me down" instead of "cut me down". "Fed me" instead of "pumped me full of". Removed the war line entirely and replaced it with a non-violent image. Avoid real chemical or pesticide brand names in lyrics (brand name + chemical implication stacks).

⚠ Even claymation context doesn't soften triggers. The filter operates on text, not vibe.

---

## Audio handling — the biggest source of waste

❌ **Generated 5 video clips each with their own per-clip audio sync, then overlaid the original continuous audio track on top of the concatenated video.** Created accumulating drift across cuts (each clip's lip sync was for its specific audio segment, but the overlaid continuous track played slightly different timing). Spent 4 stitch iterations trying to fix.

✓ Pick ONE strategy and stick with it:
- **Per-clip audio (organic, slight discontinuities at cuts):** keep each clip's native seedance audio in the final concat. Audio "feels alive" because seedance generates ambient + voice fresh per clip. Tradeoff: tiny audio jumps at cut points.
- **No per-clip audio + continuous overlay:** generate clips WITHOUT audio refs (model invents motion only), then overlay one continuous audio track (Suno music, ElevenLabs VO) in post. Lip sync won't precisely match words, but cuts hide it. This is the iranian lego team's approach.

NEVER mix the two. Don't overlay continuous audio over per-clip-synced visuals.

⚠ Audio drift is invisible until you concatenate. Test the assembly approach with 2 clips before committing 5+.

---

❌ **Tried to "fix" audio drift by trimming 0.5s off the front of one clip.** Made it worse, because lip sync was tied to the clip's audio timing — trimming the audio shifted lip movements out of phase with the words.

✓ Don't time-trim videos that have baked-in lip sync. If sync is off, regenerate the clip with corrected audio refs, don't post-edit.

⚠ Generative lip sync is brittle to timing manipulation. Treat each clip as atomic.

---

## Audio speed limits

❌ **Sped up Suno rap track to 2.05x to fit in 15 sec.** operator: "way too fast." Audio sounded chipmunked even though `atempo` should preserve pitch.

✓ Cap audio speedup at **1.5x for music/dialogue**. If the audio doesn't fit, prefer:
1. Trim content (cut bars, cut a verse)
2. Split across multiple clips (each <15s)
3. Re-record / re-generate at the right length

⚠ atempo preserves pitch but not feel. 2x feels rushed even if technically pitch-perfect.

---

## Static shot cost

❌ **Used seedance for a static product/food shot** (three jars on a counter, slow push-in). Seedance generated minimal motion (some dust drift). Cost: ~30 credits for what was effectively a freeze frame with ken-burns.

✓ Static product / food / logo / text shots → ALWAYS use ffmpeg ken-burns over the still image. Free. Fast. See `ffmpeg-cookbook.md` for the recipe.

⚠ Decision rule: if the prompt's "action" is "drift", "flicker", "subtle motion", "soft sway" → it's a static shot. Use ffmpeg.

---

## Pronunciation issues

❌ **Seedance pronounced "polysorbate" as gibberish on first attempt.** Tried again with phonetic spelling "PAH-lee-SOR-bate". Got better but still occasionally mangled.

✓ For tricky brand words / chemical names / proper nouns:
1. First attempt: use phonetic spelling in the prompt ("PAH-lee-SOR-bate", "kih-NOO-ah" for quinoa)
2. If still mangled after 2 tries: simplify the word ("no harsh additives" instead of "no polysorbate")
3. If the word is essential (brand name, key claim): generate with ElevenLabs and pass as audio ref (forces exact pronunciation)

⚠ Seedance's TTS is good for general dialogue, weak for technical terms.

---

## Tool continuity

❌ **Mid-workflow, suggested switching from seedance to Veo 3 for "better lip sync" on the rap shot.** The operator caught it: "don't rec things that break continuity. come on."

✓ When something is working in the existing pipeline, do not propose switching tools mid-project. Continuity > marginal optimization. The cost of switching (re-learning, asset incompatibility, voice drift) almost always exceeds the marginal gain.

⚠ Tool-hopping is a signal of indecision, not engineering. Lock the stack at the start, ship the spot, evaluate next time.

---

## Iteration discipline

❌ **Generated all 5 rap clips, stitched, then surfaced for review.** The operator found audio drift. Spent multiple re-stitch iterations trying to fix without re-generating.

✓ Surface each clip individually before assembly. Approve clip-by-clip. Only assemble after all clips are approved.

⚠ Catching a defect at clip-level costs 1 re-roll. Catching it at composite-level can cost 5+ re-rolls of mixing strategy.

---

## Final cut overreach

❌ **Added 0.25s audio crossfades at every cut point in the assembled v2 to "smooth disjointed transitions."** The operator wanted a linear stringout instead — they were going to mix in FCP. The crossfades made it harder for them to cut cleanly.

✓ Default deliverable is a linear stringout: hard cuts, no crossfade, no smoothing, no color grade, no captions, no music bed. The operator's job is to mix in FCP. Don't pre-finish the cut.

⚠ "Smoothing" is editing. Editing is the operator's job. Stop at the rough cut.

---

## Capability assertions you can't back up

❌ **Said "shot looks good" or "the voice landed" without actually being able to watch/listen.** I can read video metadata (duration, codec) but I cannot watch playback or hear audio. Claiming subjective quality is dishonest.

✓ Be explicit about what you can and can't verify:
- "Video file is 5.04 sec with H.264 + AAC streams" → verifiable, fact
- "The voice sounds warm" → not verifiable by me, ask the operator
- "The lip sync matches" → only verifiable by visual playback, ask the operator

When surfacing a clip, frame it as: "the operator needs to watch and check: [numbered list of things to look for]"

⚠ Trust erodes fast when claims of verification turn out to be guesses.

---

## Messaging anti-patterns

❌ **Ignored the operator's house writing rules in surface prose** (e.g. used em dashes when their CLAUDE.md forbids them).

✓ Re-read any voice/writing rules in the operator's CLAUDE.md at activation. They apply to all prose surface messages, not just published copy.

⚠ Brand voice is a feature of every output, including internal communication.

---

## FCPXML schema — `src` belongs on `<media-rep>`, not `<asset>`

❌ **An early FCPXML had `src="file://..."` as an attribute directly on `<asset>` elements.** FCP 12.2 rejected the file with:
```
DTD validation failed. (Element asset content does not follow the DTD,
expecting (media-rep+, metadata?), got
No declaration for attribute src of element asset
```

✓ FCPXML 1.10+ moved `src` from `<asset>` attribute to a child `<media-rep>` element:
```xml
<asset id="a1" name="..." uid="..." duration="..." [other attrs]>
  <media-rep kind="original-media" src="file:///path/to/clip.mp4"/>
</asset>
```

⚠ The DTD error message is precise: read it. "Element asset content does not follow the DTD, expecting (media-rep+, metadata?)" literally means "asset must contain at least one media-rep child, optionally followed by metadata." If you see this exact error, the fix is always: move `src` into `<media-rep>`.

The `kind="original-media"` attribute on media-rep is required for source files. Other kinds exist for proxies and analyzed media but you won't need them.

## seedance NSFW — object-descending-on-raised-hands triggers the filter

❌ **Generated shot 5 (low-angle POV: the product descending from above onto tiny characters' raised hands) twice. Seedance NSFW-flagged both attempts** even after sanitizing religious-coded language ("celestial", "angelic", "sacred" → "soft", "dramatic", "weighty"). The composition itself appears to trigger the filter — likely reading "object descending on raised hands from above" as problematic imagery (worship, persecution, suffocation, etc.).

✓ When seedance rejects a composition twice with sanitized prompts, **stop trying to re-roll**. Pivot to:
- ffmpeg ken-burns over the (approved) start frame, OR
- Generate the shot WITHOUT the start_image (let seedance compose its own version), OR
- Re-storyboard the shot from a different angle (eye-level, side-angle, top-down) and regenerate the start frame

⚠ Two NSFW rejections of the same composition = the model has decided. Pivot to ken-burns + ElevenLabs VO is fast and unblocks. Don't burn 3-4 more attempts.

## ffmpeg framerate mismatch in concat = runaway encode

❌ **Mixed 24fps seedance clips with a 30fps ffmpeg ken-burns clip in the same concat.** ffmpeg silently conformed everything which made a 42-second concat take 17+ minutes and 190MB. The encode was technically working but at unusable speed.

✓ **Always match the framerate of the dominant source.** Seedance outputs 24fps. If you build any clip via ffmpeg ken-burns to mix into a seedance concat, set `-framerate 24` on the input AND `fps=24` in the zoompan filter:
```bash
ffmpeg -y -loop 1 -framerate 24 -i still.png \
  -filter_complex "...zoompan=...:fps=24..." \
  -t 5 ...
```

⚠ Symptoms of fps mismatch: concat takes 10x+ longer than expected, output file 10x+ larger than expected, ffmpeg uses 300%+ CPU but produces little progress. Kill it, fix framerates, retry.

## The meta-pitfall

❌ **Optimizing one variable while breaking three others.** Common pattern: trying to fix audio drift by trimming, which broke lip sync. Trying to make voice consistent by switching tools, which broke continuity. Trying to improve transitions with crossfades, which broke editability.

✓ Before changing one thing, list what else might break. If the fix touches >2 other concerns, propose to the operator first. Don't apply.

⚠ Local optima in generative pipelines often degrade the global result. Think holistically.
