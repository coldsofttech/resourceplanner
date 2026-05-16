'use strict';

import { apiFetch, showFlash, formatDate, formatDateTime, escHtml, hasPerm } from './../main.js';

// ── Widget registry ────────────────────────────────────────────────────────

const ALL_WIDGETS = [
    { id: 'active_sprint',        title: 'Active Sprint',     type: 'count',  cols: 3 },
    { id: 'active_fy',            title: 'Financial Year',    type: 'count',  cols: 3 },
    { id: 'team_members_count',   title: 'Team Members',      type: 'count',  cols: 3 },
    { id: 'delivery_teams_count', title: 'Delivery Teams',    type: 'count',  cols: 3 },
    { id: 'open_projects_count',  title: 'Open Projects',     type: 'count',  cols: 3 },
    { id: 'upcoming_leaves',      title: 'Upcoming Leaves',   type: 'list',   cols: 6 },
    { id: 'team_members_table',   title: 'Team Members',      type: 'table',  cols: 12 },
    { id: 'projects_table',       title: 'Projects',          type: 'table',  cols: 12 },
    { id: 'leaves_by_team_chart', title: 'Leaves by Team',    type: 'graph_bar', cols: 6 },
    { id: 'sprint_progress_chart',title: 'Sprint Progress',   type: 'graph_pie', cols: 6 },
];

const DEFAULT_CONFIG = ALL_WIDGETS.map((w, i) => ({
    id: w.id,
    visible: i < 6,
    order: i,
}));

// ── State ─────────────────────────────────────────────────────────────────

let _config = [];      // [{id, visible, order}]
let _sortable = null;  // Sortable instance for config list
let _panel = null;     // Bootstrap Offcanvas

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    _panel = new bootstrap.Offcanvas(document.getElementById('dashboardConfigPanel'));

    document.getElementById('dashboard-config-btn').addEventListener('click', () => {
        renderConfigList();
        _panel.show();
    });
    document.getElementById('save-dashboard-btn').addEventListener('click', saveDashboard);
    document.getElementById('reset-dashboard-btn').addEventListener('click', resetDashboard);

    await loadDashboard();
});

// ── Config load & save ────────────────────────────────────────────────────

async function loadDashboard() {
    try {
        const data = await apiFetch('/api/v1/users/me/dashboard_config/');
        const saved = data?.dashboard_config;
        if (saved && Array.isArray(saved) && saved.length) {
            _config = _mergeConfig(saved);
        } else {
            _config = [...DEFAULT_CONFIG];
        }
    } catch (_) {
        _config = [...DEFAULT_CONFIG];
    }
    await renderDashboard();
}

function _mergeConfig(saved) {
    const savedMap = {};
    saved.forEach(s => { savedMap[s.id] = s; });

    const merged = ALL_WIDGETS.map((w, i) => {
        const s = savedMap[w.id];
        return {
            id: w.id,
            visible: s ? !!s.visible : i < 6,
            order: s ? (s.order ?? i) : i,
        };
    });
    merged.sort((a, b) => a.order - b.order);
    return merged;
}

async function saveDashboard() {
    const btn   = document.getElementById('save-dashboard-btn');
    const label = document.getElementById('save-dashboard-label');
    btn.disabled = true;
    label.textContent = 'Saving…';
    try {
        await apiFetch('/api/v1/users/me/dashboard_config/', {
            method: 'POST',
            body: JSON.stringify(_config),
        });
        document.getElementById('config-save-success').classList.remove('d-none');
        setTimeout(() => document.getElementById('config-save-success').classList.add('d-none'), 2500);
        _panel.hide();
        await renderDashboard();
    } catch (_) {
        showFlash('Could not save dashboard layout.', 'error');
    } finally {
        btn.disabled = false;
        label.textContent = 'Save layout';
    }
}

function resetDashboard() {
    _config = [...DEFAULT_CONFIG];
    renderConfigList();
}

// ── Config panel rendering ────────────────────────────────────────────────

