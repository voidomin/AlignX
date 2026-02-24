"""3D structure visualization using py3Dmol."""

from pathlib import Path
from typing import Optional, Any
import streamlit.components.v1 as components

from src.utils.logger import get_logger

logger = get_logger()


def render_3d_structure(pdb_file: Path, width: Any = "100%", height: int = 400, style: str = 'cartoon', unique_id: str = '1', highlight_residues = None, visible_chains = None, color_by_plddt: bool = False, style_mode: str = 'Neon Pro') -> Optional[str]:
    """
    Render 3D structure using py3Dmol in Streamlit.
    
    Args:
        pdb_file: Path to PDB file
        width: Viewer width in pixels
        height: Viewer height in pixels
        style: Visualization style ('cartoon', 'sphere', 'stick', 'line')
        unique_id: Unique identifier for the viewer div
        highlight_residues: Dict of {chain: [residue_nums]} for per-chain highlights,
                           or list of residue nums for global highlights (backward compat),
                           or None/empty for no highlights
        visible_chains: List of chain IDs to show. If None, show all.
        
    Returns:
        HTML string for embedding or None if failed
    """
    if highlight_residues is None:
        highlight_residues = {}
    
    # Backward compat: convert flat list to global dict
    if isinstance(highlight_residues, list):
        if highlight_residues:
            highlight_residues = {"__all__": highlight_residues}
        else:
            highlight_residues = {}
    
    try:
        # Read PDB file
        with open(pdb_file, 'r') as f:
            pdb_content = f.read()
        
        import json
        highlights_json = json.dumps(highlight_residues)
        has_highlights = len(highlight_residues) > 0
        
        # Create py3Dmol HTML viewer
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
        </head>
        <body style="margin:0; padding:0; overflow:hidden; background-color: transparent;">
            <div id="container_{unique_id}" style="width: 100%; height: {height}px; position: relative;"></div>
            <script>
                let viewer = $3Dmol.createViewer("container_{unique_id}", {{
                    backgroundColor: 'white' 
                }});
                viewer.setBackgroundColor(0x000000, 0); 
                
                let pdbData = `{pdb_content}`;
                viewer.addModel(pdbData, "pdb");
                
                const neonColors = [
                    '#FF00FF', '#00FFFF', '#00FF00', '#FFFF00', '#FF7E42',
                    '#4272FF', '#FF0055', '#8A2BE2', '#00FA9A', '#FFD700',
                    '#FF1493', '#1E90FF'
                ];
                
                const spectralColors = [
                    '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231', 
                    '#911eb4', '#42d4f4', '#f032e6', '#bfef45', '#fabed4', 
                    '#469990', '#dcbeff'
                ];
                
                let m = viewer.getModel(0);
                let atoms = m.selectedAtoms({{}});
                
                // Per-chain highlight dict: {{"A": [1,2,3], "C": [5,6]}} or {{"__all__": [1,2,3]}}
                let highlightDict = {highlights_json};
                let hasHighlights = {'true' if has_highlights else 'false'};
                
                let chains = [];
                for(let i=0; i<atoms.length; i++) {{
                    if(!chains.includes(atoms[i].chain)) chains.push(atoms[i].chain);
                }}
                
                // Apply base color per chain
                for(let i=0; i<chains.length; i++) {{
                    let color;
                    if ("{style_mode}" === "Scientific Spectral") {{
                        color = spectralColors[i % spectralColors.length];
                    }} else {{
                        color = neonColors[i % neonColors.length];
                    }}
                    
                    let sel = {{chain: chains[i]}};
                    let opacity = hasHighlights ? 0.6 : 1.0;
                    
                    if ("{style_mode}" === "AlphaFold Confidence" || {'true' if color_by_plddt else 'false'}) {{
                         // AlphaFold pLDDT coloring
                         viewer.setStyle(sel, {{
                             cartoon: {{
                                 colorscheme: {{
                                     prop: 'b',
                                     gradient: 'rwb',
                                     min: 50,
                                     max: 90
                                 }},
                                 opacity: opacity
                             }}
                         }});
                    }} else if ("{style}" === "cartoon") {{
                        viewer.setStyle(sel, {{cartoon: {{color: color, opacity: opacity}}}});
                    }} else if ("{style}" === "sphere") {{
                        viewer.setStyle(sel, {{sphere: {{scale: 0.3, color: color, opacity: opacity}}}});
                    }} else if ("{style}" === "stick") {{
                        viewer.setStyle(sel, {{stick: {{radius: 0.2, colorscheme: 'Jmol', opacity: opacity}}}});
                    }} else if ("{style}" === "line") {{
                        viewer.setStyle(sel, {{line: {{linewidth: 2, color: color, opacity: opacity}}}});
                    }}
                }}
                
                // Mapping of chain IDs to user-provided visibility
                let visibleChains = {json.dumps(visible_chains) if visible_chains else 'null'};
                
                // Apply per-chain highlights and visibility
                if (hasHighlights || visibleChains) {{
                    // Distinct, high-intensity colors for highlights
                    const hlColors = ['#FFD700', '#FF0000', '#00FF00', '#0000FF', '#FF00FF', '#00FFFF'];
                    let hlIdx = 0;
                    
                    for (let i=0; i<chains.length; i++) {{
                        let chainID = chains[i];
                        let sel = {{chain: chainID}};
                        
                        // Handle Visibility (Filter)
                        if (visibleChains && !visibleChains.includes(chainID)) {{
                            viewer.setStyle(sel, {{}}); // Hide if not in list
                            continue;
                        }}
                        
                        // Handle Highlights
                        if (hasHighlights) {{
                            let residues = highlightDict[chainID] || highlightDict["__all__"] || [];
                            if (residues.length > 0) {{
                                let hlColor = hlColors[hlIdx % hlColors.length];
                                viewer.setStyle({{chain: chainID, resi: residues}}, {{
                                    sphere: {{color: hlColor, scale: 1.0, opacity: 1.0}},
                                    stick: {{color: hlColor, radius: 0.5, opacity: 1.0}},
                                    cartoon: {{color: hlColor, opacity: 1.0}}
                                }});
                                hlIdx++;
                            }}
                        }}
                    }}
                }}

                viewer.zoomTo();
                viewer.render();
                viewer.zoom(0.8, 1000);
                
                // Snapshot Function
                window.takeSnapshot = function() {{
                    const canvas = document.querySelector("#container_{unique_id} canvas");
                    if (canvas) {{
                        const link = document.createElement('a');
                        link.download = 'structure_snapshot.png';
                        link.href = canvas.toDataURL("image/png");
                        link.click();
                    }}
                }};
            </script>
            
            <button onclick="takeSnapshot()" style="position: absolute; bottom: 10px; right: 10px; z-index: 1000; padding: 8px 12px; border: none; border-radius: 6px; background: rgba(255,255,255,0.2); backdrop-filter: blur(5px); color: white; font-family: sans-serif; cursor: pointer; border: 1px solid rgba(255,255,255,0.3); transition: 0.2s;">
                📸 Save Snapshot
            </button>
        </body>
        </html>
        """
        
        logger.info(f"Generated High-Impact 3D viewer for {pdb_file.name}")
        return html
        
        return html
        
    except Exception as e:
        logger.error(f"Failed to generate 3D viewer: {str(e)}")
        return None


def render_ligand_view(pdb_file: Path, ligand_data: dict, width: int = 800, height: int = 600, unique_id: str = 'ligand') -> Optional[str]:
    """
    Render 3D view focused on ligand and interactions.
    
    Args:
        pdb_file: Path to PDB file
        ligand_data: Interaction data from LigandAnalyzer
        width: Viewer width
        height: Viewer height
        unique_id: Unique ID for div
    """
    try:
        with open(pdb_file, 'r') as f:
            pdb_content = f.read()
            
        # Extract ligand ID details
        ligand_id = ligand_data['ligand'] # e.g. RET_A_296
        parts = ligand_id.split('_')
        l_name = "_".join(parts[:-2])
        l_chain = parts[-2]
        l_resi = parts[-1]
        
        # Build interaction selection JSON
        active_site_residues = [
            {'chain': i['chain'], 'resi': i['resi']} 
            for i in ligand_data['interactions']
        ]
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
        </head>
        <body style="margin:0; padding:0; overflow:hidden;">
            <div id="ligand_{unique_id}" style="width: {width}px; height: {height}px; position: relative;"></div>
            <script>
                let viewer = $3Dmol.createViewer("ligand_{unique_id}", {{
                    backgroundColor: 'white'
                }});
                viewer.setBackgroundColor(0x000000, 0);
                
                let pdbData = `{pdb_content}`;
                viewer.addModel(pdbData, "pdb");
                
                // 1. Render Protein as Ghostly Cartoon (Context)
                viewer.setStyle({{}}, {{cartoon: {{color: 'white', opacity: 0.3}}}});
                
                // 2. Render Ligand as Neon Sticks
                let ligandSel = {{chain: '{l_chain}', resi: {l_resi}, resn: '{l_name}'}};
                viewer.addStyle(ligandSel, {{stick: {{colorscheme: 'greenCarbon', radius: 0.3}}}});
                viewer.addStyle(ligandSel, {{sphere: {{scale: 0.3, color: '#00FF00'}}}});
                
                // 3. Render Interacting Residues
                let activeResidues = {active_site_residues};
                for(let i=0; i<activeResidues.length; i++) {{
                    let sel = activeResidues[i];
                    // Show sidechains as sticks
                    viewer.addStyle(sel, {{stick: {{colorscheme: 'magentaCarbon', radius: 0.15}}}});
                    // Label them
                    // viewer.addLabel(sel.resi, {{fontSize: 10, position: sel, backgroundColor: 'black'}});
                }}
                
                // 4. Zoom to Ligand
                viewer.zoomTo(ligandSel, 1000);
                
                viewer.render();
            </script>
        </body>
        </html>
        """
        return html
    except Exception as e:
        logger.error(f"Failed to render ligand view: {e}")
        return None

