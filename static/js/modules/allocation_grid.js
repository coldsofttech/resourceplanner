'use strict';

import {
    apiFetch,
    escHtml,
    getPkFromUrl,
    setPageTitle,
} from './../main.js';
import { API_URLS } from './../urls.js';

const planPk    = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

let _colMode         = 'sprint';
let _mergeMonths     = false;
let _activeTeamId    = null;
let _activeAllocSetId = null;
let _isActiveSet     = false;   // true when selected set has status=ACTIVE
let _hasPlOverrides  = false;
let _teamList        = [];

let _capacityData = null;
let _absencesData = null;
let _allocData    = null;
let _utilData     = null;

let _filters = {
    members:         [],   // selected member names (multi-select)
    programmes:      [],   // selected programme names (multi-select)
    projects:        [],   // selected project names (multi-select)
    teams:           [],   // selected team IDs (multi-select)
    employmentTypes: [],   // selected employment type names (multi-select)
};

// Editing state
let _editingTd    = null;  // currently open input cell
let _saving       = false;

// Engine polling state
let _enginePollTimer = null;
let _engineJobId     = null;

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
    if (!planPk || !versionPk) return;

    _bindColModeToggle();
    _bindScrollSync();
    _bindAccordionControls();
    _bindFilters();
    _bindEngineModal();
    _bindCellEditing();

    try {
        const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
        document.getElementById('ag-plan-name').textContent = ver.plan_name ?? '—';
        document.getElementById('ag-version-badge').innerHTML =
            `<span class="badge bg-secondary">v${ver.version}</span>`;
        setPageTitle(`Grid — ${ver.plan_name ?? ''}`);

        const bc = document.getElementById('ag-breadcrumb');
        if (bc) bc.innerHTML =
            `<a href="/resource-plans/${planPk}/" class="text-decoration-none text-secondary">Resource Plans</a>`;

        _hasPlOverrides = !!ver.has_pl_overrides;
        const badge = document.getElementById('ag-override-badge');
        if (badge) badge.classList.toggle('d-none', !_hasPlOverrides);

        const overridesSection = document.getElementById('ag-engine-overrides-section');
        if (overridesSection) overridesSection.classList.toggle('d-none', !_hasPlOverrides);
    } catch (_) {}

    await _loadTeamTabs();
    await _loadAllocationSets();
    await Promise.all([_loadAll(), _loadConflictSummary()]);
}

// ── Column mode & merge toggle ────────────────────────────────────────────────

function _bindColModeToggle() {
    document.querySelectorAll('input[name="ag-col-mode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            _colMode = radio.value;
            _toggleMergeVisibility();
            _rerender();
        });
    });
    document.getElementById('ag-merge-toggle')?.addEventListener('change', e => {
        _mergeMonths = e.target.checked;
        _rerender();
    });
}

function _toggleMergeVisibility() {
    const wrap = document.getElementById('ag-merge-wrap');
    if (wrap) wrap.classList.toggle('d-none', _colMode !== 'month');
}

function _rerender() {
    if (_capacityData) _renderCapacityTable(_capacityData);
    if (_absencesData) _renderAbsencesTable(_absencesData);
    if (_utilData)     _renderUtilTable(_utilData);
    if (_allocData)    _renderAllocTable(_allocData);
}

// ── Accordion expand/collapse all ─────────────────────────────────────────────

function _bindAccordionControls() {
    document.getElementById('ag-expand-all')?.addEventListener('click', () => {
        document.querySelectorAll('#ag-accordion .collapse').forEach(el => {
            const btn = document.querySelector(`[data-bs-target="#${el.id}"]`);
            if (!el.classList.contains('show')) {
                el.classList.add('show');
                if (btn) { btn.setAttribute('aria-expanded', 'true'); btn.classList.remove('collapsed'); }
            }
        });
    });
    document.getElementById('ag-collapse-all')?.addEventListener('click', () => {
        document.querySelectorAll('#ag-accordion .collapse').forEach(el => {
            const btn = document.querySelector(`[data-bs-target="#${el.id}"]`);
            if (el.classList.contains('show')) {
                el.classList.remove('show');
                if (btn) { btn.setAttribute('aria-expanded', 'false'); btn.classList.add('collapsed'); }
            }
        });
    });
}

// ── Scroll synchronisation ────────────────────────────────────────────────────

function _bindScrollSync() {
    const wrapIds = ['ag-capacity-grid-wrap', 'ag-absences-grid-wrap', 'ag-util-grid-wrap', 'ag-alloc-grid-wrap'];
    const ghost   = document.getElementById('ag-hscroll');
    let syncing   = false;

    const _sync = (src) => {
        if (syncing) return;
        syncing = true;
        const x = src.scrollLeft;
        const wraps = wrapIds.map(id => document.getElementById(id)).filter(Boolean);
        [...wraps, ghost].forEach(el => { if (el && el !== src) el.scrollLeft = x; });
        syncing = false;
    };

    wrapIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('scroll', () => _sync(el));
    });
    if (ghost) ghost.addEventListener('scroll', () => _sync(ghost));
}

function _updateGhostWidth() {
    const ghost = document.getElementById('ag-hscroll');
    const inner = document.getElementById('ag-hscroll-inner');
    if (!ghost || !inner) return;

    const pairs = [
        ['ag-capacity-table',  'ag-capacity-grid-wrap'],
        ['ag-absences-table',  'ag-absences-grid-wrap'],
        ['ag-util-table',      'ag-util-grid-wrap'],
        ['ag-alloc-table',     'ag-alloc-grid-wrap'],
    ];
    let maxW = 0; let refWrap = null;
    pairs.forEach(([tid, wid]) => {
        const t = document.getElementById(tid);
        const w = document.getElementById(wid);
        if (t && w && !w.classList.contains('d-none')) {
            maxW = Math.max(maxW, t.scrollWidth);
            if (!refWrap) refWrap = w;
        }
    });
    inner.style.width = maxW + 'px';
    ghost.classList.toggle('d-none', !refWrap || maxW <= refWrap.clientWidth);
}

// ── Multi-select filters ───────────────────────────────────────────────────────

function _bindFilters() {
    const clearEl  = document.getElementById('ag-filter-clear');
    const teamEl   = document.getElementById('ag-filter-team');
    const memberEl = document.getElementById('ag-filter-member');
    const progEl   = document.getElementById('ag-filter-programme');
    const projEl   = document.getElementById('ag-filter-project');
    const empEl    = document.getElementById('ag-filter-employment-type');

    const _onChange = () => {
        _filters.members         = _getMultiSelectValues(memberEl);
        _filters.programmes      = _getMultiSelectValues(progEl);
        _filters.projects        = _getMultiSelectValues(projEl);
        _filters.teams           = _activeTeamId === null ? _getMultiSelectValues(teamEl) : [];
        _filters.employmentTypes = _getMultiSelectValues(empEl);
        _updateFilterBadge();
        _rerender();
    };

    memberEl?.addEventListener('change', _onChange);
    progEl?.addEventListener('change', _onChange);
    projEl?.addEventListener('change', _onChange);
    teamEl?.addEventListener('change', _onChange);
    empEl?.addEventListener('change', _onChange);

    clearEl?.addEventListener('click', () => {
        if (memberEl) Array.from(memberEl.options).forEach(o => o.selected = false);
        if (progEl)   Array.from(progEl.options).forEach(o => o.selected = false);
        if (projEl)   Array.from(projEl.options).forEach(o => o.selected = false);
        if (teamEl)   Array.from(teamEl.options).forEach(o => o.selected = false);
        if (empEl)    Array.from(empEl.options).forEach(o => o.selected = false);
        _filters = { members: [], programmes: [], projects: [], teams: [], employmentTypes: [] };
        _updateFilterBadge();
        _rerender();
    });
}

