import { submitDiscoveryJob, pollJobUntilDone, isValidPdbId, getDiscoveryReportUrl, getDiscoveryExportUrl, getDiscoveryCitationsUrl, fetchLigands, fetchInteractions } from '../api';
import { renderDomainList, renderGoTermList } from '../utils/annotationRenderers';
import { buildContactRow } from '../utils/interactionRenderers';

const SOURCE_LABELS = {
    pdb: 'PDB',
    alphafold: 'AlphaFold',
    swissmodel: 'SWISS-MODEL',
    esmfold: 'ESMFold',
};

const DETAIL_LEVELS = [
    { key: 'public', label: 'Public' },
    { key: 'student', label: 'Student' },
    { key: 'researcher', label: 'Researcher' },
];

// The full set Foldseek's public API accepts (FoldseekClient.ALLOWED_DATABASES).
// `annotatable: false` marks databases whose hit IDs don't resolve to any
// functional annotation at all - picking one of those still returns
// structural hits but no domain/GO summary. mgnify_esm30 is the only one
// left: its MGYP-accession target IDs have no UniProt mapping and no
// dedicated annotation source of their own, and are often *expected* to
// have no existing annotation, since it's specifically metagenomic "dark
// matter" sequences. gmgcl_id hits resolve via GMGC's own API instead of
// UniProt (see annotation_aggregator.py's fetch_gmgc_features), not every
// database routes through the same resolution mechanism.
const DATABASE_OPTIONS = [
    { key: 'pdb100', label: 'PDB', hint: 'Experimentally solved structures', annotatable: true, default: true },
    { key: 'afdb50', label: 'AlphaFold DB', hint: '50%-redundancy-reduced', annotatable: true, default: true },
    { key: 'afdb-swissprot', label: 'AlphaFold DB (SwissProt)', hint: 'Reviewed UniProt entries only', annotatable: true, default: false },
    { key: 'afdb-proteome', label: 'AlphaFold DB (Proteomes)', hint: 'Full reference proteomes', annotatable: true, default: false },
    { key: 'cath50', label: 'CATH', hint: 'Structural domain classification', annotatable: true, default: false },
    { key: 'BFVD', label: 'BFVD', hint: 'Big Fantastic Virus Database', annotatable: true, default: false },
    { key: 'bfmd', label: 'BFMD', hint: 'Big Fantastic Metagenomics Database', annotatable: true, default: false },
    { key: 'mgnify_esm30', label: 'MGnify / ESM Atlas', hint: "Metagenomic 'dark matter' proteins", annotatable: false, default: false },
    { key: 'gmgcl_id', label: 'GMGC', hint: 'Global Microbial Gene Catalog', annotatable: true, default: false },
];

// Single-structure "what is this?" workflow: submit one structure to
// Foldseek, then render the resulting neighbor hits + annotation summary
// at whichever detail level the user picks. Self-contained, unlike
// OverviewTab's Compare mode - it doesn't touch selectedPDBs/currentRunId.
export class DiscoverTab {
    element = null;
    isRunning = false;
    detailLevel = 'student';
    results = null;
    selectedDatabases = new Set(DATABASE_OPTIONS.filter(d => d.default).map(d => d.key));

