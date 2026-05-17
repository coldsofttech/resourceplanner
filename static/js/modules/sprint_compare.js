'use strict';

import { apiFetch, setPageTitle, escHtml } from './../main.js';
import { API_URLS } from './../urls.js';

const sprintId   = window.SPRINT_ID;
const sprintName = window.SPRINT_NAME;

let compareData     = null;
let activeDimension = 'all';

const DIMENSIONS = [
    { key: 'all',      label: 'All',            icon: 'bi-list-ul' },
    { key: 'label',    label: 'By Label',        icon: 'bi-tag' },
    { key: 'project',  label: 'By Project',      icon: 'bi-folder' },
    { key: 'team',     label: 'By Team',         icon: 'bi-people' },
    { key: 'engineer', label: 'By Engineer',     icon: 'bi-person' },
    { key: 'mapping',  label: 'By Finance Type', icon: 'bi-currency-exchange' },
];

// Number of non-data columns before Forecast/Actual/Delta per dimension
const DIM_COLSPANS = { all: 6, team: 2, engineer: 3, label: 3, project: 3, mapping: 2 };

document.addEventListener('DOMContentLoaded', () => {
    setPageTitle(`Compare — ${sprintName}`);
    loadCompareData();
});

async function loadCompareData() {
    try {
        const { method, href } = API_URLS.sprint_compare.data(sprintId);
        compareData = await apiFetch(href, { method });
    } catch (_err) {
        showLoadingError();
        return;
    }

    document.getElementById('compare-loading').classList.add('d-none');

    if (!compareData.can_compare) {
        renderNotReady(compareData);
        return;
    }

    renderSummaryCards(compareData.summary);
    renderDimensionTabs();
    renderTable();
    document.getElementById('compare-content').classList.remove('d-none');
}

function showLoadingError() {
    document.getElementById('compare-loading').classList.add('d-none');
    const nr = document.getElementById('compare-not-ready');
    nr.classList.remove('d-none');
    nr.innerHTML = `
        <div class="rp-card">
            <div class="text-center py-4 text-danger">
                <i class="bi bi-exclamation-triangle" style="font-size:2rem"></i>
                <p class="mt-3 mb-0">Failed to load comparison data. Please refresh the page.</p>
            </div>
        </div>`;
}

function renderNotReady(data) {
    const nr = document.getElementById('compare-not-ready');
    nr.classList.remove('d-none');

    const fBadge = document.getElementById('forecast-status-badge');
    const aBadge = document.getElementById('actual-status-badge');
    if (fBadge) {
        fBadge.textContent = data.forecast_complete ? 'Complete' : 'Pending';
        fBadge.className   = `rp-badge ${data.forecast_complete ? 'rp-badge--success' : 'rp-badge--muted'}`;
    }
    if (aBadge) {
        aBadge.textContent = data.actual_complete ? 'Complete' : 'Pending';
        aBadge.className   = `rp-badge ${data.actual_complete ? 'rp-badge--success' : 'rp-badge--muted'}`;
    }
}

// ── Summary Cards ──────────────────────────────────────────────────────────

