# StructScope — Complete User Guide

*A deep, scientist-facing reference for everything StructScope does today: what
each capability means biologically, when to reach for it, how to read the
result, and a real worked example wherever one adds clarity. If `docs/FEATURES.md`
is the developer-facing capability checklist, this is the document to actually
learn and use the app from.*

StructScope has two interfaces sharing one backend: a full-featured **Vite +
FastAPI SPA** (everything in this guide) and a **Streamlit app** covering only
the core Compare workflow. Unless a section says otherwise, assume it's SPA-only
— the Streamlit app is the one currently deployed publicly for the basic
alignment workflow, but the SPA is where active development happens and where
every capability below actually lives.

**Live app:** https://align-x-xi.vercel.app/

### Where to find things: the tab map

Every section below names the real tab it lives in. If you're looking at the
running app right now, this is the quickest orientation:

| Tab (SPA nav) | What it's for | Guide section |
|---|---|---|
| **Workspace** | Add/upload/predict structures, run alignment, bulk QC | §2, §4.9 |
| **Ligands** | Binding sites, pockets, chemistry lookup | §6 |
| **Sequence** | Identity view, motif search, true MSA, true conservation | §5 |
| **Analytics** | Quality metrics, PAE, contact maps, annotation, mutations, insights | §4, §8.1, §9 |
| **Clusters** | RMSD-threshold structural families | §3 |
| **Diff Runs** (Compare) | Diff the current run against a past one | §3.6 |
| **History** | Past runs, sharing, notes/tags, cross-run trend | §10 |
| **Dashboard** | At-a-glance stats, recent activity, quick-start examples | §1 |
| **Settings** | Deployment-wide configuration (self-hosting) | §12 |

