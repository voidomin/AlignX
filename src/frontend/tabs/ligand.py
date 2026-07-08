import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.backend.structure_viewer import show_ligand_view_in_streamlit
from src.frontend.tabs.common import render_learning_card, render_help_expander


def _find_structure_pdb_path(pdb_id: str, result_dir: Path) -> Optional[Path]:
    """Ligand analysis requires the ORIGINAL (uncleaned) PDB file because
    the cleaning pipeline strips all HETATM records - checks data/raw/
    first, falls back to the (cleaned, may lack ligands) result directory,
    then a fuzzy glob as a last resort."""
    possible_names = [f"{pdb_id}.pdb", f"{pdb_id.lower()}.pdb", f"{pdb_id.upper()}.pdb"]

    for root in (Path("data/raw"), result_dir):
        for name in possible_names:
            p = root / name
            if p.exists():
                return p

    matches = list(result_dir.glob(f"*{pdb_id}*.pdb"))
    return matches[0] if matches else None


def _record_pocket_history(
    interactions: Dict[str, Any], pdb_path: Path, pdb_id: str
) -> None:
    entry = interactions.copy()
    entry["pdb_path"] = str(pdb_path)
    entry["pdb_id"] = pdb_id

    if "pocket_history" not in st.session_state:
        st.session_state.pocket_history = []
    st.session_state.pocket_history = [
        x
        for x in st.session_state.pocket_history
        if x["ligand"] != interactions["ligand"]
    ]
    st.session_state.pocket_history.append(entry)


def _render_ligand_picker_and_analysis(
    pdb_path: Path, selected_pdb_ligand: str
) -> None:
    ligands = st.session_state.ligand_analyzer.get_ligands(pdb_path)
    if not ligands:
        st.info("No ligands found in this structure.")
        return

    st.success(f"Found {len(ligands)} ligands")
    ligand_options = {f"{lig['name']} ({lig['id']})": lig for lig in ligands}
    selected_ligand_name = st.selectbox("Select Ligand", list(ligand_options.keys()))
    selected_ligand = ligand_options[selected_ligand_name]

    if st.button("Analyze Interactions", type="primary", use_container_width=True):
        interactions = st.session_state.ligand_analyzer.calculate_interactions(
            pdb_path, selected_ligand["id"]
        )
        st.session_state.current_interactions = interactions
        st.session_state.current_ligand_pdb = pdb_path
        _record_pocket_history(interactions, pdb_path, selected_pdb_ligand)


def _get_dataframe_selection_indices(df_key: str) -> List[int]:
    """Streamlit's dataframe selection state has shifted shape across
    versions (an object with `.selection.rows`, or a plain dict with
    `["selection"]["rows"]`) - handles either."""
    if df_key not in st.session_state:
        return []
    selection = st.session_state[df_key]
    if not selection:
        return []

    if hasattr(selection, "selection"):
        sel_state = selection.selection
        if hasattr(sel_state, "rows"):
            return list(sel_state.rows)
        if isinstance(sel_state, dict) and "rows" in sel_state:
            return list(sel_state["rows"])
    elif isinstance(selection, dict) and "selection" in selection:
        sel_state = selection["selection"]
        if isinstance(sel_state, dict) and "rows" in sel_state:
            return list(sel_state["rows"])
    return []


def _render_interacting_residues_table(
    interactions: Dict[str, Any], df_key: str
) -> None:
    st.markdown("#### Interacting Residues (< 5Å)")
    st.caption("💡 Select one or more rows to highlight residues in 3D.")
    if not interactions["interactions"]:
        st.info("No residues found within cutoff distance.")
        return

    df_int = pd.DataFrame(interactions["interactions"])
    st.dataframe(
        df_int[["residue", "chain", "resi", "distance", "type"]].style.format(
            {"distance": "{:.2f}"}
        ),
        use_container_width=True,
        height=400,
        on_select="rerun",
        selection_mode="multi-row",
        key=df_key,
    )


