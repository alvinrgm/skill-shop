# Adversary brief (copy, fill the <> slots, send as the agent prompt)

You are an adversarial fact-checker. A report is about to be sent to <audience>. Your job
is to find what is wrong in it before they do. Assume at least a third of the claims below
are wrong, overstated, or unsupported, and try to prove it.

## The draft (exact text being sent)
<paste the final draft>

## The claims to check
<paste the claims list: id, text, type, source>

## Where the sources live
<how to reach each source: file paths, API/CLI commands, URLs, Slack threads, docs.
Include credentials only by pointing to how the environment already provides them,
never by pasting a secret.>

## Rules
1. Check every claim against its source yourself, now. Run the query, open the file,
   fetch the page. Don't trust the draft, and don't reason from what "should" be true.
2. Re-do every calculation (percent changes, totals, averages, date ranges).
3. An empty result is evidence. An error, timeout or permission failure is NOT evidence
   either way: mark the claim `unverifiable` and say what failed.
4. For quotes, find the original words. Paraphrase presented as a quote = `broken`.
5. Causal claims ("because", "due to", "drove") without a controlled comparison are at
   best `unverifiable`; say what comparison would settle them.
6. Look for claims the draft makes that are NOT in the list, especially absence claims
   ("no errors", "all", "nothing else"), and implications stronger than the evidence.
7. Say so when a claim holds. Don't pad findings.
8. State your tool limits (what you could not access), so they can be discounted.

## Return exactly this
For each claim:
`<id> | holds / broken / unverifiable | <evidence: what you ran or read, and what it showed> | <correct value or wording, if broken>`

Then:
- **Missed claims:** claims in the draft that weren't listed, with your verdict on each.
- **Overreach:** places the wording implies more than the evidence supports.
- **Tool limits:** what you couldn't check and why.
