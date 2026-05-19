'use strict';

import { initFetch } from './../list/fetch.js';
import { initFetchMulti } from './../list/fetch_multi.js';
import { initRenderer } from './../list/render.js';
import { initSorting } from './../list/sort.js';
import { apiFetch, escAttr, escHtml, formatDate, setPageTitle, showFlash, hasPerm } from './../main.js';
import { API_URLS, URLS } from './../urls.js';
import { exportToCsv, exportToPdf } from '../export.js';

let _allSubStatuses = [];
let _progOptions = [];
let _allProjects = [];
let _deliveryTeams = [];

const COLUMN_DEFS = [
    { key: 'name', label: 'Name', fixed: true, sortField: 'name' },
    { key: 'project_type', label: 'Project Type', fixed: false, sortField: 'project_type' },
    { key: 'programme', label: 'Programme', fixed: false, sortField: 'programme_id' },
    { key: 'code', label: 'Code', fixed: false, sortField: 'code' },
    { key: 'status', label: 'Status', fixed: true, sortField: 'status' },
    { key: 'sub_status', label: 'Sub-Status', fixed: false, sortField: 'sub_status' },
    { key: 'assigned_team', label: 'Team', fixed: false, sortField: 'assigned_team' },
    { key: 'confidence', label: 'Confidence', fixed: false, sortField: 'confidence' },
    { key: 'priority', label: 'Priority', fixed: false, sortField: 'priority' },
    { key: 'is_active', label: 'Active', fixed: false, sortField: 'is_active' },
    { key: 'budget_risk', label: 'Budget Risk', fixed: false, sortField: null },
    { key: 'actions', label: 'Actions', fixed: true, sortField: null },
];

const DEFAULT_COLUMNS = [
    'name',
    'project_type',
    'programme',
    'code',
    'status',
    'sub_status',
    'assigned_team',
    'confidence',
    'priority',
    'is_active',
    'actions',
];

// Active column set (ordered list of keys)
let _activeColumns = [...DEFAULT_COLUMNS];

// Saved views state
let _savedViews = [];
let _activeViewId = null;

// Guard: suppress filter change handlers while programmatically applying a view
let _applyingView = false;

// Disable all filter selects so their change events don't fire during programmatic
// mutation. Returns a restore function that re-enables them all.
function _lockFilterSelects() {
    const all = [..._MULTI_FILTER_IDS];
    const prev = {};
    all.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        prev[id] = el.disabled;
        el.disabled = true;
    });
    return function unlock() {
        all.forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.disabled = prev[id] ?? false;
        });
    };
}

const _MULTI_FILTER_IDS = [
    'prog-filter',
    'proj-filter',
    'status-filter',
    'substatus-filter',
    'team-filter',
    'priority-filter',
    'confidence-filter',
    'ptype-filter',
    'tag-filter',
    'active-filter',
];

const LIST_EXPORT_COLUMNS = [
    { key: 'name', label: 'Name' },
    { key: 'project_type_name', label: 'Type' },
    { key: 'programme_name', label: 'Programme' },
    { key: 'code', label: 'Code' },
    { key: 'status_display', label: 'Status' },
    { key: 'assigned_team_name', label: 'Assigned Team' },
    { key: 'confidence_display', label: 'Confidence' },
    { key: 'priority_display', label: 'Priority' },
    { key: 'is_active', label: 'Active' },
];

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('proj-tbody')) return;
    initListView();
});

async function initListView() {
    setPageTitle('Projects');
    await loadStats();
    await populateFilterOptions();
    bindToolbarEvents();
    bindModalEvents();
    bindFilterEvents();
    bindSavedViewsEvents();
    bindColumnPickerEvents();
    initTable({ skipInitialFetch: true });
    await loadSavedViews();
}

async function loadStats() {
    try {
        const { method, href } = API_URLS.projects.stats;
        const data = await apiFetch(href, { method });
        document.getElementById('stat-total').textContent = data.total_projects ?? '-';
        document.getElementById('stat-active').textContent = data.active_projects ?? '-';
        document.getElementById('stat-in-progress').textContent = data.in_progress_projects ?? '-';
        document.getElementById('stat-new').textContent = data.new_projects ?? '-';
    } catch (err) {
        console.error('[loadStats] Failed.', err);
    }
}

async function populateFilterOptions() {
    try {
        const { method, href } = API_URLS.projects.options;
        const opts = await apiFetch(href, { method });

        _deliveryTeams = opts.delivery_teams ?? [];
        _allSubStatuses = opts.sub_statuses ?? [];
        _allProjects = opts.projects ?? [];
        _progOptions = opts.programmes ?? [];

        _populateMultiSelect('prog-filter', _progOptions);
        _populateMultiSelect('proj-filter', _allProjects, { useIdAsValue: true });
        _populateMultiSelect('status-filter', opts.status ?? []);
        _populateMultiSelect('team-filter', opts.delivery_teams ?? [], { useIdAsValue: true });
        _populateMultiSelect('priority-filter', opts.priority ?? []);
        _populateMultiSelect('confidence-filter', opts.confidence ?? []);
        _populateMultiSelect('ptype-filter', opts.project_types ?? [], { useIdAsValue: true });
        _populateMultiSelect('substatus-filter', _allSubStatuses, { useIdAsValue: true });
        _populateMultiSelect('tag-filter', opts.tags ?? []);
        _populateMultiSelect('active-filter', opts.is_active ?? []);
        document.getElementById('active-filter').value = true;

        // Add modal selects
        _populateSelect('proj-modal-type', opts.project_types ?? [], '', 'Select type…', {
            useIdAsValue: true,
        });
        _populateSelect('proj-modal-status', opts.status ?? [], 'NEW');
        _populateSelect('proj-modal-confidence', opts.confidence ?? [], '', 'Not set');
        _populateSelect('proj-modal-priority', opts.priority ?? [], '', 'Not set');
        _cascadeModalSubStatus();

        // Assign team modal selects
        _populateSelect('assign-team-select', _deliveryTeams, '', 'None (unassign)', {
            useIdAsValue: true,
        });

        window._progOptions = opts.programmes ?? [];

        document
            .getElementById('proj-modal-status')
            ?.addEventListener('change', () => {
                _cascadeModalSubStatus();
                _toggleModalCompletedSprint();
            });
        _populateModalSprintSelect();
    } catch (err) {
        console.error('[populateFilterOptions] Failed.', err);
    }
}

