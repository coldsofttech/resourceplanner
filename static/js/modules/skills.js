'use strict';

import {
    apiFetch, showFlash, formatDateTime, setPageTitle, escHtml, escAttr,
    getPkFromUrl, isSubPathUrl, clearErrors, setSubmitting, extractFieldMessage,
    showBanner, applyErrors
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { loadSpecs, initImportDropZone } from './../import.js';
import { exportToCsv, exportToPdf } from './../export.js';

let fetcher = null;

const skillPk = getPkFromUrl('skills');
const isEdit = isSubPathUrl('skills', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const skillsTable = document.getElementById('skills-table');
    if (skillsTable) {
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

    const formEl = document.getElementById('skill-form');
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
    setPageTitle("Skills");
    renderStatistics();
    renderStatusFilterOptions();

    const renderer = initRenderer({
        tbodyId: 'skills-tbody',
        colspan: 5,
        itemLabel: 'skills',
        rowTemplate: renderSkillRow,
        emptyState: {
            message: 'No skills yet.',
            link: {
                href: URLS.skills.new,
                label: 'Create the first one',
            },
        },
        filterEmptyState: {
            message: 'No skills match your filters.',
            link: {
                href: URLS.skills.new,
                label: 'Create a new skill',
            },
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.skills.list.href,
        pageSize: 20,
        searchInputId: 'skill-search',
        filters: [
            {
                id: 'status-filter',
                param: 'is_active',
            },
        ],
        onLoadStart: () => renderer.renderLoading('Loading skills...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load skills. Please refresh the page.'),
    });

    initSorting({
        tableId: 'skills-table',
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
        const { method, href } = API_URLS.skills.stats;
        const stats = await apiFetch(href, { method });

        document.getElementById('stat-total-skills').textContent = stats.total_skills ?? '-';
        document.getElementById('stat-active-skills').textContent = stats.active_skills ?? '-';
        document.getElementById('stat-inactive-skills').textContent = stats.inactive_skills ?? '-';
        document.getElementById('stat-unassigned-skills').textContent = stats.unassigned_skills ?? '-';
    } catch (err) {
        console.error('[renderStatistics] Failed to load statistics: ', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.skills.options;
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

function renderSkillRow(skill) {
    return `
        <tr data-skill-id="${skill.id}">
            <td>
                <a href="${URLS.skills.detail(skill.id)}"
                   class="rp-link">
                   <span class="rp-code">${escHtml(skill.skill)}</span>
                </a>
            </td>
            <td class="text-secondary"
                style="max-width: 260px;">
                <span class="rp-truncate">
                    ${escHtml(skill.description ?? '')}
                </span>
            </td>
            <td class="text-center">
                ${skill.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.skills.detail(skill.id)}"
                       class="btn btn-ghost-icon"
                       title="View skill">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.skills.edit(skill.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit skill">
                        <i class="bi bi-pencil"></i>
                    </a>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger"
                            title="Delete skill"
                            onclick="confirmDelete(${skill.id}, '${escAttr(skill.skill)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function onDeleteFromList(id, skill) {
    showFlash(`Skill "${skill}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-skill-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
}

/*
 * Import View
 */
function initImportView() {
    setPageTitle("Import");
    const importBtn        = document.getElementById('import-btn');
    const importResults    = document.getElementById('import-results');
    const importAnotherBtn = document.getElementById('import-another-btn');

    let importFile = null;

    loadSpecs(API_URLS.skills.import_spec.href);
    const dropZoneEl = document.getElementById('drop-zone');

    if (dropZoneEl) {
        const dropZoneApi = initImportDropZone(
            {
                dropZone:   dropZoneEl,
                fileInput:  document.getElementById('csv-file-input'),
                fileInfo:   document.getElementById('file-info'),
                fileNameEl: document.getElementById('file-name'),
                fileSizeEl: document.getElementById('file-size'),
                removeBtn:  document.getElementById('remove-file-btn'),
                submitBtn:  importBtn,
                errorEl:    document.getElementById('file-error'),
                errorMsgEl: document.getElementById('file-error-msg'),
            },
            {
                accept:  '.csv',
                onFile:  file => { importFile = file; },
                onReset: ()   => { importFile = null; },
            }
        );

        importBtn.addEventListener('click', () => {
            if (!importFile) return;

            submitImport(window.location.pathname, importFile, {
                submitBtn: importBtn,
                onSuccess: data => renderImportResults(data),
                onError:   msg  => dropZoneApi.showError(msg),
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
    setPageTitle("New Skill");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'New Skill';
    pageSubtitle.textContent = 'Add a new skill to the configuration';
    submitLabel.textContent  = 'Create skill';
    submitBtn.dataset.originalLabel = 'Create skill';
}

async function initEditView() {
    setPageTitle("Edit Skill");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'Edit Skill';
    pageSubtitle.textContent = 'Loading…';
    submitLabel.textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    try {
        const { method, href } = API_URLS.skills.get(skillPk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        pageSubtitle.textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash(
                'This skill no longer exists. It may have been deleted. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.skills.list; }, 3000);
            return;
        }

        showFlash(
            err.data?.error || 'Could not load skill data. Please try again.',
            'danger'
        );
    }

    submitBtn.disabled = false;
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['skill', 'description']);

    const skillInput = document.getElementById('id_skill');
    if (!skillInput.value.trim()) {
        skillInput.classList.add('is-invalid');
        document.getElementById('skill-error').textContent = 'Skill is required.';
        skillInput.focus();
        return;
    }

    const payload = {
        skill:       skillInput.value.trim(),
        description: document.getElementById('id_description').value.trim(),
        is_active:   document.getElementById('id_is_active').checked,
    };

    const method = isEdit
        ? API_URLS.skills.partial_edit(skillPk).method
        : API_URLS.skills.new.method;
    const url = isEdit
        ? API_URLS.skills.partial_edit(skillPk).href
        : API_URLS.skills.new.href;

    setSubmitting(true);

    try {
        const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.skills.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['skill', 'description']);
            return;
        }
        if (err?.status === 404) {
            showFlash(
                'This skill no longer exists and cannot be saved. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.skills.list; }, 3000);
            return;
        }
        if (err?.status === 503 || err?.status === 500) {
            showFlash(err.data?.error || `Unexpected error (${err.status}). Please try again.`, 'danger');
            return;
        }
        showFlash('Could not reach the server. Check your connection and try again.', 'danger');
    } finally {
        setSubmitting(false);
    }
}

function populateForm(skill) {
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const metadataCard  = document.getElementById('metadata-card');
    const deleteBtnSlot = document.getElementById('delete-btn-slot');

    document.getElementById('id_skill').value       = skill.skill       ?? '';
    document.getElementById('id_description').value = skill.description ?? '';
    document.getElementById('id_is_active').checked = skill.is_active   ?? true;

    pageTitle.textContent    = 'Edit Skill';
    pageSubtitle.innerHTML   = `Updating <strong>${escHtml(skill.skill)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(skill.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(skill.updated_at);
    metadataCard.classList.remove('d-none');

    deleteBtnSlot.innerHTML = `
        <button type="button"
                class="btn btn-outline-danger"
                id="delete-skill-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-skill-btn')
        .addEventListener('click', () =>
            confirmDelete(skill.id, skill.skill, onDeleteFromEdit)
        );
}

function onDeleteFromEdit(id, skill) {
    window.location.href = URLS.skills.list;
}

/*
 * Detail View
 */
async function initDetailView() {
    if (!skillPk) return;
    setPageTitle("Skill");

    try {
        const { method, href } = API_URLS.skills.detail(skillPk);
        const data = await apiFetch(href, { method });
        renderDetailTitle(data);
        renderSkillDetails(data);
    } catch (err) {
        if (err?.status === 404) {
            showFlash(
                'This skill no longer exists. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.skills.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load skill details. Please refresh.', 'danger');
    }
}

function renderDetailTitle(skill) {
    document.getElementById('skill-skill').textContent = skill.skill;
    document.getElementById('skill-status').textContent = skill.is_active ? "Active" : "Inactive";
    document.getElementById('skill-status').classList.add(
        skill.is_active ? "rp-badge--success" : "rp-badge--muted"
    );
    document.getElementById('edit-skill-btn').href = URLS.skills.edit(skillPk);
}

function renderSkillDetails(skill) {
    document.getElementById('skill-description').textContent = skill.description ?? "-";
    document.getElementById('meta-created').textContent = formatDateTime(skill.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(skill.updated_at);
}

/*
 * Delete Modal - Shared
 */
function confirmDelete(id, name, onSuccess) {
    const modal     = document.getElementById('deleteModal');
    const nameEl    = document.getElementById('delete-skill-skill');
    const btn       = document.getElementById('confirm-delete-btn');

    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.skills.delete(id);

    newBtn.addEventListener('click', async () => {
        try {
            newBtn.disabled    = true;
            newBtn.textContent = 'Deleting...';
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, name);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(
                    `Skill "${name}" was not found — it may have already been deleted.`,
                    'warning',
                );
                document.querySelector(`tr[data-team-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete skill "${name}". Please try again.`,
                'error'
            );
        } finally {
            newBtn.disabled    = false;
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
    { key: 'skill', label: 'Skill' },
    { key: 'description', label: 'Description' },
    { key: 'is_active', label: 'Active' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.skills.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `skills-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Skills', filename);
        }
    } catch (_err) {
        showFlash('Export failed. Please try again.', 'error');
    } finally {
        if (btn) {
            btn.disabled  = false;
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