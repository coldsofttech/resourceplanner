'use strict';
import { API_URLS } from './../urls.js';
import { apiFetch, escHtml, formatDateTime, getPkFromUrl } from './../main.js';

const planPk    = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

let _page       = 1;
let _eventType  = '';
let _dateFrom   = '';
let _dateTo     = '';

// ── Event type badge labels ───────────────────────────────────────────────────
const EVENT_LABELS = {
    ENGINE_RUN:           'Engine Run',
    ALLOCATION_OVERRIDE:  'Alloc Override',
    PLACEHOLDER_OVERRIDE: 'Placeholder Override',
    CONFLICT_RESOLVED:    'Conflict Resolved',
    STATUS_CHANGED:       'Status Changed',
    PLAN_CLONED:          'Plan Cloned',
    CONFIG_CHANGED:       'Config Changed',
};

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    _loadVersion();
    _loadPage();
    _bindFilters();
});

async function _loadVersion() {
    try {
        const data = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
        document.getElementById('audit-plan-name').textContent    = data.plan_name ?? `Plan #${planPk}`;
        document.getElementById('audit-version-badge').textContent = `v${data.version}`;
        document.getElementById('audit-breadcrumb').textContent   = data.plan_name ?? '';
    } catch (_) {}
}

function _bindFilters() {
    document.querySelectorAll('.audit-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.audit-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _eventType = btn.dataset.eventType || '';
            _page = 1;
            _loadPage();
        });
    });
    document.getElementById('audit-date-from').addEventListener('change', e => {
        _dateFrom = e.target.value;
        _page = 1;
        _loadPage();
    });
    document.getElementById('audit-date-to').addEventListener('change', e => {
        _dateTo = e.target.value;
        _page = 1;
        _loadPage();
    });
    document.getElementById('audit-prev-btn').addEventListener('click', () => {
        if (_page > 1) { _page--; _loadPage(); }
    });
    document.getElementById('audit-next-btn').addEventListener('click', () => {
        _page++;
        _loadPage();
    });
}

async function _loadPage() {
    const tbody = document.getElementById('audit-tbody');
    tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div></td></tr>`;

    const base = API_URLS.rp_versions.audit.list(planPk, versionPk).href;
    const params = new URLSearchParams({ page: _page });
    if (_eventType)  params.set('event_type', _eventType);
    if (_dateFrom)   params.set('date_from', _dateFrom);
    if (_dateTo)     params.set('date_to', _dateTo);

    try {
        const data = await apiFetch(`${base}?${params}`);
        _renderRows(data.results ?? []);
        _updatePagination(data);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">${escHtml(err?.detail ?? 'Failed to load audit log.')}</td></tr>`;
    }
}

function _renderRows(entries) {
    const tbody = document.getElementById('audit-tbody');
    if (!entries.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">No audit entries found.</td></tr>`;
        return;
    }
    tbody.innerHTML = entries.map(e => _rowHtml(e)).join('');
    tbody.querySelectorAll('.audit-expand-btn').forEach(btn => {
        btn.addEventListener('click', () => _toggleDetail(btn, parseInt(btn.dataset.id)));
    });
}

function _rowHtml(e) {
    const label = EVENT_LABELS[e.event_type] ?? e.event_type;
    const summary = _summarise(e);
    return `
    <tr data-audit-id="${e.id}">
        <td class="text-muted small text-nowrap">${formatDateTime(e.created_at)}</td>
        <td><span class="audit-event-badge audit-event-${escHtml(e.event_type)}">${escHtml(label)}</span></td>
        <td class="small text-muted">${escHtml(e.entity_type)}${e.entity_id ? ` #${e.entity_id}` : ''}</td>
        <td class="small">${summary}</td>
        <td><button class="audit-expand-btn" data-id="${e.id}" title="Expand"><i class="bi bi-chevron-down"></i></button></td>
    </tr>`;
}

function _summarise(e) {
    // Produce a short human-readable summary from the event type alone (detail loaded on expand)
    switch (e.event_type) {
        case 'ENGINE_RUN':           return `Engine job #${e.entity_id ?? '—'} completed`;
        case 'ALLOCATION_OVERRIDE':  return `Cell override on allocation #${e.entity_id ?? '—'}`;
        case 'PLACEHOLDER_OVERRIDE': return `Placeholder engineer updated #${e.entity_id ?? '—'}`;
        case 'CONFLICT_RESOLVED':    return `Conflict #${e.entity_id ?? '—'} resolved`;
        case 'STATUS_CHANGED':       return `${e.entity_type} #${e.entity_id ?? '—'} status changed`;
        case 'PLAN_CLONED':          return `Plan cloned → #${e.entity_id ?? '—'}`;
        case 'CONFIG_CHANGED':       return `Configuration updated on ${e.entity_type} #${e.entity_id ?? '—'}`;
        default: return e.notes ?? '';
    }
}

