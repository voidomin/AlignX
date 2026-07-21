"""Client for EBI's Job Dispatcher InterProScan5 REST API
(https://www.ebi.ac.uk/jdispatcher/pfa/iprscan5), used for real domain/GO-
term/pathway annotation directly from a raw sequence - independent of the
UniProt-accession-resolution path AnnotationAggregator otherwise relies on
exclusively. This is the one annotation path that works for structures
with no resolvable UniProt accession at all (ESM Atlas/uploaded/ESMFold-
predicted structures). Mirrors clustalo_client.py's submit/poll/fetch/
rate-limiter shape as closely as possible, since it's the same EBI Job
Dispatcher family - see that module's docstrings for detail this one
doesn't repeat.

Confirmed live this session: POST /run (form: email, sequence, goterms,
pathways, appl) returns a plain-text job ID (e.g.
"iprscan5-R20260721-..."); GET /status/{job_id} returns plain text
("RUNNING" -> "FINISHED"); GET /result/{job_id}/json returns a real
result JSON. One real discrepancy from a naive reading of the feature
names, confirmed via GET /parameterdetails/appl rather than assumed: the
`appl` parameter's accepted values are "PfamA" (not "Pfam") and
"PrositeProfiles" (not "PROSITE-ProfileScan") - a request using the more
intuitive-sounding names is rejected with a 400 "Invalid parameters"
error.
"""

import asyncio
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.utils.logger import get_logger

logger = get_logger()

INTERPROSCAN_BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"
# Same EBI Job Dispatcher contact-email requirement as ClustalOmegaClient.
DEFAULT_EMAIL = "structscope@example.com"
# A small, fast, high-signal subset of InterProScan5's ~20 available
# applications rather than every one - confirmed live this keeps a real
# job's turnaround to under two minutes for a typical protein, instead of
# running every database InterProScan5 supports.
DEFAULT_APPLICATIONS = "PfamA,PrositeProfiles"
POLL_INTERVAL_SECONDS = 10
MAX_POLL_ATTEMPTS = 60  # 10 minutes ceiling, same budget as Clustal Omega
_TERMINAL_FAILURE_STATUSES = {"ERROR", "FAILURE", "NOT_FOUND"}


class InterProScanError(Exception):
    """Raised when an InterProScan5 job fails, is misconfigured, or times out."""


class _RateLimiter:
    """Serializes outbound requests to EBI's Job Dispatcher across the
    whole process - same design as ClustalOmegaClient's rate limiter."""

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


class InterProScanClient:
    """Submits a raw protein sequence to EBI's public InterProScan5 REST
    API and retrieves the resulting domain/GO-term/pathway annotation."""

    _rate_limiter = _RateLimiter(min_interval_seconds=3.0)

    def __init__(
        self,
        base_url: str = INTERPROSCAN_BASE_URL,
        email: str = DEFAULT_EMAIL,
        applications: str = DEFAULT_APPLICATIONS,
        timeout: float = 30.0,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        max_poll_attempts: int = MAX_POLL_ATTEMPTS,
    ):
        self.base_url = base_url
        self.email = email
        self.applications = applications
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts

    async def submit_sequence(
        self, sequence: str, client: Optional[httpx.AsyncClient] = None
    ) -> str:
        """Submits a raw amino-acid sequence for annotation, returning
        EBI's job ID."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            data = {
                "email": self.email,
                "sequence": sequence,
                "goterms": "true",
                "pathways": "true",
                "appl": self.applications,
            }
            response = await client.post(f"{self.base_url}/run", data=data)
            response.raise_for_status()
            job_id = response.text.strip()
            if not job_id:
                raise InterProScanError("InterProScan5 did not return a job ID")
            logger.info(f"InterProScan5 job submitted: {job_id}")
            return job_id
        except httpx.HTTPError as e:
            raise InterProScanError(f"InterProScan5 submission failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def poll_until_complete(
        self, job_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> None:
        """Polls a job until it finishes, raising InterProScanError on
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
                    raise InterProScanError(
                        f"InterProScan5 job {job_id} failed on the server (status={status})"
                    )

                await asyncio.sleep(self.poll_interval)

            raise InterProScanError(
                f"InterProScan5 job {job_id} did not complete within "
                f"{self.max_poll_attempts * self.poll_interval}s"
            )
        except httpx.HTTPError as e:
            raise InterProScanError(f"InterProScan5 polling failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def fetch_result(
        self, job_id: str, client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Fetches the completed job's real result JSON."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            response = await client.get(f"{self.base_url}/result/{job_id}/json")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise InterProScanError(f"InterProScan5 result fetch failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def annotate(self, sequence: str) -> Dict[str, Any]:
        """End-to-end: submit a sequence, wait for completion, return the
        real completed result JSON."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            job_id = await self.submit_sequence(sequence, client=client)
            await self.poll_until_complete(job_id, client=client)
            return await self.fetch_result(job_id, client=client)

    @staticmethod
    def parse_domains_and_go_terms(
        result: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Flattens InterProScan5's real result JSON into the same
        {name, type, locations}-shaped domain list and {id, name, aspect}
        -shaped GO-term list AnnotationAggregator's InterPro-accession
        path already produces, so the frontend's existing renderDomainList/
        renderGoTermList utilities need no new render logic - just this
        one adapter. Real duplicate GO-term rows (the same term backed by
        two different signature matches) are deduplicated by id, matching
        aggregate_for_structure's own existing dedup convention."""
        domains: List[Dict[str, Any]] = []
        seen_go_ids = set()
        go_terms: List[Dict[str, Any]] = []

        for hit in result.get("results") or []:
            for match in hit.get("matches") or []:
                signature = match.get("signature") or {}
                entry = signature.get("entry") or {}
                if entry.get("accession"):
                    locations = [
                        {
                            "start": loc.get("start"),
                            "end": loc.get("end"),
                        }
                        for loc in match.get("locations") or []
                        if loc.get("start") and loc.get("end")
                    ]
                    domains.append(
                        {
                            "accession": entry["accession"],
                            "name": entry.get("name") or entry["accession"],
                            "type": entry.get("type", "domain"),
                            "locations": locations,
                        }
                    )
                for go_ref in entry.get("goXRefs") or []:
                    go_id = go_ref.get("id")
                    if not go_id or go_id in seen_go_ids:
                        continue
                    seen_go_ids.add(go_id)
                    go_terms.append(
                        {
                            "id": go_id,
                            "name": go_ref.get("name"),
                            "aspect": go_ref.get("category"),
                        }
                    )

        return domains, go_terms
