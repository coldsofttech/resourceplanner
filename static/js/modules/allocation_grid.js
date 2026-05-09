'use strict';

import {
    apiFetch,
    escHtml,
    getPkFromUrl,
    setPageTitle,
} from './../main.js';
import { API_URLS } from './../urls.js';

const planPk = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

let _colMode = 'sprint';   // 'sprint' | 'month'
let _mergeMonths = false;  // month-view merge toggle
let _activeTeamId = null;
let _capacityData = null;
let _absencesData = null;

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
    if (!planPk || !versionPk) return;

    _bindColModeToggle();
    _bindScrollSync();

    try {
        const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
        document.getElementById('ag-plan-name').textContent = ver.plan_name ?? '—';
        document.getElementById('ag-version-badge').innerHTML =
            `<span class="badge bg-secondary">v${ver.version}</span>`;
        setPageTitle(`Grid — ${ver.plan_name ?? ''}`);
        const bc = document.getElementById('ag-breadcrumb');
        if (bc) bc.innerHTML =
            `<a href="/resource-plans/${planPk}/" class="text-decoration-none text-secondary">Resource Plans</a>`;
    } catch (_) {}

    await _loadTeamTabs();
    await _loadAll();
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
}

// ── Scroll synchronisation ────────────────────────────────────────────────────

function _bindScrollSync() {
    const cap = document.getElementById('ag-capacity-grid-wrap');
    const abs = document.getElementById('ag-absences-grid-wrap');
    const ghost = document.getElementById('ag-hscroll');
    if (!cap || !abs) return;
    let syncing = false;
    const _sync = (src) => {
        if (syncing) return;
        syncing = true;
        const x = src.scrollLeft;
        [cap, abs, ghost].forEach(el => { if (el && el !== src) el.scrollLeft = x; });
        syncing = false;
    };
    cap.addEventListener('scroll', () => _sync(cap));
    abs.addEventListener('scroll', () => _sync(abs));
    if (ghost) ghost.addEventListener('scroll', () => _sync(ghost));
}

function _updateGhostWidth() {
    const ghost = document.getElementById('ag-hscroll');
    const inner = document.getElementById('ag-hscroll-inner');
    const cap = document.getElementById('ag-capacity-grid-wrap');
    const table = document.getElementById('ag-capacity-table');
    if (!ghost || !inner || !cap || !table) return;
    const tableW = table.scrollWidth;
    inner.style.width = tableW + 'px';
    ghost.classList.toggle('d-none', tableW <= cap.clientWidth);
}

// ── Team tabs ─────────────────────────────────────────────────────────────────

async function _loadTeamTabs() {
    const tabList = document.getElementById('ag-team-tabs');
    if (!tabList) return;
    try {
        const teams = await apiFetch(API_URLS.rp_versions.grid.teams(planPk, versionPk).href);
        teams.forEach(t => {
            const li = document.createElement('li');
            li.className = 'nav-item';
            li.setAttribute('role', 'presentation');
            li.innerHTML =
                `<button class="nav-link" type="button" role="tab" data-team-id="${t.id}">${escHtml(t.name)}</button>`;
            tabList.appendChild(li);
        });
    } catch (_) {}

    tabList.addEventListener('click', async e => {
        const btn = e.target.closest('[data-team-id]');
        if (!btn) return;
        tabList.querySelectorAll('.nav-link').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _activeTeamId = btn.dataset.teamId || null;
        await _loadAll();
    });
}

// ── Load both tables ──────────────────────────────────────────────────────────

async function _loadAll() {
    await Promise.all([_loadCapacity(), _loadAbsences()]);
}

// ── Capacity table ────────────────────────────────────────────────────────────

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

    const cols = _groupCols(data.sprints);
    const merged = _colMode === 'month' && _mergeMonths;

    let h1 = '<tr><th class="ag-col-member">Member</th>';
    for (let i = 0; i < cols.length; i++) {
        const sep = i > 0 ? ' ag-col-sep' : '';
        const span = merged ? 1 : cols[i].span;
        h1 += `<th colspan="${span}" class="${sep}" title="${escHtml(cols[i].key)}">${escHtml(cols[i].label)}</th>`;
    }
    h1 += '</tr>';
    head.innerHTML = h1;

    let html = '';
    for (const row of data.rows) {
        html += `<tr><td class="ag-col-member" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
        const cm = {};
        row.cells.forEach(c => { cm[c.sprint_id] = c; });

        for (let i = 0; i < cols.length; i++) {
            const sep = i > 0 ? ' ag-col-sep' : '';
            if (merged) {
                // Aggregate all sprints in this month
                let sumNet = 0; let hasAny = false;
                for (const sprint of cols[i].sprints) {
                    const c = cm[sprint.id] ?? {};
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
                    const s = (si === 0) ? sep : '';
                    html += `<td class="${cls}${s}" title="${escHtml(sprint.name)} — Net ${net}d">${hasData ? net : '—'}</td>`;
                }
            }
        }
        html += '</tr>';
    }
    body.innerHTML = html;
    _updateGhostWidth();
}

// ── Absences table ────────────────────────────────────────────────────────────

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

    const cols = _groupCols(data.sprints);
    const merged = _colMode === 'month' && _mergeMonths;

    let h1 = '<tr><th class="ag-col-member">Member</th>';
    for (let i = 0; i < cols.length; i++) {
        const sep = i > 0 ? ' ag-col-sep' : '';
        const span = merged ? 1 : cols[i].span;
        h1 += `<th colspan="${span}" class="${sep}">${escHtml(cols[i].label)}</th>`;
    }
    h1 += '</tr>';
    head.innerHTML = h1;

    let html = '';
    for (const row of data.rows) {
        html += `<tr><td class="ag-col-member" title="${escHtml(row.member_name)}">${escHtml(row.member_name)}</td>`;
        const cm = {};
        row.cells.forEach(c => { cm[c.sprint_id] = c; });

        for (let i = 0; i < cols.length; i++) {
            const sep = i > 0 ? ' ag-col-sep' : '';
            if (merged) {
                let sumH = 0, sumL = 0, sumPh = 0; let hasAny = false;
                for (const sprint of cols[i].sprints) {
                    const c = cm[sprint.id] ?? {};
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
                    const c = cm[sprint.id] ?? {};
                    const tot  = parseFloat(c.total_absence ?? 0);
                    const h    = parseFloat(c.holiday_days ?? 0);
                    const l    = parseFloat(c.leave_days ?? 0);
                    const ph   = parseFloat(c.placeholder_days ?? 0);
                    const hasData = c.holiday_days != null;
                    const cls  = _absCls(tot);
                    const s    = (si === 0) ? sep : '';
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

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
