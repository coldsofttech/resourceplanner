'use strict';

import { apiFetch, escHtml, getPkFromUrl, setPageTitle } from './../main.js';
import { API_URLS } from './../urls.js';

const planPk    = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

let _conflicts        = [];
let _manpowerRequests = [];
let _severityFilter   = '';
let _statusFilter     = '';
let _activeConflict   = null;

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
    if (!planPk || !versionPk) return;

    _bindFilterButtons();
    _bindModal();

    try {
        const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
        document.getElementById('cf-plan-name').textContent = ver.plan_name ?? '—';
        document.getElementById('cf-version-badge').innerHTML =
            `<span class="badge bg-secondary">v${ver.version}</span>`;
        setPageTitle(`Conflicts — ${ver.plan_name ?? ''}`);
        const bc = document.getElementById('cf-breadcrumb');
        if (bc) bc.innerHTML =
            `<a href="/resource-plans/${planPk}/" class="text-decoration-none text-secondary">Resource Plans</a>`;
    } catch (_) {}

    await Promise.all([_loadConflicts(), _loadManpowerRequests()]);
}

// ── Load conflicts ────────────────────────────────────────────────────────────

async function _loadConflicts() {
    const loading = document.getElementById('cf-loading');
    const empty   = document.getElementById('cf-empty');
    const list    = document.getElementById('cf-list');

    loading?.classList.remove('d-none');
    empty?.classList.add('d-none');
    list?.classList.add('d-none');

    try {
        const [conflicts, summary] = await Promise.all([
            apiFetch(API_URLS.rp_versions.conflicts.list(planPk, versionPk).href),
            apiFetch(API_URLS.rp_versions.conflicts.summary(planPk, versionPk).href),
        ]);
        _conflicts = Array.isArray(conflicts) ? conflicts : (conflicts.results ?? []);
        _renderSummaryChips(summary);
        _renderCards();
    } catch (_) {
        loading?.classList.add('d-none');
        _showBanner('Failed to load conflicts.', 'danger');
    }
}

// ── Load manpower requests ────────────────────────────────────────────────────

async function _loadManpowerRequests() {
    try {
        const data = await apiFetch(API_URLS.rp_versions.manpower.list(planPk, versionPk).href);
        _manpowerRequests = Array.isArray(data) ? data : (data.results ?? []);
        _renderManpowerRequests();
    } catch (_) {}
}

// ── Summary chips ─────────────────────────────────────────────────────────────

function _renderSummaryChips(summary) {
    const el = document.getElementById('cf-summary-chips');
    if (!el) return;

    document.getElementById('cf-summary-loading')?.remove();

    const errorBadge = document.getElementById('cf-error-count-badge');
    if (errorBadge) {
        const n = summary.open_errors ?? 0;
        errorBadge.textContent = n > 0 ? `${n} open error${n !== 1 ? 's' : ''}` : '';
        errorBadge.classList.toggle('d-none', n === 0);
    }

    if (!summary.total) {
        el.innerHTML = `<span class="text-secondary small"><i class="bi bi-check-circle-fill text-success me-1"></i>No conflicts detected</span>`;
        return;
    }

    el.innerHTML = [
        `<span class="cf-summary-chip cf-badge-error"><i class="bi bi-x-circle me-1"></i>${summary.errors ?? 0} Error${(summary.errors ?? 0) !== 1 ? 's' : ''}</span>`,
        `<span class="cf-summary-chip cf-badge-warning"><i class="bi bi-exclamation-triangle me-1"></i>${summary.warnings ?? 0} Warning${(summary.warnings ?? 0) !== 1 ? 's' : ''}</span>`,
        `<span class="cf-summary-chip cf-badge-info"><i class="bi bi-info-circle me-1"></i>${summary.infos ?? 0} Info</span>`,
        `<span class="vr mx-1"></span>`,
        `<span class="cf-summary-chip" style="background:var(--bs-tertiary-bg);border:1px solid var(--bs-border-color)"><span class="cf-status-dot open d-inline-block me-1"></span>${summary.open ?? 0} Open</span>`,
        `<span class="cf-summary-chip" style="background:var(--bs-tertiary-bg);border:1px solid var(--bs-border-color)"><span class="cf-status-dot resolved d-inline-block me-1"></span>${summary.resolved ?? 0} Resolved</span>`,
        `<span class="cf-summary-chip" style="background:var(--bs-tertiary-bg);border:1px solid var(--bs-border-color)"><span class="cf-status-dot dismissed d-inline-block me-1"></span>${summary.dismissed ?? 0} Dismissed</span>`,
    ].join('');
}

