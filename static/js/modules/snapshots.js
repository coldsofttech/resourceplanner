'use strict';
import { API_URLS } from './../urls.js';
import { apiFetch, escHtml, getPkFromUrl, setPageTitle } from './../main.js';

const planPk    = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

let _snapshots = [];
let _pollTimer = null;

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
    if (!planPk || !versionPk) return;
    await _loadVersionMeta();
    await _loadSnapshots();
    _bindCompare();
}

// ── Version meta ──────────────────────────────────────────────────────────────

async function _loadVersionMeta() {
    try {
        const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
        document.getElementById('snap-plan-name').textContent = ver.plan_name ?? '—';
        const badge = document.getElementById('snap-version-badge');
        if (badge) badge.textContent = `v${ver.version}`;
        setPageTitle(`Snapshots — ${ver.plan_name ?? ''}`);
    } catch (_) {}
}

// ── Load & render snapshots ───────────────────────────────────────────────────

async function _loadSnapshots() {
    try {
        _snapshots = await apiFetch(API_URLS.rp_versions.snapshots.list(planPk, versionPk).href) ?? [];
    } catch (_) {
        _snapshots = [];
    }
    _renderList();
    _updateComparePickers();
    _checkInProgressBanner();
    _maybeStartPoll();
}

function _renderList() {
    const tbody = document.getElementById('snap-tbody');
    if (!tbody) return;
    if (!_snapshots.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-secondary py-4">No snapshots yet. Take one to capture the current allocation state.</td></tr>`;
        return;
    }
    tbody.innerHTML = _snapshots.map(s => `
        <tr data-snap-id="${s.id}">
            <td><strong>${escHtml(s.label)}</strong>${s.notes ? `<div class="text-muted small">${escHtml(s.notes)}</div>` : ''}</td>
            <td>${_statusBadge(s.status)}</td>
            <td class="text-end">${s.total_allocation_days != null ? s.total_allocation_days.toFixed(1) + 'd' : '—'}</td>
            <td class="text-end">${s.total_members ?? '—'}</td>
            <td class="text-end">${s.total_projects ?? '—'}</td>
            <td class="small text-secondary">${s.initiated_at ? new Date(s.initiated_at).toLocaleString() : '—'}</td>
            <td>
                ${s.status === 'COMPLETE' ? `
                <button class="btn btn-xs btn-outline-secondary me-1 snap-alloc-btn" data-id="${s.id}" data-label="${escHtml(s.label)}" title="View Allocations">
                    <i class="bi bi-table"></i>
                </button>` : ''}
                <button class="btn btn-xs btn-outline-danger snap-delete-btn" data-id="${s.id}" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
    tbody.querySelectorAll('.snap-delete-btn').forEach(btn => {
        btn.addEventListener('click', () => _deleteSnapshot(Number(btn.dataset.id)));
    });
    tbody.querySelectorAll('.snap-alloc-btn').forEach(btn => {
        btn.addEventListener('click', () => _openAllocModal(Number(btn.dataset.id), btn.dataset.label));
    });
}

function _statusBadge(status) {
    const map = {
        PENDING:     'bg-secondary',
        IN_PROGRESS: 'bg-warning text-dark',
        COMPLETE:    'bg-success',
        FAILED:      'bg-danger',
    };
    const cls = map[status] ?? 'bg-secondary';
    return `<span class="badge ${cls}">${status}</span>`;
}

// ── Banner ─────────────────────────────────────────────────────────────────────

function _checkInProgressBanner() {
    const inProgress = _snapshots.find(s => s.status === 'PENDING' || s.status === 'IN_PROGRESS');
    const banner = document.getElementById('snap-lock-banner');
    if (!banner) return;
    if (inProgress) {
        banner.classList.remove('d-none');
        banner.textContent = `Snapshot "${inProgress.label}" is in progress. All plan write operations are currently locked (423).`;
    } else {
        banner.classList.add('d-none');
    }
}

// ── Polling ────────────────────────────────────────────────────────────────────

function _maybeStartPoll() {
    const inProgress = _snapshots.some(s => s.status === 'PENDING' || s.status === 'IN_PROGRESS');
    if (inProgress && !_pollTimer) {
        _pollTimer = setInterval(async () => {
            await _loadSnapshots();
            if (!_snapshots.some(s => s.status === 'PENDING' || s.status === 'IN_PROGRESS')) {
                clearInterval(_pollTimer);
                _pollTimer = null;
            }
        }, 3000);
    }
}

// ── Take Snapshot modal ────────────────────────────────────────────────────────

function _bindTakeSnapshotBtn() {
    document.getElementById('snap-take-btn')?.addEventListener('click', () => {
        document.getElementById('snap-label-input').value = '';
        document.getElementById('snap-notes-input').value = '';
        document.getElementById('snap-modal-error').classList.add('d-none');
        document.getElementById('snap-modal-spinner').classList.add('d-none');
        document.getElementById('snap-modal-submit').disabled = false;
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('snapModal'));
        modal.show();
    });

    document.getElementById('snap-modal-submit')?.addEventListener('click', async () => {
        const label = document.getElementById('snap-label-input').value.trim();
        if (!label) {
            _showModalError('Label is required.');
            return;
        }
        const notes = document.getElementById('snap-notes-input').value.trim();
        const submitBtn = document.getElementById('snap-modal-submit');
        const spinner = document.getElementById('snap-modal-spinner');
        submitBtn.disabled = true;
        spinner.classList.remove('d-none');
        document.getElementById('snap-modal-error').classList.add('d-none');
        try {
            await apiFetch(API_URLS.rp_versions.snapshots.create(planPk, versionPk).href, {
                method: 'POST',
                body: JSON.stringify({ label, notes }),
            });
            bootstrap.Modal.getInstance(document.getElementById('snapModal'))?.hide();
            await _loadSnapshots();
        } catch (err) {
            const msg = err?.detail ?? err?.message ?? 'Failed to create snapshot.';
            _showModalError(msg);
            submitBtn.disabled = false;
            spinner.classList.add('d-none');
        }
    });
}

function _showModalError(msg) {
    const el = document.getElementById('snap-modal-error');
    if (el) {
        el.textContent = msg;
        el.classList.remove('d-none');
    }
}

// ── Compare ────────────────────────────────────────────────────────────────────

function _updateComparePickers() {
    const done = _snapshots.filter(s => s.status === 'COMPLETE');
    ['snap-compare-a', 'snap-compare-b'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const prev = sel.value;
        sel.innerHTML = '<option value="">— select —</option>' +
            done.map(s => `<option value="${s.id}"${String(s.id) === prev ? ' selected' : ''}>${escHtml(s.label)} (${new Date(s.initiated_at).toLocaleDateString()})</option>`).join('');
    });
}

function _bindCompare() {
    document.getElementById('snap-compare-btn')?.addEventListener('click', _runCompare);
}

async function _runCompare() {
    const aId = document.getElementById('snap-compare-a')?.value;
    const bId = document.getElementById('snap-compare-b')?.value;
    const errEl = document.getElementById('snap-compare-error');
    if (!aId || !bId) {
        if (errEl) { errEl.textContent = 'Select both A and B snapshots.'; errEl.classList.remove('d-none'); }
        return;
    }
    if (aId === bId) {
        if (errEl) { errEl.textContent = 'A and B must be different snapshots.'; errEl.classList.remove('d-none'); }
        return;
    }
    if (errEl) errEl.classList.add('d-none');
    const snapPk = aId; // endpoint mounted under either snap pk; pass a and b as query params
    const url = API_URLS.rp_versions.snapshots.compare(planPk, versionPk, snapPk).href + `?a=${aId}&b=${bId}`;
    try {
        const data = await apiFetch(url);
        _renderDiff(data);
    } catch (err) {
        if (errEl) { errEl.textContent = err?.detail ?? 'Compare failed.'; errEl.classList.remove('d-none'); }
    }
}

function _renderDiff(data) {
    const panel = document.getElementById('snap-diff-panel');
    if (!panel) return;

    const { snapshot_a: sa, snapshot_b: sb, diff } = data;
    const labelA = escHtml(sa?.label ?? 'A');
    const labelB = escHtml(sb?.label ?? 'B');

    if (!diff || !diff.length) {
        panel.innerHTML = `<div class="alert alert-info mt-3">No allocation data found in either snapshot.</div>`;
        return;
    }
    const changedCount = diff.filter(r => r.delta_days !== 0).length;
    const unchangedCount = diff.length - changedCount;

    // Build hierarchy: programme → team → member → rows
    const tree = {};
    diff.forEach(row => {
        const prog = row.programme_name || '(No Programme)';
        const team = row.team_name || '(No Team)';
        const member = row.member_name || '(Unknown)';
        if (!tree[prog]) tree[prog] = {};
        if (!tree[prog][team]) tree[prog][team] = {};
        if (!tree[prog][team][member]) tree[prog][team][member] = [];
        tree[prog][team][member].push(row);
    });

    const accordionId = `diff-acc-${Date.now()}`;
    let itemIdx = 0;

    const progBlocks = Object.entries(tree).map(([prog, teams]) => {
        const progId  = `${accordionId}-p${itemIdx++}`;
        const progRows = Object.values(teams).flatMap(members =>
            Object.values(members).flat()
        );

        const teamBlocks = Object.entries(teams).map(([team, members]) => {
            const memberBlocks = Object.entries(members).map(([member, rows]) => {
                const lineHtml = rows.map(row => {
                    const delta  = row.delta_days;
                    const sign   = delta > 0 ? '+' : '';
                    const cls    = delta > 0 ? 'diff-line-add' : delta < 0 ? 'diff-line-del' : 'diff-line-same';
                    const prefix = delta > 0 ? '+' : delta < 0 ? '−' : ' ';
                    return `<div class="diff-line ${cls}">
                        <span class="diff-prefix">${prefix}</span>
                        <span class="diff-meta">${escHtml(row.sprint_name)} &bull; ${escHtml(row.project_name)}</span>
                        <span class="diff-days">
                            <span class="diff-a">${row.days_a.toFixed(2)}d</span>
                            <span class="diff-arrow">→</span>
                            <span class="diff-b">${row.days_b.toFixed(2)}d</span>
                            ${delta !== 0 ? `<span class="diff-delta">${sign}${delta.toFixed(2)}d</span>` : ''}
                        </span>
                    </div>`;
                }).join('');
                return `<div class="diff-member-block">
                    <div class="diff-member-header"><i class="bi bi-person me-1"></i>${escHtml(member)} <span class="diff-count">${rows.length}</span></div>
                    <div class="diff-body">${lineHtml}</div>
                </div>`;
            }).join('');
            const teamTotal = Object.values(members).flat().length;
            return `<div class="diff-team-block">
                <div class="diff-team-header"><i class="bi bi-people me-1"></i>${escHtml(team)} <span class="diff-count">${teamTotal}</span></div>
                ${memberBlocks}
            </div>`;
        }).join('');

        return `
        <div class="accordion-item diff-prog-item">
            <h2 class="accordion-header">
                <button class="accordion-button diff-acc-btn" type="button"
                        data-bs-toggle="collapse" data-bs-target="#${progId}"
                        aria-expanded="true" aria-controls="${progId}">
                    <span class="diff-prog-name">${escHtml(prog)}</span>
                    <span class="diff-count ms-2">${progRows.length} change${progRows.length === 1 ? '' : 's'}</span>
                </button>
            </h2>
            <div id="${progId}" class="accordion-collapse collapse show">
                <div class="accordion-body p-0">${teamBlocks}</div>
            </div>
        </div>`;
    }).join('');

    panel.innerHTML = `
        <div class="d-flex align-items-center gap-2 mt-3 mb-3">
            <span class="badge bg-secondary">${labelA}</span>
            <i class="bi bi-arrow-right text-muted"></i>
            <span class="badge bg-secondary">${labelB}</span>
            <span class="text-muted small ms-2">${changedCount > 0 ? `${changedCount} changed` : 'no changes'}${unchangedCount > 0 ? `, ${unchangedCount} unchanged` : ''}</span>
        ${changedCount === 0 ? `<span class="badge bg-success ms-1">Identical</span>` : ''}
        </div>
        <div class="accordion diff-container" id="${accordionId}">${progBlocks}</div>`;
}

// ── Allocations Modal ─────────────────────────────────────────────────────────

let _allocPage = 1;
let _allocSnapId = null;

async function _openAllocModal(snapId, label) {
    _allocSnapId = snapId;
    _allocPage   = 1;
    const titleEl = document.getElementById('snap-alloc-modal-title');
    if (titleEl) titleEl.textContent = `Allocations — ${label}`;
    document.getElementById('snap-alloc-tbody').innerHTML =
        `<tr><td colspan="6" class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary"></div></td></tr>`;
    bootstrap.Modal.getOrCreateInstance(document.getElementById('snapAllocModal')).show();
    await _loadAllocPage();
}

async function _loadAllocPage() {
    const url = API_URLS.rp_versions.snapshots.allocations(planPk, versionPk, _allocSnapId).href + `?page=${_allocPage}`;
    try {
        const data = await apiFetch(url);
        const rows  = data.results ?? [];
        const count = data.count ?? 0;
        const pageSize = data.page_size ?? 100;
        const totalPages = Math.ceil(count / pageSize);

        const tbody = document.getElementById('snap-alloc-tbody');
        if (!tbody) return;
        tbody.innerHTML = rows.length
            ? rows.map(r => `<tr>
                <td>${escHtml(r.sprint_name)}</td>
                <td>${escHtml(r.member_name)}</td>
                <td>${escHtml(r.team_name)}</td>
                <td>${escHtml(r.project_name)}</td>
                <td>${escHtml(r.assignment_type ?? '—')}</td>
                <td class="text-end">${parseFloat(r.days).toFixed(2)}d</td>
              </tr>`).join('')
            : `<tr><td colspan="6" class="text-center text-secondary py-3">No allocations</td></tr>`;

        const nav = document.getElementById('snap-alloc-nav');
        if (nav) {
            nav.innerHTML = totalPages <= 1 ? '' : `
                <div class="d-flex align-items-center gap-2">
                    <button class="btn btn-sm btn-outline-secondary" id="snap-alloc-prev" ${_allocPage <= 1 ? 'disabled' : ''}>
                        <i class="bi bi-chevron-left"></i>
                    </button>
                    <span class="small text-secondary">Page ${_allocPage} / ${totalPages} &nbsp;(${count} rows)</span>
                    <button class="btn btn-sm btn-outline-secondary" id="snap-alloc-next" ${_allocPage >= totalPages ? 'disabled' : ''}>
                        <i class="bi bi-chevron-right"></i>
                    </button>
                </div>`;
            document.getElementById('snap-alloc-prev')?.addEventListener('click', async () => {
                if (_allocPage > 1) { _allocPage--; await _loadAllocPage(); }
            });
            document.getElementById('snap-alloc-next')?.addEventListener('click', async () => {
                if (_allocPage < totalPages) { _allocPage++; await _loadAllocPage(); }
            });
        }
    } catch (err) {
        const tbody = document.getElementById('snap-alloc-tbody');
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-danger py-2">${escHtml(err?.detail ?? 'Failed to load allocations.')}</td></tr>`;
    }
}

// ── Delete ────────────────────────────────────────────────────────────────────

async function _deleteSnapshot(snapId) {
    if (!confirm('Delete this snapshot? This cannot be undone.')) return;
    try {
        await apiFetch(API_URLS.rp_versions.snapshots.delete(planPk, versionPk, snapId).href, {
            method: 'DELETE',
        });
        await _loadSnapshots();
    } catch (err) {
        alert(err?.detail ?? 'Delete failed. The snapshot may be the only one for this plan.');
    }
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    _bindTakeSnapshotBtn();
    init();
});
