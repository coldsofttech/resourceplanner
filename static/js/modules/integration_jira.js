'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import { createWizard, renderField } from '../wizard.js';

const STEPS = [
    { id: 'step-1', title: 'Connection' },
    { id: 'step-2', title: 'Credentials' },
];

document.addEventListener('DOMContentLoaded', async () => {
    let data;
    try {
        data = await apiFetch(API_URLS.integrations.jira.get.href, { method: 'GET' });
    } catch (_) {
        showFlash('Could not load Jira settings. Please refresh.', 'danger');
        return;
    }

    // JIRA_ENABLED — boolean select
    const enabledCfg = data['JIRA_ENABLED'];
    if (enabledCfg) {
        const cur = enabledCfg.value === 'true' ? 'true' : 'false';
        document.getElementById('ctrl-JIRA_ENABLED').innerHTML = `
            <select id="inp-JIRA_ENABLED" class="form-select rp-input" style="max-width:200px;">
                <option value="true"  ${cur === 'true'  ? 'selected' : ''}>Enabled</option>
                <option value="false" ${cur === 'false' ? 'selected' : ''}>Disabled</option>
            </select>`;
    }

    ['JIRA_URL', 'JIRA_EMAIL', 'JIRA_API_TOKEN', 'JIRA_PROJECT_KEY'].forEach(code => {
        const cfg = data[code];
        if (!cfg) return;
        const container = document.getElementById(`ctrl-${code}`);
        if (container) renderField(container, cfg, `inp-${code}`);
    });

    document.getElementById('ctrl-JIRA_AUTH_MODE').value = data['JIRA_AUTH_MODE']?.value || 'token';

    createWizard({
        steps: STEPS,
        progressId: 'wizard-progress',
        backId: 'wizard-back',
        nextId: 'wizard-next',
        saveId: 'wizard-save',
        onSave: () => saveAll(),
    }).goTo(0);
});

async function saveAll() {
    const token = document.getElementById('inp-JIRA_API_TOKEN')?.value?.trim();
    const payload = {
        JIRA_ENABLED:     document.getElementById('inp-JIRA_ENABLED')?.value ?? 'false',
        JIRA_URL:         document.getElementById('inp-JIRA_URL')?.value?.trim() ?? '',
        JIRA_AUTH_MODE:   document.getElementById('ctrl-JIRA_AUTH_MODE')?.value ?? 'token',
        JIRA_EMAIL:       document.getElementById('inp-JIRA_EMAIL')?.value?.trim() ?? '',
        JIRA_PROJECT_KEY: document.getElementById('inp-JIRA_PROJECT_KEY')?.value?.trim() ?? '',
    };
    if (token) payload['JIRA_API_TOKEN'] = token;

    const saveBtn = document.getElementById('wizard-save');
    const orig = saveBtn?.innerHTML;
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…'; }

    try {
        await apiFetch(API_URLS.integrations.jira.patch.href, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        showFlash('Jira integration settings saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = orig; }
    }
}
