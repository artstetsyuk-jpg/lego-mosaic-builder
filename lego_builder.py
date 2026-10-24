"""LEGO Mosaic Builder (Streamlit).

What's different from the first version
- Colors are matched in OKLab (a perceptual color space) instead of raw RGB distance, so near-black
  pixels become LEGO Black instead of Dark Brown, and skin tones, blues and greens land on sensible bricks.
- Down-sampling is done in linear light, so thin bright details are not washed out.
- Logos / graphics use a "majority vote with detail boost" per brick instead of averaging, so a thin yellow
  outline stays yellow instead of turning into brown. Photos use gamma-correct averaging (+ optional dithering).
- Auto-detects photo vs graphic, fixes phone-photo rotation and transparent PNGs, has crop / zoom,
  limits on the number of colors, stray-brick cleanup, 3D-looking previews, and CSV downloads.
"""
import csv
import html
import io
import math

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps

st.set_page_config(page_title="LEGO Mosaic Builder", layout="wide")

# ----------------------------------------------------------------------------
# Palette (sRGB approximations of LEGO colors; real bricks vary with lighting and print)


# ----------------------------------------------------------------------------
LEGO_ALL_COLORS = {
    # --- Neutrals, Grays & Blacks (7) ---
    "White": (255, 255, 255),
    "Very Light Bluish Gray": (229, 228, 223),
    "Light Bluish Gray": (160, 165, 169),
    "Light Gray": (155, 161, 157),
    "Dark Gray": (109, 110, 92),
    "Dark Bluish Gray": (108, 110, 104),
    "Black": (18, 18, 18),

    # --- Tans, Nougats & Browns (10) ---
    "Light Nougat": (246, 215, 179),
    "Tan": (228, 205, 158),
    "Dark Tan": (149, 138, 115),
    "Nougat": (208, 145, 104),
    "Medium Nougat": (170, 125, 85),
    "Dark Nougat": (173, 97, 64),
    "Dark Orange": (169, 85, 0),
    "Reddish Brown": (88, 38, 22),
    "Brown": (88, 57, 39),
    "Dark Brown": (48, 25, 16),

    # --- Reds, Pinks, Corals & Magentas (9) ---
    "Dark Red": (114, 14, 15),
    "Red": (180, 0, 0),
    "Reddish Orange": (236, 70, 18),
    "Coral": (255, 105, 143),
    "Sand Red": (149, 121, 118),
    "Pink": (252, 151, 172),
    "Bright Pink": (228, 173, 200),
    "Dark Pink": (200, 112, 160),
    "Magenta": (146, 57, 120),

    # --- Oranges & Yellows (7) ---
    "Orange": (254, 138, 24),
    "Medium Orange": (255, 167, 11),
    "Bright Light Orange": (248, 187, 61),
    "Yellow": (250, 200, 10),
    "Light Yellow": (251, 230, 150),
    "Bright Light Yellow": (255, 240, 58),
    "Vibrant Neon Yellow": (235, 255, 0),

    # --- Greens & Limes (7) ---
    "Spring Yellowish Green": (223, 238, 165),
    "Lime": (187, 233, 11),
    "Olive Green": (155, 154, 90),
    "Sand Green": (160, 188, 172),
    "Bright Green": (75, 159, 74),
    "Green": (35, 120, 65),
    "Dark Green": (24, 70, 50),

    # --- Blues, Teals, Aquas & Azures (9) ---
    "Light Aqua": (173, 221, 213),
    "Dark Turquoise (Teal)": (0, 143, 155),
    "Medium Azure": (54, 174, 191),
    "Dark Azure": (7, 139, 201),
    "Maersk Blue": (53, 146, 195),
    "Bright Light Blue": (159, 195, 233),
    "Medium Blue": (90, 147, 219),
    "Sand Blue": (96, 116, 161),
    "Blue": (0, 85, 191),
    "Dark Blue": (10, 52, 99),

    # --- Purples & Lavenders (4) ---
    "Lavender": (225, 213, 237),
    "Medium Lavender": (172, 120, 186),
    "Purple": (129, 0, 123),
    "Dark Purple": (63, 54, 145),
}

LEGO_GRAYSCALE = {k: LEGO_ALL_COLORS[k] for k in
                  ["White", "Very Light Bluish Gray", "Light Bluish Gray", "Dark Bluish Gray", "Black"]}

# Real BrickLink availability & pricing across 3004 (1x2), 3003 (2x2), and 3001 (2x4)
BRICKLINK_1X1_PRICE = {
    # Tier 1: Massive supply across 1x2, 2x2, and 2x4 ($0.05 - $0.08)
    "Black": 0.05, "White": 0.05, "Light Bluish Gray": 0.05, "Dark Bluish Gray": 0.05,
    "Red": 0.05, "Blue": 0.05, "Yellow": 0.05, "Tan": 0.05, "Reddish Brown": 0.05,
    "Dark Tan": 0.06, "Orange": 0.06, "Lime": 0.06, "Green": 0.06, "Dark Red": 0.07,
    "Dark Blue": 0.07, "Dark Green": 0.07, "Dark Brown": 0.08, "Bright Light Orange": 0.07,
    "Medium Nougat": 0.07, "Medium Azure": 0.07, "Bright Pink": 0.07, "Dark Purple": 0.08,

    # Tier 2: Good supply across all 3 bricks ($0.09 - $0.18)
    "Dark Azure": 0.09, "Dark Turquoise (Teal)": 0.09, "Medium Blue": 0.09, "Medium Lavender": 0.10,
    "Sand Green": 0.10, "Light Aqua": 0.10, "Sand Blue": 0.11, "Bright Light Yellow": 0.10,
    "Lavender": 0.11, "Dark Orange": 0.11, "Coral": 0.11, "Dark Pink": 0.11,
    "Bright Light Blue": 0.12, "Vibrant Neon Yellow": 0.12, "Spring Yellowish Green": 0.14,
    "Olive Green": 0.15, "Light Gray": 0.18, "Dark Gray": 0.18, "Brown": 0.18,

    # Tier 3: Lower 2x4 (3001) or 2x2 (3003) supply — blocked when Price Slider >= 60 ($0.28 - $0.85)
    "Purple": 0.28, "Light Yellow": 0.28, "Pink": 0.32, "Light Nougat": 0.32,
    "Bright Green": 0.35, "Magenta": 0.35, "Medium Orange": 0.38, "Maersk Blue": 0.55,
    "Sand Red": 0.65, "Nougat": 0.65, "Reddish Orange": 0.65,
    "Very Light Bluish Gray": 0.75, "Dark Nougat": 0.85,
}

# Longer interlocking bricks cost much less per stud than four 1x1 bricks on BrickLink
BRICK_SIZE_PRICE_MULT = {1: 1.0, 2: 1.25, 3: 1.50, 4: 1.70}

def get_brick_price(color_name, width=1, depth=1):
    base = BRICKLINK_1X1_PRICE.get(color_name, 0.95)
    depth_mult = 1.18 if depth == 2 else 1.0
    return base * BRICK_SIZE_PRICE_MULT.get(width, float(width)) * depth_mult
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


def linear_to_oklab(lin):
    return np.cbrt(lin @ _M1.T) @ _M2.T


def srgb8_to_oklab(rgb8):
    return linear_to_oklab(srgb_to_linear(rgb8))


def oklab_to_srgb8(lab):
    lms = (np.asarray(lab, dtype=np.float64) @ _M2_INV.T) ** 3
    return linear_to_srgb8(lms @ _M1_INV.T)


def dist2(lab, pal, l_weight=1.0):
    """Balanced OKLab distance: keeps full brightness contrast for sharp lines without pink/orange shifts."""
    dl = lab[:, None, 0] - pal[None, :, 0]
    da = lab[:, None, 1] - pal[None, :, 1]
    db = lab[:, None, 2] - pal[None, :, 2]

    c_pix = np.hypot(lab[:, 1], lab[:, 2])[:, None]
    c_pal = np.hypot(pal[:, 1], pal[:, 2])[None, :]

    # Keep neutral grays/blacks on neutral bricks, and penalize bricks that are MORE saturated than the pixel
    # (prevents pale window reflections from turning Bright Pink and gray pavement from turning Orange)
    neutral_w = 1.0 + 6.0 * np.exp(-c_pix / 0.028)
    oversat_penalty = np.maximum(0.0, c_pal - c_pix * 1.15) ** 2

    # Pure hue difference for saturated colors so deep reds prefer Dark Red/Rust over Brown
    dh2 = np.maximum(0.0, 2.0 * (c_pix * c_pal - lab[:, None, 1] * pal[None, :, 1] - lab[:, None, 2] * pal[None, :, 2]))
    color_mask = np.clip((c_pix - 0.04) / 0.04, 0.0, 1.0)

    return (
        1.15 * l_weight * (dl * dl)
        + neutral_w * (da * da + db * db)
        + 4.5 * color_mask * dh2
        + 10.0 * oversat_penalty
    )


