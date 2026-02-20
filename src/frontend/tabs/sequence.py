import streamlit as st
import pandas as pd
from typing import List, Dict, Any
from src.frontend.tabs.common import render_learning_card

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
    parts = range_str.split(',')
    for part in parts:
        part = part.strip()
        if not part: continue
        
        if '-' in part:
            try:
                start_str, end_str = part.split('-')
                start = max(1, int(start_str))
                end = min(max_val, int(end_str))
                if start <= end:
                    for i in range(start, end + 1):
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
    return sorted(list(result))

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
    if not gaps: return "None"
    
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

def render_sequences_tab(results: Dict[str, Any]) -> None:
    """
    Render the Sequence Analysis tab.
    
    Args:
        results: The results dictionary containing sequence alignment info.
    """
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
            st.markdown("#### Alignment Details & Gaps")
            table_data = []
            for name, seq in sequences.items():
                gaps = [i+1 for i, char in enumerate(seq) if char == '-']
                raw_seq = seq.replace('-', '')
                table_data.append({
                    "PDB ID": name,
                    "Total Length": len(raw_seq),
                    "Gap Count": len(gaps),
                    "Gap Positions": _gaps_to_ranges_str(gaps)
                })
            st.table(pd.DataFrame(table_data))
            
            # 3. Conserved Residue Highlighting
            st.divider()
            st.markdown("#### 🎯 Selective Extraction & Pocket Analysis")
            st.caption("Identify 100% conserved residues and highlight them in the 3D viewer.")
            
            # Find 100% conserved columns (using conservation from sequence_viewer)
            conserved_cols = [i for i, val in enumerate(conservation) if val == 1.0]
            
            if conserved_cols:
                n_total = len(conservation)
                st.success(f"Found {len(conserved_cols)} strictly conserved residues ({(len(conserved_cols)/n_total)*100:.1f}% of alignment)")
                
                sel_col1, sel_col2 = st.columns(2)
                
                with sel_col1:
                    st.write("**Selection Strategy**")
                    strategy = st.radio("Highlight Option:", 
                                      ["All Strictly Conserved", "Manual Residue Selection"],
                                      horizontal=True)
                
                with sel_col2:
                    if strategy == "Manual Residue Selection":
                        user_input = st.text_input("Enter residue indices (e.g. 1-10, 25, 30-45)", "")
                        selected_indices = _parse_range_str(user_input, n_total)
                    else:
                        selected_indices = conserved_cols
                
                if selected_indices:
                    st.info(f"Selected: {_selection_to_range_str(selected_indices)}")
                    
                    if st.button("✨ Project Selection to 3D Viewer", use_container_width=True, type="primary"):
                        # Map alignment indices to residues in structures
                        # This maps alignment index (0-based) to PDB residue numbers for EACH structure in current alignment
                        mapping = {}
                        for pid, seq in sequences.items():
                            res_nums = []
                            current_res = 1 # Assuming PDB starts at 1, simplified
                            for i, char in enumerate(seq):
                                if char != '-':
                                    if (i + 1) in selected_indices: 
                                        res_nums.append(current_res)
                                    current_res += 1
                            mapping[pid] = res_nums
                        
                        st.session_state.active_3d_selection = mapping
                        st.session_state.show_3d_viewer = True
                        st.success("Selection transferred. Switch to '3D Visualization' tab to view results.")
            else:
                st.warning("No strictly conserved residues found in this alignment.")
    else:
        st.warning("Alignment file (AFASTA) not found. Sequence tab unavailable.")
