# v2.2 Roadmap & To-Do List

Complete audit of the Mustang Pipeline repository. All findings organized by priority.

---

## 🚨 1. Critical Bugs & Deployment Fixes

- [x] **Circular Import Chain**: Fixed by removing eager imports in `__init__.py` files.
- [x] **Stale `__version__` in `src/__init__.py`**: Updated to `"2.1.0"`.
- [x] **ReDoS Vulnerability in `rmsd_calculator.py`**: Replaced potentially vulnerable regex with secure manual parsing.
- [x] **Committed `.db` and temp files**: Verified as ignored/untracked.
- [ ] **Pinned Dependency Versions**: `requirements.txt` pins old versions...

---

## 🛠️ 2. Technical Debt & Code Cleanup

### Dead Code

- [ ] **Remove Bio3D backend option from Settings page**: `pages/3_Settings.py` line 34 still lists `"bio3d"` as a backend. Bio3D was fully removed in v2.0.
- [ ] **Remove R/Bio3D check from diagnostics**: `utilities.py` `run_diagnostics()` lines 56-62 check for R installation — dead since Bio3D removal.
- [ ] **Remove commented-out code in Settings**: `pages/3_Settings.py` lines 53-55 have a commented-out water checkbox.
- [ ] **Remove DEBUG print in downloads.py**: `downloads.py` line 15 has `print(f"DEBUG: Rendering downloads tab...")` — leftover debug statement.

### Code Quality

- [ ] **`notebook_exporter.py` monolithic template**: 228-line HTML template string lives inside `__init__()`. Extract to a separate `.html` template file in `resources/`.
- [ ] **`report_generator.py` still uses Latin-1**: The `clean_text()` function on line 57 still uses `encode('latin-1', 'ignore')` instead of UTF-8 with DejaVuSans font. Angstrom symbols (Å) get stripped.
- [ ] **`insights.py` re-creates `RMSDAnalyzer`**: Line 99 creates a new `RMSDAnalyzer(self.config)` on every call to `generate_insights()`. Should accept it as a parameter or cache it.
- [ ] **`rmsd_calculator.py` has 4 parsing strategies** (330 lines): `calculate_rmsd_from_alignment`, `parse_mustang_log_for_rmsd`, `parse_rms_rot_file`, and `calculate_structure_rmsd`. Consolidate into clear primary + fallback.
- [ ] **Duplicate `id` check in `results.py`**: Lines 22-24 and 41-43 both do the exact same `if 'id' not in results` check.
- [x] **Duplicate `st.divider()` in `sidebar.py`**: Fixed.
- [ ] **`analysis.py` is 426 lines**: Largest frontend module. Extract PDB input form and progress bar into separate components.

### Repo Hygiene

- [x] **README overhaul**: Updated for v2.1.0 with modern feature highlights.
- [ ] **Archive planning docs**: `v2_roadmap.md` and `v2.1_planning/` are from completed versions — move to `docs/archive/`.
- [ ] **Dockerfile Python version**: Uses `python:3.11-slim` but Streamlit Cloud runs Python 3.10. Align or document.

---

## 🐞 3. Frontend Bugs & UX Polish

- [ ] **No error boundaries on tabs**: If any tab's render function throws (e.g., missing dict key), the entire app crashes. Wrap each tab call in `results.py` with `try/except` showing a user-friendly fallback.
- [ ] **Home page is bare**: `home.py` is 32 lines of basic text. No branding, no version badge, no recent activity. Add a hero section with quick-start buttons and recent run summary.
- [ ] **Sequence alignment uses white/hardcoded colors**: `sequence_viewer.py` uses hardcoded white backgrounds (`#ffffff`, `#dfe6e9`) — clashes with the dark theme. Should use theme-aware colors.
- [ ] **Settings page missing v2.1 options**: No UI for `visualization.heatmap_colormap`, `viewer_default_style`, `max_proteins`, or cache management.
- [ ] **Clusters tab unsafe session state access**: `clusters.py` line 50 accesses `st.session_state.metadata` with `hasattr` but it may not exist — needs a safer `.get()` pattern.
- [ ] **Guided Mode cards are 13KB of hardcoded text**: `common.py` has all learning card content inline. Extract to a YAML/JSON data file for maintainability.
- [ ] **3D tab missing emoji in tab list**: `results.py` line 34 — "3D Visualization" has no emoji, unlike all other tabs (e.g., "📊 Summary & RMSD").
- [ ] **Session state initialization scattered**: 15+ `if 'x' not in st.session_state` blocks spread across `app.py`, `analysis.py`, and individual tabs. Centralize in `app.py`.

---

## 🚀 4. New Features (v2.2)

- [ ] **Batch Comparison Mode**: Compare two separate alignment runs side-by-side (e.g., family A vs family B), showing differential RMSD and overlap.
- [ ] **AlphaFold Integration**: Accept AlphaFold DB IDs or `.cif` file uploads — auto-convert CIF→PDB for Mustang.
- [ ] **Alignment Quality Score**: Per-structure confidence score (TM-score or GDT-TS) showing how well each structure fits the consensus.
- [ ] **CI/CD Pipeline**: GitHub Actions for `pytest`, `mypy`, and auto-deploy on merge to `main`.

---

**Status**: 📋 Roadmap Drafted — 29 items total  
**Target Branch**: `feat/v2.2-improvements`
