#!/usr/bin/env python3
"""Claude Code PreToolUse hook: no write reaches a public repo until the leak checks pass.

Wired in two places:
  - this repo's .claude/settings.json, so any Claude session working in this checkout
    (local or cloud) is gated;
  - the maintainer's user-level ~/.claude/settings.json (make-portable/hooks/), so a
    session anywhere on their machine is gated too.

What it blocks (exit 2, with the reason on stderr, which Claude sees):
  - `git commit` / `git push` in a checkout whose origin is a public repo, unless
    scripts/check_public.py passes: every package labeled `trust_level: public`, no
    personal paths, emails, secrets or image metadata, and a current leak-audit receipt
    (`.leak-audit/<package>.txt` with `VERDICT: PASS` and the package's current hash).
    When the maintainer's private leak-gate config exists, it also runs make-portable's
    leak_gate.py hard checks (private client denylist, identity) on every package.
  - GitHub MCP file writes (push_files, create_or_update_file, delete_file) to a public
    repo: those skip every check, so they are refused outright. Commit and push instead.
  - GitHub MCP merges into a public repo unless this checkout is clean and sitting on
    the exact head being merged (expectedHeadSha), so the checks above ran on it.

Public repos: PUBLIC_REPOS env (space-separated owner/name), default alvinrgm/skill-shop.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PUBLIC = set(os.environ.get("PUBLIC_REPOS", "alvinrgm/skill-shop").split())
MCP_WRITES = ("push_files", "create_or_update_file", "delete_file")
LEAK_CFG = Path(os.environ.get("LEAK_GATE_CONFIG", os.path.expanduser("~/Claude/secrets/leak-gate.json")))
LEAK_GATE = [Path(os.environ["LEAK_GATE_SCRIPT"])] if os.environ.get("LEAK_GATE_SCRIPT") else [
    Path(__file__).resolve().parent.parent / "scripts" / "leak_gate.py"] + [
    Path(os.path.expanduser(p)) for p in (
        "~/.claude/skills/make-portable/scripts/leak_gate.py",
        "~/Claude/skills/make-portable/scripts/leak_gate.py")]


def block(msg):
    print(f"BLOCKED by publish_guard: {msg}", file=sys.stderr)
    sys.exit(2)


def git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def repo_slug(cwd):
    url = git(cwd, "remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]+([^/]+/[^/.]+?)(\.git)?/?$", url)
    if not m:
        # cloud sessions push through a local proxy: .../git/<owner>/<repo>
        m = re.search(r"/([^/]+/[^/.]+?)(\.git)?/?$", url)
    return m.group(1) if m else ""


def run_checks(root):
    root = Path(root)
    checker = root / "scripts" / "check_public.py"
    if not checker.exists():
        block(f"{root} has no scripts/check_public.py, so nothing can vouch for this push.")
    r = subprocess.run([sys.executable, str(checker), str(root)], capture_output=True, text=True)
    if r.returncode != 0:
        block("public leak checks failed:\n" + (r.stdout + r.stderr)[-3000:])
    gate = next((p for p in LEAK_GATE if p.exists()), None)
    if LEAK_CFG.exists() and gate:
        for pkg in sorted(d for d in root.iterdir() if (d / "dependencies.yml").exists()):
            r = subprocess.run([sys.executable, str(gate), str(pkg), "--hard-only", "--config", str(LEAK_CFG)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                block(f"leak_gate.py hard checks failed on {pkg.name}:\n" + r.stdout[-2500:])


def main():
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        return
    tool = ev.get("tool_name", "")
    ti = ev.get("tool_input", {}) or {}
    cwd = Path(ev.get("cwd") or os.getcwd())

    if tool == "Bash":
        cmd = ti.get("command", "")
        if not re.search(r"\bgit\b[^;&|]*\b(push|commit)\b", cmd):
            return
        m = re.search(r"\bgit\s+-C\s+(\S+)", cmd) or re.search(r"\bcd\s+(\S+)\s*&&", cmd)
        where = Path(os.path.expanduser(m.group(1).strip("'\""))) if m else cwd
        root = git(where, "rev-parse", "--show-toplevel")
        if root and repo_slug(root) in PUBLIC:
            run_checks(root)
        return

    m = re.match(r"mcp__.*github.*__(\w+)$", tool)
    if not m:
        return
    action = m.group(1)
    slug = f"{ti.get('owner', '')}/{ti.get('repo', '')}"
    if slug not in PUBLIC:
        return
    if action in MCP_WRITES:
        block(f"{action} writes straight to public repo {slug} and skips the leak checks. "
              "Commit in a local checkout and push, so the checks run.")
    if action == "merge_pull_request":
        sha = ti.get("expectedHeadSha", "")
        root = git(cwd, "rev-parse", "--show-toplevel")
        if not sha:
            block("merging into a public repo needs expectedHeadSha, so the merged code is the code that was checked.")
        if not root or repo_slug(root) != slug or git(root, "rev-parse", "HEAD") != sha or git(root, "status", "--porcelain"):
            block(f"check out {sha[:7]} cleanly in a local checkout of {slug} and run this from there, "
                  "so the leak checks run on exactly what is being merged.")
        run_checks(root)


if __name__ == "__main__":
    main()
