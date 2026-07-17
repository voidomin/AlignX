// Real inline SVG icons for the Analytics Insights list, keyed by the same
// icon_name string insights.py already emits in each insight's leading
// "[[icon_name]] " marker. Built entirely via createElementNS/setAttribute
// (never innerHTML/insertAdjacentHTML), matching this app's existing
// no-HTML-string-sink convention for user-adjacent DOM construction - and,
// unlike an icon font, these render immediately with no risk of a brief
// flash of literal glyph-name text before a webfont loads.
const SVG_NS = 'http://www.w3.org/2000/svg';

// Each shape list is a minimal, hand-verified set of primitive SVG
// elements (circle/line/rect/polyline/polygon/straight-line-only path) on
// a shared 24x24 viewBox - deliberately not an attempt to reproduce any
// particular icon library's exact artwork, just a clear, recognizable
// glyph per insight category.
const ICON_SHAPES = {
    check_circle: [
        { tag: 'circle', attrs: { cx: 12, cy: 12, r: 9 } },
        { tag: 'polyline', attrs: { points: '8,12.5 10.5,15 16,9' } },
    ],
    warning: [
        { tag: 'polygon', attrs: { points: '12,3 22,20 2,20' } },
        { tag: 'line', attrs: { x1: 12, y1: 9, x2: 12, y2: 14 } },
        { tag: 'circle', attrs: { cx: 12, cy: 17.3, r: 0.6, fill: 'currentColor', stroke: 'none' } },
    ],
    info: [
        { tag: 'circle', attrs: { cx: 12, cy: 12, r: 9 } },
        { tag: 'line', attrs: { x1: 12, y1: 11, x2: 12, y2: 16 } },
        { tag: 'circle', attrs: { cx: 12, cy: 7.5, r: 0.6, fill: 'currentColor', stroke: 'none' } },
    ],
    military_tech: [
        { tag: 'circle', attrs: { cx: 12, cy: 9, r: 6 } },
        { tag: 'line', attrs: { x1: 9.8, y1: 14.5, x2: 7.5, y2: 21 } },
        { tag: 'line', attrs: { x1: 14.2, y1: 14.5, x2: 16.5, y2: 21 } },
    ],
    compare_arrows: [
        { tag: 'line', attrs: { x1: 4, y1: 8, x2: 18, y2: 8 } },
        { tag: 'polyline', attrs: { points: '14,4 18,8 14,12' } },
        { tag: 'line', attrs: { x1: 20, y1: 16, x2: 6, y2: 16 } },
        { tag: 'polyline', attrs: { points: '10,12 6,16 10,20' } },
    ],
    flag: [
        { tag: 'line', attrs: { x1: 5, y1: 3, x2: 5, y2: 21 } },
        { tag: 'path', attrs: { d: 'M5,4 L19,4 L15,8 L19,12 L5,12 Z' } },
    ],
    medication: [
        { tag: 'rect', attrs: { x: 3, y: 8, width: 18, height: 8, rx: 4 } },
        { tag: 'line', attrs: { x1: 12, y1: 8, x2: 12, y2: 16 } },
    ],
    // Similar binding pockets - two overlapping circles read as "linked".
    biotech: [
        { tag: 'circle', attrs: { cx: 9, cy: 12, r: 5 } },
        { tag: 'circle', attrs: { cx: 15, cy: 12, r: 5 } },
    ],
    // Divergent binding pockets - same two circles, pulled apart.
    science: [
        { tag: 'circle', attrs: { cx: 7, cy: 12, r: 4 } },
        { tag: 'circle', attrs: { cx: 17, cy: 12, r: 4 } },
    ],
    group_work: [
        { tag: 'circle', attrs: { cx: 9, cy: 9, r: 5 } },
        { tag: 'circle', attrs: { cx: 15, cy: 9, r: 5 } },
        { tag: 'circle', attrs: { cx: 12, cy: 15, r: 5 } },
    ],
    verified: [
        { tag: 'path', attrs: { d: 'M12,3 L19,6 L19,12 L12,21 L5,12 L5,6 Z' } },
        { tag: 'polyline', attrs: { points: '8.5,12 11,14.5 15.5,9' } },
    ],
    star: [
        {
            tag: 'polygon',
            attrs: {
                points:
                    '12,3 14.7,9.5 21.5,9.9 16,14.3 17.8,21 12,17.1 6.2,21 8,14.3 2.5,9.9 9.3,9.5',
            },
        },
    ],
    trending_down: [
        { tag: 'polyline', attrs: { points: '4,7 10,13 14,9 20,17' } },
        { tag: 'polyline', attrs: { points: '20,10 20,17 13,17' } },
    ],
    diamond: [
        { tag: 'polygon', attrs: { points: '12,3 21,12 12,21 3,12' } },
    ],
};

// Returns a real <svg> element for a known icon name, or null for an
// unrecognized one (a caller should skip appending it entirely rather
// than show a broken/empty icon).
export function createInsightIconSvg(iconName) {
    const shapes = ICON_SHAPES[iconName];
    if (!shapes) return null;

    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', '16');
    svg.setAttribute('height', '16');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.8');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');

    shapes.forEach(({ tag, attrs }) => {
        const el = document.createElementNS(SVG_NS, tag);
        Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
        svg.appendChild(el);
    });

    return svg;
}
