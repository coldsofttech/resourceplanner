'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import { createWizard, renderField } from '../wizard.js';

const STEPS = [
    { id: 'step-1', title: 'Authentication' },
    { id: 'step-2', title: 'Session' },
];

document.addEventListener('DOMContentLoaded', async () => {
    let data;
    try {
        data = await apiFetch(API_URLS.security.get.href, { method: 'GET' });
    } catch (_) {
        showFlash('Could not load security settings. Please refresh.', 'danger');
        return;
    }

    document.getElementById('ctrl-AUTH_MODE').value = data['AUTH_MODE']?.value || 'classic';
    document.getElementById('ctrl-ALLOW_REGISTRATION').value =
        data['ALLOW_REGISTRATION']?.value === 'true' ? 'true' : 'false';

    const timeoutCfg = data['SESSION_TIMEOUT_MINUTES'];
    if (timeoutCfg) {
        renderField(document.getElementById('ctrl-SESSION_TIMEOUT_MINUTES'), timeoutCfg, 'inp-SESSION_TIMEOUT_MINUTES');
    }

    updateSsoWarning();

    createWizard({
        steps: STEPS,
        progressId: 'wizard-progress',
        backId: 'wizard-back',
        nextId: 'wizard-next',
        saveId: 'wizard-save',
        onSave: () => saveAll(),
    }).goTo(0);

    document.getElementById('ctrl-AUTH_MODE').addEventListener('change', updateSsoWarning);
});

function updateSsoWarning() {
    const mode = document.getElementById('ctrl-AUTH_MODE')?.value ?? 'classic';
    document.getElementById('sso-warning').classList.toggle('d-none', mode !== 'sso');
}

async function saveAll() {
    const payload = {
        AUTH_MODE:               document.getElementById('ctrl-AUTH_MODE')?.value ?? 'classic',
        ALLOW_REGISTRATION:      document.getElementById('ctrl-ALLOW_REGISTRATION')?.value ?? 'true',
        SESSION_TIMEOUT_MINUTES: document.getElementById('inp-SESSION_TIMEOUT_MINUTES')?.value ?? '480',
    };

    const saveBtn = document.getElementById('wizard-save');
    const orig = saveBtn?.innerHTML;
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…'; }

    try {
        await apiFetch(API_URLS.security.patch.href, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        showFlash('Security settings saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = orig; }
    }
}
