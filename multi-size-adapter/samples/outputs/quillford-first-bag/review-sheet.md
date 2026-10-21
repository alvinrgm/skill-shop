# Review sheet: quillford-first-bag

Designer-ready starting points, not finished ads.

_Sample note: Quillford is a fictional brand, and these sample images were hand-drawn to show the output format; a real run generates them with the image model._

**Both images below are named `.NEEDS-LEGAL.` on purpose.** The legal text from the source
creative was deliberately not generated, so these files are missing a required element. The
marker travels with the file, because a review sheet does not: the moment someone drags an
image into Slack or an ad platform, this page stays behind. Paste the legal text back in
during finishing, then rename the file.

Every size also still needs a design pass (brand QA, kerning/typesetting, final touch-up).

This sheet shows what an honest verification looks like: the numbers below are `measure.py`'s
actual output, pasted in, not an impression. Both sizes pass; the "CHECK for a seam" step each
one reports was looked at, not waved through, and it is the edge of the CTA button, not a
seam. (Quillford Coffee is a fictional brand made up for this sample.)

| Size | Strategy | Headline | Body | CTA | Verify (measured) |
|---|---|---|---|---|---|
| 1080x1080 | generate | Your first bag is on us | Fresh-roasted. Shipped the same week. | Claim your bag | copy verbatim OK · brand OK · legal band empty as intended · content 10.9%–66.2% · 8.8% gap above legal band (fine) · 39-level tonal step at 56% is the CTA button edge, not a seam (looked) · file 2048x2048 JPEG, scale down not up |
| 1080x1920 | generate | Your first bag is on us | Fresh-roasted. Shipped the same week. | Claim your bag | copy verbatim OK · brand OK · safe zones PASS (content 22.1%–64.9%, inside 15–75%) · legal band empty · 10.1% gap above legal band (fine) · 40-level tonal step at 59% is the CTA button edge, not a seam (looked) · file 1536x2752 JPEG |

Each size's folder also has its own `copy.md` with the full text.

How to read this: `measure.py` reports the numbers, a person confirms copy and brand by eye,
and any FAIL means regenerate before shipping. WEAK is a look-before-you-accept flag, not a
blocker. Safe zones and the empty legal band are measured, never eyeballed — a top-anchored
logo looks normal to the eye while sitting inside the excluded band.
