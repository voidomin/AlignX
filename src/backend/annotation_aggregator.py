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
import gzip
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
# The unfiltered /mappings/{pdb_id} endpoint (distinct from SIFTS_BASE_URL's
# /mappings/uniprot/{pdb_id}) - that one only resolves an accession; this one
# carries the real per-segment residue-level mapping (unp_start/unp_end plus
# each segment's author_residue_number range) needed to translate a UniProt-
# numbered domain/feature location onto a PDB entry's own author numbering.
PDBE_ALL_MAPPINGS_BASE_URL = "https://www.ebi.ac.uk/pdbe/api/mappings"
PDBE_CATH_MAPPINGS_BASE_URL = "https://www.ebi.ac.uk/pdbe/api/mappings/cath_b"
RCSB_ASSEMBLY_BASE_URL = "https://data.rcsb.org/rest/v1/core/assembly"
GMGC_BASE_URL = "https://gmgc.embl.de/api/v1.0"
UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb"
ALPHAFOLD_FILES_BASE_URL = "https://alphafold.ebi.ac.uk/files"
# M-CSA (Mechanism and Catalytic Site Atlas, EBI) - a curated database of
# real enzyme catalytic-site residues, ~1000 entries. Verified live: its
# /entries/ endpoint has no server-side filter by accession at all
# (reference_uniprot_id= and search= query params are both silently
# ignored) - it's a fixed, paginated (100/page) bulk dump, so the whole
# thing is fetched and cached once (see _fetch_mcsa_entries) rather than
# re-fetched per accession.
MCSA_ENTRIES_URL = "https://www.ebi.ac.uk/thornton-srv/m-csa/api/entries/"
# NCBI's E-utilities work keyless at 3 req/s - fast enough for one
# interactive mutation lookup (a single esearch+esummary pair), no
# dedicated rate limiter needed the way the batch STRING/Foldseek fetches
# have (those loop over many neighbors in one job; this doesn't).
CLINVAR_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
CLINVAR_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
# myvariant.info (Biothings) aggregates gnomAD + dbNSFP + ClinVar - used
# here purely for gnomAD's real population allele frequencies, keyed by
# gene+protein position rather than genomic coordinate (gnomAD's own
# GraphQL API keys by genomic variant, which would need an extra
# HGVS/VEP mapping step this app has no existing code for; myvariant.info
# already indexes dbNSFP's protein-level ref/alt/pos alongside gnomAD's
# frequencies in the same document, removing that hop entirely).
MYVARIANT_QUERY_URL = "https://myvariant.info/v1/query"
# MobiDB (EBI) - real sequence-based intrinsic-disorder predictions, keyed
# by UniProt accession alone, keyless. Confirmed live: returns several
# independent predictors per accession, not one black-box score -
# "prediction-disorder-alphafold" is a real per-residue 0-1 score array
# (MobiDB's own disorder-from-pLDDT derivation, not AlphaFold's pLDDT
# relabeled), and "prediction-disorder-th_50" is MobiDB's own recommended
# consensus-of-predictors call, as disordered regions rather than a score.
MOBIDB_DOWNLOAD_URL = "https://mobidb.org/api/download"
# Human Protein Atlas - real tissue/subcellular expression data, keyed by
# UniProt accession via a two-hop lookup (resolve to an Ensembl gene ID,
# then fetch that gene's full record). Verified live: search_download.php
# responds with Content-Type: application/gzip but NO Content-Encoding
# header, so httpx does NOT auto-decompress it - the raw bytes must be
# gzip.decompress()'d by hand before json.loads(), unlike every other
# fetch in this module. The per-gene record endpoint below is plain JSON.
PROTEIN_ATLAS_SEARCH_URL = "https://www.proteinatlas.org/api/search_download.php"
PROTEIN_ATLAS_GENE_URL = "https://www.proteinatlas.org"
# KEGG's REST API (rest.kegg.jp) - a second, independently-curated pathway
# database alongside Reactome (fetch_reactome_pathways above), which can
# legitimately disagree on scope/naming. Verified live: both endpoints
# below return flat plain text (Content-Type: text/plain), not JSON - the
# only non-JSON external response this module parses.
KEGG_CONV_URL = "https://rest.kegg.jp/conv/genes/uniprot"
KEGG_GET_URL = "https://rest.kegg.jp/get"
# OrthoDB - real cross-species ortholog mapping, genuinely different from
# BLAST conservation's unstructured homolog search (whatever sequences
# BLAST returns, not a defined per-species ortholog group). Verified live
# gotcha: an invalid/malformed group id does NOT 404 - it returns HTTP
# 200 with a generic usage-help body ({"message": "id - is an ODB
# orthologous group or gene id..."}, no "status"/"data" keys). A real
# result always has "status": "ok" plus a populated "data" key - every
# response must be checked for that shape, not just the HTTP status code.
ORTHODB_BASE_URL = "https://data.orthodb.org/current"
# A small fixed set of common model organisms (NCBI taxon ids) rather than
# a user-configurable species picker - a deliberate first-version scope
# decision, documented rather than silent.
ORTHODB_MODEL_ORGANISMS = {
    "mouse": "10090",
    "zebrafish": "7955",
    "fly": "7227",
    "yeast": "4932",
}

# UniProt's own /features list carries ~15 feature types per entry (Chain,
# Domain, Helix, Beta strand, Turn, Glycosylation, ...); most duplicate a
# signal already covered elsewhere (InterPro domains, the new backbone-
# torsion secondary-structure assignment) - these 5 are the ones with real,
# distinct value for a "what's biologically important at this residue?"
# question: catalytic/binding sites, PTMs, structural disulfides, and known
# natural variants.
_UNIPROT_FEATURE_TYPES = {
    "Active site",
    "Binding site",
    "Modified residue",
    "Disulfide bond",
    "Natural variant",
    # Added for real PTM-site coverage: these are UniProt's own type names
    # for glycosylation, lipid attachment (e.g. palmitoylation,
    # prenylation), and cross-linked residues (e.g. ubiquitination,
    # SUMOylation) - the same rest.uniprot.org host/endpoint this app
    # already calls above, just three more real PTM feature types it
    # wasn't asking for yet. Verified live against real accessions known
    # to carry each (P69905 for Glycosylation, P04637/P0DTD1 for
    # Cross-link, P01112 for Lipidation).
    "Glycosylation",
    "Lipidation",
    "Cross-link",
}
# The subset of _UNIPROT_FEATURE_TYPES that specifically means "a residue
# was chemically modified after translation" - used to split the single
# fetch_uniprot_features() result into a distinct "PTM sites" list in the
# UI, separate from active/binding sites and natural variants, without a
# second fetch against a second UniProt host for data this app already has.
PTM_FEATURE_TYPES = {
    "Modified residue",
    "Disulfide bond",
    "Glycosylation",
    "Lipidation",
    "Cross-link",
}
STRING_CALLER_IDENTITY = "structscope"
_JSON_ACCEPT_HEADERS = {"Accept": "application/json"}

