'use strict';

import {
    apiFetch,
    showFlash,
    formatDateTime,
    setPageTitle,
    escHtml,
    escAttr,
    getPkFromUrl,
    isSubPathUrl,
    clearErrors,
    setSubmitting,
    applyErrors,
    hasPerm,
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { loadSpecs, initImportDropZone } from './../import.js';
import { exportToCsv, exportToPdf } from './../export.js';
import { initMembersPanel } from './../member_panel.js';
import { initLeavesPanel } from './../leave_panel.js';
import { initTeamProjectsPanel } from './../project_panel.js';

let fetcher = null;

const teamPk = getPkFromUrl('delivery-teams');
const isEdit = isSubPathUrl('delivery-teams', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const teamsTable = document.getElementById('delivery-teams-table');
    if (teamsTable) {
        initListView();
        return;
    }

    const dropZone = document.getElementById('drop-zone');
    if (dropZone) {
        initImportView();
        return;
    }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) {
        initDetailView();
        return;
    }

    const formEl = document.getElementById('team-form');
    if (formEl) {
        formEl.addEventListener('submit', handleCreateEditSubmit);
        if (isEdit) {
            initEditView();
        } else {
            initCreateView();
        }
    }
});

/*
 * List View
 */
function initListView() {
    setPageTitle('Teams');
    renderStatistics();
    renderStatusFilterOptions();

    const renderer = initRenderer({
        tbodyId: 'teams-tbody',
        colspan: 5,
        itemLabel: 'teams',
        rowTemplate: renderTeamRow,
        emptyState: {
            message: 'No teams yet.',
            link: {
                href: URLS.delivery_teams.new,
                label: 'Create the first one',
            },
        },
        filterEmptyState: {
            message: 'No teams match your filters.',
            link: {
                href: URLS.delivery_teams.new,
                label: 'Create a new team',
            },
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: (page) => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.delivery_teams.list.href,
        pageSize: 20,
        searchInputId: 'team-search',
        filters: [
            {
                id: 'status-filter',
                param: 'is_active',
            },
        ],
        onLoadStart: () => renderer.renderLoading('Loading teams...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load teams. Please refresh the page.'),
    });

    initSorting({
        tableId: 'delivery-teams-table',
        fetcher,
    });

    fetcher.refresh();

    document.getElementById('export-csv').addEventListener('click', () => {
        runListExport('csv');
    });
    document.getElementById('export-pdf').addEventListener('click', () => {
        runListExport('pdf');
    });
}

async function renderStatistics() {
    try {
        const { method, href } = API_URLS.delivery_teams.stats;
        const stats = await apiFetch(href, { method });

        document.getElementById('stat-total-teams').textContent = stats.total_teams ?? '-';
        document.getElementById('stat-active-teams').textContent = stats.active_teams ?? '-';
        document.getElementById('stat-total-members').textContent = stats.total_members ?? '-';
        document.getElementById('stat-unassigned-members').textContent =
            stats.unassigned_members ?? '-';
    } catch (err) {
        console.error('[renderStatistics] Failed to load statistics: ', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.delivery_teams.options;
        const options = await apiFetch(href, { method });
        const statuses = options?.is_active ?? [];

        const select = document.getElementById('status-filter');
        statuses.forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions] Failed to load status filter options: ', err);
    }
}

function renderTeamRow(team) {
    const avatarHtml = team.avatar_svg
        ? `<span style="display:inline-block;width:28px;height:28px;border-radius:50%;overflow:hidden;vertical-align:middle;margin-right:8px;flex-shrink:0">${team.avatar_svg}</span>`
        : '';
    return `
        <tr data-team-id="${team.id}">
            <td>
                <a href="${URLS.delivery_teams.detail(team.id)}"
                   class="rp-link fw-500 d-inline-flex align-items-center">
                    ${avatarHtml}${escHtml(team.name)}
                </a>
            </td>
            <td class="text-secondary"
                style="max-width: 260px;">
                <span class="rp-truncate">
                    ${escHtml(team.description ?? '')}
                </span>
            </td>
            <td class="text-center">
                <span class="fw-500">
                    ${escHtml(team.member_count ?? 0)}
                </span>
            </td>
            <td class="text-center">
                ${
                    team.is_active
                        ? '<span class="rp-badge rp-badge--success">Active</span>'
                        : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.delivery_teams.detail(team.id)}"
                       class="btn btn-ghost-icon"
                       title="View team">
                        <i class="bi bi-eye"></i>
                    </a>
                    ${hasPerm('delivery_teams.change_deliveryteam') ? `
                    <a href="${URLS.delivery_teams.edit(team.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit team">
                        <i class="bi bi-pencil"></i>
                    </a>` : ''}
                    ${hasPerm('delivery_teams.delete_deliveryteam') ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete team"
                            onclick="confirmDelete(${team.id}, '${escAttr(team.name)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, name) {
    showFlash(`Team "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-team-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
}

/*
 * Import View
 */
function initImportView() {
    setPageTitle('Import');
    const importBtn = document.getElementById('import-btn');
    const importResults = document.getElementById('import-results');
    const importAnotherBtn = document.getElementById('import-another-btn');

    let importFile = null;

    loadSpecs(API_URLS.delivery_teams.import_spec.href);
    const dropZoneEl = document.getElementById('drop-zone');

    if (dropZoneEl) {
        const dropZoneApi = initImportDropZone(
            {
                dropZone: dropZoneEl,
                fileInput: document.getElementById('csv-file-input'),
                fileInfo: document.getElementById('file-info'),
                fileNameEl: document.getElementById('file-name'),
                fileSizeEl: document.getElementById('file-size'),
                removeBtn: document.getElementById('remove-file-btn'),
                submitBtn: importBtn,
                errorEl: document.getElementById('file-error'),
                errorMsgEl: document.getElementById('file-error-msg'),
            },
            {
                accept: '.csv',
                onFile: (file) => {
                    importFile = file;
                },
                onReset: () => {
                    importFile = null;
                },
            },
        );

        importBtn.addEventListener('click', () => {
            if (!importFile) return;

            submitImport(window.location.pathname, importFile, {
                submitBtn: importBtn,
                onSuccess: (data) => renderImportResults(data),
                onError: (msg) => dropZoneApi.showError(msg),
            });
        });
    }

    if (importAnotherBtn) {
        importAnotherBtn.addEventListener('click', () => {
            importResults.classList.add('d-none');
            document.getElementById('remove-file-btn')?.click();
        });
    }
}

/*
 * Create & Edit View
 */
function initCreateView() {
    setPageTitle('New Team');
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');
    const submitLabel = document.getElementById('submit-label');
    const submitBtn = document.getElementById('submit-btn');
    pageTitle.textContent = 'New Team';
    pageSubtitle.textContent = 'Add a new team to the business unit';
    submitLabel.textContent = 'Create team';
    submitBtn.dataset.originalLabel = 'Create team';
}

async function initEditView() {
    setPageTitle('Edit Team');
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');
    const submitLabel = document.getElementById('submit-label');
    const submitBtn = document.getElementById('submit-btn');
    pageTitle.textContent = 'Edit Team';
    pageSubtitle.textContent = 'Loading…';
    submitLabel.textContent = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    try {
        const { method, href } = API_URLS.delivery_teams.detail(teamPk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        pageSubtitle.textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash(
                'This team no longer exists. It may have been deleted. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => {
                window.location.href = URLS.delivery_teams.list;
            }, 3000);
            return;
        }

        showFlash(err?.data?.error || 'Could not load team data. Please try again.', 'danger');
    }

    submitBtn.disabled = false;
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['name', 'description']);

    const nameInput = document.getElementById('id_name');
    if (!nameInput.value.trim()) {
        nameInput.classList.add('is-invalid');
        document.getElementById('name-error').textContent = 'Team name is required.';
        nameInput.focus();
        return;
    }

    const payload = {
        name: nameInput.value.trim(),
        description: document.getElementById('id_description').value.trim(),
        is_active: document.getElementById('id_is_active').checked,
    };

    const method = isEdit
        ? API_URLS.delivery_teams.update(teamPk).method
        : API_URLS.delivery_teams.create.method;
    const url = isEdit
        ? API_URLS.delivery_teams.update(teamPk).href
        : API_URLS.delivery_teams.create.href;

    setSubmitting(true);

    try {
        const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.delivery_teams.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['name', 'description']);
            return;
        }
        if (err?.status === 404) {
            showFlash(
                'This team no longer exists and cannot be saved. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => {
                window.location.href = URLS.delivery_teams.list;
            }, 3000);
            return;
        }
        if (err?.status === 503 || err?.status === 500) {
            showFlash(
                err.data?.error || `Unexpected error (${err.status}). Please try again.`,
                'danger',
            );
            return;
        }
        showFlash('Could not reach the server. Check your connection and try again.', 'danger');
    } finally {
        setSubmitting(false);
    }
}

