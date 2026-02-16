import logging
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
from Bio.PDB import PDBParser, Selection, NeighborSearch, Residue
from Bio.PDB.PDBExceptions import PDBConstructionWarning

logger = logging.getLogger(__name__)

class LigandAnalyzer:
    """
    Analyzes ligand-protein interactions in PDB structures.
    Identifies ligands (HETATM) and finds interacting residues.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the LigandAnalyzer.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        # Common ions and solvents to ignore by default
        self.ignored_residues = {
            'HOH', 'WAT', 'TIP', 'SOL', # Water
            'NA', 'CL', 'K', 'MG', 'CA', 'ZN', 'MN', 'FE', # Common Ions
            'SO4', 'PO4', 'ACT', 'EDO', 'GOL' # Common crystallization additives
        }
        
    def get_ligands(self, pdb_file: Path) -> List[Dict[str, Any]]:
        """
        Identify potential ligands in a PDB file.
        
        Args:
            pdb_file: Path to the PDB file
            
        Returns:
            List of dictionaries containing ligand info (name, id, location)
        """
        pdb_file = Path(pdb_file)
        if not pdb_file.exists():
            logger.error(f"PDB file not found: {pdb_file}")
            return []
            
        parser = PDBParser(QUIET=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", PDBConstructionWarning)
                structure = parser.get_structure('struct', str(pdb_file))
        except Exception as e:
            logger.error(f"Failed to parse {pdb_file}: {e}")
            return []
            
        ligands = []
        
        for model in structure:
            for chain in model:
                for residue in chain:
                    # Check if it's a HETATM (heteroatom)
                    # BioPython uses keys like ('H_NAG', 123, ' ') for HETATMs
                    # Standard residues have empty first element in tuple id
                    hetfield, resseq, icode = residue.get_id()
                    
                    if hetfield != ' ':
                        resname = residue.get_resname().strip()
                        
                        # Filter out water and common ions
                        if resname in self.ignored_residues:
                            continue
                            
                        # Calculate geometric center
                        coords = [atom.get_coord() for atom in residue]
                        center = np.mean(coords, axis=0).tolist() if coords else [0,0,0]
                        
                        ligand_info = {
                            'name': resname,
                            'id': f"{resname}_{chain.get_id()}_{resseq}",
                            'chain': chain.get_id(),
                            'resi': resseq,
                            'full_id': residue.get_full_id(),
                            'center': center,
                            'atom_count': len(residue)
                        }
                        ligands.append(ligand_info)
                        
        logger.info(f"Found {len(ligands)} ligands in {pdb_file.name}")
        return ligands

    def calculate_interactions(self, pdb_file: Path, ligand_id: str, cutoff: float = 5.0) -> Dict[str, Any]:
        """
        Find residues interacting with a specific ligand.
        
        Args:
            pdb_file: Path to PDB file
            ligand_id: Unique ID of the ligand (Name_Chain_Resi)
            cutoff: Distance cutoff in Angstroms (default 5.0)
            
        Returns:
            Dictionary with interaction details
        """
        pdb_file = Path(pdb_file)
        parser = PDBParser(QUIET=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", PDBConstructionWarning)
                structure = parser.get_structure('struct', str(pdb_file))
        except Exception as e:
            return {'error': str(e)}

        # Find the specific ligand residue
        target_ligand = None
        target_atoms = []
        
        # Parse ligand_id to find it (Format: RESNAME_CHAIN_RESI)
        # Verify format matches get_ligands output
        try:
            parts = ligand_id.split('_')
            # Handle cases where resname might have underscores (rare but possible)
            # Assuming standard 3 parts: Name, Chain, Resi
            l_chain = parts[-2]
            l_resi = int(parts[-1])
            l_name = "_".join(parts[:-2]) 
        except:
            logger.error(f"Invalid ligand ID format: {ligand_id}")
            return {'error': "Invalid ID"}

        # Extract atoms for NeighborSearch
        all_atoms = []
        for model in structure:
            for chain in model:
                for residue in chain:
                    # Check if this is our target ligand
                    if (chain.get_id() == l_chain and 
                        residue.get_id()[1] == l_resi and 
                        residue.get_resname().strip() == l_name):
                        target_ligand = residue
                        target_atoms = list(residue.get_atoms())
                    else:
                        # Add non-ligand atoms to search space
                        # Exclude solvent/ions from being "interacting partners" usually?
                        # For now keep protein atoms (standard residues)
                        if residue.get_id()[0] == ' ':
                            all_atoms.extend(residue.get_atoms())

        if not target_ligand:
            return {'error': f"Ligand {ligand_id} not found in structure"}

        # Perform Neighbor Search
        ns = NeighborSearch(all_atoms)
        interacting_residues = set()
        
        for atom in target_atoms:
            # Find nearby atoms
            neighbors = ns.search(atom.get_coord(), cutoff, level='R')
            for residue in neighbors:
                interacting_residues.add(residue)
                
        # Format results
        results = {
            'ligand': ligand_id,
            'interactions': []
        }
        
        for res in interacting_residues:
            # Calculate min distance to ligand
            min_dist = 999.9
            res_atoms = list(res.get_atoms())
            for la in target_atoms:
                for ra in res_atoms:
                    dist = la - ra
                    if dist < min_dist:
                        min_dist = dist
            
            results['interactions'].append({
                'residue': res.get_resname(),
                'chain': res.get_parent().get_id(),
                'resi': res.get_id()[1],
                'distance': round(min_dist, 2),
                'type': 'Hydrophobic' if res.get_resname() in ['ALA', 'VAL', 'LEU', 'ILE', 'MET', 'PHE', 'TRP', 'PRO'] else 'Polar/Charged'
            })
            
        # Sort by distance
        results['interactions'].sort(key=lambda x: x['distance'])
        
        return results