# Foldseek's AlphaFold DB hits are named "AF-{UniProt}-F{fragment}[-v{n}] ...",
# which embeds a UniProt accession directly - free to extract, no lookup.
_AFDB_TARGET_PATTERN = re.compile(r"^AF-([A-Z0-9]+)-F\d+", re.IGNORECASE)
# Compare-mode's own AlphaFold workspace IDs are "AF-{UniProt}-F{fragment}"
# (see pdb_manager.py's _fetch_alphafold_response) - same accession+fragment
# shape as a Foldseek AFDB target, but with no trailing "-model_v6 ..." to
# strip, so this needs its own pattern rather than reusing
# _AFDB_TARGET_PATTERN (which anchors on that trailing text being absent).
_ALPHAFOLD_ID_PATTERN = re.compile(r"^AF-([A-Z0-9]+)-(F\d+)", re.IGNORECASE)

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

    @staticmethod
    def _residue_map_from_segment(segment: Dict[str, Any]) -> Dict[int, int]:
        """One SIFTS segment's UniProt<->author-numbering range, walked in
        lockstep - standard SIFTS convention is no internal gaps within a
        single segment (a real gap/insertion shows up as a separate
        segment instead), so a clean 1:1 span is the expected case; a
        segment whose UniProt and author spans differ in length is skipped
        rather than mismapped."""
        unp_start, unp_end = segment.get("unp_start"), segment.get("unp_end")
        author_start = (segment.get("start") or {}).get("author_residue_number")
        author_end = (segment.get("end") or {}).get("author_residue_number")
        if None in (unp_start, unp_end, author_start, author_end):
            return {}
        span = unp_end - unp_start
        if span != author_end - author_start:
            return {}
        return {unp_start + offset: author_start + offset for offset in range(span + 1)}

    async def resolve_uniprot_residue_mapping(
        self, pdb_id: str, chain_id: str, client: httpx.AsyncClient
    ) -> Dict[int, int]:
        """Real per-residue {uniprot_position: author_residue_number} map
        for one chain of a PDB entry, via PDBe's unfiltered
        /mappings/{pdb_id} endpoint - distinct from
        resolve_pdb_uniprot_accession()'s /mappings/uniprot/{pdb_id}, which
        only resolves the accession, not per-residue positions. This is
        what lets a UniProt-numbered domain/feature location be translated
        onto a real PDB entry's own (often different) author numbering,
        closing the gap _attach_domain_highlight_chains()/
        _attach_feature_highlight_chains() used to flag as PDB-unsupported.
        Returns {} if nothing resolves for this chain."""

        async def _fetch() -> Dict[str, Any]:
            try:
                response = await client.get(
                    f"{PDBE_ALL_MAPPINGS_BASE_URL}/{pdb_id.lower()}",
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return {}
                return response.json().get(pdb_id.lower(), {})
            except httpx.HTTPError as e:
                logger.warning(
                    f"PDBe residue-mapping lookup failed for {sanitize_for_log(pdb_id)}: {e}"
                )
                return {}

        entry = await self._get_or_fetch(
            f"pdbe_mappings:{pdb_id}", "pdbe_mappings", _fetch
        )

        residue_map: Dict[int, int] = {}
        for accession_info in (entry.get("UniProt") or {}).values():
            for segment in accession_info.get("mappings", []):
                if segment.get("chain_id") != chain_id:
                    continue
                residue_map.update(self._residue_map_from_segment(segment))
        return residue_map

    async def resolve_structure_uniprot_position(
        self,
        pdb_id: str,
        chain: Optional[str],
        author_resi: int,
        source: str,
        client: httpx.AsyncClient,
    ) -> Optional[Tuple[str, int]]:
        """Resolves one of a structure's own author-numbered residues to
        (uniprot_accession, uniprot_position) - the inverse direction of
        resolve_uniprot_residue_mapping()'s UniProt->author translation,
        needed for looking up a residue the *structure* numbers in
        UniProt/ClinVar's own protein-position numbering (e.g. for mutation
        mapping). AlphaFold's 1:1 numbering makes the position identical to
        the author number; a real PDB entry inverts the real SIFTS segment
        map. Returns None if the structure has no resolvable accession, or
        (for a PDB entry) no segment maps to this exact author residue."""
        accession = await self._resolve_structure_accession(
            pdb_id, chain, source, client, None
        )
        if not accession:
            return None
        if source == "alphafold":
            return accession, author_resi
        if source == "pdb" and chain:
            residue_map = await self.resolve_uniprot_residue_mapping(
                pdb_id, chain, client
            )
            for uniprot_pos, mapped_author_resi in residue_map.items():
                if mapped_author_resi == author_resi:
                    return accession, uniprot_pos
        return None

    async def fetch_uniprot_gene_and_sequence(
        self, accession: str, client: httpx.AsyncClient
    ) -> Dict[str, Optional[str]]:
        """Fetches a protein's gene symbol (ClinVar's own gene-based search
        term) and full sequence (to read off the real wild-type residue at
        a resolved UniProt position) from the same UniProt entry
        fetch_uniprot_features() already targets."""

        async def _fetch() -> Dict[str, Optional[str]]:
            try:
                response = await client.get(
                    f"{UNIPROT_BASE_URL}/{accession}.json",
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return {"gene": None, "sequence": None}
                data = response.json()
                genes = data.get("genes") or []
                gene = (genes[0].get("geneName") or {}).get("value") if genes else None
                sequence = (data.get("sequence") or {}).get("value")
                return {"gene": gene, "sequence": sequence}
            except httpx.HTTPError as e:
                logger.warning(
                    f"UniProt gene/sequence lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return {"gene": None, "sequence": None}

        return await self._get_or_fetch(
            f"uniprot_summary:{accession}", "uniprot_summary", _fetch
        )

    async def fetch_uniprot_function_summary(
        self, accession: str, client: httpx.AsyncClient
    ) -> Optional[str]:
        """Real plain-English "what does this protein do" text from
        UniProt's own curated FUNCTION comment - the single most useful
        sentence for a non-specialist, distinct from the structured
        domains/GO-terms/pathways this class already surfaces. Returns
        None if UniProt has no FUNCTION comment for this accession (common
        for less-characterized proteins) or the request fails."""

        async def _fetch() -> Optional[str]:
            try:
                response = await client.get(
                    f"{UNIPROT_BASE_URL}/{accession}.json",
                    params={"fields": "cc_function"},
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                for comment in data.get("comments") or []:
                    if comment.get("commentType") != "FUNCTION":
                        continue
                    # A `molecule`-scoped entry describes a cleaved peptide's
                    # own function (e.g. hemopressin, cleaved from HBB), not
                    # the main protein - skip those in favor of the
                    # unscoped, whole-protein entry.
                    if comment.get("molecule"):
                        continue
                    texts = comment.get("texts") or []
                    if texts and texts[0].get("value"):
                        return texts[0]["value"]
                return None
            except httpx.HTTPError as e:
                logger.warning(
                    f"UniProt function summary lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return None

        return await self._get_or_fetch(
            f"uniprot_function:{accession}", "uniprot_function", _fetch
        )

    async def fetch_protein_atlas_expression(
        self, accession: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """Real tissue/subcellular expression data from the Human Protein
        Atlas - genuinely different information from every other source
        this class fetches, none of which answer "where in the body is
        this actually expressed." Two hops: resolve the accession to an
        Ensembl gene id (search_download.php, which needs a manual gzip
        decompress - see PROTEIN_ATLAS_SEARCH_URL's comment), then fetch
        that gene's full record (plain JSON) and pull out 3 human-readable
        fields out of the dozens available. Returns None if the accession
        doesn't resolve to a Human Protein Atlas gene (e.g. non-human
        proteins, which HPA doesn't cover) or the request fails."""

        async def _fetch() -> Optional[Dict[str, Any]]:
            try:
                search_response = await client.get(
                    PROTEIN_ATLAS_SEARCH_URL,
                    params={
                        "search": accession,
                        "format": "json",
                        "columns": "g,eg,up",
                    },
                )
                if search_response.status_code != 200:
                    return None
                search_hits = json.loads(gzip.decompress(search_response.content))
                ensembl_id = None
                for hit in search_hits:
                    if accession in (hit.get("Uniprot") or []):
                        ensembl_id = hit.get("Ensembl")
                        break
                if not ensembl_id:
                    return None

                gene_response = await client.get(
                    f"{PROTEIN_ATLAS_GENE_URL}/{ensembl_id}.json"
                )
                if gene_response.status_code != 200:
                    return None
                gene_data = gene_response.json()
                return {
                    "tissue_specificity": gene_data.get("RNA tissue specificity"),
                    "tissue_distribution": gene_data.get("RNA tissue distribution"),
                    "subcellular_location": gene_data.get("Subcellular location") or [],
                }
            except (httpx.HTTPError, OSError, ValueError) as e:
                logger.warning(
                    f"Human Protein Atlas lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return None

        return await self._get_or_fetch(
            f"protein_atlas:{accession}", "protein_atlas", _fetch
        )

    async def fetch_kegg_pathways(
        self, accession: str, client: httpx.AsyncClient
    ) -> List[Dict[str, str]]:
        """Real KEGG pathway membership - a second, independently-curated
        pathway database alongside Reactome (fetch_reactome_pathways
        above), which can legitimately disagree on scope/naming. Two
        hops, both plain text (not JSON, see KEGG_CONV_URL's comment):
        conv (UniProt accession -> KEGG gene id) then get (gene id -> its
        full flat record, from which the PATHWAY section is parsed).
        A UniProt accession can map to more than one KEGG gene id (real
        paralogs sharing an identical protein sequence, e.g. HBA1/HBA2) -
        only the first mapped gene id is used, a deliberate scope
        decision. Returns [] if nothing maps or on any request failure."""

        async def _fetch() -> List[Dict[str, str]]:
            try:
                conv_response = await client.get(f"{KEGG_CONV_URL}:{accession}")
                if conv_response.status_code != 200 or not conv_response.text.strip():
                    return []
                gene_id = conv_response.text.strip().splitlines()[0].split("\t")[1]

                get_response = await client.get(f"{KEGG_GET_URL}/{gene_id}")
                if get_response.status_code != 200:
                    return []
                return self._parse_kegg_pathways(get_response.text)
            except (httpx.HTTPError, IndexError) as e:
                logger.warning(
                    f"KEGG pathway lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return []

        return await self._get_or_fetch(
            f"kegg_pathways:{accession}", "kegg_pathways", _fetch
        )

    @staticmethod
    def _parse_kegg_pathways(flat_record: str) -> List[Dict[str, str]]:
        """KEGG's flat-record format has no delimiters a JSON parser could
        use - a field starts at a fixed-width, all-caps header at the
        start of a line, and continues on every following line that
        starts with whitespace instead of a new header. Extracts just the
        PATHWAY field's entries (each "hsa#####  Description" pair)."""
        pathways = []
        in_pathway_section = False
        for line in flat_record.splitlines():
            if line.startswith("PATHWAY"):
                in_pathway_section = True
                entry = line[len("PATHWAY") :].strip()
            elif in_pathway_section and line.startswith(" "):
                entry = line.strip()
            else:
                in_pathway_section = False
                continue
            parts = entry.split(None, 1)
            if len(parts) == 2:
                pathways.append({"id": parts[0], "name": parts[1]})
        return pathways

    async def fetch_orthodb_orthologs(
        self, accession: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, List[str]]]:
        """Real cross-species ortholog gene symbols from OrthoDB - "what's
        the equivalent gene in mouse/zebrafish/fly/yeast," genuinely
        different from BLAST conservation's unstructured homolog search
        (which finds whatever sequences BLAST returns, not a defined
        per-species ortholog group). Two hops: search (accession -> an
        OrthoDB ortholog-group id) then, for each of a small fixed set of
        model organisms (ORTHODB_MODEL_ORGANISMS - a deliberate
        first-version scope decision, not a user-configurable species
        picker), orthologs (group id + species -> that species' real gene
        symbols in the group). Every response is checked for the real
        "status": "ok" + non-empty "data" shape before being trusted - see
        ORTHODB_BASE_URL's comment for why (an invalid id returns HTTP 200
        with a fake-looking success body). Returns None if the accession
        has no OrthoDB group at all, or a dict of species -> gene symbols
        (a species with no ortholog found in the group is simply omitted,
        not an error)."""

        async def _orthologs_for(group_id, species_name, taxon_id):
            try:
                response = await client.get(
                    f"{ORTHODB_BASE_URL}/orthologs",
                    params={"id": group_id, "species": taxon_id},
                )
                if response.status_code != 200:
                    return species_name, []
                data = response.json()
                if data.get("status") != "ok" or not data.get("data"):
                    return species_name, []
                # Live-verified real-data gotcha: OrthoDB's gene_id.id is
                # NOT reliably a gene symbol - for some entries it's a
                # real symbol ("HBA", "Hba-x"), for others (even within
                # the same species' result) it's an internal numeric gene
                # id with no symbol at all. Numeric-only ids are far less
                # useful to show as "the equivalent gene," so real symbols
                # are preferred; numeric ids are only used as a fallback
                # when a species has no symbol-form entry at all.
                symbol_ids, numeric_ids = [], []
                for entry in data["data"]:
                    for gene in entry.get("genes", []):
                        gene_id = (gene.get("gene_id") or {}).get("id")
                        if not gene_id:
                            continue
                        bucket = numeric_ids if gene_id.isdigit() else symbol_ids
                        if gene_id not in bucket:
                            bucket.append(gene_id)
                ids = symbol_ids or numeric_ids
                return species_name, ids[:2]
            except httpx.HTTPError as e:
                logger.warning(
                    f"OrthoDB ortholog lookup failed for {sanitize_for_log(accession)} ({species_name}): {e}"
                )
                return species_name, []

        async def _fetch() -> Optional[Dict[str, List[str]]]:
            try:
                search_response = await client.get(
                    f"{ORTHODB_BASE_URL}/search",
                    params={"query": accession, "level": "2759"},
                )
                if search_response.status_code != 200:
                    return None
                search_data = search_response.json()
                if search_data.get("status") != "ok" or not search_data.get("data"):
                    return None
                group_id = search_data["data"][0]

                results = await asyncio.gather(
                    *(
                        _orthologs_for(group_id, name, taxon_id)
                        for name, taxon_id in ORTHODB_MODEL_ORGANISMS.items()
                    )
                )
                orthologs = {name: symbols for name, symbols in results if symbols}
                return orthologs or None
            except httpx.HTTPError as e:
                logger.warning(
                    f"OrthoDB search failed for {sanitize_for_log(accession)}: {e}"
                )
                return None

        return await self._get_or_fetch(f"orthodb:{accession}", "orthodb", _fetch)

    async def fetch_clinvar_significance(
        self, gene: str, variant_notation: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """Looks up a gene+variant's real clinical significance via NCBI's
        keyless ClinVar E-utilities: esearch (find matching variant
        records) then esummary (fetch the top match's real classification).
        `variant_notation` is matched as free text against ClinVar's own
        indexed fields, so either short form ("E7V") or HGVS protein
        notation ("p.Glu7Val") works. Returns None if nothing resolves."""

        async def _fetch() -> Optional[Dict[str, Any]]:
            try:
                search_response = await client.get(
                    CLINVAR_ESEARCH_URL,
                    params={
                        "db": "clinvar",
                        "term": f"{gene}[gene] AND {variant_notation}",
                        "retmode": "json",
                    },
                )
                if search_response.status_code != 200:
                    return None
                ids = (
                    search_response.json().get("esearchresult", {}).get("idlist") or []
                )
                if not ids:
                    return None

                summary_response = await client.get(
                    CLINVAR_ESUMMARY_URL,
                    params={"db": "clinvar", "id": ids[0], "retmode": "json"},
                )
                if summary_response.status_code != 200:
                    return None
                record = summary_response.json().get("result", {}).get(ids[0])
                if not record:
                    return None

                classification = record.get("germline_classification") or {}
                return {
                    "variation_id": ids[0],
                    "accession": record.get("accession"),
                    "title": record.get("title"),
                    "clinical_significance": classification.get("description"),
                    "review_status": classification.get("review_status"),
                }
            except httpx.HTTPError as e:
                logger.warning(
                    f"ClinVar lookup failed for {sanitize_for_log(gene)} "
                    f"{sanitize_for_log(variant_notation)}: {e}"
                )
                return None

        return await self._get_or_fetch(
            f"clinvar:{gene}:{variant_notation}", "clinvar", _fetch
        )

    async def fetch_gnomad_frequency(
        self,
        gene: str,
        wildtype_residue: str,
        position: int,
        mutant_residue: str,
        client: httpx.AsyncClient,
    ) -> Optional[Dict[str, Any]]:
        """Real gnomAD population allele frequency plus REVEL pathogenicity
        score for a specific protein substitution, via myvariant.info's
        keyless query API - both are independent signals from ClinVar/
        AlphaMissense (a variant can be common in the population yet still
        flagged pathogenic by a predictor, or vice versa, and REVEL is
        itself a separately-validated ensemble predictor distinct from
        AlphaMissense, so agreement/disagreement between the two is
        informative). One gene+position query can return several distinct
        genomic hits (different codon-level substitutions can produce the
        same amino-acid change) - each hit is filtered by its own
        dbnsfp.aa.ref/alt to the one actually matching wildtype_residue/
        mutant_residue rather than assuming the top-scored hit is the
        wanted one; if more than one genomic hit still matches (codon
        degeneracy), the one with the highest exome allele frequency is
        used, since that's the predominant real-world observation (REVEL's
        own score is protein-position-based, not codon-based, so it's
        identical across codon-degenerate hits regardless of which one
        wins this tie-break). Returns None if myvariant.info has no
        matching record or the request fails - population frequency/REVEL
        data not existing for a given substitution is common and expected,
        not an error."""

        async def _fetch() -> Optional[Dict[str, Any]]:
            try:
                response = await client.get(
                    MYVARIANT_QUERY_URL,
                    params={
                        "q": f"dbnsfp.genename:{gene} AND dbnsfp.aa.pos:{position}",
                        "fields": "dbnsfp.aa.ref,dbnsfp.aa.alt,dbnsfp.revel.score,gnomad_exome.af.af,gnomad_genome.af.af",
                        "size": 20,
                    },
                )
                if response.status_code != 200:
                    return None
                hits = response.json().get("hits") or []

                matches = []
                for hit in hits:
                    dbnsfp = hit.get("dbnsfp") or {}
                    aa = dbnsfp.get("aa") or {}
                    if (
                        aa.get("ref") == wildtype_residue.upper()
                        and aa.get("alt") == mutant_residue.upper()
                    ):
                        exome_af = (
                            (hit.get("gnomad_exome") or {}).get("af") or {}
                        ).get("af")
                        genome_af = (
                            (hit.get("gnomad_genome") or {}).get("af") or {}
                        ).get("af")
                        revel_score = (dbnsfp.get("revel") or {}).get("score")
                        matches.append(
                            {
                                "af_exome": exome_af,
                                "af_genome": genome_af,
                                "revel_score": revel_score,
                            }
                        )
                if not matches:
                    return None

                return max(
                    matches, key=lambda m: m["af_exome"] if m["af_exome"] else -1
                )
            except httpx.HTTPError as e:
                logger.warning(
                    f"gnomAD/myvariant.info lookup failed for {sanitize_for_log(gene)} "
                    f"{sanitize_for_log(wildtype_residue)}{position}{sanitize_for_log(mutant_residue)}: {e}"
                )
                return None

        cache_key = f"gnomad:{gene}:{wildtype_residue.upper()}{position}{mutant_residue.upper()}"
        return await self._get_or_fetch(cache_key, "gnomad", _fetch)

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
                            # Residue positions (UniProt sequence numbering)
                            # this domain occupies - see aggregate_for_
                            # structure() for why these are only usable as
                            # structure residue numbers for AlphaFold-
                            # sourced structures specifically, not any PDB
                            # entry's own author numbering.
                            "locations": [
                                {"start": frag["start"], "end": frag["end"]}
                                for protein in item.get("proteins") or []
                                for loc in protein.get("entry_protein_locations") or []
                                for frag in loc.get("fragments") or []
                                if frag.get("start") is not None
                                and frag.get("end") is not None
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

    @staticmethod
    def _parse_uniprot_feature(f: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """One raw UniProt feature entry, flattened to this app's shape -
        or None if it's not a type this app cares about (see
        _UNIPROT_FEATURE_TYPES) or has no resolvable start/end location."""
        if f.get("type") not in _UNIPROT_FEATURE_TYPES:
            return None
        loc = f.get("location") or {}
        start = (loc.get("start") or {}).get("value")
        end = (loc.get("end") or {}).get("value")
        if start is None or end is None:
            return None
        return {
            "type": f["type"],
            "description": f.get("description") or "",
            "start": start,
            "end": end,
        }

    async def fetch_uniprot_features(
        self, accession: str, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Returns this protein's own curated sequence features straight
        from UniProt (active/binding sites, PTMs, disulfide bonds, natural
        variants) - a different signal than InterPro's domain/family
        entries or QuickGO's GO terms, both already fetched elsewhere.
        Filtered to _UNIPROT_FEATURE_TYPES; a raw UniProt entry has many
        more feature types than that, most already covered by other
        signals in this app (see that set's docstring)."""

        async def _fetch() -> List[Dict[str, Any]]:
            url = f"{UNIPROT_BASE_URL}/{accession}.json"
            try:
                response = await client.get(url, headers=_JSON_ACCEPT_HEADERS)
                if response.status_code != 200:
                    return []
                raw_features = response.json().get("features") or []
                parsed = (self._parse_uniprot_feature(f) for f in raw_features)
                return [feature for feature in parsed if feature is not None]
            except httpx.HTTPError as e:
                logger.warning(
                    f"UniProt features lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return []

        return await self._get_or_fetch(
            f"uniprot_features:{accession}", "uniprot_features", _fetch
        )

    async def _fetch_mcsa_entries(
        self, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """The full M-CSA curated catalytic-site database, fetched page by
        page and cached once under one fixed key - see MCSA_ENTRIES_URL's
        docstring for why (no server-side accession filter exists)."""

        async def _fetch() -> List[Dict[str, Any]]:
            entries: List[Dict[str, Any]] = []
            url = f"{MCSA_ENTRIES_URL}?format=json"
            try:
                while url:
                    response = await client.get(url, headers=_JSON_ACCEPT_HEADERS)
                    if response.status_code != 200:
                        break
                    data = response.json()
                    entries.extend(data.get("results") or [])
                    url = data.get("next")
            except httpx.HTTPError as e:
                logger.warning(f"M-CSA entries fetch failed: {e}")
            return entries

        return await self._get_or_fetch("mcsa:_all_entries", "mcsa", _fetch)

    async def fetch_catalytic_site_residues(
        self, accession: str, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Real curated catalytic/active-site residues for this protein
        from M-CSA (Mechanism and Catalytic Site Atlas) - coverage is
        curated and partial (~1000 entries total), so most accessions
        correctly get an empty list back, not an error. Each M-CSA entry
        documents its catalytic residues against one specific reference
        PDB structure (not a UniProt position directly), so this reports
        the reference PDB id/chain/residue M-CSA itself curated rather
        than attempting a further residue-number remapping onto whichever
        structure the user has loaded."""
        entries = await self._fetch_mcsa_entries(client)
        matches = [e for e in entries if e.get("reference_uniprot_id") == accession]

        results = []
        for entry in matches:
            residues = []
            for r in entry.get("residues") or []:
                ref_chain = next(
                    (
                        rc
                        for rc in r.get("residue_chains") or []
                        if rc.get("is_reference")
                    ),
                    None,
                )
                if not ref_chain:
                    continue
                residues.append(
                    {
                        "roles_summary": r.get("roles_summary") or "",
                        "reference_pdb_id": ref_chain.get("pdb_id"),
                        "chain": ref_chain.get("chain_name"),
                        "resi": ref_chain.get("auth_resid"),
                        "code": ref_chain.get("code"),
                    }
                )
            results.append(
                {
                    "mcsa_id": entry.get("mcsa_id"),
                    "enzyme_name": entry.get("enzyme_name") or "",
                    "ec_numbers": entry.get("all_ecs") or [],
                    "residues": residues,
                }
            )
        return results

    @staticmethod
    def _parse_alphafold_id(pdb_id: str) -> Optional[Tuple[str, str]]:
        """Pulls (uniprot_id, fragment) out of a Compare-mode AlphaFold
        workspace ID, e.g. "AF-P69905-F1" -> ("P69905", "F1"). None for
        anything that isn't AlphaFold-sourced."""
        match = _ALPHAFOLD_ID_PATTERN.match((pdb_id or "").strip())
        if not match:
            return None
        return match.group(1).upper(), match.group(2).upper()

    async def fetch_predicted_aligned_error(
        self, pdb_id: str, client: httpx.AsyncClient
    ) -> Optional[List[List[float]]]:
        """Real per-residue-pair confidence matrix for an AlphaFold model -
        a different signal than per-residue pLDDT (which says how
        confident AlphaFold is in *one* residue's own position, not how
        confident it is in that residue's position *relative to* another,
        which is what actually matters for judging whether two domains are
        correctly oriented relative to each other). Only exists for
        AlphaFold-sourced structures; returns None for anything else or if
        no matching PAE file is found (tries the same version fallback
        chain pdb_manager.py's own AlphaFold downloader does, since not
        every entry has been reprocessed onto the latest model version)."""
        parsed = self._parse_alphafold_id(pdb_id)
        if not parsed:
            return None
        uniprot_id, fragment = parsed

        async def _fetch() -> Optional[List[List[float]]]:
            for v in ("6", "5", "4", "3", "2", "1"):
                url = (
                    f"{ALPHAFOLD_FILES_BASE_URL}/AF-{uniprot_id}-{fragment}"
                    f"-predicted_aligned_error_v{v}.json"
                )
                try:
                    response = await client.get(url)
                except httpx.HTTPError as e:
                    logger.warning(
                        f"PAE lookup failed for {sanitize_for_log(pdb_id)}: {e}"
                    )
                    return None
                if response.status_code == 200:
                    payload = response.json()
                    entry = payload[0] if payload else {}
                    return entry.get("predicted_aligned_error")
            return None

        return await self._get_or_fetch(f"pae:{uniprot_id}:{fragment}", "pae", _fetch)

    async def fetch_alphamissense_scores(
        self, accession: str, client: httpx.AsyncClient
    ) -> Dict[str, Dict[str, Any]]:
        """Real per-substitution pathogenicity scores from AlphaMissense,
        keyed by UniProt position (as a string, since a JSON round-trip
        through the annotation cache would silently coerce int keys to
        strings anyway - keeping them strings from the start avoids a
        cache-hit-vs-miss inconsistency): {"132": {"wildtype": "R",
        "scores": {"A": {"pathogenicity": 0.42, "class": "Amb"}, ...}}}.
        AlphaMissense was only ever published for a protein's first
        AlphaFold fragment (it doesn't follow AlphaFold's multi-fragment
        split for proteins over ~2700 residues), so this is looked up by
        accession alone - works for any structure with a resolved
        accession (see _resolve_structure_accession), not just an
        AlphaFold-sourced one the way fetch_predicted_aligned_error is."""

        async def _fetch() -> Dict[str, Dict[str, Any]]:
            url = f"{ALPHAFOLD_FILES_BASE_URL}/AF-{accession}-F1-aa-substitutions.csv"
            try:
                response = await client.get(url)
            except httpx.HTTPError as e:
                logger.warning(
                    f"AlphaMissense lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return {}
            if response.status_code != 200:
                return {}

            by_position: Dict[str, Dict[str, Any]] = {}
            for line in response.text.splitlines()[1:]:  # skip the header row
                parts = line.split(",")
                if len(parts) != 3:
                    continue
                variant, score_str, variant_class = parts
                if len(variant) < 3:
                    continue
                wildtype, alt = variant[0], variant[-1]
                try:
                    position = str(int(variant[1:-1]))
                    pathogenicity = float(score_str)
                except ValueError:
                    continue
                entry = by_position.setdefault(
                    position, {"wildtype": wildtype, "scores": {}}
                )
                entry["scores"][alt] = {
                    "pathogenicity": pathogenicity,
                    "class": variant_class,
                }
            return by_position

        return await self._get_or_fetch(
            f"alphamissense:{accession}", "alphamissense", _fetch
        )

    async def fetch_disorder_prediction(
        self, accession: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """Real sequence-based intrinsic-disorder prediction from MobiDB,
        keyed by UniProt accession alone. Returns
        {"per_residue_score": {"1": 0.43, "2": 0.41, ...}, "consensus_regions":
        [[1, 8], [140, 142], ...]} - `per_residue_score` (from MobiDB's own
        AlphaFold-derived predictor) is what a 3D viewer color scheme needs;
        `consensus_regions` (MobiDB's own recommended threshold-50 consensus
        of several independent predictors) is a coarser, more citable
        disordered-region call. Returns None if MobiDB has no entry for this
        accession at all - a majority of proteins (especially predicted/
        uncommon ones) genuinely have no MobiDB record, same honest-fallback
        shape as M-CSA/CATH coverage elsewhere in this class."""

        async def _fetch() -> Optional[Dict[str, Any]]:
            try:
                response = await client.get(
                    MOBIDB_DOWNLOAD_URL, params={"acc": accession, "format": "json"}
                )
            except httpx.HTTPError as e:
                logger.warning(
                    f"MobiDB disorder lookup failed for {sanitize_for_log(accession)}: {e}"
                )
                return None
            # An unrecognized accession returns HTTP 200 with an empty body
            # (Content-Length: 0) rather than a 404 - confirmed live - so
            # response.json() must never be called on an empty body, or it
            # raises an uncaught JSONDecodeError instead of the honest
            # "no MobiDB coverage" None this is supposed to return.
            if response.status_code != 200 or not response.text.strip():
                return None

            data = response.json()
            score_entry = data.get("prediction-disorder-alphafold") or {}
            scores = score_entry.get("scores") or []
            consensus_entry = data.get("prediction-disorder-th_50") or {}
            regions = consensus_entry.get("regions") or []
            if not scores and not regions:
                return None

            return {
                "per_residue_score": {
                    str(i): score for i, score in enumerate(scores, start=1)
                },
                "consensus_regions": regions,
            }

        return await self._get_or_fetch(f"mobidb:{accession}", "mobidb", _fetch)

    async def aggregate_disorder_prediction(
        self,
        pdb_id: str,
        chain: Optional[str],
        source: str,
        client: httpx.AsyncClient,
    ) -> Dict[str, Any]:
        """Real per-residue intrinsic-disorder overlay for one Compare-mode
        structure, translated onto this structure's own residue numbering -
        same accession resolution and AlphaFold-1:1-vs-real-SIFTS-mapping
        split aggregate_mutation_tolerance() already uses; SWISS-MODEL/ESM
        Atlas structures correctly get nothing back, same scope those
        methods already have."""
        accession = await self._resolve_structure_accession(
            pdb_id, chain, source, client, None
        )
        result: Dict[str, Any] = {
            "accession": accession,
            "per_residue_score": {},
            "consensus_regions": [],
        }
        if not accession:
            return result

        disorder = await self.fetch_disorder_prediction(accession, client)
        if not disorder:
            return result

        per_residue_score = disorder["per_residue_score"]
        if source == "alphafold":
            result["per_residue_score"] = per_residue_score
            result["consensus_regions"] = disorder["consensus_regions"]
        elif source == "pdb" and chain:
            residue_map = await self.resolve_uniprot_residue_mapping(
                pdb_id, chain, client
            )
            result["per_residue_score"] = {
                str(author_resi): per_residue_score[str(uniprot_pos)]
                for uniprot_pos, author_resi in residue_map.items()
                if str(uniprot_pos) in per_residue_score
            }
            # consensus_regions stays [] for real PDB entries - MobiDB's
            # region boundaries are UniProt-numbered, and translating a
            # range (not a single position) through a possibly-gapped
            # residue_map without collapsing it back into misleading
            # pseudo-contiguous ranges isn't worth doing for a purely
            # descriptive field when per_residue_score above already
            # carries the real, correctly-translated signal.
        return result

    async def fetch_cath_classification(
        self, pdb_id: str, client: httpx.AsyncClient
    ) -> List[Dict[str, str]]:
        """Real CATH fold classifications for a real PDB entry, via PDBe's
        cath_b mappings endpoint - a standardized fold-family label
        independent of Foldseek's own structural-similarity search.
        Returns one entry per (chain, domain), e.g. [{"chain_id": "A",
        "domain": "4hhbA00", "classification": "1.10.490.10"}, ...] since
        a multi-domain chain can have more than one classification.
        AlphaFold/SWISS-MODEL/ESM Atlas structures have no CATH mapping at
        all (CATH only classifies real experimentally-solved structures) -
        callers should only invoke this for source == "pdb"."""

        async def _fetch() -> List[Dict[str, str]]:
            try:
                response = await client.get(
                    f"{PDBE_CATH_MAPPINGS_BASE_URL}/{pdb_id.lower()}",
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return []
                entry = response.json().get(pdb_id.lower(), {})
                domains = []
                for classification, details in (entry.get("CATH-B") or {}).items():
                    for mapping in details.get("mappings") or []:
                        domains.append(
                            {
                                "chain_id": mapping.get("chain_id"),
                                "domain": mapping.get("domain"),
                                "classification": classification,
                            }
                        )
                return domains
            except httpx.HTTPError as e:
                logger.warning(
                    f"CATH classification lookup failed for {sanitize_for_log(pdb_id)}: {e}"
                )
                return []

        return await self._get_or_fetch(f"cath:{pdb_id}", "cath", _fetch)

    async def fetch_assembly_info(
        self, pdb_id: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """Real oligomeric-state metadata for a real PDB entry's first
        biological assembly, via RCSB's assembly API - e.g. {"oligomeric_
        count": 4, "oligomeric_details": "tetrameric"} for 4HHB. Deliberately
        metadata-only (not a new interface-analysis engine - that's
        InterfaceAnalyzer's job, see calculate_interface()). Only meaningful
        for source == "pdb"; returns None if nothing resolves."""

        async def _fetch() -> Optional[Dict[str, Any]]:
            try:
                response = await client.get(
                    f"{RCSB_ASSEMBLY_BASE_URL}/{pdb_id.lower()}/1",
                    headers=_JSON_ACCEPT_HEADERS,
                )
                if response.status_code != 200:
                    return None
                assembly = response.json().get("pdbx_struct_assembly") or {}
                oligomeric_count = assembly.get("oligomeric_count")
                oligomeric_details = assembly.get("oligomeric_details")
                if oligomeric_count is None and oligomeric_details is None:
                    return None
                return {
                    "oligomeric_count": oligomeric_count,
                    "oligomeric_details": oligomeric_details,
                }
            except httpx.HTTPError as e:
                logger.warning(
                    f"RCSB assembly lookup failed for {sanitize_for_log(pdb_id)}: {e}"
                )
                return None

        return await self._get_or_fetch(f"assembly:{pdb_id}", "assembly", _fetch)

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

    @staticmethod
    def _domain_residues(
        domain: Dict[str, Any], residue_map: Optional[Dict[int, int]]
    ) -> List[int]:
        """Residues a domain's locations cover, translated through
        residue_map if given - an unmapped UniProt position (no entry in
        residue_map) is silently dropped rather than mismapped. `None`
        means no translation needed (AlphaFold's 1:1 numbering shortcut),
        not "map everything to nothing"."""
        raw = {
            r
            for loc in domain.get("locations") or []
            for r in range(loc["start"], loc["end"] + 1)
        }
        if residue_map is None:
            return sorted(raw)
        return sorted(residue_map[r] for r in raw if r in residue_map)

    async def _attach_domain_highlight_chains(
        self,
        domains: List[Dict[str, Any]],
        chain: Optional[str],
        source: str,
        pdb_id: str,
        client: httpx.AsyncClient,
    ) -> None:
        """Mutates each domain dict in place with a highlight_chains field.

        AlphaFold models are numbered 1..N to exactly match their source
        UniProt sequence, by construction - so InterPro's UniProt-numbered
        domain locations can be used directly as this structure's own
        residue numbers (_domain_residues' residue_map=None case). A real
        PDB entry's author numbering routinely differs from UniProt
        numbering (crystallization constructs, non-1-start numbering,
        tags) - resolve_uniprot_residue_mapping()'s real SIFTS segment
        mapping translates through that for source == "pdb" too."""
        residue_map: Optional[Dict[int, int]] = None
        if source == "alphafold" and chain:
            pass  # residue_map stays None - AlphaFold's 1:1 shortcut
        elif source == "pdb" and chain and domains:
            residue_map = await self.resolve_uniprot_residue_mapping(
                pdb_id, chain, client
            )
        else:
            for domain in domains:
                domain["highlight_chains"] = None
            return

        for domain in domains:
            residues = self._domain_residues(domain, residue_map)
            domain["highlight_chains"] = {chain: residues} if residues else None

    async def _attach_feature_highlight_chains(
        self,
        features: List[Dict[str, Any]],
        chain: Optional[str],
        source: str,
        pdb_id: str,
        client: httpx.AsyncClient,
    ) -> None:
        """Same AlphaFold 1:1-numbering shortcut plus real PDB residue-map
        translation as _attach_domain_highlight_chains() above - see that
        method's docstring."""
        if source == "alphafold" and chain:
            for feature in features:
                residues = list(range(feature["start"], feature["end"] + 1))
                feature["highlight_chains"] = {chain: residues} if residues else None
            return

        if source == "pdb" and chain and features:
            residue_map = await self.resolve_uniprot_residue_mapping(
                pdb_id, chain, client
            )
            for feature in features:
                residues = [
                    residue_map[r]
                    for r in range(feature["start"], feature["end"] + 1)
                    if r in residue_map
                ]
                feature["highlight_chains"] = {chain: residues} if residues else None
            return

        for feature in features:
            feature["highlight_chains"] = None

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
            "uniprot_features": [],
            "catalytic_sites": [],
            "function_summary": None,
            "tissue_expression": None,
            "kegg_pathways": [],
            "orthologs": None,
        }
        if not accession:
            return result

        (
            domains,
            quickgo_terms,
            reactome_pathways,
            uniprot_features,
            catalytic_sites,
            function_summary,
            tissue_expression,
            kegg_pathways,
            orthologs,
        ) = await asyncio.gather(
            self.fetch_interpro_entries(accession, client),
            self.fetch_quickgo_annotations(accession, client),
            self.fetch_reactome_pathways(accession, client),
            self.fetch_uniprot_features(accession, client),
            self.fetch_catalytic_site_residues(accession, client),
            self.fetch_uniprot_function_summary(accession, client),
            self.fetch_protein_atlas_expression(accession, client),
            self.fetch_kegg_pathways(accession, client),
            self.fetch_orthodb_orthologs(accession, client),
        )
        result["catalytic_sites"] = catalytic_sites
        result["function_summary"] = function_summary
        result["tissue_expression"] = tissue_expression
        result["kegg_pathways"] = kegg_pathways
        result["orthologs"] = orthologs

        go_ids = [g["id"] for g in quickgo_terms if g.get("id")]
        names = await self.resolve_go_term_names(go_ids, client)
        for term in quickgo_terms:
            term["name"] = names.get(term.get("id"))

        await self._attach_domain_highlight_chains(
            domains, chain, source, pdb_id, client
        )
        await self._attach_feature_highlight_chains(
            uniprot_features, chain, source, pdb_id, client
        )

        result["domains"] = domains
        result["uniprot_features"] = uniprot_features
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

    async def aggregate_mutation_tolerance(
        self,
        pdb_id: str,
        chain: Optional[str],
        source: str,
        client: httpx.AsyncClient,
    ) -> Dict[str, Any]:
        """Real per-residue mutation-tolerance overlay for one Compare-mode
        structure - the mean AlphaMissense pathogenicity across all 19
        possible substitutions at each position, translated onto this
        structure's own residue numbering. Same accession resolution and
        AlphaFold-1:1-vs-real-SIFTS-mapping split _attach_domain_highlight_
        chains() already uses; SWISS-MODEL/ESM Atlas structures correctly
        get nothing back, same scope those methods already have."""
        accession = await self._resolve_structure_accession(
            pdb_id, chain, source, client, None
        )
        result: Dict[str, Any] = {"accession": accession, "per_residue_average": {}}
        if not accession:
            return result

        scores = await self.fetch_alphamissense_scores(accession, client)
        if not scores:
            return result

        averages = {
            position: sum(s["pathogenicity"] for s in entry["scores"].values())
            / len(entry["scores"])
            for position, entry in scores.items()
            if entry.get("scores")
        }

        if source == "alphafold":
            result["per_residue_average"] = averages
        elif source == "pdb" and chain:
            residue_map = await self.resolve_uniprot_residue_mapping(
                pdb_id, chain, client
            )
            result["per_residue_average"] = {
                str(author_resi): averages[str(uniprot_pos)]
                for uniprot_pos, author_resi in residue_map.items()
                if str(uniprot_pos) in averages
            }
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
