#!/usr/bin/env python3
"""extract_style.py — learn the formatting + style of an EXISTING Google Slides deck.

Reads a reference presentation through the bridge and emits a compact "style spec"
(JSON): theme colors, page size, layout map, and the real title/body/subtitle/table
formatting actually used on its slides (font family, size, weight, color). That spec
is what apply_style.py and deckkit.py consume so new or restyled slides MATCH the
reference deck instead of using arbitrary defaults.

    python3 extract_style.py <REFERENCE_PRESENTATION_ID>            # print spec to stdout
    python3 extract_style.py <REFERENCE_PRESENTATION_ID> style.json # also write to file

Tip: <PRESENTATION_ID> is the long id in the deck's URL:
    https://docs.google.com/presentation/d/<PRESENTATION_ID>/edit
"""
import collections
import json
import sys

import bridge
import gslib

# A precise field mask — only what we need to derive the spec (keeps the response small).
FIELDS = (
    "presentationId,pageSize,"
    "masters(pageProperties.colorScheme),"
    "layouts(objectId,layoutProperties(displayName,name)),"
    "slides(slideProperties.layoutObjectId,pageElements(objectId,"
    "shape(shapeType,placeholder(type),text(textElements(textRun(content,"
    "style(fontSize,bold,italic,weightedFontFamily,foregroundColor))))),"
    "table(tableRows(tableCells("
    "tableCellProperties(tableCellBackgroundFill),"
    "text(textElements(textRun(content,style(fontSize,bold,weightedFontFamily,foregroundColor)))))))))"
)


def first_run_style(text_obj):
    """Return the style of the first non-whitespace text run in a shape/cell, or None."""
    for te in (text_obj or {}).get("textElements", []):
        run = te.get("textRun")
        if run and run.get("content", "").strip():
            return run.get("style", {})
    return None


def style_to_spec(style, theme_map, font_counter):
    """Convert a Slides textRun style into our compact spec fields."""
    if not style:
        return None
    fam = (style.get("weightedFontFamily") or {}).get("fontFamily")
    if fam:
        font_counter[fam] += 1
    size = (style.get("fontSize") or {}).get("magnitude")
    color = gslib.color_from_opaque((style.get("foregroundColor") or {}).get("opaqueColor"), theme_map)
    spec = {}
    if fam:
        spec["font"] = fam
    if size is not None:
        spec["size_pt"] = round(size, 1)
    if style.get("bold"):
        spec["bold"] = True
    if style.get("italic"):
        spec["italic"] = True
    if color:
        spec["color"] = color
    return spec or None


def main():
    if len(sys.argv) < 2:
        print("usage: extract_style.py <REFERENCE_PRESENTATION_ID> [out.json]", file=sys.stderr)
        sys.exit(1)
    pid = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else None

    resp = bridge.api("slides", "GET", f"/v1/presentations/{pid}", query={"fields": FIELDS})
    if not resp.get("success"):
        print("Failed to read presentation:", json.dumps(resp)[:400], file=sys.stderr)
        sys.exit(1)
    d = resp["body"]

    # 1. Theme colors (resolves themeColor refs downstream).
    masters = d.get("masters", [])
    theme_map = gslib.parse_color_scheme(
        masters[0].get("pageProperties", {}).get("colorScheme", {}) if masters else {}
    )

    # 2. Layout map (displayName -> objectId) + a usable name->id lookup.
    layouts = {}
    for L in d.get("layouts", []):
        lp = L.get("layoutProperties", {})
        name = lp.get("displayName") or lp.get("name") or L["objectId"]
        layouts[name] = L["objectId"]

    # 3. Walk slides; capture the FIRST real example of each role.
    font_counter = collections.Counter()
    roles = {}            # role -> spec
    table_header = None
    table_body = None
    cover_layout = None
    body_layout = None

    PLACEHOLDER_ROLE = {
        "TITLE": "title", "CENTERED_TITLE": "title",
        "SUBTITLE": "subtitle",
        "BODY": "body",
    }

    for slide in d.get("slides", []):
        layout_id = slide.get("slideProperties", {}).get("layoutObjectId")
        for el in slide.get("pageElements", []):
            shape = el.get("shape")
            if shape:
                ph_type = (shape.get("placeholder") or {}).get("type")
                role = PLACEHOLDER_ROLE.get(ph_type)
                if role:
                    if cover_layout is None and role == "title" and ph_type == "CENTERED_TITLE":
                        cover_layout = layout_id
                    if body_layout is None and role == "body":
                        body_layout = layout_id
                    if role not in roles:
                        spec = style_to_spec(first_run_style(shape.get("text")), theme_map, font_counter)
                        if spec:
                            roles[role] = spec
            table = el.get("table")
            if table and table_header is None:
                rows = table.get("tableRows", [])
                if rows:
                    # Header = row 0 first cell; capture fill + text style.
                    cells0 = rows[0].get("tableCells", [])
                    if cells0:
                        cell = cells0[0]
                        fill = (cell.get("tableCellProperties", {})
                                .get("tableCellBackgroundFill", {})
                                .get("solidFill", {}).get("color", {}))
                        fill_hex = gslib.color_from_opaque(
                            {"rgbColor": fill["rgbColor"]} if "rgbColor" in fill else fill, theme_map
                        )
                        hspec = style_to_spec(first_run_style(cell.get("text")), theme_map, font_counter) or {}
                        if fill_hex:
                            hspec["fill"] = fill_hex
                        table_header = hspec or None
                    if len(rows) > 1:
                        cells1 = rows[1].get("tableCells", [])
                        if cells1:
                            table_body = style_to_spec(
                                first_run_style(cells1[0].get("text")), theme_map, font_counter)

    primary_font = font_counter.most_common(1)[0][0] if font_counter else None

    spec = {
        "source_presentation_id": pid,
        "page_size": d.get("pageSize"),
        "fonts": {"primary": primary_font},
        "theme_colors": theme_map,
        "title": roles.get("title"),
        "subtitle": roles.get("subtitle"),
        "body": roles.get("body"),
        "table_header": table_header,
        "table_body": table_body,
        "layouts": layouts,
        "cover_layout_id": cover_layout,
        "body_layout_id": body_layout,
    }

    text = json.dumps(spec, indent=2)
    print(text)
    if out_path:
        with open(out_path, "w") as f:
            f.write(text + "\n")
        print(f"\n→ wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
