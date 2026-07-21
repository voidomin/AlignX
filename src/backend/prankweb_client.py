"""
Client for PrankWeb (CUSBG, Charles University), a free, no-key real
geometric ligand-binding-pocket detector (P2Rank) - https://prankweb.cz.
Mirrors ddmut_client.py's submit/poll shape as closely as possible (same
threading-Lock rate limiter, same async submit-then-poll flow) - see that
module's docstrings for detail this one doesn't repeat.

PrankWeb has no publicly documented REST API (its OpenAPI spec at
github.com/cusbg/prankweb/documentation/prankweb.open-api.yaml only
covers polling/result routes, not submission) - the real submission
contract here was found by reading the actual server source
(web-server/src/api_v2.py and database_v3.py in that same repo), then
confirmed live end-to-end before writing this client:
- POST /api/v2/prediction/v3-user-upload (NOT .../v3 - that database is
  read-only for known PDB/UniProt codes; a naive POST there returns 403.
  -user-upload is the only database registered with a working POST
  handler) - multipart with two file fields: `structure` (the raw
  structure file text) and `configuration` (a JSON file:
  {"structure-sealed": true, "chains": [], "prediction-model": "default"}
  - whole-file analysis, no chain restriction, matching this codebase's
  existing heuristic pocket finder's scope). Returns 201 with
  {"id": ..., "status": "queued", ...}.
- Polling is GET /api/v2/prediction/v3-user-upload/{id} until status is
  "successful" or "failed" - unlike DDMut, status and result are two
  separate URLs, not the same one.
- Results are GET /api/v2/prediction/v3-user-upload/{id}/public/
  prediction.json - {"pockets": [{"name", "rank", "score", "probability",
  "center", "residues": ["E_104", ...], "surface": [...]}, ...],
  "structure": {...}, "metadata": {...}}. Confirmed live: 0 pockets for
  crambin (1CRN, no known binding site - a real negative, not a bug),
  6 real pockets for 1ATP (cAMP-dependent protein kinase) with rank-1
  residues matching its known ATP-binding cleft.
"""

import asyncio
import json
import threading
import time
from typing import Any, Dict, Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger()

PRANKWEB_BASE_URL = "https://prankweb.cz/api/v2/prediction/v3-user-upload"
POLL_INTERVAL_SECONDS = 8
MAX_POLL_ATTEMPTS = 60  # 8 minutes ceiling, similar budget to DDMut
_TERMINAL_FAILURE_STATUSES = {"failed"}
# Confirmed live: a real multipart submission (structure + configuration
# files) to this academic server sometimes takes well over 30s to
# acknowledge, not just on a cold start - a naive 30s default intermittently
# timed out on a real ~300KB structure file that succeeded on a later
# attempt with more headroom. This applies to every request this client
# makes (submission and polling both), not just the first one.
DEFAULT_TIMEOUT_SECONDS = 60.0
_MAX_CONSECUTIVE_TRANSPORT_ERRORS = 5


class PrankWebError(Exception):
    """Raised when a PrankWeb pocket-detection job fails, is misconfigured, or times out."""


class _RateLimiter:
    """Serializes outbound requests to PrankWeb's academic server across
    the whole process - same design as ClustalOmegaClient/DDMutClient."""

    def __init__(self, min_interval_seconds: float):
        self._min_interval = min_interval_seconds
        self._lock = threading.Lock()
        self._last_request_at: float = 0.0

    async def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            remaining = self._min_interval - elapsed
            self._last_request_at = max(now, self._last_request_at) + max(
                remaining, 0.0
            )
            wait_for = remaining
        if wait_for > 0:
            await asyncio.sleep(wait_for)


