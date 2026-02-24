"""PDB file management: download, validation, and preprocessing."""

import requests
import httpx
import shutil
import logging
import asyncio
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from Bio import PDB
from Bio.PDB import PDBIO, Select, MMCIFParser, PDBParser
import gzip
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from src.utils.logger import get_logger
from src.utils.cache_manager import CacheManager

logger = get_logger()


class PDBManager:
    """Manages PDB file downloads, validation, and preprocessing."""
    
    def __init__(self, config: Dict[str, Any], cache_manager: Optional[CacheManager] = None):
        """
        Initialize PDB Manager.
        
        Args:
            config: Configuration dictionary
            cache_manager: Optional CacheManager instance
        """
        self.config = config
        self.cache_manager = cache_manager
        self.pdb_source = config.get('pdb', {}).get('source_url', 
                                                     'https://files.rcsb.org/download/')
        self.timeout = config.get('pdb', {}).get('timeout', 60)
        self.max_size_mb = config.get('pdb', {}).get('max_file_size_mb', 500)
        self.raw_dir = Path('data/raw')
        self.cleaned_dir = Path('data/cleaned')
        
        # Create directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def validate_pdb_id(pdb_id: str) -> bool:
        """
        Validate PDB ID format.
        Supports standard 4-char PDB IDs and AlphaFold IDs (AF-UniProt-F1).
        """
        pdb_id = pdb_id.strip().upper()
        # Standard PDB ID
        if re.match(r'^[0-9][A-Z0-9]{3}$', pdb_id):
            return True
        # AlphaFold ID
        if re.match(r'^AF-[A-Z0-9]+-F[0-9]+$', pdb_id):
            return True
        return False
    
    def save_uploaded_file(self, uploaded_file: Any) -> Tuple[bool, str, Optional[Path]]:
        """
        Save an uploaded file to the raw directory.
        
        Args:
            uploaded_file: Streamlit UploadedFile object
            
        Returns:
            Tuple of (success, message, file_path)
        """
        try:
            # Clean filename
            name = Path(uploaded_file.name).stem
            # Replace spaces with underscores
            name = re.sub(r'\s+', '_', name)
            
            output_file = self.raw_dir / f"{name}.pdb"
            
            with open(output_file, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            logger.info(f"Saved uploaded file: {output_file}")
            return True, "Saved uploaded file", output_file
        except Exception as e:
            logger.error(f"Failed to save upload: {e}")
            return False, str(e), None

    async def download_pdb(self, pdb_id: str, force: bool = False, client: Optional[httpx.AsyncClient] = None) -> Tuple[bool, str, Optional[Path]]:
        """
        Download a structural file (PDB or AlphaFold CIF) (Asynchronous).
        """
        pdb_id = pdb_id.strip()
        is_af = pdb_id.upper().startswith("AF-")
        ext = ".cif" if is_af else ".pdb"
        
        # Check if already exists
        output_file = self.raw_dir / f"{pdb_id}{ext}"
        if output_file.exists() and not force:
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            if self.cache_manager:
                self.cache_manager.update_access(pdb_id)
            return True, f"Using local file ({file_size_mb:.2f} MB)", output_file
        
        if not self.validate_pdb_id(pdb_id):
            return False, f"Invalid ID format: {pdb_id}", None
        
        if is_af:
            # AlphaFold DB URL (v4)
            uniprot_id = pdb_id.split("-")[1].upper()
            fragment = pdb_id.split("-")[2].upper()
            url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-{fragment}-model_v4.cif"
        else:
            pdb_id = pdb_id.upper()
            url = f"{self.pdb_source}{pdb_id}.pdb"
        
        try:
            manage_client = client is None
            if manage_client:
                client = httpx.AsyncClient(timeout=self.timeout)
            
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                if manage_client: await client.aclose()
                return False, f"Download failed (Status {response.status_code})", None
            
            # Check file size
            file_size = len(response.content)
            file_size_mb = file_size / (1024 * 1024)
            
            with open(output_file, 'wb') as f:
                f.write(response.content)
                
            if manage_client: await client.aclose()
            
            if self.cache_manager:
                self.cache_manager.register_item(pdb_id, output_file)
                
            logger.info(f"Downloaded {pdb_id} successfully ({file_size_mb:.2f} MB)")
            return True, f"Downloaded ({file_size_mb:.2f} MB)", output_file
            
        except Exception as e:
            logger.error(f"Failed to download {pdb_id}: {str(e)}")
            return False, f"Download failed: {str(e)}", None

    async def batch_download(self, pdb_ids: List[str]) -> Dict[str, Tuple[bool, str, Optional[Path]]]:
        """
        Download multiple PDB files in parallel using AsyncIO.
        """
        results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [self.download_pdb(pdb_id, client=client) for pdb_id in pdb_ids]
            download_responses = await asyncio.gather(*tasks)
            
            for pdb_id, res in zip(pdb_ids, download_responses):
                results[pdb_id] = res
                
        return results
    
    def _get_structure(self, file_path: Path) -> Any:
        """Hybrid parser for PDB and mmCIF formats."""
        if file_path.suffix.lower() == '.cif':
            parser = MMCIFParser(QUIET=True)
        else:
            parser = PDBParser(QUIET=True)
        return parser.get_structure('protein', str(file_path))

    def analyze_structure(self, pdb_file: Path) -> Dict:
        """
        Analyze structural file and return information.
        """
        structure = self._get_structure(pdb_file)
        
        chains = []
        total_residues = 0
        
        for model in structure:
            for chain in model:
                chain_id = chain.id
                residues = list(chain.get_residues())
                chains.append({
                    'id': chain_id,
                    'residue_count': len(residues)
                })
                total_residues += len(residues)
        
        file_size_mb = pdb_file.stat().st_size / (1024 * 1024)
        
        return {
            'file_size_mb': file_size_mb,
            'chains': chains,
            'total_residues': total_residues,
            'num_models': len(structure)
        }
    
    def clean_pdb(self, 
                  pdb_file: Path, 
                  chain: Optional[str] = None,
                  remove_heteroatoms: bool = True,
                  remove_water: bool = True) -> Tuple[bool, str, Optional[Path]]:
        """
        Clean structural file (PDB/CIF) and sanitize into standard PDB.
        """
        try:
            structure = self._get_structure(pdb_file)
            
            class CleanSelect(Select):
                def accept_residue(self, residue):
                    # Remove water
                    if remove_water and (residue.id[0] == 'W' or residue.resname == 'HOH'):
                        return 0
                    
                    # Keep standard residues
                    if residue.id[0] == ' ':
                        return 1
                    
                    # For non-standard residues (HETATM), keep them if they have a CA atom
                    # (prevents gaps in structures like Collagen with HYP)
                    if residue.has_id('CA'):
                        return 1
                        
                    return 0 if remove_heteroatoms else 1
                
                def accept_atom(self, atom):
                    # Exclude hydrogens (mustang often crashes on them)
                    if atom.element == 'H' or atom.name.startswith('H'):
                        return 0
                    return 1
            
            # Extract model 0
            model = structure[0]
            
            # Create a New sanitized structure
            new_structure = PDB.Structure.Structure(structure.id)
            new_model = PDB.Model.Model(0)
            new_structure.add(new_model)
            
            # Find the chain
            target_chain_obj = None
            for ch in model:
                if chain is None or ch.id == chain:
                    target_chain_obj = ch
                    break
            
            if not target_chain_obj:
                 return False, f"Chain {chain} not found", None
                 
            new_chain = PDB.Chain.Chain(target_chain_obj.id)
            new_model.add(new_chain)
            
            # Mapping of common non-standard residues to standard ones
            RESIDUE_MAPPING = {
                'HYP': 'PRO',
                'MSE': 'MET',
                'CSD': 'ALA',
                'CAS': 'CYS',
                'KCX': 'LYS',
                'LLP': 'LYS',
                'CME': 'CYS',
                'MLY': 'LYS',
            }
            
            clean_select = CleanSelect()
            res_count = 1
            for residue in target_chain_obj:
                # Use our logic to accept residue
                if not clean_select.accept_residue(residue):
                    continue
                
                # Standardize residue: remove HETATM prefix, map name, renumber
                res_name = residue.resname.strip()
                std_res_name = RESIDUE_MAPPING.get(res_name, res_name)
                
                # Force to be standard ATOM record: id[0] = ' '
                new_id = (' ', res_count, ' ')
                new_res = PDB.Residue.Residue(new_id, std_res_name, ' ')
                
                # Add atoms
                atoms_added = 0
                for atom in residue:
                    if clean_select.accept_atom(atom):
                        # Construct a fresh atom to ensure clean state
                        new_atom = PDB.Atom.Atom(
                            atom.name,
                            atom.coord,
                            atom.occupancy,
                            atom.bfactor,
                            atom.altloc,
                            atom.get_fullname(), # Fix: fullname must be string
                            atom.serial_number,
                            element=atom.element
                        )
                        new_res.add(new_atom)
                        atoms_added += 1
                
                if atoms_added > 0:
                    new_chain.add(new_res)
                    res_count += 1
            
            # Save cleaned structure with LF line endings
            # Force .pdb extension for Mustang compatibility
            output_file = self.cleaned_dir / f"{pdb_file.stem}.pdb"
            with open(str(output_file), 'w', newline='\n') as f:
                io = PDBIO()
                io.set_structure(new_structure)
                io.save(f)
            
            # Get size reduction
            original_size = pdb_file.stat().st_size / (1024 * 1024)
            cleaned_size = output_file.stat().st_size / (1024 * 1024)
            
            logger.info(f"Cleaned {pdb_file.name}: {original_size:.2f}MB -> {cleaned_size:.2f}MB")
            
            return True, "Cleaning and sanitization successful", output_file
            
        except Exception as e:
            logger.error(f"Failed to clean {pdb_file.name}: {str(e)}")
            return False, f"Cleaning failed: {str(e)}", None

    def batch_clean(self, pdb_files: List[Path], max_workers: int = 4) -> Dict[str, Tuple[bool, str, Optional[Path]]]:
        """
        Clean multiple PDB files in parallel.
        
        Args:
            pdb_files: List of PDB file paths
            max_workers: Number of parallel workers
            
        Returns:
            Dictionary mapping PDB filename to (success, message, path)
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.clean_pdb, p): p 
                for p in pdb_files
            }
            
            with tqdm(total=len(pdb_files), desc="Cleaning PDB files") as pbar:
                for future in as_completed(list(future_to_file.keys())):
                    pdb_file = future_to_file[future]
                    try:
                        results[pdb_file.name] = future.result()
                    except Exception as e:
                        logger.error(f"Error cleaning {pdb_file.name}: {str(e)}")
                        results[pdb_file.name] = (False, f"Error: {str(e)}", None)
                    pbar.update(1)
        
        return results

    async def fetch_metadata(self, pdb_ids: List[str], client: Optional[httpx.AsyncClient] = None) -> Dict[str, Dict]:
        """
        Fetch metadata for multiple PDB IDs from RCSB GraphQL API (Asynchronous).
        """
        if not pdb_ids:
            return {}
            
        unique_base_ids = []
        af_ids = []
        for pid in pdb_ids:
            clean_id = pid.strip().upper()
            if clean_id.startswith("AF-"):
                af_ids.append(clean_id)
                original_to_base[clean_id] = clean_id
            else:
                base_id = clean_id[:4]
                unique_base_ids.append(base_id)
                original_to_base[clean_id] = base_id
        
        unique_base_ids = list(set(unique_base_ids))
        af_ids = list(set(af_ids))
        
        query = """
        query($ids: [String!]!) {
          entries(entry_ids: $ids) {
            rcsb_id
            struct { title }
            exptl { method }
            rcsb_entry_info { resolution_combined }
            polymer_entities {
              rcsb_entity_source_organism { scientific_name }
            }
          }
        }
        """
        
        base_results = {bid: {'title': 'N/A', 'method': 'N/A', 'resolution': 'N/A', 'organism': 'N/A'} for bid in unique_base_ids}
            
        try:
            manage_client = client is None
            if manage_client:
                client = httpx.AsyncClient(timeout=10)
                
            url = "https://data.rcsb.org/graphql"
            payload = {"query": query, "variables": {"ids": unique_base_ids}}
            
            logger.info(f"Fetching metadata for {len(unique_base_ids)} entries via GraphQL (Async)")
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                entries = (data.get('data') or {}).get('entries') or []
                
                for entry in entries:
                    bid = entry.get('rcsb_id')
                    if not bid: continue
                    
                    struct = entry.get('struct') or {}
                    title = struct.get('title', 'N/A')
                    
                    exptl_list = entry.get('exptl') or []
                    method = exptl_list[0].get('method', 'N/A') if exptl_list else 'N/A'
                    
                    info = entry.get('rcsb_entry_info') or {}
                    res_list = info.get('resolution_combined') or []
                    resolution = f"{res_list[0]:.2f} \u00c5" if res_list else "N/A"
                    
                    organism = "N/A"
                    entities = entry.get('polymer_entities') or []
                    if entities:
                        for entity in entities:
                            sources = (entity.get('rcsb_entity_source_organism') or [])
                            if sources:
                                organism = sources[0].get('scientific_name', 'N/A')
                                break
                    
                    base_results[bid] = {
                        'title': title,
                        'method': method,
                        'resolution': resolution,
                        'organism': organism
                    }
            
            # 2. Fetch AlphaFold Metadata (via UniProt)
            for af_id in af_ids:
                try:
                    uniprot_id = af_id.split("-")[1]
                    # Use UniProt API
                    up_url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
                    up_resp = await client.get(up_url, timeout=5)
                    if up_resp.status_code == 200:
                        up_data = up_resp.json()
                        title = up_data.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', 'AF Model')
                        organism = up_data.get('organism', {}).get('scientificName', 'N/A')
                        base_results[af_id] = {
                            'title': f"[AlphaFold] {title}",
                            'method': 'Predicted (AF2)',
                            'resolution': 'pLDDT Scored',
                            'organism': organism
                        }
                    else:
                        base_results[af_id] = {
                            'title': f"AlphaFold model {uniprot_id}",
                            'method': 'Predicted',
                            'resolution': 'N/A',
                            'organism': 'N/A'
                        }
                except Exception:
                    continue

            if manage_client: await client.aclose()
            
            final_results = {}
            for original_id, base_id in original_to_base.items():
                final_results[original_id] = base_results.get(base_id, base_results.get(base_id.upper(), {
                    'title': 'N/A', 'method': 'N/A', 'resolution': 'N/A', 'organism': 'N/A'
                }))
                
            return final_results
            
        except Exception as e:
            logger.error(f"Metadata fetch failed: {str(e)}")
            return {pid: {'title': 'N/A', 'method': 'N/A', 'resolution': 'N/A', 'organism': 'N/A'} for pid in pdb_ids}
