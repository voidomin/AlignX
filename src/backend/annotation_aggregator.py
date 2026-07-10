"""
Annotation Aggregator Module.
Given a list of Foldseek structural-neighbor hits (see FoldseekClient),
fetches functional annotations (InterPro domains, QuickGO terms, STRING
interaction partners, Reactome pathways) for whichever neighbors we can
resolve to a UniProt accession, plus Pfam domains from GMGC's own API for
gmgcl_id hits (which have no UniProt accession at all), and aggregates the
ontology-based signals (domains, GO terms) into frequency summaries across
the neighbor set.

This is Phase 3 of the Discover pipeline (docs/ROADMAP_V3.md), extended
with the STRING/Reactome/GMGC fast-follows flagged there. Turning this
into a tiered, narrative "function hypothesis" report is a later phase.
"""

import asyncio
import json
import re
import threading
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.utils.logger import get_logger, sanitize_for_log

logger = get_logger()

INTERPRO_BASE_URL = "https://www.ebi.ac.uk/interpro/api"
QUICKGO_BASE_URL = "https://www.ebi.ac.uk/QuickGO/services"
STRING_BASE_URL = "https://version-12-0.string-db.org/api/json"
REACTOME_BASE_URL = "https://reactome.org/ContentService"
SIFTS_BASE_URL = "https://www.ebi.ac.uk/pdbe/api/mappings/uniprot"
GMGC_BASE_URL = "https://gmgc.embl.de/api/v1.0"
STRING_CALLER_IDENTITY = "structscope"
_JSON_ACCEPT_HEADERS = {"Accept": "application/json"}

# Foldseek's AlphaFold DB hits are named "AF-{UniProt}-F{fragment}[-v{n}] ...",
# which embeds a UniProt accession directly - free to extract, no lookup.
_AFDB_TARGET_PATTERN = re.compile(r"^AF-([A-Z0-9]+)-F\d+", re.IGNORECASE)

# pdb100 hits are named "{pdbid}-assembly{n}.cif.gz_{chain} {title}", e.g.
# "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN" or, for a specific biological
# assembly copy, "2ij9-assembly1.cif.gz_A-2" (the "-2" is an assembly copy
# suffix, not part of the real author chain ID, and must be stripped before
# querying SIFTS). These don't embed a UniProt accession, but PDBe's SIFTS
# mapping API resolves {pdb_id, chain} -> UniProt accession directly - see
# resolve_pdb_uniprot_accession().
_PDB_TARGET_PATTERN = re.compile(r"^([0-9A-Za-z]{4})-assembly\d+\.cif\.gz_(\S+)")

# cath50 hits are named as a 7-character CATH domain ID: 4-char PDB code +
# 1-char author chain + 2-digit domain number within that chain, e.g.
# "1cbnA00" -> PDB "1CBN", chain "A". This is directly a (pdb_id, chain)
# pair, same as pdb100's, so it resolves through the same SIFTS lookup -
# see resolve_accession(). Confirmed live against 1CRN's cath50 hits.
_CATH_DOMAIN_PATTERN = re.compile(r"^(\d[A-Za-z0-9]{3})([A-Za-z0-9])\d{2}$")

# BFVD and bfmd hits embed a UniProt accession as one underscore/dot/hyphen-
# delimited token in their target string - e.g. BFVD's
# "A0A7U0G8Z5_unrelaxed_rank_001_alphafold2_ptm_model_2_seed_000" or bfmd's
# "LevyLab_Q8U2A3_V1_4_relaxed_B" and "ProtVar_P08559_Q9Y6H1_B" (a variant
# pair - the first accession is used). Confirmed live against 1CRN. The
# pattern is UniProt's own official accession regex (6- or 10-character
# form); mgnify_esm30 ("MGYP...") hits have no such token and are genuinely
# unresolvable - they're not UniProt-keyed at all, not just missing a lookup
# step, and are expected to often have no existing annotation at all, since
# it's specifically metagenomic "dark matter" sequences (see
# docs/ROADMAP_V3.md).
_UNIPROT_ACCESSION_RE = re.compile(
    r"^([OPQ]\d[A-Z0-9]{3}\d|[A-NR-Z]\d([A-Z][A-Z0-9]{2}\d){1,2})$"
)

# gmgcl_id hits are named "GMGC10.{9-digit cluster id}.{eggnog-mapper name
# or "UNKNOWN"}_trun_{n}.pdb" - not UniProt-keyed at all, but GMGC's own API
# (gmgc.embl.de/api_help.cgi) resolves the gene ID itself (everything before
# "_trun_{n}[.pdb]", which Foldseek/PDB-export bookkeeping appended and isn't
# part of the real ID) directly to Pfam/eggNOG annotation - no UniProt
# involved. Confirmed live: e.g. "GMGC10.040_893_565.PILY1_trun_2.pdb" ->
# gene ID "GMGC10.040_893_565.PILY1" -> a real Pfam domain hit
# (Neisseria_PilC) via GMGC's /unigene/{id}/features endpoint. The name
# segment can itself contain underscores (e.g. "SCLAV_5304" in GMGC's own
# docs), so the pattern is non-greedy up to the first "_trun_{n}" suffix
# rather than splitting on the last underscore.
_GMGC_TARGET_PATTERN = re.compile(
    r"^(GMGC10\.\d{3}_\d{3}_\d{3}\.\S+?)_trun_\d+(?:\.pdb)?$", re.IGNORECASE
)

