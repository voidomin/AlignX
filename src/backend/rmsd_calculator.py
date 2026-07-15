import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from Bio.PDB import PDBParser
from src.utils.logger import get_logger

logger = get_logger()


def calculate_rmsd_from_superposition(
    pdb_file: Path, num_expected: int
) -> Optional[pd.DataFrame]:
    """
    Fallback: Calculate pairwise RMSD matrix directly from superimposed PDB coordinates
    assuming sequential atom matching (only for structures with identical residue/atom counts).

    Args:
        pdb_file: Path to superimposed PDB
        num_expected: Number of structures to expect
    """
    try:
        from Bio.PDB import PDBParser

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("aln", str(pdb_file))

        # Extract entities (Models or Chains)
        models = list(structure.get_models())
        if len(models) >= num_expected:
            entities = models[:num_expected]
        else:
            # Try chains in model 0
            chains = list(models[0].get_chains())
            if len(chains) >= num_expected:
                entities = chains[:num_expected]
            else:
                return None

        # Extract CA coords
        coords = []
        for e in entities:
            cas = [a.coord for a in e.get_atoms() if a.name == "CA"]
            coords.append(np.array(cas))

        # Verify identical lengths for simple subtraction
        n = len(coords)
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                if len(coords[i]) == len(coords[j]) and len(coords[i]) > 0:
                    diff = coords[i] - coords[j]
                    rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
                    matrix[i, j] = matrix[j, i] = rmsd
        return pd.DataFrame(matrix)
    except Exception as e:
        logger.exception("Manual RMSD calc failed")
        return None


def _try_parse_rmsd_row(line: str) -> Optional[List[float]]:
    """Parses one Mustang log line as an RMSD-matrix row - a numeric row
    index (1, 2, 3...) followed by RMSD values (float or '---') - or
    returns None if the line doesn't match that shape."""
    parts = line.split()
    if not parts:
        return None
    try:
        int(parts[0])
    except ValueError:
        return None
    if len(parts) <= 1:
        return None

    row = []
    for p in parts[1:]:
        if p == "---":
            row.append(0.0)
            continue
        try:
            row.append(float(p))
        except ValueError:
            # Not a float, might be part of another line
            break
    return row or None


def parse_mustang_log_for_rmsd(log_file: Path) -> Optional[pd.DataFrame]:
    """
    Parse Mustang's log file (stdout) to extract the pairwise RMSD table.
    Mustang outputs a table like:

    > RMSD TABLE:
    1   0.00   0.85   1.20
    2   0.85   0.00   0.90
    3   1.20   0.90   0.00
    """
    try:
        if not log_file.exists():
            return None

        with open(log_file, "r") as f:
            lines = f.readlines()

        potential_matrix = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            row = _try_parse_rmsd_row(line)
            if row:
                potential_matrix.append(row)

        if not potential_matrix:
            return None

        # Find the largest square submatrix at the end (typical Mustang output)
        n = len(potential_matrix[-1])
        if len(potential_matrix) >= n:
            matrix = potential_matrix[-n:]
            return pd.DataFrame(matrix)

        return None

    except Exception:
        logger.exception("Failed to parse Mustang log")
        return None


def parse_rmsd_matrix(output_dir: Path, pdb_ids: List[str]) -> Optional[pd.DataFrame]:
    """
    Unified entry point for extracting structural similarity data.
    Strategies:
    1. Parse Mustang .rms_rot (Most precise)
    2. Parse Mustang .log (Standard)
    3. Bio3D CSV (Legacy/Fallback)
    4. Calculate from superposition (Absolute fallback)
    """
    # 1. Mustang's precise .rms_rot file
    rms_rot = output_dir / "alignment.rms_rot"
    if rms_rot.exists():
        df = parse_rms_rot_file(rms_rot, pdb_ids)
        if df is not None:
            return df

    # 2. Mustang's log file output
    log_file = output_dir / "mustang.log"
    if log_file.exists():
        df = parse_mustang_log_for_rmsd(log_file)
        if df is not None and len(df) == len(pdb_ids):
            df.index, df.columns = pdb_ids, pdb_ids
            return df

    # 3. Calculation from PDB/FASTA (PyRMSD)
    alignment_pdb = output_dir / "alignment.pdb"
    alignment_fasta = output_dir / "alignment.afasta"
    if alignment_pdb.exists() and alignment_fasta.exists():
        df = calculate_structure_rmsd(alignment_pdb, alignment_fasta)
        if df is not None:
            return df

    logger.error("All RMSD parsing strategies failed.")
    return None