    constructor(props = {}) {
        this.onStructureLoaded = props.onStructureLoaded || (() => {});
        this.onSwitchToOverview = props.onSwitchToOverview || (() => {});
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-discover-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Structural Discovery</span>
                    <h2 class="section-title">Discover</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <p class="font-body-sm text-secondary max-w-[560px]">
                    Have one structure and don't know what it does? Search it against
                    Foldseek's structural databases to find known proteins with a similar
                    fold, and see what's known about them - structure is conserved far
                    longer than sequence, so this can find connections sequence search misses.
                </p>

                <div class="flex gap-2">
                    <input id="discover-input" type="text" placeholder="PDB ID, or AF-/SM-/ESM- accession"
                        class="flex-1 bg-surface border border-border rounded-sm px-3 py-2 text-body-sm font-mono focus:outline-none focus:border-accent" />
                    <button id="discover-run-btn" class="btn-primary px-5 py-2 rounded-sm font-label-md text-label-md flex items-center gap-2 whitespace-nowrap">
                        <span class="material-symbols-outlined text-[18px]">travel_explore</span>
                        Discover
                    </button>
                </div>

                <details id="discover-db-picker" class="group">
                    <summary class="font-body-sm text-[11px] text-secondary cursor-pointer select-none hover:text-primary w-fit">
                        Databases: <span id="discover-db-summary" class="font-mono"></span>
                        <span class="material-symbols-outlined text-[14px] align-middle group-open:rotate-180 transition-transform">expand_more</span>
                    </summary>
                    <div class="flex flex-col gap-2 pt-3">
                        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                            ${DATABASE_OPTIONS.map(d => `
                                <label class="flex items-start gap-2 p-2 rounded-sm border border-border-subtle bg-surface hover:border-border cursor-pointer">
                                    <input type="checkbox" data-db="${d.key}" class="discover-db-checkbox mt-0.5" ${this.selectedDatabases.has(d.key) ? 'checked' : ''} />
                                    <span class="flex flex-col">
                                        <span class="font-label-sm text-label-sm">${d.label}${!d.annotatable ? ' <span class="text-secondary" title="Hits shown, but no domain/GO annotation yet">*</span>' : ''}</span>
                                        <span class="font-body-sm text-[10px] text-secondary">${d.hint}</span>
                                    </span>
                                </label>
                            `).join('')}
                        </div>
                        <p class="font-body-sm text-[10px] text-secondary">* Hits from these databases are shown but don't yet resolve to functional annotations.</p>
                    </div>
                </details>

                <div id="discover-status" class="hidden font-body-sm text-secondary flex items-center gap-2">
                    <span id="discover-status-icon" class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                    <span id="discover-status-text"></span>
                </div>
                <div id="discover-error" class="hidden font-body-sm text-error"></div>
                <div id="discover-results"></div>

                <p class="font-body-sm text-[11px] text-secondary border-t border-border-subtle pt-4">
                    Structural search via <a href="https://search.foldseek.com/search" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">Foldseek</a>.
                    Functional annotations via EMBL-EBI's
                    <a href="https://www.ebi.ac.uk/interpro/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">InterPro</a>,
                    <a href="https://www.ebi.ac.uk/QuickGO/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">QuickGO</a>, and
                    <a href="https://www.ebi.ac.uk/pdbe/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">PDBe SIFTS</a>,
                    <a href="https://string-db.org/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">STRING</a>,
                    <a href="https://reactome.org/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">Reactome</a>, and
                    <a href="https://gmgc.embl.de/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">GMGC</a>.
                    Results are computational inferences from structural similarity, not experimentally confirmed
                    function - see each service's own terms of use for details.
                </p>
            </div>
        `;

        this.element = div;
        this.element.querySelector('#discover-run-btn').addEventListener('click', () => this.handleRun());
        this.element.querySelector('#discover-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.handleRun();
        });
        this.element.querySelectorAll('.discover-db-checkbox').forEach(cb => {
            cb.addEventListener('change', () => {
                if (cb.checked) this.selectedDatabases.add(cb.dataset.db);
                else this.selectedDatabases.delete(cb.dataset.db);
                this.updateDbSummary();
            });
        });
        this.updateDbSummary();

        if (this.results) {
            this.element.querySelector('#discover-input').value = this.results.pdb_id;
            this.syncDbCheckboxes(this.results.databases_searched);
            this.renderResults();
            this.onStructureLoaded(this.results.pdb_id);
        }
        return div;
    }

    setStatus(text) {
        const el = this.element.querySelector('#discover-status');
        if (text) {
            this.element.querySelector('#discover-status-text').textContent = text;
            el.classList.remove('hidden');
        } else {
            el.classList.add('hidden');
        }
    }

    setError(text) {
        const el = this.element.querySelector('#discover-error');
        if (text) {
            el.textContent = text;
            el.classList.remove('hidden');
        } else {
            el.classList.add('hidden');
        }
    }

    setRunning(isRunning) {
        this.isRunning = isRunning;
        const btn = this.element.querySelector('#discover-run-btn');
        if (btn) btn.disabled = isRunning;
    }

    updateDbSummary() {
        const el = this.element.querySelector('#discover-db-summary');
        if (!el) return;
        const n = this.selectedDatabases.size;
        const total = DATABASE_OPTIONS.length;
        el.textContent = n === total ? 'all' : `${n} of ${total} selected`;
    }

    // Checks the boxes matching a previously-run job's actual database list
    // (e.g. reopening a saved run from history) instead of leaving the
    // picker on its default selection, which could silently misrepresent
    // what that run actually searched. Unrecognized entries (e.g. the local
    // backend's synthetic "local:{path}" pseudo-database) are ignored since
    // there's no matching checkbox for them.
    syncDbCheckboxes(databases) {
        if (!this.element || !Array.isArray(databases)) return;
        const recognized = databases.filter(db => DATABASE_OPTIONS.some(d => d.key === db));
        // If nothing matches a real database key, the run likely used the
        // self-hosted local backend (a synthetic "local:{path}" entry) -
        // leave the picker's current selection alone rather than wiping it
        // to zero, since it has no bearing on what a local-backend run did.
        if (recognized.length === 0) return;
        this.selectedDatabases = new Set(recognized);
        this.element.querySelectorAll('.discover-db-checkbox').forEach(cb => {
            cb.checked = this.selectedDatabases.has(cb.dataset.db);
        });
        this.updateDbSummary();
    }

    // Foldseek's public API is rate-limited across ALL StructScope users (see
    // FoldseekClient's process-wide rate limiter), so under real load a job
    // can sit queued for a while before it actually starts - without a
    // distinct message for that, it would look like the app hung rather
    // than fairly waiting its turn behind other users' searches.
    statusMessageForJob(status) {
        if (status === 'queued') {
            return "Queued - Foldseek's search API is shared and rate-limited across all users, so this may wait a moment before starting.";
        }
        return 'Searching Foldseek structural databases... this can take a minute or two.';
    }

    async handleRun() {
        const input = this.element.querySelector('#discover-input');
        const pdbId = (input.value || '').trim().toUpperCase();
        if (!isValidPdbId(pdbId)) {
            this.setError('Enter a valid PDB ID, or AF-/SM-/ESM- accession.');
            return;
        }
        if (this.selectedDatabases.size === 0) {
            this.setError('Select at least one database to search.');
            return;
        }

        this.setError(null);
        this.setRunning(true);
        this.element.querySelector('#discover-results').innerHTML = '';
        this.setStatus(this.statusMessageForJob('queued'));

        try {
            const submission = await submitDiscoveryJob(pdbId, Array.from(this.selectedDatabases));
            const job = await pollJobUntilDone(submission.job_id, {
                onTick: (j) => this.setStatus(this.statusMessageForJob(j.status)),
            });
            if (job.status === 'failed') {
                throw new Error(job.error || 'Discovery pipeline failed.');
            }
            this.results = job.results;
            this.setStatus(null);
            this.renderResults();
            this.onStructureLoaded(this.results.pdb_id);
        } catch (err) {
            console.error('Discovery run failed:', err);
            this.setError(err.message);
            this.setStatus(null);
        } finally {
            this.setRunning(false);
        }
    }

    setDetailLevel(level) {
        this.detailLevel = level;
        if (this.results) this.renderResults();
    }

    // Reopens a Discover run loaded from the Dashboard/History tab. Unlike
    // Compare runs, there's no result directory/RMSD matrix to reload -
    // the full result was stashed in history metadata at save time, so
    // this just hands it back to the same rendering path a fresh run uses.
    loadSavedResults(results) {
        this.results = results;
        this.detailLevel = 'student';
        if (this.element) {
            const input = this.element.querySelector('#discover-input');
            if (input && results) input.value = results.pdb_id;
            if (results) this.syncDbCheckboxes(results.databases_searched);
            this.setError(null);
            this.setStatus(null);
            this.renderResults();
            if (results) this.onStructureLoaded(results.pdb_id);
        }
    }

    renderResults() {
        const container = this.element.querySelector('#discover-results');
        if (!this.results) {
            container.innerHTML = '';
            return;
        }

        const r = this.results;
        const ann = r.annotations;
        const sourceLabel = SOURCE_LABELS[r.source] || 'PDB';

        const detailToggleHTML = `
            <div class="flex gap-1 p-1 rounded-md bg-surface-raised border border-border-subtle w-fit">
                ${DETAIL_LEVELS.map(d => `
                    <button data-level="${d.key}" class="detail-level-btn px-3 py-1 rounded-md font-label-sm text-label-sm transition-colors ${this.detailLevel === d.key ? 'bg-accent-muted text-accent' : 'text-secondary hover:text-primary'}">${d.label}</button>
                `).join('')}
            </div>
        `;

        const bodyHTML = this.renderBody(r, ann);

        // Discover runs are always saved to history (see DiscoveryCoordinator),
        // so a completed result should always have an id - guard anyway in
        // case of an older/malformed result with no id to build a URL from.
        const downloadHTML = r.id ? `
            <div class="flex gap-4">
                <a href="${getDiscoveryReportUrl(r.id)}" target="_blank" rel="noopener noreferrer" class="flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:text-primary transition-colors">
                    <span class="material-symbols-outlined text-[16px]">description</span>
                    Download Report
                </a>
                <a href="${getDiscoveryExportUrl(r.id)}" target="_blank" rel="noopener noreferrer" class="flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:text-primary transition-colors">
                    <span class="material-symbols-outlined text-[16px]">data_object</span>
                    Download JSON
                </a>
                <a href="${getDiscoveryCitationsUrl(r.id)}" target="_blank" rel="noopener noreferrer" class="flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:text-primary transition-colors">
                    <span class="material-symbols-outlined text-[16px]">format_quote</span>
                    Export Citations
                </a>
            </div>
        ` : '';

        container.innerHTML = `
            <div class="flex flex-col gap-4 border-t border-border pt-6">
                <div class="flex items-center justify-between flex-wrap gap-3">
                    <div class="flex items-center gap-2">
                        <span class="font-headline-sm text-body-md font-bold text-primary font-mono">${r.pdb_id}</span>
                        <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase source-badge">${sourceLabel}</span>
                        <span class="font-body-sm text-[11px] text-secondary">${r.hit_count} structural matches (${r.databases_searched.join(', ')})</span>
                    </div>
                    ${detailToggleHTML}
                </div>
                ${downloadHTML}
                ${bodyHTML}
                <div id="discover-ligand-section" class="flex flex-col gap-3 border-t border-border-subtle pt-4"></div>
                <div class="flex flex-col gap-2 p-3 rounded-md bg-surface-raised border border-border-subtle">
                    <span class="font-body-sm text-body-sm text-secondary">Want to structurally align ${r.pdb_id} against another structure?</span>
                    <button id="discover-switch-overview-btn" class="self-start font-label-sm text-label-sm text-accent hover:underline">Switch to Overview</button>
                </div>
            </div>
        `;

        container.querySelectorAll('.detail-level-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setDetailLevel(btn.dataset.level));
        });
        container.querySelector('#discover-switch-overview-btn').addEventListener('click', () => this.onSwitchToOverview());

        this.loadLigandSection(r.pdb_id);
    }

    // The searched structure's own ligands/binding sites - independent of
    // the neighbor-search annotation above, and independent of any
    // Compare-mode alignment (fetchLigands/fetchInteractions work from a
    // bare pdb_id; no ligand-pocket-similarity matrix here, since that's
    // inherently a multi-structure comparison that doesn't apply to one
    // searched structure).
    async loadLigandSection(pdbId) {
        const section = this.element.querySelector('#discover-ligand-section');
        if (!section) return;
        section.innerHTML = `<span class="font-body-sm text-secondary"><span class="animate-spin material-symbols-outlined text-[16px] align-middle">sync</span> Checking for bound ligands...</span>`;

        let ligands;
        try {
            const data = await fetchLigands(pdbId);
            ligands = data.ligands || [];
        } catch (err) {
            console.error('Failed to load ligands for Discover structure:', err);
            section.innerHTML = `<span class="font-body-sm text-secondary">Could not check for bound ligands.</span>`;
            return;
        }

        if (ligands.length === 0) {
            section.innerHTML = `<span class="font-body-sm text-secondary">No bound ligands detected in this structure.</span>`;
            return;
        }

        section.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="eyebrow">Bound ligands</span>
                <select id="discover-ligand-select" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[240px]">
                    <option value="">Select a ligand</option>
                    ${ligands.map(l => `<option value="${l.id}">${l.name} (Chain ${l.chain}, Resi ${l.resi})</option>`).join('')}
                </select>
            </div>
            <div id="discover-ligand-results"></div>
        `;
        section.querySelector('#discover-ligand-select').addEventListener('change', (e) => {
            this.loadLigandInteractions(pdbId, e.target.value);
        });
    }

