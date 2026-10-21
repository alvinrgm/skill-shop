#!/usr/bin/env python3
"""verify_portable.py -- structural portability audit gate for portable packages.

Refuses to bless a packaged skill that ships with incomplete install coverage. It is the
the analog of an audit-gate-that-refuses-to-publish: packaging is NOT complete until
this exits 0. Ships INSIDE each package (copied in like doctor.sh) so package updates re-run it.

Five checks (mirrors doctor.sh's PASS/FAIL-per-line style):

  1. COVERAGE PARITY        every third-party import, external binary, env var, and MCP tool the
                            CODE actually uses must appear in dependencies.yml. Used-but-undeclared
                            = a package that cannot run on a clean machine.
  2. MANIFEST<->INSTALLER   every dependencies.yml dep must have (a) a probe in doctor.sh,
     PARITY                 (b) a mention in SETUP.md, (c) coverage by the SKILL.md onboarding gate.
  3. ACQUISITION            every dep that is a user-produced INPUT (a file/asset the recipient must
     COMPLETENESS           make) must carry a real acquisition method (export path / script / URL /
                            walkthrough), not a bare "drop it in X". Catches "how do I get my videos".
  4. SELF-CONTRADICTION     stale "no dependencies / nothing to install / no API key" claims in
                            dependencies.yml or SETUP.md when deps of that type exist. (warn-level.)
  5. INPUTS-HAVE-PRODUCERS  every platform-data INPUT the code CONSUMES (a --performance / --links /
     (end-to-end            --destinations style CLI flag, or a data/ file it reads) must be PRODUCED
      automation parity)    by some shipped puller script, OR declared in dependencies.yml as a
                            manual platform fallback (`manual_fallback: true` with a reason). An
                            input that is consumed but has no producer and no fallback declaration =
                            the OPERATOR-MASKING GAP: during dev the operator pulled it by hand, the
                            workspace filled with the RESULT of automation that never got built, all
                            gates passed, and the end user inherited a manual step that was never
                            meant to exist. Doctrine: connectors are set up ONCE, then the skill does
                            everything; there is no manual path.


Usage:
  python3 verify_portable.py <package-dir> [--json]

Exit code: 0 if the audit passes (no hard violations), 1 otherwise. Warnings do not fail.
Stdlib only.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal YAML-subset parser for the portable-package manifest shape.
# Handles: top-level `key: value`, `path_vars:` / `deps:` lists of dicts
# (`- name: X` starts a new dict; deeper-indented `key: value` are its fields).
# Strips full-line and inline comments while preserving `#` inside quotes.
# ---------------------------------------------------------------------------

def _clean_value(raw):
    raw = raw.strip()
    if not raw:
        return ""
    if raw[0] in "\"'":
        q = raw[0]
        end = raw.find(q, 1)
        if end != -1:
            return raw[1:end]
        return raw[1:]
    # unquoted: strip inline comment (space + #)
    hashpos = raw.find(" #")
    if hashpos != -1:
        raw = raw[:hashpos]
    return raw.strip()


def parse_manifest(text):
    """Return dict with keys: package, path_vars (list of dict), deps (list of dict)."""
    result = {"package": None, "path_vars": [], "deps": []}
    lines = text.splitlines()
    section = None          # None | 'path_vars' | 'deps'
    cur = None              # current list-item dict
    for line in lines:
        stripped = line.rstrip("\n")
        # skip blank and full-line comments
        if not stripped.strip():
            continue
        if stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.strip()

        # top-level section headers / scalars (indent 0)
        if indent == 0:
            if content in ("path_vars:", "deps:"):
                section = content[:-1]
                cur = None
                continue
            m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", content)
            if m:
                section = None
                cur = None
                key, val = m.group(1), _clean_value(m.group(2))
                if key == "package":
                    result["package"] = val
                elif key == "trust_level":
                    result["trust_level"] = val
            continue

        if section not in ("path_vars", "deps"):
            continue

        # list item start
        if content.startswith("- "):
            cur = {}
            result[section].append(cur)
            content = content[2:].strip()
            # `- name: X` -> parse first field inline
            m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", content)
            if m and cur is not None:
                cur[m.group(1)] = _clean_value(m.group(2))
            continue

        # field line inside current item
        if cur is not None:
            m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", content)
            if m:
                cur[m.group(1)] = _clean_value(m.group(2))
    return result


def manifest_blob(manifest):
    """Declared-dependency field values concatenated (lowercased) for substring matching.

    Deliberately EXCLUDES the top-level `package` name: a dependency counts as declared only
    when a dep/path_var entry names it, never because the package label happens to contain the
    token (e.g. a package called `demo-ffmpeg` must not auto-satisfy an ffmpeg coverage check).
    """
    parts = []
    for coll in ("path_vars", "deps"):
        for item in manifest.get(coll, []):
            for v in item.values():
                if v:
                    parts.append(str(v))
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Code scanning -- grep categories reimplemented in Python.
# ---------------------------------------------------------------------------

PY_STDLIB = {
    "abc", "argparse", "ast", "asyncio", "base64", "bisect", "builtins", "calendar",
    "collections", "concurrent", "configparser", "contextlib", "copy", "csv", "ctypes",
    "datetime", "decimal", "difflib", "dis", "email", "enum", "errno", "functools", "gc",
    "fnmatch", "getopt", "getpass", "glob", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json", "logging", "math",
    "mimetypes", "multiprocessing", "operator", "os", "pathlib", "pickle", "platform",
    "pprint", "queue", "random", "re", "secrets", "select", "shlex", "shutil", "signal",
    "smtplib", "socket", "sqlite3", "ssl", "stat", "string", "struct", "subprocess", "sys",
    "tarfile", "tempfile", "textwrap", "threading", "time", "timeit", "traceback", "types",
    "typing", "unicodedata", "unittest", "urllib", "uuid", "warnings", "wave", "weakref",
    "xml", "zipfile", "zlib", "dataclasses", "fractions", "statistics", "webbrowser",
    "__future__", "test",
}

# External binaries worth flagging when invoked but undeclared.
KNOWN_BINARIES = {
    "ffmpeg", "ffprobe", "whisper", "curl", "wget", "osascript", "sips", "convert",
    "magick", "imagemagick", "pandoc", "yt-dlp", "youtube-dl", "node", "npm", "npx",
    "sox", "gifsicle", "tesseract", "rsync", "gs",
}

SYSTEM_ENV = {
    "HOME", "PATH", "PWD", "USER", "SHELL", "TMPDIR", "LANG", "LC_ALL", "TERM",
    "PYTHONPATH", "VIRTUAL_ENV", "NO_COLOR",
}

CODE_EXTS = (".py", ".sh", ".bash", ".zsh")


def collect_code_files(pkg_dir):
    files = []
    for root, dirs, names in os.walk(pkg_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for n in names:
            if n.endswith(CODE_EXTS):
                files.append(os.path.join(root, n))
    return files


def local_module_names(pkg_dir):
    """Top-level module names that resolve to files/dirs inside the package (not third-party)."""
    names = set()
    for root, dirs, files in os.walk(pkg_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for d in dirs:
            names.add(d)
        for f in files:
            if f.endswith(".py"):
                names.add(f[:-3])
    return names


# ---------------------------------------------------------------------------
# Binary-invocation detection -- confined to real invocation contexts, never a
# bare word search. A word like "convert" in a docstring, "node" as a Python
# variable name, or "curl" in a comment/prose string must NOT count as a use.
# ---------------------------------------------------------------------------

_PY_TRIPLE_DQ_RE = re.compile(r'"""[\s\S]*?"""')
_PY_TRIPLE_SQ_RE = re.compile(r"'''[\s\S]*?'''")
_PY_COMMENT_RE = re.compile(r"#[^\n]*")
_SHELL_COMMENT_RE = re.compile(r"#[^\n]*")

_SUBPROCESS_CALL_RE = re.compile(
    r"\b(?:subprocess\.(?:run|call|Popen|check_output|check_call)|os\.system)\s*\("
)
# Matches a single- or double-quoted string, respecting escapes, without crossing
# quote type or newline (adequate for reading a literal argv token out of a call).
_QUOTED_RE = re.compile(r"""(['"])((?:\\.|(?!\1)[^\n])*)\1""")

# A binary token in shell "command position": line start, or right after a
# pipe/AND/semicolon/command-substitution/backtick opener.
_SHELL_CMD_TOKEN_RE = re.compile(
    r"(?:^[ \t]*|\|[ \t]*|&&[ \t]*|;[ \t]*|\$\([ \t]*|`[ \t]*)([A-Za-z0-9_./-]+)",
    re.M,
)


def _strip_py_prose(text):
    """Blank out triple-quoted (doc)strings and '#' comments so invocation-context
    matching below can never fire on prose/docstrings. Newline count is preserved
    (not the content) so this stays a pure line-structure-preserving blank.

    Deliberately leaves single/double-quoted string literals untouched: a real
    `subprocess.run(["ffmpeg", ...])` call needs its literal argv text readable
    by `_python_invoked_binaries` below. Imports are scanned separately against
    the ORIGINAL unstripped text -- imports are code, not strings/comments.
    """
    text = _PY_TRIPLE_DQ_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _PY_TRIPLE_SQ_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _PY_COMMENT_RE.sub("", text)
    return text


def _strip_shell_comments(text):
    """Drop '#'-to-end-of-line comments from shell source (naive: does not
    special-case a '#' embedded inside a same-line quoted string; acceptable
    for a heuristic gate -- it only ever makes detection more conservative)."""
    return _SHELL_COMMENT_RE.sub("", text)


def _matching_paren_end(text, open_idx):
    """Index just past the ')' that balances the '(' found at open_idx."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _binary_from_call(call_text):
    """First quoted token's basename inside a subprocess/os.system call's args.

    Handles both list form (`["ffmpeg", "-i", ...]` -- first element is the
    literal we want) and string form (`"ffmpeg -i ..."` -- first whitespace
    token of the command string is the binary).
    """
    m = _QUOTED_RE.search(call_text)
    if not m:
        return None
    inner = m.group(2).strip()
    if not inner:
        return None
    first_word = inner.split()[0]
    return first_word.rsplit("/", 1)[-1].lower()


def _python_invoked_binaries(text):
    """Binaries invoked via subprocess.run/call/Popen/check_output/check_call(...)
    or os.system(...), with the binary as the literal first argv token. Runs on
    prose-stripped text so a comment or docstring that merely mentions/shows a
    call can never match -- only real, live call sites can."""
    found = set()
    clean = _strip_py_prose(text)
    for m in _SUBPROCESS_CALL_RE.finditer(clean):
        open_idx = m.end() - 1  # index of the call's opening '('
        close_idx = _matching_paren_end(clean, open_idx)
        call_text = clean[open_idx:close_idx]
        base = _binary_from_call(call_text)
        if base in KNOWN_BINARIES:
            found.add(base)
    return found


def _shell_invoked_binaries(text):
    """Binaries in shell command position: line start, or right after
    `|`, `&&`, `;`, `$(`, or a backtick. A binary named merely as an argument
    (e.g. `command -v ffmpeg`) is intentionally NOT command position."""
    found = set()
    clean = _strip_shell_comments(text)
    for m in _SHELL_CMD_TOKEN_RE.finditer(clean):
        base = m.group(1).rsplit("/", 1)[-1].lower()
        if base in KNOWN_BINARIES:
            found.add(base)
    return found


def scan_code(pkg_dir):
    """Return dict of used-in-code artifacts: imports, binaries, env_vars, mcp_tools."""
    imports = set()
    binaries = set()
    env_vars = set()
    mcp_tools = set()
    local_mods = local_module_names(pkg_dir)

    # Group 1 = leading indentation, group 2 = dotted module path. Import scanning
    # runs on the ORIGINAL unstripped text -- imports are code, not strings/comments.
    imp_re = re.compile(r"^([ \t]*)(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", re.M)
    env_re = re.compile(
        r"""os\.environ\.get\(\s*['"]([A-Z][A-Z0-9_]+)['"]"""
        r"""|os\.environ\[\s*['"]([A-Z][A-Z0-9_]+)['"]\s*\]"""
        r"""|os\.getenv\(\s*['"]([A-Z][A-Z0-9_]+)['"]"""
        r"""|getenv\(\s*['"]([A-Z][A-Z0-9_]+)['"]"""
    )
    mcp_re = re.compile(r"mcp__[a-z0-9_]+(?:__[a-z0-9_]+)?")

    for path in collect_code_files(pkg_dir):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        is_py = path.endswith(".py")

        if is_py:
            # Scan imports on prose-stripped source so a docstring/comment line
            # like `from richer evidence than X` is not misread as `from <mod> import`.
            py_clean = _strip_py_prose(text)
            for m in imp_re.finditer(py_clean):
                indent, mod = m.group(1), m.group(2)
                if indent:
                    # Indented import = inside a function/if/try block = lazy,
                    # conditional, or guarded (e.g. `try: import yaml`). Optional
                    # by construction -- do not hard-fail on it. Only unguarded
                    # top-level (column-0) imports count as required deps.
                    continue
                top = mod.split(".")[0]
                if top in PY_STDLIB or top in local_mods:
                    continue
                imports.add(top if "." not in mod else mod)
            binaries |= _python_invoked_binaries(text)
        else:
            binaries |= _shell_invoked_binaries(text)

        # env vars (mostly python, but scan all) -- unchanged, raw text
        for m in env_re.finditer(text):
            var = next(g for g in m.groups() if g)
            if var not in SYSTEM_ENV:
                env_vars.add(var)
        # MCP tools -- unchanged, raw text
        for m in mcp_re.finditer(text):
            mcp_tools.add(m.group(0))

    return {
        "imports": sorted(imports),
        "binaries": sorted(binaries),
        "env_vars": sorted(env_vars),
        "mcp_tools": sorted(mcp_tools),
    }


def import_tokens(mod):
    """Significant lowercase tokens for a module name (for fuzzy manifest matching)."""
    raw = re.split(r"[._]", mod.lower())
    toks = [t for t in raw if len(t) >= 3 and t not in ("the", "lib", "api", "core")]
    return toks or [mod.lower()]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_coverage(manifest, code, blob):
    """Check 1 -- everything used in code is declared in the manifest."""
    violations = []
    has_mcp_dep = any((d.get("type") == "mcp") or ("mcp" in blob)
                      for d in manifest.get("deps", []))

    # imports
    for mod in code["imports"]:
        toks = import_tokens(mod)
        if not any(t in blob for t in toks):
            violations.append((
                "import",
                "`%s` imported in code but not in dependencies.yml" % mod,
                "add a `type: python` dep whose install/verify names `%s`" % mod,
            ))
    # binaries
    for b in code["binaries"]:
        if b not in blob:
            violations.append((
                "binary",
                "external binary `%s` invoked in code but not in dependencies.yml" % b,
                "add a `type: cli` dep for `%s` (install + verify)" % b,
            ))
    # env vars
    declared_pathvars = {pv.get("name", "").upper() for pv in manifest.get("path_vars", [])}
    for var in code["env_vars"]:
        if var.lower() in blob or var in declared_pathvars:
            continue
        violations.append((
            "env-var",
            "env var `%s` read in code but not in dependencies.yml / path_vars" % var,
            "add a `type: env-key` dep with `key: %s` (or a path_var if it's a path)" % var,
        ))
    # mcp tools
    if code["mcp_tools"] and not has_mcp_dep:
        tools = ", ".join(code["mcp_tools"][:4])
        violations.append((
            "mcp",
            "MCP tools referenced in code (%s) but no `type: mcp` dep in dependencies.yml" % tools,
            "add a `type: mcp` dep with get_url + connect + mcp_tool_probe",
        ))
    return violations


def check_installer_parity(manifest, pkg_dir):
    """Check 2 -- every dep is probed in doctor.sh, mentioned in SETUP.md, covered by the gate."""
    violations = []
    doctor = _read(pkg_dir, "doctor.sh")
    setup = _read(pkg_dir, "SETUP.md")
    # multi-skill bundles keep SKILL.md files under skills/<name>/ -- gather them all
    skill_paths = sorted(Path(pkg_dir).rglob("SKILL.md"))
    skill = "\n".join(p.read_text(errors="replace") for p in skill_paths) if skill_paths else None

    doctor_l = (doctor or "").lower()
    setup_l = (setup or "").lower()
    skill_l = (skill or "").lower()

    gate_present = bool(skill) and (
        "onboarding gate" in skill_l or "doctor.sh" in skill_l or ".onboarded" in skill_l
    )
    gate_datadriven = "dependencies.yml" in skill_l

    if doctor is None:
        violations.append(("installer", "doctor.sh is missing from the package",
                           "generate doctor.sh from dependencies.yml (see SETUP.md)"))
    if setup is None:
        violations.append(("installer", "SETUP.md is missing from the package",
                           "generate SETUP.md from dependencies.yml (Phase 4)"))
    if not gate_present:
        violations.append(("installer",
                           "SKILL.md has no onboarding gate (no doctor.sh/.onboarded reference)",
                           "prepend the onboarding gate (see SETUP.md) to SKILL.md"))

    for dep in manifest.get("deps", []):
        # author-only deps are intentionally NOT installed by the recipient
        if dep.get("type") == "author-only":
            continue
        label = dep.get("name") or dep.get("id") or "?"
        tokens = _dep_match_tokens(dep)

        if doctor is not None and not _any_token_in(tokens, doctor_l):
            violations.append((
                "installer",
                "dep '%s' has no probe in doctor.sh" % label,
                "add a check block for '%s' in doctor.sh" % label,
            ))
        if setup is not None and not _any_token_in(tokens, setup_l):
            violations.append((
                "installer",
                "dep '%s' is not mentioned in SETUP.md" % label,
                "add a row/mention for '%s' in SETUP.md (regen from manifest)" % label,
            ))
        # (c) gate coverage: covered if the gate is data-driven (reads dependencies.yml)
        # or the dep is named directly in SKILL.md.
        covered_by_gate = (gate_present and gate_datadriven) or _any_token_in(tokens, skill_l)
        if not covered_by_gate:
            violations.append((
                "installer",
                "dep '%s' not covered by the SKILL.md onboarding gate" % label,
                "make the gate reference dependencies.yml, or name '%s' in SKILL.md" % label,
            ))
    return violations


# What counts as a user-produced INPUT that needs an acquisition method.
INPUT_TYPES = {"file-check", "file", "input", "asset", "user-file", "user-input"}
ACQUISITION_FIELDS = ("connect", "acquire", "get_url", "how", "source", "produce")


def check_acquisition(manifest):
    """Check 3 -- user-produced inputs must document HOW to obtain/produce them."""
    violations = []
    for dep in manifest.get("deps", []):
        label = dep.get("name") or dep.get("id") or "?"
        dtype = (dep.get("type") or "").lower()
        is_input = dtype in INPUT_TYPES or str(dep.get("input", "")).lower() == "true"
        if not is_input:
            continue
        # gather acquisition text
        method_text = ""
        for f in ACQUISITION_FIELDS:
            if dep.get(f):
                method_text += " " + str(dep[f])
        method_text = method_text.strip()
        if not method_text:
            violations.append((
                "acquisition",
                "input dep '%s' has no acquisition method (no connect/get_url/how)" % label,
                "add `connect:` explaining HOW to produce it (export path, script, or URL)",
            ))
            continue
        if _is_trivial_acquisition(method_text):
            violations.append((
                "acquisition",
                "input dep '%s' only says where to put it, not how to get it (\"%s\")"
                % (label, method_text[:60]),
                "expand `connect:` with a real method: an export path, a script, a URL, "
                "or a step-by-step walkthrough",
            ))
    return violations


def _is_trivial_acquisition(text):
    low = text.lower()
    has_method = (
        "http://" in low or "https://" in low
        or "export" in low or "download" in low or "run " in low
        or ".py" in low or ".sh" in low or "script" in low
        or "walkthrough" in low or "step" in low
    )
    if has_method:
        return False
    # bare "drop it in X" / "put it in X" / "place it in X" with no method
    if re.search(r"\b(drop|put|place|copy|move) it (in|into|to)\b", low):
        return True
    # very short and no method keyword
    return len(low) < 40


TRUST_LEVELS = ("internal", "team", "client", "public")


def check_trust_level(manifest):
    """Check 0b -- every package must declare its distribution label.

    `trust_level:` at manifest top level: internal (author-convention paths allowed,
    private internal repos ONLY) | team | client | public. Unlabeled packages are how
    internal-only builds drift into public repos -- the label makes the classification
    explicit so a publish step can check the destination matches.
    """
    tl = manifest.get("trust_level")
    if not tl:
        return [(
            "trust",
            "dependencies.yml has no `trust_level:` -- the package's audience is undeclared",
            "add top-level `trust_level: internal|team|client|public` (Step 0 of SKILL.md)",
        )]
    if tl.lower() not in TRUST_LEVELS:
        return [(
            "trust",
            "trust_level '%s' is not one of %s" % (tl, "/".join(TRUST_LEVELS)),
            "use one of: internal, team, client, public",
        )]
    return []


OAUTH_KEY_MARKERS = ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")


def check_oauth_scaffolding(manifest, pkg_dir):
    """Check 3b -- OAuth-gated deps must ship a self-scaffolding walkthrough.

    Any dep whose keys include an OAuth client credential (CLIENT_ID / CLIENT_SECRET /
    REFRESH_TOKEN) means the recipient must create their OWN cloud project + OAuth client.
    A bare docs URL is not enough: the acquisition text must reference a shipped script
    (.py/.sh) or a package .md walkthrough that actually exists. Without it, recipients end up
    depending on the author's cloud project.
    """
    violations = []
    for dep in manifest.get("deps", []):
        label = dep.get("name") or dep.get("id") or "?"
        key_text = " ".join(str(dep.get(f, "")) for f in ("key", "keys", "where")).upper()
        if not any(m in key_text for m in OAUTH_KEY_MARKERS):
            continue
        method_text = " ".join(str(dep.get(f)) for f in ACQUISITION_FIELDS if dep.get(f))
        low = method_text.lower()
        referenced_local = re.findall(r"[\w./-]+\.(?:py|sh|md)\b", method_text)
        has_real_path = any(
            list(Path(pkg_dir).rglob(Path(ref).name)) for ref in referenced_local
        )
        if not has_real_path:
            violations.append((
                "oauth",
                "OAuth dep '%s' has no self-scaffolding walkthrough -- a docs URL alone "
                "leaves the recipient to improvise (or to ask the author for access to "
                "THEIR cloud project)" % label,
                "ship a walkthrough .md (own project -> consent screen -> own OAuth client "
                "-> token-mint script) plus the mint script, and reference both in `connect:`",
            ))
        elif "own" not in low and "your" not in low:
            violations.append((
                "oauth",
                "OAuth dep '%s' walkthrough never says the credentials are the RECIPIENT'S "
                "OWN -- ambiguity here is how people end up on the author's OAuth client" % label,
                "state it in `connect:`: 'create YOUR OWN cloud project + OAuth client'",
            ))
    return violations


CONTRADICTION_PATTERNS = [
    (r"no dependenc", "claims 'no dependencies'"),
    (r"nothing to install", "claims 'nothing to install'"),
    (r"no api[ _-]?key", "claims 'no API key'"),
    (r"no mcp", "claims 'no MCP'"),
    (r"no bridge", "claims 'no bridge'"),
    (r"no account", "claims 'no account'"),
    (r"zero (setup|dependenc|config)", "claims 'zero setup/dependencies'"),
]


def check_contradiction(manifest, pkg_dir):
    """Check 4 -- stale 'no dependencies' claims when deps exist. Warn-level."""
    warnings = []
    deps = manifest.get("deps", [])
    real_deps = [d for d in deps if (d.get("type") or "") != "author-only"]
    if not real_deps:
        return warnings
    types = {(d.get("type") or "").lower() for d in real_deps}
    has_key = "env-key" in types
    has_mcp = "mcp" in types

    setup = _read(pkg_dir, "SETUP.md") or ""
    haystacks = [("SETUP.md", setup.lower())]
    # also scan raw manifest text
    mtext = _read(pkg_dir, "dependencies.yml") or ""
    haystacks.append(("dependencies.yml", mtext.lower()))

    for fname, hay in haystacks:
        for pat, desc in CONTRADICTION_PATTERNS:
            if re.search(pat, hay):
                # only flag key/mcp claims if that type actually exists
                if "api" in desc and not has_key:
                    continue
                if "mcp" in desc and not has_mcp:
                    continue
                warnings.append((
                    "contradiction",
                    "%s %s but the manifest declares %d real dep(s)"
                    % (fname, desc, len(real_deps)),
                    "remove the stale 'no X' claim; the package DOES have dependencies",
                ))
    return warnings


# ---------------------------------------------------------------------------
# Check 5 -- INPUTS-HAVE-PRODUCERS (end-to-end automation parity)
#
# Guards the OPERATOR-MASKING GAP: during development the operator manually pulls
# a platform-data input (an ad-performance export, a link map, a destinations
# map), the workspace fills with the RESULT of a pull that was never scripted,
# checks 1-4 all pass (the file IS present, its acquisition IS documented), the
# package ships, and the recipient inherits a manual export step that the skill
# was supposed to do for them. Doctrine: the recipient sets up connectors ONCE,
# then the skill pulls everything automatically. A consumed input with no
# producer script and no `manual_fallback: true` declaration is an orphan.
#
# Pragmatics: a "consumed input" is scoped by INPUT_FLAG_VOCAB (the platform-data
# class), so a package with none of these flags produces zero findings -- the
# vocab is the tunable, low-noise surface. Internally-produced handoff files
# (results.json, creative-library.jsonl) never enter the vocab, so they are not
# flagged. Producer detection is OUTPUT-BASED (see scan_automation): a concept is
# "produced" when a shipped script REALLY WRITES a path whose file/dir/glob matches
# the consumed input -- resolved from write-mode opens, .to_csv/.to_json/... writes,
# `--out*` argparse defaults, and (write-anchored) puller basenames. Directory-level
# writes credit directory/glob inputs (a producer that fills creatives/ satisfies a
# `creatives/*` consumer; one that fills data/ satisfies `data/*.csv`). Detection is
# deliberately generous (it errs toward NOT flagging) but honest: a path merely named
# in prose, a docstring, or a doctor.sh status label is never a producer -- only a
# real write is. The only survivors are inputs with genuinely no shipped producer.
# ---------------------------------------------------------------------------

# Flags that denote externally-sourced platform data a user would otherwise pull
# or export by hand. Key = compact concept token; value = human label. Extend
# this set as new platform-data input shapes appear; keep it to clearly-external
# exports so internal pipeline handoffs never match.
INPUT_FLAG_VOCAB = {
    "performance": "ad performance export",
    "links": "ad-link / URL map",
    "destinations": "destination-URL map",
    "adcopy": "ad-copy export",
    "delivery": "delivery breakdown export",
    "attribution": "attribution export",
    "coverage": "account-coverage export",
    "weekly": "weekly performance export",
    "placement": "placement breakdown export",
}

# A script whose basename starts with one of these prefixes is a puller. Its name
# tokens count toward "this input has a producer" ONLY when the script also performs
# a real write operation (see _WRITE_OP_RE): a pull_*.py that writes nothing is not a
# producer. This keeps even the name signal output-anchored, never prose-based.
_PULLER_PREFIX_RE = re.compile(r"^(pull|fetch|export|download|get|sync|scrape|ingest)[_-]", re.I)

_ADDARG_FLAG_RE = re.compile(r"""add_argument\(\s*['"](--[a-z0-9][a-z0-9-]*)['"]""")
_WRITE_OPEN_RE = re.compile(r"""open\(\s*(['"])([^'"\n]+)\1\s*,\s*(['"])[^'"\n]*[wa][^'"\n]*\3""")
_TOCSV_RE = re.compile(r"""to_csv\(\s*(['"])([^'"\n]+)\1""")
_DATA_LITERAL_RE = re.compile(r"""(['"])((?:data|creatives)/[^'"\n]+)\1""")

# --- output-based producer detection ---------------------------------------
# A "produced path" is a path a shipped script REALLY writes (or declares as its
# output location). Producer detection scans, per script:
#   - write-mode opens: open(TARGET, 'w'/'wb'/'a'...)        -> TARGET path
#   - dataframe/plot/pathlib writes: .to_csv / .to_json / .savefig / .write_text
#     / .write_bytes(TARGET)                                 -> TARGET path
#   - argparse output defaults: add_argument('--out*', default=EXPR) -> EXPR path
#   - puller-prefix basename, gated on a real write in the same file
# TARGET/EXPR is resolved through string literals, os.path.join() literal
# components, and single-file variable/const assignment (so `out = os.path.join(
# ROOT, "ad_links.json"); open(out, "w")` credits ad_links.json). A consumed input
# is satisfied when a produced path matches its file, its DIRECTORY, or its glob.
# Doctrine held honest: a path merely NAMED in prose/a docstring/a status label is
# never a producer; only a real write operation is.

# A real output/write operation anywhere in a script marks it as capable of producing.
_WRITE_OP_RE = re.compile(
    r"""open\s*\(\s*[^,()]+,\s*['"][^'"]*[waxWAX+][^'"]*['"]"""
    r"""|\.to_csv\s*\(|\.to_json\s*\(|\.savefig\s*\(|\.write_text\s*\(|\.write_bytes\s*\("""
    r"""|json\.dump\s*\(|csv\.writer\s*\(|\.download\s*\(|urlretrieve\s*\("""
    r"""|shutil\.copy|shutil\.move|os\.replace\s*\(|os\.rename\s*\("""
)
# First argument (the write TARGET) of a write-mode open(...).
_OPEN_WRITE_RE = re.compile(
    r"""open\s*\(\s*([^,()]+?)\s*,\s*['"][^'"]*[waxWAX+][^'"]*['"]"""
)
# TARGET of a .to_csv/.to_json/.savefig/.write_text/.write_bytes(...) write.
_METHOD_WRITE_RE = re.compile(
    r"""\.(?:to_csv|to_json|savefig|write_text|write_bytes)\s*\(\s*([^,()]+?)\s*[,)]"""
)


def _norm(tok):
    """Compact-normalize a token: lowercase, strip everything but a-z0-9."""
    return re.sub(r"[^a-z0-9]", "", str(tok).lower())


def _first_string_literal(s):
    """Content of the first quoted string literal in s, or None."""
    m = _QUOTED_RE.search(s)
    return m.group(2) if m else None


def _split_top_level(s, seps):
    """Split s on any separator in `seps` at bracket-depth 0, honoring quotes.

    `seps` is a set of single chars (e.g. {","}). Returns the list of parts.
    """
    parts, buf, depth, instr = [], [], 0, None
    i = 0
    while i < len(s):
        ch = s[i]
        if instr:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(s):
                buf.append(s[i + 1]); i += 2; continue
            if ch == instr:
                instr = None
            i += 1; continue
        if ch in "\"'":
            instr = ch; buf.append(ch); i += 1; continue
        if ch in "([{":
            depth += 1; buf.append(ch); i += 1; continue
        if ch in ")]}":
            depth -= 1; buf.append(ch); i += 1; continue
        if depth == 0 and ch in seps:
            parts.append("".join(buf)); buf = []; i += 1; continue
        buf.append(ch); i += 1
    parts.append("".join(buf))
    return parts


def _split_top_or(s):
    """Split a Python expression on top-level ` or ` (used for `A or B` defaults)."""
    out, buf, depth, instr = [], [], 0, None
    i = 0
    while i < len(s):
        ch = s[i]
        if instr:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(s):
                buf.append(s[i + 1]); i += 2; continue
            if ch == instr:
                instr = None
            i += 1; continue
        if ch in "\"'":
            instr = ch; buf.append(ch); i += 1; continue
        if ch in "([{":
            depth += 1; buf.append(ch); i += 1; continue
        if ch in ")]}":
            depth -= 1; buf.append(ch); i += 1; continue
        if depth == 0 and s[i:i + 4] == " or ":
            out.append("".join(buf)); buf = []; i += 4; continue
        buf.append(ch); i += 1
    out.append("".join(buf))
    return out


def _resolve_path_expr(expr, varmap, _depth=0):
    """Resolve a path-valued expression to a literal-ish relative path, or None.

    Handles: string literals, `A or B` (prefers a resolvable operand, fallback
    first), os.path.join(...) of literal components (non-literal leads like
    PKG_ROOT/args.x are dropped), and bare NAMEs looked up in varmap. Anything it
    cannot resolve to real literal text returns None -- never a guess.
    """
    if expr is None or _depth > 5:
        return None
    e = expr.strip()
    if not e:
        return None
    ors = _split_top_or(e)
    if len(ors) > 1:
        for p in reversed(ors):
            r = _resolve_path_expr(p, varmap, _depth + 1)
            if r:
                return r
        return None
    if e[0] in "\"'":
        return _first_string_literal(e)
    m = re.match(r"os\.path\.join\s*\(", e)
    if m:
        end = _matching_paren_end(e, m.end() - 1)
        inner = e[m.end():end - 1]
        comps = []
        for arg in _split_top_level(inner, {","}):
            arg = arg.strip()
            if arg[:1] in "\"'":
                lit = _first_string_literal(arg)
                if lit is not None:
                    comps.append(lit)
        if comps:
            return "/".join(comps)
        return None
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", e):
        return varmap.get(e)
    return None


def _build_varmap(text):
    """Map single-line `NAME = <path-expr>` assignments to resolved paths (two
    passes so a const referenced before its definition still resolves)."""
    assigns = []
    for line in text.splitlines():
        m = re.match(r"[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.+?)[ \t]*$", line)
        if not m:
            continue
        name, expr = m.group(1), m.group(2)
        if name in ("if", "elif", "while", "for", "return", "and", "or", "not"):
            continue
        assigns.append((name, expr))
    vm = {}
    for _ in range(2):
        for name, expr in assigns:
            r = _resolve_path_expr(expr, vm)
            if r:
                vm[name] = r
    return vm


def _iter_call_texts(text, name):
    """Yield the inner text (between the parens) of each `name(...)` call."""
    for m in re.finditer(r"\b" + re.escape(name) + r"\s*\(", text):
        open_idx = m.end() - 1
        end = _matching_paren_end(text, open_idx)
        yield text[open_idx + 1:end - 1]


def _first_flag(call_inner):
    m = re.search(r"""(['"])(--[a-z0-9][a-z0-9-]*)\1""", call_inner)
    return m.group(2) if m else None


def _arg_value(call_inner, key):
    """The raw expression assigned to keyword `key` inside a call's arg list."""
    m = re.search(r"\b" + re.escape(key) + r"\s*=\s*", call_inner)
    if not m:
        return None
    rest = call_inner[m.end():]
    depth, instr, buf = 0, None, []
    i = 0
    while i < len(rest):
        ch = rest[i]
        if instr:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(rest):
                buf.append(rest[i + 1]); i += 2; continue
            if ch == instr:
                instr = None
            i += 1; continue
        if ch in "\"'":
            instr = ch; buf.append(ch); i += 1; continue
        if ch in "([{":
            depth += 1; buf.append(ch); i += 1; continue
        if ch in ")]}":
            if depth == 0:
                break
            depth -= 1; buf.append(ch); i += 1; continue
        if ch == "," and depth == 0:
            break
        buf.append(ch); i += 1
    return "".join(buf).strip() or None


def _is_output_flag(nf):
    """A normalized argparse flag name that denotes an OUTPUT location (producer),
    not a consumed input. Kept to the `out`-prefix so input flags like
    `--destinations` are never misread as outputs."""
    return nf.startswith("out")


_FILE_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _register_path(path, produced_dirs, produced_files, tokens):
    """Fold a produced path into the dir set, file set, and token list."""
    if not path:
        return
    path = str(path).strip().strip("/")
    if not path or "*" in path.split("/")[0]:
        return
    comps = [c for c in path.split("/") if c]
    if not comps:
        return
    last = comps[-1]
    if _FILE_EXT_RE.search(last):
        produced_files.add(path.lower())
        for c in comps[:-1]:
            produced_dirs.add(_norm(c))
        tokens.append(_norm(last))
        tokens.append(_norm(path))
    else:
        for c in comps:
            produced_dirs.add(_norm(c))
        tokens.append(_norm(last))


def scan_automation(pkg_dir):
    """Scan scripts for consumed platform-data inputs and OUTPUT-BASED producer signals.

    Returns dict with:
      consumed       list of (concept, label) -- distinct platform-data inputs the code reads.
      data_files     list of (basename, literal) -- data/ or creatives/ files read (not written).
      producer_blob  one lowercased compact string of all producer tokens (produced-path
                     basenames + full paths, `--out*` flag names, write-anchored puller
                     basenames) for substring matching.
      produced_dirs  sorted list of normalized directory names a shipped script writes into.
      produced_files sorted list of produced file paths (lowercased) for glob/exact matching.
    """
    consumed = {}       # concept -> label
    data_files = {}     # normbasename -> literal
    producer_parts = []
    produced_dirs = set()
    produced_files = set()
    write_literals = set()

    files = collect_code_files(pkg_dir)
    for path in files:
        base = os.path.basename(path)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                raw = fh.read()
        except OSError:
            continue
        is_py = path.endswith(".py")
        text = _strip_py_prose(raw) if is_py else _strip_shell_comments(raw)

        file_has_write = bool(_WRITE_OP_RE.search(text))
        varmap = _build_varmap(text) if is_py else {}

        # argparse flags: partition into consumed inputs vs `--out*` producer flags
        for m in _ADDARG_FLAG_RE.finditer(text):
            flag = m.group(1)[2:]           # strip leading --
            nf = _norm(flag)
            if _is_output_flag(nf):
                if file_has_write:
                    producer_parts.append(nf)   # --out / --out-adcopy ... producer output flag
                continue
            for concept, label in INPUT_FLAG_VOCAB.items():
                if concept in nf:
                    consumed.setdefault(concept, label)

        if is_py and file_has_write:
            # producer: DEFAULT value of every `--out*` argparse flag = a declared output path
            for call in _iter_call_texts(text, "add_argument"):
                flag = _first_flag(call)
                if not flag or not _is_output_flag(_norm(flag[2:])):
                    continue
                resolved = _resolve_path_expr(_arg_value(call, "default"), varmap)
                _register_path(resolved, produced_dirs, produced_files, producer_parts)

            # producer: resolved TARGET of every write-mode open(...) and method write
            for m in _OPEN_WRITE_RE.finditer(text):
                resolved = _resolve_path_expr(m.group(1), varmap)
                if resolved:
                    write_literals.add(resolved)
                    _register_path(resolved, produced_dirs, produced_files, producer_parts)
            for m in _METHOD_WRITE_RE.finditer(text):
                resolved = _resolve_path_expr(m.group(1), varmap)
                if resolved:
                    write_literals.add(resolved)
                    _register_path(resolved, produced_dirs, produced_files, producer_parts)

        # producer: write-anchored puller basename (name signal only when it truly writes)
        if _PULLER_PREFIX_RE.match(base) and file_has_write:
            producer_parts.append(_norm(os.path.splitext(base)[0]))

        # producer: literal-string write targets (open('lit','w'), to_csv('lit'))
        for m in _WRITE_OPEN_RE.finditer(text):
            write_literals.add(m.group(2))
            _register_path(m.group(2), produced_dirs, produced_files, producer_parts)
        for m in _TOCSV_RE.finditer(text):
            write_literals.add(m.group(2))
            _register_path(m.group(2), produced_dirs, produced_files, producer_parts)

        # consumed data/ or creatives/ file literals (read side): recorded, cleared
        # later if a producer writes the same basename.
        for m in _DATA_LITERAL_RE.finditer(text):
            lit = m.group(2)
            data_files.setdefault(_norm(os.path.basename(lit)), lit)

    # a data-file literal that is itself a write target is produced-in-place, not a consumed input
    written_bases = {_norm(os.path.basename(w)) for w in write_literals}
    data_files = {k: v for k, v in data_files.items() if k not in written_bases}

    return {
        "consumed": sorted(consumed.items()),
        "data_files": sorted(data_files.items()),
        "producer_blob": " ".join(producer_parts).lower(),
        "produced_dirs": sorted(produced_dirs),
        "produced_files": sorted(produced_files),
    }


def _fallback_blob(manifest):
    """Compact tokens of every dep declared `manual_fallback: true`."""
    parts = []
    for dep in manifest.get("deps", []):
        val = str(dep.get("manual_fallback", "")).strip().lower()
        if val in ("true", "1", "yes"):
            parts.append(_norm(dep.get("id", "")))
            parts.append(_norm(dep.get("key", "")))
            for w in re.split(r"[^A-Za-z0-9]+", str(dep.get("name", ""))):
                parts.append(_norm(w))
    return " ".join(p for p in parts if p)


def check_automation(manifest, pkg_dir):
    """Check 5 -- every consumed platform-data input has a producer or a declared fallback.

    Returns (violations, warnings).
    """
    violations = []
    warnings = []
    io = scan_automation(pkg_dir)
    producer_blob = io["producer_blob"]
    produced_dirs = set(io["produced_dirs"])
    produced_files = set(io["produced_files"])
    fallback_blob = _fallback_blob(manifest)

    def _tok_satisfied(*tokens):
        for t in tokens:
            if t and (t in producer_blob or t in fallback_blob):
                return True
        return False

    def _datafile_satisfied(lit, base):
        """A consumed data/ or creatives/ literal is satisfied when a produced path
        matches its FILE, its DIRECTORY, or its GLOB."""
        # concept token embedded in the filename (e.g. <acct>-destinations.json)
        concept_hit = next((c for c in INPUT_FLAG_VOCAB if c in base), None)
        if _tok_satisfied(base, concept_hit or ""):
            return True
        low = str(lit).lower().strip("/")
        comps = [c for c in low.split("/") if c]
        # directory-level write credit: a producer writes into this literal's dir
        parent = _norm(comps[-2]) if len(comps) >= 2 else ""
        if parent and parent in produced_dirs:
            return True
        # glob / exact credit: a produced file matches the consumed literal (globs and all)
        if any(fnmatch.fnmatch(pf, low) for pf in produced_files):
            return True
        # a produced file living in the same directory as the consumed literal
        want_dir = "/".join(comps[:-1])
        if want_dir and any("/".join(pf.split("/")[:-1]) == want_dir for pf in produced_files):
            return True
        return False

    # flag-driven platform-data inputs
    for concept, label in io["consumed"]:
        if _tok_satisfied(concept):
            continue
        violations.append((
            "automation",
            "input `--%s` (%s) is consumed but has no producer and no declared fallback" % (concept, label),
            "build a puller (a pull_%s.py the skill runs from connectors) or declare it a platform "
            "fallback in dependencies.yml (`manual_fallback: true` with a reason)" % concept,
        ))

    # data/ or creatives/ file literals read but never written by any shipped script
    for base, lit in io["data_files"]:
        if _datafile_satisfied(lit, base):
            continue
        violations.append((
            "automation",
            "data file `%s` is read but no shipped script produces it and it is not declared a fallback" % lit,
            "build a puller that writes `%s`, or declare its source a platform fallback in "
            "dependencies.yml (`manual_fallback: true` with a reason)" % lit,
        ))

    # hygiene: a dep marked manual_fallback should carry a reason
    for dep in manifest.get("deps", []):
        if str(dep.get("manual_fallback", "")).strip().lower() not in ("true", "1", "yes"):
            continue
        label = dep.get("name") or dep.get("id") or "?"
        if not any(dep.get(f) for f in ("reason", "why", "powers", "connect")):
            warnings.append((
                "automation",
                "dep '%s' is manual_fallback: true but states no reason" % label,
                "add a `reason:` explaining WHY this input cannot be pulled automatically",
            ))

    return violations, warnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(pkg_dir, name):
    path = os.path.join(pkg_dir, name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def _dep_match_tokens(dep):
    """Tokens that identify a dep in generated files (id, name words, key, verify head)."""
    toks = []
    if dep.get("id"):
        toks.append(str(dep["id"]).lower())
    if dep.get("key"):
        toks.append(str(dep["key"]).lower())
    if dep.get("name"):
        # significant words from the name
        for w in re.split(r"[^A-Za-z0-9]+", str(dep["name"]).lower()):
            if len(w) >= 3 and w not in ("the", "and", "api", "for"):
                toks.append(w)
    return [t for t in toks if t]


def _any_token_in(tokens, hay):
    return any(t in hay for t in tokens)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

CHECK_TITLES = {
    "coverage": "1. COVERAGE PARITY (code deps vs manifest)",
    "installer": "2. MANIFEST <-> INSTALLER PARITY (doctor.sh / SETUP.md / gate)",
    "acquisition": "3. ACQUISITION COMPLETENESS (how to get user-produced inputs)",
    "contradiction": "4. SELF-CONTRADICTION (stale 'no dependencies' claims)",
    "automation": "5. INPUTS-HAVE-PRODUCERS (consumed platform-data inputs have pullers)",
}


def run_audit(pkg_dir):
    manifest_text = _read(pkg_dir, "dependencies.yml")
    result = {"package_dir": pkg_dir, "checks": {}, "violations": [], "warnings": []}

    if manifest_text is None:
        result["checks"]["manifest"] = "FAIL"
        result["violations"].append({
            "check": "manifest", "detail": "dependencies.yml not found in package",
            "fix": "build the manifest (Phase 3.5) -- it is the source of truth for the installer",
        })
        return result

    manifest = parse_manifest(manifest_text)
    blob = manifest_blob(manifest)
    code = scan_code(pkg_dir)

    trust = check_trust_level(manifest)
    cov = check_coverage(manifest, code, blob)
    inst = check_installer_parity(manifest, pkg_dir)
    acq = check_acquisition(manifest)
    oauth = check_oauth_scaffolding(manifest, pkg_dir)
    auto, auto_warns = check_automation(manifest, pkg_dir)
    warns = check_contradiction(manifest, pkg_dir)

    for key, vlist in (("trust", trust), ("coverage", cov), ("installer", inst),
                       ("acquisition", acq), ("oauth", oauth), ("automation", auto)):
        result["checks"][key] = "FAIL" if vlist else "PASS"
        for cat, detail, fix in vlist:
            result["violations"].append({"check": key, "detail": detail, "fix": fix})

    # automation hygiene warnings share the automation check line
    if auto_warns and result["checks"]["automation"] == "PASS":
        result["checks"]["automation"] = "WARN"
    for cat, detail, fix in auto_warns:
        result["warnings"].append({"check": "automation", "detail": detail, "fix": fix})

    result["checks"]["contradiction"] = "WARN" if warns else "PASS"
    for cat, detail, fix in warns:
        result["warnings"].append({"check": "contradiction", "detail": detail, "fix": fix})

    result["scanned"] = code
    return result


def print_report(result):
    print("")
    print("=== portability audit: %s ===" % result["package_dir"])
    print("")
    order = ["trust", "coverage", "installer", "acquisition", "oauth", "automation", "contradiction"]
    if "manifest" in result["checks"]:
        order = ["manifest"] + order
        CHECK_TITLES["manifest"] = "0. MANIFEST PRESENT (dependencies.yml)"

    for key in order:
        status = result["checks"].get(key)
        if status is None:
            continue
        title = CHECK_TITLES.get(key, key)
        if status == "PASS":
            print("  \033[32mPASS\033[0m  %s" % title)
        elif status == "WARN":
            print("  \033[33mWARN\033[0m  %s" % title)
        else:
            print("  \033[31mFAIL\033[0m  %s" % title)
        for v in result["violations"]:
            if v["check"] == key:
                print("        \033[31mx\033[0m %s" % v["detail"])
                print("          fix: %s" % v["fix"])
        for w in result["warnings"]:
            if w["check"] == key:
                print("        \033[33m!\033[0m %s" % w["detail"])
                print("          fix: %s" % w["fix"])
    print("")
    n = len(result["violations"])
    if n == 0:
        print("\033[32mPORTABILITY AUDIT PASSED\033[0m")
        if result["warnings"]:
            print("(%d warning(s) -- non-blocking, review above.)" % len(result["warnings"]))
    else:
        print("\033[31mPORTABILITY AUDIT FAILED (%d violation%s)\033[0m"
              % (n, "" if n == 1 else "s"))
    print("")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Structural portability audit for a portable package.")
    ap.add_argument("package_dir", help="path to the packaged skill directory")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON output")
    args = ap.parse_args(argv)

    pkg_dir = os.path.abspath(args.package_dir)
    if not os.path.isdir(pkg_dir):
        sys.stderr.write("error: not a directory: %s\n" % pkg_dir)
        return 2

    result = run_audit(pkg_dir)
    passed = len(result["violations"]) == 0

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
