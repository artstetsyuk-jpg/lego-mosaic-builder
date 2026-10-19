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
    # --- Neutrals, Grays & Blacks (9) ---
    "Milky White": (255, 255, 255),
    "White": (242, 243, 242),
    "Very Light Gray": (230, 227, 218),
    "Very Light Bluish Gray": (229, 228, 223),
    "Light Bluish Gray": (160, 165, 169),
    "Light Gray": (155, 161, 157),
    "Dark Gray": (109, 110, 92),
    "Dark Bluish Gray": (108, 110, 104),
    "Black": (0, 0, 0),

    # --- Tans, Nougats, Flesh & Browns (18) ---
    "Very Light Orange": (243, 207, 155),
    "Light Nougat": (246, 215, 179),
    "Tan": (228, 205, 158),
    "Warm Tan": (204, 163, 115),
    "Dark Tan": (149, 138, 115),
    "Nougat": (208, 145, 104),
    "Medium Nougat": (170, 125, 85),
    "Dark Nougat": (173, 97, 64),
    "Fabuland Brown": (179, 105, 78),
    "Sienna Brown": (145, 92, 60),
    "Light Brown": (124, 80, 58),
    "Medium Brown": (117, 89, 69),
    "Dark Orange": (169, 85, 0),
    "Rust": (179, 16, 4),
    "Reddish Brown": (88, 42, 18),
    "Brown": (88, 57, 39),
    "Umber Brown": (84, 63, 51),
    "Dark Brown": (53, 33, 0),

    # --- Reds, Pinks, Corals & Magentas (16) ---
    "Dark Red": (114, 14, 15),
    "Red": (180, 0, 0),
    "Coral Red": (225, 37, 27),
    "Reddish Orange": (236, 70, 18),
    "Salmon": (242, 112, 94),
    "Light Salmon": (254, 186, 189),
    "Coral": (255, 105, 143),
    "Sand Red": (149, 121, 118),
    "Light Pink": (254, 204, 207),
    "Pink": (252, 151, 172),
    "Rose Pink": (238, 157, 195),
    "Bright Pink": (228, 173, 200),
    "Medium Dark Pink": (247, 133, 177),
    "Dark Pink": (200, 112, 160),
    "Magenta": (146, 57, 120),
    "Reddish Violet": (143, 31, 118),

    # --- Oranges & Yellows (13) ---
    "Earth Orange": (250, 156, 28),
    "Fabuland Orange": (239, 145, 33),
    "Orange": (254, 138, 24),
    "Medium Orange": (255, 167, 11),
    "Bright Light Orange": (248, 187, 61),
    "Light Orange": (249, 186, 97),
    "Dark Yellow": (220, 165, 20),
    "Yellow": (250, 200, 10),
    "Medium Yellow": (252, 216, 55),
    "Light Yellow": (251, 230, 150),
    "Bright Light Yellow": (255, 240, 58),
    "Vibrant Neon Yellow": (235, 255, 0),
    "Lemon": (245, 242, 95),

    # --- Greens & Limes (14) ---
    "Spring Yellowish Green": (223, 238, 165),
    "Light Lime": (217, 228, 167),
    "Medium Lime": (199, 210, 60),
    "Lime": (187, 233, 11),
    "Electric Green": (120, 235, 45),
    "Olive Green": (155, 154, 90),
    "Dark Olive Green": (88, 93, 58),
    "Light Green": (194, 218, 184),
    "Medium Green": (115, 220, 161),
    "Sand Green": (160, 188, 172),
    "Bright Green": (75, 159, 74),
    "Green": (35, 120, 65),
    "Dark Green": (24, 70, 50),
    "Deep Green": (15, 48, 34),

    # --- Blues, Teals, Aquas & Azures (16) ---
    "Light Aqua": (173, 221, 213),
    "Aqua": (179, 215, 209),
    "Light Turquoise": (85, 165, 175),
    "Dark Turquoise (Teal)": (0, 143, 155),
    "Medium Azure": (54, 174, 191),
    "Dark Azure": (7, 139, 201),
    "Maersk Blue": (53, 146, 195),
    "Sky Blue": (125, 191, 221),
    "Light Blue": (180, 210, 227),
    "Bright Light Blue": (159, 195, 233),
    "Pastel Blue": (90, 196, 232),
    "Medium Blue": (90, 147, 219),
    "Sand Blue": (96, 116, 161),
    "Blue": (0, 85, 191),
    "Dark Royal Blue": (14, 62, 154),
    "Dark Blue": (10, 52, 99),

    # --- Purples, Violets & Lavenders (11) ---
    "Lavender": (225, 213, 237),
    "Light Lilac": (205, 194, 232),
    "Light Violet": (201, 202, 226),
    "Medium Lavender": (172, 120, 186),
    "Sand Purple": (132, 94, 132),
    "Lilac": (107, 98, 155),
    "Medium Violet": (104, 116, 202),
    "Violet": (67, 84, 163),
    "Purple": (129, 0, 123),
    "Dark Purple": (63, 54, 145),
    "Deep Purple": (42, 32, 98),

    # --- Pearl & Metallic Solid Colors (8) ---
    "Pearl Light Gray": (156, 163, 168),
    "Metallic Silver": (165, 169, 180),
    "Flat Silver": (137, 135, 136),
    "Pearl Dark Gray": (87, 88, 87),
    "Titanium Metallic": (62, 60, 57),
    "Warm Gold": (204, 156, 43),
    "Pearl Gold": (170, 127, 46),
    "Copper": (174, 122, 89),
}

