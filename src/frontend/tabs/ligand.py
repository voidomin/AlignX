import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from src.backend.structure_viewer import show_ligand_view_in_streamlit
from src.frontend.tabs.common import render_learning_card, render_help_expander

def render_ligand_tab(results: Dict[str, Any]) -> None:
    """
    Render the Ligand & Interaction Analysis tab.
    
    Args:
        results: The results dictionary containing data directory for ligand lookup.
    """
    st.subheader("💊 Ligand & Interaction Analysis")
    render_learning_card("Ligands")
    render_help_expander("ligands")
    
    tab_single, tab_compare, tab_sasa = st.tabs(["🧪 Single Ligand Analysis", "⚔️ Pocket Comparison", "🌊 Surface Area (SASA)"])
    
    with tab_single:
        sel_col1, sel_col2 = st.columns(2)
        
        with sel_col1:
            selected_pdb_ligand = st.selectbox("Select Protein Structure", st.session_state.pdb_ids, key="ligand_pdb_select")
        
        result_dir = results['result_dir']
        
        pdb_path = None
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
                        
                        entry = interactions.copy()
                        entry['pdb_path'] = str(pdb_path)
                        entry['pdb_id'] = selected_pdb_ligand
                        
                        if 'pocket_history' not in st.session_state: st.session_state.pocket_history = []
                        
                        st.session_state.pocket_history = [x for x in st.session_state.pocket_history if x['ligand'] != interactions['ligand']]
                        st.session_state.pocket_history.append(entry)
                    
        else:
            st.error(f"PDB file not found for {selected_pdb_ligand}")
    
        st.divider()

        if 'current_interactions' in st.session_state:
            interactions = st.session_state.current_interactions
            pdb_path = st.session_state.current_ligand_pdb
            
            if 'error' in interactions:
                st.error(interactions['error'])
            else:
                st.markdown(f"### Binding Site: **{interactions['ligand']}**")
                
                res_col1, res_col2 = st.columns([1, 1])
                
                with res_col1:
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

    with tab_compare:
        st.caption("Compare the environments of analyzed ligands. (Analyze ligands in the Single tab first to add them here).")
        
        history = st.session_state.get('pocket_history', [])
        
        if history:
            if st.button("🗑️ Clear Interaction History", use_container_width=True):
                st.session_state.pocket_history = []
                if 'current_interactions' in st.session_state:
                    del st.session_state.current_interactions
                st.rerun()

        if len(history) < 2:
             st.warning("⚠️ Analyze at least 2 different ligands in the 'Single Ligand Analysis' tab to enable comparison.")
        else:
            st.subheader("Chemical Environment Similarity Matrix")
            st.caption("Jaccard Index based on shared residue types in the binding pocket.")
            
            sim_matrix = st.session_state.ligand_analyzer.calculate_interaction_similarity(history)
            st.dataframe(sim_matrix.style.background_gradient(cmap="Greens", vmin=0, vmax=1))
            
            st.divider()
            
            st.subheader("⚔️ Side-by-Side Pocket View")
            
            c_sel1, c_sel2 = st.columns(2)
            options = [h['ligand'] for h in history]
            
            l1_id = c_sel1.selectbox("Pocket 1", options, index=0, key="cmp_p1")
            l2_id = c_sel2.selectbox("Pocket 2", options, index=1 if len(options)>1 else 0, key="cmp_p2")
            
            if l1_id and l2_id:
                d1 = next(h for h in history if h['ligand'] == l1_id)
                d2 = next(h for h in history if h['ligand'] == l2_id)
                
                row1_c1, row1_c2 = st.columns(2)
                with row1_c1:
                    show_ligand_view_in_streamlit(Path(d1['pdb_path']), d1, width=350, height=350, key="ligand_view_1")
                with row1_c2:
                    show_ligand_view_in_streamlit(Path(d2['pdb_path']), d2, width=350, height=350, key="ligand_view_2")
                    
                st.subheader("Comparison Details")
                
                set1 = set([x['residue'] for x in d1['interactions']])
                set2 = set([x['residue'] for x in d2['interactions']])
                
                shared = set1.intersection(set2)
                unique1 = set1 - set2
                unique2 = set2 - set1
                
                delta_col1, delta_col2, delta_col3 = st.columns(3)
                delta_col1.metric("Shared Residue Types", len(shared), help=f"{', '.join(shared)}")
                delta_col2.metric(f"Unique to {l1_id}", len(unique1), help=f"{', '.join(unique1)}")
                delta_col3.metric(f"Unique to {l2_id}", len(unique2), help=f"{', '.join(unique2)}")

    with tab_sasa:
        st.caption("Compute Solvent Accessible Surface Area (SASA) using the Shrake-Rupley algorithm.")
        
        selected_sasa_pdb = st.selectbox("Select Protein", st.session_state.pdb_ids, key="sasa_pdb_select")
        
        result_dir = results['result_dir']
        sasa_pdb_path = None
        for name in [f"{selected_sasa_pdb}.pdb", f"{selected_sasa_pdb.lower()}.pdb", f"{selected_sasa_pdb.upper()}.pdb"]:
            p = result_dir / name
            if p.exists():
                sasa_pdb_path = p
                break
        
        if sasa_pdb_path:
            if st.button("🌊 Calculate SASA", type="primary", use_container_width=True, key="btn_sasa"):
                with st.spinner("Computing solvent accessible surface area..."):
                    sasa_result = st.session_state.ligand_analyzer.calculate_sasa(sasa_pdb_path)
                    st.session_state.sasa_result = sasa_result
                    st.session_state.sasa_pdb_id = selected_sasa_pdb
            
            if 'sasa_result' in st.session_state and st.session_state.get('sasa_pdb_id') == selected_sasa_pdb:
                sasa = st.session_state.sasa_result
                
                if 'error' in sasa:
                    st.error(sasa['error'])
                else:
                    # Metrics row
                    m1, m2 = st.columns(2)
                    m1.metric("Total SASA", f"{sasa['total_sasa']:.1f} Å²")
                    chain_summary = ", ".join([f"Chain {k}: {v:.0f} Å²" for k, v in sasa['chain_sasa'].items()])
                    m2.metric("Chains", chain_summary)
                    
                    # Per-residue chart
                    if sasa.get('residues'):
                        import plotly.express as px
                        
                        df_sasa = pd.DataFrame(sasa['residues'])
                        df_sasa['label'] = df_sasa['residue'] + df_sasa['resi'].astype(str)
                        
                        fig = px.bar(
                            df_sasa,
                            x='label',
                            y='sasa',
                            color='sasa',
                            color_continuous_scale='Viridis',
                            labels={'label': 'Residue', 'sasa': 'SASA (Å²)'},
                            title=f'Per-Residue SASA — {selected_sasa_pdb}'
                        )
                        fig.update_layout(height=400, xaxis_tickangle=-45, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f"PDB file not found for {selected_sasa_pdb}")