    async loadLigandInteractions(pdbId, ligandId) {
        const results = this.element.querySelector('#discover-ligand-results');
        if (!results) return;
        if (!ligandId) {
            results.innerHTML = '';
            return;
        }

        results.innerHTML = `<div class="py-2 font-body-sm text-secondary"><span class="animate-spin material-symbols-outlined text-[16px] align-middle">sync</span> Analyzing binding site...</div>`;

        try {
            const data = await fetchInteractions(pdbId, ligandId);
            const contacts = data.interactions.interactions || [];
            if (contacts.length === 0) {
                results.innerHTML = `<div class="py-2 font-body-sm text-secondary">No specific interaction contacts found.</div>`;
                return;
            }

            const table = document.createElement('table');
            table.className = "w-full text-left border-collapse mt-2";
            table.innerHTML = `
                <thead class="font-label-sm text-label-sm text-secondary">
                    <tr>
                        <th class="px-0 py-2 border-b border-border font-medium">Residue</th>
                        <th class="px-3 py-2 border-b border-border font-medium">Chain</th>
                        <th class="px-3 py-2 border-b border-border font-medium text-right">Resi</th>
                        <th class="px-3 py-2 border-b border-border font-medium text-right">Dist (Å)</th>
                        <th class="px-3 py-2 border-b border-border font-medium">Type</th>
                    </tr>
                </thead>
            `;
            const tbody = document.createElement('tbody');
            tbody.className = "font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle";
            contacts.forEach(item => tbody.appendChild(buildContactRow(item)));
            table.appendChild(tbody);

            results.innerHTML = '';
            results.appendChild(table);
        } catch (err) {
            console.error('Failed to load ligand interactions:', err);
            results.innerHTML = `<div class="py-2 font-body-sm text-secondary">Failed to analyze binding site.</div>`;
        }
    }

