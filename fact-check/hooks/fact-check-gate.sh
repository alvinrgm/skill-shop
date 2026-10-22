#!/bin/bash
# fact-check-gate — PreToolUse hook for tools that send a message to other people
# (Slack posts, email sends). Blocks a LONG message (default 500+ chars) when no
# fact-check receipt was written in the last 90 minutes. Short messages pass.
# Why: AI reports reach teammates half-true and they inherit the checking. The
# fact-check skill moves that work back to the author; this hook makes it the default.
#
# Install: copy to ~/.claude/hooks/, then add a PreToolUse entry in settings.json whose
# matcher lists your send tools (see the skill's SETUP.md).
# Tune: FACT_CHECK_MIN_CHARS (500), FACT_CHECK_WINDOW_MIN (90), FACT_CHECK_HOME.
# Bypass one send: put "[no-fact-check]" in the message (then remove it, or leave it:
# the reader sees you skipped the check, which is honest).
INPUT=$(cat)
RESULT=$(FCG_INPUT="$INPUT" python3 - <<'PY'
import json, os, glob, time
try:
    hook = json.loads(os.environ.get("FCG_INPUT", "{}"))
except Exception:
    print("ok"); raise SystemExit
ti = hook.get("tool_input") or {}
fields = ("text", "message", "body", "content", "markdown_text", "htmlBody", "html_body")
text = "\n".join(str(ti[k]) for k in fields if isinstance(ti.get(k), str))
if "[no-fact-check]" in text:
    print("ok"); raise SystemExit
if len(text.strip()) < int(os.environ.get("FACT_CHECK_MIN_CHARS", "500")):
    print("ok"); raise SystemExit
home = os.path.expanduser(os.environ.get("FACT_CHECK_HOME", "~/.claude/fact-check"))
window = 60 * int(os.environ.get("FACT_CHECK_WINDOW_MIN", "90"))
fresh = [p for p in glob.glob(os.path.join(home, "receipts", "*.json"))
         if time.time() - os.path.getmtime(p) < window]
print("ok" if fresh else f"block {len(text.strip())}")
PY
)

case "$RESULT" in
  block*)
    echo "fact-check-gate: this message is ${RESULT#block } characters and no fact-check receipt was written in the last ${FACT_CHECK_WINDOW_MIN:-90} minutes. Run the fact-check skill on the exact text first (extract claims, check each against its source, one adversarial agent, fix or label, then scripts/receipt.py) and add its footer line to the message. If this message makes no checkable claims, add [no-fact-check] to it and resend." >&2
    exit 2 ;;
esac
exit 0