// ── Card rendering ────────────────────────────────────────────────────────────

const CONFLICT_TYPE_LABELS = {
    CAPACITY_EXCEEDED:   'Capacity Exceeded',
    COMPETING_PRIORITY:  'Competing Priority',
    TIMELINE_BREACH:     'Timeline Breach',
    BUDGET_EXCEEDED:     'Budget Exceeded',
    DEPENDENCY_VIOLATED: 'Dependency Violated',
    UNRESOLVABLE_GAP:    'Unresolvable Gap',
    THRESHOLD_BREACH:    'Threshold Breach',
};

const RESOLUTION_LABELS = {
    DEPRIORITISED:    'Deprioritised',
    TIMELINE_SHIFTED: 'Timeline Shifted',
    ENGINEER_SWAPPED: 'Engineer Swapped',
    TEAM_CHANGED:     'Team Changed',
    MANPOWER_RAISED:  'Manpower Raised',
    REBALANCED:       'Rebalanced',
    DISMISSED:        'Dismissed',
};

function _renderCards() {
    const loading = document.getElementById('cf-loading');
    const empty   = document.getElementById('cf-empty');
    const list    = document.getElementById('cf-list');
    if (!list) return;

    loading?.classList.add('d-none');

    const visible = _conflicts.filter(c => {
        if (_severityFilter && c.severity !== _severityFilter) return false;
        if (_statusFilter   && c.status   !== _statusFilter)   return false;
        return true;
    });

    if (visible.length === 0) {
        list.classList.add('d-none');
        empty?.classList.remove('d-none');
        return;
    }

    empty?.classList.add('d-none');
    list.innerHTML = visible.map(_buildCard).join('');
    list.classList.remove('d-none');
}

function _buildCard(c) {
    const sevClass  = { ERROR: 'cf-badge-error', WARNING: 'cf-badge-warning', INFO: 'cf-badge-info' }[c.severity] ?? '';
    const dotClass  = c.status.toLowerCase();
    const typeLabel = CONFLICT_TYPE_LABELS[c.conflict_type] ?? c.conflict_type;

    const affected = [];
    if (c.affected_project_name) affected.push(`<i class="bi bi-kanban me-1"></i>${escHtml(c.affected_project_name)}`);
    if (c.affected_phase_name)   affected.push(`<i class="bi bi-layers me-1"></i>${escHtml(c.affected_phase_name)}`);
    if (c.affected_team_name)    affected.push(`<i class="bi bi-people me-1"></i>${escHtml(c.affected_team_name)}`);
    if (c.affected_member_name)  affected.push(`<i class="bi bi-person me-1"></i>${escHtml(c.affected_member_name)}`);
    if (c.affected_sprint_name)  affected.push(`<i class="bi bi-calendar3 me-1"></i>${escHtml(c.affected_sprint_name)}`);

    const resolvedInfo = c.status !== 'OPEN'
        ? `<div class="mt-2 pt-2 border-top small text-secondary">
               <i class="bi bi-check2 me-1"></i>
               <strong>${escHtml(RESOLUTION_LABELS[c.resolution_type] ?? c.resolution_type ?? 'Dismissed')}</strong>
               ${c.resolution_notes ? ` — ${escHtml(c.resolution_notes)}` : ''}
           </div>`
        : '';

    const resolveBtn = c.status === 'OPEN'
        ? `<button class="btn btn-sm btn-outline-primary cf-resolve-btn" data-conflict-id="${c.id}">
               <i class="bi bi-check2-square me-1"></i>Resolve
           </button>`
        : `<span class="badge ${c.status === 'RESOLVED' ? 'bg-success-subtle text-success-emphasis' : 'bg-secondary-subtle text-secondary-emphasis'}">${c.status}</span>`;

    return `
<div class="cf-card cf-card-${dotClass}" data-conflict-id="${c.id}" data-severity="${c.severity}" data-status="${c.status}">
    <div class="cf-card-header">
        <span class="cf-status-dot ${dotClass}"></span>
        <span class="cf-severity-badge ${sevClass}">${c.severity}</span>
        <span class="cf-type-label">${escHtml(typeLabel)}</span>
        <span class="ms-auto">${resolveBtn}</span>
    </div>
    <div class="cf-card-body">
        <div>${escHtml(c.description)}</div>
        ${affected.length ? `<div class="cf-affected d-flex flex-wrap gap-3 mt-2">${affected.join('')}</div>` : ''}
        ${resolvedInfo}
    </div>
</div>`.trim();
}

