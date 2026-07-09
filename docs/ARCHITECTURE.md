# StructScope Architecture

This document covers how StructScope's pieces fit together at runtime — module relationships and data flow. For *what* each capability does, see [docs/FEATURES.md](FEATURES.md). For the REST API's exact endpoints/schemas, see the auto-generated `/docs` and `/openapi.json` served by the running app — those stay in lockstep with the code by construction (see `src/backend/api.py`'s `FastAPI(version=...)` call, which reads `config.yaml`'s `app.version` rather than a hardcoded string), so this document doesn't duplicate them.

---

## 1. System overview

Two frontends share one backend and one Mustang core — see the README's "Two Interfaces, One Backend" section for which capabilities live where:

- **Vite SPA** (`web-frontend/`, built into `static/`) — the actively developed interface, talks to the backend exclusively over the REST API described below.
- **Streamlit app** (`app.py`, `pages/`, `src/frontend/`) — a separate, currently-deployed interface, imports `src/backend/` modules directly (no HTTP hop).
- **`src/backend/`** — the shared analysis engine (FastAPI app in `api.py`, plus every analyzer/coordinator module). This is the only place pipeline logic lives; neither frontend re-implements it.

## 2. Compare pipeline data flow

Entry point: `AnalysisCoordinator.run_full_pipeline()` (`src/backend/coordinator.py`), invoked either directly (Streamlit) or via `POST /api/jobs/align` → a background task (SPA). Each stage below mutates or builds the `results` dict that's eventually persisted and returned:

1. **`_download_structures`** — fetches each PDB ID from its source database (RCSB / AlphaFold DB / SWISS-MODEL / ESM Atlas, resolved via `PDBManager.detect_source`) into `data/raw/`. Produces the raw file list.
2. **`_clean_structures`** — strips waters/heteroatoms (configurable), renumbers residues, isolates the requested chain per structure (`PDBManager.clean_pdb`) into `data/cleaned/`.
3. **`_run_mustang_alignment`** — runs the Mustang binary (`MustangRunner`) over the cleaned structures, producing `alignment.pdb`, `alignment.afasta`, and Mustang's own RMSD log/`.rms_rot` output in a fresh `results/<run_id>/` directory.
4. **`process_result_directory`** — the heavy-lifting stage. Parses Mustang's output into the `results` dict: `rmsd_df` (`RMSDCalculator`), `heatmap_path`/`heatmap_fig` and `tree_path`/`tree_fig` (`PhyloTreeGenerator`), `rmsf_values` (`RMSDAnalyzer.calculate_residue_rmsf`), `quality_metrics` (TM-score/GDT via `RMSDCalculator.calculate_alignment_quality_metrics`), and `ramachandran_stats` (`RamachandranService`).
5. **`_generate_insights`** — feeds the `results` dict so far into `InsightsGenerator.generate_insights()` (`src/backend/insights.py`), which runs a handful of independent sub-generators (RMSD homogeneity, outliers, ligand summary, binding-pocket similarity, clustering, quality-metric banding, Ramachandran banding) and sets `results["insights"]`. Every sub-generator degrades to contributing nothing on bad/missing input rather than raising, and a failure in `_generate_insights` itself degrades to `results["insights"] = []` — insights are a summary of already-successful analysis, never a reason to fail the run.
6. **`_persist_run`** — sanitizes the `results` dict (DataFrames → `{index, columns, data}`, `Path` → `str`, so it round-trips through JSON) and writes it to `HistoryDatabase` (`run_history.db`), making it reachable via `GET /api/history` and `GET /api/runs/{id}`.

The SPA never talks to any of the above directly — it submits a job, polls `GET /api/jobs/{job_id}` until `status` is `completed`/`failed`, then reads `job.results` (see §5).

## 3. Discover pipeline data flow

Entry point: `DiscoveryCoordinator.run_discovery_pipeline()` (`src/backend/discovery_coordinator.py`), invoked via `POST /api/jobs/discover` → background task, same job-polling shape as Compare.

