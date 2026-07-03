# 🧬 AlignX — Protein Structural Alignment Pipeline

An automated, full-stack bioinformatics pipeline for multiple structural alignment of **any protein family** using Mustang, featuring an N-structure 3D viewer, four structure-source databases, phylogenetic analysis, structural clustering, batch comparison, ligand hunting, and a configurable PDF/HTML report builder.

[![Version](https://img.shields.io/badge/version-2.4.1-orange.svg)](#)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🎯 Key Features

### 🎨 Two Interfaces, One Backend

- **Vite + FastAPI SPA** — the actively developed interface, driven entirely by the REST API. Covers every feature below, including the ones not yet in the Streamlit app.
- **Streamlit App** — a separate, currently-deployed interface kept running in parallel. Covers the core alignment/analysis workflow; some newer capabilities (multi-source structure fetching, the Dashboard, the report-section builder) are SPA-only for now.

Both share the same `src/backend/` pipeline and Mustang core — they're two front ends on one analysis engine, not two separate products.

### 🧬 Structure Sources

Add structures from four databases by ID prefix, mixed freely in the same alignment:

| Source | ID format | Example |
|---|---|---|
| RCSB PDB | 4-character code | `4RLT` |
| AlphaFold DB | `AF-{UniProt}-F{fragment}` | `AF-P69905-F1` |
| SWISS-MODEL Repository | `SM-{UniProt}` | `SM-P69905` |
| ESM Metagenomic Atlas | `ESM-{MGYP accession}` | `ESM-MGYP002537940442` |

Each structure shows its source database and available metadata (method, resolution, organism) right in the workspace list, so it's clear what you're aligning and how much confidence to place in it.

### 🧠 Advanced Analysis

- **N-Structure Alignment**: Superimpose two or more structures at once — the 3D viewer, HUD legend, and pairwise RMSD list all scale to however many you add, not just a fixed pair.
- **Structural Clusters**: Interactive RMSD-threshold clustering (hierarchical/average-linkage) to group structurally similar proteins into families.
- **Batch Comparison**: Diff the RMSD matrix of the current run against any past run to see how structural relationships shifted.
- **Ligand Hunter**: Auto-detect binding pockets, calculate interaction similarities, and visualize SASA (Solvent Accessible Surface Area) — for any of the N structures in a run, not just the first.
- **Interactive Phylogeny**: Structural phylogenetic trees generated via average linkage (UPGMA).
- **Dashboard**: Aggregate stats (total runs, proteins analyzed, cache size), recent activity, and quick-start examples.
- **Multi-User Session Isolation**: Session-scoped results and history, safe for stateless/shared deployments.

### 🚀 Visualization & Export

- **Dynamic 3D Viewer**: Embedded 3Dmol.js viewer with per-structure identity coloring, residue highlighting, and spinning controls.
- **Interactive Heatmaps**: Plotly-powered RMSD matrices with custom colormaps.
- **Configurable PDF Reports**: Pick which sections to include (summary, insights, heatmap, phylogenetic tree, RMSD matrix) before exporting.
- **HTML Lab Notebook**: A standalone, self-contained HTML export with an embedded 3D viewer and all analysis figures.

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/<your-org>/AlignX.git
cd AlignX

python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
```

### 2. External Tools

The pipeline requires the **Mustang** binary (v3.2.3).

- **Docker**: handled automatically (see below) — the image compiles Mustang from the bundled `mustang.tgz`.
- **Windows (local)**: see [docs/setup/WINDOWS_SETUP.md](docs/setup/WINDOWS_SETUP.md) for WSL or Bio3D setup instructions.
- Run `.venv\Scripts\python scripts\check_setup.py` at any point to verify Mustang is detected.

### 3. Run the App

You can run either interface, or containerize the SPA + backend.

#### Option A: Vite + FastAPI (Recommended — full feature set)
1. Build the Vite frontend:
   ```powershell
   powershell -File scripts\build_frontend.ps1
   ```
2. Start the FastAPI backend:
   ```powershell
   .venv\Scripts\uvicorn src.backend.api:app --host 127.0.0.1 --port 8000
   ```
3. Open `http://127.0.0.1:8000` in your browser (the backend automatically serves the built static frontend).

#### Option B: Streamlit
```powershell
.venv\Scripts\streamlit run app.py
```
_Access at:_ `http://localhost:8501`

#### Option C: Docker (Vite + FastAPI)
```bash
docker build -t alignx .
docker run -p 8000:8000 --env-file .env alignx
```
The image compiles Mustang from the bundled source and serves the FastAPI backend (with the **already-built** `static/` frontend committed in the repo). If you've changed the frontend, run `scripts\build_frontend.ps1` and commit the updated `static/` before building the image.

---

## 🔐 Environment Variables

Copy `.env.example` to `.env` and customize. Notable production-relevant ones:

| Variable | Default | Purpose |
|---|---|---|
| `ALIGNX_API_KEY` | unset (open) | Requires this value in the `X-API-Key` header (or `?api_key=` query param) on all `/api/*` routes. Leave unset for local dev. |
| `ALIGNX_CORS_ORIGINS` | `*` | Comma-separated list of allowed CORS origins. Restrict to your real frontend origin(s) in production. |
| `MUSTANG_BACKEND` | `auto` | `native`, `bio3d`, or `wsl`. |

---

## 🧪 Testing

Backend (pytest, 70 tests):
```powershell
powershell -File scripts\run_tests.ps1
```

Frontend (Vitest, 68 tests):
```powershell
cd web-frontend
npm test
```

Full step-by-step verification protocol (setup checks, scientific metrics, API smoke tests, UI flow): see [docs/testing/VERIFICATION.md](docs/testing/VERIFICATION.md).

---

## 📚 Documentation

| Doc | Covers |
|---|---|
| [docs/setup/WINDOWS_SETUP.md](docs/setup/WINDOWS_SETUP.md) | Installing Mustang, Phylip, PyMOL on Windows (WSL or Bio3D) |
| [docs/deployment/DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md) | Docker deployment (SPA + FastAPI) + Streamlit Cloud/Hugging Face deployment |
| [docs/testing/VERIFICATION.md](docs/testing/VERIFICATION.md) | Full verification protocol: setup checks, pytest, Vitest, API smoke tests, UI flow |
| [docs/design/DESIGN.md](docs/design/DESIGN.md) | SPA visual design system (colors, typography, component styling) |
| [docs/design/UI_UX_DESIGN.md](docs/design/UI_UX_DESIGN.md) | Streamlit UI/UX layout spec and interaction flows |
| [docs/archive/](docs/archive/) | Superseded planning docs, kept for history |

---

## 📂 Project Architecture

```
AlignX/
├── app.py                  # Streamlit entry point
├── config.yaml             # Global configuration
├── Dockerfile              # FastAPI + Mustang container build
├── docs/
│   ├── setup/               # Platform setup guides
│   ├── deployment/          # Deployment guides
│   ├── design/              # Visual/UX design specs
│   ├── testing/             # Verification protocol
│   └── archive/             # Superseded planning docs
├── src/
│   ├── backend/            # Coordinator, Mustang runner, analyzers, FastAPI app (api.py)
│   ├── frontend/            # Streamlit UI (Mission Control, tabs)
│   └── utils/               # Config loading, caching, logging
├── web-frontend/            # Vite SPA source (builds into static/)
├── static/                  # Built SPA served by FastAPI (git-tracked build output)
├── pages/                   # Streamlit multipage routes (History, Settings)
├── data/                    # Raw & cleaned PDB storage
├── results/                 # Run history & artifact exports
└── tests/                   # Pytest suite (backend) — web-frontend/src/**/*.test.js (frontend)
```

---

## 🔧 Configuration

Customize the pipeline in `config.yaml`:

- **mustang**: Set execution backend (native/wsl) and timeouts.
- **visualization**: Set default 3D styles and heatmap colormaps.
- **pdb**: Configure cleaning levels (water removal, renumbering).

---

## 🤝 Citation & Support

If you use this pipeline in your research, please cite:

- **MUSTANG**: Konagurthu AS, et al. _Proteins_. 2006; 64(3):559-74.
- **BioPython**: Cock PJ, et al. _Bioinformatics_. 2009.
- **AlphaFold DB**: Varadi M, et al. _Nucleic Acids Research_. 2022.
- **SWISS-MODEL Repository**: Bienert S, et al. _Nucleic Acids Research_. 2017.
- **ESM Metagenomic Atlas**: Lin Z, et al. _Science_. 2023.

**Issues?** Open a GitHub issue or contact at `akashkbhat4414@gmail.com`.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

Developed with ❤️ by **Akash**
_Optimized for Structural Biology & Computational Drug Discovery_
