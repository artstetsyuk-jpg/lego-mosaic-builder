"""LEGO Mosaic Builder (Streamlit) — Complete Unified Edition."""
import csv
import html
import io
import math
import os
import tempfile
import copy

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps

st.set_page_config(page_title="LEGO Mosaic Builder", layout="wide")

# ----------------------------------------------------------------------------
# Verified BrickLink Solid Colors (exist in 3004 (1x2), 3003 (2x2), AND 3001 (2x4))
# ----------------------------------------------------------------------------
LEGO_ALL_COLORS = {
    # --- Neutrals, Grays & Blacks (7) ---
    "White": (255, 255, 255), "Very Light Bluish Gray": (229, 228, 223),
    "Light Bluish Gray": (160, 165, 169), "Light Gray": (155, 161, 157),
    "Dark Gray": (109, 110, 92), "Dark Bluish Gray": (108, 110, 104), "Black": (18, 18, 18),
    # --- Tans, Nougats & Browns (10) ---
    "Light Nougat": (246, 215, 179), "Tan": (228, 205, 158), "Dark Tan": (149, 138, 115),
    "Nougat": (208, 145, 104), "Medium Nougat": (170, 125, 85), "Dark Nougat": (173, 97, 64),
    "Dark Orange": (169, 85, 0), "Reddish Brown": (88, 38, 22), "Brown": (88, 57, 39), "Dark Brown": (48, 25, 16),
    # --- Reds, Pinks, Corals & Magentas (9) ---
    "Dark Red": (114, 14, 15), "Red": (180, 0, 0), "Reddish Orange": (236, 70, 18),
    "Coral": (255, 105, 143), "Sand Red": (149, 121, 118), "Pink": (252, 151, 172),
    "Bright Pink": (228, 173, 200), "Dark Pink": (200, 112, 160), "Magenta": (146, 57, 120),
    # --- Oranges & Yellows (7) ---
    "Orange": (254, 138, 24), "Medium Orange": (255, 167, 11), "Bright Light Orange": (248, 187, 61),
    "Yellow": (250, 200, 10), "Light Yellow": (251, 230, 150), "Bright Light Yellow": (255, 240, 58), "Neon Yellow": (235, 255, 0),
    # --- Greens & Limes (7) ---
    "Yellowish Green": (223, 238, 165), "Lime": (187, 233, 11), "Olive Green": (155, 154, 90),
    "Sand Green": (160, 188, 172), "Bright Green": (75, 159, 74), "Green": (35, 120, 65), "Dark Green": (24, 70, 50),
    # --- Blues, Teals, Aquas & Azures (9) ---
    "Light Aqua": (173, 221, 213), "Dark Turquoise": (0, 143, 155), "Medium Azure": (54, 174, 191),
    "Dark Azure": (7, 139, 201), "Maersk Blue": (53, 146, 195), "Bright Light Blue": (159, 195, 233),
    "Medium Blue": (90, 147, 219), "Sand Blue": (96, 116, 161), "Blue": (0, 85, 191), "Dark Blue": (10, 52, 99),
    # --- Purples & Lavenders (5) ---
    "Lavender": (225, 213, 237), "Medium Lavender": (172, 120, 186), "Light Purple": (238, 157, 195),
    "Purple": (129, 0, 123), "Dark Purple": (63, 54, 145),
}

LEGO_GRAYSCALE = {k: LEGO_ALL_COLORS[k] for k in ["White", "Light Bluish Gray", "Dark Bluish Gray", "Black"]}

BRICKLINK_1X1_PRICE = {
    "Black": 0.05, "White": 0.05, "Light Bluish Gray": 0.05, "Dark Bluish Gray": 0.05,
    "Red": 0.05, "Blue": 0.05, "Yellow": 0.05, "Tan": 0.05, "Reddish Brown": 0.05,
    "Dark Tan": 0.06, "Orange": 0.06, "Lime": 0.06, "Green": 0.06, "Dark Red": 0.07,
    "Dark Blue": 0.07, "Dark Green": 0.07, "Dark Brown": 0.08, "Bright Light Orange": 0.07,
    "Medium Nougat": 0.07, "Medium Azure": 0.07, "Bright Pink": 0.07, "Dark Purple": 0.08,
    "Dark Azure": 0.09, "Dark Turquoise": 0.09, "Medium Blue": 0.09, "Medium Lavender": 0.10,
    "Sand Green": 0.10, "Light Aqua": 0.10, "Sand Blue": 0.11, "Bright Light Yellow": 0.10,
    "Lavender": 0.11, "Dark Orange": 0.11, "Coral": 0.11, "Dark Pink": 0.11,
    "Bright Light Blue": 0.12, "Neon Yellow": 0.12, "Yellowish Green": 0.14,
    "Olive Green": 0.15, "Light Gray": 0.18, "Dark Gray": 0.18, "Brown": 0.18,
    "Purple": 0.28, "Light Yellow": 0.28, "Light Purple": 0.30, "Pink": 0.32,
    "Light Nougat": 0.32, "Bright Green": 0.35, "Magenta": 0.35, "Medium Orange": 0.38,
    "Maersk Blue": 0.55, "Sand Red": 0.65, "Nougat": 0.65, "Reddish Orange": 0.65,
    "Very Light Bluish Gray": 0.75, "Dark Nougat": 0.85,
}

