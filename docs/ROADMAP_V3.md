# AlignX v3: From Alignment Tool to Structure-to-Function Platform

This document is the working design/roadmap for the next major version. It captures
*why* we're changing direction, *what* has to change architecturally, *what* is new,
and *what's required* to build it. Nothing here is implemented yet — this is the plan
to review and refine before writing code.

## 1. Problem statement

Structure prediction (AlphaFold DB, ESM Metagenomic Atlas) has produced hundreds of
millions of protein structures with **no known function**. Sequence-similarity search
(BLAST-style) fails on many of these because sequence identity has decayed past
recognition over evolutionary time — but 3D fold is conserved far longer than sequence.
A researcher (or student, or curious person) who has one structure of interest and
wants to know *"what does this protein probably do?"* currently has no good single
place to answer that question — they'd need to manually run a structural search, then
separately look up domains, GO terms, pathways, and interactions for whatever comes
back, then synthesize it themselves.

**AlignX today solves a narrower, adjacent problem**: given 2+ structures you *already
picked*, compute their structural alignment and RMSD (via Mustang). That's useful, but
it assumes the user already knows what to compare — it doesn't answer "what is this?"
for a single, unannotated structure.

## 2. Vision

Move from "alignment calculator" to **"give me one structure, tell me what's known
about it and what it's probably related to."** Structural comparison (Mustang) stays
in the product as one capability among several, not the product's whole identity.

Serve three audiences from the *same* underlying pipeline, varying only presentation
depth — not three separate products:

| Audience | What they need |
|---|---|
| Researchers | Raw hit tables, E-values/probabilities, confidence-scored annotation aggregation, exportable data |
| Students | A guided narrative: *why* this match suggests that function, explained in context |
| Public / citizen science | A plain-language summary with explicit uncertainty caveats — no overclaiming |

## 3. What has to change

### 3.1 Single-structure input is now a first-class workflow

