import streamlit as st
import time

def render_console(log_file_path=None):
    """
    Render a command console style log viewer.
    """
    st.markdown("### 📟 Command Console")
    
    log_content = ""
    if log_file_path and log_file_path.exists():
        with open(log_file_path, "r") as f:
            log_content = f.read()
    else:
        log_content = "Waiting for logs..."

    # Use a text area with a dark theme look code block or just st.code
    st.code(log_content, language="bash", line_numbers=True)
