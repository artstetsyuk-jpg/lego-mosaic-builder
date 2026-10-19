import streamlit as st
import numpy as np
from PIL import Image, ImageDraw
import io

st.set_page_config(page_title="LEGO Side-Stack Mosaic Builder", layout="wide")

# Complete 50-Color Official Solid LEGO Palette (RGB)
LEGO_ALL_COLORS = {
    # Neutrals & Grays
    "White": (242, 243, 242),
    "Very Light Bluish Gray": (229, 228, 223),
    "Light Bluish Gray": (160, 165, 169),
    "Dark Bluish Gray": (108, 110, 104),
    "Black": (27, 42, 52),
    
    # Tans, Nougats & Browns (Great for faces/portraits)
    "Light Nougat": (246, 215, 179),
    "Tan": (228, 205, 158),
    "Nougat": (208, 145, 104),
    "Medium Nougat": (170, 125, 85),
    "Dark Nougat": (173, 97, 64),
    "Dark Tan": (149, 138, 115),
    "Sienna Brown": (145, 92, 60),
    "Dark Orange": (169, 85, 0),
    "Reddish Brown": (88, 42, 18),
    "Umber Brown": (84, 63, 51),
    "Dark Brown": (53, 33, 0),

    # Reds, Pinks & Corals
    "Dark Red": (114, 14, 15),
    "Red": (180, 0, 0),
    "Reddish Orange": (236, 70, 18),
    "Coral": (255, 105, 143),
    "Sand Red": (149, 121, 118),
    "Bright Pink": (228, 173, 200),
    "Dark Pink": (200, 112, 160),
    "Magenta": (146, 57, 120),

    # Oranges & Yellows
    "Orange": (254, 138, 24),
    "Medium Orange": (255, 167, 11),
    "Bright Light Orange": (248, 187, 61),
    "Yellow": (250, 200, 10),
    "Bright Light Yellow": (255, 240, 58),
    "Vibrant Neon Yellow": (235, 255, 0),

    # Greens
    "Spring Yellowish Green": (223, 238, 165),
    "Lime": (187, 233, 11),
    "Olive Green": (155, 154, 90),
    "Sand Green": (160, 188, 172),
    "Bright Green": (75, 159, 74),
    "Green": (35, 120, 65),
    "Dark Green": (24, 70, 50),

    # Blues, Teals & Azures
    "Light Aqua": (173, 221, 213),
    "Dark Turquoise (Teal)": (0, 143, 155),
    "Medium Azure": (54, 174, 191),
    "Dark Azure": (7, 139, 201),
    "Bright Light Blue": (159, 195, 233),
    "Medium Blue": (90, 147, 219),
    "Sand Blue": (96, 116, 161),
    "Blue": (0, 85, 191),
    "Dark Blue": (10, 52, 99),

    # Purples & Lavenders
    "Lavender": (225, 213, 237),
    "Medium Lavender": (172, 120, 186),
    "Reddish Violet": (143, 31, 118),
    "Dark Purple": (63, 54, 145),
}

LEGO_GRAYSCALE = {k: LEGO_ALL_COLORS[k] for k in [
    "White", "Very Light Bluish Gray", "Light Bluish Gray", "Dark Bluish Gray", "Black"
]}

def match_to_palette(img_array, palette_dict):
    """Snap every pixel to the closest LEGO color using human-eye weighted RGB distance."""
    names = list(palette_dict.keys())
    colors = np.array(list(palette_dict.values()), dtype=np.float32)
    
    pixels = img_array.reshape(-1, 3).astype(np.float32)
    
    # Redmean perceptual color distance (more accurate for skin tones & large palettes)
    r_mean = (pixels[:, None, 0] + colors[None, :, 0]) / 2.0
    dr = pixels[:, None, 0] - colors[None, :, 0]
    dg = pixels[:, None, 1] - colors[None, :, 1]
    db = pixels[:, None, 2] - colors[None, :, 2]
    
    distances = np.sqrt(
        (2.0 + r_mean / 256.0) * (dr ** 2) +
        4.0 * (dg ** 2) +
        (2.0 + (255.0 - r_mean) / 256.0) * (db ** 2)
    )
    
    closest_indices = np.argmin(distances, axis=1)
    matched_pixels = colors[closest_indices].astype(np.uint8).reshape(img_array.shape)
    
    unique_idx, counts = np.unique(closest_indices, return_counts=True)
    part_counts = {names[idx]: int(count) for idx, count in zip(unique_idx, counts)}
    
    return matched_pixels, part_counts

