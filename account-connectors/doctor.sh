#!/usr/bin/env bash
# doctor.sh: setup health check for account-connectors. Follows dependencies.yml.
# Run anytime:  bash doctor.sh          (full check, uses the network)
#               bash doctor.sh --quick  (local checks only)
# Exits non-zero if a REQUIRED dependency is missing.
# Windows: powershell -ExecutionPolicy Bypass -File doctor.ps1

cd "$(dirname "$0")" || exit 1
ENV_FILE="${ACCOUNT_CONNECTORS_ENV:-./.env}"
QUICK=0; [ "${1:-}" = "--quick" ] && QUICK=1
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
load_env "$ENV_FILE"

FAIL=0
ok()   { printf '  OK    %-30s %s\n' "$1" "$2"; }
bad()  { printf '  MISS  %-30s %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
warn() { printf '  WARN  %-30s %s\n' "$1" "$2"; }
info() { printf '  --    %-30s %s\n' "$1" "$2"; }

echo ""
echo "=== account-connectors: setup health check ==="

echo ""
echo "Tooling:"
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  if [ "$NODE_MAJOR" -ge 20 ] 2>/dev/null; then ok "node" "$(node --version) (npm $(npm --version 2>/dev/null), npx included)"
  else bad "node" "found $(node --version), need 20+ -> https://nodejs.org/en/download"; fi
else
  bad "node" "NOT FOUND -> install Node 20+: https://nodejs.org/en/download  (or: brew install node)"
fi
if [ -d node_modules/wrangler ]; then
  if [ "$QUICK" -eq 1 ]; then ok "npm_deps" "node_modules present"
  elif npx tsc --noEmit >/dev/null 2>&1; then ok "npm_deps" "installed; npx tsc --noEmit passes"
  else bad "npm_deps" "installed but the typecheck fails -> run: npx tsc --noEmit"; fi
else
  bad "npm_deps" "not installed -> run: npm install"
fi
if command -v curl >/dev/null 2>&1; then ok "curl" "found (smoke test)"; else warn "curl" "optional; needed only for scripts/smoke-test.sh -> https://curl.se/download.html"; fi

echo ""
echo "Cloudflare:"
LOGGED_IN=0
if [ "$QUICK" -eq 1 ]; then
  info "cloudflare (wrangler login)" "skipped (--quick); check with: npx wrangler whoami"
elif [ -d node_modules/wrangler ] && npx wrangler whoami 2>/dev/null | grep -qi "logged in"; then
  ok "cloudflare (wrangler login)" "logged in"; LOGGED_IN=1
else
  bad "cloudflare (wrangler login)" "free account: https://dash.cloudflare.com/sign-up  then run: npx wrangler login"
fi
if grep -q REPLACE_WITH_YOUR_KV_NAMESPACE_ID wrangler.jsonc 2>/dev/null; then
  bad "kv_namespace (OAUTH_KV)" "after npx wrangler login, run: npx wrangler kv namespace create OAUTH_KV  then paste the id into wrangler.jsonc"
else
  ok "kv_namespace (OAUTH_KV)" "id set in wrangler.jsonc"
fi

echo ""
echo "Secrets (.env staging -> Cloudflare secrets):"
if [ -f "$ENV_FILE" ]; then ok ".env" "found at $ENV_FILE"; else bad ".env" "run: cp .env.example .env   then fill it in (SETUP.md)"; fi
[ -n "${GOOGLE_CLIENT_ID:-}" ] && ok "GOOGLE_CLIENT_ID" "set" || bad "GOOGLE_CLIENT_ID" "YOUR OWN OAuth client: https://console.cloud.google.com/apis/credentials (SETUP.md step 4)"
[ -n "${GOOGLE_CLIENT_SECRET:-}" ] && ok "GOOGLE_CLIENT_SECRET" "set" || bad "GOOGLE_CLIENT_SECRET" "shown with your OAuth client id (SETUP.md step 4)"
[ -n "${COOKIE_ENCRYPTION_KEY:-}" ] && ok "COOKIE_ENCRYPTION_KEY" "set" || warn "COOKIE_ENCRYPTION_KEY" "blank; bash scripts/push-secrets.sh generates it"
if [ -z "${ALLOWED_EMAILS:-}${ALLOWED_DOMAINS:-}" ]; then
  bad "allowlist (ALLOWED_EMAILS)" "empty = nobody can sign in. Set ALLOWED_EMAILS and/or ALLOWED_DOMAINS (SETUP.md step 5)"
elif [ "${ALLOWED_EMAILS:-}" = "you@example.com" ] && [ -z "${ALLOWED_DOMAINS:-}" ]; then
  bad "allowlist (ALLOWED_EMAILS)" "still the placeholder you@example.com; put your real email"
else
  ok "allowlist (ALLOWED_EMAILS)" "${ALLOWED_EMAILS:-}${ALLOWED_DOMAINS:+ domains: $ALLOWED_DOMAINS}"
fi
case "${WORKER_BASE:-}" in
  ""|*your-subdomain*) warn "WORKER_BASE" "not set yet; printed by your first npx wrangler deploy (needed for Meta writes + Shopify install)";;
  *) ok "WORKER_BASE" "$WORKER_BASE";;
