# AlignX Verification Protocol

Follow this step-by-step guide to verify the AlignX project setup, backend operations, scientific quality calculations, and frontend SPA interface.

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
```

---

### Step 1: Environment & Setup Verification
Before running calculations, verify that external binaries like Mustang and the local Python interpreter environment are correctly configured.

Run the setup diagnostics check:
```powershell
# Run using the local virtual environment Python
.venv\Scripts\python check_setup.py
```
*Expected Output:*
- Checks the Python interpreter and verify if Mustang is detected successfully (either via WSL or native binary).

---

### Step 2: Automated Pytest Unit Tests
Run the comprehensive suite of unit tests, which mock external requests and check the integrity of coordinates downloading, caching, configurations, structures, and API logic.

Run the test suite script:
```powershell
# Executes pytest in the virtual environment
powershell -File run_tests.ps1
```
*Expected Output:*
- Pytest runs 70 items successfully and shows no errors.
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
*Expected Output:* all test files pass (currently 68 tests across 9 files, covering `api.js` and every tab/panel component).

---

### Step 6: Frontend Build & UI Flow Verification
Verify the Vite single page application (SPA).

1. **Rebuild the Frontend:**
   Make sure the built HTML assets are packaged for production and copied to the backend's static directory.
   ```powershell
   powershell -File build_frontend.ps1
   ```
2. **Start Development Dev Server (Optional):**
   If you want to run the front-end dynamically with reload capabilities:
   ```powershell
   cd web-frontend
   npm run dev
   ```
   Access the dev server at: `http://localhost:5173`.
3. **Verify Full-Stack Single Port Execution (Recommended):**
   Once built using `build_frontend.ps1`, open `http://127.0.0.1:8000/` in your browser.
   - Check the top bar's tab strip: **Dashboard, Overview, Ligands, Sequence, Analytics, Clusters, Compare, History**.
   - On **Dashboard**, confirm aggregate stats and recent activity populate (may take a few seconds on first load).
   - On **Overview**, add at least two structures — try mixing sources, e.g. a plain PDB ID (`4RLT`) alongside an `AF-`, `SM-`, or `ESM-` prefixed ID — and confirm each shows the correct source badge and metadata line.
   - Choose a chain per structure and click **Run Structural Alignment** — it should show an "Aligning..." state while the background job runs, then populate all tabs once complete.
   - In the 3D viewer, confirm each structure gets a distinct color and the HUD legend/pairwise RMSD list scale to however many structures were aligned (not just a fixed pair).
   - On **Ligands**, switch the structure picker between the aligned structures and confirm the ligand list and interactions refresh for each.
   - On **Sequence**, toggle the report-section checklist and confirm the "Download PDF" link's URL updates; confirm "View Notebook" opens a valid HTML file.
   - Run a second alignment with different structures, then check the **Compare** tab to diff it against the first run.
   - On **History**, confirm past runs list and reloading one restores its full state (3D view, stats, tabs).
