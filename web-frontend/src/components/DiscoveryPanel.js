import { submitDiscoveryJob, pollJobUntilDone, getDiscoveryReportUrl, getDiscoveryExportUrl, getDiscoveryCitationsUrl } from '../api';
import { renderDomainList, renderGoTermList } from '../utils/annotationRenderers';
import { escapeHtml } from '../escapeHtml';

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

// Per-structure "what is this?" panel: submit one structure to Foldseek,
// then render the resulting neighbor hits + annotation summary at whichever
// detail level the user picks. Unlike the old DiscoverTab, this has no
// pdb-id input or own ligand section of its own - the caller (WorkspaceTab)
// already knows which structure to run this for, and Ligands/Analytics
// tabs now handle ligand/pocket data for any structure count (see
// LigandTab/AnalyticsTab's runId-optional guards).
export class DiscoveryPanel {
    element = null;
    isRunning = false;
    detailLevel = 'student';
    results = null;
    pdbId = null;
    selectedDatabases = new Set(DATABASE_OPTIONS.filter(d => d.default).map(d => d.key));

    constructor(props = {}) {
        this.onClose = props.onClose || (() => {});
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex flex-col gap-4 p-4 rounded-md bg-surface-raised border border-border-subtle";
        div.id = "discovery-panel-container";

        div.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[18px] text-accent">travel_explore</span>
                    <span class="font-label-md text-label-md">Discover: <span id="discovery-panel-pdbid" class="font-mono">${escapeHtml(this.pdbId || '')}</span></span>
                </div>
                <button id="discovery-panel-close-btn" class="text-secondary hover:text-primary" aria-label="Close">
                    <span class="material-symbols-outlined text-[18px]">close</span>
                </button>
            </div>

            <p class="font-body-sm text-secondary max-w-[560px]">
                Searches this structure against Foldseek's structural databases to find known
                proteins with a similar fold, and shows what's known about them - structure is
                conserved far longer than sequence, so this can find connections sequence search misses.
            </p>

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
                    <label class="flex flex-col gap-1">
                        <span class="font-label-sm text-label-sm text-secondary">Notify me when done - we'll POST to this URL when the job finishes (optional)</span>
                        <input id="discover-webhook-url" type="url" placeholder="https://..." class="w-full max-w-[320px] bg-surface border border-border rounded-md px-2 py-1 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent font-mono" />
                    </label>
                    <button id="discover-rerun-btn" class="btn-secondary self-start px-4 py-1.5 rounded-sm font-label-sm text-label-sm">Search again</button>
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
        `;

        this.element = div;
        this.element.querySelector('#discovery-panel-close-btn').addEventListener('click', () => this.onClose());
        this.element.querySelector('#discover-rerun-btn').addEventListener('click', () => { void this.runFor(this.pdbId); });
        this.element.querySelectorAll('.discover-db-checkbox').forEach(cb => {
            cb.addEventListener('change', () => {
                if (cb.checked) this.selectedDatabases.add(cb.dataset.db);
                else this.selectedDatabases.delete(cb.dataset.db);
                this.updateDbSummary();
            });
        });
        this.updateDbSummary();

        if (this.results) {
            this.syncDbCheckboxes(this.results.databases_searched);
            this.renderResults();
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
        const btn = this.element.querySelector('#discover-rerun-btn');
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

    async runFor(pdbId) {
        this.pdbId = pdbId;
        if (this.element) {
            this.element.querySelector('#discovery-panel-pdbid').textContent = pdbId;
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
            const webhookUrl = this.element.querySelector('#discover-webhook-url')?.value.trim();
            const submission = webhookUrl
                ? await submitDiscoveryJob(pdbId, Array.from(this.selectedDatabases), webhookUrl)
                : await submitDiscoveryJob(pdbId, Array.from(this.selectedDatabases));
            const job = await pollJobUntilDone(submission.job_id, {
                onTick: (j) => this.setStatus(this.statusMessageForJob(j.status)),
            });
            if (job.status === 'failed') {
                throw new Error(job.error || 'Discovery pipeline failed.');
            }
            this.results = job.results;
            this.setStatus(null);
            this.renderResults();
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
        this.pdbId = results ? results.pdb_id : null;
        this.detailLevel = 'student';
        if (this.element) {
            if (results) this.element.querySelector('#discovery-panel-pdbid').textContent = results.pdb_id;
            if (results) this.syncDbCheckboxes(results.databases_searched);
            this.setError(null);
            this.setStatus(null);
            this.renderResults();
        }
    }

    renderResults() {
        const container = this.element.querySelector('#discover-results');
        if (!container) return;
        container.innerHTML = '';
        if (!this.results) return;

        const r = this.results;
        const ann = r.annotations;
        const sourceLabel = SOURCE_LABELS[r.source] || 'PDB';

        const wrapper = document.createElement('div');
        wrapper.className = "flex flex-col gap-4 border-t border-border pt-6";

        const topBar = document.createElement('div');
        topBar.className = "flex items-center justify-between flex-wrap gap-3";

        const infoGroup = document.createElement('div');
        infoGroup.className = "flex items-center gap-2";

        const pdbSpan = document.createElement('span');
        pdbSpan.className = "font-headline-sm text-body-md font-bold text-primary font-mono";
        pdbSpan.textContent = r.pdb_id;

        const sourceBadge = document.createElement('span');
        sourceBadge.className = "px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase source-badge";
        sourceBadge.textContent = sourceLabel;

        const matchesSpan = document.createElement('span');
        matchesSpan.className = "font-body-sm text-[11px] text-secondary";
        matchesSpan.textContent = `${r.hit_count} structural matches (${(r.databases_searched || []).join(', ')})`;

        infoGroup.appendChild(pdbSpan);
        infoGroup.appendChild(sourceBadge);
        infoGroup.appendChild(matchesSpan);

        const detailToggle = document.createElement('div');
        detailToggle.className = "flex gap-1 p-1 rounded-md bg-surface border border-border-subtle w-fit";
        DETAIL_LEVELS.forEach(d => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.dataset.level = d.key;
            btn.className = `detail-level-btn px-3 py-1 rounded-md font-label-sm text-label-sm transition-colors ${this.detailLevel === d.key ? 'bg-accent-muted text-accent' : 'text-secondary hover:text-primary'}`;
            btn.textContent = d.label;
            btn.addEventListener('click', () => this.setDetailLevel(d.key));
            detailToggle.appendChild(btn);
        });

        topBar.appendChild(infoGroup);
        topBar.appendChild(detailToggle);
        wrapper.appendChild(topBar);

        if (r.id) {
            const downloadRow = document.createElement('div');
            downloadRow.className = "flex gap-4";

            const links = [
                { href: getDiscoveryReportUrl(r.id), icon: 'description', label: 'Download Report' },
                { href: getDiscoveryExportUrl(r.id), icon: 'data_object', label: 'Download JSON' },
                { href: getDiscoveryCitationsUrl(r.id), icon: 'format_quote', label: 'Export Citations' },
            ];

            links.forEach(link => {
                const a = document.createElement('a');
                a.href = link.href;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                a.className = "flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:text-primary transition-colors";

                const icon = document.createElement('span');
                icon.className = "material-symbols-outlined text-[16px]";
                icon.textContent = link.icon;

                a.appendChild(icon);
                a.appendChild(document.createTextNode(link.label));
                downloadRow.appendChild(a);
            });
            wrapper.appendChild(downloadRow);
        }

        const bodyContainer = document.createElement('div');
        this.renderBodyInto(bodyContainer, r, ann);
        wrapper.appendChild(bodyContainer);

        container.appendChild(wrapper);
    }

    renderBodyInto(container, r, ann) {
        if (!ann || ann.annotated_neighbor_count === 0) {
            this.renderEmptyAnnotationsInto(container, r);
            return;
        }
        if (this.detailLevel === 'researcher') {
            this.renderResearcherViewInto(container, ann);
            return;
        }
        if (ann.high_confidence_annotated_count === 0) {
            this.renderLowConfidenceMessageInto(container, ann);
            return;
        }
        if (this.detailLevel === 'public') {
            this.renderPublicViewInto(container, ann);
        } else {
            this.renderStudentViewInto(container, ann);
        }
    }

    renderEmptyAnnotationsInto(container, r) {
        const div = document.createElement('div');
        div.className = "py-6 text-center text-secondary font-body-sm";
        div.textContent = r.hit_count > 0
            ? `Found ${r.hit_count} structural matches, but none could be resolved to a protein with known functional annotations yet.`
            : 'No structural matches were found in the searched databases.';
        container.appendChild(div);
    }

    renderLowConfidenceMessageInto(container, ann) {
        const div = document.createElement('div');
        div.className = "py-6 text-center text-secondary font-body-sm max-w-[480px] mx-auto";
        div.textContent = `Found ${ann.annotated_neighbor_count} structurally similar protein(s) with known functional annotations, but none matched with high enough structural confidence (Foldseek probability ≥ ${ann.min_confident_probability}) to state a reliable function hypothesis here. Switch to the Researcher view to see the raw data and judge for yourself.`;
        container.appendChild(div);
    }

    renderPublicViewInto(container, ann) {
        const topDomain = ann.high_confidence_top_domains[0];
        const topGo = ann.high_confidence_top_go_terms[0];

        const div = document.createElement('div');
        div.className = "p-4 rounded-md bg-surface border border-border-subtle font-body-md leading-relaxed";

        div.appendChild(document.createTextNode('This structure looks similar to '));
        if (topDomain) {
            div.appendChild(document.createTextNode('known '));
            const strongDomain = document.createElement('strong');
            strongDomain.textContent = topDomain.name;
            div.appendChild(strongDomain);
            div.appendChild(document.createTextNode('-type proteins'));
        } else {
            div.appendChild(document.createTextNode('proteins with a known function'));
        }

        if (topGo) {
            div.appendChild(document.createTextNode(', which are typically involved in '));
            const strongGo = document.createElement('strong');
            strongGo.textContent = topGo.name;
            div.appendChild(strongGo);
        }
        div.appendChild(document.createTextNode('. This is a computational inference based on structural similarity, not a confirmed experimental result.'));

        container.appendChild(div);
    }

    renderStudentViewInto(container, ann) {
        const topDomain = ann.high_confidence_top_domains[0];
        const topGo = ann.high_confidence_top_go_terms[0];

        const wrapper = document.createElement('div');
        wrapper.className = "flex flex-col gap-4";

        const card = document.createElement('div');
        card.className = "p-4 rounded-md bg-surface border border-border-subtle font-body-md leading-relaxed flex flex-col gap-3";

        const p1 = document.createElement('p');
        p1.appendChild(document.createTextNode(`Out of ${ann.neighbors_considered} of the most confident structural neighbors, `));
        const strongCount = document.createElement('strong');
        strongCount.textContent = ann.high_confidence_annotated_count;
        p1.appendChild(strongCount);
        p1.appendChild(document.createTextNode(` matched a protein with known functional annotations at high enough structural confidence (Foldseek probability ≥ ${ann.min_confident_probability}).`));
        card.appendChild(p1);

        if (topDomain) {
            const p2 = document.createElement('p');
            p2.appendChild(document.createTextNode('The most common protein family among these neighbors is '));
            const strong = document.createElement('strong');
            strong.textContent = topDomain.name;
            p2.appendChild(strong);
            p2.appendChild(document.createTextNode(` (seen in ${topDomain.neighbor_count} of ${ann.high_confidence_annotated_count} confidently-matched neighbors). Because structural fold is conserved much longer than sequence identity over evolution, a strong structural match to a known family is meaningful evidence for shared function - even in cases where sequence similarity alone wouldn't have found the connection.`));
            card.appendChild(p2);
        } else if (topGo) {
            const p2 = document.createElement('p');
            p2.appendChild(document.createTextNode('No single protein family dominates, but a common thread across these neighbors is '));
            const strong = document.createElement('strong');
            strong.textContent = topGo.name;
            p2.appendChild(strong);
            p2.appendChild(document.createTextNode(` (seen in ${topGo.neighbor_count} of ${ann.high_confidence_annotated_count} confidently-matched neighbors) - a shared Gene Ontology annotation that's meaningful evidence for function even without a matching domain family.`));
            card.appendChild(p2);
        }

