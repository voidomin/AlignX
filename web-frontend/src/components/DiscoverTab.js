import { submitDiscoveryJob, pollJobUntilDone, isValidPdbId } from '../api';

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

// Single-structure "what is this?" workflow: submit one structure to
// Foldseek, then render the resulting neighbor hits + annotation summary
// at whichever detail level the user picks. Self-contained, unlike
// OverviewTab's Compare mode - it doesn't touch selectedPDBs/currentRunId.
export class DiscoverTab {
    constructor() {
        this.element = null;
        this.isRunning = false;
        this.detailLevel = 'student';
        this.results = null;
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
                    <button id="discover-run-btn" class="btn-primary-hard px-5 py-2 rounded-sm font-label-md text-label-md flex items-center gap-2 whitespace-nowrap">
                        <span class="material-symbols-outlined text-[18px]">travel_explore</span>
                        Discover
                    </button>
                </div>

                <div id="discover-status" class="hidden font-body-sm text-secondary flex items-center gap-2">
                    <span id="discover-status-icon" class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                    <span id="discover-status-text"></span>
                </div>
                <div id="discover-error" class="hidden font-body-sm text-error"></div>
                <div id="discover-results"></div>

                <p class="font-body-sm text-[11px] text-secondary border-t border-border-subtle pt-4">
                    Structural search via <a href="https://search.foldseek.com/search" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">Foldseek</a>.
                    Functional annotations via EMBL-EBI's
                    <a href="https://www.ebi.ac.uk/interpro/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">InterPro</a> and
                    <a href="https://www.ebi.ac.uk/QuickGO/" target="_blank" rel="noopener noreferrer" class="text-accent hover:underline">QuickGO</a>.
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

        if (this.results) this.renderResults();
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

        this.setError(null);
        this.setRunning(true);
        this.element.querySelector('#discover-results').innerHTML = '';
        this.setStatus(this.statusMessageForJob('queued'));

        try {
            const submission = await submitDiscoveryJob(pdbId);
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

        const bodyHTML = (!ann || ann.annotated_neighbor_count === 0)
            ? this.renderEmptyAnnotations(r)
            : this.renderTieredBody(ann);

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
                ${bodyHTML}
            </div>
        `;

        container.querySelectorAll('.detail-level-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setDetailLevel(btn.dataset.level));
        });
    }

    renderEmptyAnnotations(r) {
        const reason = r.hit_count > 0
            ? `Found ${r.hit_count} structural matches, but none could be resolved to a protein with known functional annotations yet.`
            : 'No structural matches were found in the searched databases.';
        return `<div class="py-6 text-center text-secondary font-body-sm">${reason}</div>`;
    }

    renderTieredBody(ann) {
        if (this.detailLevel === 'public') return this.renderPublicView(ann);
        if (this.detailLevel === 'researcher') return this.renderResearcherView(ann);
        return this.renderStudentView(ann);
    }

    renderPublicView(ann) {
        // annotated_neighbor_count > 0 only guarantees SOME signal exists
        // (domains OR go_terms) - a neighbor set can have GO terms with zero
        // domain matches (or vice versa), so top_domains/top_go_terms must
        // each be treated as independently possibly-empty here.
        const topDomain = ann.top_domains[0];
        const topGo = ann.top_go_terms[0];
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
        const topDomain = ann.top_domains[0];
        const topGo = ann.top_go_terms[0];
        const consensusParagraph = topDomain
            ? `<p>The most common protein family among these neighbors is <strong>${topDomain.name}</strong>
               (seen in ${topDomain.neighbor_count} of ${ann.annotated_neighbor_count} annotated neighbors).
               Because structural fold is conserved much longer than sequence identity over evolution, a strong
               structural match to a known family is meaningful evidence for shared function - even in cases
               where sequence similarity alone wouldn't have found the connection.</p>`
            : topGo
              ? `<p>No single protein family dominates, but a common thread across these neighbors is
                 <strong>${topGo.name}</strong> (seen in ${topGo.neighbor_count} of ${ann.annotated_neighbor_count}
                 annotated neighbors) - a shared Gene Ontology annotation that's meaningful evidence for function
                 even without a matching domain family.</p>`
              : '';
        return `
            <div class="flex flex-col gap-4">
                <div class="p-4 rounded-md bg-surface-raised border border-border-subtle font-body-md leading-relaxed flex flex-col gap-3">
                    <p>Out of ${ann.neighbors_considered} of the most confident structural neighbors,
                    <strong>${ann.annotated_neighbor_count}</strong> matched a protein with known functional annotations.</p>
                    ${consensusParagraph}
                </div>
                ${this.renderDomainList(ann)}
                ${this.renderGoTermList(ann)}
            </div>
        `;
    }

    renderResearcherView(ann) {
        return `
            <div class="flex flex-col gap-4">
                <div class="grid grid-cols-3 gap-4">
                    <div class="stat-row"><span class="stat-key">Total hits</span><span class="stat-value">${ann.total_hit_count}</span></div>
                    <div class="stat-row"><span class="stat-key">Resolvable to UniProt</span><span class="stat-value">${ann.resolvable_hit_count}</span></div>
                    <div class="stat-row"><span class="stat-key">Annotated neighbors</span><span class="stat-value">${ann.annotated_neighbor_count} / ${ann.neighbors_considered}</span></div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="stat-row"><span class="stat-key">With STRING interactions</span><span class="stat-value">${ann.neighbors_with_interactions_count}</span></div>
                    <div class="stat-row"><span class="stat-key">With Reactome pathways</span><span class="stat-value">${ann.neighbors_with_pathways_count}</span></div>
                </div>
                ${this.renderDomainList(ann)}
                ${this.renderGoTermList(ann)}
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

    renderDomainList(ann) {
        if (!ann.top_domains.length) return '';
        return `
            <div class="flex flex-col gap-2">
                <span class="eyebrow">Common domains / families</span>
                ${ann.top_domains.map(d => `
                    <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                        <span class="font-body-sm">${d.name} <span class="text-secondary text-[11px]">(${d.type})</span></span>
                        <span class="font-mono text-[11px] text-secondary">${d.neighbor_count} neighbors</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderGoTermList(ann) {
        if (!ann.top_go_terms.length) return '';
        return `
            <div class="flex flex-col gap-2">
                <span class="eyebrow">Common GO terms</span>
                ${ann.top_go_terms.map(g => `
                    <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                        <span class="font-body-sm">${g.name || g.id} <span class="text-secondary text-[11px]">(${g.aspect || 'n/a'})</span></span>
                        <span class="font-mono text-[11px] text-secondary">${g.neighbor_count} neighbors</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderHitTable(hits) {
        const rows = [...hits]
            .sort((a, b) => (parseFloat(a.eval) || 1e9) - (parseFloat(b.eval) || 1e9))
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