esac
[ -n "${ADMIN_EMAIL:-}" ] && ok "ADMIN_EMAIL" "$ADMIN_EMAIL" || info "ADMIN_EMAIL" "optional; but with the default ACL ({}) vendor tools are admin-only, so with no admin nobody can use them (SETUP.md step 5)"

echo ""
echo "Vendors (all optional; tools appear only for configured vendors):"
[ -n "${META_ACCESS_TOKEN:-}" ] && ok "meta_read (META_ACCESS_TOKEN)" "set" || info "meta_read (META_ACCESS_TOKEN)" "optional -> https://business.facebook.com/settings/system-users"
if [ -n "${META_APP_ID:-}" ] && [ -n "${META_APP_SECRET:-}" ]; then ok "meta_app (META_APP_ID)" "id + secret set"
elif [ -n "${META_APP_ID:-}${META_APP_SECRET:-}" ]; then bad "meta_app (META_APP_ID)" "set BOTH META_APP_ID and META_APP_SECRET"
else info "meta_app (META_APP_ID)" "optional (Meta writes) -> https://developers.facebook.com/apps"; fi
GADS_SET=0
for k in GOOGLE_ADS_DEVELOPER_TOKEN GOOGLE_ADS_CLIENT_ID GOOGLE_ADS_CLIENT_SECRET GOOGLE_ADS_REFRESH_TOKEN; do [ -n "${!k:-}" ] && GADS_SET=$((GADS_SET+1)); done
if [ "$GADS_SET" -eq 4 ]; then ok "gads_dev_token + gads_oauth" "all four Google Ads keys set"
elif [ "$GADS_SET" -eq 0 ]; then info "gads_dev_token + gads_oauth" "optional -> https://ads.google.com/aw/apicenter ; token: node scripts/mint-google-ads-refresh-token.mjs"
else
  [ -n "${GOOGLE_ADS_DEVELOPER_TOKEN:-}" ] || bad "GOOGLE_ADS_DEVELOPER_TOKEN" "missing (API Center: https://ads.google.com/aw/apicenter)"
  [ -n "${GOOGLE_ADS_CLIENT_ID:-}" ] && [ -n "${GOOGLE_ADS_CLIENT_SECRET:-}" ] || bad "gads_oauth client" "missing GOOGLE_ADS_CLIENT_ID/SECRET (Desktop app client, SETUP.md Google Ads)"
  [ -n "${GOOGLE_ADS_REFRESH_TOKEN:-}" ] || bad "GOOGLE_ADS_REFRESH_TOKEN" "run: node scripts/mint-google-ads-refresh-token.mjs --write-env"
