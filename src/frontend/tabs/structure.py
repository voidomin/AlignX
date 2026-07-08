import streamlit as st
from pathlib import Path
from src.backend.structure_viewer import show_structure_in_streamlit
from src.frontend.tabs.common import render_learning_card, render_help_expander

from typing import Dict, Any, Optional, Tuple


def get_conservation_color(val: float) -> str:
    # 0.0 (variable) -> Cool Blue/Gray: #4a607a
    # 0.5 (partially conserved) -> Light Yellow/Green: #e0d870
    # 1.0 (fully conserved) -> Sunset Orange/Red: #ff7e42
    if val < 0.5:
        t = val / 0.5
        r = int(74 + t * (224 - 74))
        g = int(96 + t * (216 - 96))
        b = int(122 + t * (112 - 122))
    else:
        t = (val - 0.5) / 0.5
        r = int(224 + t * (255 - 224))
        g = int(216 + t * (126 - 216))
        b = int(112 + t * (66 - 112))
    return f"#{r:02x}{g:02x}{b:02x}"


def get_rmsf_color(val: float, max_val: float = 5.0) -> str:
    norm = min(1.0, max(0.0, val / max_val))
    # 0.0 (low RMSF/rigid) -> Cool Cyan/Blue: #42eaff
    # 0.5 (medium RMSF) -> Yellow: #e0d870
    # 1.0 (high RMSF/flexible) -> Hot Pink/Red: #ff0055
    if norm < 0.5:
        t = norm / 0.5
        r = int(66 + t * (224 - 66))
        g = int(234 + t * (216 - 234))
        b = int(255 + t * (112 - 255))
    else:
        t = (norm - 0.5) / 0.5
        r = int(224 + t * (255 - 224))
        g = int(216 + t * (0 - 216))
        b = int(112 + t * (85 - 112))
    return f"#{r:02x}{g:02x}{b:02x}"


def _build_residue_colors_from_scores(
    sequences: Dict[str, str], scores: list, color_fn
) -> Dict[str, Dict[int, str]]:
    """Maps each sequence's non-gap residues to a color derived from
    `scores` (aligned-column-indexed) via `color_fn` - shared by the
    Conservation Density and RMSF Flexibility themes, which differ only in
    which score array and color function they use."""
    residue_colors = {}
    for p_idx, (name, seq) in enumerate(sequences.items()):
        chain_id = chr(ord("A") + p_idx)
        residue_colors[chain_id] = {}
        current_res = 1
        for i, char in enumerate(seq):
            if char != "-":
                score = scores[i] if i < len(scores) else 0.0
                residue_colors[chain_id][current_res] = color_fn(score)
                current_res += 1
    return residue_colors


def _build_residue_colors(
    style_mode: str, results: Dict[str, Any]
) -> Optional[Dict[str, Dict[int, str]]]:
    """Custom per-residue colors for the themes that need them, or None
    for themes 3Dmol's built-in coloring already handles."""
    sequences = results.get("sequences", {})
    if not sequences:
        return None

    if style_mode == "Conservation Density":
        conservation = results.get("conservation", [])
        if not conservation:
            return None
        return _build_residue_colors_from_scores(
            sequences, conservation, get_conservation_color
        )

    if style_mode == "RMSF Flexibility":
        rmsf_values = results.get("rmsf_values", [])
        if not rmsf_values:
            return None
        max_rmsf = max(rmsf_values) if rmsf_values else 5.0
        if max_rmsf == 0:
            max_rmsf = 1.0
        return _build_residue_colors_from_scores(
            sequences, rmsf_values, lambda score: get_rmsf_color(score, max_rmsf)
        )

    return None


def _render_cluster_filter_banner(results: Dict[str, Any]):
    """Handles cluster-family isolation; returns the visible-chains filter
    (or None) for the viewer to apply."""
    visible_chains, members = _get_visible_chains_from_cluster(results)
    if members:
        st.warning(f"🎯 Currently viewing Cluster Family ({len(members)} proteins)")
        if st.button("🔓 Clear Cluster Filter", use_container_width=True):
            del st.session_state.selected_cluster_members
            st.rerun()
    return visible_chains


