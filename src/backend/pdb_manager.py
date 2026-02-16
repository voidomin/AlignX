"""PDB file management: download, validation, and preprocessing."""

import requests
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from Bio import PDB
from Bio.PDB import PDBIO, Select
import gzip
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from ..utils.logger import get_logger

logger = get_logger()


class PDBManager:
    """Manages PDB file downloads, validation, and preprocessing."""
    
    def __init__(self, config: Dict):
        """
        Initialize PDB Manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
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
        Validate PDB ID format (4 characters: letter followed by 3 alphanumeric).
        
        Args:
            pdb_id: PDB identifier
            
        Returns:
            True if valid, False otherwise
        """
        pattern = r'^[0-9][A-Za-z0-9]{3}$'
        return bool(re.match(pattern, pdb_id.strip()))
    
    def download_pdb(self, pdb_id: str, force: bool = False) -> Tuple[bool, str, Optional[Path]]:
        """
        Download a PDB file from RCSB.
        
        Args:
            pdb_id: PDB identifier
            force: Re-download even if file exists
            
        Returns:
            Tuple of (success, message, file_path)
        """
        pdb_id = pdb_id.strip().upper()
        
        # Validate ID
        if not self.validate_pdb_id(pdb_id):
            return False, f"Invalid PDB ID format: {pdb_id}", None
        
        # Check if already downloaded
        output_file = self.raw_dir / f"{pdb_id}.pdb"
        if output_file.exists() and not force:
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            logger.info(f"{pdb_id} already downloaded ({file_size_mb:.2f} MB)")
            return True, f"Already downloaded ({file_size_mb:.2f} MB)", output_file
        
        # Download
        try:
            url = f"{self.pdb_source}{pdb_id}.pdb"
            logger.info(f"Downloading {pdb_id} from {url}")
            
            response = requests.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            # Check file size
            file_size = int(response.headers.get('content-length', 0))
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > self.max_size_mb:
                logger.warning(f"{pdb_id} is large ({file_size_mb:.2f} MB). Consider filtering.")
            
            # Save file
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded {pdb_id} successfully ({file_size_mb:.2f} MB)")
            return True, f"Downloaded ({file_size_mb:.2f} MB)", output_file
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download {pdb_id}: {str(e)}")
            return False, f"Download failed: {str(e)}", None
    
    def batch_download(self, pdb_ids: List[str], max_workers: int = 4) -> Dict[str, Tuple[bool, str, Optional[Path]]]:
        """
        Download multiple PDB files in parallel.
        
        Args:
            pdb_ids: List of PDB identifiers
            max_workers: Number of parallel downloads
            
        Returns:
            Dictionary mapping PDB ID to (success, message, path)
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_pdb = {
                executor.submit(self.download_pdb, pdb_id): pdb_id 
                for pdb_id in pdb_ids
            }
            
            # Progress bar
            with tqdm(total=len(pdb_ids), desc="Downloading PDB files") as pbar:
                for future in as_completed(future_to_pdb):
                    pdb_id = future_to_pdb[future]
                    try:
                        results[pdb_id] = future.result()
                    except Exception as e:
                        logger.error(f"Error downloading {pdb_id}: {str(e)}")
                        results[pdb_id] = (False, f"Error: {str(e)}", None)
                    pbar.update(1)
        
        return results
    
    def analyze_structure(self, pdb_file: Path) -> Dict:
        """
        Analyze PDB structure and return information.
        
        Args:
            pdb_file: Path to PDB file
            
        Returns:
            Dictionary with structure information
        """
        parser = PDB.PDBParser(QUIET=True)
        structure = parser.get_structure('protein', str(pdb_file))
        
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
        Clean PDB file by removing unwanted components.
        
        Args:
            pdb_file: Input PDB file
            chain: Specific chain to extract (None = keep all)
            remove_heteroatoms: Remove heteroatoms (ligands, ions)
            remove_water: Remove water molecules
            
        Returns:
            Tuple of (success, message, output_path)
        """
        try:
            parser = PDB.PDBParser(QUIET=True)
            structure = parser.get_structure('protein', str(pdb_file))
            
            class CleanSelect(Select):
                def accept_residue(self, residue):
                    # Remove water
                    if remove_water and residue.id[0] == 'W':
                        return 0
                    # Remove heteroatoms
                    if remove_heteroatoms and residue.id[0] != ' ':
                        return 0
                    return 1
                
                def accept_chain(self, chain_obj):
                    if chain is None:
                        return 1
                    return chain_obj.id == chain
            
            # Save cleaned structure
            output_file = self.cleaned_dir / pdb_file.name
            io = PDBIO()
            io.set_structure(structure)
            io.save(str(output_file), CleanSelect())
            
            # Get size reduction
            original_size = pdb_file.stat().st_size / (1024 * 1024)
            cleaned_size = output_file.stat().st_size / (1024 * 1024)
            
            msg = f"Cleaned: {original_size:.2f} MB → {cleaned_size:.2f} MB"
            if chain:
                msg += f" (Chain {chain} only)"
            
            logger.info(msg)
            return True, msg, output_file
            
        except Exception as e:
            logger.error(f"Failed to clean {pdb_file.name}: {str(e)}")
            return False, f"Cleaning failed: {str(e)}", None

    def fetch_metadata(self, pdb_ids: List[str], max_workers: int = 4) -> Dict[str, Dict]:
        """
        Fetch metadata for multiple PDB IDs from RCSB API.
        
        Args:
            pdb_ids: List of PDB IDs
            max_workers: Number of parallel requests
            
        Returns:
            Dictionary mapping PDB ID to metadata dict
        """
        metadata_url = "https://data.rcsb.org/rest/v1/core/entry/"
        results = {}
        
        def _fetch_single(pdb_id):
            try:
                # Normalize ID
                pid = pdb_id.strip().upper()
                response = requests.get(f"{metadata_url}{pid}", timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract relevant fields
                    # Ensure struct exists
                    struct = data.get('struct', {})
                    title = struct.get('title', 'N/A') if struct else 'N/A'
                    
                    # Method
                    exptl = data.get('exptl', [{}])
                    method = exptl[0].get('method', 'N/A') if exptl else 'N/A'
                    
                    resolution = data.get('rcsb_entry_info', {}).get('resolution_combined', [None])[0]
                    
                    # Organism - Try simpler path or default to N/A without failing
                    # rcsb_entity_source_organism is often not in Entry endpoint
                    organism = "N/A"
                    # Try basic lookup if available, otherwise just leave N/A to avoid errors
                    if 'struct_keywords' in data:
                        # Sometimes keywords contain organism hints, but better to be safe
                        pass
                            
                    return pid, {
                        'title': title,
                        'method': method,
                        'resolution': f"{resolution:.2f} Å" if resolution else "N/A",
                        'organism': organism
                    }
                else:
                    return pid, None
            except Exception as e:
                logger.warning(f"Failed to fetch metadata for {pdb_id}: {str(e)}")
                return pid, None

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pid = {executor.submit(_fetch_single, pid): pid for pid in pdb_ids}
            
            for future in as_completed(future_to_pid):
                pid = future_to_pid[future]
                try:
                    result_pid, info = future.result()
                    if info:
                        results[result_pid] = info
                except Exception as e:
                    logger.error(f"Error fetching metadata for {pid}: {str(e)}")
                    
        return results
