# StructScope v4: Bring Your Own Structure, Bulk Input, Shareable Runs

This document is the working design/roadmap for the next feature set on the SPA. It
captures *why*, *what's changing*, and *what's required* to build it, grounded in the
actual current code (file/line references throughout) rather than a generic wishlist.
Nothing here is implemented yet — this is the plan to review before writing code.

## 1. Problem statement

Three real, concrete gaps exist in the SPA today, found by tracing the actual add-structure
and result-sharing flows rather than guessing:

1. **No custom structure upload.** The SPA's only way to add a structure is typing an ID
   that resolves to one of four public databases (`PDBManager.detect_source()`,
   `src/backend/pdb_manager.py:78-92`). Anyone with an unpublished structure, a private
   AlphaFold run, or a structure from a database not yet supported has no way in. Streamlit
   already has half of this: `PDBManager.save_uploaded_file()` (`pdb_manager.py:116-143`)
   saves an uploaded file to `raw_dir`, but it's only ever called from Streamlit's file
   uploader widget — no FastAPI endpoint calls it. The SPA is behind its own older sibling.
2. **No bulk input.** `OverviewTab.js`'s add-structure control is a single `<input
   type="text">` (`web-frontend/src/components/OverviewTab.js:41`) — one ID, one click, one
   at a time. Building a 10+ structure alignment today means 10+ manual round trips.
   Notably, the backend side of this is *already* fine: `/api/chains`
   (`src/backend/api.py:250`) already accepts a list of `pdb_ids` and validates each one
   (`api.py:260`) — the one-at-a-time constraint is purely a frontend UI limitation.
3. **No shareable run links, and the run-ID scheme can't safely support them yet.**
   Read endpoints like `/api/report` (`api.py:967`) look a run up by `run_id` alone
   (`history_db.get_run(run_id)`, `api.py:990`) with **no check that the requester's
   `session_id` matches the run's owner** — so in one sense, sharing already works: hand
   someone a `run_id` and they can pull the report today. The actual gap is that `run_id`
   is not a safe thing to hand out or leave guessable: Compare-mode runs are named
   `f"run_{int(now.timestamp())}"` and Discover runs `f"discover_{int(now.timestamp())}"`
   (`src/backend/coordinator.py:116`, `src/backend/discovery_coordinator.py:112`) — a
   **second-resolution Unix timestamp**, not a random token. Anyone can enumerate nearby
   integers and pull other users' runs, whether or not "sharing" ever ships as a feature.
   This is worth fixing on its own, and it's also the prerequisite for shipping sharing
   as an intentional, safe feature rather than an accidental side effect of weak IDs.

## 2. Vision

Same principle as the v3 Discover work: extend what StructScope can take in and what it
can hand back out, without touching the core Mustang/RMSD pipeline underneath. After this:

- A user can analyze a structure **nobody else has a public ID for**.
- A user can start a **10-structure alignment as easily as a 2-structure one**.
- A user can **hand a colleague a link** to a specific completed run and have it open
  read-only, without the colleague needing the original session or an account — and
  without that also meaning *any* run is guessable by a stranger.

## 3. Feature specs

### 3.1 Custom structure upload

- New endpoint `POST /api/upload` (multipart `UploadFile`), session-scoped like every
  other write path. Wraps `PDBManager.save_uploaded_file()` — that method already exists
  and already writes into the right session-namespaced `raw_dir`
  (`pdb_manager.py:66-76`); it just needs an HTTP entry point and validation currently
  only applied to downloads (`pdb.max_file_size_mb` from `config.yaml`, checked for
  fetched files but not today's Streamlit upload path either — worth closing for both).
- Uploaded structures need a stable synthetic ID (e.g. `UPLOAD-{short-hash}`) so they can
  flow through the *same* downstream code every fetched ID already uses — chain listing,
  cleaning/filtering (`filtering.*` in `config.yaml`), and the alignment job itself
  — without `PDBManager`/`MustangRunner` needing to know a structure didn't come from a
  URL.
- Frontend: an "Upload structure" affordance next to `OverviewTab.js`'s existing add-ID
  input (drag-drop or file picker), accepting `.pdb`/`.cif`, showing the same
  source/metadata line other structures get (source badge: "Uploaded").
- Validate file *content* server-side (parses as a structure with at least one chain),
  not just extension — a `.pdb`-named text file that isn't a structure should fail
  clearly, not reach Mustang and produce a confusing downstream error.

### 3.2 Batch ID input

- Frontend-only for the common case: replace/extend the single input with a mode that
  accepts a newline/comma-separated paste of IDs, parses it client-side, and calls the
  existing `/api/chains` (already list-accepting) once with the full batch instead of
  once per ID.
- CSV/FASTA-header upload (extract IDs from a header line like `>4RLT_A`) is a
  reasonable fast-follow once plain paste-a-list ships, not a blocker for it.
- Surface partial failure clearly: if 8 of 10 pasted IDs resolve and 2 don't (typo, or a
  since-removed PDB entry), show which 8 got added and which 2 failed and why — don't
  silently drop them or fail the whole batch on one bad ID.
- `config.yaml`'s `core.max_proteins` / `app.max_proteins` (currently `20`) is already
  the right cap to enforce against the batch size — reuse it, don't add a second limit.

### 3.3 Shareable run links

- **Prerequisite fix, do this regardless of the rest**: change run-ID generation from a
  bare timestamp to timestamp + random suffix (or switch to `uuid4` outright, matching
  how job IDs already do it — `job_id = uuid.uuid4().hex` at `api.py:486`/`599`). This
  closes a real enumeration gap that exists today independent of whether "sharing" ships.
- Once IDs are unguessable, "sharing" is mostly: a "Copy share link" action (in
  `HistoryPanel.js`, on a completed run) that copies a URL like `/run/{run_id}`, plus a
  minimal read-only frontend route that loads a run by ID via the existing
  `/api/report`/`/api/sequence`/etc. endpoints and renders it without requiring that run
  to be in the viewer's own `/api/history` list.
- Decide explicitly (see Open Questions) whether a shared run is world-readable to anyone
  with the link (simplest, matches how `/results` already behaves once IDs are
  unguessable) or needs an additional explicit "make shareable" toggle stored per run —
  don't let this be implicit/undecided the way plain run-ID access is today.

## 4. Technical requirements

- **Backend**: `POST /api/upload` (multipart), extending `PDBManager` to route a
  synthetic upload ID through the same `download_pdb`-adjacent path fetched IDs use;
  random-suffixed run-ID generation in `coordinator.py`/`discovery_coordinator.py`;
  content-type/structure validation on upload separate from the existing size check.
- **Frontend**: upload control in `OverviewTab.js`; a batch-paste input mode in the same
  component; a new minimal read-only run view route/component; a share-link action in
  `HistoryPanel.js`.
- **No changes needed** to `MustangRunner`, `RMSDAnalyzer`, the Mustang core, or anything
  Streamlit shares — this is entirely SPA/API-layer work, so none of it needs cherry-picking
  to `streamlit-stable`.
- **Tests**: new tests for `/api/upload` (valid structure, invalid content, oversized
  file, path-traversal-style filename), batch `/api/chains` partial-failure behavior, and
  run-ID uniqueness/unguessability; a frontend test for the batch-paste parser and the
  read-only run view.

## 5. Phased plan

- [x] **Phase 1 — Run-ID hardening**: switched Compare/Discover run-ID generation from a
      bare `int(timestamp())` to `{prefix}_{timestamp}_{16-hex-char random suffix}`.
      Done: extracted the (previously duplicated) generation logic into
      `src/utils/run_id.py`'s `generate_run_id()`, used by both
      `coordinator.py` and `discovery_coordinator.py` — also removes the
      near-identical duplication that existed between the two call sites.
      `tests/test_run_id.py` covers format, path-segment safety, and
      no-collision-at-the-same-second. Verified live through the real
      running server: a real 4RLT+3UG9 alignment produced
      `run_1783414603_2b797f99f0bee74f`, not the old guessable
      `run_1783414603`. Full suite (227 tests) + ruff/black clean.
- [x] **Phase 2 — Batch ID input**: shipped frontend-only, no backend changes needed —
      `/api/chains` already accepted a list. Done: a "Paste multiple IDs" toggle in
      `OverviewTab.js` reveals a textarea; `App.addManyPDBs()` (`main.js`) enforces the
      same 20-structure cap `config.yaml`'s `core.max_proteins` defines (previously
      unenforced anywhere — a batch paste is the first path that can realistically hit
      it in one action). Partial-failure feedback distinguishes invalid tokens,
      in-workspace duplicates, and over-cap skips. 5 new frontend tests; live-verified
      via Playwright against the real running server (screenshot: pasted
      `1CRN, 2LYZ\nnotanid, 4RLT` against a workspace that already had 4RLT/3UG9 →
      correctly added 1CRN+2LYZ, skipped the 4RLT duplicate, flagged NOTANID, real
      chain metadata resolved for all 4, zero console errors).
- [x] **Phase 3 — Custom structure upload**: `POST /api/upload` (multipart), returning
      the same `{"chains": {...}}` shape `/api/chains` does so the frontend merges it
      identically. Done: `PDBManager.save_uploaded_bytes()` enforces
      `pdb.max_file_size_mb` and actually validates the content parses as a real
      structure with ≥1 chain via `_get_structure()` (deletes the file and fails
      clearly otherwise) — a `.pdb`-named text file that isn't a structure fails here,
      not later inside Mustang. The saved extension matches the upload's real format
      (`.cif` preserved, not forced to `.pdb`), and `download_pdb()`'s cache-hit check
      now looks for either extension so a later alignment run finds the already-saved
      upload instead of trying to fetch a remote source it never came from. Synthetic
      IDs are `UPLOAD-{random 8-hex}` (random, not derived from the filename, so two
      uploads can't collide or be guessed). `OverviewTab.js` gained an "Upload a
      structure file" control next to the paste-multiple-IDs one; uploaded structures
      get an "Uploaded" source badge and show the original filename (HTML-escaped).
      9 new backend tests + 6 new frontend tests. Live-verified through the real
      running server: uploaded a genuine small PDB file (1CRN), watched it get an
      `UPLOAD-` ID and "Uploaded" badge, then **ran a real 3-structure alignment**
      (2 fetched + the upload) that actually succeeded end-to-end — real RMSD values,
      3D superposition, sequence view, and all export formats generated — proving the
      cache-hit fallback actually works, not just that the upload endpoint responds.
- [ ] **Phase 4 — Shareable run links**: read-only run view + share-link action, built on
      top of Phase 1's hardened IDs. Resolve the world-readable-vs-explicit-toggle open
      question below before shipping the UI for this (the backend read path already works
      either way).

## 6. Open questions

- Is a shared run world-readable to anyone with the link once IDs are unguessable
  (simplest, matches today's de-facto `/results` behavior), or does sharing need an
  explicit opt-in per run (safer default, more UI/state)? Affects Phase 4's scope, not
  Phases 1-3.
- Should uploaded structures be cached/deduplicated like fetched ones are
  (`pdb_cache` table, `database.py:59`), or always treated as one-off/session-only since
  there's no stable public ID to key a cache on?
- Does batch input need a hard ceiling below `max_proteins` (e.g. warn at 10, hard-stop
  at 20) to keep a single paste from immediately maxing out an alignment, or is the
  existing cap sufficient on its own?
