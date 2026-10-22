---
name: prospect-sim
description: >-
  Roleplay the people on the other side of a sales deal with agents (one per decision
  maker, plus a rival bidder) to expose your weak spots before or after a sales call, and
  give you concrete fixes, questions to drill and a follow-up draft. Use for "/prospect-sim",
  "prep me for my call with <company>", "debrief my call with <company>", "roleplay the
  buyer", "what will they push back on", "where did I lose them", "sim this prospect".
---

# prospect-sim

Agents play the people across the table: the buyer who signs, the person who referred
you or guards the door, the technical evaluator, and a rival who wants the deal. Each one
reads what actually happened and tells you, bluntly, where you are weak and what a strong
answer sounds like. Blunt is the point. Comfort doesn't win deals.

Two modes:
- **prep**: before a first or next call. No transcript yet. Personas generate the likely
  questions, objections and what you must research before the call.
- **debrief**: after a call. Personas score you against what you actually said, quoting you.

## FIRST RUN: onboarding gate
If `.onboarded` does NOT exist in this folder, run `bash doctor.sh` first (Windows:
`powershell -ExecutionPolicy Bypass -File doctor.ps1`). Nothing is required beyond Claude
Code. Then, one at a time, offer the optional pieces from `dependencies.yml` and skip any
the user declines:
1. **Work folder** (`PROSPECT_SIM_HOME`, default `~/prospect-sims`): create it, and copy
   `reference/approved-facts-template.md` to `<home>/approved-facts.md`. Ask the user to
   fill in their real proof (results, client types, prices) now or later. Strong answers
   may only use facts from this file or numbers the prospect gave.
2. **Call notes source** (`notes_connector`): if they record calls (Granola, Fireflies,
   Otter, Fathom, Gong, Wispr Flow or similar), point them to the connector directory at
   <https://claude.ai/settings/connectors> or the tool's own MCP docs, and verify by
   checking that its tools are available to you. Without one, they paste the transcript.
3. **CRM / email** (`crm_connector`): optional, same way (HubSpot, Attio, Salesforce,
   Gmail). It adds history: past threads, titles, first contact.
4. **Web access** (`web`): lets agents read the prospect's site and LinkedIn. Usually on.
When done, write `.onboarded` (`date > .onboarded`) and ask: "Which prospect, and is this
prep or a debrief?"

---

**Paths.** `<home>` is `$PROSPECT_SIM_HOME` (default `~/prospect-sims`). Each prospect
gets `<home>/<prospect-slug>/`.

## Step 0. Intake (one message)
Ask only what you can't find yourself:
1. Company, the people on their side (name, role) and who referred you, if anyone.
2. Prep or debrief. For a debrief: where the transcript is (connector, file, or paste).
3. What you offered or plan to offer (scope, price, terms).
4. What a "win" is this week (signed, a second call, a pilot).

## Step 1. Build the dossier
Write `<home>/<prospect-slug>/dossier.md`. Gather, in this order:
- **The call transcript** (debrief): from the notes connector if one is set up (search by
  meeting title or date, then pull the full transcript), else the file or paste the user
  gives. Speaker labels are sometimes swapped by recorders: attribute quotes by content.
- **Email and CRM history**, if connected: threads with the prospect's domain and the
  referrer's domain, titles, first interactions. Older threads with the same referrer
  often show how they make decisions.
- **The prospect's website and LinkedIn** (public pages).
- **Your approved facts**: `<home>/approved-facts.md`. Strong answers may only use these
  or numbers the prospect gave. Never invent proof. If a strong answer needs data you
  don't have, name the data and where to get it.

Dossier sections: company and unit economics (what they sell, price points, margins if
known, growth stage), each person (role, stance, exact quotes, what they asked), what you
said and offered, your approved facts.

Say in one line what you could not reach (a connector not set up, a private profile).

## Step 2. Spawn the agents in parallel
One general-purpose agent per person on their side who matters (economic buyer,
referrer or gatekeeper, technical evaluator), plus one **rival bidder** agent. Launch
them in one message so they run in parallel. Each reads the dossier and the transcript
itself, then writes `sim-<role>.md` in the prospect folder. Persona briefs are in
`reference/persona-briefs.md`.

Each persona returns:
- a private, in-character debrief ("what I'm really thinking after that call");
- their evaluation criteria, ranked, each with a 1-5 score for you, the exact quote
  behind the score, and what a 5 would have sounded like;
- unspoken concerns they would never say out loud;
- the hardest next questions, with the weak answer you are likely to give and a strong one;
- what gets a yes this week, and what kills the deal;
- their next move if you do nothing.

The referrer persona also covers pricing traps and how to turn them into a champion. The
rival researches the realistic alternatives (a cheap freelancer, a specialist agency,
building in-house, doing nothing) and the prospect's industry vocabulary, and returns
competitor pitches, who wins today and why, your domain gaps, and ranked moves for the
next 72 hours.

Style for all agents: plain simple English, no em dashes, short sentences.

## Step 3. Synthesize
Write `<home>/<prospect-slug>/readout.md` (or a doc in the user's docs tool if they
prefer). Lead with the verdict: would you win if they decided today, and why. Then:
1. **Weak spots**, worst first, as a table: what you said | why it hurt | the fix.
2. **Questions to drill**, each with a strong answer built only from approved facts.
3. **Deal structure traps** and a stronger counter. Never volunteer a weaker position;
   any concession is a labeled option with what you get in return.
4. **Next 72 hours** as a dated checklist.
5. **Draft follow-up** for the user to edit and send. Never send anything to the prospect.
6. **Patterns that repeat** from earlier sims: read the other folders under `<home>` and
   `<home>/weak-spots.md`.

Then update `<home>/weak-spots.md`: add or bump each recurring weak spot with the date
and prospect, so the list gets sharper with every run.

## Cadence (suggest it once, then follow the user's lead)
- Prep sim the day before every first sales call.
- Debrief sim within 24 hours after every sales call.
- Monthly roll-up of recurring weak spots across all sims, with one drill per spot.

## Rules
- Never contact the prospect, post anywhere, or send the follow-up. Drafts only.
- Quotes must be the person's real words from the transcript. Paraphrase is labeled.
- No invented proof, case studies or numbers, ever. Missing proof is a weak spot to fix.
- Keep it honest. A sim that flatters you is a failed sim.

---
Free from Rise Growth Marketing (risegm.com/skills). CC BY 4.0, see `LICENSE.txt`.
Feedback or bugs: open an issue at github.com/alvinrgm/skill-shop.