def render_brick_preview(grid_array, w_ratio=5, h_ratio=6, scale=5, draw_seams=True):
    """Upscale each (Nx, Ny) pixel into a (w_ratio*scale) x (h_ratio*scale) brick."""
    ny, nx, _ = grid_array.shape
    brick_w = w_ratio * scale
    brick_h = h_ratio * scale
    
    upscaled = np.repeat(np.repeat(grid_array, brick_h, axis=0), brick_w, axis=1)
    preview_img = Image.fromarray(upscaled)
    
    if draw_seams:
        draw = ImageDraw.Draw(preview_img)
        width_px = nx * brick_w
        height_px = ny * brick_h
        seam_color = (40, 40, 40)
        
        for x in range(0, width_px, brick_w):
            draw.line([(x, 0), (x, height_px)], fill=seam_color, width=1)
        for y in range(0, height_px, brick_h):
            draw.line([(0, y), (width_px, y)], fill=seam_color, width=1)
            
    return preview_img

# --- UI Layout ---
st.title("🧱 Side-View LEGO Brick Mosaic Generator")
st.write("Upload an image to pixelate it into stacked LEGO bricks with a **5:6 width-to-height ratio**.")

with st.sidebar:
    st.header("1. Brick Geometry")
    brick_type = st.selectbox(
        "Piece Type & View",
        [
            "1x1 Bricks - Side View (5:6 ratio)",
            "1x1 Plates - Side View (5:2 ratio)",
            "Studs Facing Out (1:1 square ratio)"
        ]
    )
    if "5:6" in brick_type:
        w_ratio, h_ratio = 5, 6
    elif "5:2" in brick_type:
        w_ratio, h_ratio = 5, 2
    else:
        w_ratio, h_ratio = 1, 1

    st.header("2. Amount of LEGO Pieces")
    total_bricks = st.slider(
        "Target total pieces (budget):",
        min_value=100,
        max_value=15000,
        value=2500,
        step=100
    )

    st.header("3. Color Palette")
    color_mode = st.radio(
        "Palette Mode",
        [
            "All 50 Official LEGO Colors",
            "Pick Specific LEGO Colors",
            "LEGO Grayscale (5 Shades)",
            "Adaptive Photo Colors (Custom Count)",
            "Unlimited True RGB (No Palette Limit)"
        ]
    )

    active_palette = dict(LEGO_ALL_COLORS)

    if color_mode == "Pick Specific LEGO Colors":
        selected_names = st.multiselect(
            "Choose available brick colors:",
            options=list(LEGO_ALL_COLORS.keys()),
            default=["White", "Light Bluish Gray", "Dark Bluish Gray", "Black", "Red", "Blue", "Yellow", "Tan"]
        )
        if not selected_names:
            st.warning("Select at least one color! Defaulting to Black & White.")
            selected_names = ["White", "Black"]
        active_palette = {k: LEGO_ALL_COLORS[k] for k in selected_names}

    elif color_mode == "Adaptive Photo Colors (Custom Count)":
        num_colors = st.slider("Number of adaptive colors:", 2, 64, 16)

    # Optional custom color adder for official modes
    if color_mode in ["All 50 Official LEGO Colors", "Pick Specific LEGO Colors"]:
        with st.expander("➕ Add a Custom Brick Color"):
            custom_hex = st.color_picker("Pick color", "#FF5500")
            custom_name = st.text_input("Color name", "My Custom Brick")
            if st.checkbox("Include this custom color"):
                r = int(custom_hex[1:3], 16)
                g = int(custom_hex[3:5], 16)
                b = int(custom_hex[5:7], 16)
                active_palette[custom_name] = (r, g, b)

    show_seams = st.checkbox("Show brick outlines", value=True)

