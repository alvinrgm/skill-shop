#!/usr/bin/env bash
# init_concept.sh — create a new adgen concept folder with the enforced naming + structure.
#
# This is the ONLY sanctioned way to start a concept (Phase 0). It makes the folder law and the
# concept-naming convention PROACTIVE — you can't create a malformed slug or a sibling-folder mess,
# because the script refuses before anything lands on disk.
#
# Usage:
#   init_concept.sh <client-slug> <YYYY-MM-DD>-<angle>-<protagonist>
#
# Examples:
#   init_concept.sh acme 2025-03-14-sink-showdown-suds
#   init_concept.sh acme 2025-02-27-pharma-parody-hank
#
# Naming law: <YYYY-MM-DD>-<angle>-<protagonist>, all lowercase kebab, NO spaces.
#   - date  = the day the concept was first started (origin date, for chronological sort)
#   - angle = creative archetype / hook (origin-story, manifesto, pharma-parody, city-launch)
#   - protagonist = the character / POV (suds, hank, mom)
# At minimum: a valid date + two descriptor tokens.

set -euo pipefail

ADGEN_ROOT="${ADGEN_HOME:-${ADGEN_ROOT:-$HOME/adgen}}"

die() { echo "✗ $*" >&2; exit 1; }

[ $# -eq 2 ] || die "usage: init_concept.sh <client-slug> <YYYY-MM-DD>-<angle>-<protagonist>"

CLIENT="$1"
SLUG="$2"

# --- validate client slug (kebab, no spaces) ---
[[ "$CLIENT" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || die "client slug must be lowercase kebab-case, no spaces: got '$CLIENT' (see adgen/CLIENTS.md)"

# --- validate concept slug: date + >=2 descriptor tokens, all kebab, no spaces ---
if [[ "$SLUG" == *" "* ]]; then
  die "concept slug has a space. Use kebab-case: '${SLUG// /-}'"
fi
if ! [[ "$SLUG" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}(-[a-z0-9]+){2,}$ ]]; then
  die "concept slug must be <YYYY-MM-DD>-<angle>-<protagonist> (date + >=2 descriptor tokens, lowercase kebab).
   got:      '$SLUG'
   good e.g. '2025-03-14-sink-showdown-suds'"
fi
# sanity-check the date portion is a real-ish date
DATE_PART="${SLUG:0:10}"
if ! date -j -f "%Y-%m-%d" "$DATE_PART" >/dev/null 2>&1 \
   && ! date -d "$DATE_PART" >/dev/null 2>&1; then   # BSD/macOS date, then GNU/Linux date
  die "date portion '$DATE_PART' is not a valid YYYY-MM-DD date"
fi

CLIENT_DIR="$ADGEN_ROOT/$CLIENT"

# --- branch on client folder state (Phase 0 logic) ---
if [ ! -d "$CLIENT_DIR" ]; then
  echo "→ client '$CLIENT' is new; bootstrapping brand/ skeleton"
  mkdir -p "$CLIENT_DIR/brand/"{product-images,reference-photos,refs/scraped,characters}
  mkdir -p "$CLIENT_DIR/concepts"
elif [ -d "$CLIENT_DIR/brand" ] && [ -d "$CLIENT_DIR/concepts" ]; then
  : # already migrated, proceed
else
  # exists but flat/legacy
  die "client folder '$CLIENT_DIR' exists but is FLAT/legacy (no brand/ + concepts/).
   Do NOT stack a new concept on top of the mess. Migrate first:
     move brand kit (bible, logo, product photos, scraped PDP) into $CLIENT/brand/
     move the prior flat concept into $CLIENT/concepts/<YYYY-MM-DD>-<angle>-<protagonist>/
   See adgen/CLIENTS.md for which clients are still flat."
fi

CONCEPT_DIR="$CLIENT_DIR/concepts/$SLUG"
[ -d "$CONCEPT_DIR" ] && die "concept already exists: $CONCEPT_DIR"

# --- create the canonical concept skeleton ---
mkdir -p "$CONCEPT_DIR/refs/"{characters,environments,scenes,product}
mkdir -p "$CONCEPT_DIR/"{clips,audio,tmp,final,handoff}

echo "✓ created concept: $CONCEPT_DIR"
echo "  brand-global assets → $CLIENT/brand/"
echo "  everything this concept generates → $CLIENT/concepts/$SLUG/"
echo ""
echo "next: Phase 1 discovery → write $SLUG/brief.md, then STOP for sign-off."
