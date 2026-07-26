from typing import Any

import streamlit as st


def render_chain_selector(chain_info: dict[str, Any]):
    """
    Render the chain information and selection UI.
    """
    if not chain_info:
        return

    st.success("✓ Chain analysis complete!")
    with st.expander("🔗 Chain Information & Selection", expanded=True):

        for pdb_id, info in chain_info.items():
            # Create a card-like container for each protein
            st.markdown(f"#### {pdb_id}")

            c1, c2 = st.columns([1, 2])

            with c1:
                # Allow selecting chain for THIS PDB
                chain_ids = [c["id"] for c in info["chains"]]
                current_sel = st.session_state.manual_chain_selections.get(
                    pdb_id, chain_ids[0] if chain_ids else "A"
                )

                new_sel = st.selectbox(
                    f"Select Chain for {pdb_id}",
                    options=chain_ids,
                    index=(
                        chain_ids.index(current_sel) if current_sel in chain_ids else 0
                    ),
                    key=f"sel_chain_{pdb_id}",
                    label_visibility="collapsed",
                )
                st.session_state.manual_chain_selections[pdb_id] = new_sel

            with c2:
                cols = st.columns(min(len(info["chains"]), 4))
                for idx, chain in enumerate(info["chains"]):
                    with cols[idx % 4]:
                        # Highlight the selected chain
                        label = f"Chain {chain['id']}"
                        if (
                            chain["id"]
                            == st.session_state.manual_chain_selections[pdb_id]
                        ):
                            label = f"🎯 {label}"
                        st.metric(label, f"{chain['residue_count']} res")
            st.divider()