function _populateMultiSelect(id, items, opts = {}) {
    const el = document.getElementById(id);
    if (!el) return;
    while (el.options.length) el.remove(0);
    items.forEach((item) => {
        const opt = document.createElement('option');
        opt.value = opts.useIdAsValue ? (item.id ?? item.value) : (item.value ?? item.id);
        opt.textContent = item.label ?? item.name;
        el.appendChild(opt);
    });
}

function _populateSelect(id, items, defaultValue = '', emptyLabel = null, opts = {}) {
    const el = document.getElementById(id);
    if (!el) return;

    while (el.options.length) el.remove(0);

    if (emptyLabel !== null) {
        const ph = document.createElement('option');
        ph.value = '';
        ph.textContent = emptyLabel;
        el.appendChild(ph);
    }

    items.forEach((item) => {
        const opt = document.createElement('option');
        opt.value = opts.useIdAsValue ? (item.id ?? item.value) : (item.value ?? item.id);
        opt.textContent = item.label ?? item.name;
        if (String(opt.value) === String(defaultValue)) opt.selected = true;
        el.appendChild(opt);
    });
}

async function loadSavedViews() {
    try {
        const { method, href } = API_URLS.projects.views.list;
        const data = await apiFetch(href, { method });
        _savedViews = data;
        _renderViewsBar();

        // Apply default view on first load if no view manually selected
        const defaultView = _savedViews.find((v) => v.is_default);
        if (defaultView) {
            // Apply filters/columns from default view, then fetch once.
            _applyView(defaultView, true);
        } else {
            // No default view — just fire the initial fetch with default state.
            window._projFetcher?.refresh();
        }
    } catch (err) {
        console.error('[loadSavedViews] Failed.', err);
        // On error still load the table with defaults.
        window._projFetcher?.refresh();
    }
}

function _renderViewsBar() {
    const bar = document.getElementById('proj-views-bar');
    if (!bar) return;

    const chips = _savedViews.length === 0
        ? '<span class="text-secondary small fst-italic">No saved views</span>'
        : _savedViews.map((v) => `
            <button
                class="btn btn-sm rp-view-chip ${_activeViewId === v.id ? 'rp-view-chip--active' : ''}"
                data-view-id="${v.id}"
                title="${escAttr(v.name)}${v.is_default ? ' (default)' : ''}"
            >
                ${v.is_default ? '<i class="bi bi-star-fill me-1" style="font-size:10px;color:#f59e0b"></i>' : ''}
                ${escHtml(v.name)}
            </button>
        `).join('');

    const clearBtn = _activeViewId !== null
        ? `<button class="btn btn-ghost-icon btn-ghost-icon--danger rp-view-chip-clear"
                id="clear-active-view-btn"
                title="Clear active view — reset to system defaults"
                style="width:24px;height:24px;font-size:12px">
                <i class="bi bi-x-lg"></i>
           </button>`
        : '';

    bar.innerHTML = chips + clearBtn;
}

function _clearActiveView() {
    _activeViewId = null;
    _activeColumns = [...DEFAULT_COLUMNS];

    // Reset search
    const searchEl = document.getElementById('proj-search');
    if (searchEl) searchEl.value = '';

    // Reset all multi-selects
    _MULTI_FILTER_IDS.forEach((id) => {
        const el = document.getElementById(id);
        if (el) Array.from(el.options).forEach((o) => (o.selected = false));
    });

    // Re-cascade substatus/project dropdowns
    _populateMultiSelect('substatus-filter', _allSubStatuses, { useIdAsValue: true });
    _cascadeFilterProject();

    // Mirror the backend default: active-only when no is_active filter is set.
    const activeEl = document.getElementById('active-filter');
    if (activeEl) {
        Array.from(activeEl.options).forEach((o) => {
            o.selected = (o.value === 'true' || o.value === 'True');
        });
    }
    
    _updateClearBtn();
    _renderViewsBar();
    _applyColumnVisibility();
    _renderColumnPickerChecks();

    // Notify initFetchMulti of cleared search
    if (searchEl) searchEl.dispatchEvent(new Event('input', { bubbles: true }));

    window._projFetcher?.syncAndRefresh();
}

