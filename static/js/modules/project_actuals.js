'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch, escHtml, setPageTitle, showFlash } from '../main.js';

const PAGE_SIZE = 20;

let _allActuals      = [];
let _fySprintsList   = [];   // sprints for the "current" FY (active or user-selected)
let _fySprintsFyId   = null; // which FY _fySprintsList belongs to
let _filteredActuals = [];
let _currentPage     = 1;
let _sprintChart     = null;
let _riskConfigId    = null;

document.addEventListener('DOMContentLoaded', () => {
    setPageTitle('Project Actuals');
    // Load dropdowns first (incl. active FY sprints pre-load), then actuals
    _loadDropdowns().then(() => _loadActuals());

    document.getElementById('filter-fy')?.addEventListener('change', async e => {
        const val = e.target.value;
        if (val) {
            await _loadFySprints(val);
        } else {
            // Filter cleared — revert to active FY sprints
            await _reloadActiveFySprints();
        }
        _currentPage = 1;
        _applyFilters();
    });
    document.getElementById('filter-programme')?.addEventListener('change', async e => {
        await _loadProjectOptions(e.target.value);
        _currentPage = 1;
        _applyFilters();
    });
    document.getElementById('filter-project')?.addEventListener('change', () => { _currentPage = 1; _applyFilters(); });
    document.getElementById('filter-team')?.addEventListener('change',    () => { _currentPage = 1; _applyFilters(); });
    document.getElementById('filter-risk')?.addEventListener('change',    () => { _currentPage = 1; _applyFilters(); });

    document.getElementById('risk-config-save-btn')?.addEventListener('click', _saveRiskConfig);
});

// ── Dropdowns ─────────────────────────────────────────────────────────────────

async function _loadDropdowns() {
    try {
        const [fys, programmes, teams, activeFy] = await Promise.all([
            apiFetch(API_URLS.project_actuals.fy_options.href).catch(() => []),
            apiFetch(API_URLS.recharges.programme_options.href).catch(() => []),
            apiFetch(API_URLS.project_actuals.team_options.href).catch(() => []),
            apiFetch(API_URLS.financial_years.active.href).catch(() => null),
        ]);

        const fySel      = document.getElementById('filter-fy');
        const activeFyId = activeFy?.id ? String(activeFy.id) : null;

        // Populate FY dropdown — include active FY even if it has no actuals yet
        const fyList = [...(fys || [])];
        if (activeFy && !fyList.some(f => String(f.id) === activeFyId)) {
            fyList.unshift(activeFy);
        }
        fyList.forEach(f => {
            const o = document.createElement('option');
            o.value = f.id;
            o.textContent = f.short_fy;
            fySel.appendChild(o);
        });

        // Pre-load active FY sprints (for accordion + chart defaults, without filtering the list)
        if (activeFyId) await _loadFySprints(activeFyId);

        const progSel = document.getElementById('filter-programme');
        (programmes || []).forEach(p => {
            const o = document.createElement('option');
            o.value = p.id;
            o.textContent = p.name;
            progSel.appendChild(o);
        });

        const teamSel = document.getElementById('filter-team');
        (teams || []).forEach(t => {
            const o = document.createElement('option');
            o.value = t.id;
            o.textContent = t.name;
            teamSel.appendChild(o);
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
            const o = document.createElement('option');
            o.value = p.id;
            o.textContent = p.name;
            projSel.appendChild(o);
        });
        if (currentVal && [...projSel.options].some(o => o.value === currentVal)) {
            projSel.value = currentVal;
        }
    } catch (_) { /* non-critical */ }
}

async function _loadFySprints(fyId) {
    if (!fyId) {
        _fySprintsList = [];
        _fySprintsFyId = null;
        return;
    }
    try {
        _fySprintsList = await apiFetch(API_URLS.project_actuals.fy_sprints(fyId).href) || [];
        _fySprintsFyId = String(fyId);
    } catch (_) {
        _fySprintsList = [];
        _fySprintsFyId = null;
    }
}

async function _reloadActiveFySprints() {
    try {
        const activeFy = await apiFetch(API_URLS.financial_years.active.href);
        await _loadFySprints(activeFy?.id || null);
    } catch (_) {
        _fySprintsList = [];
        _fySprintsFyId = null;
    }
}

// ── Data load ─────────────────────────────────────────────────────────────────

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

// ── Filters ───────────────────────────────────────────────────────────────────