fi
if [ -n "${SHOPIFY_CLIENT_ID:-}${SHOPIFY_TOKENS:-}" ]; then
  if [ -n "${SHOPIFY_CLIENT_ID:-}" ] && [ -z "${SHOPIFY_CLIENT_SECRET:-}" ]; then bad "shopify" "SHOPIFY_CLIENT_SECRET missing"; else ok "shopify" "configured"; fi
else info "shopify" "optional -> https://dev.shopify.com"; fi
[ -n "${KLAVIYO_API_KEY:-}" ] && ok "klaviyo (KLAVIYO_API_KEY)" "set" || info "klaviyo (KLAVIYO_API_KEY)" "optional -> https://www.klaviyo.com/settings/account/api-keys"

if [ "$QUICK" -eq 0 ] && command -v node >/dev/null 2>&1 && [ -n "${META_ACCESS_TOKEN:-}${META_APP_ID:-}${GOOGLE_ADS_DEVELOPER_TOKEN:-}${SHOPIFY_TOKENS:-}${SHOPIFY_CLIENT_ID:-}${KLAVIYO_API_KEY:-}" ]; then
  echo ""
  echo "Live vendor probes (same calls the server makes):"
  PROBE_OUT="$(node scripts/check-vendors.mjs 2>&1)"; PROBE_RC=$?
  printf '%s\n' "$PROBE_OUT" | grep -E '^(OK|FAIL|--) ' | sed 's/^/  /'
  [ "$PROBE_RC" -eq 0 ] || FAIL=$((FAIL+1))
fi

if [ "$LOGGED_IN" -eq 1 ] && [ -f "$ENV_FILE" ]; then
  echo ""
  echo "Pushed to Cloudflare:"
  LIST="$(npx wrangler secret list 2>/dev/null || true)"
  if [ -z "$LIST" ]; then
    warn "secrets" "could not list (Worker not deployed yet?) -> npx wrangler deploy, then bash scripts/push-secrets.sh"
  else
    MISSING=""
    while IFS= read -r line; do
      case "$line" in ''|\#*) continue;; esac
      n="${line%%=*}"; v="${line#*=}"
      [[ "$n" =~ ^[A-Z0-9_]+$ ]] || continue
      [[ "$n" == CHECK_* || "$n" == MINT_* ]] && continue
      [ -z "$v" ] && continue
      printf '%s' "$LIST" | grep -q "\"$n\"" || MISSING="$MISSING $n"
    done < "$ENV_FILE"
    if [ -z "$MISSING" ]; then ok "secrets" "every non-empty .env key is a Cloudflare secret"
    else bad "secrets" "not pushed yet:$MISSING -> bash scripts/push-secrets.sh"; fi
  fi
fi

if [ "$QUICK" -eq 0 ] && [ -n "${WORKER_BASE:-}" ] && [[ "${WORKER_BASE:-}" != *your-subdomain* ]] && command -v curl >/dev/null 2>&1; then
  echo ""
  echo "Deployed server:"
  bash scripts/smoke-test.sh "$WORKER_BASE" | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" -eq 0 ] || FAIL=$((FAIL+1))   # the smoke test's status, not sed's
fi

echo ""
echo "MCP connection (Claude verifies this, the shell can't):"
info "mcp_connection" "claude.ai: https://claude.ai/settings/connectors > Add custom connector > ${WORKER_BASE:-<WORKER_BASE>}/mcp"
info "" "Claude Code: claude mcp add --transport http account-connectors ${WORKER_BASE:-<WORKER_BASE>}/mcp  then /mcp to sign in"
info "" "then ask Claude to call the ping tool (mcp__account-connectors__ping)"

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "-> $FAIL required item(s) missing. Fix the MISS lines above, then re-run: bash doctor.sh"
  exit 1
fi
echo "-> All required checks passed. Next: connect the MCP in Claude and call ping."
exit 0
