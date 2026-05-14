'use strict';

import {
    apiFetch, showFlash, formatDateTime, setPageTitle, escHtml
} from './../main.js';
import { initFetch } from './../list/fetch.js';
import { initRenderer } from './../list/render.js';

let fetcher = null;

document.addEventListener('DOMContentLoaded', () => {
    setPageTitle('Users');
    initListView();
});

function initListView() {
    loadStats();

    const renderer = initRenderer({
        tbodyId: 'users-tbody',
        colspan: 6,
        itemLabel: 'users',
        rowTemplate: renderUserRow,
        emptyState: { message: 'No users yet.' },
        filterEmptyState: { message: 'No users match your filters.' },
        paginationBarId: 'pagination-bar',
        paginationInfoId: 'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl: '/api/v1/users/',
        pageSize: 25,
        searchInputId: 'user-search',
        filters: [{ inputId: 'status-filter', paramName: 'is_active' }],
        onLoadStart: () => renderer.renderLoading('Loading users…'),
        onSuccess: ({ results, pagination }) => {
            renderer.renderRows(results, false);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load users. Please refresh.'),
    });

    fetcher.refresh();
    wireModals();
}

async function loadStats() {
    try {
        const s = await apiFetch('/api/v1/users/stats/');
        document.getElementById('stat-total').textContent  = s.total  ?? '—';
        document.getElementById('stat-active').textContent = s.active ?? '—';
        document.getElementById('stat-staff').textContent  = s.staff  ?? '—';
        document.getElementById('stat-sso').textContent    = s.sso    ?? '—';
    } catch (_) {}
}

function renderUserRow(user) {
    const fullName = user.full_name || user.email;
    const avatar = user.avatar_display
        ? `<img src="${escHtml(user.avatar_display)}" class="rp-avatar-sm me-2" alt="">`
        : `<span class="rp-avatar-sm-initials me-2">${escHtml((user.first_name || user.email || '?')[0].toUpperCase())}</span>`;

    const roleBadge = user.is_staff
        ? `<span class="rp-badge rp-badge--warning">Admin</span>`
        : `<span class="rp-badge rp-badge--muted">Member</span>`;

    const ssoTag = user.profile?.sso_provider
        ? `<span class="rp-badge rp-badge--info ms-1">${escHtml(user.profile.sso_provider)}</span>`
        : '';

    const statusBadge = user.is_active
        ? `<span class="rp-badge rp-badge--success">Active</span>`
        : `<span class="rp-badge rp-badge--danger">Inactive</span>`;

    const activateBtn = user.is_active
        ? `<button class="btn btn-ghost-icon text-warning" title="Deactivate"
               onclick="showStatusModal(${user.id}, '${escHtml(user.email)}', false)">
               <i class="bi bi-slash-circle"></i></button>`
        : `<button class="btn btn-ghost-icon text-success" title="Activate"
               onclick="showStatusModal(${user.id}, '${escHtml(user.email)}', true)">
               <i class="bi bi-check-circle"></i></button>`;

    return `
        <tr data-user-id="${user.id}">
            <td>
                <div class="d-flex align-items-center">
                    ${avatar}
                    <div>
                        <div class="fw-500">${escHtml(fullName)}</div>
                        <div class="text-secondary small">${escHtml(user.email)}</div>
                    </div>
                </div>
            </td>
            <td>${roleBadge}${ssoTag}</td>
            <td>
                ${user.profile?.sso_provider
                    ? `<span class="text-secondary small"><i class="bi bi-shield-check me-1"></i>SSO</span>`
                    : `<span class="text-secondary small"><i class="bi bi-key me-1"></i>Classic</span>`}
            </td>
            <td>${statusBadge}</td>
            <td class="text-secondary small">${formatDateTime(user.date_joined)}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    ${activateBtn}
                    <button class="btn btn-ghost-icon" title="Reset password"
                            onclick="showResetPwdModal(${user.id}, '${escHtml(user.email)}')">
                        <i class="bi bi-key"></i>
                    </button>
                    <button class="btn btn-ghost-icon text-danger" title="Delete"
                            onclick="showDeleteModal(${user.id}, '${escHtml(user.email)}')">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </td>
        </tr>`;
}

function wireModals() {
    // Status modal
    const statusModal = new bootstrap.Modal(document.getElementById('statusModal'));
    window.showStatusModal = (userId, email, activate) => {
        const title = document.getElementById('status-modal-title');
        const body  = document.getElementById('status-modal-body');
        const btn   = document.getElementById('status-confirm-btn');
        title.textContent = activate ? 'Activate user?' : 'Deactivate user?';
        body.innerHTML = activate
            ? `<strong>${escHtml(email)}</strong> will be able to sign in again.`
            : `<strong>${escHtml(email)}</strong> will no longer be able to sign in.`;
        btn.className = activate ? 'btn btn-sm btn-success' : 'btn btn-sm btn-warning';
        btn.textContent = activate ? 'Activate' : 'Deactivate';
        btn.onclick = async () => {
            statusModal.hide();
            try {
                const endpoint = activate ? 'activate' : 'deactivate';
                await apiFetch(`/api/v1/users/${userId}/${endpoint}/`, { method: 'POST' });
                showFlash(`User ${activate ? 'activated' : 'deactivated'}.`, 'success');
                fetcher.refresh();
                loadStats();
            } catch (err) {
                showFlash(err?.data?.error || 'Action failed.', 'error');
            }
        };
        statusModal.show();
    };

    // Delete modal
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    window.showDeleteModal = (userId, email) => {
        document.getElementById('delete-user-email').textContent = email;
        document.getElementById('confirm-delete-btn').onclick = async () => {
            deleteModal.hide();
            try {
                await apiFetch(`/api/v1/users/${userId}/`, { method: 'DELETE' });
                showFlash('User deleted.', 'success');
                fetcher.refresh();
                loadStats();
            } catch (err) {
                showFlash(err?.data?.error || 'Could not delete user.', 'error');
            }
        };
        deleteModal.show();
    };

    // Reset password modal
    const resetPwdModal = new bootstrap.Modal(document.getElementById('resetPwdModal'));
    window.showResetPwdModal = (userId, email) => {
        document.getElementById('reset-user-email').textContent = email;
        document.getElementById('reset-pwd-input').value = '';
        const errEl = document.getElementById('reset-pwd-error');
        errEl.textContent = '';
        document.getElementById('reset-pwd-input').classList.remove('is-invalid');
        document.getElementById('reset-pwd-confirm-btn').onclick = async () => {
            const pwd = document.getElementById('reset-pwd-input').value;
            if (!pwd) {
                document.getElementById('reset-pwd-input').classList.add('is-invalid');
                errEl.textContent = 'Password is required.';
                return;
            }
            try {
                await apiFetch(`/api/v1/users/${userId}/reset_password/`, {
                    method: 'POST',
                    body: JSON.stringify({ new_password: pwd }),
                });
                resetPwdModal.hide();
                showFlash('Password reset successfully.', 'success');
            } catch (err) {
                const detail = err?.data?.details?.new_password;
                errEl.textContent = detail ? detail[0] : (err?.data?.error || 'Reset failed.');
                document.getElementById('reset-pwd-input').classList.add('is-invalid');
            }
        };
        resetPwdModal.show();
    };
}
