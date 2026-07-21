"""
Gaussian Network Model (GNM) flexibility prediction - a coarse-grained
Normal Mode Analysis over a structure's own CA coordinates. Unlike every
other external integration in this codebase, this needs no API call at
all: it's pure linear algebra on coordinates already downloaded, using
dependencies already in requirements.txt (numpy, scipy).

Standard GNM (Tirion 1996, "Large amplitude elastic motions in proteins
from a single-parameter atomic analysis"): build an N×N Kirchhoff/
connectivity matrix from CA-CA distances within a cutoff radius,
eigendecompose it, and use the pseudo-inverse's diagonal as each
residue's predicted mean-square fluctuation - a relative "how much does
this position move" prediction, the same information content a real
crystallographic B-factor carries, just predicted from geometry alone
rather than measured. This is a prediction, not ground truth - every
caller should label it honestly as such, the same way this codebase
already treats the heuristic pocket finder and M-CSA's partial coverage.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from Bio.PDB import PDBParser
from scipy.linalg import eigh

from src.utils.logger import get_logger

logger = get_logger()

DEFAULT_CUTOFF_ANGSTROM = 10.0
# Eigenvalues at/below this are treated as the model's rigid-body
# translation/rotation modes (theoretically exactly zero; numerically a
# small positive or negative residual) - excluded from the pseudo-inverse,
# the standard GNM convention, since they carry no internal-flexibility
# information.
_ZERO_EIGENVALUE_THRESHOLD = 1e-6


def calculate_gnm_flexibility(
    pdb_path: Path, cutoff_angstrom: float = DEFAULT_CUTOFF_ANGSTROM
) -> Optional[Dict[str, Any]]:
    """
    Real-time GNM flexibility prediction for one structure's first model.
    Returns {"residue_numbers": [...], "flexibility": [...normalized to
    0-1...], "b_factor": [...same length, or None if the structure carries
    no real per-residue B-factor...]} - `b_factor` is read directly off
    the same parsed structure (already-available data for real PDB
    entries, not a separate fetch), included as a free real-world
    comparison point against the prediction, not a separate signal to
    fetch. Returns None if the structure has fewer than 3 CA-bearing
    residues, or on any parse/computation failure.
    """
    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("s", str(pdb_path))
        model = next(iter(structure))

        residues = [
            residue
            for chain in model
            for residue in chain
            if residue.get_id()[0] == " " and "CA" in residue
        ]
        if len(residues) < 3:
            return None

        coords = np.array([r["CA"].get_coord() for r in residues])
        residue_numbers = [r.get_id()[1] for r in residues]
        n = len(coords)

        diff = coords[:, None, :] - coords[None, :, :]
        distances = np.sqrt(np.sum(diff**2, axis=-1))

        # distances > 0 already excludes the diagonal (self-distance is 0),
        # so off-diagonal entries are set first, then the diagonal is the
        # negated row sum - the standard Kirchhoff-matrix construction.
        kirchhoff = np.where(
            (distances <= cutoff_angstrom) & (distances > 0), -1.0, 0.0
        )
        np.fill_diagonal(kirchhoff, -kirchhoff.sum(axis=1))

        # Kirchhoff is real and symmetric by construction (built from a
        # symmetric distance matrix) - eigh is the correct, faster solver
        # for that case rather than a general eig.
        eigenvalues, eigenvectors = eigh(kirchhoff)

        nonzero_mask = eigenvalues > _ZERO_EIGENVALUE_THRESHOLD
        if not np.any(nonzero_mask):
            return None

        inv_eigenvalues = np.zeros(n)
        inv_eigenvalues[nonzero_mask] = 1.0 / eigenvalues[nonzero_mask]
        # diag(V @ diag(1/lambda) @ V.T) without materializing the full
        # N x N pseudo-inverse matrix.
        msf = np.sum((eigenvectors**2) * inv_eigenvalues[np.newaxis, :], axis=1)

        msf_min, msf_max = msf.min(), msf.max()
        if msf_max > msf_min:
            flexibility = (msf - msf_min) / (msf_max - msf_min)
        else:
            flexibility = np.zeros(n)

        b_factors = [r["CA"].get_bfactor() for r in residues]
        has_real_b_factor = any(b not in (0.0, None) for b in b_factors)

        return {
            "residue_numbers": residue_numbers,
            "flexibility": flexibility.tolist(),
            "b_factor": b_factors if has_real_b_factor else None,
        }
    except Exception:
        logger.exception(f"Failed to calculate GNM flexibility for {pdb_path}")
        return None
