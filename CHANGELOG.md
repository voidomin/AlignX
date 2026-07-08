# Changelog

All notable changes to StructScope (formerly AlignX) are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

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