LDRAW_COLOR_CODES = {
    "White": 15, "Very Light Bluish Gray": 151, "Light Bluish Gray": 71, "Light Gray": 7, "Dark Gray": 8,
    "Dark Bluish Gray": 72, "Black": 0, "Light Nougat": 78, "Tan": 19, "Dark Tan": 28, "Nougat": 92,
    "Medium Nougat": 84, "Dark Nougat": 128, "Dark Orange": 484, "Reddish Brown": 70, "Brown": 6,
    "Dark Brown": 308, "Dark Red": 320, "Red": 4, "Reddish Orange": 402, "Coral": 353, "Sand Red": 335,
    "Pink": 13, "Bright Pink": 29, "Dark Pink": 5, "Magenta": 26, "Orange": 25, "Medium Orange": 462,
    "Bright Light Orange": 191, "Yellow": 14, "Light Yellow": 18, "Bright Light Yellow": 226,
    "Neon Yellow": 368, "Yellowish Green": 326, "Lime": 27, "Olive Green": 330, "Sand Green": 378,
    "Bright Green": 10, "Green": 2, "Dark Green": 288, "Light Aqua": 323, "Dark Turquoise": 3,
    "Medium Azure": 322, "Dark Azure": 321, "Maersk Blue": 313, "Bright Light Blue": 212,
    "Medium Blue": 73, "Sand Blue": 379, "Blue": 1, "Dark Blue": 272, "Lavender": 31,
    "Medium Lavender": 30, "Light Purple": 69, "Purple": 22, "Dark Purple": 85,
}

BRICKLINK_COLOR_IDS = {
    "White": 1, "Very Light Bluish Gray": 99, "Light Bluish Gray": 86, "Light Gray": 9, "Dark Gray": 10,
    "Dark Bluish Gray": 85, "Black": 11, "Light Nougat": 90, "Tan": 2, "Dark Tan": 69, "Nougat": 28,
    "Medium Nougat": 150, "Dark Nougat": 225, "Dark Orange": 68, "Reddish Brown": 88, "Brown": 8,
    "Dark Brown": 120, "Dark Red": 59, "Red": 5, "Reddish Orange": 167, "Coral": 220, "Sand Red": 58,
    "Pink": 23, "Bright Pink": 104, "Dark Pink": 47, "Magenta": 71, "Orange": 4, "Medium Orange": 31,
    "Bright Light Orange": 110, "Yellow": 3, "Light Yellow": 33, "Bright Light Yellow": 103,
    "Neon Yellow": 236, "Yellowish Green": 158, "Lime": 34, "Olive Green": 155, "Sand Green": 48,
    "Bright Green": 36, "Green": 6, "Dark Green": 80, "Light Aqua": 152, "Dark Turquoise": 39,
    "Medium Azure": 156, "Dark Azure": 153, "Maersk Blue": 72, "Bright Light Blue": 105,
    "Medium Blue": 42, "Sand Blue": 55, "Blue": 7, "Dark Blue": 63, "Lavender": 154,
    "Medium Lavender": 157, "Light Purple": 93, "Purple": 24, "Dark Purple": 89,
}

BRICK_SIZE_PRICE_MULT = {1: 1.0, 2: 1.25, 3: 1.50, 4: 1.70}

def get_brick_price(color_name, width=1, depth=1):
    base = BRICKLINK_1X1_PRICE.get(color_name, 0.45)
    return base * BRICK_SIZE_PRICE_MULT.get(width, float(width)) * (1.18 if depth == 2 else 1.0)

GEOMETRY = {
    "Side-view bricks (2x1, 2x2, 2x4 interlocking — 5:6)": dict(w=5, h=6, cm=(0.8, 0.96), piece="Brick", studs=False),
    "Side-view plates (5:2)": dict(w=5, h=2, cm=(0.8, 0.32), piece="Plate", studs=False),
    "Studs facing out (1:1)": dict(w=1, h=1, cm=(0.8, 0.8), piece="Plate 1x1", studs=True),
}

CROPS = {
    "Keep original shape": None, "Square 1:1": 1.0, "Landscape 4:3": 4 / 3, "Landscape 3:2": 3 / 2,
    "Wide 16:9": 16 / 9, "Portrait 3:4": 3 / 4, "Portrait 4:5": 4 / 5, "Portrait 2:3": 2 / 3,
}
MAX_GRID_SIDE = 400
MAX_SOURCE_SIDE = 3000

# ----------------------------------------------------------------------------
# Color science: sRGB <-> linear <-> OKLab
# ----------------------------------------------------------------------------
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])
_M1_INV, _M2_INV = np.linalg.inv(_M1), np.linalg.inv(_M2)

def srgb_to_linear(rgb8):
    c = np.asarray(rgb8, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def linear_to_srgb8(lin):
    c = np.clip(lin, 0.0, 1.0)
    c = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return np.clip(np.rint(c * 255.0), 0, 255).astype(np.uint8)

def linear_to_oklab(lin): return np.cbrt(lin @ _M1.T) @ _M2.T
def srgb8_to_oklab(rgb8): return linear_to_oklab(srgb_to_linear(rgb8))
def oklab_to_srgb8(lab): return linear_to_srgb8((np.asarray(lab, dtype=np.float64) @ _M2_INV.T) ** 3 @ _M1_INV.T)

def dist2(lab, pal, l_weight=1.0):
    dl = lab[:, None, 0] - pal[None, :, 0]
    da = lab[:, None, 1] - pal[None, :, 1]
    db = lab[:, None, 2] - pal[None, :, 2]
    c_pix = np.hypot(lab[:, 1], lab[:, 2])[:, None]
    c_pal = np.hypot(pal[:, 1], pal[:, 2])[None, :]
    neutral_w = 1.0 + 6.0 * np.exp(-c_pix / 0.028)
    oversat_penalty = np.maximum(0.0, c_pal - c_pix * 1.15) ** 2
    dh2 = np.maximum(0.0, 2.0 * (c_pix * c_pal - lab[:, None, 1] * pal[None, :, 1] - lab[:, None, 2] * pal[None, :, 2]))
    color_mask = np.clip((c_pix - 0.04) / 0.04, 0.0, 1.0)
    return 1.15 * l_weight * (dl * dl) + neutral_w * (da * da + db * db) + 4.5 * color_mask * dh2 + 10.0 * oversat_penalty

def nearest(lab, pal_lab, chunk=60000, l_weight=1.0, price_penalty=None):
    lab = np.asarray(lab, dtype=np.float32).reshape(-1, 3)
    pal = np.asarray(pal_lab, dtype=np.float32)
    out = np.empty(len(lab), dtype=np.int32)
    for s in range(0, len(lab), chunk):
        d = dist2(lab[s:s + chunk], pal, l_weight)
        if price_penalty is not None: d = d + price_penalty[None, :]
        out[s:s + chunk] = d.argmin(1)
    return out

def snap(rgb8, pal_lab, l_weight=1.0, price_penalty=None):
    flat = rgb8.reshape(-1, 3).astype(np.uint32)
    packed = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    uniq, inverse = np.unique(packed, return_inverse=True)
    u_rgb = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], axis=1).astype(np.uint8)
    return nearest(srgb8_to_oklab(u_rgb), pal_lab, l_weight, price_penalty)[inverse.reshape(-1)].reshape(rgb8.shape[:2])

