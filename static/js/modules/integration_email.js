'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import { createWizard, renderField, setFieldError, clearFieldError } from '../wizard.js';

const STEPS = [
    { id: 'step-1', title: 'Protocol & Server' },
    { id: 'step-2', title: 'Auth & Sender' },
];

const PLAIN_FIELDS = ['EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_FROM'];
const SECRET_FIELDS = ['EMAIL_HOST_PASSWORD'];

document.addEventListener('DOMContentLoaded', async () => {
    let data;
    try {
        data = await apiFetch(API_URLS.integrations.email.get.href, { method: 'GET' });
    } catch (_) {
        showFlash('Could not load email settings. Please refresh.', 'danger');
        return;
    }

    // Populate selects
    document.getElementById('ctrl-EMAIL_PROTOCOL').value = data['EMAIL_PROTOCOL']?.value || 'console';
    updateSmtpPanel();

    [...PLAIN_FIELDS, ...SECRET_FIELDS].forEach(code => {
        const cfg = data[code];
        if (!cfg) return;
        const container = document.getElementById(`ctrl-${code}`);
        if (container) renderField(container, cfg, `inp-${code}`);
    });

    const wizard = createWizard({
        steps: STEPS,
        progressId: 'wizard-progress',
        backId: 'wizard-back',
        nextId: 'wizard-next',
        saveId: 'wizard-save',
        onValidate,
        onSave: () => saveAll(),
    });
    wizard.goTo(0);

    document.getElementById('ctrl-EMAIL_PROTOCOL').addEventListener('change', updateSmtpPanel);
});

function updateSmtpPanel() {
    const protocol = document.getElementById('ctrl-EMAIL_PROTOCOL')?.value ?? 'console';
    document.getElementById('panel-smtp-server').classList.toggle('d-none', protocol === 'console');
}

function onValidate(stepIndex) {
    let valid = true;
    if (stepIndex === 1) {
        const from = document.getElementById('inp-EMAIL_FROM')?.value?.trim();
        if (!from) {
            setFieldError('inp-EMAIL_FROM', 'From address is required.');
            valid = false;
        } else {
            clearFieldError('inp-EMAIL_FROM');
        }
    }
    return valid;
}

async function saveAll() {
    const payload = {
        EMAIL_PROTOCOL: document.getElementById('ctrl-EMAIL_PROTOCOL')?.value ?? 'console',
        EMAIL_HOST:     document.getElementById('inp-EMAIL_HOST')?.value?.trim() ?? '',
        EMAIL_PORT:     document.getElementById('inp-EMAIL_PORT')?.value ?? '25',
        EMAIL_HOST_USER: document.getElementById('inp-EMAIL_HOST_USER')?.value?.trim() ?? '',
        EMAIL_FROM:     document.getElementById('inp-EMAIL_FROM')?.value?.trim() ?? '',
    };
    const pwd = document.getElementById('inp-EMAIL_HOST_PASSWORD')?.value?.trim();
    if (pwd) payload['EMAIL_HOST_PASSWORD'] = pwd;

    const saveBtn = document.getElementById('wizard-save');
    const orig = saveBtn?.innerHTML;
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…'; }

    try {
        await apiFetch(API_URLS.integrations.email.patch.href, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        showFlash('Email settings saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = orig; }
    }
}
