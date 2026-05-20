'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import { createWizard, renderField } from '../wizard.js';

const STEPS = [
    { id: 'step-1', title: 'Protocol & Provider' },
    { id: 'step-2', title: 'Configuration' },
];

const OAUTH2_FIELDS = [
    'SSO_OAUTH2_CLIENT_ID', 'SSO_OAUTH2_CLIENT_SECRET',
    'SSO_OAUTH2_AUTH_URL', 'SSO_OAUTH2_TOKEN_URL', 'SSO_OAUTH2_USERINFO_URL', 'SSO_OAUTH2_SCOPE',
];
const SAML_FIELDS = [
    'SSO_SAML_IDP_ENTITY_ID', 'SSO_SAML_IDP_SSO_URL', 'SSO_SAML_IDP_CERT',
    'SSO_SAML_SP_ENTITY_ID', 'SSO_SAML_SP_ACS_URL',
];

document.addEventListener('DOMContentLoaded', async () => {
    let data;
    try {
        data = await apiFetch(API_URLS.integrations.sso.get.href, { method: 'GET' });
    } catch (_) {
        showFlash('Could not load SSO settings. Please refresh.', 'danger');
        return;
    }

    document.getElementById('ctrl-SSO_PROTOCOL').value = data['SSO_PROTOCOL']?.value || 'oauth2';

    const nameContainer = document.getElementById('ctrl-SSO_PROVIDER_NAME');
    if (nameContainer && data['SSO_PROVIDER_NAME']) {
        renderField(nameContainer, data['SSO_PROVIDER_NAME'], 'inp-SSO_PROVIDER_NAME');
    }

    [...OAUTH2_FIELDS, ...SAML_FIELDS].forEach(code => {
        const cfg = data[code];
        if (!cfg) return;
        const container = document.getElementById(`ctrl-${code}`);
        if (container) renderField(container, cfg, `inp-${code}`);
    });

    updateProtocolPanels();

    const wizard = createWizard({
        steps: STEPS,
        progressId: 'wizard-progress',
        backId: 'wizard-back',
        nextId: 'wizard-next',
        saveId: 'wizard-save',
        onSave: () => saveAll(),
    });
    wizard.goTo(0);

    document.getElementById('ctrl-SSO_PROTOCOL').addEventListener('change', updateProtocolPanels);
});

function updateProtocolPanels() {
    const protocol = document.getElementById('ctrl-SSO_PROTOCOL')?.value ?? 'oauth2';
    document.getElementById('panel-oauth2').classList.toggle('d-none', protocol !== 'oauth2');
    document.getElementById('panel-saml').classList.toggle('d-none',   protocol !== 'saml');

    // Show the relevant generated-config card
    document.getElementById('generated-oauth2')?.classList.toggle('d-none', protocol !== 'oauth2');
    document.getElementById('generated-saml')?.classList.toggle('d-none',   protocol !== 'saml');

    // Auto-fill SP Entity ID and ACS URL when switching to SAML and fields are blank
    if (protocol === 'saml') {
        const entityEl = document.getElementById('inp-SSO_SAML_SP_ENTITY_ID');
        const acsEl    = document.getElementById('inp-SSO_SAML_SP_ACS_URL');
        const entity   = document.getElementById('gen-saml-entity')?.textContent?.trim();
        const acs      = document.getElementById('gen-saml-acs')?.textContent?.trim();
        if (entityEl && !entityEl.value && entity) entityEl.value = entity;
        if (acsEl    && !acsEl.value    && acs)    acsEl.value = acs;
    }
}

window.rpCopyText = function(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const text = el.textContent || el.value || '';
    navigator.clipboard?.writeText(text).catch(() => {});
};

async function saveAll() {
    const protocol = document.getElementById('ctrl-SSO_PROTOCOL')?.value ?? 'oauth2';
    const payload = {
        SSO_PROTOCOL: protocol,
        SSO_PROVIDER_NAME: document.getElementById('inp-SSO_PROVIDER_NAME')?.value?.trim() ?? '',
    };

    if (protocol === 'oauth2') {
        OAUTH2_FIELDS.forEach(code => {
            const val = document.getElementById(`inp-${code}`)?.value?.trim();
            if (val !== undefined) {
                const cfg = { is_secret: code.endsWith('_ID') || code.endsWith('_SECRET') };
                if (!cfg.is_secret || val) payload[code] = val;
            }
        });
    } else {
        SAML_FIELDS.forEach(code => {
            const val = document.getElementById(`inp-${code}`)?.value?.trim();
            if (val !== undefined) {
                const isSecret = code === 'SSO_SAML_IDP_CERT';
                if (!isSecret || val) payload[code] = val;
            }
        });
    }

    const saveBtn = document.getElementById('wizard-save');
    const orig = saveBtn?.innerHTML;
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…'; }

    try {
        await apiFetch(API_URLS.integrations.sso.patch.href, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        showFlash('SSO settings saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = orig; }
    }
}
