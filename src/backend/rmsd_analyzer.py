"""RMSD analysis and visualization module."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from ..utils.logger import get_logger

logger = get_logger()


class RMSDAnalyzer:
    """Analyze and visualize RMSD matrices."""
    
    def __init__(self, config: Dict):
        """Initialize RMSD Analyzer."""
        self.config = config
        self.colormap = config.get('visualization', {}).get('heatmap_colormap', 'RdYlBu_r')
        self.dpi = config.get('visualization', {}).get('dpi', 300)
    
    def generate_heatmap(self, rmsd_df: pd.DataFrame, output_path: Path) -> bool:
        """
        Generate RMSD heatmap visualization.
        
        Args:
            rmsd_df: DataFrame containing RMSD matrix
            output_path: Path to save the heatmap image
            
        Returns:
            True if successful
        """
        try:
            plt.figure(figsize=(10, 8))
            
            # Create heatmap
            sns.heatmap(
                rmsd_df,
                annot=True,
                fmt='.2f',
                cmap=self.colormap,
                square=True,
                cbar_kws={'label': 'RMSD (Å)'},
                linewidths=0.5
            )
            
            plt.title('Pairwise RMSD Matrix', fontsize=16, fontweight='bold')
            plt.xlabel('Protein', fontsize=12)
            plt.ylabel('Protein', fontsize=12)
            plt.tight_layout()
            
            plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Heatmap saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate heatmap: {str(e)}")
            return False

    def generate_plotly_heatmap(self, rmsd_df: pd.DataFrame):
        """
        Generate interactive Plotly heatmap.
        
        Args:
            rmsd_df: DataFrame containing RMSD matrix
            
        Returns:
            Plotly Figure object or None
        """
        try:
            import plotly.graph_objects as go
            
            # Custom colorscale: Royal Blue -> Cyan -> Mustard -> Sunset Orange
            # This aligns with the "Sunset" palette
            colorscale = [
                [0.0, '#4272FF'],  # Royal Blue (Low RMSD)
                [0.33, '#42EAFF'], # Cyan
                [0.66, '#FFB343'], # Mustard
                [1.0, '#FF7E42']   # Sunset Orange (High RMSD)
            ]
            
            fig = go.Figure(data=go.Heatmap(
                z=rmsd_df.values,
                x=rmsd_df.columns,
                y=rmsd_df.index,
                colorscale=colorscale,
                text=rmsd_df.values,
                texttemplate="%{text:.2f}",
                textfont={"color": "white"},
                hoverongaps=False,
                hovertemplate='<b>Protein A</b>: %{y}<br>' +
                              '<b>Protein B</b>: %{x}<br>' +
                              '<b>RMSD</b>: %{z:.2f} Å<extra></extra>'
            ))
            
            fig.update_layout(
                title='Pairwise RMSD Matrix (Interactive)',
                xaxis_title="Protein ID",
                yaxis_title="Protein ID",
                width=700,
                height=600,
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(
                    family="Inter, sans-serif",
                    size=12,
                    color="white"
                )
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Failed to generate Plotly heatmap: {str(e)}")
            return None
    
    def calculate_statistics(self, rmsd_df: pd.DataFrame) -> Dict:
        """
        Calculate RMSD statistics.
        
        Args:
            rmsd_df: DataFrame containing RMSD matrix
            
        Returns:
            Dictionary with statistics
        """
        # Get upper triangle (excluding diagonal)
        mask = np.triu(np.ones_like(rmsd_df, dtype=bool), k=1)
        values = rmsd_df.where(mask).values.flatten()
        values = values[~np.isnan(values)]
        
        stats = {
            'mean_rmsd': float(np.mean(values)),
            'median_rmsd': float(np.median(values)),
            'min_rmsd': float(np.min(values)),
            'max_rmsd': float(np.max(values)),
            'std_rmsd': float(np.std(values)),
        }
        
        return stats
    
    def identify_clusters(self, rmsd_df: pd.DataFrame, threshold: float = 3.0) -> Dict[int, List[str]]:
        """
        Identify structural clusters based on RMSD threshold.
        
        Args:
            rmsd_df: DataFrame containing RMSD matrix
            threshold: RMSD threshold for clustering (Angstroms)
            
        Returns:
            Dictionary mapping cluster ID to list of protein IDs
        """
        from scipy.cluster.hierarchy import linkage, fcluster
        
        # Convert to distance matrix (upper triangle)
        condensed = []
        n = len(rmsd_df)
        for i in range(n):
            for j in range(i+1, n):
                condensed.append(rmsd_df.iloc[i, j])
        
        # Hierarchical clustering
        Z = linkage(condensed, method='average')
        labels = fcluster(Z, threshold, criterion='distance')
        
        # Group by cluster
        clusters = {}
        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(rmsd_df.index[idx])
        
        return clusters
    
    def export_to_phylip(self, rmsd_df: pd.DataFrame, output_path: Path) -> bool:
        """
        Export RMSD matrix in Phylip distance matrix format.
        
        Args:
            rmsd_df: DataFrame containing RMSD matrix
            output_path: Output file path
            
        Returns:
            True if successful
        """
        try:
            n = len(rmsd_df)
            
            with open(output_path, 'w') as f:
                # Header: number of taxa
                f.write(f"    {n}\n")
                
                # Write each row
                for idx, row_name in enumerate(rmsd_df.index):
                    # Phylip format: 10-character name (left-justified) + values
                    name = str(row_name)[:10].ljust(10)
                    values = '  '.join([f"{val:.4f}" for val in rmsd_df.iloc[idx]])
                    f.write(f"{name}  {values}\n")
            
            logger.info(f"Phylip distance matrix saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export Phylip format: {str(e)}")
            return False

    def calculate_residue_rmsf(self, alignment_pdb: Path, alignment_afasta: Path) -> Tuple[List[float], List[str]]:
        """
        Calculate Root Mean Square Fluctuation (RMSF) per residue/column.
        
        Args:
            alignment_pdb: Path to alignment PDB file (must have multiple chains)
            alignment_afasta: Path to alignment AFASTA file
            
        Returns:
            Tuple of (rmsf_values, conservation_labels)
        """
        try:
            # 1. Parse Sequences to get alignment length and structure
            sequences = {}
            current_header = None
            current_seq = []
            
            with open(alignment_afasta, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith('>'):
                        if current_header: sequences[current_header] = ''.join(current_seq)
                        current_header = line[1:].strip()
                        current_seq = []
                    else:
                        current_seq.append(line)
                if current_header: sequences[current_header] = ''.join(current_seq)
            
            if not sequences:
                logger.error("No sequences found in AFASTA file")
                return [], []

            seq_keys = list(sequences.keys())
            alignment_length = len(list(sequences.values())[0])
            num_structures = len(sequences)
            
            # Initialize coordinate storage: [alignment_pos][structure_idx] = (x, y, z)
            # Use None for gaps
            coords = [[None for _ in range(num_structures)] for _ in range(alignment_length)]
            
            # 2. Parse PDB
            # We assume PDB chains correspond to sequences in order (or by ID but order is safer for Mustang output)
            # Mustang outputs Chain A, B, C... in order of input
            
            current_chain_idx = -1
            current_residue_idx = -1 # Index in the SEQUENCE (ignoring gaps)
            last_chain_id = None
            
            # Map sequence index to alignment index for each structure
            # structure_maps[struct_idx][seq_idx] = alignment_idx
            structure_maps = []
            for seq in sequences.values():
                mapping = {}
                seq_idx = 0
                for align_idx, char in enumerate(seq):
                    if char != '-':
                        mapping[seq_idx] = align_idx
                        seq_idx += 1
                structure_maps.append(mapping)

            with open(alignment_pdb, 'r') as f:
                for line in f:
                    if line.startswith('ATOM') and line[12:16].strip() == 'CA':
                        chain_id = line[21]
                        
                        if chain_id != last_chain_id:
                            current_chain_idx += 1
                            current_residue_idx = -1
                            last_chain_id = chain_id
                            
                        current_residue_idx += 1
                        
                        if current_chain_idx >= num_structures:
                            break # Should not happen if files match
                            
                        # Get alignment index
                        # current_residue_idx is the index of the RESIDUE in the sequence
                        # We need to find which alignment column this corresponds to
                        if current_chain_idx < len(structure_maps) and current_residue_idx in structure_maps[current_chain_idx]:
                            align_idx = structure_maps[current_chain_idx][current_residue_idx]
                            
                            x = float(line[30:38])
                            y = float(line[38:46])
                            z = float(line[46:54])
                            
                            coords[align_idx][current_chain_idx] = np.array([x, y, z])

            # 3. Calculate RMSF per column
            rmsf_values = []
            
            for i in range(alignment_length):
                col_coords = [c for c in coords[i] if c is not None]
                n = len(col_coords)
                
                if n < 2:
                    rmsf_values.append(0.0) # Not enough data for variance
                else:
                    # Calculate mean position (centroid)
                    mean_pos = np.mean(col_coords, axis=0)
                    
                    # Calculate RMSD from mean
                    # mean of squared diffs
                    sq_diffs = [np.sum((c - mean_pos)**2) for c in col_coords]
                    # RMSF = sqrt(mean(sq_diffs))
                    rmsf = np.sqrt(np.mean(sq_diffs))
                    rmsf_values.append(float(rmsf))
                
            return rmsf_values, list(sequences.keys())

        except Exception as e:
            logger.error(f"Failed to calculate residue RMSF: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return [], []
