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

const SECRET_MASK = '••••••••';

const DATA_TYPE_ICONS = {
    string:  'bi-fonts',
    integer: 'bi-hash',
    float:   'bi-calculator',
    boolean: 'bi-toggle-on',
};

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
        colspan: 6,
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

function renderDataTypeBadge(config) {
    const icon = DATA_TYPE_ICONS[config.data_type] || 'bi-fonts';
    const label = config.data_type || 'string';
    const secretBadge = config.is_secret
        ? `<span class="rp-badge rp-badge--warning ms-1" title="Encrypted at rest">
               <i class="bi bi-shield-lock-fill"></i>
           </span>`
        : '';
    return `<span class="text-secondary small"><i class="bi ${icon} me-1"></i>${escHtml(label)}</span>${secretBadge}`;
}

function renderValueCell(config) {
    if (config.is_secret) {
        if (config.value) {
            return `<span class="rp-badge rp-badge--muted">
                        <i class="bi bi-lock-fill me-1"></i>${escHtml(SECRET_MASK)}
                    </span>`;
        }
        return `<span class="text-muted fst-italic small">Not set</span>`;
    }
    if (config.data_type === 'boolean') {
        const isTrue = config.value === 'true';
        return `<span class="rp-badge ${isTrue ? 'rp-badge--success' : 'rp-badge--muted'}">
                    ${escHtml(config.value ?? '')}
                </span>`;
    }
    return `<span class="rp-value-pill">${escHtml(config.value ?? '')}</span>`;
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
                ${renderDataTypeBadge(config)}
            </td>
            <td>
                ${renderValueCell(config)}
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

    // Clear previous errors
    const valueEl = document.getElementById('id_value');
    valueEl?.classList.remove('is-invalid');
    const errEl = document.getElementById('value-error');
    if (errEl) errEl.textContent = '';

    const config = e.target._configData;
    const rawValue = valueEl ? valueEl.value : '';

    // For non-secret configs, value is required
    if (!config?.is_secret && !rawValue.trim()) {
        valueEl?.classList.add('is-invalid');
        if (errEl) errEl.textContent = 'Value is required.';
        valueEl?.focus();
        return;
    }

    // SSO switch warning: intercept AUTH_MODE → sso
    if (config?.code === 'AUTH_MODE' && rawValue.trim() === 'sso') {
        showSsoSwitchModal();
        return;
    }

    await _doSaveConfig(rawValue.trim());
}

