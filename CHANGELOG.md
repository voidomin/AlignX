# Changelog

All notable changes to StructScope (formerly AlignX) are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [3.1.0]

Seven fast-follow items closing gaps left by the initial Discover launch (v3.0.0): feature parity with Compare mode (history, export), the annotation pipeline's remaining coverage/scale/safety questions, and deployment verification.

### Added
- **Discover run history**: Discover runs now persist to `HistoryDatabase` the same way Compare runs always have, with `"run_type": "discover"` in metadata. Dashboard and History show a `COMPARE`/`DISCOVER` badge per run; reopening a past Discover run hands its saved result straight back to the Discover tab instead of attempting a Compare-style reload.
- **PDB-to-UniProt resolution via SIFTS**: previously only AlphaFold DB hits (`AF-{UniProt}-F{n}`) could resolve to a UniProt accession for annotation. pdb100 hits (the *other* default search database) now resolve too, via PDBe's SIFTS mapping API. `aggregate_for_hits()` was reworked to oversample a candidate pool and resolve it cheaply before paying for the 4 full annotation API calls only on the neighbors actually kept.
- **STRING and Reactome integration**: interaction partners and pathway membership for each resolvable neighbor, alongside the existing InterPro/QuickGO. Reuses the taxon ID Foldseek's own hit payload already carries (confirmed present on *every* hit type, not just AlphaFold DB) - no extra species lookup needed.
- **Persistent annotation cache**: a new `annotation_cache` table (same `run_history.db` file as the existing PDB file cache) avoids refetching InterPro/QuickGO/SIFTS/STRING/Reactome data for an accession someone already looked up recently (default 30-day TTL, `annotation.cache_ttl_days`). Measured ~35% faster on an identical repeat query.
- **Export/report parity for Discover mode**: `GET /api/discover/report` (a standalone, self-contained HTML report) and `GET /api/discover/export` (raw JSON) - the same export capability Compare mode has always had.
- **Confidence-gated function hypothesis**: a neighbor's curated annotations now only count toward the Public/Student "function hypothesis" narrative if its own Foldseek match probability also clears `annotation.min_confident_probability` (default 0.5). Researcher is never gated - it shows the unfiltered data plus a new "high-confidence" stat for transparency.
- **Self-hosted Foldseek option**: `FoldseekRunner` wraps a local Foldseek binary (`foldseek.backend: local` in `config.yaml`) as an alternative to the public API's shared rate limit. Proven against a small hand-built test database; provisioning a production-scale search database remains a deployment-time decision, not something this ships.

### Fixed
- **A real, previously-invisible config bug**: `PipelineConfig` (the Pydantic model `config.yaml` is validated against) never declared `foldseek`/`annotation` fields, so Pydantic silently dropped both sections on every load. Every "config-driven" Foldseek/annotation setting since the v3.0.0 launch had actually been falling back to hardcoded Python defaults the whole time - undetected because those defaults happened to match what `config.yaml` specified. Found while wiring the `foldseek.backend: local` toggle, which had zero effect until this was fixed.
- A ranking bug where near-identical PDB entries of the exact same protein (e.g. Crambin, solved dozens of times) could crowd out every annotatable AFDB hit even after PDB-to-UniProt resolution was added, since the crowding was about ranking order, not resolvability.
- `.env.example` was missing `ALIGNX_DISCOVERY_RATE_LIMIT_MAX` (used in code since the v3.0.0 launch, never documented); `DEPLOYMENT.md`'s "Legacy UI only" framing on the Streamlit deployment options contradicted the "separately-deployed, not legacy" correction already made earlier in the same file.

### Verified
- Fresh Docker rebuild from the full v3.1.0 codebase: both Compare and Discover pipelines, history persistence for both run types, and both new export endpoints all confirmed working end-to-end in the same container.

## [3.0.0]

### Changed
- **Renamed AlignX → StructScope.** The old name described the alignment feature specifically; the product now covers two workflows (Compare and Discover, see below), so the name needed to stop implying "alignment only." Scope of this rename: the Vite/FastAPI SPA's UI text, README, config, and package metadata. The deployed Streamlit app's branding and the GitHub repository name are unchanged for now (see `docs/ROADMAP_V3.md` §3.3).

### Added
- **Discover mode**: given a single structure (PDB/AlphaFold/SWISS-MODEL/ESM Atlas), search it against Foldseek's structural databases to find known proteins with a similar fold, then aggregate InterPro domain and QuickGO annotations across the resolvable neighbors into a domain/GO-term consensus. Useful for predicted structures with no known function, since fold is conserved far longer than sequence - see `docs/ROADMAP_V3.md` for the full design.
- New "Discover" tab: single-structure input, Public/Student/Researcher detail-level toggle rendering the same result at three depths, a low-friction attribution note (Foldseek/InterPro/QuickGO, each linked to its own terms of use), and distinct "queued" vs "running" status messaging.
- New backend: `FoldseekClient` (public Foldseek web API), `AnnotationAggregator` (InterPro/QuickGO fetch + aggregation), `DiscoveryCoordinator` (single-structure pipeline), `POST /api/jobs/discover` + shared job polling.

