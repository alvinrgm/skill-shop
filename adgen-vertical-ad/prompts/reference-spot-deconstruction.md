# Reference-spot deconstruction template

When the operator shares a real ad, sketch, music video, or short film as a tonal/structural reference for the spot we're producing, STOP at Phase 1.5 (between Phase 1 brief and Phase 2 breakdown) and write a `reference-spot-analysis.md` artifact.

## Why this exists

A reference gets borrowed for its surface cues (lines, punchline style, register) while its STRUCTURAL architecture goes unexamined. But a reference's audio pattern — who narrates, when characters speak in-scene, whether an announcer interrupts — defines the entire downstream pipeline. Miss it and the spot defaults to per-clip seedance audio (Strategy A) when the reference actually needs a continuous narrator (Strategy B), which is only discovered at stringout and costs a rebuild.

A reference-spot deconstruction at Phase 1.5 catches this. The 5-axis analysis is fast (~10 minutes) and feeds directly into the Phase 2 breakdown's audio architecture column.

## When to run

Trigger this when the operator says:
→ "do it like [reference]"
→ "tonally like the [X] ad"
→ "structure it like that [Y] video"
→ "I love the way [Z] does this beat"
→ pastes a YouTube transcript / video link as inspiration

Skip when:
→ the operator gives only abstract creative direction ("make it weird," "lean comedic") with no specific reference
→ Reference is purely visual (a still image, a Pinterest board) — no audio architecture to deconstruct

## The 5 axes

### Axis 1 — Narrator architecture

Who carries the through-line of the reference spot?

Possible patterns:
- **First-person testimonial:** main character narrates their own experience retrospectively (most testimonial ads, lots of B2B founder videos)
- **Omniscient third-person:** detached narrator describes what's happening (Apple "Think Different" voice-over, Nike "find your greatness")
- **In-scene only:** no narrator, all audio is from characters speaking in real time (most commercial dialogue spots, indie shorts)
- **Multiple narrators interleaved:** documentary-style with several voices (vox-pop ads, ensemble pieces)
- **Voiceless:** music + visuals only, no spoken word (perfume ads, fashion campaigns)

Write 2-3 sentences capturing the reference's narrator pattern. Be specific about WHO speaks WHEN.

### Axis 2 — In-scene moments

What dialogue is lip-synced to on-screen characters? When does the in-scene break the narration?

For each in-scene moment in the reference:
→ Who speaks
→ What they say (1-line summary)
→ Whether the narrator continues over them or pauses
→ Whether the in-scene is the joke / emotional beat / setup

This axis matters because in-scene moments need lip-synced seedance video, while pure narration over silent visuals can be 11L + ken-burns. The ratio of in-scene to narration determines the Strategy A / B / hybrid call.

### Axis 3 — Music role

What does music do in the reference?

