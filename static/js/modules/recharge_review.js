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
        const fmtCost = v => `£${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

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
                        ${statusBadge}
                    </div>
                </button>
            </div>
            <div id="entry-body-${idx}" class="accordion-collapse collapse">
                <div class="accordion-body pt-0">
                    ${_buildEmailPreview(entry)}
                    ${entry.email_status ? `<div class="mt-2 text-secondary small">Last triggered: ${_fmtDate(entry.last_sent_at)}</div>` : ''}
                </div>
            </div>
        </div>`;
    }).join('');
}

function _buildEmailPreview(entry) {
    const toList = (entry.to_emails || []).join(', ') || '—';
    const ccList = (entry.cc_emails || []).join(', ') || '—';

    // Build HTML body preview (text snippet from first project's stories)
    let bodyPreview = `<p>Dear Team,</p>`;
    const verb = RECHARGE_TYPE === 'FORECAST' ? 'planned' : 'completed';
    bodyPreview += `<p>We are writing to request your approval for the ${verb} Jira stories for this sprint.</p>`;

    entry.projects.forEach(p => {
        bodyPreview += `<h4 style="font-size:14px;margin-top:16px;margin-bottom:6px">${_esc(p.name)} (${_esc(p.programme_name)})</h4>`;
        bodyPreview += `<p style="margin:0 0 8px"><strong>Project Code:</strong> ${_esc(p.project_code || '—')}</p>`;
        if (p.stories && p.stories.length) {
            bodyPreview += `<table style="width:100%;border-collapse:collapse;font-size:13px">
                <thead><tr style="background:#f0f0f0">
                    <th style="padding:4px 8px;border:1px solid #ddd;text-align:left">Jira ID</th>
                    <th style="padding:4px 8px;border:1px solid #ddd;text-align:left">Title</th>
                    <th style="padding:4px 8px;border:1px solid #ddd;text-align:right">Days</th>
                    <th style="padding:4px 8px;border:1px solid #ddd;text-align:right">Cost (£)</th>
                </tr></thead><tbody>`;
            p.stories.forEach(s => {
                bodyPreview += `<tr>
                    <td style="padding:4px 8px;border:1px solid #ddd">${_esc(s.jira_id)}</td>
                    <td style="padding:4px 8px;border:1px solid #ddd">${_esc(s.title)}</td>
                    <td style="padding:4px 8px;border:1px solid #ddd;text-align:right">${s.total_days}</td>
                    <td style="padding:4px 8px;border:1px solid #ddd;text-align:right">£${parseFloat(s.cost).toLocaleString(undefined,{minimumFractionDigits:2})}</td>
                </tr>`;
            });
            bodyPreview += `<tr style="font-weight:bold;background:#f9f9f9">
                <td colspan="2" style="padding:4px 8px;border:1px solid #ddd">Total</td>
                <td style="padding:4px 8px;border:1px solid #ddd;text-align:right">${p.total_days}</td>
                <td style="padding:4px 8px;border:1px solid #ddd;text-align:right">£${parseFloat(p.total_cost).toLocaleString(undefined,{minimumFractionDigits:2})}</td>
            </tr>`;
            bodyPreview += `</tbody></table>`;
        } else {
            bodyPreview += `<p class="text-secondary small">No stories linked.</p>`;
        }
    });
    bodyPreview += `<p style="margin-top:16px">Please review and respond within <strong>48 hours</strong> to confirm your approval.</p>`;

    return `
    <div class="email-preview-block">
        <div class="email-field-row">
            <span class="email-field-label">To:</span>
            <span>${_esc(toList)}</span>
        </div>
        <div class="email-field-row">
            <span class="email-field-label">Cc:</span>
            <span class="text-secondary">${_esc(ccList)}</span>
        </div>
        <div class="email-field-row">
            <span class="email-field-label">Subject:</span>
            <span>${_esc(entry.subject)}</span>
        </div>
        <div class="email-body-wrap">
            <div style="font-size:13px">${bodyPreview}</div>
        </div>
    </div>`;
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
