"""Deck appender — prepend a house-style weekly period block into a LIVE deck.

HARD INVARIANT: insert-at-top only. We never modify or delete an existing
slide. New slides are created at `insert_index` (default 1, under the cover).
The whole period block goes in a SINGLE batchUpdate (atomic-ish); we verify
afterwards and roll back (delete only the slides WE created) on any mismatch.

Payload schema (dict):
{
  "period_label": "6/25",                 # divider headline (date or range)
  "divider_label": "Weekly dashboard",           # divider sub-line
  "dashboard": {"title": "...", "metrics": ["Spend $X", "ROAS 2.1x", ...]},
  "observations": [{"title","observation":[...],"next_steps":[...]}, ...],
  "deep_dives":   [{"title","observation":[...],"next_steps":[...]}, ...],
  "action_items": [{"action","notes","status"}, ...]
}
"""
import time

from . import bridge

EMU_W = 9144000
EMU_H = 5143500
# Screenshots are DEPRECATED (see REPORTING-SPEC.md): dashboard screenshots
# aren't feasible to host/embed, so native tables rendered from the client's locked
# core_data_source carry the SAME data instead. This placeholder is legacy.
PLACEHOLDER_TEXT = "[ native data table from core_data_source — screenshots deprecated ]"

# Body text box geometry — inset from the right so text clears the corner graphic.
# Right edge at 7,757,200 EMU leaves ~1.5" clear of the brand swoosh.
BODY_X = 457200      # 0.5" from left
BODY_Y = 1295400     # ~1.42" from top (under the title)
BODY_W = 7300000     # ~8.0" wide (was full-bleed via the placeholder)
BODY_H = 3550000
BODY_FONT = "Poppins"   # match the deck's brand font (titles use Poppins)
BODY_SIZE = 12


def _oid(run, n):
    return f"am_{run}_{n}"


