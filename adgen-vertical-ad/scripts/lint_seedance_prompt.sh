#!/usr/bin/env bash
# lint_seedance_prompt.sh — final tripwire before submitting a seedance video prompt.
#
# THIS IS A SAFETY NET, NOT THE FIX. The real fix is upstream: the seedance prompt is
# CONSTRUCTED clean (physical description only, music suppressed) per prompts/seedance-shot.md.
# This grep exists only because the downside of a slip is asymmetric and unrecoverable:
# a flagged seedance job charges credits, has no cancel, and never auto-refunds. A 1-second
# pre-submit grep against a ~45-credit irreversible loss is cheap insurance. Run it on every
# seedance prompt right before generate_video.
#
# Usage:
#   lint_seedance_prompt.sh prompt.txt
#   echo "<prompt>" | lint_seedance_prompt.sh
#
# Exit 0 = clean. Exit 1 = blocking issue found (do NOT submit until fixed).

set -uo pipefail

PROMPT="$(cat "${1:-/dev/stdin}")"
LC="$(printf '%s' "$PROMPT" | tr '[:upper:]' '[:lower:]')"
ERRORS=0
WARNINGS=0

err()  { echo "  ✗ BLOCK: $*" >&2; ERRORS=$((ERRORS+1)); }
warn() { echo "  ⚠ warn:  $*" >&2; WARNINGS=$((WARNINGS+1)); }

# --- 1. IP-stacking vocab (ip_detected risk). NOTE: these are fine in GEMINI image prompts;
#        they must NOT reach a SEEDANCE prompt. The translation to physical description happens
#        at construction time — this catches anything that leaked through. ---
IP_TERMS="aardman pixar disney dreamworks ghibli laika illumination wallace and gromit toy story yellowstone grapes of wrath of mice and men sam elliott john dutton most interesting man sheriff woody dust bowl roundup"
for t in $IP_TERMS; do :; done
# multi-word + single-word scan
while IFS= read -r term; do
  [ -z "$term" ] && continue
  if printf '%s' "$LC" | grep -qF -- "$term"; then
    err "IP-coded term '$term' in seedance prompt → describe the technique physically instead (see prompts/seedance-shot.md translation table)"
  fi
done <<'EOF'
aardman
pixar
disney
dreamworks
ghibli
laika
illumination
wallace and gromit
toy story
yellowstone
grapes of wrath
of mice and men
sam elliott
john dutton
most interesting man
sheriff woody
dust bowl
roundup
EOF

# --- 2. Music generation (the couplabeers piano slip). Seedance must generate NO music. ---
# Scrub the negation clauses first so "NO MUSICAL SCORE" / "no music" don't self-trip the scan.
LC_SCAN="$(printf '%s' "$LC" \
  | sed -E 's/no music\.? no musical score\.? no instrumental backing\.?//g' \
  | sed -E 's/no (music|musical score|instrumental backing|score|soundtrack|background music)//g')"
while IFS= read -r term; do
  [ -z "$term" ] && continue
  if printf '%s' "$LC_SCAN" | grep -qE -- "$term"; then
    err "music-positive language '$term' → seedance will bake in a score that collides with the FCP suno bed. Remove it; music is added in FCP at Phase 6"
  fi
done <<'EOF'
piano
orchestr
soundtrack
musical score
score swells?
strings? swell
violin
cello
guitar (chord|strum|riff)
synth pad
background music
gentle music
soft music
EOF

# --- 3. The NO MUSIC clause MUST be present, verbatim-ish ---
if ! printf '%s' "$LC" | grep -qE 'no music'; then
  err "missing the mandatory 'NO MUSIC' clause. Every seedance prompt must include: NO MUSIC. NO MUSICAL SCORE. NO INSTRUMENTAL BACKING."
fi

# --- 4. NSFW trigger words (warn — re-check the higgsfield-models.md list) ---
while IFS= read -r term; do
  [ -z "$term" ] && continue
  if printf '%s' "$LC" | grep -qE -- "$term"; then
    warn "possible NSFW trigger '$term' (see reference/higgsfield-models.md trigger list)"
  fi
done <<'EOF'
\bbomb
\bweapon
\bgun\b
\bwar\b
\bkill
\bstab
\bblood
\bwound
\bcut (me )?down
pumped me full
\binjected
\bneedle
\bnaked
\bstripped
glyphosate
EOF

echo "" >&2
if [ "$ERRORS" -gt 0 ]; then
  echo "✗ $ERRORS blocking issue(s), $WARNINGS warning(s). DO NOT submit — fix the prompt first." >&2
  exit 1
fi
echo "✓ seedance prompt clean ($WARNINGS warning(s) to eyeball)." >&2
exit 0
