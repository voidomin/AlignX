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
from src.backend.ligand_analyzer import LigandAnalyzer
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.phylo_tree import PhyloTreeGenerator
from src.backend.rmsd_calculator import (
    parse_rmsd_matrix,
    calculate_alignment_quality_metrics,
)
from src.backend.ramachandran_service import RamachandranService
from src.backend.database import HistoryDatabase
from src.backend.sequence_viewer import SequenceViewer
from src.utils.cache_manager import CacheManager
from src.utils.run_id import generate_run_id

logger = get_logger()


def _sanitize_json_key(k: Any) -> Any:
    """A dict key must itself be JSON-serializable, which np.integer/
    np.floating/Path (and anything else non-primitive) aren't."""
    import numpy as np
    from pathlib import Path

    if isinstance(k, (np.integer, np.floating)):
        return k.item()
    if isinstance(k, Path):
        return str(k)
    if not isinstance(k, (str, int, float, bool, type(None))):
        return str(k)
    return k


def sanitize_for_json(val: Any) -> Any:
    """Recursively convert custom objects (Path, np.ndarray, DataFrame, etc) to JSON-serializable types."""
    import numpy as np
    import pandas as pd
    from pathlib import Path

    if isinstance(val, dict):
        return {_sanitize_json_key(k): sanitize_for_json(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_for_json(item) for item in val]
    elif isinstance(val, tuple):
        # Convert tuple to list for proper JSON serialization
        return [sanitize_for_json(item) for item in val]
    elif isinstance(val, np.integer):
        return int(val)
    elif isinstance(val, np.floating):
        return float(val)
    elif isinstance(val, np.ndarray):
        return [sanitize_for_json(item) for item in val.tolist()]
    elif hasattr(val, "to_plotly_json"):
        return sanitize_for_json(val.to_plotly_json())
    elif isinstance(val, pd.DataFrame):
        return sanitize_for_json(val.to_dict(orient="split"))
    elif isinstance(val, Path):
        return str(val)
    return val


class AnalysisCoordinator:
    """
    Orchestrates the entire structural analysis pipeline.
    Decouples UI from backend implementation logic.
    """

    def __init__(self, config: Dict[str, Any], session_id: str = None):
        self.config = config
        self.session_id = session_id
        self.history_db = HistoryDatabase()
        self.ramachandran_service = RamachandranService()
        self.cache_manager = CacheManager(config, self.history_db)
        self.pdb_manager = PDBManager(config, self.cache_manager, session_id=session_id)
        self.mustang_runner = MustangRunner(config)
        self.ligand_analyzer = LigandAnalyzer(config)
        self.rmsd_analyzer = RMSDAnalyzer(config)
        self.sequence_viewer = SequenceViewer()

        # Eagerly check installation to set up the correct backend
        success, msg = self.mustang_runner.check_installation()
        if not success:
            logger.warning(f"Mustang installation check failed: {msg}")
        else:
            logger.info(f"Mustang installation verified: {msg}")

    def _resolve_run_identity(
        self, output_dir: Optional[Path], pdb_ids: List[str]
    ) -> Tuple[Path, str, str, datetime]:
        """Derives (output_dir, run_id, run_name, now) - either fresh, or
        from a caller-supplied output_dir whose name IS the run_id."""
        now = datetime.now()
        if output_dir:
            return (
                output_dir,
                output_dir.name,
                f"Custom Run ({now.strftime('%H:%M')})",
                now,
            )

        run_id = generate_run_id("run", now)
        run_name = f"Analysis of {len(pdb_ids)} structures ({now.strftime('%H:%M')})"
        # Namespace results by session ID
        base = Path("results") / self.session_id if self.session_id else Path("results")
        return base / run_id, run_id, run_name, now

    def _download_structures(self, pdb_ids: List[str]) -> Tuple[bool, str, List[Path]]:
        # Run async batch download from sync context
        download_results = asyncio.run(self.pdb_manager.batch_download(pdb_ids))
        failed = [
            pid for pid, (success, msg, path) in download_results.items() if not success
        ]
        if failed:
            return False, f"Failed to download: {', '.join(failed)}", []

        pdb_files = [path for success, msg, path in download_results.values() if path]
        return True, "", pdb_files

    def _clean_structure(
        self,
        pdb_file: Path,
        chain_selection: Optional[Dict[str, str]],
        remove_water: bool,
        remove_heteroatoms: bool,
    ) -> Tuple[Optional[Path], Optional[str]]:
        """Cleans one downloaded structure, returning (cleaned_path, None)
        on success or (None, failure_description) on failure."""
        pdb_id = pdb_file.stem.split("_")[0].upper()
        target_chain = chain_selection.get(pdb_id) if chain_selection else None

        # Mustang requires exactly one chain per structure.
        # If no specific chain is requested, we automatically pick the first one.
        if not target_chain:
            info = self.pdb_manager.analyze_structure(pdb_file)
            if info["chains"]:
                target_chain = info["chains"][0]["id"]
                logger.info(
                    f"Auto-detected multi-chain PDB {pdb_id}. Selecting chain '{target_chain}' for Mustang."
                )

        _, msg, cleaned_path = self.pdb_manager.clean_pdb(
            pdb_file,
            chain=target_chain,
            remove_water=remove_water,
            remove_heteroatoms=remove_heteroatoms,
        )
        if cleaned_path:
            return cleaned_path, None
        logger.warning(f"Could not clean {pdb_file}: {msg}")
        return None, f"{pdb_id} ({msg})"

    def _clean_structures(
        self,
        pdb_files: List[Path],
        chain_selection: Optional[Dict[str, str]],
        remove_water: bool,
        remove_heteroatoms: bool,
    ) -> Tuple[bool, str, List[Path]]:
        cleaned_files = []
        failed_cleaning = []
        for pdb_file in pdb_files:
            cleaned_path, failure = self._clean_structure(
                pdb_file, chain_selection, remove_water, remove_heteroatoms
            )
            if cleaned_path:
                cleaned_files.append(cleaned_path)
            else:
                failed_cleaning.append(failure)

        # A structure that fails cleaning must not be silently dropped -
        # continuing with fewer structures than requested would produce
        # a misleading result (e.g. the final RMSD matrix would still be
        # shaped for the full requested set, with fabricated values for
        # whichever structure got excluded).
        if failed_cleaning:
            return (
                False,
                f"Failed to prepare structures for alignment: {'; '.join(failed_cleaning)}",
                [],
            )
        return True, "", cleaned_files

    def _analyze_ligands(
        self, pdb_files: List[Path]
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
        """Runs ligand detection on the RAW downloaded structures - cleaning
        strips HETATM records by default, so this must run against
        `pdb_files` from `_download_structures`, never `cleaned_files`.

        Returns (ligand_analysis, all_interactions): `ligand_analysis` is
        `{pdb_id: [get_ligands() dicts]}`, the shape `_get_ligand_insights`
        and `NotebookExporter._ligand_html` already expect. `all_interactions`
        is the flat list of `calculate_interactions()` outputs - one per
        ligand actually found with at least one interacting residue - that
        `calculate_interaction_similarity` needs; ligands that failed to
        resolve or found zero interactions are dropped here so an empty
        pocket can't masquerade as a real dissimilarity signal downstream.

        Each entry's "ligand" field is re-namespaced to "{pdb_id}:{ligand_id}"
        before being returned - `calculate_interaction_similarity` uses that
        field verbatim as the resulting DataFrame's index/columns, and the
        bare ligand_id alone (e.g. "HEM_A_1") doesn't say which structure it
        came from, so two different structures with identically-shaped
        ligand IDs would otherwise be indistinguishable in the result.
        """
        ligand_analysis: Dict[str, List[Dict[str, Any]]] = {}
        all_interactions: List[Dict[str, Any]] = []

        for pdb_file in pdb_files:
            pdb_id = pdb_file.stem.split("_")[0].upper()
            try:
                ligands = self.ligand_analyzer.get_ligands(pdb_file)
            except Exception as e:
                logger.warning(f"Ligand detection failed for {pdb_id}: {e}")
                ligands = []
            ligand_analysis[pdb_id] = ligands

            for ligand in ligands:
                try:
                    interactions = self.ligand_analyzer.calculate_interactions(
                        pdb_file, ligand["id"]
                    )
                except Exception as e:
                    logger.warning(
                        f"Interaction calc failed for {pdb_id}/{ligand['id']}: {e}"
                    )
                    continue
                if "error" not in interactions and interactions.get("interactions"):
                    interactions["ligand"] = f"{pdb_id}:{interactions['ligand']}"
                    all_interactions.append(interactions)

        return ligand_analysis, all_interactions

    def _attach_ligand_analysis(
        self, pdb_files: List[Path], results: Dict[str, Any]
    ) -> None:
        """Mutates `results` with `ligand_analysis` and (when there's
        enough data to compare) `ligand_pocket_similarity`. Best-effort,
        matching `_generate_insights`' philosophy: a bug here must never
        fail an otherwise-successful Compare run."""
        try:
            ligand_analysis, all_interactions = self._analyze_ligands(pdb_files)
            results["ligand_analysis"] = ligand_analysis
            if len(all_interactions) >= 2:
                results["ligand_pocket_similarity"] = (
                    self.ligand_analyzer.calculate_interaction_similarity(
                        all_interactions
                    )
                )
        except Exception as e:
            logger.warning(f"Ligand analysis failed: {e}")
            results["ligand_analysis"] = {}

    def _run_mustang_alignment(
        self, cleaned_files: List[Path], output_dir: Path
    ) -> Tuple[bool, str, Optional[Path]]:
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        success, msg, result_dir = self.mustang_runner.run_alignment(
            cleaned_files, output_dir
        )
        if not success:
            return False, f"Mustang alignment failed: {msg}", None

        # Ensure input PDBs are copied to results
        for pdb_file in cleaned_files:
            dest = result_dir / pdb_file.name
            if not dest.exists():
                shutil.copy2(pdb_file, dest)
        return True, "", result_dir

    @staticmethod
    def _generate_insights(config: Dict[str, Any], results: Dict[str, Any]) -> None:
        """Mutates `results["insights"]` in place - a failure here shouldn't
        fail the whole pipeline, since insights are a nice-to-have summary
        of results that were already computed successfully."""
        try:
            from src.backend.insights import InsightsGenerator

            gen = InsightsGenerator(config)
            results["insights"] = gen.generate_insights(results)
            logger.info("Pre-generated structural insights.")
        except Exception as e:
            logger.warning(f"Failed to generate pre-computed insights: {e}")
            results["insights"] = []

    def _persist_run(
        self,
        run_id: str,
        run_name: str,
        pdb_ids: List[str],
        result_dir: Path,
        chain_selection: Optional[Dict[str, str]],
        remove_water: bool,
        remove_heteroatoms: bool,
        results: Dict[str, Any],
        now: datetime,
    ) -> None:
        """Saves the run to the history DB, writes metadata.json alongside
        the results for portability, and injects the same identity fields
        into `results` for the UI - three views of the same run metadata,
        kept in sync in one place."""
        sanitized_results = sanitize_for_json(results)
        self.history_db.save_run(
            run_id,
            run_name,
            pdb_ids,
            result_dir,
            metadata={
                "chain_selection": chain_selection,
                "clean_params": {
                    "remove_water": remove_water,
                    "remove_heteroatoms": remove_heteroatoms,
                },
                "results": sanitized_results,
            },
            session_id=self.session_id,
        )

        import json

        metadata = {
            "id": run_id,
            "name": run_name,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "protein_count": len(pdb_ids),
            "proteins": pdb_ids,
        }
        with open(result_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=4)

        results["id"] = run_id
        results["name"] = run_name
        results["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")

    def run_full_pipeline(
        self,
        pdb_ids: List[str],
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str, int], None]] = None,
        chain_selection: Optional[Dict[str, str]] = None,
        remove_water: bool = True,
        remove_heteroatoms: bool = True,
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
            output_dir, run_id, run_name, now = self._resolve_run_identity(
                output_dir, pdb_ids
            )

            if progress_callback:
                progress_callback(0.1, "📥 Downloading PDB files...", 1)
            success, msg, pdb_files = self._download_structures(pdb_ids)
            if not success:
                return False, msg, None

            if progress_callback:
                progress_callback(0.3, "🧹 Cleaning PDB files...", 2)
            success, msg, cleaned_files = self._clean_structures(
                pdb_files, chain_selection, remove_water, remove_heteroatoms
            )
            if not success:
                return False, msg, None

            if progress_callback:
                progress_callback(0.5, "⚙️ Running Mustang alignment...", 3)
            success, msg, result_dir = self._run_mustang_alignment(
                cleaned_files, output_dir
            )
            if not success:
                return False, msg, None

            if progress_callback:
                progress_callback(0.75, "📊 Generating visualizations...", 4)
            results = self.process_result_directory(result_dir, pdb_ids)
            if not results:
                return False, "Failed to process result directory", None

            self._attach_ligand_analysis(pdb_files, results)
            self._generate_insights(self.config, results)
            self._persist_run(
                run_id,
                run_name,
                pdb_ids,
                result_dir,
                chain_selection,
                remove_water,
                remove_heteroatoms,
                results,
                now,
            )

            if progress_callback:
                progress_callback(1.0, "✅ Analysis complete!", 4)
            return True, "Analysis completed successfully", results

        except Exception as e:
            logger.exception("Pipeline error")
            return False, str(e), None

    def process_result_directory(
        self, result_dir: Path, pdb_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a completed Mustang run directory into a results dictionary.
        """
        try:
            # Parse RMSD
            rmsd_df = parse_rmsd_matrix(result_dir, pdb_ids)
            if rmsd_df is None:
                return None

            # Persist the authoritative matrix (preferring Mustang's own native
            # .rms_rot output) so ResultManager.get_run_rmsd() — used only by
            # the Comparison tab — reads the same values as everywhere else in
            # the app, instead of mustang_runner's separate, less accurate
            # calculate_structure_rmsd() fallback.
            rmsd_df.to_csv(result_dir / "rmsd_matrix.csv")

            # Static Artifacts
            heatmap_path = result_dir / "rmsd_heatmap.png"
            tree_path = result_dir / "phylogenetic_tree.png"
            newick_path = result_dir / "tree.newick"
            alignment_pdb = result_dir / "alignment.pdb"
            # mustang_runner guarantees alignment.fasta exists (standardized)
            alignment_fasta = result_dir / "alignment.fasta"

            # Calculations
            self.rmsd_analyzer.generate_heatmap(rmsd_df, heatmap_path)
            stats = self.rmsd_analyzer.calculate_statistics(rmsd_df)
            stats["rmsd"] = stats["mean_rmsd"]

            # Quality Metrics (TM-score / GDT-TS)
            quality_metrics = None
            if alignment_pdb.exists() and alignment_fasta.exists():
                quality_metrics = calculate_alignment_quality_metrics(
                    alignment_pdb, alignment_fasta
                )

            # Ramachandran (Torsion) Analysis
            torsion_data = None
            ramachandran_stats = None
            if alignment_pdb.exists():
                torsion_data = self.ramachandran_service.calculate_torsion_angles(
                    alignment_pdb
                )
                if torsion_data:
                    ramachandran_stats = self.ramachandran_service.aggregate_metrics(
                        torsion_data
                    )

            # Calculate sequence identity and save parsed alignments for UI
            sequences = None
            conservation = None
            if alignment_fasta.exists():
                sequences = self.sequence_viewer.parse_afasta(alignment_fasta)
                if sequences:
                    stats["seq_identity"] = self.sequence_viewer.calculate_identity(
                        sequences
                    )
                    conservation = self.sequence_viewer.calculate_conservation(
                        sequences
                    )
                    # Add aligned_length and seq_similarity
                    stats["aligned_length"] = len(next(iter(sequences.values())))
                    similar_cols = sum(1 for c in conservation if c > 0.5)
                    stats["seq_similarity"] = (similar_cols / len(conservation)) * 100

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
                rmsf_values, _ = self.rmsd_analyzer.calculate_residue_rmsf(
                    alignment_pdb, alignment_fasta
                )
            except Exception as e:
                logger.warning(f"Residue RMSF failed: {e}")

            return {
                "pdb_ids": pdb_ids,
                "rmsd_df": rmsd_df,
                "heatmap_path": heatmap_path,
                "stats": stats,
                "clusters": clusters,
                "result_dir": result_dir,
                "tree_path": tree_path,
                "newick_path": newick_path,
                "heatmap_fig": heatmap_fig,
                "tree_fig": tree_fig,
                "alignment_pdb": alignment_pdb,
                "alignment_afasta": alignment_fasta,  # Pass down the real fasta path
                "sequences": sequences,
                "conservation": conservation,
                "rmsf_values": rmsf_values,
                "quality_metrics": quality_metrics,
                "torsion_data": torsion_data,
                "ramachandran_stats": ramachandran_stats,
            }
        except Exception:
            logger.exception("Data processing failed")
            return None