def kmeans_palette(rgb8, k, seed=0, iters=12, max_samples=40000):
    flat = rgb8.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    if len(flat) > max_samples: flat = flat[rng.choice(len(flat), max_samples, replace=False)]
    lab, k = srgb8_to_oklab(flat), max(1, min(k, len(np.unique(flat, axis=0))))
    centers = [lab[rng.integers(len(lab))]]
    d2 = ((lab - centers[0]) ** 2).sum(1)
    for _ in range(1, k):
        total = d2.sum()
        pick = rng.choice(len(lab), p=d2 / total) if total > 0 else rng.integers(len(lab))
        centers.append(lab[pick])
        d2 = np.minimum(d2, ((lab - lab[pick]) ** 2).sum(1))
    centers = np.array(centers)
    for _ in range(iters):
        assign = ((lab[:, None, :] - centers[None]) ** 2).sum(2).argmin(1)
        for j in range(k):
            members = assign == j
            if members.any(): centers[j] = lab[members].mean(0)
    return oklab_to_srgb8(centers[np.argsort(centers[:, 0])])

# ----------------------------------------------------------------------------
# Image Prep & Interlocking Algorithm
# ----------------------------------------------------------------------------
def load_image(file_bytes, transparent_bg="White"):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)))
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255) if transparent_bg == "White" else (0, 0, 0, 255))
        img = Image.alpha_composite(base, rgba).convert("RGB")
    return img.convert("RGB").copy()

def crop_image(img, aspect, zoom, pan_x, pan_y):
    w, h = img.size
    if aspect is None: cw, ch = float(w), float(h)
    elif w / h > aspect: cw, ch = h * aspect, float(h)
    else: cw, ch = float(w), w / aspect
    cw, ch = max(1.0, cw / zoom), max(1.0, ch / zoom)
    left, top = (w - cw) * pan_x, (h - ch) * pan_y
    box = (int(round(left)), int(round(top)), int(round(left + cw)), int(round(top + ch)))
    return img.crop((box[0], box[1], max(box[2], box[0] + 1), max(box[3], box[1] + 1)))

def grid_size(img_w, img_h, total, w_ratio, h_ratio):
    nx = max(1, round(math.sqrt(total * (img_w / img_h) * (h_ratio / w_ratio))))
    ny = max(1, round(nx * (img_h / img_w) * (w_ratio / h_ratio)))
    return min(nx, MAX_GRID_SIDE), min(ny, MAX_GRID_SIDE)

def detect_kind(img):
    small = np.asarray(img.resize((min(img.width, 256), min(img.height, 256)), Image.Resampling.BILINEAR))
    q = (small >> 4).astype(np.int32)
    counts = np.bincount(((q[..., 0] << 8) | (q[..., 1] << 4) | q[..., 2]).ravel(), minlength=4096)
    return "graphic" if np.sort(counts)[::-1][:6].sum() / counts.sum() > 0.80 else "photo"

def supersample(nx, ny, kind):
    return int(min(10, max(3, math.sqrt(2.5e6 / (nx * ny))))) if kind == "graphic" else 4

def enhance(img, p, kind):
    brightness, contrast, saturation = p["brightness"], p["contrast"], p["saturation"]
    if kind == "photo" and p["auto_enhance"]:
        arr = np.asarray(img, dtype=np.float32)
        lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
        lo, hi = np.percentile(lum, (1, 99.5))
        if hi > lo + 1e-3:
            scale = np.clip((lum - lo) / (hi - lo), 0.0, 1.0) ** 0.88 * 255.0 / np.maximum(lum, 1.0)
            img = Image.fromarray(np.clip(arr * scale[..., None], 0, 255).astype(np.uint8))
        contrast, saturation = contrast * 1.06, saturation * 1.08
    for enhancer, factor in ((ImageEnhance.Brightness, brightness), (ImageEnhance.Contrast, contrast), (ImageEnhance.Color, saturation)):
        if abs(factor - 1.0) > 1e-3: img = enhancer(img).enhance(factor)
    return img

def average_cells(hi_rgb8, nx, ny, S):
    return linear_to_srgb8(srgb_to_linear(hi_rgb8).reshape(ny, S, nx, S, 3).mean(axis=(1, 3)))

