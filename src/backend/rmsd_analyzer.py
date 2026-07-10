"""RMSD analysis and visualization module."""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from src.utils.logger import get_logger

logger = get_logger()


class RMSDAnalyzer:
    """Analyze and visualize RMSD matrices."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize RMSD Analyzer."""
        self.config = config
        self.colormap = config.get("visualization", {}).get(
            "heatmap_colormap", "RdYlBu_r"
        )
        self.dpi = config.get("visualization", {}).get("dpi", 300)

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
            import matplotlib.pyplot as plt
            import seaborn as sns

            plt.figure(figsize=(10, 8))

            # Create heatmap
            sns.heatmap(
                rmsd_df,
                annot=True,
                fmt=".2f",
                cmap=self.colormap,
                square=True,
                cbar_kws={"label": "RMSD (Å)"},
                linewidths=0.5,
            )

            plt.title("Pairwise RMSD Matrix", fontsize=16, fontweight="bold")
            plt.xlabel("Protein", fontsize=12)
            plt.ylabel("Protein", fontsize=12)
            plt.tight_layout()

            plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight")
            plt.close()

            logger.info(f"Heatmap saved to {output_path}")
            return True

        except Exception:
            logger.exception("Failed to generate heatmap")
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
                [0.0, "#4272FF"],  # Royal Blue (Low RMSD)
                [0.33, "#42EAFF"],  # Cyan
                [0.66, "#FFB343"],  # Mustard
                [1.0, "#FF7E42"],  # Sunset Orange (High RMSD)
            ]

            fig = go.Figure(
                data=go.Heatmap(
                    # .tolist() (not the raw ndarray) so Plotly serializes plain
                    # JSON arrays instead of its compact binary typed-array format,
                    # which the pinned frontend Plotly.js CDN version can't decode.
                    z=rmsd_df.values.tolist(),
                    x=rmsd_df.columns.tolist(),
                    y=rmsd_df.index.tolist(),
                    colorscale=colorscale,
                    text=rmsd_df.values.tolist(),
                    texttemplate="%{text:.2f}",
                    textfont={"color": "white"},
                    hoverongaps=False,
                    hovertemplate="<b>Protein A</b>: %{y}<br>"
                    + "<b>Protein B</b>: %{x}<br>"
                    + "<b>RMSD</b>: %{z:.2f} Å<extra></extra>",
                )
            )

            fig.update_layout(
                title="Pairwise RMSD Matrix (Interactive)",
                xaxis_title="Protein ID",
                yaxis_title="Protein ID",
                width=700,
                height=600,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"family": "Inter, sans-serif", "size": 12, "color": "white"},
            )

            return fig

        except Exception:
            logger.exception("Failed to generate Plotly heatmap")
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
            "mean_rmsd": float(np.mean(values)),
            "median_rmsd": float(np.median(values)),
            "min_rmsd": float(np.min(values)),
            "max_rmsd": float(np.max(values)),
            "std_rmsd": float(np.std(values)),
        }

        return stats

    def identify_clusters(
        self, rmsd_df: pd.DataFrame, threshold: float = 3.0
    ) -> Dict[int, List[str]]:
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
            for j in range(i + 1, n):
                condensed.append(rmsd_df.iloc[i, j])

        # Hierarchical clustering
        Z = linkage(condensed, method="average")
        labels = fcluster(Z, threshold, criterion="distance")

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

            with open(output_path, "w") as f:
                # Header: number of taxa
                f.write(f"    {n}\n")

                # Write each row
                for idx, row_name in enumerate(rmsd_df.index):
                    # Phylip format: 10-character name (left-justified) + values
                    name = str(row_name)[:10].ljust(10)
                    values = "  ".join([f"{val:.4f}" for val in rmsd_df.iloc[idx]])
                    f.write(f"{name}  {values}\n")

            logger.info(f"Phylip distance matrix saved to {output_path}")
            return True

        except Exception:
            logger.exception("Failed to export Phylip format")
            return False

    @staticmethod
    def _parse_afasta_sequences(alignment_afasta: Path) -> Dict[str, str]:
        sequences = {}
        current_header = None
        current_seq = []
        with open(alignment_afasta, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(">"):
                    if current_header:
                        sequences[current_header] = "".join(current_seq)
                    current_header = line[1:].strip()
                    current_seq = []
                else:
                    current_seq.append(line)
            if current_header:
                sequences[current_header] = "".join(current_seq)
        return sequences

    @staticmethod
    def _build_structure_maps(sequences: Dict[str, str]) -> List[Dict[int, int]]:
        """structure_maps[struct_idx][seq_idx] = alignment_idx - maps each
        structure's ungapped residue index to its alignment column, so a
        PDB residue (indexed by sequence position) can be placed in the
        shared alignment-column coordinate grid."""
        structure_maps = []
        for seq in sequences.values():
            mapping = {}
            seq_idx = 0
            for align_idx, char in enumerate(seq):
                if char != "-":
                    mapping[seq_idx] = align_idx
                    seq_idx += 1
            structure_maps.append(mapping)
        return structure_maps

    @staticmethod
    def _parse_ca_coords(
        alignment_pdb: Path,
        structure_maps: List[Dict[int, int]],
        alignment_length: int,
        num_structures: int,
    ) -> List[List[Optional[np.ndarray]]]:
        """[alignment_pos][structure_idx] = CA coordinate, or None for a gap.
        Assumes PDB chains correspond to sequences in order - Mustang
        outputs Chain A, B, C... in the same order structures were input."""
        coords = [
            [None for _ in range(num_structures)] for _ in range(alignment_length)
        ]

        current_chain_idx = -1
        current_residue_idx = -1  # Index in the SEQUENCE (ignoring gaps)
        last_chain_id = None

        with open(alignment_pdb, "r") as f:
            for line in f:
                if not (line.startswith("ATOM") and line[12:16].strip() == "CA"):
                    continue

                chain_id = line[21]
                if chain_id != last_chain_id:
                    current_chain_idx += 1
                    current_residue_idx = -1
                    last_chain_id = chain_id
                current_residue_idx += 1

                if current_chain_idx >= num_structures:
                    break  # Should not happen if files match
                if current_chain_idx >= len(structure_maps):
                    continue
                if current_residue_idx not in structure_maps[current_chain_idx]:
                    continue

                align_idx = structure_maps[current_chain_idx][current_residue_idx]
                x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
                coords[align_idx][current_chain_idx] = np.array([x, y, z])

        return coords

    @staticmethod
    def _rmsf_for_column(col_coords: List[np.ndarray]) -> float:
        if len(col_coords) < 2:
            return 0.0  # Not enough data for variance
        mean_pos = np.mean(col_coords, axis=0)
        sq_diffs = [np.sum((c - mean_pos) ** 2) for c in col_coords]
        # RMSF is the square root of the mean squared deviation
        return float(np.sqrt(np.mean(sq_diffs)))

    def calculate_residue_rmsf(
        self, alignment_pdb: Path, alignment_afasta: Path
    ) -> Tuple[List[float], List[str]]:
        """
        Calculate Root Mean Square Fluctuation (RMSF) per residue/column.

        Args:
            alignment_pdb: Path to alignment PDB file (must have multiple chains)
            alignment_afasta: Path to alignment AFASTA file

        Returns:
            Tuple of (rmsf_values, conservation_labels)
        """
        try:
            sequences = self._parse_afasta_sequences(alignment_afasta)
            if not sequences:
                logger.error("No sequences found in AFASTA file")
                return [], []

            alignment_length = len(next(iter(sequences.values())))
            structure_maps = self._build_structure_maps(sequences)
            coords = self._parse_ca_coords(
                alignment_pdb, structure_maps, alignment_length, len(sequences)
            )

            rmsf_values = [
                self._rmsf_for_column([c for c in col if c is not None])
                for col in coords
            ]
            return rmsf_values, list(sequences.keys())

        except Exception:
            logger.exception("Failed to calculate residue RMSF")
            return [], []
