// A tiny, framework-free implementation of the WAI-ARIA APG "tab" widget's
// keyboard model: ArrowLeft/ArrowRight move focus between sibling tab
// buttons (wrapping at the ends), Home/End jump to the first/last. Moving
// focus also activates the newly-focused tab, matching this app's existing
// click-to-activate behavior rather than requiring a separate Enter/Space
// step - keyboard and mouse end up doing the same thing.
export function wireArrowKeyNavigation(navElement, buttonSelector, activate) {
    navElement.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;

        const buttons = Array.from(navElement.querySelectorAll(buttonSelector));
        const currentIndex = buttons.indexOf(document.activeElement);
        if (currentIndex === -1) return;

        event.preventDefault();
        let nextIndex;
        if (event.key === 'ArrowLeft') {
            nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
        } else if (event.key === 'ArrowRight') {
            nextIndex = (currentIndex + 1) % buttons.length;
        } else if (event.key === 'Home') {
            nextIndex = 0;
        } else {
            nextIndex = buttons.length - 1;
        }

        const nextButton = buttons[nextIndex];
        nextButton.focus();
        activate(nextButton);
    });
}