def _render_binding_site_results(selected_pdb_ligand: str) -> None:
    interactions = st.session_state.current_interactions
    pdb_path = st.session_state.current_ligand_pdb

    if "error" in interactions:
        st.error(interactions["error"])
        return

    st.markdown(f"### Binding Site: **{interactions['ligand']}**")

    # Retrieve highlight selection from session state to prevent one-frame latency
    df_key = f"df_select_{selected_pdb_ligand}_{interactions['ligand']}"
    highlight_indices = _get_dataframe_selection_indices(df_key)

    res_col1, res_col2 = st.columns([1, 1])
    with res_col1:
        show_ligand_view_in_streamlit(
            pdb_path,
            interactions,
            width=500,
            height=450,
            key="ligand_3d",
            highlight_indices=highlight_indices if highlight_indices else None,
        )
    with res_col2:
        _render_interacting_residues_table(interactions, df_key)


def _render_single_ligand_tab(results: Dict[str, Any]) -> None:
    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        selected_pdb_ligand = st.selectbox(
            "Select Protein Structure",
            st.session_state.pdb_ids,
            key="ligand_pdb_select",
        )

    pdb_path = _find_structure_pdb_path(selected_pdb_ligand, results["result_dir"])
    if pdb_path:
        with sel_col2:
            _render_ligand_picker_and_analysis(pdb_path, selected_pdb_ligand)
    else:
        st.error(f"PDB file not found for {selected_pdb_ligand}")

    st.divider()

    if "current_interactions" in st.session_state:
        _render_binding_site_results(selected_pdb_ligand)


def _render_pocket_similarity_matrix(history: List[Dict[str, Any]]) -> None:
    st.subheader("Chemical Environment Similarity Matrix")
    st.caption("Jaccard Index based on shared residue types in the binding pocket.")

    sim_matrix = st.session_state.ligand_analyzer.calculate_interaction_similarity(
        history
    )
    st.dataframe(sim_matrix.style.background_gradient(cmap="Greens", vmin=0, vmax=1))


def _render_pocket_comparison_details(
    d1: Dict[str, Any], d2: Dict[str, Any], l1_id: str, l2_id: str
) -> None:
    row1_c1, row1_c2 = st.columns(2)
    with row1_c1:
        show_ligand_view_in_streamlit(
            Path(d1["pdb_path"]), d1, width=350, height=350, key="ligand_view_1"
        )
    with row1_c2:
        show_ligand_view_in_streamlit(
            Path(d2["pdb_path"]), d2, width=350, height=350, key="ligand_view_2"
        )

    st.subheader("Comparison Details")
    set1 = {x["residue"] for x in d1["interactions"]}
    set2 = {x["residue"] for x in d2["interactions"]}
    shared = set1.intersection(set2)
    unique1 = set1 - set2
    unique2 = set2 - set1

    delta_col1, delta_col2, delta_col3 = st.columns(3)
    delta_col1.metric("Shared Residue Types", len(shared), help=f"{', '.join(shared)}")
    delta_col2.metric(f"Unique to {l1_id}", len(unique1), help=f"{', '.join(unique1)}")
    delta_col3.metric(f"Unique to {l2_id}", len(unique2), help=f"{', '.join(unique2)}")


def _render_side_by_side_pocket_view(history: List[Dict[str, Any]]) -> None:
    st.subheader("⚔️ Side-by-Side Pocket View")

    c_sel1, c_sel2 = st.columns(2)
    options = [h["ligand"] for h in history]
    l1_id = c_sel1.selectbox("Pocket 1", options, index=0, key="cmp_p1")
    l2_id = c_sel2.selectbox(
        "Pocket 2", options, index=1 if len(options) > 1 else 0, key="cmp_p2"
    )
    if not (l1_id and l2_id):
        return

    d1 = next(h for h in history if h["ligand"] == l1_id)
    d2 = next(h for h in history if h["ligand"] == l2_id)
    _render_pocket_comparison_details(d1, d2, l1_id, l2_id)


