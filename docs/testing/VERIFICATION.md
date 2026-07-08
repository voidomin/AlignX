# StructScope Verification Protocol

Follow this step-by-step guide to verify the StructScope project setup, backend operations, scientific quality calculations, and frontend SPA interface.

---

## Verification Pipeline (Recommended Order)

To ensure comprehensive coverage and prevent troubleshooting bottlenecks, always run tests in the following order:

```mermaid
graph TD
    A[1. Setup & Environment Checker] --> B[2. Automated Pytest Unit Tests]
    B --> C[3. Scientific Metrics Verification]
    C --> D[4. FastAPI Web Server Check]
    D --> E[5. Frontend Unit Tests]
    E --> F[6. Frontend Compilation & UI Flow]
    F --> G[7. Discover Mode Verification]
    G --> H[8. Security & CI Verification]
```

---

### Step 1: Environment & Setup Verification
Before running calculations, verify that external binaries like Mustang and the local Python interpreter environment are correctly configured.

Run the setup diagnostics check:
```powershell
# Run using the local virtual environment Python
.venv\Scripts\python scripts\check_setup.py
```
*Expected Output:*
- Checks the Python interpreter and verify if Mustang is detected successfully (either via WSL or native binary).

---

### Step 2: Automated Pytest Unit Tests
Run the comprehensive suite of unit tests, which mock external requests and check the integrity of coordinates downloading, caching, configurations, structures, and API logic.

Run the test suite script:
```powershell
# Executes pytest in the virtual environment
powershell -File scripts\run_tests.ps1
```
*Expected Output:*
- Pytest runs 674 items successfully and shows no errors.
- Verification scripts are executed automatically as part of the run.

---

### Step 3: Scientific Metrics & Torsion Verification
Verify the accuracy of scientific calculations, specifically the TM-Score/GDT calculations and Ramachandran torsion angle mapping.

1. **Verify sequence identity:**
   ```powershell
   .venv\Scripts\python tests/verify_identity.py
   ```
2. **Verify RMSD/TM-score metrics on a real run:**
   ```powershell
   .venv\Scripts\python tests/verify_metrics.py
   ```
3. **Verify Ramachandran/Torsion calculation:**
   ```powershell
   .venv\Scripts\python tests/verify_ramachandran.py
   ```

---

### Step 4: FastAPI Web Server Verification
Run the FastAPI web server locally and verify that the backend endpoints are online.

1. **Launch the backend server:**
   ```powershell
   .venv\Scripts\uvicorn src.backend.api:app --host 127.0.0.1 --port 8000
   ```
2. **Test the health endpoint:**
   Open your browser or terminal and hit:
   `http://127.0.0.1:8000/health`
   *Expected Response:*
   ```json
   {
     "status": "healthy",
     "mustang_installed": true,
     "mustang_message": "..."
   }
   ```
