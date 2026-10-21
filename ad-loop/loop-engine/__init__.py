"""loop-engine — the canonical, client-neutral ad-QA instruments.

This is the ONE place the algorithms live; thresholds were calibrated in a prior run.

Governing rules that travel with this package:

  - QA zones are COMPUTED from the render, never hand-typed. A hand-typed box can
    certify an ad whose only hard defect sits just outside it.
  - A sharpened instrument must re-fail the artifact it was written for. If the fixed
    ruler stops failing that file, the score was fixed, not the ruler.
  - Instruments port with DOCUMENTED SAMPLING CHANGES ONLY. Thresholds never move
    mid-experiment. Every generalisation carries a comment at the line where it happens.
  - An instrument that counts a photographed object's own print as the ad's text will
    fail every product photograph. Report it; do not move the bar.

Import the pieces you need:

    from loop_engine import common, zones, physics, vision, device, claims, glance
"""
