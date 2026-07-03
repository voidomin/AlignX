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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logger import get_logger
from src.backend.pdb_manager import PDBManager
from src.backend.foldseek_client import FoldseekClient, FoldseekError
from src.backend.annotation_aggregator import AnnotationAggregator
from src.utils.cache_manager import CacheManager
from src.backend.database import HistoryDatabase

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
        self.annotation_aggregator = AnnotationAggregator(config)

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
                    top_n = self.config.get("annotation", {}).get(
                        "top_n_neighbors", 10
                    )
                    annotations = asyncio.run(
                        self.annotation_aggregator.aggregate_for_hits(
                            hits, top_n_neighbors=top_n
                        )
                    )
                except Exception as e:
                    logger.warning(f"Annotation aggregation failed for {pdb_id}: {e}")

            results = {
                "pdb_id": pdb_id.strip().upper(),
                "source": PDBManager.detect_source(pdb_id),
                "databases_searched": databases,
                "hit_count": len(hits),
                "hits": hits,
                "annotations": annotations,
            }
            return True, "Discovery completed successfully", results

        except Exception as e:
            logger.error(f"Discovery pipeline error: {e}", exc_info=True)
            return False, str(e), None