function _applyView(view, refreshTable = true) {
    // Disable all filter inputs before mutating them so that initFetchMulti's
    // internal change listeners cannot fire during programmatic value assignment.
    // This is the only reliable way to prevent spurious concurrent fetches without
    // access to initFetchMulti internals.
    const unlockFilters = _lockFilterSelects();
    _applyingView = true;
    try {
        _activeViewId = view.id;
        _renderViewsBar();

        // Apply columns
        if (Array.isArray(view.columns) && view.columns.length > 0) {
            _activeColumns = view.columns;
        } else {
            _activeColumns = [...DEFAULT_COLUMNS];
        }
        _applyColumnVisibility();
        _renderColumnPickerChecks();

        // Apply filters
        const f = view.filters || {};

        // Clear all filters first
        _MULTI_FILTER_IDS.forEach((id) => {
            const el = document.getElementById(id);
            if (el) Array.from(el.options).forEach((o) => (o.selected = false));
        });

        const searchEl = document.getElementById('proj-search');
        if (searchEl) searchEl.value = f.search || '';

        _applyMultiFilterFromView('prog-filter', f.programme);
        _applyMultiFilterFromView('status-filter', f.status);
        _applyMultiFilterFromView('substatus-filter', f.sub_status);
        _applyMultiFilterFromView('team-filter', f.team);
        _applyMultiFilterFromView('priority-filter', f.priority);
        _applyMultiFilterFromView('confidence-filter', f.confidence);
        _applyMultiFilterFromView('ptype-filter', f.project_type);
        _applyMultiFilterFromView('tag-filter', f.tags);
        _applyMultiFilterFromView('active-filter', f.is_active);

        // Cascade UI state (no fetches possible while selects are disabled)
        _cascadeFilterSubStatus();
        _cascadeFilterProject();
        _updateClearBtn();
    } finally {
        // Re-enable selects BEFORE calling syncAndRefresh so the fetcher can
        // read the current values when it builds its query string.
        unlockFilters();
        // Fire a synthetic input event on the search box BEFORE clearing the
        // _applyingView guard. This updates initFetchMulti's internal search
        // state to the value we just set programmatically, without triggering
        // an actual fetch (the guard suppresses that). Without this event,
        // syncAndRefresh() below would send the old/stale search term because
        // initFetchMulti tracks search via the input event, not by reading
        // .value on demand.
        const _searchEl = document.getElementById('proj-search');
        if (_searchEl) {
            _searchEl.dispatchEvent(new Event('input', { bubbles: true }));
        }
        _applyingView = false;
    }

    // Single fetch now that all state is settled and selects are re-enabled.
    if (refreshTable) {
        window._projFetcher?.syncAndRefresh();
    }
}

function _applyMultiFilterFromView(id, values) {
    if (!values || (Array.isArray(values) && values.length === 0)) return;
    const el = document.getElementById(id);
    if (!el) return;
    const vals = Array.isArray(values) ? values.map(String) : [String(values)];
    Array.from(el.options).forEach((o) => {
        o.selected = vals.includes(o.value);
    });
}

function _collectCurrentFilters() {
    const f = {};

    const search = document.getElementById('proj-search')?.value?.trim();
    if (search) f.search = search;

    const collectMulti = (id, key) => {
        const el = document.getElementById(id);
        if (!el) return;
        const vals = Array.from(el.selectedOptions).map((o) => o.value);
        if (vals.length) f[key] = vals;
    };

    collectMulti('prog-filter', 'programme');
    collectMulti('status-filter', 'status');
    collectMulti('substatus-filter', 'sub_status');
    collectMulti('team-filter', 'team');
    collectMulti('priority-filter', 'priority');
    collectMulti('confidence-filter', 'confidence');
    collectMulti('ptype-filter', 'project_type');
    collectMulti('tag-filter', 'tags');
    collectMulti('active-filter', 'is_active');

    return f;
}

function bindSavedViewsEvents() {
    // Click a view chip
    document.getElementById('proj-views-bar')?.addEventListener('click', (e) => {
        if (e.target.closest('#clear-active-view-btn')) {
            _clearActiveView();
            return;
        }
        const chip = e.target.closest('[data-view-id]');
        if (!chip) return;
        const viewId = parseInt(chip.dataset.viewId);
        const view = _savedViews.find((v) => v.id === viewId);
        if (view) _applyView(view);
    });

    // Save current view button
    document.getElementById('save-view-btn')?.addEventListener('click', openSaveViewModal);

    // Save view modal confirm
    document.getElementById('confirm-save-view-btn')?.addEventListener('click', handleSaveView);

    // Manage views button
    document.getElementById('manage-views-btn')?.addEventListener('click', openManageViewsModal);
}

function openSaveViewModal() {
    const nameEl = document.getElementById('save-view-name');
    const defaultEl = document.getElementById('save-view-default');
    const bannerEl = document.getElementById('save-view-banner');
    const nameErrEl = document.getElementById('save-view-name-err');

    if (nameEl) nameEl.value = '';
    if (nameEl) nameEl.classList.remove('is-invalid');
    if (nameErrEl) nameErrEl.textContent = '';
    if (defaultEl) defaultEl.checked = false;
    if (bannerEl) bannerEl.classList.add('d-none');

    _showModal('saveViewModal');
    setTimeout(() => nameEl?.focus(), 300);
}

