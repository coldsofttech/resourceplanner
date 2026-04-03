'use strict';

/**
 * Server-side column sorting for list tables.
 * Clicking a <th data-col data-field> re-fetches via the fetcher with order_by + order_dir.
 * Does NOT reorder DOM rows — the API returns pre-sorted results.
 *
 * @param {Object}   cfg
 * @param {string}   cfg.tableId                    - ID of the <table>
 * @param {Object}   cfg.fetcher                    - Return value of initFetch()
 * @param {string}   [cfg.iconClass='rp-sort-icon'] - Class on the <i> icon in each <th>
 */

export function initSorting(cfg = {}) {
    const {
        tableId,
        fetcher,
        iconClass = 'rp-sort-icon',
    } = cfg;

    if (!tableId) {
        console.warn('[initSorting] tableId is required.');
        return;
    }
    if (!fetcher) {
        console.warn('[initSorting] fetcher is required.');
        return;
    }

    const table = document.getElementById(tableId);
    if (!table) {
        console.warn(`[initSorting] Table #${tableId} not found.`);
        return;
    }

    let currentField = '';
    let currentDir   = 'asc';

    table.querySelectorAll('thead th[data-field]').forEach(th => {
        th.style.cursor = 'pointer';
        th.addEventListener('click', () => {
            const field = th.dataset.field;

            if (field === currentField) {
                currentDir = currentDir === 'asc' ? 'desc' : 'asc';
            } else {
                currentField = field;
                currentDir   = 'asc';
            }

            _updateIcons(table, th, currentDir, iconClass);
            fetcher.setOrder(currentField, currentDir);
        });
    });

    function _updateIcons(table, activeTh, dir, iconClass) {
        table.querySelectorAll(`thead th .${iconClass}`).forEach(icon => {
            const isActive = icon.closest('th') === activeTh;
            icon.className = `bi ${iconClass} ` + (
                isActive
                    ? (dir === 'asc' ? 'bi-chevron-up' : 'bi-chevron-down')
                    : 'bi-chevron-expand'
            );
        });
    }
}