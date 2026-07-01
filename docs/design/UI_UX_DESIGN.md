# Mustang Pipeline - UI/UX Design Documentation

## 1. CLI Interface Design

### Interactive Mode - Terminal UI

```
╔════════════════════════════════════════════════════════════════╗
║           🧬 Mustang Structural Alignment Pipeline            ║
║                    Interactive Setup Wizard                    ║
╚════════════════════════════════════════════════════════════════╝

📋 Step 1/5: Protein Selection
─────────────────────────────────────────────────────────────────
Select input method:
  [1] Enter PDB IDs manually
  [2] Load from file
  [3] Use example (GPCR Channelrhodopsins)

Your choice: 3

✓ Loaded 5 proteins: 4YZI, 3UG9, 7E6X, 7X86, 7E6Y


📥 Step 2/5: Downloading PDB Files
─────────────────────────────────────────────────────────────────
Downloading 4YZI... ████████████████████████████████ 100% 2.3 MB
Downloading 3UG9... ████████████████████████████████ 100% 1.8 MB
Downloading 7E6X... ████████████████████░░░░░░░░░░░░  60% 51.2 MB

⚠️  Warning: 7E6X is 85.3 MB (large file detected)

💡 Recommendation: Extract specific chain to reduce size
   Available chains: A, B, C

Select action:
  [1] Extract chain A only (recommended)
  [2] Keep all chains
  [3] Custom selection

Your choice: 1

✓ Will extract chain A from 7E6X
✓ All downloads complete (4.2s)


🧹 Step 3/5: Cleaning PDB Files
─────────────────────────────────────────────────────────────────
Removing waters and heteroatoms...
Processing 4YZI... ✓ (0.3s)
Processing 3UG9... ✓ (0.2s)
Processing 7E6X... ✓ (1.1s) - Extracted chain A, 85.3 MB → 8.2 MB
Processing 7X86... ✓ (0.4s)
Processing 7E6Y... ✓ (0.9s)

✓ Cleaned 5 structures


⚙️  Step 4/5: Running Mustang Alignment
─────────────────────────────────────────────────────────────────
Aligning 5 structures...
Progress ████████████████████████████████████░░░░  85%

Estimated time remaining: 12s

[Mustang output]
> Aligning 4YZI vs 3UG9... RMSD: 2.34 Å
> Aligning 4YZI vs 7E6X... RMSD: 3.12 Å
> Aligning 7E6X vs 7E6Y... RMSD: 0.89 Å

✓ Alignment complete (38.2s)
✓ RMSD matrix generated


📊 Step 5/5: Generating Reports
─────────────────────────────────────────────────────────────────
Creating RMSD heatmap... ✓
Building phylogenetic tree... ✓
Generating PyMOL visualization... ✓
Compiling HTML report... ✓

═══════════════════════════════════════════════════════════════

                    ✨ Analysis Complete! ✨

Results saved to: results/gpcr_channelrhodopsin_20260215/

📁 Output Files:
   ├─ report.html              Interactive HTML report
   ├─ rmsd_matrix.csv          RMSD values
   ├─ phylogenetic_tree.png    Tree visualization
   ├─ superposition.pse        PyMOL session
   └─ alignment/               Mustang outputs

🌐 Open report:
   file:///results/gpcr_channelrhodopsin_20260215/report.html

Next steps:
  • View HTML report in browser
  • Open PyMOL session for 3D exploration
  • Share results/ folder with collaborators

═══════════════════════════════════════════════════════════════
```

### Quick Mode - Simple One-Liner

```
$ python main.py --pdb-ids 4YZI,3UG9,7E6X,7X86,7E6Y

🧬 Mustang Pipeline v1.0

Downloading... ████████████████████████████████████ 100% 5/5
Cleaning...    ████████████████████████████████████ 100% 5/5
Aligning...    ████████████████████████████████████ 100% (38s)
Analyzing...   ████████████████████████████████████ 100%
Reporting...   ████████████████████████████████████ 100%

✓ Complete! Open: results/report.html
```

---

## 2. HTML Report Design

### Layout Structure