**A note on the two interfaces**: sections below apply to the **SPA**
(everything) unless marked `(SPA only)`. The **Streamlit app** — the one
currently deployed publicly for the basic workflow — covers only §3.1–§3.5,
§4.1–§4.2, §6 (minus druggability/chemistry lookup), §7, and §11's PDF/HTML
exports. Streamlit also only accepts **plain RCSB PDB IDs** — none of the
other three structure sources (AlphaFold, SWISS-MODEL, ESM Atlas), upload, or
sequence prediction from §2 are available there. Everything else in this
guide (Discover mode, mutation mapping, PAE/AlphaMissense, true MSA/
conservation, sharing, Dashboard, webhooks, and prediction from a sequence)
is SPA-only.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Adding Structures to Your Workspace](#2-adding-structures-to-your-workspace)
3. [Comparing Multiple Structures](#3-comparing-multiple-structures)
4. [Judging Whether You Can Trust a Structure](#4-judging-whether-you-can-trust-a-structure)
5. [Sequence-Level Analysis](#5-sequence-level-analysis)
6. [Ligand & Binding Site Analysis](#6-ligand--binding-site-analysis)
7. [Protein-Protein Interfaces](#7-protein-protein-interfaces)
8. [Functional Annotation & "What Does This Do?"](#8-functional-annotation--what-does-this-do) `(SPA only)`
9. [Mutations: ClinVar, AlphaMissense, gnomAD & REVEL](#9-mutations-clinvar-alphamissense-gnomad--revel) `(SPA only)`
10. [History, Sharing, Notes & Sessions](#10-history-sharing-notes--sessions)
11. [Exporting & Sharing Results](#11-exporting--sharing-results)
12. [Settings & Access Control](#12-settings--access-control) `(SPA only)`
13. [Interpreting the Numbers — Quick Reference](#13-interpreting-the-numbers--quick-reference)
14. [Glossary](#14-glossary)
15. [FAQ & Troubleshooting](#15-faq--troubleshooting)
16. [Appendix: Full Feature Index](#16-appendix-full-feature-index)

---

## 1. Getting Started

The fastest way to understand StructScope is to run one real comparison end to
end. This walkthrough uses two structures of the same real protein — human
hemoglobin's alpha chain — solved two different ways, so you can see the whole
pipeline produce a real, checkable result.

1. Open the **Workspace** tab (the default landing tab).
2. Type `4HHB` into the ID box and click **Add** — this is the real,
   experimentally-solved human hemoglobin structure from RCSB PDB.
3. Type `AF-P69905-F1` and **Add** it too — this is AlphaFold's own predicted
   structure of the same protein's alpha chain.
4. Both cards now show their source, method, and resolution/confidence — you
   can already see at a glance that one is X-ray (a real resolution in Å) and
   one is a prediction (pLDDT-scored, no resolution).
5. Click **Run Structural Alignment**. Mustang superimposes both structures;
   the 3D viewer on the right fills in with both overlaid in distinct colors.
6. Switch to the **Analytics** tab. The Quality sub-tab now shows a real RMSD
   and an independent TM-score for the pair — a direct, numeric answer to "how
   good is this prediction, really."
7. From here, every other tab (Ligands, Sequence, Clusters) is already
   populated for this same run — nothing to re-fetch or re-configure.

If you only have one structure and no interest in aligning it against
anything yet, you don't need 2+ to get value: a single structure alone still
gets a 3D preview, functional annotation (§8), ligand/pocket analysis (§6),
mutation mapping (§9), and bulk QC (§4) — alignment-specific results (RMSD,
clustering, phylogeny) are the only things that genuinely need a second
structure.

### 1.1 The Dashboard: your at-a-glance home base

*(SPA only)* Once you've run a few things, the **Dashboard** tab gives you
aggregate stats across everything you've done — total runs, total proteins
analyzed, cache size — plus a feed of recent activity and the same one-click
quick-start examples available from an empty Workspace, for getting oriented
fast without retyping IDs you use often.

---

## 2. Adding Structures to Your Workspace

### 2.1 The four structure databases

Type an ID into the Workspace tab's input box — sources can be freely mixed
within the same run:

| Source | ID format | Example | What it actually is |
|---|---|---|---|
| RCSB PDB | 4-character code | `4RLT` | A real, experimentally solved structure (X-ray, cryo-EM, or NMR) |
| AlphaFold DB | `AF-{UniProt}-F{fragment}` | `AF-P69905-F1` | A predicted structure, one entry per UniProt protein (or fragment, for very long ones) |
| SWISS-MODEL Repository | `SM-{UniProt}` | `SM-P69905` | A homology-modeled structure built from a related solved template |
| ESM Metagenomic Atlas | `ESM-{MGYP accession}` | `ESM-MGYP002537940442` | A predicted structure for an uncharacterized, metagenomic ("dark matter") protein sequence |

After adding a structure, StructScope lists every chain it contains with its
residue count, so picking the right one for a multi-chain entry isn't a guess.

### 2.2 Reading a structure's card correctly

Each card in the Workspace shows real metadata pulled at add-time, plus a
handful of badges that only appear when relevant:

- **NMR · N models** — this entry is a multi-model NMR ensemble. Every
  analysis in StructScope only ever looks at model 1; this badge exists so
  that fact is visible rather than silently true.
- **N disordered regions** — the deposited structure has a genuine gap in its
  own residue numbering (a region that was never resolved experimentally).
  Hover the badge for exactly which residues.
- **View publication** — a direct PubMed or DOI link from RCSB's own citation
  record, when one exists. AlphaFold/SWISS-MODEL/ESM Atlas entries have no
  citation concept and show nothing here.
- **CATH classification** (e.g. "CATH 1.10.490.10") — a standardized
  fold-family label, independent of anything StructScope itself computed.
  Real PDB entries only.
- **Assembly state** (e.g. "Tetrameric") — the real biological assembly RCSB
  has on file for this entry. Real PDB entries only.

### 2.3 Adding many structures at once

Click **"Paste multiple IDs"** to reveal a text box — paste a comma-, space-,
or newline-separated list mixing any of the four sources freely (e.g. `4RLT,
3UG9, AF-P69905-F1`) and click **Add All**. You'll get an explicit summary of
what was added, what was already present, and what wasn't recognized, so one
typo in a long paste doesn't silently disappear. Capped at 20 structures per
workspace.

### 2.4 Bringing your own file

Click **"Upload a structure file"** for a `.pdb`, `.ent`, or `.cif` you have
locally — an unpublished structure, your own modeling output, or anything
without a public accession at all. The file is actually parsed and validated
before being accepted, so a malformed upload fails immediately with a real
reason instead of surfacing a confusing error two steps later. An uploaded
structure works identically to a fetched one in every downstream feature.

### 2.5 Predicting a structure from nothing but a sequence

Click **"Predict from sequence"** if you have no accession at all — just a raw
amino-acid sequence (10–300 residues). This calls ESM Atlas's real ESMFold
model directly and returns a genuinely predicted 3D structure, typically in a
few seconds to under a minute. The result becomes a normal workspace member
immediately: alignment, ligand hunting, mutation mapping, and every export all
work on it exactly like anything fetched from a public database. Sequences
longer than 300 residues are rejected upfront rather than left to silently
time out against the public prediction service's own limit.

**Try it**: paste this real human hemoglobin alpha-chain sequence (141
residues) and click Predict Structure —

```
MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR
```

---

## 3. Comparing Multiple Structures

### 3.1 N-structure alignment

Add two or more structures and click **Run Structural Alignment** — Mustang
superimposes all of them in one pass, not just a fixed pair. The 3D viewer,
legend, and pairwise RMSD list all scale automatically to however many you
added.

### 3.2 The 3D viewer

Every aligned structure renders overlaid, each in a distinct color with a
legend identifying which is which. Drag to rotate, scroll to zoom. The
initial auto-rotate stops itself after a few seconds or the moment you
interact with it. Click any residue in the **Sequence** tab's alignment grid
to highlight that exact position in the 3D viewer — the fastest way to go
from "this residue looks conserved" to "here's exactly where it sits in
space."

Color-scheme options beyond plain chain identity:

- **pLDDT confidence** — for AlphaFold/ESM Atlas structures, recolors by real
  per-residue prediction confidence (red = low, blue = high), correctly
  handling both AlphaFold's 0–100 scale and ESM Atlas's 0–1 fraction without
  you needing to know which one applies. Disabled when nothing in the run is
  a predicted model.
- **Mutation tolerance (AlphaMissense)** — colors every residue by its mean
  predicted pathogenicity across all 19 possible substitutions at that
  position (green = tolerant, red = intolerant) — see §9 for the
  single-substitution version of this.
- **InterPro domains** — colors every domain simultaneously and
  persistently (one color per domain, from the same domain/residue mapping
  §8.1's "Highlight in 3D" uses) — unlike that button, which ghosts
  everything except one domain at a time, this shows every domain at once as
  a standing view.
- **Sequence disorder (MobiDB)** — colors every residue by a real
  sequence-based intrinsic-disorder prediction (MobiDB's own predictor, not
  just AlphaFold's pLDDT relabeled) — a computational prediction, honestly
  labeled as such.
- **Predicted flexibility (GNM)** — colors every residue by the same
  real-time Gaussian Network Model prediction described in §4.5.
- **PAE-derived domains** — for an AlphaFold-sourced structure, auto-splits
  it into rigid domains by connectivity in its own real PAE matrix (see
  §4.4) — distinct from the sequence-based "InterPro domains" scheme above.
  Disabled when nothing in the run is AlphaFold-sourced.

### 3.3 RMSD heatmap

A Plotly heatmap of pairwise RMSD across every structure in the run — read
similarity/divergence at a glance instead of scanning a raw table.

### 3.4 Structural clustering

Group the run's structures into families using interactive RMSD-threshold
hierarchical (average-linkage) clustering. Drag the threshold slider and
watch groupings update live — most useful once you're aligning more than a
handful of structures and want to see natural groupings rather than one flat
list.

### 3.5 Phylogenetic tree

A structural phylogenetic tree (UPGMA/average-linkage), built directly from
the RMSD matrix — a visual family tree of how the aligned structures relate.

### 3.6 Batch comparison against a past run

Pick any past run from your history and diff its RMSD matrix against your
current one, to see exactly how structural relationships shifted — e.g. did
adding a new structure change which pairs cluster together.

### 3.7 Cross-run RMSD trend

From the History panel, select 2 or more past runs to see a chronological
trend line (mean/max RMSD over time) — useful when you've run the same
protein family repeatedly and want to know whether structural similarity
drifted as you added sources or changed parameters. (TM-score isn't trended
here — unlike the RMSD matrix, it's computed at run time and never saved to
disk, so trending it for old runs would mean re-running the alignment for
each one.)

---

## 4. Judging Whether You Can Trust a Structure

This is the section most worth reading closely — a low RMSD or a
good-looking cartoon doesn't automatically mean a structure (or a comparison)
is trustworthy. StructScope reports several genuinely independent signals;
each one flags a different kind of problem.

### 4.1 Ramachandran outlier detection

Every residue's backbone torsion angles (phi/psi) are checked against the
regions real proteins actually occupy. The **Ramachandran score** is the
percentage of residues in favored regions; an outlier list names specifically
which residues fall outside them — a real red flag for a modeling or
refinement problem at that exact position, computed per structure.

### 4.2 TM-score / GDT-TS

An independent structural-alignment quality table, separate from RMSD. TM-score
and GDT-TS are both length-normalized and much less sensitive to a single
badly-superposed loop than RMSD is — a structure pair can have a deceptively
low RMSD and still a poor TM-score if most of the structure aligns well but
one region is wildly off. See §13 for interpretation cutoffs.

### 4.3 pLDDT confidence

AlphaFold/ESM Atlas structures carry a genuine per-residue confidence score.
High pLDDT means that **one residue's own position** is trustworthy — it says
nothing about how two distant regions relate to each other. That's what PAE
is for.

### 4.4 Predicted Aligned Error (PAE)

For an AlphaFold-sourced structure, load the PAE heatmap in Analytics' Quality
sub-tab. This is AlphaFold's own confidence that two residues are positioned
correctly *relative to each other* — genuinely different information from
pLDDT. A multi-domain protein can have high pLDDT everywhere (each domain's
own shape is confidently predicted) and still have high PAE between domains
(their relative orientation to each other is not trustworthy at all). Low
error (blue) between two regions means you can trust their relative
positioning; high error (red) means treat it with real skepticism regardless
of what pLDDT says.

The same PAE matrix also drives the **"PAE-derived domains"** 3D viewer
color scheme (§3.2): it auto-splits the structure into rigid domains by
connected-component analysis over the matrix's own real confidence values —
group residues whose relative positions are mutually trusted, and cut where
that trust breaks down. Distinct from the "InterPro domains" scheme, which
is sequence-based. Deliberately a simplified connectivity split rather than
full weighted-graph community detection, and only available for
AlphaFold-sourced structures, since it needs this same PAE data.

### 4.5 Real-time flexibility prediction (GNM)

A separate chart in Analytics' Quality sub-tab runs a real-time, coarse-
grained Gaussian Network Model (Normal Mode Analysis) over any one
structure's own CA coordinates — no external API call, unlike every other
signal on this page, just linear algebra on coordinates already downloaded.
This is a *prediction* of which residues move the most, not a measurement.
For a real PDB entry, its own crystallographic B-factor is overlaid as a
free real-world comparison point (a real 0.59 Pearson correlation was
verified between the two on a real structure) — the prediction and the
measurement are complementary, not the same thing. The matching **"Predicted
flexibility (GNM)"** 3D viewer color scheme (§3.2) colors every residue by
this same prediction.

### 4.6 wwPDB validation report

For real, experimentally-solved PDB entries: clashscore and Ramachandran/
rotamer outlier percentiles, with both archive-wide and similar-resolution
context, pulled directly from the wwPDB's own validation pipeline — the same
numbers a structural biologist would check before trusting a deposited entry.

### 4.7 Contact maps & difference-distance matrices

In Analytics' RMSD Matrix sub-tab: a real CA-CA contact map for any one
structure (thresholded at 8 Å), and a real difference-distance matrix between
any two structures over their commonly aligned columns. This reveals domain
*movements* — a hinge rotation between two conformational states, for
example — that a single global RMSD number completely hides, since RMSD only
tells you the average deviation, not where it's concentrated.

### 4.8 Structure-diff narrative

In Analytics' Insights sub-tab, pick any two structures in the run to get a
plain-English paragraph (RMSD magnitude plus, when available, the TM-score's
fold-level interpretation) — a fast, exact-pair answer, distinct from the
automated Insights list, which only ever surfaces the single best/worst pair
across the whole run.

### 4.9 Bulk QC sweep

The **"Run QC on all"** button in the Workspace tab runs Ramachandran outlier
detection, secondary-structure assignment, and (for real PDB entries) wwPDB
validation across every loaded structure at once, with **no alignment
required** — a summary table instead of clicking into each card individually.
This is the fastest way to sanity-check a whole batch of structures before
committing to an alignment run at all.

The same summary table also includes a **"Self Clash"** column — a real,
self-computed all-atom steric-clash score, available for every structure
regardless of source. The existing wwPDB clashscore column only ever
populates for a real PDB entry, so AlphaFold/ESM Atlas/uploaded/predicted
structures previously had no clash signal here at all. Treat this as a
*rough sanity check* against a real PDB entry's own wwPDB clashscore where
both exist, not a reproduction of it: real MolProbity adds explicit
hydrogens before counting overlaps, and hydrogen-dominated clashes are
invisible to this heavy-atom-only detector, so the two numbers can diverge
sharply for an older, poorly-refined structure even though they track
reasonably for a modern, well-refined one.

---

## 5. Sequence-Level Analysis

### 5.1 Identity & conservation view

Aligned sequences with per-position highlighting, so you can see which
residues are conserved across the run at a glance. **Important**: this
default highlighting is *identity across whichever structures you happened to
load*, not a true evolutionary measure — it's labeled as such deliberately.
See §5.3 for the real thing.

### 5.2 Motif search

Search the alignment for a residue pattern (e.g. `RYY`, `G.G`, `G-X-P` — `X`,
`.`, and `-` all act as single-residue wildcards). Every match across every
structure appears in a table, with a **"Highlight Motif in 3D Viewer"**
button that selects every matched residue across all structures at once.

### 5.3 True sequence-only MSA and true evolutionary conservation

Two background jobs, independent of Mustang's structural alignment entirely:

- **True sequence-only MSA** (via EBI Clustal Omega) — a real multiple
  sequence alignment computed purely from each structure's own sequence. It
  can legitimately *disagree* with the structural alignment for divergent
  sequences that still happen to share a similar fold — that disagreement is
  itself informative, not an error.
- **True evolutionary conservation** (via NCBI BLAST) — searches for real
  homologs of a selected structure's sequence and scores real per-position
  conservation (Shannon entropy) from their alignment. This is the
  longest-running job in the app — real BLAST searches commonly take several
  minutes, which is exactly the kind of job worth attaching a webhook to
  (§8.5) so you don't have to keep the tab open.

---

## 6. Ligand & Binding Site Analysis

### 6.1 Detecting ligands and pockets

For any structure in the run, StructScope auto-detects bound ligands and
their binding pockets, then classifies **every contact residue by real
geometry** — Hydrogen Bond, Salt Bridge, Van der Waals, Polar Contact, or
Metal Coordination — based on donor/acceptor/charged-atom proximity. This is
a heavy-atom-only heuristic (PDB files carry no hydrogens) and doesn't
attempt pi-stacking, which needs bond-order/aromaticity information a PDB
file simply doesn't include.

Catalytic/structural metal cofactors (Zn, Mg, Ca, Mn, Fe, Cu, Ni, Co, Cd,
Mo — a zinc-finger's Zn, a kinase's Mg) are recognized as real ligands, not
filtered out as generic ionic noise, and get their own Metal Coordination
classification at real coordination-bond distances.

### 6.2 SASA and pocket similarity

Solvent-Accessible Surface Area (SASA) is visualized for the pocket-lining
residues. When a run has two or more detected ligands, an interactive
**binding-pocket similarity matrix** (Jaccard index of pocket-residue
composition) shows how alike each ligand's chemical environment is to every
other one — useful for spotting a conserved active site, or a surprisingly
divergent one, across otherwise-similar structures.

### 6.3 Ligand chemistry lookup

Select any detected ligand for a **"what is this?"** line — its real name,
molecular formula, SMILES, and InChIKey, resolved live from RCSB's Chemical
Component Dictionary. Alongside it, a **"Similar known compounds"** list
shows real PubChem 2D similarity search results for that ligand's SMILES —
up to 10 structurally related compounds (≥95% Tanimoto similarity), each a
clickable link straight to its real PubChem entry. Useful for spotting
related known ligands or drugs for a binding site you're investigating.

A **"Known bioactivity"** list shows real ChEMBL potency data (IC50, Ki, Kd,
or EC50, against a real target) for that same ligand — a different question
from the analog list above: not "what looks like this" but "how potent is
this, against what." Resolved from the ligand's own InChIKey, capped to the
10 most potent numeric records for a well-studied compound (a real drug can
carry thousands).

### 6.4 No bound ligand? Candidate pocket finding

A heuristic candidate binding-pocket finder looks for surface-exposed
residues that spatially cluster with residues from a distant part of the
sequence — the standard signature of a fold packing together to form a
concave pocket wall — ranked by cluster size and hydrophobic/aromatic
content, with a convex-hull **volume estimate** per candidate. Every result
is explicitly labeled a computational prediction, not a validated pocket or a
measured volume (a convex hull over-estimates a true concave cavity — treat
it as a rough size signal). Especially useful for AlphaFold/ESM Atlas
structures, which essentially never come with a co-crystallized ligand.

---

## 7. Protein-Protein Interfaces

For any multi-chain structure in the run (a hemoglobin tetramer's four
subunits, for example), pick two chains to find every contact residue between
them, using the same real geometry-based classification Ligand Hunter uses.
You also get the **buried interface area** — total ΔSASA: each chain's own
solvent-accessible surface area, minus the complex's, the standard way
interface size is reported in the literature. This operates on the
structure's original pre-alignment file, so it works even though Mustang
itself only ever aligns one chain per structure.

---

## 8. Functional Annotation & "What Does This Do?"

### 8.1 Functional annotation in Compare mode

For any structure already in a Compare-mode run, StructScope resolves it to a
real UniProt accession (a live SIFTS lookup for a plain PDB entry; free for
AlphaFold/SWISS-MODEL IDs, which embed the accession directly) and pulls real
InterPro domains, GO terms, and Reactome pathways, plus a **real UniProt
free-text function summary** — the same plain-English "Function" paragraph
UniProt's own entry page shows — surfaced at the top of the panel as an
at-a-glance answer before you dig into the structured domain/GO-term lists
below it.

Alongside it: real **Human Protein Atlas tissue/subcellular expression**
data (where in the body this is actually expressed — nothing else here
answers that); a second, independently-curated **KEGG pathway list**
alongside Reactome's (the two can legitimately disagree); and a real
**OrthoDB cross-species ortholog** line naming the equivalent gene in a
small fixed set of model organisms (mouse, zebrafish, fly, yeast) —
distinct from the BLAST-based true evolutionary conservation feature
(§5.3), which searches for homologs rather than a defined per-species
ortholog group.

ESM Atlas structures have no UniProt mapping at all (they're uncharacterized,
metagenomic sequences), and an uploaded file or a raw-sequence prediction
(§2.5) has no accession either — every source above is unavailable by
construction for these, since they all key off that accession. An
**"Annotate from sequence (InterProScan5)"** action fills that specific gap:
it submits the structure's own sequence (extracted directly from its
coordinates, no accession needed) to EBI's InterProScan5 as a background job
and renders real Pfam/PROSITE domain and GO-term hits once it completes —
the one annotation path here that works purely from sequence.

When 2+ structures in the run resolve an accession, a **shared across all
structures** summary lists exactly which domains/terms every one of them has
in common — a real way to confirm a shared function isn't just a shared
fold.

**"Highlight in 3D"** works for AlphaFold-sourced structures (their numbering
matches UniProt 1:1 by construction) and for real PDB entries too, via a real
per-segment SIFTS residue mapping that correctly translates around
crystallization constructs and non-standard numbering.

### 8.2 Discover mode: structure-to-function for an unannotated structure

Have one structure and genuinely no idea what it does? Discover mode answers
that directly — most useful for a predicted structure (AlphaFold, ESM Atlas)
with no known function yet, since 3D fold is conserved far longer than
sequence, so this finds real connections a plain sequence search would miss
entirely.

### 8.3 Search databases

Searches your structure against Foldseek's structural-neighbor databases.
Defaults to PDB + AlphaFold DB, with an expandable picker exposing all **9**
supported databases (SwissProt/Proteome AFDB subsets, CATH, BFVD, BFMD, GMGC,
MGnify/ESM Atlas). Only MGnify/ESM Atlas is marked as "structural hits only,
no functional annotation" — so it's always clear upfront what a given
database will and won't tell you.

### 8.4 Annotation sources and confidence gating

Once neighbors are found, real annotation data is pulled from **six
sources** — InterPro, QuickGO, STRING, Reactome, PDBe SIFTS, and GMGC — and
aggregated into a single domain/GO-term consensus rather than shown as six
disconnected lists.

Critically, a neighbor's annotations only count toward the final function
hypothesis if that neighbor's own structural-match probability also clears a
configurable threshold (default 0.5). Having annotation data available isn't
enough on its own if the structural match that found it was weak — this is
what keeps the headline result honest rather than optimistic.

### 8.5 Detail levels and async job webhooks

The same result renders at three depths: **Public** (plain-language, explicit
uncertainty framing, no jargon), **Student** (a guided explanation of *why*
the match suggests that function), and **Researcher** (raw hit tables, match
probabilities, the full unfiltered list). Switch between them at any time
without re-running the search.

Discover, Clustal Omega MSA, and BLAST conservation jobs — the three you're
most likely to walk away from — all accept an optional **webhook URL** at
submission time. A notification POST arrives there the moment the job
finishes, so you don't need to keep the tab open polling for a multi-minute
search.

### 8.6 Self-hosted search backend

*(Relevant if you're administering a deployment.)* Discover mode defaults to
the public Foldseek API, shared and rate-limited across all users. For
heavier use, set `foldseek.backend: local` in `config.yaml` to switch to a
local Foldseek binary and search database you provision yourself — no code
changes needed, just configuration. Discover runs are cached (annotation
lookups default to a 30-day TTL) and appear in Dashboard/History alongside
Compare runs with a distinct `DISCOVER` badge.

### 8.7 3D viewer and ligand inspector in Discover mode

As soon as a Discover search resolves your structure, it renders directly in
the 3D viewer as-is (no re-alignment). If it has a bound ligand, the same
real interaction-geometry classification from Ligand Hunter applies here too
— a single unaligned structure gets real binding-site analysis with no second
structure needed for comparison. No ligand? The same candidate-pocket finder
from §6.4 applies.

---

## 9. Mutations: ClinVar, AlphaMissense, gnomAD & REVEL

In Analytics' Annotations sub-tab, enter a chain, residue number, and
proposed substitution. StructScope maps it onto the structure's real UniProt
position, reports the real wild-type residue and gene, and — if a matching
record exists — the real **ClinVar clinical significance** of that exact
substitution, plus the real **AlphaMissense pathogenicity score** for it,
plus the real **gnomAD population allele frequency** and a real **REVEL
pathogenicity score** for the same exact substitution (both from the same
myvariant.info lookup). AlphaMissense and REVEL are two independent
predictors — useful when they disagree — and gnomAD frequency is an
independent signal from either: a variant can be common in the population
yet still flagged pathogenic by a predictor, or vice versa, and that
disagreement is itself informative. Any already-known UniProt natural
variant at that position is surfaced too. This builds on the same real
residue mapping described in §8.1, so it works for real PDB entries as well
as AlphaFold-sourced ones.

**Verified example**: mapping HBB chain B, residue 6, substitution to Val
(the real sickle-cell mutation) on `4HHB` correctly resolves to HBB position
7 and returns a real ClinVar record — the well-known `rs334` variant.

For a whole-structure view rather than one substitution at a time, use the
**"Mutation tolerance (AlphaMissense)"** 3D viewer color scheme described in
§3.2.

---

## 10. History, Sharing, Notes & Sessions

Every completed run — Compare or Discover — is saved and browsable from the
History tab. Reopening a past run restores its full state (3D view, stats,
every tab) exactly as it was when the run finished.

- **Delete/clear** — delete a single run or clear your entire history, both
  with a confirmation step first, and neither undoable.
- **Share** — click Share on any run to copy a link. Anyone who opens it —
  no account, no session, nothing else required — sees exactly that run's
  results in a read-only view. This is intentionally world-readable by
  anyone holding the link (a run ID is long and random enough that it can't
  practically be guessed) rather than gated behind an extra "make shareable"
  step.
- **Notes & tags** — every run can carry free-text notes and tags, edited
  inline from the History panel.
- **Cross-run trend** — described in §3.7.

**Session isolation**: results and history are scoped per session, so
multiple people can use the same deployment at once without seeing each
other's runs.

---

## 11. Exporting & Sharing Results

| Export | What you get |
|---|---|
| **PDF report** | Configurable — choose exactly which sections to include (summary, insights, heatmap, phylogenetic tree, RMSD matrix) instead of always exporting everything. |
| **HTML lab notebook** | A standalone, self-contained file with an embedded 3D viewer and every figure baked in — opens in any browser, no server needed, good for sharing with someone who doesn't have StructScope running. |
| **Jupyter Notebook** (`.ipynb`) | A real, *runnable* notebook whose code cells re-fetch the run's data live from StructScope's own REST API — for continued programmatic exploration, not just a static snapshot. |
| **Discover export** | A completed Discover run as a standalone HTML report or raw JSON. |
| **Raw data exports** | RMSD matrix as CSV, heatmap as PNG, phylogenetic tree as a standard Newick file — for pulling numbers into your own analysis or a dedicated phylogenetics tool. |
| **Download everything** | One ZIP bundling the aligned PDB, FASTA, RMSD matrix CSV, heatmap PNG, and an auto-generated lab notebook. |
| **REST API** | Every backend route is documented and explorable at `/docs`, machine-readable at `/openapi.json` — script against StructScope directly instead of only using the UI. |

---

## 12. Settings & Access Control

*Relevant mainly if you're self-hosting or administering a shared deployment.*

- **API key access control** — setting `ALIGNX_API_KEY` requires it (via an
  `X-API-Key` header or `?api_key=` link parameter) on every API route,
  generated file, and downloaded structure — locking the deployment down for
  anyone without the key. Left unset by default so local development needs
  zero configuration.
- **Rate limiting** — job-submission endpoints are rate-limited per API key
  (or per IP if no key is set), so one client can't queue unlimited
  compute-heavy jobs and starve everyone else on a shared deployment.
- **Settings tab** — change the Mustang execution backend and timeout, max
  proteins/file-size limits, the default heatmap colormap, and the default 3D
  viewer style — no config file editing or restart required. **Note**: these
  are deployment-wide settings, not personal ones — changing them affects
  every user of the deployment, immediately, for every subsequent run.

---

## 13. Interpreting the Numbers — Quick Reference

These are rule-of-thumb ranges, not hard scientific thresholds — always read
them alongside the structural context (resolution, method, how divergent the
proteins actually are).

| Metric | Range | What it means |
|---|---|---|
| **RMSD** (Å) | < 2.0 | Very similar structures |
| | 2.0 – 5.0 | Moderate structural divergence |
| | > 5.0 | Substantial difference in shape |
| **TM-score** | > 0.9 | Same fold, high confidence |
| | 0.5 – 0.9 | Same overall fold |
| | < 0.5 | Likely *not* the same fold, regardless of RMSD |
| **GDT-TS** | Higher = more residues superpose within relaxed thresholds; used alongside TM-score, standard in CASP-style assessment |
| **pLDDT** | > 90 | Very high per-residue confidence |
| | 70 – 90 | Confident |
| | 50 – 70 | Low confidence |
| | < 50 | Should not be interpreted at all — likely disordered |
| **PAE** | Low (blue) | This residue pair's *relative* position is trustworthy |
| | High (red) | Treat their relative orientation with real skepticism, even if both residues individually have high pLDDT |
| **Ramachandran favored %** | > 95% | Exceptional geometric quality |
| | < 80% | Worth investigating specific outliers |
| **Jaccard index** (pocket similarity) | 1.0 | Identical pocket-residue composition |
| | ≥ 0.6 | Meaningfully similar chemical environment |
| | ≤ 0.2 | Largely divergent pockets |
| **AlphaMissense / REVEL pathogenicity** | Closer to 1.0 | More likely pathogenic |
| | Closer to 0.0 | More likely benign |
| **Clashscore (self-computed)** | Lower | Fewer detected all-atom steric overlaps — a rough sanity check against a real PDB entry's own wwPDB clashscore, not a reproduction of it (see §4.9) |

---

## 14. Glossary

- **RMSD** — Root-mean-square deviation: the average distance, in Ångströms,
  between corresponding atoms after superposition.
- **TM-score** — A length-normalized fold-similarity score (0–1), less
  sensitive to local outliers than RMSD.
- **GDT-TS** — Global Distance Test: percentage of residues superposing
  within a set of increasingly relaxed distance thresholds.
- **pLDDT** — AlphaFold's per-residue confidence in its own predicted
  position (0–100, or 0–1 for ESM Atlas).
- **PAE** — Predicted Aligned Error: AlphaFold's confidence that two residues
  are positioned correctly *relative to each other*.
- **SASA** — Solvent-Accessible Surface Area: how exposed a residue or pocket
  is to surrounding solvent.
- **Jaccard index** — A similarity score for two sets (here, two ligands'
  pocket residues): the size of their overlap divided by the size of their
  union.
- **Ramachandran outlier** — A residue whose backbone torsion angles fall
  outside the regions real proteins occupy — a geometric red flag.
- **UPGMA** — Unweighted Pair Group Method with Arithmetic mean: the
  average-linkage clustering algorithm used for both structural clustering
  and the phylogenetic tree.
- **SIFTS** — PDBe's mapping service resolving a PDB entry (and chain) to its
  real UniProt accession and per-residue numbering.
- **NMR ensemble** — A multi-model structure from NMR; StructScope only ever
  analyzes model 1.
- **Foldseek** — The structural-neighbor search engine behind Discover mode.
- **ClinVar** — NCBI's database of clinically observed genetic variants and
  their significance.
- **AlphaMissense** — DeepMind's model predicting pathogenicity for every
  possible single-residue substitution across the proteome.

---

## 15. FAQ & Troubleshooting

**Why does the Quality tab show "--" for a single structure I just added?**
Ramachandran/quality metrics are computed as part of a full alignment run
(2+ structures). For a single structure with no alignment, use **Workspace →
"Run QC on all"** instead (§4.9) — it needs no alignment at all.

**What's the difference between "ESM Atlas" and "ESMFold prediction"?**
ESM Atlas (ID prefix `ESM-`) is a *database* of already-predicted structures
for metagenomic sequences you look up by accession. "Predict from sequence"
(§2.5) calls the same underlying ESMFold model directly on a sequence you
provide, with no existing accession at all — a different entry point to a
related but distinct piece of technology.

**My AlphaFold structure's 3D viewer looks blank.** This was a real bug fixed
in a recent release (AlphaFold structures download as real mmCIF files, and
older builds mis-parsed them as plain PDB). If you still see this, hard-
refresh the page.

**Why does Discover mode say "no results" for one database but hits for
another?** Not every Foldseek database resolves to functional annotation —
MGnify/ESM Atlas hits are structural-only by design (§8.3), since they're
metagenomic sequences with no existing curated annotation to pull from.

**A BLAST conservation search is taking minutes — is it stuck?** No — real
BLAST searches commonly take several minutes; this is the longest-running job
type in the app. Set a webhook URL (§8.5) instead of waiting on the tab.

---

## 16. Appendix: Full Feature Index

For a flat, checklist-style index of every capability (useful if you're
confirming "does it do X" quickly rather than reading a section), see
[`docs/FEATURES.md`](FEATURES.md) — the developer-facing companion to this
guide, describing the same capabilities with direct links into the same
underlying behavior.
