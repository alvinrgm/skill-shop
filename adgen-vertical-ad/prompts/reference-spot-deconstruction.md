# Reference-spot deconstruction template

When the operator shares a real ad, sketch, music video, or short film as a tonal/structural reference for the spot we're producing, STOP at Phase 1.5 (between Phase 1 brief and Phase 2 breakdown) and write a `reference-spot-analysis.md` artifact.

## Why this exists

Past mistake (the coffee brand "ask your abuelo," May 2026): the operator referenced the SNL Couplabeers skit at Phase 2 as the tonal/structural inspiration. Used it for surface cues (script lines, "ask your abuelo" punchline, suburban-mockumentary register) but never deconstructed its STRUCTURAL architecture. Couplabeers has a specific audio pattern (husband narrates over flashbacks while characters speak in-scene around him + fake pharma announcer interrupts) that defines the entire downstream pipeline. Missed it. Defaulted to per-clip seedance audio (Strategy A) when the reference required continuous-narrator (Strategy B). Cost ~200 credits in re-fires.

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
- **First-person testimonial:** main character narrates their own experience retrospectively (Couplabeers, most pharma ads, lots of B2B founder videos)
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
- **Continuous bed, low volume:** music ties cuts together but stays under dialogue (most pharma ads, prestige tech ads)
- **Dramatic score with peaks:** music swells at emotional beats, ducks during dialogue (movie trailers, prestige TV)
- **Genre-mimicry track:** the music itself IS the format reference (e.g., "couple of beers" uses sad-piano-pharma-ad music as the joke)
- **Silent:** no music, ambient only (vérité-style, sketch comedy)
- **Source music only:** music plays from a visible in-scene source (radio, TV in the background)

Write 1-2 sentences. The music role affects Phase 6+ planning (Suno bed in FCP? per-clip seedance music? silent throughout?).

### Axis 4 — Format-mimicry beats

What genre conventions does the reference borrow, and which BEATS of that genre does it hit?

For example, Couplabeers borrows from the standard pharma-ad format:
→ Beat 1: somber piano + testimonial open ("a few months ago anxiety was ruining my life")
→ Beat 2: doctor consultation (or product introduction)
→ Beat 3: transformation montage with bright music
→ Beat 4: calm announcer reading clinical claims over product b-roll
→ Beat 5: "side effects may include" with absurd visuals
→ Beat 6: "ask your doctor" CTA
→ Beat 7: family confrontation / emotional close

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
| 0:05 | wife | "have a great day" | silent (no narrator yet) | setup |
| 0:18 | son | "gah, come on!" | husband narrates over | supports "struggling as father" |
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

## Worked example — SNL Couplabeers for the "ask your abuelo" spot

If this had been run at Phase 1.5 (instead of skipped), the output would have been:

```markdown
# Reference spot deconstruction — SNL Couplabeers

## Axis 1 — Narrator architecture
First-person testimonial. The husband (the patient in the parody) narrates retrospectively about his transformation, with his voice playing OVER flashbacks of his life falling apart and recovering. He never delivers narration lines to camera in-scene; the in-scene moments are him interacting with family while his voiceover plays.

## Axis 2 — In-scene moments
| Timecode | Speaker | Line | Narrator status | Role |
|---|---|---|---|---|
| 0:00 | wife | "have a great day, gang" | silent | setup |
| 0:13 | son | "gah! come on!" | husband VO over | supports "struggling as father" |
| 0:31 | husband | "andrew, I love you, buddy" | in-scene break from VO | shows transformation effect |
| 0:38 | colleagues | (laughter) | "what are you guys laughing at" → "how stupid you are" | the dark turn |
| 1:09 | husband | "she's just jealous cause you're so beautiful" | breaks VO with unhinged in-scene | shows side effect |
| 2:14 | son | "honey, can you come sit down" | wife in-scene | confrontation setup |

→ Ratio: ~70% narrator VO over silent / 30% in-scene dialogue. Strategy B with hybrid moments.

## Axis 3 — Music role
Continuous sad-piano pharma-ad bed throughout. The MUSIC ITSELF is the format reference — the somber piano is what tells the viewer "this is a pharma ad" before any clinical claims appear. Music ducks under the fake-clinical-claims voiceover. Goes slightly warmer in transformation moments. Returns to sad piano in confrontation.

→ Implication: Suno continuous bed across whole coffee-brand spot, low volume, slight warming in shots 3-5.

## Axis 4 — Format-mimicry beats
1. Somber testimonial open ("a few months ago anxiety was ruining my life")
2. Doctor consultation ("that's when I talked to my doctor about a couple of beers")
3. Product introduction ("a couple of beers is a revolutionary medicine...")
4. Transformation montage ("within minutes of taking it, I'm back to my old self")
5. Calm clinical-claims announcer voiceover ("a couple of beers is clinically proven to treat conditions like boredom, depression...")
6. "Side effects may include" with absurd visuals
7. "Ask your doctor" CTA
8. Family confrontation close

For the spot: hit beats 1, 2 (friend = doctor analog), 3, 4, 5, 6 ("you may notice..."), 7 ("ask your abuelo"), 8 (pantry stockpile).

## Axis 5 — Punchline structure
Main punchline = format mismatch (a normal thing reframed as medicine). Recurring micro-punchlines = the husband's increasingly inappropriate behavior delivered with deadpan-positive narrator framing. Final punchline = family confrontation interrupted by his calm "no" while wife is mid-question.

For the spot: equivalent = "ask your abuelo" tagline punchlines the entire pharma-format. Pantry stockpile + dead-serious "MY heirloom brew" closes the bit.

## Implications for our spot
→ Narrator architecture: Strategy B with hybrid. 11L Kiora carries 7-8 narrator beats, seedance handles 5 in-scene moments.
→ Voice cast: 1 11L voice (Kiora pharma-ad announcer) + 4 seedance voices (dad in-scene, wife, friend, kid — kid is visual only).
→ Music plan: Suno continuous pharma-ad piano bed across spot, ducked under dialogue.
→ Shot count: 7 main shots + 4 vignettes inside shot 5 = 11-12 clips.
→ Critical setup: shots 1-3 must establish the testimonial register; shot 6 is the "more is too much" beat; shot 7 is the punchline.
```

Had this artifact existed at Phase 1.5, the Phase 2 breakdown would have nailed the Kiora architecture from row 1, the Phase 5 seedance gens would have been the right per-shot decisions, and we would have shipped v1 cleanly.
