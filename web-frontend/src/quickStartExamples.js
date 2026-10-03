// Curated example structure sets, shared by the Dashboard tab, the
// Workspace tab's empty state, and the Showcase demo cards.
// Each example provides educational context so beginners understand
// what biological question is being answered.
export const QUICK_START_EXAMPLES = [
    {
        label: 'Hemoglobin variants',
        pdbIds: ['4HHB', '2HHB'],
        tag: 'Genetic Mutation',
        icon: 'bloodtype',
        description: 'See how a single amino acid substitution alters oxygen-carrying hemoglobin in human blood.'
    },
    {
        label: 'Kinase family',
        pdbIds: ['1ATP', '1CDK'],
        tag: 'Drug Discovery',
        icon: 'medication',
        description: 'Discover how cancer drug targets switch shapes between active and inactive conformations.'
    },
    {
        label: 'Trp-cage + AlphaFold',
        pdbIds: ['1L2Y', 'AF-P69905-F1'],
        tag: 'AI vs Wet Lab',
        icon: 'smart_toy',
        description: 'Compare an experimental NMR-solved miniprotein against DeepMind AlphaFold predicted coordinates.'
    },
    {
        label: 'COVID-19 Spike RBD',
        pdbIds: ['7KRR', '7V76'],
        tag: 'Viral Evolution',
        icon: 'coronavirus',
        description: 'Compare how viral receptor-binding domain mutations reshape the spike to evade antibody defenses.'
    }
];
