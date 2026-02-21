# v2.1 Roadmap & To-Do List

This document tracks all planned improvements, bug fixes, and feature requests for the **Mustang Pipeline v2.1** release.

## 🛠️ 1. Technical Debt & Code Cleanup (AI Suggestions)

_Based on a review of the v2.0 repository, here are areas we can optimize:_

- [ ] **Data Validation**: Replace raw dictionary parsing of `config.yaml` with **Pydantic** models. This will catch configuration errors immediately upon startup.
- [ ] **Async PDB Downloads**: Refactor the `PDBManager` to use `aiohttp` or `asyncio`. Currently, PDBs download sequentially. Fetching 20 proteins asynchronously will drastically reduce the "Data Prep" waiting time.
- [ ] **Decouple Pipeline Orchestration**: `src/frontend/analysis.py` is a 600+ line monolith handling both UI rendering and backend execution. We should extract the backend orchestration into a new `src/backend/coordinator.py` to achieve true MVC architecture.
- [ ] **Remove RMSD Code Duplication**: Both `mustang_runner.py` and `rmsd_calculator.py` contain redundant functions for parsing the Mustang output logs and matrices (`parse_mustang_log`, `_parse_rms_rot_file`). These should be consolidated exclusively into `rmsd_calculator.py`.
- [ ] **Remove Dead Bio3D Code**: Since we switched to purely native auto-compilation, all Fallback R/Bio3D execution logic inside `mustang_runner.py` is now dead code and should be aggressively deleted.
- [ ] **Expanded Test Coverage**: We built robust tests for `pdb_manager.py`. We need to expand this to cover `mustang_runner.py` and `rmsd_analyzer.py` to ensure core analysis algorithms never break.
- [ ] **Type Checking Enforcement**: We added type hints, but we should add a `mypy` check to the CI pipeline to enforce strict typing across `src/`.
- [ ] **Cache Management**: Improve `src/utils/` to handle persistent LRU caching for previously downloaded PDBs so we don't spam the RCSB servers.

## 🐞 2. Frontend Bugs & UX Issues (Audit Findings)

_Identified during the v2.0 repository audit:_

- [ ] **3D Viewer Flicker**: The 4-way structural superposition grid re-initializes all WebGL contexts on every state change. Implement a more stable state-locking mechanism to prevent flickering.
- [ ] **PDF Character Encoding**: `report_generator.py` uses Latin-1 encoding which fails on non-ASCII characters (e.g., Angstrom symbols or Greek letters). Switch to **UTF-8** capable fonts (e.g., DejaVuSans).
- [ ] **Sync Styling**: The Lab Notebook HTML export uses a hardcoded color palette. Refactor to inject the app's CSS variables (neon-blue/purple) directly into the template.
- [ ] **Ligand History Control**: Add a "Clear History" button to the Ligand Comparison tab to reset the similarity matrix without refreshing the entire app.
- [ ] **Responsive 3D Viewers**: The 3D viewports are fixed size (400x300). They should adapt to the container width for better visibility on smaller screens.
- [ ] **Global UI Settings**: Move harcoded visualization defaults (e.g., 'RdYlBu_r' colormap, 'cartoon' style) into `config.yaml` so they are globally configurable.
- [ ] **Terminal Auto-Cleanup**: The Bio-Terminal persists logs through the whole session; add a "Clear Terminal" utility.

## 🚀 3. Phase 3 Integration Prep (New Features)

_Setting the groundwork for Deep Structural Analytics._

- [ ] **Advanced Ligand Analysis**: Expand the ligand interaction metrics to calculate solvent-accessible surface area (SASA).
- [ ] **Dynamic 3D Exports**: Allow users to export `.gif` or rotating `.mp4` animations of the aligned structures directly from the 3Dmol viewer.

---

**Status**: 📝 Planning Phase
**Target Branch**: `dev-v2.1`