async function _doSaveConfig(value) {
    const method = API_URLS.configurations.partial_edit(configPk).method;
    const url    = API_URLS.configurations.partial_edit(configPk).href;

    setSubmitting(true);

    try {
        await apiFetch(url, { method, body: JSON.stringify({ value }) });
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
    const resetBtnSlot  = document.getElementById('reset-btn-slot');
    const overrideBadge = document.getElementById('override-badge');
    const secretBadge   = document.getElementById('id_secret_badge');
    const formEl        = document.getElementById('config-form');

    // Attach config data to the form element so the submit handler can read it
    formEl._configData = config;

    document.getElementById('id_code').textContent        = config.code        ?? '';
    document.getElementById('id_label').textContent       = config.label       ?? '';
    document.getElementById('id_description').textContent = config.description ?? '';

    // Data type display
    const dtIcon  = DATA_TYPE_ICONS[config.data_type] || 'bi-fonts';
    document.getElementById('id_data_type').innerHTML =
        `<i class="bi ${dtIcon} me-1"></i>${escHtml(config.data_type || 'string')}`;

    // Secret badge
    if (config.is_secret) {
        secretBadge?.classList.remove('d-none');
    }

    pageTitle.textContent  = 'Edit Configuration';
    pageSubtitle.innerHTML = `Updating <strong>${escHtml(config.code)}</strong>`;

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
    const defaultVal = def_value?.default_value ?? '';

    // System default hint
    if (config.is_secret) {
        document.getElementById('id_default_value').textContent = defaultVal || '(empty)';
    } else {
        document.getElementById('id_default_value').textContent = defaultVal;
        if (config.value !== defaultVal) {
            overrideBadge.classList.remove('d-none');
        } else {
            overrideBadge.classList.add('d-none');
        }
    }

    // Render the appropriate value control
    renderValueControl(config);
}

function renderValueControl(config) {
    const container = document.getElementById('value-control-container');
    const hintEl    = document.getElementById('value-hint');

    if (config.is_secret) {
        container.innerHTML = `
            <div class="input-group">
                <input type="password"
                       id="id_value"
                       name="value"
                       class="form-control rp-input"
                       autocomplete="new-password"
                       placeholder="${config.value ? 'Enter new value to replace the current secret' : 'Enter secret value'}">
                <button class="btn btn-outline-secondary"
                        type="button"
                        id="toggle-secret-btn"
                        title="Show / hide value">
                    <i class="bi bi-eye" id="toggle-secret-icon"></i>
                </button>
            </div>`;
        if (hintEl) {
            hintEl.textContent = config.value
                ? 'A secret value is already stored. Leave blank to keep it unchanged.'
                : 'Enter the secret value. It will be encrypted before being saved.';
        }
        document.getElementById('toggle-secret-btn').addEventListener('click', () => {
            const inp  = document.getElementById('id_value');
            const icon = document.getElementById('toggle-secret-icon');
            const isPassword = inp.type === 'password';
            inp.type       = isPassword ? 'text' : 'password';
            icon.className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
        });

    } else if (config.data_type === 'boolean') {
        const cur = config.value === 'true' ? 'true' : 'false';
        container.innerHTML = `
            <select id="id_value"
                    name="value"
                    class="form-select rp-input"
                    style="max-width:200px;">
                <option value="true"  ${cur === 'true'  ? 'selected' : ''}>true</option>
                <option value="false" ${cur === 'false' ? 'selected' : ''}>false</option>
            </select>`;
        if (hintEl) hintEl.textContent = 'Select true or false.';

    } else if (config.data_type === 'integer') {
        container.innerHTML = `
            <input type="number"
                   id="id_value"
                   name="value"
                   class="form-control rp-input"
                   style="max-width:240px;"
                   step="1"
                   value="${escAttr(config.value ?? '')}"
                   autocomplete="off">`;
        if (hintEl) hintEl.textContent = 'Enter a whole number (no decimals).';

    } else if (config.data_type === 'float') {
        container.innerHTML = `
            <input type="number"
                   id="id_value"
                   name="value"
                   class="form-control rp-input"
                   style="max-width:240px;"
                   step="any"
                   value="${escAttr(config.value ?? '')}"
                   autocomplete="off">`;
        if (hintEl) hintEl.textContent = 'Enter a decimal number (e.g. 1.50).';

    } else {
        // string
        container.innerHTML = `
            <textarea id="id_value"
                      name="value"
                      class="form-control rp-input"
                      rows="3"
                      autocomplete="off"
                      placeholder="Enter value">${escHtml(config.value ?? '')}</textarea>`;
        if (hintEl) {
            hintEl.textContent =
                'Values are stored as strings. Use pipe characters (|) to separate multiple values, e.g. option1|option2.';
        }
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

    // Override / Default badge
    const overriddenEl = document.getElementById('config-overridden');
    if (config.is_secret) {
        // For secrets we can't compare masked value to default, so skip the badge
        overriddenEl.classList.remove('rp-badge--warning', 'rp-badge--success');
        overriddenEl.textContent = '';
    } else {
        const isOverridden = config.value !== (def?.default_value ?? '');
        overriddenEl.classList.toggle('rp-badge--warning', isOverridden);
        overriddenEl.classList.toggle('rp-badge--success', !isOverridden);
        overriddenEl.textContent = isOverridden ? 'Overridden' : 'Default';
    }

    // Secret badge
    if (config.is_secret) {
        document.getElementById('config-secret-badge')?.classList.remove('d-none');
    }

    document.getElementById('config-label').textContent = config.label;
    document.getElementById('edit-config-btn').href = URLS.configurations.edit(configPk);
}

function renderConfigDetails(config, def) {
    // Current Value
    const currentValueEl = document.getElementById('current-value');
    if (config.is_secret) {
        if (config.value) {
            currentValueEl.innerHTML =
                `<span class="rp-badge rp-badge--muted">
                     <i class="bi bi-lock-fill me-1"></i>${escHtml(SECRET_MASK)}
                 </span>`;
        } else {
            currentValueEl.innerHTML =
                `<span class="text-muted fst-italic">Not set</span>`;
        }
    } else if (config.data_type === 'boolean') {
        const isTrue = config.value === 'true';
        currentValueEl.innerHTML =
            `<span class="rp-badge ${isTrue ? 'rp-badge--success' : 'rp-badge--muted'} rp-value-pill--lg">
                 ${escHtml(config.value ?? '')}
             </span>`;
    } else {
        currentValueEl.textContent = config.value;
    }

    // System Default
    const defEl = document.getElementById('factory-default');
    if (config.is_secret) {
        defEl.innerHTML = `<span class="text-muted fst-italic small">(secret — no displayable default)</span>`;
    } else {
        defEl.textContent = def?.default_value ?? '—';
    }

    // Data Type
    const dtIcon = DATA_TYPE_ICONS[config.data_type] || 'bi-fonts';
    document.getElementById('config-data-type').innerHTML =
        `<i class="bi ${dtIcon} me-1"></i>${escHtml(config.data_type || 'string')}` +
        (config.is_secret
            ? ` <span class="rp-badge rp-badge--warning ms-1"><i class="bi bi-shield-lock-fill me-1"></i>Encrypted</span>`
            : '');

    document.getElementById('config-description').textContent = config.description ?? '—';
    document.getElementById('meta-created').textContent = formatDateTime(config.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(config.updated_at);
}

/*
 * Reset Modal - Shared
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
                err?.data?.detail || `Failed to reset configuration "${name}". Please try again.`,
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
    { key: 'id',          label: 'ID' },
    { key: 'code',        label: 'Code' },
    { key: 'label',       label: 'Label' },
    { key: 'data_type',   label: 'Type' },
    { key: 'is_secret',   label: 'Secret' },
    { key: 'value',       label: 'Value' },
    { key: 'description', label: 'Description' },
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
            return null;
        }
        showFlash(err?.data?.error || 'Could not load configuration details. Please refresh.', 'danger');
        return null;
    }
}

/*
 * SSO switch warning modal
 */
function showSsoSwitchModal() {
    const existing = document.getElementById('sso-switch-modal');
    if (existing) existing.remove();

    const html = `
    <div class="modal fade" id="sso-switch-modal" tabindex="-1" data-bs-backdrop="static">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content rp-modal">
          <div class="modal-header border-0 pb-0">
            <h5 class="modal-title d-flex align-items-center gap-2">
              <i class="bi bi-exclamation-triangle-fill text-warning"></i>
              Switch to SSO authentication?
            </h5>
          </div>
          <div class="modal-body">
            <p>You are about to switch the authentication mode to <strong>SSO</strong>. Once applied:</p>
            <ul class="mb-3">
              <li>Users will no longer be able to sign in with email and password.</li>
              <li>All authentication will be handled by the configured identity provider.</li>
            </ul>
            <div class="alert alert-danger mb-3">
              <i class="bi bi-shield-exclamation me-2"></i>
              <strong>Clear classic passwords?</strong><br>
              For security, it is strongly recommended to clear all stored passwords
              so users cannot bypass SSO by switching back to classic mode manually.
            </div>
            <div class="form-check form-switch rp-switch">
              <input class="form-check-input" type="checkbox" id="sso-wipe-passwords" checked>
              <label class="form-check-label" for="sso-wipe-passwords">
                Clear all classic user passwords on switch
              </label>
            </div>
          </div>
          <div class="modal-footer border-0 pt-0 gap-2">
            <button type="button" class="btn btn-outline-secondary" id="sso-modal-cancel">Cancel</button>
            <button type="button" class="btn btn-danger" id="sso-modal-confirm">
              <i class="bi bi-arrow-right-circle me-1"></i>Switch to SSO
            </button>
          </div>
        </div>
      </div>
    </div>`;

    document.body.insertAdjacentHTML('beforeend', html);
    const modal = new bootstrap.Modal(document.getElementById('sso-switch-modal'));
    modal.show();

    document.getElementById('sso-modal-cancel').addEventListener('click', () => modal.hide());

    document.getElementById('sso-modal-confirm').addEventListener('click', async () => {
        const wipe = document.getElementById('sso-wipe-passwords').checked;
        modal.hide();
        setSubmitting(true);
        try {
            // 1. Save the AUTH_MODE config
            await _doSaveConfig('sso');
            // 2. Optionally wipe passwords via users API
            if (wipe) {
                try {
                    await apiFetch('/api/v1/users/switch_auth_mode/', {
                        method: 'POST',
                        body: JSON.stringify({ mode: 'sso', wipe_passwords: true }),
                    });
                } catch (_) {
                    showFlash('Auth mode saved, but password wipe failed. Run it manually.', 'warning');
                }
            }
        } finally {
            setSubmitting(false);
        }
    });
}

/*
 * Window Exports
 */
window.confirmReset = confirmReset;
window.onDeleteFromEdit = onDeleteFromEdit;