def graphic_cells(hi_rgb8, nx, ny, S, pal_lab, boost):
    K = len(pal_lab)
    idx_all = snap(hi_rgb8, pal_lab)
    bg = int(np.bincount(idx_all.ravel(), minlength=K).argmax())
    bg_lab = np.median(srgb8_to_oklab(hi_rgb8)[idx_all == bg], axis=0)
    dist = np.linalg.norm(srgb8_to_oklab(hi_rgb8) - bg_lab, axis=2)
    idx_fg = snap(hi_rgb8, pal_lab, l_weight=0.5)

    def blocks(a): return a.reshape(ny, S, nx, S).transpose(0, 2, 1, 3).reshape(ny, nx, S * S)
    d, f = blocks(dist), blocks(idx_fg)
    pure = d >= 0.75 * d.max(-1, keepdims=True)
    votes = np.zeros((ny, nx, K), dtype=np.float32)
    for k in np.unique(idx_fg): votes[..., k] = ((f == k) & pure).sum(-1)
    fg_dist = (d * pure).sum(-1) / np.maximum(pure.sum(-1), 1)
    is_fg = (np.clip(d / np.maximum(fg_dist[..., None], 1e-6), 0, 1).mean(-1) >= 0.5 - 0.38 * boost / 100.0) & (fg_dist >= 0.08)
    return np.where(is_fg, votes.argmax(-1), bg).astype(np.int32)

def dither(cell_lab, pal_lab, strength=0.85):
    work, pal, (ny, nx) = cell_lab.astype(np.float64).copy(), np.asarray(pal_lab, dtype=np.float64), cell_lab.shape[:2]
    out = np.zeros((ny, nx), dtype=np.int32)
    for y in range(ny):
        forward = y % 2 == 0
        step = 1 if forward else -1
        for x in (range(nx) if forward else range(nx - 1, -1, -1)):
            old = work[y, x]
            out[y, x] = int(dist2(old[None, :], pal)[0].argmin())
            err = (old - pal[out[y, x]]) * strength
            if 0 <= x + step < nx: work[y, x + step] += err * 7 / 16
            if y + 1 < ny:
                if 0 <= x - step < nx: work[y + 1, x - step] += err * 3 / 16
                work[y + 1, x] += err * 5 / 16
                if 0 <= x + step < nx: work[y + 1, x + step] += err * 1 / 16
    return out

def despeckle(idx, K, level):
    if level <= 0 or idx.shape[0] < 3 or idx.shape[1] < 3: return idx
    ny, nx = idx.shape
    onehot = np.zeros((ny, nx, K), dtype=np.int16)
    onehot[np.arange(ny)[:, None], np.arange(nx)[None, :], idx] = 1
    pad = np.pad(onehot, ((1, 1), (1, 1), (0, 0)))
    nb = sum(pad[1 + dy:1 + dy + ny, 1 + dx:1 + dx + nx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0))
    same = np.take_along_axis(nb, idx[..., None], axis=2)[..., 0]
    return np.where((same <= (0 if level == 1 else 1)) & (nb.max(-1) >= 3), nb.argmax(-1), idx)

def limit_colors(idx, cell_lab, pal_lab, max_colors):
    used, counts = np.unique(idx, return_counts=True)
    if max_colors <= 0 or len(used) <= max_colors: return idx
    keep = used[np.argsort(-counts)[:max_colors]]
    return keep[nearest(cell_lab.reshape(-1, 3), pal_lab[keep])].reshape(idx.shape)

def pack_interlocking_wall(idx_grid, names, depth=2):
    allowed_widths = (1, 2, 4)
    ny, nx = idx_grid.shape
    brick_spans = np.ones((ny, nx), dtype=np.int32)
    brick_id_grid = np.zeros((ny, nx), dtype=np.int32)
    parts_tally = {name: {w: 0 for w in allowed_widths} for name in names}

    prev_seams = set()
    uid = 1
    total_seams, staggered_seams = 0, 0

    for y in range(ny - 1, -1, -1):
        row = idx_grid[y]
        dp = [(-1e9, -1)] * (nx + 1)
        dp[0] = (0.0, 0)

        for x in range(nx):
            if dp[x][0] <= -1e8: continue
            color = row[x]
            for w in allowed_widths:
                nx_pos = x + w
                if nx_pos > nx or not np.all(row[x:nx_pos] == color): break

                # Strongly prioritize 2x4 bricks
                score = {1: 1.0, 2: 5.0, 4: 16.0}[w]
                if nx_pos < nx and nx_pos in prev_seams: score -= 5.0
                for internal_x in range(x + 1, nx_pos):
                    if internal_x in prev_seams: score += 2.5
                
                is_run_start = (x == 0) or (row[x - 1] != color)
                if is_run_start and (y % 2 == 1) and w == 2 and (x + 6 <= nx) and np.all(row[x:x + 6] == color):
                    score += 1.5

                if dp[x][0] + score > dp[nx_pos][0]:
                    dp[nx_pos] = (dp[x][0] + score, x)

        cur = nx
        row_bricks = []
        current_seams = set()
        while cur > 0:
            start_x = dp[cur][1]
            w = cur - start_x
            row_bricks.append((start_x, w, int(row[start_x])))
            if start_x > 0: current_seams.add(start_x)
            cur = start_x

        for start_x, w, c_idx in reversed(row_bricks):
            brick_spans[y, start_x] = w
            brick_spans[y, start_x + 1:start_x + w] = 0
            brick_id_grid[y, start_x:start_x + w] = uid
            uid += 1
            parts_tally[names[c_idx]][w] += 1

        if y < ny - 1:
            for s_x in current_seams:
                total_seams += 1
                if s_x not in prev_seams: staggered_seams += 1
        prev_seams = current_seams

    strength_pct = 100.0 * staggered_seams / max(total_seams, 1)
    return brick_spans, brick_id_grid, parts_tally, strength_pct

class Mosaic:
    def __init__(self, **kw):
        self.__dict__.update(kw)

