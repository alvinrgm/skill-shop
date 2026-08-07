# Concept ideation prompt template

Used in Phase 2 of the adgen-vertical-ad pipeline. Generates 2-3 wild ad concepts from the brief.

## When to use

After Phase 1 discovery is complete and the operator has a brief.md. Before any character refs or video gen.

## Goal

Surface 2-3 distinct creative concepts so the operator picks before we commit to a script. Each concept should be different in tone / archetype / risk level so they have a real choice.

## What "wild" means

The operator's preference is to push past safe / generic ad concepts. The flour-brand spot's iconic moment was a hybridized wheat character rapping in autotuned trap style. That kind of energy.

Reference points:
- Iranian lego war commentary videos (visual archetype + character voice does the lifting)
- Liquid Death (absurd tone, anti-marketing)
- Old Spice (surreal, character-driven)
- Aviation Gin "Peloton wife" (subverting expectations)

NOT reference points:
- Generic explainer videos
- Talking-head testimonials  
- Any concept that could exist for any brand

## Template

```
# Ad concept brief: [brand]

## Concept 1: [name]
**Archetype:** [the visual/narrative shape — e.g., "courtroom drama", "lego war footage", "pixar character origin story", "cooking show parody"]
**Vibe reference:** [specific touchstones — "Aviation Gin wife", "Lil Yachty music video", "Aardman Chicken Run", etc.]
**Hook (first 2 sec):** [what makes someone stop scrolling]
**Story (6-8 shot outline):**
1. [Shot 1 description]
2. [Shot 2 description]
...
**CTA:** [how it lands the brand promise]
**Risk:** [what could go wrong — too edgy? too weird? unclear product link?]
**Why it works:** [the insight — what makes this archetype right for THIS brand]

## Concept 2: [name]
[same structure]

## Concept 3: [name]
[same structure]

---

Recommendation: I'd push [concept #N] because [reason].
What do you want to develop?
```

## Example output (the flour brand — what we ended up doing)

```
# Ad concept brief: [Brand]

## Concept 1: "Amber's Story"
**Archetype:** character origin story → corruption → redemption
**Vibe reference:** Pixar Cars meets Iranian Lego war videos. Anthropomorphized wheat as a character with a dramatic arc.
**Hook (first 2 sec):** Wholesome wheat character introduces himself in a 1900s field. Slam cut to him being abducted and experimented on by 1950s big-ag.
**Story (6 shot outline):**
1. Amber intros himself in golden 1900s wheat field (warm)
2. SLAM CUT to 1953 lab — strapped to table, NORIN-10 syringe (cold horror)
3. THE RAP — modern hybridized Amber raps in deadpan autotune about what was done to him (music video, multiple cuts)
4. SOFT CUT back to the wheat field — original Amber still alive (warm restoration)
5. Bread montage — sourdough, tortillas, pizza dough (mouth-watering)
6. Bag CTA + "tall wheat, real bread, no apologies" (definitive close)
**CTA:** [brand domain] — heritage wheat, milled fresh, pre-industrial
**Risk:** rap shot is the centerpiece — if it lands, viral; if it doesn't, the whole spot collapses
**Why it works:** the absurdity hooks (rapping wheat), the science is real (Norin 10 hybridization in 1953 IS the origin of modern wheat), and the brand IS the resolution to the corruption story

## Concept 2: "The Exorcism"
**Archetype:** supervillain / showdown
**Vibe reference:** Aardman claymation, Wallace and Gromit, Liquid Death's "wholesome violence"
**Hook (first 2 sec):** A modern bread loaf in a kitchen RISES OFF the counter, eyes form in the crust, glowing toxic green. "I am Roundup-ready."
**Story:**
1. Woman bloated on kitchen floor, supermarket bread glowing toxic green
2. Bread loaf becomes a CHEMICAL DEMON, hovering, dripping green
3. Pantry door opens — tiny claymation MILLER with sack of the brand's flour
4. STANDOFF — "Amber. White Sonora. 1873."
5. Miller throws flour, demon SHRIEKS and deflates
6. Woman eats heritage bread, glows, levitates
7. Logo + tagline
**CTA:** PRE-INDUSTRIAL. POST-BLOAT.
**Risk:** more characters to develop (woman, miller, demon bread), maybe too many voices
**Why it works:** body-horror-as-comedy, names the heritage varieties explicitly, immediate stakes (bloating)

## Concept 3: "The Trial"
**Archetype:** courtroom drama
**Vibe reference:** South Park trials, Aardman, "What if grains had a court of law"
**Hook (first 2 sec):** Wide shot of a tiny claymation courtroom. Modern hybrid wheat on the witness stand. "State your name." "I... I don't remember anymore."
**Story:**
1. Courtroom establishing — wheat varieties as jury members
2. Modern hybrid wheat testifies, breaking down
3. Prosecutor (Amber as lawyer) presents evidence — 1953 lab footage flashbacks
4. Judge: "Guilty of crimes against gut health"
5. Smash cut to bread montage
6. Logo + CTA
**CTA:** bring back the original
**Risk:** more dialogue-heavy (3-4 voices), harder to script in 50 sec, less immediately viral
**Why it works:** unique format (no one's done a wheat courtroom drama), gives space to lay out the whole modern-wheat critique with comedy beats

---

Recommendation: I'd push CONCEPT 1 ("Amber's Story") because:
- Single protagonist arc is easiest to track in 50 sec vertical
- The rap shot is the kind of thing that gets shared (high viral coefficient)
- Brand promise (heritage wheat) IS the resolution to the story — every beat sells

Which way?
```

## Iteration

If the operator rejects all 3 concepts:
- Ask what specifically didn't work — too safe? too weird? wrong archetype?
- Propose 2 NEW concepts that address his feedback
- Don't just iterate the same 3 with small tweaks

If the operator picks one but wants modifications:
- Make the changes IN the brief, save it
- Move to Phase 3 (script writing) with the modified concept

## Voice rules for the concept brief itself

The CONCEPT BRIEF is prose written for the operator. Voice rules from `~/.claude/CLAUDE.md` apply:

- All lowercase
- → arrows for lists, not bullets  
- No em dashes (use ellipses or new sentences)
- No AI-isms ("here's the thing", "let me break it down")
- Lead with a sharp claim
- Educate before selling

The CONCEPT CONTENT (character descriptions, dialogue, etc.) can use any voice/dialect that fits the spot.
