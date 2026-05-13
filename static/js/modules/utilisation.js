'use strict';

import { apiFetch, escHtml, getPkFromUrl, setPageTitle } from './../main.js';
import { API_URLS } from './../urls.js';

const planPk    = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

const RAMPDOWN_THRESHOLD_PCT = 50;

let _activeTab   = 'team';
let _memberView  = 'bar';
let _teamChart   = null;
let _memberChart = null;
let _progCharts  = [];
let _memberData  = null;
let _showAuto    = false;
let _allProjects = [];  // full project list for cascade filter

// ── Helpers ───────────────────────────────────────────────────────────────────

function _spinner(show) {
    document.getElementById('util-spinner')?.classList.toggle('d-none', !show);
}

function _showBanner(msg, type = 'info') {
    const el = document.getElementById('util-banner');
    if (!el) return;
    el.className = `alert alert-${type} mb-3`;
    el.textContent = msg;
    el.classList.remove('d-none');
    setTimeout(() => el.classList.add('d-none'), 5000);
}

function _fmtDays(v) { return v == null ? '—' : `${parseFloat(v).toFixed(1)}d`; }
function _fmtPct(v)  { return v == null ? '—' : `${parseFloat(v).toFixed(1)}%`; }
function _fmtCost(v) { return v == null ? '—' : `£${Math.round(v).toLocaleString()}`; }

function _cellClass(pct, allocDays) {
    if (!allocDays) return 'util-cell-none';
    if (pct == null) return 'util-cell-none';
    if (pct > 100)  return 'util-cell-over';
    if (pct >= 85)  return 'util-cell-good';
    if (pct >= RAMPDOWN_THRESHOLD_PCT) return 'util-cell-healthy';
    return 'util-cell-rampdown';
}

function _selectedIds(elId) {
    const el = document.getElementById(elId);
    if (!el) return null;
    const vals = Array.from(el.selectedOptions).map(o => o.value).filter(Boolean);
    return vals.length ? vals.join(',') : null;
}

function _clearSelect(elId) {
    const el = document.getElementById(elId);
    if (el) Array.from(el.options).forEach(o => (o.selected = false));
}

function _round(v, dp) {
    const f = 10 ** dp;
    return Math.round(v * f) / f;
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
    if (!planPk || !versionPk) return;
    _bindTabs();
    _bindFilters();
    _bindMemberViewToggle();
    _bindHeatmapClick();
    _bindAutoToggle();
    await _loadVersionMeta();
    await Promise.all([_loadAllocationSets(), _loadFilterOptions()]);
    await _renderActiveTab();
}

// ── Version meta ──────────────────────────────────────────────────────────────

async function _loadVersionMeta() {
    try {
        const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
        document.getElementById('util-plan-name').textContent = ver.plan_name ?? '—';
        const badge = document.getElementById('util-version-badge');
        if (badge) badge.textContent = `v${ver.version}`;
        setPageTitle(`Utilisation — ${ver.plan_name ?? ''}`);
    } catch (_) {}
}

// ── Allocation sets dropdown ──────────────────────────────────────────────────

async function _loadAllocationSets() {
    try {
        const data = await apiFetch(API_URLS.rp_versions.allocation_sets.list(planPk, versionPk).href);
        const sets  = Array.isArray(data) ? data : (data.results ?? []);
        const sel   = document.getElementById('util-alloc-set');
        if (!sel) return;
        sets.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            let label = s.label ?? s.name ?? `Set #${s.id}`;
            if (s.is_active) label += ' (active)';
            opt.textContent = label;
            sel.appendChild(opt);
        });
    } catch (_) {}
}

// ── Filter options ────────────────────────────────────────────────────────────