DEFAULT_TOP_N_NEIGHBORS = 10
DEFAULT_TOP_N_SUMMARY = 10
DEFAULT_TOP_N_PARTNERS = 5
DEFAULT_TOP_N_PATHWAYS = 5
# How many extra candidates (beyond top_n_neighbors) to consider when
# ranking, so a few unresolvable hits (e.g. from a database we can't map,
# or a PDB entry with no SIFTS mapping) can't starve the annotation step of
# a full top_n_neighbors' worth of real signal.
CANDIDATE_OVERSAMPLE_FACTOR = 2


class _RateLimiter:
    """Serializes requests to a single-QPS-limited API across the process.

    Same threading.Lock-based design as FoldseekClient's rate limiter (see
    that module's docstring for why asyncio.Lock is unsafe here): each
    Discover job's annotation fetches run inside their own asyncio.run() on
    a dedicated worker thread, so concurrent jobs call this from different
    event loops. A plain threading.Lock is real OS-level mutual exclusion
    and works correctly across that.

    The lock only ever guards the synchronous slot-reservation math below,
    never the actual wait - aggregate_for_hits() runs multiple neighbors'
    annotation fetches concurrently via asyncio.gather() on the SAME event
    loop, so two of *this same job's* coroutines really can call wait() at
    once. Sleeping (via time.sleep(), previously) while still holding the
    lock would block that whole thread for the sleep's duration - fine on
    its own - but a sibling gathered coroutine hitting `with self._lock:`
    during that window does a blocking, synchronous acquire() on a lock its
    own thread already holds, which freezes the event loop that would
    otherwise have advanced the timer and released it: a real, reproducible
    deadlock the moment 2+ neighbors need this rate limiter in the same
    job. Reserving the slot (a fast, non-yielding calculation) inside the
    lock and awaiting the actual delay outside it avoids that entirely,
    while still serializing correctly: each reservation is pushed at least
    min_interval past the previous one, regardless of which thread or
    coroutine claims it or how long that caller then takes to actually
    sleep.
    """

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