3. **Test the async alignment job queue:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/jobs/align -H "Content-Type: application/json" -d "{\"pdb_ids\": [\"4RLT\", \"3UG9\"]}"
   ```
   Expect an immediate `202` with a `job_id`. Poll `GET /api/jobs/{job_id}` until `status` is `completed` (or `failed`).
4. **Test API auth (only if `ALIGNX_API_KEY` is set in your `.env`):**
   A request to any `/api/*` route without `X-API-Key` (or `?api_key=`) should return `401`; with the correct key, `200`.
5. **Test a non-PDB structure source:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/chains -H "Content-Type: application/json" -d "{\"pdb_ids\": [\"AF-P69905-F1\"]}"
   ```
   Expect a `200` with `source: "alphafold"` in the response. Same pattern works for `SM-{UniProt}` (SWISS-MODEL) and `ESM-{MGYP accession}` (ESM Atlas) IDs.

---

### Step 5: Frontend Unit Tests
Run the Vitest suite covering `api.js` and the JS components (auth headers, job polling, cluster/comparison rendering).

```powershell
cd web-frontend
npm test
```
*Expected Output:* all test files pass (currently 142 tests across the suite, covering `api.js` and every tab/panel component, including `DiscoverTab.js`).

---

### Step 6: Frontend Build & UI Flow Verification
Verify the Vite single page application (SPA).

1. **Rebuild the Frontend:**
   Make sure the built HTML assets are packaged for production and copied to the backend's static directory.
   ```powershell
   powershell -File scripts\build_frontend.ps1
   ```
2. **Start Development Dev Server (Optional):**
   If you want to run the front-end dynamically with reload capabilities:
   ```powershell
   cd web-frontend
   npm run dev
   ```
   Access the dev server at: `http://localhost:5173`.
3. **Verify Full-Stack Single Port Execution (Recommended):**
   Once built using `scripts\build_frontend.ps1`, open `http://127.0.0.1:8000/` in your browser.
   - Check the top bar's tab strip: **Dashboard, Overview, Ligands, Sequence, Analytics, Clusters, Compare, History**.
   - On **Dashboard**, confirm aggregate stats and recent activity populate (may take a few seconds on first load).
   - On **Overview**, add at least two structures — try mixing sources, e.g. a plain PDB ID (`4RLT`) alongside an `AF-`, `SM-`, or `ESM-` prefixed ID — and confirm each shows the correct source badge and metadata line.
   - Choose a chain per structure and click **Run Structural Alignment** — it should show an "Aligning..." state while the background job runs, then populate all tabs once complete.
   - In the 3D viewer, confirm each structure gets a distinct color and the HUD legend/pairwise RMSD list scale to however many structures were aligned (not just a fixed pair).
   - On **Ligands**, switch the structure picker between the aligned structures and confirm the ligand list and interactions refresh for each.
   - On **Sequence**, toggle the report-section checklist and confirm the "Download PDF" link's URL updates; confirm "View Notebook" opens a valid HTML file.
   - Run a second alignment with different structures, then check the **Compare** tab to diff it against the first run.
   - On **History**, confirm past runs list and reloading one restores its full state (3D view, stats, tabs).

---

### Step 7: Discover Mode Verification
Verify the structure-to-function inference pipeline (Foldseek search + InterPro/QuickGO/STRING/Reactome/SIFTS annotation aggregation), separate from the Compare workflow above.

1. **Submit a Discover job:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/jobs/discover -H "Content-Type: application/json" -d "{\"pdb_id\": \"AF-P69905-F1\"}"
   ```
   Expect an immediate `202` with a `job_id`. Poll `GET /api/jobs/{job_id}` until `status` is `completed` (or `failed`) — this calls the live public Foldseek API (shared rate limit, ~0.1 req/s), so it may take a minute or more.
2. **Verify the three detail levels in the browser:**
   On the **Discover** tab, submit a structure ID and confirm the Public/Student/Researcher toggle changes what's shown for the same underlying result — Researcher should show the unfiltered domain/GO-term lists plus a "High-confidence" stat, while Public/Student show only the confidence-gated ("`annotation.min_confident_probability`-cleared") subset.
3. **Verify the low-confidence path:**
   If a result has zero neighbors clearing the confidence threshold, Public/Student should show an explicit low-confidence message rather than an empty or misleadingly confident result.
4. **Verify export/report parity:**
   From a completed Discover run, confirm both "Download Report" (`GET /api/discover/report`, a self-contained HTML file) and "Download JSON" (`GET /api/discover/export`) links work.
5. **Verify History integration:**
   Confirm the completed Discover run appears on the **Dashboard** and **History** tab with a `DISCOVER` badge (distinct from `COMPARE`-badged Compare runs), and that reopening it from History repopulates the Discover tab (not the Compare workspace).
6. **(Optional) Verify the self-hosted Foldseek backend:**
   Set `foldseek.backend: local` in `config.yaml` with `foldseek.local.binary_path`/`database_dir` pointed at a real Foldseek binary and search database, restart the server, and repeat step 1 — confirm the job completes without calling the public API.
7. **Verify the database picker:**
   On the **Discover** tab, expand the "Databases" disclosure below the input — confirm `pdb100`/`afdb50` (PDB / AlphaFold DB) are checked by default and the other 7 are not. Uncheck both defaults and check a different one (e.g. CATH), submit, and confirm the completed run's `databases_searched` reflects the custom selection, not the default. Confirm unchecking every box blocks submission with an inline error instead of calling the API. Reopen a past run from History and confirm the picker's checkboxes update to match that run's actual `databases_searched`.
8. **Verify CATH/BFVD/BFMD/GMGC annotation resolution:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/jobs/discover -H "Content-Type: application/json" -d "{\"pdb_id\": \"1CRN\", \"databases\": [\"cath50\"]}"
   ```
   Poll to completion and confirm `annotations.resolvable_hit_count` is nonzero (CATH domain IDs resolve via the same SIFTS path as pdb100). Repeat with `"databases": ["BFVD"]` or `["bfmd"]` (these embed a UniProt accession directly in the target ID) and `"databases": ["gmgcl_id"]` (resolves via GMGC's own API instead of UniProt - see `annotations.top_domains` for real Pfam hits like `Phage_portal`) and confirm the same. Only `mgnify_esm30` is expected to still show `resolvable_hit_count: 0` for essentially every candidate — see `docs/ROADMAP_V3.md` §7.
9. **(Optional) Verify provisioning a real self-hosted Foldseek database:**
   Run `bash scripts/provision_foldseek_db.sh CATH50 /some/path` (real download, ~1GB, several minutes). Point `foldseek.local.database_dir` at the resulting output prefix and `foldseek.backend: local` in `config.yaml`, restart the server, and repeat step 6 above — confirm a real query correctly finds structural matches against the full downloaded database, not just a small hand-built one.

---

### Step 8: Security & CI Verification
Verify the API-key auth boundary, and that CI actually validates the production Docker image and dependency health rather than just running unit tests.

1. **Verify `/results` and `/raw` are gated by `ALIGNX_API_KEY` when set:**
   ```bash
   ALIGNX_API_KEY=secret-key .venv\Scripts\uvicorn src.backend.api:app --host 127.0.0.1 --port 8000
   ```
   ```bash
   curl -i http://127.0.0.1:8000/results/some_run/alignment.pdb
   ```
   Expect `401` with no key. Repeat with `-H "X-API-Key: secret-key"` or `?api_key=secret-key` appended - expect a `404` (no such file - proves the request passed the auth check and reached `StaticFiles`), not `401`. Confirm `curl http://127.0.0.1:8000/` (the SPA shell) is never gated regardless of the key.
2. **Verify concurrent job submission stays correct under real load:**
   ```powershell
   .venv\Scripts\python -m pytest tests/test_concurrency.py -v
   ```
   Confirm all 3 tests pass: the rate limiter holds exactly at its configured limit under a genuine concurrent burst (not just sequential requests), different clients get independent rate-limit buckets, and many concurrent Discover jobs each resolve to their own correct result with no cross-job data corruption.
3. **Verify the Docker CI job locally:**
   ```bash
   docker build -t structscope:verify .
   docker run -d --name structscope-verify -p 8000:8000 structscope:verify
   curl --retry 10 --retry-delay 2 --retry-connrefused http://localhost:8000/health
   docker rm -f structscope-verify
   ```
   This is exactly what `.github/workflows/ci.yml`'s `docker-build` job runs on every push/PR.
4. **Verify dependency scanning is clean:**
   ```powershell
   pip install pip-audit; pip-audit -r requirements.txt
   ```
   ```powershell
   cd web-frontend; npm audit --audit-level=high
   ```
   Both should report zero known vulnerabilities (matching CI). A finding here means a real dependency CVE needs addressing, not a test bug.