    // Researcher always sees whatever data exists (its own empty-state
    // handling per section already covers zero domains/GO terms/hits
    // gracefully) - only Public/Student are gated on confidence, since
    // stating a function hypothesis from a single weak structural match
    // would be misleading precisely for the audiences least equipped to
    // judge that for themselves.
    renderBody(r, ann) {
        if (!ann || ann.annotated_neighbor_count === 0) {
            return this.renderEmptyAnnotations(r);
        }
        if (this.detailLevel === 'researcher') {
            return this.renderResearcherView(ann);
        }
        if (ann.high_confidence_annotated_count === 0) {
            return this.renderLowConfidenceMessage(ann);
        }
        return this.detailLevel === 'public'
            ? this.renderPublicView(ann)
            : this.renderStudentView(ann);
    }

    renderEmptyAnnotations(r) {
        const reason = r.hit_count > 0
            ? `Found ${r.hit_count} structural matches, but none could be resolved to a protein with known functional annotations yet.`
            : 'No structural matches were found in the searched databases.';
        return `<div class="py-6 text-center text-secondary font-body-sm">${reason}</div>`;
    }

    renderLowConfidenceMessage(ann) {
        return `
            <div class="py-6 text-center text-secondary font-body-sm max-w-[480px] mx-auto">
                Found ${ann.annotated_neighbor_count} structurally similar protein(s) with known
                functional annotations, but none matched with high enough structural confidence
                (Foldseek probability &ge; ${ann.min_confident_probability}) to state a reliable
                function hypothesis here. Switch to the Researcher view to see the raw data and
                judge for yourself.
            </div>
        `;
    }

