# StructScope Feature Guide

A complete, user-facing reference for every capability StructScope ships today —
what it does, how to use it, and which interface(s) it's available in. If you're
trying to confirm "does it do X" before relying on it, this is the doc to check.

StructScope has two interfaces on one shared analysis engine:

| Interface | Best for |
|---|---|
| **Vite + FastAPI SPA** | The full feature set — everything in this document. |
| **Streamlit App** | The core Compare workflow only, currently the one deployed publicly. |

Every feature below is marked **SPA** (SPA only) or **Both** so you know exactly
what to expect from whichever interface you're using.

---

## Feature checklist

Use this table as a quick audit of what's available. Jump to the linked section
for how to actually use each one.

| # | Feature | Interface | Section |
|---|---|---|---|
| 1 | Multi-source structure input (PDB, AlphaFold, SWISS-MODEL, ESM Atlas) | SPA | [§1](#1-structure-input) |
| 1a | Paste multiple structure IDs at once | SPA | [§1.1](#11-batch-id-input) |
| 1b | Upload your own .pdb/.ent/.cif file | SPA | [§1.2](#12-custom-structure-upload) |
| 2 | N-structure alignment (2 or more at once) | Both | [§2.1](#21-n-structure-alignment) |
| 3 | Interactive 3D viewer with per-structure coloring | Both | [§2.2](#22-3d-structure-viewer) |
| 4 | Residue highlighting in the 3D viewer | Both | [§2.2](#22-3d-structure-viewer) |
| 5 | RMSD heatmap matrix | Both | [§2.3](#23-rmsd-heatmap) |
| 6 | Structural clustering (hierarchical, RMSD-threshold) | Both | [§2.4](#24-structural-clustering) |
| 7 | Batch comparison against a past run | Both | [§2.5](#25-batch-comparison) |
| 8 | Ligand Hunter (binding pockets, SASA, interaction similarity) | Both | [§2.6](#26-ligand-hunter) |
| 9 | Interactive phylogenetic tree (UPGMA) | Both | [§2.7](#27-phylogenetic-tree) |
| 10 | Sequence identity / conservation view | Both | [§2.8](#28-sequence-view) |
| 11 | Dashboard (aggregate stats, recent activity) | SPA | [§2.9](#29-dashboard) |
| 11a | Alignment quality metrics (Ramachandran, TM-score/GDT-TS) | Both | [§2.10](#210-alignment-quality-metrics) |
| 11b | Protein-protein interface analysis | SPA | [§2.11](#211-protein-protein-interfaces) |
| 12 | Structure-to-function discovery ("Discover" mode) | SPA | [§3](#3-discover-mode-structure-to-function) |
| 13 | Selectable Foldseek search databases (9 total) | SPA | [§3.1](#31-search-databases) |
| 14 | Multi-source annotation aggregation (6 sources) | SPA | [§3.2](#32-annotation-sources) |
| 15 | Confidence-gated function hypothesis | SPA | [§3.3](#33-confidence-gating) |
| 16 | Public / Student / Researcher detail levels | SPA | [§3.4](#34-detail-levels) |
| 17 | Self-hostable Foldseek backend | SPA | [§3.5](#35-self-hosted-search-backend) |
| 18 | Configurable PDF report export | Both | [§4.1](#41-pdf-report) |
| 19 | Standalone HTML lab notebook export | Both | [§4.2](#42-html-notebook) |
| 20 | Discover HTML report / raw JSON export | SPA | [§4.3](#43-discover-export) |
| 21 | Run history with reload | Both | [§5.1](#51-run-history) |
| 21a | Shareable run links | SPA | [§5.1](#51-run-history) |
| 22 | Multi-user session isolation | Both | [§5.2](#52-session-isolation) |
| 23 | API key access control | SPA | [§6.1](#61-api-key-access-control) |
| 24 | Per-client job rate limiting | SPA | [§6.2](#62-rate-limiting) |

---

## 1. Structure Input

Add structures from **four databases**, mixed freely in the same run, by typing an
ID into the workspace — no manual downloading:

| Source | ID format | Example |
|---|---|---|
| RCSB PDB | 4-character code | `4RLT` |
| AlphaFold DB | `AF-{UniProt}-F{fragment}` | `AF-P69905-F1` |
| SWISS-MODEL Repository | `SM-{UniProt}` | `SM-P69905` |
| ESM Metagenomic Atlas | `ESM-{MGYP accession}` | `ESM-MGYP002537940442` |

Each structure you add shows its source database and available metadata (method,
resolution, organism) directly in the workspace list, so it's clear what you're
about to analyze and how much confidence to place in it. After adding a structure,
pick which chain to use if it has more than one — StructScope lists every chain
with its residue count so you're not guessing.

*(SPA only for now — Streamlit currently only accepts plain RCSB PDB IDs.)*

### 1.1 Batch ID Input

Instead of adding structures one at a time, click "Paste multiple IDs" to reveal a
text box — paste a comma-, space-, or newline-separated list (mixing sources freely,
e.g. `4RLT, 3UG9, AF-P69905-F1`) and click **Add All**. You'll get a clear summary of
what was added, what was already in the workspace, and what wasn't recognized, so a
typo in a 20-ID paste doesn't silently vanish. Capped at 20 structures per workspace.

### 1.2 Custom Structure Upload

Click "Upload a structure file" to add your own `.pdb`, `.ent`, or `.cif` file instead
of fetching one of the four public databases by ID — useful for an unpublished
structure, your own AlphaFold output, or anything without a public accession.
StructScope actually validates the file parses as a real structure before accepting
it, so a bad upload fails clearly with a reason instead of producing a confusing error
later. Uploaded structures show an "Uploaded" badge and their original filename, and
work in every downstream feature (alignment, clustering, ligand hunting, export)
exactly like a fetched structure would.

---

## 2. Compare Mode

The core workflow: align two or more structures and analyze how they relate.

### 2.1 N-Structure Alignment

Superimpose **two or more** structures in a single run using Mustang. The 3D
viewer, legend, and pairwise RMSD list all scale automatically to however many
structures you added — this isn't a fixed pairwise tool.

### 2.2 3D Structure Viewer

An embedded, interactive 3Dmol.js viewer shows every aligned structure overlaid,
each in a distinct color with a legend identifying which is which. Click a
residue in the sequence view to highlight it in 3D. Drag to rotate, scroll to
zoom, and the initial auto-rotate stops itself after a few seconds (or the moment
you interact) so it never keeps spinning in the background.

For AlphaFold- or ESM Atlas-sourced structures in the run, a **pLDDT confidence
coloring** toggle recolors that structure by its real per-residue prediction
confidence (a red-to-blue gradient, scaled to whatever range is actually present
— AlphaFold's 0-100 scale and ESM Atlas's 0-1 fraction are both handled without
needing to know which one you're looking at). The toggle is disabled when no
structure in the run is a predicted model, since experimentally-determined
structures don't carry this kind of per-residue confidence score.

### 2.3 RMSD Heatmap

A Plotly-powered heatmap of pairwise RMSD values across every structure in the
run, with a selectable colormap — read structural similarity/divergence at a
glance instead of scanning a raw number table.

### 2.4 Structural Clustering

Group the structures in a run into families using interactive, RMSD-threshold
hierarchical (average-linkage) clustering — drag the threshold and watch the
cluster groupings update live. Useful once you're aligning more than a
handful of structures and want to see natural groupings rather than one flat list.

### 2.5 Batch Comparison

Pick any past run from your history and diff its RMSD matrix against your
current run, to see exactly how structural relationships shifted between the two
— e.g. did adding a new structure change which pairs cluster together.

### 2.6 Ligand Hunter

For any structure in the run (not just the first), auto-detect bound ligands and
their binding pockets, calculate cross-structure interaction similarity, and
visualize SASA (Solvent Accessible Surface Area) for the pocket-lining residues.
Switch the structure picker to refresh the ligand list and interaction view for
a different member of the run.

Each contact residue is classified by real geometry — **Hydrogen Bond**,
**Salt Bridge**, **Van der Waals**, or **Polar Contact** — based on
donor/acceptor/charged-atom proximity (a heavy-atom-only heuristic, since PDB
files carry no hydrogens; this doesn't attempt pi-stacking or metal
coordination, both of which need chemistry data a PDB file doesn't provide).

When a run has two or more detected ligands, an interactive **binding-pocket
similarity matrix** (Jaccard index of pocket-residue composition) shows how
alike each ligand's chemical environment is to every other one in the run —
useful for spotting a conserved active site (or a surprisingly divergent one)
across otherwise-similar structures.

### 2.7 Phylogenetic Tree

An interactive structural phylogenetic tree (UPGMA/average-linkage) built from
the RMSD matrix — a visual family tree of how the aligned structures relate
evolutionarily/structurally.

### 2.8 Sequence View

Aligned sequences with per-position conservation highlighting, so you can see at
a glance which residues are conserved across every structure in the run versus
which vary.

**Motif search** lets you search the alignment for a specific residue pattern
(e.g. `RYY`, `G.G`, `G-X-P` — `X`/`.`/`-` act as single-residue wildcards),
see every match across every structure in a table, and jump straight to a
**"Highlight Motif in 3D Viewer"** button that selects every matched residue
across all aligned structures at once.

### 2.9 Dashboard

*(SPA only)* Aggregate stats across everything you've run — total runs, proteins
analyzed, cache size — plus recent activity and one-click quick-start examples for
getting oriented fast.

### 2.10 Alignment Quality Metrics

The Analytics tab's Quality panel reports two independent signals for how
trustworthy an alignment is: a **Ramachandran score** (percentage of residues in
favored phi/psi torsion regions, with an outlier list) computed per structure,
and a **TM-score / GDT-TS table** — standard structural-alignment quality
metrics (each structure's score averaged against every other structure in the
run) that flag whether structures are a genuinely strong match or only loosely
superposed despite a low RMSD.

### 2.11 Protein-Protein Interfaces

*(SPA only)* For any multi-chain structure in the run (e.g. a hemoglobin
tetramer's four subunits), pick two chains and find every contact residue
between them — the same real geometry-based classification Ligand Hunter uses
(Hydrogen Bond / Salt Bridge / Van der Waals / Polar Contact) — plus a **buried
interface area** (total ΔSASA: each chain's solvent-accessible surface area
alone, minus the complex's, the standard way interface size is reported).
Operates on the structure's original, pre-alignment file, so it works even
though Mustang itself only ever aligns one chain per structure.

---

## 3. Discover Mode: Structure-to-Function

*(SPA only)* Have one structure and no idea what it does? Discover mode answers
*"what is this?"* for a single, unannotated structure — useful for predicted
structures (AlphaFold, ESM Atlas) with no known function yet, since 3D fold is
conserved far longer than sequence, so this finds real connections that a plain
sequence search would miss.

### 3.1 Search Databases

Searches your structure against Foldseek's structural-neighbor databases.
Defaults to **PDB + AlphaFold DB**, but an expandable picker exposes all **9**
supported databases (SwissProt/Proteome AFDB subsets, CATH, BFVD, BFMD, GMGC,
MGnify/ESM Atlas). Only MGnify/ESM Atlas is marked as "structural hits only, no
functional annotation" — so it's always clear upfront what a given database will
and won't tell you.

### 3.2 Annotation Sources

Once structural neighbors are found, StructScope pulls real functional annotation
data from **six sources**:

- **InterPro** — protein domains and families
- **QuickGO** — Gene Ontology terms
- **STRING** — known protein-protein interaction partners
- **Reactome** — pathway membership
- **PDBe SIFTS** — resolves PDB/CATH hits to a UniProt accession
- **GMGC** — resolves microbial gene-catalog hits directly to Pfam domains

All of these are aggregated into a single domain/GO-term consensus rather than
shown as six disconnected lists.

### 3.3 Confidence Gating

A neighbor's annotations only count toward the final function hypothesis if that
neighbor's own structural-match probability also clears a configurable threshold
(default 0.5) — having annotation data available isn't enough on its own if the
structural match that found it was weak. This keeps the headline result honest.

### 3.4 Detail Levels

The same result renders at **three depths** depending on who's reading it:

- **Public** — plain-language summary, explicit uncertainty framing, no jargon.
- **Student** — a guided explanation of *why* the match suggests that function.
- **Researcher** — raw hit tables, match probabilities, the full unfiltered
  domain/GO-term list, and a high-confidence-neighbor count.

Switch between them at any time without re-running the search.

### 3.5 Self-Hosted Search Backend

Defaults to the public Foldseek API (shared, rate-limited across all users). For
heavier use, `foldseek.backend: local` in `config.yaml` switches to a local
Foldseek binary and search database you provision yourself — no code changes
needed, just configuration.

Discover runs are cached (annotation lookups default to a 30-day TTL) and appear
in your Dashboard/History alongside Compare runs with a distinct `DISCOVER` badge.

---

## 4. Export

### 4.1 PDF Report

Generate a PDF report from any completed run, choosing exactly which sections to
include — summary, insights, heatmap, phylogenetic tree, RMSD matrix — instead of
always exporting everything.

### 4.2 HTML Notebook

A standalone, self-contained HTML export with an embedded 3D viewer and every
analysis figure baked in — open it in any browser, no server or install required,
useful for sharing a result with someone who doesn't have StructScope running.

### 4.3 Discover Export

*(SPA only)* Export a completed Discover run as a standalone HTML report or raw
JSON — the same export parity Compare mode has always had.

### 4.4 Raw Data Exports

Download the underlying RMSD matrix as a plain CSV, the RMSD heatmap as a raw
PNG image, or the phylogenetic tree as a standard Newick file — for pulling
numbers into your own analysis, dropping a figure straight into a slide deck,
or opening the tree in a dedicated phylogenetics tool, without generating a
full report.

### 4.5 Download Everything

One button bundles every generated artifact for a run — the aligned PDB and
FASTA, the RMSD matrix CSV, the heatmap PNG, and an auto-generated lab
notebook HTML — into a single ZIP download.

---

## 5. History & Sessions

### 5.1 Run History

Every completed run (Compare or Discover) is saved and browsable from the History
tab. Reopening a past run restores its full state — 3D view, stats, every tab —
exactly as it was when the run finished.

Delete a single run, or clear your entire history at once, directly from the
History tab — both ask for confirmation first, and neither is undoable.

*(SPA only)* Click **Share** on any run to copy a link to it. Anyone who opens that
link — no account, no session, nothing else required — sees exactly that run's
results in a read-only view with a clear banner. This is intentionally
world-readable by anyone who has the link (not gated by an extra "make shareable"
step): a run's ID is long and random enough that it can't practically be guessed,
so having the link *is* the access control.

### 5.2 Session Isolation

Results and history are scoped per session, so multiple people can use the same
deployment at once without seeing each other's runs — safe for shared or
stateless deployments out of the box.

---

## 6. Access Control *(relevant if you're self-hosting)*

### 6.1 API Key Access Control

Set `ALIGNX_API_KEY` and every API route, generated report/notebook, and
downloaded structure file requires it (via an `X-API-Key` header or `?api_key=`
link parameter) — locks the deployment down for anyone without the key. Left
unset by default so local development works with zero configuration.

### 6.2 Rate Limiting

Job-submission endpoints (starting a new alignment or Discover search) are
rate-limited per API key (or per IP if no key is set), so one client can't queue
unlimited compute-heavy jobs and starve everyone else on a shared deployment.

### 6.3 Settings

*(SPA only)* A Settings tab lets you change the Mustang execution backend and
timeout, the max proteins/file size limits, the default heatmap colormap, and
the default 3D viewer style — no `config.yaml` editing or restart required.
Changes apply immediately to every subsequent run, and affect every user of
the deployment (this is a deployment-wide setting, not a per-session one).

---

## What's next

This document covers what's shipped today. v4 (custom structure upload, batch ID
input, shareable run links) is complete — see [docs/ROADMAP_V4.md](ROADMAP_V4.md)
for that history, including one real open item found along the way:
`/api/history`'s response payload growing unbounded as run count/figure data
accumulates, which is worth a real pagination fix before heavy multi-session use.
