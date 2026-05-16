'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch } from '../main.js';

let _showDetail = false;

document.addEventListener('DOMContentLoaded', () => {
    _loadDropdowns();
    _loadRecharges();

    ['filter-fy', 'filter-sprint', 'filter-type', 'filter-programme', 'filter-project'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            _loadRecharges();
            if (_showDetail) _loadDetails();
        });
    });

    document.getElementById('toggle-detail-btn').addEventListener('click', () => {
        _showDetail = !_showDetail;
        const btn = document.getElementById('toggle-detail-btn');
        const card = document.getElementById('detail-card');
        btn.innerHTML = _showDetail
            ? '<i class="bi bi-list-ul me-1"></i>Hide Engineer Detail'
            : '<i class="bi bi-list-ul me-1"></i>Show Engineer Detail';
        if (_showDetail) {
            card.classList.remove('d-none');
            _loadDetails();
        } else {
            card.classList.add('d-none');
        }
    });
});

async function _loadDropdowns() {
    try {
        const [fys, sprints, programmes, projects] = await Promise.all([
            apiFetch(API_URLS.financial_years.summary.href),
            apiFetch(API_URLS.sprints.summary.href),
            apiFetch(API_URLS.recharges.programme_options.href),
            apiFetch(API_URLS.recharges.project_options.href),
        ]);

        const fySel = document.getElementById('filter-fy');
        (fys || []).forEach(fy => {
            const opt = document.createElement('option');
            opt.value = fy.id;
            opt.textContent = fy.long_fy || fy.short_fy || String(fy.id);
            fySel.appendChild(opt);
        });

        const sprintSel = document.getElementById('filter-sprint');
        (sprints || []).forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.sprint_name;
            sprintSel.appendChild(opt);
        });

        const progSel = document.getElementById('filter-programme');
        (programmes || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            progSel.appendChild(opt);
        });

        const projSel = document.getElementById('filter-project');
        (projects || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            projSel.appendChild(opt);
        });
    } catch (_) { /* non-critical */ }
}

async function _loadRecharges() {
    _showLoading('recharges');
    try {
        const params = _buildParams();
        const url = API_URLS.recharges.list.href + (params ? '?' + params : '');
        const data = await fetch(url).then(r => r.json());
        _renderRecharges(data || []);
    } catch (e) {
        _showError('recharges');
    }
}

async function _loadDetails() {
    _showLoading('detail');
    try {
        const params = _buildParams();
        const url = API_URLS.recharge_details.list.href + (params ? '?' + params : '');
        const data = await fetch(url).then(r => r.json());
        _renderDetails(data || []);
    } catch (e) {
        _showError('detail');
    }
}

function _buildParams() {
    const parts = [];
    const fy = document.getElementById('filter-fy').value;
    const sprint = document.getElementById('filter-sprint').value;
    const type = document.getElementById('filter-type').value;
    const prog = document.getElementById('filter-programme').value;
    const proj = document.getElementById('filter-project').value;
    if (fy) parts.push('fy_id=' + fy);
    if (sprint) parts.push('sprint_id=' + sprint);
    if (type) parts.push('type=' + type);
    if (prog) parts.push('programme_id=' + prog);
    if (proj) parts.push('project_id=' + proj);
    return parts.join('&');
}

