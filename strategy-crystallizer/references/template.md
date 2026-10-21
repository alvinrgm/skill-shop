# Strategy Template — canonical structure

This is the exact output structure for every strategy doc this skill
produces. Fill the slots *in order*. Each slot has a test the answer must
pass before moving on.

> The worked example throughout is **Southwest Airlines, founding through the
> 2000s** — the period the strategy is famous for. Parts of it have since
> changed (international routes from 2014, assigned and premium seating from
> 2026), which is itself the lesson: a strategy's refusals are dated, and the
> disconfirmation test in §8 is what tells you when they have expired.

---

## 1. Situation (2–3 sentences)

Neutral ground truth. What's happening in the market, the company, the
category. This is not yet the diagnosis. It's the facts a smart outsider
would need to follow the rest.

**Test:** Would a competitor write roughly the same sentences? If yes,
you've stayed neutral. If no, you've snuck in your conclusion.

**Anti-example:** "Southwest is poised to capture the booming low-cost
travel opportunity." (Editorializing, not neutral.)

**Good:** "Southwest flies a single aircraft type, point-to-point between
mid-sized US airports, with no assigned seats, no first class, and no
interline baggage transfer. Network carriers run hub-and-spoke with mixed
fleets and connecting itineraries."

---

## 2. Diagnosis (1–2 sentences)

Name the *actual* constraint beneath the surface. Not the symptom. Not
the goal. The real thing.

**Test:** Does it name a constraint, not an aspiration? Is it specific
enough that you could be wrong? Would the company's leadership feel
uncomfortable reading it?

**Anti-example:** "Southwest needs to grow brand awareness." (Symptom, not
constraint.)

**Good:** "Southwest's real competition is not other airlines but the car.
On a 400-mile trip the traveler is already willing to drive, and every hour
of airport friction hands the trip back to the highway."

---

## 3. Choice — where to play (1 sentence)

In what arena, with which customer, around which occasion, in which
geography are we competing?

**Test:** Does this sentence rule something out? If it could apply to any
player in the space, it's not specific enough.

**Anti-example:** "Southwest serves travelers and businesses across the
country." (Rules nothing out.)

**Good:** "Southwest competes for short-haul trips between mid-sized city
pairs where the realistic alternative is a 4-to-6-hour drive."

---

## 4. Mechanism — how to win (1 sentence)

The specific edge or advantage. Not a tactic. Not an aspiration. The
structural thing that makes winning possible.

**Test:** Could a competitor copy this by spending more money? If yes,
it's a tactic, not a mechanism. A real mechanism leverages something
structural — density, network effects, partner exclusivity, process
power, a cornered resource — that competitors can't replicate by trying
harder.

**Anti-example:** "Southwest will win by running better advertising."
(Copyable with budget.)

**Good:** "Southwest wins on structural cost: one aircraft type collapses
training, maintenance, and spares into a single pool, and point-to-point
routing keeps planes in the air rather than waiting on connections — a cost
base a hub carrier cannot match without dismantling its own network."

---

## 5. Coherent actions (3–5 specific moves)

The moves that, together, make the mechanism work. Each one specific
enough that someone could own and ship it. Each one reinforces the
others.

**Test:** If you removed one action, do the others lose force? If they
hold up fine without it, that wasn't part of the strategy — it was just
a thing to do. Drop it.

Cap at 5. If you have more, you don't have a strategy, you have a
roadmap.

---

## 6. Refusals (3–5 explicit NOTs)

What the company will *not* do. Customers it will not serve. Markets it
will not enter. Channels it will not invest in. Metrics it will not
optimize for.

**Test:** Would saying these out loud in the leadership room create
political friction? If no, you haven't refused anything real. You've
just listed things no one was doing anyway.

**Anti-example:** "We will not be unfocused." (Refuses nothing.)

**Good:** "Southwest will not fly international. Southwest will not offer
first class. Southwest will not add a second aircraft type. Southwest will
not transfer baggage to another carrier."

---

## 7. Crystallization (one sentence, ≤25 words)

Compress diagnosis + choice + mechanism into a single bus-side sentence.
This is the version that has to survive being repeated in a hallway.

**Test:** Read it aloud. Does it land? Does it imply tradeoffs? Could a
future fact prove it wrong? Could a colleague repeat it from memory after
hearing it once?

**Anti-example:** "We will unlock incremental travel demand by offering
low fares to value-conscious segments, while building brand affinity in
launch markets, and compounding loyalty through experiences that increase
repeat utilization across trip types." (Three sentences fused; corporate
jargon; refuses nothing.)

**Good:** "Southwest beats the car on short-haul city pairs by refusing
every feature that would raise its cost base above driving."

---

## 8. Disconfirmation test (1–2 sentences)

What data, at what threshold, would force you to abandon or significantly
revise this strategy? Name a leading indicator and a level.

**Test:** Is the answer falsifiable? Could the strategy actually be wrong,
and would you know it?

**Anti-example:** "If growth slows, we'll reassess." (Vague.)

**Good:** "If cost per available seat mile comes within 10% of the network
carriers on any route cohort for two consecutive quarters, the cost
advantage has stopped being structural and the whole refusal list needs
re-litigating."

---

## Output file structure

Every strategy doc this skill produces follows this exact structure:

```markdown
# [Brand or situation] — Strategy
*Date · Mode (Build / Audit / Compare) · Author: strategy-crystallizer*

## Situation
[2-3 sentences]

## Diagnosis
[1-2 sentences]

## The Strategy

### Where to play
[1 sentence]

### How to win
[1 sentence]

### Coherent actions
1. [Action]
2. [Action]
3. [Action]
(...up to 5)

### Refusals
- We will not [refusal 1]
- We will not [refusal 2]
- We will not [refusal 3]
(...up to 5)

## The Crystallization
> [One sentence, ≤25 words]

## Disconfirmation Test
[1-2 sentences]

---

## Grade: [letter] ([score]/70)

| Dimension | Score | Reasoning |
|---|---|---|
| Diagnosis sharpness | X/10 | ... |
| Choice clarity | X/10 | ... |
| Mechanism defensibility | X/10 | ... |
| Action coherence | X/10 | ... |
| Refusal honesty | X/10 | ... |
| Crystallization sharpness | X/10 | ... |
| Falsifiability | X/10 | ... |

## Top improvements (if grade < A)
1. [Specific change with reasoning]
2. [Specific change with reasoning]
3. [Specific change with reasoning]
```
