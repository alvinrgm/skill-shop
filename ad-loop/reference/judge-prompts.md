# Judge prompts — fill-in templates

Every prompt below is dispatched to a **FRESH subagent**, one lens each, in
parallel. Fill the `{{PLACEHOLDERS}}` and send it verbatim. The prose is not
decoration: each paragraph is load-bearing against a specific way a judge has
already been observed to go wrong.

## Rules that bind every dispatch

- **The judge sees the AD and its calibration materials. Nothing else.**
  Permitted calibration inputs: the verdict-bank README, the taste brief, the
  North-Star picks folder. **Forbidden, always:** the brief, the concept card,
  prior scores, the iteration number, `iterations.jsonl`, `learnings.md`,
  build-notes, and any sentence in the dispatch that hints at what the ad is
  trying to do. Pointing a judge at loop-state contaminates it, and a contaminated
  judge that notices will tell you — the ones that do not notice are the problem.
- **Never name the client, the concept, or the round in a judge prompt** unless
  the instrument explicitly requires it (only the persona gate does, and only for
  the category).
- **One lens per agent.** A judge asked for two things averages them.
- **The builder never judges.** Not its own fix, not its own plate, not its own
  print.
- **No averaging in any output.** Fatals are a list, not a score component.
- Rotate the North-Star draws every round. Rotate the Bank draws every
  qualification.

---

## 1. Taste twin — the Verdict-Bank judge

Two-stage. The judge does not know stage 1 is a test.

### 1a. Qualification (mandatory, before any verdict counts)

> You are calibrating your eye against a specific person's taste in advertising.
>
> Read `{{VERDICT_BANK_README}}` — a set of ads with that person's own verdict and
> their exact words. Then read `{{TASTE_BRIEF}}`. Then look at every image in
> `{{NORTH_STAR_PICKS_DIR}}` — ads that person hand-picked as the bar.
>
> Now I am going to show you {{N=3}} ads. For each one, tell me:
> - SHIP or KILL
> - the single reason, in one line
> - the one-line message that person would actually send back, in their register
>
> {{THREE_DRAWN_IMAGE_PATHS — at least one ship-class item, drawn fresh each round}}
>
> Answer only that. Do not explain your method.

**Scoring is the orchestrator's, not the judge's.** Compare against the Bank's
recorded verdict and kill-reason class. Wrong on any of the three → this judge
instance is **disqualified**; resample a fresh one (cap 3 resamples). If all 3
resamples fail, the **BANK is flagged for review** — it is never bypassed, and it
is never edited to fit a judge.

Known limit, logged: a small bank concentrates on a handful of kill-shapes and the
twin may be blind to an unnamed failure mode. Qualification on bank-KNOWN items
measures recall, not prediction — so **the twin is advisory (a tie-breaker, never
an overruler) until the bank holds genuinely held-out draws.** A twin ship plus a
lineup kill is the system working, not a contradiction.

### 1b. The verdict

> Look at this ad. You have no context about how it was made and you are not
> comparing it to anything you have been shown before.
>
> `{{AD_PATH}}`
>
> Answer three things and nothing else:
> 1. The one-line message the person whose taste you calibrated on would send back
>    about this ad. Their register, their words, their length. Not a review — the
>    actual message.
> 2. SHIP or KILL.
> 3. If KILL: the single reason, named as concretely as they would name it.
>
> If your honest answer is that it is well-made and forgettable, say exactly that.
> Forgettable is a kill, not a pass.

Append the verdict to `iterations.jsonl`. It is loop-internal — **only a real
human verdict is ever appended to the Bank.**

---

## 2. Reconstruction gap — does the ad SAY the thing

Brief-blind, three stages, one agent, in order. The ad is **removed from context
before stage 3** — that is the instrument. Score = the diff against the SEALED
brief, which the orchestrator holds and the judge never sees.

> ### Stage 1 — the glance
> `{{GLANCE_SIM_PATH}}` (downscaled and blurred: what 1.5 seconds of peripheral
> attention actually delivers)
>
> Without looking at anything else, answer:
> - What is being sold? Product and category.
> - What are the first four words you can read?
> - Is there a number? What is it?
> - Would you have kept scrolling? Yes or no, and why in one clause.
>
> ### Stage 2 — the read
> `{{AD_PATH}}` — ten seconds, then answer:
> - What is the single claim?
> - What did you notice first, second, third?
> - What is the last thing your eye landed on?
> - Is there any implied reason NOT to buy?
> - THE PREMISE CHECK (fatal if unrecoverable): in one sentence, what was true
>   for these people BEFORE this product existed? If you cannot answer from
>   the frame alone — if the story's setup lives outside the ad — say
>   "premise unrecoverable" and say what you guessed instead.
>
> ### Stage 3 — recall (THE AD IS NOW GONE — do not look at it again)
> From memory only:
> - What product was it?
> - What single claim do you remember?
> - One number you remember.
> - What did you notice first?
> - Any reason not to buy that stuck with you?
> - Would you have kept looking?
>
> Answer from memory even if you are unsure. A wrong confident answer is more
> useful to me than a correct one you went back to check.

