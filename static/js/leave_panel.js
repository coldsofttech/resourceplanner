'use strict';

/**
 * leave_panel.js
 * Shared utility: renders a paginated list of MemberLeave records
 * inside a detail view (team member or delivery team).
 *
 * Usage — member context:
 *   import { initLeavesPanel } from './../leave_panel.js';
 *
 *   initLeavesPanel({
 *       apiUrl:              API_URLS.team_members.leaves(memberPk).href,
 *       tbodyId:             'member-leaves-tbody',
 *       paginationBarId:     'member-leaves-pagination-bar',
 *       paginationInfoId:    'member-leaves-pagination-info',
 *       paginationControlsId:'member-leaves-pagination-controls',
 *       includePastToggleId: 'member-leaves-include-past',
 *       showMemberColumn:    false,
 *   });
 *
 * Usage — team context:
 *   initLeavesPanel({
 *       apiUrl:              API_URLS.delivery_teams.leaves(teamPk).href,
 *       tbodyId:             'team-leaves-tbody',
 *       paginationBarId:     'team-leaves-pagination-bar',
 *       paginationInfoId:    'team-leaves-pagination-info',
 *       paginationControlsId:'team-leaves-pagination-controls',
 *       includePastToggleId: 'team-leaves-include-past',
 *       showMemberColumn:    true,
 *   });
 */

import { apiFetch, escHtml } from './main.js';
import { URLS } from './urls.js';

const PAGE_SIZE = 15;

// Number of columns varies by context
const COLS_WITH_MEMBER    = 6;   // Member | Start | End | Days | Type | Actions
const COLS_WITHOUT_MEMBER = 5;   // Start  | End   | Days | Type | Actions

export function initLeavesPanel({
    apiUrl,
    tbodyId,
    paginationBarId,
    paginationInfoId,
    paginationControlsId,
    includePastToggleId,
    showMemberColumn = false,
}) {
    let currentPage  = 1;
    let includePast  = false;

    const tbody       = document.getElementById(tbodyId);
    const paginationBar      = document.getElementById(paginationBarId);
    const paginationInfo     = document.getElementById(paginationInfoId);
    const paginationControls = document.getElementById(paginationControlsId);

    const pastToggle = includePastToggleId
        ? document.getElementById(includePastToggleId)
        : null;

    if (pastToggle) {
        pastToggle.addEventListener('change', () => {
            includePast = pastToggle.checked;
            currentPage = 1;
            load();
        });
    }

    load();

    async function load() {
        if (!tbody) return;
        _renderLoading(tbody, showMemberColumn);

        try {
            const include = includePast ? 'past' : '';
            const url = `${apiUrl}?page=${currentPage}&page_size=${PAGE_SIZE}${include ? `&include=${include}` : ''}`;
            const data = await apiFetch(url, { method: 'GET' });
            const results    = data.results    ?? [];
            const pagination = data.pagination ?? {};

            if (!results.length) {
                _renderEmpty(tbody, showMemberColumn, includePast);
            } else {
                tbody.innerHTML = results.map(leave =>
                    showMemberColumn ? _rowWithMember(leave) : _rowWithoutMember(leave)
                ).join('');
            }

            _renderPagination(
                pagination, paginationBar, paginationInfo, paginationControls,
                (p) => { currentPage = p; load(); }
            );
        } catch (_err) {
            const cols = showMemberColumn ? COLS_WITH_MEMBER : COLS_WITHOUT_MEMBER;
            if (tbody) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="${cols}" class="text-center text-secondary py-3">
                            Failed to load leave records.
                        </td>
                    </tr>`;
            }
        }
    }
}

/* ── Row renderers ───────────────────────────────────────── */

function _typeBadge(leave) {
    if (!leave.is_half_day) return '<span class="rp-badge">Full day</span>';
    const period = leave.half_day_period ? ` (${escHtml(leave.half_day_period)})` : '';
    return `<span class="rp-badge rp-badge--muted">Half-day${period}</span>`;
}

function _actions(leave) {
    return `
        <div class="d-flex justify-content-center gap-1">
            <a href="${URLS.leaves.detail(leave.id)}"
               class="btn btn-ghost-icon btn-sm" title="View leave">
                <i class="bi bi-eye"></i>
            </a>
            <a href="${URLS.leaves.edit(leave.id)}"
               class="btn btn-ghost-icon btn-sm" title="Edit leave">
                <i class="bi bi-pencil"></i>
            </a>
        </div>`;
}

function _rowWithMember(leave) {
    const memberName = leave.member_name ?? '—';
    const memberId   = leave.member
    const memberCell = memberId
        ? `<a href="${URLS.team_members.detail(memberId)}" class="rp-link">${escHtml(memberName)}</a>`
        : escHtml(memberName);

    return `
        <tr data-leave-id="${leave.id}">
            <td>${memberCell}</td>
            <td>${escHtml(leave.start_date ?? '—')}</td>
            <td>${escHtml(leave.end_date   ?? '—')}</td>
            <td>${leave.days != null ? leave.days : '—'}</td>
            <td>${_typeBadge(leave)}</td>
            <td class="text-center">${_actions(leave)}</td>
        </tr>`;
}

function _rowWithoutMember(leave) {
    return `
        <tr data-leave-id="${leave.id}">
            <td>${escHtml(leave.start_date ?? '—')}</td>
            <td>${escHtml(leave.end_date   ?? '—')}</td>
            <td>${leave.days != null ? leave.days : '—'}</td>
            <td>${_typeBadge(leave)}</td>
            <td class="text-center">${_actions(leave)}</td>
        </tr>`;
}

/* ── Helpers ─────────────────────────────────────────────── */

function _renderLoading(tbody, showMemberColumn) {
    const cols = showMemberColumn ? COLS_WITH_MEMBER : COLS_WITHOUT_MEMBER;
    tbody.innerHTML = `
        <tr>
            <td colspan="${cols}" class="text-center py-3 text-secondary">
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Loading leave records…
            </td>
        </tr>`;
}

function _renderEmpty(tbody, showMemberColumn, includePast) {
    const cols = showMemberColumn ? COLS_WITH_MEMBER : COLS_WITHOUT_MEMBER;
    const msg  = includePast
        ? 'No leave records found.'
        : 'No upcoming leave records. Toggle "Include past" to see historical records.';
    tbody.innerHTML = `
        <tr>
            <td colspan="${cols}" class="text-center py-4 text-secondary">
                <i class="bi bi-calendar-x fs-4 d-block mb-2 opacity-50"></i>
                <span class="small">${msg}</span>
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
            html += `
                <li class="page-item ${p === current_page ? 'active' : ''}">
                    <button class="page-link" data-page="${p}">${p}</button>
                </li>`;
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