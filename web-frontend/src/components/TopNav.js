import { fetchSuggestions } from '../api';

export class TopNav {
    constructor(props) {
        this.onAddPDB = props.onAddPDB;
        this.onRunAlignment = props.onRunAlignment;
        this.onExportData = props.onExportData;
        this.element = null;
        this.suggestTimeout = null;
    }

    render() {
        const header = document.createElement('header');
        header.className = "flex items-center justify-between px-6 w-full sticky top-0 z-50 bg-surface/70 backdrop-blur-xl h-16 border-b border-white/10 shadow-sm shrink-0 glass-panel";
        header.innerHTML = `
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
        `;

        this.element = header;
        this.setupEventListeners();
        return header;
    }

    setupEventListeners() {
        const searchInput = this.element.querySelector('#search-input');
        const suggestionsContainer = this.element.querySelector('#search-suggestions-container');
        const runBtn = this.element.querySelector('#header-run-btn');
        const exportBtn = this.element.querySelector('#header-export-btn');

        // Suggestions logic
        const renderSuggestions = (list) => {
            suggestionsContainer.innerHTML = "";
            const defaultSuggestions = ["4RLT", "1L2Y", "3UG9"];
            const items = (list && list.length > 0) ? list.slice(0, 4) : defaultSuggestions;
            
            items.forEach(item => {
                const span = document.createElement('span');
                span.className = "px-2 py-0.5 rounded-full bg-surface-variant border border-white/10 font-label-sm text-label-sm text-text-secondary cursor-pointer hover:bg-surface-variant/80 transition-colors suggestion-pill";
                span.innerText = item;
                span.addEventListener('click', () => {
                    this.onAddPDB(item);
                    searchInput.value = "";
                    renderSuggestions([]);
                });
                suggestionsContainer.appendChild(span);
            });
        };

        searchInput.addEventListener('input', () => {
            clearTimeout(this.suggestTimeout);
            const q = searchInput.value.trim();
            if (q.length < 1) {
                renderSuggestions([]);
                return;
            }
            this.suggestTimeout = setTimeout(async () => {
                try {
                    const data = await fetchSuggestions(q);
                    renderSuggestions(data.suggestions);
                } catch (err) {
                    console.error("Autocomplete suggestions failed:", err);
                }
            }, 300);
        });

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const q = searchInput.value.trim().toUpperCase();
                if (q.length === 4) {
                    this.onAddPDB(q);
                    searchInput.value = "";
                    renderSuggestions([]);
                }
            }
        });

        // Initialize defaults
        renderSuggestions([]);

        runBtn.addEventListener('click', () => this.onRunAlignment());
        exportBtn.addEventListener('click', () => this.onExportData());
    }

    setAligning(isAligning) {
        const runBtn = this.element.querySelector('#header-run-btn');
        if (!runBtn) return;
        if (isAligning) {
            runBtn.disabled = true;
            runBtn.innerHTML = `
                <span class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                Aligning...
            `;
        } else {
            runBtn.disabled = false;
            runBtn.innerHTML = `
                <span class="material-symbols-outlined text-[16px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Alignment
            `;
        }
    }
}
