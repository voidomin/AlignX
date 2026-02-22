"""PDB file management: download, validation, and preprocessing."""

import requests
import httpx
import asyncio
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from Bio import PDB
from Bio.PDB import PDBIO, Select
import gzip
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from src.utils.logger import get_logger
from src.utils.cache_manager import CacheManager

logger = get_logger()


class PDBManager:
    """Manages PDB file downloads, validation, and preprocessing."""
    
    def __init__(self, config: Dict[str, Any]):
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
        Validate PDB ID format (4 characters: letter followed by 3 alphanumeric).
        
        Args:
            pdb_id: PDB identifier
            
        Returns:
            True if valid, False otherwise
        """
        pattern = r'^[0-9][A-Za-z0-9]{3}$'
        return bool(re.match(pattern, pdb_id.strip()))
    
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
        Download a PDB file from RCSB (Asynchronous).
        """
        pdb_id = pdb_id.strip()
        
        # Check if already exists
        output_file = self.raw_dir / f"{pdb_id}.pdb"
        if output_file.exists() and not force:
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            if self.cache_manager:
                self.cache_manager.update_access(pdb_id)
            return True, f"Using local file ({file_size_mb:.2f} MB)", output_file
        
        pdb_id = pdb_id.upper()
        if not self.validate_pdb_id(pdb_id):
            return False, f"Invalid PDB ID format: {pdb_id}", None
        
        output_file = self.raw_dir / f"{pdb_id}.pdb"
        url = f"{self.pdb_source}{pdb_id}.pdb"
        
        try:
            manage_client = client is None
            if manage_client:
                client = httpx.AsyncClient(timeout=self.timeout)
            
            async with client.get(url, follow_redirects=True) as response:
                if response.status_code != 200:
                    if manage_client: await client.aclose()
                    return False, f"Download failed (Status {response.status_code})", None
                
                # Check file size
                file_size = int(response.headers.get('content-length', 0))
                file_size_mb = file_size / (1024 * 1024)
                
                content = await response.aread()
                with open(output_file, 'wb') as f:
                    f.write(content)
                
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
                for future in as_completed(future_to_file):
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
            
        original_to_base = {}
        for pid in pdb_ids:
            clean_id = pid.strip().upper()
            base_id = clean_id[:4]
            original_to_base[clean_id] = base_id
            
        unique_base_ids = list(set(original_to_base.values()))
        
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
                entries = data.get('data', {}).get('entries', [])
                
                for entry in entries:
                    bid = entry.get('rcsb_id')
                    if not bid: continue
                    
                    struct = entry.get('struct', {})
                    title = struct.get('title', 'N/A') if struct else 'N/A'
                    
                    exptl = entry.get('exptl', [])
                    method = exptl[0].get('method', 'N/A') if exptl else 'N/A'
                    
                    res_list = entry.get('rcsb_entry_info', {}).get('resolution_combined', [])
                    resolution = f"{res_list[0]:.2f} \u00c5" if res_list else "N/A"
                    
                    organism = "N/A"
                    entities = entry.get('polymer_entities', [])
                    if entities:
                        for entity in entities:
                            sources = entity.get('rcsb_entity_source_organism', [])
                            if sources:
                                organism = sources[0].get('scientific_name', 'N/A')
                                break
                    
                    base_results[bid] = {
                        'title': title,
                        'method': method,
                        'resolution': resolution,
                        'organism': organism
                    }
            
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
