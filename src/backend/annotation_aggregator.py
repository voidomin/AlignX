"""
Annotation Aggregator Module.
Given a list of Foldseek structural-neighbor hits (see FoldseekClient),
fetches functional annotations (InterPro domains, QuickGO terms, STRING
interaction partners, Reactome pathways) for whichever neighbors we can
resolve to a UniProt accession, and aggregates the ontology-based signals
(domains, GO terms) into frequency summaries across the neighbor set.

This is Phase 3 of the Discover pipeline (docs/ROADMAP_V3.md), extended
with the STRING/Reactome fast-follow flagged there. Turning this into a
tiered, narrative "function hypothesis" report is a later phase.
"""

import asyncio
import re
import threading
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.utils.logger import get_logger

logger = get_logger()

INTERPRO_BASE_URL = "https://www.ebi.ac.uk/interpro/api"
QUICKGO_BASE_URL = "https://www.ebi.ac.uk/QuickGO/services"
STRING_BASE_URL = "https://version-12-0.string-db.org/api/json"
REACTOME_BASE_URL = "https://reactome.org/ContentService"
STRING_CALLER_IDENTITY = "structscope"

# Foldseek's AlphaFold DB hits are named "AF-{UniProt}-F{fragment}[-v{n}] ...".
# This is currently the only Foldseek target format we can resolve to a
# UniProt accession without an extra lookup (PDB/CATH hits are named after
# the structure file, not a UniProt accession - see docs/ROADMAP_V3.md's
# open questions). Neighbors we can't resolve are still returned, just
# without annotations.
_AFDB_TARGET_PATTERN = re.compile(r"^AF-([A-Za-z0-9]+)-F\d+", re.IGNORECASE)

DEFAULT_TOP_N_NEIGHBORS = 10
DEFAULT_TOP_N_SUMMARY = 10
DEFAULT_TOP_N_PARTNERS = 5
DEFAULT_TOP_N_PATHWAYS = 5