```
┌───────────────────────────────────────────────────────────────┐
│                         HEADER BAR                            │
│  🧬 Structural Alignment Analysis Report                     │
│     GPCR Channelrhodopsins                                   │
├─────────────┬─────────────────────────────────────────────────┤
│             │                                                 │
│  SIDEBAR    │              MAIN CONTENT                       │
│             │                                                 │
│ • Summary   │  ┌──────────────────────────────────────────┐  │
│ • RMSD      │  │       📊 Analysis Summary                │  │
│ • Trees     │  │                                          │  │
│ • 3D View   │  │  • Proteins analyzed: 5                  │  │
│ • Downloads │  │  • Average RMSD: 2.34 Å                  │  │
│             │  │  • Clusters identified: 2                │  │
│             │  │  • Analysis date: 2026-02-15             │  │
│             │  └──────────────────────────────────────────┘  │
│             │                                                 │
│             │  ┌──────────────────────────────────────────┐  │
│             │  │       🔥 RMSD Heatmap                    │  │
│             │  │                                          │  │
│             │  │         4YZI  3UG9  7E6X  7X86  7E6Y     │  │
│             │  │  4YZI   0.00  2.34  3.12  2.98  3.45     │  │
│             │  │  3UG9   2.34  0.00  2.87  2.56  2.91     │  │
│             │  │  7E6X   3.12  2.87  0.00  1.23  0.89     │  │
│             │  │  7X86   2.98  2.56  1.23  0.00  1.45     │  │
│             │  │  7E6Y   3.45  2.91  0.89  1.45  0.00     │  │
│             │  │                                          │  │
│             │  │  [Colorful gradient: blue→green→red]     │  │
│             │  │   Low RMSD ←──────────→ High RMSD        │  │
│             │  └──────────────────────────────────────────┘  │
│             │                                                 │
│             │  ┌──────────────────────────────────────────┐  │
│             │  │       🌳 Phylogenetic Tree               │  │
│             │  │                                          │  │
│             │  │         ┌─── 7E6X (4ms)                  │  │
│             │  │     ┌───┤                                │  │
│             │  │     │   └─── 7E6Y (1μs)                  │  │
│             │  │  ───┤                                    │  │
│             │  │     └─────── 7X86                        │  │
│             │  │                                          │  │
│             │  │  ─────────── 4YZI                        │  │
│             │  │                                          │  │
│             │  │  ─────────── 3UG9                        │  │
│             │  │                                          │  │
│             │  │  Branch lengths = RMSD distances         │  │
│             │  └──────────────────────────────────────────┘  │
│             │                                                 │
│             │  ┌──────────────────────────────────────────┐  │
│             │  │       🧬 Structural Superposition        │  │
│             │  │                                          │  │
│             │  │  [3D visualization image:                │  │
│             │  │   5 colorful protein ribbons overlaid,   │  │
│             │  │   rotatable protein structure view]      │  │
│             │  │                                          │  │
│             │  │  Color legend:                           │  │
│             │  │  🔵 4YZI  🟢 3UG9  🔴 7E6X               │  │
│             │  │  🟡 7X86  🟣 7E6Y                        │  │
│             │  └──────────────────────────────────────────┘  │
│             │                                                 │
│             │  ┌──────────────────────────────────────────┐  │
│             │  │       📥 Download Results                │  │
│             │  │                                          │  │
│             │  │  [Button] RMSD Matrix (CSV)              │  │
│             │  │  [Button] Phylogenetic Tree (Newick)     │  │
│             │  │  [Button] PyMOL Session (.pse)           │  │
│             │  │  [Button] Full Report (PDF)              │  │
│             │  └──────────────────────────────────────────┘  │
│             │                                                 │
└─────────────┴─────────────────────────────────────────────────┘
```

### Color Scheme

**Primary Colors:**

- Background: Clean white (#FFFFFF)
- Cards: Light gray (#F8F9FA)
- Accents: Scientific blue (#2196F3)
- Success: Green (#4CAF50)
- Warning: Amber (#FFC107)

**Heatmap Gradient:**

- Low RMSD (similar): Blue (#0D47A1)
- Medium RMSD: Green/Yellow (#FDD835)
- High RMSD (different): Red (#D32F2F)

### Responsive Features

- Mobile-friendly collapsible sidebar
- Touch-friendly buttons
- Zoom/pan on visualizations
- Print-optimized stylesheet
- Accessible (WCAG 2.1 AA compliant)

---

## 3. Design Principles

## 2. Web Interface (Streamlit)

The implemented solution uses a modern Streamlit web application.

### Layout Overview

**Sidebar (Setup & Configuration)**

- **Status Checks**: Verifies Mustang installation.
- **Input Method**: Manual Entry, Load Example, or File Upload.
- **Advanced Options**: Chain selection (Auto vs Manual), filtering settings.

**Main Dashboard (Tabs)**

1.  **📈 RMSD Analysis**:
    - Heatmap of pairwise RMSD.
    - Statistical summary (Mean, Median, Std Dev).
    - Residue-Level RMSF Plot (Line chart of flexibility).
2.  **🌳 Phylogenetic Tree**:
    - UPGMA tree visualization.
    - Evolutionary relationship interpretation.

3.  **🧬 3D Visualization**:
    - Interactive Mol/Py3Dmol viewer.
    - Superimposed structures.
    - Chain-based coloring.

4.  **🔍 Clusters**:
    - Grouping proteins by structural similarity threshold.

5.  **🧬 Sequences**:
    - Interactive Multiple Sequence Alignment (MSA).
    - Conservation coloring (Red=Identity, Yellow=Similar).

6.  **📁 Downloads**:
    - Download all results as ZIP.
    - **Generate PDF Report**: Comprehensive summary document.

### UX Flow

1.  **Input**: User selects "Load Example" -> "GPCRs".
2.  **Process**: Clicks "Run Analysis". Progress bar shows 4 steps (Download, Clean, Align, Analyze).
3.  **Result**: Tabs unlock, balloons animation plays.
4.  **Explore**: User switches tabs to view different data angles.
5.  **Export**: User generates PDF report for publication.

### CLI Design

✓ **Clear progress indication** - Users always know what's happening
✓ **Helpful warnings** - Proactive suggestions for large files
✓ **Colorful feedback** - Green=success, yellow=warning, red=error
✓ **Time estimates** - Know how long to wait
✓ **Error recovery** - Resume from checkpoints

### Report Design

✓ **Scannable** - Quick overview in summary cards
✓ **Interactive** - Hover tooltips on heatmap cells
✓ **Print-ready** - Professional PDF export
✓ **Self-contained** - All images embedded, no external deps
✓ **Shareable** - Single HTML file can be emailed

---

## 4. User Flows

### Flow 1: First-Time User

1. Run interactive mode → Wizard guides setup
2. Choose from examples → Pre-configured GPCR analysis
3. Watch progress → Clear status at each step
4. View report → Results automatically open in browser
5. Share → Download PDF or share results folder

### Flow 2: Power User

1. Write config YAML → Define all parameters
2. Run batch mode → Process multiple protein families
3. Automated pipeline → No interaction needed
4. CI/CD integration → Automated analysis in research pipeline

### Flow 3: Recovery from Failure

1. Pipeline crashes → Checkpoint saved
2. Re-run with --resume → Picks up where it left off
3. Skip completed steps → Only re-run failed stage
4. Complete successfully → Full results generated
