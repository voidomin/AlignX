# AlignX v2.0: The "Holo-Lab" Roadmap

This document outlines the development path for Version 2.0, categorized by the type of work required.

## 🐞 Bugs (Known Issues & Fixes)

Issues to resolve before or during v2.0 development.

- [x] **Streamlit Reruns**: Investigate and fix excessive app reruns. (Added caching to heavy compute functions).
- [x] **Mobile Responsiveness**: Fix sidebar overlapping content and table scrolling.
- [x] **Large File Handling**: Added file size check and UI warnings for >50MB PDBs.
- [x] **WSL Timeout**: Added retry logic (2 attempts) and user-configurable timeout slider.

## 🚀 Improvements (Enhancements to Existing)

Polishing and upgrading what we already have.

### "Holo-Lab" UI Overhaul

- [x] switch to "Glassmorphism" design (translucent cards, neon borders).
- [x] **Hero Layout**: Massive, glowing titles and animated backgrounds.
- [x] **Central "Mission Control"**: Move inputs from sidebar to a central landing page.
- [x] Implement a "Command Console" log view instead of standard text output.

### Performance Optimization

- [x] Parallel processing for PDB cleaning and Mustang execution. (Implemented ThreadPoolExecutor in `pdb_manager` and optimized runner)
- [ ] Lazy loading for 3D molecular views to speed up initial render.

### Download Manager

- [ ] Add a "Cancel" button for long download batches.
- [x] Show individual progress bars for each file.

### Contextual Education (For Non-Experts)

- [x] Add "Explain this" tooltips/modals for technical terms (RMSD, P-value, etc.).
- [ ] **"Guided Mode"**: A walkthrough wizard that explains the results step-by-step.

## ✨ Features (New Capabilities)

Brand new functionality to expand scientific scope.

### Custom Report Builder

- [ ] Selectable modules: Users choose which results (RMSD, Sequence, clusters) to include.
- [x] Comprehensive Output: Support for full-resolution plots and data tables in the PDF/HTML report.

### Bidirectional Sync (The "Killer Feature")

- [x] Clicking a residue in Sequence View highlights it in Structure View.
- [ ] Selecting a cluster in the Tree View filters the Structure View.

### Ligand Hunter

- [x] Automated detection of residues within 5Å of ligands.
- [x] "Binding Pocket View": Side-by-side comparison of active sites.
- [ ] Ligand chemical similarity matrix.

### Automated Insights

- [ ] "Smart Captions" that textually describe RMSD outliers and conserved regions. (Currently placeholder)
- [ ] Exportable HTML Lab Notebook.

## 🏗️ Architecture & Tech Debt

Internal changes to support the future.

- [x] **Backend Decoupling**: Fully separate the analysis logic from Streamlit (allows for a future REST API).
- [x] **Testing Suite**: Add automated unit tests for the `MustangRunner` and `PDBManager`.
- [x] **Configuration UI**: Move `config.toml` settings to a UI-based settings menu.
- [x] **Multi-Page App Structure**: Refactor the monolithic `app.py` into Streamlit `pages/` for better maintainability.
- [x] **Dependency Management**: Lock versions in `requirements.txt` to prevent future breakage.
