'use strict';

/**
 * member_panel.js
 * Shared utility: renders a paginated, sortable list of team members
 * inside a FK-module's detail view.
 *
 * Usage:
 *   import { initMembersPanel } from './../member_panel.js';
 *
 *   initMembersPanel({
 *       containerSelector: '#members-panel',  // wrapper <div>
 *       tbodyId:           'members-tbody',
 *       filterParam:       'team_id',          // query-param key
 *       filterValue:       teamPk,             // e.g. the current PK
 *       columns:           'delivery_teams',   // 'delivery_teams' | 'other'
 *       newMemberHref:     '/team-members/new/',
 *   });
 */

import { apiFetch, escHtml, escAttr } from './main.js';
import { URLS, API_URLS } from './urls.js';

const PAGE_SIZE = 15;

export function initMembersPanel({
    containerSelector,
    tbodyId,
    paginationBarId,
    paginationInfoId,
    paginationControlsId,
    includeInactiveToggleId,
    filterParam,
    filterValue,
    columns,         // 'delivery_teams' | 'other'
    newMemberHref,
}) {
    let currentPage     = 1;
    let currentSort     = 'display_name';
    let currentDir      = 'asc';
    let includeInactive = false;

    const tbody         = document.getElementById(tbodyId);
    const paginationBar = document.getElementById(paginationBarId);
    const paginationInfo    = document.getElementById(paginationInfoId);
    const paginationControls = document.getElementById(paginationControlsId);

    // Include-inactive toggle
    const inactiveToggle = includeInactiveToggleId
        ? document.getElementById(includeInactiveToggleId)
        : null;
    if (inactiveToggle) {
        inactiveToggle.addEventListener('change', () => {
            includeInactive = inactiveToggle.checked;
            currentPage = 1;
            loadMembers();
        });
    }

    // Column sorting
    const container = document.querySelector(containerSelector);
    if (container) {
        container.querySelectorAll('th[data-sort]').forEach(th => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                const field = th.dataset.sort;
                if (currentSort === field) {
                    currentDir = currentDir === 'asc' ? 'desc' : 'asc';
                } else {
                    currentSort = field;
                    currentDir  = 'asc';
                }
                currentPage = 1;
                // Update sort icons
                container.querySelectorAll('th[data-sort] .rp-sort-icon').forEach(icon => {
                    icon.className = 'bi bi-chevron-expand rp-sort-icon';
                });
                const icon = th.querySelector('.rp-sort-icon');
                if (icon) {
                    icon.className = currentDir === 'asc'
                        ? 'bi bi-chevron-up rp-sort-icon'
                        : 'bi bi-chevron-down rp-sort-icon';
                }
                loadMembers();
            });
        });
    }

    loadMembers();

    async function loadMembers() {
        if (!tbody) return;
        _renderLoading(tbody, columns);

        try {
            let url = `${API_URLS.team_members.list.href}?${filterParam}=${filterValue}&page=${currentPage}&page_size=${PAGE_SIZE}&order_by=${currentSort}&order_dir=${currentDir}`;
            if (!includeInactive) url += '&is_active=true';

            const data = await apiFetch(url, { method: 'GET' });
            const results    = data.results    ?? [];
            const pagination = data.pagination ?? {};

            if (!results.length) {
                _renderEmpty(tbody, columns, newMemberHref);
            } else {
                tbody.innerHTML = results.map(m =>
                    columns === 'delivery_teams'
                        ? _rowDeliveryTeam(m)
                        : _rowOther(m)
                ).join('');
            }

            _renderPagination(pagination, paginationBar, paginationInfo, paginationControls, (p) => {
                currentPage = p;
                loadMembers();
            });
        } catch (_err) {
            if (tbody) {
                const cols = columns === 'delivery_teams' ? 7 : 5;
                tbody.innerHTML = `<tr><td colspan="${cols}" class="text-center text-secondary py-3">
                    Failed to load members.</td></tr>`;
            }
        }
    }
}

/* ── Row renderers ───────────────────────────────────────── */