LEGO_GRAYSCALE = {k: LEGO_ALL_COLORS[k] for k in
                  ["White", "Very Light Bluish Gray", "Light Bluish Gray", "Dark Bluish Gray", "Black"]}

GEOMETRY = {
    "1x1 bricks, side view (15.8:9.6 ratio)": dict(w=8, h=5, cm=(1.58, 0.96), piece="Brick 1x1", studs=False),
    "1x1 bricks, side view (standard 5:6)": dict(w=5, h=6, cm=(0.8, 0.96), piece="Brick 1x1", studs=False),
    "1x1 plates, side view (5:2)": dict(w=5, h=2, cm=(0.8, 0.32), piece="Plate 1x1", studs=False),
    "Studs facing out (1:1)": dict(w=1, h=1, cm=(0.8, 0.8), piece="Plate 1x1 (or round plate 1x1)", studs=True),
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
    """Squared color distance (pixels x palette) in OKLab.

    Neutral pixels (grays, blacks, whites) weight hue/saturation error much more heavily, so they land on
    neutral bricks instead of a tinted one (LEGO's "Black" is lighter than Dark Brown, and its gray ramp has
    gaps that pinkish Sand Red would otherwise fill). Saturated pixels are matched mostly on overall color.
    """
    dl = lab[:, None, 0] - pal[None, :, 0]
    da = lab[:, None, 1] - pal[None, :, 1]
    db = lab[:, None, 2] - pal[None, :, 2]
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    w = (1.0 + 7.0 * np.exp(-chroma / 0.04))[:, None]
    return l_weight * dl * dl + w * (da * da + db * db)


def nearest(lab, pal_lab, chunk=60000, l_weight=1.0):
    """Index of the closest palette color for each OKLab row (chunked to keep memory small)."""
    lab = np.asarray(lab, dtype=np.float32).reshape(-1, 3)
    pal = np.asarray(pal_lab, dtype=np.float32)
    out = np.empty(len(lab), dtype=np.int32)
    for s in range(0, len(lab), chunk):
        out[s:s + chunk] = dist2(lab[s:s + chunk], pal, l_weight).argmin(1)
    return out


def snap(rgb8, pal_lab, l_weight=1.0):
    """Palette index for every pixel of an (H, W, 3) uint8 image. Works on unique colors only (fast)."""
    flat = rgb8.reshape(-1, 3).astype(np.uint32)
    packed = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    uniq, inverse = np.unique(packed, return_inverse=True)
    u_rgb = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], axis=1).astype(np.uint8)
    idx_u = nearest(srgb8_to_oklab(u_rgb), pal_lab, l_weight=l_weight)
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
        img = ImageOps.autocontrast(img, cutoff=1)
        contrast, saturation = contrast * 1.05, saturation * 1.12
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
    if kind == "photo" and abs(p["sharpness"] - 1.0) > 1e-3:  # sharpen at brick scale, where it matters
        cells = np.asarray(ImageEnhance.Sharpness(Image.fromarray(cells)).enhance(p["sharpness"]))

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

    if kind == "graphic":
        idx = graphic_cells(hi_rgb8, nx, ny, S, pal_lab, p["detail_boost"])
        cell_lab = pal_lab[idx]
    else:
        cell_lab = srgb8_to_oklab(cells)
        idx = dither(cell_lab, pal_lab) if p["dither"] else nearest(cell_lab, pal_lab).reshape(ny, nx)

    idx = despeckle(idx, len(pal_rgb), p["despeckle"])
    idx = limit_colors(idx, cell_lab, pal_lab, p["max_colors"])
    used, counts = np.unique(idx, return_counts=True)
    result.update(idx=idx, grid=pal_rgb[idx], names=names, palette=pal_rgb,
                  counts={names[int(u)]: int(c) for u, c in zip(used, counts)})
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


