'use strict';

import { apiFetch, showFlash, setSubmitting } from '../main.js';
import { API_URLS } from '../urls.js';
import { createWizard, renderField, getFieldValue, setFieldError, clearFieldError } from '../wizard.js';

const STEPS = [
    { id: 'step-1', title: 'Enable & Provider' },
    { id: 'step-2', title: 'Credentials' },
    { id: 'step-3', title: 'Model' },
];

const FIELDS = [
    'AI_ENABLED', 'AI_PROVIDER',
    'AI_ANTHROPIC_API_KEY',
    'AI_BEDROCK_REGION', 'AI_BEDROCK_AUTH_MODE', 'AI_BEDROCK_IAM_KEY', 'AI_BEDROCK_IAM_SECRET',
    'AI_MODEL',
];

let configData = {};

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const data = await apiFetch(API_URLS.integrations.ai.get.href, { method: 'GET' });
        configData = data;
        populateFields(data);
    } catch (_) {
        showFlash('Could not load AI integration settings. Please refresh.', 'danger');
        return;
    }

    const wizard = createWizard({
        steps: STEPS,
        progressId: 'wizard-progress',
        backId: 'wizard-back',
        nextId: 'wizard-next',
        saveId: 'wizard-save',
        onValidate,
        onSave: () => saveAll(wizard),
    });
    wizard.goTo(0);

    // Show/hide Anthropic vs Bedrock panels when provider changes
    document.getElementById('ctrl-AI_PROVIDER').addEventListener('change', updateProviderPanels);

    // Show/hide IAM key panel when bedrock auth mode changes
    document.getElementById('ctrl-AI_BEDROCK_AUTH_MODE').addEventListener('change', updateBedrockAuthPanel);
});

function populateFields(data) {
    FIELDS.forEach(code => {
        const cfg = data[code];
        if (!cfg) return;
        const container = document.getElementById(`ctrl-${code}`);
        if (!container) return;

        if (code === 'AI_PROVIDER') {
            document.getElementById('ctrl-AI_PROVIDER').value = cfg.value || 'anthropic';
            updateProviderPanels();
        } else if (code === 'AI_BEDROCK_AUTH_MODE') {
            document.getElementById('ctrl-AI_BEDROCK_AUTH_MODE').value = cfg.value || 'role';
            updateBedrockAuthPanel();
        } else {
            renderField(container, cfg, `inp-${code}`);
        }
    });

    // Boolean for AI_ENABLED: swap to select
    const enabledCfg = data['AI_ENABLED'];
    if (enabledCfg) {
        const container = document.getElementById('ctrl-AI_ENABLED');
        const cur = enabledCfg.value === 'true' ? 'true' : 'false';
        container.innerHTML = `
            <select id="inp-AI_ENABLED" class="form-select rp-input" style="max-width:200px;">
                <option value="true"  ${cur === 'true'  ? 'selected' : ''}>Enabled</option>
                <option value="false" ${cur === 'false' ? 'selected' : ''}>Disabled</option>
            </select>`;
    }
}

function updateProviderPanels() {
    const provider = document.getElementById('ctrl-AI_PROVIDER')?.value ?? 'anthropic';
    document.getElementById('panel-anthropic').classList.toggle('d-none', provider !== 'anthropic');
    document.getElementById('panel-bedrock').classList.toggle('d-none', provider !== 'bedrock');
}

function updateBedrockAuthPanel() {
    const mode = document.getElementById('ctrl-AI_BEDROCK_AUTH_MODE')?.value ?? 'role';
    document.getElementById('panel-bedrock-iam').classList.toggle('d-none', mode !== 'user');
}

function onValidate(stepIndex) {
    let valid = true;

    if (stepIndex === 2) {
        const model = document.getElementById('inp-AI_MODEL')?.value?.trim();
        if (!model) {
            setFieldError('inp-AI_MODEL', 'Model identifier is required.');
            valid = false;
        } else {
            clearFieldError('inp-AI_MODEL');
        }
    }
    return valid;
}

async function saveAll(wizard) {
    const provider = document.getElementById('ctrl-AI_PROVIDER')?.value ?? 'anthropic';
    const authMode = document.getElementById('ctrl-AI_BEDROCK_AUTH_MODE')?.value ?? 'role';

    const payload = {
        AI_ENABLED: document.getElementById('inp-AI_ENABLED')?.value ?? 'false',
        AI_PROVIDER: provider,
        AI_MODEL: document.getElementById('inp-AI_MODEL')?.value?.trim() ?? '',
    };

    if (provider === 'anthropic') {
        const key = document.getElementById('inp-AI_ANTHROPIC_API_KEY')?.value?.trim();
        if (key) payload['AI_ANTHROPIC_API_KEY'] = key;
    } else {
        payload['AI_BEDROCK_REGION'] = document.getElementById('inp-AI_BEDROCK_REGION')?.value?.trim() ?? '';
        payload['AI_BEDROCK_AUTH_MODE'] = authMode;
        if (authMode === 'user') {
            const iamKey = document.getElementById('inp-AI_BEDROCK_IAM_KEY')?.value?.trim();
            const iamSecret = document.getElementById('inp-AI_BEDROCK_IAM_SECRET')?.value?.trim();
            if (iamKey) payload['AI_BEDROCK_IAM_KEY'] = iamKey;
            if (iamSecret) payload['AI_BEDROCK_IAM_SECRET'] = iamSecret;
        }
    }

    const saveBtn = document.getElementById('wizard-save');
    const orig = saveBtn?.innerHTML;
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…';
    }

    try {
        await apiFetch(API_URLS.integrations.ai.patch.href, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        showFlash('AI integration settings saved successfully.', 'success');
    } catch (err) {
        const msg = err?.data?.error || err?.data?.errors?.join(', ') || 'Save failed. Please try again.';
        showFlash(msg, 'danger');
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = orig; }
    }
}
