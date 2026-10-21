#!/usr/bin/env bash
# Smoke test against your live Worker (or a local `npm run dev` on http://localhost:8788). Proves the deployment is up
# and the OAuth gate is closed to anonymous callers. It does not sign in; the
# signed-in check is the `ping` tool from Claude (SETUP.md, step 8).
#
# Usage: bash scripts/smoke-test.sh [https://account-connectors.<your-subdomain>.workers.dev]
# Defaults to WORKER_BASE from .env.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Load .env without executing it (values may contain JSON, spaces or quotes).
load_env() {
  [ -f "$1" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|\#*) continue ;; esac
    name="${line%%=*}"; value="${line#*=}"
    [[ "$name" =~ ^[A-Z0-9_]+$ ]] || continue
    case "$value" in \"*\") value="${value:1:${#value}-2}" ;; \'*\') value="${value:1:${#value}-2}" ;; esac
    [ -n "${!name:-}" ] || export "$name=$value"
  done < "$1"
}
load_env "${ACCOUNT_CONNECTORS_ENV:-$ROOT/.env}"
BASE="${1:-${WORKER_BASE:-}}"
BASE="${BASE%/}"
if [ -z "$BASE" ]; then
  echo "Pass your Worker URL, or set WORKER_BASE in .env" >&2
  exit 2
fi
FAIL=0
check() { if [ "$2" = "$3" ]; then echo "OK   $1 ($2)"; else echo "FAIL $1 (got $2, want $3)"; FAIL=1; fi; }

code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/")
check "landing page /" "$code" 200

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}')
check "anonymous /mcp is refused" "$code" 401

meta=$(curl -s "$BASE/.well-known/oauth-authorization-server")
if printf '%s' "$meta" | grep -q '"authorization_endpoint"'; then echo "OK   OAuth discovery metadata"; else echo "FAIL OAuth discovery metadata missing"; FAIL=1; fi

code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/authorize?response_type=code&client_id=smoke-test-unknown-client&redirect_uri=https%3A%2F%2Fexample.invalid%2Fcb")
check "unknown OAuth client is a 400, not a 500" "$code" 400

exit $FAIL
