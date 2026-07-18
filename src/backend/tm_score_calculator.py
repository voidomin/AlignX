from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from Bio import SeqIO
from Bio.PDB import PDBParser

from src.utils.logger import get_logger

logger = get_logger()


def calculate_tm_score_matrix(
    alignment_pdb: Path, fasta_file: Path
) -> Optional[pd.DataFrame]:
    """
    Computes a real, independent pairwise TM-score matrix from Mustang's
    aligned structure file.

    This is deliberately NOT the same metric as
    rmsd_calculator.calculate_alignment_quality_metrics()'s existing
    tm_score - that one reuses Mustang's own column correspondence (from
    the FASTA alignment) to score each structure against the rest.
    tmtools.tm_align() instead performs its own independent, sequence-
    order-agnostic optimal-superposition search per pair, ignoring
    whatever correspondence Mustang produced - so it can surface a
    genuinely different (and often more informative) fold-similarity
    signal, especially for structures Mustang aligned less confidently.
    Both metrics are complementary, not redundant - shown side by side in
    the UI rather than one replacing the other.

    Returns a symmetric pdb_id x pdb_id DataFrame (self-comparisons = 1.0),
    or None if tmtools isn't installed, fewer than 2 structures are
    present, or the alignment file can't be parsed.
    """
    try:
        from tmtools import tm_align
        from tmtools.io import get_residue_data
    except ImportError:
        logger.warning(
            "tmtools not installed - skipping independent pairwise TM-score matrix"
        )
        return None

    try:
        alignment = list(SeqIO.parse(fasta_file, "fasta"))
        if len(alignment) < 2:
            return None

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("aln", str(alignment_pdb))

        models = list(structure.get_models())
        if len(models) == len(alignment):
            entities = models
        else:
            chains = list(models[0].get_chains())
            entities = chains[: len(alignment)]

        pdb_ids = [record.id for record in alignment]
        chain_data = []
        for entity in entities:
            coords, seq = get_residue_data(entity)
            chain_data.append((coords, seq))

        n = len(pdb_ids)
        matrix = np.ones((n, n))
        for i in range(n):
            coords_i, seq_i = chain_data[i]
            if len(coords_i) == 0:
                continue
            for j in range(i + 1, n):
                coords_j, seq_j = chain_data[j]
                if len(coords_j) == 0:
                    continue
                result = tm_align(coords_i, coords_j, seq_i, seq_j)
                # Average of both length-normalizations - matches the same
                # "average, not either-normalization-alone" convention
                # calculate_alignment_quality_metrics() already uses, so
                # the two TM-score sources stay comparable in scale.
                score = (result.tm_norm_chain1 + result.tm_norm_chain2) / 2
                matrix[i][j] = score
                matrix[j][i] = score

        return pd.DataFrame(matrix, index=pdb_ids, columns=pdb_ids)
    except Exception:
        logger.exception(f"Failed to calculate TM-score matrix for {alignment_pdb}")
        return None


def calculate_pairwise_tm_score(pdb_path_a: Path, pdb_path_b: Path):
    """Real, Mustang-independent TM-score + RMSD between two INDEPENDENT
    structure files (not two chains/models already inside one shared
    Mustang alignment.pdb, unlike calculate_tm_score_matrix above) - the
    primitive a "reference vs many" batch screen is built on, since it
    needs no prior N-way superposition at all. Each file's own first
    model's first chain is used. tm_align's own returned `.rmsd` is a
    real RMSD over its own optimal superposition, not borrowed from any
    other alignment. Returns None if tmtools isn't installed, either
    file has no resolvable residues, or parsing fails."""
    try:
        from tmtools import tm_align
        from tmtools.io import get_residue_data
    except ImportError:
        logger.warning("tmtools not installed - skipping standalone pairwise TM-score")
        return None

    try:
        parser = PDBParser(QUIET=True)
        structure_a = parser.get_structure("a", str(pdb_path_a))
        structure_b = parser.get_structure("b", str(pdb_path_b))
        chain_a = next(iter(next(iter(structure_a)).get_chains()))
        chain_b = next(iter(next(iter(structure_b)).get_chains()))
        coords_a, seq_a = get_residue_data(chain_a)
        coords_b, seq_b = get_residue_data(chain_b)
        if len(coords_a) == 0 or len(coords_b) == 0:
            return None

        result = tm_align(coords_a, coords_b, seq_a, seq_b)
        tm_score = (result.tm_norm_chain1 + result.tm_norm_chain2) / 2
        return {"tm_score": float(tm_score), "rmsd": float(result.rmsd)}
    except Exception:
        logger.exception(
            f"Failed to calculate standalone pairwise TM-score for "
            f"{pdb_path_a} vs {pdb_path_b}"
        )
        return None