function populateForm(team) {
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');
    const metadataCard = document.getElementById('metadata-card');
    const deleteBtnSlot = document.getElementById('delete-btn-slot');

    document.getElementById('id_name').value = team.name ?? '';
    document.getElementById('id_description').value = team.description ?? '';
    document.getElementById('id_is_active').checked = team.is_active ?? true;

    pageTitle.textContent = 'Edit Team';
    pageSubtitle.innerHTML = `Updating <strong>${escHtml(team.name)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(team.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(team.updated_at);
    metadataCard.classList.remove('d-none');

    deleteBtnSlot.innerHTML = `
        <button type="button"
                class="btn btn-outline-danger"
                id="delete-team-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document
        .getElementById('delete-team-btn')
        .addEventListener('click', () => confirmDelete(team.id, team.name, onDeleteFromEdit));
}

function onDeleteFromEdit(id, name) {
    window.location.href = URLS.delivery_teams.list;
}

/*
 * Detail View
 */
async function initDetailView() {
    if (!teamPk) return;
    setPageTitle('Team');

    try {
        const { method, href } = API_URLS.delivery_teams.detail(teamPk);
        const data = await apiFetch(href, { method });
        renderDetailTitle(data);
        renderTeamDetails(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash('This team no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => {
                window.location.href = URLS.delivery_teams.list;
            }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load team details. Please refresh.', 'danger');
    }

    initLeadershipPanel(teamPk);

    initMembersPanel({
        containerSelector: '#members-panel',
        tbodyId: 'members-tbody',
        paginationBarId: 'members-pagination-bar',
        paginationInfoId: 'members-pagination-info',
        paginationControlsId: 'members-pagination-controls',
        includeInactiveToggleId: 'include-inactive-toggle',
        filterParam: 'team_id',
        filterValue: teamPk,
        columns: 'delivery_teams',
        newMemberHref: URLS.team_members.new,
        extraParams: { exclude_shareable: 'true' },
    });

    initTeamProjectsPanel({
        tbodyId: 'team-projects-tbody',
        paginationBarId: 'team-projects-pagination-bar',
        paginationInfoId: 'team-projects-pagination-info',
        paginationControlsId: 'team-projects-pagination-controls',
        teamId: teamPk,
        newProjectHref: '/projects/',
    });

    initLeavesPanel({
        apiUrl: API_URLS.delivery_teams.leaves(teamPk).href,
        tbodyId: 'team-leaves-tbody',
        paginationBarId: 'team-leaves-pagination-bar',
        paginationInfoId: 'team-leaves-pagination-info',
        paginationControlsId: 'team-leaves-pagination-controls',
        includePastToggleId: 'team-leaves-include-past',
        showMemberColumn: true,
    });
}

function renderDetailTitle(team) {
    document.getElementById('team-name').textContent = team.name;
    document.getElementById('team-status').textContent = team.is_active ? 'Active' : 'Inactive';
    document
        .getElementById('team-status')
        .classList.add(team.is_active ? 'rp-badge--success' : 'rp-badge--muted');
    document.getElementById('edit-team-btn').href = URLS.delivery_teams.edit(teamPk);

    const avatarWrapper = document.getElementById('team-avatar-wrapper');
    if (avatarWrapper && team.avatar_svg) {
        avatarWrapper.innerHTML = team.avatar_svg;
        const svg = avatarWrapper.querySelector('svg');
        if (svg) { svg.style.width = '100%'; svg.style.height = '100%'; }
    }
}

function renderTeamDetails(team) {
    document.getElementById('total-team-members').textContent = team.member_count ?? 0;
    document.getElementById('team-description').textContent = team.description ?? '-';
    document.getElementById('meta-created').textContent = formatDateTime(team.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(team.updated_at);
}

/*
 * Leadership Panel
 */
async function initLeadershipPanel(teamId) {
    const list = document.getElementById('leadership-list');
    if (!list) return;

    let _sharableMembers = [];

    async function loadLeadership() {
        try {
            const { method, href } = API_URLS.delivery_teams.members(teamId);
            const data = await apiFetch(`${href}?page_size=100`, { method });
            const all = data.results ?? [];
            _sharableMembers = all.filter(m => m.role?.is_shareable);
            renderLeadershipList(_sharableMembers);
        } catch (err) {
            list.innerHTML = '<p class="text-secondary small">Could not load leadership members.</p>';
        }
    }

    function renderLeadershipList(members) {
        if (!members.length) {
            list.innerHTML = '<p class="text-secondary small mb-0">No leadership members assigned to this team.</p>';
            return;
        }
        list.innerHTML = `
            <div class="rp-table-wrap">
                <table class="table rp-table mb-0">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Role</th>
                            <th>Location</th>
                            <th class="text-center">Actions</th>
                        </tr>
                    </thead>
                    <tbody>${members.map(m => `
                        <tr>
                            <td>
                                <a href="${URLS.team_members.detail(m.id)}" class="rp-link">
                                    ${escHtml(m.display_name)}
                                </a>
                            </td>
                            <td>${m.role ? escHtml(m.role.role) : '—'}</td>
                            <td>${m.location ? escHtml(`${m.location.city}, ${m.location.country}`) : '—'}</td>
                            <td class="text-center">
                                ${hasPerm('team_members.change_teammember') ? `
                                <button class="btn btn-ghost-icon btn-ghost-icon--danger btn-sm"
                                        title="Remove from this team"
                                        data-member-id="${m.id}"
                                        data-member-name="${escAttr(m.display_name)}">
                                    <i class="bi bi-x-circle"></i>
                                </button>` : ''}
                            </td>
                        </tr>
                    `).join('')}</tbody>
                </table>
            </div>
        `;
        list.querySelectorAll('button[data-member-id]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const memberId   = parseInt(btn.dataset.memberId);
                const memberName = btn.dataset.memberName;
                if (!confirm(`Remove ${memberName} from this team?`)) return;
                btn.disabled = true;
                try {
                    const { method, href } = API_URLS.delivery_teams.unassign_member(teamId, memberId);
                    await apiFetch(href, { method });
                    showFlash(`${memberName} removed from this team.`, 'success');
                    await loadLeadership();
                } catch (err) {
                    showFlash(err?.data?.error || 'Failed to remove member.', 'danger');
                    btn.disabled = false;
                }
            });
        });
    }

    // "Add" button
    document.getElementById('add-leadership-btn')?.addEventListener('click', async () => {
        await _openAddLeadershipModal(teamId, _sharableMembers, loadLeadership);
    });

    await loadLeadership();
}