// ── Manpower request rendering ────────────────────────────────────────────────

const MP_STATUS_BADGE = {
    OPEN:       'bg-danger-subtle text-danger-emphasis',
    HIRING:     'bg-warning-subtle text-warning-emphasis',
    REBALANCED: 'bg-success-subtle text-success-emphasis',
    DISMISSED:  'bg-secondary-subtle text-secondary-emphasis',
};

function _renderManpowerRequests() {
    const section = document.getElementById('cf-mp-section');
    const mpList  = document.getElementById('cf-mp-list');
    if (!section || !mpList) return;

    if (_manpowerRequests.length === 0) {
        section.classList.add('d-none');
        return;
    }

    mpList.innerHTML = _manpowerRequests.map(mp => {
        const badgeClass = MP_STATUS_BADGE[mp.status] ?? 'bg-secondary-subtle text-secondary-emphasis';
        const isActive   = mp.status === 'OPEN' || mp.status === 'HIRING';

        const actions = isActive ? `
            <div class="d-flex gap-2 flex-shrink-0">
                ${mp.status === 'OPEN' ? `<button class="btn btn-sm btn-outline-success mp-hire-btn" data-mp-id="${mp.id}"><i class="bi bi-person-plus me-1"></i>Hire</button>` : ''}
                <button class="btn btn-sm btn-outline-secondary mp-rebalance-btn" data-mp-id="${mp.id}"><i class="bi bi-arrow-left-right me-1"></i>Rebalance</button>
                <button class="btn btn-sm btn-outline-secondary mp-dismiss-btn" data-mp-id="${mp.id}"><i class="bi bi-x me-1"></i>Dismiss</button>
            </div>` : '';

        return `
<div class="cf-mp-card" data-mp-id="${mp.id}">
    <div>
        <span class="badge ${badgeClass} me-2">${mp.status}</span>
        <strong>${escHtml(mp.team_name)}</strong>
        ${mp.phase_name ? `<span class="text-secondary ms-1">· ${escHtml(mp.phase_name)}</span>` : ''}
        <span class="text-secondary ms-2 small">
            ${mp.sprints_needed} sprint${mp.sprints_needed !== 1 ? 's' : ''} · ${mp.days_needed}d needed
        </span>
    </div>
    ${actions}
</div>`.trim();
    }).join('');

    section.classList.remove('d-none');

    mpList.querySelectorAll('.mp-hire-btn').forEach(btn =>
        btn.addEventListener('click', () => _mpAction('hire', btn.dataset.mpId)));
    mpList.querySelectorAll('.mp-rebalance-btn').forEach(btn =>
        btn.addEventListener('click', () => _mpAction('rebalance', btn.dataset.mpId)));
    mpList.querySelectorAll('.mp-dismiss-btn').forEach(btn =>
        btn.addEventListener('click', () => _mpAction('dismiss', btn.dataset.mpId)));
}

async function _mpAction(action, mpId) {
    const urlFn = API_URLS.rp_versions.manpower[action];
    if (!urlFn) return;
    try {
        await apiFetch(urlFn(planPk, versionPk, mpId).href, { method: 'POST', body: '{}' });
        await _loadManpowerRequests();
    } catch (e) {
        _showBanner(e?.data?.detail ?? `Failed to ${action} manpower request.`, 'danger');
    }
}

