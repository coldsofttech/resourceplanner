'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch, escHtml, setPageTitle } from '../main.js';

let _allActuals = [];
let _sprintChart = null;

document.addEventListener('DOMContentLoaded', () => {
    setPageTitle('Project Actuals');
    _loadDropdowns();
    _loadActuals();

    document.getElementById('filter-fy')?.addEventListener('change', _applyFilters);
    document.getElementById('filter-programme')?.addEventListener('change', async e => {
        await _loadProjectOptions(e.target.value);
        _applyFilters();
    });
    document.getElementById('filter-project')?.addEventListener('change', _applyFilters);
});

// ── Dropdowns ────────────────────────────────────────────────────────────────

async function _loadDropdowns() {
    try {
        const [fys, programmes] = await Promise.all([
            apiFetch(API_URLS.project_actuals.fy_options.href),
            apiFetch(API_URLS.recharges.programme_options.href),
        ]);

        const fySel = document.getElementById('filter-fy');
        (fys || []).forEach(f => {
            const opt = document.createElement('option');
            opt.value = f.id;
            opt.textContent = f.short_fy;
            fySel.appendChild(opt);
        });

        const progSel = document.getElementById('filter-programme');
        (programmes || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            progSel.appendChild(opt);
        });
    } catch (_) { /* non-critical */ }
}

async function _loadProjectOptions(programmeId) {
    const projSel = document.getElementById('filter-project');
    if (!projSel) return;
    const currentVal = projSel.value;
    projSel.innerHTML = '<option value="">All Projects</option>';
    try {
        const projects = await apiFetch(API_URLS.project_actuals.project_options(programmeId).href);
        (projects || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            projSel.appendChild(opt);
        });
        if (currentVal && [...projSel.options].some(o => o.value === currentVal)) {
            projSel.value = currentVal;
        }
    } catch (_) { /* non-critical */ }
}

// ── Data load ────────────────────────────────────────────────────────────────

async function _loadActuals() {
    const loadingEl   = document.getElementById('actuals-loading');
    const tableWrapEl = document.getElementById('actuals-table-wrap');
    const emptyEl     = document.getElementById('actuals-empty');

    loadingEl?.classList.remove('d-none');
    tableWrapEl?.classList.add('d-none');
    emptyEl?.classList.add('d-none');

    try {
        _allActuals = await apiFetch(API_URLS.project_actuals.list.href);
        _applyFilters();
    } catch (_) {
        if (loadingEl) loadingEl.innerHTML = '<span class="text-danger">Failed to load project actuals.</span>';
    }
}

// ── Filters ──────────────────────────────────────────────────────────────────

function _applyFilters() {
    const fyId   = document.getElementById('filter-fy')?.value || null;
    const progId = document.getElementById('filter-programme')?.value;
    const projId = document.getElementById('filter-project')?.value;

    let filtered = _allActuals;
    if (progId) filtered = filtered.filter(a => String(a.programme) === progId);
    if (projId) filtered = filtered.filter(a => String(a.project) === projId);
    if (fyId)   filtered = filtered.filter(a =>
        (a.sprint_actuals || []).some(sa => String(sa.sprint_fy_id) === String(fyId))
    );

    _renderActuals(filtered, fyId);
}

// ── Render ───────────────────────────────────────────────────────────────────