function _getMultiSelectValues(sel) {
    if (!sel) return [];
    return Array.from(sel.selectedOptions).map(o => o.value).filter(Boolean);
}

function _populateFilterOptions(allocData) {
    const memberEl = document.getElementById('ag-filter-member');
    const progEl   = document.getElementById('ag-filter-programme');
    const projEl   = document.getElementById('ag-filter-project');
    const teamEl   = document.getElementById('ag-filter-team');
    const empEl    = document.getElementById('ag-filter-employment-type');

    const members         = new Set();
    const programmes      = new Set();
    const projects        = new Set();
    const teams           = new Map(); // id → name
    const employmentTypes = new Set();

    (allocData.rows ?? []).forEach(r => {
        if (r.member_name)              members.add(r.member_name);
        if (r.programme_name)           programmes.add(r.programme_name);
        if (r.project_name)             projects.add(r.project_name);
        if (r.team_id != null && r.team_name) teams.set(String(r.team_id), r.team_name);
        if (r.member_employment_type)   employmentTypes.add(r.member_employment_type);
    });

    _refillSelect(memberEl, [...members].sort());
    _refillSelect(progEl,   [...programmes].sort());
    _refillSelect(projEl,   [...projects].sort());
    _refillTeamSelect(teamEl, [...teams.entries()].sort((a, b) => a[1].localeCompare(b[1])));
    _refillSelect(empEl,    [...employmentTypes].sort());
}

function _refillTeamSelect(sel, entries) {
    if (!sel) return;
    const prev = new Set(_getMultiSelectValues(sel));
    sel.innerHTML = '';
    entries.forEach(([id, name]) => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = name;
        opt.selected = prev.has(id);
        sel.appendChild(opt);
    });
}

function _refillSelect(sel, values) {
    if (!sel) return;
    const prev = new Set(_getMultiSelectValues(sel));
    sel.innerHTML = '';
    values.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        opt.selected = prev.has(v);
        sel.appendChild(opt);
    });
}

function _updateFilterBadge() {
    const badge = document.getElementById('ag-filter-active-badge');
    if (!badge) return;
    const hasFilters = _filters.members.length > 0 || _filters.programmes.length > 0
        || _filters.projects.length > 0 || _filters.teams.length > 0
        || _filters.employmentTypes.length > 0;
    badge.classList.toggle('d-none', !hasFilters);
}

async function _loadConflictSummary() {
    if (!planPk || !versionPk) return;
    try {
        const summary = await apiFetch(API_URLS.rp_versions.conflicts.summary(planPk, versionPk).href);
        const badge = document.getElementById('ag-header-conflict-badge');
        if (badge) {
            if (summary.open_errors > 0) {
                badge.textContent = `${summary.open_errors} error${summary.open_errors !== 1 ? 's' : ''}`;
                badge.className = 'badge bg-danger ms-1';
                badge.classList.remove('d-none');
            } else if (summary.open > 0) {
                badge.textContent = `${summary.open}`;
                badge.className = 'badge bg-warning text-dark ms-1';
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
            }
        }
    } catch (_) {}
}

function _filterMemberRows(rows) {
    return rows.filter(r => {
        if (_filters.members.length > 0 && r.member_id != null && !_filters.members.includes(r.member_name)) return false;
        if (_filters.teams.length > 0   && !_filters.teams.includes(String(r.team_id ?? ''))) return false;
        return true;
    });
}

function _filterAllocRows(rows) {
    return rows.filter(r => {
        if (_filters.members.length > 0         && !_filters.members.includes(r.member_name))       return false;
        if (_filters.programmes.length > 0      && !_filters.programmes.includes(r.programme_name)) return false;
        if (_filters.projects.length > 0        && !_filters.projects.includes(r.project_name))     return false;
        if (_filters.teams.length > 0           && !_filters.teams.includes(String(r.team_id ?? ''))) return false;
        if (_filters.employmentTypes.length > 0 && !_filters.employmentTypes.includes(r.member_employment_type ?? '')) return false;
        return true;
    });
}

// ── Team tabs ─────────────────────────────────────────────────────────────────

async function _loadTeamTabs() {
    const tabList        = document.getElementById('ag-team-tabs');
    const teamFilter     = document.getElementById('ag-filter-team');
    const teamFilterWrap = document.getElementById('ag-filter-team-wrap');
    if (!tabList) return;

    try {
        _teamList = await apiFetch(API_URLS.rp_versions.grid.teams(planPk, versionPk).href);

        _teamList.forEach(t => {
            const li = document.createElement('li');
            li.className = 'nav-item';
            li.setAttribute('role', 'presentation');
            li.innerHTML =
                `<button class="nav-link" type="button" role="tab" data-team-id="${t.id}">${escHtml(t.name)}</button>`;
            tabList.appendChild(li);
        });

        // Team filter options are populated from alloc data in _populateFilterOptions
    } catch (_) {}

    tabList.addEventListener('click', async e => {
        const btn = e.target.closest('[data-team-id]');
        if (!btn) return;
        tabList.querySelectorAll('.nav-link').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _activeTeamId = btn.dataset.teamId || null;

        _filters.teams = [];
        if (teamFilter) Array.from(teamFilter.options).forEach(o => o.selected = false);
        const isAllTeams = _activeTeamId === null;
        if (teamFilterWrap) teamFilterWrap.classList.toggle('d-none', !isAllTeams);

        // Clear lazy alloc state so switcher reloads cleanly
        _allocData = null;
        _utilData  = null;
        await _loadAll();
    });

    if (teamFilterWrap) teamFilterWrap.classList.remove('d-none');
}

// ── Allocation sets ───────────────────────────────────────────────────────────

async function _loadAllocationSets() {
    const sel         = document.getElementById('ag-alloc-set-select');
    const activateBtn = document.getElementById('ag-alloc-set-activate');
    if (!sel) return;

    try {
        const sets = await apiFetch(API_URLS.rp_versions.allocation_sets.list(planPk, versionPk).href);
        sel.innerHTML = '<option value="">— None —</option>';

        let activeSetId = null;
        sets.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.dataset.status = s.status;
            opt.dataset.conflicts = s.conflict_count ?? 0;
            if (s.status === 'ACTIVE') {
                opt.textContent = `Set #${s.id} — Active ✓`;
                opt.selected = true;
                activeSetId = s.id;
            } else {
                opt.textContent = `Set #${s.id} — ${s.status}`;
                if (!activeSetId && s.status === 'DRAFT') {
                    // Pre-select latest DRAFT if no ACTIVE
                    opt.selected = true;
                    activeSetId = s.id;
                }
            }
            sel.appendChild(opt);
        });
        _activeAllocSetId = activeSetId;
        _syncActiveSetState(sel, activateBtn);
    } catch (_) {}

    sel.addEventListener('change', async () => {
        _cancelCurrentEdit();
        _activeAllocSetId = sel.value ? parseInt(sel.value, 10) : null;
        _syncActiveSetState(sel, activateBtn);
        // Clear lazy data so tables reload for the new set
        _allocData = null;
        _utilData  = null;
        await _loadAllocTables();
    });

    if (activateBtn) {
        activateBtn.addEventListener('click', async () => {
            if (!_activeAllocSetId) return;

            const opt = sel.querySelector(`option[value="${_activeAllocSetId}"]`);
            const conflicts = parseInt(opt?.dataset.conflicts ?? '0', 10);
            if (conflicts > 0) {
                if (!confirm(`This set has ${conflicts} conflict(s). Activate anyway?`)) return;
            }

            activateBtn.disabled = true;
            try {
                const updated = await apiFetch(
                    API_URLS.rp_versions.allocation_sets.activate(planPk, versionPk, _activeAllocSetId).href,
                    { method: 'POST' }
                );
                // Reload sets to reflect new status
                await _loadAllocationSets();
                // Rerender alloc table as read-only
                if (_allocData) _renderAllocTable(_allocData);
            } catch (err) {
                alert(`Activate failed: ${err.message ?? err}`);
            } finally {
                activateBtn.disabled = false;
            }
        });
    }
}

