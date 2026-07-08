import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Tuple
from src.frontend.tabs.common import render_learning_card

_ALL_PROTEINS_LABEL = "All Proteins (Alignment Columns)"


def _parse_range_part(part: str, max_val: int) -> List[int]:
    """One comma-separated token of a range string ('1-20' or '30') into
    the residue indices it names, clamped to [1, max_val] - or [] if the
    token is empty, malformed, or out of range."""
    part = part.strip()
    if not part:
        return []

    if "-" in part:
        try:
            start_str, end_str = part.split("-")
            start = max(1, int(start_str))
            end = min(max_val, int(end_str))
            return list(range(start, end + 1)) if start <= end else []
        except ValueError:
            return []

    try:
        val = int(part)
        return [val] if 1 <= val <= max_val else []
    except ValueError:
        return []


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
    for part in range_str.split(","):
        result.update(_parse_range_part(part, max_val))
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


def _raw_to_aligned_map(aligned_seq: str) -> Tuple[str, Dict[int, int]]:
    """Strips gaps from an aligned sequence, returning the raw (ungapped)
    sequence and a map from raw (0-indexed) position to aligned (1-indexed)
    column - lets a match found in the raw sequence be reported at its real
    alignment column."""
    raw_chars = []
    raw_to_aligned = {}
    current_raw_idx = 0
    for aligned_idx, char in enumerate(aligned_seq):
        if char != "-":
            raw_chars.append(char)
            raw_to_aligned[current_raw_idx] = aligned_idx + 1
            current_raw_idx += 1
    return "".join(raw_chars).upper(), raw_to_aligned


def _motif_matches_for_sequence(aligned_seq: str, pattern) -> List[int]:
    raw_seq, raw_to_aligned = _raw_to_aligned_map(aligned_seq)
    aligned_positions = []
    for match in pattern.finditer(raw_seq):
        start, end = match.span()  # [start, end)
        for raw_pos in range(start, end):
            if raw_pos in raw_to_aligned:
                aligned_positions.append(raw_to_aligned[raw_pos])
    return aligned_positions


def find_motif_matches(sequences: Dict[str, str], query: str) -> Dict[str, List[int]]:
    """
    Find columns in the alignment matching a motif query.
    Supports wildcards like 'X', '.', or '-' in the query.
    Example: 'RYY' or 'G.G' or 'G-P'
    """
    import re

    if not query.strip():
        return {}

    # Clean query: convert 'X' or 'x' or '-' to regex wildcard '.'
    clean_query = query.upper().replace("X", ".").replace("-", ".").replace(" ", "")
    try:
        pattern = re.compile(clean_query)
    except re.error:
        return {}  # Invalid regex

    matches_map = {}
    for name, aligned_seq in sequences.items():
        positions = _motif_matches_for_sequence(aligned_seq, pattern)
        if positions:
            matches_map[name] = positions
    return matches_map


def _aligned_cols_to_raw_residues(seq: str, aligned_cols) -> List[int]:
    """Maps a set/list of 1-indexed aligned column numbers back to the
    1-indexed raw (gap-stripped) residue numbers they correspond to in
    this particular sequence."""
    cols = set(aligned_cols)
    raw_nums = []
    current_res = 1
    for i, char in enumerate(seq):
        if char != "-":
            if (i + 1) in cols:
                raw_nums.append(current_res)
            current_res += 1
    return raw_nums


def _empty_chain_mapping(sequences: Dict[str, str]) -> Dict[str, List[int]]:
    return {chr(ord("A") + i): [] for i in range(len(sequences))}


def _render_conservation_legend() -> None:
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


def _render_alignment_visualization(
    sequences: Dict[str, str], conservation: list
) -> None:
    html_view = st.session_state.sequence_viewer.generate_html(sequences, conservation)
    # Dynamic Height Calculation to fix UI gap
    n_seqs = len(sequences)
    viz_height = min(600, max(150, 60 + (n_seqs * 30)))
    st.components.v1.html(html_view, height=viz_height, scrolling=True)


def _render_alignment_details_table(sequences: Dict[str, str]) -> None:
    st.markdown("#### Alignment Details & Gaps")
    table_data = []
    for name, seq in sequences.items():
        gaps = [i + 1 for i, char in enumerate(seq) if char == "-"]
        table_data.append(
            {
                "PDB ID": name,
                "Total Length": len(seq.replace("-", "")),
                "Gap Count": len(gaps),
                "Gap Positions": _gaps_to_ranges_str(gaps),
            }
        )
    st.table(pd.DataFrame(table_data))


def _build_motif_match_summary(
    sequences: Dict[str, str], matches: Dict[str, list]
) -> pd.DataFrame:
    match_summary = [
        {
            "PDB ID": name,
            "Residues Matching Motif": _selection_to_range_str(
                _aligned_cols_to_raw_residues(sequences[name], cols)
            ),
        }
        for name, cols in matches.items()
    ]
    return pd.DataFrame(match_summary)


def _build_chain_mapping_from_matches(
    sequences: Dict[str, str], matches: Dict[str, list]
) -> Dict[str, List[int]]:
    all_headers = list(sequences.keys())
    final_mapping = _empty_chain_mapping(sequences)
    for name, cols in matches.items():
        chain_id = chr(ord("A") + all_headers.index(name))
        final_mapping[chain_id].extend(
            _aligned_cols_to_raw_residues(sequences[name], cols)
        )
    return final_mapping


