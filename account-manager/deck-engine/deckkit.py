#!/usr/bin/env python3
"""deckkit — reusable Google Slides primitives over your own deployed Apps Script bridge
(decks are created in the bridge account's Drive). Bakes in every formatting lesson: theme
colors, Poppins via weightedFontFamily, autofit OFF, hierarchy, no em dashes.

⛔ GOLDEN RULE: create_deck / wipe_slides are FIRST-BUILD ONLY. Once a deck exists and the operator
may have edited it, use ONLY the granular add_* helpers (for new slides) and updateTextStyle (for
edits). NEVER wipe-and-recreate a live deck — it destroys human edits.

Configuration: set BRIDGE_URL (and BRIDGE_SECRET) in the package .env — the exec URL + secret of
your own deployed Apps Script bridge (see bridge/SETUP.md).

Usage (first build):
    import deckkit as dk
    pid = dk.copy_template(TEMPLATE_ID, "Acme Opportunities")
    dk.wipe_slides(pid)                      # only on the fresh copy
    dk.add_cover(pid, "Google Ads Opportunities", "Acme  ×  your agency   ·   Jun 2026", LOGO_PNG_URL)
    dk.add_text_slide(pid, 1, "Context", [("h","Today"),("b","...")])
    dk.add_table_slide(pid, 2, "The demand", ["Term","Searches","Comp","Bid"], rows, subtitle="...", caption=("Source: ...", []))
    dk.set_autofit_none(pid)                 # uniform body sizing
    dk.render(pid, 0, "/tmp/cover.png")
"""
import json, os, urllib.request, urllib.parse, time

try:
    from dotenv import load_dotenv
    load_dotenv()  # load BRIDGE_URL / BRIDGE_SECRET from the package .env
except ImportError:
    pass

# Your own deployed Apps Script bridge (see bridge/SETUP.md). NEVER hardcode the URL/secret.
URL = os.environ.get("BRIDGE_URL", "")
SECRET = os.environ.get("BRIDGE_SECRET", "")

# DARK deck theme: ink background, BRIGHT high-contrast text + bright (inverted) tables.
# Explicit RGB so the scheme is deterministic; builders use these names — flip here to retheme.
INKBG = {"rgbColor": {"red": 0.090, "green": 0.098, "blue": 0.094}}    # slide background + callout text  #171918
DARK2 = {"rgbColor": {"red": 1.000, "green": 1.000, "blue": 1.000}}    # titles (pure white)             #ffffff
INK = {"rgbColor": {"red": 0.949, "green": 0.949, "blue": 0.949}}      # body text (near-white)          #f2f2f2
GREY = {"rgbColor": {"red": 0.760, "green": 0.776, "blue": 0.792}}     # subtitle/caption (bright muted) #c2c6ca
GOLD = {"rgbColor": {"red": 1.000, "green": 0.769, "blue": 0.302}}     # accent: callout band + rule     #ffc44d
CHARCOAL = {"rgbColor": {"red": 1.000, "green": 0.769, "blue": 0.302}} # callout band fill (= gold)      #ffc44d
HDRBG = {"rgbColor": {"red": 1.000, "green": 0.769, "blue": 0.302}}    # table header fill (gold)        #ffc44d
CELLBG = {"rgbColor": {"red": 0.980, "green": 0.980, "blue": 0.980}}   # table body cell fill (paper)    #fafafa
CELLTXT = {"rgbColor": {"red": 0.180, "green": 0.192, "blue": 0.188}}  # table header + cell text (ink)  #2e3130
LINKC = {"rgbColor": {"red": 0.521, "green": 0.717, "blue": 0.921}}    # caption links (on dark bg)      #85b7eb
WHITE = {"rgbColor": {"red": 1, "green": 1, "blue": 1}}
FONT = "Poppins"
PAGE_W, PAGE_H = 9144000, 5143500
_seq = [0]

def _uid(p):
    _seq[0] += 1
    return f"{p}{int(time.time()*1000)%100000}{_seq[0]:03d}"

def call(payload, _tries=4):
    if not URL:
        raise RuntimeError("BRIDGE_URL is not set. Deploy your own Apps Script bridge "
                           "(see bridge/SETUP.md) and set BRIDGE_URL (and BRIDGE_SECRET) "
                           "in the package .env.")
    payload = {"secret": SECRET, **payload}
    last = None
    for k in range(_tries):
        r = urllib.request.Request(URL, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            return json.loads(urllib.request.urlopen(r, timeout=240).read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code >= 500 and k < _tries - 1:
                time.sleep(1.5 * (k + 1)); continue
            raise
    raise last

def api(method, path, body=None):
    return call({"action": "google_api", "api": "slides", "method": method, "path": path, "body": body})

def emu(v): return {"magnitude": v, "unit": "EMU"}
def _pt(v): return {"magnitude": v, "unit": "PT"}
def _font(style): style["weightedFontFamily"] = {"fontFamily": FONT}; return style

# ---- template / structure ----
def copy_template(template_id, name):
    """Duplicate a themed master deck into the bridge account's Drive. Returns new presentationId."""
    r = call({"action": "copy_file", "fileId": template_id, "name": name})
    return r.get("newFileId") or r.get("fileId") or r.get("id")

def slide_ids(pid):
    return [s["objectId"] for s in api("GET", f"/v1/presentations/{pid}?fields=slides.objectId")["body"]["slides"]]

def wipe_slides(pid):
    """FIRST-BUILD ONLY. Delete all slides on a freshly-copied template before building."""
    ids = slide_ids(pid)
    # create one throwaway so we never hit zero, then delete originals, then delete throwaway
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests":
        [{"createSlide": {"objectId": "tmp_wipe0", "insertionIndex": len(ids)}}]
        + [{"deleteObject": {"objectId": o}} for o in ids]})
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": [{"deleteObject": {"objectId": "tmp_wipe0"}}]})