class PrankWebClient:
    # Class-level (not per-instance) so it serializes requests to
    # PrankWeb's academic server across the whole process, same design as
    # ClustalOmegaClient._rate_limiter/DDMutClient._rate_limiter.
    _rate_limiter = _RateLimiter(min_interval_seconds=1.0)

    def __init__(
        self,
        base_url: str = PRANKWEB_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        max_poll_attempts: int = MAX_POLL_ATTEMPTS,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts

    async def submit_structure(
        self, pdb_file_content: str, client: Optional[httpx.AsyncClient] = None
    ) -> str:
        """Submits a real structure file for geometric pocket detection,
        returning PrankWeb's own job id. Retries once on a transient
        connection failure (confirmed live: a real submission attempt
        occasionally drops the connection with no other symptom) before
        giving up, since this is a one-shot step with no later chance to
        recover the way the poll loop has."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            configuration = json.dumps(
                {
                    "structure-sealed": True,
                    "chains": [],
                    "prediction-model": "default",
                }
            )
            files = {
                "structure": ("structure.pdb", pdb_file_content, "text/plain"),
                "configuration": (
                    "configuration.json",
                    configuration,
                    "application/json",
                ),
            }
            response = None
            last_transport_error = None
            for attempt in range(2):
                await self._rate_limiter.wait()
                try:
                    response = await client.post(self.base_url, files=files)
                    break
                except httpx.TransportError as e:
                    last_transport_error = e
                    logger.warning(
                        f"Transient PrankWeb submission error (attempt {attempt + 1}): {e}"
                    )
            if response is None:
                raise last_transport_error
            response.raise_for_status()
            job_id = response.json().get("id")
            if not job_id:
                raise PrankWebError(
                    f"PrankWeb submission did not return an id: {response.text}"
                )
            return job_id
        except httpx.HTTPError as e:
            raise PrankWebError(f"PrankWeb submission failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def poll_until_complete(
        self, job_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Polls PrankWeb's own status endpoint until the job reaches a
        terminal state, then fetches and returns the real completed
        prediction.json payload - status and result are two separate
        URLs on this service, unlike DDMut's single shared endpoint.

        A single poll attempt can hit a transient connection failure
        (confirmed live: a real poll loop against this server dropped one
        connection attempt mid-sequence with no other symptom) without the
        job itself having failed - httpx.TransportError on an individual
        attempt is retried (up to _MAX_CONSECUTIVE_TRANSPORT_ERRORS in a
        row) rather than immediately failing the whole job over one blip.
        """
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        consecutive_transport_errors = 0
        try:
            for _ in range(self.max_poll_attempts):
                await self._rate_limiter.wait()
                try:
                    response = await client.get(f"{self.base_url}/{job_id}")
                    response.raise_for_status()
                    data = response.json()
                except httpx.TransportError as e:
                    consecutive_transport_errors += 1
                    if consecutive_transport_errors > _MAX_CONSECUTIVE_TRANSPORT_ERRORS:
                        raise PrankWebError(f"PrankWeb polling failed: {e}") from e
                    logger.warning(
                        f"Transient PrankWeb polling error for job {job_id} "
                        f"(attempt {consecutive_transport_errors}): {e}"
                    )
                    await asyncio.sleep(self.poll_interval)
                    continue
                consecutive_transport_errors = 0
                status = data.get("status")

                if status == "successful":
                    result_response = await client.get(
                        f"{self.base_url}/{job_id}/public/prediction.json"
                    )
                    result_response.raise_for_status()
                    return result_response.json()
                if status in _TERMINAL_FAILURE_STATUSES:
                    raise PrankWebError(
                        f"PrankWeb job {job_id} failed on the server (status={status})"
                    )

                await asyncio.sleep(self.poll_interval)

            raise PrankWebError(
                f"PrankWeb job {job_id} did not complete within "
                f"{self.max_poll_attempts * self.poll_interval}s"
            )
        except httpx.HTTPError as e:
            raise PrankWebError(f"PrankWeb polling failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def detect_pockets(self, pdb_file_content: str) -> Dict[str, Any]:
        """End-to-end: submit a structure, wait for completion, return the
        real completed prediction payload."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            job_id = await self.submit_structure(pdb_file_content, client=client)
            return await self.poll_until_complete(job_id, client=client)
