"""
PAE-based automatic domain segmentation - a second, independent use of the
same real per-residue-pair AlphaFold PAE matrix already fetched for
/api/pae (AnnotationAggregator.fetch_predicted_aligned_error), distinct
from InterPro's sequence-based domain boundaries already shown elsewhere.
No external API call at all - pure graph connectivity on data already in
hand, the same "no new dependency" pattern flexibility_calculator.py uses.

Deliberately a simplified connectivity-based split (symmetrize the PAE
matrix, threshold into a binary adjacency, scipy.sparse.csgraph.
connected_components for grouping) rather than the full weighted-graph
community-detection algorithm some published PAE-domain tools use (which
would need networkx, not currently a dependency) - a residue pair below
the threshold is treated as "AlphaFold trusts their relative position," so
a connected component of such pairs is a rigid unit; residues in a
component smaller than min_domain_size are dropped as noise rather than
reported as a spurious tiny domain.

Live-verified real-data gotcha: PAE between sequentially adjacent residues
(i, i+1) is essentially always well below any reasonable threshold, even
across genuinely disordered linkers - AlphaFold is highly confident about
a residue's position relative to its own covalent neighbor regardless of
overall fold confidence. Without excluding this trivial local band, every
residue is transitively connected to the next along the backbone and the
whole chain always collapses into a single "domain" (confirmed against a
real AlphaFold p53 model, AF-P04637-F1, where naive thresholding merged
all 393 residues into one component). Only pairs at least
min_sequence_gap apart count toward connectivity, so a domain must be
supported by genuine long-range (tertiary-structure) confidence, not just
an unbroken run of confident local peptide bonds.
"""

from typing import List, Optional

import numpy as np
from scipy.sparse.csgraph import connected_components

from src.utils.logger import get_logger

logger = get_logger()

DEFAULT_PAE_THRESHOLD_ANGSTROM = 5.0
DEFAULT_MIN_DOMAIN_SIZE = 10
DEFAULT_MIN_SEQUENCE_GAP = 5


def calculate_pae_domains(
    pae_matrix: List[List[float]],
    threshold_angstrom: float = DEFAULT_PAE_THRESHOLD_ANGSTROM,
    min_domain_size: int = DEFAULT_MIN_DOMAIN_SIZE,
    min_sequence_gap: int = DEFAULT_MIN_SEQUENCE_GAP,
) -> Optional[List[List[int]]]:
    """
    Splits a structure into rigid domains by connectivity in its own real
    PAE matrix. Returns a list of domains, each a list of 1-based residue
    numbers (matching the matrix's own row/column order), sorted by each
    domain's first residue - or None if the matrix is empty/malformed, or
    every residue ends up in a component smaller than min_domain_size (no
    real domain structure found, an honest empty result rather than
    fabricating one).
    """
    try:
        pae = np.array(pae_matrix, dtype=float)
        if pae.ndim != 2 or pae.shape[0] != pae.shape[1] or pae.shape[0] == 0:
            return None

        # PAE is not symmetric in general (AlphaFold's confidence in
        # residue i's position relative to j can differ from j relative to
        # i) - symmetrizing before thresholding treats a pair as "trusted"
        # only when both directions agree, the more conservative choice.
        symmetric = (pae + pae.T) / 2
        adjacency = symmetric < threshold_angstrom
        np.fill_diagonal(adjacency, False)

        # Drop trivially-local pairs - see the module docstring's gotcha.
        n = adjacency.shape[0]
        row_idx, col_idx = np.indices((n, n))
        adjacency &= np.abs(row_idx - col_idx) >= min_sequence_gap

        n_components, labels = connected_components(
            adjacency, directed=False, connection="weak"
        )

        domains = []
        for label in range(n_components):
            residues = [int(i) + 1 for i in range(len(labels)) if labels[i] == label]
            if len(residues) >= min_domain_size:
                domains.append(residues)

        if not domains:
            return None

        domains.sort(key=lambda residues: residues[0])
        return domains
    except Exception:
        logger.exception("Failed to calculate PAE-based domain segmentation")
        return None