async function handleSaveView() {
    const nameEl = document.getElementById('save-view-name');
    const defaultEl = document.getElementById('save-view-default');
    const bannerEl = document.getElementById('save-view-banner');
    const nameErrEl = document.getElementById('save-view-name-err');
    const btn = document.getElementById('confirm-save-view-btn');

    nameEl?.classList.remove('is-invalid');
    if (nameErrEl) nameErrEl.textContent = '';
    bannerEl?.classList.add('d-none');

    const name = nameEl?.value?.trim();
    if (!name) {
        nameEl?.classList.add('is-invalid');
        if (nameErrEl) nameErrEl.textContent = 'Name is required.';
        return;
    }

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const payload = {
            name,
            filters: _collectCurrentFilters(),
            columns: [..._activeColumns],
            ordering: window._projFetcher?.ordering || '-created_at',
            is_default: defaultEl?.checked ?? false,
        };
        const { method, href } = API_URLS.projects.views.new;
        const created = await apiFetch(href, { method, body: JSON.stringify(payload) });
        _savedViews.push(created);
        if (created.is_default) {
            _savedViews.forEach((v) => {
                if (v.id !== created.id) v.is_default = false;
            });
        }
        _activeViewId = created.id;
        _renderViewsBar();
        showFlash(`View "${name}" saved.`, 'success');
        _hideModal('saveViewModal');
    } catch (err) {
        const msg = _extractError(err, 'Failed to save view.');
        if (bannerEl) {
            bannerEl.textContent = msg;
            bannerEl.classList.remove('d-none');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

function openManageViewsModal() {
    _renderManageViewsList();
    _showModal('manageViewsModal');
}

function _renderManageViewsList() {
    const listEl = document.getElementById('manage-views-list');
    if (!listEl) return;

    if (_savedViews.length === 0) {
        listEl.innerHTML =
            '<p class="text-secondary small fst-italic mb-0">No saved views yet.</p>';
        return;
    }

    listEl.innerHTML = _savedViews
        .map(
            (v) => `
        <div class="d-flex align-items-center justify-content-between py-2 border-bottom" data-manage-view-id="${v.id}">
            <div class="d-flex align-items-center gap-2">
                ${
                    v.is_default
                        ? '<i class="bi bi-star-fill text-warning" style="font-size:12px" title="Default view"></i>'
                        : `<button class="btn btn-ghost-icon" style="width:22px;height:22px;font-size:11px" title="Set as default" onclick="window._setDefaultView(${v.id})"><i class="bi bi-star"></i></button>`
                }
                <span class="fw-500 small">${escHtml(v.name)}</span>
            </div>
            <div class="d-flex gap-1">
                <button class="btn btn-ghost-icon btn-ghost-icon--danger" style="width:26px;height:26px;font-size:12px"
                    title="Delete view" onclick="window._deleteView(${v.id}, '${escAttr(v.name)}')">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </div>
    `,
        )
        .join('');
}

window._setDefaultView = async function (viewId) {
    try {
        const { method, href } = API_URLS.projects.views.update(viewId);
        const updated = await apiFetch(href, {
            method,
            body: JSON.stringify({ is_default: true }),
        });
        _savedViews.forEach((v) => {
            v.is_default = v.id === viewId;
            if (v.id === viewId) Object.assign(v, updated);
        });
        _renderViewsBar();
        _renderManageViewsList();
        showFlash('Default view updated.', 'success');
    } catch (err) {
        showFlash(_extractError(err, 'Failed to update default view.'), 'error');
    }
};

window._deleteView = async function (viewId, name) {
    if (!confirm(`Delete view "${name}"?`)) return;
    try {
        const { method, href } = API_URLS.projects.views.delete(viewId);
        await apiFetch(href, { method });
        _savedViews = _savedViews.filter((v) => v.id !== viewId);
        if (_activeViewId === viewId) _activeViewId = null;
        _renderViewsBar();
        _renderManageViewsList();
        showFlash(`View "${name}" deleted.`, 'success');
    } catch (err) {
        showFlash(_extractError(err, 'Failed to delete view.'), 'error');
    }
};

function bindColumnPickerEvents() {
    const btn = document.getElementById('col-picker-btn');
    const panel = document.getElementById('col-picker-panel');

    if (!btn || !panel) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = panel.classList.toggle('d-none');
        if (!open) _renderColumnPickerChecks();
    });

    document.addEventListener('click', (e) => {
        if (!panel.contains(e.target) && e.target !== btn) {
            panel.classList.add('d-none');
        }
    });

    panel.addEventListener('change', (e) => {
        const cb = e.target.closest('input[type=checkbox][data-col]');
        if (!cb) return;
        const key = cb.dataset.col;
        if (cb.checked) {
            if (!_activeColumns.includes(key)) {
                // Insert before 'actions' if present, else append
                const actIdx = _activeColumns.indexOf('actions');
                if (actIdx >= 0) {
                    _activeColumns.splice(actIdx, 0, key);
                } else {
                    _activeColumns.push(key);
                }
            }
        } else {
            _activeColumns = _activeColumns.filter((k) => k !== key);
        }
        _applyColumnVisibility(true);
        _renderColumnPickerChecks();
    });

    panel.addEventListener('click', (e) => {
        if (!e.target.closest('.col-picker-reset')) return;
        _activeColumns = [...DEFAULT_COLUMNS];
        _applyColumnVisibility(true);
        _renderColumnPickerChecks();
    });
}

function _renderColumnPickerChecks() {
    const panel = document.getElementById('col-picker-panel');
    if (!panel) return;

    const toggleable = COLUMN_DEFS.filter((c) => !c.fixed);
    const isDefault = DEFAULT_COLUMNS.every((k) => _activeColumns.includes(k)) &&
                      _activeColumns.every((k) => DEFAULT_COLUMNS.includes(k));

    panel.querySelector('.col-picker-items').innerHTML = toggleable
        .map(
            (c) => `
        <label class="d-flex align-items-center gap-2 py-1 px-2 rounded rp-col-picker-item">
            <input type="checkbox" data-col="${c.key}" ${_activeColumns.includes(c.key) ? 'checked' : ''} />
            <span class="small">${escHtml(c.label)}</span>
        </label>
    `,
        )
        .join('');

    const resetBtn = panel.querySelector('.col-picker-reset');
    if (resetBtn) resetBtn.classList.toggle('d-none', isDefault);
}

function _applyColumnVisibility(triggerRefresh = false) {
    const table = document.getElementById('proj-table');
    if (!table) return;

    COLUMN_DEFS.forEach((col) => {
        const visible = col.fixed || _activeColumns.includes(col.key);
        // Header
        const th = table.querySelector(`th[data-col="${col.key}"]`);
        if (th) th.classList.toggle('d-none', !visible);
        // Body cells — done at render time via renderProjectRow
    });

    // Update colspan
    const colspan = _activeColumns.length;
    const renderer = window._projRenderer;
    if (renderer?.setColspan) renderer.setColspan(colspan);

    // Only re-fetch when called directly from the column picker (not from _applyView)
    if (triggerRefresh) {
        window._projFetcher?.refresh();
    }
}

