'use strict';

import { apiFetch, escHtml, formatDateTime, showFlash } from './../main.js';
import { API_URLS } from './../urls.js';

// ── Page detection ────────────────────────────────────────────────────────────

const isDetail = typeof window.WIN_PK !== 'undefined';
const isReport = location.pathname.includes('/wins/report');
const isList   = !isDetail && !isReport;

document.addEventListener('DOMContentLoaded', () => {
    if (isDetail) initDetailPage();
    else if (isReport) initReportPage();
    else initListPage();
});

// ─────────────────────────────────────────────────────────────────────────────
// LIST PAGE
// ─────────────────────────────────────────────────────────────────────────────

let _page = 1;

async function initListPage() {
    loadWins(1);
    await prefillNextWeekDate();

    document.getElementById('btn-new-win')?.addEventListener('click', () => {
        document.getElementById('new-win-banner').classList.add('d-none');
        document.getElementById('new-win-preview').classList.add('d-none');
        bootstrap.Modal.getOrCreateInstance(document.getElementById('newWinModal')).show();
    });

    document.getElementById('new-win-date')?.addEventListener('change', onDateChange);
    document.getElementById('btn-create-win')?.addEventListener('click', createWin);
}

async function prefillNextWeekDate() {
    try {
        const { method, href } = API_URLS.wins.nextWeek;
        const data = await apiFetch(href, { method });
        const input = document.getElementById('new-win-date');
        if (input) input.value = data.suggested_week_start;
        showPreview(data.week_number, data.suggested_week_start);
    } catch { /* non-fatal */ }
}

function showPreview(weekNumber, startDate) {
    const el = document.getElementById('new-win-preview');
    if (!el || !startDate) return;
    const start = new Date(startDate + 'T00:00:00');
    const end = new Date(start); end.setDate(end.getDate() + 6);
    const fmt = (d) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    el.textContent = `Week ${weekNumber}: ${fmt(start)} – ${fmt(end)}`;
    el.classList.remove('d-none');
}

async function onDateChange(e) {
    const val = e.target.value;
    if (!val) return;
    const d = new Date(val + 'T00:00:00');
    if (d.getDay() !== 1) {
        document.getElementById('new-win-banner').textContent = 'Please select a Monday.';
        document.getElementById('new-win-banner').classList.remove('d-none');
        document.getElementById('new-win-preview').classList.add('d-none');
        return;
    }
    document.getElementById('new-win-banner').classList.add('d-none');
    try {
        const { method, href } = API_URLS.wins.nextWeek;
        const data = await apiFetch(href, { method });
        showPreview(data.week_number, val);
    } catch { /* ignore */ }
}

async function createWin() {
    const date = document.getElementById('new-win-date')?.value;
    if (!date) {
        document.getElementById('new-win-banner').textContent = 'Week start date is required.';
        document.getElementById('new-win-banner').classList.remove('d-none');
        return;
    }
    const d = new Date(date + 'T00:00:00');
    if (d.getDay() !== 1) {
        document.getElementById('new-win-banner').textContent = 'Please select a Monday.';
        document.getElementById('new-win-banner').classList.remove('d-none');
        return;
    }
    const btn = document.getElementById('btn-create-win');
    btn.disabled = true; btn.textContent = 'Creating…';
    try {
        const { method, href } = API_URLS.wins.create;
        const win = await apiFetch(href, { method, body: JSON.stringify({ week_start_date: date }) });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('newWinModal')).hide();
        location.href = `/wins/${win.id}/`;
    } catch (err) {
        const msg = err?.detail?.week_start_date || err?.week_start_date || String(err?.detail || err?.message || 'Failed to create week.');
        document.getElementById('new-win-banner').textContent = msg;
        document.getElementById('new-win-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false; btn.textContent = 'Create Week';
    }
}

async function loadWins(page) {
    _page = page;
    const container = document.getElementById('wins-list-container');
    container.innerHTML = '<p class="text-secondary small">Loading…</p>';
    try {
        const { method, href } = API_URLS.wins.list;
        const data = await apiFetch(`${href}?page=${page}&page_size=20`, { method });
        renderWinList(data.results);
        renderWinsPagination(data.pagination);
    } catch {
        container.innerHTML = '<p class="text-danger small">Failed to load wins.</p>';
    }
}

