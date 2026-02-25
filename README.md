# 🧬 Mustang Structural Alignment Pipeline (v2.4.1)

An automated, full-stack bioinformatics pipeline for multiple structural alignment of **any protein family** using Mustang, featuring interactive 3D visualizations, phylogenetic analysis, and advanced ligand hunter capabilities.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://mustang-pipeline.streamlit.app)
[![Version](https://img.shields.io/badge/version-2.4.1-orange.svg)](https://github.com/your-repo/mustang-pipeline/releases/tag/v2.4.1)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 🎯 Key Features

### 🎨 High-Impact "Cyber-Bio" UI

- **Mission Control Dashboard**: Glassmorphic interface for orchestrating complex runs.
- **Guided Mode**: Interactive learning cards that explain analysis steps for beginners.
- **System Diagnostics**: Real-time health checks for local and cloud environments.

### 🧠 Advanced Analysis

- **Automated Alignment**: Multi-protein superposition powered by Mustang core.
- **Multi-User Session Isolation (v2.4)**: Full compatibility with stateless deployments like Streamlit Cloud, featuring auto-refreshing sessions and TTL memory management to prevent data overlap.
- **Ligand Hunter**: Auto-detect binding pockets, calculate interaction similarities, and visualize SASA (Solvent Accessible Surface Area).
- **Smart Insights**: Automated captions describing RMSD outliers, structural families, and ligand distributions.
- **Interactive Phylogeny**: Structural phylogenetic trees generated via average linkage (UPGMA).

### 🚀 Visualization & Export

- **Dynamic 3D Viewer**: Embedded 3Dmol.js viewer with highlighting and spinning controls.
- **Interactive Heatmaps**: Plotly-powered RMSD matrices with custom colormaps.
- **Standalone Lab Notebook**: Generate a self-contained HTML notebook with embedded 3D structures.
- **PDF Reports**: Professional analysis summaries ready for citation.

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/your-username/mustang-pipeline.git
cd mustang_pipeline

# Install dependencies
pip install -r requirements.txt
```

### 2. External Tools

The pipeline requires the **Mustang** binary (v3.2.3).

- **Cloud**: Pre-configured on Streamlit Cloud.
- **Windows**: See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for WSL or native setup instructions.

### 3. Run the App

```bash
streamlit run app.py
```

_Access at: `http://localhost:8501`_

---

## 📂 Project Architecture

```
mustang_pipeline/
├── app.py                # Main Entry Point
├── config.yaml           # Global Configuration
├── src/
│   ├── backend/          # Core Logistics (Coordinator, Runner, Analyzers)
│   ├── frontend/         # UI Components (Mission Control, Results, Tabs)
│   └── utils/            # Utilities (Caching, Logging, Config)
├── data/                 # Raw & Cleaned PDB Storage
├── results/              # Run History & Artifact Exports
└── tests/                # Automated Verification Suite
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

**Issues?** Open a GitHub issue or contact at `akashkbhat4414@gmail.com`.

---

Developed with ❤️ by **Akash**  
_Optimized for Structural Biology & Computational Drug Discovery_
