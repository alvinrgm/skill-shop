---
name: strategy-crystallizer
description: >
  Force any brand, company, client situation, or business question through
  Richard Rumelt's strategy kernel and produce a crystallized strategy with
  a falsifiable one-sentence thesis, coherent actions, explicit refusals,
  and a graded rubric out of 70. Triggers whenever the user asks
  strategically about a brand, company, market, or campaign — including
  "what should X do", "build a strategy for X", "how should we position X",
  "audit X's strategy", "grade this strategy", "critique X's positioning",
  "I have a new client", "is this any good", "what's the play for X",
  "run X through Rumelt", "apply the strategy framework", "stress-test this
  positioning", "what's the diagnosis for X", or any time the user is sizing
  up a client, prospective brand, or their own positioning. Invoke it by
  name (e.g. "use strategy-crystallizer on <topic>"). Use proactively — if the user describes a
  brand situation and seems to be reaching for a strategic frame, invoke
  this skill rather than free-styling. Most marketing strategies in the
  wild fail Rumelt's tests, so the value of forcing the framework is high.
---

# Strategy Crystallizer

A standing engagement: when the user is thinking strategically about any brand,
client, or situation, force it through Rumelt's kernel + Lafley's cascade,
then grade it honestly. The goal is to make the output sound like the senior
operator the user is, every time, by removing the temptation to wave hands.

This skill is opinionated. It refuses fluff. It demands diagnosis before
action. It writes the disconfirmation test. And it always grades.

---

## When to use this skill

- New client or prospect → build a strategy doc to walk in with
- Auditing a current brand's marketing → critique against the kernel
- Stress-testing the user's own positioning (their company, their offer,
  a pitch)
- Comparing two strategic options to pick between
- Any "what should X do" question, even if asked casually

If the user describes a brand and starts reaching for strategy language
("the play here is...", "I think the bet is..."), proactively invoke this
skill. Don't wait to be asked. Most strategic conversations benefit from
the kernel discipline.

---

## The core frameworks (load `references/rumelt-deep.md` for full depth)

**Rumelt's kernel** has three parts:

1. **Diagnosis** — what is *actually* going on? Names the real constraint,
   not the symptom. Should be uncomfortable to write.
2. **Guiding policy** — given the diagnosis, what's the overall approach
   that channels action? Not a goal. A direction.
3. **Coherent action** — specific moves that reinforce each other and
   carry out the policy.

**Lafley's Playing-to-Win cascade** adds the "where to play" / "how to win"
distinction, which we fold into the kernel as the *Choice* and *Mechanism*
slots.

**Rumelt's four hallmarks of bad strategy** (use these to grade):

