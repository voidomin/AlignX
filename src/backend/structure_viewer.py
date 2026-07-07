"""3D structure visualization using py3Dmol."""

from pathlib import Path
from typing import Optional, Any
import streamlit.components.v1 as components

from src.utils.logger import get_logger

logger = get_logger()

DEFAULT_STYLE_MODE = "Neon Pro"


def render_3d_structure(
    pdb_file: Path,
    width: Any = "100%",
    height: int = 400,
    style: str = "cartoon",
    unique_id: str = "1",
    highlight_residues=None,
    visible_chains=None,
    color_by_plddt: bool = False,
    style_mode: str = DEFAULT_STYLE_MODE,
    residue_colors=None,
) -> Optional[str]:
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
        color_by_plddt: Whether to color by pLDDT (AlphaFold confidence)
        style_mode: 'Neon Pro', 'Spectral', or 'AlphaFold'
        residue_colors: Dict of {chain: {resi: hex_color}} for custom colors

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
        with open(pdb_file, "r") as f:
            pdb_content = f.read()

        import json

        highlights_json = json.dumps(highlight_residues)
        has_highlights = len(highlight_residues) > 0
        residue_colors_json = json.dumps(residue_colors if residue_colors else {})

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
                
                // Apply custom residue-level colors if provided
                let resColors = {residue_colors_json};
                let hasResColors = Object.keys(resColors).length > 0;
                
                if (hasResColors) {{
                    let opacity = hasHighlights ? 0.6 : 1.0;
                    for (let chain in resColors) {{
                        for (let resi in resColors[chain]) {{
                            let rColor = resColors[chain][resi];
                            let sel = {{chain: chain, resi: parseInt(resi)}};
                            
                            if ("{style}" === "cartoon") {{
                                viewer.setStyle(sel, {{cartoon: {{color: rColor, opacity: opacity}}}});
                            }} else if ("{style}" === "sphere") {{
                                viewer.setStyle(sel, {{sphere: {{scale: 0.3, color: rColor, opacity: opacity}}}});
                            }} else if ("{style}" === "stick") {{
                                viewer.setStyle(sel, {{stick: {{radius: 0.2, color: rColor, opacity: opacity}}}});
                            }} else if ("{style}" === "line") {{
                                viewer.setStyle(sel, {{line: {{linewidth: 2, color: rColor, opacity: opacity}}}});
                            }}
                        }}
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
                                viewer.addStyle({{chain: chainID, resi: residues}}, {{
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

                // Brief auto-rotation to signal the view is interactive, then
                // stop - viewer.spin() drives an unbounded requestAnimationFrame
                // render loop with no built-in timeout, and this view can be one
                // of 4 simultaneous viewers on screen (see _render_superimposed_view
                // in src/frontend/tabs/structure.py) - 4 of these spinning forever
                // is enough sustained GPU/CPU load to make the whole browser tab
                // hang, not just this component. Also stop immediately on any
                // user interaction so it doesn't fight manual rotation.
                viewer.spin("y", 0.5);
                let spinTimer_{unique_id} = setTimeout(() => viewer.spin(false), 3000);
                let stopSpin_{unique_id} = () => {{
                    clearTimeout(spinTimer_{unique_id});
                    viewer.spin(false);
                }};
                let container_{unique_id} = document.getElementById("container_{unique_id}");
                container_{unique_id}.addEventListener("mousedown", stopSpin_{unique_id});
                container_{unique_id}.addEventListener("touchstart", stopSpin_{unique_id});
                container_{unique_id}.addEventListener("wheel", stopSpin_{unique_id});

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

    except Exception:
        logger.exception("Failed to generate 3D viewer")
        return None


def render_ligand_view(
    pdb_file: Path,
    ligand_data: dict,
    width: int = 800,
    height: int = 600,
    unique_id: str = "ligand",
    highlight_indices: Optional[list] = None,
) -> Optional[str]:
    """
    Render 3D view focused on ligand and interactions.

    Args:
        pdb_file: Path to PDB file
        ligand_data: Interaction data from LigandAnalyzer
        width: Viewer width
        height: Viewer height
        unique_id: Unique ID for div
        highlight_indices: List of row indices to highlight in yellow
    """
    try:
        with open(pdb_file, "r") as f:
            pdb_content = f.read()

        # Extract ligand ID details
        ligand_id = ligand_data["ligand"]  # e.g. RET_A_296
        parts = ligand_id.split("_")
        l_name = "_".join(parts[:-2])
        l_chain = parts[-2]
        l_resi = parts[-1]

        # Build interaction selection JSON
        active_site_residues = []
        highlighted_residues = []

        for idx, i in enumerate(ligand_data["interactions"]):
            item = {"chain": i["chain"], "resi": i["resi"]}
            if highlight_indices is not None and idx in highlight_indices:
                highlighted_residues.append(item)
            else:
                active_site_residues.append(item)

        import json

        active_site_residues_json = json.dumps(active_site_residues)
        highlighted_residues_json = json.dumps(highlighted_residues)

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
                let activeResidues = {active_site_residues_json};
                for(let i=0; i<activeResidues.length; i++) {{
                    let sel = activeResidues[i];
                    // Show sidechains as sticks
                    viewer.addStyle(sel, {{stick: {{colorscheme: 'magentaCarbon', radius: 0.15}}}});
                }}
                
                // 3b. Render Highlighted Interacting Residues (Thicker yellow sticks & labels)
                let highlightedResidues = {highlighted_residues_json};
                for(let i=0; i<highlightedResidues.length; i++) {{
                    let sel = highlightedResidues[i];
                    viewer.addStyle(sel, {{stick: {{colorscheme: 'yellowCarbon', radius: 0.35}}}});
                    viewer.addStyle(sel, {{sphere: {{scale: 0.5, color: '#FFFF00'}}}});
                    viewer.addLabel(sel.chain + ":" + sel.resi, {{
                        fontSize: 11,
                        fontColor: 'white',
                        backgroundColor: 'rgba(255, 126, 66, 0.88)',
                        backgroundOpacity: 0.9,
                        borderColor: 'white',
                        borderWidth: 1,
                        position: sel
                    }});
                }}
                
                // 4. Zoom to Ligand / Highlighted Residues
                if (highlightedResidues.length > 0) {{
                    let combinedSel = [ligandSel];
                    highlightedResidues.forEach(r => combinedSel.push(r));
                    viewer.zoomTo({{or: combinedSel}}, 1000);
                }} else {{
                    viewer.zoomTo(ligandSel, 1000);
                }}
                
                viewer.render();

                // Brief auto-rotation (only when no highlights selected), then
                // stop - see render_3d_structure's comment on why an unbounded
                // spin() render loop is a real perf/hang risk, not just a nit.
                if (highlightedResidues.length === 0) {{
                    viewer.spin("y", 0.5);
                    let ligandSpinTimer_{unique_id} = setTimeout(() => viewer.spin(false), 3000);
                    let stopLigandSpin_{unique_id} = () => {{
                        clearTimeout(ligandSpinTimer_{unique_id});
                        viewer.spin(false);
                    }};
                    let ligandContainer_{unique_id} = document.getElementById("ligand_{unique_id}");
                    ligandContainer_{unique_id}.addEventListener("mousedown", stopLigandSpin_{unique_id});
                    ligandContainer_{unique_id}.addEventListener("touchstart", stopLigandSpin_{unique_id});
                    ligandContainer_{unique_id}.addEventListener("wheel", stopLigandSpin_{unique_id});
                }}
            </script>
        </body>
        </html>
        """
        return html
    except Exception:
        logger.exception("Failed to render ligand view")
        return None


def show_structure_in_streamlit(
    pdb_file: Path,
    width: Any = "100%",
    height: int = 400,
    style: str = "cartoon",
    key: str = "1",
    highlight_residues=None,
    visible_chains=None,
    color_by_plddt: bool = False,
    style_mode: str = DEFAULT_STYLE_MODE,
    residue_colors=None,
):
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
        residue_colors: Dict of {chain: {resi: hex_color}} for custom coloring
    """
    html = render_3d_structure(
        pdb_file,
        width,
        height,
        style,
        key,
        highlight_residues,
        visible_chains,
        color_by_plddt,
        style_mode,
        residue_colors,
    )
    if html:
        components.html(html, height=height, scrolling=False)
    else:
        import streamlit as st

        st.error(f"Failed to load {style} viewer")


def render_synced_grid(
    pdb_file: Path,
    members: list,
    highlight_residues=None,
    style_mode: str = DEFAULT_STYLE_MODE,
    residue_colors=None,
    height: int = 250,
) -> Optional[str]:
    """
    Render all aligned models in a single synchronized 3D grid.
    """
    if highlight_residues is None:
        highlight_residues = {}
    if residue_colors is None:
        residue_colors = {}

    try:
        with open(pdb_file, "r") as f:
            pdb_content = f.read()

        import json

        viewers_js = []
        html_items = []

        neon_colors = [
            "#FF00FF",
            "#00FFFF",
            "#00FF00",
            "#FFFF00",
            "#FF7E42",
            "#4272FF",
            "#FF0055",
            "#8A2BE2",
            "#00FA9A",
            "#FFD700",
            "#FF1493",
            "#1E90FF",
        ]

        spectral_colors = [
            "#e6194B",
            "#3cb44b",
            "#ffe119",
            "#4363d8",
            "#f58231",
            "#911eb4",
            "#42d4f4",
            "#f032e6",
            "#bfef45",
            "#fabed4",
            "#469990",
            "#dcbeff",
        ]

        # Determine all chains in this PDB
        all_chains = [chr(ord("A") + idx) for idx in range(len(members))]

        for idx, member in enumerate(members):
            chain_id = chr(ord("A") + idx)
            div_id = f"viewer_{idx}"

            # Highlight configuration
            this_hl = (
                {chain_id: highlight_residues.get(chain_id, [])}
                if highlight_residues
                else {}
            )
            has_hl = len(this_hl.get(chain_id, [])) > 0

            this_res_colors = residue_colors.get(chain_id, {}) if residue_colors else {}

            color = (
                spectral_colors[idx % len(spectral_colors)]
                if style_mode == "Scientific Spectral"
                else neon_colors[idx % len(neon_colors)]
            )

            viewer_init = f"""
                (function() {{
                    let viewer = $3Dmol.createViewer("container_{div_id}", {{
                        backgroundColor: 'white'
                    }});
                    viewer.setBackgroundColor(0x000000, 0);
                    viewer.addModel(pdbData, "pdb");
                    
                    let m = viewer.getModel(0);
                    let opacity = { '0.6' if has_hl else '1.0' };
                    let sel = {{chain: "{chain_id}"}};
                    
                    // Base style for selected chain
                    if ("{style_mode}" === "AlphaFold Confidence") {{
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
                    }} else {{
                        viewer.setStyle(sel, {{cartoon: {{color: "{color}", opacity: opacity}}}});
                    }}
                    
                    // Hide all other chains in this specific viewer viewport
                    let otherChains = allChains.filter(c => c !== "{chain_id}");
                    otherChains.forEach(oc => {{
                        viewer.setStyle({{chain: oc}}, {{}});
                    }});
                    
                    // Custom residue colors
                    let resColors = {json.dumps(this_res_colors)};
                    if (Object.keys(resColors).length > 0) {{
                        for (let resi in resColors) {{
                            viewer.setStyle({{chain: "{chain_id}", resi: parseInt(resi)}}, {{
                                cartoon: {{color: resColors[resi], opacity: opacity}}
                            }});
                        }}
                    }}
                    
                    // Highlights
                    let hlResidues = {json.dumps(this_hl.get(chain_id, []))};
                    if (hlResidues.length > 0) {{
                        viewer.addStyle({{chain: "{chain_id}", resi: hlResidues}}, {{
                            sphere: {{color: '#FFD700', scale: 1.0, opacity: 1.0}},
                            stick: {{color: '#FFD700', radius: 0.5, opacity: 1.0}},
                            cartoon: {{color: '#FFD700', opacity: 1.0}}
                        }});
                    }}
                    
                    viewer.zoomTo({{chain: "{chain_id}"}});
                    viewer.render();
                    viewer.zoom(0.8, 1000);
                    
                    viewers.push(viewer);
                    
                    // Hook interactions for syncing cameras
                    let container = document.getElementById("container_{div_id}");
                    
                    container.addEventListener('mousedown', () => {{ activeViewer = viewer; isInteracting = true; }});
                    container.addEventListener('touchstart', () => {{ activeViewer = viewer; isInteracting = true; }});
                    
                    container.addEventListener('mousemove', () => {{
                        if (isInteracting && activeViewer === viewer) {{
                            requestAnimationFrame(syncCameras);
                        }}
                    }});
                    container.addEventListener('touchmove', () => {{
                        if (isInteracting && activeViewer === viewer) {{
                            requestAnimationFrame(syncCameras);
                        }}
                    }});
                    container.addEventListener('wheel', () => {{
                        activeViewer = viewer;
                        requestAnimationFrame(syncCameras);
                    }});
                }})();
            """
            viewers_js.append(viewer_init)

            html_items.append(f"""
            <div class="grid-item">
                <div class="viewer-title">{member} (Chain {chain_id})</div>
                <div id="container_{div_id}" class="viewer-container"></div>
            </div>
            """)

        viewers_js_str = "\n".join(viewers_js)
        html_items_str = "\n".join(html_items)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
            <style>
                .grid-container {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 12px;
                    width: 100%;
                    padding: 8px;
                    box-sizing: border-box;
                }}
                @media (max-width: 900px) {{
                    .grid-container {{
                        grid-template-columns: repeat(2, 1fr);
                    }}
                }}
                @media (max-width: 600px) {{
                    .grid-container {{
                        grid-template-columns: 1fr;
                    }}
                }}
                .grid-item {{
                    background: rgba(255,255,255,0.02);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 12px;
                    padding: 8px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                }}
                .viewer-container {{
                    width: 100%;
                    height: {height}px;
                    position: relative;
                }}
                .viewer-title {{
                    color: #e0c8b0;
                    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    font-size: 0.82rem;
                    font-weight: 600;
                    margin-bottom: 6px;
                    text-align: center;
                    letter-spacing: 0.5px;
                }}
            </style>
        </head>
        <body style="margin:0; padding:0; background-color: transparent; overflow-x:hidden;">
            <div class="grid-container">
                {html_items_str}
            </div>
            <script>
                const pdbData = `{pdb_content}`;
                const viewers = [];
                let activeViewer = null;
                let isInteracting = false;
                
                const allChains = {json.dumps(all_chains)};
                
                window.addEventListener('mouseup', () => {{ isInteracting = false; }});
                window.addEventListener('touchend', () => {{ isInteracting = false; }});
                
                function syncCameras() {{
                    if (!activeViewer) return;
                    const view = activeViewer.getView();
                    viewers.forEach(v => {{
                        if (v !== activeViewer) {{
                            v.setView(view);
                            v.render();
                        }}
                    }});
                }}
                
                // Initialize viewers
                {viewers_js_str}
            </script>
        </body>
        </html>
        """
        return html
    except Exception:
        logger.exception("Failed to generate synced grid 3D viewer")
        return None


def show_synced_grid_in_streamlit(
    pdb_file: Path,
    members: list,
    highlight_residues=None,
    style_mode: str = DEFAULT_STYLE_MODE,
    residue_colors=None,
    height: int = 250,
):
    """Display synchronized 3D grid of structures in Streamlit"""
    html = render_synced_grid(
        pdb_file=pdb_file,
        members=members,
        highlight_residues=highlight_residues,
        style_mode=style_mode,
        residue_colors=residue_colors,
        height=height,
    )
    if html:
        import math

        n_cols = 3
        rows = math.ceil(len(members) / n_cols)
        iframe_height = rows * (height + 40) + 30
        components.html(html, height=iframe_height, scrolling=False)
    else:
        import streamlit as st

        st.error("Failed to render synchronized 3D structure grid")


def show_ligand_view_in_streamlit(
    pdb_file: Path,
    ligand_data: dict,
    width: Any = "100%",
    height: int = 600,
    key: str = "ligand",
    highlight_indices: Optional[list] = None,
):
    """Wrapper for displaying ligand view in Streamlit"""
    html = render_ligand_view(
        pdb_file, ligand_data, width, height, key, highlight_indices
    )
    if html:
        components.html(html, height=height, scrolling=False)
    else:
        import streamlit as st

        st.error("Failed to render ligand visualization")
