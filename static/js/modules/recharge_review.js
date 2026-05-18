'use strict';

import { API_URLS } from '../urls.js';
import { apiFetch } from '../main.js';

const SPRINT_ID = window.SPRINT_ID;
const RECHARGE_TYPE = window.RECHARGE_TYPE;

let _entries = [];

document.addEventListener('DOMContentLoaded', () => {
    _loadReview();
    document.getElementById('trigger-all-btn').addEventListener('click', _triggerAll);
    document.getElementById('manage-groups-btn').addEventListener('click', _openManageGroups);
    document.getElementById('add-group-btn').addEventListener('click', _addGroup);
});

async function _loadReview() {
    try {
        const data = await apiFetch(
            `${API_URLS.recharges.email_review.href}?sprint_id=${SPRINT_ID}&type=${RECHARGE_TYPE}`
        );
        document.getElementById('review-loading').classList.add('d-none');
        _entries = data || [];
        if (!_entries.length) {
            document.getElementById('review-empty').classList.remove('d-none');
            return;
        }
        _renderAccordion(_entries);
        document.getElementById('review-accordion').classList.remove('d-none');
    } catch (e) {
        document.getElementById('review-loading').textContent = 'Failed to load email review data.';
    }
}

function _renderAccordion(entries) {
    const acc = document.getElementById('review-accordion');
    acc.innerHTML = entries.map((entry, idx) => {
        const label = entry.group_name
            ? `<span class="rp-badge rp-badge--muted me-2"><i class="bi bi-diagram-3 me-1"></i>${_esc(entry.group_name)}</span>`
            : '';
        const projects = entry.projects.map(p =>
            `<span class="fw-600">${_esc(p.name)}</span><span class="text-secondary small ms-1">(${_esc(p.programme_name)})</span>`
        ).join('<span class="text-secondary mx-1">·</span>');
        const statusBadge = _statusBadge(entry.email_status);
        const changedBadge = entry.has_changes
            ? `<span class="email-status-badge email-status-badge--changed"><i class="bi bi-arrow-repeat me-1"></i>Overridden</span>`
            : '';
        const fmtCost = v => `£${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

        const wasSent = entry.email_status === 'SENT';
        const sendBtnCls = (wasSent && entry.has_changes) ? 'btn-warning'
            : wasSent ? 'btn-outline-secondary'
            : 'btn-primary';
        const sendBtnIcon = wasSent ? 'bi-arrow-repeat' : 'bi-send';
        const sendBtnLabel = wasSent ? 'Resend' : 'Send';
        const sendBtnTitle = wasSent
            ? (entry.has_changes ? 'Resend with updated recharge data' : 'Resend this email')
            : 'Send this email';

        return `
        <div class="accordion-item rp-accordion-item mb-2" style="border-radius:8px;overflow:hidden">
            <div class="accordion-header">
                <button class="review-entry-header accordion-button collapsed"
                    type="button" data-bs-toggle="collapse"
                    data-bs-target="#entry-body-${idx}">
                    <div class="review-entry-projects d-flex flex-wrap align-items-center gap-2">
                        ${label}
                        <span>${projects}</span>
                    </div>
                    <div class="d-flex align-items-center gap-3 ms-auto">
                        <span class="text-secondary small font-mono">${parseFloat(entry.total_days).toFixed(2)} days</span>
                        <span class="text-secondary small font-mono">${fmtCost(entry.total_cost)}</span>
                        ${changedBadge}
                        ${statusBadge}
                    </div>
                </button>
            </div>
            <div id="entry-body-${idx}" class="accordion-collapse collapse">
                <div class="accordion-body pt-0">
                    ${entry.has_changes ? _buildChangesTable(entry) : ''}
                    ${_buildEmailPreview(entry, idx)}
                    <div class="d-flex align-items-center justify-content-between mt-3 flex-wrap gap-2">
                        ${entry.email_status
                            ? `<span class="text-secondary small">Last sent: ${_fmtDate(entry.last_sent_at)}</span>`
                            : '<span></span>'}
                        <button class="btn btn-sm ${sendBtnCls} send-entry-btn d-flex align-items-center gap-1"
                            data-entry-key="${_esc(entry.entry_key)}"
                            data-label="${sendBtnLabel}"
                            data-icon="${sendBtnIcon}"
                            title="${sendBtnTitle}">
                            <i class="bi ${sendBtnIcon} me-1"></i>${sendBtnLabel}
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');

    _injectEmailIframes(entries);

    acc.querySelectorAll('.send-entry-btn').forEach(btn =>
        btn.addEventListener('click', () => _sendEntry(btn))
    );
}

function _buildChangesTable(entry) {
    const fmtCost = v => `£${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
    const rows = entry.changes.map(c => `
        <tr>
            <td class="fw-600">${_esc(c.project_name)}</td>
            <td class="text-end font-mono text-secondary">${parseFloat(c.sent_days).toFixed(2)}</td>
            <td class="text-end font-mono text-secondary">${fmtCost(c.sent_cost)}</td>
            <td class="text-end font-mono fw-600">${parseFloat(c.current_days).toFixed(2)}</td>
            <td class="text-end font-mono fw-600">${fmtCost(c.current_cost)}</td>
        </tr>`).join('');
    return `
    <div class="changes-block mb-3">
        <div class="changes-block-title"><i class="bi bi-arrow-repeat me-1"></i>Changes since last send</div>
        <table class="table table-sm rp-table mb-0">
            <thead><tr>
                <th>Project</th>
                <th class="text-end text-secondary" style="font-weight:500">Sent Days</th>
                <th class="text-end text-secondary" style="font-weight:500">Sent Cost</th>
                <th class="text-end">Current Days</th>
                <th class="text-end">Current Cost</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>
    </div>`;
}

function _buildEmailPreview(entry, idx) {
    const toList = (entry.to_emails || []).join(', ') || '—';
    const ccList = (entry.cc_emails || []).join(', ') || '—';
    return `
    <div class="email-preview-block">
        <div class="email-client-header">
            <div class="email-field-row">
                <span class="email-field-label"><i class="bi bi-person-fill me-1"></i>To</span>
                <span>${_esc(toList)}</span>
            </div>
            <div class="email-field-row">
                <span class="email-field-label"><i class="bi bi-people me-1"></i>Cc</span>
                <span class="text-secondary">${_esc(ccList)}</span>
            </div>
            <div class="email-field-row" style="border-bottom:none;margin-bottom:0;padding-bottom:0">
                <span class="email-field-label"><i class="bi bi-tag me-1"></i>Subject</span>
                <span class="fw-600">${_esc(entry.subject)}</span>
            </div>
        </div>
        <div class="email-body-wrap" id="email-preview-${idx}">
            <div class="text-secondary small text-center py-3">
                <span class="spinner-border spinner-border-sm me-1"></span>Loading preview…
            </div>
        </div>
    </div>`;
}

function _injectEmailIframes(entries) {
    entries.forEach((entry, idx) => {
        const container = document.getElementById(`email-preview-${idx}`);
        if (!container) return;
        if (!entry.body_html) {
            container.innerHTML = '<p class="text-secondary small px-3 py-2 mb-0">No preview available.</p>';
            return;
        }
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'width:100%;min-height:420px;border:none;display:block';
        iframe.setAttribute('sandbox', 'allow-same-origin');
        iframe.title = 'Email Preview';
        container.innerHTML = '';
        container.appendChild(iframe);
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.open();
        doc.write(entry.body_html);
        doc.close();
        // Resize to content when the accordion panel is revealed
        const collapseEl = document.getElementById(`entry-body-${idx}`);
        const _resize = () => {
            try {
                const h = doc.documentElement.scrollHeight || doc.body?.scrollHeight || 420;
                if (h > 50) iframe.style.height = (h + 16) + 'px';
            } catch (_) {}
        };
        if (collapseEl) collapseEl.addEventListener('shown.bs.collapse', _resize);
        setTimeout(_resize, 250);
    });
}

async function _triggerAll() {
    const btn = document.getElementById('trigger-all-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner-border spinner-border-sm me-1"></div>Sending…';

    try {
        const result = await fetch(API_URLS.recharges.trigger_emails.href, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _getCsrf() },
            body: JSON.stringify({ sprint_id: SPRINT_ID, type: RECHARGE_TYPE }),
        }).then(r => r.json());

        const resultDiv = document.getElementById('trigger-result');
        resultDiv.classList.remove('d-none');

        if (result.error) {
            resultDiv.innerHTML = `<div class="alert alert-danger">${_esc(result.error)}</div>`;
        } else {
            const sent = (result.results || []).filter(r => r.status === 'SENT').length;
            const errors = (result.results || []).filter(r => r.status === 'ERROR').length;
            resultDiv.innerHTML = `
                <div class="alert alert-${errors ? 'warning' : 'success'}">
                    <strong>${result.count} email(s) processed:</strong>
                    ${sent} sent${errors ? `, ${errors} failed` : ''}.
                    ${errors ? (result.results || []).filter(r => r.status === 'ERROR').map(r =>
                        `<div class="small mt-1 text-danger">${_esc(r.entry_key)}: ${_esc(r.error_message)}</div>`
                    ).join('') : ''}
                </div>`;
            // Reload to show updated statuses
            await _loadReview();
        }
    } catch (e) {
        document.getElementById('trigger-result').classList.remove('d-none');
        document.getElementById('trigger-result').innerHTML = `<div class="alert alert-danger">Failed to trigger emails: ${_esc(String(e))}</div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-gear-fill"></i>Trigger All Emails';
    }
}

async function _sendEntry(btn) {
    const entryKey = btn.dataset.entryKey;
    const originalLabel = btn.dataset.label || 'Send';
    const originalIcon = btn.dataset.icon || 'bi-send';
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner-border spinner-border-sm me-1"></div>Sending…';

    try {
        const result = await fetch(API_URLS.recharges.resend.href, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _getCsrf() },
            body: JSON.stringify({ sprint_id: SPRINT_ID, type: RECHARGE_TYPE, entry_key: entryKey }),
        }).then(r => r.json());

        const resultDiv = document.getElementById('trigger-result');
        resultDiv.classList.remove('d-none');
        if (result.status === 'SENT') {
            resultDiv.innerHTML = `<div class="alert alert-success">Email sent successfully.</div>`;
            await _loadReview();
        } else {
            resultDiv.innerHTML = `<div class="alert alert-danger">Send failed: ${_esc(result.error_message || result.error || 'Unknown error')}</div>`;
            btn.disabled = false;
            btn.innerHTML = `<i class="bi ${originalIcon} me-1"></i>${originalLabel}`;
        }
    } catch (e) {
        document.getElementById('trigger-result').classList.remove('d-none');
        document.getElementById('trigger-result').innerHTML = `<div class="alert alert-danger">Send failed: ${_esc(String(e))}</div>`;
        btn.disabled = false;
        btn.innerHTML = `<i class="bi ${originalIcon} me-1"></i>${originalLabel}`;
    }
}