    renderPublicView(ann) {
        // This method is only reached once renderBody() has already gated
        // on high_confidence_annotated_count > 0, so pull from the
        // confidence-filtered lists, not the unfiltered top_domains/
        // top_go_terms (which can include domains/terms that only came
        // from a low-confidence match). Domains and GO terms are each
        // still independently possibly-empty (a neighbor set can have GO
        // terms with zero domain matches, or vice versa).
        const topDomain = ann.high_confidence_top_domains[0];
        const topGo = ann.high_confidence_top_go_terms[0];
        const subject = topDomain ? `known <strong>${topDomain.name}</strong>-type proteins` : 'proteins with a known function';
        const involvement = topGo ? `, which are typically involved in <strong>${topGo.name}</strong>` : '';
        return `
            <div class="p-4 rounded-md bg-surface-raised border border-border-subtle font-body-md leading-relaxed">
                This structure looks similar to ${subject}${involvement}.
                This is a computational inference based on structural similarity, not a confirmed experimental result.
            </div>
        `;
    }

    renderStudentView(ann) {
        const topDomain = ann.high_confidence_top_domains[0];
        const topGo = ann.high_confidence_top_go_terms[0];
        let consensusParagraph = '';
        if (topDomain) {
            consensusParagraph = `<p>The most common protein family among these neighbors is <strong>${topDomain.name}</strong>
               (seen in ${topDomain.neighbor_count} of ${ann.high_confidence_annotated_count} confidently-matched neighbors).
               Because structural fold is conserved much longer than sequence identity over evolution, a strong
               structural match to a known family is meaningful evidence for shared function - even in cases
               where sequence similarity alone wouldn't have found the connection.</p>`;
        } else if (topGo) {
            consensusParagraph = `<p>No single protein family dominates, but a common thread across these neighbors is
                 <strong>${topGo.name}</strong> (seen in ${topGo.neighbor_count} of ${ann.high_confidence_annotated_count}
                 confidently-matched neighbors) - a shared Gene Ontology annotation that's meaningful evidence for function
                 even without a matching domain family.</p>`;
        }
        return `
            <div class="flex flex-col gap-4">
                <div class="p-4 rounded-md bg-surface-raised border border-border-subtle font-body-md leading-relaxed flex flex-col gap-3">
                    <p>Out of ${ann.neighbors_considered} of the most confident structural neighbors,
                    <strong>${ann.high_confidence_annotated_count}</strong> matched a protein with known functional
                    annotations at high enough structural confidence (Foldseek probability &ge; ${ann.min_confident_probability}).</p>
                    ${consensusParagraph}
                </div>
                ${renderDomainList(ann.high_confidence_top_domains, 'Common domains / families')}
                ${renderGoTermList(ann.high_confidence_top_go_terms, 'Common GO terms')}
            </div>
        `;
    }