function statusBadge(w) {
    if (w.status === 'review_complete') {
        return '<span class="badge bg-success ms-2">Review Complete</span>';
    }
    return '<span class="badge bg-secondary ms-2">Open</span>';
}

function renderWinList(wins) {
    const container = document.getElementById('wins-list-container');
    if (!wins.length) {
        container.innerHTML = '<div class="rp-empty-state"><i class="bi bi-trophy fs-2 text-secondary"></i><p class="text-secondary mt-2">No wins yet. Start by adding a new week!</p></div>';
        return;
    }
    container.innerHTML = `
    <div class="table-responsive">
        <table class="rp-table">
            <thead><tr>
                <th>Week</th>
                <th>Start Date</th>
                <th>End Date</th>
                <th class="text-center">Entries</th>
                <th class="text-center">Teams</th>
                <th>Status</th>
                <th></th>
            </tr></thead>
            <tbody>
                ${wins.map(w => `
                <tr>
                    <td><strong>Week ${w.week_number}</strong></td>
                    <td>${escHtml(w.week_start_date)}</td>
                    <td>${escHtml(w.week_end_date)}</td>
                    <td class="text-center">${w.entry_count}</td>
                    <td class="text-center">${w.team_count}</td>
                    <td>${statusBadge(w)}</td>
                    <td class="text-center">
                        <a href="/wins/${w.id}/" class="btn btn-ghost-icon btn-sm" title="Open">
                            <i class="bi bi-arrow-right-circle"></i>
                        </a>
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>
    </div>`;
}

function renderWinsPagination(p) {
    const el = document.getElementById('wins-pagination');
    if (!el) return;
    if (p.total_pages <= 1) { el.innerHTML = ''; return; }
    el.innerHTML = `
        <button class="btn btn-outline-secondary btn-sm" ${p.current_page <= 1 ? 'disabled' : ''} id="wins-prev">
            <i class="bi bi-chevron-left"></i> Prev
        </button>
        <span class="text-secondary small">Page ${p.current_page} of ${p.total_pages}</span>
        <button class="btn btn-outline-secondary btn-sm" ${p.current_page >= p.total_pages ? 'disabled' : ''} id="wins-next">
            Next <i class="bi bi-chevron-right"></i>
        </button>`;
    el.querySelector('#wins-prev')?.addEventListener('click', () => loadWins(_page - 1));
    el.querySelector('#wins-next')?.addEventListener('click', () => loadWins(_page + 1));
}

// ─────────────────────────────────────────────────────────────────────────────
// DETAIL PAGE
// ─────────────────────────────────────────────────────────────────────────────

const WIN_PK = window.WIN_PK;
let _win = null;
let _teams = [];
let _entryMode = 'add';
let _editEntryPk = null;
let _activeTeamId = null;

async function initDetailPage() {
    try {
        _win = await apiFetch(API_URLS.wins.detail(WIN_PK).href, { method: 'GET' });
        renderWinHeader(_win);
        _teams = await loadAllTeams();
        renderTeamsAccordion(_win, _teams);
    } catch {
        document.getElementById('win-banner').textContent = 'Failed to load win data.';
        document.getElementById('win-banner').className = 'alert alert-danger mb-3';
    }

    document.getElementById('btn-save-entry')?.addEventListener('click', saveEntry);
    document.getElementById('btn-confirm-delete-entry')?.addEventListener('click', confirmDeleteEntry);
    document.getElementById('btn-review-complete')?.addEventListener('click', () => {
        bootstrap.Modal.getOrCreateInstance(document.getElementById('reviewCompleteModal')).show();
    });
    document.getElementById('btn-confirm-review-complete')?.addEventListener('click', doReviewComplete);
}

function renderWinHeader(win) {
    document.getElementById('win-title').textContent = `Week ${win.week_number}`;
    document.getElementById('win-subtitle').textContent =
        `${win.week_start_date} – ${win.week_end_date}`;
    document.title = `Week ${win.week_number} — Wins`;

    const badge = document.getElementById('win-status-badge');
    const btn = document.getElementById('btn-review-complete');

    if (win.status === 'review_complete') {
        badge.className = 'badge bg-success';
        badge.textContent = 'Review Complete';
        badge.classList.remove('d-none');
        btn?.classList.add('d-none');
    } else {
        badge.classList.add('d-none');
        btn?.classList.remove('d-none');
    }
}

async function loadAllTeams() {
    const { href } = API_URLS.delivery_teams.list;
    const data = await apiFetch(`${href}?page_size=200&is_active=true`, { method: 'GET' });
    return Array.isArray(data) ? data : (data.results ?? []);
}

function renderTeamsAccordion(win, teams) {
    const container = document.getElementById('teams-accordion');
    const loading = document.getElementById('teams-loading');
    if (loading) loading.remove();
    if (!teams.length) {
        container.innerHTML = '<p class="text-secondary small">No active teams found.</p>';
        return;
    }

    const byTeam = {};
    (win.entries || []).forEach(e => {
        if (!byTeam[e.team]) byTeam[e.team] = [];
        byTeam[e.team].push(e);
    });

    container.innerHTML = teams.map((team, i) => {
        const entries = byTeam[team.id] || [];
        const badge = entries.length ? `<span class="badge bg-primary ms-2">${entries.length}</span>` : '';
        const avatarHtml = team.avatar_svg
            ? `<span style="display:inline-flex;width:24px;height:24px;border-radius:50%;overflow:hidden;flex-shrink:0">${team.avatar_svg}</span>`
            : '<i class="bi bi-people me-1"></i>';
        return `
        <div class="accordion-item rp-accordion-item" id="team-accordion-${team.id}">
            <h2 class="accordion-header">
                <button class="accordion-button ${i > 0 ? 'collapsed' : ''}" type="button"
                        data-bs-toggle="collapse" data-bs-target="#team-collapse-${team.id}">
                    <span class="d-flex align-items-center gap-2">
                        ${avatarHtml}
                        ${escHtml(team.name)} ${badge}
                    </span>
                </button>
            </h2>
            <div id="team-collapse-${team.id}" class="accordion-collapse collapse ${i === 0 ? 'show' : ''}">
                <div class="accordion-body">
                    <div id="entries-${team.id}">
                        ${renderTeamEntries(entries)}
                    </div>
                    <button class="btn btn-outline-primary btn-sm mt-2"
                            onclick="openAddEntry(${team.id}, '${escHtml(team.name).replace(/'/g, "\\'")}')">
                        <i class="bi bi-plus-lg me-1"></i>Add win entry
                    </button>
                </div>
            </div>
        </div>`;
    }).join('');
}

function renderTeamEntries(entries) {
    if (!entries.length) return '<p class="text-secondary small mb-2">No entries yet.</p>';
    return entries.map(e => `
        <div class="win-entry-card d-flex justify-content-between align-items-start gap-2" data-entry-id="${e.id}">
            <div class="flex-grow-1">
                <div class="win-entry-title">${escHtml(e.title)}</div>
                ${e.description ? `<div class="win-entry-desc">${escHtml(e.description)}</div>` : ''}
                <div class="win-entry-meta">${escHtml(e.created_by_name || '')} · ${formatDateTime(e.created_at)}</div>
            </div>
            <div class="win-entry-actions d-flex gap-1 flex-shrink-0">
                <button class="btn btn-ghost-icon btn-sm" title="Edit"
                        onclick="openEditEntry(${e.id}, '${escHtml(e.title).replace(/'/g, "\\'")}', '${escHtml(e.description || '').replace(/'/g, "\\'")}')">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm" title="Delete"
                        onclick="openDeleteEntry(${e.id})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </div>`).join('');
}

