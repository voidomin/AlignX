# Deployment Guide for StructScope

This guide covers deploying StructScope's two interfaces: the primary **Vite + FastAPI** full-stack app (via a free Vercel + Render split, or via Docker for a real production deploy), and the separately-deployed **Streamlit** app (via Streamlit Cloud / Hugging Face Spaces).

---

## 🆓 Option 1: Vercel + Render (Free-Tier Split Deploy)

The current beta deployment path — getting the SPA in front of early
reviewers/scientists for feedback before committing to a real production
host. Frontend and backend deploy as two separate free services; Docker
(Option 2 below) remains the recommended path once ready for a real launch,
since these free tiers have real limits (see below).

Steps marked **(manual)** require logging into a dashboard with your own
account. Everything else here is already committed to the repo.

### 1. Backend on Render

Render's free web-service tier runs the existing `Dockerfile` as-is — no
rewrite needed. `render.yaml` (repo root) is a Render "Blueprint" that
pre-fills the service config.

**(manual)**
1. Go to [render.com](https://dashboard.render.com), sign in, **New +** →
   **Blueprint**.
2. Connect this GitHub repo. Render detects `render.yaml` and proposes a
   `structscope-backend` web service on the free plan.
3. It prompts for the two env vars declared in `render.yaml`:
   - `ALIGNX_CORS_ORIGINS` — leave blank for now (step 3 below fills this in
     once the frontend URL exists; blank defaults to `*`, fine for an
     initial trial but not final).
   - `ALIGNX_API_KEY` — leave unset for an open beta, or set a value to
     require it on every `/api/*` request.
4. Deploy. First build compiles Mustang from source, so expect several
   minutes. Once live, note the URL Render gives you, e.g.
   `https://structscope-backend.onrender.com`.
5. Confirm it's up: `curl https://structscope-backend.onrender.com/health`.

`render.yaml` already sets `MUSTANG_BACKEND=native` — the committed
`config.yaml` defaults to `wsl` (this project's Windows local-dev
convention), which would fail on Render's Linux container without this
override.

### 2. Frontend on Vercel

`web-frontend/vercel.json` sets the build command/output dir and an SPA
rewrite.

**(manual)**
1. Go to [vercel.com](https://vercel.com/new), sign in, **Import** this
   repo.
2. Set **Root Directory** to `web-frontend` (the SPA, not the repo root).
   Vercel auto-detects Vite; `vercel.json` covers the rest.
3. Add an environment variable: `VITE_API_BASE` = the Render URL from
   step 1 (e.g. `https://structscope-backend.onrender.com`). If you set
   `ALIGNX_API_KEY` on the backend, also add `VITE_ALIGNX_API_KEY` here with
   the same value.
4. Deploy. Note the resulting URL, e.g. `https://structscope.vercel.app`.

### 3. Close the CORS loop

**(manual)** Back in Render's dashboard, set `ALIGNX_CORS_ORIGINS` to the
exact Vercel URL from step 2 (no trailing slash; comma-separate if you also
want preview-deploy URLs allowed). Saving triggers an automatic redeploy.

At this point the split deployment is live end-to-end: Vercel serves the
SPA, which calls the Render-hosted API, which only accepts requests from
that origin.

### Known limitations of this free-tier setup

- Render's free web service **sleeps after ~15 min idle** and takes 30-60s
  to wake on the next request — fine for early reviewers who know to expect
  it, not for a real launch.
- Leaving `ALIGNX_CORS_ORIGINS` / `ALIGNX_API_KEY` open is a deliberate
  choice for a small, trusted feedback round — tighten before wider access
  (see `src/backend/api.py`'s own startup warning if these are
  misconfigured together).

---

## 🐳 Option 2: Docker (Recommended for Production — Vite + FastAPI)

This is the production path: a single container running the FastAPI backend, serving the pre-built Vite SPA as static files.

### Prerequisites

1. Docker installed locally or on your host.
2. The frontend built and committed: run `powershell -File scripts\build_frontend.ps1` after any frontend change, then commit the updated `static/` directory. The Dockerfile does **not** run `npm install`/`npm run build` itself — it copies whatever is already in `static/`.

### Build & Run

```bash
docker build -t structscope .
docker run -p 8000:8000 --env-file .env structscope
```

The app is now live at `http://localhost:8000` (or your host's address).

### Production Configuration

Set these in your `.env` (copy from `.env.example`) before building/running for anything beyond local testing:

- **`ALIGNX_API_KEY`** — set a real secret. Without it, every `/api/*` route (plus `/results` and `/raw`, which serve generated reports/notebooks and downloaded structure files directly off disk) is open to anyone who can reach the container.
- **`ALIGNX_CORS_ORIGINS`** — set to your actual frontend origin(s) (comma-separated). The default `*` is fine for local testing only.

### Persistent Storage

`results/`, `data/`, and `run_history.db` (SQLite, written to `/app/run_history.db`) live inside the container by default and are lost on container recreation. Mount `results/` and `data/` as volumes:

```bash
docker run -p 8000:8000 --env-file .env \
  -v structscope_results:/app/results \
  -v structscope_data:/app/data \
  structscope
```

`run_history.db` is a single file rather than a directory, so it can't be targeted by a named volume the same way — either bind-mount a host directory over `/app` and place the file inside it, or point `HistoryDatabase(db_path=...)` (in `src/backend/api.py`) at a path under one of the mounted volumes above. This file holds more than run history now: it also has the `annotation_cache` table (InterPro/QuickGO/SIFTS/STRING/Reactome lookups, ~30-day TTL by default - see `annotation.cache_ttl_days`), so losing it on every container recreation means Discover mode loses its cache too, not just the History tab.

### Network Requirements

Beyond RCSB/AlphaFold/SWISS-MODEL/ESM Atlas (already required for Compare mode's structure downloads), **Discover mode adds outbound HTTPS calls to six more third-party services**: `search.foldseek.com`, `www.ebi.ac.uk` (InterPro + QuickGO + the SIFTS PDB-to-UniProt mapping), `string-db.org`, `reactome.org`, and `gmgc.embl.de` (native annotation for `gmgcl_id` hits). If the container runs behind a restrictive egress firewall, allowlist these or Discover jobs will fail (Compare mode is unaffected). To avoid depending on the public Foldseek API entirely (rate-limited to ~0.1 req/s shared across every user), see `foldseek.backend: local` in `config.yaml` and `src/backend/foldseek_runner.py` - self-hosting a Foldseek binary + search database is the scale-up path (see below for provisioning a real database).

### Provisioning a self-hosted Foldseek database

`foldseek.backend: local` needs a real Foldseek search database on disk - `bash scripts/provision_foldseek_db.sh <database-name> <output-dir>` wraps Foldseek's own `foldseek databases` command (which downloads and indexes one of Foldseek's officially-distributed databases) with the exact config wiring you need afterward. Run it on the host/volume that will actually serve Discover traffic, not in CI or during development - depending on which database you pick, this ranges from under a gigabyte to hundreds of gigabytes and can take minutes to many hours.

Live-verified end-to-end: `bash scripts/provision_foldseek_db.sh CATH50 /path/to/dbs` downloaded (~970MB) and built a real, complete CATH50 database (~1.9GB extracted on disk), and pointing `foldseek.local.database_dir` at the result correctly found 1CRN's own real CATH domain entry (prob 1.0) plus related structures - the same discrimination the public API gives, from a fully real (not hand-built) database.

Picking a database (see the script's own comments for the full list and more detail):
- **CATH50** - domain-clustered CATH database, ~1GB download. Good default if you want a real, complete, self-hosted database without a large disk/bandwidth commitment.
- **PDB** - the full Protein Data Bank, matching Discover's default `pdb100`. Larger than CATH50 but still far smaller than any AlphaFold option.
- **Alphafold/UniProt50-minimal** or **Alphafold/Swiss-Prot** - matches Discover's default `afdb50` coverage (or a reviewed-only subset) at a small fraction of the full AlphaFold DB's size.
- **Alphafold/UniProt** (the full AlphaFold Protein Structure Database) - Foldseek's own docs list this at ~700GB download / ~950GB extracted. Only provision this if you specifically need full AFDB coverage; the UniProt50 options above cover the same structures far more cheaply.
- **BFMD** - as of this writing, `foldseek databases BFMD ...` has an open upstream bug where the download doesn't work despite being listed (steineggerlab/foldseek#563) - don't rely on it without checking that issue first.

### Health Check

The image defines a `HEALTHCHECK` hitting `GET /health`. Confirm it manually with:

```bash
curl http://localhost:8000/health
```

### Known Limitation: Single-Process Job State

`alignment_jobs`, `discovery_jobs`, and the job-submission rate limiter (`src/backend/api.py`) are plain in-memory Python dicts, not backed by a shared store. This is fine for a single-process deployment (the default - the Dockerfile's `ENTRYPOINT` starts one `uvicorn` worker), which a real concurrency test (`tests/test_concurrency.py`) confirmed handles concurrent submissions correctly - no race conditions, rate limits enforced accurately, no cross-job data corruption under real concurrent load.

It does **not** work correctly if you run multiple worker processes or replicas behind a load balancer (e.g. `uvicorn --workers 4`, or multiple container replicas): each process has its own independent set of dicts, so a client could submit a job to one worker and get a `404 Job not found` polling a different one, and the rate limiter's quota is per-process rather than global. Stick to a single worker process (scale vertically, not horizontally) until job state is moved to a shared store (e.g. the existing SQLite `run_history.db`, or Redis) - not attempted here since it's a real architecture change, not a quick fix.

While investigating job-submission concurrency, the same test suite also caught a real, fixed performance bug: `HistoryDatabase.__init__` re-ran its full `CREATE TABLE`/`ALTER TABLE` schema migration on *every single construction* (both `DiscoveryCoordinator` and `AnalysisCoordinator` construct their own `HistoryDatabase()` per job), which measurably serialized concurrent job startup once `run_history.db` grows large - a handful of concurrent submissions took minutes instead of seconds against a real ~170MB dev database. Fixed by memoizing "already migrated" per `db_path` for the life of the process.

---

## ☁️ Option 3: Streamlit Community Cloud (Streamlit UI only)

Deploys `app.py` (the Streamlit interface). Does **not** deploy the Vite SPA or FastAPI backend, so it doesn't include Discover mode (SPA-only, see README) — use this only if you specifically want the Streamlit experience hosted for free.

### Steps

This repo already maintains two long-lived branches for exactly this reason: `main` is the active FastAPI/SPA/Discover development trunk, and `streamlit-stable` is frozen for whatever's actually live on Streamlit Cloud - so a push to `main` (however large) can never break the deployed Streamlit app. **Deploy from `streamlit-stable`, not `main`.**

1. **If you're forking/setting this up fresh**, push both branches to your own GitHub remote:
    ```bash
    git push -u origin main
    git push -u origin streamlit-stable
    ```
    (If you already have this repo cloned with both branches, skip straight to step 2.)

2. **Sign up/Login to Streamlit Cloud**: [share.streamlit.io](https://share.streamlit.io/), sign in with GitHub.

3. **Deploy the App**:
    - Click "New app" → select your repository → branch **`streamlit-stable`** → main file path `app.py` → **Deploy!**
    - If you're re-pointing an *already-deployed* app rather than creating a new one, use the app's Settings panel instead (Settings → Branch → `streamlit-stable` → Save) - this triggers a reboot from the new branch.

4. Streamlit installs from `requirements.txt`. `packages.txt` provides the system build tools needed to compile Mustang from the bundled source on first run.

5. **When you actually want to ship a Streamlit-visible change** (a fix that touches `app.py`, `pages/`, `src/frontend/`, or backend files Streamlit shares - see `SECURITY.md`/`config_models.py`'s `_soften_optional_sections` for which those are): cherry-pick the specific commit onto `streamlit-stable` and push it there. Don't merge `main` wholesale - that reintroduces the exact coupling this branch split exists to avoid.

### ⚠️ Note on Persistent History

Streamlit Community Cloud uses ephemeral storage:

- The **"History"** sidebar and **result files** are cleared on server restart.
- Download results from the "Downloads" tab for permanent storage.

---

## 🤗 Option 4: Hugging Face Spaces (Streamlit UI only)

Same caveat as above — Streamlit UI only.

1. Create a Space at [huggingface.co/spaces](https://huggingface.co/spaces), SDK: **Streamlit**.
2. Clone the Space repo, copy project files in, `git add . && git commit && git push`.
3. Ensure `requirements.txt` is present — Hugging Face auto-installs it.

---

## 🔒 Secrets

- **Render**: Service → Environment (`ALIGNX_API_KEY`, `ALIGNX_CORS_ORIGINS`, `MUSTANG_BACKEND` — pre-filled by `render.yaml`).
- **Vercel**: Project → Settings → Environment Variables (`VITE_API_BASE`, `VITE_ALIGNX_API_KEY`).
- **Docker**: pass via `--env-file .env` or your orchestrator's secret manager (`ALIGNX_API_KEY`, `ALIGNX_CORS_ORIGINS`).
- **Streamlit Cloud**: App Dashboard → Settings → Secrets.
- **Hugging Face**: Space Settings → Repository secrets.