function _getActiveFilterCount() {
    return _MULTI_FILTER_IDS.filter((id) => {
        const el = document.getElementById(id);
        return el && Array.from(el.selectedOptions).length > 0;
    }).length;
}

function _updateClearBtn() {
    const count = _getActiveFilterCount();
    const btn = document.getElementById('clear-filters-btn');
    const badge = document.getElementById('filter-count-badge');
    if (btn) btn.classList.toggle('d-none', count === 0);
    if (badge) {
        badge.textContent = count > 0 ? `${count} active` : '';
        badge.classList.toggle('d-none', count === 0);
    }
}

function bindFilterEvents() {
    document.getElementById('status-filter')?.addEventListener('change', () => {
        if (_applyingView) return;
        _cascadeFilterSubStatus();
        _updateClearBtn();
    });
    document.getElementById('prog-filter')?.addEventListener('change', () => {
        if (_applyingView) return;
        _cascadeFilterProject();
        _updateClearBtn();
    });

    _MULTI_FILTER_IDS.forEach((id) => {
        document.getElementById(id)?.addEventListener('change', () => {
            if (_applyingView) return;
            _updateClearBtn();
        });
    });

    document.getElementById('clear-filters-btn')?.addEventListener('click', () => {
        window._clearProjectFilters?.();
    });

    _updateClearBtn();
}

function _cascadeFilterSubStatus() {
    const statusEl = document.getElementById('status-filter');
    const selectedStatuses = statusEl
        ? Array.from(statusEl.selectedOptions).map((o) => o.value)
        : [];

    const matching =
        selectedStatuses.length === 0
            ? _allSubStatuses
            : _allSubStatuses.filter((s) => selectedStatuses.includes(s.main_status));

    const subEl = document.getElementById('substatus-filter');
    const prevSel = subEl
        ? new Set(Array.from(subEl.selectedOptions).map((o) => o.value))
        : new Set();

    _populateMultiSelect('substatus-filter', matching, { useIdAsValue: true });

    if (subEl) {
        Array.from(subEl.options).forEach((o) => {
            o.selected = prevSel.has(o.value);
        });
    }
}

function _cascadeFilterProject() {
    const progEl = document.getElementById('prog-filter');
    const selectedIds = progEl
        ? Array.from(progEl.selectedOptions).map((o) => Number(o.value))
        : [];

    const selectedNames =
        selectedIds.length === 0
            ? []
            : _progOptions.filter((p) => selectedIds.includes(p.id)).map((p) => p.name);

    const matching =
        selectedNames.length === 0
            ? _allProjects
            : _allProjects.filter((s) => selectedNames.includes(s.programme_name ?? ''));

    const projEl = document.getElementById('proj-filter');
    const prevSel = projEl
        ? new Set(Array.from(projEl.selectedOptions).map((o) => o.value))
        : new Set();

    _populateMultiSelect('proj-filter', matching, { useIdAsValue: true });

    if (projEl) {
        Array.from(projEl.options).forEach((o) => {
            o.selected = prevSel.has(o.value);
        });
    }
}

function _toggleModalCompletedSprint() {
    const statusVal = document.getElementById('proj-modal-status')?.value;
    const row = document.getElementById('proj-modal-completed-sprint-row');
    if (row) {
        if (statusVal === 'COMPLETED') {
            row.classList.remove('d-none');
        } else {
            row.classList.add('d-none');
        }
    }
}

async function _populateModalSprintSelect() {
    const sel = document.getElementById('proj-modal-completed-sprint');
    if (!sel || sel.options.length > 1) return;
    try {
        const data = await apiFetch(API_URLS.sprints.list.href + '?page_size=100');
        const sorted = (data?.results || []).slice().reverse();
        sorted.forEach(s => {
            const o = document.createElement('option');
            o.value = s.id;
            o.textContent = s.sprint_name;
            sel.appendChild(o);
        });
    } catch (_) { /* non-critical */ }
}

function _cascadeModalSubStatus() {
    const statusVal = document.getElementById('proj-modal-status')?.value ?? '';
    const matching = statusVal ? _allSubStatuses.filter((s) => s.main_status === statusVal) : [];

    const subEl = document.getElementById('proj-modal-substatus');
    const currentVal = subEl?.value ?? '';

    while (subEl?.options.length) subEl.remove(0);

    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = 'Select sub-status…';
    subEl?.appendChild(ph);

    matching.forEach((s) => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        if (String(s.id) === currentVal) opt.selected = true;
        subEl?.appendChild(opt);
    });
}

function bindToolbarEvents() {
    document.getElementById('add-project-btn')?.addEventListener('click', () => openAddModal());
    document.getElementById('export-csv')?.addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf')?.addEventListener('click', () => runListExport('pdf'));
}