def render_preview(grid, w_ratio, h_ratio, style, studs, target_width=1100):
    """Draw the brick wall. Returns a PIL image about `target_width` pixels wide."""
    ny, nx, _ = grid.shape
    if studs and style == "Round studs":
        s = int(np.clip(round(target_width / nx), 8, 24))
        up = np.repeat(np.repeat(grid, s, 0), s, 1).astype(np.float32)
        mask, shade = _stud_sprite(s)
        m, sh = np.tile(mask, (ny, nx))[..., None], np.tile(shade, (ny, nx))[..., None]
        out = up * 0.45 * (1 - m) + np.clip(up * sh, 0, 255) * m
    else:
        scale = int(np.clip(round(target_width / (nx * w_ratio)), 2, 14))
        cw, ch = w_ratio * scale, h_ratio * scale
        up = np.repeat(np.repeat(grid, ch, 0), cw, 1).astype(np.float32)
        out = np.clip(up * np.tile(_shade_tile(cw, ch, style), (ny, nx, 1)), 0, 255)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def parts_csv(mosaic, piece):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Color", "Hex", "R", "G", "B", "Piece", "Quantity"])
    lookup = {n: tuple(int(v) for v in mosaic.palette[i]) for i, n in enumerate(mosaic.names)}
    for name, count in sorted(mosaic.counts.items(), key=lambda kv: -kv[1]):
        r, g, b = lookup[name]
        writer.writerow([name, f"#{r:02x}{g:02x}{b:02x}", r, g, b, piece, count])
    return buf.getvalue().encode("utf-8-sig")


def build_map_csv(mosaic):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in mosaic.idx:
        writer.writerow([mosaic.names[int(i)] for i in row])
    return buf.getvalue().encode("utf-8-sig")


# ============================================================================
# UI
# ============================================================================
@st.cache_data(show_spinner="Building your mosaic...", max_entries=12)
def build_cached(file_bytes, params, palette_items):
    return build_mosaic(file_bytes, params, palette_items)


st.title("🧱 LEGO Mosaic Builder")
st.write("Upload any picture and turn it into a LEGO brick mosaic with a parts list.")

with st.sidebar:
    st.header("1. Brick type")
    geo_name = st.selectbox("Piece type & view", list(GEOMETRY))
    geo = GEOMETRY[geo_name]

    st.header("2. Size")
    total_bricks = st.slider("Target number of pieces (budget)", 100, 20000, 2500, 100)

    st.header("3. Colors")
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
)
try:
    mosaic = build_cached(uploaded.getvalue(), params, tuple((n, tuple(c)) for n, c in active_palette.items()))
except Exception:  # unreadable / corrupt / unsupported image
    st.error("That file could not be read as a picture. Try a JPG, PNG or WEBP exported from your phone or computer.")
    st.stop()

preview = render_preview(mosaic.grid, geo["w"], geo["h"], style, geo["studs"])
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
st.info(
    f"**Build specs:** {mosaic.nx} × {mosaic.ny} bricks | **Total pieces:** {mosaic.nx * mosaic.ny:,} | "
    f"**Colors used:** {len(mosaic.counts) if mosaic.counts else 'unlimited'} | "
    f"**Real-world size:** {width_cm:.1f} cm × {height_cm:.1f} cm"
)
st.caption("Screen colors are approximations of real LEGO colors. Check that each color is available as the piece "
           "you need (BrickLink / Pick-a-Brick) before ordering.")

if mosaic.counts:
    st.subheader(f"📦 Parts list ({len(mosaic.counts)} colors)")
    lookup = {n: tuple(int(v) for v in mosaic.palette[i]) for i, n in enumerate(mosaic.names)}
    cols = st.columns(4)
    for i, (name, count) in enumerate(sorted(mosaic.counts.items(), key=lambda kv: -kv[1])):
        r, g, b = lookup[name]
        with cols[i % 4]:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;padding:6px 10px;border:1px solid #444;"
                f"border-radius:6px;margin-bottom:8px;'><div style='width:22px;height:26px;"
                f"background:#{r:02x}{g:02x}{b:02x};border:1px solid #222;border-radius:3px;flex-shrink:0;'></div>"
                f"<div><strong>{html.escape(name)}</strong><br><span style='color:#aaa;'>{count:,} pcs</span></div></div>",
                unsafe_allow_html=True,
            )

png = io.BytesIO()
preview.save(png, format="PNG")
d1, d2, d3 = st.columns(3)
with d1:
    st.download_button("⬇️ Mosaic picture (PNG)", png.getvalue(), f"lego_mosaic_{mosaic.nx}x{mosaic.ny}.png", "image/png")
if mosaic.counts:
    with d2:
        st.download_button("⬇️ Parts list (CSV)", parts_csv(mosaic, geo["piece"]), "lego_parts_list.csv", "text/csv")
    with d3:
        st.download_button("⬇️ Build map: color per brick (CSV)", build_map_csv(mosaic), "lego_build_map.csv", "text/csv")
