'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import { createWizard } from '../wizard.js';

const API_MODULE = `${location.origin}/api/v1/project-approval/`;

const STEPS = [
    { id: 'step-1', title: 'Recipient Roles' },
    { id: 'step-2', title: 'Contacts' },
    { id: 'step-3', title: 'Run Cost' },
];

// ── state ────────────────────────────────────────────────────────────────────

const state = {
    roles: [],
    contacts: [],
    projectTypes: [],
    config: {},
};

// ── init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const [rolesResp, contactsResp, typesResp, configData] = await Promise.all([
            apiFetch(`${API_URLS.roles.list.href}?page_size=200&active_only=true`, { method: 'GET' }),
            apiFetch(`${API_URLS.contacts.list.href}?page_size=200`, { method: 'GET' }),
            apiFetch(`${API_URLS.project_types.list.href}?page_size=200&active_only=true`, { method: 'GET' }),
            apiFetch(API_MODULE, { method: 'GET' }),
        ]);
        state.roles = rolesResp.results ?? rolesResp ?? [];
        state.contacts = contactsResp.results ?? contactsResp ?? [];
        state.projectTypes = typesResp.results ?? typesResp ?? [];
        state.config = configData;
    } catch (_) {
        showFlash('Could not load project approval settings. Please refresh.', 'danger');
        return;
    }

    renderChecklist('ctrl-PROJECT_APPROVAL_NOTIFY_ROLES', state.roles, 'role', getSelected('PROJECT_APPROVAL_NOTIFY_ROLES'));
    renderChecklist('ctrl-PROJECT_APPROVAL_RECHARGE_CONTACT_ROLES', state.roles, 'role', getSelected('PROJECT_APPROVAL_RECHARGE_CONTACT_ROLES'));
    renderChecklist('ctrl-PROJECT_APPROVAL_INFO_CONTACTS', state.contacts, 'name', getSelected('PROJECT_APPROVAL_INFO_CONTACTS'), 'email');
    renderChecklist('ctrl-PROJECT_APPROVAL_FINOPS_CONTACTS', state.contacts, 'name', getSelected('PROJECT_APPROVAL_FINOPS_CONTACTS'), 'email');
    renderChecklist('ctrl-PROJECT_APPROVAL_CHARGE_TYPES', state.projectTypes, 'name', getSelected('PROJECT_APPROVAL_CHARGE_TYPES'));
    renderChecklist('ctrl-PROJECT_APPROVAL_NO_CHARGE_TYPES', state.projectTypes, 'name', getSelected('PROJECT_APPROVAL_NO_CHARGE_TYPES'));

    createWizard({
        steps: STEPS,
        progressId: 'wizard-progress',
        backId: 'wizard-back',
        nextId: 'wizard-next',
        saveId: 'wizard-save',
        onSave: saveAll,
    }).goTo(0);
});

// ── helpers ───────────────────────────────────────────────────────────────────

function getSelected(code) {
    const raw = state.config[code]?.value ?? '';
    return new Set(raw.split(',').map(s => s.trim()).filter(Boolean).map(Number));
}

function renderChecklist(containerId, items, labelField, selectedIds, subtitleField = null) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!items.length) {
        container.innerHTML = '<p class="text-muted small mb-0">No options available.</p>';
        return;
    }

    container.innerHTML = items.map(item => {
        const checked = selectedIds.has(item.id) ? 'checked' : '';
        const subtitle = subtitleField ? `<small class="text-muted ms-1">${escHtml(item[subtitleField] ?? '')}</small>` : '';
        return `
        <div class="form-check">
            <input class="form-check-input" type="checkbox" value="${item.id}"
                   id="chk-${containerId}-${item.id}" data-ctrl="${containerId}" ${checked}>
            <label class="form-check-label" for="chk-${containerId}-${item.id}">
                ${escHtml(item[labelField] ?? '')}${subtitle}
            </label>
        </div>`;
    }).join('');
}

function getChecked(containerId) {
    return Array.from(
        document.querySelectorAll(`[data-ctrl="${containerId}"]:checked`)
    ).map(el => el.value).join(',');
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── save ──────────────────────────────────────────────────────────────────────

async function saveAll() {
    const payload = {
        PROJECT_APPROVAL_NOTIFY_ROLES:            getChecked('ctrl-PROJECT_APPROVAL_NOTIFY_ROLES'),
        PROJECT_APPROVAL_RECHARGE_CONTACT_ROLES:  getChecked('ctrl-PROJECT_APPROVAL_RECHARGE_CONTACT_ROLES'),
        PROJECT_APPROVAL_INFO_CONTACTS:           getChecked('ctrl-PROJECT_APPROVAL_INFO_CONTACTS'),
        PROJECT_APPROVAL_FINOPS_CONTACTS:         getChecked('ctrl-PROJECT_APPROVAL_FINOPS_CONTACTS'),
        PROJECT_APPROVAL_CHARGE_TYPES:            getChecked('ctrl-PROJECT_APPROVAL_CHARGE_TYPES'),
        PROJECT_APPROVAL_NO_CHARGE_TYPES:         getChecked('ctrl-PROJECT_APPROVAL_NO_CHARGE_TYPES'),
    };

    const saveBtn = document.getElementById('wizard-save');
    const orig = saveBtn?.innerHTML;
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…';
    }

    try {
        await apiFetch(API_MODULE, { method: 'PATCH', body: JSON.stringify(payload) });
        showFlash('Project approval settings saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = orig; }
    }
}
