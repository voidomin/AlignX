"""Client for NCBI's BLAST URL API (https://blast.ncbi.nlm.nih.gov/Blast.cgi),
used to find real homologs of a query sequence and compute real per-column
evolutionary conservation from them - unlike sequence_viewer.py's existing
calculate_conservation(), which only measures identity across whatever
structures happen to be loaded in the current workspace, not real
evolutionary conservation across a homolog panel.

Confirmed live this session: CMD=Put returns an HTML page with a real
RID/RTOE pair embedded in a QBlastInfoBegin/QBlastInfoEnd block (e.g.
"RID = 5FUFR8MX014", "RTOE = 36"); CMD=Get&FORMAT_OBJECT=SearchInfo returns
"Status=WAITING"/"Status=READY" the same way; CMD=Get&FORMAT_TYPE=XML
returns real Hit/Hsp XML.

Unlike foldseek_client.py/clustalo_client.py, this deliberately builds a
query-anchored conservation profile directly from BLAST's own per-hit
pairwise alignments (Hsp_qseq/Hsp_hseq), rather than fetching each
homolog's full sequence and re-aligning all of them with Clustal Omega.
Every HSP is already aligned to the same query, so using the query as the
common coordinate system is mathematically equivalent to (and how
PSSM/profile-based conservation scoring standardly works) - not a lesser
approximation, and it avoids stacking two independent multi-minute
external-service round trips into one feature.

NCBI's usage policy for this API explicitly asks for at most one status
poll per minute and a first poll no sooner than RTOE seconds after
submission - both enforced directly in poll_until_complete() below,
separate from the shared _RateLimiter (which only throttles submit/fetch
calls, not the poll loop's own cadence).
"""

import asyncio
import math
import re
import threading
import time
from collections import Counter
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import httpx

from src.utils.logger import get_logger

logger = get_logger()

BLAST_BASE_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
DEFAULT_PROGRAM = "blastp"
DEFAULT_DATABASE = "nr"
DEFAULT_HITLIST_SIZE = 20
# NCBI policy: no more than one status check per minute.
MIN_POLL_INTERVAL_SECONDS = 60
MAX_POLL_ATTEMPTS = 20  # ~20 minutes ceiling - real BLAST searches can take a while
_TERMINAL_FAILURE_STATUSES = {"FAILED", "UNKNOWN"}
# Standard 20-letter amino acid alphabet - the denominator for normalizing
# Shannon entropy into a 0-1 conservation score (log2(20) is the maximum
# possible entropy for a fully random column).
_MAX_ENTROPY_BITS = math.log2(20)


class BlastError(Exception):
    """Raised when a BLAST search fails, is misconfigured, or times out."""


class _RateLimiter:
    """Serializes outbound submit/fetch requests to NCBI's BLAST API across
    the whole process - same threading.Lock-based design as FoldseekClient/
    ClustalOmegaClient's rate limiters (see either for why asyncio.Lock is
    unsafe here). Deliberately NOT used for the poll loop's own cadence -
    poll_until_complete() enforces NCBI's stricter 1/minute polling policy
    directly, since this limiter's job is just per-call courtesy spacing."""

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


