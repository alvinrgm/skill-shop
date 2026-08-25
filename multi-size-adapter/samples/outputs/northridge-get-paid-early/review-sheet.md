# Review sheet: northridge-get-paid-early

Designer-ready starting points, not finished ads.

**Both images below are named `.NEEDS-LEGAL.` on purpose.** The legal text from the source
creative was deliberately not generated, so these files are missing a required element. The
marker travels with the file, because a review sheet does not: the moment someone drags an
image into Slack or an ad platform, this page stays behind. Paste the legal text back in
during finishing, then rename the file.

Every size also still needs a design pass (brand QA, kerning/typesetting, final touch-up).

This sheet shows what an honest verification looks like: the numbers below are `measure.py`'s
actual output, pasted in, not an impression. Note the 9:16 is flagged WEAK composition — the
tool is not shy about the exemplar, and neither should you be about a real run.

| Size | Strategy | Headline | Body | CTA | Verify (measured) |
|---|---|---|---|---|---|
| 1080x1080 | generate | Get paid up to 2 days early | No fees. No minimum balance. | Get started | copy verbatim OK · brand OK · legal band empty as intended · content 8.7%–64.4% · 10.6% gap above legal band (fine) · 32-level tonal step at 64% is the background-shape edge, not a seam (looked) · file 2048x2048 JPEG, scale down not up |
| 1080x1920 | generate | Get paid up to 2 days early | No fees. No minimum balance. | Get started | copy verbatim OK · brand OK · safe zones PASS (content 18.3%–57.8%, inside 14–79%) · legal band empty · WEAK composition: 17% dead canvas above the legal band — acceptable here, the layout still reads as designed, but a tighter regenerate would fill it better · file 1536x2752 JPEG |

Each size's folder also has its own `copy.md` with the full text.

How to read this: `measure.py` reports the numbers, a person confirms copy and brand by eye,
and any FAIL means regenerate before shipping. WEAK is a look-before-you-accept flag, not a
blocker. Safe zones and the empty legal band are measured, never eyeballed — a top-anchored
logo looks normal to the eye while sitting inside the excluded band.
