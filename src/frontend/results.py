import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from src.backend.structure_viewer import show_structure_in_streamlit, show_ligand_view_in_streamlit
from src.backend.notebook_exporter import NotebookExporter

def render_learning_card(tab_name):
    """Render a context-aware learning card for Guided Mode."""
    if not st.session_state.get('guided_mode', False):
        return

    content = {
        "Summary": {
            "title": "🎓 Learning: Understanding Alignment Quality",
            "body": """
            - **RMSD (Root Mean Square Deviation)**: Measures the average distance between atoms. Lower is better (0.0 is perfect).
            - **Alignment Length**: How many residues were successfully matched.
            - **Sequence Identity**: % of exact amino acid matches. High identity often means similar function.
            """
        },
        "Sequence": {
            "title": "🎓 Learning: Sequence Conservation",
            "body": """
            - **Conservation Score (0-9)**:
                - **9 (Star)**: Identity. The same amino acid is present in all structures. Crucial for function.
                - **0-4**: Variable regions. These parts evolve rapidly or are less important.
            - **Tip**: Click on a residue in the table to highlight it in the 3D viewer!
            """
        },
        "Structure": {
            "title": "🎓 Learning: Structural Superposition",
            "body": """
            - **Superposition**: Rotates proteins to overlap them as best as possible.
            - **Visual Styles**:
                - **Cartoon**: Best for seeing helices and sheets.
                - **Surface**: Good for finding pockets.
            - **Controls**: Mouse Wheel to Zoom, Drag to Rotate.
            """
        },
        "Ligands": {
            "title": "🎓 Learning: Ligand Interactions",
            "body": """
            - **Ligands**: Small molecules (drugs, cofactors) bound to the protein.
            - **Interaction Similarity**:
                - **1.0**: Identical binding pockets.
                - **0.0**: Completely different binding pockets.
            - **Tip**: Use 'Pocket Comparison' to see how different proteins bind the same (or different) ligands.
            """
        },
        "Tree": {
            "title": "🎓 Learning: Phylogenetic Tree",
            "body": """
            - **Clustering**: Groups proteins by structural similarity.
            - **Branch Length**: Longer branches mean more structural difference.
            - **Clusters**: Items in the same color group are likely a sub-family.
            """
        }
    }

    if tab_name in content:
        card = content[tab_name]
        with st.container():
            st.info(f"**{card['title']}**\n\n{card['body']}")
            st.divider()

