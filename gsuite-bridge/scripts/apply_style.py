#!/usr/bin/env python3
"""apply_style.py — make a target deck ADHERE to a style spec.

Walks every slide of the target presentation and restyles titles, bodies,
subtitles, and tables to match a style spec (from extract_style.py, or hand-written).
It also turns OFF placeholder autofit, the silent cause of inconsistent body sizes.

STYLE-ONLY + CONTENT-SAFE: it never inserts, deletes, or rewrites text — only
text styles, table-cell fills, and autofit. Safe to run on a live deck someone
has edited. Idempotent: run it as many times as you like.

    python3 apply_style.py <TARGET_PRESENTATION_ID> style.json

Common flow:
    python3 extract_style.py <REFERENCE_ID> brand.json     # learn the look
    python3 apply_style.py   <TARGET_ID>    brand.json      # stamp it on the target
"""
import json
import sys

import bridge
import gslib


def text_style_req(object_id, spec, cell=None):
    """Build an updateTextStyle request from a compact spec ({font,size_pt,bold,italic,color})."""
    if not spec:
        return None
    style, fields = {}, []
    if spec.get("font"):
        gslib.font(style, spec["font"])
        fields.append("weightedFontFamily")
    if spec.get("size_pt") is not None:
        style["fontSize"] = gslib.pt(spec["size_pt"])
        fields.append("fontSize")
    if "bold" in spec:
        style["bold"] = bool(spec["bold"])
        fields.append("bold")
    if "italic" in spec:
        style["italic"] = bool(spec["italic"])
        fields.append("italic")
    if spec.get("color"):
        style["foregroundColor"] = gslib.opaque(spec["color"])
        fields.append("foregroundColor")
    if not fields:
        return None
    req = {"updateTextStyle": {"objectId": object_id, "style": style,
                               "textRange": {"type": "ALL"}, "fields": ",".join(fields)}}
    if cell is not None:
        req["updateTextStyle"]["cellLocation"] = cell
    return req


def autofit_none_req(object_id):
    return {"updateShapeProperties": {"objectId": object_id,
            "shapeProperties": {"autofit": {"autofitType": "NONE"}},
            "fields": "autofit.autofitType"}}


def main():
    if len(sys.argv) < 3:
        print("usage: apply_style.py <TARGET_PRESENTATION_ID> <style.json>", file=sys.stderr)
        sys.exit(1)
    pid = sys.argv[1]
    with open(sys.argv[2]) as f:
        spec = json.load(f)

    title_s = spec.get("title")
    body_s = spec.get("body")
    subtitle_s = spec.get("subtitle")
    th = spec.get("table_header") or {}
    tb = spec.get("table_body")

    fields = ("slides(pageElements(objectId,shape(shapeType,placeholder(type)),"
              "table(columns,tableRows(tableCells(text(textElements(textRun(content)))))))) ")
    resp = bridge.api("slides", "GET", f"/v1/presentations/{pid}", query={"fields": fields})
    if not resp.get("success"):
        print("Failed to read target:", json.dumps(resp)[:400], file=sys.stderr)
        sys.exit(1)
    d = resp["body"]

    reqs = []
    for slide in d.get("slides", []):
        for el in slide.get("pageElements", []):
            oid = el["objectId"]
            table = el.get("table")
            if table:
                ncol = table.get("columns", len(table.get("tableRows", [{}])[0].get("tableCells", [])))
                # Header row fill
                if th.get("fill"):
                    reqs.append({"updateTableCellProperties": {"objectId": oid,
                        "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0},
                                       "rowSpan": 1, "columnSpan": ncol},
                        "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": gslib.solid(th["fill"])}},
                        "fields": "tableCellBackgroundFill.solidFill.color"}})
                for ri, row in enumerate(table.get("tableRows", [])):
                    for ci, cell in enumerate(row.get("tableCells", [])):
                        txt = "".join(te.get("textRun", {}).get("content", "")
                                      for te in cell.get("text", {}).get("textElements", [])).strip()
                        if not txt:
                            continue
                        cell_loc = {"rowIndex": ri, "columnIndex": ci}
                        r = text_style_req(oid, th if ri == 0 else tb, cell=cell_loc)
                        if r:
                            reqs.append(r)
                continue

            shape = el.get("shape")
            if not shape:
                continue
            ph = (shape.get("placeholder") or {}).get("type")
            if ph == "SLIDE_NUMBER":
                continue
            if ph in ("TITLE", "CENTERED_TITLE"):
                r = text_style_req(oid, title_s)
                if r:
                    reqs.append(r)
            elif ph == "SUBTITLE":
                r = text_style_req(oid, subtitle_s)
                if r:
                    reqs.append(r)
            elif ph == "BODY":
                reqs.append(autofit_none_req(oid))
                r = text_style_req(oid, body_s)
                if r:
                    reqs.append(r)

    if not reqs:
        print("Nothing to restyle (no matching placeholders/tables found).")
        return
    print(f"applying {len(reqs)} style ops to {pid} …")
    out = bridge.api("slides", "POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})
    print("batchUpdate:", out.get("success"), out.get("status"))
    if not out.get("success"):
        print(json.dumps(out)[:600])
        sys.exit(1)


if __name__ == "__main__":
    main()
