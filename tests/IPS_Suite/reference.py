"""CPU model of the coordinated chain; this is not execution of the FX shader."""
import importlib.util
from pathlib import Path

import numpy as np

TESTS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / name / "reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ips = load("IPS_Depth_v2")
sdb = load("Selective_Deband")
ac = load("Adaptive_Clarity")


def process(image, quality=1, stages=(True, True, True), dither=True, bit_depth=8,
            color_space=1, contrast=None, deband=None, clarity=None,
            masks=(), feather=0, split=None, crop_height=None, target_dtype=np.float32):
    original = np.asarray(image, dtype=float)
    if color_space > 1:
        return original.copy(), {}
    c = {"Strength": 1.0} | (contrast or {})
    d = dict(deband or {})
    a = dict(clarity or {})
    if not any((stages[0] and c["Strength"] > 0,
                stages[1] and d.get("Strength", sdb.DEFAULTS["Strength"]) > 0,
                stages[2] and a.get("Strength", ac.DEFAULTS["Strength"]) > 0)):
        return original.copy(), {}
    result = original.copy()
    diagnostics = {}
    if stages[0]:
        if c["Strength"] > 0:
            rgb, detail, confidence = ips.process(np.clip(result[..., :3], 0, 1),
                                                  quality, crop_height=crop_height,
                                                  **{k: v for k, v in c.items() if k != "Strength"})
            result[..., :3] += c["Strength"] * (rgb - result[..., :3])
            diagnostics["contrast_detail"] = detail
            diagnostics["confidence"] = confidence
        if stages[1] or stages[2]:
            result = result.astype(target_dtype).astype(float)
    eligibility = np.zeros(original.shape[:2])
    if stages[1]:
        result, info = sdb.process(result, quality, enable_dither=False, hud_masks=False, **d)
        change = np.max(np.abs(info["delta"]), axis=-1)
        eligibility = (sdb.smooth(0, .25, info["eligible"])
                       * d.get("Strength", sdb.DEFAULTS["Strength"])
                       * sdb.smooth(.01 * sdb.STEP8, .25 * sdb.STEP8, change))
        eligibility = np.where(change > 1e-7, eligibility, 0)
        diagnostics["deband"] = info
        diagnostics["after_deband"] = result.copy()
        if stages[2]:
            result = result.astype(target_dtype).astype(float)
            eligibility = eligibility.astype(target_dtype).astype(float)
    if stages[2]:
        result, diagnostics["clarity"] = ac.process(result, quality, hud_masks=False, **a)
    if stages[1] and dither and bit_depth in (8, 10):
        step = 1 / (2 ** bit_depth - 1)
        yy, xx = np.indices(original.shape[:2])
        noise = sdb.hash2(xx, yy) - sdb.hash2(xx + 37, yy + 17)
        lo = result[..., :3].min(-1)
        hi = result[..., :3].max(-1)
        headroom = sdb.smooth(0, 2 * step, np.minimum(lo, 1 - hi))
        amplitude = d.get("Dither", sdb.DEFAULTS["Dither"]) * step * eligibility * headroom
        result[..., :3] = np.where((amplitude > 0)[..., None],
                                   np.clip(result[..., :3] + (noise * amplitude)[..., None], 0, 1),
                                   result[..., :3])
        diagnostics["dither"] = noise * amplitude
    h, w = original.shape[:2]
    uv = sdb.grid(h, w)
    protection = np.zeros((h, w))
    for rect in masks:
        protection = np.maximum(protection, sdb.rect_mask(uv, rect, feather, w, h))
    result[..., :3] = (original[..., :3] * protection[..., None]
                       + result[..., :3] * (1 - protection[..., None]))
    result[protection >= 1] = original[protection >= 1]
    if split is not None:
        result[uv[0] < split] = original[uv[0] < split]
    if original.shape[-1] == 4:
        result[..., 3] = original[..., 3]
    diagnostics["protection"] = protection
    diagnostics["eligibility"] = eligibility
    return result, diagnostics