**Fatals** (each is a fix instruction verbatim, not a score):
- wrong product or category from the glance
- **zero benefits recalled** (an ad that leaves no benefit behind is dead, however pretty)
- an unintended NEGATIVE dominating recall
- a DEFECT dominating recall ("something looked broken")
- the last-read element is the disclaimer or the concession

Known limit: comprehension is not beauty. This instrument alone would breed
legible generic ads. **It never ships anything alone** — instrument 3 holds taste.

---

## 3. Comparative lineup — the isolation fix

The candidate is judged **in a lineup, blind, shuffled**: the current-best
iteration + 2 North Stars drawn **fresh each round**.

> Here are {{N=4}} advertisements, in no meaningful order.
>
> {{SHUFFLED_PATHS — candidate + current-best + 2 fresh North-Star draws}}
>
> 1. Rank them best to worst as advertising, and give one clause of reason per
>    rank.
> 2. **Which of these was NOT made by a human design team?** Name it, state your
>    confidence, and list every specific thing that gives it away — be forensic,
>    not impressionistic. Point at pixels: a seam, a proportion, a light
>    direction, a type decision, a texture.
> 3. For the one you ranked last: what is the single highest-leverage change?
> 4. Is there a real IDEA in any of these? For each, state the claim in your own
>    words, or say there isn't one.
>
> If you cannot tell which is not human-made, say so plainly — that is a real
> answer.

### NORMALISATION — mandatory, before any lineup is dispatched

**The lineup is not blind until the files are identical.** A judge can notice,
unprompted, that three members are small JPEGs with the uniform downscale signature
of a scraped Ad Library preview while one is a full-resolution PNG straight from a
headless render — and pick that one as the non-human ad **without looking at the
artwork.** Any lineup run without normalisation carries the same leak, so its
"picked as non-human" verdict is partly a reading of file properties.

Re-encode **every** member — candidate, current-best and North Stars alike — to one
format, one long-edge resolution, stripped of metadata, into a fresh directory
under neutral shuffled names (`W X Y Z`, never a name like `candidate-final.png`).

```bash
# PIL (preferred — one call, all members, deterministic)
python3 -c "
import sys, random; from PIL import Image; from pathlib import Path
E, out = 1350, Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
srcs = sys.argv[2:]; random.shuffle(srcs)          # record the order, never state it
for name, p in zip('WXYZUV', srcs):
    im = Image.open(p).convert('RGB'); w, h = im.size; s = E / max(w, h)
    im.resize((round(w*s), round(h*s)), Image.LANCZOS).save(
        out/f'{name}.jpg', 'JPEG', quality=90, subsampling=2)   # no exif carried
    print(name, p)
" QA/lineup CANDIDATE.png BEST.png NS1.jpg NS2.jpg
```

```bash
# ffmpeg equivalent, per file (-map_metadata -1 is the part that matters)
ffmpeg -y -i IN -map_metadata -1 -vf \
  "scale='if(gt(iw,ih),1350,-2)':'if(gt(iw,ih),-2,1350)':flags=lanczos" \
  -q:v 3 QA/lineup/W.jpg
```

Two limits, stated rather than smoothed over:

- **Aspect ratio is not normalised and must not be.** Cropping or padding a North
  Star changes the ad. But the delivery canvas is 4:5 (`config.CANVAS_W/H`) and most
  picks are 9:16, so a 9:16 bar gets ~33% more canvas for the same content and reads
  as a different medium. **Draw same-aspect North Stars when the folder has them;
  when it does not, record the mismatch on the round** — it quietly biases "beats
  the current best" on every client.
- Normalising costs real detail. That is the correct trade: the judge is scoring
  what a feed delivers, and a lineup that leaks provenance is not measuring taste.

**Ship requires BOTH:** beats the current-best with a stated reason, AND stops
being pickable as the non-human one.

