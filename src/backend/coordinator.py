"""
Analysis Coordinator Module.
Orchestrates the structural alignment pipeline (PDB -> Mustang -> RMSD -> Report).
"""

import shutil
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Callable
from datetime import datetime

from src.utils.logger import get_logger
from src.backend.pdb_manager import PDBManager
from src.backend.mustang_runner import MustangRunner
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.phylo_tree import PhyloTreeGenerator
from src.backend.rmsd_calculator import parse_rmsd_matrix
from src.backend.database import HistoryDatabase
from src.backend.sequence_viewer import SequenceViewer
from src.utils.cache_manager import CacheManager

logger = get_logger()

class AnalysisCoordinator:
    """
    Orchestrates the entire structural analysis pipeline.
    Decouples UI from backend implementation logic.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.history_db = HistoryDatabase()
        self.cache_manager = CacheManager(config, self.history_db)
        self.pdb_manager = PDBManager(config, self.cache_manager)
        self.mustang_runner = MustangRunner(config)
        self.rmsd_analyzer = RMSDAnalyzer(config)
        self.sequence_viewer = SequenceViewer()
        
        # Eagerly check installation to set up the correct backend
        success, msg = self.mustang_runner.check_installation()
        if not success:
            logger.warning(f"Mustang installation check failed: {msg}")
        else:
            logger.info(f"Mustang installation verified: {msg}")
        
    def run_full_pipeline(
        self, 
        pdb_ids: List[str], 
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str, int], None]] = None,
        chain_selection: Optional[Dict[str, str]] = None,
        remove_water: bool = True,
        remove_heteroatoms: bool = True
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Execute the full analysis pipeline.
        
        Args:
            pdb_ids: List of 4-character PDB identifiers.
            output_dir: Base directory for results.
            progress_callback: Function to report progress (fraction, message, step).
            chain_selection: Optional mapping of PDB ID to specific chain ID.
            
        Returns:
            Tuple of (success, message, results_dict).
        """
        try:
            if not output_dir:
                now = datetime.now()
                run_id = f"run_{int(now.timestamp())}"
                run_name = f"Analysis of {len(pdb_ids)} structures ({now.strftime('%H:%M')})"
                output_dir = Path("results") / run_id
            else:
                run_id = output_dir.name
                now = datetime.now()
                run_name = f"Custom Run ({now.strftime('%H:%M')})"
            
            # 1. DATA PREPARATION (Step 1)
            if progress_callback: progress_callback(0.1, "📥 Downloading PDB files...", 1)
            
            # Run async batch download from sync context
            download_results = asyncio.run(self.pdb_manager.batch_download(pdb_ids))
            failed = [pid for pid, (success, msg, path) in download_results.items() if not success]
            if failed:
                return False, f"Failed to download: {', '.join(failed)}", None
                
            pdb_files = [path for success, msg, path in download_results.values() if path]
            
            # 2. CLEANING & FILTERING (Step 2)
            if progress_callback: progress_callback(0.3, "🧹 Cleaning PDB files...", 2)
            
            cleaned_files = []
            for pdb_file in pdb_files:
                pdb_id = pdb_file.stem.split('_')[0].upper()
                target_chain = chain_selection.get(pdb_id) if chain_selection else None
                
                # Mustang requires exactly one chain per structure.
                # If no specific chain is requested, we automatically pick the first one.
                if not target_chain:
                    info = self.pdb_manager.analyze_structure(pdb_file)
                    if info['chains']:
                        target_chain = info['chains'][0]['id']
                        logger.info(f"Auto-detected multi-chain PDB {pdb_id}. Selecting chain '{target_chain}' for Mustang.")
                
                success, msg, cleaned_path = self.pdb_manager.clean_pdb(
                    pdb_file,
                    chain=target_chain,
                    remove_water=remove_water,
                    remove_heteroatoms=remove_heteroatoms
                )
                if cleaned_path:
                    cleaned_files.append(cleaned_path)
                else:
                    logger.warning(f"Could not clean {pdb_file}: {msg}")
            
            # 3. STRUCTURAL ALIGNMENT (Step 3)
            if progress_callback: progress_callback(0.5, "⚙️ Running Mustang alignment...", 3)
            
            # Ensure output directory is clean
            if output_dir.exists():
                shutil.rmtree(output_dir, ignore_errors=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            success, msg, result_dir = self.mustang_runner.run_alignment(cleaned_files, output_dir)
            if not success:
                return False, f"Mustang alignment failed: {msg}", None
            
            # Ensure input PDBs are copied to results
            for pdb_file in cleaned_files:
                dest = result_dir / pdb_file.name
                if not dest.exists():
                    shutil.copy2(pdb_file, dest)
            
            # 4. DATA PROCESSING & VISUALIZATION (Step 4)
            if progress_callback: progress_callback(0.75, "📊 Generating visualizations...", 4)
            
            results = self.process_result_directory(result_dir, pdb_ids)
            if not results:
                return False, "Failed to process result directory", None
            
            # 5. SAVE TO HISTORY & WRITE METADATA
            self.history_db.save_run(
                run_id,
                run_name,
                pdb_ids,
                result_dir
            )
            
            # Write metadata.json for portability and indexing stability
            import json
            metadata = {
                "id": run_id,
                "name": run_name,
                "timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
                "protein_count": len(pdb_ids),
                "proteins": pdb_ids
            }
            with open(result_dir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=4)
            
            # Inject metadata into results for UI
            results['id'] = run_id
            results['name'] = run_name
            results['timestamp'] = now.strftime('%Y-%m-%d %H:%M:%S')
            
            if progress_callback: progress_callback(1.0, "✅ Analysis complete!", 4)
            return True, "Analysis completed successfully", results

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return False, str(e), None

    def process_result_directory(self, result_dir: Path, pdb_ids: List[str]) -> Optional[Dict[str, Any]]:
        """
        Process a completed Mustang run directory into a results dictionary.
        """
        try:
            # Parse RMSD
            rmsd_df = parse_rmsd_matrix(result_dir, pdb_ids)
            if rmsd_df is None:
                return None
                
            # Static Artifacts
            heatmap_path = result_dir / 'rmsd_heatmap.png'
            tree_path = result_dir / 'phylogenetic_tree.png'
            newick_path = result_dir / 'tree.newick'
            alignment_pdb = result_dir / 'alignment.pdb'
            alignment_afasta = result_dir / 'alignment.afasta'
            
            # Calculations
            self.rmsd_analyzer.generate_heatmap(rmsd_df, heatmap_path)
            stats = self.rmsd_analyzer.calculate_statistics(rmsd_df)
            
            # Calculate sequence identity
            if alignment_afasta.exists():
                sequences = self.sequence_viewer.parse_afasta(alignment_afasta)
                if sequences:
                    stats['seq_identity'] = self.sequence_viewer.calculate_identity(sequences)
            
            clusters = self.rmsd_analyzer.identify_clusters(rmsd_df)
            
            phylo = PhyloTreeGenerator(self.config)
            phylo.generate_tree(rmsd_df, tree_path)
            phylo.export_newick(rmsd_df, newick_path)
            
            # Interactive Figures
            heatmap_fig = self.rmsd_analyzer.generate_plotly_heatmap(rmsd_df)
            tree_fig = phylo.generate_plotly_tree(rmsd_df)
            
            # RMSF
            rmsf_values = []
            try:
                rmsf_values, _ = self.rmsd_analyzer.calculate_residue_rmsf(alignment_pdb, alignment_afasta)
            except Exception as e:
                logger.warning(f"Residue RMSF failed: {e}")

            return {
                'pdb_ids': pdb_ids,
                'rmsd_df': rmsd_df,
                'heatmap_path': heatmap_path,
                'stats': stats,
                'clusters': clusters,
                'result_dir': result_dir,
                'tree_path': tree_path,
                'newick_path': newick_path,
                'heatmap_fig': heatmap_fig,
                'tree_fig': tree_fig,
                'alignment_pdb': alignment_pdb,
                'alignment_afasta': alignment_afasta,
                'rmsf_values': rmsf_values
            }
        except Exception as e:
            logger.error(f"Data processing failed: {e}")
            return None