    renderResearcherView(ann) {
        return `
            <div class="flex flex-col gap-4">
                <div class="grid grid-cols-4 gap-4">
                    <div class="stat-row"><span class="stat-key">Total hits</span><span class="stat-value">${ann.total_hit_count}</span></div>
                    <div class="stat-row"><span class="stat-key">Candidates examined</span><span class="stat-value">${ann.candidates_examined}</span></div>
                    <div class="stat-row"><span class="stat-key">Resolvable to UniProt</span><span class="stat-value">${ann.resolvable_hit_count} / ${ann.candidates_examined}</span></div>
                    <div class="stat-row"><span class="stat-key">Annotated neighbors</span><span class="stat-value">${ann.annotated_neighbor_count} / ${ann.neighbors_considered}</span></div>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="stat-row"><span class="stat-key">With STRING interactions</span><span class="stat-value">${ann.neighbors_with_interactions_count}</span></div>
                    <div class="stat-row"><span class="stat-key">With Reactome pathways</span><span class="stat-value">${ann.neighbors_with_pathways_count}</span></div>
                    <div class="stat-row"><span class="stat-key">High-confidence (prob &ge; ${ann.min_confident_probability})</span><span class="stat-value">${ann.high_confidence_annotated_count} / ${ann.annotated_neighbor_count}</span></div>
                </div>
                ${renderDomainList(ann.top_domains, 'Common domains / families')}
                ${renderGoTermList(ann.top_go_terms, 'Common GO terms')}
                ${this.renderInteractionsAndPathways(ann)}
                ${this.renderHitTable(this.results.hits)}
            </div>
        `;
    }