function _renderActuals(actuals, fyId) {
    const loadingEl   = document.getElementById('actuals-loading');
    const tableWrapEl = document.getElementById('actuals-table-wrap');
    const emptyEl     = document.getElementById('actuals-empty');
    const tbody       = document.getElementById('actuals-tbody');
    const countEl     = document.getElementById('actuals-count');

    loadingEl?.classList.add('d-none');

    if (!actuals || actuals.length === 0) {
        tableWrapEl?.classList.add('d-none');
        emptyEl?.classList.remove('d-none');
        if (countEl) countEl.textContent = '';
        return;
    }

    // Collect all sprints visible under the current FY filter, sorted by number
    const sprintMap = new Map(); // sprint id → {id, name, number, fy_id, fy_short}
    actuals.forEach(a => {
        (a.sprint_actuals || []).forEach(sa => {
            if (fyId && String(sa.sprint_fy_id) !== String(fyId)) return;
            if (!sprintMap.has(sa.sprint)) {
                sprintMap.set(sa.sprint, {
                    id: sa.sprint,
                    name: sa.sprint_name,
                    number: sa.sprint_number,
                    fy_id: sa.sprint_fy_id,
                    fy_short: sa.sprint_fy_short,
                });
            }
        });
    });
    const sprints = [...sprintMap.values()].sort((a, b) => a.number - b.number);

    // Rebuild header row
    const headerRow = document.getElementById('actuals-header-row');
    const fixedHeaders = [
        '<th>Programme</th>',
        '<th>Project</th>',
        '<th>FY</th>',
        '<th>Label</th>',
        '<th>Code</th>',
        '<th>Assigned Team</th>',
        '<th>Collaborators</th>',
        '<th class="text-end">Estimate</th>',
        '<th class="text-end">Est. + Contingency</th>',
        '<th class="text-end">Total Cost</th>',
        '<th class="text-end">Remaining</th>',
        '<th class="text-center">Risk</th>',
    ];
    const sprintHeaders = sprints.map(s =>
        `<th class="text-end" style="min-width:90px;font-size:11px">${escHtml(s.name)}</th>`
    );
    headerRow.innerHTML = [...fixedHeaders, ...sprintHeaders, '<th style="width:36px"></th>'].join('');

    // Render body
    tableWrapEl?.classList.remove('d-none');
    emptyEl?.classList.add('d-none');
    if (countEl) countEl.textContent = `${actuals.length} project${actuals.length !== 1 ? 's' : ''}`;

    tbody.innerHTML = actuals.map(a => _renderRow(a, sprints, fyId)).join('');

    // Init Bootstrap tooltips on label cells
    tbody.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        bootstrap.Tooltip.getOrCreateInstance(el);
    });
}

function _renderRow(a, sprints, fyId) {
    const risk        = a.risk || 'NEUTRAL';
    const riskBadge   = _riskBadge(risk);
    const collab      = (a.collaborator_names || []).join(', ') || '—';
    const estimate    = _fmt(a.estimate_value);
    const estimateWC  = _fmt(a.estimate_value_with_contingency);
    const total       = _fmt(a.total_cost_till_date);
    const remaining   = _fmt(a.remaining_amount);
    const remainClass = parseFloat(a.remaining_amount) >= 0 ? 'text-success' : 'text-danger';

    // FY column — derive from last_updated_sprint or sprint_actuals
    const fyText = _fyLabel(a, fyId);

    // Label cell with primary + hover for secondaries
    const labelCell = _labelCell(a);

    // Build sprint cost lookup for this project
    const costBySprint = {};
    (a.sprint_actuals || []).forEach(sa => {
        if (!fyId || String(sa.sprint_fy_id) === String(fyId)) {
            costBySprint[sa.sprint] = sa.total_cost;
        }
    });
    const sprintCols = sprints.map(s => {
        const val = costBySprint[s.id];
        return val != null
            ? `<td class="text-end" style="font-size:12px">${_fmt(val)}</td>`
            : `<td class="text-end text-secondary" style="font-size:12px">—</td>`;
    }).join('');

    return `<tr>
        <td>${escHtml(a.programme_name || '—')}</td>
        <td class="fw-500">${escHtml(a.project_name || '—')}</td>
        <td class="text-secondary" style="font-size:12px">${escHtml(fyText)}</td>
        ${labelCell}
        <td class="rp-code text-secondary" style="font-size:12px">${escHtml(a.code || '—')}</td>
        <td>${escHtml(a.assigned_team_name || '—')}</td>
        <td class="text-secondary" style="font-size:12px">${escHtml(collab)}</td>
        <td class="text-end">${estimate}</td>
        <td class="text-end">${estimateWC}</td>
        <td class="text-end fw-600">${total}</td>
        <td class="text-end ${remainClass}">${remaining}</td>
        <td class="text-center">${riskBadge}</td>
        ${sprintCols}
        <td>
            <button class="btn btn-ghost-icon btn-sm" title="Sprint utilisation chart"
                    onclick="openChart(${a.id}, '${escHtml(a.project_name || '')}')">
                <i class="bi bi-bar-chart-line"></i>
            </button>
        </td>
    </tr>`;
}

function _labelCell(a) {
    const labels = a.all_labels || [];
    if (!labels.length) return '<td class="text-secondary">—</td>';

    const primary = labels.find(l => l.is_primary) || labels[0];
    const secondaries = labels.filter(l => l !== primary);

    if (!secondaries.length) {
        return `<td><span class="rp-code text-secondary" style="font-size:12px">${escHtml(primary.label)}</span></td>`;
    }

    const tooltip = secondaries.map(l => l.label).join(', ');
    return `<td>
        <span class="rp-code text-secondary" style="font-size:12px"
              title="Also: ${escHtml(tooltip)}"
              data-bs-toggle="tooltip" data-bs-placement="top">
            ${escHtml(primary.label)}
            <i class="bi bi-info-circle ms-1" style="font-size:10px;opacity:.6"></i>
        </span>
    </td>`;
}

