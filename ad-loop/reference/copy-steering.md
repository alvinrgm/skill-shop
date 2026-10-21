# Copy steering — directing the messaging, at charter or mid-loop

The operator can iterate on copy or nudge it toward a strategic angle (e.g. counterpositioning against a specific
competitor) without touching the visual loop. Two entry points, one artifact.

## The artifact: the copy-direction card

`<workdir>/loop-state/<concept>/copy-direction.md` — written whenever a
direction is set, read by every builder, and INCLUDED IN THE SEALED BRIEF so the
judge battery evaluates against the declared direction (the reconstruction gap
diffs what a cold reader received against the direction's intended message; the
persona checks it lands in the buyer's currency; the twin's verdict is grounded
in it).

```
direction: counterposition | category-claim | customer-voice | origin-story | offer-led
enemy: <named competitor | a category convention | an ingredient/practice> (counterposition only)
mode: implicit | explicit          # see the legal/brand gate below
stance: <one sentence — what the copy argues>
register-constraints: <client voice rules that bind here>
provenance: <the operator's words that set this direction, verbatim, dated>
```

## Entry point 1 — charter-time intake (one batched round)

At concept charter, ask 3-4 questions WITH DEFAULTS (skipping is safe):
1. Positioning stance — category claim / counterposition / customer-voice /
   origin story / offer-led? (default: whatever the account evidence supports)
2. If counterposition: against WHOM or WHAT — a named competitor, a category
   convention ("the usual brand"), or an ingredient/practice? What is the ONE
   contrast that matters?
3. Any copy directions already tried and disliked? (bans list)
4. Register constraints beyond the client voice file?

## Entry point 2 — mid-loop steering command

"steer copy: <direction>" (e.g. "steer copy: counterposition against the
category leader on freshness") at ANY point:
1. Orchestrator writes/updates the copy-direction card with the operator's
   verbatim words as provenance.
2. The CURRENT iteration finishes its round (never orphan a judging pass);
   the NEXT build generates copy against the new card.
3. Copy-only steering does not reset the visual loop — plates, layout, and the
   monotone gate carry forward; only the copy layer and its gates re-run.
4. The direction change is logged in iterations.jsonl as `copy_steer` with
   provenance — direction changes are data for the verdict bank too.

## The legal/brand gate on counterpositioning (hard)

- Read the client layer FIRST: if the client's voice/claims rules ban naming
  competitors or snark (many do), `mode: explicit` is unavailable —
  counterposition runs IMPLICIT: the unnamed generic ("the usual brand", "most
  of what's on the shelf"), category conventions, or the customer's own comparative
  language from verified reviews (quoted + attributed).
- `mode: explicit` (naming the competitor) additionally requires: every
  comparative claim substantiated and traced in claims/ (comparative
  advertising is a heightened legal surface); no claim about the competitor's
  product that isn't publicly verifiable; flagged in the ship report for the
  operator's sign-off EVERY time — never ships on gate passes alone.
- The no-snark law (design-laws law 20 register + client rules) binds in both
  modes: contrast is drawn generously ("you'd have to ask" not "they hide it").

## Copy variants inside a round

When a direction is set, the builder writes headline/support candidates for the
SAME visual under 2-3 stances max (the card's + one alternate), and the copy
gates (banned-phrase scrub, persona, claims) pick per the rubric — variants are cheap;
judging attention is not. The losing stance's candidates are logged, not
discarded (bans/learnings food).