def _render_motif_matches(sequences: Dict[str, str], matches: Dict[str, list]) -> None:
    total_hits = sum(len(cols) for cols in matches.values())
    st.success(
        f"✨ Found {total_hits} matching residue positions across {len(matches)} proteins!"
    )
    st.table(_build_motif_match_summary(sequences, matches))

    if st.button(
        "⭐ Highlight Motif in 3D Viewer", use_container_width=True, type="primary"
    ):
        st.session_state.highlight_chains = _build_chain_mapping_from_matches(
            sequences, matches
        )
        st.session_state.show_3d_viewer = True
        st.toast(
            "Motif highlighted! Go to the '3D Visualization' tab to view.", icon="✨"
        )
        st.rerun()


def _render_motif_search_section(sequences: Dict[str, str]) -> None:
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
    if not motif_query:
        return

    st.session_state.motif_query = motif_query
    matches = find_motif_matches(sequences, motif_query)
    if matches:
        _render_motif_matches(sequences, matches)
    else:
        st.warning("No matches found for this motif pattern.")


def _render_conserved_selection_buttons(conserved_cols: List[int]) -> None:
    col1_btn, col2_btn = st.columns(2)
    with col1_btn:
        if st.button(
            "⭐ Select All strictly Conserved columns", use_container_width=True
        ):
            cons_str = _selection_to_range_str([i + 1 for i in conserved_cols])
            st.session_state.residue_selections[_ALL_PROTEINS_LABEL] = cons_str
            st.session_state[f"text_input_{_ALL_PROTEINS_LABEL}"] = cons_str
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


def _render_manual_selection_input(target_protein: str, n_total: int) -> None:
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
        st.caption(f"📍 {len(current_selected)} residues active for this target.")


def _build_projection_mapping(
    sequences: Dict[str, str], residue_selections: Dict[str, str], n_total: int
) -> Dict[str, List[int]]:
    all_headers = list(sequences.keys())
    final_mapping = _empty_chain_mapping(sequences)

    for target, input_str in residue_selections.items():
        if not input_str.strip():
            continue
        indices = _parse_range_str(input_str, n_total)

        if target == _ALL_PROTEINS_LABEL:
            # Apply columns to EVERY protein
            for p_idx, (_, seq) in enumerate(sequences.items()):
                chain_id = chr(ord("A") + p_idx)
                final_mapping[chain_id].extend(
                    _aligned_cols_to_raw_residues(seq, indices)
                )
        elif target in all_headers:
            # Apply internal numbering to SPECIFIC protein
            chain_id = chr(ord("A") + all_headers.index(target))
            final_mapping[chain_id].extend(indices)

    return {k: sorted(set(v)) for k, v in final_mapping.items()}


def _render_selective_extraction_summary(
    sequences: Dict[str, str], n_total: int
) -> None:
    active_entries = {
        k: v for k, v in st.session_state.residue_selections.items() if v.strip()
    }
    if not active_entries:
        return

    st.markdown("#### 📋 Selective Extraction Summary")
    summary_data = [
        {"Target": target, "Residue Ranges": ranges}
        for target, ranges in active_entries.items()
    ]
    st.table(pd.DataFrame(summary_data))
    st.info(
        "💡 Click the button below to project these selections onto the 3D structures."
    )

    if st.button(
        "✨ Project Selection to 3D Viewer", use_container_width=True, type="primary"
    ):
        st.session_state.highlight_chains = _build_projection_mapping(
            sequences, st.session_state.residue_selections, n_total
        )
        st.session_state.show_3d_viewer = True
        st.success(
            "Selection transferred. Switch to '3D Visualization' tab to view results."
        )


def _render_conserved_residue_section(
    sequences: Dict[str, str], conservation: list
) -> None:
    st.divider()
    st.markdown("#### 🎯 Selective Extraction & Pocket Analysis")
    st.caption("Identify 100% conserved residues and highlight them in the 3D viewer.")

    conserved_cols = [i for i, val in enumerate(conservation) if val >= 1.0]
    if not conserved_cols:
        st.warning("No strictly conserved residues found in this alignment.")
        return

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
        _render_conserved_selection_buttons(conserved_cols)
    with sel_col2:
        _render_manual_selection_input(target_protein, n_total)

    _render_selective_extraction_summary(sequences, n_total)


def render_sequences_tab(results: Dict[str, Any]) -> None:
    """
    Render the Sequence Analysis tab.

    Args:
        results: The results dictionary containing sequence alignment info.
    """
    render_learning_card("Sequence")
    st.subheader("🧬 Sequence Alignment")

    identity = results["stats"].get("seq_identity", 0.0)
    st.metric(
        "Global Sequence Identity",
        f"{identity:.1f}%",
        help="Average pairwise identity across all aligned structures.",
    )
    _render_conservation_legend()

    if not (results.get("sequences") and results.get("conservation")):
        st.warning("Alignment file (AFASTA) not found. Sequence tab unavailable.")
        return

    sequences = results["sequences"]
    conservation = results["conservation"]

    _render_alignment_visualization(sequences, conservation)
    _render_alignment_details_table(sequences)
    _render_motif_search_section(sequences)
    _render_conserved_residue_section(sequences, conservation)
