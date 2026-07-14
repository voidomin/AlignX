// Shared between LigandTab.js (Compare-mode ligand contacts + chain-chain
// interface contacts) and DiscoverTab.js's single-structure ligand
// inspector - all three call sites render the exact same contact-row shape
// (residue/chain/resi/distance/type), classified by the same real geometry
// (interaction_geometry.py's classify_contact).

// Functional data-encoding: dot color signals interaction type. Matches the
// 5 real classifications LigandAnalyzer/InterfaceAnalyzer actually emit -
// not a guess at possible labels, since PDB files carry no hydrogens/bond-
// order data, so pi-stacking still isn't attempted (see
// interaction_geometry.py). Metal Coordination (v3.87.0) is the one
// exception to that - a bare recognized metal-ion ligand gets real
// coordination-geometry classification now that ligand_analyzer.py no
// longer filters metals out as noise.
export function dotColorForType(type) {
    switch (type) {
        case 'Hydrogen Bond': return 'bg-accent';
        case 'Salt Bridge': return 'bg-success';
        case 'Van der Waals': return 'bg-muted';
        case 'Metal Coordination': return 'bg-error';
        default: return 'bg-secondary';
    }
}

export function buildContactRow(item) {
    const tr = document.createElement('tr');
    const resn = item.resn || item.residue || "UNK";
    tr.innerHTML = `
        <td class="px-0 py-2.5">${resn}</td>
        <td class="px-3 py-2.5">${item.chain}</td>
        <td class="px-3 py-2.5 text-right text-secondary group-hover:text-primary">${item.resi}</td>
        <td class="px-3 py-2.5 text-right font-semibold">${item.distance.toFixed(1)}</td>
        <td class="px-3 py-2.5"><span class="inline-flex items-center gap-1.5 text-secondary"><span class="w-1.5 h-1.5 rounded-full ${dotColorForType(item.type)}"></span>${item.type}</span></td>
    `;
    return tr;
}