@st.cache_data(show_spinner="Building base mosaic...", max_entries=12)
def build_base_mosaic(file_bytes, p, palette_items):
    """The cached core image processing phase."""
    img = crop_image(load_image(file_bytes, p["transparent_bg"]), p["crop_aspect"], p["zoom"], p["pan_x"], p["pan_y"])
    nx, ny = grid_size(img.width, img.height, p["total"], p["w_ratio"], p["h_ratio"])
    kind = p["kind"] if p["kind"] != "auto" else detect_kind(img)
    S = supersample(nx, ny, kind)
    hi = img.resize((nx * S, ny * S), Image.Resampling.NEAREST if (kind == "graphic" and (img.width < nx * S or img.height < ny * S)) else Image.Resampling.LANCZOS)
    if p["color_mode"] == "lego_gray": hi = ImageOps.grayscale(hi).convert("RGB")
    hi_rgb8 = np.asarray(enhance(hi, p, kind))
    cells = average_cells(hi_rgb8, nx, ny, S)
    if kind == "photo" and abs(p["sharpness"] - 1.0) > 1e-3:
        cells = np.asarray(ImageEnhance.Sharpness(Image.fromarray(cells)).enhance(p["sharpness"]))

    result = dict(nx=nx, ny=ny, kind=kind, prepared=img, names=None, palette=None, idx=None, counts=None)
    if p["color_mode"] == "true": return Mosaic(**result, grid=cells)

    if p["color_mode"] == "adaptive":
        pal_rgb = kmeans_palette(hi_rgb8, p["num_colors"])
        names = [f"Color {i + 1}" for i in range(len(pal_rgb))]
    else:
        names = [n for n, _ in palette_items]
        pal_rgb = np.array([c for _, c in palette_items], dtype=np.uint8)
    pal_lab = srgb8_to_oklab(pal_rgb)

    price_weight = p.get("price_weight", 55) / 100.0
    if p["color_mode"] in ("lego_all", "lego_pick") and price_weight > 0:
        raw_prices = np.array([BRICKLINK_1X1_PRICE.get(n, 0.45) for n in names], dtype=np.float64)
        price_penalty = (price_weight ** 1.2) * 0.35 * ((raw_prices - 0.05) ** 1.2)
        if price_weight >= 0.85: price_penalty = np.where(raw_prices > 0.10, 1e6, price_penalty)
        elif price_weight >= 0.60: price_penalty = np.where(raw_prices > 0.25, 1e6, price_penalty)
    else: price_penalty = None

    if kind == "graphic":
        idx = graphic_cells(hi_rgb8, nx, ny, S, pal_lab, p["detail_boost"])
        if price_penalty is not None: idx = nearest(pal_lab[idx].reshape(-1, 3), pal_lab, price_penalty=price_penalty).reshape(ny, nx)
        cell_lab = pal_lab[idx]
    elif p["color_mode"] in ("lego_all", "lego_pick") and not p["dither"]:
        adap_rgb = kmeans_palette(hi_rgb8, p["max_colors"] if p["max_colors"] > 0 else 20)
        adap_lab, cell_lab = srgb8_to_oklab(adap_rgb), srgb8_to_oklab(cells)
        cluster_idx = ((cell_lab.reshape(-1, 1, 3) - adap_lab[None, :, :]) ** 2).sum(2).argmin(1).reshape(ny, nx)
        d_mat = dist2(adap_lab, pal_lab)
        if price_penalty is not None: d_mat = d_mat + price_penalty[None, :]
        order = np.argsort(-np.unique(cluster_idx, return_counts=True)[1])
        cluster_to_lego, used_penalty = np.zeros(len(adap_rgb), dtype=np.int32), np.zeros(len(pal_rgb), dtype=np.float64)
        for c_i in order:
            if d_mat[c_i].min() < 0.0025: best_lego = int(d_mat[c_i].argmin())
            else:
                best_lego = int((d_mat[c_i] + used_penalty).argmin())
                used_penalty[best_lego] += 0.008
            cluster_to_lego[c_i] = best_lego
        idx = cluster_to_lego[cluster_idx]
    else:
        cell_lab = srgb8_to_oklab(cells)
        idx = dither(cell_lab, pal_lab) if p["dither"] else nearest(cell_lab, pal_lab, price_penalty=price_penalty).reshape(ny, nx)

    idx = despeckle(idx, len(pal_rgb), p["despeckle"])
    idx = limit_colors(idx, cell_lab, pal_lab, p["max_colors"])

    # Basic unswapped info
    used, counts = np.unique(idx, return_counts=True)
    result.update(
        idx=idx, grid=pal_rgb[idx], grid_unswapped=pal_rgb[idx].copy(), has_swaps=False, names=names, palette=pal_rgb,
        counts={names[int(u)]: int(c) for u, c in zip(used, counts)}
    )
    return Mosaic(**result)

def apply_swaps_and_pack(base_mosaic, swap_map, depth_studs):
    """Applies instant custom swaps and packs the bricks without recalculating image pixels."""
    m = copy.copy(base_mosaic)
    if not m.idx is not None: return m
    
    idx = m.idx.copy()
    has_swaps = False
    
    if swap_map and m.names:
        name_to_idx = {n: i for i, n in enumerate(m.names)}
        for src_name, tgt_name in swap_map.items():
            if src_name in name_to_idx and tgt_name in name_to_idx:
                src_i, tgt_i = name_to_idx[src_name], name_to_idx[tgt_name]
                if np.any(idx == src_i):
                    idx[idx == src_i] = tgt_i
                    has_swaps = True
                    
    m.idx = idx
    m.grid = m.palette[idx]
    m.has_swaps = has_swaps
    
    # Pack the wall AFTER the swaps so new colors form complete 2x4 bricks
    spans, ids, tally, strength = pack_interlocking_wall(idx, m.names, depth=depth_studs)
    m.brick_spans = spans
    m.brick_id_grid = ids
    m.brick_tally = tally
    m.strength_pct = strength
    
    # Calculate costs
    used, counts = np.unique(idx, return_counts=True)
    m.counts = {m.names[int(u)]: int(c) for u, c in zip(used, counts)}
    m.total_physical_bricks = sum(sum(w_counts.values()) for w_counts in tally.values())
    
    m.est_cost = sum(qty * get_brick_price(c_name, width=w, depth=depth_studs) for c_name, w_counts in tally.items() for w, qty in w_counts.items())
    m.raw_1x1_cost = sum(cnt * get_brick_price(m.names[int(u)], width=1, depth=depth_studs) for u, cnt in zip(used, counts))
    
    return m

