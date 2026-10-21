# Concept ideation prompt template

Used in Phase 2 of the adgen-vertical-ad pipeline. Generates 2-3 wild ad concepts from the brief.

## When to use

After Phase 1 discovery is complete and the operator has a brief.md. Before any character refs or video gen.

## Goal

Surface 2-3 distinct creative concepts so the operator picks before we commit to a script. Each concept should be different in tone / archetype / risk level so they have a real choice.

## What "wild" means

The operator's preference is to push past safe / generic ad concepts. Think of a villain who stops the ad cold to sing a power ballad, or a mascot played completely straight in an absurd genre. That kind of energy.

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

## Example output (an invented dish-soap brand, for illustration only)

```
# Ad concept brief: [Brand]

## Concept 1: "Sink Showdown"
**Archetype:** small-town western standoff, played completely straight
**Vibe reference:** spaghetti-western framing at kitchen-counter scale, claymation, deadpan narration
**Hook (first 2 sec):** Extreme close-up of a clay kitchen sponge squinting into the dawn light over a pile of dirty dishes. A tumbleweed of lint rolls past.
**Story (6 shot outline):**
1. Suds (the sponge sheriff) surveys the overflowing sink at dawn (warm, wide)
2. The drain gurgles. The Grease Baron oozes up from it, crown of burnt crumbs and all (cold, ominous)
3. THE ANTHEM: the Grease Baron sings a slow villain ballad about every pan he has ruined (music-video cuts, lip-synced to an external track)
4. Suds is knocked flat into the suds of a cheap, harsh soap that does nothing (low point)
5. The [Brand] bottle slides down the counter like a drink across a saloon bar; Suds catches it (the turn)
6. One squeeze, the Baron dissolves, plates sparkle, Suds tips his hat + tagline
**CTA:** [brand domain]: plant-based, cuts grease, kind to hands
**Risk:** the villain song is the centerpiece; if it lands it gets shared, if it does not the middle drags
**Why it works:** the product is literally the hero's weapon, so every beat after the turn sells

## Concept 2: "Sink Noir"
**Archetype:** hard-boiled detective
**Vibe reference:** black-and-white noir lighting, rain on the window, claymation
**Hook (first 2 sec):** "The pan came in at midnight. It had been through things."
**Story:**
1. Rainy kitchen at night, a scorched pan sits on the counter like a client in a detective's office
2. Detective Suds takes the case, narrating in voice-over
3. Flashback: the lasagna incident
4. Suds interrogates three cheap soaps; each one cracks under pressure
5. The [Brand] bottle steps out of the shadows
6. Morning light, clean pan, case closed
7. Logo + tagline
**CTA:** case closed on grease
**Risk:** noir needs a lot of narration; harder to land in 30-50 sec vertical
**Why it works:** the stubborn-grease problem maps cleanly onto "the case nobody could crack"

## Concept 3: "Dish Pile Documentary"
**Archetype:** nature-documentary parody
**Vibe reference:** hushed wildlife narration, macro lenses, claymation
**Hook (first 2 sec):** Macro push-in on a cereal bowl. A whispered narrator: "Here, in the sink, only the strong survive."
**Story:**
1. Establishing macro shots of the dish pile as a landscape
2. The narrator tracks a lone fork across the "plains"
3. The grease "migrates" across a plate
4. A dramatic predator moment: the [Brand] bottle arrives
5. Time-lapse of the pile clearing
6. Logo + CTA
**CTA:** survival of the cleanest
**Risk:** relies on one narrator voice, lower energy than Concept 1
**Why it works:** cheap to produce (few characters), easy to cut into multiple lengths

---

Recommendation: I'd push CONCEPT 1 ("Sink Showdown") because:
- Single protagonist arc is easiest to track in 50 sec vertical
- The villain song is the kind of thing that gets shared
- The product IS the turn of the story, so every beat after it sells

Which way?
```

## Iteration

If the operator rejects all 3 concepts:
- Ask what specifically didn't work — too safe? too weird? wrong archetype?
- Propose 2 NEW concepts that address their feedback
- Don't just iterate the same 3 with small tweaks

If the operator picks one but wants modifications:
- Make the changes IN the brief, save it
- Move to Phase 3 (script writing) with the modified concept

## Voice rules for the concept brief itself

The CONCEPT BRIEF is prose written for the operator. If they keep voice rules in their `CLAUDE.md`, apply them. An example house style:

- All lowercase
- → arrows for lists, not bullets  
- No em dashes (use ellipses or new sentences)
- No AI-isms ("here's the thing", "let me break it down")
- Lead with a sharp claim
- Educate before selling

The CONCEPT CONTENT (character descriptions, dialogue, etc.) can use any voice/dialect that fits the spot.