async function _openAddLeadershipModal(teamId, currentMembers, onSuccess) {
    const modal  = document.getElementById('addLeadershipModal');
    const select = document.getElementById('leadership-member-select');
    const btn    = document.getElementById('confirm-add-leadership-btn');
    if (!modal || !select || !btn) return;

    // Load all active shareable-role members to populate the dropdown.
    try {
        const { method, href } = API_URLS.team_members.list;
        const data = await apiFetch(`${href}?is_active=true&page_size=200`, { method });
        const all  = (data.results ?? []).filter(m => m.role?.is_shareable);
        const currentIds = new Set(currentMembers.map(m => m.id));

        select.innerHTML = '<option value="">— Select a member —</option>';
        all
            .filter(m => !currentIds.has(m.id))
            .forEach(m => {
                const opt = document.createElement('option');
                opt.value       = m.id;
                opt.textContent = `${escHtml(m.display_name)} (${escHtml(m.role?.role ?? '')})`;
                select.appendChild(opt);
            });
    } catch (err) {
        showFlash('Could not load members. Please try again.', 'danger');
        return;
    }

    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    newBtn.addEventListener('click', async () => {
        const memberId = parseInt(select.value);
        if (!memberId) return;
        newBtn.disabled  = true;
        newBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Adding…';
        try {
            const { method, href } = API_URLS.delivery_teams.assign_member(teamId);
            await apiFetch(href, { method, body: JSON.stringify({ member_id: memberId }) });
            bootstrap.Modal.getInstance(modal)?.hide();
            showFlash('Leadership member added.', 'success');
            await onSuccess();
        } catch (err) {
            showFlash(err?.data?.error || 'Failed to add member.', 'danger');
        } finally {
            newBtn.disabled  = false;
            newBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Add';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

/*
 * Delete Modal - Shared
 */
function confirmDelete(id, name, onSuccess) {
    const modal = document.getElementById('deleteModal');
    const nameEl = document.getElementById('delete-team-name');
    const btn = document.getElementById('confirm-delete-btn');

    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.delivery_teams.delete(id);

    newBtn.addEventListener('click', async () => {
        try {
            newBtn.disabled = true;
            newBtn.textContent = 'Deleting...';
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, name);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(
                    `Team "${name}" was not found — it may have already been deleted.`,
                    'warning',
                );
                document.querySelector(`tr[data-team-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete team "${name}". Please try again.`,
                'error',
            );
        } finally {
            newBtn.disabled = false;
            newBtn.textContent = 'Delete';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

/*
 * Export View
 */
const LIST_EXPORT_COLUMNS = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'description', label: 'Description' },
    { key: 'member_count', label: 'Total Members' },
    { key: 'is_active', label: 'Active' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled = true;
        btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.delivery_teams.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `delivery_teams-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Delivery Teams', filename);
        }
    } catch (_err) {
        showFlash('Export failed. Please try again.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

/*
 * Window Exports
 */
window.confirmDelete = confirmDelete;
window.onDeleteFromList = onDeleteFromList;
window.onDeleteFromEdit = onDeleteFromEdit;
