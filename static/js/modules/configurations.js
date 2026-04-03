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
import { exportToCsv, exportToPdf } from './../export.js';

let fetcher = null;

const configPk = getPkFromUrl('configurations');
const isEdit = isSubPathUrl('configurations', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const teamsTable = document.getElementById('configs-table');
    if (teamsTable) {
        initListView();
        return;
    }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) {
        initDetailView();
        return;
    }

    const formEl = document.getElementById('config-form');
    if (formEl) {
        formEl.addEventListener('submit', handleCreateEditSubmit);
        if (isEdit) {
            initEditView();
        }
    }
});

/*
 * List View
 */
function initListView() {
    setPageTitle("Configurations");

    const renderer = initRenderer({
        tbodyId: 'configs-tbody',
        colspan: 5,
        itemLabel: 'configurations',
        rowTemplate: renderConfigurationRow,
        emptyState: {
            message: 'No configurations yet.',
        },
        filterEmptyState: {
            message: 'No configurations match your filters.',
        },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: API_URLS.configurations.list.href,
        pageSize: 20,
        searchInputId: 'config-search',
        filters: [],
        onLoadStart: () => renderer.renderLoading('Loading configurations...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load configurations. Please refresh the page.'),
    });

    initSorting({
        tableId: 'configs-table',
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

function renderConfigurationRow(config) {
    return `
        <tr data-config-id="${config.id}">
            <td>
                <a href="${URLS.configurations.detail(config.id)}"
                   class="rp-link">
                   <span class="rp-code">${escHtml(config.code)}</span>
                </a>
            </td>
            <td>
                <span class="rp-truncate">
                    ${escHtml(config.label ?? '')}
                </span>
            </td>
            <td>
                <span class="rp-value-pill">
                    ${escHtml(config.value ?? '')}
                </span>
            </td>
            <td class="text-secondary"
                style="max-width: 300px;">
                <span class="rp-truncate">
                    ${escHtml(config.description ?? '')}
                </span>
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.configurations.detail(config.id)}"
                       class="btn btn-ghost-icon"
                       title="View config">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.configurations.edit(config.id)}"
                       class="btn btn-ghost-icon"
                       title="Edit config">
                        <i class="bi bi-pencil"></i>
                    </a>
                </div>
            </td>
        </tr>
    `;
}

/*
 * Edit View
 */
async function initEditView() {
    setPageTitle("Edit Configuration");
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const submitLabel   = document.getElementById('submit-label');
    const submitBtn     = document.getElementById('submit-btn');
    pageTitle.textContent    = 'Edit Configuration';
    pageSubtitle.textContent = 'Loading…';
    submitLabel.textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    try {
        const { method, href } = API_URLS.configurations.get(configPk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        pageSubtitle.textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash(
                'This configuration no longer exists. It may have been deleted. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.configurations.list; }, 3000);
            return;
        }

        showFlash(
            err?.data?.error || 'Could not load configuration data. Please try again.',
            'danger',
        );
    }

    submitBtn.disabled = false;
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['value']);

    const valueInput = document.getElementById('id_value');
    if (!valueInput.value.trim()) {
        valueInput.classList.add('is-invalid');
        document.getElementById('value-error').textContent = 'Value is required.';
        valueInput.focus();
        return;
    }

    const payload = {
        value: valueInput.value.trim(),
    };

    const method = API_URLS.configurations.partial_edit(configPk).method
    const url = API_URLS.configurations.partial_edit(configPk).href

    setSubmitting(true);

    try {
        const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.configurations.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['value']);
            return;
        }
        if (err?.status === 404) {
            showFlash(
                'This configuration no longer exists and cannot be saved. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.configurations.list; }, 3000);
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

async function populateForm(config) {
    const pageTitle     = document.getElementById('page-title');
    const pageSubtitle  = document.getElementById('page-subtitle');
    const metadataCard  = document.getElementById('metadata-card');
    const resetBtnSlot = document.getElementById('reset-btn-slot');
    const overrideBadge = document.getElementById('override-badge');

    document.getElementById('id_code').textContent  = config.code        ?? '';
    document.getElementById('id_label').textContent = config.label       ?? '';
    document.getElementById('id_description').textContent = config.description ?? '';
    document.getElementById('id_value').value = config.value ?? '';

    pageTitle.textContent    = 'Edit Configuration';
    pageSubtitle.innerHTML   = `Updating <strong>${escHtml(config.code)}</strong>`;

    document.getElementById('meta-created').textContent = formatDateTime(config.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(config.updated_at);
    metadataCard.classList.remove('d-none');

    resetBtnSlot.innerHTML = `
        <button type="button"
                class="btn btn-outline-danger"
                id="reset-config-btn">
            <i class="bi bi-trash me-1"></i> Reset to default
        </button>`;
    document.getElementById('reset-config-btn')
        .addEventListener('click', () =>
            confirmReset(config.id, config.code, onDeleteFromEdit)
        );

    const def_value = await getDefault(config.code);
    document.getElementById('id_default_value').textContent = def_value.default_value ?? '';
    if (config.value !== def_value.default_value) {
        overrideBadge.classList.remove('d-none');
    } else {
        overrideBadge.classList.add('d-none');
    }
}

function onDeleteFromEdit(id, name) {
    window.location.href = URLS.configurations.list;
}

/*
 * Detail View
 */
async function initDetailView() {
    if (!configPk) return;
    setPageTitle("Configuration");

    try {
        const { method, href } = API_URLS.configurations.detail(configPk);
        const data = await apiFetch(href, { method });

        const def_value = await getDefault(data.code);

        renderDetailTitle(data, def_value);
        renderConfigDetails(data, def_value);
    } catch (err) {
        if (err?.status === 404) {
            showFlash(
                'This configuration no longer exists. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.configurations.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load configuration details. Please refresh.', 'danger');
    }
}

async function renderDetailTitle(config, def) {
    document.getElementById('config-code').textContent = config.code;

    if (config.value !== def.default_value) {
        document.getElementById('config-overridden').classList.add('rp-badge--warning');
        document.getElementById('config-overridden').classList.remove('rp-badge--success');
        document.getElementById('config-overridden').textContent = 'Overridden';
    } else {
        document.getElementById('config-overridden').classList.remove('rp-badge--warning');
        document.getElementById('config-overridden').classList.add('rp-badge--success');
        document.getElementById('config-overridden').textContent = 'Default';
    }

    document.getElementById('config-label').textContent = config.label;
    document.getElementById('edit-config-btn').href = URLS.configurations.edit(configPk);
}

function renderConfigDetails(config, def) {
    document.getElementById('current-value').textContent = config.value;
    document.getElementById('factory-default').textContent = def.default_value;
    document.getElementById('config-description').textContent = config.description ?? "-";
    document.getElementById('meta-created').textContent = formatDateTime(config.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(config.updated_at);
}

/*
 * Delete Modal - Shared
 */
function confirmReset(id, name, onSuccess) {
    const modal     = document.getElementById('resetModal');
    const nameEl    = document.getElementById('reset-config-code');
    const btn       = document.getElementById('confirm-reset-btn');

    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.configurations.reset(id);

    newBtn.addEventListener('click', async () => {
        try {
            newBtn.disabled    = true;
            newBtn.textContent = 'Resetting...';
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, name);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(
                    `Configuration "${name}" was not found — it may have already been deleted.`,
                    'warning',
                );
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete configuration "${name}". Please try again.`,
                'error'
            );
        } finally {
            newBtn.disabled    = false;
            newBtn.textContent = 'Reset to default';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

/*
 * Export View
 */
const LIST_EXPORT_COLUMNS = [
    { key: 'id', label: 'ID' },
    { key: 'code', label: 'Code' },
    { key: 'label', label: 'Label' },
    { key: 'value', label: 'Value' },
    { key: 'description', label: 'Description' }
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.configurations.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `configurations-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Configurations', filename);
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

async function getDefault(code) {
    try {
        const { method, href } = API_URLS.configurations.default(code);
        const res = await apiFetch(href, { method });
        return res;
    } catch (err) {
        if (err?.status === 404) {
            showFlash(
                'No system default registered for this code. Redirecting to the list…',
                'warning',
            );
            setTimeout(() => { window.location.href = URLS.configurations.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load configuration details. Please refresh.', 'danger');
    }
}

/*
 * Window Exports
 */
window.confirmReset = confirmReset;
window.onDeleteFromEdit = onDeleteFromEdit;