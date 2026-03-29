'use strict';

/*******************************************************************************/
/* import.js                                                                   */
/* Reusable helpers for any page that accepts a file upload, shows import      */
/* specifications, and renders a results table.                                */
/*                                                                             */
/* Public API:                                                                 */
/*                                                                             */
/*   initImportDropZone(elements, options)  → { showError, clearError, reset } */
/*   submitImport(url, file, options)                                           */
/*   renderImportResults(data, ids)                                            */
/*   loadSpecs(url, ids)                                                       */
/*   formatBytes(bytes)  → string                                              */
/*   escHtml(str)        → string                                              */
/*******************************************************************************/


/* =========================================================================== */
/* initImportDropZone                                                           */
/*                                                                             */
/* Wires a drop zone, file input, file pill, remove button, and error          */
/* display. Returns { showError, clearError, reset } for the caller to use.   */
/*                                                                             */
/* elements (all HTMLElement):                                                 */
/*   dropZone   fileInput   fileInfo   fileNameEl   fileSizeEl                */
/*   removeBtn  submitBtn   errorEl    errorMsgEl                              */
/*                                                                             */
/* options:                                                                    */
/*   accept       — file extension to allow  (default: '.csv')                */
/*   onFile(file) — called when a valid file is chosen                        */
/*   onReset()    — called when the file is cleared                           */
/* =========================================================================== */