def nearest(lab, pal_lab, chunk=60000, l_weight=1.0, price_penalty=None):
    """Index of the closest palette color for each OKLab row, balancing color accuracy and BrickLink cost."""
    lab = np.asarray(lab, dtype=np.float32).reshape(-1, 3)
    pal = np.asarray(pal_lab, dtype=np.float32)
    out = np.empty(len(lab), dtype=np.int32)
    for s in range(0, len(lab), chunk):
        d = dist2(lab[s:s + chunk], pal, l_weight)
        if price_penalty is not None:
            d = d + price_penalty[None, :]
        out[s:s + chunk] = d.argmin(1)
    return out


def snap(rgb8, pal_lab, l_weight=1.0, price_penalty=None):
    """Palette index for every pixel of an (H, W, 3) uint8 image. Works on unique colors only (fast)."""
    flat = rgb8.reshape(-1, 3).astype(np.uint32)
    packed = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    uniq, inverse = np.unique(packed, return_inverse=True)
    u_rgb = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], axis=1).astype(np.uint8)
    idx_u = nearest(srgb8_to_oklab(u_rgb), pal_lab, l_weight=l_weight, price_penalty=price_penalty)
    return idx_u[inverse.reshape(-1)].reshape(rgb8.shape[:2])


def kmeans_palette(rgb8, k, seed=0, iters=12, max_samples=40000):
    """k adaptive colors for the picture (k-means in OKLab). Returns uint8 RGB, darkest first."""
    flat = rgb8.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    if len(flat) > max_samples:
        flat = flat[rng.choice(len(flat), max_samples, replace=False)]
    lab = srgb8_to_oklab(flat)
    k = max(1, min(k, len(np.unique(flat, axis=0))))
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
            if members.any():
                centers[j] = lab[members].mean(0)
    centers = centers[np.argsort(centers[:, 0])]
    return oklab_to_srgb8(centers)


# ----------------------------------------------------------------------------
# Image preparation
# ----------------------------------------------------------------------------
def load_image(file_bytes, transparent_bg="White"):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)))  # phone photos: respect rotation
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255) if transparent_bg == "White" else (0, 0, 0, 255))
        img = Image.alpha_composite(base, rgba).convert("RGB")
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_SOURCE_SIDE, MAX_SOURCE_SIDE), Image.Resampling.LANCZOS)
    return img


def crop_image(img, aspect, zoom, pan_x, pan_y):
    """Crop to an aspect ratio, then zoom in. pan_x / pan_y are 0..1 (0.5 = centered)."""
    w, h = img.size
    if aspect is None:
        cw, ch = float(w), float(h)
    elif w / h > aspect:
        cw, ch = h * aspect, float(h)
    else:
        cw, ch = float(w), w / aspect
    cw, ch = max(1.0, cw / zoom), max(1.0, ch / zoom)
    left, top = (w - cw) * pan_x, (h - ch) * pan_y
    box = (int(round(left)), int(round(top)), int(round(left + cw)), int(round(top + ch)))
    box = (box[0], box[1], max(box[2], box[0] + 1), max(box[3], box[1] + 1))
    return img.crop(box)


def grid_size(img_w, img_h, total, w_ratio, h_ratio):
    """Bricks across / down for ~`total` bricks, keeping the picture's proportions."""
    nx = max(1, round(math.sqrt(total * (img_w / img_h) * (h_ratio / w_ratio))))
    ny = max(1, round(nx * (img_h / img_w) * (w_ratio / h_ratio)))
    return min(nx, MAX_GRID_SIDE), min(ny, MAX_GRID_SIDE)


def detect_kind(img):
    """'graphic' when a handful of colors cover almost the whole picture (logos, pixel art), else 'photo'."""
    small = np.asarray(img.resize((min(img.width, 256), min(img.height, 256)), Image.Resampling.BILINEAR))
    q = (small >> 4).astype(np.int32)
    counts = np.bincount(((q[..., 0] << 8) | (q[..., 1] << 4) | q[..., 2]).ravel(), minlength=4096)
    return "graphic" if np.sort(counts)[::-1][:6].sum() / counts.sum() > 0.80 else "photo"


def supersample(nx, ny, kind):
    if kind == "graphic":
        return int(min(10, max(3, math.sqrt(2.5e6 / (nx * ny)))))
    return 4


def enhance(img, p, kind):
    brightness, contrast, saturation = p["brightness"], p["contrast"], p["saturation"]
    if kind == "photo" and p["auto_enhance"]:
        # Gentle luminance stretch that lifts dark shadow separation without shifting RGB hues
        arr = np.asarray(img, dtype=np.float32)
        lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
        lo, hi = np.percentile(lum, (1, 99.5))
        if hi > lo + 1e-3:
            norm_l = np.clip((lum - lo) / (hi - lo), 0.0, 1.0)
            # Slight gamma lift (0.88) opens up dark red car contours so they don't crush into one brick
            lifted_l = (norm_l ** 0.88) * 255.0
            scale = lifted_l / np.maximum(lum, 1.0)
            arr = np.clip(arr * scale[..., None], 0, 255)
            img = Image.fromarray(arr.astype(np.uint8))
        contrast, saturation = contrast * 1.06, saturation * 1.08
    for enhancer, factor in ((ImageEnhance.Brightness, brightness), (ImageEnhance.Contrast, contrast),
                             (ImageEnhance.Color, saturation)):
        if abs(factor - 1.0) > 1e-3:
            img = enhancer(img).enhance(factor)
    return img


# ----------------------------------------------------------------------------
# Turning pixels into bricks
# ----------------------------------------------------------------------------
def average_cells(hi_rgb8, nx, ny, S):
    """Gamma-correct average of each S x S block (averaging in linear light keeps bright details bright)."""
    lin = srgb_to_linear(hi_rgb8).reshape(ny, S, nx, S, 3).mean(axis=(1, 3))
    return linear_to_srgb8(lin)


def graphic_cells(hi_rgb8, nx, ny, S, pal_lab, boost):
    """Palette index per brick for logos, text, icons and pixel art.

    Averaging a thin colored line with its background gives a muddy in-between color (yellow + black = brown).
    Instead, per brick we (1) estimate how much of it is foreground (area coverage, so blended anti-aliased
    edge pixels count partially), and (2) take the foreground color from the PUREST pixels, the ones farthest
    from the background, never from the blend. `boost` (0-100) lowers the coverage needed to claim a brick.
    """
    K = len(pal_lab)
    lab = srgb8_to_oklab(hi_rgb8).astype(np.float32)
    idx_all = snap(hi_rgb8, pal_lab)
    bg = int(np.bincount(idx_all.ravel(), minlength=K).argmax())
    bg_lab = np.median(lab[idx_all == bg], axis=0)  # the background as it really appears in the picture
    dist = np.linalg.norm(lab - bg_lab, axis=2)
    idx_fg = snap(hi_rgb8, pal_lab, l_weight=0.5)  # foreground: judge by hue/saturation more than lightness

    def blocks(a):
        return a.reshape(ny, S, nx, S).transpose(0, 2, 1, 3).reshape(ny, nx, S * S)

    d, f = blocks(dist), blocks(idx_fg)
    pure = d >= 0.75 * d.max(-1, keepdims=True)
    votes = np.zeros((ny, nx, K), dtype=np.float32)
    for k in np.unique(idx_fg):
        votes[..., k] = ((f == k) & pure).sum(-1)
    fg_idx = votes.argmax(-1)
    fg_dist = (d * pure).sum(-1) / np.maximum(pure.sum(-1), 1)
    coverage = np.clip(d / np.maximum(fg_dist[..., None], 1e-6), 0, 1).mean(-1)
    needed = 0.5 - 0.38 * boost / 100.0
    is_fg = (coverage >= needed) & (fg_dist >= 0.08)  # tiny differences are just noise
    return np.where(is_fg, fg_idx, bg).astype(np.int32)


