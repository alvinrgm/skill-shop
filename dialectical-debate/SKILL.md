---
name: dialectical-debate
description: >-
  Stress-test a claim, answer, or question by spawning multiple sub-agents that
  hold opposing and complementary viewpoints, have them investigate independently,
  cross-examine each other across two or more rounds, and synthesize a
  confidence-rated verdict. Use this whenever the user wants to fact-check or
  double-check something, says "are you sure", "verify this", "I don't trust that
  answer", "double-check your last response", "stress-test this", "red team this",
  "what's the strongest case against X", "get me to the highest-confidence truth",
  or wants opposing perspectives weighed against each other before trusting a
  conclusion. Also trigger when a prior answer is high-stakes (medical, financial,
  legal, deployment, factual claims that will be acted on) and accuracy matters
  more than speed. Prefer this over answering directly whenever the user signals
  doubt about correctness or explicitly asks for multi-perspective verification.
---

# Dialectical Debate

## What this is for

Single-pass answers fail in two ways: factual errors no one challenged, and
reasoning that sounds right but rests on an unexamined assumption. This skill
attacks both by running a **dialectic** — opposing and complementary viewpoints
that investigate independently, then cross-examine each other — and ending with a
neutral judge that rates confidence by *evidence quality*, not rhetorical force.

The point is not to produce a confident answer. The point is to produce a
*calibrated* one: to separate what's genuinely solid from what only looks solid,
and to name what's still unresolved instead of papering over it.

## Two modes

Detect which mode applies from the request; when ambiguous, ask one quick question.

- **Verify mode** — the user has an answer/claim/output in hand (often one I just
  gave) and wants it checked. Trigger phrases: "are you sure", "double-check this",
  "verify the last answer", "is that right". Here the *subject under test* is a
  specific existing claim.
- **Investigate mode** — the user has a question and wants it answered from scratch
  with adversarial rigor. Closer to research, but structured as a debate. Here the
  subject under test is a question, and Phase 1 also has to *form* the candidate
  positions.

The phases below are the same for both; the only difference is Phase 0.

## The flow

### Phase 0 — Frame the subject under test

Pin down exactly what is being tested before spawning anyone. Vague framing is the
most common way these runs go wrong — agents end up arguing past each other.