function _rowDeliveryTeam(m) {
    const loc = m.location ? escHtml(`${m.location.city}, ${m.location.country}`) : '—';
    const skills = (m.skills || []).length
        ? m.skills.map(s => `<span class="rp-badge rp-badge--info me-1">${escHtml(s.skill)}</span>`).join('')
        : '<span class="text-secondary small">—</span>';
    return `
        <tr>
            <td>
                <a href="${URLS.team_members.detail(m.id)}" class="rp-link">${escHtml(m.display_name)}</a>
                ${!m.is_active ? '<span class="rp-badge rp-badge--muted ms-1">Inactive</span>' : ''}
            </td>
            <td>${escHtml(m.email_address)}</td>
            <td>${m.role ? escHtml(m.role.role) : '—'}</td>
            <td>${loc}</td>
            <td>${m.employment_type ? escHtml(m.employment_type.name) : '—'}</td>
            <td>${skills}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.team_members.detail(m.id)}" class="btn btn-ghost-icon btn-sm" title="View">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.team_members.edit(m.id)}" class="btn btn-ghost-icon btn-sm" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </a>
                </div>
            </td>
        </tr>`;
}

function _rowOther(m) {
    const team = m.team ? escHtml(m.team.name) : '<span class="text-secondary">—</span>';
    return `
        <tr>
            <td>
                <a href="${URLS.team_members.detail(m.id)}" class="rp-link">${escHtml(m.display_name)}</a>
                ${!m.is_active ? '<span class="rp-badge rp-badge--muted ms-1">Inactive</span>' : ''}
            </td>
            <td>${escHtml(m.email_address)}</td>
            <td>${team}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.team_members.detail(m.id)}" class="btn btn-ghost-icon btn-sm" title="View">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.team_members.edit(m.id)}" class="btn btn-ghost-icon btn-sm" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </a>
                </div>
            </td>
        </tr>`;
}

/* ── Helpers ─────────────────────────────────────────────── */

function _renderLoading(tbody, columns) {
    const cols = columns === 'delivery_teams' ? 7 : 4;
    tbody.innerHTML = `
        <tr>
            <td colspan="${cols}" class="text-center py-3 text-secondary">
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Loading members…
            </td>
        </tr>`;
}

function _renderEmpty(tbody, columns, newMemberHref) {
    const cols = columns === 'delivery_teams' ? 7 : 4;
    tbody.innerHTML = `
        <tr>
            <td colspan="${cols}" class="text-center py-4 text-secondary">
                <i class="bi bi-people fs-4 d-block mb-2 opacity-50"></i>
                No members found.
                ${newMemberHref
                    ? `<a href="${newMemberHref}" class="d-block small mt-1 rp-link">Add a member</a>`
                    : ''}
            </td>
        </tr>`;
}

function _renderPagination(pagination, bar, info, controls, goToPage) {
    if (!bar) return;
    const { total_count, total_pages, current_page, has_next, has_previous } = pagination;
    if (!total_count || total_pages <= 1) {
        bar.style.display = 'none';
        return;
    }
    bar.style.display = '';

    if (info) {
        const start = (current_page - 1) * PAGE_SIZE + 1;
        const end   = Math.min(current_page * PAGE_SIZE, total_count);
        info.textContent = `${start}–${end} of ${total_count}`;
    }

    if (controls) {
        let html = `
            <li class="page-item ${!has_previous ? 'disabled' : ''}">
                <button class="page-link" data-page="${current_page - 1}">&laquo;</button>
            </li>`;
        for (let p = 1; p <= total_pages; p++) {
            html += `<li class="page-item ${p === current_page ? 'active' : ''}">
                <button class="page-link" data-page="${p}">${p}</button></li>`;
        }
        html += `
            <li class="page-item ${!has_next ? 'disabled' : ''}">
                <button class="page-link" data-page="${current_page + 1}">&raquo;</button>
            </li>`;
        controls.innerHTML = html;
        controls.querySelectorAll('button[data-page]').forEach(btn => {
            btn.addEventListener('click', () => {
                const p = parseInt(btn.dataset.page);
                if (p >= 1 && p <= total_pages) goToPage(p);
            });
        });
    }
}