function _syncActiveSetState(sel, activateBtn) {
    const opt = sel.querySelector(`option[value="${_activeAllocSetId}"]`);
    _isActiveSet = (opt?.dataset.status === 'ACTIVE');

    // Activate button visibility — only show for DRAFT sets
    if (activateBtn) {
        activateBtn.classList.toggle('d-none', !_activeAllocSetId || _isActiveSet);
    }

    // ACTIVE banner
    _updateActiveBanner(_isActiveSet);
}

function _updateActiveBanner(isActive) {
    const banner = document.getElementById('ag-active-set-banner');
    if (!banner) return;
    if (isActive) {
        banner.innerHTML = `<i class="bi bi-lock-fill me-2"></i>
            <strong>Active allocation set.</strong>
            Cells are read-only. Run the engine to create a new DRAFT set for editing.`;
        banner.classList.remove('d-none');
    } else {
        banner.classList.add('d-none');
    }
}

// ── Conflict count badge ──────────────────────────────────────────────────────

function _updateConflictBadge(count) {
    const el = document.getElementById('ag-conflict-badge');
    if (!el) return;
    if (!_activeAllocSetId || count == null) { el.classList.add('d-none'); return; }
    el.textContent = count > 0 ? `${count} conflict${count !== 1 ? 's' : ''}` : '';
    el.className = count > 0
        ? 'badge bg-danger ms-2'
        : 'badge bg-success ms-2';
    el.classList.toggle('d-none', count === 0);
}

// ── Load helpers ──────────────────────────────────────────────────────────────

async function _loadAll() {
    await Promise.all([_loadCapacity(), _loadAbsences(), _loadAllocTables()]);
    _updateGhostWidth();
}

async function _loadAllocTables() {
    await Promise.all([_loadAllocatedCapacity(), _loadAllocations()]);
    _updateGhostWidth();
}

// ── Capacity table (Table 1) ──────────────────────────────────────────────────

async function _loadCapacity() {
    const loading = document.getElementById('ag-capacity-loading');
    const empty   = document.getElementById('ag-capacity-empty');
    const wrap    = document.getElementById('ag-capacity-grid-wrap');

    loading?.classList.remove('d-none');
    empty?.classList.add('d-none');
    wrap?.classList.add('d-none');

    try {
        let url = API_URLS.rp_versions.grid.capacity(planPk, versionPk).href;
        if (_activeTeamId) url += `?team=${_activeTeamId}`;
        _capacityData = await apiFetch(url);

        loading?.classList.add('d-none');
        if (!_capacityData.rows?.length) {
            empty?.classList.remove('d-none');
        } else {
            wrap?.classList.remove('d-none');
            _renderCapacityTable(_capacityData);
        }
    } catch (_) {
        loading?.classList.add('d-none');
        if (empty) { empty.classList.remove('d-none'); empty.textContent = 'Failed to load capacity.'; }
    }
}

function _capCls(net) {
    if (net === 10) return 'ag-cell-full';
    if (net > 8)   return 'ag-cell-good';
    if (net > 5)   return 'ag-cell-fair';
    if (net > 3)   return 'ag-cell-ok';
    if (net > 0)   return 'ag-cell-low';
    return 'ag-cell-zero';
}

function _renderCapacityTable(data) {
    const head = document.getElementById('ag-capacity-head');
    const body = document.getElementById('ag-capacity-body');
    if (!head || !body) return;

    const showTeam = _activeTeamId === null;
    const cols     = _groupCols(data.sprints);
    const merged   = _colMode === 'month' && _mergeMonths;

    const table = document.getElementById('ag-capacity-table');
    if (table) table.classList.toggle('ag-no-team-col', !showTeam);

    let h1 = '<tr>';
    if (showTeam) {
        h1 += '<th class="ag-col-member">Member</th>';
        h1 += '<th class="ag-col-team" colspan="4">Team</th>';
    } else {
        h1 += '<th class="ag-col-member" colspan="5">Member</th>';
    }
    for (let i = 0; i < cols.length; i++) {
        const sep  = i > 0 ? ' ag-col-sep' : '';
        const span = merged ? 1 : cols[i].span;
        h1 += `<th colspan="${span}" class="${sep}" title="${escHtml(cols[i].key)}">${escHtml(cols[i].label)}</th>`;
    }
    h1 += '</tr>';
    head.innerHTML = h1;

    const rows = _filterMemberRows(data.rows ?? []);
    let html = '';
    for (const row of rows) {
        const cm = {};
        row.cells.forEach(c => { cm[c.sprint_id] = c; });
        if (showTeam) {
            html += `<tr><td class="ag-col-member" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
            html += `<td class="ag-col-team" colspan="4" title="${escHtml(row.team_name ?? '')}">${escHtml(row.team_name ?? '—')}</td>`;
        } else {
            html += `<tr><td class="ag-col-member" colspan="5" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
        }

        for (let i = 0; i < cols.length; i++) {
            const sep = i > 0 ? ' ag-col-sep' : '';
            if (merged) {
                let sumNet = 0; let hasAny = false;
                for (const s of cols[i].sprints) {
                    const c = cm[s.id] ?? {};
                    if (c.net_capacity != null) { sumNet += parseFloat(c.net_capacity); hasAny = true; }
                }
                const cls = hasAny ? _capCls(sumNet) : '';
                html += `<td class="${cls}${sep}" title="${escHtml(cols[i].label)} — Net ${sumNet}d">${hasAny ? sumNet : '—'}</td>`;
            } else {
                for (let si = 0; si < cols[i].sprints.length; si++) {
                    const sprint = cols[i].sprints[si];
                    const c = cm[sprint.id] ?? {};
                    const net = parseFloat(c.net_capacity ?? 0);
                    const hasData = c.net_capacity != null;
                    const cls = hasData ? _capCls(net) : '';
                    const s = si === 0 ? sep : '';
                    html += `<td class="${cls}${s}" title="${escHtml(sprint.name)} — Net ${net}d">${hasData ? net : '—'}</td>`;
                }
            }
        }
        html += '</tr>';
    }
    body.innerHTML = html;
    _updateGhostWidth();
}

// ── Absences table (Table 2) ──────────────────────────────────────────────────

async function _loadAbsences() {
    const loading = document.getElementById('ag-absences-loading');
    const empty   = document.getElementById('ag-absences-empty');
    const wrap    = document.getElementById('ag-absences-grid-wrap');

    loading?.classList.remove('d-none');
    empty?.classList.add('d-none');
    wrap?.classList.add('d-none');

    try {
        let url = API_URLS.rp_versions.grid.absences(planPk, versionPk).href;
        if (_activeTeamId) url += `?team=${_activeTeamId}`;
        _absencesData = await apiFetch(url);

        loading?.classList.add('d-none');
        if (!_absencesData.rows?.length) {
            empty?.classList.remove('d-none');
        } else {
            wrap?.classList.remove('d-none');
            _renderAbsencesTable(_absencesData);
        }
    } catch (_) {
        loading?.classList.add('d-none');
        if (empty) { empty.classList.remove('d-none'); empty.textContent = 'Failed to load absences.'; }
    }
}

function _absCls(tot) {
    if (tot > 5) return 'ag-cell-low';
    if (tot > 2) return 'ag-cell-ok';
    return '';
}

