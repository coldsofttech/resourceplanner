'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch, escHtml, setPageTitle } from '../main.js';

let _allActuals = [];

document.addEventListener('DOMContentLoaded', () => {
    setPageTitle('Project Actuals');
    _loadDropdowns();
    _loadActuals();

    ['filter-programme', 'filter-project'].forEach(id => {
        document.getElementById(id)?.addEventListener('change', _applyFilters);
    });
});

async function _loadDropdowns() {
    try {
        const [programmes, projects] = await Promise.all([
            apiFetch(API_URLS.recharges.programme_options.href),
            apiFetch(API_URLS.recharges.project_options.href),
        ]);

        const progSel = document.getElementById('filter-programme');
        (programmes || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            progSel.appendChild(opt);
        });

        const projSel = document.getElementById('filter-project');
        (projects || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            projSel.appendChild(opt);
        });
    } catch (_) { /* non-critical */ }
}

async function _loadActuals() {
    const loadingEl     = document.getElementById('actuals-loading');
    const tableWrapEl   = document.getElementById('actuals-table-wrap');
    const emptyEl       = document.getElementById('actuals-empty');

    loadingEl?.classList.remove('d-none');
    tableWrapEl?.classList.add('d-none');
    emptyEl?.classList.add('d-none');

    try {
        _allActuals = await apiFetch(API_URLS.project_actuals.list.href);
        _renderActuals(_allActuals);
    } catch (_) {
        loadingEl.innerHTML = '<span class="text-danger">Failed to load project actuals.</span>';
    }
}

function _applyFilters() {
    const progId = document.getElementById('filter-programme')?.value;
    const projId = document.getElementById('filter-project')?.value;

    let filtered = _allActuals;
    if (progId) filtered = filtered.filter(a => String(a.programme) === progId);
    if (projId) filtered = filtered.filter(a => String(a.project) === projId);
    _renderActuals(filtered);
}

function _renderActuals(actuals) {
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

    tableWrapEl?.classList.remove('d-none');
    emptyEl?.classList.add('d-none');
    if (countEl) countEl.textContent = `${actuals.length} project${actuals.length !== 1 ? 's' : ''}`;

    tbody.innerHTML = actuals.map(a => {
        const risk       = a.risk || 'NEUTRAL';
        const riskBadge  = _riskBadge(risk);
        const collab     = (a.collaborator_names || []).join(', ') || '—';
        const estimate   = _fmt(a.estimate_value);
        const estimateWC = _fmt(a.estimate_value_with_contingency);
        const total      = _fmt(a.total_cost_till_date);
        const remaining  = _fmt(a.remaining_amount);
        const remainClass = parseFloat(a.remaining_amount) >= 0 ? 'text-success' : 'text-danger';

        return `<tr>
            <td>${escHtml(a.programme_name || '—')}</td>
            <td class="fw-500">${escHtml(a.project_name || '—')}</td>
            <td class="text-secondary">${escHtml(a.label_name || '—')}</td>
            <td class="rp-code text-secondary" style="font-size:12px">${escHtml(a.code || '—')}</td>
            <td>${escHtml(a.assigned_team_name || '—')}</td>
            <td class="text-secondary" style="font-size:12px">${escHtml(collab)}</td>
            <td class="text-end">${estimate}</td>
            <td class="text-end">${estimateWC}</td>
            <td class="text-end fw-600">${total}</td>
            <td class="text-end ${remainClass}">${remaining}</td>
            <td class="text-center">${riskBadge}</td>
            <td>
                <button class="btn btn-ghost-icon btn-sm" title="Per-sprint breakdown"
                        onclick="openBreakdown(${a.id}, '${escHtml(a.project_name || '')}')">
                    <i class="bi bi-bar-chart-line"></i>
                </button>
            </td>
        </tr>`;
    }).join('');
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

window.openBreakdown = function(actualsId, projectName) {
    const titleEl = document.getElementById('breakdown-modal-title');
    const tbody   = document.getElementById('breakdown-tbody');
    if (!titleEl || !tbody) return;

    titleEl.textContent = `Per-Sprint Actuals — ${projectName}`;

    const actuals = _allActuals.find(a => a.id === actualsId);
    const rows = actuals?.sprint_actuals || [];

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-secondary py-3">No sprint actuals recorded.</td></tr>';
    } else {
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td class="rp-code">${escHtml(r.sprint_name || String(r.sprint))}</td>
                <td class="text-end">${r.total_days}</td>
                <td class="text-end">${_fmt(r.total_cost)}</td>
            </tr>
        `).join('');
    }

    bootstrap.Modal.getOrCreateInstance(document.getElementById('sprintBreakdownModal')).show();
};