Today `/api/jobs/align` hard-requires `len(pdb_ids) >= 2`
([src/backend/api.py:425](../src/backend/api.py#L425)) because the entire pipeline is
built around pairwise/N-way Mustang alignment. The new "what is this?" flow needs to
accept **exactly one** structure and run a completely different pipeline (structural
neighbor search + annotation), not alignment. This isn't a matter of loosening a
validation check — it's a second, parallel pipeline that happens to share the existing
structure-ingestion layer (`PDBManager`, the 4 source connectors, cleaning/renumbering).

Concretely: a new "Discover" mode/tab sits alongside the existing "Compare" (Mustang)
mode. Compare still requires 2+; Discover requires exactly 1.

### 3.2 Mustang becomes one feature, not the product's identity

Positioning shift only, not a code rewrite: Mustang-based structural alignment stays
exactly as it is today (engine, RMSD matrix, tree, superposition viewer) but becomes
the "Compare" feature within a broader tool, sitting next to "Discover" (structure →
function) and whatever comes after. `AnalysisCoordinator` likely gets split
conceptually into a `ComparisonCoordinator` (today's `run_full_pipeline`, unchanged)
and a new `DiscoveryCoordinator` (below), both built on the same `PDBManager`.

### 3.3 Naming

"AlignX" (and the backend's internal name, "Mustang Structural Alignment Pipeline" —
[config.yaml:2](../config.yaml#L2)) both describe the alignment feature specifically,
not a structure-to-function platform. Worth renaming once the new capability is real,
not before — renaming twice is wasted churn. Criteria for a new name: should not imply
"alignment only," should read credibly to a researcher, and shouldn't overclaim
certainty (avoid words like "predict" or "identify" that sound more definitive than a
structural-homology inference actually is). No name chosen yet — revisit once Discover
mode has a working prototype and we know what it actually feels like to use.

## 4. New feature: structural neighbor search + function annotation ("Discover")

### 4.1 Pipeline

```
1 structure in (PDB ID / AF-.../SM-.../ESM-... / user upload)
        ↓
Foldseek structural search (against PDB, AlphaFold DB, MGnify/ESM, CATH, etc.)
        ↓
Top-N structural neighbors (each with probability, E-value, query coverage, seq identity)
        ↓
For each neighbor: pull annotations (UniProt name/organism, InterPro domains,
QuickGO terms, STRING interaction partners, Reactome pathways)
        ↓
Aggregate across neighbors → confidence-weighted function hypothesis
(dominant GO terms / domains / pathway themes, weighted by neighbor match quality)
        ↓
Tiered report (researcher / student / public views of the same data)
```

### 4.2 Foldseek integration — confirmed feasible without self-hosting

Investigated Google DeepMind's `science-skills` repo
(https://github.com/google-deepmind/science-skills) for a reference implementation.
Its `foldseek_structural_search` skill calls the **public Foldseek web API**
(`https://search.foldseek.com`) — no local Foldseek binary or multi-GB search database
needed, unlike Mustang which we do compile/bundle ourselves. Mechanics:

1. `POST /api/ticket` — multipart upload of the structure file, `mode=3diaa`,
   `database[]` = one or more of `afdb50`, `afdb-swissprot`, `pdb100`, `BFVD`,
   `mgnify_esm30`, `cath50`, `gmgcl_id`, `bfmd`, `afdb-proteome`. Returns a ticket ID.
2. Poll `GET /api/ticket/{id}` until `status == "COMPLETE"`.
3. `GET /api/result/{id}/0` — full JSON of hits (target ID, probability, E-value,
   query coverage, sequence identity, alignment length).

Rate limit: the service asks for ≤0.1 requests/second per client. This matters a lot
for a multi-user product — we need one shared, server-side queue/throttle for outbound
Foldseek calls (not per-request-from-browser), the same way Mustang execution is
already serialized through the backend rather than run client-side.

`mgnify_esm30` is particularly relevant since we already support ESM Atlas structures
as an input source — this is the database most likely to contain neighbors for
metagenomic "dark matter" proteins, which is the actual problem statement above.

### 4.3 Annotation sources (all free public REST APIs, same integration pattern as today's UniProt calls in `fetch_metadata()`)

| Source | Gives us | API |
|---|---|---|
| UniProt | Canonical name, organism (already integrated) | `rest.uniprot.org` |
| InterPro | Domains/families/sites (Pfam, CDD, etc. unified) | EBI InterPro REST API |
| QuickGO | GO terms (biological process / molecular function / cellular component) | EBI QuickGO REST API |
| STRING | Protein-protein interaction partners, confidence scores | `string-db.org` API (requires an NCBI taxon ID per query — can't guess species, must derive it from the neighbor's UniProt record) |
| Reactome | Pathway membership, enrichment | `reactome.org` Content/Analysis Service |

All of these are **third-party services with their own terms of use** — several of the
science-skills docs explicitly require notifying the user of ToS before first use
(EBI's, Foldseek's, STRING's). If Discover mode is public-facing, we need our own
equivalent: a visible attribution/ToS notice, and to not misrepresent these as AlignX's
own data. Also need local caching of annotation lookups (similar to the existing PDB
download cache) both to respect rate limits and to avoid re-querying the same neighbor
repeatedly across different users' searches.

### 4.4 Tiered reporting

One synthesis step, three renderings of the same underlying result object:

- **Researcher**: full hit table (sortable by probability/E-value/coverage), raw
  annotation lists per neighbor, aggregation methodology shown, export to
  JSON/CSV/notebook (reuses existing `NotebookExporter` pattern).
- **Student**: narrative explanation — "this structure matches known
  [enzyme class] with high confidence because X; here's what that family typically
  does and why structural conservation implies function here."
- **Public**: 2-3 sentence plain-language summary + explicit confidence/uncertainty
  language, no jargon, clear "this is an inference, not a confirmed fact" framing.

## 5. Technical requirements to build this

**Backend (new)**
- `FoldseekClient` (mirrors `MustangRunner`'s role, but a REST client rather than a
  subprocess wrapper): submit ticket, poll, fetch results; server-side throttling to
  respect the 0.1 qps limit across *all* concurrent AlignX users, not per-user.
- `AnnotationAggregator`: fetches InterPro/QuickGO/STRING/Reactome for a list of
  neighbor accessions, merges into one confidence-weighted summary. Needs its own
  cache table (extend `database.py`, same idea as the existing PDB file cache).
- `DiscoveryCoordinator`: orchestrates structure download/clean (reusing
  `PDBManager`) → Foldseek search → annotation aggregation → tiered result object.
- New job-queue endpoint, e.g. `POST /api/jobs/discover` (single `pdb_id`, no `>= 2`
  check), following the existing async job pattern (`/api/jobs/align`'s polling model).
- New `GET /api/discover/{job_id}` result endpoint returning the tiered report object.

**Frontend (new)**
- New "Discover" tab/mode, separate from "Overview" (which stays Mustang-based
  Compare mode): single structure-ID input, no "Add" list.
- Results view: neighbor hit list, aggregated function summary, and a detail-level
  toggle (Researcher / Student / Public) driving which fields render.
- Reuse existing source-badge component (PDB/AlphaFold/SWISS-MODEL/ESMFold) for
  displaying neighbor provenance.

**Cross-cutting**
- Attribution/ToS surface for Foldseek + EBI + STRING + Reactome, visible in the UI
  (likely a footer/info panel, not a blocking modal, to stay low-friction).
- Rate-limit-aware job queue: Discover jobs may need to queue behind each other
  server-side given the 0.1 qps Foldseek ceiling — needs a visible "queued" state in
  the UI so a public multi-user deployment doesn't look broken under load.
- Decide self-host vs. rely on the public Foldseek API long-term: relying on
  `search.foldseek.com` is the fast path to a working prototype, but a public-facing
  product at any real scale will hit that rate ceiling fast (0.1 qps ≈ one search per
  10 seconds, shared across every user). Self-hosting Foldseek + a PDB/AFDB search
  database is the scale-up path if this gets real usage — flagged here as a known
  future constraint, not something to solve now.

## 6. Phased plan

- [x] **Phase 1 — Foldseek prototype**: `FoldseekClient`, one hardcoded test structure,
      confirm we can submit/poll/retrieve real hits against `pdb100` + `afdb50`.
      Done: `src/backend/foldseek_client.py` + `tests/test_foldseek_client.py`,
      verified live against 1CRN (returned correct thionin-family hits).
- [x] **Phase 2 — Single-structure pipeline**: `DiscoveryCoordinator` +
      `/api/jobs/discover`, returning raw Foldseek hits with no annotation yet.
      Done: `src/backend/discovery_coordinator.py`, new job-queue endpoints
      (`POST /api/jobs/discover`, shared `GET /api/jobs/{job_id}` polling,
      TTL sweep, per-path rate limiting tighter than alignment jobs).
      Verified live end-to-end through the running server (not just mocked
      tests): submitted 1CRN, got back the same 179 thionin-family hits as
      the Phase 1 prototype.
- [x] **Phase 3 — Annotation aggregation**: `AnnotationAggregator` wired to
      InterPro/QuickGO first (domains + GO terms are the highest-value signal),
      STRING/Reactome after (not yet done - tracked as a fast-follow).
      Done: `src/backend/annotation_aggregator.py`, wired into
      `DiscoveryCoordinator` as a best-effort step. Only AFDB-format Foldseek
      targets resolve to a UniProt accession today (PDB/CATH hits need a
      further ID-mapping lookup - open question, unchanged). Found and fixed
      a real gap live-testing 1CRN: ranking top-N by E-value across all
      databases let near-identical PDB100 hits (same protein, re-solved many
      times) crowd out every annotatable AFDB hit; fixed by filtering to
      resolvable hits before ranking. Verified live post-fix: 9/10 top
      neighbors correctly annotated as Thionin family/superfamily with GO
      terms for defense response, extracellular region, toxin activity.
- [ ] **Phase 4 — Tiered report + Discover UI**: frontend tab, detail-level toggle,
      neighbor list with source badges.
- [ ] **Phase 5 — Attribution/ToS surface + rate-limit queueing UX**.
- [ ] **Phase 6 — Naming decision + rebrand** (once Discover mode is real and used).

## 7. Open questions

- Do we cap Discover to PDB/AFDB/MGnify(ESM) databases only, or expose all 9 Foldseek
  databases as user-selectable (adds UI complexity for likely-marginal value for
  non-expert users)?
- How do we derive the NCBI taxon ID STRING requires per neighbor automatically
  (from the neighbor's UniProt organism field) rather than asking the user?
- What confidence threshold (probability/E-value) should gate whether we show a
  function hypothesis at all, versus saying "no confident structural neighbors found"
  — important for the public tier especially, to avoid confidently-wrong summaries.
- Self-host Foldseek now or defer — depends on how much real usage this gets.
