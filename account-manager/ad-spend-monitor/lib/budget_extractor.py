"""Budget sheet extractor.

Hard rule (also in design doc §6, account.md, README):
    Pull ONLY the monthly budget target. Never read 'actual spend',
    '% of budget', 'pacing to finish' from the sheet. Those are manually
    populated and not trustworthy.

Strategy: Google Sheets public gviz CSV export. Requires the sheet to be
shared "Anyone with the link → Viewer". For tighter privacy later, swap to
a service account.

Caching: history/budgets/{slug}-{YYYY-MM}.json. Cache for 7 days. If a fresh
extract fails, fall back to the most recent successful cache (still better
than crashing the daily run).

LLM PATH (TODO): when ANTHROPIC_API_KEY is configured and you have client
sheets with more diverse formats, swap _parse_budget_sheet_format() for an LLM
call that uses extraction_hint to navigate any layout.

Output:
{
    "month": "2026-06",
    "meta_budget": 60000.0,
    "google_budget": 14000.0,
    "combined_budget": 74000.0,
    "confidence": 0.95,
    "source": "public_csv" | "manual" | "stale_cache",
    "notes": "...",
    "extracted_at": "2026-06-01T13:00:00Z",
}
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

CACHE_TTL_DAYS = 7


def extract(
    *,
    slug: str,
    sheet_id: str,
    extraction_hint: str,
    month: date,
    cache_dir: Path,
) -> dict:
    """Get current-month budget for `slug`. Uses cache when fresh, fetches when stale."""
    cache_path = cache_dir / f"{slug}-{month.strftime('%Y-%m')}.json"

    # Cache check
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if not _is_stale(cached) and cached.get("confidence", 0) >= 0.5:
                return cached
        except (json.JSONDecodeError, KeyError):
            pass

    # Fetch
    try:
        csv_rows = _fetch_sheet_csv(sheet_id, sheet_name=_guess_tab_name(month, extraction_hint))
        result = _parse_budget_sheet_format(csv_rows, month)
        result["confidence"] = 0.95
        result["source"] = "public_csv"
        result["sheet_id"] = sheet_id
        result["extracted_at"] = dt.datetime.utcnow().isoformat() + "Z"
    except Exception as exc:  # noqa: BLE001
        # Fallback: stale cache if any
        if cache_path.exists():
            try:
                stale = json.loads(cache_path.read_text())
                stale["source"] = "stale_cache"
                stale["fetch_error"] = str(exc)
                return stale
            except json.JSONDecodeError:
                pass
        return {
            "month": month.strftime("%Y-%m"),
            "confidence": 0.0,
            "source": "none",
            "error": str(exc),
            "extracted_at": dt.datetime.utcnow().isoformat() + "Z",
        }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, indent=2, default=str))
    return result


# ────────────────────────────────────────────────────────────────────────────
# Fetch
# ────────────────────────────────────────────────────────────────────────────

def _fetch_sheet_csv(sheet_id: str, sheet_name: str) -> list[list[str]]:
    """Fetch a sheet tab as CSV via gviz public URL.

    Returns list of rows (each row = list of cell strings).
    Raises if the sheet is not publicly accessible or the tab doesn't exist.
    """
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={requests.utils.quote(sheet_name)}"
    )
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(
            f"Sheet fetch failed ({r.status_code}). Ensure sheet sharing "
            f"is 'Anyone with the link → Viewer'. URL: {url}"
        )
    if "text/html" in r.headers.get("content-type", ""):
        # Google returns HTML when auth-walled
        raise RuntimeError(
            f"Sheet returned HTML (likely auth-walled). Set sharing to "
            f"'Anyone with the link → Viewer' on sheet {sheet_id}."
        )
    return list(csv.reader(io.StringIO(r.text)))


# ────────────────────────────────────────────────────────────────────────────
# Tab name heuristic
# ────────────────────────────────────────────────────────────────────────────

def _guess_tab_name(month: date, hint: str) -> str:
    """Look for a year-mentioning tab name in the hint (e.g. 'Budgets 2026')."""
    year = month.strftime("%Y")
    # Try to find a phrase like 'Budgets 2026' or 'Budget 2026' or 'YYYY' in the hint
    m = re.search(r"[A-Za-z]+\s+%s" % year, hint)
    if m:
        return m.group(0)
    # Fallback: try common patterns
    for candidate in (f"Budgets {year}", f"Budget {year}", year):
        if candidate.lower() in hint.lower():
            return candidate
    return f"Budgets {year}"  # best guess


# ────────────────────────────────────────────────────────────────────────────
# Parser — tuned for a common 'Budgets YYYY' monthly-column layout
# ────────────────────────────────────────────────────────────────────────────

def _parse_budget_sheet_format(rows: list[list[str]], month: date) -> dict:
    """Parse a 'Budgets YYYY' tab with monthly columns.

    Layout assumed (describe yours in each client's budget_extraction_hint):
        Row 0: header — 'Budget' followed by month columns like '8/2024', ..., 'Total'
        Some rows: 'Meta', 'Google', 'Total' (these are the first-pass section)
        Blank row
        Row N: a SECOND header sub-section — repeated 'Total' / 'Facebook' / 'Google'
               where 'Total' is the TRUE authoritative monthly budget.

    Strategy: find ALL rows starting with 'Total'/'Facebook'/'Google' (case-insensitive).
    The authoritative ones are the second occurrence (the one with non-zero values).
    """
    target_month_label = _month_column_label(month)  # e.g. '6/2026'

    # Find header row (contains the month label)
    header_row_idx, month_col_idx = _locate_month_column(rows, target_month_label)
    if header_row_idx is None:
        raise RuntimeError(f"Could not find column for month '{target_month_label}' in any header row")

    # Collect candidate rows by label. HARD STOP at the first "Actual spend"
    # (or similar) header — anything below is reported spend, not budget. The
    # design doc rule: NEVER read actual spend / % of budget / pacing cells
    # from the sheet.
    ACTUALS_BARRIERS = (
        "actual spend",
        "actuals",
        "spent",
        "actual",
        "% of budget",
        "% budget",
        "pacing to finish",
        "pacing",
    )
    label_rows: dict[str, list[list[str]]] = {"total": [], "facebook": [], "meta": [], "google": []}
    in_actuals_section = False
    for row in rows[header_row_idx + 1:]:
        if not row:
            continue
        label = row[0].strip().lower()
        if any(label.startswith(h) for h in ACTUALS_BARRIERS):
            in_actuals_section = True
            continue
        if in_actuals_section:
            continue  # everything past the "Actual spend" header is reported data, not target
        if label in label_rows:
            label_rows[label].append(row)

    def pick_value(label_options: list[str]) -> float | None:
        """Take the LAST non-empty value across given labels (later sections win)."""
        for label in label_options:
            for row in reversed(label_rows[label]):
                if len(row) > month_col_idx:
                    v = _parse_money(row[month_col_idx])
                    if v is not None and v > 0:
                        return v
        return None

    meta_budget = pick_value(["facebook", "meta"])
    google_budget = pick_value(["google"])
    total_from_row = pick_value(["total"])

    # Combined = sum of channel budgets if we have them, else fall back to the Total row
    if meta_budget is not None or google_budget is not None:
        combined = (meta_budget or 0.0) + (google_budget or 0.0)
    else:
        combined = total_from_row or 0.0

    return {
        "month": month.strftime("%Y-%m"),
        "meta_budget": meta_budget,
        "google_budget": google_budget,
        "combined_budget": combined,
        "total_row_budget": total_from_row,
        "notes": (
            f"Pulled from tab via gviz, month column '{target_month_label}'. "
            f"Took last non-zero values from Facebook/Meta + Google + Total rows."
        ),
    }


def _month_column_label(month: date) -> str:
    """Return 'M/YYYY' (e.g. '6/2026') — matches the column header convention."""
    return f"{month.month}/{month.year}"


def _locate_month_column(rows: list[list[str]], target: str) -> tuple[int | None, int | None]:
    """Find the (row_idx, col_idx) where `target` appears as a header cell."""
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if cell.strip() == target:
                return i, j
    return None, None


_MONEY_RE = re.compile(r"[^0-9.\-]")


def _parse_money(s: str) -> float | None:
    """Parse '$74,000.00' or '$60,000' or '60000' → float. Empty/invalid → None."""
    if not s:
        return None
    cleaned = _MONEY_RE.sub("", s)
    if not cleaned or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# ────────────────────────────────────────────────────────────────────────────
# Cache freshness
# ────────────────────────────────────────────────────────────────────────────

def _is_stale(cached: dict) -> bool:
    ts = cached.get("extracted_at")
    if not ts:
        return True
    extracted = dt.datetime.fromisoformat(ts.rstrip("Z"))
    age = dt.datetime.utcnow() - extracted
    return age > dt.timedelta(days=CACHE_TTL_DAYS)


if __name__ == "__main__":
    # Smoke test: pass a public budget sheet ID to extract the current month.
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--sheet", required=True, help="Google Sheet ID (publicly viewable)")
    p.add_argument("--month", default=None, help="YYYY-MM")
    p.add_argument("--slug", default="example-brand")
    args = p.parse_args()

    target_month = (
        dt.date.fromisoformat(args.month + "-01") if args.month else dt.date.today().replace(day=1)
    )
    cache_dir = Path(__file__).resolve().parent.parent / "history" / "budgets"
    out = extract(
        slug=args.slug,
        sheet_id=args.sheet,
        extraction_hint="Budgets 2026 tab",
        month=target_month,
        cache_dir=cache_dir,
    )
    print(json.dumps(out, indent=2, default=str), file=sys.stdout)