def theme(pid):
    """Return {layouts: {displayName: id}, colors: [...]} for the copied template."""
    d = api("GET", f"/v1/presentations/{pid}?fields=layouts(objectId,layoutProperties.displayName),masters(pageProperties(colorScheme))")["body"]
    lay = {L.get("layoutProperties", {}).get("displayName", "?"): L["objectId"] for L in d.get("layouts", [])}
    return {"layouts": lay, "colors": d.get("masters", [{}])[0].get("pageProperties", {}).get("colorScheme", {})}

# ---- slide builders ----
def add_cover(pid, title, subtitle, logo_url=None, blank_layout="p12"):
    sid, tid, subid = _uid("cov"), _uid("covT"), _uid("covS")
    reqs = [{"createSlide": {"objectId": sid, "insertionIndex": 0, "slideLayoutReference": {"layoutId": blank_layout}}}]
    if logo_url:
        lw = 1400000
        reqs.append({"createImage": {"objectId": _uid("logo"), "url": logo_url, "elementProperties": {"pageObjectId": sid,
            "size": {"width": emu(lw), "height": emu(lw)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": (PAGE_W - lw) // 2, "translateY": 380000, "unit": "EMU"}}}})
    reqs += [
        {"createShape": {"objectId": tid, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": emu(8000000), "height": emu(1200000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 572000, "translateY": 2150000, "unit": "EMU"}}}},
        {"insertText": {"objectId": tid, "text": title}},
        {"updateTextStyle": {"objectId": tid, "style": _font({"bold": True, "fontSize": _pt(36), "foregroundColor": {"opaqueColor": DARK2}}),
            "textRange": {"type": "ALL"}, "fields": "bold,fontSize,weightedFontFamily,foregroundColor"}},
        {"updateParagraphStyle": {"objectId": tid, "style": {"alignment": "CENTER"}, "textRange": {"type": "ALL"}, "fields": "alignment"}},
        {"createShape": {"objectId": subid, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": emu(8000000), "height": emu(700000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 572000, "translateY": 3520000, "unit": "EMU"}}}},
        {"insertText": {"objectId": subid, "text": subtitle}},
        {"updateTextStyle": {"objectId": subid, "style": _font({"fontSize": _pt(14), "foregroundColor": {"opaqueColor": DARK2}}),
            "textRange": {"type": "ALL"}, "fields": "fontSize,weightedFontFamily,foregroundColor"}},
        {"updateParagraphStyle": {"objectId": subid, "style": {"alignment": "CENTER"}, "textRange": {"type": "ALL"}, "fields": "alignment"}},
    ]
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})
    return sid

def add_text_slide(pid, index, title, items, subtitle=None, body_layout="p4"):
    """items = list of ('h', text) headings | ('b', text) bullets. Headings render bold (no bullet)."""
    sid, tid, bid = _uid("s"), _uid("t"), _uid("b")
    reqs = [{"createSlide": {"objectId": sid, "insertionIndex": index, "slideLayoutReference": {"layoutId": body_layout},
        "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid},
                                  {"layoutPlaceholder": {"type": "BODY", "index": 0}, "objectId": bid}]}},
        {"insertText": {"objectId": tid, "text": title}},
        {"updateTextStyle": {"objectId": tid, "style": _font({"bold": True, "fontSize": _pt(24), "foregroundColor": {"opaqueColor": DARK2}}),
            "textRange": {"type": "ALL"}, "fields": "bold,fontSize,weightedFontFamily,foregroundColor"}}]
    body = ("" if not subtitle else subtitle + "\n") + "\n".join(it[1] for it in items)
    reqs.append({"insertText": {"objectId": bid, "text": body}})
    reqs.append({"updateShapeProperties": {"objectId": bid, "shapeProperties": {"autofit": {"autofitType": "NONE"}}, "fields": "autofit.autofitType"}})
    reqs.append({"updateTextStyle": {"objectId": bid, "style": _font({"fontSize": _pt(12), "foregroundColor": {"opaqueColor": INK}}),
        "textRange": {"type": "ALL"}, "fields": "fontSize,weightedFontFamily,foregroundColor"}})
    if subtitle:
        reqs.append({"updateTextStyle": {"objectId": bid, "style": {"italic": True, "fontSize": _pt(11), "foregroundColor": {"opaqueColor": GREY}},
            "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": len(subtitle)}, "fields": "italic,fontSize,foregroundColor"}})
    off = (len(subtitle) + 1) if subtitle else 0
    groups, cur = [], None
    for kind, text in items:
        s0, e0 = off, off + len(text)
        if kind == "h":
            reqs.append({"updateTextStyle": {"objectId": bid, "style": {"bold": True, "foregroundColor": {"opaqueColor": INK}},
                "textRange": {"type": "FIXED_RANGE", "startIndex": s0, "endIndex": e0}, "fields": "bold,foregroundColor"}})
            reqs.append({"updateParagraphStyle": {"objectId": bid, "style": {"spaceAbove": _pt(6)},
                "textRange": {"type": "FIXED_RANGE", "startIndex": s0, "endIndex": e0}, "fields": "spaceAbove"}})
            if cur: groups.append(cur); cur = None
        else:
            cur = [s0, e0] if cur is None else [cur[0], e0]
        off = e0 + 1
    if cur: groups.append(cur)
    for g in groups:
        reqs.append({"createParagraphBullets": {"objectId": bid, "textRange": {"type": "FIXED_RANGE", "startIndex": g[0], "endIndex": g[1]},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})
    return sid

def add_callout(pid, slide_id, text, y=4360000):
    """Charcoal crystallization callout at the bottom of a slide."""
    box = _uid("cry")
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": [
        {"createShape": {"objectId": box, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": slide_id,
            "size": {"width": emu(8300000), "height": emu(640000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": y, "unit": "EMU"}}}},
        {"updateShapeProperties": {"objectId": box, "shapeProperties": {"shapeBackgroundFill": {"solidFill": {"color": CHARCOAL}}, "contentAlignment": "MIDDLE"},
            "fields": "shapeBackgroundFill.solidFill.color,contentAlignment"}},
        {"insertText": {"objectId": box, "text": text}},
        {"updateTextStyle": {"objectId": box, "style": _font({"bold": True, "fontSize": _pt(13), "foregroundColor": {"opaqueColor": INKBG}}),
            "textRange": {"type": "ALL"}, "fields": "bold,fontSize,weightedFontFamily,foregroundColor"}},
        {"updateParagraphStyle": {"objectId": box, "style": {"alignment": "CENTER"}, "textRange": {"type": "ALL"}, "fields": "alignment"}}]})
    return box

def add_table_slide(pid, index, title, headers, rows, subtitle=None, caption=None, title_layout="p6"):
    """caption = (text, [(substr,url),...]) or None. rows = list of list[str]; empty cells skipped."""
    sid, tid, tbl = _uid("s"), _uid("t"), _uid("tb")
    ncol, nrow = len(headers), len(rows) + 1
    reqs = [{"createSlide": {"objectId": sid, "insertionIndex": index, "slideLayoutReference": {"layoutId": title_layout},
        "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": tid}]}},
        {"insertText": {"objectId": tid, "text": title}},
        {"updateTextStyle": {"objectId": tid, "style": _font({"bold": True, "fontSize": _pt(24), "foregroundColor": {"opaqueColor": DARK2}}),
            "textRange": {"type": "ALL"}, "fields": "bold,fontSize,weightedFontFamily,foregroundColor"}}]
    ty = 1250000
    if subtitle:
        sb = _uid("sub")
        reqs += [{"createShape": {"objectId": sb, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": emu(8300000), "height": emu(380000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": 1080000, "unit": "EMU"}}}},
            {"insertText": {"objectId": sb, "text": subtitle}},
            {"updateTextStyle": {"objectId": sb, "style": _font({"italic": True, "fontSize": _pt(11), "foregroundColor": {"opaqueColor": GREY}}),
                "textRange": {"type": "ALL"}, "fields": "italic,fontSize,weightedFontFamily,foregroundColor"}}]
        ty = 1560000
    reqs.append({"createTable": {"objectId": tbl, "elementProperties": {"pageObjectId": sid,
        "size": {"width": emu(8300000), "height": emu(min(2900000, nrow * 420000))},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": ty, "unit": "EMU"}}, "rows": nrow, "columns": ncol}})
    reqs.append({"updateTableCellProperties": {"objectId": tbl, "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": ncol},
        "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": HDRBG}}}, "fields": "tableCellBackgroundFill.solidFill.color"}})
    if nrow > 1:
        reqs.append({"updateTableCellProperties": {"objectId": tbl, "tableRange": {"location": {"rowIndex": 1, "columnIndex": 0}, "rowSpan": nrow - 1, "columnSpan": ncol},
            "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": CELLBG}}}, "fields": "tableCellBackgroundFill.solidFill.color"}})
    for c, h in enumerate(headers):
        reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": 0, "columnIndex": c}, "text": h}})
        reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": 0, "columnIndex": c},
            "style": _font({"bold": True, "fontSize": _pt(9), "foregroundColor": {"opaqueColor": CELLTXT}}),
            "textRange": {"type": "ALL"}, "fields": "bold,fontSize,weightedFontFamily,foregroundColor"}})
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            if val == "" or val is None: continue
            reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c}, "text": str(val)}})
            reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c},
                "style": _font({"fontSize": _pt(9), "foregroundColor": {"opaqueColor": CELLTXT}}),
                "textRange": {"type": "ALL"}, "fields": "fontSize,weightedFontFamily,foregroundColor"}})
    if caption:
        txt, links = caption
        cap = _uid("cap")
        reqs += [{"createShape": {"objectId": cap, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": sid,
            "size": {"width": emu(8300000), "height": emu(360000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 420000, "translateY": 4760000, "unit": "EMU"}}}},
            {"insertText": {"objectId": cap, "text": txt}},
            {"updateTextStyle": {"objectId": cap, "style": _font({"italic": True, "fontSize": _pt(8), "foregroundColor": {"opaqueColor": GREY}}),
                "textRange": {"type": "ALL"}, "fields": "italic,fontSize,weightedFontFamily,foregroundColor"}}]
        for sub, u in (links or []):
            i = txt.find(sub)
            if i >= 0:
                reqs.append({"updateTextStyle": {"objectId": cap, "style": {"link": {"url": u}, "underline": True,
                    "foregroundColor": {"opaqueColor": LINKC}},
                    "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i + len(sub)}, "fields": "link,underline,foregroundColor"}})
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})
    return sid

def render(pid, index, out_path):
    ids = slide_ids(pid)
    tr = api("GET", f"/v1/presentations/{pid}/pages/{ids[index]}/thumbnail?thumbnailProperties.mimeType=PNG&thumbnailProperties.thumbnailSize=LARGE")
    cu = tr.get("body", {}).get("contentUrl")
    if cu:
        urllib.request.urlretrieve(cu, out_path)
    return out_path

def set_autofit_none(pid):
    """Disable shrink-on-overflow on every BODY so identical font sizes render uniformly. Safe to re-run."""
    d = api("GET", f"/v1/presentations/{pid}?fields=slides(pageElements(objectId,shape(placeholder(type))))")["body"]
    reqs = []
    for s in d["slides"]:
        for e in s.get("pageElements", []):
            if (e.get("shape", {}).get("placeholder") or {}).get("type") == "BODY":
                reqs.append({"updateShapeProperties": {"objectId": e["objectId"], "shapeProperties": {"autofit": {"autofitType": "NONE"}}, "fields": "autofit.autofitType"}})
    if reqs:
        api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})


