'use strict';

import { apiFetch, escHtml, formatDateTime, showFlash } from './../main.js';
import { API_URLS } from './../urls.js';

const isList      = location.pathname === '/wins/monthly/' || location.pathname === '/wins/monthly';
const isDetail    = typeof window.MONTHLY_WIN_PK !== 'undefined' && !location.pathname.includes('/report/');
const isReport    = typeof window.MONTHLY_WIN_PK !== 'undefined' && location.pathname.includes('/report/');
const isPOPage    = location.pathname.includes('product-owners');

document.addEventListener('DOMContentLoaded', () => {
    if (isPOPage) initPOPage();
    else if (isList) initListPage();
    else if (isReport) initReportPage();
    else if (isDetail) initDetailPage();
});

// ─────────────────────────────────────────────────────────────────────────────
// LIST PAGE
// ─────────────────────────────────────────────────────────────────────────────

let _listPage = 1;

async function initListPage() {
    loadMonthlyWins(1);

    document.getElementById('btn-new-monthly')?.addEventListener('click', async () => {
        document.getElementById('new-monthly-banner').classList.add('d-none');
        document.getElementById('monthly-name').value = '';
        document.getElementById('monthly-phase1-deadline').value = '';
        await loadWeeksPicker();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('newMonthlyModal')).show();
    });

    document.getElementById('btn-create-monthly')?.addEventListener('click', createMonthlyWin);
}

async function loadWeeksPicker() {
    const container = document.getElementById('weeks-picker');
    container.innerHTML = '<p class="text-secondary small mb-0">Loading…</p>';
    try {
        const { href } = API_URLS.wins.list;
        const data = await apiFetch(`${href}?page_size=200`, { method: 'GET' });
        const wins = data.results ?? [];
        if (!wins.length) {
            container.innerHTML = '<p class="text-secondary small mb-0">No weeks found.</p>';
            return;
        }
        container.innerHTML = wins.map(w => `
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="${w.id}" id="wk-${w.id}">
                <label class="form-check-label small" for="wk-${w.id}">
                    ${escHtml(w.label)} <span class="text-secondary">(${w.entry_count} entries)</span>
                </label>
            </div>`).join('');
    } catch {
        container.innerHTML = '<p class="text-danger small mb-0">Failed to load weeks.</p>';
    }
}

async function createMonthlyWin() {
    const name = document.getElementById('monthly-name').value.trim();
    const deadline = document.getElementById('monthly-phase1-deadline').value;
    const checkedWeeks = [...document.querySelectorAll('#weeks-picker input:checked')].map(c => parseInt(c.value));

    if (!name) {
        showListBanner('Name is required.', 'danger');
        return;
    }
    if (!checkedWeeks.length) {
        showListBanner('Select at least one week.', 'danger');
        return;
    }

    const btn = document.getElementById('btn-create-monthly');
    btn.disabled = true; btn.textContent = 'Creating…';
    try {
        const { method, href } = API_URLS.monthly_wins.create;
        const body = { name, win_ids: checkedWeeks };
        if (deadline) body.phase1_deadline = deadline;
        const mw = await apiFetch(href, { method, body: JSON.stringify(body) });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('newMonthlyModal')).hide();
        location.href = `/wins/monthly/${mw.id}/`;
    } catch (err) {
        const msg = err?.name || err?.detail || err?.message || 'Failed to create.';
        document.getElementById('new-monthly-banner').textContent = String(msg);
        document.getElementById('new-monthly-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false; btn.textContent = 'Create';
    }
}

async function loadMonthlyWins(page) {
    _listPage = page;
    const container = document.getElementById('monthly-list-container');
    container.innerHTML = '<p class="text-secondary small">Loading…</p>';
    try {
        const { href } = API_URLS.monthly_wins.list;
        const data = await apiFetch(`${href}?page=${page}&page_size=20`, { method: 'GET' });
        renderMonthlyList(data.results);
        renderPagination(data.pagination, 'monthly-pagination', loadMonthlyWins);
    } catch {
        container.innerHTML = '<p class="text-danger small">Failed to load monthly wins.</p>';
    }
}

