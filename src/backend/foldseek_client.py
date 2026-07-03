"""Client for the public Foldseek structural search API (search.foldseek.com).

Foldseek finds structurally similar proteins for a query structure across
PDB, AlphaFold DB, MGnify (ESM Atlas), CATH, and others. This wraps the same
three-step ticket workflow (submit, poll, fetch) used by Foldseek's own web
UI and documented in google-deepmind/science-skills' foldseek-structural-search
skill: https://github.com/google-deepmind/science-skills
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from src.utils.logger import get_logger

logger = get_logger()

FOLDSEEK_BASE_URL = "https://search.foldseek.com"

ALLOWED_DATABASES = [
    "afdb50",
    "afdb-swissprot",
    "pdb100",
    "BFVD",
    "mgnify_esm30",
    "cath50",
    "gmgcl_id",
    "bfmd",
    "afdb-proteome",
]

DEFAULT_DATABASES = ["pdb100", "afdb50"]
POLL_INTERVAL_SECONDS = 10
MAX_POLL_ATTEMPTS = 60  # 10 minutes ceiling


class FoldseekError(Exception):
    """Raised when a Foldseek search fails, is misconfigured, or times out."""


class _RateLimiter:
    """Serializes outbound requests to Foldseek across the whole process.

    The public API asks for a very low request rate. AlignX may have several
    Discover jobs in flight for different users at once, so this limiter is
    shared (a class attribute of FoldseekClient) rather than per-instance, so
    the total outbound rate stays bounded no matter how many jobs are running.
    """

    def __init__(self, min_interval_seconds: float):
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_request_at: float = 0.0

    async def wait(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_at = time.monotonic()


class FoldseekClient:
    """Submits structure files to the public Foldseek web API and retrieves hits."""

    _rate_limiter = _RateLimiter(min_interval_seconds=10.0)

    def __init__(self, config: Optional[Dict[str, Any]] = None, timeout: float = 30.0):
        config = config or {}
        foldseek_cfg = config.get("foldseek", {})
        self.base_url = foldseek_cfg.get("base_url", FOLDSEEK_BASE_URL)
        self.timeout = foldseek_cfg.get("timeout", timeout)
        self.poll_interval = foldseek_cfg.get("poll_interval_seconds", POLL_INTERVAL_SECONDS)
        self.max_poll_attempts = foldseek_cfg.get("max_poll_attempts", MAX_POLL_ATTEMPTS)

    @staticmethod
    def validate_databases(databases: List[str]) -> List[str]:
        invalid = [db for db in databases if db not in ALLOWED_DATABASES]
        if invalid:
            raise FoldseekError(
                f"Unsupported Foldseek database(s): {', '.join(invalid)}. "
                f"Allowed: {', '.join(ALLOWED_DATABASES)}"
            )
        return databases

    async def submit_search(
        self,
        structure_path: Path,
        databases: Optional[List[str]] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """Uploads a structure file and returns a Foldseek ticket ID."""
        databases = self.validate_databases(databases or DEFAULT_DATABASES)

        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            file_bytes = structure_path.read_bytes()
            files = {"q": (structure_path.name, file_bytes, "application/octet-stream")}
            # `data` must be a dict (not a list of tuples) or httpx's encoder
            # mistakes it for raw `content=` and silently drops `files` entirely.
            data = {"mode": "3diaa", "database[]": databases}
            response = await client.post(
                f"{self.base_url}/api/ticket", data=data, files=files
            )
            response.raise_for_status()
            payload = response.json()
            ticket_id = payload.get("id")
            if not ticket_id:
                raise FoldseekError(f"Foldseek did not return a ticket ID: {payload}")
            logger.info(f"Foldseek ticket submitted: {ticket_id} (databases={databases})")
            return ticket_id
        except httpx.HTTPError as e:
            raise FoldseekError(f"Foldseek submission failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def poll_until_complete(
        self, ticket_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> None:
        """Polls a ticket until it completes, raising FoldseekError on failure/timeout."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            for _ in range(self.max_poll_attempts):
                await self._rate_limiter.wait()
                response = await client.get(f"{self.base_url}/api/ticket/{ticket_id}")
                response.raise_for_status()
                status = response.json().get("status")

                if status == "COMPLETE":
                    return
                if status == "ERROR":
                    raise FoldseekError(f"Foldseek job {ticket_id} failed on the server")

                await asyncio.sleep(self.poll_interval)

            raise FoldseekError(
                f"Foldseek job {ticket_id} did not complete within "
                f"{self.max_poll_attempts * self.poll_interval}s"
            )
        except httpx.HTTPError as e:
            raise FoldseekError(f"Foldseek polling failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def fetch_results(
        self, ticket_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Fetches the raw result payload for a completed ticket."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            response = await client.get(f"{self.base_url}/api/result/{ticket_id}/0")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise FoldseekError(f"Foldseek result fetch failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def search(
        self, structure_path: Path, databases: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """End-to-end: submit a structure, wait for completion, return raw hits."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            ticket_id = await self.submit_search(structure_path, databases, client=client)
            await self.poll_until_complete(ticket_id, client=client)
            return await self.fetch_results(ticket_id, client=client)

    @staticmethod
    def parse_hits(raw_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flattens a raw Foldseek result payload into a list of hit dicts."""
        hits: List[Dict[str, Any]] = []
        if isinstance(raw_result, dict):
            if "results" in raw_result:
                for result_group in raw_result.get("results", []):
                    for db_alignments in result_group.get("alignments", []):
                        if isinstance(db_alignments, list):
                            hits.extend(db_alignments)
                        elif isinstance(db_alignments, dict):
                            hits.append(db_alignments)
            elif "alignments" in raw_result:
                hits = raw_result["alignments"]
        elif isinstance(raw_result, list):
            hits = raw_result
        return hits
