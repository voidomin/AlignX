"""Client for Meta's public ESM Atlas ESMFold API
(https://api.esmatlas.com/foldSequence/v1/pdb/), used for real ab-initio
structure prediction directly from a raw amino-acid sequence - no
existing public accession/ID required, unlike every other structure
source this app already supports (RCSB, AlphaFold DB, SWISS-MODEL, ESM
Atlas's own by-accession *lookup*).

Confirmed live this session: a plain POST with the raw sequence as the
request body returns a real PDB file synchronously - no submit/poll/fetch
job pattern needed the way Foldseek/Clustal Omega/BLAST use, since a
150-300 residue sequence completes in single-digit seconds. A 400-residue
random sequence hit the service's own gateway timeout (~30s, a 504 with
no PDB body) - MAX_SEQUENCE_LENGTH is capped well below that rather than
at the ~400 first assumed, so real usage stays inside what's been
empirically verified to finish reliably rather than guessed.
"""

from typing import Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger()

ESMFOLD_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"
# Verified live: 150/200/250/300-residue random sequences all completed in
# under 15s; a 400-residue one hit the service's own ~30s gateway timeout.
# Capped at 300 (not the midpoint) to stay clear of that boundary rather
# than skimming it - a real biological sequence isn't guaranteed to fold
# faster than a random one of the same length.
MAX_SEQUENCE_LENGTH = 300
MIN_SEQUENCE_LENGTH = 10
REQUEST_TIMEOUT_SECONDS = 60.0


class ESMFoldError(Exception):
    """Raised when ESMFold rejects a sequence, is unreachable, or times out."""


async def fold_sequence(
    sequence: str, client: Optional[httpx.AsyncClient] = None
) -> str:
    """
    Predicts a 3D structure directly from `sequence` via ESM Atlas's
    public ESMFold API and returns the raw PDB text. Raises ESMFoldError
    on any failure - a non-200 response, an unreachable/overloaded
    service, or a response with no usable ATOM records.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    try:
        try:
            response = await client.post(ESMFOLD_URL, content=sequence)
        except httpx.HTTPError as e:
            logger.warning(f"ESMFold request failed: {e}")
            raise ESMFoldError(f"ESMFold request failed: {e}") from e

        if response.status_code != 200:
            logger.warning(
                f"ESMFold returned status {response.status_code} for a "
                f"{len(sequence)}-residue sequence"
            )
            raise ESMFoldError(
                f"ESMFold returned status {response.status_code} - the "
                "sequence may be too long or the service may be busy."
            )

        pdb_text = response.text
        if not pdb_text or "ATOM" not in pdb_text:
            raise ESMFoldError(
                "ESMFold returned no usable structure for this sequence."
            )
        return pdb_text
    finally:
        if own_client:
            await client.aclose()
