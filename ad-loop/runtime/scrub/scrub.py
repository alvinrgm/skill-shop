#!/usr/bin/env python3
"""scrub.py: the draft-time AI-isms gate for ad copy.

Commands:
  check <file|-> [--quiet]   Scan text for listed phrases. Exit 1 if any are found.
  add "phrase" [--note ...]  Append a phrase to the list.
  list                       Print the current list.

The list is plain text, one phrase per line ('#' starts a comment). It defaults to
ai-isms.txt next to this script; set AD_LOOP_AI_ISMS to point at your own list (for
example, a per-brand list in <work>/<client>/brand/). Matching is case-insensitive and
treats hyphens and spaces as the same ("load-bearing" matches "load bearing").
Em dashes are always flagged: no em dashes in ad copy.
"""

import argparse
import os
import re
import sys
from pathlib import Path

DEFAULT_LIST = Path(__file__).resolve().parent / "ai-isms.txt"
LIST_PATH = Path(os.environ.get("AD_LOOP_AI_ISMS") or DEFAULT_LIST).expanduser()


def phrase_regex(phrase: str) -> re.Pattern:
    parts = [p for p in re.split(r"[\s\-]+", phrase.strip()) if p]
    body = r"[\s\-]+".join(re.escape(p) for p in parts)
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.IGNORECASE)


def phrases():
    if not LIST_PATH.exists():
        return []
    out = []
    for line in LIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def cmd_check(args):
    if args.target == "-":
        text = sys.stdin.read()
    else:
        target = Path(args.target)
        if not target.is_file():
            print(f"scrub.py: no such file: {target}", file=sys.stderr)
            sys.exit(2)
        text = target.read_text(encoding="utf-8")
    hits, seen = [], set()
    for phrase in phrases():
        for m in phrase_regex(phrase).finditer(text):
            if m.span() in seen:   # two list entries that normalise alike: report once
                continue
            seen.add(m.span())
            hits.append((text[: m.start()].count("\n") + 1, phrase, m.group(0)))
    for m in re.finditer("—", text):
        hits.append((text[: m.start()].count("\n") + 1, "em dash", "—"))
    if hits:
        for line_no, phrase, got in sorted(hits):
            print(f'line {line_no}: AI-ism `{phrase}` (as "{got}")')
        print(f"\n{len(hits)} violation(s). Rewrite before shipping.")
        sys.exit(1)
    if not args.quiet:
        print("clean: no listed phrases found.")


def cmd_add(args):
    existing = {p.lower() for p in phrases()}
    if args.phrase.lower() in existing:
        print(f"ALREADY LISTED: `{args.phrase}`")
        return
    LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LIST_PATH.open("a", encoding="utf-8") as f:
        f.write(args.phrase + (f"  # {args.note}" if args.note else "") + "\n")
    print(f"ADDED: `{args.phrase}` to {LIST_PATH}")


def cmd_list(_args):
    print("\n".join(phrases()) or "(empty list)")


def main():
    p = argparse.ArgumentParser(prog="scrub.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("target")
    c.add_argument("--quiet", action="store_true")
    c.set_defaults(fn=cmd_check)
    a = sub.add_parser("add")
    a.add_argument("phrase")
    a.add_argument("--note", default="")
    a.set_defaults(fn=cmd_add)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