async function _loadFilterOptions() {
    const [teamsRes, capacityRes, projectsRes, empTypesRes] = await Promise.allSettled([
        apiFetch(API_URLS.rp_versions.grid.teams(planPk, versionPk).href),
        apiFetch(API_URLS.rp_versions.grid.capacity(planPk, versionPk).href),
        apiFetch(API_URLS.rp_versions.projects.list(planPk, versionPk).href),
        apiFetch(API_URLS.employment_types.list.href),
    ]);

    // Teams
    const teams   = teamsRes.status === 'fulfilled'
        ? (Array.isArray(teamsRes.value) ? teamsRes.value : (teamsRes.value?.results ?? []))
        : [];
    const teamSel = document.getElementById('util-filter-teams');
    teams.forEach(t => {
        if (!teamSel) return;
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.name;
        teamSel.appendChild(opt);
    });

    // Members from capacity grid rows (store team_id for cascade filter)
    const capRows  = capacityRes.status === 'fulfilled' ? (capacityRes.value?.rows ?? []) : [];
    const memberSel = document.getElementById('util-filter-members');
    capRows.forEach(r => {
        if (!memberSel || !r.member_id) return;
        const opt = document.createElement('option');
        opt.value = r.member_id;
        opt.textContent = r.member_name;
        if (r.team_id) opt.dataset.team = r.team_id;
        memberSel.appendChild(opt);
    });

    // Projects + Programmes
    const projList = projectsRes.status === 'fulfilled'
        ? (Array.isArray(projectsRes.value) ? projectsRes.value : (projectsRes.value?.results ?? []))
        : [];
    _allProjects = projList;
    const projSel  = document.getElementById('util-filter-projects');
    const progSel  = document.getElementById('util-filter-programmes');
    const seenProgs = new Set();
    projList.forEach(p => {
        if (projSel && p.project) {
            const opt = document.createElement('option');
            opt.value = p.project;
            opt.textContent = p.project_name;
            projSel.appendChild(opt);
        }
        if (progSel && p.programme_id && !seenProgs.has(p.programme_id)) {
            seenProgs.add(p.programme_id);
            const opt = document.createElement('option');
            opt.value = p.programme_id;
            opt.textContent = p.programme_name ?? 'Unassigned';
            progSel.appendChild(opt);
        }
    });

    // Employment types
    const empRaw = empTypesRes.status === 'fulfilled'
        ? (Array.isArray(empTypesRes.value) ? empTypesRes.value : (empTypesRes.value?.results ?? []))
        : [];
    const empSel = document.getElementById('util-filter-emp-types');
    empRaw.forEach(e => {
        if (!empSel) return;
        const opt = document.createElement('option');
        opt.value = e.id;
        opt.textContent = e.name;
        empSel.appendChild(opt);
    });

    // Cascade: filter projects when programme changes (#11)
    progSel?.addEventListener('change', _cascadeProjectFilter);

    // Cascade: filter members when team selection changes
    teamSel?.addEventListener('change', _cascadeMemberFilter);
}

// Cascade member dropdown based on selected teams
function _cascadeMemberFilter() {
    const selTeams = _selectedIds('util-filter-teams');
    const selTeamIds = selTeams ? selTeams.split(',').map(Number) : [];
    const memberSel = document.getElementById('util-filter-members');
    if (!memberSel) return;
    Array.from(memberSel.options).forEach(opt => {
        if (!opt.value) return;
        const tid = opt.dataset.team ? Number(opt.dataset.team) : null;
        const match = !selTeamIds.length || (tid != null && selTeamIds.includes(tid));
        opt.style.display = match ? '' : 'none';
        if (!match) opt.selected = false;
    });
}

// Cascade project dropdown based on selected programmes (#11)
function _cascadeProjectFilter() {
    const selProgs = _selectedIds('util-filter-programmes');
    const selProgIds = selProgs ? selProgs.split(',').map(Number) : [];
    const projSel = document.getElementById('util-filter-projects');
    if (!projSel) return;

    Array.from(projSel.options).forEach(opt => {
        if (!opt.value) return;
        const proj = _allProjects.find(p => String(p.project) === opt.value);
        const match = !selProgIds.length || (proj && selProgIds.includes(proj.programme_id));
        opt.style.display = match ? '' : 'none';
        if (!match) opt.selected = false;
    });
}

