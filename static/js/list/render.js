'use strict';

/**
 * Generic list renderer: table rows, pagination, empty, error and loading states.
 *
 * @param {Object}   cfg
 * @param {string}   cfg.tbodyId
 * @param {number}   cfg.colspan
 * @param {Function} cfg.rowTemplate                - (item) => HTML string
 * @param {string}   [cfg.itemLabel='items']
 * @param {Object}   [cfg.emptyState]               - { message, link: { href, label, onClick } }
 * @param {Object}   [cfg.filterEmptyState]         - Shown when search/filters are active
 * @param {string}   [cfg.paginationBarId]
 * @param {string}   [cfg.paginationInfoId]
 * @param {string}   [cfg.paginationControlsId]
 * @param {Function} [cfg.onPageChange]             - (pageNumber) => void
 */

export function initRenderer(cfg = {}) {
    const {
        tbodyId,
        colspan,
        rowTemplate,
        itemLabel = 'items',
        emptyState = {},
        filterEmptyState = {},
        paginationBarId,
        paginationInfoId,
        paginationControlsId,
        onPageChange,
    } = cfg;

    if (!tbodyId || !rowTemplate) {
        console.warn('[initRenderer] tbodyId and rowTemplate are required.');
        return;
    }

    const tbody = document.getElementById(tbodyId);
    if (!tbody) {
        console.warn(`[initRenderer] #${tbodyId} not found.`);
        return;
    }

    function renderRows(items, hasFilters = false) {
        if (!items.length) {
            const s = hasFilters
                ? { message: `No ${itemLabel} match your filters.`, ...filterEmptyState }
                : { message: `No ${itemLabel} found.`, ...emptyState };
            tbody.innerHTML = emptyHtml(s);
            return;
        }
        tbody.innerHTML = items.map(rowTemplate).join('');
    }

    let _paginationListenerAttached = false;

    function renderPagination(p) {
        const bar = document.getElementById(paginationBarId);
        const infoEl = document.getElementById(paginationInfoId);
        const ctrlEl = document.getElementById(paginationControlsId);
        if (!bar || !infoEl || !ctrlEl) return;

        if (!p || p.total_count === 0) {
            bar.classList.add('d-none');
            return;
        }

        if (!_paginationListenerAttached) {
            ctrlEl.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-page]:not([disabled])');
                if (!btn) return;
                onPageChange?.(parseInt(btn.dataset.page, 10));
            });
            _paginationListenerAttached = true;
        }

        const from = (p.current_page - 1) * p.page_size + 1;
        const to = Math.min(p.current_page * p.page_size, p.total_count);
        infoEl.textContent = `Showing ${from}–${to} of ${p.total_count} ${itemLabel}`;
        bar.classList.remove('d-none');
        ctrlEl.innerHTML = paginationHtml(p);
    }

    function renderLoading(message = 'Loading…') {
        tbody.innerHTML = `
            <tr>
                <td colspan="${colspan}" class="text-center py-5 text-secondary">
                    <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                    ${message}
                </td>
            </tr>`;
    }

    function renderError(message = 'Failed to load. Please refresh the page.') {
        tbody.innerHTML = `
            <tr>
                <td colspan="${colspan}" class="text-center py-5 text-danger">
                    <i class="bi bi-exclamation-circle me-1"></i>${message}
                </td>
            </tr>`;
    }

    function emptyHtml({ message, link } = {}) {
        let linkHtml = '';
        if (link) {
            const useHref = link.href && link.href !== '#';
            if (useHref) {
                linkHtml = ` <a href="${link.href}">${link.label}</a>`;
            } else if (link.onClick) {
                linkHtml = ` <a href="#" onclick="${link.onClick}; return false;">${link.label}</a>`;
            } else {
                linkHtml = ` <a href="${link.href}">${link.label}</a>`;
            }
        }
        return `
            <tr>
                <td colspan="${colspan}" class="text-center py-5 text-secondary">
                    <i class="bi bi-inbox display-6 d-block mb-2 opacity-25"></i>
                    ${message}${linkHtml}
                </td>
            </tr>`;
    }

    function paginationHtml(p) {
        const btn = (label, page, disabled, active = false, isIcon = false) => `
            <li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
                <button class="page-link ${isIcon ? 'page-link--icon' : ''}"
                        ${disabled ? 'disabled' : ''}
                        data-page="${page}">
                    ${label}
                </button>
            </li>`;

        const pages = new Set(
            [1, p.total_pages, p.current_page - 1, p.current_page, p.current_page + 1].filter(
                (n) => n >= 1 && n <= p.total_pages,
            ),
        );
        const sorted = [...pages].sort((a, b) => a - b);

        let html = '';
        html += btn('<i class="bi bi-chevron-double-left"></i>', 1, !p.has_previous, false, true);
        html += btn(
            '<i class="bi bi-chevron-left"></i>',
            p.current_page - 1,
            !p.has_previous,
            false,
            true,
        );

        let prev = null;
        for (const n of sorted) {
            if (prev && n - prev > 1) {
                html += `
                <li class="page-item disabled">
                    <span class="page-link page-link--ellipsis">…</span>
                </li>`;
            }
            html += btn(n, n, false, n === p.current_page);
            prev = n;
        }

        html += btn(
            '<i class="bi bi-chevron-right"></i>',
            p.current_page + 1,
            !p.has_next,
            false,
            true,
        );
        html += btn(
            '<i class="bi bi-chevron-double-right"></i>',
            p.total_pages,
            !p.has_next,
            false,
            true,
        );

        return html;
    }

    return { renderRows, renderPagination, renderLoading, renderError };
}
