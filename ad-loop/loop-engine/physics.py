#!/usr/bin/env python3
"""The physics cascade — filters A, B, C, D as importable functions.

Every threshold below was calibrated in a prior run, and is either

  (i)   taken from a calibrated shadow/field probe on built plates
  (ii)  derived from a real-reference photograph (contact/ambient ratio ~0.51 on the
        real photograph; per-row SD minimum 3.02 on a real photographed ground, where
        a mathematically flat generated field measures 0.00)
  (iii) measured live off the real reference object at the SAME delivery pixel scale
        (filter D calibrates against the real label, not against a guess).

NOTHING here is tuned to make plates survive. Every raw number is returned per plate so
the gate can be re-drawn by anyone reading the table.

  A. row-luminance variance floor   -- kills mathematically flat fields
  B. shadow probe at the object base -- contact-darkest, monotonic, directional
  C. hue preservation in the umbra
  D. print legibility on the object  (2.18x downsample = "generative mush")

Single renders structurally almost never fail A or C. Composite-era checks stay for
composites; single-render triage weight goes to B (shadow behaviour) and D (micro-detail).

A crop is a physics decision and must be re-probed as one — re-run the whole
cascade on the shipped window with thresholds untouched and only the object box
re-normalised. That is what makes "the crop did not break the light story" a measurement
rather than a hope.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
from common import boxblur, red_mask  # noqa: E402


DELIV_W, DELIV_H = config.CANVAS_W, config.CANVAS_H   # 4:5 delivery canvas

# ---- calibrated constants (provenance in the module docstring) ---------------
SD_FLOOR = 3.02                        # real photographed ground: per-row SD minimum
REAL_CONTACT_RATIO = 0.51              # measured on the real reference photograph
CONTACT_LO, CONTACT_HI = 0.25, 0.75
MONO_TOL = 1.5                         # levels; built plate used 0.01 (no grain)
THROW_MIN = 0.010                      # frac of bag width; a symmetric pool is the fail
HUE_RETAIN = 0.50
HUE_ABS_MIN = 0.02
MAX_DOWNSAMPLE = 2.18                  # calibrated kill value
HP_RATIO_MIN = 0.60

# Probe offsets, as fractions of the measured object WIDTH so the geometry transfers
# to any plate scale. (Calibrated as offs=[0,2,8,20,45,75,115,165,225,300] px on a
# field plate whose object was 1050px wide.)
OFF_FRAC = [0.0, 0.0019, 0.0076, 0.019, 0.043, 0.071, 0.110, 0.157, 0.214, 0.286]

# Declared window side per prompt variant -> which side of the footprint the pool must be
# DARKER on (light from the left throws the shadow to the right). The default below is
# an example map for five prompt variants A-E.
# SAMPLING CHANGE: this is a caller-supplied map, because it encodes one experiment's
# prompt set and nothing else. It is RECORDED, never gated — the gate is
# b_direction_ok, which reads the measured lateral gradient. A variant absent from the map
# yields prompt_light_ok=None rather than a KeyError.
DARK_SIDE_DEFAULT = {"A": "R", "B": "L", "C": "R", "D": "L", "E": "R"}


# ---------------------------------------------------------------- reference object
def ref_pack_for(slug: str) -> Path:
    """Resolve the client's REFERENCE OBJECT — the real photograph of the thing the
    generated plates are pretending to be. Filter D calibrates against it.

    The client layer names it: <brand>/pack-reference.txt holds one line, a path
    absolute or relative to the brand dir. There is deliberately NO filename heuristic:
    a heuristic here would silently calibrate filter D against the wrong object and
    every downsample number after that would be wrong but plausible.

    (Typical value: product-images/<sku>-pack-cutout.png, an alpha-matted real photo.)
    """
    brand = config.brand_dir(slug)
    ptr = brand / "pack-reference.txt"
    if not ptr.exists():
        raise FileNotFoundError(
            f"no reference object declared for '{slug}'. Write the path of the real pack "
            f"shot into {ptr}, or pass ref_pack= / --ref explicitly.")
    raw = ptr.read_text().strip().splitlines()[0].strip()
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = brand / p
    if not p.exists():
        raise FileNotFoundError(f"{ptr} points at {p}, which does not exist")
    return p


_REF_CACHE: dict[str, dict] = {}


def ref_band_metrics(ref_pack) -> dict:
    """Measure the REAL reference shot: object alpha height, printed band height, and the
    band's pixels (resampled per-plate by filter D to the same delivery height)."""
    key = str(ref_pack)
    if key in _REF_CACHE:
        return _REF_CACHE[key]
    im = Image.open(ref_pack).convert("RGBA")
    a = np.array(im)
    alpha = a[..., 3] > 8
    ys, xs = np.where(alpha)
    bag_h = int(ys.max() - ys.min() + 1)
    rgb = a[..., :3].astype(float)
    m = red_mask(rgb) & alpha
    rows = m.sum(1).astype(float)
    peak = int(np.argmax(rows))
    thr = rows[peak] * 0.40
    y0 = peak
    while y0 > 0 and rows[y0 - 1] >= thr:
        y0 -= 1
    y1 = peak
    while y1 < len(rows) - 1 and rows[y1 + 1] >= thr:
        y1 += 1
    colfill = m[y0:y1 + 1].mean(0)
    xs2 = np.where(colfill >= 0.55)[0]
    band = a[y0:y1 + 1, xs2.min():xs2.max() + 1, :3]
    out = dict(bag_h=bag_h, band=band, band_h=y1 - y0 + 1, band_w=band.shape[1],
               bag_bottom_below_band=int(ys.max() - y1))
    _REF_CACHE[key] = out
    return out