// ── Tab management ────────────────────────────────────────────────────────────

function _bindTabs() {
    document.querySelectorAll('#util-tabs [data-tab]').forEach(btn => {
        btn.addEventListener('click', async () => {
            document.querySelectorAll('#util-tabs .nav-link').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _activeTab = btn.dataset.tab;
            _updateFilterVisibility();
            await _renderActiveTab();
        });
    });
    _updateFilterVisibility();
}

function _updateFilterVisibility() {
    const isMember  = _activeTab === 'member';
    const isProg    = _activeTab === 'programme';
    const isTeam    = _activeTab === 'team';

    document.getElementById('util-filter-members-wrap')?.classList.toggle('d-none', !isMember);
    document.getElementById('util-filter-emp-types-wrap')?.classList.toggle('d-none', !isMember && !isTeam);
    document.getElementById('util-filter-programmes-wrap')?.classList.toggle('d-none', !isProg);
    document.getElementById('util-filter-projects-wrap')?.classList.toggle('d-none', isTeam);
    document.getElementById('util-auto-toggle-wrap')?.classList.toggle('d-none', false);

    ['team', 'member', 'programme'].forEach(t => {
        document.getElementById(`util-panel-${t}`)?.classList.toggle('d-none', t !== _activeTab);
    });
}

// ── Filters ───────────────────────────────────────────────────────────────────

function _bindFilters() {
    document.getElementById('util-apply-filters')?.addEventListener('click', () => _renderActiveTab());
    document.getElementById('util-reset-filters')?.addEventListener('click', () => {
        const allocSel = document.getElementById('util-alloc-set');
        if (allocSel) allocSel.selectedIndex = 0;
        ['util-filter-teams', 'util-filter-members', 'util-filter-programmes',
            'util-filter-projects', 'util-filter-emp-types'].forEach(_clearSelect);
        _cascadeMemberFilter();
        _cascadeProjectFilter();
        _renderActiveTab();
    });
}

function _bindAutoToggle() {
    document.getElementById('util-auto-toggle')?.addEventListener('change', e => {
        _showAuto = e.target.checked;
        _renderActiveTab();
    });
}

function _buildQS(extras = {}) {
    const p = new URLSearchParams();
    const allocSet = document.getElementById('util-alloc-set')?.value;
    if (allocSet) p.set('allocation_set', allocSet);
    const teams = _selectedIds('util-filter-teams');
    if (teams) p.set('teams', teams);
    Object.entries(extras).forEach(([k, v]) => { if (v != null) p.set(k, v); });
    return p.toString() ? `?${p}` : '';
}

// ── Render dispatcher ─────────────────────────────────────────────────────────

async function _renderActiveTab() {
    _spinner(true);
    try {
        if      (_activeTab === 'team')      await _renderTeamTab();
        else if (_activeTab === 'member')    await _renderMemberTab();
        else if (_activeTab === 'programme') await _renderProgrammeTab();
    } catch (err) {
        console.error('Utilisation load error:', err);
        _showBanner('Failed to load utilisation data.', 'danger');
    } finally {
        _spinner(false);
    }
}

// ── Team Tab ──────────────────────────────────────────────────────────────────

async function _renderTeamTab() {
    const extras = {};
    const empTypes = _selectedIds('util-filter-emp-types');
    if (empTypes) extras.employment_types = empTypes;
    extras.show_auto = _showAuto ? '1' : '0';

    const data = await apiFetch(API_URLS.rp_versions.utilisation.teams(planPk, versionPk).href + _buildQS(extras));
    const { sprints = [], rows = [] } = data ?? {};
    const hasData = rows.length > 0;

    document.getElementById('util-team-no-data')?.classList.toggle('d-none', hasData);
    document.getElementById('util-team-chart-card')?.classList.toggle('d-none', !hasData);
    document.getElementById('util-team-table-card')?.classList.toggle('d-none', !hasData);
    if (!hasData) return;

    _renderTeamChart(sprints, rows);
    _renderTeamTable(sprints, rows);
}

