(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),e.crossOrigin===`use-credentials`?t.credentials=`include`:e.crossOrigin===`anonymous`?t.credentials=`omit`:t.credentials=`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var e=`http://127.0.0.1:8000`,t=null;function n(e){t=e}function r(e={}){return t?{...e,"X-API-Key":t}:e}function i(t,n){let r=new URL(t,e);if(n)for(let[e,t]of Object.entries(n))t!=null&&r.searchParams.set(e,t);return r.toString()}function a(e){if(!t)return e;let n=new URL(e);return n.searchParams.set(`api_key`,t),n.toString()}var o=/^\d[A-Z0-9]{3}$/,s=/^AF-[A-Z0-9]+-F\d+(-V\d+)?$/,c=/^SM-[A-Z0-9]+$/,l=/^ESM-MGYP\d+$/,u=/^UPLOAD-[A-F0-9]{8}$/,d=/^PRED-[A-F0-9]{8}$/;function f(e){let t=(e||``).trim().toUpperCase();return o.test(t)||s.test(t)||c.test(t)||l.test(t)||u.test(t)||d.test(t)}var p=/^[A-Za-z0-9_-]+$/;function m(e,t){if(typeof e!=`string`||!p.test(e))throw Error(`Invalid ${t}: ${JSON.stringify(e)}`);return e}function h(e,t){if(!f(e))throw Error(`Invalid ${t}: ${JSON.stringify(e)}`);return e}async function g(){let e=await fetch(i(`/health`),{priority:`low`});if(!e.ok)throw Error(`Health check failed`);return e.json()}async function _(e){let t=await fetch(i(`/api/suggest`,{q:e}),{headers:r()});if(!t.ok)throw Error(`Suggestions fetch failed`);return t.json()}async function v(e){let t=await fetch(i(`/api/chains`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify({pdb_ids:e})});if(!t.ok){let e=await t.json();throw Error(e.detail||`Chains fetch failed`)}return t.json()}async function y(e,t){e=h(e,`referencePdbId`);let n=await fetch(i(`/api/screen`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify({reference_pdb_id:e,target_pdb_ids:t})});if(!n.ok){let e=await n.json();throw Error(e.detail||`Structure screen failed`)}return n.json()}async function ee(e){let t=new FormData;t.append(`file`,e);let n=await fetch(i(`/api/upload`),{method:`POST`,headers:r(),body:t});if(!n.ok){let e=await n.json();throw Error(e.detail||`Upload failed`)}return n.json()}async function te(e){let t=await fetch(i(`/api/fold-sequence`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify({sequence:e})});if(!t.ok){let e=await t.json();throw Error(e.detail||`Structure prediction failed`)}return t.json()}async function ne(e,t,n,a){let o=await fetch(i(`/api/jobs/align`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify({pdb_ids:e,chain_selection:t,remove_water:n,remove_heteroatoms:a})});if(!o.ok){let e=await o.json();throw Error(e.detail||`Alignment submission failed`)}return o.json()}async function re(e){e=m(e,`jobId`);let t=await fetch(i(`/api/jobs/${e}`),{headers:r()});if(!t.ok){let e=await t.json();throw Error(e.detail||`Job status fetch failed`)}return t.json()}async function b(e,{intervalMs:t=1500,onTick:n=null}={}){for(;;){let r=await re(e);if(n&&n(r),r.status===`completed`||r.status===`failed`)return r;await new Promise(e=>setTimeout(e,t))}}async function x(e,t){let n={sequences:e};t&&(n.webhook_url=t);let a=await fetch(i(`/api/jobs/clustalo`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify(n)});if(!a.ok){let e=await a.json();throw Error(e.detail||`Clustal Omega submission failed`)}return a.json()}async function S(e,t){let n={sequence:e};t&&(n.webhook_url=t);let a=await fetch(i(`/api/jobs/conservation`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify(n)});if(!a.ok){let e=await a.json();throw Error(e.detail||`Conservation search submission failed`)}return a.json()}async function ie(e,t,n,a,o){e=h(e,`pdbId`),t=m(t,`chain`);let s={pdb_id:e,chain:t,resi:n,mutant:a};o&&(s.webhook_url=o);let c=await fetch(i(`/api/jobs/ddg-stability`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify(s)});if(!c.ok){let e=await c.json();throw Error(e.detail||`Stability prediction submission failed`)}return c.json()}async function ae(e,t,n,a){e=h(e,`pdbId`);let o={pdb_id:e};t&&(o.run_id=m(t,`runId`)),n&&(o.session_id=m(n,`sessionId`)),a&&(o.webhook_url=a);let s=await fetch(i(`/api/jobs/pocket-detection`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify(o)});if(!s.ok){let e=await s.json();throw Error(e.detail||`Pocket detection submission failed`)}return s.json()}async function oe(e,t,n,a,o){e=h(e,`pdbId`);let s={pdb_id:e};t&&(s.chain=m(t,`chain`)),n&&(s.run_id=m(n,`runId`)),a&&(s.session_id=m(a,`sessionId`)),o&&(s.webhook_url=o);let c=await fetch(i(`/api/jobs/sequence-annotation`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify(s)});if(!c.ok){let e=await c.json();throw Error(e.detail||`Sequence annotation submission failed`)}return c.json()}async function C(e,t,n){let a={pdb_id:e};t&&t.length>0&&(a.databases=t),n&&(a.webhook_url=n);let o=await fetch(i(`/api/jobs/discover`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify(a)});if(!o.ok){let e=await o.json();throw Error(e.detail||`Discovery submission failed`)}return o.json()}async function se(e,t){let n=await fetch(i(`/api/clusters`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify({rmsd_df:e,threshold:t})});if(!n.ok){let e=await n.json();throw Error(e.detail||`Clusters fetch failed`)}return n.json()}async function ce(e){e=e?m(e,`excludeRunId`):``;let t=await fetch(i(`/api/comparison/runs`,{exclude_run_id:e}),{headers:r()});if(!t.ok)throw Error(`Comparison runs fetch failed`);return t.json()}async function le(e,t){e=m(e,`currentRunId`),t=m(t,`targetRunId`);let n=await fetch(i(`/api/comparison`,{current_run_id:e,target_run_id:t}),{headers:r()});if(!n.ok){let e=await n.json();throw Error(e.detail||`Comparison fetch failed`)}return n.json()}async function w(e,t){e=h(e,`pdbId`);let n={pdb_id:e};t&&(n.run_id=m(t,`runId`));let a=await fetch(i(`/api/ligands`,n),{headers:r()});if(!a.ok)throw Error(`Ligands fetch failed`);return a.json()}async function ue(e){e=m(e,`ligandCode`);let t=await fetch(i(`/api/ligand-info`,{ligand_code:e}),{headers:r()});if(!t.ok)throw Error(`Ligand info fetch failed`);return t.json()}async function de(e,t){e=h(e,`pdbId`);let n={pdb_id:e};t&&(n.run_id=m(t,`runId`));let a=await fetch(i(`/api/pockets`,n),{headers:r()});if(!a.ok)throw Error(`Pocket detection failed`);return a.json()}async function fe(e,t,n){e=h(e,`pdbId`),t=m(t,`ligandId`);let a={pdb_id:e,ligand_id:t};n&&(a.run_id=m(n,`runId`));let o=await fetch(i(`/api/interactions`,a),{headers:r()});if(!o.ok)throw Error(`Interactions fetch failed`);return o.json()}async function pe(){let e=await fetch(i(`/api/memory`),{headers:r(),priority:`low`});if(!e.ok)throw Error(`Memory stats fetch failed`);return e.json()}async function me(){let e=await fetch(i(`/api/memory/clear`),{method:`POST`,headers:r()});if(!e.ok)throw Error(`Clear memory execution failed`);return e.json()}async function T(e){e=m(e,`runId`);let t=await fetch(i(`/api/runs/${e}`),{headers:r()});if(!t.ok){let e=await t.json();throw Error(e.detail||`Run fetch failed`)}return t.json()}function he(e){e=m(e,`runId`);let t=new URL(window.location.origin);return t.searchParams.set(`shared_run`,e),a(t.toString())}async function E(e=20,t=0){let n=await fetch(i(`/api/history`,{limit:e,offset:t}),{headers:r()});if(!n.ok)throw Error(`History fetch failed`);return n.json()}async function ge(e){e=m(e,`runId`);let t=await fetch(i(`/api/history/${e}`),{method:`DELETE`,headers:r()});if(!t.ok){let e=await t.json();throw Error(e.detail||`Failed to delete run`)}return t.json()}async function _e(e,{notes:t,tags:n}={}){e=m(e,`runId`);let a=await fetch(i(`/api/history/${e}/notes`),{method:`PUT`,headers:{...r(),"Content-Type":`application/json`},body:JSON.stringify({notes:t??null,tags:n??null})});if(!a.ok){let e=await a.json();throw Error(e.detail||`Failed to update run notes`)}return a.json()}async function ve(){let e=await fetch(i(`/api/history`),{method:`DELETE`,headers:r()});if(!e.ok){let t=await e.json();throw Error(t.detail||`Failed to clear history`)}return e.json()}async function ye(){let e=await fetch(i(`/api/stats`),{headers:r()});if(!e.ok)throw Error(`Stats fetch failed`);return e.json()}async function D(e,t){e=m(e,`runId`);let n={run_id:e};t&&(n.motif=t);let a=await fetch(i(`/api/sequence`,n),{headers:r()});if(!a.ok)throw Error(`Sequence alignment fetch failed`);return a.json()}function O(e){return e=m(e,`runId`),a(i(`/results/${e}/alignment.pdb`))}function be(e){return e=m(e,`runId`),a(i(`/results/${e}/alignment.fasta`))}function xe(e,t,n,r){e=m(e,`runId`),t=h(t,`pdbIdA`),n=h(n,`pdbIdB`);let o={run_id:e,pdb_id_a:t,pdb_id_b:n};return r&&(o.num_frames=r),a(i(`/api/morph`,o))}function Se(e,t){e=h(e,`pdbId`);let n={pdb_id:e};return t&&(n.session_id=m(t,`sessionId`)),a(i(`/api/structure-file`,n))}var Ce=new Set([`summary`,`insights`,`heatmap`,`tree`,`matrix`]);function k(e,t){return e=m(e,`runId`),!t||t.length===0?a(i(`/api/report`,{run_id:e})):(t.forEach(e=>{if(!Ce.has(e))throw Error(`Invalid report section: ${JSON.stringify(e)}`)}),a(i(`/api/report`,{run_id:e,sections:t.join(`,`)})))}function we(e){return e=m(e,`runId`),a(i(`/api/notebook`,{run_id:e}))}function Te(e){return e=m(e,`runId`),a(i(`/api/notebook/ipynb`,{run_id:e}))}function Ee(e){return e=m(e,`runId`),a(i(`/api/report/citations`,{run_id:e}))}function De(e){return e=m(e,`runId`),a(i(`/api/report/rmsd-csv`,{run_id:e}))}function Oe(e){return e=m(e,`runId`),a(i(`/api/report/heatmap-png`,{run_id:e}))}function A(e){return e=m(e,`runId`),a(i(`/api/report/zip`,{run_id:e}))}function ke(e){return e=m(e,`runId`),a(i(`/api/report/newick`,{run_id:e}))}function Ae(e){return e=m(e,`runId`),a(i(`/api/report/pymol-script`,{run_id:e}))}function je(e){return e=m(e,`runId`),a(i(`/api/report/chimerax-script`,{run_id:e}))}async function j(e,t){e=h(e,`pdbId`);let n={pdb_id:e};t&&(n.chain=m(t,`chain`));let a=await fetch(i(`/api/annotations`,n),{headers:r()});if(!a.ok)throw Error(`Annotation fetch failed`);return a.json()}async function Me(e,t,n,a){e=h(e,`pdbId`),t=m(t,`chain`);let o=await fetch(i(`/api/mutation-impact`,{pdb_id:e,chain:t,resi:n,mutant:a}),{headers:r()});if(!o.ok)throw Error(`Mutation impact fetch failed`);return o.json()}async function Ne(e){e=h(e,`pdbId`);let t=await fetch(i(`/api/validation`,{pdb_id:e}),{headers:r()});if(!t.ok)throw Error(`Validation fetch failed`);return t.json()}async function Pe(e,t){e=h(e,`pdbId`);let n={pdb_id:e};t&&(n.run_id=m(t,`runId`));let a=await fetch(i(`/api/qc`,n),{headers:r()});if(!a.ok)throw Error(`QC fetch failed`);return a.json()}async function Fe(e){let t=await fetch(i(`/api/runs/trend`),{method:`POST`,headers:{...r(),"Content-Type":`application/json`},body:JSON.stringify({run_ids:e})});if(!t.ok){let e=await t.json();throw Error(e.detail||`Run trend fetch failed`)}return t.json()}async function Ie(e,t){e=h(e,`pdbId`);let n={pdb_id:e};t&&(n.chain=m(t,`chain`));let a=await fetch(i(`/api/mutation-tolerance`,n),{headers:r()});if(!a.ok)throw Error(`Mutation tolerance fetch failed`);return a.json()}async function Le(e,t){e=h(e,`pdbId`);let n={pdb_id:e};t&&(n.chain=m(t,`chain`));let a=await fetch(i(`/api/disorder`,n),{headers:r()});if(!a.ok)throw Error(`Disorder prediction fetch failed`);return a.json()}async function M(e,t,n){e=h(e,`pdbId`);let a={pdb_id:e};t&&(a.run_id=m(t,`runId`)),n&&(a.session_id=m(n,`sessionId`));let o=await fetch(i(`/api/flexibility`,a),{headers:r()});if(!o.ok){let e=await o.json();throw Error(e.detail||`Flexibility prediction fetch failed`)}return o.json()}async function Re(e,t,n){e=h(e,`pdbId`);let a={pdb_id:e};t&&(a.run_id=m(t,`runId`)),n&&(a.session_id=m(n,`sessionId`));let o=await fetch(i(`/api/clash-score`,a),{headers:r()});if(!o.ok){let e=await o.json();throw Error(e.detail||`Clash score fetch failed`)}return o.json()}async function ze(e){e=h(e,`pdbId`);let t=await fetch(i(`/api/cath`,{pdb_id:e}),{headers:r()});if(!t.ok)throw Error(`CATH classification fetch failed`);return t.json()}async function Be(e){e=h(e,`pdbId`);let t=await fetch(i(`/api/assembly`,{pdb_id:e}),{headers:r()});if(!t.ok)throw Error(`Assembly info fetch failed`);return t.json()}async function Ve(e){e=h(e,`pdbId`);let t=await fetch(i(`/api/pae`,{pdb_id:e}),{headers:r()});if(!t.ok)throw Error(`PAE fetch failed`);return t.json()}async function He(e){e=h(e,`pdbId`);let t=await fetch(i(`/api/pae-domains`,{pdb_id:e}),{headers:r()});if(!t.ok){let e=await t.json();throw Error(e.detail||`PAE domain segmentation fetch failed`)}return t.json()}async function Ue(e,t,n){e=m(e,`runId`),t=m(t,`pdbId`);let a={run_id:e,pdb_id:t};n!==void 0&&(a.threshold=n);let o=await fetch(i(`/api/contact-map`,a),{headers:r()});if(!o.ok)throw Error(`Contact map fetch failed`);return o.json()}async function We(e,t,n){e=m(e,`runId`),t=m(t,`pdbIdA`),n=m(n,`pdbIdB`);let a=await fetch(i(`/api/difference-distance`,{run_id:e,pdb_id_a:t,pdb_id_b:n}),{headers:r()});if(!a.ok)throw Error(`Difference-distance fetch failed`);return a.json()}async function Ge(e,t,n,a){e=h(e,`pdbId`),t=m(t,`chainA`),n=m(n,`chainB`);let o={pdb_id:e,chain_a:t,chain_b:n};a&&(o.run_id=m(a,`runId`));let s=await fetch(i(`/api/interface`,o),{headers:r()});if(!s.ok){let e=await s.json();throw Error(e.detail||`Interface analysis fetch failed`)}return s.json()}async function Ke(){let e=await fetch(i(`/api/settings`),{headers:r()});if(!e.ok)throw Error(`Settings fetch failed`);return e.json()}async function qe(e){let t=await fetch(i(`/api/settings`),{method:`POST`,headers:r({"Content-Type":`application/json`}),body:JSON.stringify(e)});if(!t.ok){let e=(await t.json()).detail;throw Error(typeof e==`string`?e:`Failed to save settings`)}return t.json()}async function Je(){let e=await fetch(i(`/api/settings/reset`),{method:`POST`,headers:r()});if(!e.ok)throw Error(`Failed to reset settings`);return e.json()}function Ye(e){return e=m(e,`runId`),a(i(`/api/discover/report`,{run_id:e}))}function Xe(e){return e=m(e,`runId`),a(i(`/api/discover/export`,{run_id:e}))}function Ze(e){return e=m(e,`runId`),a(i(`/api/discover/citations`,{run_id:e}))}function N(e,t,n){e.addEventListener(`keydown`,r=>{if(![`ArrowLeft`,`ArrowRight`,`Home`,`End`].includes(r.key))return;let i=Array.from(e.querySelectorAll(t)),a=i.indexOf(document.activeElement);if(a===-1)return;r.preventDefault();let o;o=r.key===`ArrowLeft`?(a-1+i.length)%i.length:r.key===`ArrowRight`?(a+1)%i.length:r.key===`Home`?0:i.length-1;let s=i[o];s.focus(),n(s)})}function Qe(){let e=document.getElementById(`desktop-download-modal`);e&&e.remove();let t=document.createElement(`div`);t.id=`desktop-download-modal`,t.className=`fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity duration-200`,t.innerHTML=`
        <div class="relative w-full max-w-2xl bg-surface border border-border rounded-xl shadow-2xl p-6 flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
            <div class="flex items-start justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center text-accent">
                        <span class="material-symbols-outlined text-[24px]">desktop_windows</span>
                    </div>
                    <div>
                        <h3 class="font-headline-sm text-headline-sm font-bold text-primary">StructScope Desktop Edition</h3>
                        <p class="font-body-sm text-body-sm text-secondary">Run unlimited alignments &amp; custom structures with 100% privacy on your own PC.</p>
                    </div>
                </div>
                <button id="close-desktop-modal-btn" type="button" class="text-secondary hover:text-primary p-1 rounded-md transition-colors" aria-label="Close modal">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <!-- Key Benefits Grid -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div class="p-3 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1">
                    <span class="material-symbols-outlined text-[20px] text-accent">lock</span>
                    <span class="font-label-sm text-label-sm font-semibold text-primary">100% Private</span>
                    <span class="font-body-sm text-[12px] text-secondary">Your proprietary structures never leave your local computer.</span>
                </div>
                <div class="p-3 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1">
                    <span class="material-symbols-outlined text-[20px] text-accent">all_inclusive</span>
                    <span class="font-label-sm text-label-sm font-semibold text-primary">Zero Limits</span>
                    <span class="font-body-sm text-[12px] text-secondary">No server timeouts, RAM caps, or protein size restrictions.</span>
                </div>
                <div class="p-3 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1">
                    <span class="material-symbols-outlined text-[20px] text-accent">speed</span>
                    <span class="font-label-sm text-label-sm font-semibold text-primary">Full Performance</span>
                    <span class="font-body-sm text-[12px] text-secondary">Direct multi-core CPU and native Mustang/Foldseek speed.</span>
                </div>
            </div>

            <!-- Distribution Options -->
            <div class="flex flex-col gap-3">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Choose your local setup:</span>

                <!-- Option 1: Docker -->
                <div class="p-4 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md font-semibold text-primary flex items-center gap-1.5">
                            <span class="material-symbols-outlined text-[18px] text-accent">inventory_2</span>
                            Docker Container (Recommended)
                        </span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-accent-muted text-accent">Plug &amp; Play</span>
                    </div>
                    <span class="font-body-sm text-body-sm text-secondary">Pre-compiles Mustang binary and all dependencies inside an isolated container:</span>
                    <pre class="bg-surface p-2.5 rounded border border-border-subtle font-mono text-[12px] text-primary overflow-x-auto select-all">docker run -p 8000:8000 alignx</pre>
                </div>

                <!-- Option 2: Local Python Launcher -->
                <div class="p-4 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md font-semibold text-primary flex items-center gap-1.5">
                            <span class="material-symbols-outlined text-[18px] text-accent">terminal</span>
                            Python Local Environment
                        </span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-surface border border-border text-secondary">Native</span>
                    </div>
                    <span class="font-body-sm text-body-sm text-secondary">Run directly on Windows (WSL/Bio3D), macOS, or Linux:</span>
                    <pre class="bg-surface p-2.5 rounded border border-border-subtle font-mono text-[12px] text-primary overflow-x-auto select-all">git clone https://github.com/voidomin/AlignX.git
