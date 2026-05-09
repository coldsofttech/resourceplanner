'use strict';

import {
    apiFetch,
    escHtml,
    getPkFromUrl,
    setPageTitle,
} from './../main.js';
import { API_URLS } from './../urls.js';

const planPk = getPkFromUrl('resource-plans');
const versionPk = getPkFromUrl('versions');

const PAGE_SIZE = 25;

let _allData = [];
let _filtered = [];
let _currentPage = 1;
let _sortCol = 'sprint';
let _sortAsc = true;
let _editingId = null;

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
    if (!planPk || !versionPk) return;

    try {
        const ver = await apiFetch(API_URLS.rp_versions.detail(planPk, versionPk).href);
        document.getElementById('pl-plan-name').textContent = ver.plan_name ?? '—';
        document.getElementById('pl-version-badge').innerHTML =
            `<span class="badge bg-secondary">v${ver.version}</span>`;
        setPageTitle(`Placeholder Leaves — ${ver.plan_name ?? ''}`);
        const bc = document.getElementById('pl-breadcrumb');
        if (bc) bc.innerHTML =
            `<a href="/resource-plans/${planPk}/" class="text-decoration-none text-secondary">Resource Plans</a>`;
    } catch (_) {}

    await _loadTeams();
    await _loadData();
    _bindControls();
}

// ── Teams filter dropdown ─────────────────────────────────────────────────────

async function _loadTeams() {
    try {
        const teams = await apiFetch(API_URLS.rp_versions.grid.teams(planPk, versionPk).href);
        const sel = document.getElementById('pl-team-filter');
        teams.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name;
            sel.appendChild(opt);
        });
    } catch (_) {}
}

// ── Load data ─────────────────────────────────────────────────────────────────

async function _loadData() {
    document.getElementById('pl-loading').classList.remove('d-none');
    document.getElementById('pl-empty').classList.add('d-none');
    document.getElementById('pl-table-wrap').classList.add('d-none');

    try {
        const url = API_URLS.rp_versions.placeholder_leaves.list(planPk, versionPk).href;
        _allData = await apiFetch(url);
    } catch (_) {
        _allData = [];
    }

    document.getElementById('pl-loading').classList.add('d-none');
    _applyFilters();
}

// ── Controls binding ──────────────────────────────────────────────────────────

function _bindControls() {
    document.getElementById('pl-search')?.addEventListener('input', () => { _currentPage = 1; _applyFilters(); });
    document.getElementById('pl-team-filter')?.addEventListener('change', () => { _currentPage = 1; _applyFilters(); });
    document.getElementById('pl-source-filter')?.addEventListener('change', () => { _currentPage = 1; _applyFilters(); });

    document.querySelectorAll('.pl-col-sort').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.col;
            if (_sortCol === col) { _sortAsc = !_sortAsc; } else { _sortCol = col; _sortAsc = true; }
            _currentPage = 1;
            _applyFilters();
        });
    });

    document.getElementById('pl-edit-save-btn')?.addEventListener('click', _saveEdit);
}

// ── Filter, sort, paginate ────────────────────────────────────────────────────

function _applyFilters() {
    const search = (document.getElementById('pl-search')?.value ?? '').toLowerCase().trim();
    const teamId = document.getElementById('pl-team-filter')?.value ?? '';
    const source = document.getElementById('pl-source-filter')?.value ?? '';

    let data = _allData;
    if (search) {
        data = data.filter(p =>
            (p.member_name ?? '').toLowerCase().includes(search) ||
            (p.sprint_name ?? '').toLowerCase().includes(search)
        );
    }
    if (teamId) {
        data = data.filter(p => String(p.team_id ?? '') === teamId);
    }
    if (source === 'auto') data = data.filter(p => p.is_auto);
    if (source === 'manual') data = data.filter(p => !p.is_auto);

    data = [...data].sort((a, b) => {
        let va, vb;
        if (_sortCol === 'member') { va = a.member_name ?? ''; vb = b.member_name ?? ''; }
        else if (_sortCol === 'days') { va = parseFloat(a.days); vb = parseFloat(b.days); }
        else { va = a.sprint_name ?? ''; vb = b.sprint_name ?? ''; }
        if (typeof va === 'number') return _sortAsc ? va - vb : vb - va;
        return _sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    });

    _filtered = data;
    _render();
}