function _renderTeamChart(sprints, rows) {
    if (_teamChart) { _teamChart.destroy(); _teamChart = null; }
    const canvas = document.getElementById('util-team-chart');
    if (!canvas) return;

    const labels  = sprints.map(s => s.name);
    const netCap  = sprints.map((_, i) =>
        _round(rows.reduce((sum, r) => sum + (r.cells[i]?.net_capacity ?? 0), 0), 2));
    const alloc   = sprints.map((_, i) =>
        _round(rows.reduce((sum, r) => sum + (r.cells[i]?.allocated_days ?? 0), 0), 2));
    const utilPct = sprints.map((_, i) => {
        let sum = 0, n = 0;
        rows.forEach(r => { const p = r.cells[i]?.utilisation_pct; if (p != null) { sum += p; n++; } });
        return n ? _round(sum / n, 1) : null;
    });

    _teamChart = _barLineChart(canvas, labels, netCap, alloc, utilPct);
}

function _renderTeamTable(sprints, rows) {
    const tbody = document.getElementById('util-team-tbody');
    if (!tbody) return;
    tbody.innerHTML = rows.map(row => {
        let totNet = 0, totAlloc = 0, utilSum = 0, utilN = 0, over = 0;
        row.cells.forEach((c, i) => {
            if (sprints[i]?.is_past) return;  // skip past sprints (#6)
            totNet   += c.net_capacity ?? 0;
            totAlloc += c.allocated_days;
            if (c.utilisation_pct != null) { utilSum += c.utilisation_pct; utilN++; }
            if (c.is_over) over++;
        });
        const avg = utilN ? _round(utilSum / utilN, 1) : null;
        return `<tr>
            <td>${escHtml(row.team_name)}</td>
            <td class="text-end">${_fmtDays(totNet || null)}</td>
            <td class="text-end">${_fmtDays(totAlloc)}</td>
            <td class="text-end">${_fmtPct(avg)}</td>
            <td class="text-end${over > 0 ? ' text-danger fw-semibold' : ''}">${over}</td>
        </tr>`;
    }).join('');
}

// ── Member Tab ────────────────────────────────────────────────────────────────

async function _renderMemberTab() {
    const extras = {};
    const members  = _selectedIds('util-filter-members');
    const empTypes = _selectedIds('util-filter-emp-types');
    const projects = _selectedIds('util-filter-projects');
    if (members)  extras.members          = members;
    if (empTypes) extras.employment_types = empTypes;
    if (projects) extras.projects         = projects;
    extras.show_auto = _showAuto ? '1' : '0';

    _memberData = (await apiFetch(
        API_URLS.rp_versions.utilisation.members(planPk, versionPk).href + _buildQS(extras)
    )) ?? { sprints: [], rows: [] };

    const { sprints = [], rows = [] } = _memberData;
    const hasData = rows.length > 0;

    document.getElementById('util-member-no-data')?.classList.toggle('d-none', hasData);
    document.getElementById('util-member-chart-card')?.classList.toggle('d-none', !hasData);
    document.getElementById('util-member-table-card')?.classList.toggle('d-none', !hasData);
    if (!hasData) return;

    if (_memberView === 'bar') {
        _showMemberView('bar');
        _renderMemberBarChart(sprints, rows);
    } else {
        _showMemberView('heatmap');
        _renderMemberHeatmap(sprints, rows);
    }
    _renderMemberTable(sprints, rows);
}

