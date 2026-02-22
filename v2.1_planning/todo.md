# v2.1 Roadmap & To-Do List

This document tracks all planned improvements, bug fixes, and feature requests for the **Mustang Pipeline v2.1** release.

## 🛠️ 1. Technical Debt & Code Cleanup (AI Suggestions)

_Based on a review of the v2.0 repository, here are areas we can optimize:_

- [x] **Data Validation**: Replace raw dictionary parsing of `config.yaml` with **Pydantic** models. This catches configuration errors immediately upon startup.
- [x] **Async PDB Downloads**: Refactored the `PDBManager` to use `httpx` and `asyncio`. Fetching multiple proteins concurrently drastically reduces data prep time.
- [x] **Decouple Pipeline Orchestration**: `src/frontend/analysis.py` is a 600+ line monolith handling both UI rendering and backend execution. We should extract the backend orchestration into a new `src/backend/coordinator.py` to achieve true MVC architecture.
- [x] **Remove RMSD Code Duplication**: Both `mustang_runner.py` and `rmsd_calculator.py` contain redundant functions for parsing the Mustang output logs and matrices (`parse_mustang_log`, `_parse_rms_rot_file`). These should be consolidated exclusively into `rmsd_calculator.py`.
- [x] **Remove Dead Bio3D Code**: Since we switched to purely native auto-compilation, all Fallback R/Bio3D execution logic inside `mustang_runner.py` is now dead code and should be aggressively deleted.
- [ ] **Expanded Test Coverage**: We built robust tests for `pdb_manager.py`. We need to expand this to cover `mustang_runner.py` and `rmsd_analyzer.py` to ensure core analysis algorithms never break.
- [ ] **Type Checking Enforcement**: We added type hints, but we should add a `mypy` check to the CI pipeline to enforce strict typing across `src/`.
- [x] **Cache Management**: Improve `src/utils/` to handle persistent LRU caching for previously downloaded PDBs so we don't spam the RCSB servers.

## 🐞 2. Frontend Bugs & UX Issues (Audit Findings)

_Identified during the v2.0 repository audit:_

- [x] **3D Viewer Flicker**: The 4-way structural superposition grid re-initializes all WebGL contexts on every state change. Implement a more stable state-locking mechanism to prevent flickering.
- [x] **PDF Character Encoding**: `report_generator.py` uses Latin-1 encoding which fails on non-ASCII characters (e.g., Angstrom symbols or Greek letters). Switch to **UTF-8** capable fonts (e.g., DejaVuSans).
- [x] **Sync Styling**: The Lab Notebook HTML export uses a hardcoded color palette. Refactor to inject the app's CSS variables (neon-blue/purple) directly into the template.
- [x] **Ligand History Control**: Add a "Clear History" button to the Ligand Comparison tab to reset the similarity matrix without refreshing the entire app.
- [x] **Responsive 3D Viewers**: The 3D viewports are fixed size (400x300). They should adapt to the container width for better visibility on smaller screens.
- [x] **Automated Insights Staleness**: Insights were cached once per session and never regenerated for new runs. Fixed by keying regeneration to the current run ID.
- [x] **Mustang Alignment Robustness**: Implemented structural sanitization in `PDBManager` (residue renumbering, HYP→PRO mapping, forced ATOM records) and improved `MustangRunner` error handling for Exit Code 139 with actionable user feedback.
- [ ] **Global UI Settings**: Move harcoded visualization defaults (e.g., 'RdYlBu_r' colormap, 'cartoon' style) into `config.yaml` so they are globally configurable.
- [ ] **Terminal Auto-Cleanup**: The Bio-Terminal persists logs through the whole session; add a "Clear Terminal" utility.

## 🚀 3. Phase 3 Integration Prep (New Features)

_Setting the groundwork for Deep Structural Analytics._

- [ ] **Advanced Ligand Analysis**: Expand the ligand interaction metrics to calculate solvent-accessible surface area (SASA).
- [ ] **Dynamic 3D Exports**: Allow users to export `.gif` or rotating `.mp4` animations of the aligned structures directly from the 3Dmol viewer.

---

**Status**: ✅ v2.1 Bug Fixes Applied (Release Candidate)
**Target Branch**: `main`