function _fyLabel(a, fyId) {
    if (fyId) {
        const match = (a.sprint_actuals || []).find(sa => String(sa.sprint_fy_id) === String(fyId));
        return match?.sprint_fy_short || '—';
    }
    // Show distinct FY labels
    const fys = [...new Set((a.sprint_actuals || []).map(sa => sa.sprint_fy_short).filter(Boolean))];
    return fys.join(', ') || '—';
}

// ── Chart ────────────────────────────────────────────────────────────────────

window.openChart = function(actualsId, projectName) {
    const a = _allActuals.find(x => x.id === actualsId);
    if (!a) return;

    const fyId = document.getElementById('filter-fy')?.value || null;

    const rows = (a.sprint_actuals || [])
        .filter(sa => !fyId || String(sa.sprint_fy_id) === String(fyId))
        .sort((x, y) => x.sprint_number - y.sprint_number);

    const titleEl = document.getElementById('chart-modal-title');
    const badgeEl = document.getElementById('chart-modal-risk-badge');
    if (titleEl) titleEl.textContent = `Sprint Utilisation — ${projectName}`;
    if (badgeEl) badgeEl.innerHTML = _riskBadge(a.risk || 'NEUTRAL');

    const estimateWC = parseFloat(a.estimate_value_with_contingency) || 0;
    const estimatePct = estimateWC > 0
        ? (parseFloat(a.estimate_value) / estimateWC) * 100
        : 0;

    const labels = rows.map(r => r.sprint_name);
    const barData = rows.map(r => estimateWC > 0
        ? parseFloat(((parseFloat(r.total_cost) / estimateWC) * 100).toFixed(2))
        : 0
    );

    const barColors = barData.map((_, i) => {
        const cumPct = barData.slice(0, i + 1).reduce((s, v) => s + v, 0);
        if (cumPct > 100) return 'rgba(239,68,68,0.75)';
        if (cumPct > estimatePct) return 'rgba(245,158,11,0.75)';
        return 'rgba(99,102,241,0.75)';
    });

    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('sprintChartModal'));

    if (_sprintChart) {
        _sprintChart.destroy();
        _sprintChart = null;
    }

    modal.show();

    requestAnimationFrame(() => {
        const ctx = document.getElementById('sprintChart')?.getContext('2d');
        if (!ctx) return;

        _sprintChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        type: 'bar',
                        label: 'Sprint Cost %',
                        data: barData,
                        backgroundColor: barColors,
                        borderColor: barColors.map(c => c.replace('0.75', '1')),
                        borderWidth: 1,
                        order: 2,
                    },
                    {
                        type: 'line',
                        label: `Estimate (${estimatePct.toFixed(1)}%)`,
                        data: Array(labels.length).fill(parseFloat(estimatePct.toFixed(2))),
                        borderColor: '#f59e0b',
                        borderWidth: 2,
                        borderDash: [6, 3],
                        pointRadius: 0,
                        fill: false,
                        order: 1,
                    },
                    {
                        type: 'line',
                        label: 'Est. + Contingency (100%)',
                        data: Array(labels.length).fill(100),
                        borderColor: '#ef4444',
                        borderWidth: 2,
                        borderDash: [6, 3],
                        pointRadius: 0,
                        fill: false,
                        order: 0,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`,
                        },
                    },
                },
                scales: {
                    y: {
                        title: { display: true, text: '% of Est. + Contingency' },
                        ticks: { callback: v => `${v}%` },
                    },
                    x: {
                        ticks: { maxRotation: 45, minRotation: 0 },
                    },
                },
            },
        });
    });
};

// ── Utilities ────────────────────────────────────────────────────────────────

function _riskBadge(risk) {
    if (risk === 'RISK')    return '<span class="rp-badge rp-badge--danger">Risk</span>';
    if (risk === 'WARNING') return '<span class="rp-badge rp-badge--warning">Warning</span>';
    return '<span class="rp-badge rp-badge--muted">Neutral</span>';
}

function _fmt(val) {
    const n = parseFloat(val);
    if (isNaN(n)) return '—';
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'GBP', minimumFractionDigits: 2 }).format(n);
}