cd AlignX &amp;&amp; python scripts/launch_desktop.py</pre>
                </div>
            </div>

            <div class="flex items-center justify-end gap-3 pt-3 border-t border-border">
                <a href="https://github.com/voidomin/AlignX" target="_blank" rel="noopener noreferrer" class="btn-secondary px-4 py-2 rounded-md font-label-md text-label-md flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-[16px]">code</span>
                    GitHub Repository
                </a>
                <button id="dismiss-desktop-modal-btn" type="button" class="btn-primary px-4 py-2 rounded-md font-label-md text-label-md">
                    Got it, thanks!
                </button>
            </div>
        </div>
    `,document.body.appendChild(t);let n=()=>t.remove(),r=t.querySelector(`#close-desktop-modal-btn`);r&&r.addEventListener(`click`,n);let i=t.querySelector(`#dismiss-desktop-modal-btn`);i&&i.addEventListener(`click`,n),t.addEventListener(`click`,e=>{e.target===t&&n()})}var $e=[{key:`workspace`,label:`Workspace`,group:`Workspace`},{key:`ligands`,label:`Ligands`,group:`Results`},{key:`sequence`,label:`Sequence`,group:`Results`},{key:`analytics`,label:`Analytics`,group:`Results`},{key:`clusters`,label:`Clusters`,group:`Results`},{key:`comparison`,label:`Diff Runs`,group:`Manage`},{key:`history`,label:`History`,group:`Manage`},{key:`dashboard`,label:`Dashboard`,group:`Manage`},{key:`settings`,label:`Settings`,group:`Manage`}],et=class{constructor(e){this.onTabChange=e.onTabChange,this.onExportData=e.onExportData,this.onNewWorkspace=e.onNewWorkspace,this.activeTab=`workspace`,this.element=null,this.memoryInterval=null}render(){let e=document.createElement(`header`);return e.className=`sticky top-0 z-50 bg-surface border-b border-border shrink-0`,e.innerHTML=`
            <div class="max-w-[1600px] mx-auto px-6 py-3 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2 lg:gap-6">
                <div class="flex items-center gap-2.5 shrink-0">
                    <span class="material-symbols-outlined text-[20px] text-accent">science</span>
                    <span class="font-headline-md text-headline-md font-bold text-primary">StructScope</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium tracking-wide uppercase bg-accent-muted text-accent border border-accent/20" title="Interactive Web Showcase - optimized for quick comparisons and curated demos">Web Demo</span>
                </div>

                <div id="topbar-tabs-wrapper" class="flex items-center w-full lg:w-auto lg:flex-1 min-w-0">
                    <button id="topbar-scroll-left" class="hidden shrink-0 w-8 h-8 items-center justify-center rounded-md bg-surface border border-border-subtle text-secondary hover:text-primary transition-colors mr-1" title="Scroll tabs left" aria-label="Scroll tabs left">
                        <span class="material-symbols-outlined text-[16px]">chevron_left</span>
                    </button>
                    <nav id="topbar-tabs" role="tablist" class="flex items-center gap-1 min-w-0 overflow-x-auto scroll-smooth">
                        ${$e.map((e,t)=>`
                            ${t>0&&e.group!==$e[t-1].group?`<div class="w-px h-5 bg-border-subtle mx-1.5 shrink-0" aria-hidden="true"></div>`:``}
                            <button data-tab="${e.key}" role="tab" class="tab-trigger px-3 py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors" aria-selected="${e.key===`workspace`}" tabindex="${e.key===`workspace`?`0`:`-1`}">${e.label}</button>
                        `).join(``)}
                    </nav>
                    <button id="topbar-scroll-right" class="hidden shrink-0 w-8 h-8 items-center justify-center rounded-md bg-surface border border-border-subtle text-secondary hover:text-primary transition-colors ml-1" title="Scroll tabs right" aria-label="Scroll tabs right">
                        <span class="material-symbols-outlined text-[16px]">chevron_right</span>
                    </button>
                </div>

                <div class="flex items-center flex-wrap lg:flex-nowrap gap-3 shrink-0 font-mono text-label-sm">
                    <button id="topbar-download-desktop-btn" class="btn-primary px-3 py-1.5 rounded-md font-label-md text-label-md flex items-center gap-1.5 shadow-sm" title="Download Desktop Edition for unlimited large files & private local compute">
                        <span class="material-symbols-outlined text-[16px]">desktop_windows</span>
                        Desktop App
                    </button>
                    <button id="topbar-new-ws-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">New Workspace</button>
                    <button id="topbar-export-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Export</button>
                    <div class="h-5 w-px bg-border"></div>
                    <span id="topbar-health-status" class="text-secondary truncate max-w-[200px]">Alignment engine: Checking...</span>
                    <span id="topbar-ram-text" class="text-muted">--</span>
                    <button id="topbar-free-ram-btn" class="text-accent hover:text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:text-accent" title="Runs garbage collection on the shared server process - affects all users, not just your session">Free up memory</button>
                </div>
            </div>
        `,this.element=e,this.updateTabStyles(),this.setupEventListeners(),this.setupTabScrollAffordance(),this.startMemoryTracking(),e}setupTabScrollAffordance(){let e=this.element.querySelector(`#topbar-tabs`),t=this.element.querySelector(`#topbar-scroll-left`),n=this.element.querySelector(`#topbar-scroll-right`),r=()=>{let r=e.scrollLeft>2,i=e.scrollLeft+e.clientWidth<e.scrollWidth-2;t.classList.toggle(`hidden`,!r),t.classList.toggle(`flex`,r),n.classList.toggle(`hidden`,!i),n.classList.toggle(`flex`,i)};t.addEventListener(`click`,()=>e.scrollBy({left:-150,behavior:`smooth`})),n.addEventListener(`click`,()=>e.scrollBy({left:150,behavior:`smooth`})),e.addEventListener(`scroll`,r),window.addEventListener(`resize`,r),this._updateScrollArrows=r,requestAnimationFrame(r)}setupEventListeners(){this.element.querySelectorAll(`.tab-trigger`).forEach(e=>{e.addEventListener(`click`,()=>{let t=e.dataset.tab;this.switchTab(t),this.onTabChange(t)})}),N(this.element.querySelector(`#topbar-tabs`),`.tab-trigger`,e=>{let t=e.dataset.tab;this.switchTab(t),this.onTabChange(t)}),this.element.querySelector(`#topbar-export-btn`).addEventListener(`click`,()=>this.onExportData()),this.element.querySelector(`#topbar-new-ws-btn`).addEventListener(`click`,()=>this.onNewWorkspace());let e=this.element.querySelector(`#topbar-download-desktop-btn`);e&&e.addEventListener(`click`,()=>Qe());let t=this.element.querySelector(`#topbar-free-ram-btn`);t.addEventListener(`click`,async()=>{t.innerText=`Clearing...`,t.disabled=!0;try{let e=await me();this.updateMemoryDisplay(e.ram_mb)}catch(e){console.error(`Free memory failed:`,e)}finally{t.innerText=`Free up memory`,t.disabled=!1}})}switchTab(e){this.activeTab=e,this.updateTabStyles()}updateTabStyles(){this.element.querySelectorAll(`.tab-trigger`).forEach(e=>{let t=e.dataset.tab===this.activeTab;e.className=`tab-trigger px-3 py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors ${t?`bg-accent-muted text-accent`:`text-secondary hover:text-primary`}`,e.setAttribute(`aria-selected`,String(t)),e.tabIndex=t?0:-1,t&&e.scrollIntoView({behavior:`smooth`,inline:`nearest`,block:`nearest`})}),this._updateScrollArrows&&requestAnimationFrame(this._updateScrollArrows)}startMemoryTracking(){let e=async()=>{try{let e=await pe();this.updateMemoryDisplay(e.ram_mb)}catch(e){console.warn(`Top bar memory update failed:`,e)}try{let e=await g(),t=this.element.querySelector(`#topbar-health-status`);if(t&&e)if(e.mustang_installed){let n=(e.mustang_message||``).toLowerCase().includes(`wsl`)?`WSL`:`Native`;t.innerText=`Alignment engine: Ready`,t.title=`Runs via Mustang, in ${n} mode`,t.className=`text-success truncate max-w-[200px]`}else t.innerText=`Alignment engine: Offline`,t.title=`Mustang could not be found on the server`,t.className=`text-error truncate max-w-[200px]`}catch(e){console.warn(`Top bar health update failed:`,e);let t=this.element.querySelector(`#topbar-health-status`);t&&(t.innerText=`Alignment engine: Disconnected`,t.title=`Could not reach the backend server`,t.className=`text-error truncate max-w-[200px]`)}};this.initialPollTimeout=setTimeout(()=>{e()},3e3),this.memoryInterval=setInterval(()=>{e()},2e4)}updateMemoryDisplay(e){let t=this.element.querySelector(`#topbar-ram-text`);t&&(t.innerText=`${e} MB`)}destroy(){this._updateScrollArrows&&window.removeEventListener(`resize`,this._updateScrollArrows),clearTimeout(this.initialPollTimeout),clearInterval(this.memoryInterval)}},P=[`#8B5CF6`,`#06B6D4`,`#EC4899`,`#A3E635`,`#FB923C`,`#2DD4BF`];function F(e){return P[e%P.length]}var tt=[{key:`cartoon`,label:`Cartoon`},{key:`stick`,label:`Stick`},{key:`sphere`,label:`Sphere`},{key:`line`,label:`Line`}],nt=[{key:`chain`,label:`Chain identity`,group:`General`,title:`Colors each structure a distinct color - always available.`},{key:`secondary`,label:`Secondary structure`,group:`General`,title:`Colors by real backbone secondary structure (helix/sheet/coil) - always available.`},{key:`spectrum`,label:`Spectrum (N→C)`,group:`General`,title:`Colors along a gradient from the N-terminus to the C-terminus - always available.`},{key:`confidence`,label:`pLDDT Confidence`,group:`Prediction-derived`,title:`Requires an AlphaFold- or ESM Atlas-sourced structure in the run.`},{key:`pae-domains`,label:`PAE-derived domains`,group:`Prediction-derived`,title:`Requires an AlphaFold-sourced structure in the run (needs its real PAE matrix).`},{key:`flexibility`,label:`Predicted flexibility (GNM)`,group:`Prediction-derived`,title:`A real-time Gaussian Network Model prediction, computed from any structure's own coordinates.`},{key:`missense`,label:`Mutation tolerance (AlphaMissense)`,group:`External annotation`,title:`Requires a resolvable UniProt accession for the structure.`},{key:`domain`,label:`InterPro domains`,group:`External annotation`,title:`Requires a resolvable UniProt accession for the structure.`},{key:`disorder`,label:`Sequence disorder (MobiDB)`,group:`External annotation`,title:`Requires a resolvable UniProt accession for the structure.`}],I=[`#38BDF8`,`#F472B6`,`#84CC16`,`#A78BFA`,`#FB7185`,`#2DD4BF`,`#FBBF24`,`#60A5FA`];function L(e){return I[e%I.length]}var R=`#F59E0B`,rt=class{element=null;viewer=null;currentRunId=null;isSurfaceVisible=!1;structures=[];rmsdDf=null;currentStyle=`cartoon`;currentColorScheme=`chain`;missenseScoresByPdbId={};domainColorsByPdbId={};disorderScoresByPdbId={};flexibilityScoresByPdbId={};paeDomainColorsByPdbId={};interactionMode=`inspect`;inspectLabelHandle=null;measurePoints=[];measureHandles=[];isSpinning=!1;isMorphing=!1;render(){let e=document.createElement(`div`);return e.className=`flex-1 panel-raised shadow-panel rounded-lg flex flex-col overflow-hidden relative [&:fullscreen]:rounded-none`,e.innerHTML=`
            <!-- Viewport Header -->
            <div class="px-4 py-3 border-b border-border flex flex-col gap-2">
                <div class="flex justify-between items-center">
                    <h3 class="font-body-md text-body-md font-semibold text-primary">Superposition Viewer</h3>
                    <div class="flex gap-2 items-center">
                        <details id="viewer-style-picker" class="group relative">
                            <summary class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors cursor-pointer select-none flex items-center gap-0.5 list-none [&::-webkit-details-marker]:hidden" title="Representation Style" aria-label="Representation Style">
                                <span class="material-symbols-outlined text-[18px]">view_in_ar</span>
                                <span class="material-symbols-outlined text-[14px] group-open:rotate-180 transition-transform">expand_more</span>
                            </summary>
                            <div class="absolute right-0 top-full mt-1 z-20 bg-surface border border-border rounded-md shadow-panel p-1 flex flex-col gap-0.5 min-w-[130px]">
                                ${tt.map(e=>`
                                    <button data-style="${e.key}" class="viewer-style-option text-left px-2 py-1 rounded-sm font-label-sm text-label-sm text-secondary hover:text-primary hover:bg-surface-raised transition-colors">${e.label}</button>
                                `).join(``)}
                            </div>
                        </details>
                        <details id="viewer-colorscheme-picker" class="group relative">
                            <summary class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors cursor-pointer select-none flex items-center gap-0.5 list-none [&::-webkit-details-marker]:hidden" title="Color Scheme" aria-label="Color Scheme">
                                <span class="material-symbols-outlined text-[18px]">palette</span>
                                <span class="material-symbols-outlined text-[14px] group-open:rotate-180 transition-transform">expand_more</span>
                            </summary>
                            <div class="absolute right-0 top-full mt-1 z-20 bg-surface border border-border rounded-md shadow-panel p-1 flex flex-col gap-0.5 min-w-[220px] max-h-[70vh] overflow-y-auto">
                                ${(()=>{let e=null;return nt.map(t=>{let n=t.group===e?``:`<span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider px-2 pt-1.5 pb-0.5 ${e===null?``:`mt-1 border-t border-border-subtle`}">${t.group}</span>`;return e=t.group,`
                                    ${n}
                                    <button data-scheme="${t.key}" title="${t.title}" class="viewer-colorscheme-option text-left px-2 py-1 rounded-sm font-label-sm text-label-sm text-secondary hover:text-primary hover:bg-surface-raised transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-secondary" ${t.key===`confidence`?`disabled`:``}>${t.label}</button>
                                `}).join(``)})()}
                            </div>
                        </details>
                        <button id="btn-toggle-surface" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Surface" aria-label="Toggle Surface">
                            <span class="material-symbols-outlined text-[18px]">blur_on</span>
                        </button>
                        <button id="btn-reset-view" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Reset View" aria-label="Reset View">
                            <span class="material-symbols-outlined text-[18px]">center_focus_strong</span>
                        </button>
                    </div>
                </div>
                <div class="flex justify-end gap-2 items-center">
                    <button id="btn-toggle-spin" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Auto-Spin" aria-label="Toggle Auto-Spin">
                        <span class="material-symbols-outlined text-[18px]">autorenew</span>
                    </button>
                    <button id="btn-toggle-morph" disabled class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-secondary" title="Play Morph Animation (2-structure alignments only)" aria-label="Play Morph Animation">
                        <span class="material-symbols-outlined text-[18px]">movie</span>
                    </button>
                    <button id="btn-toggle-fullscreen" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Fullscreen" aria-label="Toggle Fullscreen">
                        <span class="material-symbols-outlined text-[18px]">fullscreen</span>
                    </button>
                    <button id="btn-toggle-measure" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Measurement Mode" aria-label="Toggle Measurement Mode">
                        <span class="material-symbols-outlined text-[18px]">straighten</span>
                    </button>
                    <button id="btn-screenshot" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Download Screenshot (PNG)" aria-label="Download Screenshot (PNG)">
                        <span class="material-symbols-outlined text-[18px]">photo_camera</span>
                    </button>
                    <button id="btn-download-pdb" disabled class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-secondary" title="Download Superimposed Aligned PDB (1-Click)" aria-label="Download Superimposed Aligned PDB">
                        <span class="material-symbols-outlined text-[18px]">download_for_offline</span>
                    </button>
                    <button id="btn-download-zip" disabled class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-secondary" title="Download Complete Alignment Bundle (ZIP)" aria-label="Download Complete Alignment Bundle (ZIP)">
                        <span class="material-symbols-outlined text-[18px]">folder_zip</span>
                    </button>
                </div>
            </div>

            <!-- 3D Canvas Area -->
            <div id="3d-canvas-container" class="flex-grow relative bg-bg overflow-hidden min-h-[300px]">
                <!-- 3Dmol viewer div (positioned absolutely to fill the container) -->
                <div id="viewer-canvas-3dmol" class="w-full h-full absolute inset-0 z-0"></div>

                <!-- Placeholder shown only before an alignment has been run -->
                <div id="ambient-placeholder" class="absolute inset-0 flex items-center justify-center pointer-events-none z-5 px-8 text-center">
                    <span class="font-body-sm text-body-sm text-muted">Add 2+ structures and run alignment to view superposition</span>
                </div>

                <!-- HUD: dynamic per-structure legend -->
                <div id="hud-structure-legend" class="absolute top-4 left-4 bg-surface border border-border px-3 py-1.5 rounded-md flex flex-col gap-1.5 z-10 max-w-[240px]"></div>

                <!-- HUD: RMSD (single value for N=2, pairwise list for N>2) -->
                <div id="hud-rmsd-container" class="absolute top-4 right-4 bg-surface border border-border p-3 rounded-md flex flex-col items-end z-10 font-mono max-h-[220px] overflow-y-auto"></div>
            </div>
        `,this.element=e,this.setupEventListeners(),this._renderEmptyHUD(),this._updateStylePickerUI(),this._updateColorSchemePopoverUI(),e}init3Dmol(){let e=this.element.querySelector(`#viewer-canvas-3dmol`);if(e){e.innerHTML=``;try{this.viewer=$3Dmol.createViewer(e,{defaultcolors:$3Dmol.rasmolElementColors,preserveDrawingBuffer:!0}),this.viewer.setBackgroundColor(`#050608`)}catch(t){console.error(`3D viewer failed to initialize (3Dmol.js may not have loaded):`,t),this.viewer=null,e.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm text-center px-4">3D viewer failed to load — check your connection and reload the page.</div>`;return}window.addEventListener(`resize`,()=>{this.viewer&&this.viewer.resize()})}}setupEventListeners(){let e=this.element.querySelector(`#btn-toggle-surface`),t=this.element.querySelector(`#btn-reset-view`);this.element.querySelectorAll(`.viewer-style-option`).forEach(e=>{e.addEventListener(`click`,()=>{this.setStyleRepresentation(e.dataset.style),this.element.querySelector(`#viewer-style-picker`).open=!1})}),this.element.querySelectorAll(`.viewer-colorscheme-option`).forEach(e=>{e.addEventListener(`click`,()=>{this.setColorScheme(e.dataset.scheme),this.element.querySelector(`#viewer-colorscheme-picker`).open=!1})}),e.addEventListener(`click`,()=>{this.viewer&&(this.isSurfaceVisible?(this.viewer.removeAllSurfaces(),this.isSurfaceVisible=!1):(this.viewer.addSurface($3Dmol.SurfaceType.SAS,{opacity:.45,colorscheme:`whiteCarbon`}),this.isSurfaceVisible=!0),this.viewer.render())}),t.addEventListener(`click`,()=>{this.viewer&&(this.viewer.zoomTo(),this.viewer.render())}),this.element.querySelector(`#btn-toggle-spin`).addEventListener(`click`,()=>{this.toggleSpin()}),this.element.querySelector(`#btn-toggle-morph`).addEventListener(`click`,()=>{this.isMorphing?this.stopMorph():this.structures.length===2&&this.currentRunId&&this.loadMorph(this.structures[0].pdbId,this.structures[1].pdbId)}),this.element.querySelector(`#btn-toggle-fullscreen`).addEventListener(`click`,()=>{document.fullscreenElement?document.exitFullscreen():this.element.requestFullscreen()}),this.element.addEventListener(`fullscreenchange`,()=>{let e=document.fullscreenElement===this.element,t=this.element.querySelector(`#btn-toggle-fullscreen`);t.querySelector(`.material-symbols-outlined`).textContent=e?`fullscreen_exit`:`fullscreen`,t.classList.toggle(`bg-surface-raised`,e),t.classList.toggle(`text-primary`,e),requestAnimationFrame(()=>{this.viewer&&this.viewer.resize()}),setTimeout(()=>{this.viewer&&this.viewer.resize()},150)}),this.element.querySelector(`#btn-toggle-measure`).addEventListener(`click`,()=>{this.toggleMeasureMode()}),this.element.querySelector(`#btn-screenshot`).addEventListener(`click`,()=>{this.downloadScreenshot()}),this.element.querySelector(`#btn-download-pdb`).addEventListener(`click`,()=>{this.currentRunId&&window.open(O(this.currentRunId),`_blank`)}),this.element.querySelector(`#btn-download-zip`).addEventListener(`click`,()=>{this.currentRunId&&window.open(A(this.currentRunId),`_blank`)})}_updateStylePickerUI(){this.element?.querySelectorAll(`.viewer-style-option`).forEach(e=>{let t=e.dataset.style===this.currentStyle;e.classList.toggle(`bg-surface-raised`,t),e.classList.toggle(`text-primary`,t)})}_updateColorSchemePopoverUI(){this.element?.querySelectorAll(`.viewer-colorscheme-option`).forEach(e=>{let t=e.dataset.scheme;t===`confidence`&&(e.disabled=!this.hasPlddtStructures()),t===`pae-domains`&&(e.disabled=!this.hasAlphaFoldStructures());let n=t===this.currentColorScheme;e.classList.toggle(`bg-surface-raised`,n),e.classList.toggle(`text-primary`,n)})}setStyleRepresentation(e){this.currentStyle=e,this._updateStylePickerUI(),this.resetCartoonStyles()}async setColorScheme(e){this.currentColorScheme=e,this._updateColorSchemePopoverUI(),!(e===`missense`&&(await this.loadMissenseScores(),this.currentColorScheme!==`missense`))&&(e===`domain`&&(await this.loadDomainColors(),this.currentColorScheme!==`domain`)||e===`disorder`&&(await this.loadDisorderScores(),this.currentColorScheme!==`disorder`)||e===`flexibility`&&(await this.loadFlexibilityScores(),this.currentColorScheme!==`flexibility`)||e===`pae-domains`&&(await this.loadPaeDomainColors(),this.currentColorScheme!==`pae-domains`)||this.resetCartoonStyles())}async loadMissenseScores(){let e=this.structures.filter(e=>!(e.pdbId in this.missenseScoresByPdbId));e.length!==0&&await Promise.all(e.map(async e=>{try{let t=await Ie(e.pdbId,e.sourceChain===`?`?void 0:e.sourceChain);this.missenseScoresByPdbId[e.pdbId]=t.tolerance?.per_residue_average||{}}catch(t){console.error(`Failed to load mutation tolerance for ${e.pdbId}:`,t),this.missenseScoresByPdbId[e.pdbId]={}}}))}async loadDomainColors(){let e=this.structures.filter(e=>!(e.pdbId in this.domainColorsByPdbId));e.length!==0&&await Promise.all(e.map(async e=>{try{let t=e.sourceChain===`?`?void 0:e.sourceChain,n=(await j(e.pdbId,t)).annotation?.domains||[],r={};n.forEach((e,n)=>{(e.highlight_chains?.[t]||Object.values(e.highlight_chains||{})[0]||[]).forEach(e=>{r[e]=L(n)})}),this.domainColorsByPdbId[e.pdbId]=r}catch(t){console.error(`Failed to load domain annotation for ${e.pdbId}:`,t),this.domainColorsByPdbId[e.pdbId]={}}}))}async loadDisorderScores(){let e=this.structures.filter(e=>!(e.pdbId in this.disorderScoresByPdbId));e.length!==0&&await Promise.all(e.map(async e=>{try{let t=e.sourceChain===`?`?void 0:e.sourceChain,n=await Le(e.pdbId,t);this.disorderScoresByPdbId[e.pdbId]=n.disorder?.per_residue_score||{}}catch(t){console.error(`Failed to load disorder prediction for ${e.pdbId}:`,t),this.disorderScoresByPdbId[e.pdbId]={}}}))}_disorderColorPartFor(e){let t=this.disorderScoresByPdbId[e.pdbId];return!t||Object.keys(t).length===0?{color:e.color}:{colorfunc:e=>{let n=t[e.resi];return n===void 0?`#4B5563`:this._missenseColorForScore(n)}}}async loadFlexibilityScores(){let e=this.structures.filter(e=>!(e.pdbId in this.flexibilityScoresByPdbId));e.length!==0&&await Promise.all(e.map(async e=>{try{let{residue_numbers:t,flexibility:n}=(await M(e.pdbId,this.currentRunId)).flexibility||{},r={};(t||[]).forEach((e,t)=>{r[e]=n[t]}),this.flexibilityScoresByPdbId[e.pdbId]=r}catch(t){console.error(`Failed to load flexibility prediction for ${e.pdbId}:`,t),this.flexibilityScoresByPdbId[e.pdbId]={}}}))}_flexibilityColorPartFor(e){let t=this.flexibilityScoresByPdbId[e.pdbId];return!t||Object.keys(t).length===0?{color:e.color}:{colorfunc:e=>{let n=t[e.resi];return n===void 0?`#4B5563`:this._missenseColorForScore(n)}}}_domainColorPartFor(e){let t=this.domainColorsByPdbId[e.pdbId];return!t||Object.keys(t).length===0?{color:e.color}:{colorfunc:e=>t[e.resi]??`#4B5563`}}async loadPaeDomainColors(){let e=this.structures.filter(e=>(e.pdbId||``).toUpperCase().startsWith(`AF-`)&&!(e.pdbId in this.paeDomainColorsByPdbId));e.length!==0&&await Promise.all(e.map(async e=>{try{let t=await He(e.pdbId),n={};(t.domains||[]).forEach((e,t)=>{e.forEach(e=>{n[e]=L(t)})}),this.paeDomainColorsByPdbId[e.pdbId]=n}catch(t){console.error(`Failed to load PAE domain split for ${e.pdbId}:`,t),this.paeDomainColorsByPdbId[e.pdbId]={}}}))}_paeDomainsColorPartFor(e){let t=this.paeDomainColorsByPdbId[e.pdbId];return!t||Object.keys(t).length===0?{color:e.color}:{colorfunc:e=>t[e.resi]??`#4B5563`}}toggleSpin(){if(!this.viewer)return;this.isSpinning=!this.isSpinning,this.viewer.spin(this.isSpinning?`y`:!1);let e=this.element.querySelector(`#btn-toggle-spin`);e.classList.toggle(`bg-surface-raised`,this.isSpinning),e.classList.toggle(`text-primary`,this.isSpinning)}_updateMorphButtonUI(){let e=this.element?.querySelector(`#btn-toggle-morph`);e&&(e.disabled=!(this.structures.length===2&&this.currentRunId),e.classList.toggle(`bg-surface-raised`,this.isMorphing),e.classList.toggle(`text-primary`,this.isMorphing))}_updateDownloadButtonsUI(){let e=this.element?.querySelector(`#btn-download-pdb`),t=this.element?.querySelector(`#btn-download-zip`),n=!!this.currentRunId;e&&(e.disabled=!n),t&&(t.disabled=!n)}async loadMorph(e,t,n=20){if(!(!this.viewer||!this.currentRunId))try{let r=await fetch(xe(this.currentRunId,e,t,n));if(!r.ok)throw Error(`Failed to fetch morph frames: ${r.statusText}`);let i=await r.text();this.viewer.clear(),this.viewer.addModelsAsFrames(i,`pdb`),this.viewer.setStyle({},{sphere:{scale:.4,colorscheme:`whiteCarbon`}}),this.viewer.zoomTo(),this.viewer.animate({loop:`forward`,interval:80,reps:0}),this.isMorphing=!0,this._updateMorphButtonUI()}catch(e){console.error(`Error loading morph animation:`,e)}}stopMorph(){this.viewer&&(this.viewer.stopAnimate(),this.isMorphing=!1,this._updateMorphButtonUI(),this._reloadSuperpositionView())}async _reloadSuperpositionView(){if(!(!this.viewer||!this.currentRunId))try{let e=await fetch(O(this.currentRunId));if(!e.ok)return;let t=await e.text();this.viewer.clear(),this.viewer.addModel(t,`pdb`),this.structures.forEach(e=>{this.viewer.setStyle(this._selectorFor(e),this._styleFor(e))}),this.viewer.zoomTo(),this.viewer.render()}catch(e){console.error(`Error restoring superposition view after morph:`,e)}}downloadScreenshot(){if(!this.viewer)return;this.viewer.render();let e=this.viewer.pngURI(),t=(this.structures.length>0?this.structures.map(e=>e.pdbId).join(`_`):`structure`).replace(/[^A-Za-z0-9_.-]/g,`_`),n=document.createElement(`a`);n.href=e,n.download=`structscope_${t}.png`,document.body.appendChild(n),n.click(),n.remove()}_buildStructures(e,t){return e.map((e,n)=>({pdbId:e,mustangChain:String.fromCodePoint(65+n),sourceChain:t?.[e]||`?`,color:F(n)}))}_sizeParamsFor(e){switch(e){case`stick`:return{radius:.25};case`sphere`:return{scale:.3};case`line`:return{linewidth:2};default:return{}}}_plddtColorPartFor(e){if(!this._isPlddtStructure(e.pdbId))return{color:e.color};let t=this.viewer?.getModel();if(!t)return{color:e.color};let n=t.selectedAtoms(this._selectorFor(e)).map(e=>e.b).filter(e=>typeof e==`number`);return n.length===0?{color:e.color}:{colorscheme:{prop:`b`,gradient:`roygb`,min:Math.min(...n),max:Math.max(...n)}}}_missenseColorForScore(e){let t=Math.max(0,Math.min(1,e)),n={r:34,g:197,b:94},r={r:178,g:58,b:58},i=(e,n)=>Math.round(e+(n-e)*t);return`#${[i(n.r,r.r),i(n.g,r.g),i(n.b,r.b)].map(e=>e.toString(16).padStart(2,`0`)).join(``)}`}_missenseColorPartFor(e){let t=this.missenseScoresByPdbId[e.pdbId];return!t||Object.keys(t).length===0?{color:e.color}:{colorfunc:e=>{let n=t[e.resi];return n===void 0?`#4B5563`:this._missenseColorForScore(n)}}}_colorPartFor(e){switch(this.currentColorScheme){case`secondary`:return{colorscheme:`ssPyMOL`};case`spectrum`:return{colorscheme:`spectrum`};case`confidence`:return this._plddtColorPartFor(e);case`missense`:return this._missenseColorPartFor(e);case`domain`:return this._domainColorPartFor(e);case`disorder`:return this._disorderColorPartFor(e);case`flexibility`:return this._flexibilityColorPartFor(e);case`pae-domains`:return this._paeDomainsColorPartFor(e);default:return{color:e.color}}}_dimColor(e,t){let n={r:5,g:6,b:8},r=Number.parseInt(e.replace(`#`,``),16),i=r>>16&255,a=r>>8&255,o=r&255,s=(e,n)=>Math.round(e+(n-e)*t);return`#${[s(i,n.r),s(a,n.g),s(o,n.b)].map(e=>e.toString(16).padStart(2,`0`)).join(``)}`}_styleFor(e,{opacity:t=.85}={}){let n=this.currentStyle,r=this._colorPartFor(e);return n===`line`&&t<.85&&r.color&&(r={color:this._dimColor(r.color,1-t/.85)}),{[n]:{...r,opacity:t,...this._sizeParamsFor(n)}}}_renderEmptyHUD(){let e=this.element.querySelector(`#hud-structure-legend`),t=this.element.querySelector(`#hud-rmsd-container`);this._updateMorphButtonUI(),this._updateDownloadButtonsUI(),e&&(e.innerHTML=`<span class="font-label-sm text-label-sm text-muted font-mono">No structures loaded</span>`),t&&(t.innerHTML=`
            <span class="font-label-sm text-label-sm text-secondary uppercase">Global RMSD</span>
            <span class="font-headline-md text-headline-md text-success font-semibold">-- Å</span>
        `)}_renderHUD(){let e=this.element.querySelector(`#hud-structure-legend`),t=this.element.querySelector(`#hud-rmsd-container`);if(this._updateMorphButtonUI(),this._updateDownloadButtonsUI(),e.innerHTML=this.structures.map(e=>`
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full shrink-0" style="background-color: ${e.color};"></div>
                <span class="font-label-sm text-label-sm text-primary font-mono truncate">${e.pdbId} (Chain ${e.sourceChain})</span>
            </div>
        `).join(``),this.structures.length<=2||!this.rmsdDf){t.innerHTML=`
                <span class="font-label-sm text-label-sm text-secondary uppercase">Global RMSD</span>
                <span class="font-headline-md text-headline-md text-success font-semibold">${this._meanRmsd()}</span>
            `;return}t.innerHTML=`
            <span class="font-label-sm text-label-sm text-secondary uppercase mb-1">Pairwise RMSD</span>
            <div class="flex flex-col gap-1 items-end">
                ${this._pairwiseRmsdRows().map(e=>`
                    <div class="flex items-center gap-2 text-body-sm">
                        <span class="text-secondary">${e.a} &harr; ${e.b}</span>
                        <span class="text-success font-semibold">${e.value.toFixed(2)} Å</span>
                    </div>
                `).join(``)}
            </div>
        `}_pairwiseRmsdRows(){if(!this.rmsdDf?.index||!this.rmsdDf?.data)return[];let{index:e,data:t}=this.rmsdDf,n=[];for(let r=0;r<e.length;r++)for(let i=r+1;i<e.length;i++)n.push({a:e[r],b:e[i],value:t[r][i]});return n}_meanRmsd(){let e=this._pairwiseRmsdRows();return e.length===0?`-- Å`:`${(e.reduce((e,t)=>e+t.value,0)/e.length).toFixed(2)} Å`}async loadSuperposition(e,t,n,r){this.viewer||this.init3Dmol(),this.currentRunId=e,this.structures=this._buildStructures(t,n),this.rmsdDf=r||null,this.element.querySelector(`#ambient-placeholder`).style.display=`none`,this._renderHUD();try{let t=await fetch(O(e));if(!t.ok)throw Error(`Failed to fetch alignment PDB: ${t.statusText}`);let n=await t.text();this.viewer.clear(),this.viewer.addModel(n,`pdb`),this.structures.forEach(e=>{this.viewer.setStyle(this._selectorFor(e),this._styleFor(e))}),this._wireClickHandler(),this.viewer.zoomTo(),this.viewer.render(),this.isSurfaceVisible=!1,this._updateColorSchemePopoverUI()}catch(e){console.error(`Error loading superposition coordinate data:`,e)}}async loadSingleStructure(e){this.viewer||this.init3Dmol(),this.currentRunId=null,this.structures=[{pdbId:e,mustangChain:null,sourceChain:null,color:F(0)}],this.rmsdDf=null,this.element.querySelector(`#ambient-placeholder`).style.display=`none`,this._renderSingleStructureHUD(e);try{let t=await fetch(Se(e));if(!t.ok)throw Error(`Failed to fetch structure file: ${t.statusText}`);let n=await t.text();this.viewer.clear();let r=n.trimStart().startsWith(`data_`)?`cif`:`pdb`;this.viewer.addModel(n,r),this.viewer.setStyle({},this._styleFor(this.structures[0])),this._wireClickHandler(),this.viewer.zoomTo(),this.viewer.render(),this.isSurfaceVisible=!1,this._updateColorSchemePopoverUI()}catch(e){console.error(`Error loading single structure:`,e)}}_wireClickHandler(){this.viewer&&this.viewer.setClickable({},!0,e=>{this.interactionMode===`measure`?this._handleMeasureClick(e):this._handleInspectClick(e)})}_renderSingleStructureHUD(e){let t=this.element.querySelector(`#hud-structure-legend`),n=this.element.querySelector(`#hud-rmsd-container`);t&&(t.innerHTML=`
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full shrink-0" style="background-color: ${F(0)};"></div>
                <span class="font-label-sm text-label-sm text-primary font-mono truncate">${e}</span>
            </div>
        `),n&&(n.innerHTML=`
            <span class="font-label-sm text-label-sm text-secondary uppercase">Single Structure</span>
        `),this._updateMorphButtonUI()}_isPlddtStructure(e){let t=(e||``).toUpperCase();return t.startsWith(`AF-`)||t.startsWith(`ESM-`)}hasPlddtStructures(){return this.structures.some(e=>this._isPlddtStructure(e.pdbId))}hasAlphaFoldStructures(){return this.structures.some(e=>(e.pdbId||``).toUpperCase().startsWith(`AF-`))}_selectorFor(e){return e.mustangChain?{chain:e.mustangChain}:{}}showLigandBindingSite(e,t,n){if(!this.viewer)return;this.structures.forEach(e=>{this.viewer.setStyle(this._selectorFor(e),this._styleFor(e,{opacity:.3}))});let r=this.structures[e],i=r?r.mustangChain:`A`,a=n.map(e=>e.aligned_resi).filter(e=>e!=null);a.forEach(e=>{this.viewer.addStyle({chain:i,resi:e},{stick:{colorscheme:`purpleCarbon`,radius:.25},cartoon:{color:r?r.color:`#8B5CF6`,opacity:1}})}),a.length>0?this.viewer.zoomTo({chain:i,resi:a}):this.viewer.zoomTo(),this.viewer.render()}highlightResidue(e,t,n,r){if(!this.viewer)return;if(this.structures.forEach(e=>{this.viewer.setStyle(this._selectorFor(e),this._styleFor(e,{opacity:.35}))}),r==null){this.viewer.zoomTo(),this.viewer.render();return}let i=this.structures[e],a={chain:i?i.mustangChain:t,resi:r};this.viewer.addStyle(a,{stick:{color:R,radius:.45},sphere:{color:R,scale:1.3},cartoon:{color:R,opacity:1}}),this.viewer.zoomTo(a),this.viewer.render()}highlightResidues(e){if(!this.viewer)return;this.structures.forEach(e=>{this.viewer.setStyle(this._selectorFor(e),this._styleFor(e,{opacity:.35}))});let t=[];Object.entries(e||{}).forEach(([e,n])=>{if(!n||n.length===0)return;let r={chain:e,resi:n};this.viewer.addStyle(r,{stick:{color:R,radius:.35},cartoon:{color:R,opacity:1}}),t.push(r)}),t.length===0?this.viewer.zoomTo():this.viewer.zoomTo({or:t}),this.viewer.render()}resetCartoonStyles(){this.viewer&&(this.structures.forEach(e=>{this.viewer.setStyle(this._selectorFor(e),this._styleFor(e))}),this.viewer.zoomTo(),this.viewer.render())}constructor(e={}){this.onAtomSelect=e.onAtomSelect||null}_handleInspectClick(e){if(!this.viewer||(this.inspectLabelHandle&&=(this.viewer.removeLabel(this.inspectLabelHandle),null),!e))return;typeof this.onAtomSelect==`function`&&this.onAtomSelect(e);let t=e.chain?` · Chain ${e.chain}`:``,n=`${e.resn} ${e.resi}${t}`;this.inspectLabelHandle=this.viewer.addLabel(n,{position:{x:e.x,y:e.y,z:e.z},backgroundColor:`#111318`,backgroundOpacity:.85,fontColor:`#F5F5F5`,fontSize:12,borderThickness:0}),this.viewer.render()}_clearInspectLabel(){!this.viewer||!this.inspectLabelHandle||(this.viewer.removeLabel(this.inspectLabelHandle),this.inspectLabelHandle=null)}_handleMeasureClick(e){if(!this.viewer||!e)return;if(this.measurePoints.length>=2&&this._clearMeasurement(),this.measurePoints.length===0){this.measurePoints.push(e);let t=this.viewer.addLabel(`A`,{position:{x:e.x,y:e.y,z:e.z},backgroundColor:R,backgroundOpacity:.9,fontColor:`#111318`,fontSize:11,borderThickness:0});this.measureHandles.push(t),this.viewer.render();return}let[t]=this.measurePoints,n=e;this.measurePoints.push(n);let r=Math.hypot(t.x-n.x,t.y-n.y,t.z-n.z);this.viewer.addLine?this.measureHandles.push(this.viewer.addLine({start:{x:t.x,y:t.y,z:t.z},end:{x:n.x,y:n.y,z:n.z},color:R,dashed:!0})):this.viewer.addCylinder&&this.measureHandles.push(this.viewer.addCylinder({start:{x:t.x,y:t.y,z:t.z},end:{x:n.x,y:n.y,z:n.z},radius:.05,color:R,dashed:!0}));let i={x:(t.x+n.x)/2,y:(t.y+n.y)/2,z:(t.z+n.z)/2};this.measureHandles.push(this.viewer.addLabel(`${r.toFixed(2)} Å`,{position:i,backgroundColor:`#111318`,backgroundOpacity:.85,fontColor:`#F5F5F5`,fontSize:12,borderThickness:0})),this.viewer.render()}_clearMeasurement(){this.viewer&&(this.viewer.removeAllLabels(),this.viewer.removeAllShapes()),this.measurePoints=[],this.measureHandles=[]}toggleMeasureMode(){this.interactionMode=this.interactionMode===`measure`?`inspect`:`measure`,this._clearMeasurement(),this._clearInspectLabel();let e=this.element.querySelector(`#btn-toggle-measure`),t=this.interactionMode===`measure`;e.classList.toggle(`bg-surface-raised`,t),e.classList.toggle(`text-primary`,t),this.viewer&&this.viewer.render()}reset(){this.structures=[],this.rmsdDf=null,this.currentRunId=null,this.currentStyle=`cartoon`,this.currentColorScheme=`chain`,this.missenseScoresByPdbId={},this.domainColorsByPdbId={},this.disorderScoresByPdbId={},this.flexibilityScoresByPdbId={},this.paeDomainColorsByPdbId={},this.interactionMode=`inspect`,this.measurePoints=[],this.measureHandles=[],this.inspectLabelHandle=null,this.isSpinning&&this.viewer&&this.viewer.spin(!1),this.isSpinning=!1,this.isMorphing&&this.viewer&&this.viewer.stopAnimate(),this.isMorphing=!1,this.viewer&&(this.viewer.clear(),this.viewer.render()),this.element&&(this.element.querySelector(`#ambient-placeholder`).style.display=`flex`,this._renderEmptyHUD(),this._updateStylePickerUI(),this._updateColorSchemePopoverUI(),this._updateMorphButtonUI(),this.element.querySelector(`#btn-toggle-spin`).classList.remove(`bg-surface-raised`,`text-primary`),this.element.querySelector(`#btn-toggle-measure`).classList.remove(`bg-surface-raised`,`text-primary`))}};function z(e){return String(e??``).replaceAll(`&`,`&amp;`).replaceAll(`<`,`&lt;`).replaceAll(`>`,`&gt;`).replaceAll(`"`,`&quot;`).replaceAll(`'`,`&#39;`)}var B=[{label:`Hemoglobin variants`,pdbIds:[`4HHB`,`2HHB`],tag:`Genetic Mutation`,icon:`bloodtype`,description:`See how a single amino acid substitution alters oxygen-carrying hemoglobin in human blood.`},{label:`Kinase family`,pdbIds:[`1ATP`,`1CDK`],tag:`Drug Discovery`,icon:`medication`,description:`Discover how cancer drug targets switch shapes between active and inactive conformations.`},{label:`Trp-cage + AlphaFold`,pdbIds:[`1L2Y`,`AF-P69905-F1`],tag:`AI vs Wet Lab`,icon:`smart_toy`,description:`Compare an experimental NMR-solved miniprotein against DeepMind AlphaFold predicted coordinates.`},{label:`COVID-19 Spike RBD`,pdbIds:[`7KRR`,`7V76`],tag:`Viral Evolution`,icon:`coronavirus`,description:`Compare how viral receptor-binding domain mutations reshape the spike to evade antibody defenses.`}];function V(e,t=`Domains / families`){return e?.length?`
        <div class="flex flex-col gap-2">
            ${t?`<span class="eyebrow">${t}</span>`:``}
            ${e.map((e,t)=>`
                <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${e.name} <span class="text-secondary text-[11px]">(${e.type})</span></span>
                    <span class="flex items-center gap-3">
                        ${e.neighbor_count==null?``:`<span class="font-mono text-[11px] text-secondary">${e.neighbor_count} neighbors</span>`}
                        ${e.highlight_chains?`<button type="button" class="domain-highlight-btn font-label-sm text-label-sm text-accent hover:underline" data-domain-index="${t}">Highlight in 3D</button>`:``}
                    </span>
                </div>
            `).join(``)}
        </div>
    `:``}function H(e,t=`UniProt features`,n=`feature-highlight-btn`,r=15){if(!e?.length)return``;let i=e.length-r;return`
        <div class="flex flex-col gap-2">
            ${t?`<span class="eyebrow">${t}</span>`:``}
            ${e.map((e,t)=>`
                <div class="flex justify-between items-center py-1.5 border-b border-border-subtle${t>=r?` hidden feature-overflow-row`:``}" ${t>=r?`data-feature-overflow-group="${n}"`:``}>
                    <span class="font-body-sm">${e.type}${e.description?` <span class="text-secondary text-[11px]">(${e.description})</span>`:``} <span class="font-mono text-[11px] text-secondary">${e.start===e.end?e.start:`${e.start}-${e.end}`}</span></span>
                    ${e.highlight_chains?`<button type="button" class="${n} font-label-sm text-label-sm text-accent hover:underline" data-feature-index="${t}">Highlight in 3D</button>`:``}
                </div>
            `).join(``)}
            ${i>0?`<button type="button" class="feature-show-all-btn font-label-sm text-label-sm text-accent hover:underline self-start" data-feature-overflow-group="${n}">Show all ${e.length}</button>`:``}
        </div>
    `}function it(e){return`${e.code||`?`}${e.resi??`?`} (${e.reference_pdb_id||`?`} chain ${e.chain||`?`})${e.roles_summary?` - ${e.roles_summary}`:``}`}function at(e,t=`Catalytic sites (M-CSA)`){return e?.length?`
        <div class="flex flex-col gap-2">
            ${t?`<span class="eyebrow">${t}</span>`:``}
            ${e.map(e=>{let t=e.residues.map(it).join(`; `),n=e.ec_numbers?.length?` <span class="font-mono text-secondary text-[11px]">(EC ${e.ec_numbers.join(`, `)})</span>`:``;return`
                <div class="flex flex-col gap-1 py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${e.enzyme_name}${n}</span>
                    <span class="font-body-sm text-[11px] text-secondary">
                        ${t}
                    </span>
                </div>
            `}).join(``)}
        </div>
    `:``}var ot={molecular_function:`Molecular function`,biological_process:`Biological process`,cellular_component:`Cellular component`},U=[`molecular_function`,`biological_process`,`cellular_component`];function W(e,t=`GO terms`){if(!e?.length)return``;let n=new Map;for(let t of e){let e=t.aspect||`unspecified`;n.has(e)||n.set(e,[]),n.get(e).push(t)}let r=[...U.filter(e=>n.has(e)),...[...n.keys()].filter(e=>!U.includes(e))];return`
        <div class="flex flex-col gap-3">
            ${t?`<span class="eyebrow">${t}</span>`:``}
            ${r.map(e=>`
                <div class="flex flex-col gap-1">
                    <span class="font-label-sm text-[11px] text-secondary uppercase tracking-wider">${ot[e]||(e===`unspecified`?`Unspecified aspect`:e)}</span>
                    ${n.get(e).map(e=>`
                        <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                            <span class="font-body-sm">${e.name||e.id}</span>
                            ${e.neighbor_count==null?``:`<span class="font-mono text-[11px] text-secondary">${e.neighbor_count} neighbors</span>`}
                        </div>
                    `).join(``)}
                </div>
            `).join(``)}
        </div>
    `}var st=/[ \t]*\((PubMed:\d+(?:,[ \t]*PubMed:\d+)*)\)/g;function ct(e){if(!e)return``;let t=[];return`<div class="font-body-sm text-primary py-2">${z(e).replace(st,(e,n)=>{let r=n.match(/\d+/g);return r?(t.push(...r),``):e}).trim()}${t.length?`
            <details class="mt-1">
                <summary class="font-label-sm text-label-sm text-accent cursor-pointer select-none">${t.length} reference${t.length===1?``:`s`}</summary>
                <div class="flex flex-col gap-1 pt-1">
                    ${t.map(e=>`<a href="https://pubmed.ncbi.nlm.nih.gov/${e}/" target="_blank" rel="noopener noreferrer" class="font-body-sm text-[11px] text-accent hover:underline">PubMed:${e}</a>`).join(``)}
                </div>
            </details>
        `:``}</div>`}var lt={pdb:`PDB`,alphafold:`AlphaFold`,swissmodel:`SWISS-MODEL`,esmfold:`ESMFold`},ut=[{key:`public`,label:`Public`},{key:`student`,label:`Student`},{key:`researcher`,label:`Researcher`}],G=[{key:`pdb100`,label:`PDB`,hint:`Experimentally solved structures`,annotatable:!0,default:!0},{key:`afdb50`,label:`AlphaFold DB`,hint:`50%-redundancy-reduced`,annotatable:!0,default:!0},{key:`afdb-swissprot`,label:`AlphaFold DB (SwissProt)`,hint:`Reviewed UniProt entries only`,annotatable:!0,default:!1},{key:`afdb-proteome`,label:`AlphaFold DB (Proteomes)`,hint:`Full reference proteomes`,annotatable:!0,default:!1},{key:`cath50`,label:`CATH`,hint:`Structural domain classification`,annotatable:!0,default:!1},{key:`BFVD`,label:`BFVD`,hint:`Big Fantastic Virus Database`,annotatable:!0,default:!1},{key:`bfmd`,label:`BFMD`,hint:`Big Fantastic Metagenomics Database`,annotatable:!0,default:!1},{key:`mgnify_esm30`,label:`MGnify / ESM Atlas`,hint:`Metagenomic 'dark matter' proteins`,annotatable:!1,default:!1},{key:`gmgcl_id`,label:`GMGC`,hint:`Global Microbial Gene Catalog`,annotatable:!0,default:!1}],dt=class{element=null;isRunning=!1;detailLevel=`student`;results=null;pdbId=null;selectedDatabases=new Set(G.filter(e=>e.default).map(e=>e.key));constructor(e={}){this.onClose=e.onClose||(()=>{})}render(){let e=document.createElement(`div`);return e.className=`flex flex-col gap-4 p-4 rounded-md bg-surface-raised border border-border-subtle`,e.id=`discovery-panel-container`,e.innerHTML=`
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[18px] text-accent">travel_explore</span>
                    <span class="font-label-md text-label-md">Discover: <span id="discovery-panel-pdbid" class="font-mono">${z(this.pdbId||``)}</span></span>
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
                        ${G.map(e=>`
                            <label class="flex items-start gap-2 p-2 rounded-sm border border-border-subtle bg-surface hover:border-border cursor-pointer">
                                <input type="checkbox" data-db="${e.key}" class="discover-db-checkbox mt-0.5" ${this.selectedDatabases.has(e.key)?`checked`:``} />
                                <span class="flex flex-col">
                                    <span class="font-label-sm text-label-sm">${e.label}${e.annotatable?``:` <span class="text-secondary" title="Hits shown, but no domain/GO annotation yet">*</span>`}</span>
                                    <span class="font-body-sm text-[10px] text-secondary">${e.hint}</span>
                                </span>
                            </label>
                        `).join(``)}
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
        `,this.element=e,this.element.querySelector(`#discovery-panel-close-btn`).addEventListener(`click`,()=>this.onClose()),this.element.querySelector(`#discover-rerun-btn`).addEventListener(`click`,()=>{this.runFor(this.pdbId)}),this.element.querySelectorAll(`.discover-db-checkbox`).forEach(e=>{e.addEventListener(`change`,()=>{e.checked?this.selectedDatabases.add(e.dataset.db):this.selectedDatabases.delete(e.dataset.db),this.updateDbSummary()})}),this.updateDbSummary(),this.results&&(this.syncDbCheckboxes(this.results.databases_searched),this.renderResults()),e}setStatus(e){let t=this.element.querySelector(`#discover-status`);e?(this.element.querySelector(`#discover-status-text`).textContent=e,t.classList.remove(`hidden`)):t.classList.add(`hidden`)}setError(e){let t=this.element.querySelector(`#discover-error`);e?(t.textContent=e,t.classList.remove(`hidden`)):t.classList.add(`hidden`)}setRunning(e){this.isRunning=e;let t=this.element.querySelector(`#discover-rerun-btn`);t&&(t.disabled=e)}updateDbSummary(){let e=this.element.querySelector(`#discover-db-summary`);if(!e)return;let t=this.selectedDatabases.size,n=G.length;e.textContent=t===n?`all`:`${t} of ${n} selected`}syncDbCheckboxes(e){if(!this.element||!Array.isArray(e))return;let t=e.filter(e=>G.some(t=>t.key===e));t.length!==0&&(this.selectedDatabases=new Set(t),this.element.querySelectorAll(`.discover-db-checkbox`).forEach(e=>{e.checked=this.selectedDatabases.has(e.dataset.db)}),this.updateDbSummary())}statusMessageForJob(e){return e===`queued`?`Queued - Foldseek's search API is shared and rate-limited across all users, so this may wait a moment before starting.`:`Searching Foldseek structural databases... this can take a minute or two.`}async runFor(e){if(this.pdbId=e,this.element&&(this.element.querySelector(`#discovery-panel-pdbid`).textContent=e),this.selectedDatabases.size===0){this.setError(`Select at least one database to search.`);return}this.setError(null),this.setRunning(!0),this.element.querySelector(`#discover-results`).innerHTML=``,this.setStatus(this.statusMessageForJob(`queued`));try{let t=this.element.querySelector(`#discover-webhook-url`)?.value.trim(),n=await b((t?await C(e,Array.from(this.selectedDatabases),t):await C(e,Array.from(this.selectedDatabases))).job_id,{onTick:e=>this.setStatus(this.statusMessageForJob(e.status))});if(n.status===`failed`)throw Error(n.error||`Discovery pipeline failed.`);this.results=n.results,this.setStatus(null),this.renderResults()}catch(e){console.error(`Discovery run failed:`,e),this.setError(e.message),this.setStatus(null)}finally{this.setRunning(!1)}}setDetailLevel(e){this.detailLevel=e,this.results&&this.renderResults()}loadSavedResults(e){this.results=e,this.pdbId=e?e.pdb_id:null,this.detailLevel=`student`,this.element&&(e&&(this.element.querySelector(`#discovery-panel-pdbid`).textContent=e.pdb_id),e&&this.syncDbCheckboxes(e.databases_searched),this.setError(null),this.setStatus(null),this.renderResults())}renderResults(){let e=this.element.querySelector(`#discover-results`);if(!e||(e.innerHTML=``,!this.results))return;let t=this.results,n=t.annotations,r=lt[t.source]||`PDB`,i=document.createElement(`div`);i.className=`flex flex-col gap-4 border-t border-border pt-6`;let a=document.createElement(`div`);a.className=`flex items-center justify-between flex-wrap gap-3`;let o=document.createElement(`div`);o.className=`flex items-center gap-2`;let s=document.createElement(`span`);s.className=`font-headline-sm text-body-md font-bold text-primary font-mono`,s.textContent=t.pdb_id;let c=document.createElement(`span`);c.className=`px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase source-badge`,c.textContent=r;let l=document.createElement(`span`);l.className=`font-body-sm text-[11px] text-secondary`,l.textContent=`${t.hit_count} structural matches (${(t.databases_searched||[]).join(`, `)})`,o.appendChild(s),o.appendChild(c),o.appendChild(l);let u=document.createElement(`div`);if(u.className=`flex gap-1 p-1 rounded-md bg-surface border border-border-subtle w-fit`,ut.forEach(e=>{let t=document.createElement(`button`);t.type=`button`,t.dataset.level=e.key,t.className=`detail-level-btn px-3 py-1 rounded-md font-label-sm text-label-sm transition-colors ${this.detailLevel===e.key?`bg-accent-muted text-accent`:`text-secondary hover:text-primary`}`,t.textContent=e.label,t.addEventListener(`click`,()=>this.setDetailLevel(e.key)),u.appendChild(t)}),a.appendChild(o),a.appendChild(u),i.appendChild(a),t.id){let e=document.createElement(`div`);e.className=`flex gap-4`,[{href:Ye(t.id),icon:`description`,label:`Download Report`},{href:Xe(t.id),icon:`data_object`,label:`Download JSON`},{href:Ze(t.id),icon:`format_quote`,label:`Export Citations`}].forEach(t=>{let n=document.createElement(`a`);n.href=t.href,n.target=`_blank`,n.rel=`noopener noreferrer`,n.className=`flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:text-primary transition-colors`;let r=document.createElement(`span`);r.className=`material-symbols-outlined text-[16px]`,r.textContent=t.icon,n.appendChild(r),n.appendChild(document.createTextNode(t.label)),e.appendChild(n)}),i.appendChild(e)}let d=document.createElement(`div`);this.renderBodyInto(d,t,n),i.appendChild(d),e.appendChild(i)}renderBodyInto(e,t,n){if(!n||n.annotated_neighbor_count===0){this.renderEmptyAnnotationsInto(e,t);return}if(this.detailLevel===`researcher`){this.renderResearcherViewInto(e,n);return}if(n.high_confidence_annotated_count===0){this.renderLowConfidenceMessageInto(e,n);return}this.detailLevel===`public`?this.renderPublicViewInto(e,n):this.renderStudentViewInto(e,n)}renderEmptyAnnotationsInto(e,t){let n=document.createElement(`div`);n.className=`py-6 text-center text-secondary font-body-sm`,n.textContent=t.hit_count>0?`Found ${t.hit_count} structural matches, but none could be resolved to a protein with known functional annotations yet.`:`No structural matches were found in the searched databases.`,e.appendChild(n)}renderLowConfidenceMessageInto(e,t){let n=document.createElement(`div`);n.className=`py-6 text-center text-secondary font-body-sm max-w-[480px] mx-auto`,n.textContent=`Found ${t.annotated_neighbor_count} structurally similar protein(s) with known functional annotations, but none matched with high enough structural confidence (Foldseek probability ≥ ${t.min_confident_probability}) to state a reliable function hypothesis here. Switch to the Researcher view to see the raw data and judge for yourself.`,e.appendChild(n)}renderPublicViewInto(e,t){let n=t.high_confidence_top_domains[0],r=t.high_confidence_top_go_terms[0],i=document.createElement(`div`);if(i.className=`p-4 rounded-md bg-surface border border-border-subtle font-body-md leading-relaxed`,i.appendChild(document.createTextNode(`This structure looks similar to `)),n){i.appendChild(document.createTextNode(`known `));let e=document.createElement(`strong`);e.textContent=n.name,i.appendChild(e),i.appendChild(document.createTextNode(`-type proteins`))}else i.appendChild(document.createTextNode(`proteins with a known function`));if(r){i.appendChild(document.createTextNode(`, which are typically involved in `));let e=document.createElement(`strong`);e.textContent=r.name,i.appendChild(e)}i.appendChild(document.createTextNode(`. This is a computational inference based on structural similarity, not a confirmed experimental result.`)),e.appendChild(i)}renderStudentViewInto(e,t){let n=t.high_confidence_top_domains[0],r=t.high_confidence_top_go_terms[0],i=document.createElement(`div`);i.className=`flex flex-col gap-4`;let a=document.createElement(`div`);a.className=`p-4 rounded-md bg-surface border border-border-subtle font-body-md leading-relaxed flex flex-col gap-3`;let o=document.createElement(`p`);o.appendChild(document.createTextNode(`Out of ${t.neighbors_considered} of the most confident structural neighbors, `));let s=document.createElement(`strong`);if(s.textContent=t.high_confidence_annotated_count,o.appendChild(s),o.appendChild(document.createTextNode(` matched a protein with known functional annotations at high enough structural confidence (Foldseek probability ≥ ${t.min_confident_probability}).`)),a.appendChild(o),n){let e=document.createElement(`p`);e.appendChild(document.createTextNode(`The most common protein family among these neighbors is `));let r=document.createElement(`strong`);r.textContent=n.name,e.appendChild(r),e.appendChild(document.createTextNode(` (seen in ${n.neighbor_count} of ${t.high_confidence_annotated_count} confidently-matched neighbors). Because structural fold is conserved much longer than sequence identity over evolution, a strong structural match to a known family is meaningful evidence for shared function - even in cases where sequence similarity alone wouldn't have found the connection.`)),a.appendChild(e)}else if(r){let e=document.createElement(`p`);e.appendChild(document.createTextNode(`No single protein family dominates, but a common thread across these neighbors is `));let n=document.createElement(`strong`);n.textContent=r.name,e.appendChild(n),e.appendChild(document.createTextNode(` (seen in ${r.neighbor_count} of ${t.high_confidence_annotated_count} confidently-matched neighbors) - a shared Gene Ontology annotation that's meaningful evidence for function even without a matching domain family.`)),a.appendChild(e)}i.appendChild(a);let c=V(t.high_confidence_top_domains,`Common domains / families`);if(c){let e=document.createElement(`div`);e.innerHTML=c,i.appendChild(e)}let l=W(t.high_confidence_top_go_terms,`Common GO terms`);if(l){let e=document.createElement(`div`);e.innerHTML=l,i.appendChild(e)}e.appendChild(i)}renderResearcherViewInto(e,t){let n=document.createElement(`div`);n.className=`flex flex-col gap-4`;let r=document.createElement(`div`);r.className=`grid grid-cols-4 gap-4`,r.innerHTML=`
            <div class="stat-row"><span class="stat-key">Total hits</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">Candidates examined</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">Resolvable to UniProt</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">Annotated neighbors</span><span class="stat-value"></span></div>
        `;let i=r.querySelectorAll(`.stat-value`);i[0].textContent=t.total_hit_count,i[1].textContent=t.candidates_examined,i[2].textContent=`${t.resolvable_hit_count} / ${t.candidates_examined}`,i[3].textContent=`${t.annotated_neighbor_count} / ${t.neighbors_considered}`,n.appendChild(r);let a=document.createElement(`div`);a.className=`grid grid-cols-3 gap-4`,a.innerHTML=`
            <div class="stat-row"><span class="stat-key">With STRING interactions</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">With Reactome pathways</span><span class="stat-value"></span></div>
            <div class="stat-row"><span class="stat-key">High-confidence</span><span class="stat-value"></span></div>
        `;let o=a.querySelectorAll(`.stat-value`);o[0].textContent=t.neighbors_with_interactions_count,o[1].textContent=t.neighbors_with_pathways_count,o[2].textContent=`${t.high_confidence_annotated_count} / ${t.annotated_neighbor_count}`,n.appendChild(a);let s=V(t.top_domains,`Common domains / families`);if(s){let e=document.createElement(`div`);e.innerHTML=s,n.appendChild(e)}let c=W(t.top_go_terms,`Common GO terms`);if(c){let e=document.createElement(`div`);e.innerHTML=c,n.appendChild(e)}this.renderInteractionsAndPathwaysInto(n,t),this.renderHitTableInto(n,this.results.hits),e.appendChild(n)}renderInteractionsAndPathwaysInto(e,t){let n=t.per_neighbor.filter(e=>e.string_partners.length>0||e.reactome_pathways.length>0);if(!n.length)return;let r=document.createElement(`div`);r.className=`flex flex-col gap-2`;let i=document.createElement(`span`);i.className=`font-label-md text-label-md text-secondary uppercase tracking-wider`,i.textContent=`Interactions & pathways (per neighbor)`,r.appendChild(i),n.forEach(e=>{let t=document.createElement(`div`);t.className=`flex flex-col gap-1 py-1.5 border-b border-border-subtle`;let n=document.createElement(`span`);if(n.className=`font-mono text-[11px] text-secondary`,n.textContent=(e.target||``).slice(0,60),t.appendChild(n),e.string_partners.length){let n=document.createElement(`span`);n.className=`font-body-sm text-[12px]`,n.textContent=`STRING partners: ${e.string_partners.map(e=>e.partner_name).join(`, `)}`,t.appendChild(n)}if(e.reactome_pathways.length){let n=document.createElement(`span`);n.className=`font-body-sm text-[12px]`,n.textContent=`Reactome pathways: ${e.reactome_pathways.map(e=>e.name).join(`, `)}`,t.appendChild(n)}r.appendChild(t)}),e.appendChild(r)}renderHitTableInto(e,t){if(!t||!t.length)return;let n=document.createElement(`div`);n.className=`flex flex-col gap-2`;let r=document.createElement(`span`);r.className=`font-label-md text-label-md text-secondary uppercase tracking-wider`,r.textContent=`Top structural matches`,n.appendChild(r);let i=document.createElement(`div`);i.className=`overflow-x-auto`;let a=document.createElement(`table`);a.className=`w-full text-left font-body-sm text-[12px]`,a.innerHTML=`
            <thead>
                <tr class="text-secondary border-b border-border-subtle">
                    <th class="py-1.5 pr-4">Target</th>
                    <th class="py-1.5 pr-4">Prob</th>
                    <th class="py-1.5 pr-4">E-value</th>
                    <th class="py-1.5 pr-4">Seq ID</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;let o=a.querySelector(`tbody`);[...t].sort((e,t)=>(Number.parseFloat(e.eval)||1e9)-(Number.parseFloat(t.eval)||1e9)).slice(0,20).forEach(e=>{let t=document.createElement(`tr`);t.className=`border-b border-border-subtle`;let n=document.createElement(`td`);n.className=`py-1.5 pr-4 font-mono`,n.textContent=(e.target||``).slice(0,60);let r=document.createElement(`td`);r.className=`py-1.5 pr-4 font-mono`,r.textContent=typeof e.prob==`number`?e.prob.toFixed(3):e.prob;let i=document.createElement(`td`);i.className=`py-1.5 pr-4 font-mono`,i.textContent=e.eval;let a=document.createElement(`td`);a.className=`py-1.5 pr-4 font-mono`,a.textContent=e.seqId,t.appendChild(n),t.appendChild(r),t.appendChild(i),t.appendChild(a),o.appendChild(t)}),i.appendChild(a),n.appendChild(i),e.appendChild(n)}},ft={pdb:`PDB`,alphafold:`AlphaFold`,swissmodel:`SWISS-MODEL`,esmfold:`ESMFold`,upload:`Uploaded`},K=`structscope:onboarding-dismissed`;function pt(){try{return localStorage.getItem(K)===`true`}catch{return!1}}function mt(){try{localStorage.setItem(K,`true`)}catch{}}var ht=class{constructor(e){this.selectedPDBs=e.selectedPDBs||[],this.chainSelections=e.chainSelections||{},this.pdbMetadata=e.pdbMetadata||{},this.onAddPDB=e.onAddPDB,this.onAddManyPDBs=e.onAddManyPDBs,this.onUploadStructure=e.onUploadStructure,this.onPredictFromSequence=e.onPredictFromSequence,this.onRemovePDB=e.onRemovePDB,this.onChainSelection=e.onChainSelection,this.onRunAlignment=e.onRunAlignment,this.onQuickStart=e.onQuickStart,this.isSharedView=!!e.isSharedView,this.element=null,this.isLoadingChains=!1,this.isUploading=!1,this.suggestTimeout=null,this.batchInputVisible=!1,this.predictInputVisible=!1,this.isPredicting=!1,this.discoveryPanelVisible=!1,this.discoveryPanel=new dt({onClose:()=>this.hideDiscoveryPanel()}),this.validationCache={},this._validationLoading=new Set,this.cathCache={},this._cathLoading=new Set,this.assemblyCache={},this._assemblyLoading=new Set}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-workspace-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Workspace</span>
                    <h2 class="section-title">Structures &amp; parameters</h2>
                </div>
                <span id="workspace-pdb-count-badge" class="font-label-sm text-label-sm text-secondary">0 Proteins</span>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div class="flex flex-col gap-3">
                    <div class="flex gap-2 relative">
                        <input id="workspace-add-pdb-input" type="text" placeholder="PDB ID, or AF- / SM- / ESM- accession" aria-label="PDB ID, or AF- / SM- / ESM- accession" class="flex-grow bg-surface-raised border border-border rounded-md px-3 py-1.5 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase" autocomplete="off"/>
                        <button id="workspace-add-pdb-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add</button>
                    </div>
                    <div id="workspace-add-pdb-suggestions" class="flex gap-2"></div>

                    <div class="flex items-center gap-4">
                        <button id="workspace-toggle-batch-add-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Paste multiple IDs</button>
                        <button id="workspace-upload-structure-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Upload a structure file</button>
                        <input id="workspace-upload-structure-input" type="file" accept=".pdb,.ent,.cif" aria-label="Upload a structure file" class="hidden"/>
                        <button id="workspace-toggle-predict-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Predict from sequence</button>
                    </div>
                    <span id="workspace-upload-structure-feedback" class="font-body-sm text-[11px] text-secondary"></span>

                    <div id="workspace-batch-add-container" class="flex flex-col gap-2 ${this.batchInputVisible?``:`hidden`}">
                        <textarea id="workspace-batch-pdb-input" rows="3" placeholder="Paste PDB IDs or accessions, separated by commas, spaces, or new lines (e.g. 4RLT, 3UG9, AF-P69905-F1)" aria-label="Paste multiple PDB IDs or accessions" class="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase"></textarea>
                        <div class="flex items-center gap-3">
                            <button id="workspace-batch-add-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add All</button>
                            <span id="workspace-batch-add-feedback" class="font-body-sm text-[11px] text-secondary"></span>
                        </div>
                    </div>

                    <div id="workspace-predict-container" class="flex flex-col gap-2 ${this.predictInputVisible?``:`hidden`}">
                        <textarea id="workspace-predict-sequence-input" rows="3" placeholder="Paste a raw amino-acid sequence (10-300 residues) to predict its structure via ESMFold - no existing accession needed" aria-label="Amino-acid sequence to predict a structure for" class="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase"></textarea>
                        <div class="flex items-center gap-3">
                            <button id="workspace-predict-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Predict Structure</button>
                            <span id="workspace-predict-feedback" class="font-body-sm text-[11px] text-secondary"></span>
                        </div>
                    </div>

                    <div id="workspace-pdb-list-container" class="flex flex-col gap-2 mt-1">
                        <!-- Dynamic list of PDBs with chain dropdowns -->
                    </div>

                    <div class="flex flex-col gap-2">
                        <button id="workspace-run-qc-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Run QC on all</button>
                        <div id="workspace-qc-summary" class="hidden flex-col gap-2"></div>
                    </div>

                    <div id="workspace-discovery-panel-slot" class="${this.discoveryPanelVisible?``:`hidden`}"></div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Batch screen (reference vs. many)</span>
                    <span class="font-body-sm text-body-sm text-secondary">Rank a batch of structures by TM-score/RMSD against one reference - a fast pairwise screen, independent of the N-way alignment above.</span>
                    <label class="flex flex-col gap-1">
                        <span class="font-label-sm text-label-sm text-secondary">Reference structure</span>
                        <select id="screen-reference-select" aria-label="Reference structure for batch screen" class="bg-surface-raised border border-border rounded-md px-3 py-1.5 text-body-sm text-primary focus:outline-none focus:border-accent font-mono"></select>
                    </label>
                    <textarea id="screen-targets-input" rows="2" placeholder="Paste target PDB IDs or accessions to screen against the reference (e.g. 4RLT, 3UG9, AF-P69905-F1)" aria-label="Target structures to screen against the reference" class="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase"></textarea>
                    <div class="flex items-center gap-3">
                        <button id="screen-run-btn" type="button" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Run Screen</button>
                        <span id="screen-feedback" class="font-body-sm text-[11px] text-secondary"></span>
                    </div>
                    <div id="screen-results"></div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Parameters</span>
                    <label class="flex items-center gap-3 cursor-pointer group" title="Removes crystallographic water molecules (HOH records) before alignment and analysis, since they carry no structural signal">
                        <input id="param-remove-water" type="checkbox" checked class="rounded border-border bg-surface-raised text-accent focus:ring-2 focus:ring-accent focus:ring-offset-1"/>
                        <span class="font-body-sm text-body-sm text-secondary group-hover:text-primary transition-colors">Filter water molecules (HOH)</span>
                    </label>
                    <label class="flex items-center gap-3 cursor-pointer group" title="Drops ions and buffer molecules used in crystallization, but keeps real bound ligands intact for the Ligand tab">
                        <input id="param-remove-heteroatoms" type="checkbox" checked class="rounded border-border bg-surface-raised text-accent focus:ring-2 focus:ring-accent focus:ring-offset-1"/>
                        <span class="font-body-sm text-body-sm text-secondary group-hover:text-primary transition-colors">Exclude non-ligand heteroatoms</span>
                    </label>
                </div>

                <button id="workspace-run-btn" class="btn-primary-hard w-full py-3 rounded-sm font-label-md text-label-md flex justify-center items-center gap-2">
                    <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                    Run Structural Alignment
                </button>
            </div>
        `,this.element=e,this.setupEventListeners(),this.refreshPDBList(),this.discoveryPanelVisible&&this.element.querySelector(`#workspace-discovery-panel-slot`).appendChild(this.discoveryPanel.render()),e}setupEventListeners(){let e=this.element.querySelector(`#workspace-add-pdb-btn`),t=this.element.querySelector(`#workspace-add-pdb-input`),n=this.element.querySelector(`#workspace-run-btn`),r=this.element.querySelector(`#workspace-add-pdb-suggestions`),i=e=>{r.innerHTML=``,(e&&e.length>0?e.slice(0,4):[]).forEach(e=>{let n=document.createElement(`span`);n.className=`px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-label-sm text-label-sm text-secondary cursor-pointer hover:text-primary transition-colors`,n.innerText=e,n.addEventListener(`click`,()=>{this.onAddPDB(e),t.value=``,i([])}),r.appendChild(n)})};t.addEventListener(`input`,()=>{clearTimeout(this.suggestTimeout);let e=t.value.trim();if(e.length<1){i([]);return}this.suggestTimeout=setTimeout(()=>{_(e).then(e=>{i(e.suggestions)}).catch(e=>{console.error(`Autocomplete suggestions failed:`,e)})},300)}),e.addEventListener(`click`,()=>{let e=t.value.trim().toUpperCase();f(e)&&(this.onAddPDB(e),t.value=``,i([]))}),t.addEventListener(`keypress`,e=>{if(e.key===`Enter`){let e=t.value.trim().toUpperCase();f(e)&&(this.onAddPDB(e),t.value=``,i([]))}}),n.addEventListener(`click`,()=>{this.selectedPDBs.length<2||this.onRunAlignment()}),this.element.querySelector(`#workspace-run-qc-btn`).addEventListener(`click`,()=>{this.runQcOnAll()});let a=this.element.querySelector(`#workspace-toggle-batch-add-btn`),o=this.element.querySelector(`#workspace-batch-add-container`),s=this.element.querySelector(`#workspace-batch-pdb-input`),c=this.element.querySelector(`#workspace-batch-add-btn`),l=this.element.querySelector(`#workspace-batch-add-feedback`);a.addEventListener(`click`,()=>{this.batchInputVisible=!this.batchInputVisible,o.classList.toggle(`hidden`,!this.batchInputVisible),this.batchInputVisible&&s.focus()}),c.addEventListener(`click`,async()=>{c.disabled=!0;try{let e=s.value.split(/[\s,]+/).map(e=>e.trim().toUpperCase()).filter(Boolean),t=[],n=[],r=0,i=new Set(this.selectedPDBs);e.forEach(e=>{if(!f(e)){n.push(e);return}if(i.has(e)){r+=1;return}i.add(e),t.push(e)});let a=0,o=0;if(t.length>0){let e=await this.onAddManyPDBs(t);o=e?.added?e.added.length:t.length,a=e?.overCap||0}let c=[];o>0&&c.push(`Added ${o}.`),r>0&&c.push(`Skipped ${r} already in the workspace.`),n.length>0&&c.push(`Couldn't recognize: ${n.join(`, `)}.`),a>0&&c.push(`Skipped ${a} — workspace limit is 20 structures.`),c.length===0&&c.push(`Nothing to add — paste at least one ID.`),l.innerText=c.join(` `),o>0&&(s.value=``)}finally{c.disabled=!1}});let u=this.element.querySelector(`#workspace-upload-structure-btn`),d=this.element.querySelector(`#workspace-upload-structure-input`),p=this.element.querySelector(`#workspace-upload-structure-feedback`);u.addEventListener(`click`,()=>d.click()),d.addEventListener(`change`,async()=>{let e=d.files?.[0];if(d.value=``,e){this.isUploading=!0,p.innerText=`Uploading ${e.name}...`;try{await this.onUploadStructure(e),p.innerText=`Added ${e.name}.`}catch(t){p.innerText=t.message||`Upload of ${e.name} failed.`}finally{this.isUploading=!1}}}),this.element.querySelector(`#screen-run-btn`).addEventListener(`click`,()=>{this.runScreen()});let m=this.element.querySelector(`#workspace-toggle-predict-btn`),h=this.element.querySelector(`#workspace-predict-container`),g=this.element.querySelector(`#workspace-predict-sequence-input`),v=this.element.querySelector(`#workspace-predict-btn`),y=this.element.querySelector(`#workspace-predict-feedback`);m.addEventListener(`click`,()=>{this.predictInputVisible=!this.predictInputVisible,h.classList.toggle(`hidden`,!this.predictInputVisible),this.predictInputVisible&&g.focus()}),v.addEventListener(`click`,async()=>{let e=g.value.trim().toUpperCase().replace(/\s+/g,``);if(e.length<10){y.innerText=`A sequence of at least 10 residues is required.`;return}this.isPredicting=!0,v.disabled=!0,y.innerText=`Predicting structure for ${e.length} residues (this can take up to a minute)…`;try{await this.onPredictFromSequence(e),y.innerText=`Structure predicted for ${e.length} residues.`,g.value=``}catch(e){y.innerText=e.message||`Structure prediction failed.`}finally{this.isPredicting=!1,v.disabled=!1}})}updateState(e,t,n){this.selectedPDBs=e,this.chainSelections=t,this.pdbMetadata=n,this.discoveryPanelVisible&&!this.selectedPDBs.includes(this.discoveryPanel.pdbId)&&this.hideDiscoveryPanel(),this.refreshPDBList()}setLoadingChains(e){this.isLoadingChains=e,this.refreshPDBList();let t=this.element?.querySelector(`#workspace-run-btn`);t&&(t.disabled=e)}showDiscoveryPanel(e){this.discoveryPanelVisible=!0;let t=this.element.querySelector(`#workspace-discovery-panel-slot`);t.classList.remove(`hidden`),t.innerHTML=``,t.appendChild(this.discoveryPanel.render()),this.discoveryPanel.runFor(e)}showSavedDiscoveryResults(e){if(this.discoveryPanelVisible=!0,!this.element)return;let t=this.element.querySelector(`#workspace-discovery-panel-slot`);t.classList.remove(`hidden`),t.innerHTML=``,t.appendChild(this.discoveryPanel.render()),this.discoveryPanel.loadSavedResults(e)}hideDiscoveryPanel(){this.discoveryPanelVisible=!1;let e=this.element?.querySelector(`#workspace-discovery-panel-slot`);e&&(e.classList.add(`hidden`),e.innerHTML=``)}refreshPDBList(){if(!this.element)return;let e=this.element.querySelector(`#workspace-pdb-count-badge`);e.innerText=`${this.selectedPDBs.length} Protein${this.selectedPDBs.length===1?``:`s`}`;let t=this.element.querySelector(`#workspace-run-btn`);t&&t.classList.toggle(`hidden`,this.selectedPDBs.length<2);let n=this.element.querySelector(`#screen-reference-select`);if(n){let e=n.value;n.innerHTML=this.selectedPDBs.map(e=>`<option value="${z(e)}">${z(e)}</option>`).join(``),this.selectedPDBs.includes(e)&&(n.value=e)}let r=this.element.querySelector(`#workspace-pdb-list-container`);if(this.isLoadingChains){r.innerHTML=`
                <div class="flex items-center justify-center py-4 gap-2 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Loading structure chains...
                </div>
            `;return}if(r.innerHTML=``,this.selectedPDBs.length===0){if(r.innerHTML=`
                <div class="flex flex-col items-center gap-4 py-4 text-center max-w-3xl mx-auto">
                    <div class="flex flex-col items-center gap-1">
                        <span class="font-headline-sm text-headline-sm font-semibold text-primary">Explore Curated Showcase Demos</span>
                        <span class="text-secondary font-body-sm">Add a structure to analyze it on its own, or 2+ to align them &mdash; or click an example below to instantly populate:</span>
                    </div>
                    <div id="workspace-quick-start" class="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left"></div>
                </div>
            `,!this.isSharedView&&!pt()){let e=document.createElement(`div`);e.id=`workspace-onboarding-hint`,e.className=`flex items-start justify-between gap-3 bg-surface-raised border border-border-subtle rounded-md px-4 py-3 mt-1 max-w-md mx-auto text-left`;let t=document.createElement(`span`);t.className=`font-body-sm text-body-sm text-secondary`,t.textContent=`Three ways to add a structure: type a PDB ID or accession above, upload a file, or paste a batch of IDs - pick whichever fits what you already have.`;let n=document.createElement(`button`);n.id=`workspace-onboarding-dismiss-btn`,n.type=`button`,n.className=`text-secondary hover:text-primary shrink-0`,n.setAttribute(`aria-label`,`Dismiss`),n.innerHTML=`<span class="material-symbols-outlined text-[16px]">close</span>`,n.addEventListener(`click`,()=>{mt(),e.remove()}),e.appendChild(t),e.appendChild(n),r.insertBefore(e,r.firstChild)}let e=r.querySelector(`#workspace-quick-start`);e&&this.onQuickStart&&B.forEach(t=>{let n=document.createElement(`button`);n.type=`button`,n.className=`quick-start-btn group text-left p-3.5 rounded-lg bg-surface border border-border-subtle hover:border-accent hover:bg-surface-raised transition-all duration-150 flex flex-col gap-1.5 shadow-sm`,n.innerHTML=`
                        <div class="flex items-center justify-between w-full">
                            <span class="inline-flex items-center gap-1.5 font-label-md text-label-md font-semibold text-primary group-hover:text-accent transition-colors">
                                <span class="material-symbols-outlined text-[18px] text-accent">${t.icon||`science`}</span>
                                ${t.label}
                            </span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono tracking-wide bg-surface-raised border border-border-subtle text-secondary">${t.tag||`Demo`}</span>
                        </div>
                        <span class="font-body-sm text-body-sm text-secondary line-clamp-2">${t.description||``}</span>
                        <span class="font-mono text-[11px] text-muted mt-1 flex items-center gap-1">
                            <span class="material-symbols-outlined text-[13px]">dataset</span>
                            ${t.pdbIds.join(` + `)}
                        </span>
                    `,n.addEventListener(`click`,()=>this.onQuickStart(t.pdbIds)),e.appendChild(n)});return}this.selectedPDBs.forEach(e=>this._renderPDBCard(e,r))}async runScreen(){let e=this.element.querySelector(`#screen-reference-select`),t=this.element.querySelector(`#screen-targets-input`),n=this.element.querySelector(`#screen-run-btn`),r=this.element.querySelector(`#screen-feedback`),i=this.element.querySelector(`#screen-results`),a=e.value,o=t.value.split(/[\s,]+/).map(e=>e.trim().toUpperCase()).filter(Boolean),s=o.filter(e=>f(e)),c=o.filter(e=>!f(e));if(!a){r.innerText=`Add a structure to the workspace to use as a reference first.`;return}if(s.length===0){r.innerText=c.length>0?`Couldn't recognize: ${c.join(`, `)}.`:`Paste at least one target PDB ID or accession.`;return}n.disabled=!0,i.innerHTML=``,r.innerText=`Screening ${s.length} structure(s) against ${a}...`;try{let e=await y(a,s);r.innerText=c.length>0?`Couldn't recognize: ${c.join(`, `)}.`:``,this.renderScreenResults(i,e)}catch(e){r.innerText=e.message||`Structure screen failed.`}finally{n.disabled=!1}}renderScreenResults(e,t){e.innerHTML=`
            <div class="overflow-x-auto mt-1">
                <table class="w-full text-left border-collapse">
                    <thead class="font-label-sm text-label-sm text-secondary">
                        <tr>
                            <th class="py-2 border-b border-border font-medium">Structure</th>
                            <th class="py-2 border-b border-border font-medium text-right">TM-score</th>
                            <th class="py-2 border-b border-border font-medium text-right">RMSD (Å)</th>
                        </tr>
                    </thead>
                    <tbody class="font-body-sm text-body-sm text-primary divide-y divide-border-subtle">
                        ${(t.results||[]).map(e=>`
            <tr>
                <td class="py-1.5 font-mono">${z(e.pdb_id)}</td>
                <td class="py-1.5 text-right font-mono">${e.tm_score==null?`—`:e.tm_score.toFixed(3)}</td>
                <td class="py-1.5 text-right font-mono">${e.rmsd==null?`—`:e.rmsd.toFixed(2)}</td>
            </tr>
        `).join(``)}
                    </tbody>
                </table>
            </div>
        `}_chainsOptionsHTML(e,t){return t?.chains?t.chains.map(t=>{let n=this.chainSelections[e]===t.id?`selected`:``;return`<option value="${t.id}" ${n}>Chain ${t.id} (${t.residue_count} residues)</option>`}).join(``):`<option value="A">Chain A</option>`}_citationLinkHTML(e){if(!e?.citation?.pubmed_id&&!e?.citation?.doi)return``;let t=e.citation,n=t.pubmed_id?`https://pubmed.ncbi.nlm.nih.gov/${t.pubmed_id}/`:`https://doi.org/${t.doi}`,r=t.pubmed_id?`PubMed`:`DOI`;return`<a href="${z(n)}" target="_blank" rel="noopener noreferrer" class="pdb-citation-link font-body-sm text-[11px] text-accent hover:underline pl-0.5" title="${z(t.title||``)}">View publication (${r})</a>`}_renderPDBCard(e,t){let n=this.pdbMetadata[e],r=document.createElement(`div`);r.className=`flex flex-col gap-1.5 p-3 rounded-md bg-surface-raised border border-border-subtle`;let i=this._chainsOptionsHTML(e,n),a=ft[n?.source]||`PDB`,o=n?[n.method,n.resolution,n.organism].filter(e=>e&&e!==`N/A`):[];n?.source===`upload`&&n.original_filename&&o.push(z(n.original_filename));let s=(n?.chains||[]).filter(e=>e.gaps?.length>0),c=s.reduce((e,t)=>e+t.gaps.length,0),l=s.flatMap(e=>e.gaps.map(t=>`Chain ${e.id}: residues ${t.after+1}-${t.before-1} missing`)).join(`; `),u=c===1?`region`:`regions`,d=this._citationLinkHTML(n);r.innerHTML=`
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="font-headline-sm text-body-md font-bold text-primary font-mono">${e}</span>
                    <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase source-badge">${a}</span>
                    <select class="bg-surface border border-border rounded-md px-2 py-1 text-body-sm text-secondary focus:outline-none focus:border-accent font-mono chain-select" data-pdb="${e}">
                        ${i}
                    </select>
                </div>
                <div class="flex items-center gap-1">
                    <button class="discover-structure-btn font-label-sm text-label-sm text-secondary hover:text-accent px-2 py-1 rounded-md hover:bg-surface transition-colors whitespace-nowrap" data-pdb="${e}">What is this?</button>
                    <button class="text-error hover:text-red-400 p-1 rounded-md hover:bg-surface transition-colors remove-pdb-btn" data-pdb="${e}" aria-label="Remove structure ${e}">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                </div>
            </div>
            ${o.length>0?`<span class="pdb-meta-line font-body-sm text-[11px] text-secondary pl-0.5">${o.join(` · `)}</span>`:``}
            ${n?.is_nmr?`<span class="pdb-nmr-badge font-body-sm text-[11px] text-tertiary pl-0.5" title="Showing model 1 of ${n.num_models} - other conformers in this NMR ensemble aren't analyzed.">NMR · ${n.num_models} models (model 1 shown)</span>`:``}
            ${c>0?`<span class="pdb-gaps-badge font-body-sm text-[11px] text-tertiary pl-0.5" title="${z(l)}">${c} disordered ${u}</span>`:``}
            ${n?.source===`pdb`?`<span id="validation-badge-${e}" class="pdb-validation-badge font-body-sm text-[11px] text-tertiary pl-0.5" title="From wwPDB's own validation pipeline. Archive percentile is how this structure's clashscore/Ramachandran-outlier rate compares to every other validated entry in the archive - higher is better.">${this._validationBadgeContent(e)}</span>`:``}
            ${n?.source===`pdb`?`<span id="cath-badge-${e}" class="pdb-cath-badge font-body-sm text-[11px] text-tertiary pl-0.5">${this._cathBadgeContent(e)}</span>`:``}
            ${n?.source===`pdb`?`<span id="assembly-badge-${e}" class="pdb-assembly-badge font-body-sm text-[11px] text-tertiary pl-0.5">${this._assemblyBadgeContent(e)}</span>`:``}
            ${d}
        `,r.querySelector(`.chain-select`).addEventListener(`change`,t=>{this.onChainSelection(e,t.target.value)}),r.querySelector(`.remove-pdb-btn`).addEventListener(`click`,()=>{this.onRemovePDB(e)}),r.querySelector(`.discover-structure-btn`).addEventListener(`click`,()=>{this.showDiscoveryPanel(e)}),t.appendChild(r),n?.source===`pdb`&&(this._loadValidation(e),this._loadCath(e),this._loadAssembly(e))}_validationBadgeContent(e){let t=this.validationCache[e];if(t===void 0)return`Checking wwPDB validation…`;if(!t)return`No wwPDB validation report available`;let n=[];return t.clashscore&&n.push(`Clashscore ${t.clashscore.value.toFixed(1)} (archive percentile ${Math.round(t.clashscore.percentile_archive)})`),t.percent_rama_outliers&&n.push(`Rama outliers ${t.percent_rama_outliers.value.toFixed(1)}% (archive percentile ${Math.round(t.percent_rama_outliers.percentile_archive)})`),n.length>0?n.join(` · `):`No wwPDB validation report available`}async _loadValidation(e){if(this.validationCache[e]!==void 0||this._validationLoading.has(e))return;this._validationLoading.add(e);try{let t=await Ne(e);this.validationCache[e]=t.validation}catch(t){console.error(`Failed to load wwPDB validation for`,e,t),this.validationCache[e]=null}finally{this._validationLoading.delete(e)}let t=this.element?.querySelector(`#validation-badge-${e}`);t&&(t.textContent=this._validationBadgeContent(e))}_cathBadgeContent(e){let t=this.cathCache[e];if(t===void 0)return`Checking CATH classification…`;if(!t||t.length===0)return`No CATH classification available`;let n=[...new Set(t.map(e=>e.classification))];return n.length>1?`CATH ${n[0]} (+${n.length-1} more)`:`CATH ${n[0]}`}async _loadCath(e){if(this.cathCache[e]!==void 0||this._cathLoading.has(e))return;this._cathLoading.add(e);try{let t=await ze(e);this.cathCache[e]=t.domains}catch(t){console.error(`Failed to load CATH classification for`,e,t),this.cathCache[e]=null}finally{this._cathLoading.delete(e)}let t=this.element?.querySelector(`#cath-badge-${e}`);t&&(t.textContent=this._cathBadgeContent(e))}_assemblyBadgeContent(e){let t=this.assemblyCache[e];return t===void 0?`Checking assembly state…`:t?.oligomeric_details?t.oligomeric_details.charAt(0).toUpperCase()+t.oligomeric_details.slice(1):`No assembly state available`}async _loadAssembly(e){if(this.assemblyCache[e]!==void 0||this._assemblyLoading.has(e))return;this._assemblyLoading.add(e);try{let t=await Be(e);this.assemblyCache[e]=t.assembly}catch(t){console.error(`Failed to load assembly info for`,e,t),this.assemblyCache[e]=null}finally{this._assemblyLoading.delete(e)}let t=this.element?.querySelector(`#assembly-badge-${e}`);t&&(t.textContent=this._assemblyBadgeContent(e))}async runQcOnAll(){if(!this.element||this.selectedPDBs.length===0)return;let e=this.element.querySelector(`#workspace-run-qc-btn`),t=this.element.querySelector(`#workspace-qc-summary`);e.disabled=!0,t.classList.remove(`hidden`),t.classList.add(`flex`),t.innerHTML=`<div class="font-body-sm text-[11px] text-secondary"><span class="animate-spin material-symbols-outlined text-[14px]">sync</span> Running QC on ${this.selectedPDBs.length} structure(s)…</div>`;let n=await Promise.all(this.selectedPDBs.map(async e=>{try{let t=await Pe(e),n=await Re(e).catch(()=>null);return{...t,self_clash:n?.clashes??null}}catch(t){return console.error(`QC failed for`,e,t),{pdb_id:e,error:!0}}}));e.disabled=!1,this.renderQcSummary(n)}renderQcSummary(e){let t=this.element.querySelector(`#workspace-qc-summary`);t.innerHTML=``;let n=document.createElement(`table`);n.className=`w-full text-left border-collapse`,n.innerHTML=`
            <thead class="font-label-sm text-label-sm text-secondary">
                <tr>
                    <th class="px-0 py-1.5 border-b border-border font-medium">Structure</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Favored %</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right" title="Raw count of Ramachandran-outlier residues from this sweep's own computation - a different, independent signal from the wwPDB validation badge's percentage above.">Outlier Count</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Helix %</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Clashscore</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Self Clash</th>
                </tr>
            </thead>
        `;let r=document.createElement(`tbody`);r.className=`font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle`,e.forEach(e=>{let t=document.createElement(`tr`);if(e.error){t.innerHTML=`<td class="py-1.5">${z(e.pdb_id)}</td><td class="px-3 py-1.5 text-secondary" colspan="5">QC failed for this structure.</td>`,r.appendChild(t);return}let n=e.ramachandran_stats,i=e.secondary_structure_stats,a=e.validation?.clashscore?.value,o=e.self_clash?.clashscore,s=this.pdbMetadata[e.pdb_id]?.source===`pdb`,c=document.createElement(`td`);c.className=`py-1.5`,c.textContent=e.pdb_id,t.appendChild(c),[{value:n?.favored_percent==null?`--`:n.favored_percent.toFixed(1)},{value:n?.outlier_count??`--`},{value:i?.helix_percent==null?`--`:i.helix_percent.toFixed(1)},a==null?{value:s?`--`:`N/A`,title:s?void 0:`wwPDB validation only exists for real, experimentally-solved PDB entries.`}:{value:a.toFixed(1)},{value:o==null?`--`:o.toFixed(1)}].forEach(({value:e,title:n})=>{let r=document.createElement(`td`);r.className=`px-3 py-1.5 text-right`,r.textContent=e,n&&(r.title=n),t.appendChild(r)}),r.appendChild(t)}),n.appendChild(r);let i=document.createElement(`div`);i.className=`overflow-x-auto`,i.appendChild(n),t.appendChild(i)}getParameters(){return{removeWater:this.element.querySelector(`#param-remove-water`).checked,removeHeteroatoms:this.element.querySelector(`#param-remove-heteroatoms`).checked}}setAligning(e){let t=this.element.querySelector(`#workspace-run-btn`);t&&(e?(t.disabled=!0,t.innerHTML=`
                <span class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                Aligning Pipeline...
            `):(t.disabled=!1,t.innerHTML=`
                <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Structural Alignment
            `))}};function gt(e){switch(e){case`Hydrogen Bond`:return`bg-accent`;case`Salt Bridge`:return`bg-success`;case`Van der Waals`:return`bg-muted`;case`Metal Coordination`:return`bg-error`;default:return`bg-secondary`}}function q(e){let t=document.createElement(`tr`);return t.innerHTML=`
        <td class="px-0 py-2.5">${e.resn||e.residue||`UNK`}</td>
        <td class="px-3 py-2.5">${e.chain}</td>
        <td class="px-3 py-2.5 text-right text-secondary group-hover:text-primary">${e.resi}</td>
        <td class="px-3 py-2.5 text-right font-semibold">${e.distance.toFixed(1)}</td>
        <td class="px-3 py-2.5"><span class="inline-flex items-center gap-1.5 text-secondary"><span class="w-1.5 h-1.5 rounded-full ${gt(e.type)}"></span>${e.type}</span></td>
    `,t}var _t={rmsd:{title:`Shape Difference (RMSD)`,badge:`Shape Match`,summary:`Measures how much the 3D structures diverge on average in Angstroms (Å).`,detail:`Scores below 2.0 Å mean the proteins are nearly identical twins in 3D shape; scores above 4.0 Å indicate noticeably different shapes.`,ruleOfThumb:`< 2.0 Å: Close match | > 4.0 Å: Distinct difference`},tmScore:{title:`Fold Family Match (TM-score)`,badge:`Fold Match`,summary:`A normalized similarity score ranging from 0.0 to 1.0.`,detail:`Unlike sequence-only comparisons, TM-score evaluates 3D architecture. Any score above 0.5 proves both proteins share the exact same structural fold family.`,ruleOfThumb:`> 0.50: Same structural fold family | < 0.30: Unrelated folds`},ramachandran:{title:`Protein Physical Health (Ramachandran)`,badge:`Backbone Health`,summary:`A quality check on the protein backbone dihedral angles.`,detail:`Checks if amino acid residues sit in physically natural, unstrained geometry. Outliers highlight possible structural distortion or modeling errors.`,ruleOfThumb:`> 95% Favored: Healthy physical model`},ligandPocket:{title:`Medicine Docking Cavity (Binding Pocket)`,badge:`Drug Target`,summary:`A 3D surface cavity where drug molecules can anchor.`,detail:`Identifies druggable pockets on the protein surface where therapeutic compounds or natural cofactors bind to switch biological activity on or off.`,ruleOfThumb:`Larger volume & high SASA indicate prime docking sites`},clinvar:{title:`Human Disease Link (ClinVar)`,badge:`Medical Impact`,summary:`Connects genetic mutations directly to human medical records.`,detail:`Surfaces whether a specific amino acid substitution is medically classified as Pathogenic (causes disease), Benign (harmless variation), or Uncertain.`,ruleOfThumb:`Pathogenic = Clinically confirmed disease variant`},discover:{title:`Unknown Protein Decoder (Discovery Mode)`,badge:`Mystery Decoder`,summary:`Predicts biological function for unannotated 3D models.`,detail:`Searches global structural databases using Foldseek to find known proteins that share the same 3D fold, then aggregates functional GO terms and domains.`,ruleOfThumb:`Structure is conserved millions of years longer than sequence`}};function J(e,t=``){let n=_t[e];if(!n)return z(t);let r=z(n.title),i=z(n.detail),a=z(n.ruleOfThumb),o=z(n.badge);return`
        <span class="inline-flex items-center gap-1 group relative cursor-help select-none">
            ${t?`<span class="mr-1">${z(t)}</span>`:``}
            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-surface-raised border border-border-subtle text-secondary group-hover:text-accent transition-colors" title="${r}: ${i}">
                <span class="material-symbols-outlined text-[13px] mr-0.5 text-accent">lightbulb</span>
                ${o}
            </span>
            <span class="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 rounded-lg bg-surface border border-border shadow-panel text-[12px] leading-relaxed text-primary opacity-0 group-hover:opacity-100 transition-opacity z-50">
                <span class="font-bold text-accent block mb-1">${r}</span>
                <span class="text-secondary block mb-1.5">${i}</span>
                <span class="text-[11px] font-mono text-muted block border-t border-border-subtle pt-1">${a}</span>
            </span>
        </span>
    `}var vt=class{constructor(e){this.selectedPDBs=e.selectedPDBs||[],this.currentRunId=e.currentRunId,this.onResidueSelected=e.onResidueSelected,this.onLigandSelected=e.onLigandSelected,this.ligandsList=[],this.element=null,this.selectedLigandId=``,this.currentStructureIndex=0,this.pocketSimilarity=null,this.availableChains=[]}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-ligands-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Binding Pocket</span>
                    <h2 class="section-title">Ligand inspector</h2>
                </div>
                <div class="flex gap-2">
                    <select id="ligand-structure-select" aria-label="Structure to inspect ligands for" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[140px]">
                    </select>
                    <select id="ligand-select" aria-label="Ligand to inspect" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[220px]">
                        <option value="">No Ligands Loaded</option>
                    </select>
                </div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <div id="ligand-pocket-desc" class="font-body-sm text-body-sm text-secondary leading-relaxed">
                    Add a second structure and run alignment to analyze ligands here in Compare mode. For a single structure, use Discover mode's ligand inspector instead.
                </div>
                <div id="ligand-sasa-row" class="stat-row hidden max-w-[180px]">
                    <span class="stat-key">SASA</span>
                    <span id="ligand-sasa-badge" class="stat-value" title="Solvent-accessible surface area of the binding pocket, in square Angstroms - a rough measure of pocket size">-- Å²</span>
                </div>
                <div id="ligand-chemistry-info" class="font-body-sm text-[11px] text-secondary hidden"></div>
                <div id="ligand-analogs-info" class="font-body-sm text-[11px] text-secondary hidden flex-wrap items-baseline gap-1.5"></div>
                <div id="ligand-bioactivity-info" class="font-body-sm text-[11px] text-secondary hidden flex-col gap-1"></div>

                <div class="flex items-baseline justify-between mt-2 pt-4 border-t border-border">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Molecular interactions</span>
                    <span id="interaction-count" class="font-label-sm text-label-sm text-secondary">0 Found</span>
                </div>
                <table class="w-full text-left border-collapse">
                    <thead class="font-label-sm text-label-sm text-secondary">
                    <tr>
                        <th class="px-0 py-2 border-b border-border font-medium">Residue</th>
                        <th class="px-3 py-2 border-b border-border font-medium">Chain</th>
                        <th class="px-3 py-2 border-b border-border font-medium text-right">Resi</th>
                        <th class="px-3 py-2 border-b border-border font-medium text-right">Dist (Å)</th>
                        <th class="px-3 py-2 border-b border-border font-medium">Type</th>
                    </tr>
                    </thead>
                    <tbody id="interactions-table-body" class="font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle">
                        <tr>
                            <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                                Select a ligand to populate interactions.
                            </td>
                        </tr>
                    </tbody>
                </table>

                <div id="pocket-similarity-section" class="hidden flex-col gap-2 mt-6 pt-4 border-t border-border">
                    <div class="flex items-baseline justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">${J(`ligandPocket`,`Binding pocket similarity`)}</span>
                        <span class="font-body-sm text-body-sm text-secondary">Jaccard index of pocket residue composition</span>
                    </div>
                    <div id="pocket-similarity-heatmap" class="w-full h-[320px]"></div>
                </div>

                <div id="candidate-pockets-section" class="hidden flex-col gap-2 mt-6 pt-4 border-t border-border">
                    <div class="flex items-baseline justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">${J(`ligandPocket`,`Candidate binding pockets`)}</span>
                        <span class="font-body-sm text-body-sm text-secondary">Heuristic - no bound ligand to analyze directly</span>
                    </div>
                    <table class="w-full text-left border-collapse">
                        <thead class="font-label-sm text-label-sm text-secondary">
                        <tr>
                            <th class="px-0 py-2 border-b border-border font-medium">Rank</th>
                            <th class="px-3 py-2 border-b border-border font-medium">Lining residues</th>
                            <th class="px-3 py-2 border-b border-border font-medium text-right">Score</th>
                            <th class="px-3 py-2 border-b border-border font-medium text-right">Est. volume (&Aring;&sup3;)</th>
                        </tr>
                        </thead>
                        <tbody id="candidate-pockets-table-body" class="font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle"></tbody>
                    </table>
                    <div class="flex items-center gap-3 mt-2">
                        <button id="prankweb-detect-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Detect real pockets (PrankWeb)</button>
                        <span id="prankweb-feedback" class="font-body-sm text-[11px] text-secondary"></span>
                    </div>
                    <div id="prankweb-pockets-section" class="hidden flex-col gap-2">
                        <span class="font-body-sm text-body-sm text-secondary">Real geometric cavity detection (P2Rank) - not a heuristic, an independent computational prediction</span>
                        <table class="w-full text-left border-collapse">
                            <thead class="font-label-sm text-label-sm text-secondary">
                            <tr>
                                <th class="px-0 py-2 border-b border-border font-medium">Rank</th>
                                <th class="px-3 py-2 border-b border-border font-medium">Lining residues</th>
                                <th class="px-3 py-2 border-b border-border font-medium text-right">Score</th>
                                <th class="px-3 py-2 border-b border-border font-medium text-right">Probability</th>
                            </tr>
                            </thead>
                            <tbody id="prankweb-pockets-table-body" class="font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle"></tbody>
                        </table>
                    </div>
                </div>

                <div id="interface-section" class="hidden flex-col gap-3 mt-6 pt-4 border-t border-border">
                    <div class="flex items-baseline justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Protein-protein interfaces</span>
                        <span class="font-body-sm text-body-sm text-secondary">Residues from two chains close enough to touch where the proteins bind each other</span>
                    </div>
                    <div class="flex items-end gap-3">
                        <label class="flex flex-col gap-1">
                            <span class="font-label-sm text-label-sm text-secondary">Chain A</span>
                            <select id="interface-chain-a" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono"></select>
                        </label>
                        <label class="flex flex-col gap-1">
                            <span class="font-label-sm text-label-sm text-secondary">Chain B</span>
                            <select id="interface-chain-b" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono"></select>
                        </label>
                        <button id="interface-analyze-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Analyze Interface</button>
                    </div>
                    <div id="interface-results" class="flex flex-col gap-3"></div>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),this.populateStructurePicker(),this.populateDropdown(),e}setupEventListeners(){this.element.querySelector(`#ligand-select`).addEventListener(`change`,async e=>{let t=e.target.value;this.selectedLigandId=t,await this.loadInteractions(t)}),this.element.querySelector(`#ligand-structure-select`).addEventListener(`change`,async e=>{await this.switchStructure(Number.parseInt(e.target.value,10))}),this.element.querySelector(`#interface-analyze-btn`).addEventListener(`click`,()=>this.analyzeInterface()),this.element.querySelector(`#prankweb-detect-btn`).addEventListener(`click`,()=>this.runPrankwebDetection())}populateStructurePicker(){if(!this.element)return;let e=this.element.querySelector(`#ligand-structure-select`);e.innerHTML=``,this.selectedPDBs.forEach((t,n)=>{let r=document.createElement(`option`);r.value=String(n),r.textContent=t,n===this.currentStructureIndex&&(r.selected=!0),e.appendChild(r)})}async switchStructure(e){if(e===this.currentStructureIndex)return;this.currentStructureIndex=e,this.selectedLigandId=``,this.clearTable(),this.onLigandSelected(this.currentStructureIndex,``);let t=this.selectedPDBs[e];try{let e=await w(t,this.currentRunId);this.ligandsList=e.ligands||[]}catch(e){console.error(`Failed to load ligands for structure:`,e),this.ligandsList=[]}this.populateDropdown(),await this.loadAvailableChains(),await this.loadCandidatePockets()}updateLigands(e,t,n,r=null){this.ligandsList=e||[],this.currentRunId=t,n&&(this.selectedPDBs=n),this.currentStructureIndex=0,this.selectedLigandId=``,this.pocketSimilarity=r,this.populateStructurePicker(),this.populateDropdown(),this.clearTable(),this.renderPocketSimilarity(),this.loadAvailableChains(),this.loadCandidatePockets()}async loadAvailableChains(){if(!this.element)return;let e=this.selectedPDBs[this.currentStructureIndex];if(!e){this.availableChains=[],this.renderInterfaceSection();return}try{let t=(await v([e])).chains?.[e];this.availableChains=(t?.chains||[]).map(e=>e.id)}catch(e){console.error(`Failed to load chain list for interface analysis:`,e),this.availableChains=[]}this.renderInterfaceSection()}async loadCandidatePockets(){if(!this.element)return;let e=this.element.querySelector(`#candidate-pockets-section`),t=this.selectedPDBs[this.currentStructureIndex];if(!t||this.ligandsList.length>0){e.classList.add(`hidden`),e.classList.remove(`flex`);return}try{let e=await de(t,this.currentRunId);this.renderCandidatePockets(e.pockets||[])}catch(e){console.error(`Failed to load candidate pockets:`,e),this.renderCandidatePockets([])}}renderCandidatePockets(e){if(!this.element)return;let t=this.element.querySelector(`#candidate-pockets-section`),n=this.element.querySelector(`#candidate-pockets-table-body`);if(!e||e.length===0){t.classList.add(`hidden`),t.classList.remove(`flex`);return}t.classList.remove(`hidden`),t.classList.add(`flex`),n.innerHTML=``,e.forEach(e=>{let t=document.createElement(`tr`),r=document.createElement(`td`);r.className=`py-1.5`,r.textContent=e.rank,t.appendChild(r);let i=(e.residues||[]).map(e=>`${e.resn} ${e.chain}${e.resi}`).join(`, `),a=document.createElement(`td`);a.className=`px-3 py-1.5`;let o=document.createElement(`span`);o.className=`block max-w-[280px] truncate`,o.title=i,o.textContent=i,a.appendChild(o),t.appendChild(a);let s=document.createElement(`td`);s.className=`px-3 py-1.5 text-right`,s.textContent=e.score,t.appendChild(s);let c=document.createElement(`td`);c.className=`px-3 py-1.5 text-right`,c.textContent=e.volume_estimate_a3==null?`--`:e.volume_estimate_a3,t.appendChild(c),n.appendChild(t)})}async runPrankwebDetection(){let e=this.element.querySelector(`#prankweb-detect-btn`),t=this.element.querySelector(`#prankweb-feedback`),n=this.selectedPDBs[this.currentStructureIndex];if(n){e.disabled=!0,t.textContent=`Submitting to PrankWeb…`;try{let e=await ae(n,this.currentRunId);t.textContent=`Running P2Rank (this can take a minute)…`;let r=await b(e.job_id,{intervalMs:8e3});if(r.status===`failed`){t.textContent=r.error||`PrankWeb pocket detection failed.`;return}let i=r.prediction?.pockets||[];t.textContent=i.length>0?`Found ${i.length} real pocket(s).`:`No real pockets detected for this structure.`,this.renderPrankwebPockets(i)}catch(e){console.error(`PrankWeb pocket detection failed:`,e),t.textContent=e.message||`PrankWeb pocket detection failed.`}finally{e.disabled=!1}}}renderPrankwebPockets(e){let t=this.element.querySelector(`#prankweb-pockets-section`),n=this.element.querySelector(`#prankweb-pockets-table-body`);if(!e||e.length===0){t.classList.add(`hidden`),t.classList.remove(`flex`);return}t.classList.remove(`hidden`),t.classList.add(`flex`),n.innerHTML=``,e.forEach(e=>{let t=document.createElement(`tr`),r=document.createElement(`td`);r.className=`py-1.5`,r.textContent=e.rank,t.appendChild(r);let i=(e.residues||[]).map(e=>e.replace(`_`,``)).join(`, `),a=document.createElement(`td`);a.className=`px-3 py-1.5`;let o=document.createElement(`span`);o.className=`block max-w-[280px] truncate`,o.title=i,o.textContent=i,a.appendChild(o),t.appendChild(a);let s=document.createElement(`td`);s.className=`px-3 py-1.5 text-right`,s.textContent=e.score,t.appendChild(s);let c=document.createElement(`td`);c.className=`px-3 py-1.5 text-right`,c.textContent=e.probability,t.appendChild(c),n.appendChild(t)})}renderInterfaceSection(){if(!this.element)return;let e=this.element.querySelector(`#interface-section`),t=this.element.querySelector(`#interface-chain-a`),n=this.element.querySelector(`#interface-chain-b`),r=this.element.querySelector(`#interface-results`);if(r.innerHTML=``,this.availableChains.length<2){e.classList.add(`hidden`),e.classList.remove(`flex`);return}e.classList.remove(`hidden`),e.classList.add(`flex`);let i=(e,t)=>{e.innerHTML=``,this.availableChains.forEach((n,r)=>{let i=document.createElement(`option`);i.value=n,i.textContent=n,r===t&&(i.selected=!0),e.appendChild(i)})};i(t,0),i(n,1)}async analyzeInterface(){if(!this.element)return;let e=this.element.querySelector(`#interface-chain-a`).value,t=this.element.querySelector(`#interface-chain-b`).value,n=this.element.querySelector(`#interface-results`);if(!e||!t||e===t){n.innerHTML=`<div class="font-body-sm text-body-sm text-secondary py-2">Select two different chains.</div>`;return}n.innerHTML=`
            <div class="font-body-sm text-body-sm text-secondary py-2">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span> Analyzing interface...
            </div>
        `;try{let n=this.selectedPDBs[this.currentStructureIndex],r=await Ge(n,e,t,this.currentRunId);this.renderInterfaceResults(r.interface)}catch(e){console.error(`Failed to analyze interface:`,e),n.innerHTML=`<div class="font-body-sm text-body-sm text-secondary py-2">Failed to analyze interface.</div>`}}renderInterfaceResults(e){let t=this.element.querySelector(`#interface-results`);if(t.innerHTML=``,!e||e.error){let n=document.createElement(`div`);n.className=`font-body-sm text-body-sm text-secondary py-2`,n.textContent=e?.error||`No interface data returned.`,t.appendChild(n);return}let n=document.createElement(`span`);n.className=`font-label-sm text-label-sm text-secondary`,n.title=`Surface area that becomes solvent-inaccessible once these two chains bind - a larger value means a bigger, typically tighter-binding interface`,n.textContent=`Buried interface area: ${e.buried_area?.toFixed(1)??`--`} Å²`,t.appendChild(n);let r=(e,t)=>{let n=document.createElement(`div`);n.className=`flex flex-col gap-1.5`;let r=document.createElement(`span`);if(r.className=`font-label-sm text-label-sm text-secondary uppercase`,r.textContent=e,n.appendChild(r),!t||t.length===0){let e=document.createElement(`div`);return e.className=`font-body-sm text-body-sm text-secondary py-1`,e.textContent=`No contact residues found.`,n.appendChild(e),n}let i=document.createElement(`table`);i.className=`w-full text-left border-collapse`,i.innerHTML=`
                <thead class="font-label-sm text-label-sm text-secondary">
                    <tr>
                        <th class="px-0 py-1.5 border-b border-border font-medium">Residue</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium">Chain</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium text-right">Resi</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium text-right">Dist (Å)</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium">Type</th>
                    </tr>
                </thead>
            `;let a=document.createElement(`tbody`);return a.className=`font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle`,t.forEach(e=>a.appendChild(q(e))),i.appendChild(a),n.appendChild(i),n};t.appendChild(r(`Chain ${e.chain_a} contacts`,e.chain_a_contacts)),t.appendChild(r(`Chain ${e.chain_b} contacts`,e.chain_b_contacts))}renderPocketSimilarity(){if(!this.element)return;let e=this.element.querySelector(`#pocket-similarity-section`),t=this.element.querySelector(`#pocket-similarity-heatmap`),n=this.pocketSimilarity;if(!n?.data?.length||n.data.length<2){e.classList.add(`hidden`);return}e.classList.remove(`hidden`);let r=n.columns.map(e=>{let t=e.indexOf(`:`);return t===-1?e:`${e.slice(0,t)}<br>${e.slice(t+1)}`}),i={z:n.data,x:r,y:r,type:`heatmap`,colorscale:`RdBu`,reversescale:!0,zmin:0,zmax:1};Plotly.newPlot(t,[i],{height:320,margin:{l:90,r:20,t:10,b:90},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`}},{responsive:!0,displayModeBar:!1})}populateDropdown(){if(!this.element)return;let e=this.element.querySelector(`#ligand-select`);if(e.innerHTML=``,this.ligandsList.length===0){e.innerHTML=`<option value="">No Ligands Loaded</option>`;return}let t=document.createElement(`option`);t.value=``,t.innerText=`Select a Ligand`,e.appendChild(t),this.ligandsList.forEach(t=>{let n=document.createElement(`option`);n.value=t.id,n.innerText=`${t.name} (Chain ${t.chain}, Resi ${t.resi})`,this.selectedLigandId===t.id&&(n.selected=!0),e.appendChild(n)})}clearTable(){if(!this.element)return;let e=this.element.querySelector(`#ligand-pocket-desc`);e.innerText=`Add a second structure and run alignment to analyze ligands here in Compare mode. For a single structure, use Discover mode's ligand inspector instead.`,this.element.querySelector(`#ligand-sasa-row`).classList.add(`hidden`),this.element.querySelector(`#ligand-chemistry-info`).classList.add(`hidden`),this.element.querySelector(`#interaction-count`).innerText=`0 Found`,this.element.querySelector(`#interactions-table-body`).innerHTML=`
            <tr>
                <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                    Select a ligand to populate interactions.
                </td>
            </tr>
        `}async loadInteractions(e){if(!this.element)return;let t=this.element.querySelector(`#interactions-table-body`),n=this.element.querySelector(`#ligand-pocket-desc`),r=this.element.querySelector(`#interaction-count`),i=this.element.querySelector(`#ligand-sasa-badge`),a=this.element.querySelector(`#ligand-sasa-row`);if(!e){this.clearTable(),this.onLigandSelected(this.currentStructureIndex,``);return}t.innerHTML=`
            <tr>
                <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Analyzing interactions...
                </td>
            </tr>
        `;try{let o=this.selectedPDBs[this.currentStructureIndex],s=(await fe(o,e,this.currentRunId)).interactions,c=s.interactions;this.onLigandSelected(this.currentStructureIndex,e,c),n.innerText=`Conserved catalytic pocket near ligand ${s.ligand}. Stable hydrophobic cluster showing coordinated interactions.`,this.loadLigandChemistry(e),s.pocket_sasa?(i.innerText=`${s.pocket_sasa.toFixed(1)} Å²`,a.classList.remove(`hidden`)):a.classList.add(`hidden`),r.innerText=`${c.length} Found`,t.innerHTML=``,c.length===0?t.innerHTML=`
                    <tr>
                        <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                            No specific interaction contacts found.
                        </td>
                    </tr>
                `:c.forEach(e=>{let n=q(e);n.className=`hover:bg-surface-raised transition-colors cursor-pointer group`,n.addEventListener(`click`,()=>{this.element.querySelectorAll(`#interactions-table-body tr`).forEach(e=>{e.className=`hover:bg-surface-raised transition-colors cursor-pointer group`;for(let t of e.querySelectorAll(`td`))t.classList.remove(`text-tertiary`,`font-bold`)}),n.className=`row-selected cursor-pointer group`,n.querySelectorAll(`td`).forEach(e=>e.classList.add(`text-tertiary`,`font-bold`)),this.onResidueSelected(this.currentStructureIndex,e.chain,e.resi,e.aligned_resi)}),t.appendChild(n)})}catch(e){console.error(`Failed to load interactions:`,e),t.innerHTML=`
                <tr>
                    <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                        Failed to calculate pocket site contacts.
                    </td>
                </tr>
            `}}async loadLigandChemistry(e){let t=this.element.querySelector(`#ligand-chemistry-info`),n=this.element.querySelector(`#ligand-analogs-info`),r=this.element.querySelector(`#ligand-bioactivity-info`);if(!t)return;let i=this.ligandsList.find(t=>t.id===e),a=i?i.name:e.split(`_`)[0];t.textContent=`Looking up ligand chemistry…`,t.classList.remove(`hidden`),n&&(n.classList.add(`hidden`),n.classList.remove(`flex`),n.innerHTML=``),r&&(r.classList.add(`hidden`),r.classList.remove(`flex`),r.innerHTML=``);try{let e=await ue(a);if(!e.chemistry){t.textContent=`${a}: no chemistry data found.`;return}let n=e.chemistry,r=[n.name,n.formula].filter(Boolean);t.textContent=r.length>0?r.join(` · `):`${a}: no chemistry data found.`,t.title=n.smiles?`SMILES: ${n.smiles}`:``,this.renderLigandAnalogs(e.pubchem_analogs),this.renderLigandBioactivity(e.chembl_bioactivity)}catch(e){console.error(`Failed to load ligand chemistry:`,e),t.textContent=`${a}: chemistry lookup failed.`}}renderLigandAnalogs(e){let t=this.element.querySelector(`#ligand-analogs-info`);if(!t||!e||e.length===0)return;t.classList.remove(`hidden`),t.classList.add(`flex`);let n=document.createElement(`span`);n.textContent=`Similar known compounds:`,t.appendChild(n),e.forEach(({cid:e,url:n})=>{let r=document.createElement(`a`);r.href=n,r.target=`_blank`,r.rel=`noopener noreferrer`,r.className=`text-accent hover:underline`,r.textContent=`CID ${e}`,t.appendChild(r)})}renderLigandBioactivity(e){let t=this.element.querySelector(`#ligand-bioactivity-info`);if(!t||!e||e.length===0)return;t.classList.remove(`hidden`),t.classList.add(`flex`);let n=document.createElement(`span`);n.textContent=`Known bioactivity:`,t.appendChild(n),e.forEach(({target:e,type:n,value:r,units:i})=>{let a=document.createElement(`span`);a.textContent=`${e||`Unknown target`}: ${n} ${r} ${i||``}`.trim(),t.appendChild(a)})}},yt=[{key:`summary`,label:`Summary`},{key:`insights`,label:`Insights`},{key:`heatmap`,label:`RMSD Heatmap`},{key:`tree`,label:`Phylogenetic Tree`},{key:`matrix`,label:`RMSD Matrix`}],bt={hydrophobic:`#f4a636`,polar:`#2ecc71`,basic:`#3498db`,acidic:`#e74c3c`,special:`#9b59b6`},xt={A:`hydrophobic`,V:`hydrophobic`,L:`hydrophobic`,I:`hydrophobic`,M:`hydrophobic`,F:`hydrophobic`,W:`hydrophobic`,C:`hydrophobic`,S:`polar`,T:`polar`,N:`polar`,Q:`polar`,Y:`polar`,K:`basic`,R:`basic`,H:`basic`,D:`acidic`,E:`acidic`,G:`special`,P:`special`};function St(e){return bt[xt[e]]||`#7f8c8d`}var Ct=class e{currentRunId=null;element=null;stats={rmsd:null,aligned_length:null,seq_identity:null,seq_similarity:null};motifMatches=null;highlightChains=null;constructor(e={}){this.onHighlightResidues=e.onHighlightResidues||(()=>{})}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-sequence-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Alignment Report</span>
                    <h2 class="section-title">Sequence &amp; identity</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-10">
                <div id="alignment-stats-container" class="grid grid-cols-2 sm:grid-cols-4 gap-6">
                    <div class="stat-row stat-primary">
                        <span class="stat-key">RMSD</span>
                        <span id="stat-rmsd" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Aligned length</span>
                        <span id="stat-length" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Seq identity</span>
                        <span id="stat-identity" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Seq similarity</span>
                        <span id="stat-similarity" class="stat-value">--</span>
                    </div>
                </div>

                <div class="flex flex-col gap-3">
                    <span class="eyebrow">Sequence alignment view</span>
                    <div class="section-caption">
                        Coloring shows identity across the structures loaded in this run, not true evolutionary conservation - see "True sequence-only MSA" below for a real homolog-based conservation profile.
                    </div>
                    <div id="sequence-alignment-grid-wrapper" class="overflow-x-auto rounded-md max-h-[350px]">
                        <div class="text-center py-8 text-secondary font-body-sm">
                            Run alignment to generate sequence view.
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">True sequence-only MSA (Clustal Omega)</span>
                        <button id="clustalo-run-btn" class="btn-secondary py-1.5 px-3 rounded-md font-label-md text-label-md" disabled>Run true sequence alignment</button>
                    </div>
                    <div class="section-caption">
                        Independent of Mustang's structural alignment above - a real multiple sequence alignment computed purely from each structure's own sequence, via EBI's public Clustal Omega service. Can disagree with the structural alignment for divergent sequences with similar folds.
                    </div>
                    <label class="flex flex-col gap-1">
                        <span class="font-label-sm text-label-sm text-secondary">Notify me when done - we'll POST to this URL when the job finishes (optional)</span>
                        <input id="clustalo-webhook-url" type="url" placeholder="https://..." class="max-w-[320px] bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent font-mono" />
                    </label>
                    <div id="clustalo-result-wrapper" class="overflow-x-auto rounded-md max-h-[350px]"></div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Real evolutionary conservation (NCBI BLAST)</span>
                        <div class="flex items-center gap-2">
                            <select id="conservation-structure-select" aria-label="Structure to show conservation mapping for" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[160px]"></select>
                            <button id="conservation-run-btn" class="btn-secondary py-1.5 px-3 rounded-md font-label-md text-label-md" disabled>Find real homologs</button>
                        </div>
                    </div>
                    <div class="section-caption">
                        Searches NCBI BLAST for real homologs of the selected structure's sequence, then scores real per-position conservation from their alignments (Shannon entropy) - genuinely different from the identity-based coloring above. Real BLAST searches commonly take several minutes.
                    </div>
                    <label class="flex flex-col gap-1">
                        <span class="font-label-sm text-label-sm text-secondary">Notify me when done - we'll POST to this URL when the job finishes (optional)</span>
                        <input id="conservation-webhook-url" type="url" placeholder="https://..." class="max-w-[320px] bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent font-mono" />
                    </label>
                    <div id="conservation-result-wrapper" class="overflow-x-auto rounded-md max-h-[350px]"></div>
                    <div id="conservation-logo-plotly" class="w-full h-[160px] hidden"></div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Sequence motif search</span>
                    <div class="section-caption">
                        Search for a residue motif (e.g. <code>RYY</code>, <code>G.G</code>, <code>G-X-P</code> — <code>X</code>/<code>.</code>/<code>-</code> act as single-residue wildcards) and highlight every match in the 3D viewer.
                    </div>
                    <div class="flex gap-2">
                        <input id="motif-search-input" type="text" placeholder="e.g. RYY or G.G" aria-label="Residue motif to search for" class="flex-1 bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary uppercase" />
                        <button id="motif-search-btn" class="btn-primary py-2 px-4 rounded-md font-label-md text-label-md" disabled>Search</button>
                    </div>
                    <div id="motif-results-container"></div>
                </div>

                <div class="flex flex-col gap-2 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider mb-2">Generated outputs</span>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">alignment.pdb</span>
                        <a id="download-pdb-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View PDB</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">alignment.fasta</span>
                        <a id="download-fasta-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View FASTA</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">lab_notebook.html</span>
                        <a id="download-notebook-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View Notebook</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">lab_notebook.ipynb</span>
                        <a id="download-notebook-ipynb-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download Jupyter Notebook</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">mustang_report.pdf</span>
                        <a id="download-report-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download PDF</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">citations.txt</span>
                        <a id="download-citations-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Export Citations</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">rmsd_matrix.csv</span>
                        <a id="download-rmsd-csv-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download CSV</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">rmsd_heatmap.png</span>
                        <a id="download-heatmap-png-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download PNG</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">tree.newick</span>
                        <a id="download-newick-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download Tree</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">session.pml</span>
                        <a id="download-pymol-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download PyMOL Script</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">session.cxc</span>
                        <a id="download-chimerax-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download ChimeraX Script</a>
                    </div>
                    <div class="flex items-center justify-between py-2">
                        <span class="font-body-sm text-body-sm text-primary font-mono">everything.zip</span>
                        <a id="download-zip-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download Everything</a>
                    </div>
                    <div id="report-section-checklist" class="flex flex-wrap gap-x-4 gap-y-1.5 pt-2">
                        ${yt.map(e=>`
                            <label class="flex items-center gap-1.5 font-label-sm text-label-sm text-secondary cursor-pointer">
                                <input type="checkbox" class="report-section-checkbox rounded border-border bg-surface-raised text-accent focus:ring-2 focus:ring-accent focus:ring-offset-1" value="${e.key}" checked/>
                                ${e.label}
                            </label>
                        `).join(``)}
                    </div>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),this.refreshStats(),e}setupEventListeners(){this.element.querySelectorAll(`.report-section-checkbox`).forEach(e=>{e.addEventListener(`change`,()=>this.updateReportLink())});let e=this.element.querySelector(`#motif-search-input`);this.element.querySelector(`#motif-search-btn`).addEventListener(`click`,()=>this.searchMotif(e.value)),e.addEventListener(`keydown`,t=>{t.key===`Enter`&&this.searchMotif(e.value)}),this.element.querySelector(`#clustalo-run-btn`).addEventListener(`click`,()=>this.runClustalOmegaAlignment()),this.element.querySelector(`#conservation-run-btn`).addEventListener(`click`,()=>this.runConservationSearch())}async searchMotif(e){if(!this.currentRunId||!e?.trim())return;let t=this.element.querySelector(`#motif-results-container`);t.innerHTML=`
            <div class="text-center py-4 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Searching...
            </div>
        `;try{let t=await D(this.currentRunId,e.trim());this.motifMatches=t.motif_matches||{},this.highlightChains=t.highlight_chains||{},this.renderMotifResults()}catch(e){console.error(`Motif search failed:`,e),t.innerHTML=`
                <div class="text-center py-4 text-error font-body-sm">
                    Motif search failed.
                </div>
            `}}renderMotifResults(){let e=this.element.querySelector(`#motif-results-container`),t=this.motifMatches||{},n=Object.keys(t);if(n.length===0){e.innerHTML=`
                <div class="text-center py-4 text-secondary font-body-sm">
                    No matches found for this motif pattern.
                </div>
            `;return}let r=n.reduce((e,n)=>e+t[n].length,0);e.innerHTML=``;let i=document.createElement(`div`);i.className=`text-success font-body-sm`,i.textContent=`Found ${r} matching residue position${r===1?``:`s`} across ${n.length} structure${n.length===1?``:`s`}.`,e.appendChild(i);let a=document.createElement(`table`);a.className=`w-full text-left border-collapse mt-2`;let o=document.createElement(`tbody`);n.forEach(e=>{let n=document.createElement(`tr`);n.className=`border-b border-border-subtle`;let r=document.createElement(`td`);r.className=`py-1.5 pr-4 font-body-sm font-mono text-primary`,r.textContent=e;let i=document.createElement(`td`);i.className=`py-1.5 font-body-sm font-mono text-secondary`,i.textContent=t[e].join(`, `),n.appendChild(r),n.appendChild(i),o.appendChild(n)}),a.appendChild(o),e.appendChild(a);let s=document.createElement(`button`);s.className=`btn-primary py-2 px-4 rounded-md font-label-md text-label-md mt-3`,s.textContent=`Highlight Motif in 3D Viewer`,s.addEventListener(`click`,()=>this.onHighlightResidues(this.highlightChains)),e.appendChild(s)}updateReportLink(){if(!this.element)return;let e=this.element.querySelector(`#download-report-link`);if(!this.currentRunId)return;let t=Array.from(this.element.querySelectorAll(`.report-section-checkbox`)),n=t.filter(e=>e.checked).map(e=>e.value);if(n.length===0){e.classList.add(`opacity-55`,`pointer-events-none`);return}e.classList.remove(`opacity-55`,`pointer-events-none`);let r=n.length===t.length;e.href=k(this.currentRunId,r?null:n)}updateResults(e,t){this.currentRunId=e,this.stats=t||{},this.motifMatches=null,this.highlightChains=null,this.refreshStats(),this.loadSequenceGrid(),this.element&&(this.element.querySelector(`#motif-search-input`).value=``,this.element.querySelector(`#motif-results-container`).innerHTML=``,this.element.querySelector(`#clustalo-result-wrapper`).innerHTML=``,this.element.querySelector(`#conservation-result-wrapper`).innerHTML=``,this.element.querySelector(`#conservation-structure-select`).innerHTML=``,this.element.querySelector(`#conservation-logo-plotly`).innerHTML=``,this.element.querySelector(`#conservation-logo-plotly`).classList.add(`hidden`))}refreshStats(){if(!this.element)return;let e=this.stats.rmsd==null?`--`:`${Number.parseFloat(this.stats.rmsd).toFixed(2)} Å`,t=this.stats.aligned_length==null?`--`:this.stats.aligned_length,n=this.stats.seq_identity==null?`--`:`${Number.parseFloat(this.stats.seq_identity).toFixed(1)}%`,r=this.stats.seq_similarity==null?`--`:`${Number.parseFloat(this.stats.seq_similarity).toFixed(1)}%`;this.element.querySelector(`#stat-rmsd`).innerText=e,this.element.querySelector(`#stat-length`).innerText=t,this.element.querySelector(`#stat-identity`).innerText=n,this.element.querySelector(`#stat-similarity`).innerText=r;let i=this.element.querySelector(`#download-pdb-link`),a=this.element.querySelector(`#download-fasta-link`),o=this.element.querySelector(`#download-notebook-link`),s=this.element.querySelector(`#download-notebook-ipynb-link`),c=this.element.querySelector(`#download-report-link`),l=this.element.querySelector(`#download-citations-link`),u=this.element.querySelector(`#download-rmsd-csv-link`),d=this.element.querySelector(`#download-heatmap-png-link`),f=this.element.querySelector(`#download-newick-link`),p=this.element.querySelector(`#download-pymol-link`),m=this.element.querySelector(`#download-chimerax-link`),h=this.element.querySelector(`#download-zip-link`),g=this.element.querySelector(`#motif-search-btn`);g.disabled=!this.currentRunId;let _=this.element.querySelector(`#clustalo-run-btn`);_.disabled=!this.currentRunId;let v=this.element.querySelector(`#conservation-run-btn`);v.disabled=!this.currentRunId,this.currentRunId?(i.href=O(this.currentRunId),i.classList.remove(`opacity-55`,`pointer-events-none`),a.href=be(this.currentRunId),a.classList.remove(`opacity-55`,`pointer-events-none`),o.href=we(this.currentRunId),o.classList.remove(`opacity-55`,`pointer-events-none`),s.href=Te(this.currentRunId),s.classList.remove(`opacity-55`,`pointer-events-none`),l.href=Ee(this.currentRunId),l.classList.remove(`opacity-55`,`pointer-events-none`),u.href=De(this.currentRunId),u.classList.remove(`opacity-55`,`pointer-events-none`),d.href=Oe(this.currentRunId),d.classList.remove(`opacity-55`,`pointer-events-none`),f.href=ke(this.currentRunId),f.classList.remove(`opacity-55`,`pointer-events-none`),p.href=Ae(this.currentRunId),p.classList.remove(`opacity-55`,`pointer-events-none`),m.href=je(this.currentRunId),m.classList.remove(`opacity-55`,`pointer-events-none`),h.href=A(this.currentRunId),h.classList.remove(`opacity-55`,`pointer-events-none`),this.element.querySelectorAll(`.report-section-checkbox`).forEach(e=>{e.checked=!0}),this.updateReportLink()):(i.href=`#`,i.classList.add(`opacity-55`,`pointer-events-none`),a.href=`#`,a.classList.add(`opacity-55`,`pointer-events-none`),o.href=`#`,o.classList.add(`opacity-55`,`pointer-events-none`),s.href=`#`,s.classList.add(`opacity-55`,`pointer-events-none`),l.href=`#`,l.classList.add(`opacity-55`,`pointer-events-none`),u.href=`#`,u.classList.add(`opacity-55`,`pointer-events-none`),d.href=`#`,d.classList.add(`opacity-55`,`pointer-events-none`),f.href=`#`,f.classList.add(`opacity-55`,`pointer-events-none`),p.href=`#`,p.classList.add(`opacity-55`,`pointer-events-none`),m.href=`#`,m.classList.add(`opacity-55`,`pointer-events-none`),h.href=`#`,h.classList.add(`opacity-55`,`pointer-events-none`),c.href=`#`,c.classList.add(`opacity-55`,`pointer-events-none`))}async loadSequenceGrid(){if(!this.element||!this.currentRunId)return;let e=this.element.querySelector(`#sequence-alignment-grid-wrapper`);e.innerHTML=`
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Parsing sequence alignment...
            </div>
        `;try{let{sequences:t,conservation:n}=await D(this.currentRunId);this.sequences=t,this._populateConservationStructureSelect(Object.keys(t));let r=``,i={identity:`#ff4757`,high_similarity:`#ffa502`,gap:`#2f3542`,default:`transparent`};Object.keys(t).forEach(e=>{let a=t[e],o=``;for(let e=0;e<a.length;e++){let t=a[e],r=n[e],s=i.default;t===`-`?s=i.gap:r===1?s=i.identity:r>.7&&(s=i.high_similarity),o+=`<td data-col="${e}" class="${r>.5||t===`-`?`res-val`:``} seq-res-cell text-center font-mono border border-border-subtle cursor-pointer hover:ring-1 hover:ring-accent transition-all relative" style="background-color: ${s}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;">${t}</td>`}r+=`
                    <tr class="border-b border-border-subtle">
                        <td class="sticky left-0 bg-surface-raised text-primary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">${e}</td>
                        ${o}
                    </tr>
                `});let a=``;n.forEach((e,t)=>{let n=`&nbsp;`;e===1?n=`*`:e>.7?n=`:`:e>.5&&(n=`.`),a+=`<td data-col="${t}" class="text-center font-mono font-bold text-secondary" style="min-width: 22px; height: 20px;">${n}</td>`}),r+=`
                <tr class="bg-surface">
                    <td class="sticky left-0 bg-surface text-secondary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">Consensus</td>
                    ${a}
                </tr>
            `,e.innerHTML=`
                <table class="text-left border-collapse">
                    <tbody>
                        ${r}
                    </tbody>
                </table>
            `,e.querySelectorAll(`.seq-res-cell`).forEach(e=>{e.addEventListener(`click`,()=>{let t=parseInt(e.dataset.col,10);if(Number.isNaN(t))return;this.highlightColumn(t);let n=this.mapColumnToResidues(t);Object.keys(n).length>0&&this.onHighlightResidues(n)})})}catch(t){console.error(`Failed to render sequence alignment viewer:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to parse alignment FASTA data.
                </div>
            `}}mapColumnToResidues(e){if(!this.sequences)return{};let t={};return Object.keys(this.sequences).forEach((n,r)=>{let i=String.fromCharCode(65+r),a=this.sequences[n];if(e>=0&&e<a.length&&a[e]!==`-`){let n=0;for(let t=0;t<=e;t++)a[t]!==`-`&&n++;t[i]=[n]}}),t}highlightColumn(e){if(!this.element)return;this.element.querySelectorAll(`.seq-res-cell`).forEach(t=>{let n=parseInt(t.dataset.col,10)===e;t.classList.toggle(`ring-2`,n),t.classList.toggle(`ring-amber-400`,n),t.classList.toggle(`z-10`,n)});let t=this.element.querySelector(`.seq-res-cell[data-col="${e}"]`);t&&t.scrollIntoView?.({behavior:`smooth`,block:`nearest`,inline:`center`})}highlightColumnByResidue(e,t){if(!this.sequences||!t)return;let n=Object.keys(this.sequences),r=n[Math.max(0,(e||`A`).toUpperCase().charCodeAt(0)-65)]||n[0],i=this.sequences[r];if(!i)return;let a=0;for(let e=0;e<i.length;e++)if(i[e]!==`-`&&(a++,a===Number(t))){this.highlightColumn(e);break}}static _parseFasta(e){let t={},n=null;return(e||``).split(/\r?\n/).forEach(e=>{e.startsWith(`>`)?(n=e.slice(1).trim(),t[n]=``):n&&(t[n]+=e.trim())}),t}async runClustalOmegaAlignment(){if(!this.currentRunId)return;let e=this.element.querySelector(`#clustalo-run-btn`),t=this.element.querySelector(`#clustalo-result-wrapper`);e.disabled=!0,t.innerHTML=`
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Submitting sequences to EBI Clustal Omega…
            </div>
        `;try{let e=await D(this.currentRunId),n=Object.fromEntries(Object.entries(e.sequences||{}).map(([e,t])=>[e,t.replaceAll(`-`,``)]));if(Object.keys(n).length<2){t.innerHTML=`<div class="text-center py-8 text-secondary font-body-sm">Need at least 2 structures for a sequence alignment.</div>`;return}let r=this.element.querySelector(`#clustalo-webhook-url`)?.value.trim(),i=r?await x(n,r):await x(n);t.innerHTML=`
                <div class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Waiting on EBI Clustal Omega (this can take a couple of minutes)…
                </div>
            `;let a=await b(i.job_id,{intervalMs:5e3});if(a.status===`failed`){t.innerHTML=`<div class="text-center py-8 text-error font-body-sm">Clustal Omega alignment failed: ${z(a.error||`unknown error`)}</div>`;return}this.renderClustalOmegaResult(a.aligned_fasta)}catch(e){console.error(`Clustal Omega alignment failed:`,e),t.innerHTML=`<div class="text-center py-8 text-error font-body-sm">Failed to run sequence-only alignment.</div>`}finally{e.disabled=!this.currentRunId}}renderClustalOmegaResult(t){let n=this.element.querySelector(`#clustalo-result-wrapper`),r=e._parseFasta(t),i=Object.keys(r);if(i.length===0){n.innerHTML=`<div class="text-center py-8 text-error font-body-sm">Could not parse the returned alignment.</div>`;return}let a=Math.max(...i.map(e=>r[e].length)),o=``;i.forEach(e=>{let t=r[e],n=``;for(let e=0;e<a;e++){let a=t[e]||`-`,o=a!==`-`&&i.every(t=>(r[t][e]||`-`)===a),s;s=o?`#ff4757`:a===`-`?`#2f3542`:`transparent`,n+=`<td class="text-center font-mono border border-border-subtle" style="background-color: ${s}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;">${z(a)}</td>`}o+=`
                <tr class="border-b border-border-subtle">
                    <td class="sticky left-0 bg-surface-raised text-primary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">${z(e)}</td>
                    ${n}
                </tr>
            `}),n.innerHTML=`
            <table class="text-left border-collapse">
                <tbody>
                    ${o}
                </tbody>
            </table>
        `}_populateConservationStructureSelect(e){let t=this.element.querySelector(`#conservation-structure-select`),n=t.value;t.innerHTML=``,e.forEach(e=>{let n=document.createElement(`option`);n.value=e,n.textContent=e,t.appendChild(n)}),e.includes(n)&&(t.value=n)}async runConservationSearch(){if(!this.currentRunId)return;let e=this.element.querySelector(`#conservation-structure-select`).value,t=this.element.querySelector(`#conservation-run-btn`),n=this.element.querySelector(`#conservation-result-wrapper`);if(!e){n.innerHTML=`<div class="text-center py-8 text-secondary font-body-sm">No structure available to search.</div>`;return}t.disabled=!0,n.innerHTML=`
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Submitting ${z(e)}'s sequence to NCBI BLAST…
            </div>
        `;try{let t=((await D(this.currentRunId)).sequences?.[e]||``).replaceAll(`-`,``);if(t.length<10){n.innerHTML=`<div class="text-center py-8 text-secondary font-body-sm">Sequence too short for a BLAST search.</div>`;return}let r=this.element.querySelector(`#conservation-webhook-url`)?.value.trim(),i=r?await S(t,r):await S(t);n.innerHTML=`
                <div class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Waiting on NCBI BLAST (real searches commonly take several minutes)…
                </div>
            `;let a=await b(i.job_id,{intervalMs:15e3});if(a.status===`failed`){n.innerHTML=`<div class="text-center py-8 text-error font-body-sm">BLAST conservation search failed: ${z(a.error||`unknown error`)}</div>`;return}this.renderConservationResult(e,a.conservation_profile,a.num_hits)}catch(e){console.error(`Conservation search failed:`,e),n.innerHTML=`<div class="text-center py-8 text-error font-body-sm">Failed to run conservation search.</div>`}finally{t.disabled=!this.currentRunId}}renderConservationResult(e,t,n){let r=this.element.querySelector(`#conservation-result-wrapper`);if(!t||t.length===0){r.innerHTML=`<div class="text-center py-8 text-error font-body-sm">No conservation profile returned.</div>`;return}let i=``;t.forEach(e=>{let t=e.conservation,n=e.most_common||`-`,r=t==null?`#2f3542`:`rgba(255, 71, 87, ${t.toFixed(2)})`,a=t==null?`No homolog coverage at this position`:`Conservation: ${(t*100).toFixed(1)}% (${e.num_homologs} homologs)`;i+=`<td class="text-center font-mono border border-border-subtle" style="background-color: ${r}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;" title="${z(a)}">${z(n)}</td>`}),r.innerHTML=`
            <div class="font-body-sm text-[11px] text-secondary pb-2">${n} real homolog(s) found via NCBI BLAST</div>
            <table class="text-left border-collapse">
                <tbody>
                    <tr class="border-b border-border-subtle">
                        <td class="sticky left-0 bg-surface-raised text-primary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">${z(e)}</td>
                        ${i}
                    </tr>
                </tbody>
            </table>
        `,this.renderConservationLogo(t)}renderConservationLogo(e){let t=this.element.querySelector(`#conservation-logo-plotly`);if(!t||typeof Plotly>`u`)return;let n=e.map(e=>e.position),r=new Set;if(e.forEach(e=>Object.keys(e.residue_counts||{}).forEach(e=>r.add(e))),r.size===0){t.classList.add(`hidden`),t.innerHTML=``;return}let i=Array.from(r).sort((e,t)=>e.localeCompare(t)).map(t=>{let r=e.map(e=>{let n=e.num_homologs||0;return n>0?(e.residue_counts?.[t]||0)/n:0}),i=r.map(e=>e>.08?t:``);return{x:n,y:r,name:t,type:`bar`,marker:{color:St(t)},text:i,textposition:`inside`,insidetextfont:{color:`#100E0B`,size:10},hovertemplate:`${t}: %{y:.0%}<extra></extra>`}}),a={barmode:`stack`,height:160,margin:{l:40,r:10,t:10,b:30},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`},showlegend:!1,xaxis:{title:`Position`,tickmode:`linear`,dtick:Math.max(1,Math.round(n.length/30))},yaxis:{title:`Frequency`,range:[0,1],tickformat:`.0%`}};t.classList.remove(`hidden`),Plotly.newPlot(t,i,a,{responsive:!0,displayModeBar:!1})}},Y=`http://www.w3.org/2000/svg`,wt={check_circle:[{tag:`circle`,attrs:{cx:12,cy:12,r:9}},{tag:`polyline`,attrs:{points:`8,12.5 10.5,15 16,9`}}],warning:[{tag:`polygon`,attrs:{points:`12,3 22,20 2,20`}},{tag:`line`,attrs:{x1:12,y1:9,x2:12,y2:14}},{tag:`circle`,attrs:{cx:12,cy:17.3,r:.6,fill:`currentColor`,stroke:`none`}}],info:[{tag:`circle`,attrs:{cx:12,cy:12,r:9}},{tag:`line`,attrs:{x1:12,y1:11,x2:12,y2:16}},{tag:`circle`,attrs:{cx:12,cy:7.5,r:.6,fill:`currentColor`,stroke:`none`}}],military_tech:[{tag:`circle`,attrs:{cx:12,cy:9,r:6}},{tag:`line`,attrs:{x1:9.8,y1:14.5,x2:7.5,y2:21}},{tag:`line`,attrs:{x1:14.2,y1:14.5,x2:16.5,y2:21}}],compare_arrows:[{tag:`line`,attrs:{x1:4,y1:8,x2:18,y2:8}},{tag:`polyline`,attrs:{points:`14,4 18,8 14,12`}},{tag:`line`,attrs:{x1:20,y1:16,x2:6,y2:16}},{tag:`polyline`,attrs:{points:`10,12 6,16 10,20`}}],flag:[{tag:`line`,attrs:{x1:5,y1:3,x2:5,y2:21}},{tag:`path`,attrs:{d:`M5,4 L19,4 L15,8 L19,12 L5,12 Z`}}],medication:[{tag:`rect`,attrs:{x:3,y:8,width:18,height:8,rx:4}},{tag:`line`,attrs:{x1:12,y1:8,x2:12,y2:16}}],biotech:[{tag:`circle`,attrs:{cx:9,cy:12,r:5}},{tag:`circle`,attrs:{cx:15,cy:12,r:5}}],science:[{tag:`circle`,attrs:{cx:7,cy:12,r:4}},{tag:`circle`,attrs:{cx:17,cy:12,r:4}}],group_work:[{tag:`circle`,attrs:{cx:9,cy:9,r:5}},{tag:`circle`,attrs:{cx:15,cy:9,r:5}},{tag:`circle`,attrs:{cx:12,cy:15,r:5}}],verified:[{tag:`path`,attrs:{d:`M12,3 L19,6 L19,12 L12,21 L5,12 L5,6 Z`}},{tag:`polyline`,attrs:{points:`8.5,12 11,14.5 15.5,9`}}],star:[{tag:`polygon`,attrs:{points:`12,3 14.7,9.5 21.5,9.9 16,14.3 17.8,21 12,17.1 6.2,21 8,14.3 2.5,9.9 9.3,9.5`}}],trending_down:[{tag:`polyline`,attrs:{points:`4,7 10,13 14,9 20,17`}},{tag:`polyline`,attrs:{points:`20,10 20,17 13,17`}}],diamond:[{tag:`polygon`,attrs:{points:`12,3 21,12 12,21 3,12`}}]};function Tt(e){let t=wt[e];if(!t)return null;let n=document.createElementNS(Y,`svg`);return n.setAttribute(`viewBox`,`0 0 24 24`),n.setAttribute(`width`,`16`),n.setAttribute(`height`,`16`),n.setAttribute(`fill`,`none`),n.setAttribute(`stroke`,`currentColor`),n.setAttribute(`stroke-width`,`1.8`),n.setAttribute(`stroke-linecap`,`round`),n.setAttribute(`stroke-linejoin`,`round`),t.forEach(({tag:e,attrs:t})=>{let r=document.createElementNS(Y,e);Object.entries(t).forEach(([e,t])=>r.setAttribute(e,t)),n.appendChild(r)}),n}function Et(e,t){String(t??``).split(/\*\*(.+?)\*\*/g).forEach((t,n)=>{if(t!==``)if(n%2==1){let n=document.createElement(`strong`);n.textContent=t,e.appendChild(n)}else e.appendChild(document.createTextNode(t))})}var Dt=/^\[\[([a-z0-9_]+)\]\]\s*/;function Ot(e){let t=Dt.exec(String(e??``));return t?{icon:t[1],text:e.slice(t[0].length)}:{icon:null,text:e??``}}function X(e,t,n=!1){return t?`
        <details ${n?`open`:``} class="group border-b border-border-subtle">
            <summary class="flex items-center gap-1.5 py-2 cursor-pointer select-none font-label-sm text-label-sm text-secondary uppercase tracking-wider list-none [&::-webkit-details-marker]:hidden">
                <span class="material-symbols-outlined text-[16px] transition-transform group-open:rotate-90">chevron_right</span>
                ${z(e)}
            </summary>
            <div class="pb-2 pl-1">${t}</div>
        </details>
    `:``}var Z=[{key:`quality`,label:`Quality`},{key:`rmsf`,label:`RMSF`},{key:`rmsd`,label:`RMSD Matrix`},{key:`phylo`,label:`Phylogeny`},{key:`insights`,label:`Insights`},{key:`annotations`,label:`Annotations`}],Q=new Set([`Modified residue`,`Disulfide bond`,`Glycosylation`,`Lipidation`,`Cross-link`]),kt=class{element=null;currentRunId=null;heatmapFig=null;treeFig=null;ramachandranStats=null;secondaryStructureStats=null;tmScoreMatrix=null;rmsfValues=[];insights=[];qualityMetrics=null;activeSubTab=`quality`;viewMode=`simple`;structures=[];annotationsCache={};annotationsLoadedForKey=null;annotationsLoading=!1;constructor(e={}){this.onHighlightResidues=e.onHighlightResidues||(()=>{}),this.onGoToWorkspace=e.onGoToWorkspace||(()=>{})}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-analytics-container`,e.innerHTML=`
            <header class="section-head flex flex-wrap justify-between items-center gap-4">
                <div>
                    <span class="eyebrow">Fig. — Structural Analytics</span>
                    <h2 class="section-title">Quality, fluctuation &amp; phylogeny</h2>
                </div>
                <div id="analytics-viewmode-toggle" class="flex items-center gap-1 bg-surface-raised border border-border p-1 rounded-md shrink-0">
                    <button id="viewmode-btn-simple" data-mode="simple" class="px-3 py-1 rounded-md font-label-sm text-label-sm transition-colors ${this.viewMode===`simple`?`bg-surface text-primary shadow-xs font-semibold`:`text-secondary hover:text-primary`}" title="Simple Overview: Layman summaries, key takeaways & plain-English badges">Simple Overview</button>
                    <button id="viewmode-btn-deep" data-mode="deep" class="px-3 py-1 rounded-md font-label-sm text-label-sm transition-colors ${this.viewMode===`deep`?`bg-surface text-primary shadow-xs font-semibold`:`text-secondary hover:text-primary`}" title="Deep Dive: Full distance matrices, B-factors, Ramachandran details & UPGMA trees">Deep Dive</button>
                </div>
            </header>
            <div class="section-body flex flex-col gap-6">
                <!-- Sub-tab strip -->
                <div id="analytics-subtab-strip" role="tablist" class="flex flex-wrap gap-1 border border-border rounded-md p-1 shrink-0">
                    ${Z.map(e=>`
                        <button data-subtab="${e.key}" id="analytics-subtab-tab-${e.key}" role="tab" aria-controls="analytics-subtab-panel-${e.key}" class="analytics-subtab-btn flex-1 min-w-[84px] py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors" aria-selected="${e.key===`quality`}" tabindex="${e.key===`quality`?`0`:`-1`}">${e.label}</button>
                    `).join(``)}
                </div>

                <!-- Ramachandran / Quality Report -->
                <div data-panel="quality" class="flex flex-col gap-4 shrink-0">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        <div class="stat-row stat-primary">
                            <span class="stat-key">${J(`ramachandran`,`Ramachandran score`)}</span>
                            <span id="ramachandran-score" class="stat-value">--</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-key">Outlier residues</span>
                            <span id="ramachandran-outliers" class="stat-value">--</span>
                        </div>
                    </div>
                    <div id="ramachandran-outliers-list-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Top outliers</span>
                        <div id="ramachandran-outliers-list" class="flex flex-wrap gap-1.5">
                            <!-- Outlier chips -->
                        </div>
                    </div>
                    <div id="quality-metrics-table-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">${J(`tmScore`,`Alignment quality (TM-score / GDT-TS)`)}</span>
                        <table class="w-full font-body-sm text-body-sm">
                            <thead>
                                <tr class="text-secondary text-left border-b border-border-subtle">
                                    <th class="font-normal py-1">Structure</th>
                                    <th class="font-normal py-1">TM-score</th>
                                    <th class="font-normal py-1">GDT-TS</th>
                                </tr>
                            </thead>
                            <tbody id="quality-metrics-table-body"></tbody>
                        </table>
                    </div>
                    <div id="secondary-structure-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Secondary structure (backbone-torsion approximation, not DSSP)</span>
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div class="stat-row"><span class="stat-key">Helix</span><span id="ss-helix-percent" class="stat-value">--</span></div>
                            <div class="stat-row"><span class="stat-key">Sheet</span><span id="ss-sheet-percent" class="stat-value">--</span></div>
                            <div class="stat-row"><span class="stat-key">Coil</span><span id="ss-coil-percent" class="stat-value">--</span></div>
                        </div>
                    </div>
                    <div id="pairwise-tm-score-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">${J(`tmScore`,`Pairwise TM-score`)}</span>
                        <table class="w-full font-body-sm text-body-sm">
                            <thead>
                                <tr class="text-secondary text-left border-b border-border-subtle">
                                    <th class="font-normal py-1">Pair</th>
                                    <th class="font-normal py-1">TM-score</th>
                                </tr>
                            </thead>
                            <tbody id="pairwise-tm-score-table-body"></tbody>
                        </table>
                    </div>
                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Predicted aligned error (AlphaFold structures only - AlphaFold's own confidence in each residue pair's relative position, lower is better)</span>
                        <div class="flex gap-2 items-center">
                            <select id="pae-pdb-select" aria-label="Structure for PAE view" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="pae-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="pae-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select an AlphaFold structure and load to view its per-residue-pair confidence.
                            </div>
                        </div>
                    </div>
                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Predicted flexibility (Gaussian Network Model - a computational prediction from geometry alone, not a measurement)</span>
                        <div class="flex gap-2 items-center">
                            <select id="flexibility-pdb-select" aria-label="Structure for predicted flexibility view" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="flexibility-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="flexibility-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select a structure and load to view its predicted per-residue flexibility.
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Residue Fluctuation (Plotly Line Chart) -->
                <div data-panel="rmsf" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="rmsf-plotly-chart" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive RMSF chart.
                        </div>
                    </div>
                </div>

                <!-- Pairwise RMSD Matrix (Plotly Heatmap) -->
                <div data-panel="rmsd" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px] flex flex-col gap-4">
                    <div id="rmsd-plotly-heatmap" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive heatmap.
                        </div>
                    </div>

                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Contact map (CA-CA, 8&Aring; default)</span>
                        <div class="flex gap-2 items-center">
                            <select id="contact-map-pdb-select" aria-label="Structure for contact map" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="contact-map-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="contact-map-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select a structure and load to view its contact map.
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Difference-distance matrix</span>
                        <div class="flex gap-2 items-center">
                            <select id="diff-distance-pdb-a-select" aria-label="First structure to compare distances between" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <select id="diff-distance-pdb-b-select" aria-label="Second structure to compare distances between" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="diff-distance-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="diff-distance-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select two structures and load to view their difference-distance matrix.
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Phylogenetic Tree (Plotly Dendrogram) -->
                <div data-panel="phylo" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="phylo-plotly-tree" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive dendrogram.
                        </div>
                    </div>
                </div>

                <!-- Automated Insights (plain-language summary bullets) -->
                <div data-panel="insights" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px] flex flex-col gap-4">
                    <ul id="analytics-insights-list" class="flex flex-col gap-2"></ul>
                    <div id="analytics-insights-empty" class="flex items-center justify-center h-full text-secondary font-body-sm">
                        Run alignment to display automated insights.
                    </div>

                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Describe the difference between two structures</span>
                        <div class="flex gap-2 items-center">
                            <select id="diff-narrative-pdb-a-select" aria-label="First structure for narrative diff" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <select id="diff-narrative-pdb-b-select" aria-label="Second structure for narrative diff" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="diff-narrative-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Describe</button>
                        </div>
                        <p id="diff-narrative-text" class="font-body-sm text-body-sm text-secondary">
                            Select two structures above to get a plain-English summary of how they differ.
                        </p>
                    </div>
                </div>

                <!-- Functional Annotation (InterPro domains / GO terms / Reactome pathways) -->
                <div data-panel="annotations" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px] flex flex-col gap-4">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Functional annotation</span>
                        <select id="annotations-structure-select" aria-label="Structure to show functional annotation for" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[160px]"></select>
                    </div>
                    <div id="annotations-content" class="flex flex-col gap-3">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display functional annotation.
                        </div>
                    </div>
                    <div id="annotations-shared-section" class="hidden flex-col gap-3 pt-3 border-t border-border-subtle">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Shared across all structures</span>
                        <div id="annotations-shared-content"></div>
                    </div>

                    <div class="flex flex-col gap-2 pt-3 border-t border-border-subtle">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Map a mutation</span>
                        <span class="font-body-sm text-body-sm text-secondary">Maps the selected structure's residue to UniProt, then checks ClinVar for a known clinical record and AlphaMissense for a predicted pathogenicity score</span>
                        <div class="flex items-end gap-2">
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary">Residue #</span>
                                <input id="mutation-resi-input" type="number" min="1" class="w-24 bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono" />
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary">Mutant residue</span>
                                <input id="mutation-mutant-input" type="text" maxlength="1" class="w-16 bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono uppercase" />
                            </label>
                            <button id="mutation-map-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Map</button>
                            <button id="mutation-ddg-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Predict stability impact</button>
                        </div>
                        <div id="mutation-impact-result" class="font-body-sm text-body-sm text-secondary flex flex-col gap-1"></div>
                        <div id="mutation-ddg-result" class="font-body-sm text-body-sm text-secondary flex flex-col gap-1"></div>
                    </div>
                </div>
            </div>
        `,this.element=e,this.setupViewModeToggle(),this.setupSubTabs(),this.setupAnnotationsPicker(),this.setupContactMapControls(),this.setupPaeControls(),this.setupFlexibilityControls(),this.setupDiffNarrativeControls(),this.renderVisuals(),e}setupViewModeToggle(){let e=this.element.querySelector(`#viewmode-btn-simple`),t=this.element.querySelector(`#viewmode-btn-deep`);e?.addEventListener(`click`,()=>this.setViewMode(`simple`)),t?.addEventListener(`click`,()=>this.setViewMode(`deep`))}_updateViewModeButtonUI(e,t){e&&(e.className=`px-3 py-1 rounded-md font-label-sm text-label-sm transition-colors ${t?`bg-surface text-primary shadow-xs font-semibold`:`text-secondary hover:text-primary`}`)}setViewMode(e){this.viewMode=e,this._updateViewModeButtonUI(this.element?.querySelector(`#viewmode-btn-simple`),e===`simple`),this._updateViewModeButtonUI(this.element?.querySelector(`#viewmode-btn-deep`),e===`deep`),e===`simple`&&this.activeSubTab===`rmsd`&&this.switchSubTab(`quality`)}setupDiffNarrativeControls(){this.element.querySelector(`#diff-narrative-load-btn`).addEventListener(`click`,()=>this.describeStructureDiff()),[`#diff-narrative-pdb-a-select`,`#diff-narrative-pdb-b-select`].forEach(e=>{this.element.querySelector(e).addEventListener(`change`,()=>{let e=this.element.querySelector(`#diff-narrative-pdb-a-select`).value,t=this.element.querySelector(`#diff-narrative-pdb-b-select`).value;this.element.querySelector(`#diff-narrative-load-btn`).disabled=!e||!t})})}setupContactMapControls(){this.element.querySelector(`#contact-map-load-btn`).addEventListener(`click`,()=>{this.loadContactMap()}),this.element.querySelector(`#diff-distance-load-btn`).addEventListener(`click`,()=>{this.loadDifferenceDistance()}),[`#contact-map-pdb-select`,`#diff-distance-pdb-a-select`,`#diff-distance-pdb-b-select`].forEach(e=>{this.element.querySelector(e).addEventListener(`change`,()=>this.updateContactMapButtonStates())})}setupPaeControls(){this.element.querySelector(`#pae-load-btn`).addEventListener(`click`,()=>{this.loadPae()}),this.element.querySelector(`#pae-pdb-select`).addEventListener(`change`,e=>{this.element.querySelector(`#pae-load-btn`).disabled=!e.target.value})}setupFlexibilityControls(){this.element.querySelector(`#flexibility-load-btn`).addEventListener(`click`,()=>{this.loadFlexibility()}),this.element.querySelector(`#flexibility-pdb-select`).addEventListener(`change`,e=>{this.element.querySelector(`#flexibility-load-btn`).disabled=!e.target.value})}setupSubTabs(){this.element.querySelectorAll(`.analytics-subtab-btn`).forEach(e=>{e.addEventListener(`click`,()=>this.switchSubTab(e.dataset.subtab))}),Z.forEach(e=>{let t=this.element.querySelector(`[data-panel="${e.key}"]`);t&&(t.id=`analytics-subtab-panel-${e.key}`,t.setAttribute(`role`,`tabpanel`),t.setAttribute(`aria-labelledby`,`analytics-subtab-tab-${e.key}`))}),N(this.element.querySelector(`#analytics-subtab-strip`),`.analytics-subtab-btn`,e=>this.switchSubTab(e.dataset.subtab)),this.updateSubTabView()}setupAnnotationsPicker(){this.element.querySelector(`#annotations-structure-select`).addEventListener(`change`,()=>this.renderAnnotationsPanel()),this.element.querySelector(`#mutation-map-btn`).addEventListener(`click`,()=>{this.loadMutationImpact()}),this.element.querySelector(`#mutation-ddg-btn`).addEventListener(`click`,()=>{this.loadDdgStability()})}switchSubTab(e){this.activeSubTab=e,this.updateSubTabView();let t={rmsf:`rmsf-plotly-chart`,rmsd:`rmsd-plotly-heatmap`,phylo:`phylo-plotly-tree`}[e];if(t&&typeof Plotly<`u`){let e=this.element.querySelector(`#${t}`);e?.data&&Plotly.Plots.resize(e)}e===`annotations`&&this.structures.length>0&&this.annotationsLoadedForKey!==this._structuresKey()&&this.loadAllAnnotations()}updateSubTabView(){this.element.querySelectorAll(`.analytics-subtab-btn`).forEach(e=>{let t=e.dataset.subtab===this.activeSubTab;e.className=`analytics-subtab-btn flex-1 min-w-[84px] py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors ${t?`bg-accent-muted text-accent`:`text-secondary hover:text-primary`}`,e.setAttribute(`aria-selected`,String(t)),e.tabIndex=t?0:-1}),this.element.querySelectorAll(`[data-panel]`).forEach(e=>{e.classList.toggle(`hidden`,e.dataset.panel!==this.activeSubTab)})}_structuresKey(){return this.structures.map(e=>e.pdbId).join(`|`)}updateResults(e,t,n,r,i,a,o){let s=o||[];s.map(e=>e.pdbId).join(`|`)!==this._structuresKey()&&(this.annotationsCache={},this.annotationsLoadedForKey=null),this.currentRunId=e,this.heatmapFig=t?.heatmap??null,this.treeFig=t?.tree??null,this.ramachandranStats=n?.ramachandran??null,this.secondaryStructureStats=n?.secondaryStructure??null,this.tmScoreMatrix=n?.tmScoreMatrix??null,this.rmsfValues=r||[],this.insights=i||[],this.qualityMetrics=a||null,this.structures=s,this.renderVisuals()}async loadAllAnnotations(){if(!this.element||this.structures.length===0)return;this.annotationsLoading=!0,this.renderAnnotationsPanel();let e=this._structuresKey(),t=await Promise.all(this.structures.map(async({pdbId:e,chain:t})=>{try{return[e,(await j(e,t)).annotation]}catch(t){return console.error(`Failed to load annotation for ${e}:`,t),[e,null]}}));e===this._structuresKey()&&(this.annotationsCache=Object.fromEntries(t),this.annotationsLoadedForKey=e,this.annotationsLoading=!1,this.populateAnnotationsPicker(),this.renderAnnotationsPanel())}populateAnnotationsPicker(){let e=this.element.querySelector(`#annotations-structure-select`),t=e.value;e.innerHTML=``,this.structures.forEach(({pdbId:t})=>{let n=document.createElement(`option`);n.value=t,n.textContent=t,e.appendChild(n)}),this.structures.some(e=>e.pdbId===t)&&(e.value=t)}renderAnnotationsPanel(){if(!this.element)return;let e=this.element.querySelector(`#annotations-content`),t=this.element.querySelector(`#annotations-shared-section`),n=this.element.querySelector(`#annotations-shared-content`);if(this.structures.length===0){e.innerHTML=``;let n=document.createElement(`div`);n.className=`flex flex-col items-center justify-center gap-2 h-full text-secondary font-body-sm`;let r=document.createElement(`span`);r.textContent=`Add a structure in the Workspace tab to display functional annotation.`,n.appendChild(r);let i=document.createElement(`button`);i.type=`button`,i.className=`font-label-sm text-label-sm text-accent hover:underline`,i.textContent=`Go to Workspace`,i.addEventListener(`click`,()=>this.onGoToWorkspace()),n.appendChild(i),e.appendChild(n),t.classList.add(`hidden`),t.classList.remove(`flex`);return}if(this.annotationsLoading){e.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm"><span class="animate-spin material-symbols-outlined text-[18px]">sync</span> Resolving functional annotation…</div>`,t.classList.add(`hidden`),t.classList.remove(`flex`);return}let r=this.element.querySelector(`#annotations-structure-select`).value||this.structures[0]?.pdbId,i=this.annotationsCache[r];if(!i)e.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Switch to this tab to load functional annotation.</div>`;else if(!i.accession){e.innerHTML=`
                <div class="font-body-sm text-secondary py-4">No UniProt accession could be resolved for ${r} - no functional annotation available that way.</div>
                <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                    <span class="font-body-sm text-body-sm text-secondary">Annotate directly from this structure's own sequence instead (InterProScan5) - the one path that works without a UniProt accession.</span>
                    <div class="flex items-center gap-3">
                        <button id="interproscan-annotate-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Annotate from sequence</button>
                        <span id="interproscan-feedback" class="font-body-sm text-[11px] text-secondary"></span>
                    </div>
                    <div id="interproscan-result" class="flex flex-col gap-3"></div>
                </div>
            `;let t=e.querySelector(`#interproscan-annotate-btn`);t&&t.addEventListener(`click`,()=>{this.loadInterproscanAnnotation(r)})}else if(!i.domains?.length&&!i.go_terms?.length&&!i.reactome_pathways?.length&&!i.kegg_pathways?.length&&!i.uniprot_features?.length&&!i.catalytic_sites?.length&&!i.function_summary&&!i.tissue_expression&&!i.orthologs&&!i.disprot_regions?.length&&!i.intact_partners?.length&&!i.rhea_reactions?.length&&!i.tractability)e.innerHTML=`<div class="font-body-sm text-secondary py-4">Resolved to UniProt ${i.accession}, but no curated domains, GO terms, pathways, or sequence features were found.</div>`;else{let t=i.uniprot_features||[],n=t.filter(e=>Q.has(e.type)),r=t.filter(e=>!Q.has(e.type)),a=X(`Function summary`,ct(i.function_summary),!0),o=X(`Domains / families`,V(i.domains,``),!0),s=X(`GO terms`,W(i.go_terms,``),!1),c=X(`PTM sites`,H(n,``,`ptm-highlight-btn`),!1),l=X(`UniProt features`,H(r,``,`feature-highlight-btn`),!1),u=X(`Catalytic sites (M-CSA)`,at(i.catalytic_sites,``),!1),d=X(`Tissue expression (Human Protein Atlas)`,this.renderTissueExpression(i.tissue_expression),!1),f=X(`Orthologs (OrthoDB)`,this.renderOrthologs(i.orthologs),!1),p=X(`Curated disordered regions (DisProt)`,this.renderDisprotRegions(i.disprot_regions),!1),m=X(`Curated interaction partners (IntAct)`,this.renderIntactPartners(i.intact_partners),!1),h=X(`Druggability (Open Targets)`,this.renderTractability(i.tractability),!1),g=X(`Reactome pathways`,this.renderReactomePathways(i.reactome_pathways),!1),_=X(`KEGG pathways`,this.renderKeggPathways(i.kegg_pathways),!1),v=X(`Catalyzed reactions (Rhea)`,this.renderRheaReactions(i.rhea_reactions),!1);e.innerHTML=`
                <div class="font-body-sm text-secondary pb-1">Resolved to UniProt <span class="font-mono text-primary">${i.accession}</span></div>
                ${a}
                ${o}
                ${s}
                ${c}
                ${l}
                ${u}
                ${d}
                ${f}
                ${p}
                ${m}
                ${h}
                ${g}
                ${_}
                ${v}
            `,e.querySelectorAll(`.domain-highlight-btn`).forEach(e=>{let t=i.domains[Number(e.dataset.domainIndex)];t?.highlight_chains&&e.addEventListener(`click`,()=>this.onHighlightResidues(t.highlight_chains))}),e.querySelectorAll(`.ptm-highlight-btn`).forEach(e=>{let t=n[Number(e.dataset.featureIndex)];t?.highlight_chains&&e.addEventListener(`click`,()=>this.onHighlightResidues(t.highlight_chains))}),e.querySelectorAll(`.feature-highlight-btn`).forEach(e=>{let t=r[Number(e.dataset.featureIndex)];t?.highlight_chains&&e.addEventListener(`click`,()=>this.onHighlightResidues(t.highlight_chains))}),e.querySelectorAll(`.feature-show-all-btn`).forEach(t=>{t.addEventListener(`click`,()=>{let n=t.dataset.featureOverflowGroup;e.querySelectorAll(`.feature-overflow-row[data-feature-overflow-group="${n}"]`).forEach(e=>e.classList.remove(`hidden`)),t.remove()})})}this.renderSharedAnnotations(t,n)}async loadMutationImpact(){let e=this.element.querySelector(`#mutation-impact-result`),t=this.element.querySelector(`#annotations-structure-select`).value||this.structures[0]?.pdbId,n=this.structures.find(e=>e.pdbId===t)?.chain,r=Number.parseInt(this.element.querySelector(`#mutation-resi-input`).value,10),i=this.element.querySelector(`#mutation-mutant-input`).value.trim();if(!t||!n){e.textContent=`Select a structure with a resolved chain first.`;return}if(!Number.isInteger(r)||!i){e.textContent=`Enter a residue number and a mutant residue.`;return}e.textContent=`Mapping mutation…`;try{let e=await Me(t,n,r,i);this.renderMutationImpact(e)}catch(t){console.error(`Failed to map mutation:`,t),e.textContent=`Failed to map this mutation.`}}renderMutationImpact(e){let t=this.element.querySelector(`#mutation-impact-result`);t.innerHTML=``;let n=document.createElement(`div`);n.className=`text-primary`,n.textContent=`UniProt ${e.accession??`--`} position ${e.uniprot_position??`--`}: ${e.wildtype_residue??`?`} → ${e.mutant_residue}`,t.appendChild(n);let r=document.createElement(`div`);e.clinvar?r.textContent=`ClinVar: ${e.clinvar.clinical_significance} (${e.clinvar.review_status})`:r.textContent=`No matching ClinVar record found.`,t.appendChild(r);let i=document.createElement(`div`);e.alphamissense?i.textContent=`AlphaMissense: ${e.alphamissense.pathogenicity.toFixed(3)} (${e.alphamissense.class})`:i.textContent=`No AlphaMissense score available for this substitution.`,t.appendChild(i);let a=document.createElement(`div`);if(e.gnomad&&(e.gnomad.af_exome!=null||e.gnomad.af_genome!=null)){let t=[];e.gnomad.af_exome!=null&&t.push(`exome ${(e.gnomad.af_exome*100).toPrecision(3)}%`),e.gnomad.af_genome!=null&&t.push(`genome ${(e.gnomad.af_genome*100).toPrecision(3)}%`),a.textContent=`gnomAD population frequency: ${t.join(`, `)}`}else a.textContent=`No gnomAD population frequency data found for this substitution.`;t.appendChild(a);let o=document.createElement(`div`);if(e.gnomad?.revel_score==null?o.textContent=`No REVEL score available for this substitution.`:o.textContent=`REVEL pathogenicity: ${e.gnomad.revel_score.toFixed(3)}`,t.appendChild(o),e.known_uniprot_variant){let n=document.createElement(`div`);n.textContent=`Known UniProt variant at this position: ${e.known_uniprot_variant.description||`(no description)`}`,t.appendChild(n)}if(e.highlight_chains){let n=document.createElement(`button`);n.type=`button`,n.className=`font-label-sm text-label-sm text-accent hover:underline text-left`,n.textContent=`Highlight in 3D`,n.addEventListener(`click`,()=>this.onHighlightResidues(e.highlight_chains)),t.appendChild(n)}}async loadDdgStability(){let e=this.element.querySelector(`#mutation-ddg-result`),t=this.element.querySelector(`#annotations-structure-select`).value||this.structures[0]?.pdbId,n=this.structures.find(e=>e.pdbId===t)?.chain,r=Number.parseInt(this.element.querySelector(`#mutation-resi-input`).value,10),i=this.element.querySelector(`#mutation-mutant-input`).value.trim();if(!t||!n){e.textContent=`Select a structure with a resolved chain first.`;return}if(!Number.isInteger(r)||!i){e.textContent=`Enter a residue number and a mutant residue.`;return}e.textContent=`Predicting stability impact (this can take a minute)…`;try{let a=await b((await ie(t,n,r,i)).job_id,{intervalMs:1e4});if(a.status===`failed`){e.textContent=a.error||`Failed to predict stability impact.`;return}this.renderDdgStability(a.prediction)}catch(t){console.error(`Failed to predict stability impact:`,t),e.textContent=`Failed to predict stability impact.`}}renderDdgStability(e){let t=this.element.querySelector(`#mutation-ddg-result`),n=e?.prediction;if(typeof n!=`number`){t.textContent=`DDMut did not return a usable prediction.`;return}let r=n>=0?`stabilizing`:`destabilizing`;t.textContent=`Predicted stability change (DDMut): ${n>=0?`+`:``}${n.toFixed(2)} kcal/mol (${r})`}async loadInterproscanAnnotation(e){let t=this.element.querySelector(`#interproscan-feedback`),n=this.element.querySelector(`#interproscan-result`),r=this.element.querySelector(`#interproscan-annotate-btn`);if(!t||!n)return;let i=this.structures.find(t=>t.pdbId===e);r.disabled=!0,t.textContent=`Submitting to InterProScan5…`,n.innerHTML=``;try{let r=await oe(e,i?.chain,this.currentRunId);t.textContent=`Running InterProScan5 (this can take a minute or two)…`;let a=await b(r.job_id,{intervalMs:1e4});if(a.status===`failed`){t.textContent=a.error||`InterProScan5 annotation failed.`;return}let o=a.domains||[],s=a.go_terms||[];t.textContent=o.length>0||s.length>0?`Found ${o.length} domain(s), ${s.length} GO term(s).`:`No domains or GO terms found for this sequence.`,n.innerHTML=`${V(o)}${W(s)}`}catch(e){console.error(`InterProScan5 annotation failed:`,e),t.textContent=e.message||`InterProScan5 annotation failed.`}finally{r.disabled=!1}}renderReactomePathways(e){return this._renderPathwayList(e)}renderKeggPathways(e){return this._renderPathwayList(e)}renderRheaReactions(e){return e?.length?this._renderPathwayList(e.map(e=>({name:e.equation,url:`https://www.rhea-db.org/rhea/${e.id}`}))):``}_renderPathwayList(e){return e?.length?`
            <div class="flex flex-col gap-2">
                ${e.map(e=>`
                    <div class="flex items-center py-1.5 border-b border-border-subtle">
                        ${e.url?`<a href="${z(e.url)}" target="_blank" rel="noopener noreferrer" class="font-body-sm text-accent hover:underline">${z(e.name)}</a>`:`<span class="font-body-sm">${z(e.name)}</span>`}
                    </div>
                `).join(``)}
            </div>
        `:``}renderTissueExpression(e){if(!e)return``;let{tissue_specificity:t,tissue_distribution:n,subcellular_location:r}=e,i=[];t&&i.push(z(t)),n&&i.push(z(n));let a=r?.length?`<div class="font-body-sm text-secondary">Subcellular location: <span class="text-primary">${r.map(z).join(`, `)}</span></div>`:``;return!i.length&&!a?``:`
            <div class="flex flex-col gap-1">
                ${i.length?`<div class="font-body-sm text-primary">${i.join(` · `)}</div>`:``}
                ${a}
            </div>
        `}renderOrthologs(e){if(!e||Object.keys(e).length===0)return``;let t={mouse:`Mouse`,zebrafish:`Zebrafish`,fly:`Fly`,yeast:`Yeast`};return`
            <div class="flex flex-col gap-1">
                <div class="font-body-sm text-primary">${Object.entries(e).map(([e,n])=>`${t[e]||e}: ${n.map(z).join(`, `)}`).join(` · `)}</div>
            </div>
        `}renderDisprotRegions(e){return!e||e.length===0?``:`
            <div class="flex flex-col gap-1">
                <div class="font-body-sm text-primary">${z(e.map(([e,t])=>`${e}-${t}`).join(`, `))}</div>
            </div>
        `}renderIntactPartners(e){return!e||e.length===0?``:`
            <div class="flex flex-col gap-1">
                <div class="font-body-sm text-primary">${e.map(z).join(`, `)}</div>
            </div>
        `}renderTractability(e){if(!e||Object.keys(e).length===0)return``;let t={SM:`Small molecule`,AB:`Antibody`,PR:`PROTAC`,OC:`Other modality`};return`
            <div class="flex flex-col gap-1">
                <div class="font-body-sm text-primary">${Object.entries(e).map(([e,n])=>`${t[e]||e}: ${n.map(z).join(`, `)}`).join(` · `)}</div>
            </div>
        `}renderSharedAnnotations(e,t){let n=Object.values(this.annotationsCache).filter(e=>e?.accession);if(n.length<2){e.classList.add(`hidden`),e.classList.remove(`flex`);return}let r=n.map(e=>new Set((e.domains||[]).map(e=>e.name))),i=[...r[0]].filter(e=>r.every(t=>t.has(e))),a=n.map(e=>new Set((e.go_terms||[]).map(e=>e.name||e.id))),o=[...a[0]].filter(e=>a.every(t=>t.has(e)));if(i.length===0&&o.length===0){e.classList.add(`hidden`),e.classList.remove(`flex`),t.innerHTML=``;return}e.classList.remove(`hidden`),e.classList.add(`flex`),t.innerHTML=`
            ${V(i.map(e=>({name:e,type:`domain`})))}
            ${W(o.map(e=>({name:e})))}
        `}renderVisuals(){this.element&&(this.renderRamachandranSection(),this.renderQualityMetricsTable(),this.renderSecondaryStructureSection(),this.renderPairwiseTmScoreTable(),this.renderRmsfChart(),this.renderRmsdHeatmap(),this.populateContactMapSelectors(),this.populatePaeSelector(),this.populateFlexibilitySelector(),this.populateDiffNarrativeSelectors(),this.renderPhyloTree(),this.renderInsightsList(),this.populateAnnotationsPicker(),this.renderAnnotationsPanel())}renderRamachandranSection(){let e=this.element.querySelector(`#ramachandran-score`),t=this.element.querySelector(`#ramachandran-outliers`),n=this.element.querySelector(`#ramachandran-outliers-list-card`),r=this.element.querySelector(`#ramachandran-outliers-list`);if(this.ramachandranStats?.favored_percent==null){e.innerText=`--`,t.innerText=`--`,n.classList.add(`hidden`);return}e.innerText=`${this.ramachandranStats.favored_percent.toFixed(1)}%`,t.innerText=this.ramachandranStats.outlier_count,this.ramachandranStats.outlier_count>0&&this.ramachandranStats.outliers_list?.length>0?(n.classList.remove(`hidden`),r.innerHTML=``,this.ramachandranStats.outliers_list.forEach(e=>{let t=document.createElement(`span`);t.className=`px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle text-error font-mono text-[10px]`,t.innerText=e,r.appendChild(t)})):n.classList.add(`hidden`)}renderSecondaryStructureSection(){let e=this.element.querySelector(`#secondary-structure-card`);if(this.secondaryStructureStats?.total_residues==null||this.secondaryStructureStats.total_residues===0){e.classList.add(`hidden`);return}e.classList.remove(`hidden`),this.element.querySelector(`#ss-helix-percent`).innerText=`${this.secondaryStructureStats.helix_percent.toFixed(1)}%`,this.element.querySelector(`#ss-sheet-percent`).innerText=`${this.secondaryStructureStats.sheet_percent.toFixed(1)}%`,this.element.querySelector(`#ss-coil-percent`).innerText=`${this.secondaryStructureStats.coil_percent.toFixed(1)}%`}renderPairwiseTmScoreTable(){let e=this.element.querySelector(`#pairwise-tm-score-card`),t=this.element.querySelector(`#pairwise-tm-score-table-body`),n=this.tmScoreMatrix?.index,r=this.tmScoreMatrix?.data;if(!n||!r||n.length<2){e.classList.add(`hidden`);return}e.classList.remove(`hidden`);let i=[];for(let e=0;e<n.length;e++)for(let t=e+1;t<n.length;t++)i.push({a:n[e],b:n[t],value:r[e][t]});t.innerHTML=i.map(e=>{let t=z(e.a||``),n=z(e.b||``);return`
            <tr>
                <td class="py-1 font-mono"><span class="block max-w-[220px] truncate" title="${t} &harr; ${n}">${t} &harr; ${n}</span></td>
                <td class="py-1 font-mono">${typeof e.value==`number`?e.value.toFixed(3):`—`}</td>
            </tr>
        `}).join(``)}renderQualityMetricsTable(){let e=this.element.querySelector(`#quality-metrics-table-card`),t=this.element.querySelector(`#quality-metrics-table-body`),n=this.qualityMetrics?Object.entries(this.qualityMetrics):[];if(n.length===0){e.classList.add(`hidden`);return}e.classList.remove(`hidden`),t.innerHTML=``,n.forEach(([e,n])=>{let r=document.createElement(`tr`);r.className=`border-b border-border-subtle last:border-0`;let i=document.createElement(`td`);i.className=`py-1 font-mono text-primary`;let a=document.createElement(`span`);a.className=`block max-w-[180px] truncate`,a.title=e,a.textContent=e,i.appendChild(a);let o=document.createElement(`td`);o.className=`py-1 text-primary`,o.textContent=n?.tm_score==null?`--`:n.tm_score.toFixed(3);let s=document.createElement(`td`);s.className=`py-1 text-primary`,s.textContent=n?.gdt_ts==null?`--`:n.gdt_ts.toFixed(3),r.appendChild(i),r.appendChild(o),r.appendChild(s),t.appendChild(r)})}renderRmsfChart(){let e=this.element.querySelector(`#rmsf-plotly-chart`);if(!this.rmsfValues?.length){this.currentRunId&&(e.innerHTML=`
                    <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                        No residue fluctuation data available.
                    </div>
                `);return}e.innerHTML=``;let t={x:Array.from({length:this.rmsfValues.length},(e,t)=>t+1),y:this.rmsfValues,type:`scatter`,mode:`lines`,line:{color:`#E2846A`,width:2.5,shape:`spline`},fill:`tozeroy`,fillcolor:`rgba(226, 132, 106, 0.1)`,hoverinfo:`x+y`,name:`RMSF`};Plotly.newPlot(e,[t],{xaxis:{title:`Alignment Position`,gridcolor:`#2C2620`,zeroline:!1},yaxis:{title:`RMSF (Å)`,gridcolor:`#2C2620`,zeroline:!1},margin:{l:50,r:20,t:20,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,height:280,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`}},{responsive:!0,displayModeBar:!1})}renderRmsdHeatmap(){let e=this.element.querySelector(`#rmsd-plotly-heatmap`);if(!this.heatmapFig?.data){this.currentRunId&&(e.innerHTML=`
                    <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                        No pairwise heatmap figure available.
                    </div>
                `);return}e.innerHTML=``;let t={...this.heatmapFig.layout,width:void 0,height:280,margin:{l:50,r:20,t:30,b:50},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`}};Plotly.newPlot(e,this.heatmapFig.data,t,{responsive:!0,displayModeBar:!1})}_populateStructureOptions(e,t){let n=e.value;if(e.innerHTML=``,t.length===0){let t=document.createElement(`option`);t.value=``,t.textContent=`Select a structure`,e.appendChild(t)}t.forEach(({pdbId:t})=>{let n=document.createElement(`option`);n.value=t,n.textContent=t,e.appendChild(n)}),t.some(e=>e.pdbId===n)&&(e.value=n)}populateContactMapSelectors(){let e=[this.element.querySelector(`#contact-map-pdb-select`)],t=[this.element.querySelector(`#diff-distance-pdb-a-select`),this.element.querySelector(`#diff-distance-pdb-b-select`)];[...e,...t].forEach(e=>this._populateStructureOptions(e,this.structures)),t[1]&&this.structures.length>1&&t[0].value===t[1].value&&(t[1].value=this.structures[1].pdbId),this.updateContactMapButtonStates()}updateContactMapButtonStates(){let e=this.element.querySelector(`#contact-map-pdb-select`),t=this.element.querySelector(`#contact-map-load-btn`);t&&(t.disabled=!e.value);let n=this.element.querySelector(`#diff-distance-pdb-a-select`).value,r=this.element.querySelector(`#diff-distance-pdb-b-select`).value,i=this.element.querySelector(`#diff-distance-load-btn`);i&&(i.disabled=!n||!r)}populatePaeSelector(){let e=this.element.querySelector(`#pae-pdb-select`),t=this.structures.filter(({pdbId:e})=>e.toUpperCase().startsWith(`AF-`));this._populateStructureOptions(e,t);let n=this.element.querySelector(`#pae-load-btn`);n&&(n.disabled=!e.value)}async loadPae(){let e=this.element.querySelector(`#pae-pdb-select`).value,t=this.element.querySelector(`#pae-plotly`);if(e){t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading PAE&hellip;</div>`;try{let t=await Ve(e);this.renderPaeHeatmap(t)}catch(e){console.error(`Failed to load PAE:`,e),t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">No PAE data available for this structure.</div>`}}}renderPaeHeatmap(e){let t=this.element.querySelector(`#pae-plotly`);if(!t)return;t.innerHTML=``;let n={z:e.pae,type:`heatmap`,colorscale:[[0,`#3E5C9A`],[.5,`#C9A063`],[1,`#B23A3A`]],showscale:!0};Plotly.newPlot(t,[n],{height:240,margin:{l:40,r:10,t:10,b:30},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`},yaxis:{autorange:`reversed`}},{responsive:!0,displayModeBar:!1})}populateFlexibilitySelector(){let e=this.element.querySelector(`#flexibility-pdb-select`);this._populateStructureOptions(e,this.structures);let t=this.element.querySelector(`#flexibility-load-btn`);t&&(t.disabled=!e.value)}async loadFlexibility(){let e=this.element.querySelector(`#flexibility-pdb-select`).value,t=this.element.querySelector(`#flexibility-plotly`);if(e){t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading flexibility prediction&hellip;</div>`;try{let t=await M(e,this.currentRunId);this.renderFlexibilityChart(t.flexibility)}catch(e){console.error(`Failed to load flexibility prediction:`,e),t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">${e.message||`No flexibility prediction available for this structure.`}</div>`}}}renderFlexibilityChart(e){let t=this.element.querySelector(`#flexibility-plotly`);if(!t)return;t.innerHTML=``;let n=[{x:e.residue_numbers,y:e.flexibility,type:`scatter`,mode:`lines`,name:`Predicted flexibility (GNM)`,line:{color:`#8B5CF6`}}];e.b_factor&&n.push({x:e.residue_numbers,y:e.b_factor,type:`scatter`,mode:`lines`,name:`Real B-factor`,yaxis:`y2`,line:{color:`#F59E0B`,dash:`dot`}});let r={height:240,margin:{l:40,r:e.b_factor?40:10,t:10,b:30},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`},xaxis:{title:`Residue`},yaxis:{title:`Predicted flexibility (0-1)`},yaxis2:e.b_factor?{title:`B-factor`,overlaying:`y`,side:`right`}:void 0,showlegend:!!e.b_factor,legend:{orientation:`h`,y:-.3}};Plotly.newPlot(t,n,r,{responsive:!0,displayModeBar:!1})}populateDiffNarrativeSelectors(){let e=[this.element.querySelector(`#diff-narrative-pdb-a-select`),this.element.querySelector(`#diff-narrative-pdb-b-select`)];e.forEach(e=>this._populateStructureOptions(e,this.structures)),this.structures.length>1&&e[0].value===e[1].value&&(e[1].value=this.structures[1].pdbId);let t=this.element.querySelector(`#diff-narrative-load-btn`);t&&(t.disabled=!e[0].value||!e[1].value)}_rmsdFor(e,t){let n=this.heatmapFig?.data?.[0];if(!n?.z||!n?.x||!n?.y)return null;let r=n.y.indexOf(e),i=n.x.indexOf(t);if(r===-1||i===-1)return null;let a=n.z[r]?.[i];return typeof a==`number`?a:null}_tmScoreFor(e,t){let n=this.tmScoreMatrix;if(!n?.data||!n?.index||!n?.columns)return null;let r=n.index.indexOf(e),i=n.columns.indexOf(t);if(r===-1||i===-1)return null;let a=n.data[r]?.[i];return typeof a==`number`?a:null}describeStructureDiff(){let e=this.element.querySelector(`#diff-narrative-pdb-a-select`).value,t=this.element.querySelector(`#diff-narrative-pdb-b-select`).value,n=this.element.querySelector(`#diff-narrative-text`);if(!n)return;if(!e||!t||e===t){n.textContent=`Select two different structures to compare.`;return}let r=this._rmsdFor(e,t);if(r===null){n.textContent=`No RMSD data available for this pair yet - run alignment first.`;return}let i;i=r<2?`${e} and ${t} are structurally very similar (${r.toFixed(2)} Å RMSD).`:r<=5?`${e} and ${t} show moderate structural divergence (${r.toFixed(2)} Å RMSD).`:`${e} and ${t} are substantially different in shape (${r.toFixed(2)} Å RMSD).`;let a=this._tmScoreFor(e,t),o=``;a!==null&&(o=a>.9?` Their independent TM-score of ${a.toFixed(3)} confirms the same fold with high confidence.`:a>=.5?` Their independent TM-score of ${a.toFixed(3)} still indicates the same overall fold.`:` Their independent TM-score of ${a.toFixed(3)} suggests these may not share the same fold at all, despite the RMSD above.`),n.textContent=i+o}async loadContactMap(){let e=this.element.querySelector(`#contact-map-pdb-select`).value,t=this.element.querySelector(`#contact-map-plotly`);if(!(!this.currentRunId||!e)){t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading contact map&hellip;</div>`;try{let t=await Ue(this.currentRunId,e);this.renderContactMapHeatmap(t)}catch(e){console.error(`Failed to load contact map:`,e),t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Failed to load contact map.</div>`}}}renderContactMapHeatmap(e){let t=this.element.querySelector(`#contact-map-plotly`);if(!t)return;if(e.capped){t.innerHTML=`
                <div class="flex items-center justify-center h-full text-secondary font-body-sm text-center px-4">
                    ${e.residue_count} residues exceeds the dense-matrix cap - ${e.contacts.length} contacts found, too sparse to render as a heatmap here.
                </div>
            `;return}t.innerHTML=``;let n={z:e.matrix,type:`heatmap`,colorscale:[[0,`rgba(0,0,0,0)`],[1,`#C9A063`]],showscale:!1};Plotly.newPlot(t,[n],{height:240,margin:{l:40,r:10,t:10,b:30},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`},yaxis:{autorange:`reversed`}},{responsive:!0,displayModeBar:!1})}async loadDifferenceDistance(){let e=this.element.querySelector(`#diff-distance-pdb-a-select`).value,t=this.element.querySelector(`#diff-distance-pdb-b-select`).value,n=this.element.querySelector(`#diff-distance-plotly`);if(!(!this.currentRunId||!e||!t)){if(e===t){n.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Select two different structures.</div>`;return}n.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading difference-distance matrix&hellip;</div>`;try{let n=await We(this.currentRunId,e,t);this.renderDifferenceDistanceHeatmap(n)}catch(e){console.error(`Failed to load difference-distance matrix:`,e),n.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Failed to load difference-distance matrix.</div>`}}}renderDifferenceDistanceHeatmap(e){let t=this.element.querySelector(`#diff-distance-plotly`);if(!t)return;if(e.capped){t.innerHTML=`
                <div class="flex items-center justify-center h-full text-secondary font-body-sm text-center px-4">
                    ${e.column_count} aligned columns exceeds the dense-matrix cap - ${e.differences.length} notable shifts (&gt;3&Aring;) found, too sparse to render as a heatmap here.
                </div>
            `;return}t.innerHTML=``;let n={z:e.matrix,type:`heatmap`,colorscale:`YlOrRd`};Plotly.newPlot(t,[n],{height:240,margin:{l:40,r:10,t:10,b:30},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`},yaxis:{autorange:`reversed`}},{responsive:!0,displayModeBar:!1})}renderPhyloTree(){let e=this.element.querySelector(`#phylo-plotly-tree`);if(!this.treeFig?.data){this.currentRunId&&(e.innerHTML=`
                    <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                        No phylogenetic tree figure available.
                    </div>
                `);return}e.innerHTML=``;let t={...this.treeFig.layout,width:void 0,height:280,margin:{l:60,r:20,t:30,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`}};Plotly.newPlot(e,this.treeFig.data,t,{responsive:!0,displayModeBar:!1})}renderInsightsList(){let e=this.element.querySelector(`#analytics-insights-list`),t=this.element.querySelector(`#analytics-insights-empty`);e.innerHTML=``,this.insights?.length>0?(t.classList.add(`hidden`),this.insights.forEach(t=>{let{icon:n,text:r}=Ot(t),i=document.createElement(`li`);i.className=`font-body-sm text-primary border border-border-subtle rounded-md p-2 flex items-start gap-2`;let a=n?Tt(n):null;a&&(a.classList.add(`text-accent`,`shrink-0`,`mt-0.5`),i.appendChild(a));let o=document.createElement(`span`);Et(o,r),i.appendChild(o),e.appendChild(i)})):this.currentRunId?(t.textContent=`No automated insights available for this run.`,t.classList.remove(`hidden`)):(t.textContent=`Run alignment to display automated insights.`,t.classList.remove(`hidden`))}},At=class{rmsdDf=null;pdbMetadata={};threshold=3;element=null;debounceTimer=null;render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-clusters-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Structural Families</span>
                    <h2 class="section-title">Structural clusters</h2>
                </div>
                <div class="section-caption">Structures with RMSD lower than this cutoff are grouped into the same family.</div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-sm text-label-sm text-secondary">RMSD threshold</span>
                        <span id="cluster-threshold-value" class="font-mono text-body-sm text-primary">3.00 Å</span>
                    </div>
                    <input id="cluster-threshold-slider" type="range" min="0.1" max="10.0" step="0.1" value="3.0" aria-label="RMSD threshold"
                        class="w-full h-1.5 rounded-md appearance-none bg-surface-raised accent-accent cursor-pointer" />
                </div>

                <div id="clusters-list-container" class="flex flex-col">
                    <div class="text-center py-8 text-secondary font-body-sm">
                        Run alignment to identify structural clusters.
                    </div>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),e}setupEventListeners(){this.element.querySelector(`#cluster-threshold-slider`).addEventListener(`input`,e=>{this.threshold=Number.parseFloat(e.target.value),this.element.querySelector(`#cluster-threshold-value`).innerText=`${this.threshold.toFixed(2)} Å`,clearTimeout(this.debounceTimer),this.debounceTimer=setTimeout(()=>this.loadClusters(),250)})}updateResults(e,t){this.rmsdDf=e,this.pdbMetadata=t||{},this.loadClusters()}async loadClusters(){if(!this.element)return;let e=this.element.querySelector(`#clusters-list-container`);if(!this.rmsdDf){e.innerHTML=`
                <div class="text-center py-8 text-secondary font-body-sm">
                    Run alignment to identify structural clusters.
                </div>
            `;return}try{let e=await se(this.rmsdDf,this.threshold);this.renderClusters(e.clusters)}catch(t){console.error(`Failed to compute structural clusters:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to compute structural clusters.
                </div>
            `}}renderClusters(e){let t=this.element.querySelector(`#clusters-list-container`);if(!e||e.length===0){t.innerHTML=`
                <div class="text-center py-8 text-secondary font-body-sm">
                    No clusters identified with current settings.
                </div>
            `;return}t.innerHTML=e.map(e=>{let t=e.members.map(e=>`
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle last:border-b-0">
                        <span class="font-mono text-body-sm text-primary">${e}</span>
                        <span class="text-body-sm text-secondary truncate ml-2">${this.pdbMetadata[e]?.title||`Unknown Title`}</span>
                    </div>
                `).join(``);return`
                <div class="border-t border-border pt-4 pb-2">
                    <div class="flex items-center justify-between mb-2">
                        <span class="font-body-md text-body-md font-semibold text-primary">
                            Cluster ${e.cluster_id} <span class="text-secondary font-normal">(${e.members.length} members)</span>
                        </span>
                        <span class="font-label-sm text-label-sm text-secondary font-mono">
                            Avg RMSD: ${e.avg_rmsd.toFixed(2)} Å
                        </span>
                    </div>
                    <div class="flex flex-col">
                        ${t}
                    </div>
                </div>
            `}).join(``)}},jt=class{currentRunId=null;pastRuns=[];targetRunId=null;element=null;render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-comparison-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Batch Comparison</span>
                    <h2 class="section-title">Compare against a past run</h2>
                </div>
                <div class="section-caption">See how structural relationships shifted between this run and a prior one.</div>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div id="comparison-controls" class="flex flex-col gap-2">
                    <div class="text-center py-4 text-secondary font-body-sm">
                        Run an alignment to enable comparison.
                    </div>
                </div>

                <div id="comparison-results-container" class="flex flex-col gap-8"></div>
            </div>
        `,this.element=e,e}async updateResults(e){if(this.currentRunId=e,this.targetRunId=null,this.element&&(this.element.querySelector(`#comparison-results-container`).innerHTML=``),!e){this.renderControls();return}try{let t=await ce(e);this.pastRuns=t.runs||[]}catch(e){console.error(`Failed to load comparison run list:`,e),this.pastRuns=[]}this.renderControls()}renderControls(){if(!this.element)return;let e=this.element.querySelector(`#comparison-controls`);if(!this.currentRunId){e.innerHTML=`
                <div class="text-center py-4 text-secondary font-body-sm">
                    Run an alignment to enable comparison.
                </div>
            `;return}if(this.pastRuns.length===0){e.innerHTML=`
                <div class="text-center py-4 text-secondary font-body-sm">
                    No other past runs found for comparison.
                </div>
            `;return}e.innerHTML=`
            <select id="comparison-target-select" class="w-full bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                ${this.pastRuns.map(e=>`
                    <option value="${e.id}">${e.timestamp} - ${e.id.slice(0,8)}... (${e.proteins.length} p)</option>
                `).join(``)}
            </select>
            <button id="btn-run-comparison" class="btn-primary w-full py-2 px-3 rounded-md font-label-md text-label-md">
                Run Comparative Analysis
            </button>
        `,this.targetRunId=this.pastRuns[0].id,e.querySelector(`#comparison-target-select`).addEventListener(`change`,e=>{this.targetRunId=e.target.value}),e.querySelector(`#btn-run-comparison`).addEventListener(`click`,()=>this.runComparison())}async runComparison(){if(!this.currentRunId||!this.targetRunId)return;let e=this.element.querySelector(`#comparison-results-container`);e.innerHTML=`
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Calculating differences...
            </div>
        `;try{let e=await le(this.currentRunId,this.targetRunId);this.renderComparisonResults(e)}catch(t){console.error(`Batch comparison failed:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    ${t.message||`No overlapping proteins found between these runs.`}
                </div>
            `}}renderComparisonResults(e){let t=this.element.querySelector(`#comparison-results-container`);t.innerHTML=`
            <div>
                <div class="flex items-baseline justify-between mb-3">
                    <span class="font-body-md text-body-md font-semibold text-primary">RMSD difference matrix (ΔRMSD)</span>
                    <span class="font-body-sm text-body-sm text-secondary">Positive = current run diverges more than the target.</span>
                </div>
                <div id="comparison-diff-heatmap" class="w-full h-[280px]"></div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <div class="stat-row stat-primary">
                    <span class="stat-key">Mean RMSD shift</span>
                    <span class="stat-value ${e.mean_rmsd_shift>=0?`text-error`:`text-success`}">${e.mean_rmsd_shift>=0?`+`:``}${e.mean_rmsd_shift.toFixed(3)} Å</span>
                </div>
                <div class="stat-row">
                    <span class="stat-key">Current mean</span>
                    <span class="stat-value">${e.current_mean_rmsd.toFixed(3)} Å</span>
                </div>
                <div class="stat-row">
                    <span class="stat-key">Target mean</span>
                    <span class="stat-value">${e.target_mean_rmsd.toFixed(3)} Å</span>
                </div>
            </div>
        `;let n=t.querySelector(`#comparison-diff-heatmap`),r=e.diff,i={z:r.data,x:r.columns,y:r.index,type:`heatmap`,colorscale:`RdBu`,zmid:0};if(Plotly.newPlot(n,[i],{height:280,margin:{l:60,r:20,t:10,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`}},{responsive:!0,displayModeBar:!1}),r.data.every(e=>e.every(e=>e===0))){let e=document.createElement(`div`);e.className=`text-center py-2 text-success font-body-sm`,e.innerText=`Perfect Consensus: overlapping proteins are structurally identical in both runs.`,t.appendChild(e)}}},$=20,Mt=class{constructor(e){this.onReloadRun=e.onReloadRun,this.element=null,this.runsList=[],this.total=0}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-history-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Table — Session History</span>
                    <h2 class="section-title">Past runs</h2>
                </div>
                <button id="history-clear-all-btn" class="font-label-sm text-label-sm text-secondary hover:text-error transition-colors underline decoration-dotted">Clear All History</button>
            </header>

            <div class="section-body">
                <div class="flex flex-col gap-2 border border-border rounded-lg p-4 mb-4">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">RMSD trend across runs</span>
                    <span class="font-body-sm text-body-sm text-secondary">Pick 2 or more past runs (Ctrl/Cmd-click for multiple) to see how their structural similarity has shifted over time.</span>
                    <div class="flex gap-2 items-center">
                        <select id="trend-run-select" multiple size="4" aria-label="Past runs to compare RMSD trend across (select 2 or more)" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm"></select>
                        <button id="trend-load-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md self-start">Show trend</button>
                    </div>
                    <div id="trend-plotly" class="w-full h-[220px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Select runs above and click "Show trend".
                        </div>
                    </div>
                </div>

                <div id="history-runs-list" class="flex flex-col">
                    <div class="text-center py-12 text-secondary font-body-sm">
                        <span class="animate-spin material-symbols-outlined text-[24px] mb-2">sync</span>
                        Loading run logs...
                    </div>
                </div>
            </div>
        `,this.element=e,this.element.querySelector(`#history-clear-all-btn`).addEventListener(`click`,()=>this.clearAll()),this.element.querySelector(`#trend-load-btn`).addEventListener(`click`,()=>this.loadTrend()),this.loadHistoryData(),e}async clearAll(){if(this.runsList.length!==0&&confirm(`Clear all run history? This cannot be undone.`))try{await ve(),this.runsList=[],this.total=0;let e=this.element.querySelector(`#history-runs-list`);e.innerHTML=`
                <div class="text-center py-12 text-secondary font-body-sm">
                    No past alignment sessions found.
                </div>
            `}catch(e){console.error(`Failed to clear history:`,e),alert(e.message||`Failed to clear history.`)}}async loadHistoryData(){let e=this.element.querySelector(`#history-runs-list`);try{let t=await E($,0);if(this.runsList=t.runs||[],this.total=t.total||this.runsList.length,e.innerHTML=``,this.runsList.length===0){e.innerHTML=`
                    <div class="text-center py-12 text-secondary font-body-sm">
                        No past alignment sessions found.
                    </div>
                `;return}this.renderRuns(this.runsList),this.renderLoadMoreControl(),this.populateTrendSelect()}catch(t){console.error(`Failed to load history data:`,t),e.innerHTML=`
                <div class="text-center py-12 text-error font-body-sm">
                    Failed to retrieve session history log.
                </div>
            `}}renderRuns(e){let t=this.element.querySelector(`#history-runs-list`);e.forEach(e=>{let n=document.createElement(`div`);n.className=`flex flex-col gap-2 py-3 border-b border-border-subtle hover:bg-surface-raised transition-colors cursor-pointer group px-2 -mx-2 rounded-md`;let r;try{r=typeof e.pdb_ids==`string`?JSON.parse(e.pdb_ids):e.pdb_ids}catch{r=[e.pdb_ids]}let i=e.timestamp;try{let t=new Date(e.timestamp);Number.isNaN(t.getTime())||(i=t.toLocaleString())}catch{}let a=(e.metadata?.run_type||`compare`)===`discover`?`Discover`:`Compare`;n.innerHTML=`
                <div class="flex justify-between items-center">
                    <div class="flex items-center gap-4">
                        <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase" data-field="type"></span>
                        <span class="font-body-sm font-bold text-primary group-hover:text-accent font-mono" data-field="id"></span>
                        <div class="flex gap-1" data-field="pids"></div>
                    </div>
                    <div class="flex items-center gap-4">
                        <span class="text-[10px] font-medium capitalize" data-field="status"></span>
                        <span class="font-label-sm text-[10px] text-secondary" data-field="time"></span>
                        <button class="notes-toggle-btn font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Notes &amp; tags</button>
                        <button class="share-run-btn font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Share</button>
                        <button class="delete-run-btn font-label-sm text-label-sm text-secondary hover:text-error transition-colors underline decoration-dotted">Delete</button>
                    </div>
                </div>
                <div class="flex flex-wrap items-center gap-1.5" data-field="tags-display"></div>
                <div class="hidden flex-col gap-2 pt-1" data-field="notes-editor">
                    <textarea class="notes-input w-full bg-surface border border-border rounded-md px-2 py-1.5 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent" rows="2" placeholder="Add a note about this run..." aria-label="Note about this run"></textarea>
                    <input type="text" class="tags-input w-full bg-surface border border-border rounded-md px-2 py-1.5 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent font-mono" placeholder="Comma-separated tags, e.g. kinase, review" aria-label="Tags for this run" />
                    <div class="flex gap-2">
                        <button class="notes-save-btn btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm">Save</button>
                        <button class="notes-cancel-btn px-3 py-1 rounded-md font-label-sm text-label-sm text-secondary hover:text-primary">Cancel</button>
                    </div>
                </div>
            `,n.querySelector(`[data-field="type"]`).textContent=a,n.querySelector(`[data-field="id"]`).textContent=e.id;let o=n.querySelector(`[data-field="status"]`),s=e.status||`success`;o.textContent=s,o.classList.add(s===`success`?`text-success`:`text-error`),n.querySelector(`[data-field="time"]`).textContent=i;let c=n.querySelector(`[data-field="pids"]`);r.forEach(e=>{let t=document.createElement(`span`);t.className=`px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-mono text-[10px] text-secondary`,t.textContent=e,c.appendChild(t)}),this.renderTagsDisplay(n,e),n.addEventListener(`click`,()=>{this.onReloadRun(e)});let l=n.querySelector(`.notes-toggle-btn`),u=n.querySelector(`[data-field="notes-editor"]`),d=n.querySelector(`.notes-input`),f=n.querySelector(`.tags-input`);l.addEventListener(`click`,t=>{t.stopPropagation(),d.value=e.metadata?.notes||``,f.value=(e.metadata?.tags||[]).join(`, `),u.classList.remove(`hidden`),u.classList.add(`flex`)}),n.querySelector(`.notes-cancel-btn`).addEventListener(`click`,e=>{e.stopPropagation(),u.classList.add(`hidden`),u.classList.remove(`flex`)}),n.querySelector(`.notes-save-btn`).addEventListener(`click`,async t=>{t.stopPropagation();let r=d.value.trim(),i=f.value.split(`,`).map(e=>e.trim()).filter(Boolean);try{await _e(e.id,{notes:r,tags:i}),e.metadata={...e.metadata,notes:r,tags:i},this.renderTagsDisplay(n,e),u.classList.add(`hidden`),u.classList.remove(`flex`)}catch(e){console.error(`Failed to save run notes:`,e),alert(e.message||`Failed to save notes.`)}});let p=n.querySelector(`.share-run-btn`);p.addEventListener(`click`,t=>{t.stopPropagation(),navigator.clipboard.writeText(he(e.id));let n=p.innerText;p.innerText=`Copied!`,setTimeout(()=>{p.innerText=n},1500)}),n.querySelector(`.delete-run-btn`).addEventListener(`click`,async r=>{if(r.stopPropagation(),confirm(`Delete run ${e.id}? This cannot be undone.`))try{await ge(e.id),this.runsList=this.runsList.filter(t=>t.id!==e.id),this.total=Math.max(0,this.total-1),n.remove(),this.runsList.length===0?t.innerHTML=`
                            <div class="text-center py-12 text-secondary font-body-sm">
                                No past alignment sessions found.
                            </div>
                        `:this.renderLoadMoreControl()}catch(e){console.error(`Failed to delete run:`,e),alert(e.message||`Failed to delete run.`)}}),t.appendChild(n)})}renderTagsDisplay(e,t){let n=e.querySelector(`[data-field="tags-display"]`);if(n.innerHTML=``,(t.metadata?.tags||[]).forEach(e=>{let t=document.createElement(`span`);t.className=`px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle text-secondary font-mono text-[10px]`,t.textContent=e,n.appendChild(t)}),t.metadata?.notes){let e=document.createElement(`span`);e.className=`font-body-sm text-[11px] text-secondary italic`,e.textContent=t.metadata.notes,n.appendChild(e)}}renderLoadMoreControl(){let e=this.element.querySelector(`#history-runs-list`),t=this.element.querySelector(`#history-load-more-btn`);if(t&&t.remove(),this.runsList.length>=this.total)return;let n=document.createElement(`button`);n.id=`history-load-more-btn`,n.className=`w-full py-3 text-secondary hover:text-primary font-label-md text-label-md transition-colors shrink-0`,n.innerText=`Load More (${this.runsList.length}/${this.total})`,n.addEventListener(`click`,()=>this.loadMore()),e.appendChild(n)}async loadMore(){try{let e=await E($,this.runsList.length),t=e.runs||[];this.total=e.total||this.total,this.runsList=this.runsList.concat(t),this.renderRuns(t),this.renderLoadMoreControl(),this.populateTrendSelect()}catch(e){console.error(`Failed to load more history:`,e)}}populateTrendSelect(){let e=this.element.querySelector(`#trend-run-select`);if(!e)return;let t=new Set([...e.selectedOptions].map(e=>e.value));e.innerHTML=``,this.runsList.forEach(n=>{let r=document.createElement(`option`);r.value=n.id,r.textContent=`${n.id} — ${n.timestamp}`,r.selected=t.has(n.id),e.appendChild(r)})}async loadTrend(){let e=this.element.querySelector(`#trend-run-select`),t=this.element.querySelector(`#trend-plotly`),n=[...e.selectedOptions].map(e=>e.value);if(n.length<2){t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Select at least 2 runs to compare a trend.</div>`;return}t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading trend&hellip;</div>`;try{let e=await Fe(n);this.renderTrendChart(e.trend||[])}catch(e){console.error(`Failed to load run trend:`,e),t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">Failed to load run trend.</div>`}}renderTrendChart(e){let t=this.element.querySelector(`#trend-plotly`);if(!t)return;if(e.length===0){t.innerHTML=`<div class="flex items-center justify-center h-full text-secondary font-body-sm">None of the selected runs have a usable RMSD matrix.</div>`;return}t.innerHTML=``;let n=e.map(e=>e.timestamp),r=[{x:n,y:e.map(e=>e.mean_rmsd),name:`Mean RMSD`,type:`scatter`,mode:`lines+markers`,line:{color:`#C9A063`}},{x:n,y:e.map(e=>e.max_rmsd),name:`Max RMSD`,type:`scatter`,mode:`lines+markers`,line:{color:`#8B5CF6`}}];Plotly.newPlot(t,r,{height:220,margin:{l:40,r:10,t:10,b:60},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#A79E8E`},legend:{orientation:`h`,y:-.3},xaxis:{tickangle:-30}},{responsive:!0,displayModeBar:!1})}},Nt=5,Pt=class{constructor(e){this.onReloadRun=e.onReloadRun,this.onQuickStart=e.onQuickStart,this.onGoToWorkspace=e.onGoToWorkspace||(()=>{}),this.element=null}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-dashboard-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Mission Control</span>
                    <h2 class="section-title">Dashboard</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div id="dashboard-stats" class="grid grid-cols-1 sm:grid-cols-3 gap-6">
                    <div class="stat-row stat-primary">
                        <span class="stat-key">Total runs</span>
                        <span id="stat-total-runs" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Proteins analyzed</span>
                        <span id="stat-total-proteins" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Cache size</span>
                        <span id="stat-cache-size" class="stat-value">--</span>
                    </div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Recent activity</span>
                    <div id="dashboard-recent-runs" class="flex flex-col">
                        <div class="text-center py-8 text-secondary font-body-sm">
                            <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                            Loading recent activity...
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Quick start</span>
                    <div id="dashboard-quick-start" class="flex flex-wrap gap-2"></div>
                </div>
            </div>
        `,this.element=e,this.renderQuickStart(),this.loadDashboardData(),e}renderQuickStart(){let e=this.element.querySelector(`#dashboard-quick-start`);e.innerHTML=``,e.className=`grid grid-cols-1 md:grid-cols-2 gap-3.5 w-full`,B.forEach(t=>{let n=document.createElement(`button`);n.type=`button`,n.className=`quick-start-btn group text-left p-3.5 rounded-lg bg-surface border border-border-subtle hover:border-accent hover:bg-surface-raised transition-all duration-150 flex flex-col gap-1.5 shadow-sm`,n.innerHTML=`
                <div class="flex items-center justify-between w-full">
                    <span class="inline-flex items-center gap-1.5 font-label-md text-label-md font-semibold text-primary group-hover:text-accent transition-colors">
                        <span class="material-symbols-outlined text-[18px] text-accent">${t.icon||`science`}</span>
                        ${t.label}
                    </span>
                    <span class="px-2 py-0.5 rounded text-[10px] font-mono tracking-wide bg-surface-raised border border-border-subtle text-secondary">${t.tag||`Demo`}</span>
                </div>
                <span class="font-body-sm text-body-sm text-secondary line-clamp-2">${t.description||``}</span>
                <span class="font-mono text-[11px] text-muted mt-1 flex items-center gap-1">
                    <span class="material-symbols-outlined text-[13px]">dataset</span>
                    ${t.pdbIds.join(` + `)}
                </span>
            `,n.addEventListener(`click`,()=>this.onQuickStart(t.pdbIds)),e.appendChild(n)})}async loadDashboardData(){if(!this.element)return;try{let e=await ye();this.element.querySelector(`#stat-total-runs`).textContent=e.total_runs,this.element.querySelector(`#stat-total-proteins`).textContent=e.total_proteins_analyzed,this.element.querySelector(`#stat-cache-size`).textContent=`${e.cache_size_mb} MB`}catch(e){console.error(`Failed to load dashboard stats:`,e)}let e=this.element.querySelector(`#dashboard-recent-runs`);try{let t=(await E(Nt,0)).runs||[];if(t.length===0){e.innerHTML=``;let t=document.createElement(`div`);t.className=`flex flex-col items-center gap-2 py-8 text-center text-secondary font-body-sm`;let n=document.createElement(`span`);n.textContent=`No past alignment sessions yet - head to the Workspace tab to add structures and run one.`,t.appendChild(n);let r=document.createElement(`button`);r.type=`button`,r.className=`font-label-sm text-label-sm text-accent hover:underline`,r.textContent=`Go to Workspace`,r.addEventListener(`click`,()=>this.onGoToWorkspace()),t.appendChild(r),e.appendChild(t);return}e.innerHTML=``,t.forEach(t=>{let n;try{n=typeof t.pdb_ids==`string`?JSON.parse(t.pdb_ids):t.pdb_ids}catch{n=[t.pdb_ids]}let r=(t.metadata?.run_type||`compare`)===`discover`?`Discover`:`Compare`,i=document.createElement(`div`);i.className=`flex justify-between items-center py-3 border-b border-border-subtle hover:bg-surface-raised transition-colors cursor-pointer group px-2 -mx-2 rounded-md`,i.innerHTML=`
                    <div class="flex items-center gap-4">
                        <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase" data-field="type"></span>
                        <span class="font-body-sm font-bold text-primary group-hover:text-accent font-mono" data-field="id"></span>
                        <div class="flex gap-1" data-field="pids"></div>
                    </div>
                    <span class="font-label-sm text-[10px] text-secondary" data-field="timestamp"></span>
                `,i.querySelector(`[data-field="type"]`).textContent=r,i.querySelector(`[data-field="id"]`).textContent=t.id,i.querySelector(`[data-field="timestamp"]`).textContent=t.timestamp;let a=i.querySelector(`[data-field="pids"]`);n.forEach(e=>{let t=document.createElement(`span`);t.className=`px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-mono text-[10px] text-secondary`,t.textContent=e,a.appendChild(t)}),i.addEventListener(`click`,()=>this.onReloadRun(t)),e.appendChild(i)})}catch(t){console.error(`Failed to load recent activity:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to retrieve recent activity.
                </div>
            `}}},Ft=[{value:`auto`,label:`Auto-detect (Recommended)`},{value:`native`,label:`Native`},{value:`wsl`,label:`WSL (Windows Subsystem for Linux)`}],It=[`cartoon`,`stick`,`sphere`,`line`],Lt=[{value:`viridis`,label:`Viridis (Default)`},{value:`plasma`,label:`Plasma`},{value:`inferno`,label:`Inferno`},{value:`magma`,label:`Magma`},{value:`cividis`,label:`Cividis`},{value:`RdBu_r`,label:`Red-Blue (Divergent)`},{value:`Spectral_r`,label:`Spectral`}],Rt=class{element=null;settings=null;render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-settings-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — System Configuration</span>
                    <h2 class="section-title">Settings</h2>
                </div>
                <div class="section-caption border-l-2 border-tertiary text-tertiary pl-3">Changes affect every user of this deployment, and take effect on the next alignment/download - not any run already in progress.</div>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div id="settings-loading" class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Loading settings...
                </div>
                <div id="settings-form" class="hidden flex-col gap-8">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-8">
                        <div class="flex flex-col gap-4">
                            <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Mustang execution</span>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Execution backend</span>
                                <select id="setting-mustang-backend" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                                    ${Ft.map(e=>`<option value="${e.value}">${e.label}</option>`).join(``)}
                                </select>
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Execution timeout (seconds)</span>
                                <input id="setting-mustang-timeout" type="number" min="60" max="3600" step="60" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary" />
                            </label>
                        </div>

                        <div class="flex flex-col gap-4">
                            <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Limits &amp; performance</span>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Max proteins per run</span>
                                <input id="setting-max-proteins" type="number" min="2" max="100" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary" />
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Max PDB file size (MB)</span>
                                <input id="setting-max-file-size" type="number" min="10" max="2000" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary" />
                            </label>
                        </div>
                    </div>

                    <div class="flex flex-col gap-4 border-t border-border pt-6">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Visualization</span>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-8">
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Heatmap colormap</span>
                                <select id="setting-heatmap-colormap" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                                    ${Lt.map(e=>`<option value="${e.value}">${e.label}</option>`).join(``)}
                                </select>
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Default 3D style</span>
                                <select id="setting-viewer-style" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                                    ${It.map(e=>`<option value="${e}">${e}</option>`).join(``)}
                                </select>
                            </label>
                        </div>
                    </div>

                    <div id="settings-feedback" class="font-body-sm"></div>

                    <div class="flex gap-3 border-t border-border pt-6">
                        <button id="settings-save-btn" class="btn-primary py-2 px-4 rounded-md font-label-md text-label-md">Save Changes</button>
                        <button id="settings-reset-btn" class="btn-secondary py-2 px-4 rounded-md font-label-md text-label-md">Restore Defaults</button>
                    </div>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),this.loadSettings(),e}setupEventListeners(){this.element.querySelector(`#settings-save-btn`).addEventListener(`click`,()=>this.save()),this.element.querySelector(`#settings-reset-btn`).addEventListener(`click`,()=>this.reset())}async loadSettings(){try{this.settings=await Ke(),this.populateForm(),this.element.querySelector(`#settings-loading`).classList.add(`hidden`),this.element.querySelector(`#settings-form`).classList.remove(`hidden`),this.element.querySelector(`#settings-form`).classList.add(`flex`)}catch(e){console.error(`Failed to load settings:`,e),this.element.querySelector(`#settings-loading`).textContent=`Failed to load settings.`}}populateForm(){let e=this.settings;this.element.querySelector(`#setting-mustang-backend`).value=e.mustang_backend,this.element.querySelector(`#setting-mustang-timeout`).value=e.mustang_timeout,this.element.querySelector(`#setting-max-proteins`).value=e.max_proteins,this.element.querySelector(`#setting-max-file-size`).value=e.max_file_size_mb,this.element.querySelector(`#setting-heatmap-colormap`).value=e.heatmap_colormap,this.element.querySelector(`#setting-viewer-style`).value=e.viewer_default_style}readForm(){return{mustang_backend:this.element.querySelector(`#setting-mustang-backend`).value,mustang_timeout:Number.parseInt(this.element.querySelector(`#setting-mustang-timeout`).value,10),max_proteins:Number.parseInt(this.element.querySelector(`#setting-max-proteins`).value,10),max_file_size_mb:Number.parseInt(this.element.querySelector(`#setting-max-file-size`).value,10),heatmap_colormap:this.element.querySelector(`#setting-heatmap-colormap`).value,viewer_default_style:this.element.querySelector(`#setting-viewer-style`).value}}showFeedback(e,t){let n=this.element.querySelector(`#settings-feedback`);n.textContent=e,n.className=`font-body-sm ${t?`text-error`:`text-success`}`}async save(){try{this.settings=await qe(this.readForm()),this.populateForm(),this.showFeedback(`Settings saved successfully.`,!1)}catch(e){console.error(`Failed to save settings:`,e),this.showFeedback(e.message||`Failed to save settings.`,!0)}}async reset(){try{this.settings=await Je(),this.populateForm(),this.showFeedback(`Defaults restored.`,!1)}catch(e){console.error(`Failed to reset settings:`,e),this.showFeedback(e.message||`Failed to reset settings.`,!0)}}};new class e{static MAX_PROTEINS=20;constructor(){this.selectedPDBs=[],this.chainSelections={},this.pdbMetadata={},this.currentRunId=null,this.activeTab=`workspace`,this.currentLigands=[],this.isAligning=!1,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.secondaryStructureStats=null,this.tmScoreDf=null,this.rmsdDf=null;let e=new URLSearchParams(window.location.search);this.sharedRunId=e.get(`shared_run`),this.isSharedView=!!this.sharedRunId,this.isSharedView&&e.get(`api_key`)&&n(e.get(`api_key`)),this.topBar=new et({onTabChange:e=>this.switchTab(e),onExportData:()=>this.exportData(),onNewWorkspace:()=>this.resetWorkspace()}),this.viewer3D=new rt({onAtomSelect:e=>{e&&this.sequenceTab&&this.sequenceTab.highlightColumnByResidue(e.chain,e.resi)}}),this.workspaceTab=new ht({selectedPDBs:this.selectedPDBs,chainSelections:this.chainSelections,pdbMetadata:this.pdbMetadata,onAddPDB:e=>this.addPDB(e),onAddManyPDBs:e=>this.addManyPDBs(e),onUploadStructure:e=>this.uploadStructure(e),onPredictFromSequence:e=>this.predictFromSequence(e),onRemovePDB:e=>this.removePDB(e),onChainSelection:(e,t)=>{this.chainSelections[e]=t},onRunAlignment:()=>this.executeAlignment(),onQuickStart:e=>this.loadQuickStart(e),isSharedView:this.isSharedView}),this.ligandTab=new vt({selectedPDBs:this.selectedPDBs,currentRunId:this.currentRunId,onLigandSelected:(e,t,n)=>{t?this.viewer3D.showLigandBindingSite(e,t,n):this.viewer3D.resetCartoonStyles()},onResidueSelected:(e,t,n,r)=>{this.viewer3D.highlightResidue(e,t,n,r)}}),this.sequenceTab=new Ct({onHighlightResidues:e=>this.viewer3D.highlightResidues(e)}),this.analyticsTab=new kt({onHighlightResidues:e=>this.viewer3D.highlightResidues(e),onGoToWorkspace:()=>this.switchTab(`workspace`)}),this.clustersTab=new At,this.comparisonTab=new jt,this.historyPanel=new Mt({onReloadRun:e=>this.reloadPastRun(e)}),this.dashboardTab=new Pt({onReloadRun:e=>this.reloadPastRun(e),onQuickStart:e=>this.loadQuickStart(e),onGoToWorkspace:()=>this.switchTab(`workspace`)}),this.settingsTab=new Rt}render(e){e.innerHTML=``;let t=document.createElement(`div`);if(t.className=`flex flex-col h-screen overflow-hidden bg-bg text-primary`,t.appendChild(this.topBar.render()),this.isSharedView){let e=document.createElement(`div`);e.id=`shared-view-banner`,e.className=`bg-accent/10 border-b border-accent/30 text-center py-2 font-body-sm text-body-sm text-primary`,e.innerText=`Viewing a shared run — read-only.`,t.appendChild(e)}let n=document.createElement(`div`);n.className=`flex-1 flex flex-col md:flex-row overflow-hidden max-w-[1280px] mx-auto w-full`;let r=document.createElement(`div`);r.id=`tab-content-pane`,r.className=`flex-1 overflow-y-auto px-8`;let i=document.createElement(`div`);i.id=`viewer-column`,i.className=`w-full md:w-[480px] shrink-0 flex flex-col max-h-[50vh] md:max-h-none md:h-full p-6 pl-0`,i.appendChild(this.viewer3D.render()),n.appendChild(r),n.appendChild(i),t.appendChild(n),e.appendChild(t),this.viewer3D.init3Dmol(),this.updateTabContentPane(),this.isSharedView?this.loadSharedRun():this.loadChainsMetadata()}async loadSharedRun(){try{let e=await T(this.sharedRunId);await this.reloadPastRun(e)}catch(e){console.error(`Failed to load shared run:`,e);let t=document.getElementById(`shared-view-banner`);t&&(t.innerText=`Couldn't load this shared run: ${e.message}`)}}buildAnalyticsStructures(){return this.selectedPDBs.map(e=>({pdbId:e,chain:this.chainSelections[e]}))}buildStructuralStats(){return{ramachandran:this.ramachandranStats,secondaryStructure:this.secondaryStructureStats,tmScoreMatrix:this.tmScoreDf}}updateTabContentPane(){let e=document.getElementById(`tab-content-pane`);e&&(e.innerHTML=``,this.activeTab===`dashboard`?e.appendChild(this.dashboardTab.render()):this.activeTab===`workspace`?e.appendChild(this.workspaceTab.render()):this.activeTab===`ligands`?(e.appendChild(this.ligandTab.render()),this.ligandTab.updateLigands(this.currentLigands,this.currentRunId,this.selectedPDBs,this.ligandTab.pocketSimilarity)):this.activeTab===`sequence`?(e.appendChild(this.sequenceTab.render()),this.sequenceTab.updateResults(this.currentRunId,this.sequenceTab.stats)):this.activeTab===`analytics`?(e.appendChild(this.analyticsTab.render()),this.analyticsTab.updateResults(this.currentRunId,{heatmap:this.heatmapFig,tree:this.treeFig},this.buildStructuralStats(),this.analyticsTab.rmsfValues,this.analyticsTab.insights,this.analyticsTab.qualityMetrics,this.buildAnalyticsStructures())):this.activeTab===`clusters`?(e.appendChild(this.clustersTab.render()),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata)):this.activeTab===`comparison`?(e.appendChild(this.comparisonTab.render()),this.comparisonTab.updateResults(this.currentRunId)):this.activeTab===`history`?e.appendChild(this.historyPanel.render()):this.activeTab===`settings`&&e.appendChild(this.settingsTab.render()))}switchTab(e){this.activeTab=e,this.topBar.switchTab(e),this.updateTabContentPane()}async loadChainsMetadata(){if(this.selectedPDBs.length!==0){this.workspaceTab.setLoadingChains(!0);try{let e=await v(this.selectedPDBs);Object.keys(e.chains).forEach(t=>{this.pdbMetadata[t]=e.chains[t],e.chains[t].chains&&e.chains[t].chains.length>0&&(this.chainSelections[t]||(this.chainSelections[t]=e.chains[t].chains[0].id))}),this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata)}catch(e){console.error(`Failed to load chain selection data:`,e)}finally{this.workspaceTab.setLoadingChains(!1)}}}syncViewerToStructureCount(){this.selectedPDBs.length===1?this.viewer3D.loadSingleStructure(this.selectedPDBs[0]):this.viewer3D.reset()}async addPDB(e){e=e.toUpperCase().trim(),f(e)&&(this.selectedPDBs.includes(e)||(this.selectedPDBs.push(e),this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),await this.loadChainsMetadata(),this.syncViewerToStructureCount()))}async addManyPDBs(t){let n=e.MAX_PROTEINS-this.selectedPDBs.length,r=t.slice(0,Math.max(n,0)),i=t.length-r.length;return this.selectedPDBs.push(...r),this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),r.length>0&&await this.loadChainsMetadata(),this.syncViewerToStructureCount(),{added:r,overCap:i}}async uploadStructure(t){if(this.selectedPDBs.length>=e.MAX_PROTEINS)throw Error(`Workspace limit is ${e.MAX_PROTEINS} structures.`);let n=await ee(t),r=Object.keys(n.chains)[0],i=n.chains[r];this.pdbMetadata[r]=i,i.chains&&i.chains.length>0&&(this.chainSelections[r]=i.chains[0].id),this.selectedPDBs.push(r),this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.syncViewerToStructureCount()}async predictFromSequence(t){if(this.selectedPDBs.length>=e.MAX_PROTEINS)throw Error(`Workspace limit is ${e.MAX_PROTEINS} structures.`);let n=await te(t),r=Object.keys(n.chains)[0],i=n.chains[r];this.pdbMetadata[r]=i,i.chains&&i.chains.length>0&&(this.chainSelections[r]=i.chains[0].id),this.selectedPDBs.push(r),this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.syncViewerToStructureCount()}removePDB(e){this.selectedPDBs=this.selectedPDBs.filter(t=>t!==e),delete this.chainSelections[e],this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.syncViewerToStructureCount()}async loadQuickStart(e){this.selectedPDBs=[...e],this.chainSelections={},this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.switchTab(`workspace`),await this.loadChainsMetadata(),this.syncViewerToStructureCount()}async executeAlignment(){if(this.selectedPDBs.length<2||this.workspaceTab.isLoadingChains)return;this.setAligningState(!0);let e=this.workspaceTab.getParameters();try{let t=await b((await ne(this.selectedPDBs,this.chainSelections,e.removeWater,e.removeHeteroatoms)).job_id);if(t.status===`failed`)throw Error(t.error||`Alignment pipeline failed.`);let n=t.results;this.currentRunId=n.id,this.heatmapFig=n.heatmap_fig,this.treeFig=n.tree_fig,this.ramachandranStats=n.ramachandran_stats,this.secondaryStructureStats=n.secondary_structure_stats,this.tmScoreDf=n.tm_score_df,this.rmsdDf=n.rmsd_df,await this.viewer3D.loadSuperposition(n.id,this.selectedPDBs,this.chainSelections,n.rmsd_df);let r=this.selectedPDBs[0];this.currentLigands=[];let i=await w(r,n.id);this.currentLigands=i.ligands||[],this.ligandTab.updateLigands(this.currentLigands,n.id,this.selectedPDBs,n.ligand_pocket_similarity),this.sequenceTab.updateResults(n.id,n.stats),this.analyticsTab.updateResults(n.id,{heatmap:this.heatmapFig,tree:this.treeFig},this.buildStructuralStats(),n.rmsf_values,n.insights,n.quality_metrics,this.buildAnalyticsStructures()),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata),this.switchTab(`sequence`)}catch(e){console.error(`Alignment run failed:`,e),alert(`Alignment pipeline failed: ${e.message}`)}finally{this.setAligningState(!1)}}setAligningState(e){this.isAligning=e,this.workspaceTab.setAligning(e)}async reloadPastRun(e){if(!e?.metadata?.results)try{e=await T(e.id)}catch(e){console.error(`Failed to fetch full run details:`,e)}let t={};try{t=typeof e.metadata==`string`?JSON.parse(e.metadata):e.metadata}catch{}let n;try{n=typeof e.pdb_ids==`string`?JSON.parse(e.pdb_ids):e.pdb_ids}catch{n=[e.pdb_ids]}if(this.selectedPDBs=n,t?.run_type===`discover`){this.currentRunId=null,this.chainSelections={},this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.secondaryStructureStats=null,this.tmScoreDf=null,this.rmsdDf=null,this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.activeTab=`workspace`,this.updateTabContentPane(),this.syncViewerToStructureCount(),this.workspaceTab.showSavedDiscoveryResults(t.results),this.loadChainsMetadata();return}this.activeTab=`sequence`,this.currentRunId=e.id,this.chainSelections=t.chain_selection||{};let r;t.results?(r=t.results.stats||{},this.heatmapFig=t.results.heatmap_fig||null,this.treeFig=t.results.tree_fig||null,this.ramachandranStats=t.results.ramachandran_stats||null,this.secondaryStructureStats=t.results.secondary_structure_stats||null,this.tmScoreDf=t.results.tm_score_df||null,this.rmsdDf=t.results.rmsd_df||null):(r=t.stats||{},this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.secondaryStructureStats=null,this.tmScoreDf=null,this.rmsdDf=null),this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.updateTabContentPane(),await this.viewer3D.loadSuperposition(e.id,this.selectedPDBs,this.chainSelections,this.rmsdDf),this.loadChainsMetadata();let i=this.selectedPDBs[0];this.currentLigands=[];try{let t=await w(i,e.id);this.currentLigands=t.ligands||[]}catch(e){console.error(`Failed to load ligands for past run:`,e)}this.ligandTab.updateLigands(this.currentLigands,e.id,this.selectedPDBs,t.results?t.results.ligand_pocket_similarity:null),this.sequenceTab.updateResults(e.id,r),this.analyticsTab.updateResults(e.id,{heatmap:this.heatmapFig,tree:this.treeFig},this.buildStructuralStats(),t.results?t.results.rmsf_values:null,t.results?t.results.insights:null,t.results?t.results.quality_metrics:null,this.buildAnalyticsStructures()),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata),this.switchTab(`sequence`)}resetWorkspace(){confirm(`Reset current workspace and clear selected structures?`)&&(this.selectedPDBs=[],this.chainSelections={},this.pdbMetadata={},this.currentRunId=null,this.currentLigands=[],this.activeTab=`workspace`,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.secondaryStructureStats=null,this.tmScoreDf=null,this.rmsdDf=null,this.workspaceTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.ligandTab.updateLigands([],null,this.selectedPDBs),this.sequenceTab.updateResults(null,null),this.analyticsTab.updateResults(null,null,null,null,null,null,[]),this.clustersTab.updateResults(null,null),this.comparisonTab.updateResults(null),this.viewer3D.reset(),this.switchTab(`workspace`))}exportData(){if(!this.currentRunId){alert(`No active alignment result to export.`);return}window.open(k(this.currentRunId),`_blank`)}}().render(document.getElementById(`app`));