def _render_viewer_style_controls() -> Tuple[str, str]:
    col_styl1, col_styl2, col_styl3 = st.columns([2, 2, 1])
    with col_styl1:
        style_mode = st.selectbox(
            "🎨 Visualization Theme",
            options=[
                "Neon Pro",
                "Scientific Spectral",
                "AlphaFold Confidence",
                "Conservation Density",
                "RMSF Flexibility",
            ],
            index=0,
            help="Choose the color scheme for the 3D viewer. 'Neon Pro' is our vibrant signature style.",
        )
    with col_styl2:
        view_mode = st.radio(
            "🔭 View Mode",
            options=[
                "Superimposed (All models)",
                "Side-by-Side (Comparison Grid)",
            ],
            horizontal=True,
            help="Choose how to see the protein structures. Superimposed shows alignment quality, Grid shows individual shapes.",
        )
    with col_styl3:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if st.button("🔄 Refresh View"):
            st.rerun()
    return style_mode, view_mode


def _render_spin_html_export(pdb_path: Path) -> None:
    if not st.button(
        "🎥 Export Spinning HTML",
        use_container_width=True,
        help="Download a self-contained HTML file with a spinning 3D view",
    ):
        return

    pdb_content = pdb_path.read_text()
    # Escape backticks and backslashes for JS template literal
    pdb_escaped = pdb_content.replace("\\", "\\\\").replace("`", "\\`")

    html_parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">',
        "<title>Structural Superposition - Spin View</title>",
        '<script src="https://3Dmol.org/build/3Dmol-min.js"></script>',
        "<style>body{margin:0;background:#111;overflow:hidden}",
        "#viewer{width:100vw;height:100vh}</style>",
        '</head><body><div id="viewer"></div><script>',
        'let viewer = window["$3Dmol"].createViewer("viewer", {backgroundColor:"#111"});',
        "let pdbData = `" + pdb_escaped + "`;",
        'viewer.addModel(pdbData, "pdb");',
        'viewer.setStyle({}, {cartoon:{color:"spectrum"}});',
        "viewer.zoomTo(); viewer.spin(true); viewer.render();",
        'window.addEventListener("resize", () => viewer.resize());',
        "</script></body></html>",
    ]
    st.download_button(
        "⬇️ Download HTML",
        data="\n".join(html_parts),
        file_name="structure_spin.html",
        mime="text/html",
        use_container_width=True,
    )


def _render_static_pdb_export(pdb_path: Path) -> None:
    if not st.button(
        "📄 Export Static PDB",
        use_container_width=True,
        help="Download the aligned PDB file",
    ):
        return
    st.download_button(
        "⬇️ Download PDB",
        data=pdb_path.read_bytes(),
        file_name="alignment.pdb",
        mime="chemical/x-pdb",
        use_container_width=True,
    )


def _render_export_controls(pdb_path: Path) -> None:
    st.divider()
    st.markdown("#### 📸 Export Options")
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        _render_spin_html_export(pdb_path)
    with exp_col2:
        _render_static_pdb_export(pdb_path)


def _render_active_highlights_info(hl_chains: dict) -> None:
    if not hl_chains:
        return
    chain_summary = ", ".join(
        f"Chain {c}: {len(r)} residues" for c, r in hl_chains.items()
    )
    st.info(f"🔥 Highlighting: {chain_summary}")


def _render_viewer_body(results: Dict[str, Any]) -> None:
    with st.spinner("Rendering 3D structures..."):
        pdb_path = results["alignment_pdb"]

    visible_chains = _render_cluster_filter_banner(results)
    hl_chains = st.session_state.get("highlight_chains", {})
    style_mode, view_mode = _render_viewer_style_controls()
    residue_colors = _build_residue_colors(style_mode, results)

    if view_mode == "Superimposed (All models)":
        _render_superimposed_view(
            pdb_path, hl_chains, visible_chains, style_mode, residue_colors
        )
    else:
        all_members = list(results["rmsd_df"].index)
        _render_side_by_side_grid(
            pdb_path, hl_chains, style_mode, all_members, residue_colors
        )

    st.caption("""
    **Controls:**
    - **Left click + drag**: Rotate | **Right click + drag**: Zoom | **Scroll**: Zoom in/out
    - Each structure is colored differently for easy identification
    """)

    _render_export_controls(pdb_path)
    _render_active_highlights_info(hl_chains)


