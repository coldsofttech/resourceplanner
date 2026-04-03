'use strict';

import { apiFetch } from '../main.js';

/**
 * Generic API fetch controller for list pages.
 * Owns all state: page, search, filters, ordering.
 * Search, filter and sort changes all reset to page 1 and re-fetch.
 *
 * @param {Object}   cfg
 * @param {string}   cfg.apiUrl                     - Base API endpoint
 * @param {number}   [cfg.pageSize=20]              - Items per page
 * @param {Object}   [cfg.defaultParams={}]         - Fixed params always included
 *
 * @param {string}   [cfg.searchInputId]            - ID of the search <input>
 * @param {number}   [cfg.searchDebounce=350]       - Debounce ms for search input
 *
 * @param {Array}    [cfg.filters=[]]               - Filter descriptors:
 *   { id, param, map: { displayVal: 'apiVal' } }
 *   e.g. { id: 'status-filter', param: 'is_active', map: { active: 'true', inactive: 'false' } }
 *
 * @param {Function} cfg.onSuccess                  - Called with ({ results, pagination, state })
 * @param {Function} [cfg.onError]                  - Called with (error) on fetch failure
 * @param {Function} [cfg.onLoadStart]              - Called before each fetch
 */

export function initFetch(cfg = {}) {
    const {
        apiUrl,
        pageSize        = 20,
        defaultParams   = {},
        searchInputId,
        searchDebounce  = 350,
        filters         = [],
        onSuccess,
        onError,
        onLoadStart,
    } = cfg;

    if (!apiUrl) {
        console.warn('[initFetch] apiUrl is required.');
        return;
    }
    if (typeof onSuccess !== 'function') {
        console.warn('[initFetch] onSuccess is required.');
        return;
    }

    const state = {
        page:      1,
        search:    '',
        filters:   {},   // { apiParam: resolvedValue }
        orderBy:   '',
        orderDir:  '',   // 'asc' | 'desc'
    };

    if (searchInputId) {
        const input = document.getElementById(searchInputId);
        if (input) {
            let timer;
            input.addEventListener('input', () => {
                clearTimeout(timer);
                timer = setTimeout(() => _fetch({ search: input.value.trim(), page: 1 }), searchDebounce);
            });
        } else {
            console.warn(`[initFetch] Search input #${searchInputId} not found.`);
        }
    }

    filters.forEach(f => {
        const el = document.getElementById(f.id);
        if (!el) {
            console.warn(`[initFetch] Filter #${f.id} not found.`);
            return;
        }

        el.addEventListener('change', () => {
            const raw      = el.value.trim();
            const resolved = raw ? (f.map?.[raw] ?? raw) : undefined;

            const updatedFilters = { ...state.filters };
            if (resolved !== undefined) {
                updatedFilters[f.param] = resolved;
            } else {
                delete updatedFilters[f.param];   // empty selection → omit param entirely
            }

            _fetch({ filters: updatedFilters, page: 1 });
        });
    });

    async function _fetch(overrides = {}) {
        Object.assign(state, overrides);

        const params = new URLSearchParams({
            ...defaultParams,
            page:      state.page,
            page_size: pageSize,
        });

        if (state.search)   params.set('search',    state.search);
        if (state.orderBy)  params.set('order_by',  state.orderBy);
        if (state.orderDir) params.set('order_dir', state.orderDir);

        Object.entries(state.filters).forEach(([k, v]) => params.set(k, v));

        onLoadStart?.();

        try {
            const data = await apiFetch(`${apiUrl}?${params}`);
            onSuccess({ results: data.results, pagination: data.pagination, state });
        } catch (err) {
            console.error('[initFetch] Fetch failed:', err);
            onError?.(err);
        }
    }

    return {
        refresh:   ()                          => _fetch(),
        goToPage:  page                        => _fetch({ page }),
        setOrder:  (orderBy, orderDir = 'asc') => _fetch({ orderBy, orderDir, page: 1 }),
        getState:  ()                          => ({ ...state }),
    };
}