def render_help_expander(topic):
    """Render educational help expanders."""
    helps = {
        "rmsd": {
            "title": "❓ What is RMSD & How to read this?",
            "content": """
                ### **1. What is RMSD?**
                **RMSD (Root Mean Square Deviation)** is the standard measure of structural difference between proteins. It calculates the average distance between matching atoms in two superimposed structures.
                *   **Unit**: Angstroms (Å). 1 Å = 0.1 nanometers.
                
                ### **2. How to read the Heatmap:**
                This grid compares every protein against every other protein.
                *   **🟦 Blue (Low RMSD, e.g., < 2.0 Å)**: The structures are **very similar**. They likely share the same function and evolutionary origin.
                *   **🟥 Red (High RMSD, e.g., > 2.0 Å)**: The structures are **different**. They may have diverged significantly or look completely different.
                *   **Diagonal**: Always 0.00, because a protein compared to itself has 0 difference.
            """
        },
        "rmsf": {
            "title": "❓ What is RMSF & How to read this?",
            "content": """
                ### **1. What is RMSF?**
                **RMSF (Root Mean Square Fluctuation)** measures how much each individual amino acid moves around in space.
                *   **Rigid**: Parts that don't move much (the core structure).
                *   **Flexible**: Parts that wobble or flap around (loops, tails).
                
                ### **2. How to read the Chart:**
                *   **X-Axis**: The sequence of amino acids (Position 1, 2, 3...).
                *   **Y-Axis (RMSF Å)**: How much that position moved. Higher = More Flexible.
                *   **Peaks 📈**: Identify flexible loops or disordered regions. These are often where ligands bind or interactions happen!
                *   **Valleys 📉**: The stable core of the protein.
            """
        },
        "tree": {
            "title": "❓ What is this Tree & How to read it?",
            "content": """
                ### **1. What is a Structural Tree?**
                Unlike traditional evolutionary trees based on DNA sequences, this tree groups proteins based on their **3D shape similarity** (Structural Phylogeny).
                *   **Clustering**: Proteins on the same branch are "structural siblings." They look very similar in 3D space.
                *   **Distance**: The horizontal length of the branches represents the RMSD distance. **Longer branches = distinct structures**.
                
                ### **2. Why use UPGMA?**
                UPGMA (Unweighted Pair Group Method with Arithmetic Mean) is a simple clustering algorithm that assumes a constant rate of evolution. It's great for visualizing hierarchical relationships in data.
            """
        },
        "clusters": {
            "title": "❓ What are Clusters & How to read this?",
            "content": """
                ### **1. What is Structural Clustering?**
                Clustering is a way to group proteins that are "structurally similar" into families. We use **Hierarchical Clustering (UPGMA)** based on the RMSD values.
                
                ### **2. The RMSD Threshold:**
                This is the "cutoff" distance for forming a group. 
                *   **Low Threshold (e.g., 1.5 Å)**: Only very similar proteins (nearly identical folds) will be grouped together.
                *   **High Threshold (e.g., 5.0 Å)**: Even distantly related proteins (sharing only broad structural features) will be put into the same cluster.
                
                ### **3. Why use this?**
                It helps identify sub-families within a large dataset, making it easier to see which proteins might share specific functionalities or binding properties.
            """
        },
        "superposition": {
            "title": "❓ What is Superposition & Interpretation Guide",
            "content": """
                ### **1. What is Superposition?**
                Superposition is the process of attempting to **overlap** multiple protein structures on top of each other to find the "best fit." This allows us to see exactly where they differ.
                *   **Aligned Regions**: Parts of the proteins that overlap perfectly usually have the same function.
                *   **Divergent Regions**: Parts that stick out or don't overlap are variable regions (often loops or surface areas).

                ### **2. Visualization Styles:**
                *   **Cartoon**: Simplifies the protein into ribbons (helices) and arrows (sheets). Best for seeing the overall "fold" or shape.
                *   **Stick**: Shows the bonds between atoms. Useful for seeing side-chains.
                *   **Surface**: Shows the outer "skin" of the molecule. Good for seeing pockets.
            """
        },
        "ligands": {
            "title": "❓ What are Ligands & How to read this?",
            "content": """
                ### **1. What is a Ligand?**
                A **ligand** is a small molecule (like a drug, hormone, or vitamin) that binds to a specific site on a protein to trigger a function or inhibit it. Think of it as a **key** fitting into a **lock** (the protein).
                
                ### **2. How to use this tool:**
                1.  **Select a Protein**: Choose one of your aligned structures from the dropdown.
                2.  **Select a Ligand**: Pick the specific small molecule found in that structure.
                3.  **Analyze Interactions**: Click the button to calculate which parts of the protein are "touching" the ligand.
                
                ### **3. Understanding the Results:**
                -   **3D View (Right)**: Shows the ligand (colorful sticks) inside its binding pocket.
                    -   The **Green/Blue/Red residues** represent the parts of the protein holding the ligand in place.
                -   **Interaction Table (Bottom Right)**:
                    -   **Residue**: The specific amino acid in the protein chain.
                    -   **Distance (Å)**: How close it is to the ligand. **< 3.5 Å** usually means a strong chemical bond.
                    -   **Type**: The kind of connection (e.g., *Hydrogen Bond* = strong, sticky; *Hydrophobic* = oily/greasy interaction).
            """
        }
    }
    if topic in helps:
        with st.expander(helps[topic]["title"], expanded=False):
            st.markdown(helps[topic]["content"])