function _renderAbsencesTable(data) {
    const head = document.getElementById('ag-absences-head');
    const body = document.getElementById('ag-absences-body');
    if (!head || !body) return;

    const showTeam = _activeTeamId === null;
    const cols     = _groupCols(data.sprints);
    const merged   = _colMode === 'month' && _mergeMonths;

    const table = document.getElementById('ag-absences-table');
    if (table) table.classList.toggle('ag-no-team-col', !showTeam);

    let h1 = '<tr>';
    if (showTeam) {
        h1 += '<th class="ag-col-member">Member</th>';
        h1 += '<th class="ag-col-team" colspan="4">Team</th>';
    } else {
        h1 += '<th class="ag-col-member" colspan="5">Member</th>';
    }
    for (let i = 0; i < cols.length; i++) {
        const sep  = i > 0 ? ' ag-col-sep' : '';
        const span = merged ? 1 : cols[i].span;
        h1 += `<th colspan="${span}" class="${sep}">${escHtml(cols[i].label)}</th>`;
    }
    h1 += '</tr>';
    head.innerHTML = h1;

    const rows = _filterMemberRows(data.rows ?? []);
    let html = '';
    for (const row of rows) {
        const cm = {};
        row.cells.forEach(c => { cm[c.sprint_id] = c; });
        if (showTeam) {
            html += `<tr><td class="ag-col-member" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
            html += `<td class="ag-col-team" colspan="4" title="${escHtml(row.team_name ?? '')}">${escHtml(row.team_name ?? '—')}</td>`;
        } else {
            html += `<tr><td class="ag-col-member" colspan="5" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
        }

        for (let i = 0; i < cols.length; i++) {
            const sep = i > 0 ? ' ag-col-sep' : '';
            if (merged) {
                let sumH = 0, sumL = 0, sumPh = 0; let hasAny = false;
                for (const s of cols[i].sprints) {
                    const c = cm[s.id] ?? {};
                    if (c.holiday_days != null) { sumH += parseFloat(c.holiday_days); hasAny = true; }
                    sumL  += parseFloat(c.leave_days ?? 0);
                    sumPh += parseFloat(c.placeholder_days ?? 0);
                }
                const tot = sumH + sumL + sumPh;
                const cls = _absCls(tot);
                const parts = [];
                if (sumH > 0)  parts.push(`<i class="bi bi-balloon-fill text-primary"></i>${sumH}`);
                if (sumL > 0)  parts.push(`<i class="bi bi-person-x-fill text-warning"></i>${sumL}`);
                if (sumPh > 0) parts.push(`<i class="bi bi-bookmark-fill text-info"></i>${sumPh}`);
                const inner = hasAny
                    ? `<div class="ag-abs-total">${tot > 0 ? tot : '0'}</div>`
                      + (parts.length ? `<div class="ag-abs-icons">${parts.join(' ')}</div>` : '')
                    : '—';
                html += `<td class="${cls}${sep} ag-abs-cell">${inner}</td>`;
            } else {
                for (let si = 0; si < cols[i].sprints.length; si++) {
                    const sprint = cols[i].sprints[si];
                    const c    = cm[sprint.id] ?? {};
                    const tot  = parseFloat(c.total_absence ?? 0);
                    const h    = parseFloat(c.holiday_days  ?? 0);
                    const l    = parseFloat(c.leave_days    ?? 0);
                    const ph   = parseFloat(c.placeholder_days ?? 0);
                    const hasData = c.holiday_days != null;
                    const cls  = _absCls(tot);
                    const s    = si === 0 ? sep : '';
                    const parts = [];
                    if (h > 0)  parts.push(`<i class="bi bi-balloon-fill text-primary"></i>${h}`);
                    if (l > 0)  parts.push(`<i class="bi bi-person-x-fill text-warning"></i>${l}`);
                    if (ph > 0) parts.push(`<i class="bi bi-bookmark-fill text-info"></i>${ph}`);
                    const inner = hasData
                        ? `<div class="ag-abs-total">${tot > 0 ? tot : '0'}</div>`
                          + (parts.length ? `<div class="ag-abs-icons">${parts.join(' ')}</div>` : '')
                        : '—';
                    html += `<td class="${cls}${s} ag-abs-cell" title="${escHtml(sprint.name)}">${inner}</td>`;
                }
            }
        }
        html += '</tr>';
    }
    body.innerHTML = html;
}

// ── Allocated Capacity table (Table 3) ────────────────────────────────────────

async function _loadAllocatedCapacity() {
    const noSet   = document.getElementById('ag-util-no-set');
    const loading = document.getElementById('ag-util-loading');
    const empty   = document.getElementById('ag-util-empty');
    const wrap    = document.getElementById('ag-util-grid-wrap');

    if (!_activeAllocSetId) {
        noSet?.classList.remove('d-none');
        loading?.classList.add('d-none');
        empty?.classList.add('d-none');
        wrap?.classList.add('d-none');
        _utilData = null;
        return;
    }

    noSet?.classList.add('d-none');
    loading?.classList.remove('d-none');
    empty?.classList.add('d-none');
    wrap?.classList.add('d-none');

    try {
        let url = API_URLS.rp_versions.grid.allocated_capacity(planPk, versionPk).href
            + `?allocation_set=${_activeAllocSetId}`;
        if (_activeTeamId) url += `&team=${_activeTeamId}`;
        _utilData = await apiFetch(url);

        loading?.classList.add('d-none');
        if (!_utilData.rows?.length) {
            empty?.classList.remove('d-none');
        } else {
            wrap?.classList.remove('d-none');
            _renderUtilTable(_utilData);
        }
    } catch (_) {
        loading?.classList.add('d-none');
        if (empty) { empty.classList.remove('d-none'); empty.textContent = 'Failed to load utilisation.'; }
    }
}

function _utilCls(pct) {
    if (pct > 100) return 'ag-util-over';
    if (pct > 80)  return 'ag-util-high';
    if (pct > 50)  return 'ag-util-mid';
    return 'ag-util-low';
}

function _allocDayCls(days) {
    if (days >= 10) return 'ag-util-full';
    if (days >= 8)  return 'ag-util-high';
    if (days >= 5)  return 'ag-util-mid';
    if (days >= 3)  return 'ag-util-low';
    if (days > 0)   return 'ag-util-vlow';
    return 'ag-util-zero';
}

function _utilBarCls(pct) {
    if (pct > 100) return 'over';
    if (pct > 80)  return 'high';
    if (pct > 50)  return 'mid';
    return 'low';
}

