(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),e.crossOrigin===`use-credentials`?t.credentials=`include`:e.crossOrigin===`anonymous`?t.credentials=`omit`:t.credentials=`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var e=`http://127.0.0.1:8000`;function t(e={}){return e}function n(e){return e}async function r(){let t=await fetch(`${e}/health`);if(!t.ok)throw Error(`Health check failed`);return t.json()}async function i(n){let r=await fetch(`${e}/api/suggest?q=${encodeURIComponent(n)}`,{headers:t()});if(!r.ok)throw Error(`Suggestions fetch failed`);return r.json()}async function a(n){let r=await fetch(`${e}/api/chains`,{method:`POST`,headers:t({"Content-Type":`application/json`}),body:JSON.stringify({pdb_ids:n})});if(!r.ok){let e=await r.json();throw Error(e.detail||`Chains fetch failed`)}return r.json()}async function o(n,r,i,a){let o=await fetch(`${e}/api/jobs/align`,{method:`POST`,headers:t({"Content-Type":`application/json`}),body:JSON.stringify({pdb_ids:n,chain_selection:r,remove_water:i,remove_heteroatoms:a})});if(!o.ok){let e=await o.json();throw Error(e.detail||`Alignment submission failed`)}return o.json()}async function s(n){let r=await fetch(`${e}/api/jobs/${n}`,{headers:t()});if(!r.ok){let e=await r.json();throw Error(e.detail||`Job status fetch failed`)}return r.json()}async function c(e,{intervalMs:t=1500,onTick:n=null}={}){for(;;){let r=await s(e);if(n&&n(r),r.status===`completed`||r.status===`failed`)return r;await new Promise(e=>setTimeout(e,t))}}async function l(n,r){let i=await fetch(`${e}/api/clusters`,{method:`POST`,headers:t({"Content-Type":`application/json`}),body:JSON.stringify({rmsd_df:n,threshold:r})});if(!i.ok){let e=await i.json();throw Error(e.detail||`Clusters fetch failed`)}return i.json()}async function u(n){let r=await fetch(`${e}/api/comparison/runs?exclude_run_id=${encodeURIComponent(n||``)}`,{headers:t()});if(!r.ok)throw Error(`Comparison runs fetch failed`);return r.json()}async function d(n,r){let i=await fetch(`${e}/api/comparison?current_run_id=${encodeURIComponent(n)}&target_run_id=${encodeURIComponent(r)}`,{headers:t()});if(!i.ok){let e=await i.json();throw Error(e.detail||`Comparison fetch failed`)}return i.json()}async function f(n,r){let i=await fetch(`${e}/api/ligands?pdb_id=${n}&run_id=${r}`,{headers:t()});if(!i.ok)throw Error(`Ligands fetch failed`);return i.json()}async function p(n,r,i){let a=await fetch(`${e}/api/interactions?pdb_id=${n}&ligand_id=${r}&run_id=${i}`,{headers:t()});if(!a.ok)throw Error(`Interactions fetch failed`);return a.json()}async function m(){let n=await fetch(`${e}/api/memory`,{headers:t()});if(!n.ok)throw Error(`Memory stats fetch failed`);return n.json()}async function h(){let n=await fetch(`${e}/api/memory/clear`,{method:`POST`,headers:t()});if(!n.ok)throw Error(`Clear memory execution failed`);return n.json()}async function g(){let n=await fetch(`${e}/api/history`,{headers:t()});if(!n.ok)throw Error(`History fetch failed`);return n.json()}async function _(n){let r=await fetch(`${e}/api/sequence?run_id=${n}`,{headers:t()});if(!r.ok)throw Error(`Sequence alignment fetch failed`);return r.json()}function v(t){return`${e}/results/${t}/alignment.pdb`}function y(t){return`${e}/results/${t}/alignment.fasta`}function b(t){return n(`${e}/api/report?run_id=${t}`)}var x=class{constructor(e){this.onAddPDB=e.onAddPDB,this.onRunAlignment=e.onRunAlignment,this.onExportData=e.onExportData,this.element=null,this.suggestTimeout=null}render(){let e=document.createElement(`header`);return e.className=`flex items-center justify-between px-6 w-full sticky top-0 z-50 bg-surface/70 backdrop-blur-xl h-16 border-b border-white/10 shadow-sm shrink-0 glass-panel`,e.innerHTML=`
            <!-- Logo -->
            <div class="flex items-center gap-3">
                <span class="material-symbols-outlined text-[28px] text-secondary">science</span>
                <span class="font-headline-md text-headline-md font-bold bg-gradient-to-r from-gradient-start to-gradient-end bg-clip-text text-transparent">AlignX</span>
            </div>
            <!-- Search / Autocomplete -->
            <div class="flex-1 max-w-lg mx-8 relative hidden md:block">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span class="material-symbols-outlined text-text-secondary text-[20px]">search</span>
                </div>
                <input id="search-input" class="w-full bg-surface-container-high/50 border border-white/10 rounded-full py-1.5 pl-10 pr-4 text-body-sm text-text-primary focus:outline-none focus:border-gradient-start transition-colors" placeholder="Search PDB ID (e.g. 4RLT)..." type="text" autocomplete="off"/>
                <!-- Suggestions container -->
                <div id="search-suggestions-container" class="absolute -bottom-8 left-0 flex gap-2 w-full pl-3">
                    <span class="px-2 py-0.5 rounded-full bg-secondary-container/20 border border-secondary-container/30 font-label-sm text-label-sm text-secondary-container cursor-pointer hover:bg-secondary-container/30 transition-colors suggestion-pill">4RLT</span>
                    <span class="px-2 py-0.5 rounded-full bg-surface-variant border border-white/10 font-label-sm text-label-sm text-text-secondary cursor-pointer hover:bg-surface-variant/80 transition-colors suggestion-pill">1L2Y</span>
                    <span class="px-2 py-0.5 rounded-full bg-surface-variant border border-white/10 font-label-sm text-label-sm text-text-secondary cursor-pointer hover:bg-surface-variant/80 transition-colors suggestion-pill">3UG9</span>
                </div>
            </div>
            <!-- Trailing Actions -->
            <div class="flex items-center gap-4">
                <button id="header-export-btn" class="btn-secondary px-4 py-1.5 rounded-full font-label-md text-label-md flex items-center gap-2">
                    <span class="material-symbols-outlined text-[16px]">download</span>
                    Export Data
                </button>
                <button id="header-run-btn" class="btn-primary px-5 py-1.5 rounded-full font-label-md text-label-md flex items-center gap-2 shadow-lg shadow-gradient-start/20 hover:shadow-gradient-start/40">
                    <span class="material-symbols-outlined text-[16px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                    Run Alignment
                </button>
                <div class="h-6 w-px bg-white/10 mx-2"></div>
                <button class="text-text-secondary hover:text-primary transition-colors duration-200 active:scale-95 transition-transform p-1 rounded-full hover:bg-white/5">
                    <span class="material-symbols-outlined text-[20px]">notifications</span>
                </button>
                <button class="text-text-secondary hover:text-primary transition-colors duration-200 active:scale-95 transition-transform p-1 rounded-full hover:bg-white/5">
                    <span class="material-symbols-outlined text-[20px]">settings</span>
                </button>
                <!-- Profile -->
                <div class="ml-2 w-8 h-8 rounded-full border border-white/20 overflow-hidden shrink-0 cursor-pointer hover:border-gradient-start transition-colors">
                    <img class="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDEyyjIkHCGepe5Ymzj0MpWOscJ_Kt-PyrVoB0S9tHDBffJYPSHxIr_tcf3T-w41wOkZrnd71QKaUeK4ED0G7js0pyNqHYPb_-lfi1D4_wdCuvA8K-0jc-8akGAdROL6OBJrtCE84WGijP6FD7yiLSHDn9eJa650zyRWOk1s1JnuyGdG2plc51hwkE9EcYXzyFodznjQvK4plqg-xk_T1Nyyq_q-3N34cEGUNssUD0g_auTsgDULTa3boCTa7_utGKKbQDd2nLCwas"/>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),e}setupEventListeners(){let e=this.element.querySelector(`#search-input`),t=this.element.querySelector(`#search-suggestions-container`),n=this.element.querySelector(`#header-run-btn`),r=this.element.querySelector(`#header-export-btn`),a=n=>{t.innerHTML=``,(n&&n.length>0?n.slice(0,4):[`4RLT`,`1L2Y`,`3UG9`]).forEach(n=>{let r=document.createElement(`span`);r.className=`px-2 py-0.5 rounded-full bg-surface-variant border border-white/10 font-label-sm text-label-sm text-text-secondary cursor-pointer hover:bg-surface-variant/80 transition-colors suggestion-pill`,r.innerText=n,r.addEventListener(`click`,()=>{this.onAddPDB(n),e.value=``,a([])}),t.appendChild(r)})};e.addEventListener(`input`,()=>{clearTimeout(this.suggestTimeout);let t=e.value.trim();if(t.length<1){a([]);return}this.suggestTimeout=setTimeout(async()=>{try{a((await i(t)).suggestions)}catch(e){console.error(`Autocomplete suggestions failed:`,e)}},300)}),e.addEventListener(`keydown`,t=>{if(t.key===`Enter`){let t=e.value.trim().toUpperCase();t.length===4&&(this.onAddPDB(t),e.value=``,a([]))}}),a([]),n.addEventListener(`click`,()=>this.onRunAlignment()),r.addEventListener(`click`,()=>this.onExportData())}setAligning(e){let t=this.element.querySelector(`#header-run-btn`);t&&(e?(t.disabled=!0,t.innerHTML=`
                <span class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                Aligning...
            `):(t.disabled=!1,t.innerHTML=`
                <span class="material-symbols-outlined text-[16px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Alignment
            `))}},S=class{constructor(e){this.onNavigate=e.onNavigate,this.onNewWorkspace=e.onNewWorkspace,this.element=null,this.activeView=`dashboard`,this.memoryInterval=null}render(){let e=document.createElement(`nav`);return e.className=`w-[280px] h-full bg-surface/70 backdrop-blur-xl border-r border-white/10 shadow-lg flex flex-col py-6 shrink-0 z-40 hidden md:flex glass-panel`,e.innerHTML=`
            <!-- Header Area (System Health) -->
            <div class="px-6 mb-8 flex flex-col gap-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-surface-variant flex items-center justify-center border border-white/10">
                        <span class="material-symbols-outlined text-gradient-start text-[24px]">memory</span>
                    </div>
                    <div>
                        <h2 class="font-body-md text-body-md font-semibold text-text-primary">System Health</h2>
                        <p id="sidebar-health-status" class="font-label-sm text-label-sm text-text-secondary font-mono">Engine: checking...</p>
                    </div>
                </div>
                <!-- Expanded Panel Content -->
                <div class="mt-2 glass-panel p-3 rounded-lg flex flex-col gap-2 bg-black/20">
                    <div class="flex justify-between items-center">
                        <span class="font-label-sm text-label-sm text-text-secondary">Live RAM</span>
                        <span id="sidebar-ram-text" class="font-label-sm text-label-sm text-text-primary font-mono">Loading...</span>
                    </div>
                    <div class="w-full bg-black/40 rounded-full h-1.5 overflow-hidden">
                        <div id="sidebar-ram-bar" class="bg-secondary-container h-full rounded-full transition-all duration-500" style="width: 30%"></div>
                    </div>
                    <button id="sidebar-free-ram-btn" class="mt-2 text-center text-secondary font-label-sm text-label-sm hover:text-secondary-fixed transition-colors border border-secondary/20 rounded py-1 hover:bg-secondary/10">
                        Free RAM
                    </button>
                </div>
                <button id="sidebar-new-ws-btn" class="mt-2 btn-secondary w-full py-2 rounded-lg font-label-md text-label-md flex justify-center items-center gap-2">
                    <span class="material-symbols-outlined text-[16px]">add</span>
                    New Workspace
                </button>
            </div>
            <!-- Navigation Links -->
            <div class="flex-1 overflow-y-auto px-4 flex flex-col gap-1" id="sidebar-links-container">
                <!-- Links rendered dynamically -->
            </div>
            <!-- Footer Links -->
            <div class="px-4 mt-auto pt-4 border-t border-white/10 flex flex-col gap-1">
                <a class="text-text-secondary font-label-md text-label-md flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 hover:text-text-primary transition-all duration-200" href="#">
                    <span class="material-symbols-outlined text-[18px]">help</span>
                    Docs
                </a>
                <a class="text-text-secondary font-label-md text-label-md flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 hover:text-text-primary transition-all duration-200" href="#">
                    <span class="material-symbols-outlined text-[18px]">contact_support</span>
                    Support
                </a>
            </div>
        `,this.element=e,this.renderLinks(),this.setupEventListeners(),this.startMemoryTracking(),e}renderLinks(){let e=this.element.querySelector(`#sidebar-links-container`);e.innerHTML=`
            <!-- Active Alignment Workspace -->
            <button data-view="dashboard" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView===`dashboard`?`bg-secondary/10 text-secondary border-secondary`:`text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent`}">
                <span class="material-symbols-outlined text-[20px]">dashboard</span>
                Active Workspace
            </button>
            
            <div class="mt-4 mb-1 px-3">
                <span class="font-label-sm text-label-sm text-text-secondary uppercase tracking-wider">History</span>
            </div>
            <!-- Session History -->
            <button data-view="history" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView===`history`?`bg-secondary/10 text-secondary border-secondary`:`text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent`}">
                <span class="material-symbols-outlined text-[20px]">history</span>
                Session History
            </button>
        `,e.querySelectorAll(`.nav-btn`).forEach(e=>{e.addEventListener(`click`,t=>{let n=e.getAttribute(`data-view`);this.setView(n),this.onNavigate(n)})})}setView(e){this.activeView=e,this.renderLinks()}setupEventListeners(){let e=this.element.querySelector(`#sidebar-free-ram-btn`),t=this.element.querySelector(`#sidebar-new-ws-btn`);e.addEventListener(`click`,async()=>{e.innerText=`Clearing...`,e.disabled=!0;try{let e=await h();this.updateMemoryDisplay(e.ram_mb)}catch(e){console.error(`Free memory failed:`,e)}finally{e.innerText=`Free RAM`,e.disabled=!1}}),t.addEventListener(`click`,()=>{this.onNewWorkspace&&this.onNewWorkspace()})}startMemoryTracking(){let e=async()=>{try{let e=await m();this.updateMemoryDisplay(e.ram_mb)}catch(e){console.warn(`Sidebar memory update failed:`,e)}try{let e=await r(),t=this.element.querySelector(`#sidebar-health-status`);t&&e&&(e.mustang_installed?(t.innerText=`Mustang: Ready (${e.mustang_message&&e.mustang_message.toLowerCase().includes(`wsl`)?`WSL`:`Native`})`,t.className=`font-label-sm text-label-sm text-success font-mono`):(t.innerText=`Mustang: Offline`,t.className=`font-label-sm text-label-sm text-error font-mono`))}catch(e){console.warn(`Sidebar health update failed:`,e);let t=this.element.querySelector(`#sidebar-health-status`);t&&(t.innerText=`Engine: Disconnected`,t.className=`font-label-sm text-label-sm text-error font-mono`)}};e(),this.memoryInterval=setInterval(e,1e4)}updateMemoryDisplay(e){let t=this.element.querySelector(`#sidebar-ram-text`),n=this.element.querySelector(`#sidebar-ram-bar`);if(t&&n){t.innerText=`${e} MB`;let r=Math.min(100,Math.max(10,e/500*100));n.style.width=`${r}%`}}destroy(){clearInterval(this.memoryInterval)}},C=class{constructor(){this.element=null,this.viewer=null,this.currentRunId=null,this.isSurfaceVisible=!1,this.activeSelections={refId:`--`,targetId:`--`,refChain:`--`,targetChain:`--`},this.rmsd=`--`}render(){let e=document.createElement(`div`);return e.className=`flex-1 glass-panel rounded-xl flex flex-col overflow-hidden relative shadow-2xl`,e.innerHTML=`
            <!-- Viewport Header -->
            <div class="px-4 py-3 border-b border-white/10 flex justify-between items-center bg-black/20 z-10">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-gradient-start text-[20px]">view_in_ar</span>
                    <h3 class="font-body-md text-body-md font-semibold text-text-primary">Superposition Viewer</h3>
                </div>
                <div class="flex gap-2">
                    <button id="btn-toggle-surface" class="p-1.5 rounded bg-white/5 hover:bg-white/10 text-text-secondary transition-colors" title="Toggle Surface">
                        <span class="material-symbols-outlined text-[18px]">blur_on</span>
                    </button>
                    <button id="btn-reset-view" class="p-1.5 rounded bg-white/5 hover:bg-white/10 text-text-secondary transition-colors" title="Reset View">
                        <span class="material-symbols-outlined text-[18px]">center_focus_strong</span>
                    </button>
                </div>
            </div>

            <!-- 3D Canvas Area -->
            <div id="3d-canvas-container" class="flex-grow relative bg-[#050608] overflow-hidden min-h-[300px]">
                <!-- 3Dmol viewer div (positioned absolutely to fill the container) -->
                <div id="viewer-canvas-3dmol" class="w-full h-full absolute inset-0 z-0"></div>
                
                <!-- Overlay HUD Elements (z-10 to stay on top of the 3D canvas) -->
                <div class="absolute inset-0 z-10 pointer-events-none">
                    <!-- Decorative scientific grid background -->
                    <div class="absolute inset-0 opacity-20" style="background-image: radial-gradient(circle at center, rgba(255,255,255,0.1) 1px, transparent 1px); background-size: 24px 24px;"></div>
                    <!-- Central Reticle -->
                    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 border border-white/5 rounded-full flex items-center justify-center">
                        <div class="w-1 h-1 bg-white/30 rounded-full"></div>
                    </div>
                </div>

                <!-- Abstract representation of superimposed proteins (shown only before PDB loading) -->
                <div id="ambient-placeholder" class="absolute inset-0 flex items-center justify-center pointer-events-none z-5">
                    <!-- Protein A (Deep Purple) -->
                    <div class="w-64 h-64 border-4 border-[#8B5CF6]/40 rounded-[40%_60%_70%_30%] animate-[spin_20s_linear_infinite] filter blur-[2px] opacity-70"></div>
                    <!-- Protein B (Neon Cyan) -->
                    <div class="absolute w-56 h-56 border-4 border-[#06B6D4]/50 rounded-[30%_70%_40%_60%] animate-[spin_15s_linear_reverse_infinite] filter blur-[1px]"></div>
                    <!-- Alignment visual connection lines -->
                    <svg class="absolute inset-0 w-full h-full opacity-30" preserveaspectratio="none" viewbox="0 0 100 100">
                        <line stroke="#f9bd22" stroke-dasharray="1 1" stroke-width="0.2" x1="30" x2="60" y1="40" y2="60"></line>
                        <line stroke="#f9bd22" stroke-dasharray="1 1" stroke-width="0.2" x1="45" x2="55" y1="20" y2="70"></line>
                    </svg>
                </div>
                
                <!-- Glassmorphic HUD Labels -->
                <div class="absolute top-4 left-4 bg-[#11141c]/80 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-lg shadow-lg flex flex-col gap-1.5 z-10">
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-[#8B5CF6] shadow-[0_0_8px_#8B5CF6]"></div>
                        <span id="hud-reference-label" class="font-label-sm text-label-sm text-text-primary font-mono">Reference: --</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-[#06B6D4] shadow-[0_0_8px_#06B6D4]"></div>
                        <span id="hud-target-label" class="font-label-sm text-label-sm text-text-primary font-mono">Target: --</span>
                    </div>
                </div>
                
                <!-- RMSD Overlay -->
                <div class="absolute top-4 right-4 bg-black/60 backdrop-blur-md border border-white/10 p-3 rounded-lg flex flex-col items-end z-10 font-mono">
                    <span class="font-label-sm text-label-sm text-text-secondary uppercase">Global RMSD</span>
                    <span id="rmsd-value-hud" class="font-headline-md text-headline-md text-success font-semibold">-- Å</span>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),e}init3Dmol(){let e=this.element.querySelector(`#viewer-canvas-3dmol`);e&&(e.innerHTML=``,this.viewer=$3Dmol.createViewer(e,{defaultcolors:$3Dmol.rasmolElementColors}),this.viewer.setBackgroundColor(`#050608`),window.addEventListener(`resize`,()=>{this.viewer&&this.viewer.resize()}))}setupEventListeners(){let e=this.element.querySelector(`#btn-toggle-surface`),t=this.element.querySelector(`#btn-reset-view`);e.addEventListener(`click`,()=>{this.viewer&&(this.isSurfaceVisible?(this.viewer.removeAllSurfaces(),this.isSurfaceVisible=!1):(this.viewer.addSurface($3Dmol.SurfaceType.SAS,{opacity:.45,colorscheme:`whiteCarbon`}),this.isSurfaceVisible=!0),this.viewer.render())}),t.addEventListener(`click`,()=>{this.viewer&&(this.viewer.zoomTo(),this.viewer.render())})}async loadSuperposition(e,t,n,r,i,a){this.viewer||this.init3Dmol(),this.currentRunId=e,this.activeSelections={refId:t,targetId:n,refChain:r,targetChain:i},this.rmsd=a,this.element.querySelector(`#ambient-placeholder`).style.display=`none`,this.element.querySelector(`#hud-reference-label`).innerText=`Reference: ${t} (Chain ${r})`,this.element.querySelector(`#hud-target-label`).innerText=`Target: ${n} (Chain ${i})`,this.element.querySelector(`#rmsd-value-hud`).innerText=`${parseFloat(a).toFixed(2)} Å`;try{let t=await fetch(v(e));if(!t.ok)throw Error(`Failed to fetch alignment PDB: ${t.statusText}`);let n=await t.text();this.viewer.clear(),this.viewer.addModel(n,`pdb`),this.viewer.setStyle({chain:`A`},{cartoon:{color:`#8B5CF6`,opacity:.85}}),this.viewer.setStyle({chain:`B`},{cartoon:{color:`#06B6D4`,opacity:.85}}),this.viewer.zoomTo(),this.viewer.render(),this.isSurfaceVisible=!1}catch(e){console.error(`Error loading superposition coordinate data:`,e)}}showLigandBindingSite(e,t){if(!this.viewer)return;this.viewer.setStyle({chain:`A`},{cartoon:{color:`#8B5CF6`,opacity:.3}}),this.viewer.setStyle({chain:`B`},{cartoon:{color:`#06B6D4`,opacity:.3}});let n=e.split(`_`),r=n.slice(0,-2).join(`_`),i=n[n.length-2],a=parseInt(n[n.length-1]),o={chain:i,resi:a,resn:r};this.viewer.addStyle(o,{stick:{colorscheme:`greenCarbon`,radius:.35}}),t.forEach(e=>{this.viewer.addStyle({chain:e.chain,resi:parseInt(e.resi)},{stick:{colorscheme:`purpleCarbon`,radius:.25},cartoon:{color:e.chain===`A`?`#8B5CF6`:`#06B6D4`,opacity:1}})}),this.viewer.zoomTo({chain:i,resi:a}),this.viewer.render()}highlightResidue(e,t){if(!this.viewer)return;this.viewer.setStyle({chain:`A`},{cartoon:{color:`#8B5CF6`,opacity:.35}}),this.viewer.setStyle({chain:`B`},{cartoon:{color:`#06B6D4`,opacity:.35}});let n={chain:e,resi:parseInt(t)};this.viewer.addStyle(n,{stick:{color:`#f9bd22`,radius:.45},sphere:{color:`#f9bd22`,scale:1.3},cartoon:{color:`#f9bd22`,opacity:1}}),this.viewer.zoomTo(n),this.viewer.render()}resetCartoonStyles(){this.viewer&&(this.viewer.removeAllSurfaces(),this.viewer.setStyle({chain:`A`},{cartoon:{color:`#8B5CF6`,opacity:.85}}),this.viewer.setStyle({chain:`B`},{cartoon:{color:`#06B6D4`,opacity:.85}}),this.viewer.zoomTo(),this.viewer.render())}},w=class{constructor(e){this.onTabChange=e.onTabChange,this.activeTab=`overview`,this.element=null}render(){let e=document.createElement(`div`);return e.className=`glass-panel rounded-xl p-1.5 flex gap-1`,e.innerHTML=`
            <button id="btn-tab-overview" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Overview</button>
            <button id="btn-tab-ligands" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Ligands</button>
            <button id="btn-tab-sequence" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Sequence</button>
            <button id="btn-tab-analytics" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Analytics</button>
            <button id="btn-tab-clusters" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Clusters</button>
            <button id="btn-tab-comparison" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Compare</button>
        `,this.element=e,this.updateTabStyles(),this.setupEventListeners(),e}setupEventListeners(){let e={overview:this.element.querySelector(`#btn-tab-overview`),ligands:this.element.querySelector(`#btn-tab-ligands`),sequence:this.element.querySelector(`#btn-tab-sequence`),analytics:this.element.querySelector(`#btn-tab-analytics`),clusters:this.element.querySelector(`#btn-tab-clusters`),comparison:this.element.querySelector(`#btn-tab-comparison`)};Object.keys(e).forEach(t=>{e[t].addEventListener(`click`,()=>{this.activeTab=t,this.updateTabStyles(),this.onTabChange(t)})})}updateTabStyles(){let e={overview:this.element.querySelector(`#btn-tab-overview`),ligands:this.element.querySelector(`#btn-tab-ligands`),sequence:this.element.querySelector(`#btn-tab-sequence`),analytics:this.element.querySelector(`#btn-tab-analytics`),clusters:this.element.querySelector(`#btn-tab-clusters`),comparison:this.element.querySelector(`#btn-tab-comparison`)};Object.keys(e).forEach(t=>{let n=e[t];n&&(t===this.activeTab?n.className=`flex-grow py-2 px-3 rounded-lg bg-white/10 border border-white/5 font-label-md text-label-md text-text-primary shadow-sm`:n.className=`flex-grow py-2 px-3 rounded-lg font-label-md text-label-md text-text-secondary hover:text-text-primary hover:bg-white/5 transition-colors`)})}switchTab(e){this.activeTab=e,this.updateTabStyles()}},T=class{constructor(e){this.selectedPDBs=e.selectedPDBs||[],this.chainSelections=e.chainSelections||{},this.pdbMetadata=e.pdbMetadata||{},this.onAddPDB=e.onAddPDB,this.onRemovePDB=e.onRemovePDB,this.onChainSelection=e.onChainSelection,this.onRunAlignment=e.onRunAlignment,this.element=null,this.isLoadingChains=!1}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-overview-container`,e.innerHTML=`
            <!-- Selected Proteins Card -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-[20px] text-primary">layers</span>
                        <h4 class="font-body-md text-body-md font-semibold text-text-primary">Alignment Structures</h4>
                    </div>
                    <span id="pdb-count-badge" class="px-2 py-0.5 rounded-full bg-white/10 text-text-secondary font-label-sm text-label-sm">0 Proteins</span>
                </div>
                
                <div id="pdb-list-container" class="flex flex-col gap-3">
                    <!-- Dynamic list of PDBs with chain dropdowns -->
                </div>
                
                <!-- Quick Add Section -->
                <div class="flex gap-2 mt-2">
                    <input id="add-pdb-input" type="text" placeholder="Enter PDB ID (e.g. 1L2Y)" class="flex-grow bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-body-sm text-text-primary focus:outline-none focus:border-primary font-mono uppercase" maxlength="4"/>
                    <button id="add-pdb-btn" class="btn-secondary px-4 py-1.5 rounded-lg font-label-md text-label-md flex items-center gap-1">
                        <span class="material-symbols-outlined text-[16px]">add</span>
                        Add
                    </button>
                </div>
            </div>
            
            <!-- Alignment Parameters -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-gradient-end">tune</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Pipeline Parameters</h4>
                </div>
                <div class="flex flex-col gap-3">
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-water" type="checkbox" checked class="rounded border-white/10 bg-black/40 text-primary focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-text-secondary group-hover:text-text-primary transition-colors">Filter Water Molecules (HOH)</span>
                    </label>
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-heteroatoms" type="checkbox" checked class="rounded border-white/10 bg-black/40 text-primary focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-text-secondary group-hover:text-text-primary transition-colors">Exclude Non-Ligand Heteroatoms</span>
                    </label>
                </div>
            </div>
            
            <!-- Quick Run Action -->
            <button id="overview-run-btn" class="btn-primary w-full py-3 rounded-xl font-label-md text-label-md flex justify-center items-center gap-2 shadow-lg shadow-gradient-start/20 hover:shadow-gradient-start/40">
                <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Structural Alignment
            </button>
        `,this.element=e,this.setupEventListeners(),this.refreshPDBList(),e}setupEventListeners(){let e=this.element.querySelector(`#add-pdb-btn`),t=this.element.querySelector(`#add-pdb-input`),n=this.element.querySelector(`#overview-run-btn`);e.addEventListener(`click`,()=>{let e=t.value.trim().toUpperCase();e.length===4&&(this.onAddPDB(e),t.value=``)}),t.addEventListener(`keypress`,e=>{if(e.key===`Enter`){let e=t.value.trim().toUpperCase();e.length===4&&(this.onAddPDB(e),t.value=``)}}),n.addEventListener(`click`,()=>{this.onRunAlignment()})}updateState(e,t,n){this.selectedPDBs=e,this.chainSelections=t,this.pdbMetadata=n,this.refreshPDBList()}setLoadingChains(e){this.isLoadingChains=e,this.refreshPDBList()}refreshPDBList(){if(!this.element)return;let e=this.element.querySelector(`#pdb-count-badge`);e.innerText=`${this.selectedPDBs.length} Protein${this.selectedPDBs.length===1?``:`s`}`;let t=this.element.querySelector(`#pdb-list-container`);if(this.isLoadingChains){t.innerHTML=`
                <div class="flex items-center justify-center py-4 gap-2 text-text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Loading structure chains...
                </div>
            `;return}if(t.innerHTML=``,this.selectedPDBs.length===0){t.innerHTML=`
                <div class="text-center py-4 text-text-secondary font-body-sm">
                    Add at least 2 PDB structures to align.
                </div>
            `;return}this.selectedPDBs.forEach(e=>{let n=this.pdbMetadata[e],r=document.createElement(`div`);r.className=`flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 transition-all`;let i=``;n&&n.chains?n.chains.forEach(t=>{let n=this.chainSelections[e]===t.id?`selected`:``;i+=`<option value="${t.id}" ${n}>Chain ${t.id} (${t.residues_count} residues)</option>`}):i=`<option value="A">Chain A</option>`,r.innerHTML=`
                <div class="flex items-center gap-3">
                    <span class="font-headline-sm text-body-md font-bold text-text-primary font-mono">${e}</span>
                    <select class="bg-black/60 border border-white/10 rounded px-2 py-1 text-body-sm text-text-secondary focus:outline-none focus:border-primary font-mono chain-select" data-pdb="${e}">
                        ${i}
                    </select>
                </div>
                <button class="text-error hover:text-red-400 p-1 rounded hover:bg-white/5 transition-colors remove-pdb-btn" data-pdb="${e}">
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                </button>
            `,r.querySelector(`.chain-select`).addEventListener(`change`,t=>{this.onChainSelection(e,t.target.value)}),r.querySelector(`.remove-pdb-btn`).addEventListener(`click`,()=>{this.onRemovePDB(e)}),t.appendChild(r)})}getParameters(){return{removeWater:this.element.querySelector(`#param-remove-water`).checked,removeHeteroatoms:this.element.querySelector(`#param-remove-heteroatoms`).checked}}setAligning(e){let t=this.element.querySelector(`#overview-run-btn`);t&&(e?(t.disabled=!0,t.innerHTML=`
                <span class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                Aligning Pipeline...
            `):(t.disabled=!1,t.innerHTML=`
                <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Structural Alignment
            `))}},E=class{constructor(e){this.selectedPDBs=e.selectedPDBs||[],this.currentRunId=e.currentRunId,this.onResidueSelected=e.onResidueSelected,this.onLigandSelected=e.onLigandSelected,this.ligandsList=[],this.element=null,this.selectedLigandId=``}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-hidden`,e.id=`tab-ligands-container`,e.innerHTML=`
            <!-- Binding Site Description Card -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-3 shrink-0 bg-[#11141c]/50">
                <div class="flex justify-between items-center">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-[20px] text-gradient-end">science</span>
                        <h4 class="font-body-md text-body-md font-semibold text-text-primary">Ligand Inspector</h4>
                    </div>
                    <select id="ligand-select" class="bg-black/60 border border-white/10 rounded-lg text-body-sm text-text-primary py-1 px-2 focus:outline-none focus:border-gradient-end font-mono max-w-[200px]">
                        <option value="">No Ligands Loaded</option>
                    </select>
                </div>
                <div id="ligand-pocket-desc" class="font-body-sm text-body-sm text-text-secondary leading-relaxed mt-1">
                    Perform an alignment and select a ligand from the list to analyze atomic interactions in the binding pocket.
                </div>
                <div class="flex gap-3 mt-2">
                    <span id="ligand-volume-badge" class="px-2.5 py-1 rounded-md bg-secondary/10 text-secondary font-label-sm text-label-sm border border-secondary/20 hidden">Volume: -- Å³</span>
                    <span id="ligand-sasa-badge" class="px-2.5 py-1 rounded-md bg-gradient-start/10 text-primary-fixed-dim font-label-sm text-label-sm border border-gradient-start/20 hidden">SASA: -- Å²</span>
                </div>
            </div>
            <!-- Data Table -->
            <div class="glass-panel rounded-xl flex-grow flex flex-col overflow-hidden min-h-[200px] bg-[#11141c]/50">
                <div class="px-4 py-3 border-b border-white/10 table-header flex justify-between items-center bg-black/20">
                    <h4 class="font-label-md text-label-md text-text-secondary uppercase tracking-wider">Molecular Interactions</h4>
                    <span id="interaction-count" class="font-label-sm text-label-sm text-text-secondary">0 Found</span>
                </div>
                <div class="flex-grow overflow-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="sticky top-0 bg-[#12141a] border-b border-white/5 font-label-sm text-label-sm text-text-secondary z-10">
                        <tr>
                            <th class="px-4 py-3 font-medium">Residue</th>
                            <th class="px-3 py-3 font-medium">Chain</th>
                            <th class="px-3 py-3 font-medium text-right">Resi</th>
                            <th class="px-3 py-3 font-medium text-right">Dist (Å)</th>
                            <th class="px-4 py-3 font-medium">Type</th>
                        </tr>
                        </thead>
                        <tbody id="interactions-table-body" class="font-body-sm text-body-sm text-text-primary font-mono divide-y divide-white/5">
                            <tr>
                                <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                                    Select a ligand to populate interactions.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),this.populateDropdown(),e}setupEventListeners(){this.element.querySelector(`#ligand-select`).addEventListener(`change`,async e=>{let t=e.target.value;this.selectedLigandId=t,await this.loadInteractions(t)})}updateLigands(e,t){this.ligandsList=e||[],this.currentRunId=t,this.selectedLigandId=``,this.populateDropdown(),this.clearTable()}populateDropdown(){if(!this.element)return;let e=this.element.querySelector(`#ligand-select`);if(e.innerHTML=``,this.ligandsList.length===0){e.innerHTML=`<option value="">No Ligands Loaded</option>`;return}let t=document.createElement(`option`);t.value=``,t.innerText=`Select a Ligand`,e.appendChild(t),this.ligandsList.forEach(t=>{let n=document.createElement(`option`);n.value=t.id,n.innerText=`${t.name} (Chain ${t.chain}, Resi ${t.resi})`,this.selectedLigandId===t.id&&(n.selected=!0),e.appendChild(n)})}clearTable(){if(!this.element)return;let e=this.element.querySelector(`#ligand-pocket-desc`);e.innerText=`Perform an alignment and select a ligand from the list to analyze atomic interactions in the binding pocket.`,this.element.querySelector(`#ligand-volume-badge`).classList.add(`hidden`),this.element.querySelector(`#ligand-sasa-badge`).classList.add(`hidden`),this.element.querySelector(`#interaction-count`).innerText=`0 Found`,this.element.querySelector(`#interactions-table-body`).innerHTML=`
            <tr>
                <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                    Select a ligand to populate interactions.
                </td>
            </tr>
        `}async loadInteractions(e){if(!this.element)return;let t=this.element.querySelector(`#interactions-table-body`),n=this.element.querySelector(`#ligand-pocket-desc`),r=this.element.querySelector(`#interaction-count`),i=this.element.querySelector(`#ligand-volume-badge`),a=this.element.querySelector(`#ligand-sasa-badge`);if(!e){this.clearTable(),this.onLigandSelected(``);return}t.innerHTML=`
            <tr>
                <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Analyzing interactions...
                </td>
            </tr>
        `;try{let o=this.selectedPDBs[0],s=(await p(o,e,this.currentRunId)).interactions,c=s.interactions;this.onLigandSelected(e,c),n.innerText=`Conserved catalytic pocket near ligand ${s.ligand}. Stable hydrophobic cluster showing coordinated interactions.`,s.pocket_volume?(i.innerText=`Volume: ${s.pocket_volume.toFixed(1)} Å³`,i.classList.remove(`hidden`)):i.classList.add(`hidden`),s.pocket_sasa?(a.innerText=`SASA: ${s.pocket_sasa.toFixed(1)} Å²`,a.classList.remove(`hidden`)):a.classList.add(`hidden`),r.innerText=`${c.length} Found`,t.innerHTML=``,c.length===0?t.innerHTML=`
                    <tr>
                        <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                            No specific interaction contacts found.
                        </td>
                    </tr>
                `:c.forEach((e,n)=>{let r=document.createElement(`tr`);r.className=`hover:bg-white/5 transition-colors cursor-pointer group`;let i=`bg-gray-500/20 text-gray-300 border border-gray-500/30`;e.type.toLowerCase().includes(`h-bond`)?i=`bg-blue-500/20 text-blue-300 border border-blue-500/30`:e.type.toLowerCase().includes(`pi`)?i=`bg-purple-500/20 text-purple-300 border border-purple-500/30`:e.type.toLowerCase().includes(`salt`)?i=`bg-green-500/20 text-green-300 border border-green-500/30`:e.type.toLowerCase().includes(`metal`)&&(i=`bg-yellow-500/20 text-yellow-300 border border-yellow-500/30`),r.innerHTML=`
                        <td class="px-4 py-2.5">${e.resn||e.residue||`UNK`}</td>
                        <td class="px-3 py-2.5">${e.chain}</td>
                        <td class="px-3 py-2.5 text-right text-text-secondary group-hover:text-text-primary">${e.resi}</td>
                        <td class="px-3 py-2.5 text-right font-semibold">${e.distance.toFixed(1)}</td>
                        <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] ${i}">${e.type}</span></td>
                    `,r.addEventListener(`click`,()=>{this.element.querySelectorAll(`#interactions-table-body tr`).forEach(e=>{e.className=`hover:bg-white/5 transition-colors cursor-pointer group`,e.querySelectorAll(`td`).forEach(e=>e.classList.remove(`text-tertiary`,`font-bold`))}),r.className=`row-selected cursor-pointer group`,r.querySelectorAll(`td`).forEach(e=>e.classList.add(`text-tertiary`,`font-bold`)),this.onResidueSelected(e.chain,e.resi)}),t.appendChild(r)})}catch(e){console.error(`Failed to load interactions:`,e),t.innerHTML=`
                <tr>
                    <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                        Failed to calculate pocket site contacts.
                    </td>
                </tr>
            `}}},D=class{constructor(){this.currentRunId=null,this.element=null,this.stats={rmsd:null,aligned_length:null,seq_identity:null,seq_similarity:null}}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-sequence-container`,e.innerHTML=`
            <!-- Alignment Statistics Card -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-tertiary">analytics</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Alignment Report</h4>
                </div>
                <div id="alignment-stats-container" class="grid grid-cols-2 gap-4">
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">RMSD</span>
                        <span id="stat-rmsd" class="font-headline-sm text-headline-sm font-semibold text-success font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Aligned Length</span>
                        <span id="stat-length" class="font-headline-sm text-headline-sm font-semibold text-primary font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Seq Identity</span>
                        <span id="stat-identity" class="font-headline-sm text-headline-sm font-semibold text-secondary font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Seq Similarity</span>
                        <span id="stat-similarity" class="font-headline-sm text-headline-sm font-semibold text-tertiary font-mono">--</span>
                    </div>
                </div>
            </div>
            
            <!-- Dynamic Sequence Alignment Table -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 overflow-hidden">
                <div class="flex items-center gap-2 border-b border-white/10 pb-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">format_align_justify</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Sequence Alignment View</h4>
                </div>
                <div id="sequence-alignment-grid-wrapper" class="overflow-x-auto rounded-lg max-h-[350px]">
                    <div class="text-center py-8 text-text-secondary font-body-sm">
                        Run alignment to generate sequence view.
                    </div>
                </div>
            </div>

            <!-- Output Files -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-3 bg-[#11141c]/50">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-text-secondary">folder_zip</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Generated Outputs</h4>
                </div>
                <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between p-2.5 rounded bg-white/5 hover:bg-white/10 transition-colors">
                        <span class="font-body-sm text-body-sm text-text-primary font-mono">alignment.pdb</span>
                        <a id="download-pdb-link" href="#" target="_blank" class="text-secondary text-body-sm hover:underline flex items-center gap-1 opacity-55 pointer-events-none">
                            <span class="material-symbols-outlined text-[16px]">open_in_new</span> View PDB
                        </a>
                    </div>
                    <div class="flex items-center justify-between p-2.5 rounded bg-white/5 hover:bg-white/10 transition-colors">
                        <span class="font-body-sm text-body-sm text-text-primary font-mono">alignment.fasta</span>
                        <a id="download-fasta-link" href="#" target="_blank" class="text-secondary text-body-sm hover:underline flex items-center gap-1 opacity-55 pointer-events-none">
                            <span class="material-symbols-outlined text-[16px]">open_in_new</span> View FASTA
                        </a>
                    </div>
                    <div class="flex items-center justify-between p-2.5 rounded bg-white/5 hover:bg-white/10 transition-colors">
                        <span class="font-body-sm text-body-sm text-text-primary font-mono">mustang_report.pdf</span>
                        <a id="download-report-link" href="#" target="_blank" class="text-secondary text-body-sm hover:underline flex items-center gap-1 opacity-55 pointer-events-none">
                            <span class="material-symbols-outlined text-[16px]">open_in_new</span> Download PDF
                        </a>
                    </div>
                </div>
            </div>
        `,this.element=e,this.refreshStats(),e}updateResults(e,t){this.currentRunId=e,this.stats=t||{},this.refreshStats(),this.loadSequenceGrid()}refreshStats(){if(!this.element)return;let e=this.stats.rmsd==null?`--`:`${parseFloat(this.stats.rmsd).toFixed(2)} Å`,t=this.stats.aligned_length==null?`--`:this.stats.aligned_length,n=this.stats.seq_identity==null?`--`:`${parseFloat(this.stats.seq_identity).toFixed(1)}%`,r=this.stats.seq_similarity==null?`--`:`${parseFloat(this.stats.seq_similarity).toFixed(1)}%`;this.element.querySelector(`#stat-rmsd`).innerText=e,this.element.querySelector(`#stat-length`).innerText=t,this.element.querySelector(`#stat-identity`).innerText=n,this.element.querySelector(`#stat-similarity`).innerText=r;let i=this.element.querySelector(`#download-pdb-link`),a=this.element.querySelector(`#download-fasta-link`),o=this.element.querySelector(`#download-report-link`);this.currentRunId?(i.href=v(this.currentRunId),i.classList.remove(`opacity-55`,`pointer-events-none`),a.href=y(this.currentRunId),a.classList.remove(`opacity-55`,`pointer-events-none`),o.href=b(this.currentRunId),o.classList.remove(`opacity-55`,`pointer-events-none`)):(i.href=`#`,i.classList.add(`opacity-55`,`pointer-events-none`),a.href=`#`,a.classList.add(`opacity-55`,`pointer-events-none`),o.href=`#`,o.classList.add(`opacity-55`,`pointer-events-none`))}async loadSequenceGrid(){if(!this.element||!this.currentRunId)return;let e=this.element.querySelector(`#sequence-alignment-grid-wrapper`);e.innerHTML=`
            <div class="text-center py-8 text-text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Parsing sequence alignment...
            </div>
        `;try{let{sequences:t,conservation:n}=await _(this.currentRunId),r=``,i={identity:`#ff4757`,high_similarity:`#ffa502`,gap:`#2f3542`,default:`transparent`};Object.keys(t).forEach(e=>{let a=t[e],o=``;for(let e=0;e<a.length;e++){let t=a[e],r=n[e],s=i.default;t===`-`?s=i.gap:r===1?s=i.identity:r>.7&&(s=i.high_similarity),o+=`<td class="${r>.5||t===`-`?`res-val`:``} text-center font-mono border border-white/5" style="background-color: ${s}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;">${t}</td>`}r+=`
                    <tr class="border-b border-white/5">
                        <td class="sticky left-0 bg-[#161a24] text-text-primary pr-4 pl-2 font-bold font-mono border-r border-white/10 whitespace-nowrap min-w-[120px] text-body-sm">${e}</td>
                        ${o}
                    </tr>
                `});let a=``;n.forEach(e=>{let t=`&nbsp;`;e===1?t=`*`:e>.7?t=`:`:e>.5&&(t=`.`),a+=`<td class="text-center font-mono font-bold text-text-secondary" style="min-width: 22px; height: 20px;">${t}</td>`}),r+=`
                <tr class="bg-[#121316]/50">
                    <td class="sticky left-0 bg-[#121316] text-text-secondary pr-4 pl-2 font-bold font-mono border-r border-white/10 whitespace-nowrap min-w-[120px] text-body-sm">Consensus</td>
                    ${a}
                </tr>
            `,e.innerHTML=`
                <table class="w-full text-left border-collapse table-fixed">
                    <tbody>
                        ${r}
                    </tbody>
                </table>
            `}catch(t){console.error(`Failed to render sequence alignment viewer:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to parse alignment FASTA data.
                </div>
            `}}},O=class{constructor(){this.element=null,this.currentRunId=null,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsfValues=[]}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-analytics-container`,e.innerHTML=`
            <!-- Ramachandran / Quality Report -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">verified</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Structure Quality Report</h4>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Ramachandran Score</span>
                        <span id="ramachandran-score" class="font-headline-sm text-headline-sm font-semibold text-success font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Outlier Residues</span>
                        <span id="ramachandran-outliers" class="font-headline-sm text-headline-sm font-semibold text-error font-mono">--</span>
                    </div>
                </div>
                <div id="ramachandran-outliers-list-card" class="bg-black/20 border border-white/5 p-3 rounded-lg flex flex-col gap-1 hidden">
                    <span class="font-label-sm text-label-sm text-text-secondary uppercase">Top Outliers</span>
                    <div id="ramachandran-outliers-list" class="flex flex-wrap gap-1.5 mt-1">
                        <!-- Outlier badges -->
                    </div>
                </div>
            </div>

            <!-- Residue Fluctuation (Plotly Line Chart) -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0 min-h-[350px]">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">show_chart</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Residue Fluctuation (RMSF)</h4>
                </div>
                <div id="rmsf-plotly-chart" class="w-full h-[280px]">
                    <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                        Run alignment to display interactive RMSF chart.
                    </div>
                </div>
            </div>

            <!-- Pairwise RMSD Matrix (Plotly Heatmap) -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0 min-h-[350px]">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-gradient-end">grid_on</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Pairwise RMSD Matrix</h4>
                </div>
                <div id="rmsd-plotly-heatmap" class="w-full h-[280px]">
                    <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                        Run alignment to display interactive heatmap.
                    </div>
                </div>
            </div>

            <!-- Phylogenetic Tree (Plotly Dendrogram) -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0 min-h-[350px]">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-tertiary">account_tree</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Phylogenetic Tree (UPGMA)</h4>
                </div>
                <div id="phylo-plotly-tree" class="w-full h-[280px]">
                    <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                        Run alignment to display interactive dendrogram.
                    </div>
                </div>
            </div>
        `,this.element=e,this.renderVisuals(),e}updateResults(e,t,n,r,i){this.currentRunId=e,this.heatmapFig=t,this.treeFig=n,this.ramachandranStats=r,this.rmsfValues=i||[],this.renderVisuals()}renderVisuals(){if(!this.element)return;let e=this.element.querySelector(`#ramachandran-score`),t=this.element.querySelector(`#ramachandran-outliers`),n=this.element.querySelector(`#ramachandran-outliers-list-card`),r=this.element.querySelector(`#ramachandran-outliers-list`);this.ramachandranStats&&this.ramachandranStats.favored_percent!=null?(e.innerText=`${this.ramachandranStats.favored_percent.toFixed(1)}%`,t.innerText=this.ramachandranStats.outlier_count,this.ramachandranStats.outlier_count>0&&this.ramachandranStats.outliers_list&&this.ramachandranStats.outliers_list.length>0?(n.classList.remove(`hidden`),r.innerHTML=``,this.ramachandranStats.outliers_list.forEach(e=>{let t=document.createElement(`span`);t.className=`px-2 py-0.5 rounded bg-error/10 border border-error/20 text-error font-mono text-[10px]`,t.innerText=e,r.appendChild(t)})):n.classList.add(`hidden`)):(e.innerText=`--`,t.innerText=`--`,n.classList.add(`hidden`));let i=this.element.querySelector(`#rmsf-plotly-chart`);if(this.rmsfValues&&this.rmsfValues.length>0){i.innerHTML=``;let e={x:Array.from({length:this.rmsfValues.length},(e,t)=>t+1),y:this.rmsfValues,type:`scatter`,mode:`lines`,line:{color:`#8B5CF6`,width:2.5,shape:`spline`},fill:`tozeroy`,fillcolor:`rgba(139, 92, 246, 0.1)`,hoverinfo:`x+y`,name:`RMSF`};Plotly.newPlot(i,[e],{xaxis:{title:`Alignment Position`,gridcolor:`rgba(255,255,255,0.05)`,zeroline:!1},yaxis:{title:`RMSF (Å)`,gridcolor:`rgba(255,255,255,0.05)`,zeroline:!1},margin:{l:50,r:20,t:20,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,height:280,font:{family:`Inter, sans-serif`,size:10,color:`#8F9CAE`}},{responsive:!0,displayModeBar:!1})}else this.currentRunId&&(i.innerHTML=`
                <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                    No residue fluctuation data available.
                </div>
            `);let a=this.element.querySelector(`#rmsd-plotly-heatmap`);if(this.heatmapFig&&this.heatmapFig.data){a.innerHTML=``;let e={...this.heatmapFig.layout,width:void 0,height:280,margin:{l:50,r:20,t:30,b:50},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#8F9CAE`}};Plotly.newPlot(a,this.heatmapFig.data,e,{responsive:!0,displayModeBar:!1})}else this.currentRunId&&(a.innerHTML=`
                <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                    No pairwise heatmap figure available.
                </div>
            `);let o=this.element.querySelector(`#phylo-plotly-tree`);if(this.treeFig&&this.treeFig.data){o.innerHTML=``;let e={...this.treeFig.layout,width:void 0,height:280,margin:{l:60,r:20,t:30,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#8F9CAE`}};Plotly.newPlot(o,this.treeFig.data,e,{responsive:!0,displayModeBar:!1})}else this.currentRunId&&(o.innerHTML=`
                <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                    No phylogenetic tree figure available.
                </div>
            `)}},k=class{constructor(){this.rmsdDf=null,this.pdbMetadata={},this.threshold=3,this.element=null,this.debounceTimer=null}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-clusters-container`,e.innerHTML=`
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">workspaces</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Structural Clusters</h4>
                </div>
                <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-sm text-label-sm text-text-secondary">RMSD Threshold</span>
                        <span id="cluster-threshold-value" class="font-label-sm text-label-sm text-text-primary font-mono">3.00 Å</span>
                    </div>
                    <input id="cluster-threshold-slider" type="range" min="0.1" max="10.0" step="0.1" value="3.0"
                        class="w-full h-1.5 rounded-lg appearance-none bg-white/10 accent-primary cursor-pointer" />
                    <span class="font-body-sm text-body-sm text-text-secondary">
                        Structures with RMSD lower than this cutoff are grouped into the same family.
                    </span>
                </div>
            </div>

            <div id="clusters-list-container" class="flex flex-col gap-3">
                <div class="text-center py-8 text-text-secondary font-body-sm">
                    Run alignment to identify structural clusters.
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),e}setupEventListeners(){this.element.querySelector(`#cluster-threshold-slider`).addEventListener(`input`,e=>{this.threshold=parseFloat(e.target.value),this.element.querySelector(`#cluster-threshold-value`).innerText=`${this.threshold.toFixed(2)} Å`,clearTimeout(this.debounceTimer),this.debounceTimer=setTimeout(()=>this.loadClusters(),250)})}updateResults(e,t){this.rmsdDf=e,this.pdbMetadata=t||{},this.loadClusters()}async loadClusters(){if(!this.element)return;let e=this.element.querySelector(`#clusters-list-container`);if(!this.rmsdDf){e.innerHTML=`
                <div class="text-center py-8 text-text-secondary font-body-sm">
                    Run alignment to identify structural clusters.
                </div>
            `;return}try{let e=await l(this.rmsdDf,this.threshold);this.renderClusters(e.clusters)}catch(t){console.error(`Failed to compute structural clusters:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to compute structural clusters.
                </div>
            `}}renderClusters(e){let t=this.element.querySelector(`#clusters-list-container`);if(!e||e.length===0){t.innerHTML=`
                <div class="text-center py-8 text-text-secondary font-body-sm">
                    No clusters identified with current settings.
                </div>
            `;return}t.innerHTML=e.map(e=>{let t=e.members.map(e=>`
                    <div class="flex items-center justify-between px-3 py-1.5 rounded bg-black/20 border border-white/5">
                        <span class="font-mono text-body-sm text-text-primary">${e}</span>
                        <span class="text-body-sm text-text-secondary truncate ml-2">${this.pdbMetadata[e]&&this.pdbMetadata[e].title||`Unknown Title`}</span>
                    </div>
                `).join(``);return`
                <div class="glass-panel rounded-xl p-4 flex flex-col gap-2 bg-[#11141c]/50">
                    <div class="flex items-center justify-between">
                        <span class="font-body-md text-body-md font-semibold text-text-primary">
                            📁 Cluster ${e.cluster_id} (${e.members.length} members)
                        </span>
                        <span class="font-label-sm text-label-sm text-text-secondary font-mono">
                            Avg RMSD: ${e.avg_rmsd.toFixed(2)} Å
                        </span>
                    </div>
                    <div class="flex flex-col gap-1">
                        ${t}
                    </div>
                </div>
            `}).join(``)}},A=class{constructor(){this.currentRunId=null,this.pastRuns=[],this.targetRunId=null,this.element=null}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col gap-4 overflow-y-auto pr-1`,e.id=`tab-comparison-container`,e.innerHTML=`
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">compare_arrows</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Batch Comparison</h4>
                </div>
                <span class="font-body-sm text-body-sm text-text-secondary">
                    Compare this run's RMSD matrix against a past run to see how structural relationships shifted.
                </span>
                <div id="comparison-controls" class="flex flex-col gap-2">
                    <div class="text-center py-4 text-text-secondary font-body-sm">
                        Run an alignment to enable comparison.
                    </div>
                </div>
            </div>

            <div id="comparison-results-container" class="flex flex-col gap-4"></div>
        `,this.element=e,e}async updateResults(e){if(this.currentRunId=e,this.targetRunId=null,this.element&&(this.element.querySelector(`#comparison-results-container`).innerHTML=``),!e){this.renderControls();return}try{let t=await u(e);this.pastRuns=t.runs||[]}catch(e){console.error(`Failed to load comparison run list:`,e),this.pastRuns=[]}this.renderControls()}renderControls(){if(!this.element)return;let e=this.element.querySelector(`#comparison-controls`);if(!this.currentRunId){e.innerHTML=`
                <div class="text-center py-4 text-text-secondary font-body-sm">
                    Run an alignment to enable comparison.
                </div>
            `;return}if(this.pastRuns.length===0){e.innerHTML=`
                <div class="text-center py-4 text-text-secondary font-body-sm">
                    No other past runs found for comparison.
                </div>
            `;return}e.innerHTML=`
            <select id="comparison-target-select" class="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 font-body-sm text-text-primary">
                ${this.pastRuns.map(e=>`
                    <option value="${e.id}">${e.timestamp} - ${e.id.slice(0,8)}... (${e.proteins.length} p)</option>
                `).join(``)}
            </select>
            <button id="btn-run-comparison" class="w-full py-2 px-3 rounded-lg bg-primary/20 border border-primary/40 text-primary font-label-md text-label-md hover:bg-primary/30 transition-colors">
                🚀 Run Comparative Analysis
            </button>
        `,this.targetRunId=this.pastRuns[0].id,e.querySelector(`#comparison-target-select`).addEventListener(`change`,e=>{this.targetRunId=e.target.value}),e.querySelector(`#btn-run-comparison`).addEventListener(`click`,()=>this.runComparison())}async runComparison(){if(!this.currentRunId||!this.targetRunId)return;let e=this.element.querySelector(`#comparison-results-container`);e.innerHTML=`
            <div class="text-center py-8 text-text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Calculating differences...
            </div>
        `;try{let e=await d(this.currentRunId,this.targetRunId);this.renderComparisonResults(e)}catch(t){console.error(`Batch comparison failed:`,t),e.innerHTML=`
                <div class="text-center py-8 text-error font-body-sm">
                    ${t.message||`No overlapping proteins found between these runs.`}
                </div>
            `}}renderComparisonResults(e){let t=this.element.querySelector(`#comparison-results-container`);t.innerHTML=`
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-3 bg-[#11141c]/50">
                <h4 class="font-body-md text-body-md font-semibold text-text-primary">RMSD Difference Matrix (ΔRMSD)</h4>
                <span class="font-body-sm text-body-sm text-text-secondary">
                    Positive values indicate increased divergence in the current run compared to the target.
                </span>
                <div id="comparison-diff-heatmap" class="w-full h-[280px]"></div>
            </div>
            <div class="glass-panel rounded-xl p-5 grid grid-cols-3 gap-4 bg-[#11141c]/50">
                <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                    <span class="font-label-sm text-label-sm text-text-secondary">Mean RMSD Shift</span>
                    <span class="font-headline-sm text-headline-sm font-semibold ${e.mean_rmsd_shift>=0?`text-error`:`text-success`} font-mono">${e.mean_rmsd_shift.toFixed(3)} Å</span>
                </div>
                <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                    <span class="font-label-sm text-label-sm text-text-secondary">Current Mean</span>
                    <span class="font-headline-sm text-headline-sm font-semibold text-text-primary font-mono">${e.current_mean_rmsd.toFixed(3)} Å</span>
                </div>
                <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                    <span class="font-label-sm text-label-sm text-text-secondary">Target Mean</span>
                    <span class="font-headline-sm text-headline-sm font-semibold text-text-primary font-mono">${e.target_mean_rmsd.toFixed(3)} Å</span>
                </div>
            </div>
        `;let n=t.querySelector(`#comparison-diff-heatmap`),r=e.diff,i={z:r.data,x:r.columns,y:r.index,type:`heatmap`,colorscale:`RdBu`,zmid:0};if(Plotly.newPlot(n,[i],{margin:{l:60,r:20,t:10,b:40},paper_bgcolor:`rgba(0,0,0,0)`,plot_bgcolor:`rgba(0,0,0,0)`,font:{family:`Inter, sans-serif`,size:10,color:`#8F9CAE`}},{responsive:!0,displayModeBar:!1}),r.data.every(e=>e.every(e=>e===0))){let e=document.createElement(`div`);e.className=`text-center py-2 text-success font-body-sm`,e.innerText=`✨ Perfect Consensus: overlapping proteins are structurally identical in both runs.`,t.appendChild(e)}}},j=class{constructor(e){this.onReloadRun=e.onReloadRun,this.onClose=e.onClose,this.element=null,this.runsList=[]}render(){let e=document.createElement(`div`);return e.className=`flex-grow flex flex-col h-full overflow-hidden p-5`,e.innerHTML=`
            <!-- Panel Header -->
            <div class="flex justify-between items-center border-b border-white/10 pb-3 mb-4 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[24px] text-secondary">history</span>
                    <h3 class="font-headline-sm text-headline-sm font-semibold text-text-primary">Session History</h3>
                </div>
                <button id="close-history-btn" class="p-1 rounded hover:bg-white/5 text-text-secondary hover:text-text-primary transition-colors">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <!-- Runs list container -->
            <div id="history-runs-list" class="flex-grow overflow-y-auto flex flex-col gap-3">
                <div class="text-center py-12 text-text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[24px] mb-2">sync</span>
                    Loading run logs...
                </div>
            </div>
        `,this.element=e,this.setupEventListeners(),this.loadHistoryData(),e}setupEventListeners(){this.element.querySelector(`#close-history-btn`).addEventListener(`click`,()=>{this.onClose&&this.onClose()})}async loadHistoryData(){let e=this.element.querySelector(`#history-runs-list`);try{let t=await g();if(this.runsList=t.runs||[],e.innerHTML=``,this.runsList.length===0){e.innerHTML=`
                    <div class="text-center py-12 text-text-secondary font-body-sm">
                        No past alignment sessions found.
                    </div>
                `;return}this.runsList.forEach(t=>{let n=document.createElement(`div`);n.className=`glass-panel p-4 rounded-lg bg-[#11141c]/50 hover:bg-[#11141c]/80 border border-white/5 hover:border-secondary/40 transition-all cursor-pointer flex flex-col gap-2 group`;let r=[];try{r=typeof t.pdb_ids==`string`?JSON.parse(t.pdb_ids):t.pdb_ids}catch{r=[t.pdb_ids]}let i=t.timestamp;try{let e=new Date(t.timestamp);isNaN(e.getTime())||(i=e.toLocaleString())}catch{}n.innerHTML=`
                    <div class="flex justify-between items-center">
                        <span class="font-body-sm font-bold text-text-primary group-hover:text-secondary font-mono">${t.id}</span>
                        <span class="font-label-sm text-[10px] text-text-secondary">${i}</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <div class="flex gap-1">
                            ${r.map(e=>`<span class="px-1.5 py-0.5 rounded bg-black/40 text-[#fff] border border-white/10 font-mono text-[10px]">${e}</span>`).join(``)}
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] bg-success/20 text-success border border-success/30 font-medium capitalize">${t.status||`success`}</span>
                    </div>
                `,n.addEventListener(`click`,()=>{this.onReloadRun(t)}),e.appendChild(n)})}catch(t){console.error(`Failed to load history data:`,t),e.innerHTML=`
                <div class="text-center py-12 text-error font-body-sm">
                    Failed to retrieve session history log.
                </div>
            `}}};new class{constructor(){this.selectedPDBs=[`4RLT`,`3UG9`],this.chainSelections={"4RLT":`A`,"3UG9":`A`},this.pdbMetadata={},this.currentRunId=null,this.activeView=`dashboard`,this.activeTab=`overview`,this.currentLigands=[],this.isAligning=!1,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsdDf=null,this.topNav=new x({onAddPDB:e=>this.addPDB(e),onRunAlignment:()=>this.executeAlignment(),onExportData:()=>this.exportData()}),this.sidebar=new S({onNavigate:e=>this.navigateView(e),onNewWorkspace:()=>this.resetWorkspace()}),this.viewer3D=new C,this.tabPanel=new w({onTabChange:e=>this.switchTab(e)}),this.overviewTab=new T({selectedPDBs:this.selectedPDBs,chainSelections:this.chainSelections,pdbMetadata:this.pdbMetadata,onAddPDB:e=>this.addPDB(e),onRemovePDB:e=>this.removePDB(e),onChainSelection:(e,t)=>{this.chainSelections[e]=t},onRunAlignment:()=>this.executeAlignment()}),this.ligandTab=new E({selectedPDBs:this.selectedPDBs,currentRunId:this.currentRunId,onLigandSelected:(e,t)=>{e?this.viewer3D.showLigandBindingSite(e,t):this.viewer3D.resetCartoonStyles()},onResidueSelected:(e,t)=>{this.viewer3D.highlightResidue(e,t)}}),this.sequenceTab=new D,this.analyticsTab=new O,this.clustersTab=new k,this.comparisonTab=new A,this.historyPanel=new j({onReloadRun:e=>this.reloadPastRun(e),onClose:()=>this.navigateView(`dashboard`)})}render(e){e.innerHTML=``;let t=document.createElement(`div`);t.className=`flex flex-col h-screen overflow-hidden bg-[#08090C] text-[#e3e2e6]`,t.appendChild(this.topNav.render());let n=document.createElement(`div`);n.className=`flex flex-1 overflow-hidden`,n.appendChild(this.sidebar.render());let r=document.createElement(`main`);r.className=`flex-grow flex flex-col md:flex-row h-full overflow-hidden p-6 gap-6 max-w-7xl mx-auto w-full`,r.appendChild(this.viewer3D.render());let i=document.createElement(`div`);i.className=`w-full md:w-[400px] lg:w-[480px] flex flex-col gap-4 shrink-0 overflow-hidden`,i.id=`dashboard-right-pane`,r.appendChild(i),n.appendChild(r),t.appendChild(n),e.appendChild(t),this.viewer3D.init3Dmol(),this.updateRightPaneDisplay(),this.loadChainsMetadata()}updateRightPaneDisplay(){let e=document.getElementById(`dashboard-right-pane`);if(e)if(e.innerHTML=``,this.activeView===`history`)e.appendChild(this.historyPanel.render());else{e.appendChild(this.tabPanel.render());let t=document.createElement(`div`);t.className=`flex-grow flex flex-col gap-4 overflow-hidden`,t.id=`tab-content-container`,e.appendChild(t),this.activeTab===`overview`?t.appendChild(this.overviewTab.render()):this.activeTab===`ligands`?(t.appendChild(this.ligandTab.render()),this.ligandTab.updateLigands(this.currentLigands,this.currentRunId,this.selectedPDBs)):this.activeTab===`sequence`?(t.appendChild(this.sequenceTab.render()),this.sequenceTab.updateResults(this.currentRunId,this.sequenceTab.stats)):this.activeTab===`analytics`?(t.appendChild(this.analyticsTab.render()),this.analyticsTab.updateResults(this.currentRunId,this.heatmapFig,this.treeFig,this.ramachandranStats,this.analyticsTab.rmsfValues)):this.activeTab===`clusters`?(t.appendChild(this.clustersTab.render()),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata)):this.activeTab===`comparison`&&(t.appendChild(this.comparisonTab.render()),this.comparisonTab.updateResults(this.currentRunId))}}navigateView(e){this.activeView=e,this.updateRightPaneDisplay()}switchTab(e){this.activeTab=e,this.tabPanel.switchTab(e),this.updateRightPaneDisplay()}async loadChainsMetadata(){if(this.selectedPDBs.length!==0){this.overviewTab.setLoadingChains(!0);try{let e=await a(this.selectedPDBs);Object.keys(e.chains).forEach(t=>{this.pdbMetadata[t]=e.chains[t],e.chains[t].chains&&e.chains[t].chains.length>0&&(this.chainSelections[t]||(this.chainSelections[t]=e.chains[t].chains[0].id))}),this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata)}catch(e){console.error(`Failed to load chain selection data:`,e)}finally{this.overviewTab.setLoadingChains(!1)}}}async addPDB(e){e=e.toUpperCase().trim(),e.length===4&&(this.selectedPDBs.includes(e)||(this.selectedPDBs.push(e),this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),await this.loadChainsMetadata()))}removePDB(e){this.selectedPDBs=this.selectedPDBs.filter(t=>t!==e),delete this.chainSelections[e],this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata)}async executeAlignment(){if(this.selectedPDBs.length<2){alert(`At least 2 PDB structures are required for structural alignment.`);return}this.setAligningState(!0);let e=this.overviewTab.getParameters();try{let t=await c((await o(this.selectedPDBs,this.chainSelections,e.removeWater,e.removeHeteroatoms)).job_id);if(t.status===`failed`)throw Error(t.error||`Alignment pipeline failed.`);let n=t.results;this.currentRunId=n.id,this.heatmapFig=n.heatmap_fig,this.treeFig=n.tree_fig,this.ramachandranStats=n.ramachandran_stats,this.rmsdDf=n.rmsd_df;let r=this.selectedPDBs[0],i=this.selectedPDBs[1];await this.viewer3D.loadSuperposition(n.id,r,i,this.chainSelections[r],this.chainSelections[i],n.stats.rmsd),this.currentLigands=[];let a=await f(r,n.id);this.currentLigands=a.ligands||[],this.ligandTab.updateLigands(this.currentLigands,n.id,this.selectedPDBs),this.sequenceTab.updateResults(n.id,n.stats),this.analyticsTab.updateResults(n.id,this.heatmapFig,this.treeFig,this.ramachandranStats,n.rmsf_values),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata),this.switchTab(`sequence`)}catch(e){console.error(`Alignment run failed:`,e),alert(`Alignment pipeline failed: ${e.message}`)}finally{this.setAligningState(!1)}}setAligningState(e){this.isAligning=e,this.topNav.setAligning(e),this.overviewTab.setAligning(e)}async reloadPastRun(e){this.activeView=`dashboard`,this.activeTab=`sequence`,this.currentRunId=e.id;let t=[];try{t=typeof e.pdb_ids==`string`?JSON.parse(e.pdb_ids):e.pdb_ids}catch{t=[e.pdb_ids]}this.selectedPDBs=t;let n={};try{n=typeof e.metadata==`string`?JSON.parse(e.metadata):e.metadata}catch{}this.chainSelections=n.chain_selection||{};let r={};n.results?(r=n.results.stats||{},this.heatmapFig=n.results.heatmap_fig||null,this.treeFig=n.results.tree_fig||null,this.ramachandranStats=n.results.ramachandran_stats||null,this.rmsdDf=n.results.rmsd_df||null):(r=n.stats||{},this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsdDf=null);let i=r.rmsd||0;this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.updateRightPaneDisplay();let a=this.selectedPDBs[0],o=this.selectedPDBs[1];await this.viewer3D.loadSuperposition(e.id,a,o,this.chainSelections[a]||`A`,this.chainSelections[o]||`A`,i),this.loadChainsMetadata(),this.currentLigands=[];try{let t=await f(a,e.id);this.currentLigands=t.ligands||[]}catch(e){console.error(`Failed to load ligands for past run:`,e)}this.ligandTab.updateLigands(this.currentLigands,e.id,this.selectedPDBs),this.sequenceTab.updateResults(e.id,r),this.analyticsTab.updateResults(e.id,this.heatmapFig,this.treeFig,this.ramachandranStats,n.results?n.results.rmsf_values:null),this.clustersTab.updateResults(this.rmsdDf,this.pdbMetadata),this.switchTab(`sequence`)}resetWorkspace(){confirm(`Reset current workspace and clear selected structures?`)&&(this.selectedPDBs=[`4RLT`,`3UG9`],this.chainSelections={"4RLT":`A`,"3UG9":`A`},this.currentRunId=null,this.currentLigands=[],this.activeTab=`overview`,this.heatmapFig=null,this.treeFig=null,this.ramachandranStats=null,this.rmsdDf=null,this.overviewTab.updateState(this.selectedPDBs,this.chainSelections,this.pdbMetadata),this.ligandTab.updateLigands([],null,this.selectedPDBs),this.sequenceTab.updateResults(null,null),this.analyticsTab.updateResults(null,null,null,null),this.clustersTab.updateResults(null,null),this.comparisonTab.updateResults(null),this.viewer3D.resetCartoonStyles(),document.getElementById(`ambient-placeholder`).style.display=`flex`,document.getElementById(`hud-reference-label`).innerText=`Reference: --`,document.getElementById(`hud-target-label`).innerText=`Target: --`,document.getElementById(`rmsd-value-hud`).innerText=`-- Å`,this.switchTab(`overview`))}exportData(){if(!this.currentRunId){alert(`No active alignment result to export.`);return}window.open(b(this.currentRunId),`_blank`)}}().render(document.getElementById(`app`));