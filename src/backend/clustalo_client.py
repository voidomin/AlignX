"""Client for EBI's Job Dispatcher Clustal Omega REST API
(https://www.ebi.ac.uk/jdispatcher/msa/clustalo), used for a true
sequence-only multiple alignment - independent of Mustang's structural
alignment, which this app otherwise relies on exclusively for sequence
correspondence. Mirrors foldseek_client.py's submit/poll/fetch/rate-
limiter shape as closely as possible (same three-step ticket workflow,
same reasons for each design choice - see that module's docstrings for
detail this one doesn't repeat).

Confirmed live this session: POST /run (multipart form: email, stype,
sequence) returns a plain-text job ID (e.g. "clustalo-R20260715-...");
GET /status/{job_id} returns plain text ("QUEUED" -> "RUNNING" ->
"FINISHED"); GET /result/{job_id}/fa returns real aligned FASTA
(gap-padded, directly parseable by Bio.SeqIO the same way alignment.fasta
already is elsewhere in this app).
"""

import asyncio
import threading
import time
from typing import Any, Dict, Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger()

CLUSTALO_BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest/clustalo"
# EBI's Job Dispatcher requires a contact email on every submission (its own
# terms of use, not an identifying credential) - a generic project address
# is standard practice for a server-side integration with no per-user email
# of its own to offer.
DEFAULT_EMAIL = "structscope@example.com"
POLL_INTERVAL_SECONDS = 10
MAX_POLL_ATTEMPTS = 60  # 10 minutes ceiling, same budget as FoldseekClient
_TERMINAL_FAILURE_STATUSES = {"ERROR", "FAILURE", "NOT_FOUND"}


class ClustalOmegaError(Exception):
    """Raised when a Clustal Omega alignment job fails, is misconfigured, or times out."""


class _RateLimiter:
    """Serializes outbound requests to EBI's Job Dispatcher across the whole
    process - same threading.Lock-based design as FoldseekClient's rate
    limiter (see that class's docstring for why asyncio.Lock is unsafe
    here: concurrent jobs run their HTTP calls inside independent
    asyncio.run() calls on separate worker threads, and a plain
    threading.Lock is real OS-level mutual exclusion, correct across
    that in a way asyncio.Lock is not)."""

    def __init__(self, min_interval_seconds: float):
        self._min_interval = min_interval_seconds
        self._lock = threading.Lock()
        self._last_request_at: float = 0.0

    async def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._last_request_at = max(now, self._last_request_at + self._min_interval)
            wait_time = self._last_request_at - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)


class ClustalOmegaClient:
    """Submits sequences to EBI's public Clustal Omega REST API and
    retrieves the resulting alignment."""

    _rate_limiter = _RateLimiter(min_interval_seconds=3.0)

    def __init__(self, config: Optional[Dict[str, Any]] = None, timeout: float = 30.0):
        config = config or {}
        cfg = config.get("clustalo", {})
        self.base_url = cfg.get("base_url", CLUSTALO_BASE_URL)
        self.email = cfg.get("email", DEFAULT_EMAIL)
        self.timeout = cfg.get("timeout", timeout)
        self.poll_interval = cfg.get("poll_interval_seconds", POLL_INTERVAL_SECONDS)
        self.max_poll_attempts = cfg.get("max_poll_attempts", MAX_POLL_ATTEMPTS)

    @staticmethod
    def _to_fasta(sequences: Dict[str, str]) -> str:
        return "\n".join(f">{seq_id}\n{seq}" for seq_id, seq in sequences.items())

    async def submit_alignment(
        self, sequences: Dict[str, str], client: Optional[httpx.AsyncClient] = None
    ) -> str:
        """Submits a {id: raw_sequence} dict for a true sequence-only MSA
        and returns EBI's job ID. `sequences` should carry each
        structure's own ungapped sequence (not a Mustang-aligned one) -
        the whole point of this alignment is to be independent of
        Mustang's structural correspondence."""
        if len(sequences) < 2:
            raise ClustalOmegaError("At least 2 sequences are required for an MSA.")

        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            data = {
                "email": self.email,
                "stype": "protein",
                "outfmt": "fa",
                "sequence": self._to_fasta(sequences),
            }
            response = await client.post(f"{self.base_url}/run", data=data)
            response.raise_for_status()
            job_id = response.text.strip()
            if not job_id:
                raise ClustalOmegaError("Clustal Omega did not return a job ID")
            logger.info(
                f"Clustal Omega job submitted: {job_id} ({len(sequences)} sequences)"
            )
            return job_id
        except httpx.HTTPError as e:
            raise ClustalOmegaError(f"Clustal Omega submission failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def poll_until_complete(
        self, job_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> None:
        """Polls a job until it finishes, raising ClustalOmegaError on
        failure/timeout."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            for _ in range(self.max_poll_attempts):
                await self._rate_limiter.wait()
                response = await client.get(f"{self.base_url}/status/{job_id}")
                response.raise_for_status()
                status = response.text.strip()

                if status == "FINISHED":
                    return
                if status in _TERMINAL_FAILURE_STATUSES:
                    raise ClustalOmegaError(
                        f"Clustal Omega job {job_id} failed on the server (status={status})"
                    )

                await asyncio.sleep(self.poll_interval)

            raise ClustalOmegaError(
                f"Clustal Omega job {job_id} did not complete within "
                f"{self.max_poll_attempts * self.poll_interval}s"
            )
        except httpx.HTTPError as e:
            raise ClustalOmegaError(f"Clustal Omega polling failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def fetch_alignment(
        self, job_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> str:
        """Fetches the completed job's aligned FASTA text (result type
        "fa" - gap-padded, directly parseable by Bio.SeqIO)."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            response = await client.get(f"{self.base_url}/result/{job_id}/fa")
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            raise ClustalOmegaError(f"Clustal Omega result fetch failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def align(self, sequences: Dict[str, str]) -> str:
        """End-to-end: submit sequences, wait for completion, return the
        aligned FASTA text."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            job_id = await self.submit_alignment(sequences, client=client)
            await self.poll_until_complete(job_id, client=client)
            return await self.fetch_alignment(job_id, client=client)
