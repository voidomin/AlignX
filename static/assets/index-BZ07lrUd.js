(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),e.crossOrigin===`use-credentials`?t.credentials=`include`:e.crossOrigin===`anonymous`?t.credentials=`omit`:t.credentials=`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var e=`http://127.0.0.1:8000`;function t(e={}){return e}function n(e){return e}async function r(){let t=await fetch(`${e}/health`);if(!t.ok)throw Error(`Health check failed`);return t.json()}async function i(n){let r=await fetch(`${e}/api/suggest?q=${encodeURIComponent(n)}`,{headers:t()});if(!r.ok)throw Error(`Suggestions fetch failed`);return r.json()}async function a(n){let r=await fetch(`${e}/api/chains`,{method:`POST`,headers:t({"Content-Type":`application/json`}),body:JSON.stringify({pdb_ids:n})});if(!r.ok){let e=await r.json();throw Error(e.detail||`Chains fetch failed`)}return r.json()}async function o(n,r,i,a){let o=await fetch(`${e}/api/jobs/align`,{method:`POST`,headers:t({"Content-Type":`application/json`}),body:JSON.stringify({pdb_ids:n,chain_selection:r,remove_water:i,remove_heteroatoms:a})});if(!o.ok){let e=await o.json();throw Error(e.detail||`Alignment submission failed`)}return o.json()}async function s(n){let r=await fetch(`${e}/api/jobs/${n}`,{headers:t()});if(!r.ok){let e=await r.json();throw Error(e.detail||`Job status fetch failed`)}return r.json()}async function c(e,{intervalMs:t=1500,onTick:n=null}={}){for(;;){let r=await s(e);if(n&&n(r),r.status===`completed`||r.status===`failed`)return r;await new Promise(e=>setTimeout(e,t))}}async function l(n,r){let i=await fetch(`${e}/api/clusters`,{method:`POST`,headers:t({"Content-Type":`application/json`}),body:JSON.stringify({rmsd_df:n,threshold:r})});if(!i.ok){let e=await i.json();throw Error(e.detail||`Clusters fetch failed`)}return i.json()}async function u(n){let r=await fetch(`${e}/api/comparison/runs?exclude_run_id=${encodeURIComponent(n||``)}`,{headers:t()});if(!r.ok)throw Error(`Comparison runs fetch failed`);return r.json()}async function d(n,r){let i=await fetch(`${e}/api/comparison?current_run_id=${encodeURIComponent(n)}&target_run_id=${encodeURIComponent(r)}`,{headers:t()});if(!i.ok){let e=await i.json();throw Error(e.detail||`Comparison fetch failed`)}return i.json()}async function f(n,r){let i=await fetch(`${e}/api/ligands?pdb_id=${n}&run_id=${r}`,{headers:t()});if(!i.ok)throw Error(`Ligands fetch failed`);return i.json()}async function p(n,r,i){let a=await fetch(`${e}/api/interactions?pdb_id=${n}&ligand_id=${r}&run_id=${i}`,{headers:t()});if(!a.ok)throw Error(`Interactions fetch failed`);return a.json()}async function m(){let n=await fetch(`${e}/api/memory`,{headers:t()});if(!n.ok)throw Error(`Memory stats fetch failed`);return n.json()}async function h(){let n=await fetch(`${e}/api/memory/clear`,{method:`POST`,headers:t()});if(!n.ok)throw Error(`Clear memory execution failed`);return n.json()}async function g(n=20,r=0){let i=await fetch(`${e}/api/history?limit=${n}&offset=${r}`,{headers:t()});if(!i.ok)throw Error(`History fetch failed`);return i.json()}async function _(n){let r=await fetch(`${e}/api/sequence?run_id=${n}`,{headers:t()});if(!r.ok)throw Error(`Sequence alignment fetch failed`);return r.json()}function v(t){return`${e}/results/${t}/alignment.pdb`}function y(t){return`${e}/results/${t}/alignment.fasta`}function b(t){return n(`${e}/api/report?run_id=${t}`)}var x=[{key:`overview`,label:`Overview`},{key:`ligands`,label:`Ligands`},{key:`sequence`,label:`Sequence`},{key:`analytics`,label:`Analytics`},{key:`clusters`,label:`Clusters`},{key:`comparison`,label:`Compare`},{key:`history`,label:`History`}],S=class{constructor(e){this.onTabChange=e.onTabChange,this.onExportData=e.onExportData,this.onNewWorkspace=e.onNewWorkspace,this.activeTab=`overview`,this.element=null,this.memoryInterval=null}render(){let e=document.createElement(`header`);return e.className=`sticky top-0 z-50 bg-surface border-b border-border shrink-0`,e.innerHTML=`
            <div class="max-w-[1600px] mx-auto px-6 py-3 flex items-center justify-between gap-6">
                <div class="flex items-center gap-3 shrink-0">
                    <span class="material-symbols-outlined text-[20px] text-accent">science</span>
                    <span class="font-headline-md text-headline-md font-bold text-primary">AlignX</span>
                </div>

                <nav id="topbar-tabs" class="flex gap-1 flex-1 overflow-x-auto">
                    ${x.map(e=>`
                        <button data-tab="${e.key}" class="tab-trigger px-4 py-2 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors">${e.label}</button>
                    `).join(``)}
                </nav>

                <div class="flex items-center gap-4 shrink-0 font-mono text-label-sm">
                    <button id="topbar-new-ws-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">New Workspace</button>
                    <button id="topbar-export-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Export</button>
                    <div class="h-5 w-px bg-border"></div>
                    <span id="topbar-health-status" class="text-secondary truncate max-w-[160px]">Engine: checking...</span>
                    <span id="topbar-ram-text" class="text-muted">--</span>
                    <button id="topbar-free-ram-btn" class="text-accent hover:text-primary transition-colors">Free RAM</button>
                </div>
            </div>
        `,this.element=e,this.updateTabStyles(),this.setupEventListeners(),this.startMemoryTracking(),e}setupEventListeners(){this.element.querySelectorAll(`.tab-trigger`).forEach(e=>{e.addEventListener(`click`,()=>{let t=e.getAttribute(`data-tab`);this.switchTab(t),this.onTabChange(t)})}),this.element.querySelector(`#topbar-export-btn`).addEventListener(`click`,()=>this.onExportData()),this.element.querySelector(`#topbar-new-ws-btn`).addEventListener(`click`,()=>this.onNewWorkspace());let e=this.element.querySelector(`#topbar-free-ram-btn`);e.addEventListener(`click`,async()=>{e.innerText=`Clearing...`,e.disabled=!0;try{let e=await h();this.updateMemoryDisplay(e.ram_mb)}catch(e){console.error(`Free memory failed:`,e)}finally{e.innerText=`Free RAM`,e.disabled=!1}})}switchTab(e){this.activeTab=e,this.updateTabStyles()}updateTabStyles(){this.element.querySelectorAll(`.tab-trigger`).forEach(e=>{e.className=`tab-trigger px-4 py-2 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors ${e.getAttribute(`data-tab`)===this.activeTab?`bg-accent-muted text-accent`:`text-secondary hover:text-primary`}`})}startMemoryTracking(){let e=async()=>{try{let e=await m();this.updateMemoryDisplay(e.ram_mb)}catch(e){console.warn(`Top bar memory update failed:`,e)}try{let e=await r(),t=this.element.querySelector(`#topbar-health-status`);t&&e&&(e.mustang_installed?(t.innerText=`Mustang: Ready (${e.mustang_message&&e.mustang_message.toLowerCase().includes(`wsl`)?`WSL`:`Native`})`,t.className=`text-success truncate max-w-[160px]`):(t.innerText=`Mustang: Offline`,t.className=`text-error truncate max-w-[160px]`))}catch(e){console.warn(`Top bar health update failed:`,e);let t=this.element.querySelector(`#topbar-health-status`);t&&(t.innerText=`Engine: Disconnected`,t.className=`text-error truncate max-w-[160px]`)}};e(),this.memoryInterval=setInterval(e,1e4)}updateMemoryDisplay(e){let t=this.element.querySelector(`#topbar-ram-text`);t&&(t.innerText=`${e} MB`)}destroy(){clearInterval(this.memoryInterval)}},C=[`#8B5CF6`,`#06B6D4`,`#EC4899`,`#A3E635`,`#FB923C`,`#2DD4BF`];function w(e){return C[e%C.length]}var T=class{constructor(){this.element=null,this.viewer=null,this.currentRunId=null,this.isSurfaceVisible=!1,this.structures=[],this.rmsdDf=null}render(){let e=document.createElement(`div`);return e.className=`flex-1 card rounded-lg flex flex-col overflow-hidden relative`,e.innerHTML=`
            <!-- Viewport Header -->
            <div class="px-4 py-3 border-b border-border flex justify-between items-center">
                <h3 class="font-body-md text-body-md font-semibold text-primary">Superposition Viewer</h3>
                <div class="flex gap-2">
                    <button id="btn-toggle-surface" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Surface">
                        <span class="material-symbols-outlined text-[18px]">blur_on</span>
                    </button>
                    <button id="btn-reset-view" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Reset View">
                        <span class="material-symbols-outlined text-[18px]">center_focus_strong</span>
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
        `,this.element=e,this.setupEventListeners(),this._renderEmptyHUD(),e}init3Dmol(){let e=this.element.querySelector(`#viewer-canvas-3dmol`);e&&(e.innerHTML=``,this.viewer=$3Dmol.createViewer(e,{defaultcolors:$3Dmol.rasmolElementColors}),this.viewer.setBackgroundColor(`#050608`),window.addEventListener(`resize`,()=>{this.viewer&&this.viewer.resize()}))}setupEventListeners(){let e=this.element.querySelector(`#btn-toggle-surface`),t=this.element.querySelector(`#btn-reset-view`);e.addEventListener(`click`,()=>{this.viewer&&(this.isSurfaceVisible?(this.viewer.removeAllSurfaces(),this.isSurfaceVisible=!1):(this.viewer.addSurface($3Dmol.SurfaceType.SAS,{opacity:.45,colorscheme:`whiteCarbon`}),this.isSurfaceVisible=!0),this.viewer.render())}),t.addEventListener(`click`,()=>{this.viewer&&(this.viewer.zoomTo(),this.viewer.render())})}_buildStructures(e,t){return e.map((e,n)=>({pdbId:e,mustangChain:String.fromCharCode(65+n),sourceChain:t&&t[e]||`?`,color:w(n)}))}_renderEmptyHUD(){let e=this.element.querySelector(`#hud-structure-legend`),t=this.element.querySelector(`#hud-rmsd-container`);e&&(e.innerHTML=`<span class="font-label-sm text-label-sm text-muted font-mono">No structures loaded</span>`),t&&(t.innerHTML=`
            <span class="font-label-sm text-label-sm text-secondary uppercase">Global RMSD</span>
            <span class="font-headline-md text-headline-md text-success font-semibold">-- Å</span>
        `)}_renderHUD(){let e=this.element.querySelector(`#hud-structure-legend`),t=this.element.querySelector(`#hud-rmsd-container`);if(e.innerHTML=this.structures.map(e=>`
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
        `}_pairwiseRmsdRows(){if(!this.rmsdDf||!this.rmsdDf.index||!this.rmsdDf.data)return[];let{index:e,data:t}=this.rmsdDf,n=[];for(let r=0;r<e.length;r++)for(let i=r+1;i<e.length;i++)n.push({a:e[r],b:e[i],value:t[r][i]});return n}_meanRmsd(){let e=this._pairwiseRmsdRows();return e.length===0?`-- Å`:`${(e.reduce((e,t)=>e+t.value,0)/e.length).toFixed(2)} Å`}async loadSuperposition(e,t,n,r){this.viewer||this.init3Dmol(),this.currentRunId=e,this.structures=this._buildStructures(t,n),this.rmsdDf=r||null,this.element.querySelector(`#ambient-placeholder`).style.display=`none`,this._renderHUD();try{let t=await fetch(v(e));if(!t.ok)throw Error(`Failed to fetch alignment PDB: ${t.statusText}`);let n=await t.text();this.viewer.clear(),this.viewer.addModel(n,`pdb`),this.structures.forEach(e=>{this.viewer.setStyle({chain:e.mustangChain},{cartoon:{color:e.color,opacity:.85}})}),this.viewer.zoomTo(),this.viewer.render(),this.isSurfaceVisible=!1}catch(e){console.error(`Error loading superposition coordinate data:`,e)}}showLigandBindingSite(e,t,n){if(!this.viewer)return;this.structures.forEach(e=>{this.viewer.setStyle({chain:e.mustangChain},{cartoon:{color:e.color,opacity:.3}})});let r=this.structures[e],i=r?r.mustangChain:`A`,a=t.split(`_`),o=a.slice(0,-2).join(`_`),s=parseInt(a[a.length-1]),c={chain:i,resi:s,resn:o};this.viewer.addStyle(c,{stick:{colorscheme:`greenCarbon`,radius:.35}}),n.forEach(e=>{this.viewer.addStyle({chain:i,resi:parseInt(e.resi)},{stick:{colorscheme:`purpleCarbon`,radius:.25},cartoon:{color:r?r.color:`#8B5CF6`,opacity:1}})}),this.viewer.zoomTo({chain:i,resi:s}),this.viewer.render()}highlightResidue(e,t,n){if(!this.viewer)return;this.structures.forEach(e=>{this.viewer.setStyle({chain:e.mustangChain},{cartoon:{color:e.color,opacity:.35}})});let r=this.structures[e],i={chain:r?r.mustangChain:t,resi:parseInt(n)};this.viewer.addStyle(i,{stick:{color:`#F59E0B`,radius:.45},sphere:{color:`#F59E0B`,scale:1.3},cartoon:{color:`#F59E0B`,opacity:1}}),this.viewer.zoomTo(i),this.viewer.render()}resetCartoonStyles(){this.viewer&&(this.viewer.removeAllSurfaces(),this.structures.forEach(e=>{this.viewer.setStyle({chain:e.mustangChain},{cartoon:{color:e.color,opacity:.85}})}),this.viewer.zoomTo(),this.viewer.render())}reset(){this.structures=[],this.rmsdDf=null,this.currentRunId=null,this.viewer&&(this.viewer.clear(),this.viewer.render()),this.element&&(this.element.querySelector(`#ambient-placeholder`).style.display=`flex`,this._renderEmptyHUD())}},E=class{constructor(e){this.selectedPDBs=e.selectedPDBs||[],this.chainSelections=e.chainSelections||{},this.pdbMetadata=e.pdbMetadata||{},this.onAddPDB=e.onAddPDB,this.onRemovePDB=e.onRemovePDB,this.onChainSelection=e.onChainSelection,this.onRunAlignment=e.onRunAlignment,this.element=null,this.isLoadingChains=!1,this.suggestTimeout=null}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-overview-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Alignment Workspace</span>
                    <h2 class="section-title">Structures &amp; parameters</h2>
                </div>
                <span id="pdb-count-badge" class="font-label-sm text-label-sm text-secondary">0 Proteins</span>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div class="flex flex-col gap-3">
                    <div class="flex gap-2 relative">
                        <input id="add-pdb-input" type="text" placeholder="Enter PDB ID (e.g. 1L2Y)" class="flex-grow bg-surface-raised border border-border rounded-md px-3 py-1.5 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase" maxlength="4" autocomplete="off"/>
                        <button id="add-pdb-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add</button>
                    </div>
                    <div id="add-pdb-suggestions" class="flex gap-2"></div>

                    <div id="pdb-list-container" class="flex flex-col gap-2 mt-1">
                        <!-- Dynamic list of PDBs with chain dropdowns -->
                    </div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="eyebrow">Parameters</span>
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-water" type="checkbox" checked class="rounded border-border bg-surface-raised text-accent focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-secondary group-hover:text-primary transition-colors">Filter water molecules (HOH)</span>
                    </label>
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-heteroatoms" type="checkbox" checked class="rounded border-border bg-surface-raised text-accent focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-secondary group-hover:text-primary transition-colors">Exclude non-ligand heteroatoms</span>
                    </label>
                </div>

                <button id="overview-run-btn" class="btn-primary-hard w-full py-3 rounded-sm font-label-md text-label-md flex justify-center items-center gap-2">
                    <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                    Run Structural Alignment
                </button>
            </div>
        `,this.element=e,this.setupEventListeners(),this.refreshPDBList(),e}setupEventListeners(){let e=this.element.querySelector(`#add-pdb-btn`),t=this.element.querySelector(`#add-pdb-input`),n=this.element.querySelector(`#overview-run-btn`),r=this.element.querySelector(`#add-pdb-suggestions`),a=e=>{r.innerHTML=``,(e&&e.length>0?e.slice(0,4):[]).forEach(e=>{let n=document.createElement(`span`);n.className=`px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-label-sm text-label-sm text-secondary cursor-pointer hover:text-primary transition-colors`,n.innerText=e,n.addEventListener(`click`,()=>{this.onAddPDB(e),t.value=``,a([])}),r.appendChild(n)})};t.addEventListener(`input`,()=>{clearTimeout(this.suggestTimeout);let e=t.value.trim();if(e.length<1){a([]);return}this.suggestTimeout=setTimeout(async()=>{try{a((await i(e)).suggestions)}catch(e){console.error(`Autocomplete suggestions failed:`,e)}},300)}),e.addEventListener(`click`,()=>{let e=t.value.trim().toUpperCase();e.length===4&&(this.onAddPDB(e),t.value=``,a([]))}),t.addEventListener(`keypress`,e=>{if(e.key===`Enter`){let e=t.value.trim().toUpperCase();e.length===4&&(this.onAddPDB(e),t.value=``,a([]))}}),n.addEventListener(`click`,()=>{this.onRunAlignment()})}updateState(e,t,n){this.selectedPDBs=e,this.chainSelections=t,this.pdbMetadata=n,this.refreshPDBList()}setLoadingChains(e){this.isLoadingChains=e,this.refreshPDBList()}refreshPDBList(){if(!this.element)return;let e=this.element.querySelector(`#pdb-count-badge`);e.innerText=`${this.selectedPDBs.length} Protein${this.selectedPDBs.length===1?``:`s`}`;let t=this.element.querySelector(`#pdb-list-container`);if(this.isLoadingChains){t.innerHTML=`
                <div class="flex items-center justify-center py-4 gap-2 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Loading structure chains...
                </div>
            `;return}if(t.innerHTML=``,this.selectedPDBs.length===0){t.innerHTML=`
                <div class="text-center py-4 text-secondary font-body-sm">
                    Add at least 2 PDB structures to align.
                </div>
            `;return}this.selectedPDBs.forEach(e=>{let n=this.pdbMetadata[e],r=document.createElement(`div`);r.className=`flex items-center justify-between p-3 rounded-md bg-surface-raised border border-border-subtle`;let i=``;n&&n.chains?n.chains.forEach(t=>{let n=this.chainSelections[e]===t.id?`selected`:``;i+=`<option value="${t.id}" ${n}>Chain ${t.id} (${t.residue_count} residues)</option>`}):i=`<option value="A">Chain A</option>`,r.innerHTML=`
                <div class="flex items-center gap-3">
                    <span class="font-headline-sm text-body-md font-bold text-primary font-mono">${e}</span>
                    <select class="bg-surface border border-border rounded-md px-2 py-1 text-body-sm text-secondary focus:outline-none focus:border-accent font-mono chain-select" data-pdb="${e}">
                        ${i}
                    </select>
                </div>
                <button class="text-error hover:text-red-400 p-1 rounded-md hover:bg-surface transition-colors remove-pdb-btn" data-pdb="${e}">
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                </button>
            `,r.querySelector(`.chain-select`).addEventListener(`change`,t=>{this.onChainSelection(e,t.target.value)}),r.querySelector(`.remove-pdb-btn`).addEventListener(`click`,()=>{this.onRemovePDB(e)}),t.appendChild(r)})}getParameters(){return{removeWater:this.element.querySelector(`#param-remove-water`).checked,removeHeteroatoms:this.element.querySelector(`#param-remove-heteroatoms`).checked}}setAligning(e){let t=this.element.querySelector(`#overview-run-btn`);t&&(e?(t.disabled=!0,t.innerHTML=`
                <span class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                Aligning Pipeline...
            `):(t.disabled=!1,t.innerHTML=`
                <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Structural Alignment
            `))}},D=class{constructor(e){this.selectedPDBs=e.selectedPDBs||[],this.currentRunId=e.currentRunId,this.onResidueSelected=e.onResidueSelected,this.onLigandSelected=e.onLigandSelected,this.ligandsList=[],this.element=null,this.selectedLigandId=``,this.currentStructureIndex=0}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-ligands-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Binding Pocket</span>
                    <h2 class="section-title">Ligand inspector</h2>
                </div>
                <div class="flex gap-2">
                    <select id="ligand-structure-select" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[140px]">
                    </select>
                    <select id="ligand-select" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[220px]">
                        <option value="">No Ligands Loaded</option>
                    </select>
                </div>
            </header>

            <div class="section-body flex flex-col gap-4">
                <div id="ligand-pocket-desc" class="font-body-sm text-body-sm text-secondary leading-relaxed">
                    Perform an alignment and select a ligand from the list to analyze atomic interactions in the binding pocket.
                </div>
                <div class="flex gap-4">
                    <span id="ligand-volume-badge" class="font-label-sm text-label-sm text-secondary hidden">Volume: -- Å³</span>
                    <span id="ligand-sasa-badge" class="font-label-sm text-label-sm text-secondary hidden">SASA: -- Å²</span>
                </div>

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
            </div>
        `,this.element=e,this.setupEventListeners(),this.populateStructurePicker(),this.populateDropdown(),e}setupEventListeners(){this.element.querySelector(`#ligand-select`).addEventListener(`change`,async e=>{let t=e.target.value;this.selectedLigandId=t,await this.loadInteractions(t)}),this.element.querySelector(`#ligand-structure-select`).addEventListener(`change`,async e=>{await this.switchStructure(parseInt(e.target.value,10))})}populateStructurePicker(){if(!this.element)return;let e=this.element.querySelector(`#ligand-structure-select`);e.innerHTML=``,this.selectedPDBs.forEach((t,n)=>{let r=document.createElement(`option`);r.value=String(n),r.textContent=t,n===this.currentStructureIndex&&(r.selected=!0),e.appendChild(r)})}async switchStructure(e){if(e===this.currentStructureIndex||(this.currentStructureIndex=e,this.selectedLigandId=``,this.clearTable(),this.onLigandSelected(this.currentStructureIndex,``),!this.currentRunId))return;let t=this.selectedPDBs[e];try{let e=await f(t,this.currentRunId);this.ligandsList=e.ligands||[]}catch(e){console.error(`Failed to load ligands for structure:`,e),this.ligandsList=[]}this.populateDropdown()}updateLigands(e,t,n){this.ligandsList=e||[],this.currentRunId=t,n&&(this.selectedPDBs=n),this.currentStructureIndex=0,this.selectedLigandId=``,this.populateStructurePicker(),this.populateDropdown(),this.clearTable()}populateDropdown(){if(!this.element)return;let e=this.element.querySelector(`#ligand-select`);if(e.innerHTML=``,this.ligandsList.length===0){e.innerHTML=`<option value="">No Ligands Loaded</option>`;return}let t=document.createElement(`option`);t.value=``,t.innerText=`Select a Ligand`,e.appendChild(t),this.ligandsList.forEach(t=>{let n=document.createElement(`option`);n.value=t.id,n.innerText=`${t.name} (Chain ${t.chain}, Resi ${t.resi})`,this.selectedLigandId===t.id&&(n.selected=!0),e.appendChild(n)})}clearTable(){if(!this.element)return;let e=this.element.querySelector(`#ligand-pocket-desc`);e.innerText=`Perform an alignment and select a ligand from the list to analyze atomic interactions in the binding pocket.`,this.element.querySelector(`#ligand-volume-badge`).classList.add(`hidden`),this.element.querySelector(`#ligand-sasa-badge`).classList.add(`hidden`),this.element.querySelector(`#interaction-count`).innerText=`0 Found`,this.element.querySelector(`#interactions-table-body`).innerHTML=`
            <tr>
                <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                    Select a ligand to populate interactions.
                </td>
            </tr>
        `}async loadInteractions(e){if(!this.element)return;let t=this.element.querySelector(`#interactions-table-body`),n=this.element.querySelector(`#ligand-pocket-desc`),r=this.element.querySelector(`#interaction-count`),i=this.element.querySelector(`#ligand-volume-badge`),a=this.element.querySelector(`#ligand-sasa-badge`);if(!e){this.clearTable(),this.onLigandSelected(this.currentStructureIndex,``);return}t.innerHTML=`
            <tr>
                <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Analyzing interactions...
                </td>
            </tr>
        `;try{let o=this.selectedPDBs[this.currentStructureIndex],s=(await p(o,e,this.currentRunId)).interactions,c=s.interactions;this.onLigandSelected(this.currentStructureIndex,e,c),n.innerText=`Conserved catalytic pocket near ligand ${s.ligand}. Stable hydrophobic cluster showing coordinated interactions.`,s.pocket_volume?(i.innerText=`Volume: ${s.pocket_volume.toFixed(1)} Å³`,i.classList.remove(`hidden`)):i.classList.add(`hidden`),s.pocket_sasa?(a.innerText=`SASA: ${s.pocket_sasa.toFixed(1)} Å²`,a.classList.remove(`hidden`)):a.classList.add(`hidden`),r.innerText=`${c.length} Found`,t.innerHTML=``,c.length===0?t.innerHTML=`
                    <tr>
                        <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                            No specific interaction contacts found.
                        </td>
                    </tr>
                `:c.forEach((e,n)=>{let r=document.createElement(`tr`);r.className=`hover:bg-surface-raised transition-colors cursor-pointer group`;let i=`bg-muted`;e.type.toLowerCase().includes(`h-bond`)?i=`bg-accent`:e.type.toLowerCase().includes(`pi`)?i=`bg-[#8B5CF6]`:e.type.toLowerCase().includes(`salt`)?i=`bg-success`:e.type.toLowerCase().includes(`metal`)&&(i=`bg-warning`),r.innerHTML=`
                        <td class="px-0 py-2.5">${e.resn||e.residue||`UNK`}</td>
                        <td class="px-3 py-2.5">${e.chain}</td>
                        <td class="px-3 py-2.5 text-right text-secondary group-hover:text-primary">${e.resi}</td>
                        <td class="px-3 py-2.5 text-right font-semibold">${e.distance.toFixed(1)}</td>
                        <td class="px-3 py-2.5"><span class="inline-flex items-center gap-1.5 text-secondary"><span class="w-1.5 h-1.5 rounded-full ${i}"></span>${e.type}</span></td>
                    `,r.addEventListener(`click`,()=>{this.element.querySelectorAll(`#interactions-table-body tr`).forEach(e=>{e.className=`hover:bg-surface-raised transition-colors cursor-pointer group`,e.querySelectorAll(`td`).forEach(e=>e.classList.remove(`text-tertiary`,`font-bold`))}),r.className=`row-selected cursor-pointer group`,r.querySelectorAll(`td`).forEach(e=>e.classList.add(`text-tertiary`,`font-bold`)),this.onResidueSelected(this.currentStructureIndex,e.chain,e.resi)}),t.appendChild(r)})}catch(e){console.error(`Failed to load interactions:`,e),t.innerHTML=`
                <tr>
                    <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                        Failed to calculate pocket site contacts.
                    </td>
                </tr>
            `}}},O=class{constructor(){this.currentRunId=null,this.element=null,this.stats={rmsd:null,aligned_length:null,seq_identity:null,seq_similarity:null}}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-sequence-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Alignment Report</span>
                    <h2 class="section-title">Sequence &amp; identity</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-10">
                <div id="alignment-stats-container" class="grid grid-cols-4 gap-6">
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
                    <div id="sequence-alignment-grid-wrapper" class="overflow-x-auto rounded-md max-h-[350px]">
                        <div class="text-center py-8 text-secondary font-body-sm">
                            Run alignment to generate sequence view.
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-2 border-t border-border pt-6">
                    <span class="eyebrow mb-2">Generated outputs</span>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">alignment.pdb</span>
                        <a id="download-pdb-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View PDB</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">alignment.fasta</span>
                        <a id="download-fasta-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View FASTA</a>
                    </div>
                    <div class="flex items-center justify-between py-2">
                        <span class="font-body-sm text-body-sm text-primary font-mono">mustang_report.pdf</span>
                        <a id="download-report-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download PDF</a>
                    </div>
                </div>
            </div>
        `,this.element=e,this.refreshStats(),e}updateResults(e,t){this.currentRunId=e,this.stats=t||{},this.refreshStats(),this.loadSequenceGrid()}refreshStats(){if(!this.element)return;let e=this.stats.rmsd==null?`--`:`${parseFloat(this.stats.rmsd).toFixed(2)} Å`,t=this.stats.aligned_length==null?`--`:this.stats.aligned_length,n=this.stats.seq_identity==null?`--`:`${parseFloat(this.stats.seq_identity).toFixed(1)}%`,r=this.stats.seq_similarity==null?`--`:`${parseFloat(this.stats.seq_similarity).toFixed(1)}%`;this.element.querySelector(`#stat-rmsd`).innerText=e,this.element.querySelector(`#stat-length`).innerText=t,this.element.querySelector(`#stat-identity`).innerText=n,this.element.querySelector(`#stat-similarity`).innerText=r;let i=this.element.querySelector(`#download-pdb-link`),a=this.element.querySelector(`#download-fasta-link`),o=this.element.querySelector(`#download-report-link`);this.currentRunId?(i.href=v(this.currentRunId),i.classList.remove(`opacity-55`,`pointer-events-none`),a.href=y(this.currentRunId),a.classList.remove(`opacity-55`,`pointer-events-none`),o.href=b(this.currentRunId),o.classList.remove(`opacity-55`,`pointer-events-none`)):(i.href=`#`,i.classList.add(`opacity-55`,`pointer-events-none`),a.href=`#`,a.classList.add(`opacity-55`,`pointer-events-none`),o.href=`#`,o.classList.add(`opacity-55`,`pointer-events-none`))}async loadSequenceGrid(){if(!this.element||!this.currentRunId)return;let e=this.element.querySelector(`#sequence-alignment-grid-wrapper`);e.innerHTML=`
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Parsing sequence alignment...
            </div>
        `;try{let{sequences:t,conservation:n}=await _(this.currentRunId),r=``,i={identity:`#ff4757`,high_similarity:`#ffa502`,gap:`#2f3542`,default:`transparent`};Object.keys(t).forEach(e=>{let a=t[e],o=``;for(let e=0;e<a.length;e++){let t=a[e],r=n[e],s=i.default;t===`-`?s=i.gap:r===1?s=i.identity:r>.7&&(s=i.high_similarity),o+=`<td class="${r>.5||t===`-`?`res-val`:``} text-center font-mono border border-border-subtle" style="background-color: ${s}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;">${t}</td>`}r+=`
                    <tr class="border-b border-border-subtle">
                        <td class="sticky left-0 bg-surface-raised text-primary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">${e}</td>
                        ${o}
                    </tr>
                `});let a=``;n.forEach(e=>{let t=`&nbsp;`;e===1?t=`*`:e>.7?t=`:`:e>.5&&(t=`.`),a+=`<td class="text-center font-mono font-bold text-secondary" style="min-width: 22px; height: 20px;">${t}</td>`}),r+=`
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
            `}catch(t){console.error(`Failed to render sequence alignment viewer:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to parse alignment FASTA data.
                </div>
            `}}},k=[{key:`quality`,label:`Quality`},{key:`rmsf`,label:`RMSF`},{key:`rmsd`,label:`RMSD Matrix`},{key:`phylo`,label:`Phylogeny`}],A=class{constructor(){this.element=null,this.currentRunId=null,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsfValues=[],this.activeSubTab=`quality`}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-analytics-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Structural Analytics</span>
                    <h2 class="section-title">Quality, fluctuation &amp; phylogeny</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <!-- Sub-tab strip -->
                <div id="analytics-subtab-strip" class="flex gap-1 border border-border rounded-md p-1 shrink-0">
                    ${k.map(e=>`
                        <button data-subtab="${e.key}" class="analytics-subtab-btn flex-1 py-1.5 rounded-md font-label-md text-label-md transition-colors">${e.label}</button>
                    `).join(``)}
                </div>

                <!-- Ramachandran / Quality Report -->
                <div data-panel="quality" class="flex flex-col gap-4 shrink-0">
                    <div class="grid grid-cols-2 gap-6">
                        <div class="stat-row stat-primary">
                            <span class="stat-key">Ramachandran score</span>
                            <span id="ramachandran-score" class="stat-value">--</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-key">Outlier residues</span>
                            <span id="ramachandran-outliers" class="stat-value">--</span>
                        </div>
                    </div>
                    <div id="ramachandran-outliers-list-card" class="flex flex-col gap-2 hidden">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Top outliers</span>
                        <div id="ramachandran-outliers-list" class="flex flex-wrap gap-1.5">
                            <!-- Outlier chips -->
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
                <div data-panel="rmsd" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="rmsd-plotly-heatmap" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive heatmap.
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
            </div>
        `,this.element=e,this.setupSubTabs(),this.renderVisuals(),e}setupSubTabs(){this.element.querySelectorAll(`.analytics-subtab-btn`).forEach(e=>{e.addEventListener(`click`,()=>this.switchSubTab(e.getAttribute(`data-subtab`)))}),this.updateSubTabView()}switchSubTab(e){this.activeSubTab=e,this.updateSubTabView();let t={rmsf:`rmsf-plotly-chart`,rmsd:`rmsd-plotly-heatmap`,phylo:`phylo-plotly-tree`}[e];if(t&&typeof Plotly<`u`){let e=this.element.querySelector(`#${t}`);e&&e.data&&Plotly.Plots.resize(e)}}updateSubTabView(){this.element.querySelectorAll(`.analytics-subtab-btn`).forEach(e=>{e.className=`analytics-subtab-btn flex-1 py-1.5 rounded-md font-label-md text-label-md transition-colors ${e.getAttribute(`data-subtab`)===this.activeSubTab?`bg-accent-muted text-accent`:`text-secondary hover:text-primary`}`}),this.element.querySelectorAll(`[data-panel]`).forEach(e=>{e.classList.toggle(`hidden`,e.getAttribute(`data-panel`)!==this.activeSubTab)})}updateResults(e,t,n,r,i){this.currentRunId=e,this.heatmapFig=t,this.treeFig=n,this.ramachandranStats=r,this.rmsfValues=i||[],this.renderVisuals()}renderVisuals(){if(!this.element)return;let e=this.element.querySelector(`#ramachandran-score`),t=this.element.querySelector(`#ramachandran-outliers`),n=this.element.querySelector(`#ramachandran-outliers-list-card`),r=this.element.querySelector(`#ramachandran-outliers-list`);this.ramachandranStats&&this.ramachandranStats.favored_percent!=null?(e.innerText=`${this.ramachandranStats.favored_percent.toFixed(1)}%`,t.innerText=this.ramachandranStats.outlier_count,this.ramachandranStats.outlier_count>0&&this.ramachandranStats.outliers_list&&this.ramachandranStats.outliers_list.length>0?(n.classList.remove(`hidden`),r.innerHTML=``,this.ramachandranStats.outliers_list.forEach(e=>{let t=document.createElement(`span`);t.className=`px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle text-error font-mono text-[10px]`,t.innerText=e,r.appendChild(t)})):n.classList.add(`hidden`)):(e.innerText=`--`,t.innerText=`--`,n.classList.add(`hidden`));let i=this.element.querySelector(`#rmsf-plotly-chart`);if(this.rmsfValues&&this.rmsfValues.length>0){i.innerHTML=``;let e={x:Array.from({length:this.rmsfValues.length},(e,t)=>t+1),y:this.rmsfValues,type:`scatter`,mode:`lines`,line:{color:`#E2846A`,width:2.5,shape:`spline`},fill:`tozeroy`,fillcolor:`rgba(226, 132, 106, 0.1)`,hoverinfo:`x+y`,name:`RMSF`};Plotly.newPlot(i,[e],{xaxis:{title:`Alignment Position`,gridcolor:`#2C2620`,zeroline:!1},yaxis:{title:`RMSF (Å)`,gridcolor:`#2C2620`,zeroline:!1},margin:{l:50,r:20,t:20,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,height:280,font:{family:`Segoe UI, sans-serif`,size:10,color:`#A79E8E`}},{responsive:!0,displayModeBar:!1})}else this.currentRunId&&(i.innerHTML=`
                <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                    No residue fluctuation data available.
                </div>
            `);let a=this.element.querySelector(`#rmsd-plotly-heatmap`);if(this.heatmapFig&&this.heatmapFig.data){a.innerHTML=``;let e={...this.heatmapFig.layout,width:void 0,height:280,margin:{l:50,r:20,t:30,b:50},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Segoe UI, sans-serif`,size:10,color:`#A79E8E`}};Plotly.newPlot(a,this.heatmapFig.data,e,{responsive:!0,displayModeBar:!1})}else this.currentRunId&&(a.innerHTML=`
                <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                    No pairwise heatmap figure available.
                </div>
            `);let o=this.element.querySelector(`#phylo-plotly-tree`);if(this.treeFig&&this.treeFig.data){o.innerHTML=``;let e={...this.treeFig.layout,width:void 0,height:280,margin:{l:60,r:20,t:30,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Segoe UI, sans-serif`,size:10,color:`#A79E8E`}};Plotly.newPlot(o,this.treeFig.data,e,{responsive:!0,displayModeBar:!1})}else this.currentRunId&&(o.innerHTML=`
                <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                    No phylogenetic tree figure available.
                </div>
            `)}},j=class{constructor(){this.rmsdDf=null,this.pdbMetadata={},this.threshold=3,this.element=null,this.debounceTimer=null}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-clusters-container`,e.innerHTML=`
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
                    <input id="cluster-threshold-slider" type="range" min="0.1" max="10.0" step="0.1" value="3.0"
                        class="w-full h-1.5 rounded-md appearance-none bg-surface-raised accent-accent cursor-pointer" />
                </div>

                <div id="clusters-list-container" class="flex flex-col">
                    <div class="text-center py-8 text-secondary font-body-sm">
                        Run alignment to identify structural clusters.
                    </div>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),e}setupEventListeners(){this.element.querySelector(`#cluster-threshold-slider`).addEventListener(`input`,e=>{this.threshold=parseFloat(e.target.value),this.element.querySelector(`#cluster-threshold-value`).innerText=`${this.threshold.toFixed(2)} Å`,clearTimeout(this.debounceTimer),this.debounceTimer=setTimeout(()=>this.loadClusters(),250)})}updateResults(e,t){this.rmsdDf=e,this.pdbMetadata=t||{},this.loadClusters()}async loadClusters(){if(!this.element)return;let e=this.element.querySelector(`#clusters-list-container`);if(!this.rmsdDf){e.innerHTML=`
                <div class="text-center py-8 text-secondary font-body-sm">
                    Run alignment to identify structural clusters.
                </div>
            `;return}try{let e=await l(this.rmsdDf,this.threshold);this.renderClusters(e.clusters)}catch(t){console.error(`Failed to compute structural clusters:`,t),e.innerHTML=`
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
                        <span class="text-body-sm text-secondary truncate ml-2">${this.pdbMetadata[e]&&this.pdbMetadata[e].title||`Unknown Title`}</span>
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
            `}).join(``)}},M=class{constructor(){this.currentRunId=null,this.pastRuns=[],this.targetRunId=null,this.element=null}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-comparison-container`,e.innerHTML=`
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
        `,this.element=e,e}async updateResults(e){if(this.currentRunId=e,this.targetRunId=null,this.element&&(this.element.querySelector(`#comparison-results-container`).innerHTML=``),!e){this.renderControls();return}try{let t=await u(e);this.pastRuns=t.runs||[]}catch(e){console.error(`Failed to load comparison run list:`,e),this.pastRuns=[]}this.renderControls()}renderControls(){if(!this.element)return;let e=this.element.querySelector(`#comparison-controls`);if(!this.currentRunId){e.innerHTML=`
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
        `;try{let e=await d(this.currentRunId,this.targetRunId);this.renderComparisonResults(e)}catch(t){console.error(`Batch comparison failed:`,t),e.innerHTML=`
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
            <div class="grid grid-cols-3 gap-6">
                <div class="stat-row stat-primary">
                    <span class="stat-key">Mean RMSD shift</span>
                    <span class="stat-value ${e.mean_rmsd_shift>=0?`text-error`:`text-success`}">${e.mean_rmsd_shift.toFixed(3)} Å</span>
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
        `;let n=t.querySelector(`#comparison-diff-heatmap`),r=e.diff,i={z:r.data,x:r.columns,y:r.index,type:`heatmap`,colorscale:`RdBu`,zmid:0};if(Plotly.newPlot(n,[i],{margin:{l:60,r:20,t:10,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Segoe UI, sans-serif`,size:10,color:`#A79E8E`}},{responsive:!0,displayModeBar:!1}),r.data.every(e=>e.every(e=>e===0))){let e=document.createElement(`div`);e.className=`text-center py-2 text-success font-body-sm`,e.innerText=`Perfect Consensus: overlapping proteins are structurally identical in both runs.`,t.appendChild(e)}}},N=20,P=class{constructor(e){this.onReloadRun=e.onReloadRun,this.element=null,this.runsList=[],this.total=0}render(){let e=document.createElement(`div`);return e.className=`editorial-section`,e.id=`tab-history-container`,e.innerHTML=`
            <header class="section-head">
                <div>
                    <span class="eyebrow">Table — Session History</span>
                    <h2 class="section-title">Past runs</h2>
                </div>
            </header>

            <div class="section-body">
                <div id="history-runs-list" class="flex flex-col">
                    <div class="text-center py-12 text-secondary font-body-sm">
                        <span class="animate-spin material-symbols-outlined text-[24px] mb-2">sync</span>
                        Loading run logs...
                    </div>
                </div>
            </div>
        `,this.element=e,this.loadHistoryData(),e}async loadHistoryData(){let e=this.element.querySelector(`#history-runs-list`);try{let t=await g(N,0);if(this.runsList=t.runs||[],this.total=t.total||this.runsList.length,e.innerHTML=``,this.runsList.length===0){e.innerHTML=`
                    <div class="text-center py-12 text-secondary font-body-sm">
                        No past alignment sessions found.
                    </div>
                `;return}this.renderRuns(this.runsList),this.renderLoadMoreControl()}catch(t){console.error(`Failed to load history data:`,t),e.innerHTML=`
                <div class="text-center py-12 text-error font-body-sm">
                    Failed to retrieve session history log.
                </div>
            `}}renderRuns(e){let t=this.element.querySelector(`#history-runs-list`);e.forEach(e=>{let n=document.createElement(`div`);n.className=`flex justify-between items-center py-3 border-b border-border-subtle hover:bg-surface-raised transition-colors cursor-pointer group px-2 -mx-2 rounded-md`;let r=[];try{r=typeof e.pdb_ids==`string`?JSON.parse(e.pdb_ids):e.pdb_ids}catch{r=[e.pdb_ids]}let i=e.timestamp;try{let t=new Date(e.timestamp);isNaN(t.getTime())||(i=t.toLocaleString())}catch{}n.innerHTML=`
                <div class="flex items-center gap-4">
                    <span class="font-body-sm font-bold text-primary group-hover:text-accent font-mono">${e.id}</span>
                    <div class="flex gap-1">
                        ${r.map(e=>`<span class="px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-mono text-[10px] text-secondary">${e}</span>`).join(``)}
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    <span class="text-[10px] font-medium capitalize text-success">${e.status||`success`}</span>
                    <span class="font-label-sm text-[10px] text-secondary">${i}</span>
                </div>
            `,n.addEventListener(`click`,()=>{this.onReloadRun(e)}),t.appendChild(n)})}renderLoadMoreControl(){let e=this.element.querySelector(`#history-runs-list`),t=this.element.querySelector(`#history-load-more-btn`);if(t&&t.remove(),this.runsList.length>=this.total)return;let n=document.createElement(`button`);n.id=`history-load-more-btn`,n.className=`w-full py-3 text-secondary hover:text-primary font-label-md text-label-md transition-colors shrink-0`,n.innerText=`Load More (${this.runsList.length}/${this.total})`,n.addEventListener(`click`,()=>this.loadMore()),e.appendChild(n)}async loadMore(){try{let e=await g(N,this.runsList.length),t=e.runs||[];this.total=e.total||this.total,this.runsList=this.runsList.concat(t),this.renderRuns(t),this.renderLoadMoreControl()}catch(e){console.error(`Failed to load more history:`,e)}}};new class{constructor(){this.selectedPDBs=[`4RLT`,`3UG9`],this.chainSelections={"4RLT":`A`,"3UG9":`A`},this.pdbMetadata={},this.currentRunId=null,this.activeTab=`overview`,this.currentLigands=[],this.isAligning=!1,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsdDf=null,this.topBar=new S({onTabChange:e=>this.switchTab(e),onExportData:()=>this.exportData(),onNewWorkspace:()=>this.resetWorkspace()}),this.viewer3D=new T,this.overviewTab=new E({selectedPDBs:this.selectedPDBs,chainSelections:this.chainSelections,pdbMetadata:this.pdbMetadata,onAddPDB:e=>this.addPDB(e),onRemovePDB:e=>this.removePDB(e),onChainSelection:(e,t)=>{this.chainSelections[e]=t},onRunAlignment:()=>this.executeAlignment()}),this.ligandTab=new D({selectedPDBs:this.selectedPDBs,currentRunId:this.currentRunId,onLigandSelected:(e,t,n)=>{t?this.viewer3D.showLigandBindingSite(e,t,n):this.viewer3D.resetCartoonStyles()},onResidueSelected:(e,t,n)=>{this.viewer3D.highlightResidue(e,t,n)}}),this.sequenceTab=new O,this.analyticsTab=new A,this.clustersTab=new j,this.comparisonTab=new M,this.historyPanel=new P({onReloadRun:e=>this.reloadPastRun(e)})}render(e){e.innerHTML=``;let t=document.createElement(`div`);t.className=`flex flex-col h-screen overflow-hidden bg-bg text-primary`,t.appendChild(this.topBar.render());let n=document.createElement(`div`);n.className=`flex-1 flex flex-col md:flex-row overflow-hidden max-w-[1280px] mx-auto w-full`;let r=document.createElement(`div`);r.id=`tab-content-pane`,r.className=`flex-1 overflow-y-auto px-8`;let i=document.createElement(`div`);i.id=`viewer-column`,i.className=`w-full md:w-[480px] shrink-0 flex flex-col h-full p-6 pl-0`,i.appendChild(this.viewer3D.render()),n.appendChild(r),n.appendChild(i),t.appendChild(n),e.appendChild(t),this.viewer3D.init3Dmol(),this.updateTabContentPane(),this.loadChainsMetadata()}updateTabContentPane(){let e=document.getElementById(`tab-content-pane`);e&&(e.innerHTML=``,this.activeTab===`overview`?e.appendChild(this.overviewTab.render()):this.activeTab===`ligands`?(e.appendChild(this.ligandTab.render()),this.ligandTab.updateLigands(this.currentLigands,this.currentRunId,this.selectedPDBs)):this.activeTab===`sequence`?(e.appendChild(this.sequenceTab.render()),this.sequenceTab.updateResults(this.currentRunId,this.sequenceTab.stats)):this.activeTab===`analytics`?(e.appendChild(this.analyticsTab.render()),this.analyticsTab.updateResults(this.currentRunId,this.heatmapFig,this.treeFig,this.ramachandranStats,this.analyticsTab.rmsfValues)):this.activeTab===`clusters`?(e.appendChild(this.clustersTab.render()),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata)):this.activeTab===`comparison`?(e.appendChild(this.comparisonTab.render()),this.comparisonTab.updateResults(this.currentRunId)):this.activeTab===`history`&&e.appendChild(this.historyPanel.render()))}switchTab(e){this.activeTab=e,this.topBar.switchTab(e),this.updateTabContentPane()}async loadChainsMetadata(){if(this.selectedPDBs.length!==0){this.overviewTab.setLoadingChains(!0);try{let e=await a(this.selectedPDBs);Object.keys(e.chains).forEach(t=>{this.pdbMetadata[t]=e.chains[t],e.chains[t].chains&&e.chains[t].chains.length>0&&(this.chainSelections[t]||(this.chainSelections[t]=e.chains[t].chains[0].id))}),this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata)}catch(e){console.error(`Failed to load chain selection data:`,e)}finally{this.overviewTab.setLoadingChains(!1)}}}async addPDB(e){e=e.toUpperCase().trim(),e.length===4&&(this.selectedPDBs.includes(e)||(this.selectedPDBs.push(e),this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),await this.loadChainsMetadata()))}removePDB(e){this.selectedPDBs=this.selectedPDBs.filter(t=>t!==e),delete this.chainSelections[e],this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata)}async executeAlignment(){if(this.selectedPDBs.length<2){alert(`At least 2 PDB structures are required for structural alignment.`);return}this.setAligningState(!0);let e=this.overviewTab.getParameters();try{let t=await c((await o(this.selectedPDBs,this.chainSelections,e.removeWater,e.removeHeteroatoms)).job_id);if(t.status===`failed`)throw Error(t.error||`Alignment pipeline failed.`);let n=t.results;this.currentRunId=n.id,this.heatmapFig=n.heatmap_fig,this.treeFig=n.tree_fig,this.ramachandranStats=n.ramachandran_stats,this.rmsdDf=n.rmsd_df,await this.viewer3D.loadSuperposition(n.id,this.selectedPDBs,this.chainSelections,n.rmsd_df);let r=this.selectedPDBs[0];this.currentLigands=[];let i=await f(r,n.id);this.currentLigands=i.ligands||[],this.ligandTab.updateLigands(this.currentLigands,n.id,this.selectedPDBs),this.sequenceTab.updateResults(n.id,n.stats),this.analyticsTab.updateResults(n.id,this.heatmapFig,this.treeFig,this.ramachandranStats,n.rmsf_values),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata),this.switchTab(`sequence`)}catch(e){console.error(`Alignment run failed:`,e),alert(`Alignment pipeline failed: ${e.message}`)}finally{this.setAligningState(!1)}}setAligningState(e){this.isAligning=e,this.overviewTab.setAligning(e)}async reloadPastRun(e){this.activeTab=`sequence`,this.currentRunId=e.id;let t=[];try{t=typeof e.pdb_ids==`string`?JSON.parse(e.pdb_ids):e.pdb_ids}catch{t=[e.pdb_ids]}this.selectedPDBs=t;let n={};try{n=typeof e.metadata==`string`?JSON.parse(e.metadata):e.metadata}catch{}this.chainSelections=n.chain_selection||{};let r={};n.results?(r=n.results.stats||{},this.heatmapFig=n.results.heatmap_fig||null,this.treeFig=n.results.tree_fig||null,this.ramachandranStats=n.results.ramachandran_stats||null,this.rmsdDf=n.results.rmsd_df||null):(r=n.stats||{},this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsdDf=null),this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.updateTabContentPane(),await this.viewer3D.loadSuperposition(e.id,this.selectedPDBs,this.chainSelections,this.rmsdDf),this.loadChainsMetadata();let i=this.selectedPDBs[0];this.currentLigands=[];try{let t=await f(i,e.id);this.currentLigands=t.ligands||[]}catch(e){console.error(`Failed to load ligands for past run:`,e)}this.ligandTab.updateLigands(this.currentLigands,e.id,this.selectedPDBs),this.sequenceTab.updateResults(e.id,r),this.analyticsTab.updateResults(e.id,this.heatmapFig,this.treeFig,this.ramachandranStats,n.results?n.results.rmsf_values:null),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata),this.switchTab(`sequence`)}resetWorkspace(){confirm(`Reset current workspace and clear selected structures?`)&&(this.selectedPDBs=[`4RLT`,`3UG9`],this.chainSelections={"4RLT":`A`,"3UG9":`A`},this.currentRunId=null,this.currentLigands=[],this.activeTab=`overview`,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsdDf=null,this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.ligandTab.updateLigands([],null,this.selectedPDBs),this.sequenceTab.updateResults(null,null),this.analyticsTab.updateResults(null,null,null,null),this.clustersTab.updateResults(null,null),this.comparisonTab.updateResults(null),this.viewer3D.reset(),this.switchTab(`overview`))}exportData(){if(!this.currentRunId){alert(`No active alignment result to export.`);return}window.open(b(this.currentRunId),`_blank`)}}().render(document.getElementById(`app`));