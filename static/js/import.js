'use strict';

import { apiFetch, escHtml, formatBytes } from './main.js';
import { initRenderer } from './list/render.js';

/*
 * Reusable helpers for any page that accepts a file uploade, shows import
 * specifications, and renders a results table.
 */

/*
 * initImportDropZone
 *
 * Wires a drop zone, file input, file pill, remove button, and error
 * display, returns { showError, clearError, reset } for the caller to use.
 */

export function initImportDropZone(elements, options = {}) {
    const {
        dropZone,
        fileInput,
        fileInfo,
        fileNameEl,
        fileSizeEl,
        removeBtn,
        submitBtn,
        errorEl,
        errorMsgEl,
    } = elements;

    const accept = (options.accept || '.csv').toLowerCase();
    const submitBtns = Array.isArray(submitBtn) ? submitBtn : [submitBtn].filter(Boolean);

    function _setSubmitDisabled(disabled) {
        submitBtns.forEach(btn => { btn.disabled = disabled; });
    }

    function showError(msg) {
        errorMsgEl.textContent = msg;
        errorEl.classList.remove('d-none');
    }

    function clearError() {
        errorEl.classList.add('d-none');
        errorMsgEl.textContent = '';
    }

    function showFilePill(file) {
        fileNameEl.textContent = file.name;
        fileSizeEl.textContent = formatBytes(file.size);
        dropZone.classList.add('d-none');
        fileInfo.classList.remove('d-none');
        _setSubmitDisabled(false);
    }

    function clearFilePill() {
        fileInput.value = '';
        fileInfo.classList.add('d-none');
        dropZone.classList.remove('d-none');
        _setSubmitDisabled(true);
        clearError();
    }

    function validate(file) {
        if (!file.name.toLowerCase().endsWith(accept)) {
            showError(`Only ${accept} files are accepted.`);
            return false;
        }
        return true;
    }

    function handleFile(file) {
        clearError();
        if (!validate(file)) return;
        showFilePill(file);
        options.onFile?.(file);
    }

    function reset() {
        clearFilePill();
        options.onReset?.();
    }

    // Browse
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) handleFile(fileInput.files[0]);
    });

    // Keyboard access
    dropZone.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') fileInput.click();
    });

    // Drag and drop
    dropZone.addEventListener('dragover', e => {
        e.preventDefault();
        dropZone.classList.add('rp-drop-zone--active');
    });

    ['dragleave', 'dragend'].forEach(evt =>
        dropZone.addEventListener(evt, () =>
            dropZone.classList.remove('rp-drop-zone--active')
        )
    );

    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('rp-drop-zone--active');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });

    // Remove button
    removeBtn.addEventListener('click', reset);

    return { showError, clearError, reset };
}

/*
 * submitImport
 *
 * Sends a multipart/form-data POST and manages the submit button state.
 */

export async function submitImport(url, file, options = {}) {
    const {
        fileKey   = 'file',
        submitBtn = null,
        extraParams  = {},
        onSuccess = () => {},
        onError   = () => {},
    } = options;

    const submitBtns = Array.isArray(submitBtn) ? submitBtn : [submitBtn].filter(Boolean);
    const originalLabels = submitBtns.map(btn => btn.innerHTML);

    submitBtns.forEach(btn => {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Importing&hellip;';
    })

    // Read CSRF token inline — does not depend on getCsrfToken() from main.js
    const csrfMeta  = document.querySelector('meta[name="csrf-token"]');
    const csrfCookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    const csrfToken  = csrfMeta
        ? csrfMeta.getAttribute('content')
        : (csrfCookie ? csrfCookie.split('=')[1].trim() : '');

    const finalUrl = new URL(url, window.location.origin);
    Object.entries(extraParams).forEach(([k, v]) => finalUrl.searchParams.set(k, v));

    const formData = new FormData();
    formData.append(fileKey, file);

    try {
        // Raw fetch — not apiFetch — because apiFetch sets Content-Type: application/json
        // which prevents Django (and most backends) from reading request.FILES
        const res  = await fetch(finalUrl.toString(), {
            method:  'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body:    formData,
        });

        const data = await res.json();

    if (!res.ok) {
        const msg = Array.isArray(data.error)
            ? data.error.join(' ')
            : (data.error || 'Import failed. Please try again.');
        onError(msg);
        return;
    }

    onSuccess(data);

    } catch (err) {
        console.error('submitImport error:', err);
        onError('A network error occurred. Please check your connection and try again.');
    } finally {
        submitBtns.forEach((btn, i) => {
            btn.disabled = false;
            btn.innerHTML = originalLabels[i];
        });
    }
}

