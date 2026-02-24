# v2.2 Roadmap & To-Do List

Complete audit of the Mustang Pipeline repository. All findings organized by priority.

---

## 🚨 1. Critical Bugs & Deployment Fixes

- [x] **Circular Import Chain**: Fixed by removing eager imports in `__init__.py` files.
- [x] **Stale `__version__` in `src/__init__.py`**: Updated to `"2.1.0"`.
- [x] **ReDoS Vulnerability in `rmsd_calculator.py`**: Replaced potentially vulnerable regex with secure manual parsing.
- [x] **Committed `.db` and temp files**: Verified as ignored/untracked.
- [x] **Pinned Dependency Versions**: `requirements.txt` updated with modern version ranges.

---

## 🛠️ 2. Technical Debt & Code Cleanup

### Dead Code

- [x] **Remove Bio3D backend option from Settings page**: Done.
- [x] **Remove R/Bio3D check from diagnostics**: Done.
- [x] **Remove commented-out code in Settings**: Done.
- [x] **Remove DEBUG print in downloads.py**: Done.

### Code Quality

- [x] **`notebook_exporter.py` monolithic template**: Extracted to `src/resources/templates/notebook_template.html`.
- [x] **`report_generator.py` still uses Latin-1**: Fixed `clean_text` to handle Å symbol correctly.
- [x] **`insights.py` re-creates `RMSDAnalyzer`**: Now caches and reuses the instance.
- [x] **`rmsd_calculator.py` has 4 parsing strategies**: Consolidated into a unified `parse_rmsd_matrix` handler.
- [x] **Duplicate `id` check in `results.py`**: Cleaned up.
- [x] **Duplicate `st.divider()` in `sidebar.py`**: Fixed.
- [x] **`analysis.py` is 426 lines**: Refactored into modular components in `src/frontend/components/`.

### Repo Hygiene

- [x] **Archive planning docs**: Moved `v2_roadmap.md` and `v2.1_planning/` to `docs/archive/`.
- [x] **Dockerfile Python version**: Aligned with Streamlit Cloud (updated to `python:3.10-slim`).

---

## 🐞 3. Frontend Bugs & UX Polish

- [x] **No error boundaries on tabs**: Wrapped result tabs in `try/except` boundaries in `results.py`.
- [x] **Home page overhaul**: Implemented "Mission Control" dashboard in `home.py`.
- [x] **Sequence alignment uses white/hardcoded colors**: Fixed with CSS variables in `sequence_viewer.py`.
- [x] **Settings page missing v2.1 options**: Added `heatmap_colormap`, `viewer_default_style`, cache management, and **Restore Defaults** button.
- [x] **Clusters tab unsafe session state access**: Fixed with `.get()` pattern in `clusters.py`.
- [x] **Guided Mode cards are 13KB of hardcoded text**: Extracted to `src/resources/guided_data.yaml`.
- [x] **3D tab missing emoji in tab list**: Fixed.
- [x] **Session state initialization scattered**: Centralized in `app.py`.

---

## 🚀 4. New Features (v2.2)

- [x] **Batch Comparison Mode**: Compare two separate alignment runs side-by-side (e.g., family A vs family B), showing differential RMSD and overlap.
- [x] **AlphaFold Integration**: Accept AlphaFold DB IDs or `.cif` file uploads — auto-convert CIF→PDB for Mustang.
- [ ] **Alignment Quality Score**: Per-structure confidence score (TM-score or GDT-TS) showing how well each structure fits the consensus.
- [ ] **ramachandran plot**: Add ramachandran plot for the aligned structures. user should be able to select the protein and alligned protein to plot.
- [ ] **CI/CD Pipeline**: GitHub Actions for `pytest`, `mypy`, and auto-deploy on merge to `main`.

---

**Status**: 📋 Phase 3.5 Repo Hygiene Complete — Phase 4 Features Next  
**Target Branch**: `feat/v2.2-improvements`