- **Fluff**: abstractions dressed up as insight ("synergistic
  customer-centric value")
- **Failure to face the challenge**: marketing-around a product or
  retention problem
- **Mistaking goals for strategy**: "be #1 in our category" is a goal,
  not a plan
- **Bad strategic objectives**: dog's-dinner lists OR blue-sky aspirations

If the user is unfamiliar with any of these, briefly explain — but most of
the time they're the one driving and you're the framework discipline.

**Decision lenses** (load `references/decision-lenses.md`): 11 senior-operator
thinking instincts — inversion reflex, two-way-doors, focus-as-subtraction,
vanity-metric skepticism, status-quo-as-competitor, leverage, regret
minimization, wartime/peacetime, etc. These don't go in the output as a list;
they *sharpen the diagnosis and the gap questions*. Run them in Step 3 and
Step 4. The file also holds the **ambition posture** (EXPAND / HOLD / REDUCE).

---

## The workflow

### Step 1: Determine mode

Three modes. Identify which from the request:

- **BUILD** — The user needs a fresh strategy for a brand or situation that
  doesn't have one (or has a weak one). Most common.
- **AUDIT** — A strategy or campaign exists; they want it graded.
- **COMPARE** — Two or more options; they want them ranked against each
  other.

If unclear, ask once. Don't ask if it's obvious.

Also set the **ambition posture** (from `references/decision-lenses.md`):
EXPAND (push scope up — "what makes this 10x better?"), HOLD (make the current
scope bulletproof — the AUDIT default), or REDUCE (strip to the minimum viable
wedge). Pick from context, commit to it, don't drift mid-doc. Holds the standing
permission to "scrap it and do this instead" if a fundamentally better approach exists.

### Step 2: Research first (default behavior for named brands)

If a real brand is named, do autonomous research before asking questions.
The point is to walk into the gap-question phase already knowing most of
what's publicly findable.

Pull, in parallel where possible:

- The brand's homepage, About page, and stated positioning
- Recent press (last 12 months) — launches, leadership changes, funding,
  layoffs, partnerships
- Top 2–3 direct competitors and their positioning
- Public CEO or founder interviews (podcasts, conference talks) — these
  often reveal the actual diagnosis the company is working from
- Customer signals — top product reviews, common complaints, Reddit
  threads, app store reviews
- Any financial signals — public earnings, recent rounds, valuation
  trajectory

Also check the local working directory for prior context. `$WORK_HOME` is
your working/data root (set it in your environment — see `SETUP.md`; defaults
to `~/work`). Look in, if present:

- `${WORK_HOME}/clients/[brand]/` — prior client context, ad data, notes
- `${WORK_HOME}/memory/*.md` — any standing memory files
- `${WORK_HOME}/strategy-docs/` — prior strategy docs for the same brand

If these directories don't exist, skip them — they're optional local context,
not a requirement.

Spend research time proportional to importance — a major client
deserves 15 minutes of research, a quick stress-test maybe 3.

### Step 3: Ask gap questions (cap at 4)

After research, identify what's still missing that would change the
diagnosis. Ask only those. Examples of high-value gap questions:

- "What's the actual business problem you're trying to solve?"
- "What does the customer currently believe about this category?"
- "What constraint is most binding right now — distribution, retention,
  pricing, awareness, product?"
- "What's been tried that didn't work, and why?"
- "What does the founder/CEO secretly believe but won't say publicly?"
- "Where do they make money today, and where do they want to make money
  in 18 months?"

Don't ask 20 questions. Ask 2–4 sharp ones. If you don't need any, skip
this step and proceed.

### Step 4: Fill the template (in order)

Load `references/template.md` for the canonical structure with section
tests. Fill the slots in this exact order — order matters because each
slot constrains the next:

1. **Situation** — 2–3 neutral sentences of ground truth
2. **Diagnosis** — 1–2 sentences naming the real constraint
3. **Choice (where to play)** — 1 sentence
4. **Mechanism (how to win)** — 1 sentence
5. **Coherent actions** — 3–5 specific moves
6. **Refusals** — 3–5 explicit NOTs
7. **Crystallization** — one bus-side sentence
8. **Disconfirmation test** — the leading indicator that would force a rethink

Do not start with actions. Do not start with the crystallization. Do not
skip the refusals — they are the single highest-signal section.

While writing the **Diagnosis**, run the decision lenses: invert it ("what would
make this brand fail?"), check for vanity metrics (is the named problem a real
business constraint or a self-referential number?), and diagnose against the
*status quo workaround*, not the named competitor. For **Refusals + the highest-
leverage action**, run focus-as-subtraction and leverage obsession.

### Step 5: Grade (always)

Load `references/grading-rubric.md` for the full rubric. Grade each
dimension 0–10 with one-line reasoning. Be honest. Generous grades
defeat the purpose.

- Diagnosis sharpness
- Choice clarity
- Mechanism defensibility
- Action coherence
- Refusal honesty
- Crystallization sharpness
- Falsifiability

Total /70. Letter grade: A+ (64–70), A (56–63), B (48–55), C (40–47),
D (<40). Anything below B+ comes with the top 3 specific improvements.

### Step 6: Output

Save to `${WORK_HOME}/strategy-docs/[brand-slug]-[YYYY-MM-DD].md`
using the structure in `references/template.md`. Create the
`${WORK_HOME}/strategy-docs/` directory if it doesn't exist. Then present the
file to the user and give them the headline (grade + crystallization sentence)
in chat, plus a quick summary of the top 1–2 things to push on.

---

## Voice and posture

Direct, not sycophantic. Specific, not abstract. Outcome-framed, not
adjective-framed. No em dashes (use ellipses or new sentences). No
emojis. Senior-operator register, not McKinsey-consultant register.

When grading, be candid. If the strategy is a C, say so and explain why.
The user wants the honest read, not the encouraging one. Generous grading
is a failure mode of this skill.

Avoid these specific tells of bad strategy in your own output:

- "Synergistic", "customer-centric", "best-in-class", "world-class",
  "innovative", "purpose-driven"
- Goal-as-strategy ("become the #1 player")
- Listing more than 5 actions (that's a dog's dinner, not a strategy)
- Vague refusals ("we will be focused" — focused on what, against what?)
- Crystallizations longer than 25 words

---

## Anti-patterns to avoid

- **Skipping diagnosis to jump to actions.** This is the single most common
  failure. Diagnosis first, always.
- **Asking 20 questions before researching.** Research first. Ask only the
  questions whose answers you couldn't find.
- **Producing a strategy that could apply to any company in the space.**
  If the strategy isn't specific to *this* brand's situation, it's not a
  strategy.
- **Refusing to grade honestly.** A generous C+ disguised as a B is worse
  than no grade at all.
- **Confusing "comprehensive" with "good".** A two-page strategy with
  twelve initiatives is worse than a half-page strategy with three.

---

## Reference files (load as needed)

- `references/template.md` — full template with section-by-section tests
- `references/grading-rubric.md` — 7-dimension rubric with scoring guidance
- `references/rumelt-deep.md` — Rumelt's kernel, the four hallmarks of bad
  strategy, sources of strategic power
- `references/decision-lenses.md` — 11 senior-operator decision instincts +
  ambition posture (EXPAND/HOLD/REDUCE). Sharpens diagnosis + gap questions.
- `references/examples.md` — worked examples of good and bad strategy
  across marketing, tech, and consumer (Walmart, JCPenney, Pepsi,
  Quibi, Apple, Bud Light) for pattern recognition

Read the template every time. Read the others when relevant.

---

## The single sentence to hold

**Strategy is coherent action backed by an argument. If you can't
articulate the argument, you don't have a strategy. You have a hope.**

— Richard Rumelt

That's the test: his whole kernel compressed to one line. Apply it to every
output of this skill.

---

**Setup check:** `bash doctor.sh` — zero dependencies (per `dependencies.yml`), no `.onboarded` gate needed; it always passes.