class BlastClient:
    """Submits a protein sequence to NCBI's public BLAST API and retrieves
    real homolog hits."""

    _rate_limiter = _RateLimiter(min_interval_seconds=3.0)

    def __init__(self, config: Optional[Dict[str, Any]] = None, timeout: float = 30.0):
        config = config or {}
        cfg = config.get("blast", {})
        self.base_url = cfg.get("base_url", BLAST_BASE_URL)
        self.program = cfg.get("program", DEFAULT_PROGRAM)
        self.database = cfg.get("database", DEFAULT_DATABASE)
        self.hitlist_size = cfg.get("hitlist_size", DEFAULT_HITLIST_SIZE)
        self.timeout = cfg.get("timeout", timeout)
        self.poll_interval = cfg.get("poll_interval_seconds", MIN_POLL_INTERVAL_SECONDS)
        self.max_poll_attempts = cfg.get("max_poll_attempts", MAX_POLL_ATTEMPTS)

    async def submit_search(
        self, sequence: str, client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Submits a protein sequence and returns {"rid": ..., "rtoe": ...}
        - `rtoe` is NCBI's own estimated seconds-to-completion, used as the
        minimum delay before the first status poll."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            data = {
                "CMD": "Put",
                "PROGRAM": self.program,
                "DATABASE": self.database,
                "QUERY": sequence,
                "HITLIST_SIZE": str(self.hitlist_size),
            }
            response = await client.post(self.base_url, data=data)
            response.raise_for_status()
            text = response.text
            rid_match = re.search(r"RID\s*=\s*(\S+)", text)
            rtoe_match = re.search(r"RTOE\s*=\s*(\d+)", text)
            if not rid_match:
                raise BlastError("NCBI BLAST did not return a request ID (RID)")
            rid = rid_match.group(1)
            logger.info(f"BLAST job submitted: {rid}")
            return {"rid": rid, "rtoe": int(rtoe_match.group(1)) if rtoe_match else 30}
        except httpx.HTTPError as e:
            raise BlastError(f"BLAST submission failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def poll_until_complete(
        self,
        rid: str,
        initial_wait_seconds: float = 0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Polls a submitted job until it's ready, raising BlastError on
        failure/timeout. `initial_wait_seconds` should be the RTOE value
        submit_search() returned - polling before NCBI's own estimated
        completion time just wastes a poll slot."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            if initial_wait_seconds > 0:
                await asyncio.sleep(initial_wait_seconds)

            for _ in range(self.max_poll_attempts):
                await self._rate_limiter.wait()
                response = await client.get(
                    self.base_url,
                    params={"CMD": "Get", "FORMAT_OBJECT": "SearchInfo", "RID": rid},
                )
                response.raise_for_status()
                status_match = re.search(r"Status=(\w+)", response.text)
                status = status_match.group(1) if status_match else "UNKNOWN"

                if status == "READY":
                    return
                if status in _TERMINAL_FAILURE_STATUSES:
                    raise BlastError(
                        f"BLAST job {rid} failed on the server (status={status})"
                    )

                await asyncio.sleep(self.poll_interval)

            raise BlastError(
                f"BLAST job {rid} did not complete within "
                f"{self.max_poll_attempts * self.poll_interval}s"
            )
        except httpx.HTTPError as e:
            raise BlastError(f"BLAST polling failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    async def fetch_hits(
        self, rid: str, client: Optional[httpx.AsyncClient] = None
    ) -> List[Dict[str, Any]]:
        """Fetches the completed job's results as XML and parses out one
        entry per hit's best HSP - see parse_hits_xml()."""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            await self._rate_limiter.wait()
            response = await client.get(
                self.base_url,
                params={"CMD": "Get", "FORMAT_TYPE": "XML", "RID": rid},
            )
            response.raise_for_status()
            return self.parse_hits_xml(response.text)
        except httpx.HTTPError as e:
            raise BlastError(f"BLAST result fetch failed: {e}") from e
        finally:
            if own_client:
                await client.aclose()

    @staticmethod
    def parse_hits_xml(xml_text: str) -> List[Dict[str, Any]]:
        """Parses real BLAST XML into a list of
        {accession, title, qseq, hseq, query_from} - one per hit's first
        (highest-scoring) HSP, since that's all build_conservation_profile()
        needs to place each homolog's aligned sequence into the query's own
        coordinate system. Returns [] on malformed/empty XML rather than
        raising - a BLAST search with zero real hits is a valid outcome,
        not an error."""
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            logger.warning("Failed to parse BLAST XML result")
            return []

        hits = []
        for hit in root.iter("Hit"):
            hsp = hit.find("Hit_hsps/Hsp")
            if hsp is None:
                continue
            qseq = hsp.findtext("Hsp_qseq") or ""
            hseq = hsp.findtext("Hsp_hseq") or ""
            query_from_text = hsp.findtext("Hsp_query-from")
            if not qseq or not hseq or not query_from_text:
                continue
            hits.append(
                {
                    "accession": (hit.findtext("Hit_accession") or "").strip(),
                    "title": (hit.findtext("Hit_def") or "").strip(),
                    "qseq": qseq,
                    "hseq": hseq,
                    "query_from": int(query_from_text),
                }
            )
        return hits

    @staticmethod
    def build_conservation_profile(
        query_length: int, hits: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Real per-query-position evolutionary conservation from a homolog
        panel, via Shannon entropy over each column's observed residues
        (normalized against log2(20), the maximum possible entropy for the
        20-letter amino acid alphabet) - 1.0 means every homolog agrees at
        that position, 0.0 means maximally diverse. `query_from` is
        1-indexed (BLAST convention); a homolog's own internal gaps
        (insertions relative to the query) are skipped since they don't
        correspond to any query column. Positions no hit covers get
        conservation: None rather than a misleading 0.0 or 1.0."""
        column_residues: Dict[int, List[str]] = {
            i: [] for i in range(1, query_length + 1)
        }

        for hit in hits:
            pos = hit["query_from"]
            for q_char, h_char in zip(hit["qseq"], hit["hseq"]):
                if q_char == "-":
                    continue  # insertion in the homolog - not a query column
                if 1 <= pos <= query_length:
                    column_residues[pos].append(h_char.upper())
                pos += 1

        profile = []
        for position in range(1, query_length + 1):
            observed = column_residues[position]
            residues = [r for r in observed if r != "-"]
            if not residues:
                profile.append(
                    {
                        "position": position,
                        "conservation": None,
                        "num_homologs": len(observed),
                        "most_common": None,
                    }
                )
                continue

            counts = Counter(residues)
            total = len(residues)
            entropy = -sum((n / total) * math.log2(n / total) for n in counts.values())
            conservation = max(0.0, min(1.0, 1.0 - entropy / _MAX_ENTROPY_BITS))
            profile.append(
                {
                    "position": position,
                    "conservation": conservation,
                    "num_homologs": len(observed),
                    "most_common": counts.most_common(1)[0][0],
                }
            )
        return profile

    async def find_homologs_and_score_conservation(
        self, sequence: str
    ) -> Dict[str, Any]:
        """End-to-end: submit the query, wait for completion, fetch hits,
        and build the real conservation profile."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            submission = await self.submit_search(sequence, client=client)
            await self.poll_until_complete(
                submission["rid"], submission["rtoe"], client=client
            )
            hits = await self.fetch_hits(submission["rid"], client=client)
            profile = self.build_conservation_profile(len(sequence), hits)
            return {
                "rid": submission["rid"],
                "num_hits": len(hits),
                "conservation_profile": profile,
            }