def render_rmsd_tab(results):
    """Render the RMSD Analysis tab."""
    st.subheader("📊 RMSD & Alignment Quality")
    render_learning_card("Summary")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("RMSD Heatmap")
        render_help_expander("rmsd")
        
        if results.get('heatmap_fig'):
             st.plotly_chart(results['heatmap_fig'], use_container_width=True)
        elif results['heatmap_path'].exists():
            st.image(str(results['heatmap_path']), use_container_width=True)
    
    with col2:
        st.subheader("Statistics")
        stats = results['stats']
        st.metric("Mean RMSD", f"{stats['mean_rmsd']:.2f} Å")
        st.metric("Median RMSD", f"{stats['median_rmsd']:.2f} Å")
        st.metric("Min RMSD", f"{stats['min_rmsd']:.2f} Å")
        st.metric("Max RMSD", f"{stats['max_rmsd']:.2f} Å")
        st.metric("Std Dev", f"{stats['std_rmsd']:.2f} Å")
    
    st.subheader("RMSD Matrix")
    st.dataframe(results['rmsd_df'].style.background_gradient(cmap='RdYlBu_r'))
    
    st.divider()
    st.subheader("Residue-Level Flexibility (RMSF)")
    render_help_expander("rmsf")
    
    if results.get('rmsf_values'):
        rmsf_data = pd.DataFrame({
            'Residue Position': range(1, len(results['rmsf_values']) + 1),
            'RMSF (Å)': results['rmsf_values']
        })
        
        fig = px.line(
            rmsf_data,
            x='Residue Position',
            y='RMSF (Å)',
            title='Structural Fluctuation per Position',
            template='plotly_white'
        )
        fig.update_traces(line_color='#2196F3', line_width=2)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Residue RMSF data not available")

def render_phylo_tree_tab(results):
    """Render the Phylogenetic Tree tab."""
    st.subheader("🌳 Phylogenetic Tree (UPGMA)")
    render_learning_card("Tree")
    render_help_expander("tree")
        
    if results.get('tree_fig'):
        st.plotly_chart(results['tree_fig'], use_container_width=True)
    elif results.get('tree_path') and results['tree_path'].exists():
        st.image(str(results['tree_path']), use_container_width=True)
    else:
        st.warning("Phylogenetic tree not available")