def dither(cell_lab, pal_lab, strength=0.85):
    """Floyd-Steinberg error diffusion in OKLab (serpentine). Smoother gradients, noisier look."""
    work = cell_lab.astype(np.float64).copy()
    pal = np.asarray(pal_lab, dtype=np.float64)
    ny, nx = work.shape[:2]
    out = np.zeros((ny, nx), dtype=np.int32)
    for y in range(ny):
        forward = y % 2 == 0
        step = 1 if forward else -1
        for x in (range(nx) if forward else range(nx - 1, -1, -1)):
            old = work[y, x]
            i = int(dist2(old[None, :], pal)[0].argmin())
            out[y, x] = i
            err = (old - pal[i]) * strength
            if 0 <= x + step < nx:
                work[y, x + step] += err * 7 / 16
            if y + 1 < ny:
                if 0 <= x - step < nx:
                    work[y + 1, x - step] += err * 3 / 16
                work[y + 1, x] += err * 5 / 16
                if 0 <= x + step < nx:
                    work[y + 1, x + step] += err * 1 / 16
    return out


def despeckle(idx, K, level):
    """Replace stray bricks that disagree with all their neighbors. level 1 = isolated bricks only."""
    if level <= 0 or idx.shape[0] < 3 or idx.shape[1] < 3:
        return idx
    ny, nx = idx.shape
    onehot = np.zeros((ny, nx, K), dtype=np.int16)
    onehot[np.arange(ny)[:, None], np.arange(nx)[None, :], idx] = 1
    pad = np.pad(onehot, ((1, 1), (1, 1), (0, 0)))
    nb = sum(pad[1 + dy:1 + dy + ny, 1 + dx:1 + dx + nx]
             for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0))
    same = np.take_along_axis(nb, idx[..., None], axis=2)[..., 0]
    best, best_n = nb.argmax(-1), nb.max(-1)
    replace = (same <= (0 if level == 1 else 1)) & (best_n >= 3)
    return np.where(replace, best, idx)


def limit_colors(idx, cell_lab, pal_lab, max_colors):
    """Keep only the `max_colors` most used colors; every brick moves to its nearest kept color."""
    used, counts = np.unique(idx, return_counts=True)
    if max_colors <= 0 or len(used) <= max_colors:
        return idx
    keep = used[np.argsort(-counts)[:max_colors]]
    choice = nearest(cell_lab.reshape(-1, 3), pal_lab[keep])
    return keep[choice].reshape(idx.shape)


class Mosaic:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        
def pack_interlocking_wall(idx_grid, names, depth=2):
    """
    Pack a (ny, nx) color grid into interlocking bricks using ONLY widths (1, 2, 4).
    Heavily prioritizes 4-wide (2x4) bricks whenever 4 matching studs exist, using a single
    2-wide brick at the edge of alternating rows so the 2x4s lock together in a running bond.
    """
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
            if dp[x][0] <= -1e8:
                continue
            color = row[x]
            for w in allowed_widths:
                nx_pos = x + w
                if nx_pos > nx or not np.all(row[x:nx_pos] == color):
                    break

                # Strongly prioritize 4-wide bricks (16.0) over two 2-wide bricks (2 * 5.0 = 10.0)
                score = {1: 1.0, 2: 5.0, 4: 16.0}[w]

                # Penalize vertical seams that line up directly with a seam on the row below
                if nx_pos < nx and nx_pos in prev_seams:
                    score -= 5.0

                # Bonus for bridging across seams from the row below (locks the wall together)
                for internal_x in range(x + 1, nx_pos):
                    if internal_x in prev_seams:
                        score += 2.5

                # On odd rows, slight nudge to start a color run with one 2x2 so all following 2x4s stagger
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
            if start_x > 0:
                current_seams.add(start_x)
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
                if s_x not in prev_seams:
                    staggered_seams += 1
        prev_seams = current_seams

    strength_pct = 100.0 * staggered_seams / max(total_seams, 1)
    return brick_spans, brick_id_grid, parts_tally, strength_pct