function _applyFilters() {
    const fyId   = document.getElementById('filter-fy')?.value || null;
    const progId = document.getElementById('filter-programme')?.value;
    const projId = document.getElementById('filter-project')?.value;
    const teamId = document.getElementById('filter-team')?.value;
    const risk   = document.getElementById('filter-risk')?.value;

    let filtered = _allActuals;
    if (progId) filtered = filtered.filter(a => String(a.programme) === progId);
    if (projId) filtered = filtered.filter(a => String(a.project) === projId);
    if (fyId)   filtered = filtered.filter(a =>
        (a.sprint_actuals || []).some(sa => String(sa.sprint_fy_id) === String(fyId))
    );
    if (teamId) filtered = filtered.filter(a =>
        String(a.assigned_team) === teamId ||
        (a.collaborator_ids || []).some(id => String(id) === teamId)
    );
    if (risk)   filtered = filtered.filter(a => a.risk === risk);

    _filteredActuals = filtered;
    _renderPage(fyId);
}

// ── Pagination ────────────────────────────────────────────────────────────────

function _renderPage(fyId) {
    const total  = _filteredActuals.length;
    const pages  = Math.ceil(total / PAGE_SIZE) || 1;
    _currentPage = Math.max(1, Math.min(_currentPage, pages));

    const start = (_currentPage - 1) * PAGE_SIZE;
    const page  = _filteredActuals.slice(start, start + PAGE_SIZE);

    _renderActuals(page, total, fyId);
    _renderPagination(total, pages);
}

function _renderPagination(total, pages) {
    const paginationEl = document.getElementById('actuals-pagination');
    const infoEl       = document.getElementById('actuals-page-info');
    const controlsEl   = document.getElementById('actuals-page-controls');

    if (pages <= 1) {
        paginationEl?.classList.add('d-none');
        return;
    }

    paginationEl?.classList.remove('d-none');

    const start = (_currentPage - 1) * PAGE_SIZE + 1;
    const end   = Math.min(_currentPage * PAGE_SIZE, total);
    if (infoEl) infoEl.textContent = `Showing ${start}–${end} of ${total}`;

    if (!controlsEl) return;

    const items = [];
    items.push(`<li class="page-item${_currentPage === 1 ? ' disabled' : ''}">
        <a class="page-link" href="#" data-page="${_currentPage - 1}">&laquo;</a></li>`);

    const windowStart = Math.max(1, _currentPage - 2);
    const windowEnd   = Math.min(pages, windowStart + 4);
    for (let p = windowStart; p <= windowEnd; p++) {
        items.push(`<li class="page-item${p === _currentPage ? ' active' : ''}">
            <a class="page-link" href="#" data-page="${p}">${p}</a></li>`);
    }

    items.push(`<li class="page-item${_currentPage === pages ? ' disabled' : ''}">
        <a class="page-link" href="#" data-page="${_currentPage + 1}">&raquo;</a></li>`);

    controlsEl.innerHTML = items.join('');
    controlsEl.querySelectorAll('.page-link').forEach(a => {
        a.addEventListener('click', e => {
            e.preventDefault();
            const p = parseInt(a.dataset.page, 10);
            if (p >= 1 && p <= pages) {
                _currentPage = p;
                _renderPage(document.getElementById('filter-fy')?.value || null);
            }
        });
    });
}

// ── Render ────────────────────────────────────────────────────────────────────

function _renderActuals(actuals, total, fyId) {
    const loadingEl   = document.getElementById('actuals-loading');
    const tableWrapEl = document.getElementById('actuals-table-wrap');
    const emptyEl     = document.getElementById('actuals-empty');
    const tbody       = document.getElementById('actuals-tbody');
    const countEl     = document.getElementById('actuals-count');

    loadingEl?.classList.add('d-none');

    if (!_filteredActuals.length) {
        tableWrapEl?.classList.add('d-none');
        emptyEl?.classList.remove('d-none');
        document.getElementById('actuals-pagination')?.classList.add('d-none');
        if (countEl) countEl.textContent = '';
        return;
    }

    tableWrapEl?.classList.remove('d-none');
    emptyEl?.classList.add('d-none');
    if (countEl) countEl.textContent = `${total} project${total !== 1 ? 's' : ''}`;

    tbody.innerHTML = actuals.map(a => _renderAccordionRows(a, fyId)).join('');

    tbody.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        bootstrap.Tooltip.getOrCreateInstance(el);
    });
}