let _expandedId = null;

async function _toggleDetail(btn, auditId) {
    const row = btn.closest('tr');
    const existing = row.nextElementSibling;

    // Collapse if already open
    if (_expandedId === auditId && existing?.classList.contains('audit-detail-row')) {
        existing.remove();
        btn.querySelector('i').className = 'bi bi-chevron-down';
        _expandedId = null;
        return;
    }

    // Remove any other open detail row
    document.querySelectorAll('.audit-detail-row').forEach(r => r.remove());
    document.querySelectorAll('.audit-expand-btn i').forEach(i => i.className = 'bi bi-chevron-down');

    _expandedId = auditId;
    btn.querySelector('i').className = 'bi bi-chevron-up';

    const detailRow = document.createElement('tr');
    detailRow.className = 'audit-detail-row';
    detailRow.innerHTML = `<td colspan="5"><div class="p-2"><div class="spinner-border spinner-border-sm text-secondary"></div></div></td>`;
    row.after(detailRow);

    try {
        const data = await apiFetch(API_URLS.rp_versions.audit.detail(planPk, versionPk, auditId).href);
        detailRow.querySelector('td').innerHTML = _detailHtml(data);
    } catch (err) {
        detailRow.querySelector('td').innerHTML = `<div class="p-2 text-danger small">${escHtml(err?.detail ?? 'Failed to load detail.')}</div>`;
    }
}

function _detailHtml(e) {
    const before = e.before_state;
    const after  = e.after_state;
    let diffHtml = '';

    if (!before && !after) {
        diffHtml = `<span class="text-muted small">No state data recorded.</span>`;
    } else {
        const allKeys = new Set([
            ...Object.keys(before ?? {}),
            ...Object.keys(after ?? {}),
        ]);
        const lines = [];
        allKeys.forEach(k => {
            const bv = before?.[k];
            const av = after?.[k];
            if (JSON.stringify(bv) !== JSON.stringify(av)) {
                if (bv !== undefined) {
                    lines.push(`<div class="audit-diff-del"><span class="audit-diff-key">${escHtml(k)}</span>${escHtml(JSON.stringify(bv))}</div>`);
                }
                if (av !== undefined) {
                    lines.push(`<div class="audit-diff-add"><span class="audit-diff-key">${escHtml(k)}</span>${escHtml(JSON.stringify(av))}</div>`);
                }
            } else {
                lines.push(`<div class="px-2 text-muted small"><span class="audit-diff-key">${escHtml(k)}</span>${escHtml(JSON.stringify(av))}</div>`);
            }
        });
        diffHtml = lines.join('');
    }

    const notesHtml = e.notes ? `<div class="small text-muted mt-1"><strong>Notes:</strong> ${escHtml(e.notes)}</div>` : '';
    const jobHtml   = e.engine_job_id ? `<div class="small text-muted mt-1"><strong>Engine job:</strong> #${e.engine_job_id}</div>` : '';

    return `<div class="audit-diff-panel p-2 border rounded my-1">${diffHtml}</div>${notesHtml}${jobHtml}`;
}

function _updatePagination(data) {
    const pageInfo  = document.getElementById('audit-page-info');
    const prevBtn   = document.getElementById('audit-prev-btn');
    const nextBtn   = document.getElementById('audit-next-btn');
    const pagFooter = document.getElementById('audit-pagination');

    const total = data.total_count ?? 0;
    const pages = data.total_pages ?? 1;
    const current = data.current_page ?? 1;

    pagFooter.style.removeProperty('display');
    pageInfo.textContent = `Page ${current} of ${pages} (${total} entries)`;
    prevBtn.disabled = !data.has_previous;
    nextBtn.disabled = !data.has_next;

    if (total === 0) pagFooter.style.display = 'none';
}