    renderInteractionsAndPathways(ann) {
        const rows = ann.per_neighbor.filter(
            n => n.string_partners.length > 0 || n.reactome_pathways.length > 0
        );
        if (!rows.length) return '';
        return `
            <div class="flex flex-col gap-2">
                <span class="eyebrow">Interactions &amp; pathways (per neighbor)</span>
                ${rows.map(n => `
                    <div class="flex flex-col gap-1 py-1.5 border-b border-border-subtle">
                        <span class="font-mono text-[11px] text-secondary">${(n.target || '').slice(0, 60)}</span>
                        ${n.string_partners.length ? `<span class="font-body-sm text-[12px]">STRING partners: ${n.string_partners.map(p => p.partner_name).join(', ')}</span>` : ''}
                        ${n.reactome_pathways.length ? `<span class="font-body-sm text-[12px]">Reactome pathways: ${n.reactome_pathways.map(p => p.name).join(', ')}</span>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderHitTable(hits) {
        const rows = [...hits]
            .sort((a, b) => (Number.parseFloat(a.eval) || 1e9) - (Number.parseFloat(b.eval) || 1e9))
            .slice(0, 20);
        return `
            <div class="flex flex-col gap-2">
                <span class="eyebrow">Top structural matches</span>
                <div class="overflow-x-auto">
                    <table class="w-full text-left font-body-sm text-[12px]">
                        <thead>
                            <tr class="text-secondary border-b border-border-subtle">
                                <th class="py-1.5 pr-4">Target</th>
                                <th class="py-1.5 pr-4">Prob</th>
                                <th class="py-1.5 pr-4">E-value</th>
                                <th class="py-1.5 pr-4">Seq ID</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows.map(h => `
                                <tr class="border-b border-border-subtle">
                                    <td class="py-1.5 pr-4 font-mono">${(h.target || '').slice(0, 60)}</td>
                                    <td class="py-1.5 pr-4 font-mono">${typeof h.prob === 'number' ? h.prob.toFixed(3) : h.prob}</td>
                                    <td class="py-1.5 pr-4 font-mono">${h.eval}</td>
                                    <td class="py-1.5 pr-4 font-mono">${h.seqId}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
}
