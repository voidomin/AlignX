import streamlit as st
import pandas as pd
from src.backend.database import HistoryDatabase
from src.frontend.utils import load_css
from src.frontend.analysis import load_run_from_history

# Page Config
st.set_page_config(
    page_title="Mission History | Mustang Holo-Lab", page_icon="🕰️", layout="wide"
)

# Load CSS
load_css()


def init_history_page():
    if "history_db" not in st.session_state:
        st.session_state.history_db = HistoryDatabase()


def render_history_page():
    st.markdown(
        '<h1 style="font-size: 2.5rem;">🕰️ Mission History</h1>', unsafe_allow_html=True
    )
    st.caption("Review past alignments, reload sessions, or clear old data.")

    db = st.session_state.history_db
    runs = db.get_all_runs(limit=20)  # Get more runs for the full page view

    if not runs:
        st.info("No mission history found. Run an analysis to start logging.")
        return

    # Create a nice dataframe view
    data = []
    for run in runs:
        data.append(
            {
                "Run ID": run["id"],
                "Date": run["timestamp"],
                "Proteins": ", ".join(run["pdb_ids"]),
                "Count": len(run["pdb_ids"]),
                "Status": "✅ Complete",  # Assuming saved runs are complete
            }
        )

    df = pd.DataFrame(data)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Past Runs")
        st.dataframe(
            df,
            column_config={
                "Date": st.column_config.DatetimeColumn(format="D MMM YYYY, H:mm"),
                "Proteins": st.column_config.TextColumn(width="medium"),
            },
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            key="history_selection",
        )

        # Handle Selection
        selection = st.session_state.history_selection
        selected_run_id = None
        try:
            # Streamlit 1.41+ returns DataframeSelectionState with .selection.rows
            selected_rows = selection.selection.rows
        except AttributeError:
            # Fallback for dict-style access
            selected_rows = (
                selection.get("rows", []) if isinstance(selection, dict) else []
            )

        if selected_rows and len(selected_rows) > 0:
            idx = selected_rows[0]
            selected_run_id = df.iloc[idx]["Run ID"]

        if selected_run_id:
            st.divider()
            st.markdown(f"### Selected Mission: `{selected_run_id}`")

            # Find run details
            run_details = next((r for r in runs if r["id"] == selected_run_id), None)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Proteins", len(run_details["pdb_ids"]))
            with c2:
                st.metric("Date", run_details["timestamp"])

            st.write("")
            col_act1, col_act2 = st.columns([1, 1])
            with col_act1:
                if st.button(
                    "🚀 Load Mission", type="primary", use_container_width=True
                ):
                    with st.spinner("Loading historical data..."):
                        load_run_from_history(selected_run_id)
                        st.switch_page("app.py")

            with col_act2:
                if st.button(
                    "🗑️ Delete Record", type="secondary", use_container_width=True
                ):
                    if db.delete_run(selected_run_id):
                        st.toast(f"Deleted mission {selected_run_id}", icon="🗑️")
                        st.rerun()
                    else:
                        st.error("Failed to delete record")

    with col2:
        st.subheader("Quick Stats")
        st.metric("Total Missions", len(runs))

        st.divider()
        st.caption("Storage Management")

        if "confirm_clear" not in st.session_state:
            st.session_state.confirm_clear = False

        if not st.session_state.confirm_clear:
            if st.button("Clear All History", type="secondary"):
                st.session_state.confirm_clear = True
                st.rerun()
        else:
            st.warning(
                "⚠️ Using this will permanently wipe the entire database. Are you sure?"
            )
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button(
                    "Yes, Clear All", type="primary", use_container_width=True
                ):
                    if db.clear_all_runs():
                        st.success("Database wiped successfully!")
                        st.session_state.confirm_clear = False
                        st.rerun()
                    else:
                        st.error("Failed to clear database")
            with col_cancel:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.confirm_clear = False
                    st.rerun()


if __name__ == "__main__":
    init_history_page()
    render_history_page()