function renderSummaryCards(summary) {
    const cards = document.getElementById('summary-cards');
    if (!cards) return;

    const deltaSign  = summary.delta > 0 ? '+' : '';
    const deltaClass = summary.delta > 0 ? 'text-success' : summary.delta < 0 ? 'text-danger' : 'text-secondary';
    const deltaIcon  = summary.delta > 0 ? 'bi-arrow-up-short' : summary.delta < 0 ? 'bi-arrow-down-short' : 'bi-dash';

    const changeChips = [
        summary.added    ? `<span class="rp-badge rp-badge--success">+${summary.added} added</span>`    : '',
        summary.removed  ? `<span class="rp-badge rp-badge--danger">−${summary.removed} removed</span>`  : '',
        summary.changed  ? `<span class="rp-badge rp-badge--warning">~${summary.changed} changed</span>` : '',
        summary.unchanged ? `<span class="rp-badge rp-badge--muted">=${summary.unchanged} same</span>`   : '',
    ].filter(Boolean).join('');

    cards.innerHTML = `
        <div class="col-sm-6 col-xl-3">
            <div class="rp-card text-center py-3">
                <p class="text-secondary small mb-1">Forecast Total</p>
                <div class="fw-700 fs-4 text-info">${summary.forecast_total_days}</div>
                <div class="text-secondary small">days</div>
            </div>
        </div>
        <div class="col-sm-6 col-xl-3">
            <div class="rp-card text-center py-3">
                <p class="text-secondary small mb-1">Actual Total</p>
                <div class="fw-700 fs-4 text-warning">${summary.actual_total_days}</div>
                <div class="text-secondary small">days</div>
            </div>
        </div>
        <div class="col-sm-6 col-xl-3">
            <div class="rp-card text-center py-3">
                <p class="text-secondary small mb-1">Variance (Actual − Forecast)</p>
                <div class="fw-700 fs-4 ${deltaClass}">
                    <i class="bi ${deltaIcon}"></i>${deltaSign}${summary.delta}
                </div>
                <div class="text-secondary small">days</div>
            </div>
        </div>
        <div class="col-sm-6 col-xl-3">
            <div class="rp-card text-center py-3">
                <p class="text-secondary small mb-1">Changes</p>
                <div class="d-flex justify-content-center gap-1 flex-wrap mt-2">
                    ${changeChips || '<span class="text-secondary small">No changes</span>'}
                </div>
            </div>
        </div>
    `;
}

// ── Dimension Tabs ─────────────────────────────────────────────────────────

function renderDimensionTabs() {
    const container = document.getElementById('dimension-tabs');
    if (!container) return;

    container.innerHTML = DIMENSIONS.map(dim => `
        <button
            class="btn btn-sm ${activeDimension === dim.key ? 'btn-primary' : 'btn-outline-secondary'}"
            onclick="window._cmpSetDim('${dim.key}')">
            <i class="bi ${dim.icon} me-1"></i>${escHtml(dim.label)}
        </button>
    `).join('');
}

window._cmpSetDim = function (dim) {
    activeDimension = dim;
    renderDimensionTabs();
    renderTable();
};

// ── Row Aggregation ────────────────────────────────────────────────────────

function aggregateRows(rows, dimension) {
    if (dimension === 'all') return rows;

    const keyFns = {
        team:     r => String(r.team_id    ?? `__${r.team}`),
        engineer: r => String(r.assignee_id ?? `__${r.assignee}`),
        label:    r => String(r.label_id   ?? `__${r.label}`),
        project:  r => String(r.project_id  ?? `__${r.project}`),
        mapping:  r => String(r.mapping_id  ?? `__${r.mapping}`),
    };
    const metaFns = {
        team:     r => ({ team: r.team }),
        engineer: r => ({ assignee: r.assignee, team: r.team }),
        label:    r => ({ label: r.label, project: r.project }),
        project:  r => ({ project: r.project, programme: r.programme }),
        mapping:  r => ({ mapping: r.mapping, mapping_name: r.mapping_name }),
    };

    const keyFn  = keyFns[dimension];
    const metaFn = metaFns[dimension];

    const groups = {};
    const meta   = {};

    for (const row of rows) {
        const k = keyFn(row);
        if (!groups[k]) {
            groups[k] = { forecast_days: 0, actual_days: 0 };
            meta[k]   = metaFn(row);
        }
        groups[k].forecast_days += row.forecast_days;
        groups[k].actual_days   += row.actual_days;
    }

    return Object.entries(groups).map(([k, totals]) => {
        const f     = Math.round(totals.forecast_days * 100) / 100;
        const a     = Math.round(totals.actual_days   * 100) / 100;
        const delta = Math.round((a - f) * 100) / 100;
        let diffStatus;
        if (f === 0 && a > 0)       diffStatus = 'added';
        else if (f > 0 && a === 0)  diffStatus = 'removed';
        else if (Math.abs(delta) > 0.001) diffStatus = 'changed';
        else                              diffStatus = 'unchanged';
        return { ...meta[k], forecast_days: f, actual_days: a, delta, status: diffStatus };
    }).sort((a, b) => {
        const order = { removed: 0, changed: 1, added: 2, unchanged: 3 };
        return (order[a.status] ?? 4) - (order[b.status] ?? 4);
    });
}