class AnnotationAggregator:
    """Fetches and aggregates InterPro/QuickGO/STRING/Reactome annotations
    for Foldseek hits."""

    # STRING's science-skills reference client uses qps=1; be a good citizen.
    _string_rate_limiter = _RateLimiter(min_interval_seconds=1.0)

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
        cache_db: Optional[Any] = None,
    ):
        config = config or {}
        annotation_cfg = config.get("annotation", {})
        self.timeout = annotation_cfg.get("timeout", timeout)
        # Duck-typed (get_annotation_cache/set_annotation_cache) rather than
        # importing HistoryDatabase directly, since callers already have one
        # instance to share (DiscoveryCoordinator's self.history_db) and
        # constructing a second sqlite connection here would be wasteful.
        # InterPro/QuickGO/SIFTS/STRING/Reactome data changes rarely, so
        # caching it avoids refetching the same accession every time someone
        # (or a different user) looks up a popular protein again.
        self.cache_db = cache_db
        self.cache_ttl_days = annotation_cfg.get("cache_ttl_days", 30)
        # Gates whether the Public/Student tiers state a function
        # hypothesis at all (see aggregate_for_hits'
        # high_confidence_annotated_count) - having *any* curated
        # annotation isn't enough on its own if the structural match
        # itself was weak. 0.5 matches common structural-bioinformatics
        # practice for "same fold" significance (e.g. TM-align/Dali-style
        # thresholds); Foldseek's own docs describe prob approaching 1.0
        # as "extreme confidence," so this is a deliberately permissive
        # floor, not a strict one - see docs/ROADMAP_V3.md open questions.
        self.min_confident_probability = annotation_cfg.get(
            "min_confident_probability", 0.5
        )

    async def _get_or_fetch(self, cache_key: str, service: str, fetch_fn) -> Any:
        """Checks the persistent annotation cache before calling fetch_fn
        (an async no-arg callable), and stores whatever it returns. A cache
        read/write failure is not fatal - it just means this call behaves
        as if there were no cache, same as when cache_db is None."""
        if self.cache_db:
            try:
                cached = self.cache_db.get_annotation_cache(
                    cache_key, self.cache_ttl_days
                )
                if cached is not None:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(
                    f"Annotation cache read failed for {sanitize_for_log(cache_key)}: {e}"
                )

        result = await fetch_fn()

        if self.cache_db:
            try:
                self.cache_db.set_annotation_cache(
                    cache_key, service, json.dumps(result)
                )
            except Exception as e:
                logger.warning(
                    f"Annotation cache write failed for {sanitize_for_log(cache_key)}: {e}"
                )

        return result

    @staticmethod
    def extract_uniprot_accession(target: str) -> Optional[str]:
        """Pulls a UniProt accession out of a Foldseek AFDB target string,
        e.g. "AF-P01541-F1-model_v6 Denclatoxin-B" -> "P01541"."""
        match = _AFDB_TARGET_PATTERN.match((target or "").strip())
        return match.group(1).upper() if match else None

    @staticmethod
    def extract_pdb_chain(target: str) -> Optional[Tuple[str, str]]:
        """Pulls (pdb_id, chain_id) out of a Foldseek pdb100 target string,
        e.g. "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN" -> ("1AB1", "A"). Any
        trailing "-{n}" assembly-copy suffix on the chain (e.g. "A-2") is
        stripped, since SIFTS mappings are keyed by the real author chain ID."""
        match = _PDB_TARGET_PATTERN.match((target or "").strip())
        if not match:
            return None
        pdb_id, raw_chain = match.groups()
        chain_id = re.sub(r"-\d+$", "", raw_chain)
        return pdb_id.upper(), chain_id

    @staticmethod
    def extract_cath_pdb_chain(target: str) -> Optional[Tuple[str, str]]:
        """Pulls (pdb_id, chain_id) out of a Foldseek cath50 target string
        (a CATH domain ID), e.g. "1cbnA00" -> ("1CBN", "A")."""
        match = _CATH_DOMAIN_PATTERN.match((target or "").strip())
        if not match:
            return None
        pdb_id, chain_id = match.groups()
        return pdb_id.upper(), chain_id

    @staticmethod
    def extract_embedded_uniprot_accession(target: str) -> Optional[str]:
        """Finds a UniProt-accession-shaped token embedded in a Foldseek
        target string (BFVD/bfmd), e.g.
        "LevyLab_Q8U2A3_V1_4_relaxed_B" -> "Q8U2A3". Returns the first
        matching token; a bfmd variant-pair target has two, and either is a
        valid resolvable neighbor, so there's no strong reason to prefer one
        over the other beyond "the one that appears first"."""
        for token in re.split(r"[_.\-]", (target or "").strip()):
            if _UNIPROT_ACCESSION_RE.match(token.upper()):
                return token.upper()
        return None

    @staticmethod
    def extract_gmgc_gene_id(target: str) -> Optional[str]:
        """Pulls the real GMGC gene ID out of a Foldseek gmgcl_id target
        string, e.g. "GMGC10.040_893_565.PILY1_trun_2.pdb" ->
        "GMGC10.040_893_565.PILY1". Unlike every other resolvable database,
        this isn't a UniProt accession - GMGC's own API annotates it
        directly, see fetch_gmgc_features()."""
        match = _GMGC_TARGET_PATTERN.match((target or "").strip())
        return match.group(1) if match else None

    @staticmethod
    def _parse_sifts_chain_accessions(entry: Dict[str, Any]) -> Dict[str, str]:
        """Flattens a SIFTS `/mappings/{pdb_id}` entry's per-accession chain
        mappings into a single {chain_id: accession} dict."""
        chain_accessions: Dict[str, str] = {}
        for accession, info in (entry.get("UniProt") or {}).items():
            for mapping in info.get("mappings", []):
                mapped_chain = mapping.get("chain_id")
                if mapped_chain:
                    chain_accessions[mapped_chain] = accession.upper()
        return chain_accessions

    async def resolve_pdb_uniprot_accession(
        self,
        pdb_id: str,
        chain_id: str,
        client: httpx.AsyncClient,
        cache: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
    ) -> Optional[str]:
        """Resolves a (PDB entry, chain) pair to a UniProt accession via
        PDBe's SIFTS mapping API. `cache` (keyed by pdb_id -> {chain_id:
        accession}) lets one aggregate_for_hits() call avoid re-fetching the
        same entry's mapping for multiple hits/chains that share it (common,
        since a well-studied protein is often deposited many times)."""
        if cache is not None and pdb_id in cache:
            return cache[pdb_id].get(chain_id)

        async def _fetch() -> Dict[str, Optional[str]]:
            try:
                response = await client.get(
                    f"{SIFTS_BASE_URL}/{pdb_id.lower()}",
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return {}
                entry = response.json().get(pdb_id.lower(), {})
                return self._parse_sifts_chain_accessions(entry)
            except httpx.HTTPError as e:
                logger.warning(
                    f"SIFTS lookup failed for {sanitize_for_log(pdb_id)}: {e}"
                )
                return {}

        chain_accessions = await self._get_or_fetch(f"sifts:{pdb_id}", "sifts", _fetch)

        if cache is not None:
            cache[pdb_id] = chain_accessions
        return chain_accessions.get(chain_id)

    async def resolve_accession(
        self,
        hit: Dict[str, Any],
        client: httpx.AsyncClient,
        pdb_cache: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
    ) -> Optional[str]:
        """Resolves a Foldseek hit to a UniProt accession via whichever
        method applies to its target format: the free AFDB regex first,
        then an embedded-accession token (BFVD/bfmd), then a live SIFTS
        lookup for pdb100/cath50 hits (both resolve to a (pdb_id, chain)
        pair, just via different target formats)."""
        target = hit.get("target", "")
        accession = self.extract_uniprot_accession(target)
        if accession:
            return accession
        embedded = self.extract_embedded_uniprot_accession(target)
        if embedded:
            return embedded
        pdb_chain = self.extract_pdb_chain(target) or self.extract_cath_pdb_chain(
            target
        )
        if pdb_chain:
            return await self.resolve_pdb_uniprot_accession(
                *pdb_chain, client, pdb_cache
            )
        return None

    async def fetch_interpro_entries(
        self, accession: str, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Returns InterPro entries (domains/families/sites) matching a
        UniProt protein, each with any GO terms InterPro itself associates
        with that entry."""

        async def _fetch() -> List[Dict[str, Any]]:
            url = f"{INTERPRO_BASE_URL}/entry/interpro/protein/uniprot/{accession}"
            try:
                response = await client.get(
                    url,
                    params={"page_size": 50},
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return []
                entries = []
                for item in response.json().get("results", []):
                    meta = item.get("metadata", {})
                    entries.append(
                        {
                            "accession": meta.get("accession"),
                            "name": meta.get("name"),
                            "type": meta.get("type"),
                            "go_terms": [
                                {
                                    "id": g.get("identifier"),
                                    "name": g.get("name"),
                                    "aspect": (g.get("category") or {}).get("name"),
                                }
                                for g in meta.get("go_terms") or []
                            ],
                        }
                    )
                return entries
            except httpx.HTTPError as e:
                logger.warning(
                    f"InterPro lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return []

        return await self._get_or_fetch(f"interpro:{accession}", "interpro", _fetch)

    async def fetch_quickgo_annotations(
        self, accession: str, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Returns this protein's own GO annotations from QuickGO (broader
        and evidence-coded, unlike InterPro's generic per-domain GO terms)."""

        async def _fetch() -> List[Dict[str, Any]]:
            url = f"{QUICKGO_BASE_URL}/annotation/search"
            try:
                response = await client.get(
                    url,
                    params={"geneProductId": f"UniProtKB:{accession}", "limit": 100},
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return []
                return [
                    {
                        "id": r.get("goId"),
                        "aspect": r.get("goAspect"),
                        "qualifier": r.get("qualifier"),
                        "evidence": r.get("goEvidence"),
                    }
                    for r in response.json().get("results") or []
                    if r.get("goId")
                ]
            except httpx.HTTPError as e:
                logger.warning(
                    f"QuickGO lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return []

        return await self._get_or_fetch(f"quickgo:{accession}", "quickgo", _fetch)

    async def fetch_string_partners(
        self,
        accession: str,
        taxon_id: Optional[int],
        client: httpx.AsyncClient,
        limit: int = DEFAULT_TOP_N_PARTNERS,
    ) -> List[Dict[str, Any]]:
        """Returns this protein's top STRING interaction partners.

        STRING requires an NCBI taxon ID and only covers organisms with a
        fully sequenced, published genome - most Foldseek AFDB hits (e.g.
        metagenomic or less-studied plant/fungal proteins) simply won't be
        in STRING at all, so an empty result here is the common case, not
        an error. `taxon_id` comes from the Foldseek hit's own `taxId`
        field when present, avoiding a separate species-lookup call.
        """
        if not taxon_id:
            return []

        async def _fetch() -> List[Dict[str, Any]]:
            url = f"{STRING_BASE_URL}/interaction_partners"
            try:
                await self._string_rate_limiter.wait()
                response = await client.post(
                    url,
                    data={
                        "identifiers": accession,
                        "species": taxon_id,
                        "limit": limit,
                        "caller_identity": STRING_CALLER_IDENTITY,
                    },
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return []
                payload = response.json()
                if isinstance(payload, dict) and payload.get("Error"):
                    return []  # e.g. "unknown organism" - not in STRING's coverage
                return [
                    {
                        "partner_name": r.get("preferredName_B"),
                        "score": r.get("score"),
                    }
                    for r in payload
                    if isinstance(r, dict) and r.get("preferredName_B")
                ]
            except httpx.HTTPError as e:
                logger.warning(
                    f"STRING lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return []

        return await self._get_or_fetch(
            f"string:{accession}:{taxon_id}", "string", _fetch
        )

    async def fetch_reactome_pathways(
        self,
        accession: str,
        client: httpx.AsyncClient,
        limit: int = DEFAULT_TOP_N_PATHWAYS,
    ) -> List[Dict[str, Any]]:
        """Returns pathways this protein participates in, per Reactome."""

        async def _fetch() -> List[Dict[str, Any]]:
            url = f"{REACTOME_BASE_URL}/data/mapping/UniProt/{accession}/pathways"
            try:
                response = await client.get(url, headers=_JSON_ACCEPT_HEADERS)
                if response.status_code != 200:
                    return []
                return [
                    {"id": p.get("stId"), "name": p.get("displayName")}
                    for p in response.json() or []
                    if p.get("stId")
                ][:limit]
            except httpx.HTTPError as e:
                logger.warning(
                    f"Reactome lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return []

        return await self._get_or_fetch(f"reactome:{accession}", "reactome", _fetch)

    async def fetch_gmgc_features(
        self, gene_id: str, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Returns Pfam domain hits for a GMGC unigene via GMGC's own
        /unigene/{id}/features endpoint. gmgcl_id hits have no UniProt
        accession at all (unlike every other resolvable database), so this
        bypasses the InterPro/QuickGO/STRING/Reactome pipeline entirely and
        queries GMGC's own eggNOG-mapper-derived annotation directly.
        Confirmed live: real hits do carry named Pfam domains, not just the
        "UNKNOWN" placeholder some gene IDs show."""

        async def _fetch() -> List[Dict[str, Any]]:
            url = f"{GMGC_BASE_URL}/unigene/{gene_id}/features"
            try:
                response = await client.get(url, headers=_JSON_ACCEPT_HEADERS)
                if response.status_code != 200:
                    return []
                pfam_hits = (response.json().get("features") or {}).get("pfam") or []
                domains = []
                for entry in pfam_hits:
                    domain_id = (entry.get("domain") or "").split(":")[-1]
                    if domain_id:
                        domains.append(
                            {
                                "accession": domain_id,
                                "name": domain_id,
                                "type": "pfam",
                                "go_terms": [],
                            }
                        )
                return domains
            except httpx.HTTPError as e:
                logger.warning(
                    f"GMGC features lookup failed for {sanitize_for_log(gene_id)}: {e}"
                )
                return []

        return await self._get_or_fetch(f"gmgc:{gene_id}", "gmgc", _fetch)

    def _try_get_cached_go_name(self, gid: str) -> Optional[str]:
        if not self.cache_db:
            return None
        try:
            cached = self.cache_db.get_annotation_cache(
                f"goterm:{gid}", self.cache_ttl_days
            )
            return json.loads(cached) if cached is not None else None
        except Exception as e:
            logger.warning(f"GO term cache read failed for {gid}: {e}")
            return None

    def _try_cache_go_name(self, gid: str, name: str) -> None:
        if not self.cache_db:
            return
        try:
            self.cache_db.set_annotation_cache(
                f"goterm:{gid}", "goterm", json.dumps(name)
            )
        except Exception as e:
            logger.warning(f"GO term cache write failed for {gid}: {e}")

    async def _fetch_go_term_names_chunk(
        self, chunk: List[str], client: httpx.AsyncClient
    ) -> Dict[str, str]:
        names: Dict[str, str] = {}
        url = f"{QUICKGO_BASE_URL}/ontology/go/terms/{','.join(chunk)}"
        try:
            response = await client.get(url, headers=_JSON_ACCEPT_HEADERS)
            if response.status_code != 200:
                return names
            for term in response.json().get("results", []):
                if term.get("id") and term.get("name"):
                    names[term["id"]] = term["name"]
                    self._try_cache_go_name(term["id"], term["name"])
        except httpx.HTTPError as e:
            logger.warning(f"GO term name resolution failed for {chunk}: {e}")
        return names

    async def resolve_go_term_names(
        self, go_ids: List[str], client: httpx.AsyncClient
    ) -> Dict[str, str]:
        """Batch-resolves GO IDs to human-readable names (QuickGO's
        annotation search endpoint returns IDs but not names). GO term names
        are essentially static, so each ID is cached individually - a
        request for 50 IDs where 45 are already cached only needs to fetch
        the remaining 5 from QuickGO."""
        unique_ids = sorted({gid for gid in go_ids if gid})
        names: Dict[str, str] = {}
        uncached_ids = []
        for gid in unique_ids:
            cached_name = self._try_get_cached_go_name(gid)
            if cached_name is not None:
                names[gid] = cached_name
            else:
                uncached_ids.append(gid)

        chunk_size = 50
        for i in range(0, len(uncached_ids), chunk_size):
            chunk = uncached_ids[i : i + chunk_size]
            names.update(await self._fetch_go_term_names_chunk(chunk, client))
        return names

    async def _resolve_structure_accession(
        self,
        pdb_id: str,
        chain: Optional[str],
        source: str,
        client: httpx.AsyncClient,
        pdb_cache: Optional[Dict[str, Dict[str, Optional[str]]]],
    ) -> Optional[str]:
        """Resolves a Compare-mode structure ID (not a Foldseek hit) to a
        UniProt accession, by source database (see
        PDBManager.detect_source()). "alphafold" IDs are the exact same
        "AF-{uniprot}-F{n}" format Foldseek's own AFDB hits use, so the
        existing free-regex extractor applies unmodified. "swissmodel" IDs
        embed the accession directly ("SM-{uniprot}"), same one-line parse
        PDBManager._fetch_swissmodel_metadata already does for its own
        metadata fetch. "pdb" (plain 4-char) IDs need the chain and a real
        SIFTS lookup, same as a Foldseek pdb100/cath50 hit. "esmfold"
        (ESM Atlas) structures have no UniProt mapping at all - metagenomic,
        uncharacterized sequences - so no lookup is attempted."""
        if source == "alphafold":
            return self.extract_uniprot_accession(pdb_id)
        if source == "swissmodel":
            parts = pdb_id.split("-", 1)
            return parts[1].upper() if len(parts) == 2 and parts[1] else None
        if source == "pdb" and chain:
            return await self.resolve_pdb_uniprot_accession(
                pdb_id, chain, client, pdb_cache
            )
        return None

    async def aggregate_for_structure(
        self,
        pdb_id: str,
        chain: Optional[str],
        source: str,
        client: httpx.AsyncClient,
        pdb_cache: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
    ) -> Dict[str, Any]:
        """Fetches functional annotation (InterPro domains, QuickGO terms,
        Reactome pathways) for one Compare-mode structure. Unlike
        aggregate_for_hits(), there is no Foldseek-style confidence gating
        here - a structure you explicitly chose to align isn't a
        probabilistic structural-neighbor match, it's just itself, so
        every accession that resolves gets annotated the same way. STRING
        interaction partners are out of scope (Compare mode has no taxon_id
        source the way a Foldseek hit's own taxId gives Discover mode one
        for free)."""
        accession = await self._resolve_structure_accession(
            pdb_id, chain, source, client, pdb_cache
        )

        result: Dict[str, Any] = {
            "pdb_id": pdb_id,
            "chain": chain,
            "accession": accession,
            "domains": [],
            "go_terms": [],
            "reactome_pathways": [],
        }
        if not accession:
            return result

        domains, quickgo_terms, reactome_pathways = await asyncio.gather(
            self.fetch_interpro_entries(accession, client),
            self.fetch_quickgo_annotations(accession, client),
            self.fetch_reactome_pathways(accession, client),
        )

        go_ids = [g["id"] for g in quickgo_terms if g.get("id")]
        names = await self.resolve_go_term_names(go_ids, client)
        for term in quickgo_terms:
            term["name"] = names.get(term.get("id"))

        result["domains"] = domains
        # QuickGO's annotation-search returns one row per curated evidence
        # code, so a well-studied protein's common GO terms (e.g. "protein
        # binding") routinely appear many times over - real duplicate
        # records, not a bug in the fetch. Discover mode never surfaces
        # this raw list directly (only a neighbor-frequency-deduplicated
        # summary), but a single structure's own annotation has no
        # frequency dimension to dedupe by, so it's deduplicated by GO id
        # here instead, keeping the first (evidence-code-agnostic for
        # display purposes) occurrence of each.
        seen_go_ids = set()
        deduped_terms = []
        for term in quickgo_terms:
            gid = term.get("id")
            if gid in seen_go_ids:
                continue
            seen_go_ids.add(gid)
            deduped_terms.append(term)
        result["go_terms"] = deduped_terms
        result["reactome_pathways"] = reactome_pathways
        return result

    @staticmethod
    def _hit_sort_key(hit: Dict[str, Any]) -> float:
        try:
            return float(hit.get("eval", hit.get("eValue", hit.get("evalue", 1e9))))
        except (TypeError, ValueError):
            return 1e9

    async def _annotate_neighbor(
        self,
        hit: Dict[str, Any],
        accession: Optional[str],
        client: httpx.AsyncClient,
        gmgc_gene_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetches the full annotation set for a hit that's already been
        resolved - either to a UniProt accession (see resolve_accession()),
        routing through InterPro/QuickGO/STRING/Reactome, or to a GMGC gene
        ID (see extract_gmgc_gene_id()), routing through GMGC's own Pfam
        annotation instead since gmgcl_id hits have no UniProt accession at
        all. Kept separate from resolution so aggregate_for_hits can resolve
        a larger, cheap candidate pool before paying for the full annotation
        calls only on the neighbors it actually keeps."""
        neighbor: Dict[str, Any] = {
            "target": hit.get("target", ""),
            "accession": accession or gmgc_gene_id,
            # Foldseek's own structural-match confidence for this hit,
            # independent of whether the accession happened to have
            # curated functional annotations. Needed to gate the
            # Public/Student "function hypothesis" narrative on match
            # quality, not just on annotation presence - see
            # aggregate_for_hits' high_confidence_annotated_count.
            "prob": hit.get("prob"),
            "eval": hit.get("eval"),
            "domains": [],
            "go_terms": [],
            "string_partners": [],
            "reactome_pathways": [],
        }
        if accession:
            # Foldseek's own hit payload already carries a taxId for AFDB
            # matches, so STRING gets it for free - no extra species lookup.
            taxon_id = hit.get("taxId")
            domains, quickgo_terms, string_partners, reactome_pathways = (
                await asyncio.gather(
                    self.fetch_interpro_entries(accession, client),
                    self.fetch_quickgo_annotations(accession, client),
                    self.fetch_string_partners(accession, taxon_id, client),
                    self.fetch_reactome_pathways(accession, client),
                )
            )
            neighbor["domains"] = domains
            neighbor["go_terms"] = quickgo_terms
            neighbor["string_partners"] = string_partners
            neighbor["reactome_pathways"] = reactome_pathways
        elif gmgc_gene_id:
            # No UniProt accession to key STRING/Reactome on for a GMGC gene
            # - just the Pfam domain signal GMGC's own API provides.
            neighbor["domains"] = await self.fetch_gmgc_features(gmgc_gene_id, client)
        return neighbor

    async def _resolve_candidates(
        self,
        hits: List[Dict[str, Any]],
        candidate_pool_size: int,
        client: httpx.AsyncClient,
    ) -> Tuple[List[Dict[str, Any]], List[Optional[str]], List[Optional[str]], int]:
        """Resolves the oversampled candidate pool to (accession, gmgc_gene_id)
        pairs. Returns (candidates, accessions, gmgc_gene_ids, resolved_count)."""
        candidates = sorted(hits, key=self._hit_sort_key)[:candidate_pool_size]
        pdb_cache: Dict[str, Dict[str, Optional[str]]] = {}
        accessions = await asyncio.gather(
            *(self.resolve_accession(hit, client, pdb_cache) for hit in candidates)
        )
        # gmgcl_id hits have no UniProt accession at all (see
        # extract_gmgc_gene_id()'s docstring), so they're only checked
        # for a GMGC-resolvable gene ID once UniProt resolution has
        # already failed - the two are mutually exclusive per hit.
        gmgc_gene_ids = [
            None if acc else self.extract_gmgc_gene_id(hit.get("target", ""))
            for hit, acc in zip(candidates, accessions)
        ]
        resolved_count = sum(
            1 for acc, gid in zip(accessions, gmgc_gene_ids) if acc or gid
        )
        return candidates, accessions, gmgc_gene_ids, resolved_count

    def _collect_neighbor_keys(
        self,
        neighbor: Dict[str, Any],
        resolved_names: Dict[str, str],
        domain_meta: Dict[Tuple[str, str], Dict[str, Any]],
        go_meta: Dict[str, Dict[str, Any]],
    ) -> Tuple[set, set]:
        """One neighbor's distinct domain keys and GO ids, updating the
        shared `domain_meta`/`go_meta` lookups as a side effect (a domain's
        or GO term's metadata is the same regardless of which neighbor's
        counters it ends up contributing to)."""
        domain_keys = set()
        go_ids = set()

        for domain in neighbor["domains"]:
            key = (domain.get("name"), domain.get("type"))
            domain_keys.add(key)
            domain_meta[key] = domain
            for g in domain.get("go_terms") or []:
                if g.get("id"):
                    go_ids.add(g["id"])
                    go_meta.setdefault(
                        g["id"], {"name": g.get("name"), "aspect": g.get("aspect")}
                    )

        for g in neighbor["go_terms"]:
            if g.get("id"):
                go_ids.add(g["id"])
                go_meta.setdefault(
                    g["id"],
                    {"name": resolved_names.get(g["id"]), "aspect": g.get("aspect")},
                )

        return domain_keys, go_ids

    def _count_neighbor_annotations(
        self, per_neighbor: List[Dict[str, Any]], resolved_names: Dict[str, str]
    ) -> Tuple[Counter, Dict, Counter, Dict, Counter, Counter]:
        """Tallies domain/GO-term frequency across all neighbors, plus a
        parallel "confident" tally restricted to neighbors whose own
        structural match probability clears min_confident_probability -
        Public/Student should only state a function hypothesis from that
        filtered set, while Researcher gets the unfiltered counts."""
        domain_counter: Counter = Counter()
        domain_meta: Dict[Tuple[str, str], Dict[str, Any]] = {}
        go_counter: Counter = Counter()
        go_meta: Dict[str, Dict[str, Any]] = {}
        confident_domain_counter: Counter = Counter()
        confident_go_counter: Counter = Counter()

        for neighbor in per_neighbor:
            is_confident = (
                isinstance(neighbor.get("prob"), (int, float))
                and neighbor["prob"] >= self.min_confident_probability
            )
            domain_keys, go_ids = self._collect_neighbor_keys(
                neighbor, resolved_names, domain_meta, go_meta
            )
            for key in domain_keys:
                domain_counter[key] += 1
                if is_confident:
                    confident_domain_counter[key] += 1
            for gid in go_ids:
                go_counter[gid] += 1
                if is_confident:
                    confident_go_counter[gid] += 1

        return (
            domain_counter,
            domain_meta,
            go_counter,
            go_meta,
            confident_domain_counter,
            confident_go_counter,
        )

    @staticmethod
    def _top_domains(
        counter: Counter,
        domain_meta: Dict[Tuple[str, str], Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "type": entry_type,
                "interpro_accession": domain_meta[(name, entry_type)].get("accession"),
                "neighbor_count": count,
            }
            for (name, entry_type), count in counter.most_common(top_n)
        ]

    @staticmethod
    def _top_go_terms(
        counter: Counter, go_meta: Dict[str, Dict[str, Any]], top_n: int
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": gid,
                "name": go_meta[gid].get("name"),
                "aspect": go_meta[gid].get("aspect"),
                "neighbor_count": count,
            }
            for gid, count in counter.most_common(top_n)
        ]

    def _neighbor_summary_counts(
        self, per_neighbor: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        # All neighbors here already have a resolved accession; "annotated"
        # distinguishes those where InterPro/QuickGO actually returned data
        # from those where the accession resolved but lookups came back
        # empty (e.g. an unreviewed UniProt entry with no curated
        # annotations yet).
        annotated_count = sum(1 for n in per_neighbor if n["domains"] or n["go_terms"])
        # A neighbor only counts here if it's BOTH annotated AND its own
        # Foldseek match probability clears min_confident_probability -
        # having curated annotations isn't enough on its own if the
        # structural match itself was weak. This gates whether Public/
        # Student state a function hypothesis at all (see DiscoverTab).
        high_confidence_annotated_count = sum(
            1
            for n in per_neighbor
            if (n["domains"] or n["go_terms"])
            and isinstance(n.get("prob"), (int, float))
            and n["prob"] >= self.min_confident_probability
        )
        # STRING/Reactome coverage is reported separately, not folded into
        # "annotated_neighbor_count": their absence is expected and common
        # (STRING only covers organisms with a sequenced genome; Reactome's
        # curated pathway coverage skews toward well-studied model species),
        # not a sign the annotation step failed the way an empty
        # domains/go_terms result would be.
        return {
            "annotated_count": annotated_count,
            "high_confidence_annotated_count": high_confidence_annotated_count,
            "interaction_count": sum(1 for n in per_neighbor if n["string_partners"]),
            "pathway_count": sum(1 for n in per_neighbor if n["reactome_pathways"]),
        }

    async def aggregate_for_hits(
        self,
        hits: List[Dict[str, Any]],
        top_n_neighbors: int = DEFAULT_TOP_N_NEIGHBORS,
        top_n_summary: int = DEFAULT_TOP_N_SUMMARY,
    ) -> Dict[str, Any]:
        """
        Fetches annotations for the most confident *resolvable* Foldseek
        hits (lowest E-value first among hits that resolve to a UniProt
        accession - AFDB hits via a free regex, pdb100 hits via a live
        SIFTS lookup, see resolve_accession()) and aggregates them into
        domain/GO-term frequency summaries.

        Resolution requiring a network call (for pdb100 hits) means we can't
        cheaply pre-filter the *entire* hit list before ranking the way the
        old AFDB-only version could. Instead this takes a modestly
        oversampled candidate pool (CANDIDATE_OVERSAMPLE_FACTOR x
        top_n_neighbors) by E-value and resolves (cheap: a regex, or one
        SIFTS call per distinct PDB entry) all of them concurrently first,
        keeps the first top_n_neighbors that actually resolved (in original
        E-value order), and only THEN pays for the 4 full-annotation API
        calls per neighbor kept - not for the whole oversampled pool. This
        preserves the original fix's intent - a query that already has a
        PDB entry (re-solved many times by X-ray/NMR) shouldn't let a wall
        of near-identical hits crowd out the annotation budget - without
        either resolving every single hit up front or wastefully
        fully-annotating more candidates than we'll actually use (found via
        live testing on 1CRN, see docs/ROADMAP_V3.md).

        Returns a dict with "neighbors_considered", "total_hit_count",
        "candidates_examined", "resolvable_hit_count",
        "annotated_neighbor_count", "unannotated_neighbor_count",
        "top_domains", "top_go_terms", and "per_neighbor" (each neighbor's
        raw domains/go_terms, for a later tiered-report phase to render at
        whatever depth it needs).
        """
        candidate_pool_size = top_n_neighbors * CANDIDATE_OVERSAMPLE_FACTOR

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            candidates, accessions, gmgc_gene_ids, resolved_count = (
                await self._resolve_candidates(hits, candidate_pool_size, client)
            )
            resolved_pairs = [
                (hit, acc, gid)
                for hit, acc, gid in zip(candidates, accessions, gmgc_gene_ids)
                if acc or gid
            ][:top_n_neighbors]

            per_neighbor = await asyncio.gather(
                *(
                    self._annotate_neighbor(hit, acc, client, gmgc_gene_id=gid)
                    for hit, acc, gid in resolved_pairs
                )
            )

            # GO names from InterPro's embedded terms are already resolved;
            # QuickGO's raw annotation-search response only has IDs, so those
            # need a separate batch name-resolution call.
            unresolved_go_ids = [
                g["id"]
                for neighbor in per_neighbor
                for g in neighbor["go_terms"]
                if g.get("id")
            ]
            resolved_names = await self.resolve_go_term_names(unresolved_go_ids, client)

        (
            domain_counter,
            domain_meta,
            go_counter,
            go_meta,
            confident_domain_counter,
            confident_go_counter,
        ) = self._count_neighbor_annotations(per_neighbor, resolved_names)

        summary_counts = self._neighbor_summary_counts(per_neighbor)

        return {
            "neighbors_considered": len(per_neighbor),
            "total_hit_count": len(hits),
            "candidates_examined": len(candidates),
            "resolvable_hit_count": resolved_count,
            "annotated_neighbor_count": summary_counts["annotated_count"],
            "unannotated_neighbor_count": len(per_neighbor)
            - summary_counts["annotated_count"],
            "min_confident_probability": self.min_confident_probability,
            "high_confidence_annotated_count": summary_counts[
                "high_confidence_annotated_count"
            ],
            "neighbors_with_interactions_count": summary_counts["interaction_count"],
            "neighbors_with_pathways_count": summary_counts["pathway_count"],
            "top_domains": self._top_domains(
                domain_counter, domain_meta, top_n_summary
            ),
            "top_go_terms": self._top_go_terms(go_counter, go_meta, top_n_summary),
            "high_confidence_top_domains": self._top_domains(
                confident_domain_counter, domain_meta, top_n_summary
            ),
            "high_confidence_top_go_terms": self._top_go_terms(
                confident_go_counter, go_meta, top_n_summary
            ),
            "per_neighbor": per_neighbor,
        }
