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
- [x] **Alignment Quality Score**: Per-structure confidence score (TM-score or GDT-TS) showing how well each structure fits the consensus.
- [x] **Ramachandran Plot**: Interactive phi/psi plot with protein highlighting, favored region shading, and residue label toggles.
- [x] **CI/CD Pipeline**: GitHub Actions for `ruff`, `black`, `pytest` — auto-runs on push/PR.

---

## 🔧 5. Bug Fixes & UI Polish (v2.3) ✅

- [x] **Deep Clean Cache**: Now wipes `data/raw/` + `data/cleaned/` + all caches + full session reset.
- [x] **Input Section Redesign**: Moved Smart Search/Upload/Load Example to top of page.
- [x] **Scrollable Result Tabs**: CSS horizontal scroll + shortened labels (all 8 tabs accessible).
- [x] **10 Example Datasets**: Added Immunoglobulins, Serine Proteases, Cytochrome P450s, Insulin, COVID-19 Spike, Fluorescent Proteins.
- [x] **Version bump**: `2.1.0` → `2.3.0`.

---

## 🔮 6. Next Version (v2.4) — Roadmap

### Multi-User Session Isolation

> ⚠️ **Known Issue**: On Streamlit Cloud, all users share the same filesystem and `st.cache_data`. This means:
>
> - Downloaded PDB files in `data/raw/` and `data/cleaned/` are shared
> - SQLite History DB is shared (all users see the same run history)
> - **Deep Clean wipes files for ALL users**

- [x] **Per-session file storage**: Use session IDs to namespace `data/raw/{session_id}/` and `data/cleaned/{session_id}/`
- [x] **Session-aware Deep Clean**: Only clear the current user's files, not everyone's
- [x] **User-scoped history**: Filter history DB by session/user ID
- [x] **TTL-based auto-cleanup**: Auto-purge stale session files after 24h to manage disk space

### Other Ideas

- [x] **Archive planning docs**: Move `v2.1_planning/` to `docs/archive/`
- [x] **Dockerfile Python version**: Align with Streamlit Cloud (Python 3.10)
- [ ] **Export to Jupyter Notebook**: One-click export of full analysis pipeline

---

**Status**: ✅ v2.4.0 Released — Multi-User Session Isolation Complete
**Current Branch**: `feat/v2.4-session-isolation`