// ── Filter buttons ────────────────────────────────────────────────────────────

function _bindFilterButtons() {
    document.querySelectorAll('.cf-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.cf-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _severityFilter = btn.dataset.filter ?? '';
            _renderCards();
        });
    });

    document.querySelectorAll('.cf-status-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.cf-status-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _statusFilter = btn.dataset.status ?? '';
            _renderCards();
        });
    });
}

// ── Resolution modal ──────────────────────────────────────────────────────────

function _bindModal() {
    document.getElementById('cf-list')?.addEventListener('click', e => {
        const btn = e.target.closest('.cf-resolve-btn');
        if (!btn) return;
        const conflict = _conflicts.find(c => String(c.id) === String(btn.dataset.conflictId));
        if (conflict) _openResolveModal(conflict);
    });

    document.getElementById('cf-resolve-submit')?.addEventListener('click', _submitResolve);
}

function _openResolveModal(conflict) {
    _activeConflict = conflict;

    document.getElementById('cf-resolve-title').textContent =
        `Resolve — ${CONFLICT_TYPE_LABELS[conflict.conflict_type] ?? conflict.conflict_type}`;
    document.getElementById('cf-resolve-desc').textContent = conflict.description;
    document.getElementById('cf-resolve-notes').value = '';
    document.getElementById('cf-resolve-err')?.classList.add('d-none');

    const allowed     = conflict.allowed_resolutions?.length ? conflict.allowed_resolutions : ['DISMISSED'];
    const optionsEl   = document.getElementById('cf-resolve-options');
    optionsEl.innerHTML = allowed.map((res, i) => `
<div class="cf-res-option${i === 0 ? ' selected' : ''}" data-value="${escHtml(res)}">
    <span class="cf-res-label">${escHtml(RESOLUTION_LABELS[res] ?? res)}</span>
</div>`).join('');

    optionsEl.querySelectorAll('.cf-res-option').forEach(opt => {
        opt.addEventListener('click', () => {
            optionsEl.querySelectorAll('.cf-res-option').forEach(o => o.classList.remove('selected'));
            opt.classList.add('selected');
        });
    });

    bootstrap.Modal.getOrCreateInstance(document.getElementById('cfResolveModal')).show();
}

async function _submitResolve() {
    if (!_activeConflict) return;

    const selected = document.querySelector('#cf-resolve-options .cf-res-option.selected');
    if (!selected) { _setResolveErr('Please select a resolution type.'); return; }

    const resolution_type = selected.dataset.value;
    const notes           = document.getElementById('cf-resolve-notes').value.trim();

    const spinner = document.getElementById('cf-resolve-spinner');
    const btn     = document.getElementById('cf-resolve-submit');
    spinner?.classList.remove('d-none');
    btn.disabled = true;

    try {
        await apiFetch(
            API_URLS.rp_versions.conflicts.resolve(planPk, versionPk, _activeConflict.id).href,
            { method: 'POST', body: JSON.stringify({ resolution_type, notes }) },
        );
        bootstrap.Modal.getInstance(document.getElementById('cfResolveModal'))?.hide();
        await _loadConflicts();
    } catch (e) {
        const msg = e?.data?.detail ?? e?.data?.resolution_type ?? 'Failed to apply resolution.';
        _setResolveErr(Array.isArray(msg) ? msg[0] : msg);
    } finally {
        spinner?.classList.add('d-none');
        btn.disabled = false;
    }
}

function _setResolveErr(msg) {
    const el = document.getElementById('cf-resolve-err');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('d-none');
}

// ── Banner ────────────────────────────────────────────────────────────────────

function _showBanner(msg, type = 'info') {
    const el = document.getElementById('cf-banner');
    if (!el) return;
    el.className = `alert alert-${type} mb-3`;
    el.textContent = msg;
    el.classList.remove('d-none');
    setTimeout(() => el.classList.add('d-none'), 5000);
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
