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

    # Ensure id is present in the dictionary for downstream tabs
    if "id" not in results:
        results["id"] = results.get("run_id", "latest")

    # --- Results Summary Banner (#8) ---
    _render_results_banner(results)

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
        "👁️ View Full Detailed Analysis", type="primary", 
    ):
        st.session_state.active_tab = "Results"
        st.rerun()


def _render_results_banner(results: Dict[str, Any]) -> None:
    """Render a rich summary banner at the top of the results view (#8)."""
    import numpy as np

    n_proteins = len(results.get("pdb_ids", []))
    run_name = results.get("name", "Latest Run")
    timestamp = results.get("timestamp", "")[:10]

    # Compute avg RMSD + homogeneity label
    avg_rmsd = None
    homogeneity = ""
    homogeneity_color = "#888"
    try:
        df = results.get("rmsd_df")
        if df is not None:
            vals = df.values
            upper = vals[np.triu_indices_from(vals, k=1)]
            if len(upper) > 0:
                avg_rmsd = float(np.mean(upper))
                if avg_rmsd < 1.0:
                    homogeneity, homogeneity_color = "Very High Homogeneity", "#00c864"
                elif avg_rmsd < 2.0:
                    homogeneity, homogeneity_color = "High Homogeneity", "#42eaff"
                elif avg_rmsd < 5.0:
                    homogeneity, homogeneity_color = "Moderate Diversity", "#ffb343"
                else:
                    homogeneity, homogeneity_color = "High Diversity", "#ff6060"
    except Exception:
        pass

    rmsd_str = f"{avg_rmsd:.2f} Å" if avg_rmsd is not None else "—"

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, rgba(0,200,100,0.06) 0%, rgba(66,234,255,0.06) 100%);
            border: 1px solid rgba(0,200,100,0.25);
            border-radius: 14px;
            padding: 1.2rem 1.5rem;
            margin-bottom: 1.2rem;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 1.5rem;
        ">
            <div style="flex:1; min-width:180px;">
                <div style="font-size:0.72rem; color:#888; text-transform:uppercase; letter-spacing:1px;">Run</div>
                <div style="font-weight:700; font-size:1rem; color:#fff;">{run_name}</div>
                <div style="font-size:0.75rem; color:#555;">{timestamp}</div>
            </div>
            <div style="text-align:center; min-width:100px;">
                <div style="font-size:0.72rem; color:#888; text-transform:uppercase; letter-spacing:1px;">Proteins</div>
                <div style="font-weight:800; font-size:1.8rem; color:#ff7e42;">{n_proteins}</div>
            </div>
            <div style="text-align:center; min-width:100px;">
                <div style="font-size:0.72rem; color:#888; text-transform:uppercase; letter-spacing:1px;">Avg RMSD</div>
                <div style="font-weight:800; font-size:1.8rem; color:#42eaff;">{rmsd_str}</div>
            </div>
            <div style="text-align:center; min-width:140px;">
                <div style="font-size:0.72rem; color:#888; text-transform:uppercase; letter-spacing:1px;">Structural Similarity</div>
                <div style="font-weight:700; font-size:0.95rem; color:{homogeneity_color};">{"● " + homogeneity if homogeneity else "—"}</div>
            </div>
        </div>
        <p style="color:#666; font-size:0.78rem; margin:-0.5rem 0 1rem;">
            💡 <strong style="color:#aaa;">Suggested order:</strong>
            📊 Summary → 🧬 Sequences → 🌳 Tree → 🔍 Clusters → 🔮 3D Viewer
        </p>
        """,
        unsafe_allow_html=True,
    )


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