- **Verify mode:** extract the specific, falsifiable claims embedded in the answer.
  Decompose a paragraph into atomic propositions ("X causes Y", "the threshold is
  Z", "library L supports feature F"). A claim you can't state crisply, you can't
  verify crisply.
- **Investigate mode:** state the question precisely, surface hidden definitional
  choices ("when they say 'best', do they mean cheapest, fastest, most reliable?"),
  and note any constraints that bound a valid answer.

Write the framed claim(s) down explicitly — you'll hand the exact text to every agent.

### Phase 1 — Decide the viewpoints (your discretion)

You decide how many agents to spawn and what stance each takes. There is no fixed
number — match it to how many genuinely distinct, defensible positions the topic
actually supports.

Guidance:

- **Start from at least two truly opposing stances** — an affirmative and a
  negative case for the claim. Opposition is what surfaces the strongest objections.
- **Add complementary or adjacent lenses when they exist and would change the
  verdict** — a different discipline's frame, a different stakeholder's reality, a
  "this depends on a definition" reframe, a base-rate/outside view. Add these
  because they'd surface something the two opposing agents would both miss, not to
  hit a quota.
- **Don't manufacture viewpoints.** A well-defined binary factual claim may only
  support two angles (the claim, and the case it's false plus source-checking).
  Fake balance is noise and dilutes the signal.
- **Soft cap: ~4–5 investigator agents per round.** If you find yourself wanting
  more, that's usually a sign two of your viewpoints overlap — consolidate them.
- **Calibrate to claim type.** Pure factual/lookup claims need fewer agents and
  more weight on source verification. Interpretive, predictive, or design claims
  support more viewpoints and need the debate.

State your roster and the one-line charge for each agent before spawning, so the
reasoning is visible and you can sanity-check it.

### Phase 2 — Independent investigation (round 1)

Spawn the chosen agents **in parallel, in a single message** (multiple Agent tool
calls at once) using `subagent_type: general-purpose` — or `Explore` for
search-heavy factual work. Web-heavy claims can have agents use WebSearch, or
delegate to the `deep-research` skill for the evidence-gathering portion.

Independence is the whole game. The Agent tool runs each sub-agent in isolation and
returns only its final message — so agents *cannot* see each other's work mid-flight.
Preserve that: do not feed one agent another's output in this round. If they see
each other early they anchor and converge prematurely, and you lose the independent
errors that cross-examination is supposed to catch.

Each agent's brief should contain: the exact framed claim, its assigned stance/lens,
and a charge to (a) build the strongest *evidence-based* case for its position, and
(b) honestly report the strongest objections to its own position and its own
confidence. See `references/agent-prompts.md` for ready templates.

### Phase 3 — Cross-examination (round 2, and round 3 if needed)

Now hand **all** round-1 outputs to a fresh cross-examiner agent. Its job is
adversarial:

- Find direct contradictions between the positions and identify which side's
  evidence is actually stronger.
- Flag unsupported leaps — claims asserted without evidence, or where the cited
  source doesn't actually support the claim.
- **Hunt for false consensus** — assumptions that *all* the agents shared and none
  questioned. Agreement is not truth if every agent inherited the same wrong premise.
  This is the highest-value thing the cross-examiner does, because it catches the
  errors the debate structure would otherwise hide.
- Re-check the most load-bearing disputed facts against primary sources.

Then decide whether a **third round** is warranted. Spawn one if cross-examination
surfaced a new crux that the round-1 agents weren't briefed to address, or if a
factual dispute can be settled by one targeted investigation. Don't loop for its own
sake — stop when another round wouldn't change the verdict. A third round is
available; use it when there's a live crux to resolve, not as ceremony.

### Phase 4 — Judge and synthesize

A neutral judge (do this yourself as orchestrator, or spawn a dedicated judge agent
for heavy cases) reads everything and produces the verdict. The judge's discipline:

- **Rank by evidence quality, not persuasiveness.** The better-argued side is not
  the same as the better-supported side. Weigh source strength, independence of
  corroboration, and whether objections survived.
- **Separate genuine consensus from false consensus.** Note explicitly when agents
  agreed for *independent* reasons (strong signal) versus agreed because they shared
  a premise (weak signal — flag it).
- **Calibrate confidence** using the scale below — don't inflate.
- **Name what's unresolved.** A surfaced, well-characterized disagreement is a
  better deliverable than a false clean answer.

## Output: inline confidence verdict

Default to a concise verdict in chat (write a full report file only if the user
asks). Use this shape:

```
Verdict: [holds / corrected / uncertain]   — one line
Confidence: [High / Moderate / Low] — one sentence of why

What's solid:
→ [claim] — [why it survived; evidence]

What changed / was wrong:   (verify mode, only if errors found)
→ [original claim] → [correction] — [what the error was]

Genuine disagreements:
→ [the crux] — [credible position A vs B, and what it hinges on]

Unresolved / would need more:
→ [open question] — [what evidence would settle it]

Sources: [links, when web/file evidence was used]
```

Keep it tight. If everything checks out cleanly, say so plainly and don't invent
disagreement to look thorough.

## Confidence scale (calibrate against this)

- **High (~85%+):** multiple *independent* lines of evidence agree; cross-examination
  found no surviving objection; sources are strong and directly on point.
- **Moderate (~60–85%):** the main thrust is supported, but with real caveats — one
  credible dissent, thin or indirect sourcing, or sensitivity to a definition.
- **Low (under ~60%):** credible disagreement persists, evidence is weak or
  conflicting, or the answer hinges on a contested premise. Say so; don't round up.
- **Flag false consensus separately** whenever the agents' agreement traces to a
  shared unexamined assumption — that caps confidence regardless of how unanimous
  they sounded.

## Anti-patterns (and why they matter)

- **Letting agents see each other in round 1** → premature convergence. Independent
  errors are the raw material cross-examination works on; destroy independence and
  you've just run one agent three times.
- **Rewarding the better debater** → you optimize for rhetoric, not truth. Judge on
  evidence.
- **Manufacturing viewpoints to hit a number** → dilutes signal with noise. Fewer
  real positions beat more fake ones.
- **Smoothing over disagreement for a clean answer** → the unresolved crux is often
  the most useful thing you can hand back. Surface it.
- **Treating unanimity as truth** → it isn't, if it rests on a shared wrong premise.
  Always run the false-consensus check.
- **Over-spawning for simple claims** → a definitional lookup doesn't need a
  five-agent tribunal. Scale effort to stakes and genuine contestedness.

## Reference files

- `references/agent-prompts.md` — copy-ready briefs for investigator, cross-examiner,
  and judge agents. Read this before spawning.

---

**Setup check:** `bash doctor.sh` — zero dependencies (per `dependencies.yml`), no `.onboarded` gate needed; it always passes.


---
Built and battle-tested at [Rise Growth Marketing](https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=dialectical-debate). More free skills, and the story of the systems behind them, at that link.
