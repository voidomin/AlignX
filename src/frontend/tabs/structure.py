import streamlit as st
from src.backend.structure_viewer import show_structure_in_streamlit
from src.frontend.tabs.common import render_learning_card, render_help_expander

from typing import Dict, Any

def render_3d_viewer_tab(results: Dict[str, Any]) -> None:
    """
    Render the 3D Visualization tab.
    
    Args:
        results: The results dictionary containing alignment PDB path.
    """
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
                # Also clear cluster selection when closing
                if 'selected_cluster_members' in st.session_state:
                    del st.session_state.selected_cluster_members
                st.rerun()
                
            try:
                pdb_path = results['alignment_pdb']
                
                # Handle Cluster Filtering
                visible_chains = None
                members = st.session_state.get('selected_cluster_members')
                if members:
                    # Map protein names/IDs to chain IDs (A, B, C...)
                    # The order in results['rmsd_df'] index is the chain order
                    all_members = list(results['rmsd_df'].index)
                    visible_chains = [chr(ord('A') + all_members.index(m)) for m in members if m in all_members]
                    
                    st.warning(f"🎯 Currently viewing Cluster Family ({len(members)} proteins)")
                    if st.button("🔓 Clear Cluster Filter", use_container_width=True):
                        del st.session_state.selected_cluster_members
                        st.rerun()
                
                col1, col2 = st.columns(2)
                hl_chains = st.session_state.get('highlight_chains', {})
                
                col_styl1, col_styl2 = st.columns([2, 1])
                with col_styl1:
                    style_mode = st.selectbox(
                        "🎨 Visualization Theme",
                        options=["Neon Pro", "Scientific Spectral", "AlphaFold Confidence"],
                        index=0,
                        help="Choose the color scheme for the 3D viewer. 'Neon Pro' is our vibrant signature style."
                    )
                with col_styl2:
                    st.write("") # Spacer
                    st.write("") # Spacer
                    if st.button("🔄 Refresh View"):
                        st.rerun()
                
                with col1:
                    st.markdown("**Cartoon (Secondary Structure)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='cartoon', key='view_cartoon', highlight_residues=hl_chains, visible_chains=visible_chains, style_mode=style_mode)
                with col2:
                    st.markdown("**Sphere (Spacefill)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='sphere', key='view_sphere', highlight_residues=hl_chains, visible_chains=visible_chains, style_mode=style_mode)
                    
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("**Stick (Bonds & Atoms)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='stick', key='view_stick', highlight_residues=hl_chains, visible_chains=visible_chains, style_mode=style_mode)
                with col4:
                    st.markdown("**Line/Trace (Backbone)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='line', key='view_line', highlight_residues=hl_chains, visible_chains=visible_chains, style_mode=style_mode)
                
                st.caption("""
                **Controls:**
                - **Left click + drag**: Rotate | **Right click + drag**: Zoom | **Scroll**: Zoom in/out
                - Each structure is colored differently for easy identification
                """)
                
                # Export controls
                st.divider()
                st.markdown("#### 📸 Export Options")
                exp_col1, exp_col2 = st.columns(2)
                
                with exp_col1:
                    if st.button("🎥 Export Spinning HTML", use_container_width=True, help="Download a self-contained HTML file with a spinning 3D view"):
                        pdb_content = pdb_path.read_text()
                        # Escape backticks and backslashes for JS template literal
                        pdb_escaped = pdb_content.replace("\\", "\\\\").replace("`", "\\`")
                        
                        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Structural Superposition — Spin View</title>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<style>body{{margin:0;background:#111;display:flex;justify-content:center;align-items:center;height:100vh}}
#viewer{{width:800px;height:600px;border:2px solid #333;border-radius:8px}}</style>
</head><body>
<div id="viewer"></div>
<script>
let viewer = $3Dmol.createViewer('viewer', {{backgroundColor:'#111'}});
let pdbData = `{pdb_escaped}`;
viewer.addModel(pdbData, 'pdb');
viewer.setStyle({{}}, {{cartoon:{{color:'spectrum'}}}});
viewer.zoomTo();
viewer.spin(true);
viewer.render();
</script></body></html>"""
                        
                        st.download_button(
                            "⬇️ Download HTML",
                            data=html_content,
                            file_name="structure_spin.html",
                            mime="text/html",
                            use_container_width=True
                        )
                
                with exp_col2:
                    if st.button("📄 Export Static PDB", use_container_width=True, help="Download the aligned PDB file"):
                        pdb_data = pdb_path.read_bytes()
                        st.download_button(
                            "⬇️ Download PDB",
                            data=pdb_data,
                            file_name="alignment.pdb",
                            mime="chemical/x-pdb",
                            use_container_width=True
                        )
                
                # Show active highlights info
                if hl_chains:
                    chain_summary = ", ".join([f"Chain {c}: {len(r)} residues" for c, r in hl_chains.items()])
                    st.info(f"🔥 Highlighting: {chain_summary}")
                    
            except Exception as e:
                st.error(f"Failed to load 3D viewer: {str(e)}")
    else:
        st.warning("3D visualization not available")
