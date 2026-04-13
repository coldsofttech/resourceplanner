'use strict';

/**
 * team_projects_panel.js
 * Renders a paginated list of active projects for a delivery team
 * inside the team detail view.
 *
 * Usage:
 *   import { initTeamProjectsPanel } from './team_projects_panel.js';
 *
 *   initTeamProjectsPanel({
 *       tbodyId:             'team-projects-tbody',
 *       paginationBarId:     'team-projects-pagination-bar',
 *       paginationInfoId:    'team-projects-pagination-info',
 *       paginationControlsId:'team-projects-pagination-controls',
 *       teamId:              teamPk,
 *       newProjectHref:      '/projects/new/',
 *   });
 */

import { apiFetch, escHtml } from './main.js';
import { URLS, API_URLS } from './urls.js';

const PAGE_SIZE = 20;

export function initTeamProjectsPanel({
    tbodyId,
    paginationBarId,
    paginationInfoId,
    paginationControlsId,
    teamId,
    newProjectHref,
}) {
    let currentPage = 1;

    const tbody = document.getElementById(tbodyId);
    const paginationBar = document.getElementById(paginationBarId);
    const paginationInfo = document.getElementById(paginationInfoId);
    const paginationControls = document.getElementById(paginationControlsId);

    loadProjects();

    async function loadProjects() {
        if (!tbody) return;
        _renderLoading(tbody);

        try {
            const url = `${API_URLS.delivery_teams.projects(teamId).href}?page=${currentPage}&page_size=${PAGE_SIZE}`;
            const data = await apiFetch(url, { method: 'GET' });
            const results = data.results ?? [];
            const pagination = data.pagination ?? {};

            if (!results.length) {
                _renderEmpty(tbody, newProjectHref);
            } else {
                tbody.innerHTML = results.map((p) => _row(p)).join('');
            }

            _renderPagination(
                pagination,
                paginationBar,
                paginationInfo,
                paginationControls,
                (p) => {
                    currentPage = p;
                    loadProjects();
                },
            );
        } catch (_err) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-secondary py-3">Failed to load projects.</td></tr>`;
        }
    }
}

/* ── Row renderer ────────────────────────────────────────── */

function _statusBadge(status, label) {
    if (!status) return '—';
    return `<span class="rp-badge rp-badge-status--${status.toLowerCase()}">${escHtml(label || status)}</span>`;
}

function _levelBadge(value, label) {
    if (!value) return '<span class="text-muted">-</span>';
    const key = value.toLowerCase().replace(/_/g, '-');
    return `<span class="rp-badge rp-badge-level--${key}">${escHtml(label || value)}</span>`;
}

function _row(p) {
    console.log(p);
    const programme = p.programme_name ? escHtml(p.programme_name) : '-';
    const roleBadge = p.assigned_team
        ? '<span class="rp-badge rp-badge--success">Assigned</span>'
        : '<span class="rp-badge rp-badge--info">Collaborator</span>';

    return `
        <tr>
            <td>
                <a href="${URLS.projects.detail(p.id)}" class="rp-link">${escHtml(p.name)}</a>
            </td>
            <td>${programme}</td>
            <td>${escHtml(p.project_type_name)}</td>
            <td>${_statusBadge(p.status, p.status_display)}</td>
            <td>${_levelBadge(p.priority, p.priority_display)}</td>
            <td>${roleBadge}</td>
            <td class="text-center">
                <a href="${URLS.projects.detail(p.id)}" class="btn btn-ghost-icon btn-sm" title="View">
                    <i class="bi bi-eye"></i>
                </a>
            </td>
        </tr>`;
}

/* ── Helpers ─────────────────────────────────────────────── */

function _renderLoading(tbody) {
    tbody.innerHTML = `
        <tr>
            <td colspan="6" class="text-center py-3 text-secondary">
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Loading projects…
            </td>
        </tr>`;
}

function _renderEmpty(tbody, newProjectHref) {
    tbody.innerHTML = `
        <tr>
            <td colspan="6" class="text-center py-4 text-secondary">
                <i class="bi bi-folder fs-4 d-block mb-2 opacity-50"></i>
                No active projects found.
                ${
                    newProjectHref
                        ? `<a href="${newProjectHref}" class="d-block small mt-1 rp-link">Create a project</a>`
                        : ''
                }
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
        const end = Math.min(current_page * PAGE_SIZE, total_count);
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
        controls.querySelectorAll('button[data-page]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const p = parseInt(btn.dataset.page);
                if (p >= 1 && p <= total_pages) goToPage(p);
            });
        });
    }
}