function _showMemberView(view) {
    document.getElementById('util-member-bar-view')?.classList.toggle('d-none', view !== 'bar');
    document.getElementById('util-member-heatmap-view')?.classList.toggle('d-none', view !== 'heatmap');
    const hint = document.getElementById('util-heatmap-rampdown-hint');
    if (hint) hint.style.display = view === 'heatmap' ? '' : 'none';
}

function _renderMemberBarChart(sprints, rows) {
    if (_memberChart) { _memberChart.destroy(); _memberChart = null; }
    const canvas = document.getElementById('util-member-chart');
    if (!canvas) return;

    // Per-sprint chart (same as team chart) — aggregate all rows (#8)
    const labels  = sprints.map(s => s.name);
    const netCap  = sprints.map((_, i) =>
        _round(rows.reduce((sum, r) => sum + (r.cells[i]?.net_capacity ?? 0), 0), 2));
    const alloc   = sprints.map((_, i) =>
        _round(rows.reduce((sum, r) => sum + (r.cells[i]?.allocated_days ?? 0), 0), 2));
    const utilPct = sprints.map((_, i) => {
        let sum = 0, n = 0;
        rows.forEach(r => { const p = r.cells[i]?.utilisation_pct; if (p != null) { sum += p; n++; } });
        return n ? _round(sum / n, 1) : null;
    });

    _memberChart = _barLineChart(canvas, labels, netCap, alloc, utilPct);
}

function _renderMemberHeatmap(sprints, rows) {
    const thead = document.getElementById('util-heatmap-thead');
    const tbody = document.getElementById('util-heatmap-tbody');
    if (!thead || !tbody) return;

    thead.innerHTML = `<tr>
        <th>Member</th>
        ${sprints.map(s => `<th>${escHtml(s.name)}</th>`).join('')}
    </tr>`;

    tbody.innerHTML = rows.map((row, ri) => {
        const cells = sprints.map((s, ci) => {
            const c = row.cells[ci];
            if (!c) return `<td class="util-heatmap-cell util-cell-none" data-ri="${ri}" data-ci="${ci}">—</td>`;
            const cls   = _cellClass(c.utilisation_pct, c.allocated_days);
            const label = c.utilisation_pct != null
                ? `${c.utilisation_pct.toFixed(0)}%`
                : (c.allocated_days ? `${c.allocated_days}d` : '—');
            return `<td class="util-heatmap-cell ${cls}" data-ri="${ri}" data-ci="${ci}"
                title="${escHtml(row.member_name)} · ${escHtml(s.name)} — ${_fmtPct(c.utilisation_pct)}"
                >${escHtml(label)}</td>`;
        }).join('');
        return `<tr>
            <td>${escHtml(row.member_name)}<br><small class="text-secondary">${escHtml(row.team_name)}</small></td>
            ${cells}
        </tr>`;
    }).join('');
}

function _renderMemberTable(sprints, rows) {
    const tbody = document.getElementById('util-member-tbody');
    if (!tbody) return;
    tbody.innerHTML = rows.map(row => {
        let totNet = 0, totAlloc = 0, utilSum = 0, utilN = 0, over = 0;
        row.cells.forEach((c, i) => {
            if (sprints[i]?.is_past) return;
            totNet   += c.net_capacity ?? 0;
            totAlloc += c.allocated_days;
            if (c.utilisation_pct != null) { utilSum += c.utilisation_pct; utilN++; }
            if (c.is_over) over++;
        });
        const avg = utilN ? _round(utilSum / utilN, 1) : null;
        return `<tr>
            <td>${escHtml(row.member_name)}<br><small class="text-secondary">${escHtml(row.team_name ?? '')}</small></td>
            <td class="text-end">${_fmtDays(totNet || null)}</td>
            <td class="text-end">${_fmtDays(totAlloc)}</td>
            <td class="text-end">${_fmtPct(avg)}</td>
            <td class="text-end${over > 0 ? ' text-danger fw-semibold' : ''}">${over}</td>
        </tr>`;
    }).join('');
}