def _render_pocket_comparison_tab() -> None:
    st.caption(
        "Compare the environments of analyzed ligands. (Analyze ligands in the Single tab first to add them here)."
    )

    history = st.session_state.get("pocket_history", [])
    if history and st.button("🗑️ Clear Interaction History", use_container_width=True):
        st.session_state.pocket_history = []
        if "current_interactions" in st.session_state:
            del st.session_state.current_interactions
        st.rerun()

    if len(history) < 2:
        st.warning(
            "⚠️ Analyze at least 2 different ligands in the 'Single Ligand Analysis' tab to enable comparison."
        )
        return

    _render_pocket_similarity_matrix(history)
    st.divider()
    _render_side_by_side_pocket_view(history)


def _find_sasa_pdb_path(pdb_id: str, result_dir: Path) -> Optional[Path]:
    for name in [f"{pdb_id}.pdb", f"{pdb_id.lower()}.pdb", f"{pdb_id.upper()}.pdb"]:
        p = result_dir / name
        if p.exists():
            return p
    return None


def _render_sasa_chart(sasa: Dict[str, Any], selected_sasa_pdb: str) -> None:
    if not sasa.get("residues"):
        return
    import plotly.express as px

    df_sasa = pd.DataFrame(sasa["residues"])
    df_sasa["label"] = df_sasa["residue"] + df_sasa["resi"].astype(str)

    fig = px.bar(
        df_sasa,
        x="label",
        y="sasa",
        color="sasa",
        color_continuous_scale="Viridis",
        labels={"label": "Residue", "sasa": "SASA (Å²)"},
        title=f"Per-Residue SASA — {selected_sasa_pdb}",
    )
    fig.update_layout(height=400, xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def _render_sasa_results(sasa: Dict[str, Any], selected_sasa_pdb: str) -> None:
    if "error" in sasa:
        st.error(sasa["error"])
        return

    m1, m2 = st.columns(2)
    m1.metric("Total SASA", f"{sasa['total_sasa']:.1f} Å²")
    chain_summary = ", ".join(
        f"Chain {k}: {v:.0f} Å²" for k, v in sasa["chain_sasa"].items()
    )
    m2.metric("Chains", chain_summary)
    _render_sasa_chart(sasa, selected_sasa_pdb)


def _render_sasa_tab(results: Dict[str, Any]) -> None:
    st.caption(
        "Compute Solvent Accessible Surface Area (SASA) using the Shrake-Rupley algorithm."
    )

    selected_sasa_pdb = st.selectbox(
        "Select Protein", st.session_state.pdb_ids, key="sasa_pdb_select"
    )
    sasa_pdb_path = _find_sasa_pdb_path(selected_sasa_pdb, results["result_dir"])

    if not sasa_pdb_path:
        st.error(f"PDB file not found for {selected_sasa_pdb}")
        return

    if st.button(
        "🌊 Calculate SASA", type="primary", use_container_width=True, key="btn_sasa"
    ):
        with st.spinner("Computing solvent accessible surface area..."):
            st.session_state.sasa_result = (
                st.session_state.ligand_analyzer.calculate_sasa(sasa_pdb_path)
            )
            st.session_state.sasa_pdb_id = selected_sasa_pdb

    if (
        "sasa_result" in st.session_state
        and st.session_state.get("sasa_pdb_id") == selected_sasa_pdb
    ):
        _render_sasa_results(st.session_state.sasa_result, selected_sasa_pdb)


def render_ligand_tab(results: Dict[str, Any]) -> None:
    """
    Render the Ligand & Interaction Analysis tab.

    Args:
        results: The results dictionary containing data directory for ligand lookup.
    """
    st.subheader("💊 Ligand & Interaction Analysis")
    render_learning_card("Ligands")
    render_help_expander("ligands")

    tab_single, tab_compare, tab_sasa = st.tabs(
        ["🧪 Single Ligand Analysis", "⚔️ Pocket Comparison", "🌊 Surface Area (SASA)"]
    )

    with tab_single:
        _render_single_ligand_tab(results)
    with tab_compare:
        _render_pocket_comparison_tab()
    with tab_sasa:
        _render_sasa_tab(results)
