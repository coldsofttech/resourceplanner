'use strict';

/*******************************************************************************/
/* skill_list.html                                                             */
/*******************************************************************************/

/* Search & Filtering Functionality */
const searchInput  = document.getElementById('team-search');
const statusFilter = document.getElementById('status-filter');
const tbody = document.querySelector('#skills-table tbody');

if (searchInput) {
  searchInput.addEventListener('input', filterTable);
}

if (statusFilter) {
    statusFilter.addEventListener('change', filterTable);
}

function filterTable() {
  if (!tbody) return;

  const query      = (searchInput?.value  || '').toLowerCase().trim();
  const status     = (statusFilter?.value || '').toLowerCase().trim();
  const rows       = tbody.querySelectorAll('tr[data-skill-id]');
  let   visible    = 0;

  rows.forEach(row => {
    const name    = (row.dataset.code   || '').toLowerCase();
    const desc    = (row.dataset.desc   || '').toLowerCase();
    const rowStat = (row.dataset.status || '').toLowerCase();

    const matchQ = !query  || name.includes(query) || desc.includes(query);
    const matchS = !status || rowStat === status;

    const show = matchQ && matchS;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  // Show empty state if all hidden
  let emptyRow = document.getElementById('empty-filter-row');
  if (!visible) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `
        <td colspan="6" class="text-center py-4 text-secondary">
          <i class="bi bi-search me-2"></i>No skills match your filters.
        </td>`;
      tbody.appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* Sorting Table Functionality */
let sortState = { col: -1, asc: true };

function sortTable(colIndex) {
  const tbody = document.querySelector('#skills-table tbody');
  if (!tbody) return;

  // Toggle direction if same column
  if (sortState.col === colIndex) {
    sortState.asc = !sortState.asc;
  } else {
    sortState.col = colIndex;
    sortState.asc = true;
  }

  // Update header icons
  document.querySelectorAll('#skills-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-skill-id]'));

  rows.sort((a, b) => {
    const aCell = a.cells[colIndex];
    const bCell = b.cells[colIndex];
    if (!aCell || !bCell) return 0;

    const aVal = aCell.innerText.trim();
    const bVal = bCell.innerText.trim();

    // Numeric columns (capacity)
    const aNum = parseFloat(aVal);
    const bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return sortState.asc ? aNum - bNum : bNum - aNum;
    }
    return sortState.asc
      ? aVal.localeCompare(bVal)
      : bVal.localeCompare(aVal);
  });

  rows.forEach(row => tbody.appendChild(row));
}

/* Export Functionality */
const LIST_EXPORT_COLUMNS = [
  { key: 'id',          label: 'ID'           },
  { key: 'skill',       label: 'Skill'        },
  { key: 'description', label: 'Description'  },
  { key: 'is_active',   label: 'Active'       },
];

const LIST_EXPORT_URL = '/api/v1/skills/export/';

async function runListExport(format) {
  const btn = document.getElementById('export-dropdown-btn');

  bootstrap.Dropdown.getInstance(btn)?.hide();

  // Briefly disable the button to prevent double-clicks
  if (btn) {
    btn.disabled  = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
  }

  try {
    const res  = await apiFetch(LIST_EXPORT_URL);
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

/*******************************************************************************/
/* skill_import.html                                                           */
/*******************************************************************************/

/* Bulk Import Functionality */
const importBtn        = document.getElementById('import-btn');
const importResults    = document.getElementById('import-results');
const importAnotherBtn = document.getElementById('import-another-btn');

let importFile = null;

loadSpecs('/api/v1/skills/import/specifications/'); // all element IDs match import.js defaults

const dropZoneEl = document.getElementById('drop-zone'); // all element IDs, delivery-team-specific callbacks

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

    /* All element IDS match import.js defaults */
    submitImport(window.location.pathname, importFile, {
      submitBtn: importBtn,
      onSuccess: data => renderImportResults(data, {}, { nameKey: 'skill' }),
      onError:   msg  => dropZoneApi.showError(msg),
    });
  });
}

/* Import Another File */
if (importAnotherBtn) {
  importAnotherBtn.addEventListener('click', () => {
    importResults.classList.add('d-none');
    document.getElementById('remove-file-btn')?.click();
  });
}

/*******************************************************************************/
/* skill_list.html & skill_form.html                                           */
/*******************************************************************************/

/* Delete Skill Functionality */
function confirmDelete(id, name, deleteUrl, redirectUrl) {
  const modal   = document.getElementById('deleteModal');
  const nameEl  = document.getElementById('delete-skill-code');
  const btn     = document.getElementById('confirm-delete-btn');

  if (!modal || !btn) return;

  nameEl.textContent = name;

  // Remove previous listener to prevent duplicates
  const newBtn = btn.cloneNode(true);
  btn.parentNode.replaceChild(newBtn, newBtn.previousSibling || btn);

  // Use passed URL or derive from current path
  const resolvedUrl  = deleteUrl || `/skills/${id}/delete/`;
  const resolvedRedir = redirectUrl || '/skills/';

  newBtn.addEventListener('click', async () => {
    try {
      newBtn.disabled = true;
      newBtn.textContent = 'Deleting...';
      await apiFetch(resolvedUrl, { method: 'POST' });
      bootstrap.Modal.getInstance(modal)?.hide();
      showFlash(`Skill "${name}" was deleted successfully.`, 'success');
      setTimeout(() => { window.location.href = resolvedRedir; }, 800);
    } catch (err) {
      newBtn.disabled = false;
      newBtn.textContent = 'Delete';
      bootstrap.Modal.getInstance(modal)?.hide();
      showFlash(
        err?.data?.detail || `Failed to delete skill "${name}". Please try again.`,
        'error'
      );
    }
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}