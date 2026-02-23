import numpy as np
import pandas as pd
from Bio.PDB import PDBParser
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from src.utils.logger import get_logger

logger = get_logger()

def calculate_rmsd_from_superposition(pdb_file: Path, num_expected: int) -> Optional[pd.DataFrame]:
    """
    Fallback: Calculate pairwise RMSD matrix directly from superimposed PDB coordinates
    assuming sequential atom matching (only for structures with identical residue/atom counts).
    
    Args:
        pdb_file: Path to superimposed PDB
        num_expected: Number of structures to expect
    """
    try:
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
            cas = [a.coord for a in e.get_atoms() if a.name == 'CA']
            coords.append(np.array(cas))
        
        # Verify identical lengths for simple subtraction
        n = len(coords)
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i+1, n):
                if len(coords[i]) == len(coords[j]) and len(coords[i]) > 0:
                    diff = coords[i] - coords[j]
                    rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
                    matrix[i, j] = matrix[j, i] = rmsd
        return pd.DataFrame(matrix)
    except Exception as e:
        logger.error(f"Manual RMSD calc failed: {e}")
        return None

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
    try:
        if not log_file.exists():
            return None
            
        with open(log_file, 'r') as f:
            lines = f.readlines()
            
        # Extract protein count by looking at IDs if possible, or just the table
        # We'll assume the number of proteins is determined by the caller or inferred from the table size
        
        potential_matrix = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # The RMSD table in Mustang logs usually starts with a numeric index
            # followed by the RMSD values. Let's try to detect those lines.
            parts = line.split()
            if not parts:
                continue
                
            # Check if the first part looks like a row index (usually 1, 2, 3...)
            # and the rest look like floats or '---'
            try:
                # Basic heuristic: if the first part is an integer and there are multiple parts
                # it's likely a row of the RMSD matrix.
                int(parts[0])
                if len(parts) > 1:
                    row = []
                    for p in parts[1:]:
                        if p == '---':
                            row.append(0.0)
                        else:
                            try:
                                row.append(float(p))
                            except ValueError:
                                # Not a float, might be part of another line
                                break
                    if row:
                        potential_matrix.append(row)
            except (ValueError, IndexError):
                continue
        
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
    Unified entry point for extracting structural similarity data.
    Strategies:
    1. Parse Mustang .rms_rot (Most precise)
    2. Parse Mustang .log (Standard)
    3. Bio3D CSV (Legacy/Fallback)
    4. Calculate from superposition (Absolute fallback)
    """
    # 1. Mustang's precise .rms_rot file
    rms_rot = output_dir / 'alignment.rms_rot'
    if rms_rot.exists():
        df = parse_rms_rot_file(rms_rot, pdb_ids)
        if df is not None: return df
    
    # 2. Mustang's log file output
    log_file = output_dir / 'mustang.log'
    if log_file.exists():
        df = parse_mustang_log_for_rmsd(log_file)
        if df is not None and len(df) == len(pdb_ids):
            df.index, df.columns = pdb_ids, pdb_ids
            return df

    # 3. Calculation from PDB/FASTA (PyRMSD)
    alignment_pdb = output_dir / 'alignment.pdb'
    alignment_fasta = output_dir / 'alignment.afasta'
    if alignment_pdb.exists() and alignment_fasta.exists():
        df = calculate_structure_rmsd(alignment_pdb, alignment_fasta)
        if df is not None: return df
            
    logger.error("All RMSD parsing strategies failed.")
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