def _parse_matrix_value(val: str) -> float:
    if val == "---" or "---" in val:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def _matrix_row(raw_row: List[str], n: int) -> List[float]:
    """Parses up to `n` values from a raw row, padding with 0.0 if the row
    (or the whole matrix, via the caller) came up short - a truncated
    .rms_rot file shouldn't crash the whole parse."""
    row = [_parse_matrix_value(v) for v in raw_row[:n]]
    row += [0.0] * (n - len(row))
    return row


def _extract_rms_rot_data_rows(lines: List[str], matrix_start: int) -> List[List[str]]:
    data_rows = []
    for line in lines[matrix_start:]:
        if "|" not in line:
            continue
        parts = line.split("|")[1].strip().split()
        if parts:
            data_rows.append(parts)
    return data_rows


def parse_rms_rot_file(
    rms_rot_file: Path, pdb_ids: List[str]
) -> Optional[pd.DataFrame]:
    """
    Parse RMSD matrix from Mustang's .rms_rot file with robust line-based detection.
    """
    try:
        with open(rms_rot_file, "r") as f:
            content = f.read()

        if "RMSD matrix" not in content:
            return None

        lines = content.splitlines()
        matrix_start = next(
            (i for i, line in enumerate(lines) if "RMSD matrix" in line), None
        )
        if matrix_start is None:
            return None

        data_rows = _extract_rms_rot_data_rows(lines, matrix_start)
        if not data_rows:
            return None

        n = len(pdb_ids)
        matrix = [_matrix_row(row, n) for row in data_rows[:n]]
        while len(matrix) < n:
            matrix.append([0.0] * n)

        return pd.DataFrame(matrix, index=pdb_ids, columns=pdb_ids)

    except Exception:
        logger.exception("Failed to parse .rms_rot file")
        return None


# Re-implementing robust RMSD using aligned FASTA + Superimposed PDB
def _build_residue_mapping(alignment: list, seq_len: int) -> List[List[Optional[int]]]:
    """mapping[struct_idx][col_idx] = 0-based residue index in that
    structure's source sequence, or None for a gap column."""
    mapping = [[None] * seq_len for _ in alignment]
    for i, record in enumerate(alignment):
        res_counter = 0  # 0-based index of residues in the PDB structure
        for col, char in enumerate(record.seq):
            if char != "-":
                mapping[i][col] = res_counter
                res_counter += 1
    return mapping


def _select_structures(structure, num_structures: int) -> list:
    """Picks Models or Chains as the per-structure entities to compare,
    depending on which count matches the alignment's structure count -
    Mustang's output PDB sometimes uses one Model per structure, sometimes
    one Chain."""
    models = list(structure.get_models())
    if len(models) == num_structures:
        return models
    if 0 < len(models) < num_structures:
        chains = list(models[0].get_chains())
        if len(chains) >= num_structures:
            logger.info(
                f"RMSD: Using chains from Model 0 as structures (Found {len(chains)})"
            )
            return chains
        logger.warning(
            f"RMSD: Structure count mismatch. FASTA={num_structures}, PDB Models={len(models)}, PDB Chains M0={len(chains)}"
        )
    return models


def _common_ca_coords(
    mapping: List[List[Optional[int]]],
    structure_cas: List[list],
    i: int,
    j: int,
    seq_len: int,
) -> Tuple[List[Any], List[Any]]:
    """CA coordinate pairs for aligned columns where both structures have a
    residue (no gap) and the mapped residue index is in bounds."""
    coords_i, coords_j = [], []
    for col in range(seq_len):
        res_i_idx = mapping[i][col]
        res_j_idx = mapping[j][col]
        if res_i_idx is None or res_j_idx is None:
            continue
        if res_i_idx >= len(structure_cas[i]) or res_j_idx >= len(structure_cas[j]):
            continue
        coords_i.append(structure_cas[i][res_i_idx].coord)
        coords_j.append(structure_cas[j][res_j_idx].coord)
    return coords_i, coords_j