def ref_geom_ratio(ref_pack) -> float:
    """(object bottom - band bottom) / band width, measured on the REAL shot.
    Used to bound the contact-seam search so a board edge cannot win it."""
    r = ref_band_metrics(ref_pack)
    return r["bag_bottom_below_band"] / r["band_w"]


# ---------------------------------------------------------------- localisation
def locate_bag(rgb, name, boxes):
    """Localisation is a PERCEPTION problem and is done by a vision model
    (vision.py localise), not by colour heuristics. Two colour heuristics were
    tried and both mis-locked: a saturation mask cannot separate the brand band
    from similar-coloured surfaces, and a channel-difference mask locks onto other
    label panels when the package is tilted or backlit. The vision pass returns the
    package box, the label band box and the CONTACT LINE; every physics number below is
    still computed on pixels by this script.

    `boxes` is the parsed vision boxes.json (SAMPLING CHANGE: it is an argument, not a
    module global read off disk, so a crop can be probed with a re-normalised box
    without mutating module state).
    """
    b = (boxes or {}).get(name)
    if not b or "bag" not in b or b.get("error"):
        return None
    H, W = rgb.shape[:2]
    g = b["bag"]
    bx0, bx1 = int(g["x0"] * W), int(g["x1"] * W)
    by0 = int(g["y0"] * H)
    floor = int(float(b["base_y"]) * H)
    rb = b.get("red_band") or {}
    band_y0 = int(rb.get("y0", g["y0"]) * H)
    band_y1 = int(rb.get("y1", g["y0"]) * H)
    band_x0 = int(rb.get("x0", g["x0"]) * W)
    band_x1 = int(rb.get("x1", g["x1"]) * W)
    fx0 = int(float(b.get("base_x0", g["x0"])) * W)
    fx1 = int(float(b.get("base_x1", g["x1"])) * W)
    if fx1 - fx0 < (bx1 - bx0) * 0.25:
        fx0, fx1 = bx0, bx1
    bw = max(40, bx1 - bx0)
    cx0, cx1 = fx0 + int((fx1 - fx0) * 0.25), fx0 + int((fx1 - fx0) * 0.75)
    if cx1 - cx0 < 20:
        cx0, cx1 = bx0 + int(bw * 0.25), bx0 + int(bw * 0.75)
    # The vision pass reports where the package visually STOPS, which can sit a little
    # BELOW the contact shadow (anything piled against the base reads as package).
    # Vision therefore supplies
    # the search REGION and the pixels supply the seam: the darkest row of the
    # smoothed footprint-column profile within [-0.12, +0.06] * bag width of it.
    lumc = rgb[:, cx0:cx1].mean(2).mean(1)
    k = max(3, bw // 60)
    lumc = np.convolve(lumc, np.ones(k) / k, "same")
    lo = max(4, floor - int(bw * 0.12))
    hi = min(H - 6, floor + int(bw * 0.06))
    vision_floor = floor
    if hi - lo > 8:
        floor = lo + int(np.argmin(lumc[lo:hi]))
    return dict(vision_floor=vision_floor,
                bx0=bx0, bx1=fx1 if fx1 > bx0 else bx1, bw=bw, band_y0=band_y0,
                band_y1=max(band_y1, band_y0 + 4), band_x0=band_x0, band_x1=band_x1,
                bag_top=by0, floor=min(floor, H - 8), cx0=cx0, cx1=cx1,
                fx0=fx0, fx1=fx1,
                occluded=bool(b.get("base_occluded")),
                light=str(b.get("light_from", "")),
                in_frame=bool(b.get("bag_fully_in_frame", True)))


def renormalise_box(box: dict, src_w: float, crop_w: float) -> dict:
    """Re-normalise a vision box for a narrower CROP of the same plate.

    x fractions grow when the frame narrows; y fractions are unchanged. This is the ONLY
    substitution allowed when re-probing a delivered crop — thresholds never move.
    """
    import copy
    k = src_w / float(crop_w)
    b = copy.deepcopy(box)
    for key in ("bag", "red_band"):
        if key in b and b[key]:
            b[key]["x0"] *= k
            b[key]["x1"] *= k
    for key in ("base_x0", "base_x1"):
        if key in b:
            b[key] *= k
    return b


# ---------------------------------------------------------------- filter A
def filter_a(rgb, bag):
    """Row-luminance variance floor on pure-ground rows (rows entirely above the bag)."""
    lum = rgb.mean(2)
    H = lum.shape[0]
    top = max(8, int(bag["band_y0"] * 0.10)) if bag else 8
    bot = max(top + 20, bag["band_y0"] - 10) if bag else H // 4
    band = lum[top:bot]
    if band.shape[0] < 10:
        band = lum[: H // 5]
    sd = band.std(axis=1)
    lat = float(lum[:, : lum.shape[1] // 4].mean() - lum[:, -lum.shape[1] // 4:].mean())
    return dict(sd_min=float(sd.min()), sd_mean=float(sd.mean()),
                lateral_LR=lat, pass_=bool(sd.min() >= SD_FLOOR))


# ---------------------------------------------------------------- filter B
def filter_b(rgb, bag):
    lum = rgb.mean(2)
    H, W = lum.shape
    bw, floor = bag["bw"], bag["floor"]
    fx0, fx1 = bag["fx0"], bag["fx1"]
    c = (bag["cx0"] + bag["cx1"]) // 2
    # The built plate's probe averaged 24px-wide patches on a smooth synthetic
    # ground. A photograph carries real surface texture (grain, drag marks, wood),
    # so the patch is widened to the bag's central 50% of columns -- the same strip
    # the seam was found in. Height stays thin so the falloff is not smeared.
    half = max(6, (bag["cx1"] - bag["cx0"]) // 2)
    offs = [int(round(f * bw)) for f in OFF_FRAC]

    def patch(cy, cx, hh=None):
        hh = hh or max(3, int(bw * 0.008))
        y0, y1 = max(0, cy - hh), min(H, cy + hh + 1)
        x0, x1 = max(0, cx - half), min(W, cx + half + 1)
        return float(lum[y0:y1, x0:x1].mean())

    prof = [patch(min(floor + o, H - 2), c) for o in offs]
    # CONTACT RATIO. The original probe divided the seam by ground sampled 0.286*bw LATERALLY.
    # These plates carry a real lateral illumination gradient (one window, by
    # construction), so a lateral denominator measures the gradient, not the
    # shadow. Denominator moved to the SAME COLUMN at the SAME 0.286*bw distance
    # (prof[-1]) -- identical distance, identical illumination. The lateral
    # reading is still computed and reported so the substitution is auditable.
    ratio = prof[0] / prof[-1] if prof[-1] > 1 else 9.9
    ay = min(floor + int(bw * 0.20), H - 8)
    gap = int(bw * 0.36)
    side = "L" if fx0 - gap > W - (fx1 + gap) else "R"
    ax = max(int(bw * 0.05), fx0 - gap) if side == "L" else min(W - int(bw * 0.05) - 1, fx1 + gap)
    amb = patch(ay, ax, hh=max(6, int(bw * 0.02)))

    # the seam must be a genuine local MINIMUM, not a flat spot: at least 1.0
    # level below the profile 0.05*bw above it and 0.05*bw below it.
    up = patch(max(4, floor - int(bw * 0.05)), c)
    dn = patch(min(H - 2, floor + int(bw * 0.05)), c)
    depth = min(up, dn) - prof[0]
    near_seam = bool(depth >= 1.0)
    darkest_off = 0

    # Monotonic recovery is gated over the FALLOFF range (the first 8 offsets, out
    # to 0.157*bw). The built plate could use all ten because its ground was an
    # infinite flat synthetic field; on a photograph the outer two offsets
    # (0.214/0.286*bw below the seam) routinely land on a different plane or a
    # second object. Both numbers are reported so the effect of the cut is visible.
    # Monotonicity is a claim about the SHADOW's recovery, so it is gated over the
    # recovery range only: from the seam out to the first offset that has reached
    # 95% of the profile's peak. Past that the shadow contributes nothing and the
    # numbers are the tabletop's own texture and the scene's lighting gradient --
    # the built plate had neither, which is why it could gate all ten offsets at a
    # tolerance of 0.01. Both the gated range and the full-profile result are
    # reported so the effect of the cut is visible per plate.
    pk = max(prof)
    rec = next((i for i, v in enumerate(prof) if v >= 0.95 * pk), len(prof) - 1)
    rec = max(rec, 3)
    mono = all(prof[i] <= prof[i + 1] + MONO_TOL for i in range(rec))
    mono_full = all(prof[i] <= prof[i + 1] + MONO_TOL for i in range(len(prof) - 1))

    # DIRECTIONALITY as the shadow mask's CENTROID THROW, not an L/R patch pair:
    # in a two-object scene the ground beside the footprint is often the second
    # object (the strip beside the footprint can land on a second object). The strip below the seam is
    # thresholded at its own darkest 30%, and the centroid of that mask is compared
    # to the footprint centre. Signed, normalised by bag width.
    # (a "symmetric pool" is usually an UNSIGNED distance — sign it.)
    sy0, sy1 = min(floor + 2, H - 4), min(floor + int(bw * 0.09), H - 2)
    sx0, sx1 = max(0, fx0 - int(bw * 0.18)), min(W, fx1 + int(bw * 0.18))
    strip = lum[sy0:sy1, sx0:sx1]
    throw = 0.0
    if strip.size > 100:
        thr = np.percentile(strip, 30)
        ys_, xs_ = np.where(strip <= thr)
        if xs_.size > 50:
            throw = float(((xs_.mean() + sx0) - (fx0 + fx1) / 2.0) / bw)
    yb = min(floor + int(bw * 0.038), H - 8)
    off = int(bw * 0.06)
    nh = max(6, int(bw * 0.023))

    def npatch(cy, cx):
        return float(lum[max(0, cy - nh):cy + nh, max(0, cx - nh):cx + nh].mean())

    L = npatch(yb, max(nh, fx0 - off))
    R = npatch(yb, min(W - nh - 1, fx1 + off))
    return dict(prof=[round(v, 1) for v in prof], seam_depth=round(depth, 2),
                recovery_idx=int(rec),
                monotonic_all10=bool(mono_full),
                ambient_lateral=round(amb, 1),
                ratio_lateral=round(prof[0] / amb, 3) if amb > 1 else None,
                contact_ratio=round(ratio, 3), darkest_off_px=darkest_off,
                near_seam=bool(near_seam), monotonic=bool(mono),
                throw=round(throw, 4), left=round(L, 1), right=round(R, 1),
                asym_RmL=round(R - L, 1), amb_side=side, floor=floor,
                pass_=bool(near_seam and mono and CONTACT_LO <= ratio <= CONTACT_HI
                           and abs(throw) >= THROW_MIN))


def b_direction_ok(res, bag, a_res):
    """INTERNAL consistency, measured on pixels: the shadow must be thrown AWAY
    from the brighter side of the frame. The brighter side comes from filter A's
    lateral gradient (mean of the left quarter minus mean of the right quarter),
    NOT from the vision pass's light_from and NOT from the prompt's declared
    window -- gating on either would import a judgment, or test prompt-adherence
    rather than physics. Both are still recorded for comparison.
    Returns None when the frame has no usable lateral gradient (< 2 levels), i.e.
    frontal light, where there is no lateral throw to test."""
    lat = a_res["lateral_LR"]            # >0 means the LEFT side is brighter
    if abs(lat) < 2.0:
        return None
    return (res["throw"] > 0) if lat > 0 else (res["throw"] < 0)


# ---------------------------------------------------------------- filter C
def filter_c(rgb, bag):
    """Hue preservation. Both samples are taken in the SAME COLUMN:
    the umbra at the contact seam and the lit ground 0.286*bw below it -- same
    material, same surface, so any hue difference is the shadow's, not the
    surface's."""
    H, W = rgb.shape[:2]
    bw, floor = bag["bw"], bag["floor"]
    c = (bag["cx0"] + bag["cx1"]) // 2
    px = rgb.astype(float)
    hh, hw = max(4, int(bw * 0.008)), max(8, int(bw * 0.05))

    def box(cy):
        y0, y1 = max(0, cy - hh), min(H, cy + hh + 1)
        x0, x1 = max(0, c - hw), min(W, c + hw + 1)
        return px[y0:y1, x0:x1].reshape(-1, 3).mean(0)

    umbra = box(floor)
    lit = box(min(H - 2, floor + int(bw * 0.286)))
    f = lambda v: float((v[0] - v[2]) / max(v.mean(), 1))
    lrb, urb = f(lit), f(umbra)
    retain = urb / lrb if abs(lrb) > 1e-6 else 0.0
    return dict(lit_rb=round(lrb, 3), umbra_rb=round(urb, 3), retain=round(retain, 3),
                lit_L=round(float(lit.mean()), 1), umbra_L=round(float(umbra.mean()), 1),
                pass_=bool(retain >= HUE_RETAIN and urb > HUE_ABS_MIN))


# ---------------------------------------------------------------- filter D
def _hp_energy(a):
    g = a.astype(float).mean(2) if a.ndim == 3 else a.astype(float)
    return float((g - boxblur(g, 2)).std())


def filter_d(rgb, bag, ref_pack, deliv=(DELIV_W, DELIV_H)):
    """Print legibility on the object.

    `ref_pack` is the REAL photograph of the same object, supplied by the caller, never a
    module constant (SAMPLING CHANGE; the calibration
    itself is unchanged: the plate's band is compared to the REAL band resampled to the
    same delivery height).
    """
    ref = ref_band_metrics(ref_pack)
    H, W = rgb.shape[:2]
    scale = deliv[1] / H                      # plate -> delivery
    bag_h_plate = max(20, bag["floor"] - bag["bag_top"])
    bag_h_deliv = bag_h_plate * scale
    downsample = ref["bag_h"] / max(bag_h_deliv, 1)

    by0, by1 = bag["band_y0"], bag["band_y1"]
    bx0b, bx1b = bag["band_x0"], bag["band_x1"]
    band = rgb[by0:by1 + 1, bx0b:bx1b + 1]
    band_h_deliv = max(4, int(round((by1 - by0 + 1) * scale)))
    band_w_deliv = max(4, int(round((bx1b - bx0b + 1) * scale)))
    pb = np.array(Image.fromarray(band.astype(np.uint8)).resize(
        (band_w_deliv, band_h_deliv), Image.LANCZOS))
    rb = np.array(Image.fromarray(ref["band"].astype(np.uint8)).resize(
        (band_w_deliv, band_h_deliv), Image.LANCZOS))
    hp_p, hp_r = _hp_energy(pb), _hp_energy(rb)
    hp_ratio = hp_p / hp_r if hp_r > 1e-6 else 0.0

    g = pb.astype(float).mean(2)
    ink = float((g < np.percentile(g, 50) - 22).mean())
    return dict(bag_h_deliv=round(bag_h_deliv, 1), downsample=round(downsample, 3),
                band_h_deliv=band_h_deliv, hp_plate=round(hp_p, 2), hp_real=round(hp_r, 2),
                hp_ratio=round(hp_ratio, 3), ink_frac=round(ink, 3),
                pass_=bool(downsample < MAX_DOWNSAMPLE and hp_ratio >= HP_RATIO_MIN))


# ---------------------------------------------------------------- the cascade
def analyse(path, boxes, ref_pack, *, deliv=(DELIV_W, DELIV_H), dark_side=None,
            name=None):
    """Run locate -> A -> B -> C -> D on one plate. Returns the full per-plate record,
    short-circuiting at the first failed filter (that IS the survival curve)."""
    path = Path(path)
    name = name or path.stem
    im = Image.open(path).convert("RGB")
    rgb = np.array(im).astype(float)
    out = {"plate": name, "variant": name[0], "size": list(im.size)}
    bag = locate_bag(rgb, name, boxes)
    if bag is None:
        out["bag"] = None
        out["A"] = filter_a(rgb, None)
        out["verdict"] = "FAIL@bag-not-found"
        return out
    # SERIALISATION CHANGE: a plain `int(v) if isinstance(v,(int,float))` would
    # also swallow the two booleans (occluded / in_frame) into 0/1, because bool is an
    # int in Python. They stay boolean here. No gate reads either field.
    out["bag"] = {k: (int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                  for k, v in bag.items()}
    out["A"] = filter_a(rgb, bag)
    out["B"] = filter_b(rgb, bag)
    d_ok = b_direction_ok(out["B"], bag, out["A"])
    out["B"]["direction_ok"] = d_ok            # None = light is frontal, not testable
    out["B"]["plate_light"] = bag["light"]
    want = (dark_side or {}).get(out["variant"])
    out["B"]["prompt_light_ok"] = (None if want is None else
                                   bool((out["B"]["throw"] > 0) if want == "R"
                                        else (out["B"]["throw"] < 0)))
    # base_occluded is a vision JUDGMENT, and on these plates it does not survive
    # contact with the brief: the prompt explicitly excluded banked loose product from
    # counting as occlusion and the model still routinely returned true, including
    # frames whose contact line is plainly open. It is RECORDED, never gated --
    # a measurement cascade does not take a perceptual verdict as an input. The
    # pixel evidence that the contact is measurable is already B1 (a real dark
    # line exists) and B2 (it recovers monotonically).
    out["B"]["base_occluded_vision"] = bag["occluded"]
    out["B"]["vision_light"] = bag["light"]
    out["B"]["measured_light_left_brighter"] = bool(out["A"]["lateral_LR"] > 0)
    out["B"]["pass_"] = bool(out["B"]["pass_"] and (d_ok is not False))
    out["C"] = filter_c(rgb, bag)
    out["D"] = filter_d(rgb, bag, ref_pack, deliv=deliv)
    for f in "ABCD":
        if not out[f]["pass_"]:
            out["verdict"] = f"FAIL@{f}"
            return out
    out["verdict"] = "SURVIVE"
    return out
