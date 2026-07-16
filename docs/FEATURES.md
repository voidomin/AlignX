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
| 11c | Functional annotation for Compare-mode structures | SPA | [§2.12](#212-functional-annotation) |
| 12 | Structure-to-function discovery ("Discover" mode) | SPA | [§3](#3-discover-mode-structure-to-function) |
| 13 | Selectable Foldseek search databases (9 total) | SPA | [§3.1](#31-search-databases) |
| 14 | Multi-source annotation aggregation (6 sources) | SPA | [§3.2](#32-annotation-sources) |
| 15 | Confidence-gated function hypothesis | SPA | [§3.3](#33-confidence-gating) |
| 16 | Public / Student / Researcher detail levels | SPA | [§3.4](#34-detail-levels) |
| 17 | Self-hostable Foldseek backend | SPA | [§3.5](#35-self-hosted-search-backend) |
| 17a | 3D viewer for the searched structure in Discover mode | SPA | [§3.6](#36-3d-structure-viewer) |
| 17b | Ligand & binding-site inspector in Discover mode | SPA | [§3.7](#37-ligand--binding-site-inspector) |
| 18 | Configurable PDF report export | Both | [§4.1](#41-pdf-report) |
| 19 | Standalone HTML lab notebook export | Both | [§4.2](#42-html-notebook) |
| 20 | Discover HTML report / raw JSON export | SPA | [§4.3](#43-discover-export) |
| 21 | Run history with reload | Both | [§5.1](#51-run-history) |
| 21a | Shareable run links | SPA | [§5.1](#51-run-history) |
| 22 | Multi-user session isolation | Both | [§5.2](#52-session-isolation) |
| 23 | API key access control | SPA | [§6.1](#61-api-key-access-control) |
| 24 | Per-client job rate limiting | SPA | [§6.2](#62-rate-limiting) |
| 25 | Metal cofactor ligand recognition + Metal Coordination classification | Both | [§2.6](#26-ligand-hunter) |
| 26 | Heuristic candidate binding-pocket finder (no bound ligand needed) | Both | [§2.6](#26-ligand-hunter) |
| 27 | AlphaFold domain "Highlight in 3D" | SPA | [§2.12](#212-functional-annotation) |
| 28 | NMR ensemble / disordered-region metadata badges | SPA | [§1](#1-structure-input) |
| 29 | Ligand chemistry lookup (name/formula/SMILES/InChIKey) | SPA | [§2.6](#26-ligand-hunter) |
| 30 | Druggability volume estimate for candidate pockets | SPA | [§2.6](#26-ligand-hunter) |
| 31 | Contact maps & inter-structure difference-distance matrices | SPA | [§2.13](#213-contact-maps--difference-distance-matrices) |
| 32 | Real PDB-entry UniProt residue mapping ("Highlight in 3D" for real PDB entries) | SPA | [§2.12](#212-functional-annotation) |
| 33 | Mutation impact mapping + ClinVar clinical significance | SPA | [§2.14](#214-mutation-impact-mapping) |
| 34 | Literature links (PubMed/DOI) on structure cards | SPA | [§1](#1-structure-input) |
| 35 | Run notes & tags | Both | [§5.1](#51-run-history) |
| 36 | Bulk QC sweep across every loaded structure | SPA | [§2.15](#215-bulk-qc-sweep) |
| 37 | Documented public REST API (`/docs`) | Both | [§4.6](#46-rest-api) |
| 38 | Runnable Jupyter Notebook export | Both | [§4.2](#42-html-notebook) |
| 39 | True sequence-only MSA (EBI Clustal Omega) | SPA | [§2.8](#28-sequence-view) |
| 40 | True evolutionary conservation via homolog search (NCBI BLAST) | SPA | [§2.8](#28-sequence-view) |

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

Two extra warning badges appear when relevant: an **"NMR · N models"** badge for
a multi-model NMR ensemble (every analysis only ever looks at model 1 - the
badge makes that explicit instead of silently doing it with no indication),
and a **"N disordered regions"** badge when the deposited structure has gaps
in its own residue numbering (a region never resolved in the crystal
structure) — hover either for the specifics.

For a real PDB entry, a **"View publication"** link also appears when RCSB has
primary-citation data for it — a direct PubMed link when a PubMed ID is on
file, falling back to the DOI resolver otherwise. AlphaFold/SWISS-MODEL/ESM
Atlas structures have no citation concept and show no link.

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
**Salt Bridge**, **Van der Waals**, **Polar Contact**, or **Metal
Coordination** — based on donor/acceptor/charged-atom proximity (a
heavy-atom-only heuristic, since PDB files carry no hydrogens; this doesn't
attempt pi-stacking, which needs bond-order/aromaticity data a PDB file
doesn't provide). Catalytic/structural metal cofactors (Zn, Mg, Ca, Mn, Fe,
Cu, Ni, Co, Cd, Mo — e.g. a zinc-finger's Zn or a kinase's Mg) are recognized
as real ligands, not filtered out as generic ionic noise, and get their own
Metal Coordination classification at real coordination-bond distances.

When a run has two or more detected ligands, an interactive **binding-pocket
similarity matrix** (Jaccard index of pocket-residue composition) shows how
alike each ligand's chemical environment is to every other one in the run —
useful for spotting a conserved active site (or a surprisingly divergent one)
across otherwise-similar structures.

Select any detected ligand to see a **"what is this?"** chemistry line — its
real name, molecular formula, SMILES, and InChIKey, resolved from RCSB's
Chemical Component Dictionary and cached the same way GO terms already are.

**No bound ligand?** A heuristic **candidate binding-pocket finder** looks for
surface-exposed residues that spatially cluster with residues from a distant
part of the sequence (the standard signature of a fold packing together to
form a concave pocket wall), ranked by cluster size and hydrophobic/aromatic
content, plus a **convex-hull volume estimate** for each candidate. Every
result is explicitly labeled a computational prediction, not a validated
pocket or a validated volume (unlike a real geometric cavity detector such as
fpocket, which this doesn't attempt to replicate — a convex hull
over-estimates a true concave cavity, so treat it as a rough size signal, not
a measured one) — useful for AlphaFold/ESM Atlas structures, which essentially
never come with a co-crystallized ligand.

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

The default conservation highlighting is identity across whatever structures
you loaded, not a true evolutionary measure — labeled honestly as such. Two
background jobs (mirroring Discover mode's submit/poll/fetch job pattern) add
the real thing:

- **True sequence-only MSA** — a real multiple sequence alignment computed
  purely from each loaded structure's own sequence via EBI's Clustal Omega,
  independent of Mustang's structural alignment. Can legitimately disagree
  with it for divergent sequences that still share a similar fold.
- **True evolutionary conservation** — searches NCBI BLAST for real homologs
  of a selected structure's sequence and scores real per-position conservation
  (Shannon entropy) from their alignment. This is the longest-running job in
  the app (real BLAST searches commonly take minutes), genuinely different
  from the identity-across-loaded-structures default above.

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

### 2.12 Functional Annotation

*(SPA only)* Real InterPro domains, GO terms, and Reactome pathways for any
structure in a Compare-mode run — the same annotation sources Discover mode
already surfaces for structural neighbors, now available for the structures
you explicitly chose to align. Resolves each structure to a UniProt accession
by its source database (a live PDBe SIFTS lookup for a plain PDB ID; free for
AlphaFold/SWISS-MODEL IDs, which embed the accession directly) — ESM Atlas
structures have no UniProt mapping (uncharacterized, metagenomic) and show a
plain "no annotation available" message rather than an error. When 2 or more
structures in the run resolve an accession, a **shared across all structures**
summary lists exactly which domains/terms every one of them has in common —
useful for confirming a shared function isn't just a shared fold. STRING
interaction partners are not included (no source for the taxon ID this needs,
unlike Discover mode which gets one free from each Foldseek hit).

For an **AlphaFold-sourced structure**, each domain/feature gets a **"Highlight
in 3D"** button that jumps straight to its real residue range in the 3D
viewer — safe here specifically because AlphaFold models are numbered 1..N to
exactly match their source UniProt sequence, so InterPro's UniProt-numbered
positions are usable directly as real structure residue numbers.

A **real PDB entry** now gets working "Highlight in 3D" too, via a real
per-segment PDBe SIFTS residue mapping that translates each UniProt position
to that entry's own author residue numbering (which commonly differs —
crystallization constructs, non-1-start numbering, tags — so a naive 1:1
passthrough would highlight the wrong residues). This deliberately isn't
offered for Discover mode's neighbor-aggregated domains (a domain's position
in a structurally similar neighbor protein says nothing about where it'd fall
in the query's own numbering).

### 2.13 Contact Maps & Difference-Distance Matrices

In the Analytics tab's RMSD Matrix sub-tab: a real CA-CA **contact map** for
any one structure in the run (thresholded at 8Å), and a real
**difference-distance matrix** between any two structures over their commonly
aligned columns — reveals domain movements a single global RMSD number hides.
Computed on demand rather than stored with the run (a dense matrix for a large
structure can reach ~200MB), with an automatic sparse-list fallback above a
3000-residue/column cap.

### 2.14 Mutation Impact Mapping

In the Analytics tab's Annotations sub-tab: enter a chain, residue number, and
proposed substitution to map it onto the structure's real UniProt position,
see the real wild-type residue and gene, and — if a matching record exists —
the real **ClinVar clinical significance** of that substitution. Also surfaces
any already-known UniProt natural variant at that position. Builds on §2.12's
real residue mapping, so this works for real PDB entries as well as
AlphaFold-sourced structures.

### 2.15 Bulk QC Sweep

A **"Run QC on all"** button in the Workspace tab runs Ramachandran outlier
detection, secondary-structure assignment, and (for real PDB entries) wwPDB
validation across every loaded structure at once, with no alignment required
— a summary table (favored %, outlier count, %helix, clashscore per structure)
instead of clicking into each structure's card individually.

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

### 3.6 3D Structure Viewer

As soon as a Discover search resolves your structure, it renders directly in the
3D viewer — no need to also add it to Compare mode just to see what you searched.
Unlike Compare mode's superposition view, this shows your one structure as-is
(no re-alignment, no per-structure coloring scheme), so it also works for a
structure with no Foldseek hits at all.

### 3.7 Ligand & Binding-Site Inspector

If your searched structure has a bound ligand, a "Ligands & Binding Sites"
section lists it and shows the same real interaction-geometry classification
Compare mode's Ligand Hunter uses (Hydrogen Bond / Salt Bridge / Van der Waals /
Polar Contact / Metal Coordination per contact residue) — so a single
unaligned structure gets real binding-site analysis without needing a second
structure to compare against.

If it has **no** bound ligand — the common case for AlphaFold/ESM Atlas
predictions, which essentially never come with one — this section instead
offers the same heuristic candidate binding-pocket finder described in
§2.6, clearly labeled as a computational prediction rather than a validated
result, each with a "Highlight in 3D" button.

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

A separate **Jupyter Notebook** export (`.ipynb`) gives you a real, runnable
notebook instead of a static snapshot — its code cells re-fetch that run's
data live from the REST API (§4.6), so you can keep exploring the result
programmatically rather than just viewing a fixed report.

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

### 4.6 REST API

Every backend route is documented and explorable at `/docs` (FastAPI's own
Swagger UI) and machine-readable at `/openapi.json` — useful if you want to
script against StructScope directly instead of only using the UI, or want to
understand exactly what data the Jupyter export (§4.2) is re-fetching.

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

Every run can also carry free-text **notes and tags**, added or edited inline
from the History panel — stored in the run's existing metadata, so no new
run-level state to migrate.

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