def calculate_structure_rmsd(
    pdb_file: Path, fasta_file: Path
) -> Optional[pd.DataFrame]:
    """
    Calculate RMSD using the aligned FASTA to map residues between superimposed structures.
    """
    try:
        from Bio import SeqIO

        alignment = list(SeqIO.parse(fasta_file, "fasta"))
        num_structures = len(alignment)
        if num_structures < 2:
            return None

        seq_len = len(alignment[0].seq)
        mapping = _build_residue_mapping(alignment, seq_len)

        from Bio.PDB import PDBParser

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("aln", str(pdb_file))
        structures = _select_structures(structure, num_structures)
        n_calc = min(len(structures), num_structures)

        # Pre-extract CA atoms for speed (works for both Model and Chain objects)
        structure_cas = [
            [atom for atom in entity.get_atoms() if atom.name == "CA"]
            for entity in structures
        ]

        matrix = np.zeros((num_structures, num_structures))
        for i in range(n_calc):
            for j in range(i + 1, n_calc):
                coords_i, coords_j = _common_ca_coords(
                    mapping, structure_cas, i, j, seq_len
                )
                if coords_i:
                    diff = np.array(coords_i) - np.array(coords_j)
                    rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
                    matrix[i, j] = rmsd
                    matrix[j, i] = rmsd
                else:
                    matrix[i, j] = 0  # Should not happen if aligned

        names = [r.id for r in alignment]
        return pd.DataFrame(matrix, index=names, columns=names)

    except Exception:
        logger.exception("PyRMSD Error")
        return None


# --- CONTACT MAPS & DIFFERENCE-DISTANCE MATRICES ---

# Above this many residues/columns, a dense NxN matrix serialized to JSON
# gets prohibitively large (8 bytes/float * N^2 - a 5000-residue complex
# would be ~200MB) - return a thresholded sparse list instead.
MAX_DENSE_MATRIX_RESIDUES = 3000
DEFAULT_CONTACT_THRESHOLD_A = 8.0
DEFAULT_NOTABLE_SHIFT_A = 3.0


def calculate_pairwise_distance_matrix(coords: np.ndarray) -> np.ndarray:
    """NxN Euclidean distance matrix for one set of coordinates."""
    if len(coords) == 0:
        return np.zeros((0, 0))
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    return np.sqrt(np.sum(diff**2, axis=-1))


def calculate_contact_map(
    coords: np.ndarray, threshold: float = DEFAULT_CONTACT_THRESHOLD_A
) -> np.ndarray:
    """Binary CA-CA contact map (1 = within `threshold` Angstroms), with the
    diagonal (self-contacts) explicitly zeroed."""
    distances = calculate_pairwise_distance_matrix(coords)
    contacts = (distances < threshold).astype(int)
    np.fill_diagonal(contacts, 0)
    return contacts


def calculate_difference_distance_matrix(
    coords1: np.ndarray, coords2: np.ndarray
) -> np.ndarray:
    """Element-wise difference between two structures' own pairwise
    CA-CA distance matrices, over the same (already-aligned) column
    ordering - reveals domain movements a single global RMSD hides,
    since a rigid-body shift of one domain leaves its internal
    distances unchanged while every distance to the other domain
    shifts together."""
    return np.abs(
        calculate_pairwise_distance_matrix(coords1)
        - calculate_pairwise_distance_matrix(coords2)
    )


def get_structure_contact_map(
    alignment_pdb: Path,
    pdb_ids: List[str],
    pdb_id: str,
    threshold: float = DEFAULT_CONTACT_THRESHOLD_A,
    max_residues: int = MAX_DENSE_MATRIX_RESIDUES,
) -> Optional[Dict[str, Any]]:
    """
    A single structure's own CA-CA contact map, keyed to its real residue
    order (not the alignment's gapped columns - a contact map describes
    one structure's own geometry).

    `pdb_ids` must be the run's original, order-matched structure id list
    (Mustang's own PDB/FASTA output preserves this input order, but its
    FASTA headers get their own filename-derived labels - e.g. "4hhb.pdb"
    lowercased - so `pdb_id` is resolved to a position in `pdb_ids` here
    rather than by matching against alignment_fasta's record text).

    Returns a dict with either a dense `matrix` (residue_count <=
    max_residues) or a sparse `contacts` list of [i, j] index pairs
    (above that cap) - never both. Returns None if `pdb_id` isn't in
    `pdb_ids` or has no CA atoms.
    """
    try:
        if pdb_id not in pdb_ids:
            return None
        idx = pdb_ids.index(pdb_id)

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("aln", str(alignment_pdb))
        entities = _select_structures(structure, len(pdb_ids))
        if idx >= len(entities):
            return None

        coords = np.array(
            [atom.coord for atom in entities[idx].get_atoms() if atom.name == "CA"]
        )
        if len(coords) == 0:
            return None

        n = len(coords)
        if n > max_residues:
            distances = calculate_pairwise_distance_matrix(coords)
            i_idx, j_idx = np.where(np.triu(distances < threshold, k=1))
            return {
                "pdb_id": pdb_id,
                "residue_count": n,
                "threshold_a": threshold,
                "capped": True,
                "matrix": None,
                "contacts": np.stack([i_idx, j_idx], axis=1).tolist(),
            }

        contacts = calculate_contact_map(coords, threshold)
        return {
            "pdb_id": pdb_id,
            "residue_count": n,
            "threshold_a": threshold,
            "capped": False,
            "matrix": contacts.tolist(),
            "contacts": None,
        }
    except Exception:
        logger.exception(f"Failed to build contact map for {pdb_id}")
        return None