1. Download the single input structure (same `PDBManager` as Compare).
2. **Foldseek search** (`FoldseekClient.search`) — queries the selected structural databases (defaults to `pdb100` + `afdb50`; a picker exposes all 9), either against the public Foldseek API or a self-hosted instance (`foldseek.backend: local` in `config.yaml`).
3. **Per-neighbor ID resolution** — maps each hit's opaque target ID back to a UniProt accession via whichever path applies (SIFTS for PDB/CATH hits, direct regex extraction for AlphaFold/BFVD/BFMD, GMGC's own API for `gmgcl_id` hits — MGnify/ESM Atlas hits have no resolution path and are expected to stay unannotated).
4. **Annotation aggregation** (`AnnotationAggregator.aggregate_for_hits`) — for every resolvable neighbor, queries InterPro/QuickGO/STRING/Reactome (cached via `CacheManager`, default 30-day TTL) and rolls the results into a domain/GO-term consensus.
5. **Confidence gating** — a neighbor's annotations only count toward the top-level function hypothesis if its own Foldseek match probability clears `annotation.min_confident_probability` (default 0.5); the aggregator returns both the full tally and a confidence-filtered one (`top_domains` vs `high_confidence_top_domains`, etc.).
6. **Tiered rendering** — the SPA's `DiscoverTab.js` renders the same result at three depths (Public/Student/Researcher), each phrasing the confidence gating differently rather than hiding it.

## 4. Module map

| Module | Responsibility | Depended on by |
|---|---|---|
| `coordinator.py` | Orchestrates the Compare pipeline end to end | `api.py`, `src/frontend/` |
| `discovery_coordinator.py` | Orchestrates the Discover pipeline end to end | `api.py`, `src/frontend/` |
| `pdb_manager.py` | Structure download (4 sources), cleaning, renumbering, metadata fetch | `coordinator.py`, `discovery_coordinator.py`, `api.py` |
| `mustang_runner.py` | Invokes the Mustang binary (native/WSL/Bio3D backends) | `coordinator.py` |
| `rmsd_calculator.py` / `rmsd_analyzer.py` | RMSD matrix parsing, TM-score/GDT, clustering, RMSF | `coordinator.py`, `insights.py` |
| `phylo_tree.py` | Dendrogram generation (static image + interactive Plotly) | `coordinator.py` |
| `ramachandran_service.py` | Torsion-angle/backbone-quality analysis | `coordinator.py` |
| `ligand_analyzer.py` | Binding-site detection, interaction analysis, SASA, pocket-similarity | `coordinator.py`, `api.py`, `src/frontend/` |
| `insights.py` | Turns computed results into plain-language summary bullets | `coordinator.py`, `report_generator.py`, `notebook_exporter.py` |
| `foldseek_client.py` / `foldseek_runner.py` | Structural search (public API / self-hosted) | `discovery_coordinator.py` |
| `annotation_aggregator.py` | Multi-source functional annotation lookup + caching | `discovery_coordinator.py` |
| `report_generator.py` / `notebook_exporter.py` / `discovery_report_exporter.py` / `citation_exporter.py` | Export formats (PDF, HTML notebook, HTML Discover report, citations) | `api.py` |
| `database.py` | SQLite-backed run history | `coordinator.py`, `discovery_coordinator.py`, `api.py` |
| `api.py` | FastAPI app — the only HTTP surface; wires every module above into REST endpoints | Vite SPA |

## 5. API overview

The exhaustive endpoint/schema reference is the auto-generated `/docs` (Swagger UI) and `/openapi.json` on the running app — deliberately kept accurate by construction rather than hand-maintained. What that schema alone doesn't convey:

- **Auth**: unset by default (open access). Set `ALIGNX_API_KEY` to require an `X-API-Key` header (or `?api_key=` query param, so plain `<a>`/`window.open` links like PDF downloads can still authenticate) on every `/api/*`, `/results/*`, and `/raw/*` route. The SPA's own shell (`/`) is never gated.
- **Rate limiting**: only `POST /api/jobs/align` and `POST /api/jobs/discover` are limited (5 and 3 submissions per 60s by default, configurable via `ALIGNX_JOB_RATE_LIMIT_MAX`/`ALIGNX_DISCOVERY_RATE_LIMIT_MAX`/`ALIGNX_JOB_RATE_LIMIT_WINDOW_SECONDS`) — these trigger real compute (Mustang) or hit Foldseek's own shared-rate-limited public API, unlike cheap reads such as `/api/history` or job-status polling. The limiter keys on the API key if one was supplied, else client IP, and applies even when no API key is configured at all.
- **Workflow pattern**: every long-running operation (alignment, Discover) is submit-then-poll, not request/response — `POST /api/jobs/{align,discover}` returns `202 {job_id, status: "queued"}` immediately; poll `GET /api/jobs/{job_id}` until `status` is `completed` or `failed`, then read `results` off the completed job. The SPA's own `main.js` (`runAlignment` → `pollJobUntilDone`) follows this exact pattern — it's not just a server-side implementation detail, it's the contract every client (including StructScope's own frontend) is expected to follow.
