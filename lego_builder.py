
with st.expander("🎨 Custom Color Override (Swap 1 color for another)"):
    enable_override = st.checkbox(
        "Enable color remapping",
        value=False,
        key="enable_color_remapping"
    )

    color_swap_map = {}

    if enable_override:
        st.write("Map generated colors to replacement colors.")
        st.info(
            "Upload a picture first. The actual color replacement "
            "controls require the generated mosaic, which is created "
            "later in the script."
        )

st.header("5. Look")
style_options = ["Round studs", "Flat squares"] if geo["studs"] else ["Bevel (3D)", "Outlines", "Flat"]
style = st.selectbox("Preview style", style_options)

uploaded = st.file_uploader(
    "Upload a picture (JPG, PNG, WEBP)",
    type=["jpg", "jpeg", "png", "webp"]
)

if uploaded is None:
    st.info("👈 Pick your settings, then upload a picture to begin.")
    st.stop()