function _renderUtilTable(data) {
    const head = document.getElementById('ag-util-head');
    const body = document.getElementById('ag-util-body');
    if (!head || !body) return;

    const showTeam = _activeTeamId === null;
    const cols     = _groupCols(data.sprints);
    const merged   = _colMode === 'month' && _mergeMonths;

    const table = document.getElementById('ag-util-table');
    if (table) table.classList.toggle('ag-no-team-col', !showTeam);

    let h1 = '<tr>';
    if (showTeam) {
        h1 += '<th class="ag-col-member">Member</th>';
        h1 += '<th class="ag-col-team" colspan="4">Team</th>';
    } else {
        h1 += '<th class="ag-col-member" colspan="5">Member</th>';
    }
    for (let i = 0; i < cols.length; i++) {
        const sep  = i > 0 ? ' ag-col-sep' : '';
        const span = merged ? 1 : cols[i].span;
        h1 += `<th colspan="${span}" class="${sep}">${escHtml(cols[i].label)}</th>`;
    }
    h1 += '</tr>';
    head.innerHTML = h1;

    const rows = _filterMemberRows(data.rows ?? []);
    let html = '';
    for (const row of rows) {
        const cm = {};
        row.cells.forEach(c => { cm[c.sprint_id] = c; });
        const memberId   = row.member_id   ?? '';
        const memberType    = row.placeholder_id ? 'placeholder' : 'member';
        const isPlaceholder = memberType === 'placeholder';
        if (showTeam) {
            html += `<tr data-member-id="${memberId}" data-member-type="${memberType}">`;
            html += `<td class="ag-col-member" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
            html += `<td class="ag-col-team" colspan="4" title="${escHtml(row.team_name ?? '')}">${escHtml(row.team_name ?? '—')}</td>`;
        } else {
            html += `<tr data-member-id="${memberId}" data-member-type="${memberType}">`;
            html += `<td class="ag-col-member" colspan="5" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
        }

        for (let i = 0; i < cols.length; i++) {
            const sep = i > 0 ? ' ag-col-sep' : '';
            if (merged) {
                let sumAlloc = 0, sumNet = 0; let hasNet = false;
                for (const s of cols[i].sprints) {
                    const c = cm[s.id] ?? {};
                    sumAlloc += parseFloat(c.allocated_days ?? 0);
                    if (c.net_capacity != null) { sumNet += parseFloat(c.net_capacity); hasNet = true; }
                }
                if (!hasNet && isPlaceholder && sumAlloc > 0) {
                    sumNet = 10 * cols[i].sprints.length;
                    hasNet = true;
                }
                const cls = _allocDayCls(sumAlloc);
                if (hasNet) {
                    const pct    = sumNet > 0 ? Math.round((sumAlloc / sumNet) * 100) : 0;
                    const barCls = _utilBarCls(pct);
                    const barW   = Math.min(pct, 100);
                    html += `<td class="${cls}${sep} ag-util-cell">
                        <div class="ag-util-days">${sumAlloc.toFixed(2)}d</div>
                        <div class="ag-util-bar-wrap"><div class="ag-util-bar">
                            <div class="ag-util-bar-fill ${barCls}" style="width:${barW}%"></div>
                        </div></div></td>`;
                } else {
                    html += `<td class="${cls}${sep} ag-util-cell">
                        <div class="ag-util-days">${sumAlloc > 0 ? sumAlloc.toFixed(2) + 'd' : '—'}</div></td>`;
                }
            } else {
                for (let si = 0; si < cols[i].sprints.length; si++) {
                    const sprint  = cols[i].sprints[si];
                    const c       = cm[sprint.id] ?? {};
                    const alloc   = parseFloat(c.allocated_days ?? 0);
                    const rawNet  = c.net_capacity != null ? parseFloat(c.net_capacity) : null;
                    const net     = rawNet ?? (isPlaceholder ? 10 : 0);
                    const hasBar  = rawNet != null || (isPlaceholder && alloc > 0);
                    const pct     = net > 0 ? Math.round((alloc / net) * 100) : 0;
                    const cls     = _allocDayCls(alloc);
                    const barCls  = _utilBarCls(pct);
                    const barW    = Math.min(pct, 100);
                    const s       = si === 0 ? sep : '';
                    const tip     = `${escHtml(sprint.name)}: ${alloc}d / ${net}d (${pct.toFixed(2)}%)`;
                    html += hasBar
                        ? `<td class="${cls}${s} ag-util-cell" data-sprint-id="${sprint.id}" data-net-capacity="${net}" data-alloc-days="${alloc}" title="${tip}">
                            <div class="ag-util-days">${alloc.toFixed(2)}d</div>
                            <div class="ag-util-bar-wrap"><div class="ag-util-bar">
                                <div class="ag-util-bar-fill ${barCls}" style="width:${barW}%"></div>
                            </div></div></td>`
                        : `<td class="${cls}${s} ag-util-cell" data-sprint-id="${sprint.id}"><div class="ag-util-days">${alloc > 0 ? alloc.toFixed(2) + 'd' : '—'}</div></td>`;
                }
            }
        }
        html += '</tr>';
    }
    body.innerHTML = html;
}

// ── Priority / Confidence indicator helpers ───────────────────────────────────

function _priorityDot(priority) {
    if (!priority) return '';
    const map = {
        VERY_HIGH: ['bg-danger',  'VH', 'Very High Priority'],
        HIGH:      ['bg-warning text-dark', 'H', 'High Priority'],
        MEDIUM:    ['bg-secondary', 'M', 'Medium Priority'],
        LOW:       ['bg-success',  'L', 'Low Priority'],
    };
    const [cls, , tip] = map[priority] ?? ['bg-secondary', priority, priority];
    return ` <span class="badge ${cls} ag-priority-dot" title="${tip}" style="width:.55rem;height:.55rem;border-radius:50%;padding:0;vertical-align:middle;display:inline-block;"></span>`;
}

function _confidenceBadge(confidence) {
    if (!confidence) return '';
    const map = {
        VERY_HIGH: ['bg-success-subtle text-success-emphasis', 'VH'],
        HIGH:      ['bg-primary-subtle text-primary-emphasis', 'H'],
        MEDIUM:    ['bg-secondary-subtle text-secondary-emphasis', 'M'],
        LOW:       ['bg-warning-subtle text-warning-emphasis', 'L'],
    };
    const [cls, label] = map[confidence] ?? ['bg-secondary-subtle text-secondary-emphasis', confidence];
    return ` <span class="badge ${cls} ag-conf-badge" title="Confidence: ${confidence}" style="font-size:.6rem;padding:1px 4px;vertical-align:middle;">${label}</span>`;
}

function _confRowCls(confidence) {
    if (confidence === 'VERY_HIGH' || confidence === 'HIGH') return 'ag-conf-row-high';
    if (confidence === 'MEDIUM') return 'ag-conf-row-mid';
    if (confidence === 'LOW') return 'ag-conf-row-low';
    return '';
}

function _confIndCls(confidence) {
    if (confidence === 'VERY_HIGH' || confidence === 'HIGH') return 'ag-conf-ind-high';
    if (confidence === 'MEDIUM') return 'ag-conf-ind-mid';
    if (confidence === 'LOW') return 'ag-conf-ind-low';
    return '';
}

// ── Allocations table (Table 4) — editable ────────────────────────────────────

async function _loadAllocations() {
    const noSet   = document.getElementById('ag-alloc-no-set');
    const loading = document.getElementById('ag-alloc-loading');
    const empty   = document.getElementById('ag-alloc-empty');
    const wrap    = document.getElementById('ag-alloc-grid-wrap');

    if (!_activeAllocSetId) {
        noSet?.classList.remove('d-none');
        loading?.classList.add('d-none');
        empty?.classList.add('d-none');
        wrap?.classList.add('d-none');
        _allocData = null;
        return;
    }

    noSet?.classList.add('d-none');
    loading?.classList.remove('d-none');
    empty?.classList.add('d-none');
    wrap?.classList.add('d-none');

    try {
        let url = API_URLS.rp_versions.grid.allocations(planPk, versionPk).href
            + `?allocation_set=${_activeAllocSetId}`;
        if (_activeTeamId) url += `&team=${_activeTeamId}`;
        _allocData = await apiFetch(url);

        loading?.classList.add('d-none');
        if (!_allocData.rows?.length) {
            empty?.classList.remove('d-none');
        } else {
            wrap?.classList.remove('d-none');
            _renderAllocTable(_allocData);
            _populateFilterOptions(_allocData);
            // Update conflict badge from first row's set data (stored on data object)
            const setOpt = document.querySelector(`#ag-alloc-set-select option[value="${_activeAllocSetId}"]`);
            if (setOpt) _updateConflictBadge(parseInt(setOpt.dataset.conflicts ?? '0', 10));
        }
    } catch (_) {
        loading?.classList.add('d-none');
        if (empty) { empty.classList.remove('d-none'); empty.textContent = 'Failed to load allocations.'; }
    }
}