def _render_active_viewer(results: Dict[str, Any]) -> None:
    if st.button("❌ Close Viewers"):
        st.session_state.show_3d_viewer = False
        # Also clear cluster selection when closing
        if "selected_cluster_members" in st.session_state:
            del st.session_state.selected_cluster_members
        st.rerun()

    try:
        _render_viewer_body(results)
    except Exception as e:
        st.error(f"Failed to load 3D viewer: {str(e)}")


def _render_lazy_load_prompt() -> None:
    st.info("⚠️ 3D visualization requires WebGL and may slow down the app.")
    if st.button("🚀 Initialize 3D Viewers", type="primary"):
        st.session_state.show_3d_viewer = True
        st.rerun()


def render_3d_viewer_tab(results: Dict[str, Any]) -> None:
    """
    Render the 3D Visualization tab.

    Args:
        results: The results dictionary containing alignment PDB path.
    """
    st.subheader("3D Structural Superposition")
    render_learning_card("Structure")
    render_help_expander("superposition")

    st.info(
        "💡 Explore different representations of the aligned structures. Rotate and zoom to investigate."
    )

    if not (results.get("alignment_pdb") and results["alignment_pdb"].exists()):
        st.warning("3D visualization not available")
        return

    if "show_3d_viewer" not in st.session_state:
        st.session_state.show_3d_viewer = False

    if not st.session_state.show_3d_viewer:
        _render_lazy_load_prompt()
    else:
        _render_active_viewer(results)


def _get_visible_chains_from_cluster(results: Dict[str, Any]):
    """Helper to determine which chains should be visible based on cluster selection."""
    visible_chains = None
    members = st.session_state.get("selected_cluster_members")
    if members:
        # Map protein names/IDs to chain IDs (A, B, C...)
        all_members = list(results["rmsd_df"].index)
        visible_chains = [
            chr(ord("A") + all_members.index(m)) for m in members if m in all_members
        ]
    return visible_chains, members


def _render_superimposed_view(
    pdb_path, hl_chains, visible_chains, style_mode, residue_colors=None
):
    """Render the standard superimposed view with 4 representations."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Cartoon (Secondary Structure)**")
        show_structure_in_streamlit(
            pdb_path,
            width=400,
            height=300,
            style="cartoon",
            key="view_cartoon",
            highlight_residues=hl_chains,
            visible_chains=visible_chains,
            style_mode=style_mode,
            residue_colors=residue_colors,
        )
    with col2:
        st.markdown("**Sphere (Spacefill)**")
        show_structure_in_streamlit(
            pdb_path,
            width=400,
            height=300,
            style="sphere",
            key="view_sphere",
            highlight_residues=hl_chains,
            visible_chains=visible_chains,
            style_mode=style_mode,
            residue_colors=residue_colors,
        )

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Stick (Bonds & Atoms)**")
        show_structure_in_streamlit(
            pdb_path,
            width=400,
            height=300,
            style="stick",
            key="view_stick",
            highlight_residues=hl_chains,
            visible_chains=visible_chains,
            style_mode=style_mode,
            residue_colors=residue_colors,
        )
    with col4:
        st.markdown("**Line/Trace (Backbone)**")
        show_structure_in_streamlit(
            pdb_path,
            width=400,
            height=300,
            style="line",
            key="view_line",
            highlight_residues=hl_chains,
            visible_chains=visible_chains,
            style_mode=style_mode,
            residue_colors=residue_colors,
        )


def _render_side_by_side_grid(
    pdb_path, hl_chains, style_mode, all_members, residue_colors=None
):
    """Render each model in its own viewport in a grid layout with synchronized cameras."""
    st.markdown("#### 🔬 Structural Comparison Grid")
    st.caption(
        "Each model from the alignment is displayed in its own viewport below. (Interactions and cameras are synchronized!)"
    )

    from src.backend.structure_viewer import show_synced_grid_in_streamlit
    from pathlib import Path

    show_synced_grid_in_streamlit(
        pdb_file=Path(pdb_path),
        members=all_members,
        highlight_residues=hl_chains,
        style_mode=style_mode,
        residue_colors=residue_colors,
        height=250,
    )
