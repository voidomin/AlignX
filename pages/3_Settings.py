import streamlit as st
from src.utils.config_loader import load_config, save_config
from src.frontend.utils import load_css

st.set_page_config(
    page_title="Settings | Mustang Holo-Lab", page_icon="⚙️", layout="wide"
)

load_css()

# Default values mapping for "Restore Defaults"
DEFAULT_SETTINGS = {
    "mustang_backend": "auto",
    "mustang_timeout": 600,
    "max_proteins": 20,
    "max_file_size": 500,
    "heatmap_cmap": "viridis",
    "viewer_style": "cartoon",
}


def render_settings_page():
    st.markdown(
        '<h1 style="font-size: 2.5rem;">⚙️ System Configuration</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Manage pipeline settings, execution backends, and visual preferences.")

    # Load config if not in session
    if "config" not in st.session_state:
        st.session_state.config = load_config()

    config = st.session_state.config

    with st.container():
        col1, col2 = st.columns([1, 1], gap="large")

        # --- Column 1: Mustang Backend ---
        with col1:
            st.subheader("🧬 Mustang Execution")

            with st.expander("Backend Settings", expanded=True):
                current_backend = config.get("mustang", {}).get("backend", "auto")
                backend_options = ["auto", "native", "wsl"]

                new_backend = st.selectbox(
                    "Execution Backend",
                    options=backend_options,
                    index=(
                        backend_options.index(current_backend)
                        if current_backend in backend_options
                        else 0
                    ),
                    help="Auto: Tries native then WSL. Native: Local binary. WSL: Windows Subsystem for Linux (recommended for Windows).",
                )

                current_timeout = config.get("mustang", {}).get("timeout", 600)
                new_timeout = st.slider(
                    "Execution Timeout (seconds)",
                    min_value=60,
                    max_value=3600,
                    value=current_timeout,
                    step=60,
                    help="Max time to wait for alignment to complete.",
                )

        # --- Column 2: Application Limits ---
        with col2:
            st.subheader("⚠️ Limits & Performance")

            with st.expander("Resource Controls", expanded=True):
                current_max = config.get("app", {}).get("max_proteins", 20)
                new_max = st.number_input(
                    "Max Proteins per Run",
                    min_value=2,
                    max_value=100,
                    value=current_max,
                    help="Limit the number of structures to prevent memory crashes.",
                )

                current_size_limit = config.get("pdb", {}).get("max_file_size_mb", 500)
                new_size_limit = st.number_input(
                    "Max PDB File Size (MB)",
                    min_value=10,
                    max_value=2000,
                    value=current_size_limit,
                )

            st.subheader("🎨 Visualization")
            with st.expander("UI Appearance & Plots", expanded=True):
                st.info(
                    "💡 Changes here will affect how new and existing results are displayed in the dashboard."
                )

                # Colormap Mapping (Display -> Internal)
                cmap_options = {
                    "Viridis (Default)": "viridis",
                    "Plasma": "plasma",
                    "Inferno": "inferno",
                    "Magma": "magma",
                    "Cividis": "cividis",
                    "Red-Blue (Divergent)": "RdBu_r",
                    "Spectral": "Spectral_r",
                }

                current_cmap = (
                    config.get("visualization", {})
                    .get("heatmap_colormap", "viridis")
                    .lower()
                )
                # Find current display name
                curr_display = next(
                    (k for k, v in cmap_options.items() if v == current_cmap),
                    "Viridis (Default)",
                )

                new_cmap_display = st.selectbox(
                    "Heatmap Colormap",
                    options=list(cmap_options.keys()),
                    index=list(cmap_options.keys()).index(curr_display),
                    help="Color scheme for the RMSD similarity matrices.",
                )
                new_cmap = cmap_options[new_cmap_display]

                current_style = config.get("visualization", {}).get(
                    "viewer_default_style", "cartoon"
                )
                new_style = st.selectbox(
                    "Default 3D Style",
                    options=["cartoon", "stick", "sphere", "line"],
                    index=(
                        ["cartoon", "stick", "sphere", "line"].index(current_style)
                        if current_style in ["cartoon", "stick", "sphere", "line"]
                        else 0
                    ),
                    help="Initial representation style when opening the 3D Structure Viewer.",
                )

    # --- Actions ---
    st.divider()
    col_save, col_defaults, col_reset = st.columns([1, 1, 4])

    with col_save:
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            # Update config object
            config["mustang"]["backend"] = new_backend
            config["mustang"]["timeout"] = new_timeout
            config["app"]["max_proteins"] = new_max
            config["pdb"]["max_file_size_mb"] = new_size_limit

            # Nested update for visualization
            if "visualization" not in config:
                config["visualization"] = {}
            config["visualization"]["heatmap_colormap"] = new_cmap
            config["visualization"]["viewer_default_style"] = new_style

            # Save to file
            try:
                save_config(config)
                st.session_state.config = config  # Update session
                if "mustang_runner" in st.session_state:
                    del st.session_state.mustang_runner
                st.toast("Settings saved successfully!", icon="✅")
            except Exception as e:
                st.error(f"Failed to save settings: {e}")

    with col_defaults:
        if st.button("🔄 Restore Defaults", use_container_width=True):
            # Apply DEFAULT_SETTINGS to the current config
            config["mustang"]["backend"] = DEFAULT_SETTINGS["mustang_backend"]
            config["mustang"]["timeout"] = DEFAULT_SETTINGS["mustang_timeout"]
            config["app"]["max_proteins"] = DEFAULT_SETTINGS["max_proteins"]
            config["pdb"]["max_file_size_mb"] = DEFAULT_SETTINGS["max_file_size"]

            if "visualization" not in config:
                config["visualization"] = {}
            config["visualization"]["heatmap_colormap"] = DEFAULT_SETTINGS[
                "heatmap_cmap"
            ]
            config["visualization"]["viewer_default_style"] = DEFAULT_SETTINGS[
                "viewer_style"
            ]

            save_config(config)
            st.session_state.config = config
            st.success("Defaults restored. Reloading...")
            st.rerun()


if __name__ == "__main__":
    render_settings_page()