def show_structure_in_streamlit(pdb_file: Path, width: Any = "100%", height: int = 400, style: str = 'cartoon', key: str = '1', highlight_residues=None, visible_chains=None, color_by_plddt: bool = False, style_mode: str = 'Neon Pro'):
    """
    Display 3D structure in Streamlit app.
    
    Args:
        pdb_file: Path to PDB file
        width: Viewer width (int or "100%")
        height: Viewer height
        style: Visualization style
        key: Unique key for component
        highlight_residues: Dict of {chain: [residues]} or list or None
        visible_chains: List of chain IDs to show or None
        color_by_plddt: Whether to color by pLDDT (AlphaFold confidence)
        style_mode: 'Neon Pro', 'Spectral', or 'AlphaFold'
    """
    html = render_3d_structure(pdb_file, width, height, style, key, highlight_residues, visible_chains, color_by_plddt, style_mode)
    if html:
        components.html(html, height=height, scrolling=False)
    else:
        import streamlit as st
        st.error(f"Failed to load {style} viewer")

def show_ligand_view_in_streamlit(pdb_file: Path, ligand_data: dict, width: Any = "100%", height: int = 600, key: str = 'ligand'):
    """Wrapper for displaying ligand view in Streamlit"""
    html = render_ligand_view(pdb_file, ligand_data, width, height, key)
    if html:
        components.html(html, height=height, scrolling=False)
    else:
        import streamlit as st
        st.error("Failed to render ligand visualization")
