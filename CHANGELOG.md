# Changelog

All notable changes to StructScope (formerly AlignX) are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [3.46.0]

First batch of the legacy Streamlit UI's `python:S3776` cleanup (2 of 14 findings: complexity 16, 61), both in `src/frontend/analysis.py`. Scoped in per an explicit decision to include the Streamlit UI despite it no longer being the actively-developed interface, since it's still deployed.

### Fixed
- **`load_run_from_history`** (16→within limit): the duplicated "process result directory, attach id/name/timestamp" logic (previously copy-pasted between the silent-auto-recovery and interactive-load branches) was extracted into `_restore_results()`; widget-syncing extracted into `_sync_input_widgets_to_run()`.
- **`render_dashboard`** (61→within limit): the largest function in this file - split along its existing numbered-comment sections into `_render_first_visit_banner`, `_render_metrics_row`/`_render_avg_rmsd_metric`, `_ensure_chain_info_loaded`, `_render_run_and_metadata_controls`/`_render_metadata_expander`, and `_render_pre_analysis_tools`.

### Added
- **`tests/test_analysis.py`** (new, 5 tests, using `streamlit.testing.v1.AppTest` - the same real-Streamlit-render approach already established for `sidebar.py`): `render_dashboard`'s empty/pre-analysis/results-shown states, and `load_run_from_history`'s not-found path in both interactive and silent-auto modes. This file had zero prior test coverage.

### Verified
- Full suite: 540 tests passing (backend + frontend + these 5 new Streamlit AppTest ones).
- `black`/`ruff` clean.

## [3.45.0]

Eighth batch of the `new_coverage` push - the Streamlit sidebar (`src/frontend/sidebar.py`), previously 0% covered despite being the app's main interactive control surface. Uses Streamlit's `AppTest` harness with a real `session_state` (via `SessionInitializer.initialize()`) rather than hand-faking widget/session semantics, following the same pattern established for `session_manager.py`.

### Added
- **`tests/test_sidebar.py`** (new, 23 tests): mustang install status banner, System Health diagnostics (Run Diagnostics/Free RAM/Clear Logs buttons, PASSED-status rendering with a faked `SystemManager`), the soft-reset confirm/cancel flow (`_do_soft_reset`'s field clearing, `zip_buffer_*` key cleanup, and its "changed size during iteration" defensive copy), the deep-clean confirm/cancel flow (`_do_deep_clean`'s real filesystem cleanup of `data/raw/<session_id>`/`data/cleaned/<session_id>`), the History panel (empty state, card rendering with protein-preview overflow, Load/Delete/Clear-All-History against a faked `HistoryDatabase`), Guided Mode toggle, and Structure Options (multi-chain-detected warning label, Specify-Chain-ID text input). File coverage: 0% → 94%.

### Verified
- Full backend suite: 535 tests passing.
- `black`/`ruff` clean.

## [3.44.0]

Finishes `pdb_manager.py`'s dedicated-session cleanup: the remaining two findings, including the single largest Cognitive Complexity finding in the codebase (94).

### Fixed
- **`build_residue_renumber_map`** (31→within limit): this function's own docstring warned "keep this predicate in sync with `CleanSelect.accept_residue`" - it was a hand-duplicated copy of the exact same accept/reject logic. Now that `_CleanSelect` is a real reusable class (from the 3.43.0 `clean_pdb` refactor), it calls `clean_select.accept_residue()` directly instead - fixes the complexity finding and eliminates the duplication (and the risk of the two drifting apart) at the same time.
- **`fetch_metadata`** (94→within limit, the largest finding in the codebase): split into `_classify_pdb_ids`, `_fetch_uniprot_name_organism` (shared by AlphaFold/SWISS-MODEL), `_fetch_rcsb_metadata`/`_parse_rcsb_entry`, `_fetch_alphafold_metadata`, `_fetch_swissmodel_metadata`/`_fetch_swissmodel_repository_info`, `_esm_metadata`, and `_remap_metadata_to_original_ids`, plus a shared `_empty_metadata()` replacing three copy-pasted default-dict literals.

### Verified
- Full backend suite: 512 tests passing.
- `fetch_metadata` had **zero existing test coverage** despite being a real, heavily-used code path - given the scale of this rewrite, verified directly against all 4 live metadata APIs (RCSB, UniProt via AlphaFold, SWISS-MODEL's own repository API, ESM Atlas's fixed fields) with a real mixed-source batch, confirming correct per-source titles/methods/resolutions/organisms, case-insensitive original-ID remapping (`4hhb` and `4HHB` both resolving correctly), and edge cases (empty batch, unknown PDB ID, malformed AlphaFold ID).
- Real end-to-end Docker verification of the `build_residue_renumber_map` reuse: ran a real 4HHB+2HHB alignment, then hit `/api/ligands` (found the real HEM heme groups) and `/api/interactions` (found the biologically-correct proximal histidine HIS87 2.14 Å from the heme, with a correctly-computed `aligned_resi`).
- `black`/`ruff` clean.

This closes out `pdb_manager.py` - all 4 of its Cognitive Complexity findings are now resolved, along with every other backend finding in the original 41-item S3776 list. Only the legacy Streamlit UI's 14 findings remain in that category.

## [3.43.0]

`pdb_manager.py` was explicitly deferred earlier as "a dedicated session" given it's the single most-used file in the app - this starts that session with its two highest-complexity findings.

