'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch } from '../main.js';

const SPRINT_ID = window.SPRINT_ID;

// detail state
let _detailData = [];
let _detailStories = [];
let _detailView = 'engineer';

document.addEventListener('DOMContentLoaded', () => {
    _loadTab('FORECAST');
    _loadTab('ACTUAL');

    // View pill handler
    document.getElementById('detail-view-pills').addEventListener('click', e => {
        const btn = e.target.closest('button[data-view]');
        if (!btn) return;
        _detailView = btn.dataset.view;
        document.querySelectorAll('#detail-view-pills button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _renderDetailTable();
    });

    document.getElementById('detail-close-btn').addEventListener('click', () => {
        document.getElementById('detail-drawer').classList.add('d-none');
        document.querySelectorAll('.expand-btn[data-active="true"]').forEach(b => {
            b.dataset.active = 'false';
            b.innerHTML = '<i class="bi bi-chevron-down"></i>';
        });
    });
});

async function _loadTab(type) {
    const prefix = type === 'FORECAST' ? 'forecast' : 'actual';
    try {
        const data = await apiFetch(`${API_URLS.recharges.summary(SPRINT_ID, type).href}`);
        _showLoading(prefix, false);
        _updateEmailBadge(prefix, data.email_status);
        if (!data.exists) {
            document.getElementById(`${prefix}-empty`).classList.remove('d-none');
            return;
        }
        document.getElementById(`${prefix}-content`).classList.remove('d-none');
        _renderSummaryCards(prefix, data);
        _renderFTCards(prefix, data.finance_type_breakdown || []);
        _loadRechargeTable(prefix, type);
        if (data.combined && data.combined.has_forecast && data.combined.has_actual) {
            _renderCombinedSummary(data.combined, data.finance_type_breakdown, type);
        }
    } catch (e) {
        _showLoading(prefix, false);
        document.getElementById(`${prefix}-empty`).classList.remove('d-none');
    }
}

function _updateEmailBadge(prefix, emailStatus) {
    const badge = document.getElementById(`${prefix}-email-badge`);
    if (!badge || !emailStatus) return;
    const sent = emailStatus.sent_count || 0;
    const errors = emailStatus.error_count || 0;
    if (errors > 0) {
        badge.className = 'ms-1 rp-tab-badge rp-tab-badge--error';
        badge.title = `${errors} email(s) failed`;
        badge.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i>`;
    } else if (sent > 0) {
        badge.className = 'ms-1 rp-tab-badge rp-tab-badge--sent';
        badge.title = `${sent} email(s) sent`;
        badge.innerHTML = `<i class="bi bi-check-circle-fill"></i>`;
    } else {
        badge.className = 'ms-1 d-none';
        return;
    }
    badge.classList.remove('d-none');
}

async function _loadRechargeTable(prefix, type) {
    try {
        const url = `${API_URLS.recharges.list.href}?sprint_id=${SPRINT_ID}&type=${type}`;
        const rows = await apiFetch(url);
        _renderRechargeTable(prefix, rows || []);
    } catch (_) {}
}

function _renderSummaryCards(prefix, data) {
    const container = document.getElementById(`${prefix}-summary-cards`);
    const fmtCost = v => `£${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    container.innerHTML = `
        <div class="col-12 col-sm-6 col-md-4">
            <div class="rp-summary-card">
                <div class="rp-summary-card-label">Total Cost</div>
                <div class="rp-summary-card-value">${fmtCost(data.total_cost)}</div>
            </div>
        </div>
        <div class="col-12 col-sm-6 col-md-4">
            <div class="rp-summary-card">
                <div class="rp-summary-card-label">Total Days</div>
                <div class="rp-summary-card-value">${parseFloat(data.total_days).toFixed(2)}</div>
            </div>
        </div>
    `;
}

function _renderFTCards(prefix, breakdown) {
    const container = document.getElementById(`${prefix}-ft-cards`);
    const fmtCost = v => `£${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    container.innerHTML = breakdown.map(ft => `
        <div class="col-auto">
            <div class="rp-ft-chip">
                <div class="rp-ft-chip-code">${_esc(ft.code)}</div>
                <div class="rp-ft-chip-value">${fmtCost(ft.cost)}</div>
                <div class="rp-ft-chip-code" style="font-weight:400">${_esc(ft.name)}</div>
            </div>
        </div>
    `).join('');
}

const _ftData = { combined: null, FORECAST: null, ACTUAL: null };

function _renderCombinedSummary(combined, ftBreakdown, currentType) {
    _ftData.combined = combined;
    _ftData[currentType] = ftBreakdown;
    if (!_ftData.FORECAST || !_ftData.ACTUAL) return;

    const container = document.getElementById('combined-summary');
    const cards = document.getElementById('combined-cards');
    const fmtCost = v => `£${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const varianceVal = parseFloat(_ftData.combined.variance);
    const varianceCls = varianceVal < 0 ? 'text-danger' : varianceVal > 0 ? 'text-success' : '';
    cards.innerHTML = `
        <div class="col-12 col-sm-6 col-md-4">
            <div class="rp-summary-card">
                <div class="rp-summary-card-label">Forecast Total</div>
                <div class="rp-summary-card-value">${fmtCost(_ftData.combined.forecast_total)}</div>
            </div>
        </div>
        <div class="col-12 col-sm-6 col-md-4">
            <div class="rp-summary-card">
                <div class="rp-summary-card-label">Actual Total</div>
                <div class="rp-summary-card-value">${fmtCost(_ftData.combined.actual_total)}</div>
            </div>
        </div>
        <div class="col-12 col-sm-6 col-md-4">
            <div class="rp-summary-card">
                <div class="rp-summary-card-label">Variance (Actual − Forecast)</div>
                <div class="rp-summary-card-value ${varianceCls}">${fmtCost(_ftData.combined.variance)}</div>
            </div>
        </div>
    `;

    // Build FT breakdown: merge forecast + actual keyed by ft code
    const ftMap = {};
    (_ftData.FORECAST || []).forEach(ft => {
        ftMap[ft.code] = { code: ft.code, name: ft.name, forecast: parseFloat(ft.cost), actual: 0 };
    });
    (_ftData.ACTUAL || []).forEach(ft => {
        if (ftMap[ft.code]) {
            ftMap[ft.code].actual = parseFloat(ft.cost);
        } else {
            ftMap[ft.code] = { code: ft.code, name: ft.name, forecast: 0, actual: parseFloat(ft.cost) };
        }
    });
    const tbody = document.getElementById('ft-comparison-tbody');
    tbody.innerHTML = Object.values(ftMap).map(ft => {
        const variance = ft.actual - ft.forecast;
        const vCls = variance < 0 ? 'text-danger' : variance > 0 ? 'text-success' : '';
        return `<tr>
            <td>${_esc(ft.code)}</td>
            <td class="text-secondary small">${_esc(ft.name)}</td>
            <td class="text-end font-mono">${fmtCost(ft.forecast)}</td>
            <td class="text-end font-mono">${fmtCost(ft.actual)}</td>
            <td class="text-end font-mono ${vCls}">${fmtCost(variance)}</td>
        </tr>`;
    }).join('');

    container.classList.remove('d-none');
}

function _renderRechargeTable(prefix, rows) {
    const count = document.getElementById(`${prefix}-count`);
    const tbody = document.getElementById(`${prefix}-tbody`);
    count.textContent = `${rows.length} record(s)`;

    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-secondary py-3">No recharge records found.</td></tr>`;
        return;
    }

    tbody.innerHTML = rows.map(r => {
        const finChips = _renderEmailChips(r.finance_contact_emails || []);
        const projChips = _renderEmailChips(r.project_contact_emails || []);
        return `
        <tr data-recharge-id="${r.id}" data-project-id="${r.project || ''}">
            <td>${_esc(r.programme_name || '—')}</td>
            <td>${_esc(r.project_name || '—')}</td>
            <td class="text-end font-mono">${parseFloat(r.total_days).toFixed(2)}</td>
            <td class="text-end font-mono">£${parseFloat(r.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
            <td>${finChips || '<span class="text-muted">—</span>'}</td>
            <td>${projChips || '<span class="text-muted">—</span>'}</td>
            <td>
                <button class="expand-btn" data-active="false"
                    data-recharge-id="${r.id}"
                    data-project-id="${r.project || ''}"
                    data-project="${_esc(r.project_name || '—')}"
                    data-programme="${_esc(r.programme_name || '—')}"
                    data-type="${prefix.toUpperCase()}"
                    data-stories='${JSON.stringify(r.stories || []).replace(/'/g, "&#39;")}'
                    title="Show detail">
                    <i class="bi bi-chevron-down"></i>
                </button>
            </td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('.expand-btn').forEach(btn => {
        btn.addEventListener('click', () => _toggleDetail(btn));
    });
}

function _renderEmailChips(emails) {
    return emails.map(e => `<span class="rp-email-chip"><i class="bi bi-envelope" style="font-size:10px"></i>${_esc(e)}</span>`).join('');
}

async function _toggleDetail(btn) {
    const rechargeId = btn.dataset.rechargeId;
    const isOpen = btn.dataset.active === 'true';

    // Close any previously open row
    document.querySelectorAll('.expand-btn[data-active="true"]').forEach(b => {
        if (b !== btn) {
            b.dataset.active = 'false';
            b.innerHTML = '<i class="bi bi-chevron-down"></i>';
        }
    });

    if (isOpen) {
        btn.dataset.active = 'false';
        btn.innerHTML = '<i class="bi bi-chevron-down"></i>';
        document.getElementById('detail-drawer').classList.add('d-none');
        return;
    }

    btn.dataset.active = 'true';
    btn.innerHTML = '<i class="bi bi-chevron-up"></i>';

    const drawer = document.getElementById('detail-drawer');
    drawer.classList.remove('d-none');
    document.getElementById('detail-drawer-title').textContent = `${btn.dataset.project}`;
    document.getElementById('detail-drawer-subtitle').textContent = btn.dataset.programme;
    document.getElementById('detail-loading').classList.remove('d-none');
    document.getElementById('detail-table-wrap').classList.add('d-none');

    // Restore default view
    _detailView = 'engineer';
    document.querySelectorAll('#detail-view-pills button').forEach(b => b.classList.remove('active'));
    document.querySelector('#detail-view-pills button[data-view="engineer"]').classList.add('active');

    // Load stories from already-fetched recharge data
    try {
        _detailStories = JSON.parse(btn.dataset.stories || '[]');
    } catch (_) { _detailStories = []; }
    _renderStories();

    // Load engineer detail from API
    const type = btn.dataset.type;
    const projectId = btn.dataset.projectId || '';

    try {
        const url = `${API_URLS.recharge_details.list.href}?sprint_id=${SPRINT_ID}&type=${type}${projectId ? `&project_id=${projectId}` : ''}`;
        const details = await apiFetch(url);
        _detailData = details || [];
        document.getElementById('detail-loading').classList.add('d-none');
        document.getElementById('detail-table-wrap').classList.remove('d-none');
        _renderDetailTable();
    } catch (_) {
        document.getElementById('detail-loading').classList.add('d-none');
        document.getElementById('detail-table-wrap').classList.remove('d-none');
        _detailData = [];
        _renderDetailTable();
    }
}

function _renderDetailTable() {
    const thead = document.getElementById('detail-thead');
    const tbody = document.getElementById('detail-tbody');
    const fmtCost = v => `£${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    if (!_detailData.length) {
        thead.innerHTML = '';
        tbody.innerHTML = `<tr><td class="text-center text-secondary py-2" colspan="5">No detail records found.</td></tr>`;
        return;
    }

    if (_detailView === 'engineer') {
        thead.innerHTML = `<tr><th>Team</th><th>Engineer</th><th>Label</th><th class="text-end">Days</th><th class="text-end">Cost</th></tr>`;
        tbody.innerHTML = _detailData.map(d => `<tr>
            <td>${_esc(d.team_name || '—')}</td>
            <td>${_esc(d.assignee_name || '—')}</td>
            <td>${_esc(d.label_name || '—')}</td>
            <td class="text-end font-mono">${parseFloat(d.total_days).toFixed(2)}</td>
            <td class="text-end font-mono">${fmtCost(d.total_cost)}</td>
        </tr>`).join('');
    } else if (_detailView === 'team') {
        const grouped = _groupBy(_detailData, d => d.team_name || '—');
        thead.innerHTML = `<tr><th>Team</th><th class="text-end">Days</th><th class="text-end">Cost</th></tr>`;
        tbody.innerHTML = Object.entries(grouped).map(([team, rows]) => {
            const days = rows.reduce((s, r) => s + parseFloat(r.total_days), 0);
            const cost = rows.reduce((s, r) => s + parseFloat(r.total_cost), 0);
            return `<tr>
                <td>${_esc(team)}</td>
                <td class="text-end font-mono">${days.toFixed(2)}</td>
                <td class="text-end font-mono">${fmtCost(cost)}</td>
            </tr>`;
        }).join('');
    } else {
        const grouped = _groupBy(_detailData, d => d.label_name || '—');
        thead.innerHTML = `<tr><th>Label</th><th class="text-end">Days</th><th class="text-end">Cost</th></tr>`;
        tbody.innerHTML = Object.entries(grouped).map(([label, rows]) => {
            const days = rows.reduce((s, r) => s + parseFloat(r.total_days), 0);
            const cost = rows.reduce((s, r) => s + parseFloat(r.total_cost), 0);
            return `<tr>
                <td>${_esc(label)}</td>
                <td class="text-end font-mono">${days.toFixed(2)}</td>
                <td class="text-end font-mono">${fmtCost(cost)}</td>
            </tr>`;
        }).join('');
    }
}

function _renderStories() {
    const tbody = document.getElementById('detail-stories-tbody');
    const section = document.getElementById('detail-stories-section');
    if (!_detailStories.length) {
        section.classList.add('d-none');
        return;
    }
    section.classList.remove('d-none');
    tbody.innerHTML = _detailStories.map(s => `<tr>
        <td><code>${_esc(s.jira_id || '—')}</code></td>
        <td>${_esc(s.title || '—')}</td>
        <td class="text-end font-mono">${parseFloat(s.total_days).toFixed(2)}</td>
    </tr>`).join('');
}

function _groupBy(arr, fn) {
    return arr.reduce((acc, item) => {
        const key = fn(item);
        if (!acc[key]) acc[key] = [];
        acc[key].push(item);
        return acc;
    }, {});
}

function _showLoading(prefix, show) {
    document.getElementById(`${prefix}-loading`).classList.toggle('d-none', !show);
}

function _esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
