import streamlit as st
import pandas as pd
import plotly.express as px
from src.frontend.tabs.common import render_learning_card, render_help_expander

from typing import Dict, Any


def render_rmsd_tab(results: Dict[str, Any]) -> None:
    """
    Render the RMSD Analysis tab.

    Args:
        results: The results dictionary containing RMSD data and stats.
    """
    st.subheader("📊 RMSD & Alignment Quality")
    render_learning_card("Summary")

    # Automated Insights
    if results.get("insights"):
        with st.expander("🧠 Automated Insights (Smart Findings)", expanded=True):
            for insight in results["insights"]:
                st.markdown(insight)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("RMSD Heatmap")
        render_help_expander("rmsd")

        if results.get("heatmap_fig"):
            st.plotly_chart(results["heatmap_fig"], use_container_width=True)
        elif results["heatmap_path"].exists():
            st.image(str(results["heatmap_path"]), use_container_width=True)

    with col2:
        st.subheader("Statistics")
        stats = results["stats"]
        st.metric("Mean RMSD", f"{stats['mean_rmsd']:.2f} Å")

        # New Scientific Metrics
        q_metrics = results.get("quality_metrics", {})
        if q_metrics:
            # Calculate global averages
            avg_tm = sum(m["tm_score"] for m in q_metrics.values()) / len(q_metrics)
            avg_gdt = sum(m["gdt_ts"] for m in q_metrics.values()) / len(q_metrics)

            st.metric(
                "Avg TM-Score",
                f"{avg_tm:.3f}",
                help="Length-independent structural similarity (0-1). >0.5 indicates same fold.",
            )
            st.metric(
                "Avg GDT-TS",
                f"{avg_gdt:.3f}",
                help="Global Distance Test. Higher is better.",
            )

        st.metric("Max RMSD", f"{stats['max_rmsd']:.2f} Å")
        st.metric("Std Dev", f"{stats['std_rmsd']:.2f} Å")

    # Per-Protein Quality Table
    if results.get("quality_metrics"):
        st.subheader("🧬 Per-Protein Structural Quality")
        q_df = pd.DataFrame.from_dict(results["quality_metrics"], orient="index")
        q_df.columns = ["TM-Score", "GDT-TS"]
        q_df.index.name = "Structure"

        # Color formatting
        def color_quality(val):
            if val >= 0.7:
                color = "#4CAF50"  # Green
            elif val >= 0.5:
                color = "#FFC107"  # Amber
            else:
                color = "#F44336"  # Red
            return f"color: {color}; font-weight: bold"

        st.table(q_df.style.format("{:.3f}").applymap(color_quality))

    st.subheader("RMSD Matrix")
    colormap = st.session_state.config.get("visualization", {}).get(
        "heatmap_colormap", "RdYlBu_r"
    )
    st.dataframe(results["rmsd_df"].style.background_gradient(cmap=colormap))

    st.divider()
    st.subheader("Residue-Level Flexibility (RMSF)")
    render_help_expander("rmsf")

    if results.get("rmsf_values"):
        rmsf_data = pd.DataFrame(
            {
                "Residue Position": range(1, len(results["rmsf_values"]) + 1),
                "RMSF (Å)": results["rmsf_values"],
            }
        )

        fig = px.line(
            rmsf_data,
            x="Residue Position",
            y="RMSF (Å)",
            title="Structural Fluctuation per Position",
            template="plotly_white",
        )
        fig.update_traces(line_color="#2196F3", line_width=2)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Residue RMSF data not available")