def build_mosaic(file_bytes, p, palette_items):
    """The whole pipeline. `p` holds the settings (see the UI), `palette_items` is [(name, (r, g, b)), ...]."""
    img = crop_image(load_image(file_bytes, p["transparent_bg"]), p["crop_aspect"], p["zoom"], p["pan_x"], p["pan_y"])
    nx, ny = grid_size(img.width, img.height, p["total"], p["w_ratio"], p["h_ratio"])
    kind = p["kind"] if p["kind"] != "auto" else detect_kind(img)
    S = supersample(nx, ny, kind)

    upscaling = img.width < nx * S or img.height < ny * S
    resample = Image.Resampling.NEAREST if (kind == "graphic" and upscaling) else Image.Resampling.LANCZOS
    hi = img.resize((nx * S, ny * S), resample)
    if p["color_mode"] == "lego_gray":
        hi = ImageOps.grayscale(hi).convert("RGB")
    hi = enhance(hi, p, kind)
    hi_rgb8 = np.asarray(hi)

    cells = average_cells(hi_rgb8, nx, ny, S)
    if kind == "photo":
        eff_sharp = p["sharpness"] * 1.35 if p["auto_enhance"] else p["sharpness"]
        if abs(eff_sharp - 1.0) > 1e-3:
            cells = np.asarray(ImageEnhance.Sharpness(Image.fromarray(cells)).enhance(eff_sharp))

    result = dict(nx=nx, ny=ny, kind=kind, prepared=img, names=None, palette=None, idx=None, counts=None)
    if p["color_mode"] == "true":
        result["grid"] = cells
        return Mosaic(**result)

    if p["color_mode"] == "adaptive":
        pal_rgb = kmeans_palette(hi_rgb8, p["num_colors"])
        names = [f"Color {i + 1}" for i in range(len(pal_rgb))]
    else:
        names = [n for n, _ in palette_items]
        pal_rgb = np.array([c for _, c in palette_items], dtype=np.uint8)
    pal_lab = srgb8_to_oklab(pal_rgb)

    # Calculate BrickLink price penalty per palette color based on user's Price-to-Color slider (0..100)
    price_weight = p.get("price_weight", 55) / 100.0
    if p["color_mode"] in ("lego_all", "lego_pick") and price_weight > 0:
        raw_prices = np.array([BRICKLINK_1X1_PRICE.get(n, 0.95) for n in names], dtype=np.float64)
        price_penalty = (price_weight ** 1.2) * 0.35 * ((raw_prices - 0.05) ** 1.2)
        # Slider >= 85 strictly locks to cheap $0.05-$0.10 bricks; >= 60 blocks rare $0.25+ bricks
        if price_weight >= 0.85:
            price_penalty = np.where(raw_prices > 0.10, 1e6, price_penalty)
        elif price_weight >= 0.60:
            price_penalty = np.where(raw_prices > 0.25, 1e6, price_penalty)
    else:
        price_penalty = None

    if kind == "graphic":
        idx = graphic_cells(hi_rgb8, nx, ny, S, pal_lab, p["detail_boost"])
        if price_penalty is not None:
            idx = nearest(pal_lab[idx].reshape(-1, 3), pal_lab, price_penalty=price_penalty).reshape(ny, nx)
        cell_lab = pal_lab[idx]
    elif p["color_mode"] in ("lego_all", "lego_pick") and not p["dither"]:
        n_clusters = p["max_colors"] if p["max_colors"] > 0 else 20
        adap_rgb = kmeans_palette(hi_rgb8, n_clusters)
        adap_lab = srgb8_to_oklab(adap_rgb)
        cell_lab = srgb8_to_oklab(cells)

        cluster_idx = ((cell_lab.reshape(-1, 1, 3) - adap_lab[None, :, :]) ** 2).sum(2).argmin(1).reshape(ny, nx)

        d_mat = dist2(adap_lab, pal_lab)
        if price_penalty is not None:
            d_mat = d_mat + price_penalty[None, :]
        _, cluster_counts = np.unique(cluster_idx, return_counts=True)
        order = np.argsort(-cluster_counts)
        cluster_to_lego = np.zeros(len(adap_rgb), dtype=np.int32)
        used_penalty = np.zeros(len(pal_rgb), dtype=np.float64)

        for c_i in order:
            # Don't force duplicate background clusters (like pure White or Black) onto different grays
            if d_mat[c_i].min() < 0.0025:
                best_lego = int(d_mat[c_i].argmin())
            else:
                best_lego = int((d_mat[c_i] + used_penalty).argmin())
                used_penalty[best_lego] += 0.008
            cluster_to_lego[c_i] = best_lego

        idx = cluster_to_lego[cluster_idx]
    else:
        cell_lab = srgb8_to_oklab(cells)
        idx = dither(cell_lab, pal_lab) if p["dither"] else nearest(cell_lab, pal_lab, price_penalty=price_penalty).reshape(ny, nx)
    # Apply custom color overrides if specified by the user
    color_swap_map = p.get("color_swap_map", {})
    if color_swap_map and names:
        name_to_idx = {n: i for i, n in enumerate(names)}
        for src_name, tgt_name in color_swap_map.items():
            if src_name in name_to_idx and tgt_name in name_to_idx:
                src_i = name_to_idx[src_name]
                tgt_i = name_to_idx[tgt_name]
                idx[idx == src_i] = tgt_i
    idx = despeckle(idx, len(pal_rgb), p["despeckle"])
    idx = limit_colors(idx, cell_lab, pal_lab, p["max_colors"])

    brick_spans, brick_id_grid, brick_tally, strength_pct = pack_interlocking_wall(
        idx, names, depth=p.get("depth_studs", 2)
    )
    total_physical_bricks = sum(sum(w_counts.values()) for w_counts in brick_tally.values())

    used, counts = np.unique(idx, return_counts=True)
    depth_val = p.get("depth_studs", 2)
    est_cost = sum(
        qty * get_brick_price(c_name, width=w, depth=depth_val)
        for c_name, w_counts in brick_tally.items()
        for w, qty in w_counts.items()
    )
    raw_1x1_cost = sum(
        cnt * get_brick_price(c_name, width=1, depth=depth_val)
        for c_name, cnt in zip([names[int(u)] for u in used], counts)
    )
    result.update(
        idx=idx, grid=pal_rgb[idx], names=names, palette=pal_rgb,
        counts={names[int(u)]: int(c) for u, c in zip(used, counts)},
        brick_spans=brick_spans, brick_id_grid=brick_id_grid,
        brick_tally=brick_tally, total_physical_bricks=total_physical_bricks,
        strength_pct=strength_pct, est_cost=est_cost, raw_1x1_cost=raw_1x1_cost,
    )
    return Mosaic(**result)


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------
def _shade_tile(cw, ch, style):
    tile = np.ones((ch, cw, 3), dtype=np.float32)
    if style == "Bevel (3D)":
        e = max(1, min(cw, ch) // 8)
        tile[:e] *= 1.18
        tile[:, :e] *= 1.08
        tile[-e:] *= 0.78
        tile[:, -e:] *= 0.88
    elif style == "Outlines":
        tile[0] *= 0.5
        tile[:, 0] *= 0.5
    return tile


def _stud_sprite(s):
    yy, xx = (np.mgrid[0:s, 0:s] + 0.5) / s
    dist = np.hypot(xx - 0.5, yy - 0.5)
    mask = np.clip((0.36 - dist) / (1.2 / s) + 0.5, 0, 1)
    glow = np.exp(-(((xx - 0.42) ** 2 + (yy - 0.40) ** 2) / 0.01))
    rim = np.clip((dist - 0.22) / 0.14, 0, 1)
    return mask.astype(np.float32), (1.0 + 0.25 * glow - 0.20 * rim).astype(np.float32)


def render_preview(grid, w_ratio, h_ratio, style, studs, target_width=1100, brick_id_grid=None, depth_studs=2, show_3d_top=True):
    """Draw the brick wall with true merged 1x2/1x3/1x4 seams and an optional 2-stud 3D top edge."""
    ny, nx, _ = grid.shape
    if studs and style == "Round studs":
        s = int(np.clip(round(target_width / nx), 8, 24))
        up = np.repeat(np.repeat(grid, s, 0), s, 1).astype(np.float32)
        mask, shade = _stud_sprite(s)
        m, sh = np.tile(mask, (ny, nx))[..., None], np.tile(shade, (ny, nx))[..., None]
        out = up * 0.45 * (1 - m) + np.clip(up * sh, 0, 255) * m
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    scale = int(np.clip(round(target_width / (nx * w_ratio)), 2, 14))
    cw, ch = w_ratio * scale, h_ratio * scale
    up = np.repeat(np.repeat(grid, ch, 0), cw, 1).astype(np.float32)

    if brick_id_grid is not None and style in ("Bevel (3D)", "Outlines"):
        # Upscale brick IDs to pixel level so seams ONLY appear between distinct physical bricks
        bid_up = np.repeat(np.repeat(brick_id_grid, ch, 0), cw, 1)
        top_edge = np.zeros_like(bid_up, dtype=bool)
        top_edge[0, :] = True
        top_edge[1:, :] = bid_up[1:, :] != bid_up[:-1, :]

        left_edge = np.zeros_like(bid_up, dtype=bool)
        left_edge[:, 0] = True
        left_edge[:, 1:] = bid_up[:, 1:] != bid_up[:, :-1]

        if style == "Outlines":
            seam = top_edge | left_edge
            up[seam] *= 0.38
        else:  # Bevel (3D) across full 1x2, 1x3, 1x4 bricks
            bot_edge = np.zeros_like(bid_up, dtype=bool)
            bot_edge[-1, :] = True
            bot_edge[:-1, :] = bid_up[:-1, :] != bid_up[1:, :]

            right_edge = np.zeros_like(bid_up, dtype=bool)
            right_edge[:, -1] = True
            right_edge[:, :-1] = bid_up[:, :-1] != bid_up[:, 1:]

            up[top_edge] = np.clip(up[top_edge] * 1.22, 0, 255)
            up[left_edge] = np.clip(up[left_edge] * 1.12, 0, 255)
            up[bot_edge] = np.clip(up[bot_edge] * 0.68, 0, 255)
            up[right_edge] = np.clip(up[right_edge] * 0.75, 0, 255)
        front_img = Image.fromarray(np.clip(up, 0, 255).astype(np.uint8))
    else:
        out = np.clip(up * np.tile(_shade_tile(cw, ch, style), (ny, nx, 1)), 0, 255)
        front_img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    # Optional 3D isometric top & side depth preview showing the 2-stud depth ("dots in length")
    if show_3d_top and not studs and depth_studs >= 1:
        from PIL import ImageDraw
        fw, fh = front_img.size
        depth_px = max(12, int(cw * depth_studs * 0.55))
        canvas = Image.new("RGB", (fw + depth_px, fh + depth_px), (30, 34, 40))
        canvas.paste(front_img, (0, depth_px))
        draw = ImageDraw.Draw(canvas)

        # Draw top 2-stud roof and studs for each brick in the top row (y = 0)
        top_row_rgb = grid[0]
        top_row_ids = brick_id_grid[0] if brick_id_grid is not None else np.arange(nx)
        for x in range(nx):
            r, g, b = [int(v) for v in top_row_rgb[x]]
            top_color = (min(255, int(r * 1.15)), min(255, int(g * 1.15)), min(255, int(b * 1.15)))
            x0, x1 = x * cw, (x + 1) * cw
            poly = [(x0, depth_px), (x1, depth_px), (x1 + depth_px, 0), (x0 + depth_px, 0)]
            draw.polygon(poly, fill=top_color)
            if x == 0 or top_row_ids[x] != top_row_ids[x - 1]:
                draw.line([(x0, depth_px), (x0 + depth_px, 0)], fill=(40, 40, 40), width=1)

            # Draw the `depth_studs` (e.g. 2 dots) along the depth of each column
            for d_i in range(depth_studs):
                frac = (d_i + 0.5) / depth_studs
                cx = int(x0 + cw * 0.5 + depth_px * frac)
                cy = int(depth_px * (1.0 - frac))
                rad_x = max(2, int(cw * 0.26))
                rad_y = max(1, int(rad_x * 0.55))
                draw.ellipse([cx - rad_x, cy - rad_y, cx + rad_x, cy + rad_y],
                             fill=top_color, outline=(40, 40, 40))

        # Draw right-hand 3D side wall (depth profile)
        for y in range(ny):
            r, g, b = [int(v) for v in grid[y, -1]]
            side_color = (int(r * 0.72), int(g * 0.72), int(b * 0.72))
            y0, y1 = depth_px + y * ch, depth_px + (y + 1) * ch
            poly = [(fw, y0), (fw + depth_px, y0 - depth_px),
                    (fw + depth_px, y1 - depth_px), (fw, y1)]
            draw.polygon(poly, fill=side_color, outline=(40, 40, 40))
        return canvas

    return front_img


def parts_csv(mosaic, depth_studs):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Color", "Hex", "Brick Size", "Quantity", "Est. Unit Price (USD)", "Est. Total Price (USD)"])
    lookup = {n: tuple(int(v) for v in mosaic.palette[i]) for i, n in enumerate(mosaic.names)}
    for name, _ in sorted(mosaic.counts.items(), key=lambda kv: -kv[1]):
        r, g, b = lookup[name]
        w_counts = mosaic.brick_tally[name]
        for w in (4, 2, 1):
            qty = w_counts.get(w, 0)
            if qty > 0:
                unit_p = get_brick_price(name, width=w, depth=depth_studs)
                writer.writerow([name, f"#{r:02x}{g:02x}{b:02x}", f"Brick {depth_studs}x{w}", qty, f"{unit_p:.2f}", f"{qty * unit_p:.2f}"])
    return buf.getvalue().encode("utf-8-sig")


def build_map_csv(mosaic):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in mosaic.idx:
        writer.writerow([mosaic.names[int(i)] for i in row])
    return buf.getvalue().encode("utf-8-sig")



import os
import tempfile

# Official LDraw Color Codes for all 105 LEGO colors in your palette
LDRAW_COLOR_CODES = {
    "Milky White": 79, "White": 15, "Very Light Gray": 503, "Very Light Bluish Gray": 151,
    "Light Bluish Gray": 71, "Light Gray": 7, "Dark Gray": 8, "Dark Bluish Gray": 72, "Black": 0,
    "Very Light Orange": 509, "Light Nougat": 78, "Tan": 19, "Warm Tan": 371, "Dark Tan": 28,
    "Nougat": 92, "Medium Nougat": 84, "Dark Nougat": 128, "Fabuland Brown": 450, "Sienna Brown": 370,
    "Light Brown": 86, "Medium Brown": 86, "Dark Orange": 484, "Rust": 216, "Reddish Brown": 70,
    "Brown": 6, "Umber Brown": 86, "Dark Brown": 308, "Dark Red": 320, "Red": 4, "Coral Red": 4,
    "Reddish Orange": 402, "Salmon": 12, "Light Salmon": 100, "Coral": 353, "Sand Red": 335,
    "Light Pink": 9, "Pink": 13, "Rose Pink": 13, "Bright Pink": 29, "Medium Dark Pink": 351,
    "Dark Pink": 5, "Magenta": 26, "Reddish Violet": 26, "Earth Orange": 366, "Fabuland Orange": 191,
    "Orange": 25, "Medium Orange": 462, "Bright Light Orange": 191, "Light Orange": 462,
    "Dark Yellow": 182, "Yellow": 14, "Medium Yellow": 14, "Light Yellow": 18,
    "Bright Light Yellow": 226, "Vibrant Neon Yellow": 368, "Lemon": 226,
    "Spring Yellowish Green": 326, "Light Lime": 326, "Medium Lime": 115, "Lime": 27,
    "Electric Green": 10, "Olive Green": 330, "Dark Olive Green": 288, "Light Green": 17,
    "Medium Green": 74, "Sand Green": 378, "Bright Green": 10, "Green": 2, "Dark Green": 288,
    "Deep Green": 288, "Light Aqua": 323, "Aqua": 118, "Light Turquoise": 11,
    "Dark Turquoise (Teal)": 3, "Medium Azure": 322, "Dark Azure": 321, "Maersk Blue": 313,
    "Sky Blue": 232, "Light Blue": 9, "Bright Light Blue": 212, "Pastel Blue": 73,
    "Medium Blue": 73, "Sand Blue": 379, "Blue": 1, "Dark Royal Blue": 73, "Dark Blue": 272,
    "Lavender": 31, "Light Lilac": 219, "Light Violet": 20, "Medium Lavender": 30,
    "Sand Purple": 373, "Lilac": 219, "Medium Violet": 110, "Violet": 110, "Purple": 22,
    "Dark Purple": 85, "Deep Purple": 85, "Pearl Light Gray": 135, "Metallic Silver": 80,
    "Flat Silver": 179, "Pearl Dark Gray": 148, "Titanium Metallic": 87, "Warm Gold": 297,
    "Pearl Gold": 297, "Copper": 134,
}


def _compute_staggered_spans(idx_grid, allowed_widths=(4, 2, 1)):
    """Packs same-color horizontal runs into staggered 4, 2, 1 bricks so seams don't line up."""
    ny, nx = idx_grid.shape
    spans = np.zeros((ny, nx), dtype=np.int32)
    prev_seams = set()

    for y in range(ny - 1, -1, -1):
        row = idx_grid[y]
        # Dynamic programming across the row to minimize brick count while avoiding seams below
        dp_cost = [10**9] * (nx + 1)
        dp_prev = [0] * (nx + 1)
        dp_cost[0] = 0

        for end in range(1, nx + 1):
            for w in allowed_widths:
                start = end - w
                if start < 0:
                    continue
                if np.all(row[start:end] == row[start]):
                    seam_penalty = 25 if (end < nx and end in prev_seams) else 0
                    cost = dp_cost[start] + 10 + seam_penalty
                    if cost < dp_cost[end]:
                        dp_cost[end] = cost
                        dp_prev[end] = w

        cur = nx
        new_seams = set()
        while cur > 0:
            w = dp_prev[cur]
            start = cur - w
            spans[y, start] = w
            if cur < nx:
                new_seams.add(cur)
            cur = start
        prev_seams = new_seams

    return spans


def export_bricklink_studio_ldr(mosaic, geo_name, depth_studs=2):
    """
    Generates an LDraw (.ldr) 3D model where every merged brick (2x4, 2x2, 2x1 or 1x4, 1x2, 1x1)
    is a separate, clickable 3D LEGO part inside BrickLink Studio.
    """
    if getattr(mosaic, "grid", None) is None:
        return None

    ny, nx, _ = mosaic.grid.shape
    is_plate = "plate" in geo_name.lower()
    is_studs_out = "studs facing out" in geo_name.lower()

    # Map every pixel to an official LEGO color name & LDraw code (works even in Adaptive/True Color modes)
    lego_names = list(LEGO_ALL_COLORS.keys())
    lego_rgb = np.array(list(LEGO_ALL_COLORS.values()), dtype=np.float32)

    if getattr(mosaic, "idx", None) is not None and getattr(mosaic, "names", None) is not None:
        idx_grid = mosaic.idx
        row_names = mosaic.names
    else:
        flat_px = mosaic.grid.reshape(-1, 3).astype(np.float32)
        d2 = ((flat_px[:, None, :] - lego_rgb[None, :, :]) ** 2).sum(axis=2)
        idx_grid = d2.argmin(axis=1).reshape(ny, nx)
        row_names = lego_names

    # Map each palette entry to an official LDraw integer color ID
    palette_ldraw_ids = []
    for i, name in enumerate(row_names):
        if name in LDRAW_COLOR_CODES:
            palette_ldraw_ids.append(LDRAW_COLOR_CODES[name])
        else:
            # Nearest LEGO color fallback for "Color 1", "Color 2", etc. in Adaptive mode
            rgb = mosaic.palette[i].astype(np.float32)
            closest_idx = int(((lego_rgb - rgb) ** 2).sum(axis=1).argmin())
            palette_ldraw_ids.append(LDRAW_COLOR_CODES.get(lego_names[closest_idx], 15))

    # Use existing interlocking brick spans, or compute staggered 4/2/1 spans automatically
    spans = getattr(mosaic, "brick_spans", None)
    if spans is None and not is_studs_out:
        spans = _compute_staggered_spans(idx_grid, allowed_widths=(4, 2, 1))
    elif is_studs_out:
        spans = np.ones((ny, nx), dtype=np.int32)

    # LDraw coordinate units: 1 stud width = 20 LDU, 1 brick height = 24 LDU, 1 plate height = 8 LDU
    stud_w = 20
    layer_h = 8 if is_plate else 24

    # Official LDraw 3D part numbers for each brick width (1, 2, 3, 4)
    if is_plate:
        parts_d1 = {1: "3024", 2: "3023", 3: "3623", 4: "3710"}
        parts_d2 = {1: "3023", 2: "3022", 3: "3021", 4: "3020"}
    else:
        parts_d1 = {1: "3005", 2: "3004", 3: "3622", 4: "3010"}
        parts_d2 = {1: "3004", 2: "3003", 3: "3002", 4: "3001"}

    lines = [
        "0 LEGO Interlocking Side-Stack Mosaic",
        "0 Name: lego_mosaic.ldr",
        "0 Author: LEGO Mosaic Builder",
        "0 !LDRAW_ORG Unofficial_Model",
    ]

    x_offset = nx * stud_w // 2  # Center model at X=0 in Studio

    # Stack rows from bottom (ny - 1) to top (0) so Step 1 is the bottom base layer
    # Складаємо ряди знизу вгору (ny - 1 -> 0), розбиваючи кожен ряд на кроки по 16-20 пікселів
    for y in range(ny - 1, -1, -1):
        ldraw_y = (y - ny) * layer_h
        studs_in_step = 0

        for x in range(nx):
            w = int(spans[y, x])
            if w <= 0:
                continue  # Цей піксель вже зайнятий ширшою цеглиною зліва

            ldraw_color = palette_ldraw_ids[int(idx_grid[y, x])]
            ldraw_x = (x * stud_w + w * (stud_w // 2)) - x_offset
            ldraw_z = 0

            if is_studs_out:
                lines.append(
                    f"1 {ldraw_color} {ldraw_x} 0 {(y * stud_w) - (ny * 10)} 1 0 0 0 1 0 0 0 1 3024.dat"
                )
            else:
                if depth_studs == 2:
                    part_id = parts_d2.get(w, "3004")
                    rot = "0 0 1 0 1 0 -1 0 0" if w == 1 else "1 0 0 0 1 0 0 0 1"
                else:
                    part_id = parts_d1.get(w, "3005")
                    rot = "1 0 0 0 1 0 0 0 1"

                lines.append(f"1 {ldraw_color} {ldraw_x} {ldraw_y} {ldraw_z} {rot} {part_id}.dat")

            studs_in_step += w
            # Коли набралося 16-20 пікселів і ряд ще не закінчився — робимо новий крок у Studio
            if studs_in_step >= studs_per_step and (x + w) < nx:
                lines.append("0 STEP")
                studs_in_step = 0

        # Закриваємо крок у кінці ряду перед переходом на наступний рівень вгору
        if studs_in_step > 0:
            lines.append("0 STEP")

    return "\r\n".join(lines)
# ============================================================================
# UI
# ============================================================================
@st.cache_data(show_spinner="Building your mosaic...", max_entries=12)
def build_cached(file_bytes, params, palette_items):
    return build_mosaic(file_bytes, params, palette_items)


st.title("🧱 LEGO Mosaic Builder")
st.write("Upload any picture and turn it into a LEGO brick mosaic with a parts list and BrickLink cost breakdown.")

with st.sidebar:
    st.header("1. Brick type")
    geo_name = st.selectbox("Piece type & view", list(GEOMETRY))
    geo = GEOMETRY[geo_name]
    depth_studs = st.radio(
        "Wall depth (3rd dimension / studs deep)", [1, 2], index=1, horizontal=True,
        help="2 studs deep uses 2x1, 2x2, and 2x4 bricks so the wall stands solidly on its own."
    )
    show_3d_top = st.checkbox("Show 3D 2-stud top & side edge", value=True)

    st.header("2. Size")
    total_bricks = st.slider("Target number of pieces (budget)", 100, 20000, 2500, 100)

    st.header("3. Colors")
    price_weight = st.slider(
        "💰 BrickLink Price-to-Color Ratio", 0, 100, 55, 5,
        help="0 = Pure color accuracy (ignores price, may use $0.95+ rare bricks). "
             "55 = Sweet spot. "
             "60+ = Blocks expensive retired bricks ($0.25+). "
             "85+ = Strictly locks to the cheapest $0.05-$0.10 bricks."
    )
    mode_label = st.radio("Palette", [
        "All official LEGO colors", "Pick specific LEGO colors", "LEGO grayscale (5 shades)",
        "Adaptive colors (not LEGO-limited)", "True color (no palette)"])
    color_mode = {"All official LEGO colors": "lego_all", "Pick specific LEGO colors": "lego_pick",
                  "LEGO grayscale (5 shades)": "lego_gray", "Adaptive colors (not LEGO-limited)": "adaptive",
                  "True color (no palette)": "true"}[mode_label]

    active_palette = dict(LEGO_ALL_COLORS)
    num_colors, max_colors = 16, 0
    if color_mode == "lego_pick":
        chosen = st.multiselect("Available brick colors", list(LEGO_ALL_COLORS),
                                default=["White", "Light Bluish Gray", "Dark Bluish Gray", "Black",
                                         "Red", "Blue", "Yellow", "Tan"])
        if not chosen:
            st.warning("Pick at least one color. Using Black and White.")
            chosen = ["White", "Black"]
        active_palette = {k: LEGO_ALL_COLORS[k] for k in chosen}
    elif color_mode == "lego_gray":
        active_palette = dict(LEGO_GRAYSCALE)
    elif color_mode == "adaptive":
        num_colors = st.slider("Number of colors", 2, 64, 16)

    if color_mode in ("lego_all", "lego_pick"):
        with st.expander("➕ Add a custom brick color"):
            custom_hex = st.color_picker("Color", "#FF5500")
            custom_name = st.text_input("Name", "My custom brick").strip() or "My custom brick"
            if st.checkbox("Include this color"):
                active_palette[custom_name] = tuple(int(custom_hex[i:i + 2], 16) for i in (1, 3, 5))
    if color_mode in ("lego_all", "lego_pick", "lego_gray", "adaptive"):
        max_colors = st.slider("Limit different colors (0 = no limit)", 0, 30, 0,
                               help="Fewer colors = fewer part types to buy and sort.")

    st.header("4. Your picture")
    kind_label = st.selectbox("Picture type", ["Auto-detect", "Photo", "Logo / graphic / pixel art"],
                              help="Photos are averaged smoothly. Logos and graphics keep thin lines and flat colors.")
    kind = {"Auto-detect": "auto", "Photo": "photo", "Logo / graphic / pixel art": "graphic"}[kind_label]
    crop_label = st.selectbox("Crop shape", list(CROPS))
    zoom = st.slider("Zoom in", 1.0, 4.0, 1.0, 0.1)
    pan_x = st.slider("Move left ↔ right", 0, 100, 50) / 100
    pan_y = st.slider("Move up ↕ down", 0, 100, 50) / 100
    transparent_bg = st.radio("Transparent areas become", ["White", "Black"], horizontal=True)

    with st.expander("Fine tuning"):
        
        auto_enhance = st.checkbox("Auto-enhance photos (levels + slight color boost)", value=True)
        brightness = st.slider("Brightness", 0.5, 1.8, 1.0, 0.05)
        contrast = st.slider("Contrast", 0.5, 1.8, 1.0, 0.05)
        saturation = st.slider("Color intensity", 0.0, 2.0, 1.0, 0.05)
        sharpness = st.slider("Sharpness (photos)", 0.5, 3.0, 1.0, 0.1)
        detail_boost = st.slider("Thin-detail boost (logos / graphics)", 0, 100, 80,
                                 help="Higher keeps thinner lines. Lower gives cleaner, thinner shapes.")
        despeckle_label = st.selectbox("Remove stray bricks", ["Off", "Light", "Strong"])
        use_dither = st.checkbox("Dither (smoother gradients, noisier look)", value=False)
        with st.expander("🎨 Custom Color Override (Swap 1 color for another)"):
        enable_override = st.checkbox(
            "Enable color remapping",
            value=False,
            key="enable_color_remapping"
        )

        color_swap_map = {}

        if enable_override:
            st.info(
                "Color remapping is enabled. The color selection controls "
                "will be available after the mosaic has been generated."
            )

    st.header("5. Look")
    style_options = ["Round studs", "Flat squares"] if geo["studs"] else ["Bevel (3D)", "Outlines", "Flat"]
    style = st.selectbox("Preview style", style_options)

uploaded = st.file_uploader("Upload a picture (JPG, PNG, WEBP)", type=["jpg", "jpeg", "png", "webp"])
if uploaded is None:
    st.info("👈 Pick your settings, then upload a picture to begin.")
    st.stop()

params = dict(
    w_ratio=geo["w"], h_ratio=geo["h"], total=total_bricks, color_mode=color_mode, num_colors=num_colors,
    max_colors=max_colors, kind=kind, crop_aspect=CROPS[crop_label], zoom=zoom, pan_x=pan_x, pan_y=pan_y,
    transparent_bg=transparent_bg, auto_enhance=auto_enhance, brightness=brightness, contrast=contrast,
    saturation=saturation, sharpness=sharpness, detail_boost=detail_boost,
    despeckle={"Off": 0, "Light": 1, "Strong": 2}[despeckle_label], dither=use_dither,
    depth_studs=depth_studs, price_weight=price_weight,
)
try:
    mosaic = build_cached(uploaded.getvalue(), params, tuple((n, tuple(c)) for n, c in active_palette.items()))
except Exception:
    st.error("That file could not be read as a picture. Try a JPG, PNG or WEBP exported from your phone or computer.")
    st.stop()

preview = render_preview(
    mosaic.grid, geo["w"], geo["h"], style, geo["studs"],
    brick_id_grid=getattr(mosaic, "brick_id_grid", None),
    depth_studs=depth_studs, show_3d_top=show_3d_top,
)
st.caption(f"Detected picture type: **{'logo / graphic' if mosaic.kind == 'graphic' else 'photo'}**"
           + ("" if kind == "auto" else " (set manually)"))

col1, col2 = st.columns(2)
with col1:
    st.subheader("Your picture (after crop)")
    st.image(mosaic.prepared)
with col2:
    st.subheader(f"LEGO result ({mosaic.nx} wide × {mosaic.ny} tall)")
    st.image(preview)

width_cm = mosaic.nx * geo["cm"][0]
height_cm = mosaic.ny * geo["cm"][1]
cost_banner = ""
if getattr(mosaic, "est_cost", None) is not None:
    saved = max(0.0, mosaic.raw_1x1_cost - mosaic.est_cost)
    cost_banner = (
        f" | 💰 **Est. Total Price:** ${mosaic.est_cost:,.2f} "
        f"*(saves ${saved:,.2f} by merging into {depth_studs}×2 & {depth_studs}×4 bricks)*"
    )

st.info(
    f"**Build specs:** {mosaic.nx} × {mosaic.ny} studs ({mosaic.nx * mosaic.ny:,} total studs) | "
    f"**Physical bricks to buy:** {getattr(mosaic, 'total_physical_bricks', mosaic.nx * mosaic.ny):,} | "
    f"**Colors used:** {len(mosaic.counts) if mosaic.counts else 'unlimited'} | "
    f"**Size:** {width_cm:.1f} cm × {height_cm:.1f} cm" + cost_banner
)
st.caption("Screen colors and BrickLink prices are approximations. Only ×1, ×2, and ×4 bricks are used (×3 bricks excluded).")

if mosaic.counts:
    st.subheader(
        f"📦 Interlocking Parts & Price List ({mosaic.total_physical_bricks:,} physical bricks | "
        f"Est. Total: ${mosaic.est_cost:,.2f} | Seam stagger: {mosaic.strength_pct:.0f}%)"
    )
    lookup = {n: tuple(int(v) for v in mosaic.palette[i]) for i, n in enumerate(mosaic.names)}
    cols = st.columns(3)
    for i, (name, count) in enumerate(sorted(mosaic.counts.items(), key=lambda kv: -kv[1])):
        r, g, b = lookup[name]
        w_counts = mosaic.brick_tally[name]
        color_total_cost = sum(
            w_counts[w] * get_brick_price(name, width=w, depth=depth_studs)
            for w in (4, 2, 1) if w_counts.get(w, 0) > 0
        )
        sizes_txt = " · ".join(
            f"<b>{depth_studs}×{w}:</b> {w_counts[w]:,} "
            f"<span style='color:#7ee787;'>(${w_counts[w] * get_brick_price(name, width=w, depth=depth_studs):,.2f})</span>"
            for w in (4, 2, 1) if w_counts.get(w, 0) > 0
        )
        with cols[i % 3]:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;padding:8px 10px;border:1px solid #444;"
                f"border-radius:6px;margin-bottom:8px;'><div style='width:24px;height:32px;"
                f"background:#{r:02x}{g:02x}{b:02x};border:1px solid #222;border-radius:3px;flex-shrink:0;'></div>"
                f"<div><strong>{html.escape(name)}</strong> <span style='color:#888;'>({count:,} studs)</span> "
                f"— <strong style='color:#7ee787;'>${color_total_cost:,.2f}</strong><br>"
                f"<span style='color:#ccc;font-size:0.85em;'>{sizes_txt}</span></div></div>",
                unsafe_allow_html=True,
            )

png = io.BytesIO()
preview.save(png, format="PNG")
d1, d2, d3 = st.columns(3)
with d1:
    st.download_button("⬇️ Mosaic picture (PNG)", png.getvalue(), f"lego_mosaic_{mosaic.nx}x{mosaic.ny}.png", "image/png")
if mosaic.counts:
    with d2:
        st.download_button("⬇️ Parts & Price list (CSV)", parts_csv(mosaic, depth_studs), "lego_parts_list.csv", "text/csv")
    with d3:
        st.download_button("⬇️ Build map: color per brick (CSV)", build_map_csv(mosaic), "lego_build_map.csv", "text/csv")
        
# Official BrickLink Color IDs for Wanted List (.xml) export
BRICKLINK_COLOR_IDS = {
    "Milky White": 60, "White": 1, "Very Light Gray": 49, "Very Light Bluish Gray": 99,
    "Light Bluish Gray": 86, "Light Gray": 9, "Dark Gray": 10, "Dark Bluish Gray": 85, "Black": 11,
    "Very Light Orange": 96, "Light Nougat": 90, "Tan": 2, "Warm Tan": 241, "Dark Tan": 69,
    "Nougat": 28, "Medium Nougat": 150, "Dark Nougat": 225, "Fabuland Brown": 106, "Sienna Brown": 240,
    "Light Brown": 91, "Medium Brown": 240, "Dark Orange": 68, "Rust": 27, "Reddish Brown": 88,
    "Brown": 8, "Umber Brown": 168, "Dark Brown": 120, "Dark Red": 59, "Red": 5, "Coral Red": 220,
    "Reddish Orange": 167, "Salmon": 25, "Light Salmon": 26, "Coral": 220, "Sand Red": 58,
    "Light Pink": 56, "Pink": 23, "Rose Pink": 23, "Bright Pink": 104, "Medium Dark Pink": 94,
    "Dark Pink": 47, "Magenta": 71, "Reddish Violet": 71, "Earth Orange": 29, "Fabuland Orange": 160,
    "Orange": 4, "Medium Orange": 31, "Bright Light Orange": 110, "Light Orange": 32,
    "Dark Yellow": 161, "Yellow": 3, "Medium Yellow": 33, "Light Yellow": 33,
    "Bright Light Yellow": 103, "Vibrant Neon Yellow": 236, "Lemon": 103,
    "Spring Yellowish Green": 158, "Light Lime": 35, "Medium Lime": 76, "Lime": 34,
    "Electric Green": 36, "Olive Green": 155, "Dark Olive Green": 80, "Light Green": 38,
    "Medium Green": 37, "Sand Green": 48, "Bright Green": 36, "Green": 6, "Dark Green": 80,
    "Deep Green": 80, "Light Aqua": 152, "Aqua": 41, "Light Turquoise": 40,
    "Dark Turquoise (Teal)": 39, "Medium Azure": 156, "Dark Azure": 153, "Maersk Blue": 72,
    "Sky Blue": 87, "Light Blue": 62, "Bright Light Blue": 105, "Pastel Blue": 72,
    "Medium Blue": 42, "Sand Blue": 55, "Blue": 7, "Dark Royal Blue": 109, "Dark Blue": 63,
    "Lavender": 154, "Light Lilac": 245, "Light Violet": 44, "Medium Lavender": 157,
    "Sand Purple": 54, "Lilac": 245, "Medium Violet": 73, "Violet": 43, "Purple": 24,
    "Dark Purple": 89, "Deep Purple": 89, "Pearl Light Gray": 66, "Metallic Silver": 67,
    "Flat Silver": 95, "Pearl Dark Gray": 77, "Titanium Metallic": 77, "Warm Gold": 115,
    "Pearl Gold": 115, "Copper": 84,
}


def export_bricklink_wanted_xml(mosaic, geo_name, depth_studs=2):
    """Generate a BrickLink Wanted List XML file (matches 'Export as WL xml...' in Studio)."""
    tally = getattr(mosaic, "brick_tally", None) or getattr(mosaic, "interlocking_parts", None)
    if not tally:
        return None

    is_plate = "plate" in geo_name.lower()
    is_studs_out = "studs facing out" in geo_name.lower()

    if is_studs_out:
        part_map = {1: "3024", 2: "3023", 3: "3623", 4: "3710"}
    elif is_plate:
        part_map = {1: "3023", 2: "3022", 3: "3021", 4: "3020"} if depth_studs == 2 else {1: "3024", 2: "3023", 3: "3623", 4: "3710"}
    else:
        part_map = {1: "3004", 2: "3003", 3: "3002", 4: "3001"} if depth_studs == 2 else {1: "3005", 2: "3004", 3: "3622", 4: "3010"}

    xml_lines = ["<INVENTORY>"]
    for color_name, width_counts in tally.items():
        bl_color = BRICKLINK_COLOR_IDS.get(color_name, 11)
        if isinstance(width_counts, dict):
            for w, qty in width_counts.items():
                if int(qty) > 0:
                    part_id = part_map.get(int(w), "3005")
                    xml_lines.append(
                        f"  <ITEM>\n"
                        f"    <ITEMTYPE>P</ITEMTYPE>\n"
                        f"    <ITEMID>{part_id}</ITEMID>\n"
                        f"    <COLOR>{bl_color}</COLOR>\n"
                        f"    <MINQTY>{int(qty)}</MINQTY>\n"
                        f"  </ITEM>"
                    )
    xml_lines.append("</INVENTORY>")
    return "\n".join(xml_lines)
def export_bricklink_studio_ldr(mosaic, geo_name, depth_studs=2, studs_per_step=16):
    """
    Генерує 3D-модель LDraw (.ldr) для BrickLink Studio, розбиваючи кожен ряд
    на зручні підкроки по `studs_per_step` стадів (пікселів).
    """
    if getattr(mosaic, "grid", None) is None:
        return None

    ny, nx, _ = mosaic.grid.shape
    is_plate = "plate" in geo_name.lower()
    is_studs_out = "studs facing out" in geo_name.lower()

    lego_names = list(LEGO_ALL_COLORS.keys())
    lego_rgb = np.array(list(LEGO_ALL_COLORS.values()), dtype=np.float32)

    if getattr(mosaic, "idx", None) is not None and getattr(mosaic, "names", None) is not None:
        idx_grid = mosaic.idx
        row_names = mosaic.names
    else:
        flat_px = mosaic.grid.reshape(-1, 3).astype(np.float32)
        d2 = ((flat_px[:, None, :] - lego_rgb[None, :, :]) ** 2).sum(axis=2)
        idx_grid = d2.argmin(axis=1).reshape(ny, nx)
        row_names = lego_names

    palette_ldraw_ids = []
    for i, name in enumerate(row_names):
        if name in LDRAW_COLOR_CODES:
            palette_ldraw_ids.append(LDRAW_COLOR_CODES[name])
        else:
            rgb = mosaic.palette[i].astype(np.float32)
            closest_idx = int(((lego_rgb - rgb) ** 2).sum(axis=1).argmin())
            palette_ldraw_ids.append(LDRAW_COLOR_CODES.get(lego_names[closest_idx], 15))

    spans = getattr(mosaic, "brick_spans", None)
    if spans is None and not is_studs_out:
        spans = _compute_staggered_spans(idx_grid, allowed_widths=(4, 2, 1))
    elif is_studs_out:
        spans = np.ones((ny, nx), dtype=np.int32)

    stud_w = 20
    layer_h = 8 if is_plate else 24

    if is_plate:
        parts_d1 = {1: "3024", 2: "3023", 3: "3623", 4: "3710"}
        parts_d2 = {1: "3023", 2: "3022", 3: "3021", 4: "3020"}
    else:
        parts_d1 = {1: "3005", 2: "3004", 3: "3622", 4: "3010"}
        parts_d2 = {1: "3004", 2: "3003", 3: "3002", 4: "3001"}

    lines = [
        "0 LEGO Interlocking Side-Stack Mosaic",
        "0 Name: lego_mosaic.ldr",
        "0 Author: LEGO Mosaic Builder",
        "0 !LDRAW_ORG Unofficial_Model",
    ]

    x_offset = nx * stud_w // 2

    for y in range(ny - 1, -1, -1):
        ldraw_y = (y - ny) * layer_h
        studs_in_step = 0

        for x in range(nx):
            w = int(spans[y, x])
            if w <= 0:
                continue

            ldraw_color = palette_ldraw_ids[int(idx_grid[y, x])]
            ldraw_x = (x * stud_w + w * (stud_w // 2)) - x_offset
            ldraw_z = 0

            if is_studs_out:
                lines.append(
                    f"1 {ldraw_color} {ldraw_x} 0 {(y * stud_w) - (ny * 10)} 1 0 0 0 1 0 0 0 1 3024.dat"
                )
            else:
                if depth_studs == 2:
                    part_id = parts_d2.get(w, "3004")
                    rot = "0 0 1 0 1 0 -1 0 0" if w == 1 else "1 0 0 0 1 0 0 0 1"
                else:
                    part_id = parts_d1.get(w, "3005")
                    rot = "1 0 0 0 1 0 0 0 1"

                lines.append(f"1 {ldraw_color} {ldraw_x} {ldraw_y} {ldraw_z} {rot} {part_id}.dat")

            studs_in_step += w
            if studs_in_step >= studs_per_step and (x + w) < nx:
                lines.append("0 STEP")
                studs_in_step = 0

        if studs_in_step > 0:
            lines.append("0 STEP")

    return "\r\n".join(lines)


st.subheader("🧱 BrickLink Studio & Shopping Exports")
studs_per_step = st.slider(
    "Кількість пікселів (стадів) в одному кроці інструкції Studio",
    min_value=8, max_value=40, value=16, step=2,
    help="Розбиває кожен горизонтальний ряд на менші підкроки по 16–20 пікселів для зручної інструкції."
)
ldr_data = export_bricklink_studio_ldr(
    mosaic, geo_name, depth_studs=depth_studs, studs_per_step=studs_per_step
)
xml_data = export_bricklink_wanted_xml(mosaic, geo_name, depth_studs=depth_studs)

if ldr_data:
    b_col1, b_col2, b_col3 = st.columns(3)

    with b_col1:
        st.download_button(
            label="⬇️ Download for BrickLink Studio (.ldr)",
            data=ldr_data.encode("utf-8"),
            file_name=f"lego_mosaic_{mosaic.nx}x{mosaic.ny}.ldr",
            mime="application/x-ldraw",
            help="In BrickLink Studio, click File -> Open (CTRL+O) or File -> Import -> Import Model and select this .ldr file."
        )

    with b_col2:
        if xml_data:
            st.download_button(
                label="🛒 Download BrickLink WL (.xml)",
                data=xml_data.encode("utf-8"),
                file_name=f"bricklink_wanted_{mosaic.nx}x{mosaic.ny}.xml",
                mime="application/xml",
                help="Upload directly to BrickLink.com -> Want -> Upload -> Upload BrickLink XML format."
            )

    with b_col3:
        if hasattr(os, "startfile"):
            if st.button("🚀 Open Directly in BrickLink Studio"):
                out_path = os.path.join(
                    tempfile.gettempdir(), f"lego_mosaic_{mosaic.nx}x{mosaic.ny}.ldr"
                )
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(ldr_data)
                os.startfile(out_path)
                st.success(f"Sent to BrickLink Studio! ({out_path})")

