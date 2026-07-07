"""
Discovery Coordinator Module.
Orchestrates the "what is this structure?" pipeline: download a single
structure, search it against Foldseek's structural databases, fetch
functional annotations for the resolvable neighbors, and return both the
ranked hits and the aggregated annotation summary. This is the
single-structure counterpart to AnalysisCoordinator's pairwise/N-way
Mustang alignment pipeline (see docs/ROADMAP_V3.md) - a tiered, narrative
report on top of this data is a later phase, not implemented here yet.
"""

import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logger import get_logger
from src.backend.pdb_manager import PDBManager
from src.backend.foldseek_client import FoldseekClient, FoldseekError
from src.backend.foldseek_runner import FoldseekRunner
from src.backend.annotation_aggregator import AnnotationAggregator
from src.backend.coordinator import sanitize_for_json
from src.utils.cache_manager import CacheManager
from src.backend.database import HistoryDatabase
from src.utils.run_id import generate_run_id

logger = get_logger()


class DiscoveryCoordinator:
    """Orchestrates the single-structure Foldseek discovery pipeline."""

    def __init__(self, config: Dict[str, Any], session_id: Optional[str] = None):
        self.config = config
        self.session_id = session_id
        self.history_db = HistoryDatabase()
        self.cache_manager = CacheManager(config, self.history_db)
        self.pdb_manager = PDBManager(config, self.cache_manager, session_id=session_id)
        self.foldseek_client = FoldseekClient(config)
        self.foldseek_runner = FoldseekRunner(config)
        self.annotation_aggregator = AnnotationAggregator(
            config, cache_db=self.history_db
        )

    def run_discovery_pipeline(
        self,
        pdb_id: str,
        databases: Optional[List[str]] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Execute the single-structure discovery pipeline.

        Args:
            pdb_id: A single structure identifier (PDB / AF- / SM- / ESM-).
            databases: Foldseek databases to search; defaults to the
                config's `foldseek.default_databases` (pdb100 + afdb50).

        Returns:
            Tuple of (success, message, results_dict). results_dict contains
            "pdb_id", "source", "databases_searched", "hit_count", and "hits"
            (each hit: target, prob, eval, seqId, alnLength, qStartPos/qEndPos).
        """
        try:
            if not PDBManager.validate_pdb_id(pdb_id):
                return False, f"Invalid structure identifier: {pdb_id}", None

            databases = databases or self.config.get("foldseek", {}).get(
                "default_databases", ["pdb100", "afdb50"]
            )

            success, msg, structure_path = asyncio.run(
                self.pdb_manager.download_pdb(pdb_id)
            )
            if not success or not structure_path:
                return False, f"Failed to download {pdb_id}: {msg}", None

            backend = self.config.get("foldseek", {}).get("backend", "api")
            if backend == "local":
                success, msg, hits = self._search_local(structure_path)
                if not success:
                    return False, msg, None
                databases = [
                    f"local:{self.config['foldseek']['local']['database_dir']}"
                ]
            else:
                try:
                    raw_result = asyncio.run(
                        self.foldseek_client.search(structure_path, databases)
                    )
                except FoldseekError as e:
                    return False, f"Foldseek search failed: {e}", None

                hits = self.foldseek_client.parse_hits(raw_result)

            # Annotation lookups are best-effort: a flaky InterPro/QuickGO
            # response must not fail the whole discovery run when we already
            # have valid Foldseek hits to show.
            annotations = None
            if hits:
                try:
                    top_n = self.config.get("annotation", {}).get("top_n_neighbors", 10)
                    annotations = asyncio.run(
                        self.annotation_aggregator.aggregate_for_hits(
                            hits, top_n_neighbors=top_n
                        )
                    )
                except Exception as e:
                    logger.warning(f"Annotation aggregation failed for {pdb_id}: {e}")

            now = datetime.now()
            run_id = generate_run_id("discover", now)
            run_name = f"Discovery: {pdb_id.strip().upper()} ({now.strftime('%H:%M')})"

            results = {
                "id": run_id,
                "name": run_name,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "pdb_id": pdb_id.strip().upper(),
                "source": PDBManager.detect_source(pdb_id),
                "databases_searched": databases,
                "hit_count": len(hits),
                "hits": hits,
                "annotations": annotations,
            }

            # Persist to history so Discover runs show up on the Dashboard
            # and History tab the same way Compare (alignment) runs already
            # do - "run_type": "discover" in metadata lets the frontend tell
            # the two apart and route a click on a past run appropriately,
            # since there's no shared result shape between them (no
            # alignment.pdb/RMSD matrix to reload for a Discover run).
            self.history_db.save_run(
                run_id,
                run_name,
                [pdb_id.strip().upper()],
                result_path=Path("results") / (self.session_id or "") / run_id,
                metadata={
                    "run_type": "discover",
                    "results": sanitize_for_json(results),
                },
                session_id=self.session_id,
            )

            return True, "Discovery completed successfully", results

        except Exception as e:
            logger.exception("Discovery pipeline error")
            return False, str(e), None

    def _search_local(
        self, structure_path: Path
    ) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """Runs the search via a locally-installed Foldseek binary against
        `foldseek.local.database_dir` instead of the public API. See
        FoldseekRunner's module docstring for what "local" does and doesn't
        cover (proven against a small test database; provisioning a
        production-scale database is a separate deployment step)."""
        database_dir = (
            self.config.get("foldseek", {}).get("local", {}).get("database_dir")
        )
        if not database_dir:
            return (
                False,
                "Local Foldseek backend selected but foldseek.local.database_dir "
                "is not configured.",
                None,
            )

        tmp_dir = Path(tempfile.mkdtemp(prefix="foldseek_local_"))
        try:
            success, msg, hits = self.foldseek_runner.search_against_directory(
                structure_path, Path(database_dir), tmp_dir
            )
            if not success:
                return False, msg, None
            return True, msg, hits
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
