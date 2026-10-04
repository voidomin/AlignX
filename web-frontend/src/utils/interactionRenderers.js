// Used by LigandTab.js for both its ligand-contact and chain-chain
// interface-contact tables - both call sites render the exact same
// contact-row shape (residue/chain/resi/distance/type), classified by the
// same real geometry (interaction_geometry.py's classify_contact).

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

const HYDROPHOBIC_RESIDUES = new Set(['ALA', 'VAL', 'LEU', 'ILE', 'MET', 'PHE', 'TRP', 'PRO']);
const POSITIVE_RESIDUES = new Set(['ARG', 'LYS', 'HIS']);
const NEGATIVE_RESIDUES = new Set(['ASP', 'GLU']);
const POLAR_RESIDUES = new Set(['SER', 'THR', 'ASN', 'GLN', 'TYR', 'CYS']);

export function isHydrophobicResidue(resn) {
    return HYDROPHOBIC_RESIDUES.has((resn || '').toUpperCase());
}

export function getResidueChargeColor(resn) {
    const r = (resn || '').toUpperCase();
    if (POSITIVE_RESIDUES.has(r)) return '#3B82F6'; // Blue
    if (NEGATIVE_RESIDUES.has(r)) return '#EF4444'; // Red
    if (POLAR_RESIDUES.has(r)) return '#10B981';    // Emerald / Green
    return '#9CA3AF';                              // Gray / Nonpolar
}

export function getResidueHydrophobicityColor(resn) {
    return isHydrophobicResidue(resn) ? '#EAB308' : '#06B6D4'; // Amber vs Cyan
}

export function render2DInteractionMap(containerEl, ligandName, contacts, onResidueClick) {
    if (!containerEl) return;
    containerEl.innerHTML = '';

    if (!contacts || contacts.length === 0) {
        containerEl.innerHTML = `
            <div class="text-center py-6 text-secondary font-body-sm">
                No contacts available to map in 2D.
            </div>
        `;
        return;
    }

    const width = 500;
    const height = 300;
    const cx = width / 2;
    const cy = height / 2;

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('class', 'w-full h-auto max-h-[320px] rounded-lg bg-surface-raised border border-border p-2');

    // Central Ligand Group
    const centerGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    
    const centerCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    centerCircle.setAttribute('cx', cx);
    centerCircle.setAttribute('cy', cy);
    centerCircle.setAttribute('r', '26');
    centerCircle.setAttribute('fill', '#111827');
    centerCircle.setAttribute('stroke', '#38BDF8');
    centerCircle.setAttribute('stroke-width', '2.5');
    centerGroup.appendChild(centerCircle);

    const centerText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    centerText.setAttribute('x', cx);
    centerText.setAttribute('y', cy + 4);
    centerText.setAttribute('text-anchor', 'middle');
    centerText.setAttribute('fill', '#F3F4F6');
    centerText.setAttribute('font-family', 'monospace');
    centerText.setAttribute('font-size', '11');
    centerText.setAttribute('font-weight', 'bold');
    const displayCode = (ligandName || 'LIG').split('_')[0];
    centerText.textContent = displayCode.length > 5 ? displayCode.slice(0, 5) : displayCode;
    centerGroup.appendChild(centerText);

    // Limit radial contacts to top 14 to fit cleanly without overlap
    const visibleContacts = contacts.slice(0, 14);
    const count = visibleContacts.length;
    const rx = 180;
    const ry = 100;

    const linesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');

    visibleContacts.forEach((item, i) => {
        const angle = (2 * Math.PI * i) / count - Math.PI / 2;
        const nx = cx + rx * Math.cos(angle);
        const ny = cy + ry * Math.sin(angle);

        // Link line
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', cx);
        line.setAttribute('y1', cy);
        line.setAttribute('x2', nx);
        line.setAttribute('y2', ny);

        let strokeColor = '#94A3B8';
        let dashArray = 'none';

        if (item.type === 'Hydrogen Bond') {
            strokeColor = '#38BDF8'; // Cyan accent
            dashArray = '4 3';
        } else if (item.type === 'Salt Bridge') {
            strokeColor = '#22C55E'; // Green
        } else if (item.type === 'Metal Coordination') {
            strokeColor = '#EF4444'; // Red
        } else {
            strokeColor = '#64748B'; // Muted
            dashArray = '2 2';
        }

        line.setAttribute('stroke', strokeColor);
        line.setAttribute('stroke-width', '1.75');
        if (dashArray !== 'none') {
            line.setAttribute('stroke-dasharray', dashArray);
        }
        linesGroup.appendChild(line);

        // Distance label at mid-line
        const mx = (cx + nx) / 2;
        const my = (cy + ny) / 2;
        const distText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        distText.setAttribute('x', mx);
        distText.setAttribute('y', my);
        distText.setAttribute('text-anchor', 'middle');
        distText.setAttribute('fill', '#94A3B8');
        distText.setAttribute('font-family', 'sans-serif');
        distText.setAttribute('font-size', '9');
        distText.textContent = `${item.distance.toFixed(1)}Å`;
        linesGroup.appendChild(distText);

        // Residue Node Group
        const resNode = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        resNode.setAttribute('class', 'cursor-pointer group');
        resNode.setAttribute('data-resi', item.resi);

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', nx);
        circle.setAttribute('cy', ny);
        circle.setAttribute('r', '17');
        circle.setAttribute('fill', '#1E293B');
        circle.setAttribute('stroke', strokeColor);
        circle.setAttribute('stroke-width', '2');
        circle.setAttribute('class', 'transition-all group-hover:scale-110 group-hover:stroke-amber-400');

        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', nx);
        label.setAttribute('y', ny + 3);
        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('fill', '#F9FAFB');
        label.setAttribute('font-family', 'monospace');
        label.setAttribute('font-size', '9.5');
        label.setAttribute('font-weight', '600');
        const resn = item.resn || item.residue || 'RES';
        label.textContent = `${resn}${item.resi}`;

        resNode.appendChild(circle);
        resNode.appendChild(label);

        if (typeof onResidueClick === 'function') {
            resNode.addEventListener('click', () => onResidueClick(item));
        }

        nodesGroup.appendChild(resNode);
    });

    svg.appendChild(linesGroup);
    svg.appendChild(centerGroup);
    svg.appendChild(nodesGroup);

    containerEl.appendChild(svg);
}

