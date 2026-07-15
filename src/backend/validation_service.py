"""
wwPDB/PDBe Validation Report Service.

Fetches per-entry experimental validation metrics (clashscore, Ramachandran/
rotamer outlier percentiles) for real, experimentally-solved PDB entries -
an externally-curated QC signal, complementary to this app's own local
Ramachandran analysis (ramachandran_service.py), which only ever sees
whatever coordinates are in the specific file downloaded/cleaned here.
"""

from typing import Any, Dict, Optional

import httpx

from src.utils.logger import get_logger, sanitize_for_log

logger = get_logger()

PDBE_VALIDATION_BASE_URL = (
    "https://www.ebi.ac.uk/pdbe/api/validation/global-percentiles/entry"
)

# PDBe's raw key -> (our key, human label). "absolute"/"relative" are
# percentile ranks (0-100) - "absolute" is this entry's percentile across
# the whole PDB archive, "relative" is its percentile among entries of
# similar resolution/method (a fairer comparison - a 3.5A structure isn't
# expected to match a 1.0A one on outlier counts).
_METRIC_KEYS = ("clashscore", "percent-rama-outliers", "percent-rota-outliers")


async def fetch_pdbe_validation(
    pdb_id: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """
    Fetches wwPDB validation metrics for one experimentally-solved PDB
    entry via PDBe's global-percentiles API. Only meaningful for real PDB
    entries (PDBManager.detect_source() == "pdb") - AlphaFold/SWISS-MODEL/
    ESMFold structures have no experimental validation report; callers
    should skip calling this for those sources entirely rather than
    calling it and getting None back.

    Returns None on any failure (entry not found, network error,
    unexpected response shape) - never raises, matching this codebase's
    other external-API fetch functions (e.g. annotation_aggregator.py's
    fetch_* methods).
    """
    try:
        response = await client.get(
            f"{PDBE_VALIDATION_BASE_URL}/{pdb_id.lower()}",
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            return None

        entry = response.json().get(pdb_id.lower())
        if not entry:
            return None

        metrics = {}
        for key in _METRIC_KEYS:
            data = entry.get(key)
            if not data or "rawvalue" not in data:
                continue
            metrics[key.replace("-", "_")] = {
                "value": data["rawvalue"],
                "percentile_archive": data.get("absolute"),
                "percentile_similar_resolution": data.get("relative"),
            }

        return metrics or None
    except httpx.HTTPError as e:
        logger.warning(
            f"PDBe validation lookup failed for {sanitize_for_log(pdb_id)}: {e}"
        )
        return None
    except Exception as e:
        logger.warning(
            f"Failed to parse PDBe validation response for {sanitize_for_log(pdb_id)}: {e}"
        )
        return None
