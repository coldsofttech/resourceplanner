'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import { createWizard, renderField, setFieldError, clearFieldError } from '../wizard.js';

const STEPS = [
    { id: 'step-1', title: 'Strength' },
    { id: 'step-2', title: 'History & Rotation' },
];

const BOOL_FIELDS = [
    'PASSWORD_REQUIRE_UPPERCASE', 'PASSWORD_REQUIRE_LOWERCASE',
    'PASSWORD_REQUIRE_DIGITS', 'PASSWORD_REQUIRE_SPECIAL',
];
const INT_FIELDS = ['PASSWORD_MIN_LENGTH', 'PASSWORD_HISTORY_COUNT', 'PASSWORD_ROTATION_DAYS'];

document.addEventListener('DOMContentLoaded', async () => {
    let data;
    try {
        data = await apiFetch(API_URLS.security.password_policy.get.href, { method: 'GET' });
    } catch (_) {
        showFlash('Could not load password policy settings. Please refresh.', 'danger');
        return;
    }

    [...BOOL_FIELDS, ...INT_FIELDS].forEach(code => {
        const cfg = data[code];
        if (!cfg) return;
        const container = document.getElementById(`ctrl-${code}`);
        if (!container) return;

        if (BOOL_FIELDS.includes(code)) {
            const cur = cfg.value === 'true' ? 'true' : 'false';
            container.innerHTML = `
                <select id="inp-${code}" class="form-select rp-input" style="max-width:200px;">
                    <option value="true"  ${cur === 'true'  ? 'selected' : ''}>Required</option>
                    <option value="false" ${cur === 'false' ? 'selected' : ''}>Not required</option>
                </select>`;
        } else {
            renderField(container, cfg, `inp-${code}`);
        }
    });

    createWizard({
        steps: STEPS,
        progressId: 'wizard-progress',
        backId: 'wizard-back',
        nextId: 'wizard-next',
        saveId: 'wizard-save',
        onValidate,
        onSave: () => saveAll(),
    }).goTo(0);
});

function onValidate(stepIndex) {
    let valid = true;
    if (stepIndex === 0) {
        const minLen = parseInt(document.getElementById('inp-PASSWORD_MIN_LENGTH')?.value ?? '8', 10);
        if (isNaN(minLen) || minLen < 1) {
            setFieldError('inp-PASSWORD_MIN_LENGTH', 'Minimum length must be at least 1.');
            valid = false;
        } else {
            clearFieldError('inp-PASSWORD_MIN_LENGTH');
        }
    }
    return valid;
}

async function saveAll() {
    const payload = {};
    [...BOOL_FIELDS, ...INT_FIELDS].forEach(code => {
        const el = document.getElementById(`inp-${code}`);
        if (el) payload[code] = el.value;
    });

    const saveBtn = document.getElementById('wizard-save');
    const orig = saveBtn?.innerHTML;
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…'; }

    try {
        await apiFetch(API_URLS.security.password_policy.patch.href, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        showFlash('Password policy saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = orig; }
    }
}