function _renderAllocTable(data) {
    const head = document.getElementById('ag-alloc-head');
    const body = document.getElementById('ag-alloc-body');
    if (!head || !body) return;

    const cols   = _groupCols(data.sprints);
    const merged = _colMode === 'month' && _mergeMonths;

    // Build sprint-id → col/sprint-index map for Tab/Enter navigation
    const sprintColMap = {};   // sprint_id → {colIdx, sprintIdx}
    let globalColIdx = 0;
    cols.forEach((col, ci) => {
        col.sprints.forEach((s, si) => {
            sprintColMap[s.id] = { colIdx: ci, globalColIdx: globalColIdx, sprintIdx: si };
            globalColIdx++;
        });
    });

    // Header
    let h1 = '<tr>';
    h1 += '<th class="ag-col-prog">Programme</th>';
    h1 += '<th class="ag-col-proj">Project</th>';
    h1 += '<th class="ag-conf-col"></th>';
    h1 += '<th class="ag-col-alloc-team">Team</th>';
    h1 += '<th class="ag-col-alloc-member">Member</th>';
    h1 += '<th class="ag-col-phase">Phase</th>';
    for (let i = 0; i < cols.length; i++) {
        const sep  = i > 0 ? ' ag-col-sep' : '';
        const span = merged ? 1 : cols[i].span;
        h1 += `<th colspan="${span}" class="${sep}">${escHtml(cols[i].label)}</th>`;
    }
    h1 += '<th class="ag-col-total">Total</th></tr>';
    head.innerHTML = h1;

    const rows = _filterAllocRows(data.rows ?? []);
    let html = '';
    rows.forEach((row, rowIdx) => {
        const cm = {};
        (row.cells ?? []).forEach(c => { cm[c.sprint_id] = c; });

        const projectId  = row.project_id  ?? '';
        const memberId   = row.member_id   ?? '';
        const memberType = row.member_type ?? 'member';
        const phaseId    = row.phase_id    ?? '';

        const confRowCls = _confRowCls(row.phase_confidence);
        const confIndCls = _confIndCls(row.phase_confidence);
        html += `<tr data-row-idx="${rowIdx}" data-project-id="${projectId}" data-member-id="${memberId}" data-member-type="${memberType}" data-phase-id="${phaseId}">`;
        html += `<td class="ag-col-prog ${confRowCls}"  title="${escHtml(row.programme_name)}">${escHtml(row.programme_name ?? '—')}</td>`;
        html += `<td class="ag-col-proj ag-proj-cell ${confRowCls}" title="${escHtml(row.project_name)}">${escHtml(row.project_name ?? '—')}</td>`;
        html += `<td class="ag-conf-col ${confIndCls}"></td>`;
        html += `<td class="ag-col-alloc-team" title="${escHtml(row.team_name)}">${escHtml(row.team_name ?? '—')}</td>`;
        html += `<td class="ag-col-alloc-member" title="${escHtml(row.member_name)}">${escHtml(row.member_name ?? '—')}</td>`;
        const priorityDot = _priorityDot(row.phase_priority);
        const confBadge   = _confidenceBadge(row.phase_confidence);
        html += `<td class="ag-col-phase" title="${escHtml(row.phase_name)}">${escHtml(row.phase_name ?? '—')}${priorityDot}${confBadge}</td>`;

        let colIdx = 0;
        for (let i = 0; i < cols.length; i++) {
            const sep = i > 0 ? ' ag-col-sep' : '';
            if (merged) {
                let sum = 0;
                for (const s of cols[i].sprints) sum += parseFloat(cm[s.id]?.days ?? 0);
                html += `<td class="${sep}">${sum > 0 ? sum.toFixed(2) : '—'}</td>`;
                colIdx++;
            } else {
                for (let si = 0; si < cols[i].sprints.length; si++) {
                    const sprint  = cols[i].sprints[si];
                    const cell    = cm[sprint.id] ?? {};
                    const d       = parseFloat(cell.days ?? 0);
                    const s       = si === 0 ? sep : '';
                    const allocId = cell.allocation_id;
                    const isOverride = !!cell.is_override;
                    const isMulti    = !!cell.multi;

                    const canEdit = !_isActiveSet && !isMulti;
                    const editCls = canEdit ? ' editable-cell' : '';
                    const overrideDot = isOverride ? '<span class="ag-override-dot" title="Manual override"></span>' : '';

                    html += `<td class="${s}${editCls}" ` +
                        `data-alloc-id="${allocId ?? ''}" ` +
                        `data-sprint-id="${sprint.id}" ` +
                        `data-days="${d}" ` +
                        `data-row-idx="${rowIdx}" ` +
                        `data-col-idx="${colIdx}" ` +
                        `title="${escHtml(sprint.name)}: ${d > 0 ? d + 'd' : 'unallocated'}"` +
                        `>${overrideDot}${d > 0 ? d.toFixed(2) : '—'}</td>`;
                    colIdx++;
                }
            }
        }
        html += `<td class="ag-col-total ag-row-total">${row.total_days ?? '—'}</td>`;
        html += '</tr>';
    });
    body.innerHTML = html;
    _updateGhostWidth();
}

// ── Cell editing ──────────────────────────────────────────────────────────────

function _bindCellEditing() {
    const allocBody = document.getElementById('ag-alloc-body');
    if (!allocBody) return;

    allocBody.addEventListener('click', e => {
        if (_isActiveSet) return;
        const td = e.target.closest('td.editable-cell');
        if (!td) return;
        if (td.querySelector('input')) return;  // already editing
        _cancelCurrentEdit();
        _startEdit(td);
    });
}

function _startEdit(td) {
    const currentVal  = parseFloat(td.dataset.days ?? '0');
    const wasOverride = td.querySelector('.ag-override-dot') !== null;
    const displayVal  = currentVal > 0 ? currentVal.toFixed(2) : '';

    td.innerHTML = `<input type="number" class="ag-cell-input"
        value="${displayVal}"
        min="0" max="10" step="0.25"
        data-orig-val="${currentVal}"
        data-orig-override="${wasOverride}">`;
    const inp = td.querySelector('input');
    _editingTd = td;
    inp.focus();
    inp.select();

    inp.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            _commitEdit(td, inp, () => _moveDown(td));
        } else if (e.key === 'Tab') {
            e.preventDefault();
            _commitEdit(td, inp, () => e.shiftKey ? _moveLeft(td) : _moveRight(td));
        } else if (e.key === 'Escape') {
            _cancelEdit(td, inp);
        }
    });

    inp.addEventListener('blur', () => {
        // blur fires before keydown on Tab; defer so keydown can run first
        setTimeout(() => {
            if (_editingTd === td && td.querySelector('input')) {
                _commitEdit(td, inp, null);
            }
        }, 80);
    });
}

function _commitEdit(td, inp, afterFn) {
    if (_saving) return;
    const rawVal = inp.value.trim();
    const days   = rawVal === '' ? 0 : parseFloat(rawVal);

    if (isNaN(days)) {
        _showCellError(td, 'Invalid number');
        return;
    }

    _saving = true;
    _editingTd = null;
    _saveCell(td, days, afterFn);
}

function _cancelEdit(td, inp) {
    const origVal    = parseFloat(inp.dataset.origVal ?? '0');
    const wasOverride = inp.dataset.origOverride === 'true';
    _editingTd = null;
    _restoreCellDisplay(td, origVal, wasOverride);
}

function _cancelCurrentEdit() {
    if (_editingTd) {
        const inp = _editingTd.querySelector('input');
        if (inp) _cancelEdit(_editingTd, inp);
    }
}