def get_difference_distance_matrix(
    alignment_pdb: Path,
    alignment_fasta: Path,
    pdb_ids: List[str],
    pdb_id_a: str,
    pdb_id_b: str,
    max_residues: int = MAX_DENSE_MATRIX_RESIDUES,
    notable_shift_a: float = DEFAULT_NOTABLE_SHIFT_A,
) -> Optional[Dict[str, Any]]:
    """
    Difference-distance matrix between two structures in the same
    alignment, over their commonly-aligned columns (reuses
    _build_structure_data/_common_aligned_coords, same basis as the
    existing pairwise TM-score/GDT-TS calculation).

    `pdb_ids` must be the run's original, order-matched structure id list
    (see get_structure_contact_map's docstring for why - `pdb_id_a`/
    `pdb_id_b` are resolved to positions in `pdb_ids`, assumed to match
    alignment_fasta's record order 1:1, rather than by matching against
    the FASTA's own record text).

    Returns a dict with either a dense `matrix` (column_count <=
    max_residues) or a sparse `differences` list of [i, j, diff] triples
    for shifts above `notable_shift_a` Angstroms (above that cap) - never
    both. Returns None if either id isn't in `pdb_ids` or they share no
    aligned columns.
    """
    try:
        if pdb_id_a not in pdb_ids or pdb_id_b not in pdb_ids:
            return None
        idx_a, idx_b = pdb_ids.index(pdb_id_a), pdb_ids.index(pdb_id_b)

        from Bio import SeqIO

        alignment = list(SeqIO.parse(alignment_fasta, "fasta"))
        if len(alignment) < 2 or idx_a >= len(alignment) or idx_b >= len(alignment):
            return None
        seq_len = len(alignment[0].seq)

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("aln", str(alignment_pdb))
        entities = _select_structures(structure, len(alignment))

        structure_data = _build_structure_data(alignment, entities, seq_len)
        c1, c2 = _common_aligned_coords(
            structure_data[idx_a], structure_data[idx_b], seq_len
        )
        if not c1:
            return None

        c1, c2 = np.array(c1), np.array(c2)
        n = len(c1)
        if n > max_residues:
            diff_matrix = calculate_difference_distance_matrix(c1, c2)
            i_idx, j_idx = np.where(np.triu(diff_matrix > notable_shift_a, k=1))
            differences = [
                [int(i), int(j), float(diff_matrix[i, j])]
                for i, j in zip(i_idx, j_idx, strict=False)
            ]
            return {
                "pdb_id_a": pdb_id_a,
                "pdb_id_b": pdb_id_b,
                "column_count": n,
                "capped": True,
                "matrix": None,
                "differences": differences,
            }

        diff_matrix = calculate_difference_distance_matrix(c1, c2)
        return {
            "pdb_id_a": pdb_id_a,
            "pdb_id_b": pdb_id_b,
            "column_count": n,
            "capped": False,
            "matrix": diff_matrix.tolist(),
            "differences": None,
        }
    except Exception:
        logger.exception(
            f"Failed to build difference-distance matrix for {pdb_id_a}/{pdb_id_b}"
        )
        return None


# --- SCIENTIFIC QUALITY METRICS ---


def calculate_tm_score(
    coords1: np.ndarray, coords2: np.ndarray, l_target: int
) -> float:
    """
    Calculate TM-score between two set of CA coordinates.
    Formula: TM = (1/l_target) * sum(1 / (1 + (d_i/d0)^2))
    """
    if len(coords1) == 0 or l_target == 0:
        return 0.0

    # Standard TM-score normalization factor
    if l_target > 15:
        d0 = 1.24 * (l_target - 15) ** (1 / 3) - 1.8
    else:
        d0 = 0.5

    d0_sq = d0**2
    distances_sq = np.sum((coords1 - coords2) ** 2, axis=1)

    score = np.sum(1.0 / (1.0 + distances_sq / d0_sq))
    return score / l_target