function _renderAccordionRows(a, fyId) {
    const risk        = a.risk || 'NEUTRAL';
    const rowClass    = risk === 'RISK' ? 'table-danger' : risk === 'WARNING' ? 'table-warning' : '';
    const collab      = (a.collaborator_names || []).join(', ') || '—';
    const estimate    = _fmt(a.estimate_value);
    const estimateWC  = _fmt(a.estimate_value_with_contingency);
    const total       = _fmt(a.total_cost_till_date);
    const remaining   = _fmt(a.remaining_amount);
    const remainClass = parseFloat(a.remaining_amount) >= 0 ? 'text-success' : 'text-danger';
    const fyText      = _fyLabel(a, fyId);
    const labelCell   = _labelCell(a);

    const summaryRow = `<tr class="${rowClass}" id="summary-${a.id}">
        <td style="width:32px;padding-left:8px;vertical-align:middle">
            <button class="btn btn-ghost-icon btn-sm p-0" style="width:22px;height:22px;line-height:1"
                    onclick="toggleAccordion(${a.id})" title="Expand sprint breakdown">
                <i class="bi bi-chevron-right" style="font-size:11px" id="toggle-icon-${a.id}"></i>
            </button>
        </td>
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
        <td class="text-end" style="white-space:nowrap">
            <button class="btn btn-ghost-icon btn-sm" title="Configure risk"
                    onclick="openRiskConfig(${a.id})">
                <i class="bi bi-gear${a.ignore_risk ? ' text-secondary' : ''}"></i>
            </button>
            <button class="btn btn-ghost-icon btn-sm" title="Sprint utilisation chart"
                    onclick="openChart(${a.id}, '${escHtml(a.project_name || '')}')">
                <i class="bi bi-bar-chart-line"></i>
            </button>
        </td>
    </tr>`;

    const detailRow = `<tr class="d-none" id="detail-${a.id}">
        <td colspan="13" style="padding:0">
            ${_renderDetailContent(a, fyId)}
        </td>
    </tr>`;

    return summaryRow + detailRow;
}

function _renderDetailContent(a, fyId) {
    const hasFySprints = _fySprintsList.length > 0 && _fySprintsFyId;

    let priorCost = 0;
    if (hasFySprints) {
        priorCost = (a.sprint_actuals || [])
            .filter(sa => String(sa.sprint_fy_id) !== _fySprintsFyId)
            .reduce((sum, sa) => sum + (parseFloat(sa.total_cost) || 0), 0);
    }

    let sprintItems = [];
    if (hasFySprints) {
        const costBySprint = {};
        (a.sprint_actuals || [])
            .filter(sa => String(sa.sprint_fy_id) === _fySprintsFyId)
            .forEach(sa => { costBySprint[sa.sprint] = parseFloat(sa.total_cost) || 0; });
        sprintItems = _fySprintsList.map(s => ({
            name: s.sprint_name,
            cost: s.id in costBySprint ? costBySprint[s.id] : null,
        }));
    } else {
        sprintItems = (a.sprint_actuals || [])
            .filter(sa => !fyId || String(sa.sprint_fy_id) === String(fyId))
            .sort((x, y) => x.sprint_number - y.sprint_number)
            .map(sa => ({ name: sa.sprint_name, cost: parseFloat(sa.total_cost) || 0 }));
    }

    if (!hasFySprints && !sprintItems.length) {
        return `<div class="px-4 py-3 text-secondary fst-italic" style="font-size:12px;background:rgba(0,0,0,.02);border-top:1px solid rgba(0,0,0,.06)">No sprint actuals yet.</div>`;
    }

    const priorTh = hasFySprints
        ? `<th class="text-end pe-3" style="min-width:90px;border-right:2px solid rgba(0,0,0,.12);font-weight:500;white-space:nowrap">Prior FYs</th>`
        : '';
    const priorTd = hasFySprints
        ? `<td class="text-end pe-3" style="border-right:2px solid rgba(0,0,0,.12)">
               ${priorCost > 0 ? `<strong>${_fmt(priorCost)}</strong>` : '<span class="text-secondary">—</span>'}
           </td>`
        : '';

    const sprintHeaders = sprintItems.map(s =>
        `<th class="text-end" style="min-width:90px;font-weight:500;white-space:nowrap"
              title="${escHtml(s.name)}">${escHtml(s.name)}</th>`
    ).join('');
    const sprintCells = sprintItems.map(s =>
        `<td class="text-end">
             ${s.cost !== null ? `<strong>${_fmt(s.cost)}</strong>` : '<span class="text-secondary">—</span>'}
         </td>`
    ).join('');

    return `<div style="overflow-x:auto;background:rgba(0,0,0,.02);border-top:1px solid rgba(0,0,0,.06)">
        <table class="table table-sm mb-0" style="min-width:max-content;font-size:12px">
            <thead>
                <tr class="text-secondary">
                    ${priorTh}${sprintHeaders}
                </tr>
            </thead>
            <tbody>
                <tr>
                    ${priorTd}${sprintCells}
                </tr>
            </tbody>
        </table>
    </div>`;
}