function _render() {
    const total = _filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (_currentPage > totalPages) _currentPage = totalPages;

    const start = (_currentPage - 1) * PAGE_SIZE;
    const page = _filtered.slice(start, start + PAGE_SIZE);

    const countLabel = document.getElementById('pl-count-label');
    if (countLabel) countLabel.textContent = total === _allData.length
        ? `${total} record${total !== 1 ? 's' : ''}`
        : `${total} of ${_allData.length} records`;

    const empty = document.getElementById('pl-empty');
    const wrap  = document.getElementById('pl-table-wrap');

    if (!total) {
        empty?.classList.remove('d-none');
        wrap?.classList.add('d-none');
        return;
    }
    empty?.classList.add('d-none');
    wrap?.classList.remove('d-none');

    const tbody = document.getElementById('pl-tbody');
    tbody.innerHTML = page.map(p => {
        const badge = p.is_auto
            ? '<span class="badge bg-secondary" style="font-size:.68rem">Auto</span>'
            : '<span class="badge bg-info text-dark" style="font-size:.68rem">Manual</span>';
        return `<tr>
            <td style="font-size:.82rem">${escHtml(p.member_name ?? '—')}</td>
            <td style="font-size:.82rem">${escHtml(p.sprint_name ?? '—')}</td>
            <td class="text-center" style="font-size:.82rem">${p.days}</td>
            <td class="text-center">${badge}</td>
            <td style="font-size:.82rem">${escHtml(p.notes ?? '')}</td>
            <td class="text-end">
                <button class="btn btn-xs btn-outline-primary py-0 px-1 js-edit"
                    data-id="${p.id}" data-member="${escHtml(p.member_name ?? '')}"
                    data-sprint="${escHtml(p.sprint_name ?? '')}"
                    data-days="${p.days}" data-notes="${escHtml(p.notes ?? '')}">
                    <i class="bi bi-pencil" style="font-size:.75rem"></i>
                </button>
                <button class="btn btn-xs btn-outline-danger py-0 px-1 js-delete"
                    data-id="${p.id}" data-member="${escHtml(p.member_name ?? '')}">
                    <i class="bi bi-trash" style="font-size:.75rem"></i>
                </button>
            </td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('.js-edit').forEach(btn => btn.addEventListener('click', () => _openEdit(btn)));
    tbody.querySelectorAll('.js-delete').forEach(btn => btn.addEventListener('click', () => _confirmDelete(btn)));

    _renderPagination(totalPages);
    _renderSortIcons();

    // Page info
    const pageInfo = document.getElementById('pl-page-info');
    if (pageInfo) pageInfo.textContent = total > PAGE_SIZE
        ? `Showing ${start + 1}–${Math.min(start + PAGE_SIZE, total)} of ${total}`
        : '';
}

function _renderPagination(totalPages) {
    const ul = document.getElementById('pl-pagination');
    if (!ul) return;
    if (totalPages <= 1) { ul.innerHTML = ''; return; }

    let html = `<li class="page-item${_currentPage === 1 ? ' disabled' : ''}">
        <button class="page-link" data-pg="${_currentPage - 1}">&laquo;</button></li>`;

    const window = 2;
    for (let p = 1; p <= totalPages; p++) {
        if (p === 1 || p === totalPages || Math.abs(p - _currentPage) <= window) {
            html += `<li class="page-item${p === _currentPage ? ' active' : ''}">
                <button class="page-link" data-pg="${p}">${p}</button></li>`;
        } else if (Math.abs(p - _currentPage) === window + 1) {
            html += `<li class="page-item disabled"><span class="page-link">…</span></li>`;
        }
    }

    html += `<li class="page-item${_currentPage === totalPages ? ' disabled' : ''}">
        <button class="page-link" data-pg="${_currentPage + 1}">&raquo;</button></li>`;

    ul.innerHTML = html;
    ul.querySelectorAll('[data-pg]').forEach(btn => {
        btn.addEventListener('click', () => { _currentPage = parseInt(btn.dataset.pg); _render(); });
    });
}

function _renderSortIcons() {
    ['member', 'sprint', 'days'].forEach(col => {
        const el = document.getElementById(`pl-sort-${col}`);
        if (!el) return;
        if (_sortCol === col) {
            el.className = _sortAsc ? 'bi bi-arrow-up text-primary' : 'bi bi-arrow-down text-primary';
        } else {
            el.className = 'bi bi-arrow-down-up text-secondary';
        }
    });
}

// ── Edit ──────────────────────────────────────────────────────────────────────

function _openEdit(btn) {
    _editingId = btn.dataset.id;
    document.getElementById('pl-edit-member').textContent = btn.dataset.member;
    document.getElementById('pl-edit-sprint').textContent = btn.dataset.sprint;
    document.getElementById('pl-edit-days').value = btn.dataset.days;
    document.getElementById('pl-edit-notes').value = btn.dataset.notes;
    document.getElementById('pl-edit-err').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('pl-edit-modal')).show();
}

async function _saveEdit() {
    if (!_editingId) return;
    const errEl = document.getElementById('pl-edit-err');
    errEl.classList.add('d-none');

    const days = parseFloat(document.getElementById('pl-edit-days').value);
    const notes = document.getElementById('pl-edit-notes').value.trim();

    if (isNaN(days) || days < 0) {
        errEl.textContent = 'Days must be a non-negative number.';
        errEl.classList.remove('d-none');
        return;
    }

    const btn = document.getElementById('pl-edit-save-btn');
    btn.disabled = true;
    try {
        const { href } = API_URLS.rp_versions.placeholder_leaves.update(planPk, versionPk, _editingId);
        await apiFetch(href, { method: 'PATCH', body: JSON.stringify({ days, notes: notes || null }) });
        bootstrap.Modal.getInstance(document.getElementById('pl-edit-modal')).hide();
        await _loadData();
    } catch (err) {
        errEl.textContent = err?.message ?? 'Save failed.';
        errEl.classList.remove('d-none');
    } finally {
        btn.disabled = false;
    }
}

// ── Delete ────────────────────────────────────────────────────────────────────

async function _confirmDelete(btn) {
    const id = btn.dataset.id;
    const member = btn.dataset.member;
    if (!confirm(`Delete placeholder leave for ${member}?`)) return;
    try {
        const { href } = API_URLS.rp_versions.placeholder_leaves.delete(planPk, versionPk, id);
        await apiFetch(href, { method: 'DELETE' });
        await _loadData();
    } catch (err) {
        alert(err?.message ?? 'Delete failed.');
    }
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