function initTable({ skipInitialFetch = false } = {}) {
    const { method, href } = API_URLS.projects.list;
    let _dispatchToken = 0; // unused in logic now; kept for onLoadStart loading state

    const renderer = initRenderer({
        tbodyId: 'proj-tbody',
        colspan: _activeColumns.length,
        itemLabel: 'projects',
        rowTemplate: renderProjectRow,
        emptyState: {
            message: 'No projects yet.',
            link: { href: '#', label: 'Add the first one', onClick: 'openAddModal()' },
        },
        filterEmptyState: {
            message: 'No projects match your filters.',
            link: { href: '#', label: 'Create a new one', onClick: 'openAddModal()' },
        },
        paginationBarId: 'proj-pagination-bar',
        paginationInfoId: 'proj-pagination-info',
        paginationControlsId: 'proj-pagination-controls',
        onPageChange: (page) => fetcher.goToPage(page),
    });

    const fetcher = initFetchMulti({
        apiUrl: href,
        pageSize: 20,
        searchInputId: 'proj-search',
        filters: [],
        multiFilters: [
            { id: 'prog-filter', param: 'programme' },
            { id: 'proj-filter', param: 'project' },
            { id: 'status-filter', param: 'status' },
            { id: 'substatus-filter', param: 'sub_status' },
            { id: 'team-filter', param: 'team' },
            { id: 'priority-filter', param: 'priority' },
            { id: 'confidence-filter', param: 'confidence' },
            { id: 'ptype-filter', param: 'project_type' },
            { id: 'tag-filter', param: 'tags' },
            { id: 'active-filter', param: 'is_active' },
        ],
        onLoadStart: () => {
            cancelAnimationFrame(renderer._pendingRaf);
            renderer._pendingRaf = null;
            renderer.renderLoading('Loading projects…');
        },
        onSuccess: ({ results, pagination, state }) => {
            // Always cancel any previously queued render before scheduling ours.
            // This means whichever fetch resolves LAST wins: it cancels all earlier
            // queued renders and installs its own. Earlier fetches that resolve
            // first will have their rAF cancelled by the next onSuccess call.
            cancelAnimationFrame(renderer._pendingRaf);
            renderer._pendingRaf = requestAnimationFrame(() => {
                renderer._pendingRaf = null;
                const hasFilters =
                    !!state.search ||
                    Object.keys(state.multiFilters).length > 0 ||
                    Object.keys(state.filters).length > 0;
                renderer.renderRows(results, hasFilters);
                renderer.renderPagination(pagination);
            });
        },
        onError: () => renderer.renderError('Failed to load projects. Please refresh the page.'),
    });

    initSorting({ tableId: 'proj-table', fetcher });
    if (!skipInitialFetch) {
        fetcher.refresh();
    }

    window._projFetcher = fetcher;
    window._projRenderer = renderer;
    window._projBaseApiUrl = href;

    _applyColumnVisibility();
}

function _colVisible(key) {
    const def = COLUMN_DEFS.find((c) => c.key === key);
    return def?.fixed || _activeColumns.includes(key);
}

function _td(key, content) {
    return _colVisible(key) ? `<td data-col="${key}">${content}</td>` : '';
}

