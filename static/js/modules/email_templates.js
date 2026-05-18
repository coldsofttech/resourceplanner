'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS, URLS } from '../urls.js';

const COLOR_ICON_MAP = {
    info:    'et-scenario-icon--info',
    warning: 'et-scenario-icon--warning',
    primary: 'et-scenario-icon--primary',
    success: 'et-scenario-icon--success',
};

document.addEventListener('DOMContentLoaded', async () => {
    const loading = document.getElementById('scenarios-loading');
    const grid    = document.getElementById('scenarios-grid');
    const error   = document.getElementById('scenarios-error');
    const cards   = document.getElementById('scenario-cards');

    let scenarios;
    try {
        scenarios = await apiFetch(API_URLS.email_templates.scenarios.href, { method: 'GET' });
    } catch (err) {
        loading.classList.add('d-none');
        error.classList.remove('d-none');
        document.getElementById('scenarios-error-msg').textContent =
            err?.data?.error || 'Failed to load scenarios. Please refresh.';
        return;
    }

    loading.classList.add('d-none');
    grid.classList.remove('d-none');

    cards.innerHTML = scenarios.map(s => _renderCard(s)).join('');
});

function _renderCard(s) {
    const iconClass = COLOR_ICON_MAP[s.color] || 'et-scenario-icon--info';
    const editorUrl = URLS.email_templates.editor(s.scenario);

    const statusBadge = s.has_template
        ? `<span class="rp-badge ${s.is_active ? 'rp-badge--success' : 'rp-badge--muted'}">
               <i class="bi ${s.is_active ? 'bi-check-circle-fill' : 'bi-dash-circle'} me-1"></i>
               ${s.is_active ? 'Active' : 'Inactive'}
           </span>`
        : `<span class="rp-badge rp-badge--muted">
               <i class="bi bi-dash me-1"></i>Not configured
           </span>`;

    const metaText = s.updated_at
        ? `Last saved ${_relativeTime(s.updated_at)}`
        : 'No template saved yet';

    return `
    <div class="col-md-6">
        <div class="et-scenario-card">
            <div class="et-scenario-card-header">
                <div class="et-scenario-icon ${iconClass}">
                    <i class="bi ${s.icon}"></i>
                </div>
                <div class="flex-fill min-width-0">
                    <div class="et-scenario-title">${_esc(s.label)}</div>
                    <div class="et-scenario-desc">${_esc(s.description)}</div>
                </div>
                ${statusBadge}
            </div>
            ${s.subject ? `<div class="px-4 py-2" style="font-size:12px;color:var(--rp-text-muted);border-bottom:1px solid var(--rp-border-color,#f3f4f6)">
                <i class="bi bi-envelope me-1 opacity-50"></i><em>${_esc(s.subject)}</em>
            </div>` : ''}
            <div class="et-scenario-footer">
                <span class="et-scenario-meta">${_esc(metaText)}</span>
                <a href="${editorUrl}" class="btn btn-sm btn-outline-secondary">
                    <i class="bi bi-pencil me-1"></i>${s.has_template ? 'Edit Template' : 'Configure'}
                </a>
            </div>
        </div>
    </div>`;
}

function _esc(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function _relativeTime(iso) {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60)   return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return new Date(iso).toLocaleDateString();
}
