import streamlit as st
import psutil
import platform
from pathlib import Path
from typing import Optional
from datetime import datetime


def render_console(log_file_path: Optional[Path] = None) -> None:
    """
    Render an immersive, scifi-styled command console with live system metrics.
    """
    # 1. Gather System Metrics (Mission Control Style)
    cpu_usage = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    mem_usage = memory.percent
    
    # 2. Determine Pipeline Status
    status = "IDLE"
    status_class = "status-idle"
    if st.session_state.get("results"):
        status = "COMPLETED"
        status_class = "status-ok"
    elif st.session_state.get("pdb_ids"):
        status = "STAGED"
        status_class = "status-warn"

    # 3. Read Log Content
    log_content = ""
    if log_file_path and log_file_path.exists():
        with open(log_file_path, "r") as f:
            lines = f.readlines()
        tail_lines = lines[-30:] if len(lines) > 30 else lines
        log_content = "".join(tail_lines)
    else:
        log_content = "> INITIALIZING SYSTEM...\n> WAITING FOR COMMANDS..."

    # 4. Render Console Header (Stats Bar)
    with st.expander("📟 Mission Control Console", expanded=True):
        # Stats Row
        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
        with c1:
            st.markdown(f"**🖥️ SYS:** `{platform.system().upper()}`")
        with c2:
            st.markdown(f"**⚡ CPU:** `{cpu_usage}%`")
        with c3:
            st.markdown(f"**🧠 RAM:** `{mem_usage}%`")
        with c4:
            st.markdown(f"**🛰️ LOG:** <span class='{status_class}'>{status}</span>", unsafe_allow_html=True)

        # Action Row
        col_info, col_clear = st.columns([4, 1])
        with col_info:
            st.caption(f"Session ID: `{st.session_state.get('session_id', 'GLOBAL')[:8]}` | {datetime.now().strftime('%H:%M:%S')}")
        with col_clear:
            if st.button("🗑️ CLEAR", key="clear_terminal", use_container_width=True):
                if log_file_path and log_file_path.exists():
                    with open(log_file_path, "w") as f:
                        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Terminal cleared\n")
                st.rerun()

        # 5. Render Main Terminal Box
        escaped = (
            log_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        
        # Inject custom scanline-enabled container
        st.markdown(
            f"""
            <div class="console-container fade-in">
                <div style="color: #42eaff; font-family: 'Roboto Mono', monospace; font-size: 0.65rem; border-bottom: 1px solid rgba(66,234,255,0.2); padding-bottom: 4px; margin-bottom: 8px;">
                    MUSTANG PIPELINE OS v3.2.3 — SYSTEM TERMINAL
                </div>
                <pre class="console-text">{escaped}</pre>
            </div>
            """,
            unsafe_allow_html=True,
        )
