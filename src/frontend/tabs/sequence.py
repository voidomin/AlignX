import streamlit as st
import pandas as pd
from typing import List, Dict, Any
from src.frontend.tabs.common import render_learning_card

_ALL_PROTEINS_LABEL = "All Proteins (Alignment Columns)"


def _parse_range_str(range_str: str, max_val: int) -> List[int]:
    """
    Parse a range string like '1-20, 23-25, 30' into a sorted list of ints.

    Args:
        range_str: User input range string.
        max_val: Maximum allowed residue index.

    Returns:
        Sorted list of unique integer residue indices.
    """
    if not range_str.strip():
        return []

    result = set()
    parts = range_str.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                start_str, end_str = part.split("-")
                start = max(1, int(start_str))
                end = min(max_val, int(end_str))
                if start <= end:
                    result.update(range(start, end + 1))
            except ValueError:
                pass
        else:
            try:
                val = int(part)
                if 1 <= val <= max_val:
                    result.add(val)
            except ValueError:
                pass
    return sorted(result)


def _gaps_to_ranges_str(gaps: List[int]) -> str:
    """
    Convert a list of gap positions to a compact range string like '21-22, 26-29'.

    Args:
        gaps: Sorted list of gap positions.

    Returns:
        Compact string representation of ranges.
    """
    if not gaps:
        return "None"
    ranges = []
    if not gaps:
        return "None"

    start = gaps[0]
    end = gaps[0]

    for i in range(1, len(gaps)):
        if gaps[i] == end + 1:
            end = gaps[i]
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = gaps[i]
            end = gaps[i]
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)


def _selection_to_range_str(residues: List[int]) -> str:
    """
    Convert a list of residue numbers to a compact range string.

    Args:
        residues: List of residue numbers.

    Returns:
        Compact string representation.
    """
    if not residues:
        return ""
    residues = sorted(residues)
    ranges = []
    start = residues[0]
    end = residues[0]
    for r in residues[1:]:
        if r == end + 1:
            end = r
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = r
            end = r
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)


def find_motif_matches(sequences: Dict[str, str], query: str) -> Dict[str, List[int]]:
    """
    Find columns in the alignment matching a motif query.
    Supports wildcards like 'X', '.', or '-' in the query.
    Example: 'RYY' or 'G.G' or 'G-P'
    """
    import re

    matches_map = {}
    if not query.strip():
        return matches_map

    # Clean query: convert 'X' or 'x' or '-' to regex wildcard '.'
    clean_query = query.upper().replace("X", ".").replace("-", ".").replace(" ", "")
    try:
        pattern = re.compile(clean_query)
    except re.error:
        return {}  # Invalid regex

    for name, aligned_seq in sequences.items():
        # Get raw sequence and its alignment index map
        raw_chars = []
        raw_to_aligned = {}  # raw index (0-indexed) -> aligned index (1-indexed)

        current_raw_idx = 0
        for aligned_idx, char in enumerate(aligned_seq):
            if char != "-":
                raw_chars.append(char)
                raw_to_aligned[current_raw_idx] = aligned_idx + 1
                current_raw_idx += 1

        raw_seq = "".join(raw_chars).upper()

        # Find all matches of pattern in raw_seq
        aligned_positions = []
        for match in pattern.finditer(raw_seq):
            start, end = match.span()  # [start, end)
            for raw_pos in range(start, end):
                if raw_pos in raw_to_aligned:
                    aligned_positions.append(raw_to_aligned[raw_pos])

        if aligned_positions:
            matches_map[name] = aligned_positions

    return matches_map