async function _saveCell(td, days, afterFn) {
    const allocId    = td.dataset.allocId;
    const sprintId   = td.dataset.sprintId;
    const tr         = td.closest('tr');
    const phaseId    = tr?.dataset.phaseId;
    const memberId   = tr?.dataset.memberId;
    const memberType = tr?.dataset.memberType;

    // Inline validation before hitting server
    const rounded = Math.round(days / 0.25) * 0.25;
    if (rounded < 0 || rounded > 10) {
        _restoreCellDisplay(td, parseFloat(td.dataset.days ?? '0'), false);
        _showCellError(td, 'Must be 0–10');
        _saving = false;
        afterFn?.();
        return;
    }

    try {
        let result;
        if (allocId) {
            result = await apiFetch(
                API_URLS.rp_versions.grid.cell_update(planPk, versionPk, allocId).href,
                { method: 'POST', body: JSON.stringify({ days: rounded }) }
            );
        } else {
            if (rounded === 0) {
                _restoreCellDisplay(td, 0, false);
                _saving = false;
                afterFn?.();
                return;
            }
            result = await apiFetch(
                API_URLS.rp_versions.grid.cell_create(planPk, versionPk).href,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        days: rounded,
                        allocation_set_id: _activeAllocSetId,
                        phase_id: phaseId ? parseInt(phaseId, 10) : null,
                        sprint_id: sprintId ? parseInt(sprintId, 10) : null,
                        member_id: memberId ? parseInt(memberId, 10) : null,
                        member_type: memberType ?? 'member',
                    })
                }
            );
            if (result.allocation_id) {
                td.dataset.allocId = result.allocation_id;
                // Update in-memory cell so next edit goes through update path
                const rowIdx = parseInt(tr?.dataset.rowIdx ?? '-1', 10);
                if (_allocData && rowIdx >= 0) {
                    const filteredRows = _filterAllocRows(_allocData.rows ?? []);
                    const spId = parseInt(sprintId, 10);
                    const cell = (filteredRows[rowIdx]?.cells ?? []).find(c => c.sprint_id === spId);
                    if (cell) cell.allocation_id = result.allocation_id;
                }
            }
        }
        _onCellSaved(result, td);
    } catch (err) {
        const msg = err?.data?.days?.[0] ?? err?.data?.detail ?? err?.message ?? 'Save failed';
        _restoreCellDisplay(td, parseFloat(td.dataset.days ?? '0'), false);
        _showCellError(td, msg);
    } finally {
        _saving = false;
        afterFn?.();
    }
}

function _onCellSaved(result, td) {
    const days      = result.effective_days ?? 0;
    const isOverride = result.is_override ?? false;

    // (a) Update cell value & dataset
    td.dataset.days = days;
    _restoreCellDisplay(td, days, isOverride);

    // (b) Update project row total
    const tr = td.closest('tr');
    if (tr) {
        const totalCell = tr.querySelector('.ag-row-total');
        if (totalCell) totalCell.textContent = result.project_total ?? '—';

        // Update in-memory alloc data row total too
        const rowIdx = parseInt(tr.dataset.rowIdx ?? '-1', 10);
        if (_allocData && rowIdx >= 0) {
            const filteredRows = _filterAllocRows(_allocData.rows ?? []);
            if (filteredRows[rowIdx]) filteredRows[rowIdx].total_days = result.project_total;
            // Update original row's cells in _allocData
            const cell = (_allocData.rows?.[rowIdx]?.cells ?? []).find(c => c.sprint_id === result.sprint_id);
            if (cell) { cell.days = days; cell.is_override = isOverride; }
        }
    }

    // (c) Update Allocated Capacity table (Table 3) for same engineer + sprint
    _updateUtilCell(result.member_id, result.member_type, result.sprint_id, result.engineer_sprint_allocated);

    // (d) Update threshold badge on project column cells for this project
    if (result.threshold_info) {
        _updateThresholdBadge(result.threshold_info);
    }

    // (e) Update conflict count badge
    if (result.conflict_count != null) {
        _updateConflictBadge(result.conflict_count);
    }
}

function _restoreCellDisplay(td, days, isOverride) {
    const overrideDot = isOverride ? '<span class="ag-override-dot" title="Manual override"></span>' : '';
    td.innerHTML = overrideDot + (days > 0 ? parseFloat(days).toFixed(2) : '—');
}

function _showCellError(td, msg) {
    const errSpan = document.createElement('span');
    errSpan.className = 'ag-cell-error';
    errSpan.title = msg;
    errSpan.textContent = '⚠';
    td.appendChild(errSpan);
    setTimeout(() => errSpan.remove(), 3000);
}

function _updateUtilCell(memberId, memberType, sprintId, allocatedDays) {
    if (!memberId) return;
    const body = document.getElementById('ag-util-body');
    if (!body) return;
    const row = body.querySelector(
        `tr[data-member-id="${memberId}"][data-member-type="${memberType}"]`
    );
    if (!row) return;
    const cell = row.querySelector(`td[data-sprint-id="${sprintId}"]`);
    if (!cell) return;

    const alloc  = parseFloat(allocatedDays) || 0;
    const net    = parseFloat(cell.dataset.netCapacity ?? '0');
    const pct    = net > 0 ? Math.round((alloc / net) * 100) : 0;
    const barW   = Math.min(pct, 100);
    const barCls = _utilBarCls(pct);
    const cls    = _allocDayCls(alloc);

    // Update data attributes
    cell.dataset.allocDays = alloc;

    // Update class
    ['ag-util-full', 'ag-util-high', 'ag-util-mid', 'ag-util-low', 'ag-util-vlow', 'ag-util-zero', 'ag-util-over'].forEach(c => cell.classList.remove(c));
    if (cls) cell.classList.add(cls);

    // Update text
    const daysDiv = cell.querySelector('.ag-util-days');
    if (daysDiv) daysDiv.textContent = `${alloc.toFixed(2)}d`;

    // Update bar
    const barFill = cell.querySelector('.ag-util-bar-fill');
    if (barFill) {
        barFill.className = `ag-util-bar-fill ${barCls}`;
        barFill.style.width = `${barW}%`;
    }
}

function _updateThresholdBadge(info) {
    const body = document.getElementById('ag-alloc-body');
    if (!body || !info?.project_id) return;
    const projCells = body.querySelectorAll(`tr[data-project-id="${info.project_id}"] .ag-proj-cell`);
    projCells.forEach(cell => {
        // Remove old badges
        cell.querySelectorAll('.ag-thresh-badge').forEach(b => b.remove());
        if (info.is_over_threshold) {
            cell.insertAdjacentHTML('beforeend',
                '<span class="ag-thresh-badge badge bg-danger ms-1" title="Over threshold">▲</span>');
        } else if (info.is_under_threshold) {
            cell.insertAdjacentHTML('beforeend',
                '<span class="ag-thresh-badge badge bg-warning text-dark ms-1" title="Under threshold">▼</span>');
        }
    });
}

// ── Keyboard navigation (Tab/Enter) ──────────────────────────────────────────

function _moveRight(td) {
    const tr   = td.closest('tr');
    if (!tr) return;
    const cells = Array.from(tr.querySelectorAll('td.editable-cell'));
    const idx   = cells.indexOf(td);
    const next  = cells[idx + 1];
    if (next) _startEdit(next);
}

function _moveLeft(td) {
    const tr    = td.closest('tr');
    if (!tr) return;
    const cells = Array.from(tr.querySelectorAll('td.editable-cell'));
    const idx   = cells.indexOf(td);
    const prev  = cells[idx - 1];
    if (prev) _startEdit(prev);
}

function _moveDown(td) {
    const body = document.getElementById('ag-alloc-body');
    if (!body) return;
    const colIdx = td.dataset.colIdx;
    const rowIdx = parseInt(td.dataset.rowIdx ?? '-1', 10);
    if (colIdx == null || rowIdx < 0) return;

    const nextRow = body.querySelector(`tr[data-row-idx="${rowIdx + 1}"]`);
    if (!nextRow) return;
    const nextCell = nextRow.querySelector(`td[data-col-idx="${colIdx}"].editable-cell`);
    if (nextCell) _startEdit(nextCell);
}

// ── Column grouping (sprint vs month) ─────────────────────────────────────────

