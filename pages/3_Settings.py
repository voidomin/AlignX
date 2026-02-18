import streamlit as st
import yaml
from pathlib import Path
from src.utils.config_loader import load_config, save_config
from src.frontend.utils import load_css

st.set_page_config(
    page_title="Settings | Mustang Holo-Lab",
    page_icon="⚙️",
    layout="wide"
)

load_css()

def render_settings_page():
    st.markdown('<h1 style="font-size: 2.5rem;">⚙️ System Configuration</h1>', unsafe_allow_html=True)
    st.caption("Manage pipeline settings, execution backends, and visual preferences.")
    
    # Load config if not in session
    if 'config' not in st.session_state:
        st.session_state.config = load_config()
        
    config = st.session_state.config
    
    with st.container():
        col1, col2 = st.columns([1, 1], gap="large")
        
        # --- Column 1: Mustang Backend ---
        with col1:
            st.subheader("🧬 Mustang Execution")
            
            with st.expander("Backend Settings", expanded=True):
                current_backend = config.get('mustang', {}).get('backend', 'auto')
                backend_options = ["auto", "native", "wsl", "bio3d"]
                
                new_backend = st.selectbox(
                    "Execution Backend",
                    options=backend_options,
                    index=backend_options.index(current_backend) if current_backend in backend_options else 0,
                    help="Auto: Tries native then WSL. Native: Local binary. WSL: Windows Subsystem for Linux. Bio3D: R package."
                )
                
                current_timeout = config.get('mustang', {}).get('timeout', 600)
                new_timeout = st.slider(
                    "Execution Timeout (seconds)",
                    min_value=60,
                    max_value=3600,
                    value=current_timeout,
                    step=60,
                    help="Max time to wait for alignment to complete."
                )
                
                # Checkbox for cleaning
                # current_clean = config.get('filtering', {}).get('remove_water', True)
                # new_clean = st.checkbox("Remove Water Molecules", value=current_clean)

        # --- Column 2: Application Limits ---
        with col2:
            st.subheader("⚠️ Limits & Performance")
            
            with st.expander("Resource Controls", expanded=True):
                current_max = config.get('app', {}).get('max_proteins', 20)
                new_max = st.number_input(
                    "Max Proteins per Run",
                    min_value=2,
                    max_value=100,
                    value=current_max,
                    help="Limit the number of structures to prevent memory crashes."
                )
                
                current_size_limit = config.get('pdb', {}).get('max_file_size_mb', 500)
                new_size_limit = st.number_input(
                    "Max PDB File Size (MB)",
                    min_value=10,
                    max_value=2000,
                    value=current_size_limit
                )

    # --- Save Actions ---
    st.divider()
    col_save, col_reset = st.columns([1, 5])
    
    with col_save:
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            # Update config object
            config['mustang']['backend'] = new_backend
            config['mustang']['timeout'] = new_timeout
            config['app']['max_proteins'] = new_max
            config['pdb']['max_file_size_mb'] = new_size_limit
            
            # Save to file
            try:
                save_config(config)
                st.session_state.config = config # Update session
                # If backend changed, might need to re-init runner
                if 'mustang_runner' in st.session_state:
                    del st.session_state.mustang_runner
                st.toast("Settings saved successfully!", icon="✅")
            except Exception as e:
                st.error(f"Failed to save settings: {e}")

if __name__ == "__main__":
    render_settings_page()
