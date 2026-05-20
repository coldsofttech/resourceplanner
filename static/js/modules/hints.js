/**
 * First-time usage hint system.
 *
 * Usage:
 *   import { initHints } from './hints.js';
 *   initHints('page-key', [
 *     { id: 'hint-1', target: '#some-element', title: 'Title', body: 'Description', placement: 'bottom' },
 *     ...
 *   ]);
 *
 * Each hint is shown once; dismissal is persisted in localStorage.
 * The hint tour advances automatically when the user clicks "Next" or dismisses.
 */

const STORAGE_KEY = 'rp_hints_dismissed';

function getDismissed() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch {
        return {};
    }
}

function markDismissed(hintId) {
    const dismissed = getDismissed();
    dismissed[hintId] = true;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(dismissed));
}

function isDismissed(hintId) {
    return !!getDismissed()[hintId];
}

function buildHintEl(hint, index, total, onNext, onDismiss) {
    const el = document.createElement('div');
    el.className = 'rp-hint';
    el.id = `rp-hint-${hint.id}`;
    el.setAttribute('role', 'tooltip');
    el.setAttribute('aria-live', 'polite');

    el.innerHTML = `
        <div class="rp-hint-arrow"></div>
        <div class="rp-hint-inner">
            <div class="rp-hint-header">
                <span class="rp-hint-title">${hint.title}</span>
                <button class="rp-hint-close" aria-label="Dismiss hint" title="Dismiss">&times;</button>
            </div>
            <div class="rp-hint-body">${hint.body}</div>
            <div class="rp-hint-footer">
                <span class="rp-hint-step">${index + 1} of ${total}</span>
                ${index + 1 < total
                    ? `<button class="btn btn-sm rp-hint-next">Next <i class="bi bi-arrow-right"></i></button>`
                    : `<button class="btn btn-sm rp-hint-next">Got it</button>`
                }
            </div>
        </div>`;

    el.querySelector('.rp-hint-close').addEventListener('click', () => onDismiss());
    el.querySelector('.rp-hint-next').addEventListener('click', () => onNext());
    return el;
}

function positionHint(hintEl, targetEl, placement) {
    const targetRect = targetEl.getBoundingClientRect();
    const scrollY = window.scrollY;
    const scrollX = window.scrollX;

    hintEl.style.position = 'absolute';
    hintEl.style.zIndex = '9999';

    // Reset placement classes
    hintEl.classList.remove('rp-hint--top', 'rp-hint--bottom', 'rp-hint--left', 'rp-hint--right');
    hintEl.classList.add(`rp-hint--${placement || 'bottom'}`);

    // Wait for element to be rendered before calculating dimensions
    requestAnimationFrame(() => {
        const hintRect = hintEl.getBoundingClientRect();
        const gap = 12;

        let top, left;
        switch (placement) {
            case 'top':
                top = targetRect.top + scrollY - hintRect.height - gap;
                left = targetRect.left + scrollX + targetRect.width / 2 - hintRect.width / 2;
                break;
            case 'left':
                top = targetRect.top + scrollY + targetRect.height / 2 - hintRect.height / 2;
                left = targetRect.left + scrollX - hintRect.width - gap;
                break;
            case 'right':
                top = targetRect.top + scrollY + targetRect.height / 2 - hintRect.height / 2;
                left = targetRect.right + scrollX + gap;
                break;
            default: // bottom
                top = targetRect.bottom + scrollY + gap;
                left = targetRect.left + scrollX + targetRect.width / 2 - hintRect.width / 2;
        }

        // Clamp to viewport width
        const maxLeft = window.innerWidth - hintRect.width - 8;
        left = Math.max(8, Math.min(left, maxLeft));

        hintEl.style.top = `${top}px`;
        hintEl.style.left = `${left}px`;
    });
}

function scrollToTarget(targetEl) {
    targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

export function initHints(pageKey, hints) {
    // Filter out already-dismissed hints
    const pending = hints.filter(h => !isDismissed(`${pageKey}:${h.id}`));
    if (!pending.length) return;

    let currentIndex = 0;
    let currentEl = null;
    let highlightEl = null;

    function removeHighlight() {
        if (highlightEl) {
            highlightEl.classList.remove('rp-hint-target-highlight');
            highlightEl = null;
        }
    }

    function showHint(index) {
        // Clean up previous
        if (currentEl) currentEl.remove();
        removeHighlight();

        if (index >= pending.length) {
            // All hints shown
            return;
        }

        const hint = pending[index];
        const targetEl = hint.target ? document.querySelector(hint.target) : null;

        // Highlight target if found
        if (targetEl) {
            targetEl.classList.add('rp-hint-target-highlight');
            highlightEl = targetEl;
            scrollToTarget(targetEl);
        }

        const onNext = () => {
            markDismissed(`${pageKey}:${hint.id}`);
            currentIndex++;
            showHint(currentIndex);
        };
        const onDismiss = () => {
            // Dismiss all remaining
            for (let i = index; i < pending.length; i++) {
                markDismissed(`${pageKey}:${pending[i].id}`);
            }
            if (currentEl) currentEl.remove();
            removeHighlight();
            currentEl = null;
        };

        const el = buildHintEl(hint, index, pending.length, onNext, onDismiss);
        document.body.appendChild(el);
        currentEl = el;

        if (targetEl) {
            positionHint(el, targetEl, hint.placement || 'bottom');
            // Reposition on scroll/resize
            const reposition = () => positionHint(el, targetEl, hint.placement || 'bottom');
            window.addEventListener('scroll', reposition, { passive: true });
            window.addEventListener('resize', reposition, { passive: true });
        } else {
            // Center float if no target
            el.style.position = 'fixed';
            el.style.bottom = '80px';
            el.style.right = '24px';
            el.style.zIndex = '9999';
        }
    }

    // Start after a short delay to let the page render
    setTimeout(() => showHint(currentIndex), 800);
}

/** Reset all hints for a page (for testing / dev). */
export function resetHints(pageKey) {
    const dismissed = getDismissed();
    Object.keys(dismissed).forEach(k => {
        if (k.startsWith(`${pageKey}:`)) delete dismissed[k];
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(dismissed));
}