// ── Accordion toggle ──────────────────────────────────────────────────────────

window.toggleAccordion = function(actualsId) {
    const detailRow = document.getElementById(`detail-${actualsId}`);
    const icon      = document.getElementById(`toggle-icon-${actualsId}`);
    if (!detailRow) return;

    const isOpen = !detailRow.classList.contains('d-none');
    detailRow.classList.toggle('d-none');
    if (icon) {
        icon.classList.toggle('bi-chevron-right', isOpen);
        icon.classList.toggle('bi-chevron-down', !isOpen);
    }
};

// ── Risk Config Modal ─────────────────────────────────────────────────────────

window.openRiskConfig = function(actualsId) {
    const a = _allActuals.find(x => x.id === actualsId);
    if (!a) return;
    _riskConfigId = actualsId;

    document.getElementById('risk-config-project-name').textContent =
        `${a.programme_name || ''} › ${a.project_name || ''}`;
    document.getElementById('risk-config-current-badge').innerHTML =
        _riskBadge(a.risk || 'NEUTRAL') +
        (a.ignore_risk
            ? ' <span class="rp-badge rp-badge--muted ms-2"><i class="bi bi-eye-slash me-1"></i>Ignored</span>'
            : '');
    document.getElementById('risk-config-ignore-check').checked = Boolean(a.ignore_risk);
    document.getElementById('risk-config-ignore-prev-fy-check').checked = Boolean(a.ignore_previous_fy_cost);
    document.getElementById('risk-config-notes').value = a.ignore_risk_notes || '';

    bootstrap.Modal.getOrCreateInstance(document.getElementById('riskConfigModal')).show();
};

