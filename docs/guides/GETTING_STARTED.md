# Getting Started with StructScope

Two short, hands-on walkthroughs — pick the one that matches what you actually have: multiple structures you want to compare, or one structure you want to understand. For a complete list of what every button does, see [docs/FEATURES.md](../FEATURES.md); for how the pipeline works internally, see [docs/ARCHITECTURE.md](../ARCHITECTURE.md).

Both walkthroughs assume the app is already running — see the README's [Quick Start](../../README.md#-quick-start) if it isn't yet.

---

## Your first Compare run

**You have two or more related structures and want to know how similar they are.**

1. Open the **Overview** tab. In the input box, paste `4HHB, 2HHB` (two hemoglobin variants) — or click the **Hemoglobin variants** quick-start example instead of typing.
2. Click **Add All**. Each structure appears in the workspace list with its source database, method, and resolution — enough to sanity-check what you're about to align before committing to it.
3. If a structure has multiple chains, pick the one you want per structure (defaults to chain A). Click **Run Structural Alignment**.
4. The app shows an "Aligning..." state while Mustang runs in the background — this typically takes a few seconds for two small structures. When it finishes, every tab populates at once.
5. **You should now see**: a 3D viewer with both structures superimposed and distinctly colored, a pairwise RMSD figure in the HUD, and (on the **Analytics** tab) a Quality summary, an RMSD heatmap, and a phylogenetic tree. Open the **Insights** sub-tab under Analytics for a plain-language summary of what the numbers mean — homogeneity, best/worst-matching pair, and (if either structure has a bound ligand) how similar their binding pockets are.
6. Try the **Ligands** tab to see any detected binding sites and their interacting residues, and **Sequence** to export a PDF report or HTML lab notebook of the whole run.

Every run is saved automatically — reopen it later from the **History** tab, or diff it against a different run on the **Compare** tab.

---

## Your first Discover run

**You have one structure and don't know (or aren't sure) what it does.**

1. Open the **Discover** tab. Enter a structure ID — e.g. `AF-P69905-F1` (an AlphaFold-predicted structure) — and submit.
2. StructScope searches it against Foldseek's structural databases (defaults to PDB + AlphaFold DB) for proteins with a similar fold, even if their sequences don't obviously match. This takes longer than a Compare run — the public Foldseek API is shared across every StructScope user, so a real search can take a minute or more.
3. **You should now see**: a function hypothesis built from the resolvable structural neighbors' curated annotations (domains, GO terms), plus how many neighbors were found vs. how many actually cleared the confidence threshold used to state that hypothesis.
4. Use the **Public / Student / Researcher** toggle above the result to see the same underlying data at different depths — Researcher shows the full unfiltered neighbor list and a high-confidence stat; Public/Student show only the confidence-gated summary, with an explicit low-confidence message if nothing cleared the bar.
5. Export the result as a standalone HTML report or raw JSON from the same tab — the same export options Compare mode has.

Like Compare runs, Discover runs show up on the **Dashboard** and **History** tab (with a `DISCOVER` badge instead of `COMPARE`) and can be reopened later.

---

**A note on both**: every automated summary StructScope produces — Compare's Insights, Discover's function hypothesis — is a computational inference from structural similarity, not a confirmed experimental result. Treat a high-confidence result as a strong lead worth following up, not a final answer.
