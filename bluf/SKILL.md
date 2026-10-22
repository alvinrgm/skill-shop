---
name: bluf
description: >-
  Package anything (a report, analysis, thread, meeting notes, research dump, status update,
  long AI output) into a Barbara Minto pyramid: bottom line up front, plain ELI5 words,
  caveman density, evidence one layer down. Use whenever the user says "minto", "bluf",
  "eli5", "summarize this", "tl;dr", "package this up", "make this readable", "write the
  exec summary", "turn this into a slack message / email for <person>", or when a long
  output is about to be handed to someone who did not ask for the detail. If the result
  is going to another person, run the `fact-check` skill on it BEFORE sending (if it is
  installed): a tidy summary of half-true claims is worse than a messy one, because it
  reads as checked.
---

# BLUF

Turn a pile of content into something a busy reader acts on in 30 seconds and can drill
into if they want. Three standards stacked:

- **Minto pyramid** sets the *structure*: the answer first, then the 2-4 reasons that
  support it, then evidence under each reason. Never the story in the order it happened.
- **ELI5** sets the *vocabulary*: words a smart outsider knows. Every term of art is
  explained the first time (what it is, why it matters), or replaced.
- **Caveman** sets the *density*: cut filler, hedges, restated context and transitions.
  Short words. Tightness comes from cutting ideas that don't serve the answer, never
  from inventing abbreviations or dropping the explanation a reader needs.

No setup. This skill has no dependencies; `bash doctor.sh` always passes.

## Procedure

### 1. Find the reader and the decision
Before writing a word, answer two questions (ask the user only if you truly can't infer):
- **Who reads this?** Teammate, client, exec, the user themselves. This decides vocabulary.
- **What do they need to do or know after reading?** Approve, decide, fix, stop worrying,
  nothing. This decides the bottom line.

If there's no decision and nothing changes for the reader, the honest summary may be one
line ("Nothing to do: X is on track"). Say that; don't pad it into a report.

### 2. Write the bottom line (one or two sentences)
The single thing the reader would want if they read nothing else. It must be:
- **An answer, not a topic.** "Support tickets doubled because the new checkout hides the
  promo field" beats "Support ticket update".
- **Specific.** Numbers, names, dates. "Behind" is a topic; "3 weeks behind" is an answer.
- **Action-bearing when there is an action.** Say what you need from them and by when.

Test: if the reader stopped after this line, would they do the right thing? If not, rewrite.

### 3. Group the support (2-4 points, MECE)
Sort everything else into 2-4 reasons that each *directly* support the bottom line.
Mutually exclusive (no overlap), collectively exhaustive (together they carry the
conclusion). One idea per bullet. If a point doesn't support the bottom line, it goes in
the appendix or gets cut. Order by importance to the reader, not by chronology.

### 4. Put evidence one layer down
Under each point: the number, source, or example that proves it. Link instead of quoting
when you can. A reader who trusts you skips this layer; a reader who doesn't can check.

**Tag every load-bearing claim** so the reader knows what was checked:
- plain statement = verified this session against the source (query run, file read, page opened)
- `(my read)` = inference or judgment
- `(unverified)` = came from someone else and wasn't checked

Never let an inference read like a fact. That is exactly how half-true reports get made.

### 5. Plain-language pass (ELI5)
Go line by line:
- Jargon, acronyms, internal codenames, metric abbreviations: explain on first use or replace.
- Labels coined during the work ("the v3 approach", "the Tuesday issue"): the reader
  wasn't there. Replace with what the thing actually is.
- Abstract nouns → concrete verbs. "Implementation of optimization" → "we changed X".
- Analogies only if they make a hard idea click; never as decoration.

### 6. Density pass (caveman)
Cut: preambles ("I wanted to share"), restating the question, previews ("below I'll cover"),
recaps, closers ("let me know if"), hedges ("it's worth noting", "arguably"), filler
transitions. Keep: every number, every name, every caveat that changes a decision.
Prefer bullets or a table over a paragraph for anything with more than two parts.

### 7. Self-check before handing off
- [ ] Bottom line is in the first two sentences and is an answer.
- [ ] Every support point backs the bottom line; nothing chronological.
- [ ] Every load-bearing claim is verified, tagged `(my read)`, or tagged `(unverified)`.
- [ ] A smart outsider understands every term.
- [ ] Nothing the reader must act on is buried below the fold.
- [ ] Going to another person? Claims are checked (`fact-check` skill, if installed).

## Output shapes

Pick by channel. Same pyramid, different wrapper.

**Slack / chat**
```
<bottom line, with the ask if there is one>
- <reason 1>: <evidence / link>
- <reason 2>: <evidence / link>
- <reason 3>: <evidence / link>
<optional: "Detail: <link to full doc>">
```

**Email**
Subject = the bottom line in under 10 words (not "Update"). Body = the Slack shape, then
a short "Detail" section the reader may skip.

**Doc / report exec summary**
A boxed or bolded "Bottom line" paragraph at the top, then "Why" (the 2-4 points), then
"What we need" (actions, owners, dates), then the full body. The body can be as long as
it needs; the summary must stand alone.

**Spoken / meeting brief**
Bottom line, then "three things", then "the ask". Readable aloud in under a minute.

## Example (invented)

Before (what usually gets sent):
> Hi all, quick recap of what I found digging into support this month. I went through the
> ticket export and talked to a couple of the agents. Volume has been up quite a bit and
> it seems related to a few things, including the checkout redesign that went out, and
> maybe also the holiday rush. Response times have slipped too. Also we hired two
> contractors last week. Happy to discuss!

After:
> **Support tickets doubled since the checkout redesign; restoring the promo-code field
> should cut most of them. Need design's OK by Thursday.**
> - Tickets went from about 400 a week to about 800 in the two weeks since the redesign
>   shipped (Mar 3). [ticket export link]
> - Six in ten new tickets ask "where do I enter my code?" The redesign moved the promo
>   field behind a link. [tagged sample of 100 tickets]
> - Holiday volume is a smaller factor (my read): last year's same weeks rose by about a tenth.
> - The two new contractors start answering next week, so wait times should ease on their own. (unverified)

## Hand-off to fact-check

When the summary is going to anyone other than the user, check its claims before sending.
If the companion `fact-check` skill is installed, run it on the final text. Summaries
compress, and compression is where an inference silently turns into a fact. The
fact-check footer ("Fact-checked: N claims...") goes at the bottom of the message, so the
reader knows what was verified.

## Anti-patterns
- **Chronological storytelling** ("first I looked at X, then Y") → the reader wants the
  answer, not your process.
- **Topic as bottom line** ("Update on Q3") → say what the update *is*.
- **Burying the ask** → if you need something, it's in sentence one.
- **Compression into jargon** → short is useless if the reader can't decode it.
- **Smoothing caveats away** → a caveat that would change the decision stays, near the top.
- **Summarizing unverified claims as facts** → tag them or check them.

---
Free from Rise Growth Marketing (risegm.com/skills). CC BY 4.0, see `LICENSE.txt`.
Feedback or bugs: open an issue at github.com/alvinrgm/skill-shop.