uploaded_file = st.file_uploader("Upload a photo (JPG, PNG, WEBP)", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file:
    original_img = Image.open(uploaded_file).convert("RGB")
    img_w, img_h = original_img.size

    # Calculate grid dimensions preserving aspect ratio
    nx = max(1, round(np.sqrt(total_bricks * (img_w / img_h) * (h_ratio / w_ratio))))
    ny = max(1, round(nx * (img_h / img_w) * (w_ratio / h_ratio)))
    actual_total = nx * ny

    # Downsample image using Box averaging
    small_img = original_img.resize((nx, ny), resample=Image.Resampling.BOX)
    part_counts = None

    if color_mode in ["All 50 Official LEGO Colors", "Pick Specific LEGO Colors"]:
        grid_np, part_counts = match_to_palette(np.array(small_img), active_palette)
    elif color_mode == "LEGO Grayscale (5 Shades)":
        gray_img = small_img.convert("L").convert("RGB")
        grid_np, part_counts = match_to_palette(np.array(gray_img), LEGO_GRAYSCALE)
    elif color_mode == "Adaptive Photo Colors (Custom Count)":
        quantized = small_img.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
        grid_np = np.array(quantized)
    else:  # Unlimited True RGB
        grid_np = np.array(small_img)

    # Upscale preview
    scale_factor = max(1, int(850 / (nx * w_ratio)))
    brick_preview = render_brick_preview(grid_np, w_ratio, h_ratio, scale=scale_factor, draw_seams=show_seams)

    # Display Results
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original Picture")
        st.image(original_img, use_container_width=True)
    with col2:
        st.subheader(f"LEGO Side-Stack Result ({nx} wide × {ny} tall)")
        st.image(brick_preview, use_container_width=True)

    # Real-World Build Specs
    real_width_cm = nx * 0.8
    real_height_cm = (ny * 0.96) if (w_ratio == 5 and h_ratio == 6) else (ny * 0.32 if h_ratio == 2 else ny * 0.8)

    st.info(
        f"**Build Specs:** {nx} studs wide × {ny} bricks tall | "
        f"**Total Pieces Used:** {actual_total:,} | "
        f"**Distinct Colors Used:** {len(part_counts) if part_counts else 'Custom'} | "
        f"**Real-World Size:** {real_width_cm:.1f} cm × {real_height_cm:.1f} cm"
    )

    # Visual Parts List with Color Swatches
    if part_counts:
        st.subheader(f"📦 Required Bricks ({len(part_counts)} Colors Used)")
        palette_lookup = active_palette if color_mode != "LEGO Grayscale (5 Shades)" else LEGO_GRAYSCALE
        cols = st.columns(4)
        for idx, (color_name, count) in enumerate(sorted(part_counts.items(), key=lambda x: -x[1])):
            r, g, b = palette_lookup[color_name]
            hex_code = f"#{r:02x}{g:02x}{b:02x}"
            with cols[idx % 4]:
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:10px;padding:6px 10px;"
                    f"border:1px solid #444;border-radius:6px;margin-bottom:8px;'>"
                    f"<div style='width:22px;height:26px;background:{hex_code};"
                    f"border:1px solid #222;border-radius:3px;flex-shrink:0;'></div>"
                    f"<div><strong>{color_name}</strong><br><span style='color:#aaa;'>{count:,} pcs</span></div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

    # Download Button
    buf = io.BytesIO()
    brick_preview.save(buf, format="PNG")
    st.download_button(
        label="⬇️ Download LEGO Blueprint (PNG)",
        data=buf.getvalue(),
        file_name=f"lego_mosaic_{nx}x{ny}.png",
        mime="image/png"
    )