// Bound once on the static container — reads _memberData at click time
function _bindHeatmapClick() {
    document.getElementById('util-member-heatmap-view')?.addEventListener('click', e => {
        const cell = e.target.closest('.util-heatmap-cell');
        if (!cell || !_memberData) return;
        const ri   = parseInt(cell.dataset.ri, 10);
        const ci   = parseInt(cell.dataset.ci, 10);
        const row  = _memberData.rows[ri];
        const sprint = _memberData.sprints[ci];
        const data = row?.cells[ci];
        if (row && sprint && data) _openDrilldown(row, sprint, data);
    });
    document.getElementById('util-drilldown-close')?.addEventListener('click', () => {
        document.getElementById('util-drilldown-panel')?.classList.add('d-none');
    });
}

function _openDrilldown(row, sprint, cell) {
    const panel = document.getElementById('util-drilldown-panel');
    if (!panel) return;

    document.getElementById('util-drilldown-title').textContent =
        `${row.member_name} — ${sprint.name}`;

    const tbody = document.getElementById('util-drilldown-tbody');
    if (tbody) {
        const bd = cell.project_breakdown ?? [];
        tbody.innerHTML = bd.length
            ? bd.map(b => `<tr>
                <td>${escHtml(b.programme_name ?? '—')}</td>
                <td>${escHtml(b.project_name ?? '—')}</td>
                <td class="text-end">${_fmtDays(b.days)}</td>
              </tr>`).join('')
            : `<tr><td colspan="3" class="text-center text-secondary py-2">No allocation this sprint</td></tr>`;
    }

    document.getElementById('util-drilldown-net').textContent   = `Net capacity: ${_fmtDays(cell.net_capacity)}`;
    document.getElementById('util-drilldown-total').textContent = `Total allocated: ${_fmtDays(cell.allocated_days)}`;
    document.getElementById('util-drilldown-pct').textContent   = `Utilisation: ${_fmtPct(cell.utilisation_pct)}`;

    panel.classList.remove('d-none');
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function _bindMemberViewToggle() {
    document.getElementById('util-member-view-bar')?.addEventListener('click', () => {
        _memberView = 'bar';
        document.getElementById('util-member-view-bar')?.classList.add('active');
        document.getElementById('util-member-view-heatmap')?.classList.remove('active');
        document.getElementById('util-drilldown-panel')?.classList.add('d-none');
        _showMemberView('bar');
        if (_memberData?.rows?.length) _renderMemberBarChart(_memberData.sprints, _memberData.rows);
    });
    document.getElementById('util-member-view-heatmap')?.addEventListener('click', () => {
        _memberView = 'heatmap';
        document.getElementById('util-member-view-heatmap')?.classList.add('active');
        document.getElementById('util-member-view-bar')?.classList.remove('active');
        _showMemberView('heatmap');
        if (_memberData?.rows?.length) _renderMemberHeatmap(_memberData.sprints, _memberData.rows);
    });
}

// ── Programme Tab ─────────────────────────────────────────────────────────────

async function _renderProgrammeTab() {
    const wrap   = document.getElementById('util-prog-charts-wrap');
    const noData = document.getElementById('util-prog-no-data');

    const progs = _selectedIds('util-filter-programmes');
    const extras = {};
    const projs = _selectedIds('util-filter-projects');
    if (progs) extras.programmes = progs;
    if (projs) extras.projects = projs;
    extras.show_auto = _showAuto ? '1' : '0';

    const data = await apiFetch(API_URLS.rp_versions.utilisation.programmes(planPk, versionPk).href + _buildQS(extras));
    const { sprints = [], rows = [] } = data ?? {};

    _progCharts.forEach(c => c.destroy());
    _progCharts = [];

    if (!wrap) return;
    wrap.innerHTML = '';

    const hasData = rows.length > 0;
    noData?.classList.toggle('d-none', hasData);
    if (!hasData) return;

    const labels = sprints.map(s => s.name);

    rows.forEach((row, idx) => {
        const cvId = `util-prog-cv-${idx}`;
        const card = document.createElement('div');
        card.className = 'card border-0 shadow-sm mb-3';
        card.innerHTML = `
            <div class="card-header d-flex align-items-center justify-content-between py-2">
                <span class="fw-semibold small">${escHtml(row.programme_name)}</span>
                <div class="d-flex gap-3 small text-secondary">
                    <span>Budget: <strong>${_fmtCost(row.total_budget)}</strong></span>
                    <span>Forecast: <strong>${_fmtCost(row.total_forecast)}</strong></span>
                </div>
            </div>
            <div class="card-body" style="position:relative;height:280px;">
                <canvas id="${cvId}"></canvas>
            </div>`;
        wrap.appendChild(card);

        const canvas = document.getElementById(cvId);
        if (!canvas) return;

        const chart = new Chart(canvas, {
            data: {
                labels,
                datasets: [
                    {
                        type: 'bar',
                        label: 'Forecast Cost (£)',
                        data: row.cells.map(c => c.forecast_cost),
                        backgroundColor: 'rgba(67,97,238,0.75)',
                        yAxisID: 'y',
                        order: 2,
                    },
                    {
                        type: 'line',
                        label: 'Cumulative (£)',
                        data: row.cells.map(c => c.cumulative_cost),
                        borderColor: '#20c997',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        pointRadius: 3,
                        yAxisID: 'y',
                        order: 1,
                    },
                    {
                        type: 'line',
                        label: 'Budget Baseline (£)',
                        data: row.cells.map(c => c.budget_baseline),
                        borderColor: '#dc3545',
                        backgroundColor: 'transparent',
                        borderDash: [6, 3],
                        borderWidth: 1.5,
                        pointRadius: 0,
                        yAxisID: 'y',
                        order: 0,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: true, position: 'top', labels: { font: { size: 11 } } },
                    tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${_fmtCost(ctx.parsed.y)}` } },
                },
                scales: {
                    x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            font: { size: 10 },
                            callback: v => `£${Math.round(v).toLocaleString()}`,
                        },
                    },
                },
            },
        });
        _progCharts.push(chart);
    });
}

// ── Shared bar + line chart ───────────────────────────────────────────────────

function _barLineChart(canvas, labels, netCapData, allocData, utilData) {
    return new Chart(canvas, {
        data: {
            labels,
            datasets: [
                {
                    type: 'bar',
                    label: 'Net Capacity',
                    data: netCapData,
                    backgroundColor: 'rgba(67,97,238,0.75)',
                    yAxisID: 'y',
                    order: 2,
                },
                {
                    type: 'bar',
                    label: 'Allocated',
                    data: allocData,
                    backgroundColor: 'rgba(247,127,0,0.85)',
                    yAxisID: 'y',
                    order: 2,
                },
                {
                    type: 'line',
                    label: 'Util%',
                    data: utilData,
                    borderColor: '#20c997',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    pointRadius: 3,
                    yAxisID: 'y1',
                    order: 1,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => ctx.datasetIndex === 2
                            ? `${ctx.dataset.label}: ${_fmtPct(ctx.parsed.y)}`
                            : `${ctx.dataset.label}: ${_fmtDays(ctx.parsed.y)}`,
                    },
                },
            },
            scales: {
                x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
                y: {
                    beginAtZero: true,
                    position: 'left',
                    title: { display: true, text: 'Days', font: { size: 10 } },
                    ticks: { font: { size: 10 } },
                },
                y1: {
                    beginAtZero: true,
                    position: 'right',
                    title: { display: true, text: 'Util%', font: { size: 10 } },
                    grid: { drawOnChartArea: false },
                    ticks: { font: { size: 10 }, callback: v => `${v}%` },
                },
            },
        },
    });
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
