import streamlit as st


def render_console(log_file_path=None):
    """
    Render a compact, styled command console log viewer.
    Shows last 30 lines in a collapsible expander.
    """
    log_content = ""
    if log_file_path and log_file_path.exists():
        with open(log_file_path, "r") as f:
            lines = f.readlines()
        # Show only last 30 lines for compactness
        tail_lines = lines[-30:] if len(lines) > 30 else lines
        log_content = "".join(tail_lines)
    else:
        log_content = "Waiting for logs..."

    with st.expander("📟 Command Console", expanded=False):
        # Render inside a height-limited styled div
        escaped = log_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(
            f"""<div class="console-container"><pre class="console-text">{escaped}</pre></div>""",
            unsafe_allow_html=True,
        )