// ── Table Rendering ────────────────────────────────────────────────────────

function statusCell(s) {
    const map = {
        added:     ['rp-badge--success', '+', 'Added in Actuals'],
        removed:   ['rp-badge--danger',  '−', 'Not in Actuals'],
        changed:   ['rp-badge--warning', '~', 'Value changed'],
        unchanged: ['rp-badge--muted',   '=', 'Unchanged'],
    };
    const [cls, sym, title] = map[s] || ['rp-badge--muted', '?', ''];
    return `<span class="rp-badge ${cls}" title="${escHtml(title)}" style="font-family:var(--font-mono);min-width:22px;text-align:center">${sym}</span>`;
}

function rowClass(s) {
    return { added: 'table-success', removed: 'table-danger', changed: 'table-warning', unchanged: '' }[s] || '';
}

function deltaCell(delta) {
    if (Math.abs(delta) < 0.001) return `<span class="text-secondary">0</span>`;
    const sign = delta > 0 ? '+' : '';
    const cls  = delta > 0 ? 'text-success' : 'text-danger';
    return `<span class="${cls} fw-500">${sign}${delta}</span>`;
}

const TABLE_CONFIGS = {
    all: {
        thead: `<tr>
            <th style="width:36px"></th>
            <th>Team</th><th>Engineer</th><th>Label</th><th>Project</th><th>Finance Type</th>
            <th class="text-end">Forecast</th><th class="text-end">Actual</th><th class="text-end">Delta</th>
        </tr>`,
        row: r => `<tr class="${rowClass(r.status)}">
            <td>${statusCell(r.status)}</td>
            <td class="text-secondary small">${escHtml(r.team || '—')}</td>
            <td class="fw-500">${escHtml(r.assignee || '—')}</td>
            <td>${escHtml(r.label || '—')}</td>
            <td class="text-secondary small">${escHtml(r.project || '—')}</td>
            <td><span class="rp-code small">${escHtml(r.mapping || '—')}</span></td>
            <td class="text-end text-info fw-500">${r.forecast_days}</td>
            <td class="text-end text-warning fw-500">${r.actual_days}</td>
            <td class="text-end">${deltaCell(r.delta)}</td>
        </tr>`,
    },
    team: {
        thead: `<tr>
            <th style="width:36px"></th><th>Team</th>
            <th class="text-end">Forecast</th><th class="text-end">Actual</th><th class="text-end">Delta</th>
        </tr>`,
        row: r => `<tr class="${rowClass(r.status)}">
            <td>${statusCell(r.status)}</td>
            <td class="fw-500">${escHtml(r.team || '—')}</td>
            <td class="text-end text-info fw-500">${r.forecast_days}</td>
            <td class="text-end text-warning fw-500">${r.actual_days}</td>
            <td class="text-end">${deltaCell(r.delta)}</td>
        </tr>`,
    },
    engineer: {
        thead: `<tr>
            <th style="width:36px"></th><th>Engineer</th><th>Team</th>
            <th class="text-end">Forecast</th><th class="text-end">Actual</th><th class="text-end">Delta</th>
        </tr>`,
        row: r => `<tr class="${rowClass(r.status)}">
            <td>${statusCell(r.status)}</td>
            <td class="fw-500">${escHtml(r.assignee || '—')}</td>
            <td class="text-secondary small">${escHtml(r.team || '—')}</td>
            <td class="text-end text-info fw-500">${r.forecast_days}</td>
            <td class="text-end text-warning fw-500">${r.actual_days}</td>
            <td class="text-end">${deltaCell(r.delta)}</td>
        </tr>`,
    },
    label: {
        thead: `<tr>
            <th style="width:36px"></th><th>Label</th><th>Project</th>
            <th class="text-end">Forecast</th><th class="text-end">Actual</th><th class="text-end">Delta</th>
        </tr>`,
        row: r => `<tr class="${rowClass(r.status)}">
            <td>${statusCell(r.status)}</td>
            <td class="fw-500">${escHtml(r.label || '—')}</td>
            <td class="text-secondary small">${escHtml(r.project || '—')}</td>
            <td class="text-end text-info fw-500">${r.forecast_days}</td>
            <td class="text-end text-warning fw-500">${r.actual_days}</td>
            <td class="text-end">${deltaCell(r.delta)}</td>
        </tr>`,
    },
    project: {
        thead: `<tr>
            <th style="width:36px"></th><th>Project</th><th>Programme</th>
            <th class="text-end">Forecast</th><th class="text-end">Actual</th><th class="text-end">Delta</th>
        </tr>`,
        row: r => `<tr class="${rowClass(r.status)}">
            <td>${statusCell(r.status)}</td>
            <td class="fw-500">${escHtml(r.project || '—')}</td>
            <td class="text-secondary small">${escHtml(r.programme || '—')}</td>
            <td class="text-end text-info fw-500">${r.forecast_days}</td>
            <td class="text-end text-warning fw-500">${r.actual_days}</td>
            <td class="text-end">${deltaCell(r.delta)}</td>
        </tr>`,
    },
    mapping: {
        thead: `<tr>
            <th style="width:36px"></th><th>Finance Type</th>
            <th class="text-end">Forecast</th><th class="text-end">Actual</th><th class="text-end">Delta</th>
        </tr>`,
        row: r => `<tr class="${rowClass(r.status)}">
            <td>${statusCell(r.status)}</td>
            <td>
                <span class="rp-code fw-500">${escHtml(r.mapping || '—')}</span>
                ${r.mapping_name && r.mapping_name !== r.mapping ? `<span class="text-secondary small ms-1">${escHtml(r.mapping_name)}</span>` : ''}
            </td>
            <td class="text-end text-info fw-500">${r.forecast_days}</td>
            <td class="text-end text-warning fw-500">${r.actual_days}</td>
            <td class="text-end">${deltaCell(r.delta)}</td>
        </tr>`,
    },
};