// ── Group management ──────────────────────────────────────────────────────────

async function _openManageGroups() {
    const modal = new bootstrap.Modal(document.getElementById('manageGroupsModal'));
    modal.show();
    await Promise.all([_loadGroupProjectOptions(), _loadGroups()]);
}

async function _loadGroupProjectOptions() {
    try {
        const projects = await apiFetch(API_URLS.recharge_project_groups.project_options.href);
        const sel = document.getElementById('new-group-projects');
        sel.innerHTML = (projects || []).map(p =>
            `<option value="${p.id}">${_esc(p.name)}</option>`
        ).join('');
    } catch (_) {}
}

async function _loadGroups() {
    const loading = document.getElementById('groups-loading');
    const list = document.getElementById('groups-list');
    const empty = document.getElementById('groups-empty');
    loading.classList.remove('d-none');
    list.classList.add('d-none');
    empty.classList.add('d-none');

    try {
        const groups = await apiFetch(API_URLS.recharge_project_groups.list.href);
        loading.classList.add('d-none');
        if (!groups || !groups.length) {
            empty.classList.remove('d-none');
            return;
        }
        list.innerHTML = groups.map(g => `
            <div class="group-row" data-group-id="${g.id}">
                <div class="flex-grow-1">
                    <div class="fw-600">${_esc(g.name)}</div>
                    <div class="text-secondary small">${(g.project_names || []).join(', ') || 'No projects'}</div>
                </div>
                <button class="btn btn-ghost-icon btn-sm delete-group-btn" data-group-id="${g.id}" title="Delete group">
                    <i class="bi bi-trash3 text-danger"></i>
                </button>
            </div>
        `).join('');
        list.classList.remove('d-none');
        list.querySelectorAll('.delete-group-btn').forEach(btn =>
            btn.addEventListener('click', () => _deleteGroup(btn.dataset.groupId))
        );
    } catch (_) {
        loading.classList.add('d-none');
        list.innerHTML = '<p class="text-danger small">Failed to load groups.</p>';
        list.classList.remove('d-none');
    }
}