# ===================== refined design system (v3) — supersedes the builders above =====================
# Restrained dark-editorial system: tight margins, small type, NO filled bars, transparent
# line-based tables with light text. Self-drawn boxes on the Blank layout (p12) for full control.
import re as _re
LM = 686000                       # left/right margin
CW = PAGE_W - 2 * LM              # content width  (7772000)
EYEY, TITY = 478000, 772000       # eyebrow / title baselines
MUTED = {"rgbColor": {"red": 0.365, "green": 0.424, "blue": 0.482}}      # #5d6c7b  muted bars/ticks
HAIR = {"rgbColor": {"red": 0.231, "green": 0.255, "blue": 0.278}}       # #3b4147  table hairlines / faint big numerals
FOOT = 4560000                    # keep content above the footer

def _txt(reqs, sid, x, y, w, h, text, size, color, *, bold=False, italic=False,
         align="START", line=None, before=None, upper=False, font=FONT):
    bid = _uid("tx"); s = text.upper() if upper else text
    reqs.append({"createShape": {"objectId": bid, "shapeType": "TEXT_BOX", "elementProperties": {
        "pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "EMU"}}}})
    reqs.append({"insertText": {"objectId": bid, "text": s}})
    reqs.append({"updateShapeProperties": {"objectId": bid, "shapeProperties": {"autofit": {"autofitType": "NONE"}}, "fields": "autofit.autofitType"}})
    reqs.append({"updateTextStyle": {"objectId": bid, "style": {"fontSize": _pt(size),
        "foregroundColor": {"opaqueColor": color}, "bold": bold, "italic": italic, "weightedFontFamily": {"fontFamily": font}},
        "textRange": {"type": "ALL"}, "fields": "fontSize,foregroundColor,bold,italic,weightedFontFamily"}})
    ps, pf = {"alignment": align}, "alignment"
    if line is not None: ps["lineSpacing"] = line; pf += ",lineSpacing"
    if before is not None: ps["spaceAbove"] = _pt(before); pf += ",spaceAbove"
    reqs.append({"updateParagraphStyle": {"objectId": bid, "style": ps, "textRange": {"type": "ALL"}, "fields": pf}})
    return bid

def _bar(reqs, sid, x, y, w, h, color):
    rid = _uid("bar")
    reqs.append({"createShape": {"objectId": rid, "shapeType": "RECTANGLE", "elementProperties": {
        "pageObjectId": sid, "size": {"width": emu(max(int(w), 1)), "height": emu(h)},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "EMU"}}}})
    reqs.append({"updateShapeProperties": {"objectId": rid, "shapeProperties": {
        "shapeBackgroundFill": {"solidFill": {"color": color}}, "outline": {"propertyState": "NOT_RENDERED"}},
        "fields": "shapeBackgroundFill.solidFill.color,outline.propertyState"}})
    return rid

def _slide(reqs, index):
    sid = _uid("s")
    reqs.append({"createSlide": {"objectId": sid, "insertionIndex": index, "slideLayoutReference": {"layoutId": "p12"}}})
    return sid

def _head(reqs, sid, eyebrow, title):
    if eyebrow: _txt(reqs, sid, LM, EYEY, CW, 250000, eyebrow, 10, GOLD, bold=True, upper=True)
    _txt(reqs, sid, LM, TITY, CW, 700000, title, 22, DARK2, bold=True, line=104)

def _commit(pid, reqs):
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": reqs})

def add_cover(pid, title, subtitle, logo_url=None, blank_layout="p12"):
    reqs = []; sid = _slide(reqs, 0)
    if logo_url:
        lw = 1120000
        reqs.append({"createImage": {"objectId": _uid("logo"), "url": logo_url, "elementProperties": {
            "pageObjectId": sid, "size": {"width": emu(lw), "height": emu(lw)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": (PAGE_W - lw)//2, "translateY": 640000, "unit": "EMU"}}}})
    _txt(reqs, sid, LM, 2230000, CW, 1000000, title, 33, DARK2, bold=True, align="CENTER", line=104)
    rw = 440000; _bar(reqs, sid, (PAGE_W - rw)//2, 3320000, rw, 26000, GOLD)
    _txt(reqs, sid, LM, 3520000, CW, 480000, subtitle, 13, GREY, align="CENTER")
    _commit(pid, reqs); return sid

def add_text_slide(pid, index, title, items, subtitle=None, eyebrow=None, body_layout="p12"):
    reqs = []; sid = _slide(reqs, index); _head(reqs, sid, eyebrow, title)
    y = 1760000
    if subtitle: _txt(reqs, sid, LM, 1480000, CW, 320000, subtitle, 12, GREY, italic=True); y = 1980000
    bid = _uid("body"); body = "\n".join(it[1] for it in items)
    reqs.append({"createShape": {"objectId": bid, "shapeType": "TEXT_BOX", "elementProperties": {
        "pageObjectId": sid, "size": {"width": emu(CW), "height": emu(FOOT - y)},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": LM, "translateY": y, "unit": "EMU"}}}})
    reqs.append({"insertText": {"objectId": bid, "text": body}})
    reqs.append({"updateShapeProperties": {"objectId": bid, "shapeProperties": {"autofit": {"autofitType": "NONE"}}, "fields": "autofit.autofitType"}})
    reqs.append({"updateTextStyle": {"objectId": bid, "style": {"fontSize": _pt(11.5), "foregroundColor": {"opaqueColor": INK}, "weightedFontFamily": {"fontFamily": FONT}},
        "textRange": {"type": "ALL"}, "fields": "fontSize,foregroundColor,weightedFontFamily"}})
    reqs.append({"updateParagraphStyle": {"objectId": bid, "style": {"lineSpacing": 116, "spaceBelow": _pt(4)}, "textRange": {"type": "ALL"}, "fields": "lineSpacing,spaceBelow"}})
    off, groups, cur = 0, [], None
    for kind, text in items:
        s0, e0 = off, off + len(text)
        if kind == "h":
            reqs.append({"updateTextStyle": {"objectId": bid, "style": {"bold": True, "foregroundColor": {"opaqueColor": DARK2}, "fontSize": _pt(12)},
                "textRange": {"type": "FIXED_RANGE", "startIndex": s0, "endIndex": e0}, "fields": "bold,foregroundColor,fontSize"}})
            reqs.append({"updateParagraphStyle": {"objectId": bid, "style": {"spaceAbove": _pt(10)},
                "textRange": {"type": "FIXED_RANGE", "startIndex": s0, "endIndex": e0}, "fields": "spaceAbove"}})
            if cur: groups.append(cur); cur = None
        else:
            cur = [s0, e0] if cur is None else [cur[0], e0]
        off = e0 + 1
    if cur: groups.append(cur)
    for g in groups:
        reqs.append({"createParagraphBullets": {"objectId": bid, "textRange": {"type": "FIXED_RANGE", "startIndex": g[0], "endIndex": g[1]}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    _commit(pid, reqs); return sid

def add_callout(pid, slide_id, text, y=4040000):
    """Crystallized thesis: short gold tick + bold line. NO filled band."""
    reqs = []; _bar(reqs, slide_id, LM, y, 440000, 22000, GOLD)
    _txt(reqs, slide_id, LM, y + 92000, CW, 440000, text, 14, DARK2, bold=True, line=112)
    _commit(pid, reqs); return slide_id

def _isnum(v): return bool(_re.fullmatch(r"[-+]?[$£€]?\d[\d,]*\.?\d*%?", str(v).strip()))

def add_table_slide(pid, index, title, headers, rows, subtitle=None, caption=None, eyebrow=None, title_layout="p12"):
    reqs = []; sid = _slide(reqs, index); _head(reqs, sid, eyebrow, title)
    ty = 1700000
    if subtitle: _txt(reqs, sid, LM, 1480000, CW, 320000, subtitle, 12, GREY, italic=True); ty = 1940000
    ncol, nrow = len(headers), len(rows) + 1; tbl = _uid("tb")
    aligns = []
    for c in range(ncol):
        vals = [rows[r][c] for r in range(len(rows)) if c < len(rows[r]) and rows[r][c] not in ("", None)]
        aligns.append("END" if vals and sum(_isnum(v) for v in vals) >= len(vals)/2 else "START")
    reqs.append({"createTable": {"objectId": tbl, "elementProperties": {"pageObjectId": sid,
        "size": {"width": emu(CW), "height": emu(min(2700000, nrow*420000))},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": LM, "translateY": ty, "unit": "EMU"}}, "rows": nrow, "columns": ncol}})
    full = {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": nrow, "columnSpan": ncol}
    reqs.append({"updateTableCellProperties": {"objectId": tbl, "tableRange": full,
        "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": INKBG}}}, "fields": "tableCellBackgroundFill.solidFill.color"}})
    for pos, col, wt in [("ALL", INKBG, 1), ("INNER_HORIZONTAL", HAIR, 1)]:
        reqs.append({"updateTableBorderProperties": {"objectId": tbl, "borderPosition": pos, "tableRange": full,
            "tableBorderProperties": {"tableBorderFill": {"solidFill": {"color": col}}, "weight": _pt(wt), "dashStyle": "SOLID"},
            "fields": "tableBorderFill.solidFill.color,weight,dashStyle"}})
    reqs.append({"updateTableBorderProperties": {"objectId": tbl, "borderPosition": "BOTTOM",
        "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": ncol},
        "tableBorderProperties": {"tableBorderFill": {"solidFill": {"color": GOLD}}, "weight": _pt(1.5), "dashStyle": "SOLID"},
        "fields": "tableBorderFill.solidFill.color,weight,dashStyle"}})
    for c, h in enumerate(headers):
        reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": 0, "columnIndex": c}, "text": h.upper()}})
        reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": 0, "columnIndex": c},
            "style": {"bold": True, "fontSize": _pt(9), "foregroundColor": {"opaqueColor": GOLD}, "weightedFontFamily": {"fontFamily": FONT}},
            "textRange": {"type": "ALL"}, "fields": "bold,fontSize,foregroundColor,weightedFontFamily"}})
        reqs.append({"updateParagraphStyle": {"objectId": tbl, "cellLocation": {"rowIndex": 0, "columnIndex": c}, "style": {"alignment": aligns[c]}, "textRange": {"type": "ALL"}, "fields": "alignment"}})
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            if val in ("", None): continue
            reqs.append({"insertText": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c}, "text": str(val)}})
            reqs.append({"updateTextStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c},
                "style": {"fontSize": _pt(10), "foregroundColor": {"opaqueColor": INK}, "weightedFontFamily": {"fontFamily": FONT}},
                "textRange": {"type": "ALL"}, "fields": "fontSize,foregroundColor,weightedFontFamily"}})
            reqs.append({"updateParagraphStyle": {"objectId": tbl, "cellLocation": {"rowIndex": r, "columnIndex": c}, "style": {"alignment": aligns[c]}, "textRange": {"type": "ALL"}, "fields": "alignment"}})
    if caption:
        txt, links = caption; cid = _txt(reqs, sid, LM, 4430000, CW, 300000, txt, 8.5, GREY, italic=True)
        for sub, u in (links or []):
            i = txt.find(sub)
            if i >= 0:
                reqs.append({"updateTextStyle": {"objectId": cid, "style": {"link": {"url": u}, "underline": True, "foregroundColor": {"opaqueColor": LINKC}},
                    "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i+len(sub)}, "fields": "link,underline,foregroundColor"}})
    _commit(pid, reqs); return sid

def add_section(pid, index, num, eyebrow, title):
    reqs = []; sid = _slide(reqs, index)
    _txt(reqs, sid, PAGE_W-3300000, 760000, 2700000, 2700000, num, 150, HAIR, bold=True, align="END")
    _txt(reqs, sid, LM, 2040000, CW, 280000, eyebrow, 11, GOLD, bold=True, upper=True)
    _bar(reqs, sid, LM, 2410000, 440000, 28000, GOLD)
    _txt(reqs, sid, LM, 2560000, CW-2600000, 1200000, title, 31, DARK2, bold=True, line=104)
    _commit(pid, reqs); return sid

def add_stat(pid, index, eyebrow, number, label, support=None):
    reqs = []; sid = _slide(reqs, index)
    _txt(reqs, sid, LM, EYEY, CW, 250000, eyebrow, 10, GOLD, bold=True, upper=True)
    _txt(reqs, sid, LM, 1460000, CW, 1500000, number, 92, GOLD, bold=True, line=100)
    _bar(reqs, sid, LM, 3160000, 440000, 26000, GOLD)
    _txt(reqs, sid, LM, 3340000, CW, 500000, label, 16, DARK2, bold=True)
    if support: _txt(reqs, sid, LM, 3820000, CW, 560000, support, 11.5, GREY, line=122)
    _commit(pid, reqs); return sid

def add_kpi_row(pid, index, title, kpis, eyebrow=None, subtitle=None):
    """kpis = [(number, label), ...] up to 4."""
    reqs = []; sid = _slide(reqs, index); _head(reqs, sid, eyebrow, title)
    if subtitle: _txt(reqs, sid, LM, 1480000, CW, 320000, subtitle, 12, GREY, italic=True)
    n = len(kpis); gap = 240000; colw = (CW - gap*(n-1)) // n; y = 2360000
    for i, (number, label) in enumerate(kpis):
        x = LM + i*(colw+gap)
        _bar(reqs, sid, x, y, 300000, 26000, GOLD)
        _txt(reqs, sid, x, y+150000, colw, 760000, number, 32, DARK2, bold=True, line=100)
        _txt(reqs, sid, x, y+860000, colw, 520000, label, 9.5, GREY, upper=True, line=120)
    _commit(pid, reqs); return sid

def add_bars(pid, index, title, data, eyebrow=None, subtitle=None, unit=""):
    """data = [(label, value, highlight_bool), ...]"""
    reqs = []; sid = _slide(reqs, index); _head(reqs, sid, eyebrow, title)
    if subtitle: _txt(reqs, sid, LM, 1480000, CW, 320000, subtitle, 12, GREY, italic=True)
    maxv = max((v for _, v, _ in data), default=1) or 1
    labelw, valw = 2100000, 1000000; barmax = CW - labelw - valw; x0 = LM + labelw
    y0 = 2060000; rowh = min(600000, (FOOT - y0)//max(len(data), 1)); bh = 188000
    for i, (label, value, hi) in enumerate(data):
        y = y0 + i*rowh
        _txt(reqs, sid, LM, y - 28000, labelw-120000, 340000, label, 10.5, INK)
        bw = int(barmax * (value/maxv))
        _bar(reqs, sid, x0, y, bw, bh, GOLD if hi else MUTED)
        vstr = f"{value:,}{unit}" if isinstance(value, (int, float)) else str(value)
        _txt(reqs, sid, x0 + bw + 110000, y - 34000, valw, 300000, vstr, 11, DARK2, bold=True)
    _commit(pid, reqs); return sid

def add_statement(pid, index, text, attrib=None, eyebrow=None):
    reqs = []; sid = _slide(reqs, index)
    if eyebrow: _txt(reqs, sid, LM, EYEY, CW, 250000, eyebrow, 10, GOLD, bold=True, upper=True)
    _bar(reqs, sid, LM, 1660000, 440000, 28000, GOLD)
    _txt(reqs, sid, LM, 1840000, CW, 2000000, text, 27, DARK2, bold=True, line=122)
    if attrib: _txt(reqs, sid, LM, 3980000, CW, 340000, attrib, 12, GREY)
    _commit(pid, reqs); return sid

# ---- Minto / dense-text structures ----
def _bullets(reqs, sid, x, y, w, h, items, size=10.5, color=INK, line=120, gap=4):
    """A standalone bulleted text box (each item one bullet line)."""
    bid = _uid("bl"); body = "\n".join(items)
    reqs.append({"createShape": {"objectId": bid, "shapeType": "TEXT_BOX", "elementProperties": {
        "pageObjectId": sid, "size": {"width": emu(w), "height": emu(h)},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "EMU"}}}})
    reqs.append({"insertText": {"objectId": bid, "text": body}})
    reqs.append({"updateShapeProperties": {"objectId": bid, "shapeProperties": {"autofit": {"autofitType": "NONE"}}, "fields": "autofit.autofitType"}})
    reqs.append({"updateTextStyle": {"objectId": bid, "style": {"fontSize": _pt(size), "foregroundColor": {"opaqueColor": color}, "weightedFontFamily": {"fontFamily": FONT}},
        "textRange": {"type": "ALL"}, "fields": "fontSize,foregroundColor,weightedFontFamily"}})
    reqs.append({"updateParagraphStyle": {"objectId": bid, "style": {"lineSpacing": line, "spaceBelow": _pt(gap)}, "textRange": {"type": "ALL"}, "fields": "lineSpacing,spaceBelow"}})
    reqs.append({"createParagraphBullets": {"objectId": bid, "textRange": {"type": "ALL"}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    return bid

def add_columns(pid, index, title, columns, eyebrow=None, subtitle=None):
    """Minto grouped arguments / pillars. columns = [(header, [bullet, ...]), ...]  (2-3 columns)."""
    reqs = []; sid = _slide(reqs, index); _head(reqs, sid, eyebrow, title)
    y0 = 1780000
    if subtitle: _txt(reqs, sid, LM, 1480000, CW, 320000, subtitle, 12, GREY, italic=True); y0 = 2020000
    n = len(columns); gap = 300000; colw = (CW - gap*(n-1)) // n
    for i, (hdr, bullets) in enumerate(columns):
        x = LM + i*(colw+gap)
        _bar(reqs, sid, x, y0, 300000, 24000, GOLD)
        _txt(reqs, sid, x, y0+120000, colw, 560000, hdr, 13, DARK2, bold=True, line=110)
        _bullets(reqs, sid, x, y0+720000, colw, FOOT-(y0+720000), bullets)
    _commit(pid, reqs); return sid

def add_pyramid(pid, index, governing, supports, eyebrow=None):
    """Minto top-down: governing thought (answer first) -> 3 supporting arguments.
    supports = [(label, detail), ...] (3)."""
    reqs = []; sid = _slide(reqs, index)
    if eyebrow: _txt(reqs, sid, LM, EYEY, CW, 250000, eyebrow, 10, GOLD, bold=True, upper=True)
    _bar(reqs, sid, LM, 820000, 440000, 28000, GOLD)
    _txt(reqs, sid, LM, 1000000, CW, 1000000, governing, 20, DARK2, bold=True, line=118)
    n = len(supports); gap = 300000; colw = (CW - gap*(n-1)) // n; y = 2640000
    _bar(reqs, sid, LM, y-150000, CW, 8000, HAIR)  # thin divider above supports
    for i, (label, detail) in enumerate(supports):
        x = LM + i*(colw+gap)
        _txt(reqs, sid, x, y, colw, 380000, f"0{i+1}", 17, GOLD, bold=True)
        _txt(reqs, sid, x, y+440000, colw, 520000, label, 13, DARK2, bold=True, line=112)
        _txt(reqs, sid, x, y+980000, colw, 1000000, detail, 10.5, GREY, line=126)
    _commit(pid, reqs); return sid

# ---- native pie / donut chart (Google Sheets chart embedded into the slide) ----
def _sheets(method, path, body=None):
    return call({"action": "google_api", "api": "sheets", "method": method, "path": path, "body": body})

_chart_ss = {}  # pid -> companion spreadsheetId (one per deck)
_CTHEME = [
    ("TEXT", {"red": 1, "green": 1, "blue": 1}), ("BACKGROUND", {"red": 0.090, "green": 0.098, "blue": 0.094}),
    ("ACCENT1", {"red": 1.0, "green": 0.769, "blue": 0.302}), ("ACCENT2", {"red": 0.459, "green": 0.525, "blue": 0.588}),
    ("ACCENT3", {"red": 0.365, "green": 0.424, "blue": 0.482}), ("ACCENT4", {"red": 1.0, "green": 0.851, "blue": 0.561}),
    ("ACCENT5", {"red": 0.604, "green": 0.655, "blue": 0.706}), ("ACCENT6", {"red": 0.231, "green": 0.255, "blue": 0.278}),
    ("LINK", {"red": 0.521, "green": 0.717, "blue": 0.921})]

def _ensure_chart_ss(pid):
    if pid in _chart_ss: return _chart_ss[pid]
    r = _sheets("POST", "/v4/spreadsheets", {"properties": {"title": "deck chart data (auto)"}})
    ssid = r["body"]["spreadsheetId"]
    _sheets("POST", f"/v4/spreadsheets/{ssid}:batchUpdate", {"requests": [{"updateSpreadsheetProperties": {
        "properties": {"spreadsheetTheme": {"primaryFontFamily": "Poppins",
            "themeColors": [{"colorType": t, "color": {"rgbColor": c}} for t, c in _CTHEME]}},
        "fields": "spreadsheetTheme"}}]})
    _chart_ss[pid] = ssid; return ssid

def add_pie(pid, index, title, data, eyebrow=None, subtitle=None, donut=True, caption=None):
    """Native pie/donut chart. data = [(label, value), ...]. Themed to the dark palette."""
    ssid = _ensure_chart_ss(pid)
    # new tab for this chart's data
    add = _sheets("POST", f"/v4/spreadsheets/{ssid}:batchUpdate", {"requests": [{"addSheet": {"properties": {"title": f"d{int(time.time()*1000)%100000}"}}}]})
    tab = add["body"]["replies"][0]["addSheet"]["properties"]; tab_id, tab_name = tab["sheetId"], tab["title"]
    vals = [["Category", "Value"]] + [[l, v] for l, v in data]
    _sheets("PUT", f"/v4/spreadsheets/{ssid}/values/{urllib.parse.quote(tab_name)}!A1?valueInputOption=RAW", {"values": vals})
    nr = len(data) + 1
    src = lambda c0, c1: {"sourceRange": {"sources": [{"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": nr, "startColumnIndex": c0, "endColumnIndex": c1}]}}
    spec = {"title": "", "fontName": "Poppins", "backgroundColorStyle": {"rgbColor": {"red": 0.090, "green": 0.098, "blue": 0.094}},
        "pieChart": {"legendPosition": "RIGHT_LEGEND", "pieHole": 0.56 if donut else 0.0, "threeDimensional": False,
            "domain": src(0, 1), "series": src(1, 2)}}
    ch = _sheets("POST", f"/v4/spreadsheets/{ssid}:batchUpdate", {"requests": [{"addChart": {"chart": {"spec": spec,
        "position": {"overlayPosition": {"anchorCell": {"sheetId": tab_id, "rowIndex": 0, "columnIndex": 4}, "widthPixels": 640, "heightPixels": 400}}}}}]})
    chart_id = ch["body"]["replies"][0]["addChart"]["chart"]["chartId"]
    reqs = []; sid = _slide(reqs, index); _head(reqs, sid, eyebrow, title)
    if subtitle: _txt(reqs, sid, LM, 1480000, CW, 320000, subtitle, 12, GREY, italic=True)
    if caption:
        txt, links = caption; cid = _txt(reqs, sid, LM, 4430000, CW, 300000, txt, 8.5, GREY, italic=True)
        for sub, u in (links or []):
            j = txt.find(sub)
            if j >= 0:
                reqs.append({"updateTextStyle": {"objectId": cid, "style": {"link": {"url": u}, "underline": True, "foregroundColor": {"opaqueColor": LINKC}},
                    "textRange": {"type": "FIXED_RANGE", "startIndex": j, "endIndex": j+len(sub)}, "fields": "link,underline,foregroundColor"}})
    _commit(pid, reqs)
    cy = 1980000
    api("POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": [{"createSheetsChart": {"objectId": _uid("chart"),
        "spreadsheetId": ssid, "chartId": chart_id, "linkingMode": "NOT_LINKED_IMAGE",
        "elementProperties": {"pageObjectId": sid, "size": {"width": emu(6900000), "height": emu(2500000)},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": LM, "translateY": cy, "unit": "EMU"}}}}]})
    return sid
