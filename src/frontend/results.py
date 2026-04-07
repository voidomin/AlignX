import streamlit as st
from typing import Optional, Dict, Any, List
from src.frontend.tabs import (
    rmsd,
    sequence,
    phylo,
    clusters,
    structure,
    ligand,
    downloads,
    comparison,
)


def display_results(results: Optional[Dict[str, Any]] = None) -> None:
    """
    Main results display logic with tabs.

    Args:
        results: Results dictionary. If None, retrieves from session state.
    """
    if results is None:
        results = st.session_state.get("results")

    if not results:
        st.warning("No analysis results found. Please run the analysis first.")
        return

    st.success(f"### Analysis Results: {results.get('name', 'Latest Run')}")
    run_id = results.get("id", "N/A")

    # Ensure id is present in the dictionary for downstream tabs
    if "id" not in results:
        results["id"] = results.get("run_id", "latest")
    timestamp = results.get("timestamp", "N/A")
    st.caption(f"Run ID: `{run_id}` | Timestamp: {timestamp}")

    _render_structural_insights(results.get("insights", []))

    # Inject CSS for horizontally scrollable tab bar
    st.markdown(
        """
        <style>
        /* Make tab bar scrollable on narrow viewports */
        div[data-testid="stTabs"] > div[role="tablist"] {
            overflow-x: auto;
            flex-wrap: nowrap !important;
            scrollbar-width: thin;
            -ms-overflow-style: auto;
            gap: 0 !important;
        }
        div[data-testid="stTabs"] > div[role="tablist"]::-webkit-scrollbar {
            height: 4px;
        }
        div[data-testid="stTabs"] > div[role="tablist"]::-webkit-scrollbar-thumb {
            background: #4a69bd;
            border-radius: 4px;
        }
        div[data-testid="stTabs"] > div[role="tablist"] button {
            white-space: nowrap;
            flex-shrink: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Define tabs (shortened labels for better fit)
    tab_list = [
        "📊 Summary",
        "🧬 Sequences",
        "🌳 Tree",
        "🔍 Clusters",
        "🔮 3D Viewer",
        "💊 Ligands",
        "🔄 Comparison",
        "📥 Downloads",
    ]

    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(tab_list)

    # Ensure id/metadata is present (Defensive)
    if "id" not in results:
        results["id"] = results.get("run_id", "latest")

    with t1:
        try:
            rmsd.render_rmsd_tab(results)
        except Exception as e:
            st.warning("⚠️ Summary tab unavailable for this run.")
            st.caption(f"Details: {e}")

    with t2:
        try:
            sequence.render_sequences_tab(results)
        except Exception:
            st.info("🧬 Sequence alignment data unavailable for this run.")

    with t3:
        try:
            phylo.render_phylo_tree_tab(results)
        except Exception:
            st.info("🌳 Phylogenetic tree data unavailable for this run.")

    with t4:
        try:
            clusters.render_clusters_tab(results)
        except Exception:
            st.info("🔍 Clustering data unavailable for this run.")

    with t5:
        try:
            structure.render_3d_viewer_tab(results)
        except Exception as e:
            st.warning("🔮 3D Viewer unavailable for this run.")
            st.caption(f"Details: {e}")

    with t6:
        try:
            ligand.render_ligand_tab(results)
        except Exception:
            st.info("💊 Ligand analysis unavailable for this run.")

    with t7:
        try:
            comparison.render_comparison_tab(results)
        except Exception:
            st.info("🔄 Comparison data unavailable for this run.")

    with t8:
        try:
            downloads.render_downloads_tab(results)
        except Exception as e:
            st.warning("📥 Downloads unavailable for this run.")
            st.caption(f"Details: {e}")


def render_compact_summary(results: Optional[Dict[str, Any]] = None) -> None:
    """
    Render a high-level summary of results for the dashboard.

    Args:
        results: Results dictionary. If None, retrieves from session state.
    """
    if results is None:
        results = st.session_state.get("results")

    if not results:
        return

    st.markdown("### 📊 Latest Analysis Summary")

    col1, col2, col3, col4, col5 = st.columns(5)
    stats = results.get("stats", {})
    q_metrics = results.get("quality_metrics", {})

    with col1:
        st.metric("Total PDBs", len(results.get("pdb_ids", [])))
    with col2:
        st.metric("Mean RMSD", f"{stats.get('mean_rmsd', 0):.2f} Å")

    if q_metrics:
        avg_tm = sum(m["tm_score"] for m in q_metrics.values()) / len(q_metrics)
        avg_gdt = sum(m["gdt_ts"] for m in q_metrics.values()) / len(q_metrics)
        with col3:
            st.metric("Avg TM-Score", f"{avg_tm:.3f}")
        with col4:
            st.metric("Avg GDT-TS", f"{avg_gdt:.3f}")
    else:
        with col3:
            st.metric("Seq Identity", f"{stats.get('seq_identity', 0):.1f}%")
        with col4:
            st.metric("Coverage", "100%")

    with col5:
        st.metric("Seq Length", results.get("sequence_length", "N/A"))

    if st.button(
        "👁️ View Full Detailed Analysis", type="primary", use_container_width=True
    ):
        st.session_state.active_tab = "Results"
        st.rerun()


def _render_structural_insights(insights: List[str]) -> None:
    """Helper to render structural insights with formatting."""
    if not insights:
        return

    with st.container():
        st.markdown(
            """
            <div style="background-color: rgba(66, 234, 255, 0.05); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(66, 234, 255, 0.2); margin-bottom: 2rem;">
                <h4 style="margin-top: 0; color: #42eaff;">✨ System Structural Insights</h4>
            """,
            unsafe_allow_html=True,
        )

        # Show top 3 by default, others in expander if > 3
        main_insights = insights[:3]
        extra_insights = insights[3:]

        for insight in main_insights:
            st.markdown(f"&nbsp;&nbsp;&nbsp;{insight}")

        if extra_insights:
            with st.expander("🔍 View more findings..."):
                for insight in extra_insights:
                    st.markdown(insight)

        st.markdown("</div>", unsafe_allow_html=True)
