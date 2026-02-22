# v2.1 Roadmap & To-Do List

This document tracks all planned improvements, bug fixes, and feature requests for the **Mustang Pipeline v2.1** release.

## 🛠️ 1. Technical Debt & Code Cleanup (AI Suggestions)

_Based on a review of the v2.0 repository, here are areas we can optimize:_

- [x] **Data Validation**: Replace raw dictionary parsing of `config.yaml` with **Pydantic** models. This catches configuration errors immediately upon startup.
- [x] **Async PDB Downloads**: Refactored the `PDBManager` to use `httpx` and `asyncio`. Fetching multiple proteins concurrently drastically reduces data prep time.
- [x] **Decouple Pipeline Orchestration**: `src/frontend/analysis.py` is a 600+ line monolith handling both UI rendering and backend execution. We should extract the backend orchestration into a new `src/backend/coordinator.py` to achieve true MVC architecture.
- [x] **Remove RMSD Code Duplication**: Both `mustang_runner.py` and `rmsd_calculator.py` contain redundant functions for parsing the Mustang output logs and matrices (`parse_mustang_log`, `_parse_rms_rot_file`). These should be consolidated exclusively into `rmsd_calculator.py`.
- [x] **Remove Dead Bio3D Code**: Since we switched to purely native auto-compilation, all Fallback R/Bio3D execution logic inside `mustang_runner.py` is now dead code and should be aggressively deleted.
- [x] **Expanded Test Coverage**: Added `test_rmsd_analyzer.py` (9 tests: statistics, clustering, heatmap, Phylip export) and expanded `test_mustang_runner.py` (5 new tests: validation, Exit 139 messaging, .afasta standardization). Total: 27 unit tests passing.
- [x] **Type Checking Enforcement**: Added `mypy.ini` with permissive settings for gradual adoption. Targets `src/` with `check_untyped_defs` enabled.
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
- [x] **Global UI Settings**: Moved hardcoded `RdYlBu_r` colormap to `config.yaml` and wired it through `rmsd.py`. Added `viewer_default_style` to config.
- [x] **Terminal Auto-Cleanup**: Added "🗑️ Clear" button to the Bio-Terminal console expander that truncates the log file.

## 🚀 3. Phase 3 Integration Prep (New Features)

_Setting the groundwork for Deep Structural Analytics._

- [x] **Advanced Ligand Analysis (SASA)**: Added `calculate_sasa()` method to `LigandAnalyzer` using BioPython's ShrakeRupley algorithm. New "🌊 Surface Area" tab in the Ligand panel with total/per-chain metrics and per-residue Plotly bar chart.
- [x] **Dynamic 3D Exports**: Added "🎥 Export Spinning HTML" button that generates a self-contained HTML file with an auto-rotating 3Dmol.js viewer, and a "📄 Export Static PDB" button for downloading the aligned structure.

---

**Status**: ✅ v2.1 Complete
**Target Branch**: `main`