class _RateLimiter:
    """Serializes requests to a single-QPS-limited API across the process.

    Same threading.Lock-based design as FoldseekClient's rate limiter (see
    that module's docstring for why asyncio.Lock is unsafe here): each
    Discover job's annotation fetches run inside their own asyncio.run() on
    a dedicated worker thread, so concurrent jobs call this from different
    event loops. A plain threading.Lock is real OS-level mutual exclusion
    and works correctly across that; blocking the calling thread during the
    wait is fine since that thread has nothing else to do meanwhile.
    """

    def __init__(self, min_interval_seconds: float):
        self._min_interval = min_interval_seconds
        self._lock = threading.Lock()
        self._last_request_at: float = 0.0

    async def wait(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request_at = time.monotonic()


class AnnotationAggregator:
    """Fetches and aggregates InterPro/QuickGO/STRING/Reactome annotations
    for Foldseek hits."""

    # STRING's science-skills reference client uses qps=1; be a good citizen.
    _string_rate_limiter = _RateLimiter(min_interval_seconds=1.0)

    def __init__(self, config: Optional[Dict[str, Any]] = None, timeout: float = 15.0):
        config = config or {}
        annotation_cfg = config.get("annotation", {})
        self.timeout = annotation_cfg.get("timeout", timeout)

    @staticmethod
    def extract_uniprot_accession(target: str) -> Optional[str]:
        """Pulls a UniProt accession out of a Foldseek AFDB target string,
        e.g. "AF-P01541-F1-model_v6 Denclatoxin-B" -> "P01541"."""
        match = _AFDB_TARGET_PATTERN.match((target or "").strip())
        return match.group(1).upper() if match else None

    async def fetch_interpro_entries(
        self, accession: str, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Returns InterPro entries (domains/families/sites) matching a
        UniProt protein, each with any GO terms InterPro itself associates
        with that entry."""
        url = f"{INTERPRO_BASE_URL}/entry/interpro/protein/uniprot/{accession}"
        try:
            response = await client.get(
                url, params={"page_size": 50}, headers={"Accept": "application/json"}
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
            logger.warning(f"InterPro lookup failed for {accession}: {e}")
            return []

    async def fetch_quickgo_annotations(
        self, accession: str, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Returns this protein's own GO annotations from QuickGO (broader
        and evidence-coded, unlike InterPro's generic per-domain GO terms)."""
        url = f"{QUICKGO_BASE_URL}/annotation/search"
        try:
            response = await client.get(
                url,
                params={"geneProductId": f"UniProtKB:{accession}", "limit": 100},
                headers={"Accept": "application/json"},
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
            logger.warning(f"QuickGO lookup failed for {accession}: {e}")
            return []

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
                headers={"Accept": "application/json"},
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
            logger.warning(f"STRING lookup failed for {accession}: {e}")
            return []

    async def fetch_reactome_pathways(
        self,
        accession: str,
        client: httpx.AsyncClient,
        limit: int = DEFAULT_TOP_N_PATHWAYS,
    ) -> List[Dict[str, Any]]:
        """Returns pathways this protein participates in, per Reactome."""
        url = f"{REACTOME_BASE_URL}/data/mapping/UniProt/{accession}/pathways"
        try:
            response = await client.get(url, headers={"Accept": "application/json"})
            if response.status_code != 200:
                return []
            return [
                {"id": p.get("stId"), "name": p.get("displayName")}
                for p in response.json() or []
                if p.get("stId")
            ][:limit]
        except httpx.HTTPError as e:
            logger.warning(f"Reactome lookup failed for {accession}: {e}")
            return []

    async def resolve_go_term_names(
        self, go_ids: List[str], client: httpx.AsyncClient
    ) -> Dict[str, str]:
        """Batch-resolves GO IDs to human-readable names (QuickGO's
        annotation search endpoint returns IDs but not names)."""
        unique_ids = sorted(set(gid for gid in go_ids if gid))
        names: Dict[str, str] = {}
        chunk_size = 50
        for i in range(0, len(unique_ids), chunk_size):
            chunk = unique_ids[i : i + chunk_size]
            url = f"{QUICKGO_BASE_URL}/ontology/go/terms/{','.join(chunk)}"
            try:
                response = await client.get(url, headers={"Accept": "application/json"})
                if response.status_code == 200:
                    for term in response.json().get("results", []):
                        if term.get("id") and term.get("name"):
                            names[term["id"]] = term["name"]
            except httpx.HTTPError as e:
                logger.warning(f"GO term name resolution failed for {chunk}: {e}")
        return names

    @staticmethod
    def _hit_sort_key(hit: Dict[str, Any]) -> float:
        try:
            return float(hit.get("eval", hit.get("eValue", hit.get("evalue", 1e9))))
        except (TypeError, ValueError):
            return 1e9

    async def _annotate_neighbor(
        self, hit: Dict[str, Any], client: httpx.AsyncClient
    ) -> Dict[str, Any]:
        target = hit.get("target", "")
        accession = self.extract_uniprot_accession(target)
        neighbor: Dict[str, Any] = {
            "target": target,
            "accession": accession,
            "domains": [],
            "go_terms": [],
            "string_partners": [],
            "reactome_pathways": [],
        }
        if accession:
            # Foldseek's own hit payload already carries a taxId for AFDB
            # matches, so STRING gets it for free - no extra species lookup.
            taxon_id = hit.get("taxId")
            domains, quickgo_terms, string_partners, reactome_pathways = await asyncio.gather(
                self.fetch_interpro_entries(accession, client),
                self.fetch_quickgo_annotations(accession, client),
                self.fetch_string_partners(accession, taxon_id, client),
                self.fetch_reactome_pathways(accession, client),
            )
            neighbor["domains"] = domains
            neighbor["go_terms"] = quickgo_terms
            neighbor["string_partners"] = string_partners
            neighbor["reactome_pathways"] = reactome_pathways
        return neighbor

    async def aggregate_for_hits(
        self,
        hits: List[Dict[str, Any]],
        top_n_neighbors: int = DEFAULT_TOP_N_NEIGHBORS,
        top_n_summary: int = DEFAULT_TOP_N_SUMMARY,
    ) -> Dict[str, Any]:
        """
        Fetches annotations for the most confident *resolvable* Foldseek
        hits (lowest E-value first among hits with a UniProt accession we
        can extract) and aggregates them into domain/GO-term frequency
        summaries.

        Ranking is restricted to resolvable hits before taking top_n rather
        than taking top_n across all hits first: a query that already has a
        PDB entry (e.g. re-solved many times by X-ray/NMR) gets a wall of
        near-identical, vanishingly-low-E-value PDB100 hits that would
        otherwise crowd out every annotatable AFDB hit further down the
        list, resulting in zero annotations despite good matches existing
        (found via live testing on 1CRN - see docs/ROADMAP_V3.md).

        Returns a dict with "neighbors_considered", "total_hit_count",
        "resolvable_hit_count", "annotated_neighbor_count",
        "unannotated_neighbor_count", "top_domains", "top_go_terms", and
        "per_neighbor" (each neighbor's raw domains/go_terms, for a later
        tiered-report phase to render at whatever depth it needs).
        """
        resolvable_hits = [
            h for h in hits if self.extract_uniprot_accession(h.get("target", ""))
        ]
        sorted_hits = sorted(resolvable_hits, key=self._hit_sort_key)[:top_n_neighbors]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            per_neighbor = await asyncio.gather(
                *(self._annotate_neighbor(hit, client) for hit in sorted_hits)
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

        domain_counter: Counter = Counter()
        domain_meta: Dict[Tuple[str, str], Dict[str, Any]] = {}
        go_counter: Counter = Counter()
        go_meta: Dict[str, Dict[str, Any]] = {}

        for neighbor in per_neighbor:
            neighbor_domain_keys = set()
            neighbor_go_ids = set()

            for domain in neighbor["domains"]:
                key = (domain.get("name"), domain.get("type"))
                neighbor_domain_keys.add(key)
                domain_meta[key] = domain
                for g in domain.get("go_terms") or []:
                    if g.get("id"):
                        neighbor_go_ids.add(g["id"])
                        go_meta.setdefault(
                            g["id"], {"name": g.get("name"), "aspect": g.get("aspect")}
                        )

            for g in neighbor["go_terms"]:
                if g.get("id"):
                    neighbor_go_ids.add(g["id"])
                    go_meta.setdefault(
                        g["id"],
                        {"name": resolved_names.get(g["id"]), "aspect": g.get("aspect")},
                    )

            for key in neighbor_domain_keys:
                domain_counter[key] += 1
            for gid in neighbor_go_ids:
                go_counter[gid] += 1

        top_domains = [
            {
                "name": name,
                "type": entry_type,
                "interpro_accession": domain_meta[(name, entry_type)].get("accession"),
                "neighbor_count": count,
            }
            for (name, entry_type), count in domain_counter.most_common(top_n_summary)
        ]
        top_go_terms = [
            {
                "id": gid,
                "name": go_meta[gid].get("name"),
                "aspect": go_meta[gid].get("aspect"),
                "neighbor_count": count,
            }
            for gid, count in go_counter.most_common(top_n_summary)
        ]

        # All neighbors here already have a resolved accession (see above);
        # "annotated" now distinguishes those where InterPro/QuickGO actually
        # returned data from those where the accession resolved but lookups
        # came back empty (e.g. an unreviewed UniProt entry with no curated
        # annotations yet).
        annotated_count = sum(
            1 for n in per_neighbor if n["domains"] or n["go_terms"]
        )
        # STRING/Reactome coverage is reported separately, not folded into
        # "annotated_neighbor_count": their absence is expected and common
        # (STRING only covers organisms with a sequenced genome; Reactome's
        # curated pathway coverage skews toward well-studied model species),
        # not a sign the annotation step failed the way an empty
        # domains/go_terms result would be.
        interaction_count = sum(1 for n in per_neighbor if n["string_partners"])
        pathway_count = sum(1 for n in per_neighbor if n["reactome_pathways"])
        return {
            "neighbors_considered": len(sorted_hits),
            "total_hit_count": len(hits),
            "resolvable_hit_count": len(resolvable_hits),
            "annotated_neighbor_count": annotated_count,
            "unannotated_neighbor_count": len(sorted_hits) - annotated_count,
            "neighbors_with_interactions_count": interaction_count,
            "neighbors_with_pathways_count": pathway_count,
            "top_domains": top_domains,
            "top_go_terms": top_go_terms,
            "per_neighbor": per_neighbor,
        }
