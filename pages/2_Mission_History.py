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


def _build_runs_dataframe(runs):
    return pd.DataFrame(
        [
            {
                "Run ID": run["id"],
                "Date": run["timestamp"],
                "Proteins": ", ".join(run["pdb_ids"]),
                "Count": len(run["pdb_ids"]),
                "Status": "✅ Complete",  # Assuming saved runs are complete
            }
            for run in runs
        ]
    )


def _get_selected_run_id(selection, df):
    try:
        # Streamlit 1.41+ returns DataframeSelectionState with .selection.rows
        selected_rows = selection.selection.rows
    except AttributeError:
        # Fallback for dict-style access
        selected_rows = selection.get("rows", []) if isinstance(selection, dict) else []

    if not selected_rows:
        return None
    return df.iloc[selected_rows[0]]["Run ID"]


def _render_selected_mission_actions(selected_run_id):
    if st.button("🚀 Load Mission", type="primary", use_container_width=True):
        with st.spinner("Loading historical data..."):
            load_run_from_history(selected_run_id)
            st.switch_page("app.py")


def _render_delete_record_action(selected_run_id, db):
    if st.button("🗑️ Delete Record", type="secondary", use_container_width=True):
        if db.delete_run(selected_run_id):
            st.toast(f"Deleted mission {selected_run_id}", icon="🗑️")
            st.rerun()
        else:
            st.error("Failed to delete record")


def _render_selected_run_details(selected_run_id, runs, db):
    st.divider()
    st.markdown(f"### Selected Mission: `{selected_run_id}`")

    run_details = next((r for r in runs if r["id"] == selected_run_id), None)

    c1, c2, _ = st.columns(3)
    with c1:
        st.metric("Proteins", len(run_details["pdb_ids"]))
    with c2:
        st.metric("Date", run_details["timestamp"])

    st.write("")
    col_act1, col_act2 = st.columns([1, 1])
    with col_act1:
        _render_selected_mission_actions(selected_run_id)
    with col_act2:
        _render_delete_record_action(selected_run_id, db)


def _render_past_runs_table(runs, db):
    st.subheader("Past Runs")
    df = _build_runs_dataframe(runs)
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

    selected_run_id = _get_selected_run_id(st.session_state.history_selection, df)
    if selected_run_id:
        _render_selected_run_details(selected_run_id, runs, db)


def _render_clear_history_confirmation(db):
    st.warning("⚠️ Using this will permanently wipe the entire database. Are you sure?")
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Yes, Clear All", type="primary", use_container_width=True):
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


def _render_storage_management(db):
    st.caption("Storage Management")
    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False

    if not st.session_state.confirm_clear:
        if st.button("Clear All History", type="secondary"):
            st.session_state.confirm_clear = True
            st.rerun()
    else:
        _render_clear_history_confirmation(db)


def _render_quick_stats(runs, db):
    st.subheader("Quick Stats")
    st.metric("Total Missions", len(runs))
    st.divider()
    _render_storage_management(db)


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

    col1, col2 = st.columns([2, 1])
    with col1:
        _render_past_runs_table(runs, db)
    with col2:
        _render_quick_stats(runs, db)


if __name__ == "__main__":
    init_history_page()
    render_history_page()