def render_sequences_tab(results: Dict[str, Any]) -> None:
    """
    Render the Sequence Analysis tab.

    Args:
        results: The results dictionary containing sequence alignment info.
    """
    render_learning_card("Sequence")
    st.subheader("🧬 Sequence Alignment")

    # Show Global Metrics
    identity = results["stats"].get("seq_identity", 0.0)
    st.metric(
        "Global Sequence Identity",
        f"{identity:.1f}%",
        help="Average pairwise identity across all aligned structures.",
    )

    st.markdown(
        """
        <div style="
            display: flex;
            flex-wrap: wrap;
            gap: 0.8rem;
            align-items: center;
            margin-bottom: 1.2rem;
            padding: 0.6rem 0.8rem;
            border-radius: 8px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
        ">
            <span style="font-size: 0.9rem; font-weight: 600; color: #ccc; margin-right: 0.5rem;">🧬 Conservation Legend:</span>
            <span style="background-color: #ff3333; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem;">100% Identity (Red)</span>
            <span style="background-color: #ffff33; color: black; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem;">High Similarity >70% (Yellow)</span>
            <span style="background-color: rgba(255,255,255,0.08); color: #888; padding: 2px 8px; border-radius: 4px; font-weight: 500; font-size: 0.8rem; border: 1px solid rgba(255,255,255,0.05);">Variable (Grey)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if results.get("sequences") and results.get("conservation"):
        sequences = results["sequences"]
        conservation = results["conservation"]

        # 1. Visualization
        html_view = st.session_state.sequence_viewer.generate_html(
            sequences, conservation
        )

        # Dynamic Height Calculation to fix UI gap
        n_seqs = len(sequences)
        viz_height = min(600, max(150, 60 + (n_seqs * 30)))
        st.components.v1.html(html_view, height=viz_height, scrolling=True)

        # 2. Alignment Table with Gap Indicators
        st.markdown("#### Alignment Details & Gaps")
        table_data = []
        for name, seq in sequences.items():
            gaps = [i + 1 for i, char in enumerate(seq) if char == "-"]
            raw_seq = seq.replace("-", "")
            table_data.append(
                {
                    "PDB ID": name,
                    "Total Length": len(raw_seq),
                    "Gap Count": len(gaps),
                    "Gap Positions": _gaps_to_ranges_str(gaps),
                }
            )
        st.table(pd.DataFrame(table_data))

        # Motif Search & Highlight
        st.divider()
        st.markdown("#### 🔍 Sequence Motif Search & 3D Mapping")
        st.caption(
            "Search for specific amino acid sequences or motifs (e.g. `RYY`, `G.G` or `G-P` where '.' or '-' is a wildcard) and highlight them in the 3D superposition."
        )

        motif_query = st.text_input(
            "Enter sequence motif:",
            value=st.session_state.get("motif_query", ""),
            placeholder="e.g. RYY or NP.Y or G-P-X",
            key="motif_search_input",
        )

        if motif_query:
            st.session_state.motif_query = motif_query
            matches = find_motif_matches(sequences, motif_query)
            if matches:
                # Count total matches
                total_hits = sum(len(cols) for cols in matches.values())
                st.success(
                    f"✨ Found {total_hits} matching residue positions across {len(matches)} proteins!"
                )

                # Show matches details
                match_summary = []
                for name, cols in matches.items():
                    # Map alignment columns to raw residue numbers for printing
                    raw_res_nums = []
                    current_res = 1
                    seq = sequences[name]
                    for i, char in enumerate(seq):
                        if char != "-":
                            if (i + 1) in cols:
                                raw_res_nums.append(current_res)
                            current_res += 1
                    ranges_str = _selection_to_range_str(raw_res_nums)
                    match_summary.append(
                        {"PDB ID": name, "Residues Matching Motif": ranges_str}
                    )
                st.table(pd.DataFrame(match_summary))

                if st.button(
                    "⭐ Highlight Motif in 3D Viewer",
                    use_container_width=True,
                    type="primary",
                ):
                    # Map match columns to chain-level residue highlights
                    all_headers = list(sequences.keys())
                    final_mapping = {}
                    for i in range(len(all_headers)):
                        c_id = chr(ord("A") + i)
                        final_mapping[c_id] = []

                    for name, cols in matches.items():
                        p_idx = all_headers.index(name)
                        chain_id = chr(ord("A") + p_idx)

                        raw_res_nums = []
                        current_res = 1
                        seq = sequences[name]
                        for i, char in enumerate(seq):
                            if char != "-":
                                if (i + 1) in cols:
                                    raw_res_nums.append(current_res)
                                current_res += 1
                        final_mapping[chain_id].extend(raw_res_nums)

                    st.session_state.highlight_chains = final_mapping
                    st.session_state.show_3d_viewer = True
                    st.toast(
                        "Motif highlighted! Go to the '3D Visualization' tab to view.",
                        icon="✨",
                    )
                    st.rerun()
            else:
                st.warning("No matches found for this motif pattern.")

        # 3. Conserved Residue Highlighting
        st.divider()
        st.markdown("#### 🎯 Selective Extraction & Pocket Analysis")
        st.caption(
            "Identify 100% conserved residues and highlight them in the 3D viewer."
        )

        # Find 100% conserved columns (using conservation from sequence_viewer)
        conserved_cols = [i for i, val in enumerate(conservation) if val >= 1.0]

        if conserved_cols:
            n_total = len(conservation)
            st.success(
                f"Found {len(conserved_cols)} strictly conserved residues ({(len(conserved_cols)/n_total)*100:.1f}% of alignment)"
            )

            if "residue_selections" not in st.session_state:
                st.session_state.residue_selections = {}

            sel_col1, sel_col2 = st.columns(2)

            with sel_col1:
                st.write("**Selection Target**")
                target_protein = st.selectbox(
                    "Apply selection to:",
                    [_ALL_PROTEINS_LABEL] + list(sequences.keys()),
                    index=0,
                    help="Choose 'All Proteins' to select columns in the alignment, or a specific protein to use its internal numbering.",
                )

                col1_btn, col2_btn = st.columns(2)
                with col1_btn:
                    if st.button(
                        "⭐ Select All strictly Conserved columns",
                        use_container_width=True,
                    ):
                        cons_str = _selection_to_range_str(
                            [i + 1 for i in conserved_cols]
                        )
                        target_k = _ALL_PROTEINS_LABEL
                        st.session_state.residue_selections[target_k] = cons_str
                        st.session_state[f"text_input_{target_k}"] = cons_str
                        st.rerun()
                with col2_btn:
                    if st.button("🗑️ Clear All Selections", use_container_width=True):
                        st.session_state.residue_selections.clear()
                        # Clear text input widget states (reassigns existing
                        # keys only, never inserts/deletes, so no defensive
                        # copy is needed here unlike sidebar.py's soft reset).
                        for k in st.session_state.keys():
                            if k.startswith("text_input_"):
                                st.session_state[k] = ""
                        # Also clear 3D viewer highlights if active
                        if "highlight_chains" in st.session_state:
                            st.session_state.highlight_chains.clear()
                        st.rerun()

            with sel_col2:
                st.write("**Manual Selection Input**")
                def_val = st.session_state.residue_selections.get(target_protein, "")
                user_input = st.text_input(
                    "Enter residue ranges (e.g. 1-10, 15, 20-25):",
                    value=def_val,
                    key=f"text_input_{target_protein}",
                )

                if user_input != def_val:
                    st.session_state.residue_selections[target_protein] = user_input

                current_selected = _parse_range_str(user_input, n_total)
                if current_selected:
                    st.caption(
                        f"📍 {len(current_selected)} residues active for this target."
                    )

            # Check if we have any active selections to show the project button
            active_entries = {
                k: v
                for k, v in st.session_state.residue_selections.items()
                if v.strip()
            }

            if active_entries:
                st.markdown("#### 📋 Selective Extraction Summary")
                # Build summary table
                summary_data = []
                for target, ranges in active_entries.items():
                    summary_data.append({"Target": target, "Residue Ranges": ranges})
                st.table(pd.DataFrame(summary_data))

                st.info(
                    "💡 Click the button below to project these selections onto the 3D structures."
                )

                if st.button(
                    "✨ Project Selection to 3D Viewer",
                    use_container_width=True,
                    type="primary",
                ):
                    # Combine all entries from residue_selections
                    all_headers = list(sequences.keys())
                    final_mapping = {}

                    # Initialize mapping with empty lists for all chains
                    for i in range(len(all_headers)):
                        c_id = chr(ord("A") + i)
                        final_mapping[c_id] = []

                    # Process each entry in selections
                    for (
                        target,
                        input_str,
                    ) in st.session_state.residue_selections.items():
                        if not input_str.strip():
                            continue

                        indices = _parse_range_str(input_str, n_total)

                        if target == _ALL_PROTEINS_LABEL:
                            # Apply columns to EVERY protein
                            for p_idx, (_, seq) in enumerate(sequences.items()):
                                chain_id = chr(ord("A") + p_idx)

                                res_nums = []
                                current_res = 1
                                for i, char in enumerate(seq):
                                    if char != "-":
                                        if (i + 1) in indices:
                                            res_nums.append(current_res)
                                        current_res += 1
                                final_mapping[chain_id].extend(res_nums)
                        else:
                            # Apply internal numbering to SPECIFIC protein
                            # Find index of header in sequences
                            if target in all_headers:
                                p_idx = all_headers.index(target)
                                chain_id = chr(ord("A") + p_idx)
                                final_mapping[chain_id].extend(indices)

                    # De-duplicate
                    for k in final_mapping:
                        final_mapping[k] = sorted(set(final_mapping[k]))

                    st.session_state.highlight_chains = final_mapping
                    st.session_state.show_3d_viewer = True
                    st.success(
                        "Selection transferred. Switch to '3D Visualization' tab to view results."
                    )
        else:
            st.warning("No strictly conserved residues found in this alignment.")
    else:
        st.warning("Alignment file (AFASTA) not found. Sequence tab unavailable.")