def _content_slide(reqs, run, ctr, index, title, body_lines, bold_labels=None):
    """Append requests for one TITLE_AND_BODY slide. Returns its slide objectId.

    bold_labels: set of line texts (e.g. {"Observation","Next steps"}) to render
    bold — their label lines stand out as sub-headers above the bullets.
    """
    bold_labels = bold_labels or set()
    sid = _oid(run, next(ctr))
    tid = _oid(run, next(ctr))
    bid = _oid(run, next(ctr))
    # TITLE_ONLY layout (theme title) + a width-controlled custom body text box so
    # bullets wrap before the corner brand graphic instead of running under it.
    reqs.append({"createSlide": {
        "objectId": sid,
        "insertionIndex": index,
        "slideLayoutReference": {"predefinedLayout": "TITLE_ONLY"},
        "placeholderIdMappings": [
            {"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid},
        ],
    }})
    reqs.append({"insertText": {"objectId": tid, "text": title}})
    if body_lines:
        reqs.append({"createShape": {
            "objectId": bid, "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": sid,
                "size": {"width": {"magnitude": BODY_W, "unit": "EMU"},
                         "height": {"magnitude": BODY_H, "unit": "EMU"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": BODY_X,
                              "translateY": BODY_Y, "unit": "EMU"},
            },
        }})
        text = "\n".join(body_lines)
        reqs.append({"insertText": {"objectId": bid, "text": text}})
        reqs.append({"createParagraphBullets": {
            "objectId": bid, "textRange": {"type": "ALL"},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
        }})
        # base body style: brand font + readable size, applied to all text
        reqs.append({"updateTextStyle": {
            "objectId": bid, "textRange": {"type": "ALL"},
            "style": {"fontFamily": BODY_FONT, "fontSize": {"magnitude": BODY_SIZE, "unit": "PT"}},
            "fields": "fontFamily,fontSize",
        }})
        # bold any label lines (compute char ranges within the body text)
        off = 0
        for ln in body_lines:
            if ln in bold_labels:
                reqs.append({"updateTextStyle": {
                    "objectId": bid,
                    "textRange": {"type": "FIXED_RANGE", "startIndex": off, "endIndex": off + len(ln)},
                    "style": {"bold": True},
                    "fields": "bold",
                }})
            off += len(ln) + 1  # +1 for the newline
    return sid


def _data_slide(reqs, run, ctr, index, title, headline, observation, action, source,
                columns, rows, totals=None, roas_col=None, roas_floor=None):
    """Real house-style slide: LEFT = Minto caption (headline = the answer, then
    terse Observation / Action at 8pt), RIGHT = a native data table from real data
    with a source citation. Mirrors the live deck's 'Google Observations' format.
    """
    sid = _oid(run, next(ctr)); tid = _oid(run, next(ctr)); cap = _oid(run, next(ctr)); tbl = _oid(run, next(ctr))
    reqs.append({"createSlide": {"objectId": sid, "insertionIndex": index,
        "slideLayoutReference": {"predefinedLayout": "TITLE_ONLY"},
        "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid}]}})
    reqs.append({"insertText": {"objectId": tid, "text": title}})

    # ---- LEFT caption (Minto: headline answer, then Observation / Action) ----
    cap_lines, bold = [], set()
    cap_lines.append(headline); bold.add(headline)
    if observation:
        cap_lines.append("Observation"); bold.add("Observation"); cap_lines += observation
    if action:
        cap_lines.append("Action / Next"); bold.add("Action / Next"); cap_lines += action
    if source:
        cap_lines.append(source)
    reqs.append({"createShape": {"objectId": cap, "shapeType": "TEXT_BOX", "elementProperties": {
        "pageObjectId": sid,
        "size": {"width": {"magnitude": 2550000, "unit": "EMU"}, "height": {"magnitude": 3700000, "unit": "EMU"}},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": 300000, "translateY": 1320000, "unit": "EMU"}}}})
    reqs.append({"insertText": {"objectId": cap, "text": "\n".join(cap_lines)}})
    reqs.append({"updateTextStyle": {"objectId": cap, "textRange": {"type": "ALL"},
        "style": {"fontFamily": BODY_FONT, "fontSize": {"magnitude": 8, "unit": "PT"}}, "fields": "fontFamily,fontSize"}})
    off = 0
    for ln in cap_lines:
        if ln in bold:
            sz = 10 if ln == headline else 8
            reqs.append({"updateTextStyle": {"objectId": cap,
                "textRange": {"type": "FIXED_RANGE", "startIndex": off, "endIndex": off + len(ln)},
                "style": {"bold": True, "fontSize": {"magnitude": sz, "unit": "PT"}}, "fields": "bold,fontSize"}})
        if ln == source:
            reqs.append({"updateTextStyle": {"objectId": cap,
                "textRange": {"type": "FIXED_RANGE", "startIndex": off, "endIndex": off + len(ln)},
                "style": {"italic": True, "fontSize": {"magnitude": 6.5, "unit": "PT"},
                          "foregroundColor": {"opaqueColor": {"rgbColor": {"red": .5, "green": .5, "blue": .5}}}},
                "fields": "italic,fontSize,foregroundColor"}})
        off += len(ln) + 1

    # ---- RIGHT data table (real data) ----
    body = list(rows) + ([totals] if totals else [])
    nrows = len(body) + 1
    reqs.append({"createTable": {"objectId": tbl, "rows": nrows, "columns": len(columns),
        "elementProperties": {"pageObjectId": sid,
            "size": {"width": {"magnitude": 5950000, "unit": "EMU"}, "height": {"magnitude": min(3700000, nrows * 240000), "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 3000000, "translateY": 1300000, "unit": "EMU"}}}})

    def cell(r, c, text, *, bold=False, color=None, size=8):
        if text is None or text == "":
            return
        reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c}, "text": str(text)}})
        style = {"fontFamily": BODY_FONT, "fontSize": {"magnitude": size, "unit": "PT"}}
        fields = "fontFamily,fontSize"
        if bold:
            style["bold"] = True; fields += ",bold"
        if color:
            style["foregroundColor"] = {"opaqueColor": {"rgbColor": color}}; fields += ",foregroundColor"
        reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c},
            "textRange": {"type": "ALL"}, "style": style, "fields": fields}})

    for c, h in enumerate(columns):
        cell(0, c, h, bold=True, size=8)
    GREEN = {"red": .13, "green": .55, "blue": .13}; RED = {"red": .79, "green": .15, "blue": .15}
    for ri, row in enumerate(body, start=1):
        is_total = totals and ri == len(body)
        for c, val in enumerate(row):
            color = None
            if roas_col is not None and c == roas_col and roas_floor is not None:
                try:
                    color = GREEN if float(str(val).replace("x", "")) >= roas_floor else RED
                except ValueError:
                    color = None
            cell(ri, c, val, bold=is_total, color=color)
    return sid


# Triple Whale UI palette (matched to the TW reporting table)
TW_GREEN = {"red": 0.18, "green": 0.49, "blue": 0.20}
TW_RED = {"red": 0.77, "green": 0.18, "blue": 0.18}
TW_GRAY = {"red": 0.58, "green": 0.59, "blue": 0.62}
TW_BLUE = {"red": 0.16, "green": 0.40, "blue": 0.80}   # campaign link color
TW_DARK = {"red": 0.13, "green": 0.14, "blue": 0.16}
TW_BAND = {"red": 0.92, "green": 0.95, "blue": 0.99}   # pale-blue ROAS/NC ROAS columns
TW_HEADER = {"red": 0.96, "green": 0.965, "blue": 0.975}


def _metric_cell(cur, prev, dpct, kind):
    """Build (text, runs) for a TW metric cell: big current + gray comparison +
    colored delta arrow. kind: 'roas' (up=green) or 'cost' (down=green).
    runs = list of (start, end, style_dict)."""
    if cur in (None, "", "-"):
        return "-", [(0, 1, {"foregroundColor": {"opaqueColor": {"rgbColor": TW_GRAY}},
                             "fontSize": {"magnitude": 6, "unit": "PT"}})]
    runs = []
    text = str(cur)
    runs.append((0, len(text), {"bold": True, "foregroundColor": {"opaqueColor": {"rgbColor": TW_DARK}},
                                "fontSize": {"magnitude": 6, "unit": "PT"}}))
    if prev not in (None, "", "-"):
        s = len(text) + 1
        text += " " + str(prev)
        runs.append((s, len(text), {"foregroundColor": {"opaqueColor": {"rgbColor": TW_GRAY}},
                                    "fontSize": {"magnitude": 4, "unit": "PT"}}))
    if dpct is not None:
        up = dpct >= 0
        good = up if kind == "roas" else (not up)
        arrow = "↑" if up else "↓"
        mag = abs(dpct)
        dtxt = f" {arrow}{mag:g}%"
        s = len(text)
        text += dtxt
        runs.append((s, len(text), {"foregroundColor": {"opaqueColor": {"rgbColor": TW_GREEN if good else TW_RED}},
                                    "fontSize": {"magnitude": 4, "unit": "PT"}}))
    return text, runs


def _tw_campaign_table(reqs, run, ctr, index, title, source, rows, totals, verify_url=None,
                       headline=None, observation=None, action=None):
    """House-style data slide matching the live 'Google Observations' template:
    small title, LEFT caption (headline + Observation/Action bullets at 8pt), RIGHT
    a condensed TW-styled campaign table (Campaign|Spend|ROAS|NC ROAS|NC CPA), white bg.
    """
    sid = _oid(run, next(ctr)); tid = _oid(run, next(ctr)); tbl = _oid(run, next(ctr))
    reqs.append({"createSlide": {"objectId": sid, "insertionIndex": index,
        "slideLayoutReference": {"predefinedLayout": "TITLE_ONLY"},
        "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid}]}})
    reqs.append({"insertText": {"objectId": tid, "text": title}})
    # shrink the (theme-huge) title to a compact single line
    reqs.append({"updateTextStyle": {"objectId": tid, "textRange": {"type": "ALL"},
        "style": {"fontSize": {"magnitude": 11, "unit": "PT"}, "bold": True}, "fields": "fontSize,bold"}})

    # ---- LEFT caption (the text-box bullets) ----
    cap = _oid(run, next(ctr))
    lines, bold = [], set()
    if headline:
        lines.append(headline); bold.add(headline)
    if observation:
        lines.append("Observation"); bold.add("Observation"); lines += observation
    if action:
        lines.append("Action / Next"); bold.add("Action / Next"); lines += action
    if lines:
        reqs.append({"createShape": {"objectId": cap, "shapeType": "TEXT_BOX", "elementProperties": {
            "pageObjectId": sid, "size": {"width": {"magnitude": 2400000, "unit": "EMU"}, "height": {"magnitude": 3500000, "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 300000, "translateY": 1000000, "unit": "EMU"}}}})
        reqs.append({"insertText": {"objectId": cap, "text": "\n".join(lines)}})
        reqs.append({"updateTextStyle": {"objectId": cap, "textRange": {"type": "ALL"},
            "style": {"fontFamily": BODY_FONT, "fontSize": {"magnitude": 7.5, "unit": "PT"}}, "fields": "fontFamily,fontSize"}})
        reqs.append({"createParagraphBullets": {"objectId": cap, "textRange": {"type": "ALL"},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
        off = 0
        for ln in lines:
            if ln in bold:
                sz = 9 if ln == headline else 7.5
                reqs.append({"updateTextStyle": {"objectId": cap,
                    "textRange": {"type": "FIXED_RANGE", "startIndex": off, "endIndex": off + len(ln)},
                    "style": {"bold": True, "fontSize": {"magnitude": sz, "unit": "PT"}}, "fields": "bold,fontSize"}})
            off += len(ln) + 1

    cols = ["Campaign", "Spend", "ROAS", "NC ROAS", "NC CPA"]
    body = rows + [totals]
    nrows = len(body) + 1
    WHITE = {"red": 1, "green": 1, "blue": 1}
    reqs.append({"createTable": {"objectId": tbl, "rows": nrows, "columns": len(cols),
        "elementProperties": {"pageObjectId": sid,
            "size": {"width": {"magnitude": 6080000, "unit": "EMU"}, "height": {"magnitude": min(3500000, nrows * 180000), "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 2780000, "translateY": 560000, "unit": "EMU"}}}})
    # column widths (sum = 6080000); Campaign wide enough that long names don't wrap
    widths = [2160000, 1100000, 980000, 980000, 860000]
    for ci, w in enumerate(widths):
        reqs.append({"updateTableColumnProperties": {"objectId": tbl, "columnIndices": [ci],
            "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "EMU"}}, "fields": "columnWidth"}})
    # whole-table WHITE background + MIDDLE vertical alignment
    reqs.append({"updateTableCellProperties": {"objectId": tbl,
        "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": nrows, "columnSpan": len(cols)},
        "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": WHITE}}},
                                "contentAlignment": "MIDDLE"},
        "fields": "tableCellBackgroundFill.solidFill.color,contentAlignment"}})

    def put(r, c, text, runs=None, base=None):
        if not text:
            return
        reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c}, "text": text}})
        # THE FIT LEVER: crush line spacing + zero paragraph spacing so rows don't auto-grow
        reqs.append({"updateParagraphStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c},
            "textRange": {"type": "ALL"},
            "style": {"lineSpacing": 72, "spaceAbove": {"magnitude": 0, "unit": "PT"}, "spaceBelow": {"magnitude": 0, "unit": "PT"}},
            "fields": "lineSpacing,spaceAbove,spaceBelow"}})
        if base:
            reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c},
                "textRange": {"type": "ALL"}, "style": base, "fields": ",".join(base.keys())}})
        for s, e, st in (runs or []):
            reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c},
                "textRange": {"type": "FIXED_RANGE", "startIndex": s, "endIndex": e}, "style": st,
                "fields": ",".join(st.keys())}})

    # header
    for c, h in enumerate(cols):
        put(0, c, h, base={"bold": True, "fontFamily": BODY_FONT, "fontSize": {"magnitude": 6, "unit": "PT"},
                           "foregroundColor": {"opaqueColor": {"rgbColor": TW_DARK}}})
    # body
    for ri, row in enumerate(body, start=1):
        is_tot = ri == len(body)
        nm = row["campaign"]
        put(ri, 0, nm, base={"fontFamily": BODY_FONT, "fontSize": {"magnitude": 6, "unit": "PT"},
                             "bold": is_tot,
                             "foregroundColor": {"opaqueColor": {"rgbColor": TW_DARK if is_tot else TW_BLUE}}})
        for c, key, kind in [(1, "spend", "roas"), (2, "roas", "roas"), (3, "nc_roas", "roas"), (4, "nc_cpa", "cost")]:
            val = row.get(key)
            if is_tot:
                put(ri, c, str(val), base={"bold": True, "fontFamily": BODY_FONT,
                    "fontSize": {"magnitude": 6.5, "unit": "PT"}, "foregroundColor": {"opaqueColor": {"rgbColor": TW_DARK}}})
            elif isinstance(val, (list, tuple)):
                text, runs = _metric_cell(val[0], val[1] if len(val) > 1 else None,
                                          val[2] if len(val) > 2 else None, kind)
                put(ri, c, text, runs=runs, base={"fontFamily": BODY_FONT})
            else:
                put(ri, c, str(val) if val is not None else "-", base={"fontFamily": BODY_FONT,
                    "fontSize": {"magnitude": 6, "unit": "PT"}, "foregroundColor": {"opaqueColor": {"rgbColor": TW_DARK}}})

    # source footnote (+ clickable Triple Whale verify link) — below the table
    fn = _oid(run, next(ctr))
    link_txt = "   ·   Open in Triple Whale ↗" if verify_url else ""
    full = source + link_txt
    reqs.append({"createShape": {"objectId": fn, "shapeType": "TEXT_BOX", "elementProperties": {
        "pageObjectId": sid, "size": {"width": {"magnitude": 6050000, "unit": "EMU"}, "height": {"magnitude": 280000, "unit": "EMU"}},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": 2780000, "translateY": 4830000, "unit": "EMU"}}}})
    reqs.append({"insertText": {"objectId": fn, "text": full}})
    reqs.append({"updateTextStyle": {"objectId": fn, "textRange": {"type": "ALL"},
        "style": {"italic": True, "fontFamily": BODY_FONT, "fontSize": {"magnitude": 6.5, "unit": "PT"},
                  "foregroundColor": {"opaqueColor": {"rgbColor": TW_GRAY}}}, "fields": "italic,fontFamily,fontSize,foregroundColor"}})
    if verify_url:
        s = len(source)
        reqs.append({"updateTextStyle": {"objectId": fn,
            "textRange": {"type": "FIXED_RANGE", "startIndex": s, "endIndex": len(full)},
            "style": {"link": {"url": verify_url}, "underline": True, "italic": False,
                      "foregroundColor": {"opaqueColor": {"rgbColor": TW_BLUE}}, "fontSize": {"magnitude": 6.5, "unit": "PT"}},
            "fields": "link,underline,italic,foregroundColor,fontSize"}})
    return sid


def _obs_body(block):
    lines = []
    obs = block.get("observation") or []
    nxt = block.get("next_steps") or []
    if obs:
        lines.append("Observation")
        lines.extend(obs)
    if nxt:
        lines.append("Next steps")
        lines.extend(nxt)
    return lines


def build_requests(payload, insert_index, run):
    """Return (requests, [new_slide_object_ids]) for the full period block."""
    reqs = []
    ctr = iter(range(1, 100000))
    new_slides = []
    idx = insert_index

    # 1) divider
    new_slides.append(_content_slide(
        reqs, run, ctr, idx,
        payload["period_label"],
        [payload.get("divider_label", "")] if payload.get("divider_label") else [],
    ))
    idx += 1

    # 2) dashboard slide: metrics text + native-table area (screenshots deprecated — REPORTING-SPEC.md)
    dash = payload.get("dashboard") or {}
    dash_title = dash.get("title") or "Weekly dashboard"
    dash_sid = _content_slide(reqs, run, ctr, idx, dash_title, dash.get("metrics") or [])
    # screenshot placeholder — sits BELOW the metrics so they never overlap
    pid = _oid(run, next(ctr))
    reqs.append({"createShape": {
        "objectId": pid, "shapeType": "TEXT_BOX",
        "elementProperties": {
            "pageObjectId": dash_sid,
            "size": {"width": {"magnitude": BODY_W, "unit": "EMU"},
                     "height": {"magnitude": 900000, "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": BODY_X,
                          "translateY": 3850000, "unit": "EMU"},
        },
    }})
    reqs.append({"insertText": {"objectId": pid, "text": PLACEHOLDER_TEXT}})
    new_slides.append(dash_sid)
    idx += 1

    # 2b) budget pacing slide (right after the topline) — content slide
    pacing = payload.get("pacing")
    if pacing:
        new_slides.append(_content_slide(reqs, run, ctr, idx, pacing["title"],
                                         pacing.get("bullets") or [],
                                         bold_labels=set(pacing.get("bold_labels") or [])))
        idx += 1

    # 3) observation slides
    for block in (payload.get("observations") or []):
        new_slides.append(_content_slide(reqs, run, ctr, idx, block["title"],
                                         _obs_body(block), bold_labels={"Observation", "Next steps"}))
        idx += 1

    # 4) deep dives
    for block in (payload.get("deep_dives") or []):
        new_slides.append(_content_slide(reqs, run, ctr, idx, block["title"],
                                         _obs_body(block), bold_labels={"Observation", "Next steps"}))
        idx += 1

    # 4b) extra sections (strategy snapshot, tactics, etc.) — content slides
    for block in (payload.get("sections") or []):
        new_slides.append(_content_slide(reqs, run, ctr, idx, block["title"],
                                         block.get("bullets") or [],
                                         bold_labels=set(block.get("bold_labels") or [])))
        idx += 1

    # 5) action items table slide
    items = payload.get("action_items") or []
    if items:
        sid = _oid(run, next(ctr)); tid = _oid(run, next(ctr))
        reqs.append({"createSlide": {
            "objectId": sid, "insertionIndex": idx,
            "slideLayoutReference": {"predefinedLayout": "TITLE_ONLY"},
            "placeholderIdMappings": [
                {"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid},
            ],
        }})
        reqs.append({"insertText": {"objectId": tid, "text": "Action items"}})
        tbl = _oid(run, next(ctr))
        rows = len(items) + 1
        reqs.append({"createTable": {
            "objectId": tbl, "rows": rows, "columns": 3,
            "elementProperties": {
                "pageObjectId": sid,
                "size": {"width": {"magnitude": 8000000, "unit": "EMU"},
                         "height": {"magnitude": 3000000, "unit": "EMU"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 600000,
                              "translateY": 1400000, "unit": "EMU"},
            },
        }})
        # header + rows (insert bottom-up so indices stay valid is unnecessary for cell text)
        header = ["Action", "Notes", "Status"]
        for c, h in enumerate(header):
            reqs.append({"insertText": {"objectId": tbl,
                        "cellLocation": {"rowIndex": 0, "columnIndex": c}, "text": h}})
        for r, it in enumerate(items, start=1):
            cells = [it.get("action", ""), it.get("notes", ""), it.get("status", "")]
            for c, val in enumerate(cells):
                if val:
                    reqs.append({"insertText": {"objectId": tbl,
                                "cellLocation": {"rowIndex": r, "columnIndex": c}, "text": str(val)}})
        new_slides.append(sid)
        idx += 1

    # 6) appendix (analysis) — a divider + content slides, co-located with the period
    ap = payload.get("appendix")
    if ap:
        new_slides.append(_content_slide(reqs, run, ctr, idx,
                                         ap.get("label", "Appendix — Analysis"), []))
        idx += 1
        for block in ap.get("slides", []):
            new_slides.append(_content_slide(reqs, run, ctr, idx, block["title"],
                                             block.get("bullets") or [],
                                             bold_labels=set(block.get("bold_labels") or [])))
            idx += 1

    return reqs, new_slides


def prepend_period(presentation_id, payload, insert_index=1):
    """Prepend a period block. Returns dict with result + verification."""
    run = str(int(time.time()))
    before = bridge.slide_object_ids(presentation_id)
    if insert_index > len(before):
        insert_index = len(before)
    anchor = before[insert_index] if insert_index < len(before) else None

    reqs, new_slides = build_requests(payload, insert_index, run)

    try:
        bridge.slides_batch(presentation_id, reqs)
    except Exception as e:  # noqa: BLE001
        # batch failed — attempt to delete any slides that DID get created
        _rollback(presentation_id, new_slides)
        raise RuntimeError(f"batchUpdate failed, rolled back: {e}")

    after = bridge.slide_object_ids(presentation_id)
    expected = len(before) + len(new_slides)
    ok_count = len(after) == expected
    # the slide that was at insert_index should now sit at insert_index+len(new_slides)
    ok_anchor = True
    if anchor is not None:
        shifted = after[insert_index + len(new_slides)] if insert_index + len(new_slides) < len(after) else None
        ok_anchor = (shifted == anchor)
    ok_top = all(s in after for s in new_slides)

    if not (ok_count and ok_anchor and ok_top):
        _rollback(presentation_id, new_slides)
        raise RuntimeError(
            f"verification failed (count={ok_count} anchor={ok_anchor} top={ok_top}); rolled back")

    return {
        "presentation_id": presentation_id,
        "slides_added": len(new_slides),
        "new_slide_ids": new_slides,
        "total_slides": len(after),
        "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit",
    }


def insert_content_slide(presentation_id, title, bullets, index, bold_labels=None):
    """Surgically insert ONE content slide at `index` (additive, verified, rollback).

    For adding a single slide to an existing deck without rebuilding the period.
    """
    run = str(int(time.time()))
    before = bridge.slide_object_ids(presentation_id)
    if index > len(before):
        index = len(before)
    anchor = before[index] if index < len(before) else None
    reqs = []
    ctr = iter(range(1, 100000))
    sid = _content_slide(reqs, run, ctr, index, title, bullets or [], bold_labels=set(bold_labels or []))
    try:
        bridge.slides_batch(presentation_id, reqs)
    except Exception as e:  # noqa: BLE001
        _rollback(presentation_id, [sid])
        raise RuntimeError(f"insert failed, rolled back: {e}")
    after = bridge.slide_object_ids(presentation_id)
    ok = len(after) == len(before) + 1 and sid in after
    if anchor is not None:
        ok = ok and (after[index + 1] == anchor if index + 1 < len(after) else False)
    if not ok:
        _rollback(presentation_id, [sid])
        raise RuntimeError("insert verification failed; rolled back")
    return {"slide_id": sid, "index": index, "total_slides": len(after),
            "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit"}


def _rollback(presentation_id, slide_ids):
    if not slide_ids:
        return
    try:
        bridge.slides_batch(presentation_id, [{"deleteObject": {"objectId": s}} for s in slide_ids])
    except Exception:  # noqa: BLE001
        pass  # best-effort; surfaced in the raised error above
