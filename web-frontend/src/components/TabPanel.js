export class TabPanel {
    constructor(props) {
        this.onTabChange = props.onTabChange;
        this.activeTab = 'overview';
        this.element = null;
    }

    render() {
        const div = document.createElement('div');
        div.className = "glass-panel rounded-xl p-1.5 flex gap-1";
        div.innerHTML = `
            <button id="btn-tab-overview" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Overview</button>
            <button id="btn-tab-ligands" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Ligands</button>
            <button id="btn-tab-sequence" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Sequence</button>
            <button id="btn-tab-analytics" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Analytics</button>
            <button id="btn-tab-clusters" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Clusters</button>
            <button id="btn-tab-comparison" class="tab-trigger flex-grow py-2 px-3 rounded-lg font-label-md text-label-md transition-colors">Compare</button>
        `;
        this.element = div;
        this.updateTabStyles();
        this.setupEventListeners();
        return div;
    }

    setupEventListeners() {
        const triggers = {
            'overview': this.element.querySelector('#btn-tab-overview'),
            'ligands': this.element.querySelector('#btn-tab-ligands'),
            'sequence': this.element.querySelector('#btn-tab-sequence'),
            'analytics': this.element.querySelector('#btn-tab-analytics'),
            'clusters': this.element.querySelector('#btn-tab-clusters'),
            'comparison': this.element.querySelector('#btn-tab-comparison')
        };

        Object.keys(triggers).forEach(tab => {
            triggers[tab].addEventListener('click', () => {
                this.activeTab = tab;
                this.updateTabStyles();
                this.onTabChange(tab);
            });
        });
    }

    updateTabStyles() {
        const triggers = {
            'overview': this.element.querySelector('#btn-tab-overview'),
            'ligands': this.element.querySelector('#btn-tab-ligands'),
            'sequence': this.element.querySelector('#btn-tab-sequence'),
            'analytics': this.element.querySelector('#btn-tab-analytics'),
            'clusters': this.element.querySelector('#btn-tab-clusters'),
            'comparison': this.element.querySelector('#btn-tab-comparison')
        };

        Object.keys(triggers).forEach(tab => {
            const btn = triggers[tab];
            if (!btn) return;
            if (tab === this.activeTab) {
                btn.className = "flex-grow py-2 px-3 rounded-lg bg-white/10 border border-white/5 font-label-md text-label-md text-text-primary shadow-sm";
            } else {
                btn.className = "flex-grow py-2 px-3 rounded-lg font-label-md text-label-md text-text-secondary hover:text-text-primary hover:bg-white/5 transition-colors";
            }
        });
    }

    switchTab(tab) {
        this.activeTab = tab;
        this.updateTabStyles();
    }
}
