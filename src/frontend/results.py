import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from src.backend.structure_viewer import show_structure_in_streamlit, show_ligand_view_in_streamlit

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
    st.subheader("Phylogenetic Tree (UPGMA)")
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
    render_help_expander("superposition")
        
    st.info("💡 Explore different representations of the aligned structures. Rotate and zoom to investigate.")
    
    if results.get('alignment_pdb') and results['alignment_pdb'].exists():
        try:
            pdb_path = results['alignment_pdb']
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Cartoon (Secondary Structure)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='cartoon', key='view_cartoon', highlight_residues=st.session_state.get('highlighted_residues', []))
            with col2:
                st.markdown("**Sphere (Spacefill)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='sphere', key='view_sphere', highlight_residues=st.session_state.get('highlighted_residues', []))
                
            col3, col4 = st.columns(2)
            with col3:
                st.markdown("**Stick (Bonds & Atoms)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='stick', key='view_stick', highlight_residues=st.session_state.get('highlighted_residues', []))
            with col4:
                st.markdown("**Line/Trace (Backbone)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='line', key='view_line', highlight_residues=st.session_state.get('highlighted_residues', []))
            
            st.caption("""
            **Controls:**
            - **Left click + drag**: Rotate | **Right click + drag**: Zoom | **Scroll**: Zoom in/out
            - Each structure is colored differently for easy identification
            """)
            
            # Show active highlights info
            hl = st.session_state.get('highlighted_residues', [])
            if hl:
                st.info(f"🔥 Highlighting {len(hl)} residues: {hl[:10]}{'...' if len(hl)>10 else ''} from Sequence Tab.")
                
        except Exception as e:
            st.error(f"Failed to load 3D viewer: {str(e)}")
    else:
        st.warning("3D visualization not available")

def render_ligand_tab(results):
    """Render the Ligand & Interaction Analysis tab."""
    st.subheader("💊 Ligand & Interaction Analysis")
    render_help_expander("ligands")
    
    # Tab Layout for Ligands
    tab_single, tab_compare = st.tabs(["🧪 Single Ligand Analysis", "⚔️ Pocket Comparison"])
    
    # --- TAB 1: SINGLE LIGAND ---
    with tab_single:
        col1, col2 = st.columns([1, 2])
        with col1:
            selected_pdb_ligand = st.selectbox("Select Protein Structure", st.session_state.pdb_ids, key="ligand_pdb_select")
            result_dir = results['result_dir']
            
            # PDB Finding Logic
            pdb_path = None
            for suffix in ["", ".lower()", ".upper()"]:
                p = result_dir / f"{selected_pdb_ligand}{suffix}.pdb"
                if p.exists():
                    pdb_path = p
                    break
            
            if not pdb_path:
                matches = list(result_dir.glob(f"*{selected_pdb_ligand}*.pdb"))
                if matches: pdb_path = matches[0]
            
            if pdb_path:
                ligands = st.session_state.ligand_analyzer.get_ligands(pdb_path)
                if not ligands:
                    st.info("No ligands found in this structure.")
                else:
                    st.success(f"Found {len(ligands)} ligands")
                    ligand_options = {f"{l['name']} ({l['id']})": l for l in ligands}
                    selected_ligand_name = st.selectbox("Select Ligand", list(ligand_options.keys()))
                    selected_ligand = ligand_options[selected_ligand_name]
                    
                    if st.button("Analyze Interactions"):
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

        with col2:
            if 'current_interactions' in st.session_state:
                interactions = st.session_state.current_interactions
                pdb_path = st.session_state.current_ligand_pdb
                
                if 'error' in interactions:
                    st.error(interactions['error'])
                else:
                    st.markdown(f"### Binding Site: **{interactions['ligand']}**")
                    show_ligand_view_in_streamlit(pdb_path, interactions, width=700, height=500, key="ligand_3d")
                    
                    st.markdown("#### Interacting Residues (< 5Å)")
                    if interactions['interactions']:
                        df_int = pd.DataFrame(interactions['interactions'])
                        st.dataframe(df_int[['residue', 'chain', 'resi', 'distance', 'type']], use_container_width=True)
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



def render_sequences_tab(results):
    """Render the Multiple Sequence Alignment tab."""
    st.subheader("Multiple Sequence Alignment")
    st.info("🧬 Color code: Red = 100% Identity, Yellow = High Similarity (>70%)")
    
    if results.get('alignment_afasta') and results['alignment_afasta'].exists():
        sequences = st.session_state.sequence_viewer.parse_afasta(results['alignment_afasta'])
        if sequences:
            # 1. Visualization
            conservation = st.session_state.sequence_viewer.calculate_conservation(sequences)
            html_view = st.session_state.sequence_viewer.generate_html(sequences, conservation)
            st.components.v1.html(html_view, height=400, scrolling=True)
            
            st.divider()
            
            # 2. Interactive Selection (Table of Residues)
            st.markdown("### 🔍 Interactive Residue Selection")
            st.caption("Select residues in the table below to highlight them in the 3D Structure Viewer.")
            
            col_sel1, col_sel2 = st.columns([3, 1])
            with col_sel1:
                # Prepare Data for Table
                seq_keys = list(sequences.keys())
                seq_len = len(sequences[seq_keys[0]])
                
                # Helper to build dataframe (cached/optimized)
                @st.cache_data
                def build_sequence_df(sequences, conservation):
                    data = []
                    keys = list(sequences.keys())
                    length = len(sequences[keys[0]])
                    for i in range(length):
                        row = {
                            "Position": i + 1,
                            "Conservation": conservation[i] if i < len(conservation) else 0.0,
                        }
                        for k in keys:
                            row[k] = sequences[k][i]
                        data.append(row)
                    return pd.DataFrame(data)

                base_df = build_sequence_df(sequences, conservation).copy()
                
                # Apply current selection state to DF
                current_highlights = set(st.session_state.get('highlighted_residues', []))
                base_df.insert(0, "Select", base_df['Position'].apply(lambda x: x in current_highlights))
                
                # Configure Columns
                column_config = {
                    "Select": st.column_config.CheckboxColumn("Highlight", default=False),
                    "Position": st.column_config.NumberColumn("Residue", format="%d"),
                    "Conservation": st.column_config.ProgressColumn("Conservation", format="%.2f", min_value=0, max_value=1),
                }
                
                # Render Editor
                edited_df = st.data_editor(
                    base_df,
                    column_config=column_config,
                    disabled=[c for c in base_df.columns if c != "Select"],
                    hide_index=True,
                    use_container_width=True,
                    height=400,
                    key="residue_table_editor"
                )
                
                # Sync State
                selected_rows = edited_df[edited_df.Select]
                new_selection = sorted(selected_rows['Position'].tolist())
                
                if new_selection != sorted(list(current_highlights)):
                    st.session_state.highlighted_residues = new_selection
                    st.rerun()

            with col_sel2:
                # Quick Range Input Helper
                st.markdown("**Quick Add Range**")
                range_input = st.text_input("e.g. 10-20", key="range_adder", help="Add a range of residues to the selection.")
                if st.button("Add Range"):
                    try:
                        if '-' in range_input:
                            s, e = map(int, range_input.split('-'))
                            new_range = list(range(s, e + 1))
                            current = set(st.session_state.get('highlighted_residues', []))
                            current.update(new_range)
                            st.session_state.highlighted_residues = sorted(list(current))
                            st.rerun()
                    except:
                        st.error("Invalid range format")

                if st.button("Clear Selection", type="primary"):
                    st.session_state.highlighted_residues = []
                    st.rerun()
            
            if st.session_state.get('highlighted_residues'):
                st.info(f"👉 **{len(st.session_state.highlighted_residues)}** residues highlighted in 3D Viewer.")

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

        if st.button("Generate PDF Report", help="Create a comprehensive PDF report", key="btn_gen_report"):
            with st.spinner("Generating report..."):
                try:
                    report_path = st.session_state.report_generator.generate_report(
                        results, 
                        st.session_state.pdb_ids,
                        sections=report_sections
                    )
                    st.success(f"Report generated: {report_path.name}")
                    with open(report_path, "rb") as f:
                        st.download_button("⬇️ Download PDF Report", f, file_name=report_path.name, mime="application/pdf")
                except Exception as e:
                    st.error(f"Failed to generate report: {e}")
    
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
    
    tab_list = [
        ("📈 RMSD Analysis", render_rmsd_tab),
        ("🌳 Phylogenetic Tree", render_phylo_tree_tab),
        ("🧬 3D Visualization", render_3d_viewer_tab),
        ("💊 Ligands", render_ligand_tab),
        ("🔍 Clusters", render_clusters_tab),
        ("🧬 Sequences", render_sequences_tab),
        ("📁 Downloads", render_downloads_tab)
    ]
    
    tabs = st.tabs([t[0] for t in tab_list])
    for tab, (_, render_func) in zip(tabs, tab_list):
        with tab:
            render_func(results)
    
    st.divider()
    if 'result_dir' in results:
        st.info(f"📂 All results saved to: `{results['result_dir']}`")
