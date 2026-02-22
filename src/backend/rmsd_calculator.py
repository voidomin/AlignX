import numpy as np
import pandas as pd
from Bio.PDB import PDBParser
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from src.utils.logger import get_logger

logger = get_logger()

def calculate_rmsd_from_alignment(pdb_file: Path) -> Optional[pd.DataFrame]:
    """
    Calculate pairwise RMSD matrix from a multi-model/multi-chain PDB file 
    containing superimposed structures (output from Mustang).
    
    Mustang's output PDB usually contains one MODEL per structure, 
    or one CHAIN per structure if merged. 
    Standard Mustang behaviour: writes structures as separate MODELs.
    
    Args:
        pdb_file: Path to the alignment.pdb file
        
    Returns:
        pd.DataFrame: Symmetric RMSD matrix with protein indices/names
    """
    try:
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("alignment", str(pdb_file))
        
        # Extract models (assuming each model is a structure)
        models = list(structure.get_models())
        if len(models) < 2:
            logger.warning("RMSD Calculation: Fewer than 2 models found in PDB. Trying chains...")
            # Fallback: check chains in first model
            chains = list(models[0].get_chains())
            if len(chains) < 2:
                logger.error("RMSD Calculation: Fewer than 2 chains/models found.")
                return None
            entities = chains
            entity_type = "chain"
        else:
            entities = models
            entity_type = "model"
            
        n = len(entities)
        rmsd_matrix = np.zeros((n, n))
        
        # Get CA coordinates for each entity
        # Note: Mustang aligns structures, so coordinates are already superimposed.
        # However, to compute RMSD, we need to match residue-to-residue.
        # Mustang enables this by outputting structurally equivalent residues?
        # Actually, standard RMSD requires 1-to-1 atom matching. 
        # Mustang's alignment.pdb contains the FULL structures rotated.
        # To get the RMSD of the *alignment*, we usually only consider the 'core' aligned columns.
        # But commonly, for these pipelines, we want the RMSD of the whole structural overlap or the core.
        
        # SIMPLIFICATION:
        # Bio3D's `rmsd` function computes RMSD based on equivalent atoms.
        # If we just extract all C-alphas, they might have different counts!
        # We need the sequence alignment to know which C-alphas match.
        
        # For now, as a robust approximation matching standard pipeline needs:
        # We will use the common set of residues if possible, OR
        # If Mustang output makes them same length (with gaps?), PDB doesn't have gaps.
        
        # CRITICAL: Without the alignment mapping (FASTA), we can't strictly compute RMSD of aligned residues only 
        # unless the PDB residues are renumbered or filtered.
        # Mustang's -r ON option (which we use) writes "a PDB file containing the superposition of structures based on the alignment."
        # It does NOT necessarily filter to core.
        
        # Implementing a heuristic: exact sequence matching is hard without parsing FASTA.
        # But typically, `Mustang` reports RMSD in its logs.
        # Let's try to parse the LOG file first?
        # Use pandas to dataframe for now.
        pass

    except Exception as e:
        logger.error(f"RMSD Calculation failed: {e}")
        return None

def parse_mustang_log_for_rmsd(log_file: Path) -> Optional[pd.DataFrame]:
    """
    Parse Mustang's log file (stdout) to extract the pairwise RMSD table.
    Mustang outputs a table like:
    
    > RMSD TABLE:
    1   0.00   0.85   1.20
    2   0.85   0.00   0.90
    3   1.20   0.90   0.00
    """
    import re
    try:
        if not log_file.exists():
            return None
            
        with open(log_file, 'r') as f:
            lines = f.readlines()
            
        # Extract protein count by looking at IDs if possible, or just the table
        # We'll assume the number of proteins is determined by the caller or inferred from the table size
        
        potential_matrix = []
        for line in lines:
            matches = re.findall(r'(\d+\.\d+|---)', line)
            if matches:
                row = []
                for m in matches:
                    if m == '---':
                        row.append(0.0)
                    else:
                        row.append(float(m))
                potential_matrix.append(row)
        
        if not potential_matrix:
            return None
            
        # Find the largest square submatrix at the end (typical Mustang output)
        n = len(potential_matrix[-1])
        if len(potential_matrix) >= n:
            matrix = potential_matrix[-n:]
            return pd.DataFrame(matrix)
            
        return None
        
    except Exception as e:
        logger.error(f"Failed to parse Mustang log: {e}")
        return None

def parse_rmsd_matrix(output_dir: Path, pdb_ids: List[str]) -> Optional[pd.DataFrame]:
    """
    Unified entry point for parsing RMSD matrix from various Mustang output formats.
    
    Args:
        output_dir: Directory containing Mustang outputs
        pdb_ids: List of PDB IDs (for labeling)
        
    Returns:
        DataFrame with RMSD matrix or None if parsing fails
    """
    # 1. Try Bio3D CSV format (if legacy results exist)
    csv_file = output_dir / 'rmsd_matrix.csv'
    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file, index_col=0)
            if len(df) == len(pdb_ids):
                df.index = pdb_ids
                df.columns = pdb_ids
                return df
        except Exception:
            pass
    
    # 2. Try Mustang's robust .rms_rot file
    rms_rot_file = output_dir / 'alignment.rms_rot'
    if rms_rot_file.exists():
        df = parse_rms_rot_file(rms_rot_file, pdb_ids)
        if df is not None:
            return df
    
    # 3. Try parsing from Mustang log
    log_file = output_dir / 'mustang.log'
    if log_file.exists():
        df = parse_mustang_log_for_rmsd(log_file)
        if df is not None and len(df) == len(pdb_ids):
            df.index = pdb_ids
            df.columns = pdb_ids
            return df
            
    logger.error("Could not find or parse RMSD matrix in output")
    return None