function renderConfigList() {
    const ul = document.getElementById('widget-config-list');
    const visible = [..._config].sort((a, b) => a.order - b.order);

    ul.innerHTML = visible.map(cfg => {
        const def = ALL_WIDGETS.find(w => w.id === cfg.id);
        if (!def) return '';
        const eyeIcon = cfg.visible ? 'bi-eye' : 'bi-eye-slash';
        const eyeTitle = cfg.visible ? 'Hide widget' : 'Show widget';
        return `
            <li class="d-flex align-items-center gap-2 py-2 border-bottom" data-widget-id="${cfg.id}"
                style="cursor:default">
                <i class="bi bi-grip-vertical text-secondary" style="cursor:grab;font-size:16px"></i>
                <span class="flex-grow-1 small fw-500">${escHtml(def.title)}
                    <span class="text-secondary fw-400 ms-1">(${def.type.replace('_', ' ')})</span>
                </span>
                <button class="btn btn-ghost-icon" title="${eyeTitle}"
                        onclick="toggleWidgetVisible('${cfg.id}', this)">
                    <i class="bi ${eyeIcon}"></i>
                </button>
            </li>`;
    }).join('');

    // Wire up Sortable
    if (_sortable) _sortable.destroy();
    _sortable = Sortable.create(ul, {
        handle: '.bi-grip-vertical',
        animation: 150,
        onEnd() {
            const items = ul.querySelectorAll('[data-widget-id]');
            items.forEach((el, idx) => {
                const id = el.dataset.widgetId;
                const cfg = _config.find(c => c.id === id);
                if (cfg) cfg.order = idx;
            });
        },
    });
}

window.toggleWidgetVisible = (id, btn) => {
    const cfg = _config.find(c => c.id === id);
    if (!cfg) return;
    cfg.visible = !cfg.visible;
    const icon = btn.querySelector('i');
    icon.className = `bi ${cfg.visible ? 'bi-eye' : 'bi-eye-slash'}`;
    btn.title = cfg.visible ? 'Hide widget' : 'Show widget';
};

// ── Dashboard rendering ────────────────────────────────────────────────────

async function renderDashboard() {
    const grid    = document.getElementById('dashboard-grid');
    const loading = document.getElementById('dashboard-loading');
    if (loading) loading.classList.add('d-none');

    const visible = [..._config]
        .filter(c => c.visible)
        .sort((a, b) => a.order - b.order);

    if (!visible.length) {
        grid.innerHTML = `
            <div class="col-12 text-center text-secondary py-5">
                <i class="bi bi-grid-3x3-gap display-6 d-block mb-2"></i>
                No widgets visible. <button class="btn btn-link p-0" onclick="document.getElementById('dashboard-config-btn').click()">Configure dashboard</button>
            </div>`;
        return;
    }

    grid.innerHTML = visible.map(cfg => {
        const def = ALL_WIDGETS.find(w => w.id === cfg.id);
        if (!def) return '';
        return `<div class="col-lg-${def.cols} col-md-${Math.min(def.cols * 2, 12)}" id="widget-wrap-${cfg.id}">
                    <div class="rp-widget h-100" id="widget-${cfg.id}">
                        <p class="rp-widget-title">${escHtml(def.title)}</p>
                        <div class="rp-widget-body text-secondary small">
                            <div class="spinner-border spinner-border-sm me-1"></div>Loading…
                        </div>
                    </div>
                </div>`;
    }).join('');

    // Load each widget in parallel
    await Promise.allSettled(visible.map(cfg => loadWidget(cfg.id)));
}

async function loadWidget(id) {
    switch (id) {
        case 'active_sprint':        return loadActiveSprint();
        case 'active_fy':            return loadActiveFy();
        case 'team_members_count':   return loadCountWidget(id, '/api/v1/team-members/', 'Team Members');
        case 'delivery_teams_count': return loadCountWidget(id, '/api/v1/delivery-teams/', 'Delivery Teams');
        case 'open_projects_count':  return loadCountWidget(id, '/api/v1/projects/?page_size=1', 'Open Projects');
        case 'upcoming_leaves':      return loadUpcomingLeaves();
        case 'team_members_table':   return loadTeamMembersTable();
        case 'projects_table':       return loadProjectsTable();
        case 'leaves_by_team_chart': return loadLeavesByTeamChart();
        case 'sprint_progress_chart':return loadSprintProgressChart();
        default: setWidgetContent(id, '<span class="text-secondary">Widget not available.</span>');
    }
}