### Fixed
- A real deadlock in the Foldseek rate limiter: it used a shared `asyncio.Lock`, but concurrent Discover jobs run their Foldseek calls on separate threads/event loops, which `asyncio.Lock` doesn't support safely - one of three concurrent callers hung forever in direct testing. Fixed with a `threading.Lock`.
- A ranking bug where near-identical PDB entries of the same protein (re-solved many times, each with a vanishingly small E-value) could crowd out every annotatable AlphaFold DB hit, producing zero annotations despite good matches existing further down the list. Fixed by filtering to resolvable hits before ranking, not after.
- An httpx bug in the Foldseek client: passing `data` as a list of tuples (needed for the repeated `database[]` form field) made httpx's encoder mistake it for raw `content=`, silently dropping the `files` payload. Fixed by passing `data` as a dict with a list value.
- Three Docker build/deploy bugs that had likely broken every containerized deployment attempt: wrong Mustang source directory name, wrong compiled-binary filename, and a missing `curl` install that made the container's own `HEALTHCHECK` always fail.

## [2.5.0]

### Added
- **N-structure alignment** in the 3D viewer: dynamic per-structure identity coloring, a legend that scales to however many structures are loaded, and a pairwise RMSD list for N>2 instead of a single collapsed number.
- **Two new structure sources** alongside RCSB PDB and AlphaFold DB: **SWISS-MODEL Repository** (`SM-{UniProt}`) and the **ESM Metagenomic Atlas** (`ESM-{MGYP accession}`) — mixable freely in the same alignment.
- **Source + metadata display**: every structure now shows which database it came from and its method/resolution/organism, right in the workspace list.
- **Dashboard tab**: aggregate stats (total runs, proteins analyzed, cache size), recent activity, and quick-start examples.
- **Configurable report builder**: pick which sections (summary, insights, heatmap, phylogenetic tree, RMSD matrix) go into the exported PDF.
- **HTML Lab Notebook export**: a standalone, self-contained HTML report with an embedded 3D viewer and all analysis figures.
- **Ligand tab structure picker**: inspect ligands and binding-site interactions for any of the N aligned structures, not just the first.
- AlphaFold model ID support (`AF-{UniProt}-F{n}`) — this existed on the backend already but was unreachable from the UI; now works end-to-end.

### Fixed
- **Comparison tab RMSD mismatch**: it computed a full-matrix mean (double-counting pairs, diluted by the zero diagonal) instead of the upper-triangle-only mean used everywhere else in the app, so its numbers silently disagreed with the 3D viewer HUD and RMSD Matrix chart.
- **Ligand/residue highlighting could blank the 3D viewer**: raw PDB residue numbers don't match Mustang's cleaned/renumbered aligned structure; highlighting now uses a proper raw-to-aligned residue remap instead of guessing.
- **ESMFold structures could silently drop out of multi-structure alignments**: the ESM Atlas encodes per-residue confidence on a 0–1 scale, not AlphaFold's 0–100 scale, so every residue was being misread as low-confidence and pruned. A structure that fails to prepare for alignment now aborts the run with a clear error instead of silently continuing with fewer structures than requested.
- **Dashboard/page-load slowness**: root cause was a blocking WSL subprocess check re-running on every `/api/chains` request (not client-side connection contention as first suspected) — it's now cached for the server's lifetime, cutting that endpoint's response time roughly 4x.
- Report generation crashed when regenerating a report for a run reloaded from history (a type mismatch between live and persisted data); the report endpoint also served a stale cached PDF when a section subset was requested instead of regenerating.
- A fast "add structure, then immediately run alignment" click could persist an incomplete chain selection for the newly-added structure.
- ClustersTab always showed "Unknown Title" instead of the real structure title.
- Several visual issues: a Comparison tab chart overlapping its stats row, inconsistent tab spacing, sequence-alignment-grid text overlap.

### Changed
- **Tailwind CSS now compiles at build time** via Vite instead of loading from a CDN at runtime — removes the "should not be used in production" warning and an external runtime dependency.
- Loose utility scripts (`check_setup.py`, `build_frontend.ps1`, `run_tests.ps1`) moved into `scripts/`.
- README and verification docs rewritten to reflect the current feature set.

---

Earlier history wasn't tracked in a changelog; see `git log` for the full commit history.