Possible patterns:
- **Continuous bed, low volume:** music ties cuts together but stays under dialogue (most testimonial ads, prestige tech ads)
- **Dramatic score with peaks:** music swells at emotional beats, ducks during dialogue (movie trailers, prestige TV)
- **Genre-mimicry track:** the music itself IS the format reference (e.g., a parody that uses the target genre's signature score as the joke)
- **Silent:** no music, ambient only (vérité-style, sketch comedy)
- **Source music only:** music plays from a visible in-scene source (radio, TV in the background)

Write 1-2 sentences. The music role affects Phase 6+ planning (Suno bed in FCP? per-clip seedance music? silent throughout?).

### Axis 4 — Format-mimicry beats

What genre conventions does the reference borrow, and which BEATS of that genre does it hit?

For example, a late-night infomercial parody borrows from the standard infomercial format:
→ Beat 1: black-and-white "there has to be a better way" struggle open
→ Beat 2: host bursts in with the product
→ Beat 3: side-by-side demo against the "old way"
→ Beat 4: rapid-fire feature list with on-screen callouts
→ Beat 5: studio-audience / testimonial reaction
→ Beat 6: "but wait, there's more" escalation
→ Beat 7: urgent call-to-action with a countdown

List the beats that the reference hits. This becomes the SHOT STRUCTURE for our spot — each beat is a potential shot or cluster of shots.

### Axis 5 — Punchline structure

Where does the joke / reveal / emotional landing happen? What supports it?

For each major punchline in the reference:
→ Where in the timeline (early / middle / end?)
→ What setup makes it land (a callback, a format break, an unexpected character beat)
→ Whether the punchline is visual, audio, or both

This axis tells us where our spot's payoff needs to land and what setup work the earlier shots have to do.

## Output format

Save to `$ADGEN_HOME/<brand>/concepts/<slug>/reference-spot-analysis.md`. Use this structure:

```markdown
# Reference spot deconstruction — [reference name]

Source: [link / transcript paste / file path]
Analyzed: [date]
For: [our spot project name]

## Axis 1 — Narrator architecture
[2-3 sentences]

## Axis 2 — In-scene moments
| Timecode | Speaker | Line (summary) | Narrator status during | Role in spot |
|---|---|---|---|---|
| 0:04 | host | "there has to be a better way" | silent (no narrator yet) | setup |
| 0:12 | customer | "it actually worked?" | announcer talks over | supports the demo beat |
| ... | ... | ... | ... | ... |

## Axis 3 — Music role
[1-2 sentences]

## Axis 4 — Format-mimicry beats
1. [Beat description]
2. [Beat description]
...

## Axis 5 — Punchline structure
[List punchlines + setup]

## Implications for our spot

→ Narrator architecture decision: Strategy A / B / hybrid? (cite Axis 1 and Axis 2 ratio)
→ Voice cast: how many 11L voices vs seedance voices?
→ Music plan: Suno bed in FCP? per-clip? silent?
→ Shot count target: based on Axis 4 beats
→ Critical setup work: based on Axis 5 punchlines

## Hand-off to Phase 2 breakdown

The breakdown's `Narrator VO (11L)` column should map directly from Axis 1 + Axis 2.
The breakdown's `In-scene dialogue (seedance)` column should map from Axis 2 in-scene rows.
The breakdown's `Music + SFX` column should reflect Axis 3.
The number of shots should align with Axis 4 beats.
```

## Worked example — a wildlife-documentary register as the reference for an invented insulated-bottle spot

For reference only (the brand, character and lines are invented). The operator asks for "an office spot narrated like a hushed nature documentary" for a steel water bottle. The deconstruction:

```markdown
# Reference spot deconstruction — wildlife-documentary register (genre reference)

## Axis 1 — Narrator architecture
Omniscient third-person. One hushed, reverent narrator observes the subject from a distance and explains its behavior as if it were an animal in the wild. The subject never addresses the narrator; the narrator never appears on screen.

## Axis 2 — In-scene moments
| Timecode | Speaker | Line (summary) | Narrator status | Role |
|---|---|---|---|---|
| — | (subjects) | none — observational footage only | narrator carries everything | establishes the register |

→ The genre has NO in-scene dialogue. Our comedic break: the subject speaks exactly ONCE, at the payoff, and the narrator reacts.
→ Ratio: ~90% narrator VO over observational visuals / ~10% in-scene. Strategy B.

## Axis 3 — Music role
Mostly ambient (room tone, natural sound) with the score held back; a single orchestral swell lands at the "discovery" moment and resolves on the closing line. The restraint IS the format cue — the hush tells the viewer what genre this is.

→ Implication: no continuous bed. Office room tone across the spot + one Suno orchestral swell (strings + horn) placed in FCP under the reveal and end card.

## Axis 4 — Format-mimicry beats
1. Dawn establishing shot of the habitat
2. Observation of the subject's daily struggle
3. The arduous journey to the watering hole
4. The discovery (the score finally swells)
5. Payoff — the subject thrives; the rest of the herd takes notice
6. Closing reflection line

For the spot: beat 1 = open-plan office at 8am; 2 = lukewarm desk water; 3 = trek to an empty water cooler; 4 = product reveal; 5 = ice still rattling at 5pm, coworkers' heads pop up over the partitions; 6 = CTA.

## Axis 5 — Punchline structure
Main punchline = format mismatch (a mundane office treated with nature-doc gravity). Recurring micro-punchlines = the narrator's solemn framing of trivial behavior. Final punchline = the subject breaks the genre by speaking to camera ("Still cold."), and the narrator, unbothered, delivers the CTA.

## Implications for our spot
→ Narrator architecture: Strategy B. One 11L narrator carries 6 of 7 beats; seedance handles a single in-scene line.
→ Voice cast: 1 11L voice (hushed documentary narrator) + 1 seedance-lip-synced voice (Otto, one line). Coworkers are silent extras.
→ Music plan: no bed. Room tone throughout; one orchestral swell at the reveal, resolving under the end card.
→ Shot count: 7 clips, no vignette clusters.
→ Critical setup: shots 1-3 must establish the hush and the deadpan narrator before the reveal; the only in-scene line is saved for shot 6 so the genre break lands.
```

Run at Phase 1.5, this locks the narrator architecture before the breakdown is written, so the Phase 5 gens are the right per-shot decisions and v1 ships cleanly.
