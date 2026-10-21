#!/usr/bin/env bash
# Push every non-empty key in .env to your Cloudflare Worker as a secret
# (npx wrangler secret put NAME, value piped on stdin, never printed).
# Generates COOKIE_ENCRYPTION_KEY first if it is empty.
#
# Usage (from the package root, after `npx wrangler login`):
#   bash scripts/push-secrets.sh            # push all non-empty keys
#   bash scripts/push-secrets.sh KEY1 KEY2  # push only these keys
#
# Keys starting with CHECK_ or MINT_ are local test helpers and are never pushed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ACCOUNT_CONNECTORS_ENV:-$ROOT/.env}"
cd "$ROOT"

if [ ! -f "$ENV_FILE" ]; then
  echo "No .env found at $ENV_FILE. Run: cp .env.example .env   then fill it in." >&2
  exit 2
fi

# Generate the cookie key if the user left it blank.
if ! grep -qE '^COOKIE_ENCRYPTION_KEY=.+' "$ENV_FILE"; then
  KEY="$(node -e 'process.stdout.write(require("crypto").randomBytes(32).toString("hex"))')"
  if grep -qE '^COOKIE_ENCRYPTION_KEY=' "$ENV_FILE"; then
    tmp="$(mktemp)"; sed "s/^COOKIE_ENCRYPTION_KEY=.*/COOKIE_ENCRYPTION_KEY=$KEY/" "$ENV_FILE" > "$tmp" && mv "$tmp" "$ENV_FILE"
  else
    printf '\nCOOKIE_ENCRYPTION_KEY=%s\n' "$KEY" >> "$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE" 2>/dev/null || true
  echo "Generated COOKIE_ENCRYPTION_KEY in .env"
fi

ONLY=" $* "
pushed=0
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|\#*) continue ;; esac
  name="${line%%=*}"
  value="${line#*=}"
  # strip one layer of matching quotes
  case "$value" in \"*\") value="${value:1:${#value}-2}" ;; \'*\') value="${value:1:${#value}-2}" ;; esac
  [[ "$name" =~ ^[A-Z0-9_]+$ ]] || continue
  [[ "$name" == CHECK_* || "$name" == MINT_* ]] && continue
  [ -z "$value" ] && continue
  if [ "$#" -gt 0 ] && [[ "$ONLY" != *" $name "* ]]; then continue; fi
  echo "-> $name"
  printf '%s' "$value" | npx wrangler secret put "$name" >/dev/null
  pushed=$((pushed+1))
done < "$ENV_FILE"

echo "Pushed $pushed secret(s). Check with: npx wrangler secret list"
