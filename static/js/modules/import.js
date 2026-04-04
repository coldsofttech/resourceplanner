'use strict';

import { showFlash } from './../main.js';
import { API_URLS, URLS } from './../urls.js';
import { loadSpecs, initImportDropZone, submitImport, renderImportResults } from './../import.js';

const LABELS = {
    delivery_teams: "teams",
    skills: "skills",
    locations: "locations",
    roles: "roles",
    employment_types: "employment types",
    team_members: "team members",
    holidays: "holidays",
};

const importBtn         = document.getElementById('import-btn');
const validateBtn       = document.getElementById('import-validate-btn');
const importResults     = document.getElementById('import-results');
const importAnotherBtn  = document.getElementById('import-another-btn');
const dropZoneEl        = document.getElementById('drop-zone');

let module      = null;
let importFile  = null;
let dropZoneApi = null;
let validated   = false;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const mod = params.get('module');

    if (!mod) {
        showFlash('?module= is required in the parameters.', 'danger');
        return;
    }

    if (!API_URLS[mod]) {
        showFlash(`Module "${mod}" is not supported.`, 'danger');
        return;
    }

    module = mod;
    renderView();
});

function renderView() {
    const label = LABELS[module] ?? module.replace(/_/g, ' ');

    document.getElementById('module-title').textContent = `Import ${label}`;
    document.getElementById('module-subtitle').textContent = `Bulk import ${label} from a CSV file.`;
    document.getElementById('back-btn').href = URLS[module].list;
    document.getElementById('cancel-btn').href = URLS[module].list;
    document.getElementById('import-sample-btn').href = URLS[module].import_sample;
    document.getElementById('view-all-btn').href = URLS[module].list;

    loadSpecs(API_URLS[module].import_spec.href);

    if (dropZoneEl) {
        dropZoneApi = initImportDropZone(
            {
                dropZone:   dropZoneEl,
                fileInput:  document.getElementById('csv-file-input'),
                fileInfo:   document.getElementById('file-info'),
                fileNameEl: document.getElementById('file-name'),
                fileSizeEl: document.getElementById('file-size'),
                removeBtn:  document.getElementById('remove-file-btn'),
                submitBtn:  [validateBtn, importBtn],
                errorEl:    document.getElementById('file-error'),
                errorMsgEl: document.getElementById('file-error-msg'),
            },
            {
                accept:  '.csv',
                onFile:  file => {
                    importFile = file;
                    validated  = false;
                    _setImportBtnStyle('default');
                },
                onReset: ()   => {
                    importFile = null;
                    validated  = false;
                    _setImportBtnStyle('default');
                },
            }
        );
    }

    validateBtn.addEventListener('click', () => {
        if (!importFile) return;

        submitImport(API_URLS[module].import.href, importFile, {
            submitBtn:    validateBtn,
            extraParams:  { validate: 'true' },
            onSuccess: data => {
                const errorCount = (data.failed ?? []).length;
                if (errorCount === 0) {
                    validated = true;
                    _setImportBtnStyle('clean');
                    renderImportResults(data, { mode: 'validate' });
                } else {
                    validated = false;
                    _setImportBtnStyle('has_errors');
                    renderImportResults(data, { mode: 'validate' });
                }
            },
            onError: msg => dropZoneApi?.showError(msg),
        });
    });

    importBtn.addEventListener('click', () => {
        if (!importFile) return;

        submitImport(API_URLS[module].import.href, importFile, {
            submitBtn: importBtn,
            onSuccess: data => renderImportResults(data, { mode: 'import' }),
            onError:   msg  => dropZoneApi?.showError(msg),
        });
    });
}

function _setImportBtnStyle(state) {
    importBtn.classList.remove(
        'btn-primary', 'btn-success', 'btn-warning'
    );

    switch (state) {
        case 'clean':
            importBtn.classList.add('btn-success');
            importBtn.innerHTML = '<i class="bi bi-upload me-1"></i>Import';
            importBtn.title = 'Validation passed — safe to import.';
            break;
        case 'has_errors':
            importBtn.classList.add('btn-warning');
            importBtn.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Import anyway?';
            importBtn.title = 'Validation found errors. Rows with errors will be skipped.';
            break;
        default:
            importBtn.classList.add('btn-primary');
            importBtn.innerHTML = '<i class="bi bi-upload me-1"></i>Import';
            importBtn.title = '';
    }
}

if (importAnotherBtn) {
    importAnotherBtn.addEventListener('click', () => {
        importResults.classList.add('d-none');
        document.getElementById('remove-file-btn')?.click();
    });
}