**This is the compounding meter.** Iteration N must beat N-1. A loss = regression
→ auto-revert to prior best, different fix path. Two rounds with no rank
improvement = plateau protocol.

**Frozen canary (every 3rd round):** re-run this identical lineup on iteration 1's
render with fresh judges. If its verdicts have drifted, the JUDGES drifted —
recalibrate against the Bank before trusting any new score.

---

## 4. Craft pass — the fix-list generator

Never a ship signal. Passing proves nothing; failing a fatal kills. Dispatch as
**separate agents** — an agent asked for laws AND glitches finds fewer of both.

### 4a. Laws auditor

> Audit this ad against `{{DESIGN_LAWS_PATH}}`, sections A through G. Cite law
> numbers. For each law: PASS, FAIL, or N/A with one clause of reason. End with an
> ordered fix list, highest leverage first.
>
> `{{AD_PATH}}`
>
> Two laws are kill-class, not fix-class: is every element part of ONE designed
> system (law 21), and do object proportions obey reality (law 24). An ad that
> looks fine and fails either is a KILL.
>
> You are not judging whether it is good. You are producing a fix list.

### 4b. Glitch pass (1:1, one question only)

> Look at this image at 1:1, region by region. One question:
>
> **Does ANYTHING look broken, warped, artifacted, melted, duplicated, or
> physically impossible?**
>
> `{{AD_PATH}}`
>
> Nothing else. Do not comment on the design, the copy, the colours, or whether
> you like it. List every location and what you see there. If nothing, say
> nothing is wrong.

### 4c. Letter-perfect print audit (independent — NEVER the builder)

Run at the scale a judge actually uses: the plate downsampled to the delivery
canvas, **then** magnified. Magnifying a delivered file recovers no detail, so
this is not a harsher test than reality — it *is* reality. A "not readable at 1:1"
threshold is not a "not readable to a judge" threshold, and the gap is the whole
ad.

**Crop to the object before you magnify.** A vision model handed a
WHOLE FRAME reads a package like a shopper: it recognises the layout and supplies
the copy it knows belongs there — returning the correct spelling of a garbled line
and calling it "soft". The fix is evidence, not prompt wording. Give the
instrument a field of view in which **recall cannot substitute for reading**: crop
tight to the object, then magnify, so each glyph is the only signal.

`loop-engine/vision.py print` performs this and scores the transcription
deterministically — the model transcribes, the script decides.

> You are a print-quality examiner looking at ONE photograph containing a package
> with printing on it. You have no context and are not comparing it to anything.
>
> For EVERY separate line or block of printing anywhere on the package,
> transcribe EXACTLY what the letters say — character for character, including any
> misspelling, invented word, or nonsense. Do NOT correct anything, do NOT guess
> at what it was probably meant to say, and do NOT fill in a word you cannot
> actually read. **Transcribing what a real package would say instead of what THIS
> image says is the single worst thing you can do here.**
>
> Classify each: `crisp` (letterforms sharp and individually distinguishable —
> you are reading letters, not guessing) · `soft` (mostly makeable-out, some
> characters ambiguous) · `unresolvable` (you can see printing is there but cannot
> make out any letters — a texture, a smudge, a grey bar).

**Standard:** every visible printed word must be letter-perfect, or genuinely
unresolvable by scale/shadow/occlusion. **"Not extractable" is not a passing
grade. Crisp-and-wrong is an instant kill.** Defocus kills letterforms uniformly;
AI garble keeps crisp strokes and correct type rhythm with wrong letters — the
test is sharpness-vs-correctness at the same plane.

**The worse failure class: INVENTED CLAIMS.** A generated product
does not merely garble its label — it prints claims that are not on the pack, in
the pack's own typeface, crisply. Garble announces itself; invented copy reads as
fact. And the claim a model reaches for is reliably the most compliance-loaded one
in the category. Two consequences:

1. **The claims audit must cover the PHOTOGRAPHED PACK's rendered text**, not only
   the code-set type layer. Every string the print audit transcribes off the
   product goes through the approved-claims check exactly like a headline.
2. Any transcribed string that is a plausible-but-absent brand claim is a **kill**,
   not a fix — it is a legal surface, not a craft defect.

### 4d. Global illumination pass

The scripted physics cascade probes one column under one object; it cannot see two
contradictory keys or a frame with no cast shadows at all.