function renderTable() {
    const wrap = document.getElementById('compare-table-wrap');
    if (!wrap || !compareData) return;

    const allRows = compareData.rows || [];
    const rows    = aggregateRows(allRows, activeDimension);
    const cfg     = TABLE_CONFIGS[activeDimension] || TABLE_CONFIGS.all;

    if (!rows.length) {
        wrap.innerHTML = '<p class="text-secondary text-center py-5">No data to compare.</p>';
        return;
    }

    const totalForecast = Math.round(rows.reduce((s, r) => s + r.forecast_days, 0) * 100) / 100;
    const totalActual   = Math.round(rows.reduce((s, r) => s + r.actual_days,   0) * 100) / 100;
    const totalDelta    = Math.round((totalActual - totalForecast) * 100) / 100;
    const colspan       = DIM_COLSPANS[activeDimension] ?? 2;

    const legend = `
        <div class="d-flex gap-3 px-1 pt-3 flex-wrap" style="font-size:12px;color:var(--color-text-2)">
            <span class="d-flex align-items-center gap-1">${statusCell('added')} Added in Actuals</span>
            <span class="d-flex align-items-center gap-1">${statusCell('removed')} Not in Actuals</span>
            <span class="d-flex align-items-center gap-1">${statusCell('changed')} Value changed</span>
            <span class="d-flex align-items-center gap-1">${statusCell('unchanged')} Unchanged</span>
        </div>`;

    wrap.innerHTML = `
        <div class="rp-table-wrap">
            <table class="table rp-table mb-0">
                <thead>${cfg.thead}</thead>
                <tbody>${rows.map(cfg.row).join('')}</tbody>
                <tfoot>
                    <tr class="fw-600">
                        <td colspan="${colspan}" class="text-secondary small py-2">Total</td>
                        <td class="text-end text-info py-2">${totalForecast}</td>
                        <td class="text-end text-warning py-2">${totalActual}</td>
                        <td class="text-end py-2">${deltaCell(totalDelta)}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        ${legend}
    `;
}