window.openAddEntry = function(teamId, teamName) {
    _entryMode = 'add';
    _editEntryPk = null;
    _activeTeamId = teamId;
    document.getElementById('add-entry-modal-title').textContent = `Add win — ${teamName}`;
    document.getElementById('entry-title').value = '';
    document.getElementById('entry-description').value = '';
    document.getElementById('add-entry-banner').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('addEntryModal')).show();
    setTimeout(() => document.getElementById('entry-title').focus(), 300);
};

window.openEditEntry = function(entryPk, currentTitle, currentDesc) {
    _entryMode = 'edit';
    _editEntryPk = entryPk;
    document.getElementById('add-entry-modal-title').textContent = 'Edit win entry';
    document.getElementById('entry-title').value = currentTitle;
    document.getElementById('entry-description').value = currentDesc;
    document.getElementById('add-entry-banner').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('addEntryModal')).show();
    setTimeout(() => document.getElementById('entry-title').focus(), 300);
};

window.openDeleteEntry = function(entryPk) {
    _editEntryPk = entryPk;
    document.getElementById('btn-confirm-delete-entry').dataset.entryPk = entryPk;
    bootstrap.Modal.getOrCreateInstance(document.getElementById('deleteEntryModal')).show();
};

async function saveEntry() {
    const title = document.getElementById('entry-title').value.trim();
    const description = document.getElementById('entry-description').value.trim();
    if (!title) {
        document.getElementById('add-entry-banner').textContent = 'Title is required.';
        document.getElementById('add-entry-banner').classList.remove('d-none');
        return;
    }
    const btn = document.getElementById('btn-save-entry');
    btn.disabled = true; btn.textContent = 'Saving…';
    try {
        if (_entryMode === 'add') {
            const { method, href } = API_URLS.wins.addEntry(WIN_PK);
            await apiFetch(href, { method, body: JSON.stringify({ team: _activeTeamId, title, description }) });
        } else {
            const { method, href } = API_URLS.wins.updateEntry(_editEntryPk);
            await apiFetch(href, { method, body: JSON.stringify({ title, description }) });
        }
        bootstrap.Modal.getOrCreateInstance(document.getElementById('addEntryModal')).hide();
        _win = await apiFetch(API_URLS.wins.detail(WIN_PK).href, { method: 'GET' });
        refreshTeamEntries(_activeTeamId || getTeamFromEntry(_editEntryPk));
        updateAccordionBadge(_win);
    } catch (err) {
        document.getElementById('add-entry-banner').textContent = String(err?.detail || err?.message || 'Failed to save entry.');
        document.getElementById('add-entry-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false; btn.textContent = 'Save';
    }
}

async function confirmDeleteEntry() {
    const entryPk = document.getElementById('btn-confirm-delete-entry').dataset.entryPk;
    const teamId = getTeamFromEntry(parseInt(entryPk));
    const btn = document.getElementById('btn-confirm-delete-entry');
    btn.disabled = true; btn.textContent = 'Deleting…';
    try {
        const { method, href } = API_URLS.wins.deleteEntry(entryPk);
        await apiFetch(href, { method });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('deleteEntryModal')).hide();
        _win = await apiFetch(API_URLS.wins.detail(WIN_PK).href, { method: 'GET' });
        refreshTeamEntries(teamId);
        updateAccordionBadge(_win);
    } catch {
        showFlash('Failed to delete entry.', 'danger');
    } finally {
        btn.disabled = false; btn.textContent = 'Delete';
    }
}