function renderProjectRow(proj) {
    const detailUrl = URLS.projects.detail(proj.id);

    return `
        <tr data-project-id="${proj.id}">
            ${_td('name', `<a href="${detailUrl}" class="rp-link fw-500">${escHtml(proj.name)}</a>${proj.via_onboarding ? ' <span class="rp-badge rp-badge--info ms-1" title="Created via Onboarding Form">Onboarding</span>' : ''}`)}
            ${_td('project_type', escHtml(proj.project_type_name ?? '-'))}
            ${_td('programme', escHtml(proj.programme_name ?? '-'))}
            ${_td('code', `<span class="rp-code">${escHtml(proj.code || '-')}</span>`)}
            ${_td('status', _statusBadge(proj.status, proj.status_display))}
            ${_td('sub_status', proj.sub_status_name ? `<span class="rp-badge rp-badge--muted">${escHtml(proj.sub_status_name)}</span>` : '-')}
            ${_td('assigned_team', escHtml(proj.assigned_team_name ?? '-'))}
            ${_td('confidence', _levelBadge(proj.confidence, proj.confidence_display))}
            ${_td('priority', _levelBadge(proj.priority, proj.priority_display))}
            ${_td(
                'is_active',
                proj.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>',
            )}
            ${_td(
                'budget_risk',
                proj.budget_risk
                    ? `<span class="rp-badge rp-badge--warning">${escHtml(proj.budget_risk)}</span>`
                    : '-',
            )}
            ${_td(
                'actions',
                `
                <div class="d-flex justify-content-center gap-1">
                    <a href="${detailUrl}" class="btn btn-ghost-icon" title="View project">
                        <i class="bi bi-eye"></i>
                    </a>
                    ${hasPerm('projects.change_project') ? `
                    <button class="btn btn-ghost-icon" title="Assign team"
                            onclick="openAssignTeamModal(${proj.id}, '${escAttr(proj.name)}', ${proj.assigned_team ?? 'null'})">
                        <i class="bi bi-people"></i>
                    </button>
                    <button class="btn btn-ghost-icon ${proj.is_active ? 'btn-ghost-icon--danger' : 'btn-ghost-icon--success'}"
                            title="${proj.is_active ? 'Deactivate' : 'Activate'} project"
                            onclick="openActiveModal(${proj.id}, '${escAttr(proj.name)}', ${proj.is_active})">
                        <i class="bi bi-check-circle"></i>
                    </button>` : ''}
                    ${hasPerm('projects.delete_project') ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger" title="Delete project"
                            onclick="openDeleteModal(${proj.id}, '${escAttr(proj.name)}')">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            `,
            )}
        </tr>
    `;
}

function _statusBadge(status, label) {
    if (!status) return '—';
    return `<span class="rp-badge rp-badge-status--${status.toLowerCase()}">${escHtml(label || status)}</span>`;
}

function _levelBadge(value, label) {
    if (!value) return '<span class="text-muted">-</span>';
    const key = value.toLowerCase().replace(/_/g, '-');
    return `<span class="rp-badge rp-badge-level--${key}">${escHtml(label || value)}</span>`;
}

function openAddModal() {
    resetAddModal();

    document.getElementById('proj-modal-status').value = 'NEW';
    _cascadeModalSubStatus();
    document.getElementById('proj-modal-banner').classList.add('d-none');

    const saveBtn = document.getElementById('proj-modal-save');
    saveBtn.dataset.mode = 'add';
    saveBtn.dataset.id = '';
    saveBtn.textContent = 'Create project';

    document.getElementById('proj-modal-title').textContent = 'New Project';
    _showModal('projModal');
    setTimeout(() => document.getElementById('proj-modal-name').focus(), 300);
}

function resetAddModal() {
    [
        'proj-modal-name',
        'proj-modal-type',
        'proj-modal-programme',
        'proj-modal-programme-id',
        'proj-modal-code',
        'proj-modal-status',
        'proj-modal-substatus',
        'proj-modal-confidence',
        'proj-modal-priority',
        'proj-modal-start',
        'proj-modal-end',
    ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    clearAddModalErrors();
}

function clearAddModalErrors() {
    document.getElementById('proj-modal-banner')?.classList.add('d-none');
    ['proj-modal-name', 'proj-modal-type'].forEach((id) => {
        document.getElementById(id)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${id}-err`);
        if (errEl) errEl.textContent = '';
    });
}

function bindModalEvents() {
    document.getElementById('projModal')?.addEventListener('hidden.bs.modal', resetAddModal);
    document.getElementById('proj-modal-save')?.addEventListener('click', handleModalSave);
    document.getElementById('confirm-active-btn')?.addEventListener('click', handleConfirmActive);
    document.getElementById('confirm-delete-btn')?.addEventListener('click', handleConfirmDelete);
    document
        .getElementById('confirm-assign-team-btn')
        ?.addEventListener('click', handleConfirmAssignTeam);
    document.getElementById('projModal')?.addEventListener('shown.bs.modal', () => {
        const inputEl = document.getElementById('proj-modal-programme');
        const suggestionsEl = document.getElementById('proj-modal-programme-suggestions');
        if (inputEl & suggestionsEl) {
            suggestionsEl.style.width = inputEl.getBoundingClientRect().width + 'px';
        }
    });

    _bindProgrammeAutocomplete(
        'proj-modal-programme',
        'proj-modal-programme-id',
        'proj-modal-programme-suggestions',
    );
}

function _bindProgrammeAutocomplete(inputId, hiddenId, suggestionsId) {
    const input = document.getElementById(inputId);
    const hiddenInput = document.getElementById(hiddenId);
    const suggestions = document.getElementById(suggestionsId);
    if (!input || !suggestions) return;

    input.addEventListener('input', () => {
        const val = input.value.trim().toLowerCase();
        hiddenInput.value = '';

        const progs = window._progOptions ?? [];
        const matches =
            val.length < 1
                ? []
                : progs.filter((p) => p.name.toLowerCase().includes(val)).slice(0, 10);

        if (!matches.length) {
            suggestions.style.display = 'none';
            return;
        }

        suggestions.innerHTML = matches
            .map(
                (p) =>
                    `<button type="button" class="list-group-item list-group-item-action py-1 px-2 small"
                     data-id="${p.id}" data-name="${escAttr(p.name)}">
                ${escHtml(p.name)}
             </button>`,
            )
            .join('');
        suggestions.style.display = 'block';
    });

    suggestions.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-id]');
        if (!btn) return;
        input.value = btn.dataset.name;
        hiddenInput.value = btn.dataset.id;
        suggestions.style.display = 'none';
    });

    document.addEventListener('click', (e) => {
        if (!suggestions.contains(e.target) && e.target !== input) {
            suggestions.style.display = 'none';
        }
    });
}

async function handleModalSave() {
    clearAddModalErrors();

    const name = document.getElementById('proj-modal-name').value.trim();
    const project_type = document.getElementById('proj-modal-type').value;
    const progInput = document.getElementById('proj-modal-programme').value.trim();
    const progId = document.getElementById('proj-modal-programme-id').value;

    let hasErrors = false;
    if (!name) {
        _setFieldError('proj-modal-name', 'proj-modal-name-err', 'Name is required.');
        hasErrors = true;
    }
    if (!project_type) {
        _setFieldError('proj-modal-type', 'proj-modal-type-err', 'Project type is required.');
        hasErrors = true;
    }
    if (hasErrors) return;

    const saveBtn = document.getElementById('proj-modal-save');
    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        let programme = progId || null;
        if (!programme && progInput) {
            programme = await _resolveOrCreateProgramme(progInput);
        }

        const newStatus = document.getElementById('proj-modal-status').value || 'NEW';
        const completedSprintVal = document.getElementById('proj-modal-completed-sprint')?.value;
        const payload = {
            name,
            project_type: parseInt(project_type),
            programme: programme ? parseInt(programme) : null,
            code: document.getElementById('proj-modal-code').value.trim(),
            status: newStatus,
            sub_status: document.getElementById('proj-modal-substatus').value || null,
            confidence: document.getElementById('proj-modal-confidence').value || '',
            priority: document.getElementById('proj-modal-priority').value || '',
            tentative_start_date: document.getElementById('proj-modal-start').value || null,
            tentative_end_date: document.getElementById('proj-modal-end').value || null,
            completed_sprint: (newStatus === 'COMPLETED' && completedSprintVal)
                ? parseInt(completedSprintVal, 10)
                : null,
        };

        const { method, href } = API_URLS.projects.new;
        const created = await apiFetch(href, {
            method,
            body: JSON.stringify(payload),
        });

        showFlash(`"${name}" created successfully.`, 'success');
        _hideModal('projModal');

        window.location.href = URLS.projects.detail(created.id);
    } catch (err) {
        const msg = _extractError(err, 'Failed to save project. Please try again.');
        const banner = document.getElementById('proj-modal-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function _resolveOrCreateProgramme(name) {
    const existing = (window._progOptions ?? []).find(
        (p) => p.name.toLowerCase() === name.toLowerCase(),
    );
    if (existing) return existing.id;

    const { method, href } = API_URLS.programmes.create;
    const created = await apiFetch(href, {
        method,
        body: JSON.stringify({ name }),
    });

    if (!window._progOptions) window._progOptions = [];
    window._progOptions.push({ id: created.id, name: created.name });

    return created.id;
}

function openAssignTeamModal(projectId, projectName, currentTeamId) {
    document.getElementById('proj-assign-team-project-name').textContent =
        `Project: ${projectName}`;
    document.getElementById('assign-team-select').value = currentTeamId ?? '';
    document.getElementById('proj-assign-team-banner').classList.add('d-none');

    const confirmBtn = document.getElementById('confirm-assign-team-btn');
    confirmBtn.dataset.projectId = projectId;

    _showModal('projAssignTeamModal');
}

async function handleConfirmAssignTeam() {
    const btn = document.getElementById('confirm-assign-team-btn');
    const projectId = btn.dataset.projectId;
    const teamVal = document.getElementById('assign-team-select').value;
    const teamId = teamVal ? parseInt(teamVal) : null;

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const { method, href } = API_URLS.projects.edit_teams(projectId);
        await apiFetch(href, { method, body: JSON.stringify({ assigned_team: teamId }) });
        showFlash('Team assigned successfully.', 'success');
        _hideModal('projAssignTeamModal');
        _refreshTable();
    } catch (err) {
        const msg = _extractError(err, 'Failed to assign team. Please try again.');
        const banner = document.getElementById('proj-assign-team-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

function openActiveModal(id, name, isActive) {
    const titleEl = document.getElementById('proj-active-modal-title');
    const messageEl = document.getElementById('proj-active-message');
    const confirmBtn = document.getElementById('confirm-active-btn');

    const action = isActive ? 'deactivated' : 'activated';
    titleEl.textContent = isActive ? 'Deactivate Project' : 'Activate Project';
    confirmBtn.textContent = isActive ? 'Deactivate' : 'Activate';
    confirmBtn.className = `btn btn-sm ${isActive ? 'btn-danger' : 'btn-success'}`;
    confirmBtn.dataset.id = id;
    confirmBtn.dataset.isActive = isActive;

    messageEl.innerHTML = `<strong>${escHtml(name)}</strong> will be ${action}. Do you want to proceed?`;
    document.getElementById('proj-active-modal-banner').classList.add('d-none');
    _showModal('projActiveModal');
}

async function handleConfirmActive() {
    const btn = document.getElementById('confirm-active-btn');
    const id = btn.dataset.id;
    const isActive = btn.dataset.isActive === 'true';

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        const { method, href } = API_URLS.projects.partial_edit(id);
        await apiFetch(href, { method, body: JSON.stringify({ is_active: !isActive }) });
        showFlash(`Project ${isActive ? 'deactivated' : 'activated'}.`, 'success');
        _hideModal('projActiveModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to update project. Please try again.');
        const banner = document.getElementById('proj-active-modal-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

function openDeleteModal(id, name) {
    document.getElementById('proj-delete-name').textContent = name;
    document.getElementById('confirm-delete-btn').dataset.id = id;
    document.getElementById('confirm-delete-btn').dataset.name = name;
    document.getElementById('proj-delete-modal-banner').classList.add('d-none');
    _showModal('projDeleteModal');
}

async function handleConfirmDelete() {
    const btn = document.getElementById('confirm-delete-btn');
    const id = btn.dataset.id;
    const name = btn.dataset.name;

    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        const { method, href } = API_URLS.projects.delete(id);
        await apiFetch(href, { method });
        showFlash(`"${name}" deleted.`, 'success');
        _hideModal('projDeleteModal');
        _refreshTable();
        await loadStats();
    } catch (err) {
        const msg = _extractError(err, 'Failed to delete project. Please try again.');
        const banner = document.getElementById('proj-delete-modal-banner');
        banner.textContent = msg;
        banner.classList.remove('d-none');
    } finally {
        btn.disabled = false;
        btn.textContent = prevText;
    }
}

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled = true;
        btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.projects.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `projects-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Projects', filename);
        }
    } catch (err) {
        showFlash('Export failed. Please try again.', 'error');
        console.error('[runListExport] Export failed.', err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

function _showModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id), { focus: false }).show();
}

function _hideModal(id) {
    bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).hide();
}

function _refreshTable() {
    window._projFetcher?.refresh();
}

function _setFieldError(inputId, errId, message) {
    document.getElementById(inputId)?.classList.add('is-invalid');
    const errEl = document.getElementById(errId);
    if (errEl) errEl.textContent = message;
}

function _extractError(err, fallback) {
    if (err?.data?.details) {
        const details = err.data.details;
        if (typeof details === 'string') return details;
        if (Array.isArray(details)) return details.join(' ');
        if (typeof details === 'object') return Object.values(details).flat().join(' ');
    }
    if (err?.data?.error) return err.data.error;
    return fallback;
}

window.openAddModal = openAddModal;
window.openAssignTeamModal = openAssignTeamModal;
window.openActiveModal = openActiveModal;
window.openDeleteModal = openDeleteModal;
window._clearProjectFilters = function () {
    _MULTI_FILTER_IDS.forEach((id) => {
        const el = document.getElementById(id);
        if (el) Array.from(el.options).forEach((o) => (o.selected = false));
    });
    _populateMultiSelect('substatus-filter', _allSubStatuses, { useIdAsValue: true });
    _activeViewId = null;
    _renderViewsBar();
    _updateClearBtn();
    window._projFetcher?.syncAndRefresh();
};