async function _addGroup() {
    const name = document.getElementById('new-group-name').value.trim();
    const sel = document.getElementById('new-group-projects');
    const project_ids = Array.from(sel.selectedOptions).map(o => parseInt(o.value));
    const errEl = document.getElementById('add-group-error');
    errEl.classList.add('d-none');

    if (!name) { errEl.textContent = 'Group name is required.'; errEl.classList.remove('d-none'); return; }

    try {
        await fetch(API_URLS.recharge_project_groups.create.href, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _getCsrf() },
            body: JSON.stringify({ name, project_ids }),
        }).then(async r => {
            if (!r.ok) {
                const e = await r.json();
                throw new Error(e.error || 'Failed to create group.');
            }
        });
        document.getElementById('new-group-name').value = '';
        Array.from(sel.options).forEach(o => (o.selected = false));
        await _loadGroups();
    } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('d-none');
    }
}

async function _deleteGroup(groupId) {
    if (!confirm('Delete this group? Projects will no longer be grouped for emails.')) return;
    try {
        await fetch(API_URLS.recharge_project_groups.delete(groupId).href, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': _getCsrf() },
        });
        await _loadGroups();
    } catch (_) {}
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _statusBadge(status) {
    if (!status) return '';
    const cls = status === 'SENT' ? 'sent' : status === 'ERROR' ? 'error' : 'pending';
    const icon = status === 'SENT' ? 'bi-check-circle-fill' : status === 'ERROR' ? 'bi-exclamation-triangle-fill' : 'bi-hourglass-split';
    return `<span class="email-status-badge email-status-badge--${cls}"><i class="bi ${icon} me-1"></i>${status}</span>`;
}

function _fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
}

function _getCsrf() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
}

function _esc(str) {
    return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