function _renderRecharges(rows) {
    const wrap = document.getElementById('recharges-table-wrap');
    const empty = document.getElementById('recharges-empty');
    const loading = document.getElementById('recharges-loading');
    const count = document.getElementById('recharge-count');
    loading.classList.add('d-none');
    count.textContent = `${rows.length} record(s)`;

    if (!rows.length) {
        wrap.classList.add('d-none');
        empty.classList.remove('d-none');
        return;
    }
    empty.classList.add('d-none');
    wrap.classList.remove('d-none');

    document.getElementById('recharges-tbody').innerHTML = rows.map(r => {
        const finContacts = (r.finance_contact_emails || []).join(', ') || '—';
        const projContacts = (r.project_contact_emails || []).join(', ') || '—';
        const storyBtn = r.stories && r.stories.length
            ? `<button class="btn btn-ghost-icon btn-sm view-stories-btn"
                data-stories='${JSON.stringify(r.stories).replace(/'/g, "&#39;")}'
                data-project="${_esc(r.project_name || '—')}"
                title="View stories"><i class="bi bi-list-task"></i></button>`
            : '';
        const typeCls = r.type === 'FORECAST' ? 'rp-badge--info' : 'rp-badge--warning';
        return `<tr>
            <td>${_esc(r.sprint_name || '—')}</td>
            <td><span class="rp-badge ${typeCls}">${_esc(r.type)}</span></td>
            <td>${_esc(r.programme_name || '—')}</td>
            <td>${_esc(r.project_name || '—')}</td>
            <td class="text-end font-mono">${parseFloat(r.total_days).toFixed(2)}</td>
            <td class="text-end font-mono">${parseFloat(r.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
            <td style="font-size:12px">${_esc(finContacts)}</td>
            <td style="font-size:12px">${_esc(projContacts)}</td>
            <td>${storyBtn}</td>
        </tr>`;
    }).join('');

    document.querySelectorAll('.view-stories-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const stories = JSON.parse(btn.dataset.stories);
            _openStoriesModal(btn.dataset.project, stories);
        });
    });
}

function _renderDetails(rows) {
    const wrap = document.getElementById('detail-table-wrap');
    const empty = document.getElementById('detail-empty');
    const loading = document.getElementById('detail-loading');
    const count = document.getElementById('detail-count');
    loading.classList.add('d-none');
    count.textContent = `${rows.length} record(s)`;

    if (!rows.length) {
        wrap.classList.add('d-none');
        empty.classList.remove('d-none');
        return;
    }
    empty.classList.add('d-none');
    wrap.classList.remove('d-none');

    const typeCls = t => t === 'FORECAST' ? 'rp-badge--info' : 'rp-badge--warning';
    document.getElementById('detail-tbody').innerHTML = rows.map(r => `<tr>
        <td>${_esc(r.sprint_name || '—')}</td>
        <td>${_esc(r.team_name || '—')}</td>
        <td>${_esc(r.assignee_name || '—')}</td>
        <td>${_esc(r.programme_name || '—')}</td>
        <td>${_esc(r.project_name || '—')}</td>
        <td>${_esc(r.label_name || '—')}</td>
        <td><span class="rp-badge ${typeCls(r.type)}">${_esc(r.type)}</span></td>
        <td class="text-end font-mono">${parseFloat(r.total_days).toFixed(2)}</td>
        <td class="text-end font-mono">${parseFloat(r.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
    </tr>`).join('');
}

function _openStoriesModal(projectName, stories) {
    document.getElementById('stories-modal-title').textContent = `Stories — ${projectName}`;
    document.getElementById('stories-tbody').innerHTML = stories.map(s => `<tr>
        <td><code>${_esc(s.jira_id || '—')}</code></td>
        <td>${_esc(s.title || '—')}</td>
        <td class="text-end font-mono">${parseFloat(s.total_days).toFixed(2)}</td>
    </tr>`).join('');
    new bootstrap.Modal(document.getElementById('storiesModal')).show();
}

function _showLoading(prefix) {
    document.getElementById(`${prefix}-loading`).classList.remove('d-none');
    document.getElementById(`${prefix}-table-wrap`).classList.add('d-none');
    document.getElementById(`${prefix}-empty`).classList.add('d-none');
}

function _showError(prefix) {
    document.getElementById(`${prefix}-loading`).classList.add('d-none');
    document.getElementById(`${prefix}-empty`).innerHTML = 'Failed to load data.';
    document.getElementById(`${prefix}-empty`).classList.remove('d-none');
}

function _esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
