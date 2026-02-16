"""Phylogenetic tree generation from RMSD matrices."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform
from pathlib import Path
from typing import Optional, Tuple
from io import StringIO

from ..utils.logger import get_logger

logger = get_logger()


class PhyloTreeGenerator:
    """Generate phylogenetic trees from RMSD distance matrices."""
    
    def __init__(self, config: dict):
        """
        Initialize PhyloTreeGenerator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
    
    def generate_tree(self, rmsd_df: pd.DataFrame, output_path: Path) -> Tuple[bool, str, Optional[Path]]:
        """
        Generate phylogenetic tree from RMSD matrix.
        
        Args:
            rmsd_df: RMSD distance matrix as DataFrame
            output_path: Output file path for tree image
            
        Returns:
            Tuple of (success, message, image_path)
        """
        try:
            # Convert RMSD matrix to condensed distance matrix
            # scipy hierarchical clustering needs condensed form
            distance_matrix = squareform(rmsd_df.values)
            
            # Perform hierarchical clustering
            linkage_matrix = linkage(distance_matrix, method='average')
            
            # Create dendrogram
            plt.figure(figsize=(12, 8))
            dendrogram(
                linkage_matrix,
                labels=rmsd_df.index.tolist(),
                leaf_font_size=12,
                orientation='right',
                color_threshold=0.7 * max(linkage_matrix[:, 2])
            )
            
            plt.xlabel('RMSD Distance (Å)', fontsize=12)
            plt.ylabel('Protein Structure', fontsize=12)
            plt.title('Phylogenetic Tree (UPGMA Algorithm)', fontsize=14, fontweight='bold')
            plt.grid(axis='x', alpha=0.3)
            plt.tight_layout()
            
            # Save figure
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Phylogenetic tree saved to {output_path}")
            return True, "Tree generated successfully", output_path
            
        except Exception as e:
            logger.error(f"Failed to generate phylogenetic tree: {str(e)}")
            return False, f"Tree generation failed: {str(e)}", None
    
    def export_newick(self, rmsd_df: pd.DataFrame, output_path: Path) -> Tuple[bool, str, Optional[Path]]:
        """
        Export phylogenetic tree in Newick format.
        
        Args:
            rmsd_df: RMSD distance matrix
            output_path: Output file path for Newick file
            
        Returns:
            Tuple of (success, message, file_path)
        """
        try:
            # Convert to condensed distance matrix
            distance_matrix = squareform(rmsd_df.values)
            
            # Perform hierarchical clustering
            linkage_matrix = linkage(distance_matrix, method='average')
            
            # Convert to Newick format (simplified - uses linkage matrix)
            labels = rmsd_df.index.tolist()
            newick_str = self._linkage_to_newick(linkage_matrix, labels)
            
            # Save to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(newick_str + ';')
            
            logger.info(f"Newick tree saved to {output_path}")
            return True, "Newick tree exported", output_path
            
        except Exception as e:
            logger.error(f"Failed to export Newick: {str(e)}")
            return False, f"Newick export failed: {str(e)}", None
    
    def _linkage_to_newick(self, linkage_matrix: np.ndarray, labels: list) -> str:
        """
        Convert scipy linkage matrix to Newick format.
        
        Args:
            linkage_matrix: Scipy linkage matrix
            labels: List of leaf labels
            
        Returns:
            Newick format string
        """
        n = len(labels)
        nodes = {i: labels[i] for i in range(n)}
        
        for i, (idx1, idx2, dist, _) in enumerate(linkage_matrix):
            idx1, idx2 = int(idx1), int(idx2)
            node_id = n + i
            
            left = nodes[idx1]
            right = nodes[idx2]
            
            # Format branch lengths
            nodes[node_id] = f"({left}:{dist/2:.4f},{right}:{dist/2:.4f})"
        
        # Return root node
        return nodes[node_id]

    def generate_plotly_tree(self, rmsd_df: pd.DataFrame):
        """
        Generate interactive Plotly dendrogram.
        
        Args:
            rmsd_df: RMSD distance matrix
            
        Returns:
            Plotly Figure object or None
        """
        try:
            import plotly.figure_factory as ff
            import plotly.graph_objects as go
            
            # Create dendrogram
            # Note: ff.create_dendrogram calculates linkage internally
            fig = ff.create_dendrogram(
                rmsd_df.values,
                orientation='left',
                labels=rmsd_df.index.tolist(),
                linkagefun=lambda x: linkage(x, method='average')
            )
            
            fig.update_layout(
                title='Phylogenetic Tree (Interactive)',
                width=800,
                height=600,
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(
                    family="Inter, sans-serif",
                    size=12,
                    color="white"
                ),
                xaxis_title="RMSD Distance (Å)"
            )
            
            # Update trace colors to match theme
            # This is a bit hacky as dendrogram returns multiple traces
            for i in range(len(fig['data'])):
                fig['data'][i]['hoverinfo'] = 'y+x'
            
            return fig
            
        except Exception as e:
            logger.error(f"Failed to generate Plotly tree: {str(e)}")
            return None