async function _saveRiskConfig() {
    if (!_riskConfigId) return;
    const ignore_risk              = document.getElementById('risk-config-ignore-check')?.checked ?? false;
    const ignore_previous_fy_cost  = document.getElementById('risk-config-ignore-prev-fy-check')?.checked ?? false;
    const ignore_risk_notes        = document.getElementById('risk-config-notes')?.value || '';

    const btn = document.getElementById('risk-config-save-btn');
    if (btn) btn.disabled = true;

    try {
        const updated = await apiFetch(API_URLS.project_actuals.patch(_riskConfigId).href, {
            method: 'PATCH',
            body: JSON.stringify({ ignore_risk, ignore_risk_notes, ignore_previous_fy_cost }),
        });
        const idx = _allActuals.findIndex(a => a.id === _riskConfigId);
        if (idx !== -1) _allActuals[idx] = updated;
        bootstrap.Modal.getOrCreateInstance(document.getElementById('riskConfigModal')).hide();
        _applyFilters();
        showFlash('Risk configuration saved.', 'success');
    } catch (_) {
        showFlash('Failed to save risk configuration.', 'danger');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ── Chart ─────────────────────────────────────────────────────────────────────

window.openChart = function(actualsId, projectName) {
    const a = _allActuals.find(x => x.id === actualsId);
    if (!a) return;

    let rows;
    if (_fySprintsList.length && _fySprintsFyId) {
        const costBySprint = {};
        (a.sprint_actuals || [])
            .filter(sa => String(sa.sprint_fy_id) === _fySprintsFyId)
            .forEach(sa => { costBySprint[sa.sprint] = parseFloat(sa.total_cost) || 0; });
        rows = _fySprintsList.map(s => ({
            sprint_name:   s.sprint_name,
            sprint_number: s.sprint_number,
            total_cost:    costBySprint[s.id] ?? 0,
        }));
    } else {
        const fyId = document.getElementById('filter-fy')?.value || null;
        rows = (a.sprint_actuals || [])
            .filter(sa => !fyId || String(sa.sprint_fy_id) === String(fyId))
            .sort((x, y) => x.sprint_number - y.sprint_number);
    }

    document.getElementById('chart-modal-title').textContent = `Sprint Utilisation — ${projectName}`;
    document.getElementById('chart-modal-risk-badge').innerHTML =
        _riskBadge(a.risk || 'NEUTRAL') +
        (a.ignore_risk
            ? ' <span class="rp-badge rp-badge--muted ms-1"><i class="bi bi-eye-slash me-1"></i>Risk Ignored</span>'
            : '');

    const estimateWC  = parseFloat(a.estimate_value_with_contingency) || 0;
    const estimateVal = parseFloat(a.estimate_value) || 0;

    const labels   = rows.map(r => r.sprint_name);
    const costData = rows.map(r => parseFloat(r.total_cost) || 0);

    // Cumulative cost for right axis
    const cumulativeData = [];
    let cumSum = 0;
    costData.forEach(v => { cumSum += v; cumulativeData.push(cumSum); });

    const _cumColor = v => {
        if (estimateWC > 0 && v > estimateWC) return 'rgba(239,68,68,1)';
        if (estimateVal > 0 && v > estimateVal) return 'rgba(245,158,11,1)';
        return 'rgba(34,197,94,1)';
    };

    const yMax  = Math.max(...costData, 1) * 1.2;
    const y1Max = Math.max(estimateWC > 0 ? estimateWC : 0, ...cumulativeData, 1) * 1.15;

    const datasets = [
        {
            type: 'bar',
            label: 'Sprint Cost',
            data: costData,
            backgroundColor: 'rgba(99,102,241,0.7)',
            borderColor: 'rgba(99,102,241,1)',
            borderWidth: 1,
            yAxisID: 'y',
            order: 3,
        },
        {
            type: 'line',
            label: 'Cumulative Cost',
            data: cumulativeData,
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: cumulativeData.map(_cumColor),
            fill: false,
            yAxisID: 'y1',
            order: 0,
            segment: {
                borderColor: ctx => _cumColor(ctx.p1.parsed.y),
            },
        },
    ];

    if (estimateVal > 0) {
        datasets.push({
            type: 'line',
            label: 'Estimate',
            data: Array(labels.length).fill(estimateVal),
            borderColor: '#d1d5db',
            borderWidth: 1.5,
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
            yAxisID: 'y1',
            order: 2,
        });
    }
    if (estimateWC > 0) {
        datasets.push({
            type: 'line',
            label: 'Est. + Contingency',
            data: Array(labels.length).fill(estimateWC),
            borderColor: '#6b7280',
            borderWidth: 1.5,
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
            yAxisID: 'y1',
            order: 1,
        });
    }

    if (_sprintChart) { _sprintChart.destroy(); _sprintChart = null; }

    bootstrap.Modal.getOrCreateInstance(document.getElementById('sprintChartModal')).show();

    requestAnimationFrame(() => {
        const ctx = document.getElementById('sprintChart')?.getContext('2d');
        if (!ctx) return;

        _sprintChart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${_fmt(ctx.parsed.y)}`,
                        },
                    },
                },
                scales: {
                    y: {
                        type: 'linear',
                        position: 'left',
                        min: 0,
                        max: yMax,
                        title: { display: true, text: 'Sprint Cost (£)' },
                        ticks: {
                            callback: v => {
                                if (v >= 1_000_000) return `£${(v / 1_000_000).toFixed(1)}M`;
                                if (v >= 1_000)     return `£${(v / 1_000).toFixed(0)}k`;
                                return `£${v}`;
                            },
                        },
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        min: 0,
                        max: y1Max,
                        title: { display: true, text: 'Cumulative Cost (£)' },
                        ticks: {
                            callback: v => {
                                if (v >= 1_000_000) return `£${(v / 1_000_000).toFixed(1)}M`;
                                if (v >= 1_000)     return `£${(v / 1_000).toFixed(0)}k`;
                                return `£${v}`;
                            },
                        },
                        grid: { drawOnChartArea: false },
                    },
                    x: { ticks: { maxRotation: 45, minRotation: 0 } },
                },
            },
        });
    });
};

// ── Utilities ─────────────────────────────────────────────────────────────────

function _labelCell(a) {
    const labels = a.all_labels || [];
    if (!labels.length) return '<td class="text-secondary">—</td>';

    const primary     = labels.find(l => l.is_primary) || labels[0];
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
    // When no FY filter, show FYs from actual sprint data
    const fys = [...new Set((a.sprint_actuals || []).map(sa => sa.sprint_fy_short).filter(Boolean))];
    return fys.join(', ') || '—';
}

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