async function doReviewComplete() {
    const btn = document.getElementById('btn-confirm-review-complete');
    btn.disabled = true; btn.textContent = 'Sending…';
    try {
        const { method, href } = API_URLS.wins.reviewComplete(WIN_PK);
        _win = await apiFetch(href, { method });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('reviewCompleteModal')).hide();
        renderWinHeader(_win);
        showFlash('Review marked complete. Document emailed to recipients.', 'success');
    } catch (err) {
        const msg = String(err?.detail || err?.message || err?.error || 'Failed to mark review complete.');
        showFlash(msg, 'danger');
    } finally {
        btn.disabled = false; btn.textContent = 'Confirm & Send';
    }
}

function getTeamFromEntry(entryPk) {
    if (!_win) return null;
    const entry = (_win.entries || []).find(e => e.id === parseInt(entryPk));
    return entry?.team ?? null;
}

function refreshTeamEntries(teamId) {
    if (!teamId) return;
    const container = document.getElementById(`entries-${teamId}`);
    if (!container) return;
    const entries = (_win.entries || []).filter(e => e.team === teamId);
    container.innerHTML = renderTeamEntries(entries);
}

function updateAccordionBadge(win) {
    const byTeam = {};
    (win.entries || []).forEach(e => {
        byTeam[e.team] = (byTeam[e.team] || 0) + 1;
    });
    _teams.forEach(team => {
        const btn = document.querySelector(`#team-accordion-${team.id} .accordion-button`);
        if (!btn) return;
        const existing = btn.querySelector('.badge');
        if (existing) existing.remove();
        const count = byTeam[team.id];
        if (count) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary ms-2';
            badge.textContent = count;
            btn.querySelector('span').appendChild(badge);
        }
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// REPORT PAGE
// ─────────────────────────────────────────────────────────────────────────────

let _reportMode = 'week';

window.setMode = function(mode) {
    _reportMode = mode;
    document.getElementById('filter-week').classList.toggle('d-none', mode !== 'week');
    document.getElementById('filter-range').classList.toggle('d-none', mode !== 'range');
    document.getElementById('btn-mode-week').classList.toggle('active', mode === 'week');
    document.getElementById('btn-mode-range').classList.toggle('active', mode === 'range');
};

async function initReportPage() {
    try {
        const { method, href } = API_URLS.wins.list;
        const data = await apiFetch(`${href}?page_size=200`, { method });
        const wins = Array.isArray(data) ? data : (data.results ?? []);
        const sel = document.getElementById('report-week-select');
        wins.forEach(w => {
            const opt = document.createElement('option');
            opt.value = w.id;
            opt.textContent = w.label || `Week ${w.week_number} (${w.week_start_date} – ${w.week_end_date})`;
            sel.appendChild(opt);
        });
    } catch {
        showReportBanner('Failed to load weeks.', 'danger');
    }

    document.getElementById('btn-load-week-report')?.addEventListener('click', () => loadReport('week'));
    document.getElementById('btn-load-range-report')?.addEventListener('click', () => loadReport('range'));
}

async function loadReport(mode) {
    let url = API_URLS.wins.reportData.href;

    if (mode === 'week') {
        const winPk = document.getElementById('report-week-select').value;
        if (!winPk) { showReportBanner('Please select a week.', 'warning'); return; }
        url += `?week_ids=${winPk}`;
    } else {
        const from = document.getElementById('report-date-from').value;
        const to = document.getElementById('report-date-to').value;
        if (!from && !to) { showReportBanner('Please enter at least one date.', 'warning'); return; }
        const params = new URLSearchParams();
        if (from) params.set('date_from', from);
        if (to) params.set('date_to', to);
        url += '?' + params.toString();
    }

    document.getElementById('report-output').classList.add('d-none');
    document.getElementById('report-empty').classList.add('d-none');
    document.getElementById('summary-cards').classList.add('d-none');
    showReportBanner('', '');

    try {
        const data = await apiFetch(url, { method: 'GET' });

        if (!data.rows.length) {
            document.getElementById('report-empty').classList.remove('d-none');
            return;
        }

        // Title
        document.getElementById('report-title').textContent = mode === 'week'
            ? `Weekly Wins — ${data.rows[0]?.week_start_date} to ${data.rows[0]?.week_end_date}`
            : 'Weekly Wins — Date Range Report';

        // Summary cards
        renderSummaryCards(data.summary);

        // Table rows
        const tbody = document.getElementById('report-table-body');
        tbody.innerHTML = data.rows.map(r => `
            <tr>
                <td><strong>${escHtml(r.team_name)}</strong></td>
                <td>Week ${r.week_number}</td>
                <td style="white-space:nowrap">${escHtml(r.week_start_date)} – ${escHtml(r.week_end_date)}</td>
                <td>
                    <div class="fw-semibold">${escHtml(r.title)}</div>
                    ${r.description ? `<div class="text-secondary small">${escHtml(r.description)}</div>` : ''}
                </td>
            </tr>`).join('');

        document.getElementById('report-output').classList.remove('d-none');
    } catch {
        showReportBanner('Failed to load report.', 'danger');
    }
}

function renderSummaryCards(summary) {
    const container = document.getElementById('summary-cards');
    container.innerHTML = summary.map(s => `
        <div class="col-sm-6 col-md-4 col-lg-3">
            <div class="rp-card text-center py-3">
                <div class="summary-card-count">${s.win_count}</div>
                <div class="small text-secondary mt-1">${escHtml(s.team_name)}</div>
            </div>
        </div>`).join('');
    container.classList.remove('d-none');
}

function showReportBanner(msg, type) {
    const el = document.getElementById('report-banner');
    if (!el) return;
    if (!msg) { el.classList.add('d-none'); return; }
    el.className = `alert alert-${type} mb-3`;
    el.textContent = msg;
    el.classList.remove('d-none');
}
