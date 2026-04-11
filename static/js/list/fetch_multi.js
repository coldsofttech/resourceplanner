'use strict';

import { apiFetch } from '../main.js';

/**
 * Like initFetch but supports <select multiple> filters.
 * Each multi-filter descriptor: { id, param }
 *   - id    : DOM id of the <select multiple>
 *   - param : query param name sent to the API
 * Selected values are joined with commas: ?status=NEW,IN_PROGRESS
 *
 * All other behaviour (search, ordering, pagination, state) is identical
 * to initFetch. Existing initFetch is untouched.
 *
 * @param {Object}   cfg
 * @param {string}   cfg.apiUrl
 * @param {number}   [cfg.pageSize=20]
 * @param {Object}   [cfg.defaultParams={}]
 * @param {string}   [cfg.searchInputId]
 * @param {number}   [cfg.searchDebounce=350]
 * @param {Array}    [cfg.filters=[]]          - { id, param } single-value filters (unchanged)
 * @param {Array}    [cfg.multiFilters=[]]     - { id, param } multi-select filters
 * @param {Function} cfg.onSuccess
 * @param {Function} [cfg.onError]
 * @param {Function} [cfg.onLoadStart]
 */
export function initFetchMulti(cfg = {}) {
    const {
        apiUrl,
        pageSize = 20,
        defaultParams = {},
        searchInputId,
        searchDebounce = 350,
        filters = [],
        multiFilters = [],
        onSuccess,
        onError,
        onLoadStart,
    } = cfg;

    if (!apiUrl) {
        console.warn('[initFetchMulti] apiUrl is required.');
        return;
    }
    if (typeof onSuccess !== 'function') {
        console.warn('[initFetchMulti] onSuccess is required.');
        return;
    }

    const state = {
        page: 1,
        search: '',
        filters: {}, // { param: singleValue }
        multiFilters: {}, // { param: 'val1,val2' }
        orderBy: '',
        orderDir: '',
    };

    // ── Search ────────────────────────────────────────────────────────────────
    if (searchInputId) {
        const input = document.getElementById(searchInputId);
        if (input) {
            let timer;
            input.addEventListener('input', () => {
                clearTimeout(timer);
                timer = setTimeout(
                    () => _fetch({ search: input.value.trim(), page: 1 }),
                    searchDebounce,
                );
            });
        } else {
            console.warn(`[initFetchMulti] Search input #${searchInputId} not found.`);
        }
    }

    // ── Single-value filters (same as initFetch) ──────────────────────────────
    filters.forEach((f) => {
        const el = document.getElementById(f.id);
        if (!el) {
            console.warn(`[initFetchMulti] Filter #${f.id} not found.`);
            return;
        }
        el.addEventListener('change', () => {
            const raw = el.value.trim();
            const resolved = raw ? (f.map?.[raw] ?? raw) : undefined;
            const updated = { ...state.filters };
            if (resolved !== undefined) {
                updated[f.param] = resolved;
            } else {
                delete updated[f.param];
            }
            _fetch({ filters: updated, page: 1 });
        });
    });

    // ── Multi-select filters ──────────────────────────────────────────────────
    multiFilters.forEach((f) => {
        const el = document.getElementById(f.id);
        if (!el) {
            console.warn(`[initFetchMulti] Multi-filter #${f.id} not found.`);
            return;
        }
        el.addEventListener('change', () => {
            const vals = Array.from(el.selectedOptions)
                .map((o) => o.value)
                .filter(Boolean);
            const updated = { ...state.multiFilters };
            if (vals.length > 0) {
                updated[f.param] = vals.join(',');
            } else {
                delete updated[f.param];
            }
            _fetch({ multiFilters: updated, page: 1 });
        });
    });

    // ── Core fetch ────────────────────────────────────────────────────────────
    async function _fetch(overrides = {}) {
        Object.assign(state, overrides);

        const params = new URLSearchParams({
            ...defaultParams,
            page: state.page,
            page_size: pageSize,
        });

        if (state.search) params.set('search', state.search);
        if (state.orderBy) params.set('order_by', state.orderBy);
        if (state.orderDir) params.set('order_dir', state.orderDir);

        // Single-value filters
        Object.entries(state.filters).forEach(([k, v]) => params.set(k, v));

        // Multi-value filters (comma-joined strings)
        Object.entries(state.multiFilters).forEach(([k, v]) => params.set(k, v));

        onLoadStart?.();

        try {
            const data = await apiFetch(`${apiUrl}?${params}`);
            onSuccess({ results: data.results, pagination: data.pagination, state });
        } catch (err) {
            console.error('[initFetchMulti] Fetch failed:', err);
            onError?.(err);
        }
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Re-read all multi-select elements and refresh.
     * Call this after programmatically changing selections (e.g. clear-all).
     */
    function syncAndRefresh() {
        const updated = {};
        multiFilters.forEach((f) => {
            const el = document.getElementById(f.id);
            const vals = el
                ? Array.from(el.selectedOptions)
                      .map((o) => o.value)
                      .filter(Boolean)
                : [];
            if (vals.length > 0) {
                updated[f.param] = vals.join(',');
            }
        });
        _fetch({ multiFilters: updated, page: 1 });
    }

    return {
        refresh: () => _fetch(),
        syncAndRefresh: () => syncAndRefresh(),
        goToPage: (page) => _fetch({ page }),
        setOrder: (orderBy, orderDir = 'asc') => _fetch({ orderBy, orderDir, page: 1 }),
        getState: () => ({ ...state }),
    };
}
