#!/usr/bin/env python3
"""certify_cleanroom.py -- clean-room certifier for a packaged skill (packaging tool).

A clean-room run proves a package works from nothing: fresh-extracted into an empty directory
with only the operator's own keys, it runs its ONE entry command, produces every input it needs,
writes its deliverable, passes its own audit gate, and exits 0. A workspace that already holds an
input file is not evidence the package can make it. This script makes that test repeatable. A
package that cannot be cold-run declares `certify: manual` with a reason, which prints an explicit
WAIVED (never a silent pass).

WHAT IT READS. Two top-level fields in the package's dependencies.yml:

  entry_run: "<the one command that cold-runs the pipeline end to end>"
      Run in the package root, with the operator's secrets installed and the input dirs empty.

  certify:                       # runnable package: the assertions that prove the run worked
    exit_code: 0                 #   required return code of entry_run (default 0)
    min_bytes: 64                #   an artifact smaller than this counts as an empty stub (default 64)
    empty_dirs:                  #   dirs that must hold no real input files before the run
      - data                    #   (default: data, creatives). Placeholders (.gitkeep, dotfiles,
      - creatives               #    0-byte files, README) are allowed.
    artifacts:                   #   globs that must exist and be non-trivial AFTER the run
      - "outputs/*.md"
    audit: "<optional: the package's own audit command>"
                                 #   run through the shell in the package root; must exit 0.

  # Non-cold-runnable package (no entry command):
  certify:
    manual: "reason it cannot be cold-run and how correctness is gated instead"
      -> printed as an explicit WAIVED (exit 0). entry_run is omitted.

MODES.
  Full clean-room (the ship gate):
    certify_cleanroom.py --zip <pkg.zip> --secrets <env-or-config-file> [--timeout SEC] [--keep]
      Fresh-extract the zip to a scratch dir, verify the input dirs are empty, install the
      operator's secrets into config.yml, run entry_run, then assert exit code + artifacts + audit.

  Assert-only against an existing room (no re-run of the expensive pipeline):
    certify_cleanroom.py --room <dir> [--manifest <dependencies.yml>]
      Point at an already-populated package dir. Skips extract + empties-check + entry_run; runs
      ONLY the artifact + audit assertions. Use to validate manifest wiring against a room that was
      already certified, or to re-check a room after a hand edit. --manifest overrides which
      dependencies.yml supplies the certify block (default: <room>/dependencies.yml).

  Dry-run (parse + print the plan, run nothing):
    certify_cleanroom.py (--zip <pkg.zip> | --room <dir> | --manifest <file>) --dry-run
      Parse the manifest, print the resolved entry_run + certify plan, confirm it is well-formed.

The --secrets file is operator-supplied and NEVER bundled. Env-style lines (KEY=value) load into the
run environment; YAML-style lines (key: value) append into the room's config.yml. Secret VALUES are
never printed -- only key names and counts.

Exit codes: 0 = PASS or WAIVED. 1 = a certification FAILURE. 2 = a usage / manifest error.
Stdlib only.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

# ---------------------------------------------------------------------------
# Colour (match verify_portable.py / doctor.sh PASS/FAIL style; degrade on non-tty / NO_COLOR)
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
def _c(code, s):
    return "\033[%sm%s\033[0m" % (code, s) if _USE_COLOR else s
def green(s):  return _c("32", s)
def red(s):    return _c("31", s)
def yellow(s): return _c("33", s)
def dim(s):    return _c("2", s)

PLACEHOLDER_NAMES = {".gitkeep", ".keep", ".gitignore", ".ds_store", "readme", "readme.md"}


# ---------------------------------------------------------------------------
# Minimal YAML-subset parser for the two certify fields (stdlib only; PyYAML is not a dependency,
# mirroring verify_portable.py which hand-rolls its own manifest parse for the same reason).
# ---------------------------------------------------------------------------

def _clean_value(raw):
    raw = raw.strip()
    if not raw:
        return ""
    if raw[0] == '"':
        # Double-quoted scalar: the closing quote is the first UNescaped ". Honor \" and \\
        # escapes so an audit command like  "test -s \"$(ls ...)\""  survives intact instead of
        # being truncated at the first inner quote (a truncated audit is a false-green gate).
        out, i = [], 1
        while i < len(raw):
            ch = raw[i]
            if ch == "\\" and i + 1 < len(raw) and raw[i + 1] in ('"', "\\"):
                out.append(raw[i + 1])
                i += 2
                continue
            if ch == '"':
                break
            out.append(ch)
            i += 1
        return "".join(out)
    if raw[0] == "'":
        end = raw.find("'", 1)
        return raw[1:end] if end != -1 else raw[1:]
    hashpos = raw.find(" #")          # strip an inline comment (space + #), keep '#' in quotes
    if hashpos != -1:
        raw = raw[:hashpos]
    return raw.strip()


_LIST_KEYS = {"artifacts", "empty_dirs"}


def _parse_certify_block(block_lines):
    """Parse the indented body of a `certify:` block mapping into a normalized dict."""
    d = {}
    cur_list = None
    for raw in block_lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        content = raw.strip()
        if content.startswith("- "):
            if cur_list is not None:
                d.setdefault(cur_list, []).append(_clean_value(content[2:]))
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", content)
        if not m:
            continue
        k, v = m.group(1), _clean_value(m.group(2))
        if k in _LIST_KEYS:
            cur_list = k
            d.setdefault(k, [])
        else:
            d[k] = v
            cur_list = None
    return d


def parse_certify_manifest(text):
    """Extract (entry_run, certify) from a dependencies.yml. certify is a normalized dict, a
    ('manual', reason) marker dict {'manual': reason}, or None if the field is absent."""
    lines = text.splitlines()
    entry_run = None
    certify = None
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if len(raw) - len(raw.lstrip()) != 0:           # only dispatch on top-level keys
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", raw.strip())
        if not m:
            continue
        key, rest = m.group(1), m.group(2)
        if key == "entry_run":
            entry_run = _clean_value(rest) or None
        elif key == "certify":
            v = _clean_value(rest)
            if v:                                        # inline scalar, e.g. `certify: manual`
                certify = {"manual": ""} if v.lower() == "manual" else {"_inline": v}
            else:                                        # block mapping follows: consume its body
                block = []
                while i < n:
                    look = lines[i]
                    if not look.strip() or look.lstrip().startswith("#"):
                        block.append(look)
                        i += 1
                        continue
                    if len(look) - len(look.lstrip()) == 0:   # dedent to a new top-level key: stop
                        break
                    block.append(look)
                    i += 1
                certify = _parse_certify_block(block)
    return entry_run, certify


def normalize_certify(certify):
    """Fill defaults + coerce types. Returns (kind, spec) where kind is 'run' | 'manual' | 'bad'."""
    if certify is None:
        return "bad", "no `certify:` block in dependencies.yml"
    if "_inline" in certify:
        return "bad", "unrecognized inline `certify: %s` (use a block, or `certify: manual`)" % certify["_inline"]
    if "manual" in certify:
        return "manual", (certify.get("manual") or "").strip()
    spec = {
        "exit_code": int(certify.get("exit_code") or 0),
        "min_bytes": int(certify.get("min_bytes") or 64),
        "empty_dirs": certify.get("empty_dirs") or ["data", "creatives"],
        "artifacts": certify.get("artifacts") or [],
        "audit": (certify.get("audit") or "").strip() or None,
    }
    return "run", spec


# ---------------------------------------------------------------------------
# Manifest sourcing (from a package dir or from inside a zip)
# ---------------------------------------------------------------------------

def _zip_member_text(zip_path, basename):
    with zipfile.ZipFile(zip_path) as zf:
        cands = [n for n in zf.namelist() if os.path.basename(n) == basename and not n.endswith("/")]
        cands.sort(key=lambda n: n.count("/"))          # shallowest wins
        if not cands:
            return None
        return zf.read(cands[0]).decode("utf-8", "replace")


def load_manifest_text(zip_path=None, room=None, manifest=None):
    if manifest:
        with open(manifest, encoding="utf-8") as fh:
            return fh.read()
    if room:
        p = os.path.join(room, "dependencies.yml")
        if not os.path.isfile(p):
            die(2, "no dependencies.yml in room %s" % room)
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    if zip_path:
        t = _zip_member_text(zip_path, "dependencies.yml")
        if t is None:
            die(2, "no dependencies.yml inside %s" % zip_path)
        return t
    die(2, "no manifest source (pass --zip, --room, or --manifest)")


# ---------------------------------------------------------------------------
# Clean-room mechanics
# ---------------------------------------------------------------------------

def extract_zip(zip_path, dest):
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    # Locate the package root = shallowest dir containing dependencies.yml.
    best = None
    for cur, _dirs, files in os.walk(dest):
        if "dependencies.yml" in files:
            depth = cur[len(dest):].count(os.sep)
            if best is None or depth < best[0]:
                best = (depth, cur)
    return best[1] if best else dest


def _is_placeholder(path):
    name = os.path.basename(path).lower()
    if name in PLACEHOLDER_NAMES or name.startswith("."):
        return True
    try:
        return os.path.getsize(path) == 0
    except OSError:
        return True


def check_empties(room, dirs):
    """Every named input dir must contain no real (non-placeholder) file. Returns (ok, offenders)."""
    offenders = []
    for d in dirs:
        base = os.path.join(room, d)
        if not os.path.isdir(base):
            continue
        for cur, _sub, files in os.walk(base):
            for f in files:
                fp = os.path.join(cur, f)
                if not _is_placeholder(fp):
                    offenders.append(os.path.relpath(fp, room))
    return (len(offenders) == 0), offenders


def install_secrets(secrets_path, room):
    """Env-style KEY=value lines -> run env; YAML-style key: value lines -> appended to config.yml.
    Returns (env_dict, key_names). Never returns or prints values."""
    env, names, yaml_lines = {}, [], []
    with open(secrets_path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if re.match(r"^(export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=", s):
                s2 = re.sub(r"^export\s+", "", s)
                k, _, v = s2.partition("=")
                env[k.strip()] = _clean_value(v)
                names.append(k.strip())
            else:
                m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", s)
                if m:
                    yaml_lines.append(s)
                    names.append(m.group(1))
    if yaml_lines:
        with open(os.path.join(room, "config.yml"), "a", encoding="utf-8") as fh:
            fh.write("\n# installed by certify_cleanroom.py (operator secrets, not bundled)\n")
            fh.write("\n".join(yaml_lines) + "\n")
    return env, names


def run_entry(cmd, room, secret_env, timeout):
    """Run entry_run in the room with progress inheriting to the console. Returns (rc, note)."""
    env = dict(os.environ)
    env.update(secret_env)
    try:
        r = subprocess.run(cmd, shell=True, cwd=room, env=env, timeout=timeout)
        return r.returncode, ""
    except subprocess.TimeoutExpired:
        return None, "timed out after %ss" % timeout


def assert_artifacts(room, globs, min_bytes):
    """Returns list of (glob, ok, detail)."""
    out = []
    for pat in globs:
        matches = [m for m in glob.glob(os.path.join(room, pat), recursive=True) if os.path.isfile(m)]
        if not matches:
            out.append((pat, False, "no file matched"))
            continue
        sized = [(m, os.path.getsize(m)) for m in matches]
        biggest = max(sized, key=lambda t: t[1])
        if biggest[1] < min_bytes:
            out.append((pat, False, "%d match(es), all < %dB (largest %s = %dB, an empty stub)"
                        % (len(matches), min_bytes, os.path.basename(biggest[0]), biggest[1])))
        else:
            out.append((pat, True, "%d match(es), largest %s = %sB"
                        % (len(matches), os.path.basename(biggest[0]), _human(biggest[1]))))
    return out


def _human(n):
    for unit in ("", "K", "M", "G"):
        if n < 1024:
            return "%d%s" % (n, unit) if unit == "" else "%.1f%s" % (n, unit)
        n /= 1024.0
    return "%.1fT" % n


def run_audit(cmd, room, timeout=1200):
    try:
        r = subprocess.run(cmd, shell=True, cwd=room, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "audit timed out after %ss" % timeout
    if r.returncode == 0:
        return True, "audit exited 0"
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:])
    return False, "audit exited %d\n%s" % (r.returncode, _indent(tail))


def _indent(s, pad="        "):
    return "\n".join(pad + ln for ln in s.splitlines())


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def line_pass(title, detail=""):
    print("  %s  %s%s" % (green("PASS"), title, "  " + dim(detail) if detail else ""))

def line_fail(title, detail=""):
    print("  %s  %s" % (red("FAIL"), title))
    if detail:
        for ln in detail.splitlines():
            print("        " + ln)

def die(code, msg):
    print(red("ERROR") + "  " + msg, file=sys.stderr)
    sys.exit(code)


def banner(kind, n_fail=0):
    print()
    if kind == "pass":
        print(green("CLEAN-ROOM CERTIFICATION PASSED") + "  -- packaging may proceed")
    elif kind == "waived":
        print(yellow("CLEAN-ROOM CERTIFICATION WAIVED") + "  -- declared non-cold-runnable (not a pass)")
    else:
        print(red("CLEAN-ROOM CERTIFICATION FAILED") + "  -- %d failure%s; packaging is NOT complete"
              % (n_fail, "" if n_fail == 1 else "s"))


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def do_dry_run(entry_run, certify):
    kind, spec = normalize_certify(certify)
    print(dim("== clean-room certification plan (dry-run, nothing executed) =="))
    if kind == "bad":
        line_fail("manifest", spec)
        banner("fail", 1)
        sys.exit(1)
    if kind == "manual":
        reason = spec or "(no reason declared -- add one)"
        print("  declared: %s" % yellow("WAIVED (certify: manual)"))
        print("  reason:   %s" % reason)
        if not spec:
            line_fail("waiver reason", "certify: manual must carry a reason")
            banner("fail", 1)
            sys.exit(1)
        banner("waived")
        sys.exit(0)
    problems = 0
    if not entry_run:
        line_fail("entry_run", "certify declares assertions but no entry_run command is set")
        problems += 1
    else:
        print("  entry_run:   %s" % entry_run)
    print("  exit_code:   %d" % spec["exit_code"])
    print("  empty_dirs:  %s" % ", ".join(spec["empty_dirs"]))
    print("  artifacts:   %s" % (", ".join(spec["artifacts"]) or red("(none declared)")))
    if not spec["artifacts"]:
        problems += 1
    print("  audit:       %s" % (spec["audit"] or dim("(none)")))
    print("  min_bytes:   %d" % spec["min_bytes"])
    if problems:
        banner("fail", problems)
        sys.exit(1)
    print("\n" + green("manifest is well-formed") + " -- run without --dry-run to certify.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Assertion phase (shared by full clean-room + --room assert-only)
# ---------------------------------------------------------------------------

def run_assertions(room, spec, entry_rc=None):
    fails = 0
    # exit code (full mode only; None in assert-only)
    if entry_rc is not None:
        if entry_rc == spec["exit_code"]:
            line_pass("entry_run exit code", "exited %d as required" % entry_rc)
        else:
            line_fail("entry_run exit code", "exited %s, required %d" % (entry_rc, spec["exit_code"]))
            fails += 1
    # artifacts
    if not spec["artifacts"]:
        line_fail("artifacts", "certify declares no artifact globs to assert")
        fails += 1
    for pat, ok, detail in assert_artifacts(room, spec["artifacts"], spec["min_bytes"]):
        (line_pass if ok else line_fail)("artifact  %s" % pat, detail)
        if not ok:
            fails += 1
    # audit
    if spec["audit"]:
        ok, detail = run_audit(spec["audit"], room)
        (line_pass if ok else line_fail)("audit gate", detail)
        if not ok:
            fails += 1
    else:
        print("  %s  audit gate  %s" % (yellow("----"), dim("(no audit command declared)")))
    return fails


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Clean-room certifier for a packaged skill (runs its entry command from an empty room).")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--zip", dest="zip_path", help="packaged .zip to fresh-extract and certify")
    src.add_argument("--room", help="an already-populated package dir (assert-only, no re-run)")
    ap.add_argument("--secrets", help="operator env-file or config snippet (installed into config.yml; "
                                      "never bundled, values never printed)")
    ap.add_argument("--manifest", help="override which dependencies.yml supplies the certify block")
    ap.add_argument("--timeout", type=int, default=1800, help="entry_run timeout in seconds (default 1800)")
    ap.add_argument("--dry-run", action="store_true", help="parse + print the plan, run nothing")
    ap.add_argument("--keep", action="store_true", help="keep the scratch extract dir after a full run")
    ap.add_argument("--scratch", help="dir to extract into (default: a fresh temp dir)")
    args = ap.parse_args(argv)

    if not (args.zip_path or args.room or args.manifest):
        die(2, "pass --zip <pkg.zip> (full clean-room), --room <dir> (assert-only), or --manifest (dry-run)")

    manifest_text = load_manifest_text(zip_path=args.zip_path, room=args.room, manifest=args.manifest)
    entry_run, certify = parse_certify_manifest(manifest_text)

    if args.dry_run:
        do_dry_run(entry_run, certify)
        return

    kind, spec = normalize_certify(certify)
    if kind == "bad":
        print(dim("== clean-room certification =="))
        line_fail("manifest", spec + "  -> add entry_run + certify, or `certify: manual` with a reason")
        banner("fail", 1)
        sys.exit(1)
    if kind == "manual":
        print(dim("== clean-room certification =="))
        reason = spec or "(no reason declared)"
        print("  %s  %s" % (yellow("WAIVED"), "certify: manual"))
        print("        reason: %s" % reason)
        if not spec:
            line_fail("waiver reason", "certify: manual must carry a reason")
            banner("fail", 1)
            sys.exit(1)
        banner("waived")
        sys.exit(0)

    # ---- assert-only against an existing room -----------------------------
    if args.room:
        room = os.path.abspath(args.room)
        if not os.path.isdir(room):
            die(2, "room not found: %s" % room)
        print(dim("== clean-room certification (assert-only against %s) ==" % room))
        print("  %s  entry_run + empties skipped (room is already populated)" % dim("note"))
        fails = run_assertions(room, spec, entry_rc=None)
        banner("pass" if fails == 0 else "fail", fails)
        sys.exit(0 if fails == 0 else 1)

    # ---- full clean-room from a zip ---------------------------------------
    if not args.zip_path:
        die(2, "full clean-room needs --zip")
    if not os.path.isfile(args.zip_path):
        die(2, "zip not found: %s" % args.zip_path)
    if not entry_run:
        die(2, "certify declares assertions but the manifest has no entry_run command")

    scratch = args.scratch or tempfile.mkdtemp(prefix="cleanroom-")
    os.makedirs(scratch, exist_ok=True)
    room = extract_zip(args.zip_path, scratch)
    print(dim("== clean-room certification =="))
    print("  extracted to: %s" % room)

    passed = False
    try:
        # empties gate (pre-run)
        ok, offenders = check_empties(room, spec["empty_dirs"])
        if ok:
            line_pass("empty input dirs", "%s hold no real files (placeholders ok)" % ", ".join(spec["empty_dirs"]))
        else:
            line_fail("empty input dirs", "bundled input files present (packaging should ship these EMPTY):\n"
                      + _indent("\n".join(offenders[:12])))

        # secrets
        secret_env = {}
        if args.secrets:
            if not os.path.isfile(args.secrets):
                die(2, "secrets file not found: %s" % args.secrets)
            secret_env, names = install_secrets(args.secrets, room)
            print("  %s  installed %d secret key(s): %s  %s"
                  % (green("PASS"), len(names), ", ".join(names) or "(none)", dim("(values never printed)")))
        else:
            print("  %s  no --secrets given; running with the ambient environment only" % yellow("warn"))

        # run the ONE entry command
        print(dim("  -- running entry_run (live output below) --"))
        print("  $ %s" % entry_run)
        rc, note = run_entry(entry_run, room, secret_env, args.timeout)
        print(dim("  -- entry_run finished --") + (("  " + red(note)) if note else ""))

        fails = 0
        if not ok:
            fails += 1
        fails += run_assertions(room, spec, entry_rc=(rc if rc is not None else -1))

        passed = (fails == 0)
        banner("pass" if passed else "fail", fails)
    finally:
        if args.keep or not passed:
            print(dim("  scratch kept at: %s" % room))
        else:
            shutil.rmtree(scratch, ignore_errors=True)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
