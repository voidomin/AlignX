import pandas as pd
import streamlit as st


def render_metadata_viewer(pdb_ids: list[str], metadata: dict[str, dict[str, str]]):
    """
    Render the protein metadata table.
    """
    if not metadata:
        return

    data = []
    for pid in pdb_ids:
        info = metadata.get(pid, {})
        data.append(
            {
                "PDB ID": pid,
                "Title": info.get("title", "N/A"),
                "Organism": info.get("organism", "N/A"),
                "Method": info.get("method", "N/A"),
                "Resolution": info.get("resolution", "N/A"),
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(
        df,
        column_config={
            "PDB ID": st.column_config.TextColumn(width="small"),
            "Title": st.column_config.TextColumn(width="large"),
        },
        hide_index=True,
        use_container_width=True,
    )
