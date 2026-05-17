'use strict';

import { API_URLS, URLS } from '../urls.js';
import { apiFetch } from '../main.js';

document.addEventListener('DOMContentLoaded', () => {
    _loadFYs();
    document.getElementById('back-btn').addEventListener('click', _showStep1);
});

async function _loadFYs() {
    try {
        const data = await apiFetch(API_URLS.financial_years.summary.href);
        _renderFYs(data || []);
    } catch (_) {
        document.getElementById('fy-loading').textContent = 'Failed to load financial years.';
    }
}

function _renderFYs(fys) {
    const loading = document.getElementById('fy-loading');
    const grid = document.getElementById('fy-grid');
    const empty = document.getElementById('fy-empty');
    loading.classList.add('d-none');
    if (!fys.length) { empty.classList.remove('d-none'); return; }
    grid.innerHTML = fys.map(fy => `
        <div class="col-6 col-sm-4 col-md-3 col-lg-2">
            <button class="rp-wizard-card w-100" data-fy-id="${fy.id}"
                data-fy-label="${_esc(fy.long_fy || fy.short_fy || '')}">
                <div class="rp-wizard-card-icon"><i class="bi bi-calendar3"></i></div>
                <div class="rp-wizard-card-label">${_esc(fy.short_fy || fy.long_fy || String(fy.id))}</div>
                <div class="rp-wizard-card-sub">${_esc(fy.long_fy || '')}</div>
            </button>
        </div>
    `).join('');
    grid.classList.remove('d-none');
    grid.querySelectorAll('.rp-wizard-card').forEach(btn =>
        btn.addEventListener('click', () => _selectFY(btn.dataset.fyId, btn.dataset.fyLabel))
    );
}

async function _selectFY(fyId, fyLabel) {
    document.getElementById('step1-content').classList.add('d-none');
    document.getElementById('step2-content').classList.remove('d-none');
    document.getElementById('selected-fy-label').textContent = `FY: ${fyLabel}`;
    _setStepActive(2);

    const loading = document.getElementById('sprint-loading');
    const grid = document.getElementById('sprint-grid');
    const empty = document.getElementById('sprint-empty');
    loading.classList.remove('d-none');
    grid.classList.add('d-none');
    grid.innerHTML = '';
    empty.classList.add('d-none');

    try {
        const sprints = await apiFetch(API_URLS.project_actuals.fy_sprints(fyId).href);
        loading.classList.add('d-none');
        _renderSprints(sprints || []);
    } catch (_) {
        loading.textContent = 'Failed to load sprints.';
    }
}

function _renderSprints(sprints) {
    const grid = document.getElementById('sprint-grid');
    const empty = document.getElementById('sprint-empty');
    if (!sprints.length) { empty.classList.remove('d-none'); return; }
    grid.innerHTML = sprints.map(s => `
        <div class="col-6 col-sm-4 col-md-3 col-lg-2">
            <a class="rp-wizard-card w-100 text-decoration-none" href="/recharges/${s.id}/">
                <div class="rp-wizard-card-icon"><i class="bi bi-lightning-charge"></i></div>
                <div class="rp-wizard-card-label">${_esc(s.sprint_name)}</div>
                <div class="rp-wizard-card-sub">Sprint ${s.sprint_number}</div>
            </a>
        </div>
    `).join('');
    grid.classList.remove('d-none');
}

function _showStep1() {
    document.getElementById('step2-content').classList.add('d-none');
    document.getElementById('step1-content').classList.remove('d-none');
    _setStepActive(1);
}

function _setStepActive(step) {
    document.getElementById('step1-dot').classList.toggle('rp-step-dot--active', step >= 1);
    document.getElementById('step2-dot').classList.toggle('rp-step-dot--active', step >= 2);
    document.getElementById('step1-label').classList.toggle('text-secondary', step < 1);
    document.getElementById('step2-label').classList.toggle('text-secondary', step < 2);
    document.getElementById('step1-label').classList.toggle('fw-semibold', step >= 1);
    document.getElementById('step2-label').classList.toggle('fw-semibold', step >= 2);
}

function _esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