const STATUS_BADGE = {
    draft:             '<span class="badge bg-secondary">Draft</span>',
    phase1_open:       '<span class="badge bg-primary">Phase 1 Open</span>',
    phase1_complete:   '<span class="badge bg-info text-dark">Phase 1 Complete</span>',
    phase2_open:       '<span class="badge bg-warning text-dark">Phase 2 Open</span>',
    declared:          '<span class="badge bg-success">Winners Declared</span>',
};

function renderMonthlyList(items) {
    const container = document.getElementById('monthly-list-container');
    if (!items.length) {
        container.innerHTML = '<div class="rp-empty-state"><i class="bi bi-stars fs-2 text-secondary"></i><p class="text-secondary mt-2">No monthly wins yet.</p></div>';
        return;
    }
    container.innerHTML = `
    <div class="table-responsive">
        <table class="rp-table">
            <thead><tr>
                <th>Name</th>
                <th>Status</th>
                <th class="text-center">Weeks</th>
                <th class="text-center">Surveys</th>
                <th>Phase 1 Deadline</th>
                <th></th>
            </tr></thead>
            <tbody>
                ${items.map(m => `
                <tr>
                    <td><strong>${escHtml(m.name)}</strong></td>
                    <td>${STATUS_BADGE[m.status] || escHtml(m.status_display)}</td>
                    <td class="text-center">${m.week_count}</td>
                    <td class="text-center">${m.survey_count}</td>
                    <td>${m.phase1_deadline ? new Date(m.phase1_deadline).toLocaleString('en-GB') : '—'}</td>
                    <td class="text-center">
                        <a href="/wins/monthly/${m.id}/" class="btn btn-ghost-icon btn-sm" title="Open">
                            <i class="bi bi-arrow-right-circle"></i>
                        </a>
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>
    </div>`;
}

function showListBanner(msg, type) {
    const el = document.getElementById('monthly-banner');
    if (!el) return;
    if (!msg) { el.classList.add('d-none'); return; }
    el.className = `alert alert-${type} mb-3`;
    el.textContent = msg;
    el.classList.remove('d-none');
}

// ─────────────────────────────────────────────────────────────────────────────
// DETAIL PAGE
// ─────────────────────────────────────────────────────────────────────────────

const MW_PK = window.MONTHLY_WIN_PK;
let _mw = null;
let _pendingDismissNomPk = null;

async function initDetailPage() {
    await loadMW();

    document.getElementById('btn-confirm-dismiss')?.addEventListener('click', async () => {
        if (!_pendingDismissNomPk) return;
        const reason = document.getElementById('dismiss-reason').value.trim();
        try {
            const { method, href } = API_URLS.monthly_wins.dismissNomination(_pendingDismissNomPk);
            await apiFetch(href, { method, body: JSON.stringify({ reason }) });
            bootstrap.Modal.getOrCreateInstance(document.getElementById('dismissModal')).hide();
            await loadMW();
        } catch (err) {
            showFlash(String(err?.detail || 'Failed to dismiss.'), 'danger');
        }
    });
}

async function loadMW() {
    try {
        const { href } = API_URLS.monthly_wins.detail(MW_PK);
        _mw = await apiFetch(href, { method: 'GET' });
        renderMWDetail(_mw);
    } catch {
        document.getElementById('mw-banner').textContent = 'Failed to load monthly win.';
        document.getElementById('mw-banner').className = 'alert alert-danger mb-3';
    }
}

function renderMWDetail(mw) {
    document.getElementById('mw-title').textContent = mw.name;
    document.getElementById('mw-status').textContent = mw.status_display;

    renderActions(mw);
    renderPhase1Panel(mw);
    renderPhase2Panel(mw);

    if (mw.status === 'phase1_open' || mw.status === 'phase1_complete') {
        loadPhase1Nominations();
    }

    if (mw.status === 'declared') {
        renderWinners(mw.results);
    }
}

function renderActions(mw) {
    const el = document.getElementById('mw-actions');
    const actions = [];

    if (mw.status === 'draft') {
        actions.push(`<button class="btn btn-primary btn-sm" onclick="doLaunchPhase1()">
            <i class="bi bi-1-circle me-1"></i>Launch Phase 1
        </button>`);
    }
    if (mw.status === 'phase1_open') {
        actions.push(`<button class="btn btn-info btn-sm text-dark" onclick="doCompletePhase1()">
            <i class="bi bi-check me-1"></i>Complete Phase 1
        </button>`);
    }
    if (mw.status === 'phase1_complete') {
        actions.push(`<button class="btn btn-warning btn-sm" onclick="doLaunchPhase2()">
            <i class="bi bi-2-circle me-1"></i>Launch Phase 2
        </button>`);
    }
    if (mw.status === 'phase2_open') {
        actions.push(`<button class="btn btn-success btn-sm" onclick="doDeclare()">
            <i class="bi bi-trophy me-1"></i>Declare Winners
        </button>`);
    }
    if (mw.status === 'declared') {
        actions.push(`<a href="/wins/monthly/${MW_PK}/report/" class="btn btn-outline-secondary btn-sm">
            <i class="bi bi-bar-chart-line me-1"></i>View Report
        </a>`);
    }

    el.innerHTML = actions.join('');
}

function renderPhase1Panel(mw) {
    const el = document.getElementById('phase1-surveys');
    const surveys = mw.surveys.filter(s => s.phase === 'phase1');
    if (!surveys.length) {
        el.innerHTML = '<p class="text-secondary small">Phase 1 has not been launched yet.</p>';
        return;
    }
    el.innerHTML = surveys.map(s => `
        <div class="d-flex align-items-center justify-content-between gap-2 mb-2 p-2 border rounded">
            <div>
                <div class="small fw-semibold">${escHtml(s.recipient_name)} <span class="text-secondary">(${escHtml(s.recipient_email)})</span></div>
                <div class="text-secondary" style="font-size:.78rem">${escHtml(s.team_names.join(', '))} · ${s.nomination_count} nominations</div>
            </div>
            <div class="d-flex gap-1 align-items-center">
                ${surveyStatusBadge(s.status)}
                ${s.status === 'pending' ? `
                    <button class="btn btn-ghost-icon btn-sm" title="Send Reminder" onclick="doRemind(${s.id})">
                        <i class="bi bi-bell"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-sm" title="Override (no response)" onclick="doOverride(${s.id})">
                        <i class="bi bi-skip-forward"></i>
                    </button>` : ''}
            </div>
        </div>`).join('');
}

function renderPhase2Panel(mw) {
    const el = document.getElementById('phase2-surveys');
    const surveys = mw.surveys.filter(s => s.phase === 'phase2');
    if (!surveys.length) {
        el.innerHTML = '<p class="text-secondary small">Phase 2 has not been launched yet.</p>';
        return;
    }
    el.innerHTML = surveys.map(s => `
        <div class="d-flex align-items-center justify-content-between gap-2 mb-2 p-2 border rounded">
            <div class="small fw-semibold">${escHtml(s.recipient_name)} <span class="text-secondary">(${escHtml(s.recipient_email)})</span></div>
            <div class="d-flex gap-1 align-items-center">
                ${surveyStatusBadge(s.status)}
                ${s.status === 'pending' ? `
                    <button class="btn btn-ghost-icon btn-sm" title="Send Reminder" onclick="doRemind(${s.id})">
                        <i class="bi bi-bell"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-sm" title="Override" onclick="doOverride(${s.id})">
                        <i class="bi bi-skip-forward"></i>
                    </button>` : ''}
            </div>
        </div>`).join('');
}

function surveyStatusBadge(status) {
    const map = { pending: 'bg-warning text-dark', completed: 'bg-success', overridden: 'bg-secondary' };
    return `<span class="badge ${map[status] || 'bg-secondary'}">${status}</span>`;
}

async function loadPhase1Nominations() {
    const container = document.getElementById('nominations-container');
    container.innerHTML = '<p class="text-secondary small">Loading…</p>';
    try {
        const { href } = API_URLS.monthly_wins.phase1Nominations(MW_PK);
        const noms = await apiFetch(href, { method: 'GET' });
        renderNominations(noms);
    } catch {
        container.innerHTML = '<p class="text-danger small">Failed to load nominations.</p>';
    }
}

function renderNominations(noms) {
    const container = document.getElementById('nominations-container');
    if (!noms.length) {
        container.innerHTML = '<p class="text-secondary small">No nominations yet.</p>';
        return;
    }

    const byCategory = {};
    noms.forEach(n => {
        if (!byCategory[n.category]) byCategory[n.category] = [];
        byCategory[n.category].push(n);
    });

    const catLabels = { delivery: 'Delivery', operational_excellence: 'Operational Excellence' };
    container.innerHTML = Object.entries(byCategory).map(([cat, catNoms]) => `
        <div class="mb-4">
            <h6 class="text-primary mb-2">${catLabels[cat] || cat}</h6>
            <div class="table-responsive">
                <table class="rp-table">
                    <thead><tr><th>Team</th><th>Week</th><th>Win</th><th>By</th><th>Status</th><th></th></tr></thead>
                    <tbody>
                        ${catNoms.map(n => `
                        <tr class="${n.is_dismissed ? 'opacity-50' : ''}">
                            <td>${escHtml(n.entry_team_name)}</td>
                            <td>Week ${n.entry_week_number}</td>
                            <td>${escHtml(n.entry_title)}</td>
                            <td class="text-secondary small">${escHtml(n.survey?.recipient_email || '')}</td>
                            <td>${n.is_dismissed
                                ? `<span class="badge bg-secondary">Dismissed</span>${n.dismissed_reason ? `<div class="text-secondary" style="font-size:.75rem">${escHtml(n.dismissed_reason)}</div>` : ''}`
                                : '<span class="badge bg-success">Active</span>'}</td>
                            <td>
                                ${n.is_dismissed
                                    ? `<button class="btn btn-ghost-icon btn-sm" title="Undismiss" onclick="doUndismiss(${n.id})"><i class="bi bi-arrow-counterclockwise"></i></button>`
                                    : `<button class="btn btn-ghost-icon btn-sm" title="Dismiss" onclick="openDismiss(${n.id})"><i class="bi bi-x-circle"></i></button>`}
                            </td>
                        </tr>`).join('')}
                    </tbody>
                </table>
            </div>
        </div>`).join('');
}

function renderWinners(results) {
    const sec = document.getElementById('winners-section');
    const container = document.getElementById('winners-container');
    if (!results.length) {
        container.innerHTML = '<p class="text-secondary small">No winners declared yet.</p>';
    } else {
        const byCategory = {};
        results.forEach(r => {
            if (!byCategory[r.category]) byCategory[r.category] = [];
            byCategory[r.category].push(r);
        });

        const catLabels = { delivery: 'Delivery', operational_excellence: 'Operational Excellence' };
        const medals = { 1: '🥇', 2: '🥈' };

        container.innerHTML = Object.entries(byCategory).map(([cat, catResults]) => `
            <div class="mb-4">
                <h6 class="text-primary mb-2">${catLabels[cat] || cat}</h6>
                ${catResults.map(r => `
                    <div class="winner-card ${cat === 'delivery' ? 'delivery' : 'ops'} d-flex gap-3 align-items-start mb-2">
                        <div class="rank-badge">${medals[r.rank] || '#' + r.rank}</div>
                        <div>
                            <div class="fw-bold">${escHtml(r.entry_title)}</div>
                            <div class="text-secondary small">${escHtml(r.entry_team_name)} · Week ${r.entry_week_number} · ${r.vote_count} vote${r.vote_count !== 1 ? 's' : ''}</div>
                        </div>
                    </div>`).join('')}
            </div>`).join('');
    }
    sec.classList.remove('d-none');
}

// Action handlers

window.doLaunchPhase1 = async function() {
    if (!confirm('Launch Phase 1? Surveys will be sent to Product Owners by email.')) return;
    try {
        const { method, href } = API_URLS.monthly_wins.launchPhase1(MW_PK);
        _mw = await apiFetch(href, { method });
        renderMWDetail(_mw);
        showFlash('Phase 1 launched. Emails sent.', 'success');
    } catch (err) {
        showFlash(String(err?.detail || err?.error || 'Failed to launch Phase 1.'), 'danger');
    }
};

window.doCompletePhase1 = async function() {
    if (!confirm('Mark Phase 1 as complete? This will allow you to proceed to Phase 2.')) return;
    try {
        const { method, href } = API_URLS.monthly_wins.completePhase1(MW_PK);
        _mw = await apiFetch(href, { method });
        renderMWDetail(_mw);
        showFlash('Phase 1 complete.', 'success');
    } catch (err) {
        showFlash(String(err?.detail || err?.error || 'Failed.'), 'danger');
    }
};

window.doLaunchPhase2 = async function() {
    if (!confirm('Launch Phase 2? Final voting emails will be sent to all Product Owners.')) return;
    try {
        const { method, href } = API_URLS.monthly_wins.launchPhase2(MW_PK);
        _mw = await apiFetch(href, { method });
        renderMWDetail(_mw);
        showFlash('Phase 2 launched. Emails sent.', 'success');
    } catch (err) {
        showFlash(String(err?.detail || err?.error || 'Failed to launch Phase 2.'), 'danger');
    }
};

window.doDeclare = async function() {
    if (!confirm('Declare winners? This will calculate final results from Phase 2 votes.')) return;
    try {
        const { method, href } = API_URLS.monthly_wins.declare(MW_PK);
        _mw = await apiFetch(href, { method });
        renderMWDetail(_mw);
        showFlash('Winners declared!', 'success');
    } catch (err) {
        showFlash(String(err?.detail || err?.error || 'Failed.'), 'danger');
    }
};

window.doRemind = async function(surveyPk) {
    try {
        const { method, href } = API_URLS.monthly_wins.remindSurvey(surveyPk);
        await apiFetch(href, { method });
        showFlash('Reminder sent.', 'success');
        await loadMW();
    } catch (err) {
        showFlash(String(err?.detail || 'Failed to send reminder.'), 'danger');
    }
};

window.doOverride = async function(surveyPk) {
    if (!confirm('Override this survey? It will be marked as completed with no selections.')) return;
    try {
        const { method, href } = API_URLS.monthly_wins.overrideSurvey(surveyPk);
        await apiFetch(href, { method });
        showFlash('Survey overridden.', 'success');
        await loadMW();
    } catch (err) {
        showFlash(String(err?.detail || 'Failed.'), 'danger');
    }
};

window.openDismiss = function(nomPk) {
    _pendingDismissNomPk = nomPk;
    document.getElementById('dismiss-reason').value = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('dismissModal')).show();
};

window.doUndismiss = async function(nomPk) {
    try {
        const { method, href } = API_URLS.monthly_wins.undismissNomination(nomPk);
        await apiFetch(href, { method });
        await loadPhase1Nominations();
    } catch (err) {
        showFlash(String(err?.detail || 'Failed.'), 'danger');
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// REPORT PAGE
// ─────────────────────────────────────────────────────────────────────────────

async function initReportPage() {
    try {
        const { href } = API_URLS.monthly_wins.detail(MW_PK);
        const mw = await apiFetch(href, { method: 'GET' });

        // Summary cards
        const cards = document.getElementById('mw-report-summary');
        cards.innerHTML = `
            <div class="col-sm-4">
                <div class="rp-card text-center">
                    <div class="summary-card-count">${mw.week_count}</div>
                    <div class="small text-secondary mt-1">Weeks Included</div>
                </div>
            </div>
            <div class="col-sm-4">
                <div class="rp-card text-center">
                    <div class="summary-card-count">${mw.surveys.filter(s => s.phase === 'phase1').length}</div>
                    <div class="small text-secondary mt-1">Phase 1 Surveys</div>
                </div>
            </div>
            <div class="col-sm-4">
                <div class="rp-card text-center">
                    <div class="summary-card-count">${mw.surveys.filter(s => s.phase === 'phase2' && s.status === 'completed').length}</div>
                    <div class="small text-secondary mt-1">Phase 2 Completed</div>
                </div>
            </div>`;

        // Winners
        renderReportWinners(mw.results);

        // Phase 1
        renderReportPhase1(mw.surveys.filter(s => s.phase === 'phase1'));

        // Phase 2
        renderReportPhase2(mw.surveys.filter(s => s.phase === 'phase2'));

    } catch {
        document.getElementById('winners-output').textContent = 'Failed to load report.';
    }
}

function renderReportWinners(results) {
    const el = document.getElementById('winners-output');
    if (!results.length) {
        el.innerHTML = '<p class="text-secondary small">Winners not yet declared.</p>';
        return;
    }
    const byCategory = {};
    results.forEach(r => {
        if (!byCategory[r.category]) byCategory[r.category] = [];
        byCategory[r.category].push(r);
    });
    const catLabels = { delivery: 'Delivery', operational_excellence: 'Operational Excellence' };
    const medals = { 1: '🥇', 2: '🥈' };

    el.innerHTML = Object.entries(byCategory).map(([cat, catResults]) => `
        <div class="mb-4">
            <h6 class="mb-2">${catLabels[cat]}</h6>
            ${catResults.map(r => `
                <div class="d-flex gap-3 align-items-start mb-2 p-3 border rounded">
                    <div style="font-size:1.4rem">${medals[r.rank] || '#' + r.rank}</div>
                    <div>
                        <div class="fw-bold">${escHtml(r.entry_title)}</div>
                        <div class="text-secondary small">${escHtml(r.entry_team_name)} · Week ${r.entry_week_number}</div>
                        ${r.entry_description ? `<div class="text-secondary small mt-1">${escHtml(r.entry_description)}</div>` : ''}
                        <div class="small text-muted mt-1">${r.vote_count} vote${r.vote_count !== 1 ? 's' : ''}</div>
                    </div>
                </div>`).join('')}
        </div>`).join('');
}

function renderReportPhase1(surveys) {
    const el = document.getElementById('phase1-output');
    if (!surveys.length) { el.innerHTML = '<p class="text-secondary small">No Phase 1 surveys.</p>'; return; }
    el.innerHTML = `
        <div class="table-responsive">
            <table class="rp-table">
                <thead><tr><th>Product Owner</th><th>Teams</th><th>Nominations</th><th>Status</th><th>Completed</th></tr></thead>
                <tbody>
                    ${surveys.map(s => `
                    <tr>
                        <td>${escHtml(s.recipient_name)}<div class="text-secondary small">${escHtml(s.recipient_email)}</div></td>
                        <td class="small">${escHtml(s.team_names.join(', '))}</td>
                        <td class="text-center">${s.nomination_count}</td>
                        <td>${surveyStatusBadge(s.status)}</td>
                        <td class="small">${s.completed_at ? new Date(s.completed_at).toLocaleString('en-GB') : '—'}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

function renderReportPhase2(surveys) {
    const el = document.getElementById('phase2-output');
    if (!surveys.length) { el.innerHTML = '<p class="text-secondary small">Phase 2 not launched yet.</p>'; return; }
    el.innerHTML = `
        <div class="table-responsive">
            <table class="rp-table">
                <thead><tr><th>Product Owner</th><th>Status</th><th>Completed</th><th>Reminders</th></tr></thead>
                <tbody>
                    ${surveys.map(s => `
                    <tr>
                        <td>${escHtml(s.recipient_name)}<div class="text-secondary small">${escHtml(s.recipient_email)}</div></td>
                        <td>${surveyStatusBadge(s.status)}</td>
                        <td class="small">${s.completed_at ? new Date(s.completed_at).toLocaleString('en-GB') : '—'}</td>
                        <td class="text-center">${s.reminder_count}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// PRODUCT OWNERS PAGE
// ─────────────────────────────────────────────────────────────────────────────

async function initPOPage() {
    loadPOs();

    document.getElementById('btn-add-po')?.addEventListener('click', async () => {
        document.getElementById('add-po-banner').classList.add('d-none');
        await loadPOModalOptions();
        bootstrap.Modal.getOrCreateInstance(document.getElementById('addPOModal')).show();
    });

    document.getElementById('btn-save-po')?.addEventListener('click', savePO);
}

async function loadPOModalOptions() {
    // Load teams
    const teamSel = document.getElementById('po-team');
    teamSel.innerHTML = '<option value="">— select team —</option>';
    try {
        const data = await apiFetch(`${API_URLS.delivery_teams.list.href}?page_size=200&is_active=true`, { method: 'GET' });
        const teams = Array.isArray(data) ? data : (data.results ?? []);
        teams.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name;
            teamSel.appendChild(opt);
        });
    } catch { /* ignore */ }

    // Load users
    const userSel = document.getElementById('po-user');
    userSel.innerHTML = '<option value="">— select user —</option>';
    try {
        const data = await apiFetch('/api/v1/users/?page_size=200', { method: 'GET' });
        const users = Array.isArray(data) ? data : (data.results ?? []);
        users.forEach(u => {
            const opt = document.createElement('option');
            opt.value = u.id;
            opt.textContent = `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email;
            userSel.appendChild(opt);
        });
    } catch { /* ignore */ }
}

async function loadPOs() {
    const container = document.getElementById('po-container');
    container.innerHTML = '<p class="text-secondary small">Loading…</p>';
    try {
        const data = await apiFetch(API_URLS.team_product_owners.list.href, { method: 'GET' });
        renderPOList(data);
    } catch {
        container.innerHTML = '<p class="text-danger small">Failed to load product owners.</p>';
    }
}

function renderPOList(items) {
    const container = document.getElementById('po-container');
    if (!items.length) {
        container.innerHTML = '<div class="rp-empty-state"><i class="bi bi-people fs-2 text-secondary"></i><p class="text-secondary mt-2">No product owners configured yet.</p></div>';
        return;
    }
    container.innerHTML = `
        <div class="table-responsive">
            <table class="rp-table">
                <thead><tr><th>Team</th><th>Product Owner</th><th>Email</th><th>Active</th><th></th></tr></thead>
                <tbody>
                    ${items.map(p => `
                    <tr>
                        <td><strong>${escHtml(p.team_name)}</strong></td>
                        <td>${escHtml(p.user_name)}</td>
                        <td>${escHtml(p.user_email)}</td>
                        <td>${p.is_active ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-secondary">Inactive</span>'}</td>
                        <td>
                            <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm" title="Remove" onclick="removePO(${p.id})">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

async function savePO() {
    const team = document.getElementById('po-team').value;
    const user = document.getElementById('po-user').value;
    if (!team || !user) {
        document.getElementById('add-po-banner').textContent = 'Both Team and User are required.';
        document.getElementById('add-po-banner').classList.remove('d-none');
        return;
    }
    const btn = document.getElementById('btn-save-po');
    btn.disabled = true; btn.textContent = 'Saving…';
    try {
        const { method, href } = API_URLS.team_product_owners.create;
        await apiFetch(href, { method, body: JSON.stringify({ team, user }) });
        bootstrap.Modal.getOrCreateInstance(document.getElementById('addPOModal')).hide();
        await loadPOs();
        showFlash('Product owner assigned.', 'success');
    } catch (err) {
        document.getElementById('add-po-banner').textContent = String(err?.detail || 'Failed.');
        document.getElementById('add-po-banner').classList.remove('d-none');
    } finally {
        btn.disabled = false; btn.textContent = 'Assign';
    }
}

window.removePO = async function(pk) {
    if (!confirm('Remove this product owner assignment?')) return;
    try {
        const { method, href } = API_URLS.team_product_owners.delete(pk);
        await apiFetch(href, { method });
        await loadPOs();
    } catch {
        showFlash('Failed to remove.', 'danger');
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function renderPagination(p, containerId, loadFn) {
    const el = document.getElementById(containerId);
    if (!el || p.total_pages <= 1) { if (el) el.innerHTML = ''; return; }
    el.innerHTML = `
        <button class="btn btn-outline-secondary btn-sm" ${p.current_page <= 1 ? 'disabled' : ''} id="${containerId}-prev">
            <i class="bi bi-chevron-left"></i> Prev
        </button>
        <span class="text-secondary small">Page ${p.current_page} of ${p.total_pages}</span>
        <button class="btn btn-outline-secondary btn-sm" ${p.current_page >= p.total_pages ? 'disabled' : ''} id="${containerId}-next">
            Next <i class="bi bi-chevron-right"></i>
        </button>`;
    el.querySelector(`#${containerId}-prev`)?.addEventListener('click', () => loadFn(_listPage - 1));
    el.querySelector(`#${containerId}-next`)?.addEventListener('click', () => loadFn(_listPage + 1));
}
