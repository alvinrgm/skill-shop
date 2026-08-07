# Scene stability clause

Copy-paste this clause into every seedance shot prompt where the camera is LOCKED (no pan, no zoom, no cut). Prevents the model from inventing new objects mid-shot.

## The clause (paste verbatim)

```
=== SCENE STABILITY REQUIREMENT (CRITICAL) ===
The scene must remain VISUALLY IDENTICAL throughout the entire {N} seconds.
NO new objects appear during the shot. NO laundry, NO clothesline, NO new ropes,
NO new banners, NO new decorations, NO new background elements, NO new props.
Whatever is visible at second 0 must be the only things visible at second {N}.
The only things that change in the shot are:
  (a) the action described above
  (b) lighting/mist/atmosphere if specified
  (c) the characters' expressions and gestures
EVERYTHING ELSE STAYS PUT. Camera does NOT cut, pan, zoom, or change angle.
```

Replace `{N}` with the shot duration in seconds.

## When to use

→ Any locked-camera shot (no camera motion in the visual description)
→ Any shot where the model has previously added unwanted objects (clotheslines, banners, decorations)
→ Any shot that needs strict continuity with the prior shot
→ Multi-character dialogue shots (where attention is on dialogue and the background should disappear)

## When NOT to use

→ Tracking shots / pans / dolly moves — the scene is intentionally changing, this clause will fight the prompt
→ Crash zooms / push-ins — same
→ Action sweeps (e.g., wipe sweeping through encampment) — the scene IS the action

## Custom enumeration

When the model has a specific bad habit on a project, enumerate the forbidden additions explicitly. Example from the pet-wipes brand:

```
DO NOT add a clothesline. DO NOT add hanging laundry. DO NOT add tiny shirts,
pants, or fabric items strung between strands. The encampment is an unfurnished
outdoor camp — no laundry, no decorations.
```

Add a similar enumeration to the clause when re-firing a shot that had a known pop-in.

## Anti-pattern: hoping the model "just keeps it stable"

❌ "Camera locked. Subtle stop-motion micro-sway. No cuts."
✓ Use the full clause above. Models extrapolate. Stop them from extrapolating.

## Why this works

Seedance interprets short prompts loosely and fills in gaps. If you say "encampment with laundry strung between strands" once and then describe action, the model may decide to add more laundry over time. The stability clause is a hard guard: anything not in second 0 is FORBIDDEN at second N.

Tested on the pet-wipes spot shot 3 v9 — explicit clothesline-prohibition fixed the mid-scene pop-in that appeared in v8.
