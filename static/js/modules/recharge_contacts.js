'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';

const API_MODULE = `${location.origin}/api/v1/recharge-contacts/`;

let _contacts = [];
let _config   = {};

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const [contactsResp, configData] = await Promise.all([
            apiFetch(`${API_URLS.contacts.list.href}?page_size=200`, { method: 'GET' }),
            apiFetch(API_MODULE, { method: 'GET' }),
        ]);
        _contacts = contactsResp.results ?? contactsResp ?? [];
        _config   = configData;
    } catch (_) {
        showFlash('Could not load recharge contact settings. Please refresh.', 'danger');
        return;
    }

    const raw = _config['RECHARGE_CC_CONTACTS']?.value ?? '';
    const selected = new Set(raw.split(',').map(s => s.trim()).filter(Boolean).map(Number));
    renderChecklist('ctrl-RECHARGE_CC_CONTACTS', _contacts, selected);

    document.getElementById('rc-save')?.addEventListener('click', saveAll);
});

function renderChecklist(containerId, items, selectedIds) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!items.length) {
        container.innerHTML = '<p class="text-muted small mb-0">No contacts available.</p>';
        return;
    }

    container.innerHTML = items.map(item => {
        const checked = selectedIds.has(item.id) ? 'checked' : '';
        const subtitle = item.email ? `<small class="text-muted ms-1">${escHtml(item.email)}</small>` : '';
        return `
        <div class="form-check">
            <input class="form-check-input" type="checkbox" value="${item.id}"
                   id="chk-rc-${item.id}" data-ctrl="${containerId}" ${checked}>
            <label class="form-check-label" for="chk-rc-${item.id}">
                ${escHtml(item.name ?? '')}${subtitle}
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

async function saveAll() {
    const payload = { RECHARGE_CC_CONTACTS: getChecked('ctrl-RECHARGE_CC_CONTACTS') };

    const btn = document.getElementById('rc-save');
    const orig = btn?.innerHTML;
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…'; }

    try {
        await apiFetch(API_MODULE, { method: 'PATCH', body: JSON.stringify(payload) });
        showFlash('Recharge contact settings saved successfully.', 'success');
    } catch (err) {
        showFlash(err?.data?.error || 'Save failed. Please try again.', 'danger');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = orig; }
    }
}