function setWidgetContent(id, html) {
    const body = document.querySelector(`#widget-${id} .rp-widget-body`);
    if (body) body.innerHTML = html;
}

// ── Widget loaders ─────────────────────────────────────────────────────────

async function loadActiveSprint() {
    try {
        const s = await apiFetch('/api/v1/sprints/active/');
        if (!s || !s.sprint_name) {
            setWidgetContent('active_sprint', '<span class="text-secondary small">No active sprint.</span>');
            return;
        }
        const pct = s.remaining_days != null ? s.remaining_days : '—';
        setWidgetContent('active_sprint', `
            <div class="rp-widget-count">${escHtml(s.sprint_name)}</div>
            <div class="rp-widget-count-label">
                <span class="${pct <= 5 ? 'text-danger' : pct <= 14 ? 'text-warning' : 'text-success'} fw-500">
                    ${pct}d remaining
                </span>
                &nbsp;·&nbsp; ${escHtml(s.start_date || '')} – ${escHtml(s.end_date || '')}
            </div>`);
    } catch (_) {
        setWidgetContent('active_sprint', '<span class="text-danger small">Could not load.</span>');
    }
}

async function loadActiveFy() {
    try {
        const fy = await apiFetch('/api/v1/fy/active/');
        if (!fy) {
            setWidgetContent('active_fy', '<span class="text-secondary small">No active financial year.</span>');
            return;
        }
        setWidgetContent('active_fy', `
            <div class="rp-widget-count">${escHtml(fy.short_fy || fy.long_fy || '—')}</div>
            <div class="rp-widget-count-label">
                ${escHtml(fy.start_date || '')} – ${escHtml(fy.end_date || '')}
                ${fy.remaining_days != null ? `&nbsp;·&nbsp; <span class="fw-500">${fy.remaining_days}d left</span>` : ''}
            </div>`);
    } catch (_) {
        setWidgetContent('active_fy', '<span class="text-danger small">Could not load.</span>');
    }
}

async function loadCountWidget(id, url, label) {
    try {
        const data = await apiFetch(url);
        const count = data?.pagination?.total_count
            ?? data?.count
            ?? (Array.isArray(data) ? data.length : '—');
        setWidgetContent(id, `
            <div class="rp-widget-count">${count}</div>
            <div class="rp-widget-count-label">${label}</div>`);
    } catch (_) {
        setWidgetContent(id, '<span class="text-danger small">Could not load.</span>');
    }
}

async function loadUpcomingLeaves() {
    try {
        const today = new Date().toISOString().slice(0, 10);
        const data  = await apiFetch(`/api/v1/leaves/?start_date__gte=${today}&ordering=start_date&page_size=8`);
        const items = Array.isArray(data) ? data : (data?.results || []);
        if (!items.length) {
            setWidgetContent('upcoming_leaves', '<span class="text-secondary small">No upcoming leaves.</span>');
            return;
        }
        const rows = items.map(l => `
            <div class="d-flex justify-content-between align-items-center py-1 border-bottom gap-3" style="font-size:13px">
                <span class="fw-500 text-truncate">${escHtml(l.member_name || l.team_member || '—')}</span>
                <span class="text-secondary text-nowrap">${escHtml(l.start_date || '')}${l.end_date && l.end_date !== l.start_date ? ' – ' + l.end_date : ''}</span>
            </div>`).join('');
        setWidgetContent('upcoming_leaves', rows);
    } catch (_) {
        setWidgetContent('upcoming_leaves', '<span class="text-danger small">Could not load.</span>');
    }
}