### Fixed
- **`download_pdb`** (69→within limit): the 4 near-identical per-source branches (AlphaFold's multi-version fallback loop, SWISS-MODEL, ESM Atlas, standard PDB) were extracted into `_fetch_alphafold_response`/`_fetch_swissmodel_response`/`_fetch_esmfold_response`/`_fetch_pdb_response`. Preserved two subtle, easy-to-miss existing behaviors exactly rather than "fixing" them as a side effect: the HTTP client is only explicitly closed on a non-200 response, not on a timeout/exception (a pre-existing resource-leak-on-exception quirk, left as-is since fixing it wasn't asked for and isn't safe to bundle into a refactor); and only the standard-PDB branch's `pdb_id = pdb_id.upper()` reassignment affects the outer function's later cache-registration and log messages (moved to the call site, not into the extracted helper, to keep that scoping identical).
- **`clean_pdb`** (38→within limit): the nested `CleanSelect` class (closing over the method's locals) became a real module-level `_CleanSelect` class taking its filter parameters via `__init__`, duck-typing `Bio.PDB.Select`'s 4-method contract instead of subclassing it (avoids a module-level Bio.PDB import). The pLDDT-scale detection and per-residue rebuild loop were extracted into `_detect_plddt_scale`/`_find_target_chain`/`_build_clean_residue`.

### Verified
- Full backend suite: 512 tests passing.
- Given both functions sit on the critical path of every single Compare-mode run, went beyond unit tests: built a fresh Docker image and ran two real end-to-end `/api/jobs/align` runs through the actual HTTP API - 4HHB+2HHB (exercises the standard-PDB download branch) and 4HHB+AF-P69905-F1 (exercises both the AlphaFold download branch and `clean_pdb`'s pLDDT-pruning path) - both completed successfully with real RMSD/identity/heatmap/tree output.
- Also ran a direct, non-Docker real-network test of `download_pdb` against both RCSB and the AlphaFold DB to confirm the extracted per-source fetchers still make the exact same live HTTP requests as before.
- `black`/`ruff` clean.

## [3.42.0]

Seventh batch of the `new_coverage` push - five backend files that had never been unit tested at all or only partially: `ligand_analyzer.py`, `result_manager.py`, `ramachandran_service.py`, `sequence_viewer.py`, and `insights.py`, plus filling the remaining gaps in the pre-existing `structure_viewer.py` suite.

### Added
- **`tests/test_ligand_analyzer.py`** (new, 16 tests): `get_ligands` (finds real ligands, ignores water/ions, missing-file and parse-failure paths), `calculate_interactions` (finds nearby residues via `NeighborSearch`, excludes far ones, invalid-ID-format and ligand-not-found error paths), `calculate_sasa`, `calculate_interaction_similarity`/`_jaccard_score` (empty input, identical/disjoint/partial-overlap fingerprints). File coverage: 14.7% → 100%.
- **`tests/test_result_manager.py`** (new, 10 tests): `list_runs` (valid/missing-dir/missing-matrix filtering, session-id pass-through), `get_run_rmsd` (load, missing, read-failure), `calculate_difference` (overlapping proteins, missing run, no-overlap case). File coverage: 35.9% → 100%.
- **`tests/test_ramachandran_service.py`** (new, 14 tests): `calculate_torsion_angles` against a real 3-residue synthetic backbone (terminal residues correctly missing one angle), `_torsion_row`, all `_classify_region` boundary cases (Alpha/Beta/L-Alpha/Allowed/Outlier/Terminal), `aggregate_metrics` (quality score math, outlier list capped at 10). File coverage: 54.8% → 100%.
- **`tests/test_sequence_viewer.py`** (new, 23 tests): `parse_afasta` (multi-sequence, wrapped lines, blank-line skipping, missing/unreadable file), `calculate_conservation`, `_residue_cell_html`/`_consensus_symbol` color/symbol thresholds, `generate_html` smoke test, `calculate_identity` (gap-gap exclusion, zero-length-pair skip, multi-pair averaging). File coverage: 35.5% → 100%.
- **`tests/test_insights.py`** (new, 21 tests): all 6 `_get_*_insights` sub-generators plus the lazy `analyzer` property and `generate_insights`'s aggregation/early-return paths. File coverage: 75.9% → 100%.
- **`tests/test_structure_viewer.py`** (+11 tests, on top of an existing 5-test suite covering the auto-rotation-stops-itself behavior): backward-compat list-to-dict highlight conversion, missing-file exception paths for all three `render_*` functions, and the three `show_*_in_streamlit` Streamlit wrappers (`components.html`/`st.error` dispatch, `show_synced_grid_in_streamlit`'s row-count-based iframe height calculation). File coverage: 69.9% → 100%.

### Verified
- Full backend suite: 512 tests passing.
- `black`/`ruff` clean on all touched/new test files.
- Confirmed via re-analysis (combined with the concurrent session's `pdb_manager.py` complexity work through v3.44.0): `new_coverage` 61.05% → 64.21%.

## [3.41.0]

Re-pulled the open SonarCloud issue list (26 remaining) and cleared the 3 quick/mechanical ones before returning to the bigger Cognitive Complexity items.

### Fixed
- **`python:S1481`** (`coordinator.py:151`): unused `success` from `clean_pdb()`'s return tuple renamed to `_`.
- **`python:S5958`** (`tests/test_report_generator.py:117`): `pytest.raises(Exception)` narrowed to `pytest.raises(FileNotFoundError)` - confirmed that's the actual (unwrapped) exception `generate_full_report()` raises when its output directory doesn't exist, by reproducing it directly.
- **`python:S3776`** (`api.py:412`, `sanitize_for_json`, 20→within limit - a new finding since the 3.36.0 refactor only got it from 30 to 20, not under threshold): extracted `_is_intlike`, `_is_floatlike`, `_coerce_float`, and `_coerce_via_to_dict`, and switched the remaining dispatch from `elif` to early `if`/`return`.

### Verified
- Full backend suite: 417 tests passing.
- Manually re-verified `sanitize_for_json()`'s numpy scalar/NaN/Inf/ndarray/DataFrame/Path/dict-key-stringification behavior is unchanged.
- `black`/`ruff` clean.

## [3.40.0]

Sixth batch of the `new_coverage` push - `database.py`'s CRUD/cache-management surface and two previously-untested files, `utilities.py` and `foldseek_runner.py`'s exception/edge paths.

### Added
- **`tests/test_database.py`** (+18 tests): `TestRunCrud` (`get_run`, `get_all_runs` sorting/pagination/session-scoping, `count_runs`, `delete_run`, `get_latest_run`, `clear_all_runs`) and `TestCacheManagementMethods` (register/retrieve/remove cache items, total size, oldest-first ordering). File coverage: 58% → 79%.
- **`tests/test_utilities.py`** (new, 13 tests): `SystemManager.run_diagnostics` (Mustang detection via subprocess, including binary-missing and unrecognized-output paths), `cleanup_old_runs` (TTL threshold, legacy-dir skip, empty-session-dir removal), `get_aggregate_stats` (sums, DB-error fallback, missing-key handling). File coverage: 39% → 93%.
- **`tests/test_foldseek_runner.py`** (+7 tests): exception paths for native/WSL binary checks and WSL path lookup, missing-result-file failure, search timeout, WSL command-shape verification. File coverage: 84% → 97%.

### Fixed
- **`test_database.py` timestamp-ordering flakiness**: two `save_run()` calls within the same wall-clock second produced identical second-granularity timestamps, so `ORDER BY timestamp DESC` didn't reliably resolve their order. Added a `_save_run_at()` helper that monkeypatches `datetime.now()` to distinct controlled values rather than relying on real elapsed time.

### Verified
- Full backend suite: 417 tests passing, both locally (Python 3.12/Windows) and inside a fresh `python:3.10-slim` Docker container matching CI's exact environment (no platform-dependent bugs found this round).
- `black`/`ruff` clean on all three touched test files.
- Confirmed via re-analysis: `new_coverage` 56.9% → 61.05%.

## [3.39.0]

Seventh and final batch of the agreed-scope backend `python:S3776` cleanup (complexity 33, 33, 37, 37). This completes every open finding from 16 through 38 except `pdb_manager.py`'s three (38/69/94), which were deliberately deferred to a dedicated session given the file's size and centrality. 22 of 26 backend findings now resolved.

### Fixed
- **`annotation_aggregator.py`**'s `aggregate_for_hits` (33→within limit): the ~180-line Discover annotation pipeline was split into `_resolve_candidates`, `_collect_neighbor_keys`, `_count_neighbor_annotations`, `_top_domains`/`_top_go_terms` (also de-duplicates the top/high-confidence list-building, previously copy-pasted twice each), and `_neighbor_summary_counts`.
- **`annotation_aggregator.py`**'s `resolve_go_term_names` (33→within limit): the cache-read/cache-write try/except blocks and the per-chunk QuickGO fetch were extracted into `_try_get_cached_go_name`, `_try_cache_go_name`, and `_fetch_go_term_names_chunk`.
- **`report_generator.py`**'s `generate_full_report` (37→within limit): split along its existing 5 numbered PDF sections into `_write_summary_section`, `_write_insights_section`, a shared `_write_image_section` (used by both the heatmap and tree sections, which render identically apart from which font their "not available" message uses), and `_write_matrix_section`.
- **`rmsd_calculator.py`**'s `calculate_structure_rmsd` (37→within limit): split into `_build_residue_mapping`, `_select_structures` (the Models-vs-Chains selection logic), and `_common_ca_coords` (the per-pair common-column extraction).

### Verified
- Full backend suite: 417 tests passing.
- Manually confirmed `_build_residue_mapping`/`_common_ca_coords` reproduce the original's exact column-mapping and gap-handling behavior against a hand-built 2-sequence alignment with a gap.
- `black`/`ruff` clean on all four touched files.

## [3.38.0]

Sixth batch of the backend `python:S3776` cleanup (3 more of the 41 open findings: complexity 31, 33, 36). 18 of 26 backend findings now resolved.

### Fixed
- **`rmsd_calculator.py:386`** (`calculate_alignment_quality_metrics`, 31→within limit): the nested "build per-structure coordinate data" then "compare every structure against every other" double loop was split into `_build_structure_data()`, `_common_aligned_coords()`, and `_average_quality_scores()`.
- **`ligand_analyzer.py:113`** (`calculate_interactions`, 33→within limit): the ligand-lookup triple-nested loop and the per-residue min-distance double loop were extracted into `_find_ligand_and_search_atoms()`, `_min_distance()`, `_interaction_type()`, and `_interaction_record()`.
- **`rmsd_analyzer.py:216`** (`calculate_residue_rmsf`, 36→within limit): the function's four sequential stages (parse AFASTA, build alignment-column maps, parse PDB CA coordinates, compute per-column RMSF) were split into `_parse_afasta_sequences()`, `_build_structure_maps()`, `_parse_ca_coords()`, and `_rmsf_for_column()` - each stage independently testable.

### Verified
- Full backend suite: 380 tests passing.
- `calculate_residue_rmsf` had **zero existing test coverage** despite being a real, reachable code path - manually verified the refactor against a hand-built 2-structure/1-gap synthetic fixture, hand-calculating the expected RMSF at all 4 alignment columns (0.5, 0.0, 0.0, 2.0 Å) and confirming the refactored code produces exactly those values, including correct gap handling and chain-boundary detection.
- `black`/`ruff` clean on all three touched files.

## [3.37.0]

Fifth batch of the `new_coverage` push - `session_manager.py`, which had never been unit tested at all (0%) despite being real, load-bearing code (`app.py`'s Streamlit entry point calls it directly).

### Added
- **`tests/test_session_manager.py`** (new, 12 tests): the 3 free functions (`get_session_id`, `get_session_paths`, `cleanup_stale_sessions` - including the TTL-purge threshold, the legacy `run_*`-prefix skip, DB-record cleanup, and a broken-DB-connection not blocking the filesystem cleanup) plus `SessionInitializer.initialize()` itself, exercised through Streamlit's `AppTest` harness (a real `session_state`, not a hand-rolled fake) rather than mocking every one of the ~10 backend classes it constructs - confirms all expected keys actually populate and that a second call is idempotent. File coverage: 0% → 96%.

### Verified
- 380 backend tests total (up from 368), all passing.

## [3.36.0]

Fifth batch of the backend `python:S3776` cleanup (3 more of the 41 open findings: complexity 29, 30, 31). 15 of 26 backend findings now resolved. This batch includes `coordinator.py`'s `run_full_pipeline` - the core Compare-mode orchestration function - refactored with extra care given its centrality.

### Fixed
- **`rmsd_calculator.py:61`** (`parse_mustang_log_for_rmsd`, 29→within limit): the per-line row-detection logic (nested try/except with an inner loop and a `break`) was extracted into `_try_parse_rmsd_row()`.
- **`api.py:366`** (`sanitize_for_json`, 30→within limit): split into `_coerce_numpy_scalar()`, `_is_plotly_bdata()`, and `_decode_plotly_bdata()` - the two nested try/except blocks (numpy-scalar coercion, Plotly binary-data decoding) that drove most of the complexity are now standalone, independently testable functions.
- **`coordinator.py:93`** (`run_full_pipeline`, 31→within limit): the ~180-line pipeline function was split along its existing numbered-step comments into `_resolve_run_identity`, `_download_structures`, `_clean_structure`/`_clean_structures`, `_run_mustang_alignment`, `_generate_insights`, and `_persist_run` - each stage now returns/raises independently instead of all sharing one function's control flow.

### Verified
- Full backend suite: 368 tests passing.
- Given `run_full_pipeline`'s centrality (it's the entire Compare-mode alignment path), went beyond the unit tests: built a fresh Docker image, ran the container, and submitted a real `/api/jobs/align` job for 4HHB/2HHB through the actual HTTP API - completed successfully end-to-end with a real RMSD (0.1 Å), 100% sequence identity, heatmap/tree/newick all generated and saved to history, matching pre-refactor behavior.
- Manually confirmed `_try_parse_rmsd_row()` and `sanitize_for_json()`'s numpy/Plotly-bdata paths reproduce the originals' exact behavior, including the malformed-input fallback paths.
- `black`/`ruff` clean on all three touched files.

## [3.35.1]

Confirming 3.34.0's `new_coverage` progress via re-analysis, and that this entry's Cognitive Complexity refactors (`notebook_exporter.py`'s `export()`, `rmsd_calculator.py`'s `parse_rms_rot_file()`) didn't break the real tests written for those two files in 3.34.0/3.26.0 - both test files re-run clean against the refactored code (38/38 passing), confirming the refactors preserved external behavior as intended.

### Verified
- **Confirmed via re-analysis**: `new_coverage` rose 56.1% → 56.9%.

## [3.35.0]

Fourth batch of the backend `python:S3776` cleanup (3 more of the 41 open findings: complexity 26, 27, 28). 12 of 26 backend findings now resolved.

### Fixed
- **`notebook_exporter.py:37`** (`export`, 26→within limit): split into `_prepare_stats`, `_load_pdb_content`, `_load_dmol_js`, `_heatmap_div`, `_rmsf_div`, `_ligand_html`, `_processed_insights` - each independent piece of the notebook's data prep is now its own testable unit instead of one long function with 7 unrelated `if` blocks.
- **`api.py:887`** (`get_interactions`, 27→within limit): its structure-file lookup (raw-download dir, then run-results-dir fallback, trying 3 filename casings in each) was byte-for-byte duplicated in `get_ligands` right above it. Extracted both into a shared `_find_structure_pdb_path()` - fixes the complexity finding and removes real duplication. The residue-renumbering block was separately extracted into `_add_aligned_resi()`.
- **`rmsd_calculator.py:167`** (`parse_rms_rot_file`, 28→within limit): the nested `for i / for j` matrix-building loop with inner value-parsing try/except was split into `_parse_matrix_value()`, `_matrix_row()`, and `_extract_rms_rot_data_rows()`.

### Verified
- Full backend suite: 368 tests passing (1 unrelated flaky failure in `test_async_pdb.py::test_async_metadata` reproduced and cleared on immediate re-run, in a file untouched by this change).
- Manually confirmed `_parse_matrix_value`/`_matrix_row` reproduce the original's exact padding/truncation/malformed-value behavior.
- `black`/`ruff` clean on all three touched files.

## [3.34.0]

Fourth batch of the `new_coverage` push - `notebook_exporter.py` and `report_generator.py`, the two largest remaining near-zero-coverage backend files (`phylo_tree.py`, the third file originally on this list, had already reached 88% via unrelated concurrent refactor work).

### Added
- **`tests/test_notebook_exporter.py`** (new, 8 tests): a full real end-to-end export (real Plotly heatmap figure, real alignment.pdb content, ligand table, markdown-stripped insights) verified by reading the actual generated HTML back and checking real content landed in it; missing-stats defaults; the no-heatmap fallback message; and the `template_str` property's fallback-to-minimal-template behavior when the real template file is missing. File coverage: 18% → 97%.
- **`tests/test_report_generator.py`** (new, 7 tests): a full real PDF generation (real stats, real tiny PNG images for the heatmap/tree sections via Pillow, a real RMSD `DataFrame`), the `sections` filter, regenerating insights when they're not already attached to a run, the Å-to-Latin-1 character mapping `clean_text()` exists specifically for, a corrupt-image-file fallback, and an output-directory-doesn't-exist failure path. File coverage: 13% → 95%.

### Verified
- 368 backend tests total (up from 353), all passing locally and in a Docker container matching CI's Python 3.10/Linux environment before pushing.

## [3.33.0]

Third batch of the backend `python:S3776` cleanup (3 more of the 41 open findings: complexity 16, 23, 25). 9 of 26 backend findings now resolved.

### Fixed
- **`coordinator.py:30`** (`sanitize_for_json`, 16→within limit): the dict-key sanitization `if/elif/elif` chain nested inside the dict branch's `for k, v in val.items()` loop was extracted into `_sanitize_json_key()`, turning the dict branch into a one-line comprehension.
- **`ramachandran_service.py:20`** (`calculate_torsion_angles`, 23→within limit): the triple-nested `for model / for chain / for i, (phi, psi)` loop was split into `_chain_torsion_angles()` (per-chain) and `_torsion_row()` (per-residue), each independently well under the threshold.
- **`utilities.py:60`** (`cleanup_old_runs`, 25→within limit): the nested `for session_dir / for run_dir / if / if / try` was split into `_cleanup_session_runs()` (per-session deletion) and `_remove_if_empty()` (the trailing empty-dir cleanup), removing two levels of nesting from the outer loop.

### Verified
- Full backend suite: 368 tests passing (up from 353 - unrelated to this entry, from concurrent test-coverage work).
- Manually confirmed `sanitize_for_json()` still correctly sanitizes both dict keys and values (np.int64 key, Path key, nested np.float32/tuple values) in one call.
- `black`/`ruff` clean on all three touched files (reformatted by `black` for line-length after extraction, no logic change).

## [3.32.0]

Second batch of the backend `python:S3776` cleanup (3 more of the 41 open findings: complexity 20, 20, 22).

### Fixed
- **`annotation_aggregator.py:261`** (`resolve_pdb_uniprot_accession`, 20→within limit): extracted the SIFTS response's nested `for accession, info in ... for mapping in ...` parsing into `_parse_sifts_chain_accessions()`, and flattened the surrounding try/if into early returns.
- **`ligand_analyzer.py:49`** (`get_ligands`, 22→within limit): the triple-nested `for model / for chain / for residue` loop with an inner `if hetfield != " " → if resname in ignored → continue` was replaced by a list comprehension over a new `_ligand_info_from_residue()` helper (returns `None` for non-ligand residues, filtered out).
- **`ligand_analyzer.py:289`** (`calculate_interaction_similarity`, 20→within limit): the pairwise Jaccard-index double loop's `if i==j / else / if both-empty / else` chain was extracted into `_jaccard_score()`.

### Verified
- Full backend suite: 353 tests passing, unchanged from before this batch.
- Manually confirmed `_jaccard_score()` reproduces the original's exact values (both-empty→0.0, partial overlap→correct ratio, identical sets→1.0) and `parse_hits`/ligand extraction produce the same shapes as before.
- `black --check` and `ruff check` clean on both touched files.

## [3.31.0]

First batch of the `python:S3776` Cognitive Complexity cleanup (41 open findings total, complexity 16-179, mostly in the legacy Streamlit UI). Scoped to backend-only, smallest-excess-first, per an explicit decision to skip the legacy Streamlit-only files for now given their size (up to 179) and the regression risk of touching live logic there without dedicated attention. This entry covers the 3 smallest backend findings (17, 17, 18).

### Fixed
- **`citation_exporter.py:320`** (17→within limit): `citations_for_discover_run()` had four near-identical `if any(...) and "x" not in ids: ids.append("x")` blocks. Replaced with a data-driven `_ANNOTATION_FIELD_SOURCE` list and a small `add()` closure that handles dedup once instead of per-branch.
- **`sequence_viewer.py:93`** (17→within limit): `generate_html()`'s per-residue coloring `if/elif` chain and per-column consensus-symbol `if/elif` chain, both nested inside loops, were extracted into `_residue_cell_html()` and `_consensus_symbol()` - same logic, but a nested branch inside a loop no longer compounds with the enclosing function's own complexity.
- **`foldseek_client.py:220`** (18→within limit): `parse_hits()`'s nested `if isinstance(dict) → if/elif → for → for → if/elif isinstance` was flattened into early returns plus a `_flatten_alignments()` helper for the innermost list-or-dict-or-neither check.

### Verified
- All three refactors produce byte-identical output to the originals on representative inputs (checked manually: `parse_hits` against dict/list/empty/garbage payloads, `generate_html` against a real conservation+sequence pair).
- Full backend suite: 353 tests passing (no change in count - these are refactors, not behavior changes, so no new tests were needed beyond the existing coverage each function already had).
- `black --check` and `ruff check` clean on all three touched files.

## [3.30.0]

First pass at the 47 open SonarCloud issues pulled from the public API (`api/issues/search?componentKeys=voidomin_AlignX&resolved=false`): 3 are the `S8544` hash-pinned-lockfile decision explicitly deferred in v3.24.0 (still deferred, no change here), 41 are Cognitive Complexity (`S3776`) refactors ranging from just-over-threshold to extreme (up to 179, mostly in the legacy Streamlit UI) - deliberately out of scope for this entry, tracked as a separate follow-up. This entry only covers the remaining 3 mechanical/safe ones.

### Fixed
- **`docker:S6500`**: `Dockerfile`'s `apt-get install` now passes `--no-install-recommends` - verified via a real `docker build` + `docker run` + `/health` check that no recommended-but-actually-needed package (e.g. TLS certs for the Mustang source download) was silently relied upon.
- **`docker:S7018`**: alphabetized the same `apt-get install` package list (`build-essential, curl, make, tar, wget`).

### Not fixed (false positive)
- **`python:S7504`** (`src/frontend/sidebar.py:19`, "unnecessary `list()` call"): the existing code comment already explains why it's required - the loop body deletes from `st.session_state` during iteration, which raises `RuntimeError: dictionary changed size during iteration` without the defensive copy. Added a note pointing at the specific rule so a future cleanup pass doesn't "fix" this into a live bug.

### Verified
- Full `docker build` succeeded; container's `/health` endpoint responded `{"status":"healthy","mustang_installed":true,...}`.
- Existing test suite unaffected (comment-only change to `sidebar.py`, Dockerfile-only change with no Python surface).

## [3.29.0]

Third batch of the `new_coverage` push - `pdb_manager.py`, the next-highest genuinely-testable gap by uncovered-line count.

### Added
- **`tests/test_pdb_manager.py`** (+22 tests): `download_pdb`'s full branch set (invalid ID format, cache-hit with no network call, standard PDB success/404, AlphaFold's multi-version fallback and all-versions-exhausted path, SWISS-MODEL and ESM Atlas success, and an unhandled-exception-becomes-a-clean-failure case), `save_uploaded_file` (the Streamlit-side upload path, distinct from the SPA's `save_uploaded_bytes`), and `batch_clean` (including a single-file failure not aborting the rest of the batch). File coverage: 52% → 64%.

### Verified
- 353 backend tests total (up from 340), all passing both locally and in a Docker container reproducing CI's Python 3.10/Linux environment before pushing - the same check that caught the previous batch's platform-dependent bugs, this time finding none.

## [3.28.0]

Second batch of the `new_coverage` push (54.3% after the previous batch) also fixed 3 new `pythonsecurity:S2083` (path-injection) vulnerabilities that landed alongside the concurrent citation-export feature - `CitationExporter.export()` built a temp-file path from `run_id` with no validation of its own, relying entirely on `api.py` having already validated it before calling in. SonarCloud's analyzer can't see that cross-module guarantee, and more importantly, `citation_exporter.py` shouldn't have to rely on it either.

### Fixed
- **`src/backend/citation_exporter.py`**: `CitationExporter.export()` now validates `run_id` against the same `^[A-Za-z0-9_-]+$` pattern `api.py`'s `_safe_segment()` already enforces, raising `ValueError` on anything else, before it ever reaches the temp-file path construction. Defense in depth, not just satisfying the analyzer - this module has no way to know whether a future caller validates first. (A separate CI break from the same concurrent commits - unformatted `citation_exporter.py`/`api.py` failing `black --check .` - was already fixed in the previous commit.)

### Added
- **`tests/test_citation_exporter.py`** (new, 20 tests): `_structure_source_citation`, `citations_for_compare_run`/`citations_for_discover_run` (including which annotation sources get cited only when they actually contributed data to a neighbor), and `CitationExporter.export()`'s validation (path traversal, path separators, empty string all rejected) plus a real end-to-end export producing an actual file with both plain-text and BibTeX sections. File coverage: 0% → 97%.
- **`tests/test_api.py`** (+4 tests): `/api/report/citations` and `/api/discover/citations`, including the 404-for-unknown-run and 400-for-wrong-run-type paths.

### Fixed (test infrastructure)
- **3 tests in `tests/test_mustang_runner.py`** from the previous entry's batch turned out to be platform-dependent in a way that only broke on Linux CI, not locally on Windows: `Path("C:/Users/...")` only behaves as a genuine absolute Windows path with a drive letter on an actual Windows machine - on Linux, pathlib treats "C:" as a plain directory name, so `.absolute()` silently prepended the real CWD instead of producing the drive-letter string the WSL-path-conversion logic expects. Found by reproducing CI's exact environment locally via Docker (`python:3.10-slim`, fresh `pip install`, real repo files) rather than trusting the Windows-local test run - fixed by mocking `.absolute()`'s return value directly instead of relying on a real `Path`.

### Verified
- 340 backend tests total (up from 316), all passing in both the local Windows dev environment and a Docker container reproducing CI's exact Python 3.10/Linux setup - this was the deciding check that caught the 3 platform-dependent failures before they could reach CI a second time.
- **Confirmed via re-analysis**: `new_coverage` rose 48.4% → 55.5%; open vulnerabilities dropped 7 → 4 (all 3 `pythonsecurity:S2083` findings resolved, back to just the pre-existing `S8544` set).

## [3.27.0]

First-run onboarding: the Overview tab's empty state was a bare "Add at least 2 PDB structures to align" message, even though curated quick-start example sets already existed — just on the separate Dashboard tab, which is not where a new user lands (`activeTab` defaults to `'overview'`).

### Added
- **`web-frontend/src/quickStartExamples.js`**: the `QUICK_START_EXAMPLES` list (kinase family, hemoglobin variants, Trp-cage + AlphaFold) extracted from `DashboardTab.js` into a shared module so both tabs use the same one-click examples instead of duplicating/drifting.
- **`OverviewTab.js`**'s empty state now renders those same quick-start buttons directly below the "add structures" prompt; clicking one calls the existing `loadQuickStart()` flow (already used by the Dashboard), which loads the pair and switches to Overview — so a first-time user never needs to already know Dashboard has examples.

### Fixed
- **Pre-existing test gap from 3.25.0**: `SequenceTab.test.js` and `DiscoverTab.test.js` mock `../api.js` and were missing `getCitationsUrl`/`getDiscoveryCitationsUrl` added by the citations-export change, which only surfaced when running the full frontend suite (the narrower `-k citation` pytest run in 3.25.0 didn't catch it, since it's a JS test failure, not Python).

### Verified
- 3 new `OverviewTab` tests (buttons render, click calls `onQuickStart` with the right IDs, buttons disappear once structures are selected). Full frontend suite: 145 tests passing (0 failing, including the two fixed pre-existing failures).
- Frontend production build succeeds; backend API test suite (49 relevant tests) unaffected.

## [3.26.0]

Real test-writing pass toward the `new_coverage` Quality Gate condition (48.4% at the start of this entry, needs 80%, free-tier SonarCloud can't have the threshold adjusted). First batch: the highest-value genuinely-testable backend gaps, prioritized by actual uncovered-line count pulled from SonarCloud's `component_tree` API rather than guessed.

### Added
- **`tests/test_rmsd_calculator.py`** (new, 30 tests): `calculate_tm_score`/`calculate_gdt_ts` (including a real correction to a wrong hand-computed assumption - TM-score only reaches 1.0 when `l_target` equals the actual compared-point count, not any larger target length), `calculate_rmsd_from_superposition`, `parse_mustang_log_for_rmsd`, `parse_rms_rot_file`, `parse_rmsd_matrix`'s fallback-strategy ordering, `calculate_structure_rmsd` (including a gapped-alignment case), and `calculate_alignment_quality_metrics` (including discovering that each structure's score is averaged across *all* other structures, not just its best match - a real behavior my first draft assertion got wrong). File coverage: 4.5% → 85%.
- **`tests/test_coordinator.py`** (+6 tests): `AnalysisCoordinator.__init__`'s Mustang-not-installed warning path, `run_full_pipeline`'s download-failure path, a full mocked-I/O-but-real-processing happy path through `run_full_pipeline` (Mustang/PDB download mocked, but `process_result_directory`, history persistence, and `metadata.json` writing all run for real against a real alignment output directory), and `process_result_directory` exercised directly against a real (minimal) Mustang-shaped output directory. File coverage: 32% → 87%.
- **`tests/test_mustang_runner.py`** (+37 tests): the full installation-detection strategy chain (native/WSL/compiled-binary checks and their priority order in `_check_mustang`), `_perform_installation_check`'s multi-stage fallback (PATH → WSL → compiled → compile-from-source), `_deep_wsl_check`, `_update_executable_from_check`, `_fallback_executable`, `_convert_to_wsl_path`, `_ensure_fasta_exists`'s three branches, `_finalize_alignment_output`'s exit-code handling, and `_stream_process_output`'s line-buffering/timeout behavior (including a real fix to my first draft's mock setup - `poll()` is only consulted when `readline()` returns empty, not every iteration). File coverage: 54% → 74%.

### Verified
- 316 backend tests total (up from 245), all passing; ruff and black clean on every new/touched file.
- Every test in this entry was run and its real failures fixed against actual code behavior, not written to assert whatever the implementation already does - two independent wrong assumptions (TM-score normalization, quality-metric averaging) were caught and corrected this way, and the mustang_runner mock-ordering bug was root-caused by reading the actual loop structure, not guessed at.

## [3.25.0]

A "Methods & Citations" export for both Compare and Discover runs — a scientist citing a StructScope result in a paper previously had no easy way to know exactly what to attribute (algorithm, structure source databases, annotation sources actually used).

### Added
- **`src/backend/citation_exporter.py`**: a bibliography of the tools/databases StructScope can draw on (Mustang, Foldseek, PDB, AlphaFold DB, SWISS-MODEL, ESM Atlas, InterPro, QuickGO, STRING, Reactome, SIFTS, GMGC, StructScope itself), plus `citations_for_compare_run()`/`citations_for_discover_run()`, which inspect a run's actual data (structure ID prefixes, Foldseek databases searched, which annotation types actually returned data for at least one neighbor) to cite only what that specific run used — not everything Discover mode is capable of querying.
- **`GET /api/report/citations`** (Compare) and **`GET /api/discover/citations`** (Discover): generate a combined plain-text + BibTeX `.txt` file, following the same run-lookup pattern as the existing report/notebook/export endpoints.
- **Frontend**: an "Export Citations" link next to the existing PDF/notebook downloads in `SequenceTab.js`, and next to Report/JSON in `DiscoverTab.js`.

### Verified
- Manually exercised both citation-builder functions and the file export end-to-end (correct dedup, correct source detection per structure prefix, correct annotation-source gating).
- Confirmed both routes register on the FastAPI app.
- Full frontend production build succeeds; full existing API test suite (49 relevant tests) still passes unchanged — no test files touched, so no overlap with concurrent test-coverage work.

## [3.24.2]

Fixed the `new_coverage` gate condition's underlying metric problem for real this time, after 3.24.1's `sonar.tests`/`sonar.test.inclusions` attempt broke the whole analysis. Also confirmed SonarCloud's free tier can't have its Quality Gate threshold edited at all (custom quality gates are a Team/Enterprise-only feature) - lowering the 80% requirement was never actually on the table.

### Fixed
- **`sonar-project.properties`**: added `sonar.coverage.exclusions=tests/**/*.py,web-frontend/src/**/*.test.js` - a narrower, different property than the one that broke things before. It only removes matching files from the coverage *requirement*, without touching `sonar.sources`/`sonar.tests` scanning/classification at all.

### Verified
- **Confirmed via re-analysis**, checking the exact metrics that broke last time first: `ncloc` (17846), `code_smells` (42), `bugs`/`vulnerabilities` (0/4) all read their expected real values - this fix did not repeat 3.24.1's breakage.
- Overall `coverage` rose 34.2% → 43.9%; the gate-relevant `new_coverage` rose 36.5% → 48.4% (`new_lines_to_cover` dropped 8097 → 5998, confirming ~2099 test-file lines were correctly excluded). Still below the 80% gate threshold - real test-writing is the only path left to close the remaining gap, tracked separately.

## [3.24.1]

Fixed the last CI/CD-scanning vulnerability from 3.24.0's investigation that wasn't an `S8544` hash-lock finding: `docker:S6470` ("Dockerfiles should not copy the build context using recursive or glob patterns", CRITICAL) on the Dockerfile's `COPY . .` - a different, newer rule than the Security Hotspot already marked "Safe" on the same line weeks ago, this one a hard Vulnerability rather than something reviewable as a hotspot.

Also attempted and reverted a fix for 3.23.0's `new_coverage` gate condition: test files (`tests/*.py`, `*.test.js`) count as "new code requiring coverage," but coverage.py/Vitest never instrument a test file's own lines, so every test file shows 0% covered - meaning writing *more* tests without fixing this first would make the metric worse, not better. Tried the standard fix (`sonar.tests`/`sonar.test.inclusions` in `sonar-project.properties`); it broke the entire analysis instead (re-analysis showed `code_smells`/`bugs`/`vulnerabilities` all reporting 0 and `ncloc` missing entirely - the scanner analyzed almost nothing). Reverted immediately and confirmed a full recovery. Root cause not yet understood; left alone rather than guessing again.

### Fixed
- **`Dockerfile`**: `COPY . .` replaced with an explicit allowlist (`COPY src/ src/`, `COPY config.yaml .`, `COPY static/ static/`) - traced every `project_root / ...` reference in `src/backend/`/`src/utils/` to confirm those three are the *only* things the FastAPI container's `uvicorn src.backend.api:app` entrypoint ever reads; `app.py`, `pages/`, `docs/`, `tests/`, `examples/`, and everything else in the repo is Streamlit-only or dev tooling this container never touches.

### Reverted
- **`sonar-project.properties`**: `sonar.tests=tests,web-frontend/src` + `sonar.test.inclusions=...` added and removed within the same session after confirming it broke analysis wholesale rather than just reclassifying test files. Not re-attempted pending further investigation.

### Verified
- Rebuilt the Docker image with the new allowlist and ran the container: `/health` returns healthy, the SPA serves at `/` (200), and a real `POST /api/chains` round-trip against RCSB (fetching and parsing 1CRN) succeeds - confirming `config.yaml` loads correctly and nothing needed by the app was left out.
- Confirmed both resource files traced as needed (`src/backend/resources/3Dmol-min.js`, `src/resources/templates/*.html`) are actually present inside the built image via `docker exec`.
- 245 backend tests still pass.
- **Confirmed via re-analysis**: the sonar.tests/test.inclusions revert restored `code_smells`/`bugs`/`ncloc` to their expected real values, and `docker:S6470` is gone - open vulnerabilities down to exactly the 4 `S8544` hash-lock findings left over from 3.24.0.

## [3.24.0]

Investigating 3.23.0's `new_security_rating` gate failure turned up something genuinely new: 9 MAJOR findings in `Dockerfile` and `.github/workflows/ci.yml` - CI/CD supply-chain hardening rules that Automatic Analysis evidently never applied to these file types, only now running for the first time under CI-driven analysis.

### Fixed
- **GitHub Actions pinned to full commit SHAs** instead of mutable version tags (`@v4` → `@34e114...  # v4.3.1`, etc.) across every job - a compromised/repointed tag could otherwise inject arbitrary code into the pipeline. Looked up each action's actual resolved SHA via GitHub's API rather than guessing.
- **`pip install --only-binary :all:`** added to every pip install step (Dockerfile + CI) - blocks a compromised package's `setup.py`/build-backend from executing arbitrary code during install, which source (sdist) builds allow and wheel installs don't.
- **`npm ci --ignore-scripts`** added to the frontend CI job - blocks npm packages' preinstall/install/postinstall lifecycle hooks from running arbitrary code.

### Changed
- **`fpdf` → stays `fpdf` (not migrated to `fpdf2`)**: `--only-binary :all:` broke the Docker build outright because the original `fpdf` (last released 2015) ships no wheel at all, only a source distribution. Tried the obvious fix - `fpdf2`, the actively maintained, wheel-shipping, API-compatible fork - but it turned out to *not* be a safe drop-in: generating a real report with `fpdf2` installed raised `FPDFException: Not enough horizontal space to render a single character` from the existing `report_generator.py` code, which works fine under classic `fpdf`. fpdf2's `multi_cell()` is measurably stricter about available width than the original. Reverted to `fpdf`, and exempted just that one package from the binary-only rule via `--no-binary fpdf` instead - migrating to fpdf2 for real would mean reviewing and re-verifying every `cell()`/`multi_cell()` call across every report section, which is a legitimate future task, not a safe side effect of a CI-hardening pass.

### Not fixed (deliberately, pending a decision)
- **`githubactions:S8544`/`docker:S8544`** ("Python dependencies should be locked to verified versions", 3 instances) wants a hash-pinned lock file (`pip install --require-hashes`), not just a flag. Tried generating one with `pip-tools`' `pip-compile --generate-hashes`; it works but produces a large lock file, immediately surfaced a `setuptools` pinning complication, and creates an ongoing maintenance burden (every dependency bump needs regenerating hashes) - different in kind from the flag-based fixes above, and not something to commit to without an explicit decision.

### Verified
- Rebuilt the actual Docker image twice locally (once with the `--only-binary :all:` break, once with the `fpdf` exemption fix) and ran the container - `/health` responds correctly.
- `npm ci --ignore-scripts` followed by a clean `npm test`/`npm run build` - all 142 tests and the production build still succeed, confirming no dependency in this project's tree actually needs an install-time script.
- Reproduced the `fpdf2` `multi_cell()` failure directly (not just read about it) before deciding to revert - generated a real report with `fpdf2` installed and hit the exception firsthand.
- 245 backend tests pass with `fpdf==1.7.2` confirmed back in place.
- **Confirmed via re-analysis**: all 4 CI jobs (including the `sonarqube` scan) passed on the real push. Open vulnerabilities on `Dockerfile`/`ci.yml` dropped 9 → 4 - only the `S8544` hash-lock findings remain, exactly the ones deliberately left open above. `new_coverage` still failing as expected (36.5%, unaddressed pending a threshold decision).

## [3.23.0]

Wired up real test-coverage reporting to SonarCloud - previously it tracked 0% coverage despite 245 backend + 142 frontend tests existing, because SonarCloud Cloud's free-tier "Automatic Analysis" mode can't ingest coverage reports at all (or read `sonar-project.properties`, per the 3.15.0 finding). Moved analysis to CI-driven instead.

### Added
- **`pytest-cov`** added to `requirements.txt`; CI's `build` job now runs `pytest --cov=src --cov-report=xml`, uploading `coverage.xml` as a build artifact.
- **`@vitest/coverage-v8`** added to `web-frontend`; a new `npm run test:coverage` script and `vitest.config.js` coverage config (`v8` provider, `lcov` reporter) produce `coverage/lcov.info`, also uploaded as a CI artifact.
- **New `sonarqube` CI job** (`.github/workflows/ci.yml`): runs after `build`/`frontend-tests` succeed, downloads both coverage artifacts, and runs `SonarSource/sonarqube-scan-action@v8` with a full (non-shallow) checkout for accurate "new code" blame.
- **`sonar-project.properties`**: added `sonar.projectKey`, `sonar.organization`, `sonar.python.coverage.reportPaths`, and `sonar.javascript.lcov.reportPaths` - all inert under Automatic Analysis, all load-bearing now that analysis is CI-driven.

### Changed
- **SonarCloud project settings**: Automatic Analysis switched off (Administration → Analysis Method) - required before CI-based analysis is accepted at all; this also means `sonar.exclusions` (previously confirmed to have no effect - see 3.15.0/3.15.1) now actually takes effect for the first time.

### Verified
- Local dry run of both coverage commands: backend 54% overall (real gaps surfaced - e.g. `rmsd_calculator.py` at 6%, `session_manager.py`/`utilities.py` at 0%, all pre-existing and not addressed here); frontend 85.55% statements. Both `coverage.xml` and `lcov.info` generate correctly and are gitignored.
- 245 backend + 142 frontend tests still pass unchanged - this only adds reporting, no test behavior changed.
- **Confirmed via the actual CI-driven analysis** (all 4 jobs, including the new `sonarqube` job, passed): SonarCloud now reports real coverage (34.2% overall) for the first time ever. This also surfaced two Quality Gate conditions that were previously vacuously passing with no data: `new_coverage` (36.5% vs. an 80% default threshold - expected for a project just starting to track coverage) and `new_security_rating` (see 3.24.0 - a set of real findings in `Dockerfile`/`ci.yml` that Automatic Analysis apparently never scanned at all).

## [3.22.0]

Mechanical safe-batch cleanup for the remaining ~52 low-severity SonarQube Code Smells (none gate-blocking), same low-risk pattern as the two earlier safe-batch passes this session.

### Fixed
- **Dict/set constructor calls replaced with literals**: `dict(k=v)` → `{"k": v}`, `set([...])` → `{...}` set comprehensions across `phylo_tree.py`, `rmsd_analyzer.py`, `comparison.py`, `phylo.py`, `ligand_analyzer.py`, `ligand.py`.
- **Redundant/inefficient calls**: `sorted(list(x))` → `sorted(x)`, `list(x)[0]` → `next(iter(x))` (avoids materializing the whole iterable) in `sequence.py`, `rmsd_analyzer.py`, `analysis.py`; a for-loop calling `.add()` per item replaced with a single `.update()` call in `ligand_analyzer.py` and `sequence.py`.
- **Naming convention**: `rmsd_calculator.py`'s `L_target`/`L_orig` renamed to `l_target`/`l_orig` (Python identifier convention - the `"L_orig"` dict *key* elsewhere in the same file is untouched, since string keys aren't identifiers).
- **Structural**: merged a nested `if` into its enclosing `if` in `rmsd_calculator.py`; extracted a nested ternary into an explicit `if`/`elif`/`else` in `common.py`'s progress stepper; flattened one level of nested `forEach` into a plain `for` loop in `LigandTab.js` (was 5 levels deep); `escapeHtml.js`'s single-character regex replacements (`/&/g`, `/</g`, etc.) simplified to plain-string `replaceAll()` args, which do the same all-occurrences replacement without needing a `g`-flagged regex.
- **Duplicated literal**: `sequence.py`'s `"All Proteins (Alignment Columns)"` (repeated 3x) extracted into a module-level constant.
- **Two `# comment` false positives** re-triggering the "commented out code" heuristic on formula/shape notation (`rmsd_calculator.py`, `rmsd_analyzer.py`) and one in `notebook_template.html` (mentioning tag-like syntax) - reworded to prose, same pattern as this rule's earlier fixes this session.
- **Unused local variables** (17 sites, mostly tuple-unpacked return values in tests) renamed to `_`: `ligand_analyzer.py`, `sequence_viewer.py`, `clusters.py`, `test_mustang_runner.py`, `test_pdb_manager.py`, `test_pipeline.py`.
- **Explicitly NOT touched**: `sidebar.py`'s `list(st.session_state.keys())` (S7504) - already investigated earlier this session and confirmed genuinely necessary (the loop body deletes from the dict being iterated), not a false positive to "fix" again.

### Verified
- 245 backend + 142 frontend tests, ruff, and black all clean.
- `phylo.py` (8 of the dict-literal fixes, the highest-complexity file touched) and `sequence.py` (`_parse_range_str`, `render_sequences_tab`) both exercised live through Streamlit's `AppTest` harness with realistic fake torsion/sequence data - zero exceptions.
- The remaining touched files' specific changes (`ligand.py`'s set comprehension, `clusters.py`'s tuple-unpack, `comparison.py`'s labels dict, `common.py`'s stepper logic, `rmsd_calculator.py`'s renamed TM-score/GDT-TS parameters) verified via direct, isolated equivalence checks against the original logic - exhaustive input sweeps where applicable (the stepper's if/elif/else vs. the original nested ternary, checked across all step/current_step combinations 0-5).
- **Confirmed via re-analysis**: open Code Smells dropped 92 → 40 (every targeted issue resolved) - the only 40 remaining are the 39 pre-existing Cognitive Complexity findings and `sidebar.py`'s single deliberately-untouched `list()` call. Quality Gate still OK, 0 vulnerabilities/bugs.

## [3.21.0]

Mechanical FastAPI documentation cleanup in `src/backend/api.py` - the two largest remaining SonarQube Code Smell rules (70 issues combined, neither gate-blocking since both predate the "new code" baseline): `python:S8410` ("use Annotated for dependency injection", 40 instances) and `python:S8415` ("document this HTTPException in responses", 30 instances).

### Changed
- Every one of the 17 route handlers' `param: Type = Query(...)/Body(...)/File(...)` parameters converted to the `param: Annotated[Type, Query(...)]` style FastAPI's own docs now recommend. Pure syntax change - confirmed no parameter's actual default/validation behavior shifted (in particular, `chain_selection`'s `{}` default is never mutated in place anywhere downstream, so the Annotated style's literal-default doesn't reintroduce Python's classic mutable-default-argument bug).
- Added a `responses={...}` dict to every decorator whose handler (directly, or via `_safe_segment()`/`_get_discover_run_results()`) can raise an `HTTPException`, documenting the real status codes and reasons - visible now in `/docs`' Swagger UI instead of only discoverable by reading the handler body.

### Verified
- 245 backend tests, ruff, and black all clean.
- `app.openapi()` still generates a valid schema with the new `responses` entries correctly merged alongside FastAPI's default `200`/`422` entries.
- Live through the real running server: a full alignment run (`/api/chains` → `/api/jobs/align` → poll → `/api/history` → click-to-reload) completed with zero console errors; spot-checked a 200 (`/api/history`), a 400 (`/api/stats?session_id=../etc`), and a 404 (`/api/jobs/doesnotexist`) all still return their original bodies/status codes unchanged.
- **Confirmed via re-analysis**: both `python:S8410` and `python:S8415` dropped to 0 open issues (was 40 and 30) - including the ones attributed to `_safe_segment()`'s own `raise HTTPException`, resolved transitively once every one of its ~15 callers documented the 400 it can produce. Total open Code Smells 162 → 92; Quality Gate still OK.

## [3.20.2]

Re-analysis after 3.20.1 surfaced a new Quality Gate failure: `python:S5332` ("Using HTTP protocol is insecure") flagging `tests/test_concurrency.py`'s `base_url="http://test"`. This is a *different* rule than the `jssecurity:S8476` finding on the same literal string resolved back in 3.19.0 - that one was JS-side CSRF/SSRF reasoning about `api.js`; this is Python-side, and unlike the earlier one, it turned out to have a real fix rather than being a genuine tool limitation.

### Fixed
- **`tests/test_concurrency.py`**: `base_url="http://test"` → `"https://test"`. `httpx.ASGITransport` never makes a real network connection - requests go straight into the app in-process - so the URL scheme is never actually dereferenced. Confirmed zero behavior change; this wasn't a "mark as safe" situation, the fix was simply free.

### Verified
- All 3 concurrency tests + full 245-test suite pass unchanged, ruff/black clean.
- **Confirmed via re-analysis**: Quality Gate back to OK, 0 open vulnerabilities/bugs.

## [3.20.1]

Finished the `logging.exception()` migration from earlier this session - querying SonarCloud's API directly (`rules=python:S8572`) turned up 10 remaining `logger.error(f"...: {e}")` sites across `phylo_tree.py` (3), `rmsd_analyzer.py` (5), `report_generator.py` (1), and `sequence_viewer.py` (1) that weren't in the original ~20-file sweep.

### Fixed
- All 10 sites now use `logger.exception(...)` (auto-includes the traceback) instead of manually interpolating `str(e)`/`{e}` into the message. Dropped the now-unused `except Exception as e:` binding wherever `e` wasn't also needed elsewhere in the block (e.g. re-raised or included in a returned error string).
- `rmsd_analyzer.py`'s `calculate_residue_rmsf` had a redundant second `logger.error(traceback.format_exc())` call plus an inline `import traceback` - both removed since `logger.exception()` already captures the full traceback.

### Verified
- 245 backend tests, ruff, and black all clean.
- SonarCloud: 10 `python:S8572` issues open before this fix, confirmed via `api/issues/search?rules=python:S8572`.

## [3.20.0]

Fixed the real `/api/history` payload-bloat issue flagged as an open item in `docs/ROADMAP_V4.md`'s Phase 4 (found there: a 42MB response for just 20 runs, once each run's cached Plotly heatmap/tree figures and Discover hit/annotation payloads accumulate in its `metadata` blob). The History tab and Dashboard's recent-activity list never actually render that data - only `reloadPastRun()` needs it, and only once a specific run is clicked.

### Fixed
- **`src/backend/api.py`**: `GET /api/history` now strips `metadata.results` (the heavy blob) from every run in the page via a new `_lighten_run_for_list()` helper, keeping small fields like `run_type`/`chain_selection` intact. `GET /api/runs/{run_id}` is unchanged and still returns the full record.
- **`web-frontend/src/main.js`**: `reloadPastRun()` now detects a lightened run (no `metadata.results`) and transparently fetches the full record via `fetchRun(run.id)` before proceeding - so clicking a run in the History tab or Dashboard's recent-activity list still reloads everything (3D view, stats, figures) exactly as before. The shared-run-link path already fetched a full record first, so this is a no-op there.

### Verified
- 245 backend tests (new: `test_history_endpoint_strips_heavy_results_metadata`) + 142 frontend tests, both clean.
- Live through the real running server: ran a real alignment, confirmed `/api/history`'s response for that run shrank to ~1.8KB with `results` absent from `metadata` (only `chain_selection`/`clean_params` remained), confirmed `GET /api/runs/{id}` still returns the full record including `heatmap_fig`, then clicked the run in the live History tab and confirmed the 3D viewer canvas rendered correctly on reload with zero console errors.

## [3.19.0]

Pulled the actual data-flow trace SonarCloud recorded for the 2 remaining `api.js`/`Viewer3D.js` findings (`api/issues/search`'s `flows` field, not just the one-line message) instead of accepting them as false positives again. It showed something neither prior pass caught: the taint source is a **server response** (`fetchRun()`'s JSON), not just user-typed input - `run.pdb_ids` flows through `selectedPDBs[0]` into a later `fetchLigands()` call. The validators from 3.18.0/3.18.1 do correctly guard this, but SonarCloud's engine doesn't trust a custom function's `return id` as clearing taint, no matter how it's called - it wants the URL built through a recognized-safe construction API.

### Fixed
- **`web-frontend/src/api.js`** rewritten to build every request URL via the `URL`/`URLSearchParams` APIs (a `buildUrl(path, queryParams)` helper) instead of template-literal string concatenation - `URLSearchParams.set()` handles query encoding itself, and this is the specific construction pattern SonarSource's own compliant examples for this rule show. Validation (`assertSafeSegment`/`assertValidPdbId`) still runs first; this changes *how* the already-validated value reaches the URL, not whether it's checked.
- **`withApiKey()`** similarly rewritten to append `api_key` via `URLSearchParams` rather than manual `?`/`&` string handling.

### Verified
- 142 frontend tests, full production build, both clean.
- Live through the real running server: real alignment + every download link (PDB/FASTA/notebook/report), Ligands, History, share-link generation, and the `?shared_run=../../etc/passwd` attack scenario all behave identically to before the rewrite.
- Live with a real `ALIGNX_API_KEY` set end-to-end: built the frontend with a matching `VITE_ALIGNX_API_KEY`, confirmed a real download link carries `api_key=...` and actually authenticates (200, not 401) against the live backend.
- **Confirmed via re-analysis**: this fully resolved both remaining findings (`api.js`, `Viewer3D.js`) - down from 3 open vulnerabilities on this rule to 1. The one left (`tests/test_concurrency.py`'s `"http://test"`) has no possible code fix; it's a literal string a pattern-based rule will always match, regardless of the fact that it's httpx's own documented convention for a transport that never makes a real connection.

## [3.18.1]

Follow-up to 3.18.0: the validators were added but never actually applied - every call site did `assertSafeSegment(runId, 'runId')` and discarded the return value instead of `runId = assertSafeSegment(runId, 'runId')`, so the original (still-tainted, from static analysis's point of view) variable was what actually reached the request URL. Confirmed this was the real cause, not just a theory: SonarCloud's open vulnerability count for this rule dropped from 7 to 3 after reassigning at every call site. Remaining 3: `tests/test_concurrency.py` (no possible code fix - the literal string "http://test" will always match this rule, and it's not a real connection), `Viewer3D.js:194` (downgraded from MAJOR to MINOR), and `api.js`'s `fetchLigands` (structurally identical to `fetchInteractions`, which did clear - looks like an analyzer quirk, not a real gap). Left as-is rather than chasing further.

### Verified
- 142 frontend tests still passing, unaffected (behavior is identical either way - the validators already threw before returning on invalid input).
- SonarCloud: security rating C→B, open vulnerabilities on this rule 7→3.

## [3.18.0]

Real fix for the 6 remaining SonarCloud vulnerabilities (`jssecurity:S8476`, "client-side requests should not be vulnerable to forging attacks") in `web-frontend/src/api.js`/`Viewer3D.js` - reversed course from the earlier plan to mark these "False Positive". Researched what the rule's own remediation model actually requires: a **Validator** (confirm the value matches an expected, safe shape before it's used) - `encodeURIComponent()` is only a **Sanitizer** (escapes characters so a string doesn't break URL syntax), which is a different thing. An attacker-supplied value like `../other-endpoint` is still fully functional after percent-encoding; sanitizing it doesn't validate that it's the kind of value that should be used at all.

### Fixed
- **`api.js`**: every function that builds a request URL from a `run_id`/`job_id`/`ligand_id`/`pdb_id` now validates the value's shape first (mirroring the backend's own `_safe_segment()` regex, or `isValidPdbId()` for structure IDs) and throws before ever reaching `fetch()` if it doesn't match - not just at the 6 originally-flagged call sites, but consistently across every function in the file with the same pattern, including several Sonar didn't flag (`fetchJobStatus`, `fetchComparison`, `fetchInteractions`, `getShareLink`, `getAlignmentFastaUrl`, `getLabNotebookUrl`, `getDiscoveryReportUrl`, `getDiscoveryExportUrl`).
- **`getAlignmentReportUrl`'s `sections` param** now validated against an explicit allowlist of the 5 known report sections, rather than just percent-encoded.
- This closes a real (if narrow) gap: `main.js`'s shared-run-link handling reads `shared_run` directly from the URL query string - genuinely attacker-influenced input, since anyone can craft a link. A malformed value there previously would have been percent-encoded and sent to the backend as-is (which would reject it, but only after the request was made); it's now rejected client-side before any network call happens.

### Verified
- 142 frontend tests (20 new), including parameterized tests proving `fetchRun`/`fetchSequence`/`fetchJobStatus`/`fetchLigands`/`getAlignmentPdbUrl`/`getShareLink` all reject malformed IDs (`../admin`, `a/b`, path traversal attempts, empty strings) without ever calling `fetch`.
- Live through the real running server: normal usage (real alignment, PDF/FASTA/notebook downloads, ligands, history, share-link generation) all still work; separately opened the app with `?shared_run=../../etc/passwd` and confirmed it's now rejected client-side with a clean error banner instead of reaching the network.

## [3.17.1]

Resolves one of the two remaining SonarCloud Security Hotspots (`mustang_runner.py`'s `os.chmod` calls).

### Fixed
- **Compiled Mustang binary permissions tightened from `0o755` to `0o700`** in both `_locate_compiled_binary()` and `_verify_native_linux_binary()`. `0o755` was never actually exploitable (world-*readable*/executable, not world-*writable*), but there was also no reason to grant it: the same single non-root user that compiles and `chmod`s the binary (see the Dockerfile's `appuser`) is also the only one that ever executes it. Removed group/other access entirely rather than just asserting the previous value was safe.

### Verified
- 2 new regression tests asserting the exact permission value at both call sites (244 backend tests total).
- Live: built and ran the actual Docker image with this change, confirmed the app still starts and detects Mustang correctly.

## [3.17.0]

Second half of the SonarCloud Code Smell cleanup - the frontend/JS side of the "safe batch" (3.16.0 was backend/Python). Same scope rule: mechanical, low-risk only; `AnalyticsTab.js`'s and `LigandTab.js`'s Cognitive Complexity/nesting-depth findings are deferred.

### Fixed
- **Optional chaining**: ~20 `x && x.y` guards across `AnalyticsTab.js`, `ClustersTab.js`, `DashboardTab.js`, `HistoryPanel.js`, `OverviewTab.js`, `TopBar.js`, `Viewer3D.js`, `main.js` rewritten as `x?.y`.
- **Empty/unused-binding `catch` blocks**: `catch(e) {}` / `catch(e) { /* never reads e */ }` → `catch {}` (or `catch { ... }` with a comment) in `DashboardTab.js`, `HistoryPanel.js`, `main.js` - these were always intentional silent fallbacks, just written in a way Sonar flags as "handle it or don't catch it."
- **Class field declarations**: constructors that only assigned static initial values (`this.x = null`, etc., no constructor params) rewritten as class fields - `AnalyticsTab.js`, `ClustersTab.js`, `ComparisonTab.js`, `DiscoverTab.js`, `SequenceTab.js`, `Viewer3D.js`.
- **`.dataset` over `getAttribute('data-*')`**: `AnalyticsTab.js`, `TopBar.js`.
- **`Number.parseFloat`/`parseInt`/`isNaN`** over the bare globals: `ClustersTab.js`, `DiscoverTab.js`, `LigandTab.js`, `SequenceTab.js`, `HistoryPanel.js`.
- **`String.fromCodePoint()`** over `String.fromCharCode()`: `Viewer3D.js`.
- **`String#replaceAll()`** over `.replace()` with a global regex: `escapeHtml.js`.
- **Nested ternary** in `DiscoverTab.js`'s consensus-paragraph logic extracted into an if/else chain.
- **Generic `.length`/`toBe(N)` assertions → `toHaveLength(N)`**: 11 instances across `ComparisonTab.test.js`, `HistoryPanel.test.js`, `LigandTab.test.js`, `OverviewTab.test.js`, `SequenceTab.test.js`.

### Verified
- Full suite (122 frontend tests) + production build, both clean.
- Live smoke test through the real running server: batch-added structures (exercises the optional-chain/Number.parseFloat code paths just changed), ran a real 4-structure alignment, and visited every touched tab (Analytics, Clusters, Ligands, Dashboard, History, Discover) - zero console errors.

## [3.16.0]

First half of a SonarCloud Code Smell (Maintainability) cleanup pass - the "safe batch" (mechanical, low-risk fixes only; the 9 Cognitive Complexity refactors and the ~65-instance FastAPI `Annotated`/response-docs convention migration in `api.py` are deliberately deferred to a separate pass). Backend/Python half only - frontend JS smells are next.

### Fixed
- **`logger.error(f"...: {e}")` → `logger.exception(...)`** across ~20 backend files (62 call sites) - `logging.exception()` automatically includes the full traceback, which the old pattern only sometimes did via a separate, easily-forgotten `traceback.format_exc()` call (removed two now-redundant duplicates of that in `notebook_exporter.py`/`rmsd_calculator.py`). Cleaned up the resulting unused `as e` bindings via `ruff --fix`.
- **Regex character classes**: `[0-9]` → `\d` (11 instances across `annotation_aggregator.py`, `pdb_manager.py`, `api.js`); a genuine duplicate in `_AFDB_TARGET_PATTERN`'s character class, since `re.IGNORECASE` already made the explicit `a-z` half of `[A-Za-z0-9]` redundant.
- **Duplicated string literals → constants**: `"application/json"` (7x, `annotation_aggregator.py`) and `"Neon Pro"` (4x, `structure_viewer.py`).
- Unused local variables (`c3`, `col_reset`, many `msg`s in test files) renamed to `_`.
- `scripts/provision_foldseek_db.sh`: `[` → `[[` for its conditional test.
- Two "commented out code" findings turned out to be false positives (a trailing comment with arithmetic in it, and a comment mentioning `<script>` tags) - reworded rather than "fixed" to stop tripping the heuristic. `tests/test_pdb_manager.py` had two genuinely commented-out lines removed for real.
- `coordinator.py`: `list(sequences.values())[0]` → `next(iter(...))` (avoids materializing the list just to take the first item). `annotation_aggregator.py`: `set(gen_expr)` → set comprehension.
- `structure_viewer.py`: renamed camelCase Python locals (`neonColors`/`spectralColors`) to snake_case in `render_synced_grid` - left the same-named JS variables inside `render_3d_structure`'s embedded `<script>` template untouched (those are real JavaScript, not Python, and were never flagged).
- Two `sidebar.py`/`sequence.py` "unnecessary `list()`" findings turned out to need opposite fixes: `sidebar.py`'s loop deletes from the dict it's iterating (so the defensive copy is required, kept with an explanatory comment); `sequence.py`'s loop only reassigns existing keys (so the copy was genuinely unneeded, removed).
- `test_config_validation.py`: 3 `pytest.raises` blocks had `load_config(str(config_file))` inside the block - `str(config_file)` itself counts as a second "possibly throwing" call to Sonar's analysis. Moved the conversion outside the block.
- `test_annotation_aggregator.py`: removed a stray `async` from a mock side effect with no `await` in it.

### Verified
Full suite (242 backend tests) + `ruff`/`black` clean after every batch, not just at the end.

## [3.15.2]

Follow-up after the `sonar.exclusions` fix actually took effect (see 3.15.1): with `static/**`/`.agents/**` noise gone, `new_reliability_rating` immediately passed. `new_security_rating` was still failing on one real CRITICAL finding underneath the noise.

### Fixed
- `mustang_runner.py`'s verified TLS context (added in 3.15.0) didn't explicitly pin a minimum TLS version - added `context.minimum_version = ssl.TLSVersion.TLSv1_2` rather than relying only on `create_default_context()`'s own defaults.

## [3.15.1]

Closes the one gap 3.15.0 flagged as unfixable from here: `sonar.exclusions` (`static/**`, `.agents/**`, etc.) is now set directly in SonarCloud's project settings (Administration → General Settings → Analysis Scope → Source File Exclusions), confirmed live via `api/settings/values` returning the real value rather than empty. Automatic Analysis mode never reads `sonar-project.properties`, so this had to happen in the UI, not a commit - this entry exists just to mark the loop as closed. Next analysis (triggered by this push) should show `static/assets/*.js`'s ~325 noise issues and 100% of the previously-open Bugs disappear from "new code" findings entirely.

## [3.15.0]

A SonarCloud pass, fetched directly from its public API (`sonarcloud.io/api/...` - no token needed since this project is public) rather than a pasted issue list. Found that 100% of currently-open Bugs and roughly half of all "new code" issues are in `static/assets/*.js` (the built bundle) and `.agents/**` - both already listed in `sonar-project.properties`, but that file isn't being read because analysis runs in SonarCloud's Automatic Analysis mode, which doesn't consult it. **Not fixed here** - closing that gap needs either a SonarCloud project-settings change or switching to CI-driven analysis, both of which need repo-admin access this session doesn't have. Everything below is what's real, outside that noise.

### Fixed
- **`web-frontend/src/api.js`**: every URL-building function now `encodeURIComponent()`s its interpolated ID params (`jobId`, `pdbId`, `runId`, `ligandId`, etc.) - previously inconsistent, some already did, several didn't.
- **Two BLOCKER-severity "arbitrary code execution" findings** (`DashboardTab.js`, `HistoryPanel.js`): both were already `escapeHtml()`-protected, but SonarCloud's static analyzer can't verify a custom sanitizer, so it still flags any `innerHTML` assignment with interpolated data as a sink. Refactored to a static-only HTML shell with all dynamic values assigned via `textContent` instead - stronger than escaping (no markup parsing happens on the dynamic values at all) and satisfies the rule for real instead of needing a suppression.
- **`mustang_runner.py`'s source-tarball download disabled SSL certificate *and* hostname verification** entirely (a documented workaround for a past Streamlit Cloud issue) - this downloads code that gets compiled and executed as a subprocess, so an unverified connection is a real MITM-to-RCE path. Switched to a fully verified TLS context using `certifi`'s CA bundle explicitly, which fixes the likely actual root cause (a stale/incomplete system CA store) without disabling verification.
- **`MUSTANG_URL` was plain `http://`** - switched to `https://` (confirmed the host serves it directly, no redirect needed).
- **Log injection** (`database.py`, `ligand_analyzer.py`, `result_manager.py`): user-controlled `run_id`/`session_id`/`ligand_id` values were interpolated directly into log messages - a value containing newlines could forge fake log lines. Added `sanitize_for_log()` (`src/utils/logger.py`) and applied it at every site carrying one of these values, not just the ones SonarCloud happened to flag in the same files.
- **Notebook export used `eval()`** to run the embedded 3Dmol.js library source. Not attacker-controlled (the source is a bundled local file, not user input), but replaced with the standard script-element-injection pattern anyway - same effect, no `eval()`, and it's what browsers actually expect for running injected script content.
- **Bootstrap/jQuery CDN tags in the notebook template had no Subresource Integrity check** - added `integrity`/`crossorigin` attributes with SHA-384 hashes computed directly from the exact files those URLs serve (not guessed/copied from memory).
- **Docker container ran as root** - added a non-root `appuser`, `chown`'d `/app` to it. Verified live: a real container built from this exact Dockerfile runs as `appuser` (not root) and still completes a real alignment job successfully (Mustang execution, file writes under `/app/data` and `/app/results` all still work).

### Verified
- 242 backend tests (3 new, covering `sanitize_for_log`) + 122 frontend tests, `ruff`/`black` clean.
- Live: built and ran the actual Dockerfile, confirmed non-root (`whoami` → `appuser`), ran a real 2-structure alignment end-to-end inside it.
- Live: downloaded a real generated notebook from that same container and opened it in a real browser - 3Dmol.js, jQuery, and Bootstrap all loaded correctly (confirming the SRI hashes are exactly right and the eval() replacement behaves identically), zero console errors.

## [3.14.0]

`docs/ROADMAP_V4.md` Phase 4 — shareable run links. This completes the v4 roadmap (Phases 1-4 all shipped).

### Added
- **`GET /api/runs/{run_id}`**: fetch a single run's raw record by ID, with no ownership check (matching every other run_id-keyed read endpoint) — the missing piece since `/api/history` only returns unscoped paginated lists, not a direct single-run lookup.
- **Shareable run links**: `getShareLink()` builds a `/?shared_run={id}` URL (carrying `api_key` too when one's configured); `main.js` detects it on load and feeds the fetched run into the existing `reloadPastRun()` path, with a "Viewing a shared run — read-only" banner. `HistoryPanel.js` gained a "Share" button per run that copies the link.
- Decided (not an accident): shared links are **world-readable by anyone who has them**, not gated by an explicit per-run opt-in — Phase 1's hardened run IDs make guessing impractical, and an opt-in toggle would have been the app's first granular access-control feature, disproportionate to what was asked.

### Verified
- 3 new backend tests + 7 new frontend tests. Full suite: 239 backend + 122 frontend.
- Live across two fully separate Playwright browser contexts: one ran a real alignment and copied its share link from the clipboard; a second, completely fresh context opened that link cold and correctly showed the same real RMSD/sequence/3D data with the read-only banner — zero console errors in either context.

### Found (not fixed, out of scope for this change)
- `/api/history` returned a **42MB response for 20 runs** after this session's heavy test-run accumulation — each run's cached Plotly figures live directly in its `metadata` blob. Worth a real fix (paginate list metadata separately from heavy per-run figure data) before real multi-session usage; not touched here since it's unrelated to run IDs, uploads, or sharing.

## [3.13.0]

`docs/ROADMAP_V4.md` Phase 3 — custom structure upload.

### Added
- **`POST /api/upload`**: upload a `.pdb`/`.ent`/`.cif` file directly instead of only fetching one of the four public databases by ID — closes a real capability gap where Streamlit already had `PDBManager.save_uploaded_file()` but the SPA had no way to reach it. Returns the same `{"chains": {...}}` shape `/api/chains` does.
- **Real content validation**: `PDBManager.save_uploaded_bytes()` actually parses the upload with Bio.PDB and requires at least one chain before accepting it, deleting the file and returning a clear error otherwise — a `.pdb`-named file that isn't a real structure fails here, not later inside Mustang. Also enforces `pdb.max_file_size_mb`, previously only checked for downloads.
- **Uploads survive into a real alignment run**: the saved file keeps its real extension (`.cif` preserved, not forced to `.pdb`), and `download_pdb()`'s cache-hit check now looks for either extension — so a later `/api/jobs/align` run finds the already-saved upload instead of trying to fetch a remote source it never came from.
- `OverviewTab.js` gained an "Upload a structure file" control; uploaded structures get an "Uploaded" source badge and show the original filename.

### Verified
- 9 new backend tests (content validation, oversized rejection, extension preservation, cache-hit fallback, endpoint auth/validation) + 6 new frontend tests. Full suite: 236 backend + 115 frontend.
- Live through the real running server: uploaded a genuine small PDB file (1CRN), then ran a real 3-structure alignment (2 fetched + the upload) that completed successfully end-to-end — real RMSD, 3D superposition, sequence view, all export formats generated.

## [3.12.0]

`docs/ROADMAP_V4.md` Phase 2 — batch structure input.

### Added
- **Paste multiple IDs**: `OverviewTab.js` gained a "Paste multiple IDs" toggle revealing a textarea that accepts a comma/space/newline-separated list of PDB IDs or accessions, parsed and added in one action instead of one at a time. Backend needed no changes — `/api/chains` already accepted a list.
- **`core.max_proteins` is now actually enforced**: the config field existed (default 20) but was never read anywhere in the backend or frontend. `App.addManyPDBs()` now caps a batch add at the same limit, since pasting a large list is the first realistic way to blow past it in one action.

### Verified
- 5 new frontend tests (toggle visibility, parsing/dedup, invalid-token reporting, cap enforcement, textarea-clear behavior). Full suite: 227 backend + 110 frontend.
- Live through the real running server via Playwright: pasted a mixed batch (2 new valid IDs, 1 duplicate, 1 invalid token) into a workspace that already had 2 structures — correct partial-failure feedback, real chain metadata resolved for all 4 resulting structures, zero browser console errors.

## [3.11.0]

First phase of `docs/ROADMAP_V4.md` — closes a real information-disclosure gap found while scoping the "shareable run links" feature, independent of whether that feature ships.

### Fixed
- **Guessable run IDs**: Compare/Discover run IDs were a bare `int(timestamp())` (`run_1783414603`) — one-second resolution, trivially enumerable. Read endpoints (`/api/report`, `/api/sequence`, `/api/notebook`, etc.) look a run up by ID alone with no ownership check, so anyone who could reach the server could script through nearby integers and pull other users' reports. Fixed by appending a 16-hex-char random suffix (`generate_run_id()`, `src/utils/run_id.py`) — also deduplicates what was near-identical logic previously copy-pasted between `coordinator.py` and `discovery_coordinator.py`.

### Verified
- `tests/test_run_id.py`: format, path-segment safety, no collisions across 20 calls at the identical second.
- Full suite (227 tests), `ruff`/`black` clean.
- Live through the real running server: a real 4RLT+3UG9 alignment produced `run_1783414603_2b797f99f0bee74f`, not the old guessable format.

## [3.10.0]

A final documentation/consistency pass before calling the project production-ready - a fresh audit (not relying on earlier-session notes) plus a real Docker-container smoke test.

### Fixed
- **`FastAPI(version="1.0.0")` was hardcoded** and never updated since the API's very first commit - visible on `/docs` and `/openapi.json`, silently out of sync with every release since. Now reads `config.yaml`'s `app.version`, so it can't drift again.
- **Stale test counts** in `README.md` (172/91) and `docs/testing/VERIFICATION.md` (210/99) - both predated the 3.8.0/3.9.0 test additions. Updated to the actual current 223/105.
- **`docs/deployment/DEPLOYMENT.md`'s Streamlit Cloud instructions still said branch `main`** - stale since the 3.6.0 branch split, which made `streamlit-stable` the actual deploy target specifically so `main` could keep evolving without risk to the live app. Rewrote the whole section: deploy from `streamlit-stable`, and cherry-pick specific commits there rather than merging `main` wholesale, which is exactly the coupling the branch split exists to avoid.

### Verified
- Fresh full-suite run (223 backend + 105 frontend), `ruff`/`black`/`pip-audit`/`npm audit` all clean.
- Built the actual production `Dockerfile` from scratch and ran it for real: `/health`, the SPA root, and a live `/api/chains` call against a real PDB ID (RCSB download + chain analysis) all worked inside the container. Separately verified the `/results` auth gate inside a fresh container with `ALIGNX_API_KEY` set - `401` with no key, `404` (past auth, file just doesn't exist) with the correct key.
- Confirmed via `git log`/diff that the stale-but-abandoned `feat/v2.2-improvements` branch (kept during the earlier branch cleanup pending this check) has nothing left to recover - every fix and feature in its 2 commits (ReDoS-safe RMSD parsing, sequence identity calculation, `pdb_manager.py` null-safety, a Streamlit UI phase) has since been independently reimplemented on `main`, in more advanced form in every case.

## [3.9.0]

SonarQube Cloud's Quality Gate also failed on "Security Rating on New Code" (4 Blocker-severity vulnerabilities). Fixed for real.

### Fixed
- **Path traversal in `PDBManager`**: `session_id` (an attacker-controlled query param at the API layer) was concatenated directly into a filesystem path with no validation of its own. Every current caller already validates it upstream before construction, so this wasn't reachable through a live code path today - but `PDBManager` itself had zero defense, making it one forgotten upstream check away from writing files outside `data/raw`/`data/cleaned`. Added an independent `^[A-Za-z0-9_-]+$` check directly in `__init__` (raises `ValueError`), so the class no longer silently depends on every future caller remembering to pre-validate.
- **Reflected/stored XSS in `DashboardTab.js` and `HistoryPanel.js`**: both interpolated `run.id`, `pdb_ids`, `run.status`, and timestamps directly into an `innerHTML` template with no escaping. `pdb_ids` traces back to user input at job-submission time - relying on upstream validation always holding is the same class of assumption as the path traversal above. Added a small `escapeHtml()` utility (`web-frontend/src/escapeHtml.js`) and applied it to every interpolated value in both components' run-list rendering.

### Verified
- 223 backend + 105 frontend tests pass, including new regression tests: `PDBManager` rejects `../../etc`, `a/b`, `..`, and similar payloads with a clean `ValueError`; both `DashboardTab`/`HistoryPanel` render a `<script>`/`<img onerror>` payload as literal escaped text with no `<script>`/`<img>` element actually created in the DOM.

## [3.8.0]

SonarQube Cloud's Quality Gate failed on "Reliability Rating on New Code" (20 flagged issues). All fixed for real, not suppressed.

### Fixed
- **A genuine deadlock risk, not just a lint nitpick**: both rate limiters (`AnnotationAggregator`'s STRING limiter, `FoldseekClient`'s) called `time.sleep()` while holding a `threading.Lock` inside an `async def`. `aggregate_for_hits()` runs multiple neighbors' annotation fetches concurrently via `asyncio.gather()` on the *same* event loop - naively swapping in `await asyncio.sleep()` without moving it outside the lock would have introduced a real, reproducible deadlock the moment 2+ neighbors needed the STRING limiter in the same job (a sibling gathered coroutine's synchronous, blocking lock-acquire freezes the very event loop that would've advanced the first caller's sleep timer). Redesigned both: the lock now only ever guards the synchronous slot-reservation math; the actual delay is `await`ed outside it. Still correctly serializes successive callers by at least `min_interval`, verified under both same-event-loop concurrency (`asyncio.gather`) and cross-thread concurrency (mirroring the existing `FoldseekClient` regression test).
- **Two `asyncio.create_task()` calls with no stored reference** (`/api/jobs/align`, `/api/jobs/discover` submission) - the event loop only holds a *weak* reference to a bare `create_task()` result, so with nothing else keeping it alive, a submitted job could in principle be garbage-collected mid-execution (a real, documented asyncio footgun, not a style preference). Added a small `_spawn_background_task()` helper that keeps a strong reference in a module-level set until the task completes.
- **Synchronous `open()`/`write()` inside an async function** (`PDBManager`'s download-save path) - blocked the whole event loop for the disk write. Moved to `asyncio.to_thread()`, matching the pattern already used elsewhere in this codebase for blocking work (Mustang/Foldseek subprocess calls).
- **9 floating-point `==` comparisons** across `sequence_viewer.py` (the one in real production code - conservation-score fully-conserved check, changed to `>=`) and 8 test assertions (changed to `pytest.approx()`).
- **CI/tooling gaps that let all of the above land unreviewed**: added `pyproject.toml`/`sonar-project.properties` excluding build artifacts (`static/`, `web-frontend/dist/`) and vendored third-party code (`.agents/skills/`) from static analysis - SonarQube was flagging a minified JS bundle that isn't source and gets overwritten on every build anyway.
- `web-frontend/src/style.css`: `@import "tailwindcss"` now precedes `@config` (CSS spec requires `@import` to be the first rule in a stylesheet) - confirmed via a byte-identical rebuild that Tailwind's Vite plugin doesn't actually require the reverse order that an earlier migration assumed.

## [3.7.0]

### Fixed
- **CI's `black --check .` and `ruff check .` gates were both silently broken.** `black`/`ruff` were pinned as open-ended lower bounds (`black>=23.9.0`, `ruff>=0.1.0`), so CI always installs whatever's newest at run time - and black in particular deliberately changes its "stable" formatting style over time, so the codebase had drifted out of sync with the installed version (~19 real project files needed reformatting, none of it a logic change). Separately, neither tool excluded `.agents/skills/` (vendored third-party skill scripts, not this project's code), so both gates were also failing on 2 lint issues that were never ours to fix. Reformatted the 19 real files with the currently-pinned `black`, excluded `.agents` from both tools (new `pyproject.toml` for black, extended `ruff.toml`'s existing exclude list), and pinned both `black`/`ruff` to exact versions in `requirements.txt` so this can't silently drift again.
- Verified every CI job green locally end-to-end: `ruff check .`, `black --check .`, `pip-audit`, `pytest` (214 tests), `npm audit --audit-level=high`, `npm test` (99 tests), `npm run build`, and a full `docker build` + `/health` smoke test.

## [3.6.0]

### Fixed
- **Config validation could crash Streamlit over a Discover-only mistake**: `load_config()` validates the entire `config.yaml` through one Pydantic model shared by every caller, Streamlit's `app.py`/`pages/` included - but Streamlit never reads the `foldseek:`/`annotation:`/`cache:` sections at all. A bad value in any of those (e.g. a future Discover-driven schema tightening, or a typo) would `SystemExit(1)` the whole config load, taking Streamlit down over a section it doesn't use. `PipelineConfig` now validates those three sections independently: an invalid one logs a warning and falls back to that section's own defaults instead of failing the whole config. Every other section (`app`, `mustang`, `pdb`, etc.) still hard-fails as before, since both interfaces genuinely depend on those.
- Also relevant now that `main` (active Discover/SPA development) and `streamlit-stable` (frozen at the currently-deployed commit, now what Streamlit Cloud actually deploys from) are separate branches - this removes one more way work on `main` could have broken the live app even before the branch split, and closes it for `streamlit-stable` too since `config_models.py` is Streamlit-only-adjacent, not Discover-exclusive.

## [3.5.0]

A first real security/ops hardening pass, prompted by a codebase survey rather than a specific incident: fix a real auth gap, add CI coverage that was previously manual/ad hoc, verify concurrent-load behavior for real, and write down what's been checked vs. still open.

### Fixed
- **Real auth bypass**: `/results` and `/raw` (serving generated reports/notebooks and downloaded structure files directly off disk) sat outside the `require_api_key` middleware's `/api/` prefix check entirely, so every file under them was open to anyone who could reach the server even with `ALIGNX_API_KEY` configured for everything else - session/run folder names aren't secrets, so this was a real information-disclosure gap, not theoretical. Fixed on the backend (middleware now also covers `/results/` and `/raw/`) and the frontend (`getAlignmentPdbUrl`/`getAlignmentFastaUrl` now carry the API key as a query param, matching every other download link).
- **A real performance bug found by load-testing**: `HistoryDatabase.__init__` re-ran its full schema migration (`CREATE TABLE`/`ALTER TABLE`) on every single construction - and both `DiscoveryCoordinator` and `AnalysisCoordinator` construct a fresh `HistoryDatabase()` per job - which measurably serialized concurrent job startup once `run_history.db` grows large (a handful of concurrent submissions took minutes instead of seconds against a real ~170MB dev database). Fixed by memoizing "already migrated" per `db_path` for the process lifetime, plus raising SQLite's busy-timeout from the 5s default to 30s across the board.

### Added
- **CI now builds and smoke-tests the actual production Docker image** on every push/PR (previously manual/ad hoc, per this file's own past "Verified" entries) - build, run, poll `/health`, tear down.
- **CI now scans for known dependency vulnerabilities**: `pip-audit` against `requirements.txt`, `npm audit --audit-level=high` for the frontend. Both were clean when added.
- **`tests/test_concurrency.py`**: real concurrency tests (httpx `AsyncClient` + `ASGITransport`, not just sequential `TestClient` calls) verifying the job-submission rate limiter holds exactly at its limit under a genuine concurrent burst, partitions independently per client, and that many concurrent Discover jobs stay individually correct (no cross-job data corruption) - this is what surfaced the `HistoryDatabase` bug above.
- **`SECURITY.md`**: vulnerability reporting process, an honest list of what's actually been checked (auth, path traversal, SQL/command injection, dependency scanning, rate limiting) vs. known limitations (no independent audit, in-memory job state doesn't survive multiple worker processes, CORS defaults wide open if `ALIGNX_CORS_ORIGINS` is forgotten).
- **`docs/deployment/DEPLOYMENT.md`** gained a "Known Limitation: Single-Process Job State" section - `alignment_jobs`/`discovery_jobs`/the rate limiter are in-memory dicts, verified correct for a single worker process, explicitly documented as broken across multiple workers/replicas until job state is externalized.

## [3.4.0]

### Added
- **`gmgcl_id` annotation resolution**: the last remaining unresolvable default-eligible Foldseek database now resolves too, just not via UniProt. Live-probing GMGC's own API (`gmgc.embl.de/api_help.cgi`) showed a gmgcl_id target's real gene ID (everything before the `_trun_{n}[.pdb]` suffix Foldseek/PDB-export bookkeeping appends) resolves directly to Pfam/eggNOG annotation via `/unigene/{id}/features` - no UniProt accession involved at all. `fetch_gmgc_features()` queries this and feeds any Pfam domain hits into the same domain-aggregation pipeline InterPro domains use. Only `mgnify_esm30` remains unresolved, and that's expected (metagenomic "dark matter" sequences), not a gap.
- The Discover tab's database picker now marks only `mgnify_esm30` as non-annotatable (previously also marked `gmgcl_id`); its attribution footer now credits STRING, Reactome, PDBe SIFTS, and GMGC alongside Foldseek/InterPro/QuickGO.
- **`bash scripts/provision_foldseek_db.sh`**: wraps Foldseek's own `foldseek databases` command with the exact `config.yaml` wiring needed afterward, for whoever provisions a real production-scale self-hosted database (deferred in `docs/ROADMAP_V3.md` §7 as a deployment decision, not a code gap). Documents realistic size tradeoffs across CATH50/PDB/AFDB50/full-AFDB and a known upstream bug where `foldseek databases BFMD` doesn't currently work.

### Verified
- Live end-to-end against 1CRN: `gmgcl_id` alone now resolves 12/12 candidates and annotates 5/12 with real Pfam domains (`Phage_portal`, `Phage_Mu_F`, etc.) via GMGC's own API - previously 0/0.
- Ran the new provisioning script for real: downloaded (~970MB) and built a complete CATH50 database (~1.9GB extracted, not a toy subset), then pointed `foldseek.local.database_dir` at it and confirmed a real 1CRN Discover query against it correctly found 1CRN's own CATH domain entry (prob 1.0) plus related structures - the first fully real (not hand-built) self-hosted database exercised end-to-end in this project.

## [3.3.0]

### Added
- **CATH and BFVD/BFMD annotation resolution**: three of the four Foldseek databases the annotation pipeline couldn't resolve to a UniProt accession are now resolvable. Live-probing each database's actual target ID format (rather than assuming from documentation) showed `cath50` hits are a 7-character CATH domain ID - 4-char PDB code + 1-char chain + 2-digit domain number - i.e. the same (pdb_id, chain) pair pdb100 hits carry, just differently formatted, so it resolves through the identical SIFTS lookup (`extract_cath_pdb_chain()`). `bfmd` and `BFVD` hits embed a UniProt accession directly as a delimited token in the target string (e.g. `LevyLab_Q8U2A3_V1_4_relaxed_B`), extractable for free via UniProt's own accession regex (`extract_embedded_uniprot_accession()`), no lookup needed.
- The Discover tab's database picker now marks only `mgnify_esm30` and `gmgcl_id` as non-annotatable (previously marked all 5 non-default databases); `gmgcl_id`'s target IDs (`GMGC10.211_012_347...`) genuinely have no embedded accession or free ID-mapping API, and `mgnify_esm30` (MGYP-accession "dark matter" sequences) is expected to often lack any existing annotation at all - both remain the one open item in `docs/ROADMAP_V3.md` §7.

### Verified
- Live end-to-end against 1CRN: `cath50` alone now resolves 20/20 candidates and correctly annotates 10/10 neighbors as Thionin family (previously 0/0 before this fix). `BFVD` alone resolves 20/20 candidates to real accessions (annotation count stays low only because InterPro/QuickGO have sparse curated coverage of viral proteins, not because resolution failed).
- Re-verified the self-hosted Foldseek backend (`foldseek.backend: local`) end-to-end from a clean slate: downloaded the official Foldseek static binary, built a fresh 3-structure test database (2LYZ/3LYZ/1CRN), and confirmed `DiscoveryCoordinator` correctly discriminates real structural similarity through it - a 2LYZ query hit 2LYZ/3LYZ (both lysozyme, prob 1.0) and correctly scored 1CRN (an unrelated fold) at prob 0.0, not just returning every file in the target directory. Provisioning an actual production-scale database remains the one deferred piece - see `docs/ROADMAP_V3.md` §7.

## [3.2.0]

### Added
- **Foldseek database selection UX**: the Discover tab's request pipeline (`FoldseekClient`, `DiscoveryCoordinator`, `POST /api/jobs/discover`) already supported searching an arbitrary subset of Foldseek's 9 databases, but there was no UI to choose one - every search silently used the `pdb100`+`afdb50` default. Added a checkbox picker covering all 9 databases (defaulting to the same two as before), with the 5 that don't yet resolve to functional annotations (`mgnify_esm30`, `cath50`, `BFVD`, `gmgcl_id`, `bfmd`) marked so it's clear upfront they'll only return structural hits. Reopening a past run from History re-checks the boxes to match what that run actually searched. Closes the corresponding open question in `docs/ROADMAP_V3.md` §7.

### Verified
- Live end-to-end: a real Discover job restricted to `pdb100` only (excluding the default `afdb50`) round-tripped correctly through the public Foldseek API, confirmed via `databases_searched` in the completed result.

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
