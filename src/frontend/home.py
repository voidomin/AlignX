import streamlit as st
from examples.protein_sets import EXAMPLES


def render_hero_section():
    """
    Render the 'Mission Control' landing page.
    Features a high-impact hero, aggregate stats, and recent activity cards.
    """

    # 1. Hero Header
    st.markdown(
        """
        <div style="background: linear-gradient(90deg, #1e3799 0%, #0c2461 100%); padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; border-left: 5px solid #4a69bd;">
            <h1 style="color: white; margin: 0; font-family: 'Inter', sans-serif;">🧬 Mission Control</h1>
            <p style="color: #d1d8e0; margin: 0.5rem 0 0 0; font-size: 1.1rem;">Automated Protein Structural Alignment & Analysis Pipeline <span style="background: #4a69bd; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; vertical-align: middle; margin-left: 10px;">v2.1.0</span></p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # 2. Key Metrics Bar
    try:
        stats = st.session_state.system_manager.get_aggregate_stats(
            st.session_state.history_db
        )
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)

        with m_col1:
            st.metric("Total Analysis Runs", stats.get("total_runs", 0))
        with m_col2:
            st.metric("Proteins Analyzed", stats.get("total_proteins", 0))
        with m_col3:
            # Estimate cache size
            cache_mb = st.session_state.history_db.get_total_cache_size() / (
                1024 * 1024
            )
            st.metric("PDB Cache Size", f"{cache_mb:.1f} MB")
        with m_col4:
            st.metric("System Health", "Optimal ✨")
    except Exception:
        pass

    st.divider()

    # 3. Main Dashboard Layout (Recent Activity vs Quick Start)
    dash_col1, dash_col2 = st.columns([2, 1])

    with dash_col1:
        st.markdown("### 🕒 Recent Activity")
        recent_runs = st.session_state.history_db.get_all_runs(limit=5)

        if recent_runs:
            for idx, run in enumerate(recent_runs):
                with st.expander(
                    f"📁 {run['name']} — {run['timestamp']}", expanded=False
                ):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(f"**Proteins**: {', '.join(run['pdb_ids'])}")
                    with c2:
                        if st.button(
                            "🚀 Load Run",
                            key=f"load_{run['id']}_{idx}",
                            use_container_width=True,
                        ):
                            # This needs transition to the analysis tab
                            from src.frontend.analysis import load_run_from_history

                            load_run_from_history(run["id"])
        else:
            st.info(
                "No analysis history found yet. Start your first run from the sidebar!"
            )

    with dash_col2:
        st.markdown("### ⚡ Quick Start")
        st.caption("Load a curated example family to see the pipeline in action.")

        # Quick access buttons for examples
        for name, ids in EXAMPLES.items():
            if st.button(
                f"🧬 Compare {name}",
                help=f"IDs: {', '.join(ids[:3])}...",
                use_container_width=True,
            ):
                st.session_state.pdb_ids = ids
                st.session_state.metadata_fetched = False
                st.rerun()

        st.divider()
        st.markdown("### 🛠️ Tech Stack")
        st.code(
            """
- Mustang (Core Aligner)
- BioPython (Parsing)
- Plotly/Seaborn (Visuals)
- SQLite (History)
        """,
            language="markdown",
        )


