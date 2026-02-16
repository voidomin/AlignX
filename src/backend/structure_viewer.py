"""3D structure visualization using py3Dmol."""

from pathlib import Path
from typing import Optional
import streamlit.components.v1 as components

from ..utils.logger import get_logger

logger = get_logger()


def render_3d_structure(pdb_file: Path, width: int = 800, height: int = 600, style: str = 'cartoon', unique_id: str = '1') -> Optional[str]:
    """
    Render 3D structure using py3Dmol in Streamlit.
    
    Args:
        pdb_file: Path to PDB file
        width: Viewer width in pixels
        height: Viewer height in pixels
        style: Visualization style ('cartoon', 'sphere', 'stick', 'line')
        unique_id: Unique identifier for the viewer div
        
    Returns:
        HTML string for embedding or None if failed
    """
    try:
        # Read PDB file
        with open(pdb_file, 'r') as f:
            pdb_content = f.read()
        
        # Define style configuration
        style_spec = ""
        if style == 'cartoon':
            style_spec = "{cartoon: {colorscheme: 'chain'}}"
        elif style == 'sphere':
            style_spec = "{sphere: {scale: 0.3, colorscheme: 'chain'}}"
        elif style == 'stick':
            style_spec = "{stick: {radius: 0.15, colorscheme: 'chain'}}"
        elif style == 'line':
            style_spec = "{line: {linewidth: 2, colorscheme: 'chain'}}"
        
        # Create py3Dmol HTML viewer
        # Use transparent background to blend with the Cyber-Bio theme
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
        </head>
        <body style="margin:0; padding:0; overflow:hidden;">
            <div id="container_{unique_id}" style="width: {width}px; height: {height}px; position: relative;"></div>
            <script>
                // Create viewer with transparent background
                let viewer = $3Dmol.createViewer("container_{unique_id}", {{
                    backgroundColor: 'white' 
                }});
                
                // Set background to dark/transparent to match theme
                viewer.setBackgroundColor(0x000000, 0); 
                
                let pdbData = `{pdb_content}`;
                
                viewer.addModel(pdbData, "pdb");
                
                // HIGH IMPACT NEON PALETTE EXPANDED (12 unique colors)
                const neonColors = [
                    '#FF00FF', // Neon Magenta
                    '#00FFFF', // Neon Cyan
                    '#00FF00', // Neon Lime
                    '#FFFF00', // Neon Yellow
                    '#FF7E42', // Sunset Orange
                    '#4272FF', // Royal Blue
                    '#FF0055', // Neon Red
                    '#8A2BE2', // Blue Violet
                    '#00FA9A', // Spring Green
                    '#FFD700', // Gold
                    '#FF1493', // Deep Pink
                    '#1E90FF'  // Dodger Blue
                ];
                
                // Get all atoms to identify unique chains
                let m = viewer.getModel(0);
                let atoms = m.selectedAtoms({{}});
                let chains = [];
                for(let i=0; i<atoms.length; i++) {{
                    if(!chains.includes(atoms[i].chain)) chains.push(atoms[i].chain);
                }}
                
                // Apply color per chain
                for(let i=0; i<chains.length; i++) {{
                    let color = neonColors[i % neonColors.length];
                    let sel = {{chain: chains[i]}};
                    
                    if ("{style}" === "cartoon") {{
                        viewer.setStyle(sel, {{cartoon: {{color: color}}}});
                    }} else if ("{style}" === "sphere") {{
                        viewer.setStyle(sel, {{sphere: {{scale: 0.3, color: color}}}});
                    }} else if ("{style}" === "stick") {{
                        // Sticks use element colors usually, but let's try chain color for carbon
                        viewer.setStyle(sel, {{stick: {{radius: 0.15, colorscheme: 'Jmol'}}}});
                    }} else if ("{style}" === "line") {{
                        viewer.setStyle(sel, {{line: {{linewidth: 2, color: color}}}});
                    }}
                }}
                
                viewer.zoomTo();
                viewer.render();
                viewer.zoom(0.8, 1000);
                
                // Add a slow spin for "High-Impact" effect
                viewer.spin("y", 0.5);
            </script>
        </body>
        </html>
        """
        
        logger.info(f"Generated High-Impact 3D viewer for {pdb_file.name}")
        return html
        
    except Exception as e:
        logger.error(f"Failed to generate 3D viewer: {str(e)}")
        return None


def show_structure_in_streamlit(pdb_file: Path, width: int = 400, height: int = 300, style: str = 'cartoon', key: str = '1'):
    """
    Display 3D structure in Streamlit app.
    
    Args:
        pdb_file: Path to PDB file
        width: Viewer width
        height: Viewer height
        style: Visualization style
        key: Unique key for component
    """
    html = render_3d_structure(pdb_file, width, height, style, key)
    if html:
        components.html(html, width=width, height=height, scrolling=False)
    else:
        import streamlit as st
        st.error(f"Failed to load {style} viewer")