/*
 * renderImportResults
 *
 * Renders the summary banner, failed/succeeded tab tbodies, and badges,
 * then activates the appropriate tab and scrolls the panel into view.
 *
 * Both tabs are paginated at PAGE_SIZE rows per page using initRenderer.
 */

const _RESULTS_PAGE_SIZE = 20;

function _buildPagination(items, page, pageSize) {
    const totalCount = items.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
    const safePage   = Math.min(Math.max(1, page), totalPages);
    return {
        current_page: safePage,
        total_pages:  totalPages,
        total_count:  totalCount,
        page_size:    pageSize,
        has_previous: safePage > 1,
        has_next:     safePage < totalPages,
    };
}

function _pageSlice(sorted, page, pageSize) {
    const start = (page - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
}

export function renderImportResults(data, ids = {}, options = {}) {
    const nameKey = options.nameKey || 'name';

    const el = {
        resultsPanel:   document.getElementById(ids.resultsPanel   || 'import-results'),
        resultsBanner:  document.getElementById(ids.resultsBanner  || 'results-banner'),
        badgeSucceeded: document.getElementById(ids.badgeSucceeded || 'badge-succeeded'),
        badgeFailed:    document.getElementById(ids.badgeFailed    || 'badge-failed'),
        tabFailed:      document.getElementById(ids.tabFailed      || 'tab-failed'),
        tabSucceeded:   document.getElementById(ids.tabSucceeded   || 'tab-succeeded'),
    };

    const succeeded = (data.succeeded || []).slice().sort((a, b) => a.row - b.row);
    const failed    = (data.failed    || []).slice().sort((a, b) => a.row - b.row);
    const total     = data.total || (succeeded.length + failed.length);
    const allOk     = failed.length    === 0;
    const allFail   = succeeded.length === 0;

    // Summary banner
    const bannerClass = allOk   ? 'alert-success'
                    : allFail ? 'alert-danger'
                    :           'alert-warning';

    const bannerIcon  = allOk   ? 'bi-check-circle-fill text-success'
                    : allFail ? 'bi-x-circle-fill text-danger'
                    :           'bi-exclamation-triangle-fill text-warning';

    el.resultsBanner.className = `alert d-flex align-items-center gap-3 mb-4 ${bannerClass}`;
    el.resultsBanner.innerHTML = `
        <i class="bi ${bannerIcon} fs-5 flex-shrink-0"></i>
        <div>
          <strong>${escHtml(data.summary)}</strong>
          <span class="text-secondary ms-2">${total} row${total !== 1 ? 's' : ''} processed.</span>
        </div>`;

    // Tab badges
    el.badgeSucceeded.textContent = succeeded.length;
    el.badgeFailed.textContent    = failed.length;

    // Failed tbody — sorted by row number
    const _failedSorted = failed;

    const failedRenderer = initRenderer({
        tbodyId:              ids.failedTbody    || 'results-failed-tbody',
        colspan:              3,
        itemLabel:            'failed rows',
        paginationBarId:      ids.failedPaginationBar      || 'failed-pagination-bar',
        paginationInfoId:     ids.failedPaginationInfo     || 'failed-pagination-info',
        paginationControlsId: ids.failedPaginationControls || 'failed-pagination-controls',
        emptyState: {
            message: 'No failures — all rows imported successfully.',
        },
        rowTemplate: r => {
            const errorText = Array.isArray(r.error) ? r.error.join(' ') : (r.error || '');
            return `
                <tr>
                    <td class="text-center text-secondary">${r.row}</td>
                    <td class="fw-500">${escHtml(r[nameKey] || '—')}</td>
                    <td class="text-danger small">${escHtml(errorText)}</td>
                </tr>`;
        },
        onPageChange: page => {
            _renderFailedPage(page);
        },
    });

    function _renderFailedPage(page) {
        if (!failedRenderer) return;
        failedRenderer.renderRows(_pageSlice(_failedSorted, page, _RESULTS_PAGE_SIZE));
        failedRenderer.renderPagination(_buildPagination(_failedSorted, page, _RESULTS_PAGE_SIZE));
    }

    _renderFailedPage(1);

    // Succeeded tbody — sorted by row number
    const _succeededSorted = succeeded;

    const succeededRenderer = initRenderer({
        tbodyId:              ids.succeededTbody    || 'results-succeeded-tbody',
        colspan:              2,
        itemLabel:            'imported rows',
        paginationBarId:      ids.succeededPaginationBar      || 'succeeded-pagination-bar',
        paginationInfoId:     ids.succeededPaginationInfo     || 'succeeded-pagination-info',
        paginationControlsId: ids.succeededPaginationControls || 'succeeded-pagination-controls',
        emptyState: {
            message: 'No rows were imported.',
        },
        rowTemplate: r => `
            <tr>
                <td class="text-center text-secondary">${r.row}</td>
                <td class="fw-500">${escHtml(r[nameKey] || '—')}</td>
            </tr>`,
        onPageChange: page => {
            _renderSucceededPage(page);
        },
    });

    function _renderSucceededPage(page) {
        if (!succeededRenderer) return;
        succeededRenderer.renderRows(_pageSlice(_succeededSorted, page, _RESULTS_PAGE_SIZE));
        succeededRenderer.renderPagination(_buildPagination(_succeededSorted, page, _RESULTS_PAGE_SIZE));
    }

    _renderSucceededPage(1);

    const failedBar    = document.getElementById(ids.failedPaginationBar    || 'failed-pagination-bar');
    const succeededBar = document.getElementById(ids.succeededPaginationBar || 'succeeded-pagination-bar');

    function _syncPaginationBars(activeTabId) {
        const failedActive = (activeTabId === (ids.tabFailed || 'tab-failed'));
        const failedHasPages    = (failedBar    && failedBar.querySelectorAll('button[data-page]').length > 0);
        const succeededHasPages = (succeededBar && succeededBar.querySelectorAll('button[data-page]').length > 0);

        if (failedBar)    failedBar.classList.toggle('d-none',     !failedActive    || !failedHasPages);
        if (succeededBar) succeededBar.classList.toggle('d-none',   failedActive    || !succeededHasPages);
    }

    const initialActiveId = failed.length
        ? (ids.tabFailed    || 'tab-failed')
        : (ids.tabSucceeded || 'tab-succeeded');
    _syncPaginationBars(initialActiveId);

    document.getElementById(ids.tabFailed    || 'tab-failed')
        ?.addEventListener('shown.bs.tab', () => _syncPaginationBars(ids.tabFailed    || 'tab-failed'));
    document.getElementById(ids.tabSucceeded || 'tab-succeeded')
        ?.addEventListener('shown.bs.tab', () => _syncPaginationBars(ids.tabSucceeded || 'tab-succeeded'));

    // Activate the relevant tab and scroll into view
    bootstrap.Tab.getOrCreateInstance(failed.length ? el.tabFailed : el.tabSucceeded).show();
    el.resultsPanel.classList.remove('d-none');
    el.resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/*
 * loadSpecs
 *
 * Fetches import specifications from the API and renders a fields table
 * and notes list. Handles loading, error, and retry states automatically.
 */

export async function loadSpecs(url, ids = {}) {
    const el = {
        loading: document.getElementById(ids.loading || 'specs-loading'),
        error:   document.getElementById(ids.error   || 'specs-error'),
        content: document.getElementById(ids.content || 'specs-content'),
        tbody:   document.getElementById(ids.tbody   || 'specs-tbody'),
        notes:   document.getElementById(ids.notes   || 'specs-notes'),
        retry:   document.getElementById(ids.retry   || 'specs-retry'),
    };

    // Guard — if the loading element is absent, this page has no specs panel
    if (!el.loading) return;

    // Wire retry link — passes same url and ids through
    el.retry?.addEventListener('click', e => {
        e.preventDefault();
        loadSpecs(url, ids);
    });

    el.loading.classList.remove('d-none');
    el.error.classList.add('d-none');
    el.content.classList.add('d-none');

    try {
        const data = await apiFetch(url);
        _renderSpecs(data, el);
    } catch (_err) {
        el.loading.classList.add('d-none');
        el.error.classList.remove('d-none');
    }
}

function _renderSpecs(data, el) {
    // Fields table
    el.tbody.innerHTML = '';
    (data.fields || []).forEach(field => {
        const notes = _buildSpecNotes(field);
        const tr    = document.createElement('tr');
        tr.innerHTML = `
            <td><code>${escHtml(field.name)}</code></td>
            <td>
                <span class="rp-badge ${field.required ? 'rp-badge--danger' : 'rp-badge--muted'}">
                    ${field.required ? 'Required' : 'Optional'}
                </span>
            </td>
            <td class="text-capitalize">${escHtml(field.type)}</td>
            <td class="text-secondary small">${notes}</td>`;
        el.tbody.appendChild(tr);
    });

    // Notes list
    el.notes.innerHTML = '';
    (data.notes || []).forEach(note => {
        const li       = document.createElement('li');
        li.textContent = note;
        el.notes.appendChild(li);
    });

    el.loading.classList.add('d-none');
    el.content.classList.remove('d-none');
}

function _buildSpecNotes(field) {
    const parts = [];
    if (field.max_length)      parts.push(`Max ${field.max_length} characters.`);
    if (field.allowed_values)  parts.push(`Accepts: <code>${field.allowed_values.join('</code> / <code>')}</code>.`);
    if (field.default != null) parts.push(`Defaults to <code>${escHtml(String(field.default))}</code>.`);
    return parts.join(' ') || '&mdash;';
}