        wrapper.appendChild(card);

        const domainListHtml = renderDomainList(ann.high_confidence_top_domains, 'Common domains / families');
        if (domainListHtml) {
            const dDiv = document.createElement('div');
            dDiv.innerHTML = domainListHtml;
            wrapper.appendChild(dDiv);
        }

        const goListHtml = renderGoTermList(ann.high_confidence_top_go_terms, 'Common GO terms');
        if (goListHtml) {
            const gDiv = document.createElement('div');
            gDiv.innerHTML = goListHtml;
            wrapper.appendChild(gDiv);
        }

        container.appendChild(wrapper);
    }

    renderResearcherViewInto(container, ann) {
        const wrapper = document.createElement('div');
        wrapper.className = "flex flex-col gap-4";

        const statsGrid = document.createElement('div');
        statsGrid.className = "grid grid-cols-4 gap-4";
        statsGrid.innerHTML = `
            <div class="stat-row"><span class="stat-key">Total hits</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">Candidates examined</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">Resolvable to UniProt</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">Annotated neighbors</span><span class="stat-value"></span></div>
        `;
        const vals1 = statsGrid.querySelectorAll('.stat-value');
        vals1[0].textContent = ann.total_hit_count;
        vals1[1].textContent = ann.candidates_examined;
        vals1[2].textContent = `${ann.resolvable_hit_count} / ${ann.candidates_examined}`;
        vals1[3].textContent = `${ann.annotated_neighbor_count} / ${ann.neighbors_considered}`;
        wrapper.appendChild(statsGrid);

        const statsGrid2 = document.createElement('div');
        statsGrid2.className = "grid grid-cols-3 gap-4";
        statsGrid2.innerHTML = `
            <div class="stat-row"><span class="stat-key">With STRING interactions</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">With Reactome pathways</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">High-confidence</span><span class="stat-value"></span></div>
        `;
        const vals2 = statsGrid2.querySelectorAll('.stat-value');
        vals2[0].textContent = ann.neighbors_with_interactions_count;
        vals2[1].textContent = ann.neighbors_with_pathways_count;
        vals2[2].textContent = `${ann.high_confidence_annotated_count} / ${ann.annotated_neighbor_count}`;
        wrapper.appendChild(statsGrid2);

        const domainListHtml = renderDomainList(ann.top_domains, 'Common domains / families');
        if (domainListHtml) {
            const dDiv = document.createElement('div');
            dDiv.innerHTML = domainListHtml;
            wrapper.appendChild(dDiv);
        }

        const goListHtml = renderGoTermList(ann.top_go_terms, 'Common GO terms');
        if (goListHtml) {
            const gDiv = document.createElement('div');
            gDiv.innerHTML = goListHtml;
            wrapper.appendChild(gDiv);
        }

        this.renderInteractionsAndPathwaysInto(wrapper, ann);
        this.renderHitTableInto(wrapper, this.results.hits);

        container.appendChild(wrapper);
    }

    renderInteractionsAndPathwaysInto(container, ann) {
        const rows = ann.per_neighbor.filter(
            n => n.string_partners.length > 0 || n.reactome_pathways.length > 0
        );
        if (!rows.length) return;

        const wrapper = document.createElement('div');
        wrapper.className = "flex flex-col gap-2";

        const header = document.createElement('span');
        header.className = "font-label-md text-label-md text-secondary uppercase tracking-wider";
        header.textContent = "Interactions & pathways (per neighbor)";
        wrapper.appendChild(header);

        rows.forEach(n => {
            const row = document.createElement('div');
            row.className = "flex flex-col gap-1 py-1.5 border-b border-border-subtle";

            const targetSpan = document.createElement('span');
            targetSpan.className = "font-mono text-[11px] text-secondary";
            targetSpan.textContent = (n.target || '').slice(0, 60);
            row.appendChild(targetSpan);

            if (n.string_partners.length) {
                const stringSpan = document.createElement('span');
                stringSpan.className = "font-body-sm text-[12px]";
                stringSpan.textContent = `STRING partners: ${n.string_partners.map(p => p.partner_name).join(', ')}`;
                row.appendChild(stringSpan);
            }

            if (n.reactome_pathways.length) {
                const reactomeSpan = document.createElement('span');
                reactomeSpan.className = "font-body-sm text-[12px]";
                reactomeSpan.textContent = `Reactome pathways: ${n.reactome_pathways.map(p => p.name).join(', ')}`;
                row.appendChild(reactomeSpan);
            }

            wrapper.appendChild(row);
        });

        container.appendChild(wrapper);
    }

    renderHitTableInto(container, hits) {
        if (!hits || !hits.length) return;

        const wrapper = document.createElement('div');
        wrapper.className = "flex flex-col gap-2";

        const header = document.createElement('span');
        header.className = "font-label-md text-label-md text-secondary uppercase tracking-wider";
        header.textContent = "Top structural matches";
        wrapper.appendChild(header);

        const overflowDiv = document.createElement('div');
        overflowDiv.className = "overflow-x-auto";

        const table = document.createElement('table');
        table.className = "w-full text-left font-body-sm text-[12px]";
        table.innerHTML = `
            <thead>
                <tr class="text-secondary border-b border-border-subtle">
                    <th class="py-1.5 pr-4">Target</th>
                    <th class="py-1.5 pr-4">Prob</th>
                    <th class="py-1.5 pr-4">E-value</th>
                    <th class="py-1.5 pr-4">Seq ID</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;

        const tbody = table.querySelector('tbody');
        const sortedHits = [...hits]
            .sort((a, b) => (Number.parseFloat(a.eval) || 1e9) - (Number.parseFloat(b.eval) || 1e9))
            .slice(0, 20);

        sortedHits.forEach(h => {
            const tr = document.createElement('tr');
            tr.className = "border-b border-border-subtle";

            const tdTarget = document.createElement('td');
            tdTarget.className = "py-1.5 pr-4 font-mono";
            tdTarget.textContent = (h.target || '').slice(0, 60);

            const tdProb = document.createElement('td');
            tdProb.className = "py-1.5 pr-4 font-mono";
            tdProb.textContent = typeof h.prob === 'number' ? h.prob.toFixed(3) : h.prob;

            const tdEval = document.createElement('td');
            tdEval.className = "py-1.5 pr-4 font-mono";
            tdEval.textContent = h.eval;

            const tdSeqId = document.createElement('td');
            tdSeqId.className = "py-1.5 pr-4 font-mono";
            tdSeqId.textContent = h.seqId;

            tr.appendChild(tdTarget);
            tr.appendChild(tdProb);
            tr.appendChild(tdEval);
            tr.appendChild(tdSeqId);
            tbody.appendChild(tr);
        });

        overflowDiv.appendChild(table);
        wrapper.appendChild(overflowDiv);
        container.appendChild(wrapper);
    }
}