async function loadTeamMembersTable() {
    try {
        const data  = await apiFetch('/api/v1/team-members/?page_size=10');
        const items = Array.isArray(data) ? data : (data?.results || []);
        if (!items.length) {
            setWidgetContent('team_members_table', '<span class="text-secondary small">No team members found.</span>');
            return;
        }
        const rows = items.map(m => `
            <tr>
                <td>${escHtml(m.full_name || m.name || '—')}</td>
                <td class="text-secondary small">${escHtml(m.role_name || m.role || '—')}</td>
                <td class="text-secondary small">${escHtml(m.team_name || m.delivery_team || '—')}</td>
            </tr>`).join('');
        setWidgetContent('team_members_table', `
            <div class="rp-table-wrap mt-1">
                <table class="table rp-table table-sm">
                    <thead><tr><th>Name</th><th>Role</th><th>Team</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`);
    } catch (_) {
        setWidgetContent('team_members_table', '<span class="text-danger small">Could not load.</span>');
    }
}

async function loadProjectsTable() {
    try {
        const data  = await apiFetch('/api/v1/projects/?page_size=10');
        const items = Array.isArray(data) ? data : (data?.results || []);
        if (!items.length) {
            setWidgetContent('projects_table', '<span class="text-secondary small">No projects found.</span>');
            return;
        }
        const rows = items.map(p => `
            <tr>
                <td>${escHtml(p.name || p.project_name || '—')}</td>
                <td class="text-secondary small">${escHtml(p.status || p.status_name || '—')}</td>
                <td class="text-secondary small">${escHtml(p.programme_name || p.programme || '—')}</td>
            </tr>`).join('');
        setWidgetContent('projects_table', `
            <div class="rp-table-wrap mt-1">
                <table class="table rp-table table-sm">
                    <thead><tr><th>Name</th><th>Status</th><th>Programme</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`);
    } catch (_) {
        setWidgetContent('projects_table', '<span class="text-danger small">Could not load.</span>');
    }
}

async function loadLeavesByTeamChart() {
    try {
        const today = new Date().toISOString().slice(0, 10);
        const data  = await apiFetch(`/api/v1/leaves/?start_date__gte=${today}&page_size=100`);
        const items = Array.isArray(data) ? data : (data?.results || []);

        const counts = {};
        items.forEach(l => {
            const team = l.team_name || l.delivery_team || 'Unknown';
            counts[team] = (counts[team] || 0) + 1;
        });

        const labels = Object.keys(counts);
        const values = labels.map(l => counts[l]);

        if (!labels.length) {
            setWidgetContent('leaves_by_team_chart', '<span class="text-secondary small">No upcoming leave data.</span>');
            return;
        }

        const canvasId = 'chart-leaves-by-team';
        setWidgetContent('leaves_by_team_chart', `<canvas id="${canvasId}" height="180"></canvas>`);

        new Chart(document.getElementById(canvasId), {
            type: 'bar',
            data: {
                labels,
                datasets: [{ label: 'Leaves', data: values, backgroundColor: '#6366f1cc', borderRadius: 4 }],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
            },
        });
    } catch (_) {
        setWidgetContent('leaves_by_team_chart', '<span class="text-danger small">Could not load.</span>');
    }
}

async function loadSprintProgressChart() {
    try {
        const s = await apiFetch('/api/v1/sprints/active/');
        if (!s || s.total_days == null) {
            setWidgetContent('sprint_progress_chart', '<span class="text-secondary small">No active sprint.</span>');
            return;
        }

        const elapsed  = (s.total_days || 0) - (s.remaining_days || 0);
        const remaining = s.remaining_days || 0;

        const canvasId = 'chart-sprint-progress';
        setWidgetContent('sprint_progress_chart', `<canvas id="${canvasId}" height="180"></canvas>`);

        new Chart(document.getElementById(canvasId), {
            type: 'pie',
            data: {
                labels: ['Elapsed', 'Remaining'],
                datasets: [{
                    data: [elapsed, remaining],
                    backgroundColor: ['#6366f1cc', '#e2e8f0'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                    title: { display: true, text: escHtml(s.sprint_name || 'Sprint Progress') },
                },
            },
        });
    } catch (_) {
        setWidgetContent('sprint_progress_chart', '<span class="text-danger small">Could not load.</span>');
    }
}