def calculate_gdt_ts(coords1: np.ndarray, coords2: np.ndarray, l_target: int) -> float:
    """
    Calculate Global Distance Test - Total Score (GDT-TS).
    Formula: (P1 + P2 + P4 + P8) / 4
    where Px is the percentage of residues with distance < x Angstroms.
    """
    if len(coords1) == 0 or l_target == 0:
        return 0.0

    distances = np.sqrt(np.sum((coords1 - coords2) ** 2, axis=1))

    p1 = np.sum(distances < 1.0) / l_target
    p2 = np.sum(distances < 2.0) / l_target
    p4 = np.sum(distances < 4.0) / l_target
    p8 = np.sum(distances < 8.0) / l_target

    return (p1 + p2 + p4 + p8) / 4.0


def _build_structure_data(
    alignment: list, entities: list, seq_len: int
) -> List[Dict[str, Any]]:
    """Maps each aligned sequence's non-gap columns to that structure's
    actual CA coordinates, for later pairwise TM-score/GDT-TS comparison."""
    structure_data = []
    for record, entity in zip(alignment, entities, strict=False):
        # Original length (excluding gaps)
        l_orig = len(str(record.seq).replace("-", ""))
        cas = [atom.coord for atom in entity.get_atoms() if atom.name == "CA"]

        # Each entry of aligned_coords holds either a coordinate or None
        aligned_coords = [None] * seq_len
        res_idx = 0
        for col, char in enumerate(record.seq):
            if char != "-" and res_idx < len(cas):
                aligned_coords[col] = cas[res_idx]
                res_idx += 1

        structure_data.append(
            {"id": record.id, "aligned_coords": aligned_coords, "L_orig": l_orig}
        )
    return structure_data


def _common_aligned_coords(
    target: Dict[str, Any], other: Dict[str, Any], seq_len: int
) -> Tuple[List[Any], List[Any]]:
    """Coordinate pairs present (non-gap) in both structures at the same
    aligned column - the basis for a pairwise TM-score/GDT-TS comparison."""
    c1, c2 = [], []
    for col in range(seq_len):
        t_coord = target["aligned_coords"][col]
        o_coord = other["aligned_coords"][col]
        if t_coord is not None and o_coord is not None:
            c1.append(t_coord)
            c2.append(o_coord)
    return c1, c2


def _average_quality_scores(
    target: Dict[str, Any], structure_data: List[Dict[str, Any]], seq_len: int
) -> Dict[str, float]:
    """Average TM-score/GDT-TS of `target` against every other structure in
    the alignment (Mustang gives a global superposition, so this is a
    reasonable proxy for "how consistent is this structure with the rest of
    the aligned core"), over their commonly-aligned columns."""
    tm_scores, gdt_scores = [], []
    for other in structure_data:
        if other is target:
            continue
        c1, c2 = _common_aligned_coords(target, other, seq_len)
        if not c1:
            continue
        c1, c2 = np.array(c1), np.array(c2)
        tm_scores.append(calculate_tm_score(c1, c2, target["L_orig"]))
        gdt_scores.append(calculate_gdt_ts(c1, c2, target["L_orig"]))

    if not tm_scores:
        return {"tm_score": 0.0, "gdt_ts": 0.0}
    return {
        "tm_score": float(np.mean(tm_scores)),
        "gdt_ts": float(np.mean(gdt_scores)),
    }


def calculate_alignment_quality_metrics(
    pdb_file: Path, fasta_file: Path
) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Calculate scientific quality metrics for each structure in the alignment.
    Returns: { 'pdb_id': {'tm_score': 0.85, 'gdt_ts': 0.92, 'rmsd': 1.2} }
    """
    try:
        from Bio import SeqIO

        alignment = list(SeqIO.parse(fasta_file, "fasta"))
        if len(alignment) < 2:
            return None

        # Parse PDB for coordinates
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("aln", str(pdb_file))

        # Extract models or chains
        models = list(structure.get_models())
        if len(models) == len(alignment):
            entities = models
        else:
            chains = list(models[0].get_chains())
            entities = chains[: len(alignment)]

        seq_len = len(alignment[0].seq)
        structure_data = _build_structure_data(alignment, entities, seq_len)

        return {
            target["id"]: _average_quality_scores(target, structure_data, seq_len)
            for target in structure_data
        }

    except Exception:
        logger.exception("Failed to calculate quality metrics")
        return None