def render_3d_viewer_tab(results):
    """Render the 3D Visualization tab."""
    st.subheader("3D Structural Superposition")
    render_learning_card("Structure")
    render_help_expander("superposition")
                
    st.info("💡 Explore different representations of the aligned structures. Rotate and zoom to investigate.")
    
    if results.get('alignment_pdb') and results['alignment_pdb'].exists():
        # Lazy Loading Logic
        if "show_3d_viewer" not in st.session_state:
            st.session_state.show_3d_viewer = False
            
        if not st.session_state.show_3d_viewer:
             st.info("⚠️ 3D visualization requires WebGL and may slow down the app.")
             if st.button("🚀 Initialize 3D Viewers", type="primary"):
                 st.session_state.show_3d_viewer = True
                 st.rerun()
        else:
            if st.button("❌ Close Viewers"):
                st.session_state.show_3d_viewer = False
                st.rerun()
                
            try:
                pdb_path = results['alignment_pdb']
                col1, col2 = st.columns(2)
                hl_chains = st.session_state.get('highlight_chains', {})
                with col1:
                    st.markdown("**Cartoon (Secondary Structure)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='cartoon', key='view_cartoon', highlight_residues=hl_chains)
                with col2:
                    st.markdown("**Sphere (Spacefill)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='sphere', key='view_sphere', highlight_residues=hl_chains)
                    
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("**Stick (Bonds & Atoms)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='stick', key='view_stick', highlight_residues=hl_chains)
                with col4:
                    st.markdown("**Line/Trace (Backbone)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='line', key='view_line', highlight_residues=hl_chains)
                
                st.caption("""
                **Controls:**
                - **Left click + drag**: Rotate | **Right click + drag**: Zoom | **Scroll**: Zoom in/out
                - Each structure is colored differently for easy identification
                """)
                
                # Show active highlights info
                if hl_chains:
                    chain_summary = ", ".join([f"Chain {c}: {len(r)} residues" for c, r in hl_chains.items()])
                    st.info(f"🔥 Highlighting: {chain_summary}")
                    
            except Exception as e:
                st.error(f"Failed to load 3D viewer: {str(e)}")
    else:
        st.warning("3D visualization not available")

def render_ligand_tab(results):
    """Render the Ligand & Interaction Analysis tab."""
    st.subheader("💊 Ligand & Interaction Analysis")
    render_learning_card("Ligands")
    render_help_expander("ligands")
    
    tab_single, tab_compare = st.tabs(["🧪 Single Ligand Analysis", "⚔️ Pocket Comparison"])
    
    with tab_single:
        # Layout: Selections on Top
        sel_col1, sel_col2 = st.columns(2)
        
        with sel_col1:
            selected_pdb_ligand = st.selectbox("Select Protein Structure", st.session_state.pdb_ids, key="ligand_pdb_select")
        
        result_dir = results['result_dir']
        
        # PDB Finding Logic
        pdb_path = None
        # precise match first
        possible_names = [
            f"{selected_pdb_ligand}.pdb",
            f"{selected_pdb_ligand.lower()}.pdb",
            f"{selected_pdb_ligand.upper()}.pdb"
        ]
        
        for name in possible_names:
            p = result_dir / name
            if p.exists():
                pdb_path = p
                break
        
        # Fuzzy match if exact fails
        if not pdb_path:
            matches = list(result_dir.glob(f"*{selected_pdb_ligand}*.pdb"))
            if matches: 
                pdb_path = matches[0]
                
        if pdb_path:
            ligands = st.session_state.ligand_analyzer.get_ligands(pdb_path)
            if not ligands:
                st.info("No ligands found in this structure.")
            else:
                with sel_col2:
                    st.success(f"Found {len(ligands)} ligands")
                    ligand_options = {f"{l['name']} ({l['id']})": l for l in ligands}
                    selected_ligand_name = st.selectbox("Select Ligand", list(ligand_options.keys()))
                    selected_ligand = ligand_options[selected_ligand_name]
                    
                    if st.button("Analyze Interactions", type="primary", use_container_width=True):
                        interactions = st.session_state.ligand_analyzer.calculate_interactions(pdb_path, selected_ligand['id'])
                        st.session_state.current_interactions = interactions
                        st.session_state.current_ligand_pdb = pdb_path
                        
                        # Store in global history for comparison
                        entry = interactions.copy()
                        entry['pdb_path'] = str(pdb_path) # Store as string for serialization safety
                        entry['pdb_id'] = selected_pdb_ligand # Keep track of ID
                        
                        if 'pocket_history' not in st.session_state: st.session_state.pocket_history = []
                        
                        # Add or Update
                        # Filter out existing entry for this ligand
                        st.session_state.pocket_history = [x for x in st.session_state.pocket_history if x['ligand'] != interactions['ligand']]
                        st.session_state.pocket_history.append(entry)
                    
        else:
            st.error(f"PDB file not found for {selected_pdb_ligand}")

        st.divider()

        # Results Section (Below)
        if 'current_interactions' in st.session_state:
            interactions = st.session_state.current_interactions
            pdb_path = st.session_state.current_ligand_pdb
            
            if 'error' in interactions:
                st.error(interactions['error'])
            else:
                st.markdown(f"### Binding Site: **{interactions['ligand']}**")
                
                # Layout: 3D View (Left) | Table (Right)
                res_col1, res_col2 = st.columns([1, 1])
                
                with res_col1:
                    # Render 3D Ligand View
                    show_ligand_view_in_streamlit(pdb_path, interactions, width=500, height=450, key="ligand_3d")
                
                with res_col2:
                    st.markdown("#### Interacting Residues (< 5Å)")
                    if interactions['interactions']:
                        df_int = pd.DataFrame(interactions['interactions'])
                        st.dataframe(
                            df_int[['residue', 'chain', 'resi', 'distance', 'type']].style.format({"distance": "{:.2f}"}), 
                            use_container_width=True, 
                            height=400
                        )
                    else:
                        st.info("No residues found within cutoff distance.")

    # --- TAB 2: POCKET COMPARISON ---
    with tab_compare:
        st.caption("Compare the environments of analyzed ligands. (Analyze ligands in the Single tab first to add them here).")
        
        history = st.session_state.get('pocket_history', [])
        
        if len(history) < 2:
             st.warning("⚠️ Analyze at least 2 different ligands in the 'Single Ligand Analysis' tab to enable comparison.")
        else:
            # 1. Similarity Matrix
            st.subheader("Chemical Environment Similarity Matrix")
            st.caption("Jaccard Index based on shared residue types in the binding pocket.")
            
            sim_matrix = st.session_state.ligand_analyzer.calculate_interaction_similarity(history)
            st.dataframe(sim_matrix.style.background_gradient(cmap="Greens", vmin=0, vmax=1))
            
            st.divider()
            
            # 2. Side-by-Side View
            st.subheader("⚔️ Side-by-Side Pocket View")
            
            # Helper to generate unique keys for widgets
            
            c_sel1, c_sel2 = st.columns(2)
            options = [h['ligand'] for h in history]
            
            l1_id = c_sel1.selectbox("Pocket 1", options, index=0, key="cmp_p1")
            l2_id = c_sel2.selectbox("Pocket 2", options, index=1 if len(options)>1 else 0, key="cmp_p2")
            
            if l1_id and l2_id:
                # Retrieve data
                d1 = next(h for h in history if h['ligand'] == l1_id)
                d2 = next(h for h in history if h['ligand'] == l2_id)
                
                # Visuals
                row1_c1, row1_c2 = st.columns(2)
                with row1_c1:
                    show_ligand_view_in_streamlit(Path(d1['pdb_path']), d1, width=350, height=350, key="ligand_view_1")
                with row1_c2:
                    show_ligand_view_in_streamlit(Path(d2['pdb_path']), d2, width=350, height=350, key="ligand_view_2")
                    
                # Shared Residues
                st.subheader("Comparison Details")
                
                # Extract residue types
                set1 = set([x['residue'] for x in d1['interactions']])
                set2 = set([x['residue'] for x in d2['interactions']])
                
                shared = set1.intersection(set2)
                unique1 = set1 - set2
                unique2 = set2 - set1
                
                delta_col1, delta_col2, delta_col3 = st.columns(3)
                delta_col1.metric("Shared Residue Types", len(shared), help=f"{', '.join(shared)}")
                delta_col2.metric(f"Unique to {l1_id}", len(unique1), help=f"{', '.join(unique1)}")
                delta_col3.metric(f"Unique to {l2_id}", len(unique2), help=f"{', '.join(unique2)}")


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


def _find_gaps(sequence):
    """Find gap positions (1-indexed) in an alignment sequence."""
    gaps = []
    for i, ch in enumerate(sequence):
        if ch == '-':
            gaps.append(i + 1)  # 1-indexed
    return gaps


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
            # Base header/footer ~60px, per-sequence row ~30px
            n_seqs = len(sequences)
            viz_height = min(600, max(150, 60 + (n_seqs * 30)))
            st.components.v1.html(html_view, height=viz_height, scrolling=True)
            
            # 2. Alignment Table with Gap Indicators
            st.markdown("### 📊 Alignment Table")
            
            seq_keys = list(sequences.keys())
            seq_len = len(sequences[seq_keys[0]])
            
            # Build alignment DataFrame — rows = positions, cols = proteins
            import pandas as pd
            table_data = {}
            gap_info = {}  # {protein_name: [gap_positions]}
            max_len = max(len(sequences[name]) for name in seq_keys)
            for name in seq_keys:
                seq = sequences[name]
                residues = []
                protein_gaps = []
                for i, ch in enumerate(seq):
                    pos = i + 1
                    if ch == '-':
                        residues.append('—')  # em dash for visual clarity
                        protein_gaps.append(pos)
                    else:
                        residues.append(ch)
                # Pad shorter sequences if needed
                while len(residues) < max_len:
                    residues.append('—')
                    protein_gaps.append(len(residues))
                table_data[name] = residues
                gap_info[name] = protein_gaps
            
            # Show a compact summary of positions (first 100 to avoid overwhelming)
            display_len = min(max_len, 100)
            # Truncate data to display_len for the DataFrame
            display_data = {name: vals[:display_len] for name, vals in table_data.items()}
            df = pd.DataFrame(display_data, index=range(1, display_len + 1))
            df.index.name = "Pos"
            
            # Style: highlight gaps in grey
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
            
            # Initialize selection state
            if 'residue_selections' not in st.session_state:
                st.session_state.residue_selections = {}
            
            # Get chain mapping: protein order → chain letter (A, B, C, ...)
            chain_letters = [chr(ord('A') + i) for i in range(len(seq_keys))]
            
            # Form to batch all inputs — single rerun on submit
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
                
                # Submit button
                col_apply, col_clear = st.columns(2)
                with col_apply:
                    submitted = st.form_submit_button("✅ Apply All Selections", type="primary", use_container_width=True)
                with col_clear:
                    clear_submitted = st.form_submit_button("🗑️ Clear All", use_container_width=True)
            
            # Handle form submission
            if submitted:
                new_selections = {}
                for name in seq_keys:
                    parsed = _parse_range_str(range_inputs.get(name, ""), max_len)
                    if parsed:
                        new_selections[name] = parsed
                st.session_state.residue_selections = new_selections
                # Build per-chain highlight dict for 3D viewer
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
            
            # Quick Actions (outside form)
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
            
            # Selection Summary
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

def render_clusters_tab(results):
    """Render the Structural Clusters tab."""
    st.subheader("🔍 Structural Clusters")
    render_help_expander("clusters")
    
    rmsd_df = results.get('rmsd_df')
    if rmsd_df is None:
        st.warning("RMSD data not available for clustering.")
        return

    # User Interactive Threshold
    col1, col2 = st.columns([1, 2])
    with col1:
        threshold = st.slider(
            "RMSD Threshold (Å)", 
            min_value=0.1, 
            max_value=10.0, 
            value=3.0, 
            step=0.1,
            help="Structures with RMSD lower than this 'distance' will be grouped together."
        )
    
    # Re-calculate clusters based on interactive threshold
    clusters = st.session_state.rmsd_analyzer.identify_clusters(rmsd_df, threshold=threshold)
    
    if clusters:
        st.markdown(f"Found **{len(clusters)}** distinct structural families at **{threshold} Å** cutoff.")
        
        for cid, members in clusters.items():
            avg_rmsd = 0.0
            if len(members) > 1:
                # Calculate internal average RMSD (homogeneity of cluster)
                subset = rmsd_df.loc[members, members]
                avg_rmsd = subset.values[np.triu_indices(len(members), k=1)].mean()
            
            with st.expander(f"📁 Cluster {cid} ({len(members)} members, Avg RMSD: {avg_rmsd:.2f} Å)", expanded=True):
                # Show members in a nice clean list or table
                member_data = []
                for m in members:
                    # Get metadata if available
                    title = st.session_state.metadata.get(m, {}).get('title', 'Unknown Title') if hasattr(st.session_state, 'metadata') else 'N/A'
                    member_data.append({"PDB ID": m, "Description": title})
                
                st.table(pd.DataFrame(member_data))
    else:
        st.info("No clusters identified with current settings.")

def render_downloads_tab(results):
    """Render the Data Downloads tab."""
    st.subheader("Data Downloads")
    
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.markdown("### 📄 Analysis Report")
        st.write("Customize your report:")
        
        # Report Configuration
        report_sections = []
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox("Summary & Stats", value=True): report_sections.append("summary")
            if st.checkbox("Key Findings", value=True): report_sections.append("insights")
            if st.checkbox("RMSD Heatmap", value=True): report_sections.append("heatmap")
        with c2:
            if st.checkbox("Phylogenetic Tree", value=True): report_sections.append("tree")
            if st.checkbox("RMSD Matrix", value=True): report_sections.append("matrix")

        c_pdf, c_html = st.columns(2)
        
        with c_pdf:
            if st.button("Generate PDF Report", help="Create a comprehensive PDF report", key="btn_gen_report", use_container_width=True):
                with st.spinner("Generating PDF..."):
                    try:
                        report_path = st.session_state.report_generator.generate_report(
                            results, 
                            st.session_state.pdb_ids,
                            sections=report_sections
                        )
                        st.success(f"PDF Ready: {report_path.name}")
                        with open(report_path, "rb") as f:
                            st.download_button("⬇️ Download PDF", f, file_name=report_path.name, mime="application/pdf", use_container_width=True)
                    except Exception as e:
                        st.error(f"Failed to generate PDF: {e}")

        with c_html:
            if st.button("Generate Lab Notebook", help="Create an interactive HTML notebook", key="btn_gen_html", use_container_width=True):
                 with st.spinner("Building interactive notebook..."):
                    try:
                        exporter = NotebookExporter()
                        # Pass insights if available
                        insights = st.session_state.get('insights', [])
                        nb_path = exporter.generate_notebook(results, insights)
                        
                        if nb_path:
                            st.success(f"Notebook Ready!")
                            with open(nb_path, "rb") as f:
                                st.download_button("⬇️ Download HTML Notebook", f, file_name="lab_notebook.html", mime="text/html", use_container_width=True)
                        else:
                            st.error("Failed to generate notebook.")
                    except Exception as e:
                         st.error(f"Error: {str(e)}")
    
    with col_d2:
        st.markdown("### 📦 Full Project Bundle")
        st.write("Download all inputs, results, and raw data.")
        
        # Zip Logic
        import shutil
        result_dir = results['result_dir']
        zip_path = result_dir.parent / f"{result_dir.name}.zip"
        
        if st.button("Prepare Zip Bundle", key="btn_zip"):
             with st.spinner("Compressing files..."):
                shutil.make_archive(str(result_dir), 'zip', result_dir)
                st.success("Bundle ready!")
                
        if zip_path.exists():
            with open(zip_path, "rb") as f:
                st.download_button(
                    "⬇️ Download All Files (ZIP)", 
                    f, 
                    file_name=f"mustang_analysis_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip"
                )
    
    st.divider()
    st.markdown("### 📂 Raw Data")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 RMSD Matrix (CSV)", results['rmsd_df'].to_csv(), file_name="rmsd_matrix.csv", mime="text/csv", use_container_width=True)
        if results['heatmap_path'].exists():
            with open(results['heatmap_path'], 'rb') as f:
                st.download_button("📥 RMSD Heatmap (PNG)", f.read(), file_name="rmsd_heatmap.png", mime="image/png", use_container_width=True)
    with col2:
        if results.get('tree_path') and results['tree_path'].exists():
            with open(results['tree_path'], 'rb') as f:
                st.download_button("📥 Phylogenetic Tree (PNG)", f.read(), file_name="phylogenetic_tree.png", mime="image/png", use_container_width=True)
        if results.get('newick_path') and results['newick_path'].exists():
            with open(results['newick_path'], 'r') as f:
                st.download_button("📥 Tree Format (Newick)", f.read(), file_name="tree.newick", mime="text/plain", use_container_width=True)


def display_results():
    """Display analysis results."""
    st.divider()
    st.header("📊 Results")
    results = st.session_state.results
    
    # --- AUTOMATED INSIGHTS SECTION ---
    st.subheader("💡 Key Findings")
    
    # Initialize generator if needed
    if 'insights' not in st.session_state:
        from src.backend.insights import InsightsGenerator
        # Assuming config is available in session state or passing empty dict for now as it's not strictly used yet
        generator = InsightsGenerator({}) 
        st.session_state.insights = generator.generate_insights(results)
    
    if st.session_state.insights:
        for insight in st.session_state.insights:
            st.markdown(insight)
    else:
        st.info("No specific insights generated for this dataset.")
    
    st.divider()
    
    # Initialize highlight state if not present
    if 'highlighted_residues' not in st.session_state:
        st.session_state.highlighted_residues = []
    
    # Define function map for render loop
    # Using specific names for render functions for clarity
    
    tab_list = [
        ("� Summary", render_rmsd_tab),
        ("🧬 Sequence", render_sequences_tab),
        ("nm Structure", render_3d_viewer_tab),
        ("💊 Ligands", render_ligand_tab),
        ("🌳 Tree", render_phylo_tree_tab),
        ("🔍 Clusters", render_clusters_tab),
        ("📁 Downloads", render_downloads_tab)
    ]
    
    tabs = st.tabs([t[0] for t in tab_list])
    for tab, (_, render_func) in zip(tabs, tab_list):
        with tab:
            render_func(results)
    
    st.divider()
    if 'result_dir' in results:
        st.info(f"📂 All results saved to: `{results['result_dir']}`")