function initImportDropZone(elements, options = {}) {
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
    submitBtn.disabled = false;
  }

  function clearFilePill() {
    fileInput.value = '';
    fileInfo.classList.add('d-none');
    dropZone.classList.remove('d-none');
    submitBtn.disabled = true;
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


/* =========================================================================== */
/* submitImport                                                                 */
/*                                                                             */
/* Sends a multipart/form-data POST and manages the submit button state.      */
/*                                                                             */
/* url          — POST endpoint e.g. '/delivery-teams/import/'                */
/* file         — File object from the drop zone                              */
/* options:                                                                    */
/*   fileKey         — FormData field name       (default: 'file')            */
/*   submitBtn       — button to disable/restore during the request           */
/*   onSuccess(data) — called with parsed JSON when res.ok                    */
/*   onError(msg)    — called with an error string on failure                 */
/* =========================================================================== */

async function submitImport(url, file, options = {}) {
  const {
    fileKey   = 'file',
    submitBtn = null,
    onSuccess = () => {},
    onError   = () => {},
  } = options;

  if (submitBtn) {
    submitBtn.disabled  = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Importing&hellip;';
  }

  const formData = new FormData();
  formData.append(fileKey, file);

  try {
    // Raw fetch — not apiFetch — because apiFetch sets Content-Type: application/json
    // which prevents Django (and most backends) from reading request.FILES
    const res  = await fetch(url, {
      method:  'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
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
    if (submitBtn) {
      submitBtn.disabled  = false;
      submitBtn.innerHTML = '<i class="bi bi-upload me-1"></i>Import';
    }
  }
}


/* =========================================================================== */
/* renderImportResults                                                          */
/*                                                                             */
/* Renders the summary banner, failed/succeeded tab tbodies, and badges,      */
/* then activates the appropriate tab and scrolls the panel into view.        */
/*                                                                             */
/* data — JSON body from the import endpoint:                                 */
/*   { succeeded: [{row, name}], failed: [{row, name, error}],               */
/*     total, summary }                                                        */
/*                                                                             */
/* ids  — override any default element ID (all optional):                     */
/*   resultsPanel   (default: 'import-results')                               */
/*   resultsBanner  (default: 'results-banner')                               */
/*   badgeSucceeded (default: 'badge-succeeded')                              */
/*   badgeFailed    (default: 'badge-failed')                                 */
/*   failedTbody    (default: 'results-failed-tbody')                         */
/*   succeededTbody (default: 'results-succeeded-tbody')                      */
/*   tabFailed      (default: 'tab-failed')                                   */
/*   tabSucceeded   (default: 'tab-succeeded')                                */
/* =========================================================================== */

function renderImportResults(data, ids = {}, options = {}) {
  const nameKey = options.nameKey || 'name';

  const el = {
    resultsPanel:   document.getElementById(ids.resultsPanel   || 'import-results'),
    resultsBanner:  document.getElementById(ids.resultsBanner  || 'results-banner'),
    badgeSucceeded: document.getElementById(ids.badgeSucceeded || 'badge-succeeded'),
    badgeFailed:    document.getElementById(ids.badgeFailed    || 'badge-failed'),
    failedTbody:    document.getElementById(ids.failedTbody    || 'results-failed-tbody'),
    succeededTbody: document.getElementById(ids.succeededTbody || 'results-succeeded-tbody'),
    tabFailed:      document.getElementById(ids.tabFailed      || 'tab-failed'),
    tabSucceeded:   document.getElementById(ids.tabSucceeded   || 'tab-succeeded'),
  };

  const succeeded = data.succeeded || [];
  const failed    = data.failed    || [];
  const total     = data.total     || (succeeded.length + failed.length);
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
  el.failedTbody.innerHTML = '';
  if (failed.length) {
    failed.slice().sort((a, b) => a.row - b.row).forEach(r => {
      const errorText = Array.isArray(r.error) ? r.error.join(' ') : (r.error || '');
      const tr        = document.createElement('tr');
      tr.innerHTML = `
        <td class="text-center text-secondary">${r.row}</td>
        <td class="fw-500">${escHtml(r[nameKey] || '&mdash;')}</td>
        <td class="text-danger small">${escHtml(errorText)}</td>`;
      el.failedTbody.appendChild(tr);
    });
  } else {
    el.failedTbody.innerHTML = `
      <tr>
        <td colspan="3" class="text-center py-4 text-secondary">
          <i class="bi bi-check-circle me-2"></i>No failures — all rows imported successfully.
        </td>
      </tr>`;
  }

  // Succeeded tbody — sorted by row number
  el.succeededTbody.innerHTML = '';
  if (succeeded.length) {
    succeeded.slice().sort((a, b) => a.row - b.row).forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="text-center text-secondary">${r.row}</td>
        <td class="fw-500">${escHtml(r[nameKey])}</td>`;
      el.succeededTbody.appendChild(tr);
    });
  } else {
    el.succeededTbody.innerHTML = `
      <tr>
        <td colspan="2" class="text-center py-4 text-secondary">
          No rows were imported.
        </td>
      </tr>`;
  }

  // Activate the relevant tab and scroll into view
  bootstrap.Tab.getOrCreateInstance(failed.length ? el.tabFailed : el.tabSucceeded).show();
  el.resultsPanel.classList.remove('d-none');
  el.resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}


/* =========================================================================== */
/* loadSpecs                                                                    */
/*                                                                             */
/* Fetches import specifications from the API and renders a fields table      */
/* and notes list. Handles loading, error, and retry states automatically.    */
/*                                                                             */
/* url  — specifications endpoint                                              */
/*        e.g. '/api/v1/delivery-teams/import/specifications/'                */
/*                                                                             */
/* ids  — override any default element ID (all optional):                     */
/*   loading  (default: 'specs-loading')                                      */
/*   error    (default: 'specs-error')                                        */
/*   content  (default: 'specs-content')                                      */
/*   tbody    (default: 'specs-tbody')                                        */
/*   notes    (default: 'specs-notes')                                        */
/*   retry    (default: 'specs-retry')                                        */
/* =========================================================================== */

async function loadSpecs(url, ids = {}) {
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


/* =========================================================================== */
/* Utilities                                                                    */
/* =========================================================================== */

/* Human-readable file size */
function formatBytes(bytes) {
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* Escape HTML for safe innerHTML injection */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}