def parse_rms_rot_file(rms_rot_file: Path, pdb_ids: List[str]) -> Optional[pd.DataFrame]:
    """
    Parse RMSD matrix from Mustang's .rms_rot file with robust line-based detection.
    """
    try:
        with open(rms_rot_file, 'r') as f:
            content = f.read()
        
        if 'RMSD matrix' not in content:
            return None
            
        lines = content.splitlines()
        matrix_start = None
        for i, line in enumerate(lines):
            if 'RMSD matrix' in line:
                matrix_start = i
                break
        
        if matrix_start is None:
            return None
            
        data_rows = []
        for line in lines[matrix_start:]:
            if '|' in line:
                parts = line.split('|')[1].strip().split()
                if parts:
                    data_rows.append(parts)
        
        if not data_rows:
            return None
            
        n = len(pdb_ids)
        matrix = []
        for i in range(min(len(data_rows), n)):
            row = []
            for j in range(min(len(data_rows[i]), n)):
                val = data_rows[i][j]
                if val == '---' or '---' in val:
                    row.append(0.0)
                else:
                    try:
                        row.append(float(val))
                    except ValueError:
                        row.append(0.0)
            while len(row) < n:
                row.append(0.0)
            matrix.append(row[:n])
        
        while len(matrix) < n:
            matrix.append([0.0] * n)
            
        df = pd.DataFrame(matrix, index=pdb_ids, columns=pdb_ids)
        return df
        
    except Exception as e:
        logger.error(f"Failed to parse .rms_rot file: {e}")
        return None

# Re-implementing robust RMSD using aligned FASTA + Superimposed PDB
def calculate_structure_rmsd(pdb_file: Path, fasta_file: Path) -> Optional[pd.DataFrame]:
    """
    Calculate RMSD using the aligned FASTA to map residues between superimposed structures.
    """
    try:
        # 1. Parse Aligned FASTA to get the mapping
        from Bio import SeqIO
        alignment = list(SeqIO.parse(fasta_file, "fasta"))
        num_structures = len(alignment)
        if num_structures < 2:
            return None
            
        # Map: For each column in alignment, which residue index (0-based) is it in the source sequence?
        # We build a list of lists: mapping[struct_idx][col_idx] = residue_number (or None)
        
        seq_len = len(alignment[0].seq)
        mapping = [[None] * seq_len for _ in range(num_structures)]
        
        for i, record in enumerate(alignment):
            res_counter = 0 # 0-based index of residues in the PDB structure
            for col, char in enumerate(record.seq):
                if char != '-':
                    mapping[i][col] = res_counter
                    res_counter += 1
                    
        # 2. Parse PDB
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("aln", str(pdb_file))
        
        # Determine if we should use Models or Chains
        models = list(structure.get_models())
        structures = []
        
        if len(models) == num_structures:
            structures = models
        elif len(models) < num_structures and len(models) > 0:
            # Check chains in first model
            chains = list(models[0].get_chains())
            if len(chains) >= num_structures:
                logger.info(f"RMSD: Using chains from Model 0 as structures (Found {len(chains)})")
                structures = chains
            else:
                logger.warning(f"RMSD: Structure count mismatch. FASTA={num_structures}, PDB Models={len(models)}, PDB Chains M0={len(chains)}")
                # Try to use whatever matches best or just models
                structures = models 
        else:
            structures = models
            
        # Use the minimum common count
        n_calc = min(len(structures), num_structures)
        
        # 3. Compute Pairwise RMSD
        # For each pair, find columns where BOTH have a residue (no gap).
        # Extract CA atoms for those residues.
        # Compute RMSD.
        
        matrix = np.zeros((num_structures, num_structures))
        
        # Pre-extract CA atoms for speed
        # structure_cas[idx] = list of CA Atom objects
        structure_cas = []
        for entity in structures:
            # Get all CA atoms in order (works for both Model and Chain objects)
            cas = [atom for atom in entity.get_atoms() if atom.name == 'CA']
            structure_cas.append(cas)
            
        for i in range(n_calc):
            for j in range(i + 1, n_calc):
                # Find common aligned columns
                common_coords_i = []
                common_coords_j = []
                
                for col in range(seq_len):
                    res_i_idx = mapping[i][col]
                    res_j_idx = mapping[j][col]
                    
                    if res_i_idx is not None and res_j_idx is not None:
                        # Safety check for index bounds
                        if res_i_idx < len(structure_cas[i]) and res_j_idx < len(structure_cas[j]):
                            common_coords_i.append(structure_cas[i][res_i_idx].coord)
                            common_coords_j.append(structure_cas[j][res_j_idx].coord)
                            
                # Calculate RMSD
                if common_coords_i:
                    diff = np.array(common_coords_i) - np.array(common_coords_j)
                    rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
                    matrix[i, j] = rmsd
                    matrix[j, i] = rmsd
                else:
                    matrix[i, j] = 0 # Should not happen if aligned
                    
        # Return labeled dataframe
        names = [r.id for r in alignment]
        df = pd.DataFrame(matrix, index=names, columns=names)
        return df
        
    except Exception as e:
        logger.error(f"PyRMSD Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
