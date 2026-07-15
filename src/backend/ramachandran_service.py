import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger()


class RamachandranService:
    """
    Service for calculating Ramachandran phi/psi angles and identifying outliers.
    """

    def __init__(self):
        from Bio.PDB import PDBParser

        self.parser = PDBParser(QUIET=True)

    def calculate_torsion_angles(self, pdb_file: Path) -> Dict[str, pd.DataFrame]:
        """
        Calculate phi/psi angles for all chains in a PDB file.

        Returns:
            Dict mapping chain IDs to DataFrames with [residue_index, residue_name, phi, psi]
        """
        try:
            from Bio.PDB import Polypeptide

            structure = self.parser.get_structure("protein", str(pdb_file))
            results = {}
            for model in structure:
                for chain in model:
                    angles = self._chain_torsion_angles(chain, Polypeptide)
                    if angles:
                        results[chain.id] = pd.DataFrame(angles)
            return results
        except Exception:
            logger.exception(f"Failed to calculate torsion angles for {pdb_file}")
            return {}

    def _chain_torsion_angles(self, chain, polypeptide_module) -> list:
        """Phi/psi angle rows for every residue in one chain that has at
        least one resolvable angle (termini only ever have one of the
        two)."""
        # BioPython's Polypeptide module makes this easy
        poly = polypeptide_module.Polypeptide(chain)
        angles = []
        for i, (phi, psi) in enumerate(poly.get_phi_psi_list()):
            row = self._torsion_row(poly[i], phi, psi)
            if row:
                angles.append(row)
        return angles

    def _torsion_row(
        self, res, phi: Optional[float], psi: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        # Convert radians to degrees, handle None for termini
        phi_deg = np.degrees(phi) if phi is not None else None
        psi_deg = np.degrees(psi) if psi is not None else None
        if phi_deg is None and psi_deg is None:
            return None
        return {
            "residue_id": res.get_id()[1],
            "residue_name": res.get_resname(),
            "phi": phi_deg,
            "psi": psi_deg,
            "region": self._classify_region(phi_deg, psi_deg),
            "secondary_structure": self._classify_secondary_structure(phi_deg, psi_deg),
        }

    def _classify_region(self, phi: Optional[float], psi: Optional[float]) -> str:
        """
        Very basic classification of Ramachandran regions.
        In a production app, this would use precise polygon boundaries (e.g. from Top8000).
        For now, we use a heuristic approach.
        """
        if phi is None or psi is None:
            return "Terminal"

        # Simplified regions based on standard boundaries
        # Alpha Helix region
        if -100 < phi < -30 and -80 < psi < 20:
            return "Favored (Alpha)"
        # Beta Sheet region
        if -160 < phi < -50 and 90 < psi < 180:
            return "Favored (Beta)"
        # Left-handed Alpha region
        if 40 < phi < 80 and 20 < psi < 100:
            return "Favored (L-Alpha)"

        # Generous "Allowed" regions
        if -180 < phi < 0 or (40 < phi < 100 and -20 < psi < 100):
            return "Allowed"

        return "Outlier"

    def _classify_secondary_structure(
        self, phi: Optional[float], psi: Optional[float]
    ) -> str:
        """
        Approximate per-residue secondary structure (Helix/Sheet/Coil) from
        phi/psi alone, using standard simplified backbone-region boundaries.
        This is deliberately distinct from _classify_region()'s
        favored/allowed/outlier Ramachandran-validity classification above -
        both read the same angle pair, but answer different questions (is
        this residue's backbone geometry favorable? vs. what kind of
        secondary structure does it look like?). Not DSSP-equivalent (no
        hydrogen-bonding geometry, no beta-bridge partner detection) - a
        backbone-torsion-only approximation, good enough for a quick %
        helix/sheet/coil summary, not for publication-grade SS assignment.
        """
        if phi is None or psi is None:
            return "Terminal"

        # Alpha-helix (and 3-10/pi helix) backbone region.
        if -100 <= phi <= -30 and -80 <= psi <= 15:
            return "Helix"
        # Beta-strand region - psi wraps around +-180, so both ends of the
        # range are included.
        if -180 <= phi <= -45 and (90 <= psi <= 180 or -180 <= psi <= -150):
            return "Sheet"

        return "Coil"

    def aggregate_secondary_structure(
        self, torsion_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Summarize %helix/%sheet/%coil across all chains, plus a per-chain
        breakdown. Terminal residues (only one resolvable angle) are
        excluded from every percentage's denominator, same as
        aggregate_metrics() excludes them from its own quality_score.
        """
        per_chain: Dict[str, Any] = {}
        total_helix = total_sheet = total_coil = total_residues = 0

        for chain_id, df in torsion_data.items():
            assigned = df[df["secondary_structure"] != "Terminal"]
            chain_total = len(assigned)
            helix = int((assigned["secondary_structure"] == "Helix").sum())
            sheet = int((assigned["secondary_structure"] == "Sheet").sum())
            coil = int((assigned["secondary_structure"] == "Coil").sum())

            per_chain[chain_id] = {
                "residue_count": chain_total,
                "helix_percent": (helix / chain_total * 100) if chain_total else 0,
                "sheet_percent": (sheet / chain_total * 100) if chain_total else 0,
                "coil_percent": (coil / chain_total * 100) if chain_total else 0,
            }

            total_helix += helix
            total_sheet += sheet
            total_coil += coil
            total_residues += chain_total

        return {
            "total_residues": total_residues,
            "helix_percent": (
                (total_helix / total_residues * 100) if total_residues else 0
            ),
            "sheet_percent": (
                (total_sheet / total_residues * 100) if total_residues else 0
            ),
            "coil_percent": (
                (total_coil / total_residues * 100) if total_residues else 0
            ),
            "per_chain": per_chain,
        }

    def aggregate_metrics(
        self, torsion_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Summarize quality metrics across all chains.
        """
        total_residues = 0
        favored_count = 0
        outliers = []

        for chain_id, df in torsion_data.items():
            total_residues += len(df)
            favored_count += len(df[df["region"].str.contains("Favored")])

            chain_outliers = df[df["region"] == "Outlier"]
            for _, row in chain_outliers.iterrows():
                outliers.append(
                    f"{row['residue_name']}{row['residue_id']} (Chain {chain_id})"
                )

        quality_score = (
            (favored_count / total_residues * 100) if total_residues > 0 else 0
        )

        return {
            "quality_score": quality_score,
            "total_residues": total_residues,
            "favored_percent": quality_score,
            "outlier_count": len(outliers),
            "outliers_list": outliers[:10],  # Show top 10
        }
