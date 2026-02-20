import streamlit as st
import pandas as pd
from src.frontend.tabs.common import render_learning_card

def _parse_range_str(range_str, max_val):
    """Parse a range string like '1-20, 23-25, 30' into a sorted list of ints."""
    result = set()
    if not range_str or not range_str.strip():
        return []
    for part in range_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                start, end = int(start.strip()), int(end.strip())
                for i in range(max(1, start), min(max_val, end) + 1):
                    result.add(i)
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

def _gaps_to_ranges_str(gaps):
    """Convert a list of gap positions to a compact range string like '21-22, 26-29'."""
    if not gaps:
        return "None"
    ranges = []
    start = gaps[0]
    end = gaps[0]
    for g in gaps[1:]:
        if g == end + 1:
            end = g
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = g
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)

def _selection_to_range_str(residues):
    """Convert a list of residue numbers to a compact range string."""
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
            start = end = r
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)

def render_sequences_tab(results):
    """Render the Sequence Analysis tab."""
    render_learning_card("Sequence")
    st.subheader("🧬 Sequence Alignment")
    
    st.info("🧬 Color code: Red = 100% Identity, Yellow = High Similarity (>70%)")
    
    if results.get('alignment_afasta') and results['alignment_afasta'].exists():
        sequences = st.session_state.sequence_viewer.parse_afasta(results['alignment_afasta'])
        if sequences:
            # 1. Visualization
            conservation = st.session_state.sequence_viewer.calculate_conservation(sequences)
            html_view = st.session_state.sequence_viewer.generate_html(sequences, conservation)
            
            # Dynamic Height Calculation to fix UI gap
            n_seqs = len(sequences)
            viz_height = min(600, max(150, 60 + (n_seqs * 30)))
            st.components.v1.html(html_view, height=viz_height, scrolling=True)
            
            # 2. Alignment Table with Gap Indicators
            st.markdown("### 📊 Alignment Table")
            
            seq_keys = list(sequences.keys())
            seq_len = len(sequences[seq_keys[0]])
            
            table_data = {}
            gap_info = {}  
            max_len = max(len(sequences[name]) for name in seq_keys)
            for name in seq_keys:
                seq = sequences[name]
                residues = []
                protein_gaps = []
                for i, ch in enumerate(seq):
                    pos = i + 1
                    if ch == '-':
                        residues.append('—')  
                        protein_gaps.append(pos)
                    else:
                        residues.append(ch)
                while len(residues) < max_len:
                    residues.append('—')
                    protein_gaps.append(len(residues))
                table_data[name] = residues
                gap_info[name] = protein_gaps
            
            display_len = min(max_len, 100)
            display_data = {name: vals[:display_len] for name, vals in table_data.items()}
            df = pd.DataFrame(display_data, index=range(1, display_len + 1))
            df.index.name = "Pos"
            
            def style_gaps(val):
                if val == '—':
                    return 'background-color: #2a2a3a; color: #666; font-weight: bold'
                return ''
            
            styled_df = df.style.map(style_gaps)
            st.dataframe(styled_df, height=300, use_container_width=True)
            
            if seq_len > 100:
                st.caption(f"Showing first 100 of {seq_len} positions. Full alignment visible in the visualization above.")
            
            # Gap Summary
            with st.expander("🔎 Gap Summary per Protein", expanded=False):
                for name in seq_keys:
                    gaps = gap_info[name]
                    gap_pct = (len(gaps) / seq_len) * 100
                    gap_str = _gaps_to_ranges_str(gaps)
                    if gaps:
                        st.markdown(f"**{name}** — {len(gaps)} gaps ({gap_pct:.1f}%): `{gap_str}`")
                    else:
                        st.markdown(f"**{name}** — No gaps ✅")
            
            # 3. Per-Protein Residue Selection
            st.markdown("### 🔍 Per-Protein Residue Selection")
            st.caption("Enter residue ranges for each protein (e.g. `1-20, 23-25, 30`). Leave blank to skip a protein.")
            
            if 'residue_selections' not in st.session_state:
                st.session_state.residue_selections = {}
            
            chain_letters = [chr(ord('A') + i) for i in range(len(seq_keys))]
            
            with st.form("residue_selection_form"):
                range_inputs = {}
                for i, name in enumerate(seq_keys):
                    chain = chain_letters[i]
                    gaps = gap_info[name]
                    existing = st.session_state.residue_selections.get(name, [])
                    existing_str = _selection_to_range_str(existing)
                    
                    col_name, col_input, col_gaps = st.columns([2, 3, 2])
                    with col_name:
                        st.markdown(f"**{name}**")
                        st.caption(f"Chain {chain}")
                    with col_input:
                        range_inputs[name] = st.text_input(
                            f"Residues for {name}",
                            value=existing_str,
                            placeholder="e.g. 1-20, 23-25, 30",
                            key=f"range_{name}",
                            label_visibility="collapsed"
                        )
                    with col_gaps:
                        if gaps:
                            st.caption(f"⚠️ Gaps: {_gaps_to_ranges_str(gaps[:10])}")
                        else:
                            st.caption("✅ No gaps")
                
                col_apply, col_clear = st.columns(2)
                with col_apply:
                    submitted = st.form_submit_button("✅ Apply All Selections", type="primary", use_container_width=True)
                with col_clear:
                    clear_submitted = st.form_submit_button("🗑️ Clear All", use_container_width=True)
            
            if submitted:
                new_selections = {}
                for name in seq_keys:
                    parsed = _parse_range_str(range_inputs.get(name, ""), max_len)
                    if parsed:
                        new_selections[name] = parsed
                st.session_state.residue_selections = new_selections
                chain_highlights = {}
                for i, name in enumerate(seq_keys):
                    chain = chain_letters[i]
                    if name in new_selections and new_selections[name]:
                        chain_highlights[chain] = new_selections[name]
                st.session_state.highlight_chains = chain_highlights
                st.rerun()
            
            if clear_submitted:
                st.session_state.residue_selections = {}
                st.session_state.highlight_chains = {}
                st.rerun()
            
            # Quick Actions
            st.markdown("**Quick Actions:**")
            qa_col1, qa_col2 = st.columns(2)
            with qa_col1:
                if st.button("🎯 Select All Non-Gap Residues", use_container_width=True):
                    all_selections = {}
                    chain_highlights = {}
                    for i, name in enumerate(seq_keys):
                        chain = chain_letters[i]
                        non_gap = [pos + 1 for pos, ch in enumerate(sequences[name]) if ch != '-']
                        all_selections[name] = non_gap
                        chain_highlights[chain] = non_gap
                    st.session_state.residue_selections = all_selections
                    st.session_state.highlight_chains = chain_highlights
                    st.rerun()
            with qa_col2:
                if st.button("🧬 Select Conserved Only (100% Identity)", use_container_width=True):
                    conserved_positions = []
                    for pos_idx in range(max_len):
                        residues_at_pos = [sequences[name][pos_idx] for name in seq_keys if pos_idx < len(sequences[name])]
                        if len(residues_at_pos) == len(seq_keys) and all(r == residues_at_pos[0] and r != '-' for r in residues_at_pos):
                            conserved_positions.append(pos_idx + 1)
                    all_selections = {}
                    chain_highlights = {}
                    for i, name in enumerate(seq_keys):
                        chain = chain_letters[i]
                        all_selections[name] = conserved_positions
                        chain_highlights[chain] = conserved_positions
                    st.session_state.residue_selections = all_selections
                    st.session_state.highlight_chains = chain_highlights
                    st.rerun()
            
            selections = st.session_state.get('residue_selections', {})
            if selections:
                st.markdown("---")
                st.markdown("#### 📋 Current Selection Summary")
                for i, name in enumerate(seq_keys):
                    chain = chain_letters[i]
                    sel = selections.get(name, [])
                    if sel:
                        st.success(f"**{name}** (Chain {chain}): {len(sel)} residues — `{_selection_to_range_str(sel)}`")
                    else:
                        st.caption(f"**{name}** (Chain {chain}): No selection")
        else:
            st.error("Failed to parse alignment file")
    else:
        st.warning("Sequence alignment file not found")