# ----------------------------------------------------------------------------
# Rendering & Exports
# ----------------------------------------------------------------------------
def _shade_tile(cw, ch, style):
    tile = np.ones((ch, cw, 3), dtype=np.float32)
    if style == "Bevel (3D)":
        e = max(1, min(cw, ch) // 8)
        tile[:e] *= 1.18; tile[:, :e] *= 1.08; tile[-e:] *= 0.78; tile[:, -e:] *= 0.88
    elif style == "Outlines":
        tile[0] *= 0.5; tile[:, 0] *= 0.5
    return tile

def render_preview(grid, w_ratio, h_ratio, style, studs, target_width=1100, brick_id_grid=None):
    ny, nx, _ = grid.shape
    if studs and style == "Round studs":
        s = int(np.clip(round(target_width / nx), 8, 24))
        up = np.repeat(np.repeat(grid, s, 0), s, 1).astype(np.float32)
        yy, xx = (np.mgrid[0:s, 0:s] + 0.5) / s
        dist = np.hypot(xx - 0.5, yy - 0.5)
        m = np.tile(np.clip((0.36 - dist) / (1.2 / s) + 0.5, 0, 1), (ny, nx))[..., None]
        sh = np.tile((1.0 + 0.25 * np.exp(-(((xx - 0.42) ** 2 + (yy - 0.40) ** 2) / 0.01)) - 0.20 * np.clip((dist - 0.22) / 0.14, 0, 1)), (ny, nx))[..., None]
        return Image.fromarray(np.clip(up * 0.45 * (1 - m) + np.clip(up * sh, 0, 255) * m, 0, 255).astype(np.uint8))

    scale = int(np.clip(round(target_width / (nx * w_ratio)), 2, 14))
    cw, ch = w_ratio * scale, h_ratio * scale
    up = np.repeat(np.repeat(grid, ch, 0), cw, 1).astype(np.float32)

    if brick_id_grid is not None and style in ("Bevel (3D)", "Outlines"):
        bid_up = np.repeat(np.repeat(brick_id_grid, ch, 0), cw, 1)
        te = np.zeros_like(bid_up, dtype=bool); te[0, :] = True; te[1:, :] = bid_up[1:, :] != bid_up[:-1, :]
        le = np.zeros_like(bid_up, dtype=bool); le[:, 0] = True; le[:, 1:] = bid_up[:, 1:] != bid_up[:, :-1]
        if style == "Outlines":
            up[te | le] *= 0.38
        else:
            be = np.zeros_like(bid_up, dtype=bool); be[-1, :] = True; be[:-1, :] = bid_up[:-1, :] != bid_up[1:, :]
            re = np.zeros_like(bid_up, dtype=bool); re[:, -1] = True; re[:, :-1] = bid_up[:, :-1] != bid_up[:, 1:]
            up[te] = np.clip(up[te] * 1.22, 0, 255); up[le] = np.clip(up[le] * 1.12, 0, 255)
            up[be] = np.clip(up[be] * 0.68, 0, 255); up[re] = np.clip(up[re] * 0.75, 0, 255)
    else:
        up = np.clip(up * np.tile(_shade_tile(cw, ch, style), (ny, nx, 1)), 0, 255)
    return Image.fromarray(up.astype(np.uint8))

def parts_csv(mosaic, depth_studs):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Color", "Hex", "Brick Size", "Quantity", "Est. Unit Price (USD)", "Est. Total Price (USD)"])
    lookup = {n: tuple(int(v) for v in mosaic.palette[i]) for i, n in enumerate(mosaic.names)}
    for name, _ in sorted(mosaic.counts.items(), key=lambda kv: -kv[1]):
        r, g, b = lookup[name]
        for w in (4, 2, 1):
            if mosaic.brick_tally[name].get(w, 0) > 0:
                qty, unit_p = mosaic.brick_tally[name][w], get_brick_price(name, width=w, depth=depth_studs)
                writer.writerow([name, f"#{r:02x}{g:02x}{b:02x}", f"Brick {depth_studs}x{w}", qty, f"{unit_p:.2f}", f"{qty * unit_p:.2f}"])
    return buf.getvalue().encode("utf-8-sig")

def export_bricklink_studio_ldr(mosaic, geo_name, depth_studs=2, studs_per_step=16):
    if getattr(mosaic, "grid", None) is None: return None
    ny, nx, _ = mosaic.grid.shape
    is_plate, is_studs_out = "plate" in geo_name.lower(), "studs facing out" in geo_name.lower()
    palette_ldraw_ids = [LDRAW_COLOR_CODES.get(n, 15) for n in (mosaic.names if mosaic.names else list(LEGO_ALL_COLORS.keys()))]
    spans = mosaic.brick_spans if (getattr(mosaic, "brick_spans", None) is not None and not is_studs_out) else np.ones((ny, nx), dtype=np.int32)
    layer_h = 8 if is_plate else 24
    p_d1 = {1: "3024", 2: "3023", 3: "3623", 4: "3710"} if is_plate else {1: "3005", 2: "3004", 3: "3622", 4: "3010"}
    p_d2 = {1: "3023", 2: "3022", 3: "3021", 4: "3020"} if is_plate else {1: "3004", 2: "3003", 3: "3002", 4: "3001"}
    lines = ["0 LEGO Interlocking Side-Stack Mosaic", "0 Name: lego_mosaic.ldr", "0 Author: LEGO Mosaic Builder", "0 !LDRAW_ORG Unofficial_Model"]
    x_offset = nx * 10
    
    for y in range(ny - 1, -1, -1):
        studs_in_step = 0
        for x in range(nx):
            w = int(spans[y, x])
            if w <= 0: continue
            c, l_x, l_y = palette_ldraw_ids[int(mosaic.idx[y, x])], (x * 20 + w * 10) - x_offset, (y - ny) * layer_h
            if is_studs_out:
                lines.append(f"1 {c} {l_x} 0 {(y * 20) - (ny * 10)} 1 0 0 0 1 0 0 0 1 3024.dat")
            else:
                lines.append(f"1 {c} {l_x} {l_y} 0 {'0 0 1 0 1 0 -1 0 0' if depth_studs == 2 and w == 1 else '1 0 0 0 1 0 0 0 1'} {p_d2.get(w, '3004') if depth_studs == 2 else p_d1.get(w, '3005')}.dat")
            studs_in_step += w
            if studs_in_step >= studs_per_step and (x + w) < nx:
                lines.append("0 STEP")
                studs_in_step = 0
        if studs_in_step > 0: lines.append("0 STEP")
    return "\r\n".join(lines)

def export_bricklink_wanted_xml(mosaic, geo_name, depth_studs=2):
    if getattr(mosaic, "brick_tally", None) is None: return None
    p_map = ({1: "3024", 2: "3023", 3: "3623", 4: "3710"} if "studs facing out" in geo_name.lower() else
             ({1: "3023", 2: "3022", 3: "3021", 4: "3020"} if depth_studs == 2 else {1: "3024", 2: "3023", 3: "3623", 4: "3710"}) if "plate" in geo_name.lower() else
             ({1: "3004", 2: "3003", 3: "3002", 4: "3001"} if depth_studs == 2 else {1: "3005", 2: "3004", 3: "3622", 4: "3010"}))
    xml = ["<INVENTORY>"]
    for c_name, counts in mosaic.brick_tally.items():
        for w, qty in counts.items():
            if qty > 0:
                xml.append(f"  <ITEM>\n    <ITEMTYPE>P</ITEMTYPE>\n    <ITEMID>{p_map.get(int(w), '3005')}</ITEMID>\n    <COLOR>{BRICKLINK_COLOR_IDS.get(c_name, 11)}</COLOR>\n    <MINQTY>{int(qty)}</MINQTY>\n  </ITEM>")
    xml.append("</INVENTORY>")
    return "\n".join(xml)

# ============================================================================
# UI
# ============================================================================
st.title("🧱 LEGO Mosaic Builder")
st.write("Upload any picture and turn it into a LEGO brick mosaic with a complete parts list.")

with st.sidebar:
    st.header("1. Brick type")
    geo_name = st.selectbox("Piece type & view", list(GEOMETRY))
    geo, depth_studs = GEOMETRY[geo_name], st.radio("Wall depth", [1, 2], index=1, horizontal=True)

    st.header("2. Size")
    total_bricks = st.slider("Target number of pieces (budget)", 100, 20000, 2500, 100)

    st.header("3. Colors")
    price_weight = st.slider("💰 BrickLink Price-to-Color Ratio", 0, 100, 60, 5)
    color_mode = {"All verified BrickLink colors (54 shades)": "lego_all", "Pick specific LEGO colors": "lego_pick", "LEGO grayscale": "lego_gray", "Adaptive colors": "adaptive"}["All verified BrickLink colors (54 shades)"]
    active_palette, num_colors, max_colors = dict(LEGO_ALL_COLORS), 16, 0

    st.header("4. Your picture")
    kind = {"Auto-detect": "auto", "Photo": "photo", "Logo / graphic / pixel art": "graphic"}[st.selectbox("Picture type", ["Auto-detect", "Photo", "Logo / graphic / pixel art"])]
    crop_label = st.selectbox("Crop shape", list(CROPS))
    zoom, pan_x, pan_y = st.slider("Zoom in", 1.0, 4.0, 1.0, 0.1), st.slider("Move left ↔ right", 0, 100, 50) / 100, st.slider("Move up ↕ down", 0, 100, 50) / 100
    transparent_bg = st.radio("Transparent areas become", ["White", "Black"], horizontal=True)

    with st.expander("Fine tuning"):
        auto_enhance, brightness, contrast, saturation = st.checkbox("Auto-enhance photos", value=True), st.slider("Brightness", 0.5, 1.8, 1.0, 0.05), st.slider("Contrast", 0.5, 1.8, 1.0, 0.05), st.slider("Color intensity", 0.0, 2.0, 1.0, 0.05)
        sharpness, detail_boost, despeckle_label, use_dither = st.slider("Sharpness", 0.5, 3.0, 1.0, 0.1), st.slider("Detail boost (logos)", 0, 100, 80), "Off", False

    st.header("5. Look")
    style = st.selectbox("Preview style", ["Bevel (3D)", "Outlines", "Flat"])

uploaded = st.file_uploader("Upload a picture (JPG, PNG, WEBP)", type=["jpg", "jpeg", "png", "webp"])
if uploaded is None:
    st.info("👈 Pick your settings, then upload a picture to begin.")
    st.stop()

# Build the base mosaic (Heavy processing, cached)
params = dict(
    w_ratio=geo["w"], h_ratio=geo["h"], total=total_bricks, color_mode=color_mode, num_colors=num_colors,
    max_colors=max_colors, kind=kind, crop_aspect=CROPS[crop_label], zoom=zoom, pan_x=pan_x, pan_y=pan_y,
    transparent_bg=transparent_bg, auto_enhance=auto_enhance, brightness=brightness, contrast=contrast,
    saturation=saturation, sharpness=sharpness, detail_boost=detail_boost,
    despeckle={"Off": 0, "Light": 1, "Strong": 2}[despeckle_label], dither=use_dither,
    depth_studs=depth_studs, price_weight=price_weight
)

try:
    base_mosaic = build_base_mosaic(uploaded.getvalue(), params, tuple((n, tuple(c)) for n, c in active_palette.items()))
except Exception:
    st.error("That file could not be read as a picture.")
    st.stop()

# Color Swapping UI (Happens outside the cache so it maps instantly!)
st.header("6. Custom Color Override")
color_swap_map = {}
if base_mosaic.counts:
    with st.expander("🎨 Swap specific colors (Click to expand)"):
        st.write("Replace an unwanted color with a different one:")
        
        # Only show colors that actually exist in the picture!
        present_colors = list(base_mosaic.counts.keys())
        palette_choices = ["(None)"] + list(active_palette.keys())
        
        for i in range(1, 4):
            c1, c2 = st.columns(2)
            src = c1.selectbox(f"Swap this:", ["(None)"] + present_colors, key=f"src_{i}")
            tgt = c2.selectbox(f"With this:", palette_choices, key=f"tgt_{i}")
            if src != "(None)" and tgt != "(None)" and src != tgt:
                color_swap_map[src] = tgt

# Apply swaps instantly
mosaic = apply_swaps_and_pack(base_mosaic, color_swap_map, depth_studs)

# Render
preview = render_preview(mosaic.grid, geo["w"], geo["h"], style, geo["studs"], brick_id_grid=getattr(mosaic, "brick_id_grid", None))

if getattr(mosaic, "has_swaps", False):
    st.success("🎨 Custom colors applied!")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Original")
        st.image(mosaic.prepared)
    with c2:
        st.subheader("Before Swap")
        st.image(render_preview(mosaic.grid_unswapped, geo["w"], geo["h"], style, geo["studs"], brick_id_grid=getattr(base_mosaic, "brick_id_grid", None)))
    with c3:
        st.subheader("After Swap")
        st.image(preview)
else:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Your picture (after crop)")
        st.image(mosaic.prepared)
    with c2:
        st.subheader(f"LEGO result ({mosaic.nx} wide × {mosaic.ny} tall)")
        st.image(preview)

st.info(f"**Build specs:** {mosaic.nx} × {mosaic.ny} studs | **Physical bricks:** {getattr(mosaic, 'total_physical_bricks', mosaic.nx * mosaic.ny):,} | **Size:** {mosaic.nx * geo['cm'][0]:.1f} cm × {mosaic.ny * geo['cm'][1]:.1f} cm | 💰 **Est. Total:** ${mosaic.est_cost:,.2f}")

if mosaic.counts:
    st.subheader(f"📦 Parts List (Optimized for 2x4 & 2x2 bricks | Seam stagger: {mosaic.strength_pct:.0f}%)")
    lookup = {n: tuple(int(v) for v in mosaic.palette[i]) for i, n in enumerate(mosaic.names)}
    cols = st.columns(3)
    for i, (name, count) in enumerate(sorted(mosaic.counts.items(), key=lambda kv: -kv[1])):
        r, g, b = lookup[name]
        sizes_txt = " · ".join(f"<b>{depth_studs}×{w}:</b> {mosaic.brick_tally[name][w]:,}" for w in (4, 2, 1) if mosaic.brick_tally[name].get(w, 0) > 0)
        with cols[i % 3]:
            st.markdown(f"<div style='display:flex;align-items:center;gap:10px;padding:8px;border:1px solid #444;border-radius:6px;margin-bottom:8px;'><div style='width:24px;height:32px;background:#{r:02x}{g:02x}{b:02x};border:1px solid #222;border-radius:3px;'></div><div><strong>{html.escape(name)}</strong> ({count:,} studs)<br><span style='color:#ccc;font-size:0.85em;'>{sizes_txt}</span></div></div>", unsafe_allow_html=True)

st.subheader("🧱 BrickLink Studio Exports")
studs_per_step = st.slider("Кількість пікселів (стадів) в одному кроці інструкції Studio", 8, 40, 16, 2)
ldr_data = export_bricklink_studio_ldr(mosaic, geo_name, depth_studs=depth_studs, studs_per_step=studs_per_step)
xml_data = export_bricklink_wanted_xml(mosaic, geo_name, depth_studs=depth_studs)

b_col1, b_col2, b_col3 = st.columns(3)
with b_col1: st.download_button("⬇️ Download for Studio (.ldr)", ldr_data.encode("utf-8"), f"lego_{mosaic.nx}x{mosaic.ny}.ldr", "application/x-ldraw")
with b_col2: st.download_button("🛒 Download BrickLink WL (.xml)", xml_data.encode("utf-8"), f"wanted_{mosaic.nx}x{mosaic.ny}.xml", "application/xml")
with b_col3:
    if hasattr(os, "startfile") and st.button("🚀 Open Directly in BrickLink Studio"):
        out_path = os.path.join(tempfile.gettempdir(), f"lego_{mosaic.nx}x{mosaic.ny}.ldr")
        with open(out_path, "w", encoding="utf-8") as f: f.write(ldr_data)
        os.startfile(out_path)