function _groupCols(sprints) {
    if (_colMode === 'sprint') {
        return sprints.map(s => ({ key: s.name, label: s.name, span: 1, sprints: [s] }));
    }
    const monthMap = new Map();
    for (const s of sprints) {
        const m = s.month || 'Unknown';
        if (!monthMap.has(m)) monthMap.set(m, []);
        monthMap.get(m).push(s);
    }
    return Array.from(monthMap.entries()).map(([month, ss]) => ({
        key: month, label: month, span: ss.length, sprints: ss,
    }));
}

// ── Run Engine Modal ──────────────────────────────────────────────────────────

function _bindEngineModal() {
    document.getElementById('ag-run-engine')?.addEventListener('click', () => {
        _resetEngineModal();
        const modal = document.getElementById('gridEngineModal');
        if (modal && window.bootstrap) {
            window.bootstrap.Modal.getOrCreateInstance(modal).show();
        }
    });

    document.getElementById('ag-engine-submit')?.addEventListener('click', _submitEngineRun);

    document.getElementById('gridEngineModal')?.addEventListener('hidden.bs.modal', () => {
        _stopEnginePoller();
    });
}

function _resetEngineModal() {
    _stopEnginePoller();
    _engineJobId = null;

    const form     = document.getElementById('ag-engine-form');
    const progress = document.getElementById('ag-engine-progress');
    const result   = document.getElementById('ag-engine-result');
    const errSec   = document.getElementById('ag-engine-error-section');
    const err      = document.getElementById('ag-engine-err');
    const submit   = document.getElementById('ag-engine-submit');
    const spinner  = document.getElementById('ag-engine-spinner');

    if (form)     form.classList.remove('d-none');
    if (progress) progress.classList.add('d-none');
    if (result)   result.classList.add('d-none');
    if (errSec)   errSec.classList.add('d-none');
    if (err)      err.classList.add('d-none');
    if (submit)   { submit.classList.remove('d-none'); submit.disabled = false; }
    if (spinner)  spinner.classList.add('d-none');

    const validateRadio = document.getElementById('ag-mode-validate');
    if (validateRadio) validateRadio.checked = true;

    const includeCurrent = document.getElementById('ag-engine-include-current');
    if (includeCurrent) includeCurrent.checked = false;

    const removeOverrides = document.getElementById('ag-engine-remove-overrides');
    if (removeOverrides) removeOverrides.checked = false;

    const overridesSection = document.getElementById('ag-engine-overrides-section');
    if (overridesSection) overridesSection.classList.toggle('d-none', !_hasPlOverrides);
}

async function _submitEngineRun() {
    const mode           = document.querySelector('input[name="ag-engine-mode"]:checked')?.value ?? 'VALIDATE';
    const includeCurrent = document.getElementById('ag-engine-include-current')?.checked ?? false;
    const removeOverrides = document.getElementById('ag-engine-remove-overrides')?.checked ?? false;
    const errEl          = document.getElementById('ag-engine-err');

    if (errEl) errEl.classList.add('d-none');

    const submitBtn = document.getElementById('ag-engine-submit');
    const spinner   = document.getElementById('ag-engine-spinner');
    if (submitBtn) submitBtn.disabled = true;
    if (spinner)   spinner.classList.remove('d-none');

    try {
        const { method, href } = API_URLS.resource_plans.engine.run(planPk);
        const result = await apiFetch(href, {
            method,
            body: JSON.stringify({
                version_id:            parseInt(versionPk, 10),
                mode,
                include_current_sprint: includeCurrent,
                remove_overrides:      removeOverrides,
            }),
        });
        _engineJobId = result.job_id;

        const form     = document.getElementById('ag-engine-form');
        const progress = document.getElementById('ag-engine-progress');
        if (form)     form.classList.add('d-none');
        if (progress) progress.classList.remove('d-none');
        if (submitBtn) submitBtn.classList.add('d-none');

        _startEnginePoller();
    } catch (err) {
        if (errEl) {
            errEl.textContent = err?.data?.detail ?? err?.message ?? 'Failed to start engine run.';
            errEl.classList.remove('d-none');
        }
        if (submitBtn) submitBtn.disabled = false;
        if (spinner)   spinner.classList.add('d-none');
    }
}

function _startEnginePoller() {
    _stopEnginePoller();
    _pollEngineStatus();
    _enginePollTimer = setInterval(_pollEngineStatus, 3000);
}

function _stopEnginePoller() {
    if (_enginePollTimer) { clearInterval(_enginePollTimer); _enginePollTimer = null; }
}

async function _pollEngineStatus() {
    if (!_engineJobId) return;
    try {
        const job = await apiFetch(API_URLS.resource_plans.engine.job_status(planPk, _engineJobId).href);
        _updateEngineProgress(job);

        if (job.status === 'COMPLETE' || job.status === 'FAILED') {
            _stopEnginePoller();
            const fullJob = await apiFetch(API_URLS.resource_plans.engine.job_detail(planPk, _engineJobId).href);

            if (fullJob.status === 'COMPLETE') {
                const resultEl = document.getElementById('ag-engine-result');
                if (resultEl) {
                    const vr = fullJob.validation_result ?? {};
                    const conflicts = vr.conflict_count ?? 0;
                    const cls = conflicts > 0 ? 'alert-warning' : 'alert-success';
                    resultEl.innerHTML = `<div class="alert ${cls} py-2 px-3 mb-0" style="font-size:.83rem">
                        <i class="bi bi-check-circle-fill me-1"></i>
                        Engine completed.${conflicts > 0 ? ` ${conflicts} conflict(s) detected.` : ' No conflicts.'}
                        ${vr.allocation_set_id ? `<br><small>Allocation Set #${vr.allocation_set_id} created.</small>` : ''}
                    </div>`;
                    resultEl.classList.remove('d-none');
                }
                // Clear lazy state then reload
                _allocData = null;
                _utilData  = null;
                await _loadAllocationSets();
                await Promise.all([_loadAllocTables(), _loadConflictSummary()]);
                try {
                    const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
                    _hasPlOverrides = !!ver.has_pl_overrides;
                    const badge = document.getElementById('ag-override-badge');
                    if (badge) badge.classList.toggle('d-none', !_hasPlOverrides);
                } catch (_) {}
            } else if (fullJob.status === 'FAILED') {
                const errSec = document.getElementById('ag-engine-error-section');
                const errLog = document.getElementById('ag-engine-error-log');
                if (errLog) errLog.textContent = fullJob.error_log ?? 'Unknown error.';
                if (errSec) errSec.classList.remove('d-none');
            }
        }
    } catch (_) {}
}

function _updateEngineProgress(job) {
    const pct    = job.progress_pct ?? 0;
    const bar    = document.getElementById('ag-engine-progress-bar');
    const stepEl = document.getElementById('ag-engine-step');
    const badge  = document.getElementById('ag-engine-status-badge');

    if (bar) {
        bar.style.width = `${pct}%`;
        bar.setAttribute('aria-valuenow', pct);
        const isComplete = job.status === 'COMPLETE';
        const isFailed   = job.status === 'FAILED';
        bar.className = `progress-bar${isFailed ? ' bg-danger' : isComplete ? ' bg-success' : ''}`;
    }
    if (stepEl) stepEl.textContent = job.current_step ?? (job.status === 'PENDING' ? 'Queued…' : '');

    const statusMap = {
        PENDING:  ['bg-secondary', 'Pending'],
        RUNNING:  ['bg-primary',   'Running'],
        COMPLETE: ['bg-success',   'Complete'],
        FAILED:   ['bg-danger',    'Failed'],
    };
    if (badge) {
        const [cls, label] = statusMap[job.status] ?? ['bg-secondary', job.status];
        badge.innerHTML = `<span class="badge ${cls}">${label}</span>`;
    }
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
