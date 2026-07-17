"""Client for DDMut (University of Queensland Biosig Lab), a free, no-key
mutation-stability (ddG) prediction service - https://biosig.lab.uq.edu.au/ddmut.
Mirrors clustalo_client.py's submit/poll shape as closely as possible (same
threading-Lock rate limiter, same async submit-then-poll flow) - see that
module's docstrings for detail this one doesn't repeat.

Confirmed live this session (the published API docs describe a slightly
different response shape than what the server actually returns, so this
was verified end-to-end, not assumed from the docs alone):
- POST /ddmut/api/prediction_single accepts either `pdb_accession` (a real
  4-character PDB code, which DDMut itself downloads) or a `pdb_file`
  upload (any PDB-format text) - `pdb_file` is used exclusively here since
  it works for every structure source this app has (AlphaFold/SWISS-Model/
  ESM Atlas/uploaded/predicted structures have no PDB accession at all),
  not just real RCSB entries.
- Both submission and polling hit the *same* URL - submission is a POST,
  polling is (unusually) a GET carrying `job_id` as multipart form data,
  not a query string (a plain query-string GET returns a server error -
  verified live).
- A real completed response looks like:
  {"job_id": "...", "status": "DONE", "prediction": 0.22, "chain": "A",
   "position": "6", "wild-type": "LYS", "mutant": "ALA",
   "results_page": "https://..."} - `prediction` is the predicted ddG in
  kcal/mol (positive = mutation stabilizes, negative = destabilizes,
  DDMut's own convention). A still-running job returns
  {"job_id": "...", "status": "RUNNING"} with no `prediction` key.
"""

import asyncio
import threading
import time
from typing import Any, Dict, Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger()

DDMUT_BASE_URL = "https://biosig.lab.uq.edu.au/ddmut/api/prediction_single"
POLL_INTERVAL_SECONDS = 10
MAX_POLL_ATTEMPTS = 60  # 10 minutes ceiling, same budget as other job-shaped clients
_TERMINAL_FAILURE_STATUSES = {"ERROR", "FAILED", "FAILURE"}


class DDMutError(Exception):
    """Raised when a DDMut ddG-prediction job fails, is misconfigured, or times out."""


class _RateLimiter:
    """Serializes outbound requests to DDMut's small academic server across
    the whole process - same design as ClustalOmegaClient's rate limiter."""

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


class DDMutClient:
    # Class-level (not per-instance) so it serializes requests to DDMut's
    # small academic server across the whole process, same design as
    # ClustalOmegaClient._rate_limiter.
    _rate_limiter = _RateLimiter(min_interval_seconds=1.0)

    def __init__(
        self,
        base_url: str = DDMUT_BASE_URL,
        timeout: float = 30.0,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        max_poll_attempts: int = MAX_POLL_ATTEMPTS,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts

    async def submit_mutation(
        self,
        pdb_file_content: str,
        chain: str,
        mutation: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """Submits a real structure file + point-mutation code
        (aaFrom+residueNumber+aaTo, e.g. "H461D") for a ddG stability
        prediction, returning DDMut's own job ID."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            files = {"pdb_file": ("structure.pdb", pdb_file_content, "text/plain")}
            data = {"chain": chain, "mutation": mutation}
            response = await client.post(self.base_url, data=data, files=files)
            response.raise_for_status()
            job_id = response.json().get("job_id")
            if not job_id:
                raise DDMutError(
                    f"DDMut submission did not return a job_id: {response.text}"
                )
            return job_id
        except httpx.HTTPError as e:
            raise DDMutError(f"DDMut submission failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def poll_until_complete(
        self, job_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Polls DDMut's own submission URL (status and result share one
        endpoint) until the job reaches a terminal state, returning the
        real completed prediction payload."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            for _ in range(self.max_poll_attempts):
                await self._rate_limiter.wait()
                # DDMut's polling endpoint expects job_id as multipart form
                # data on a GET request, not a query string - verified live
                # (a query-string GET returns a server error).
                response = await client.request(
                    "GET", self.base_url, data={"job_id": job_id}
                )
                response.raise_for_status()
                data = response.json()
                status = data.get("status")

                if status == "DONE":
                    return data
                if status in _TERMINAL_FAILURE_STATUSES:
                    raise DDMutError(
                        f"DDMut job {job_id} failed on the server (status={status})"
                    )

                await asyncio.sleep(self.poll_interval)

            raise DDMutError(
                f"DDMut job {job_id} did not complete within "
                f"{self.max_poll_attempts * self.poll_interval}s"
            )
        except httpx.HTTPError as e:
            raise DDMutError(f"DDMut polling failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def predict_stability(
        self, pdb_file_content: str, chain: str, mutation: str
    ) -> Dict[str, Any]:
        """End-to-end: submit a structure + mutation, wait for completion,
        return the real completed prediction payload."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            job_id = await self.submit_mutation(
                pdb_file_content, chain, mutation, client=client
            )
            return await self.poll_until_complete(job_id, client=client)