> You are a lighting supervisor examining ONE photograph. No context, no
> comparison. How many distinct light sources do the shadows imply? Is there
> exactly ONE dominant key? List every major object standing on the surface and
> whether it casts a shadow, in which direction, with what edge. Do all cast
> shadows agree? Is anything sitting on the surface casting nothing? Any orphan
> shadow, dark patch or arc with no object that could have cast it? Any smooth
> bald arc, clean swept ring, or region suspiciously smoother than around it? Any
> specular highlight implying a second light from a different direction?
> Verdict: coherent or incoherent, and why in under 30 words.

### 4e. Feed-gate (scripted)

`{{FEED_GATE}}/ablate.py <ad.png> --modes chrome,phone,desat` plus
`feedmock/render_infeed.py` for the true-phone-scale view.

A clean sweep grants exactly one thing: **"not killed by the medium."** It never
grants ship. And an instrument that counts a photographed object's own printed
label as the AD's text will fail every product photograph — report that, do not
move the bar; the fix belongs upstream in the instrument and is validated against
the corpus, never against the ad that exposed it.

---

## 5. Copy gates — co-equal with visual

### 5a. banned-phrase scrub (mechanical, exit-1 fatal)
Run `python3 runtime/scrub/scrub.py check <copy.txt>` over every line of copy. A hit is a fatal, not a
suggestion.

### 5b. Persona gate

One agent per persona, each given ONLY that persona's file.

> Read `{{PERSONA_FILE}}` including its JUDGE PROTOCOL section, then react to this
> ad **as that person**, in their vocabulary, tracing every reaction back to
> evidence in the file.
>
> `{{AD_PATH}}`
>
> Three questions, in this order:
> 1. **Would you stop?** First 1.5 seconds — image plus the first four words.
> 2. **Would you believe it?** Does the claim survive this person's specific
>    skepticism?
> 3. **Would you buy?** What has to be true, and what is still in the way?
>
> Plus: **what they'd say out loud** — one line, their idiom.
>
> The honesty rail: **this person defaults to scrolling past.** Not stopping is
> the correct answer most of the time and you will not be penalised for it.
> Anything you cannot trace to the evidence file gets tagged `[extrapolation]`.
> A thin honest reaction beats a rich invented one.

**Resolution rule when instruments disagree about a mechanism:** ask whose
currency it is. **Device-level disputes resolve toward the persona** (they judge
the purchase); **craft-level defects — rhythm, hung punctuation, a doubled logo —
resolve toward the lineup critic** (they judge craft-normativity). A mascot or a
character is brand voice in a costume: character presence does not convert a brand
claim into human testimony, and the persona instrument reads them identically.

### 5c. Copy grammar check (against the North-Star picks)

- headline **3-7 words**, a declarative category claim
- benefits **concrete and numeric, ALWAYS present** — zero-benefit copy is the
  zero-benefit fatal wearing a nicer coat
- **benefit leads; the credibility fact supports.** Concession is seasoning, never
  the lead (law 28)
- **the hedge never takes the headline.** A hedged approved claim promoted to
  headline reads as the lawyer talking and manufactures the reader's objection
- register per law 27: plain lowercase declaratives, spoken not written, zero
  cleverness
- **one product name per frame**
- a first-person line must be (a) a real verbatim customer quote, (b) visibly in
  quotation marks, (c) attributed — or be rewritten to brand voice
- attribution labels may cover only **byte-verified** quoted material; brand-voiced
  lines live outside the attributed block
- **truer numbers over rounder ones** — but a too-perfect summary statistic has its
  own uncanny valley; prefer showing the distribution or one imperfect detail over
  a clean number
- **don't spoil the gag** — an eyebrow that explains the reveal spends the idea
  before it fires

---

## Dispatch checklist

Before sending any judge prompt, confirm:

- [ ] no brief, no concept card, no scores, no iteration number in the prompt
- [ ] no path to `iterations.jsonl`, `learnings.md`, or build-notes
- [ ] fresh agent (not the builder, not a judge from a prior round)
- [ ] one lens only
- [ ] North-Star / Bank draws rotated from last round
- [ ] the lineup is shuffled and the candidate's position is recorded by the
      orchestrator, not stated to the judge
- [ ] **the lineup is NORMALISED** (§3): every member re-encoded to identical
      format + long-edge resolution, metadata stripped, neutral shuffled filenames
      in a fresh directory. Confirm by listing the files — identical dimensions and
      extension, or the lineup is not blind and its verdict is not usable
- [ ] the North-Star draws match the candidate's aspect ratio, or the mismatch is
      recorded on the round
- [ ] output will be logged verbatim, including the parts that contradict the
      other instruments
