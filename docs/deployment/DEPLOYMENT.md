# Deployment Guide for StructScope

This guide covers deploying StructScope's two interfaces: the primary **Vite + FastAPI** full-stack app (via Docker), and the separately-deployed **Streamlit** app (via Streamlit Cloud / Hugging Face Spaces).

---

## 🐳 Option 1: Docker (Recommended — Vite + FastAPI)

This is the production path: a single container running the FastAPI backend, serving the pre-built Vite SPA as static files.

### Prerequisites

1. Docker installed locally or on your host.
2. The frontend built and committed: run `powershell -File build_frontend.ps1` after any frontend change, then commit the updated `static/` directory. The Dockerfile does **not** run `npm install`/`npm run build` itself — it copies whatever is already in `static/`.

### Build & Run

```bash
docker build -t structscope .
docker run -p 8000:8000 --env-file .env structscope
```

The app is now live at `http://localhost:8000` (or your host's address).

### Production Configuration

Set these in your `.env` (copy from `.env.example`) before building/running for anything beyond local testing:

- **`ALIGNX_API_KEY`** — set a real secret. Without it, every `/api/*` route is open to anyone who can reach the container.
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

Beyond RCSB/AlphaFold/SWISS-MODEL/ESM Atlas (already required for Compare mode's structure downloads), **Discover mode adds outbound HTTPS calls to five more third-party services**: `search.foldseek.com`, `www.ebi.ac.uk` (InterPro + QuickGO + the SIFTS PDB-to-UniProt mapping), `string-db.org`, and `reactome.org`. If the container runs behind a restrictive egress firewall, allowlist these or Discover jobs will fail (Compare mode is unaffected). To avoid depending on the public Foldseek API entirely (rate-limited to ~0.1 req/s shared across every user), see `foldseek.backend: local` in `config.yaml` and `src/backend/foldseek_runner.py` - self-hosting a Foldseek binary + search database is the scale-up path, but provisioning a real production-scale database is a separate, non-trivial step (see `docs/ROADMAP_V3.md`).

### Health Check

The image defines a `HEALTHCHECK` hitting `GET /health`. Confirm it manually with:

```bash
curl http://localhost:8000/health
```

---

## ☁️ Option 2: Streamlit Community Cloud (Streamlit UI only)

Deploys `app.py` (the Streamlit interface). Does **not** deploy the Vite SPA or FastAPI backend, so it doesn't include Discover mode (SPA-only, see README) — use this only if you specifically want the Streamlit experience hosted for free.

### Steps

1. **Push your code to GitHub**:
    ```bash
    git init
    git add .
    git commit -m "Initial commit"
    git branch -M main
    git remote add origin https://github.com/<your-username>/AlignX.git
    git push -u origin main
    ```

2. **Sign up/Login to Streamlit Cloud**: [share.streamlit.io](https://share.streamlit.io/), sign in with GitHub.

3. **Deploy the App**:
    - Click "New app" → select your repository → branch `main` → main file path `app.py` → **Deploy!**

4. Streamlit installs from `requirements.txt`. `packages.txt` provides the system build tools needed to compile Mustang from the bundled source on first run.

### ⚠️ Note on Persistent History

Streamlit Community Cloud uses ephemeral storage:

- The **"History"** sidebar and **result files** are cleared on server restart.
- Download results from the "Downloads" tab for permanent storage.

---

## 🤗 Option 3: Hugging Face Spaces (Streamlit UI only)

Same caveat as above — Streamlit UI only.

1. Create a Space at [huggingface.co/spaces](https://huggingface.co/spaces), SDK: **Streamlit**.
2. Clone the Space repo, copy project files in, `git add . && git commit && git push`.
3. Ensure `requirements.txt` is present — Hugging Face auto-installs it.

---

## 🔒 Secrets

- **Docker**: pass via `--env-file .env` or your orchestrator's secret manager (`ALIGNX_API_KEY`, `ALIGNX_CORS_ORIGINS`).
- **Streamlit Cloud**: App Dashboard → Settings → Secrets.
- **Hugging Face**: Space Settings → Repository secrets.
