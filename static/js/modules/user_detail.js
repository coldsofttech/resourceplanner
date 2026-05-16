'use strict';

import { apiFetch, showFlash, formatDateTime, setPageTitle, escHtml } from './../main.js';

let _user = null;
let _allGroups = [];
let _allPermissions = [];
let _groupsModal = null;
let _permsModal = null;
let _statusModal = null;
let _resetPwdModal = null;

document.addEventListener('DOMContentLoaded', async () => {
    const pk = window.USER_PK;
    if (!pk) return;

    _groupsModal   = new bootstrap.Modal(document.getElementById('manageGroupsModal'));
    _permsModal    = new bootstrap.Modal(document.getElementById('managePermsModal'));
    _statusModal   = new bootstrap.Modal(document.getElementById('statusModal'));
    _resetPwdModal = new bootstrap.Modal(document.getElementById('resetPwdModal'));

    await loadUser(pk);
    loadAllGroups();
    loadAllPermissions();
    wireButtons(pk);
});

async function loadUser(pk) {
    try {
        _user = await apiFetch(`/api/v1/users/${pk}/`);
        renderUser(_user);
    } catch (_) {
        showFlash('Failed to load user.', 'error');
    }
}

function renderUser(u) {
    const fullName = u.full_name || u.email;
    setPageTitle(fullName);
    document.title = `${fullName} — Users — Resource Planner`;

    document.getElementById('page-user-name').textContent = fullName;
    document.getElementById('page-user-email').textContent = u.email;
    document.getElementById('info-email').textContent = u.email;

    // Avatar / initials
    const wrap = document.getElementById('user-avatar-wrap');
    if (u.avatar_display) {
        wrap.innerHTML = `<div class="rp-avatar-lg mx-auto">
            <img src="${escHtml(u.avatar_display)}" class="rp-avatar-img" alt="">
        </div>`;
    } else {
        document.getElementById('user-initials').textContent =
            ((u.first_name || u.email || '?')[0]).toUpperCase();
    }

    // Role
    document.getElementById('info-role').innerHTML = u.is_superuser
        ? '<span class="rp-badge rp-badge--danger">Superuser</span>'
        : u.is_staff
            ? '<span class="rp-badge rp-badge--warning">Admin</span>'
            : '<span class="rp-badge rp-badge--muted">Member</span>';

    // Status
    document.getElementById('info-status').innerHTML = u.is_active
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--danger">Inactive</span>';

    document.getElementById('info-joined').textContent    = formatDateTime(u.date_joined);
    document.getElementById('info-last-login').textContent = formatDateTime(u.last_login);

    // Groups
    renderGroupBadges(u.group_ids || []);

    // Permissions
    renderPermBadges(u.explicit_permission_ids || []);

    // Action buttons
    renderActions(u);
}

function renderGroupBadges(groupIds) {
    const listEl  = document.getElementById('groups-list');
    const emptyEl = document.getElementById('groups-empty');

    if (!groupIds.length) {
        emptyEl.classList.remove('d-none');
        listEl.innerHTML = '';
        return;
    }
    emptyEl.classList.add('d-none');

    // Use the already-loaded groups if available, else just show IDs
    if (_allGroups.length) {
        const myGroups = _allGroups.filter(g => groupIds.includes(g.id));
        listEl.innerHTML = myGroups.map(g => `
            <span class="rp-badge rp-badge--info">
                <i class="bi bi-people me-1"></i>${escHtml(g.name)}
            </span>`).join('');
    } else {
        listEl.innerHTML = groupIds.map(id =>
            `<span class="rp-badge rp-badge--muted">Group #${id}</span>`
        ).join('');
    }
}

function renderPermBadges(permIds) {
    const listEl  = document.getElementById('perms-list');
    const emptyEl = document.getElementById('perms-empty');

    if (!permIds.length) {
        emptyEl.classList.remove('d-none');
        listEl.innerHTML = '';
        return;
    }
    emptyEl.classList.add('d-none');

    // Flatten permissions from all modules
    const permMap = {};
    _allPermissions.forEach(mod => {
        mod.permissions.forEach(p => { permMap[p.id] = p; });
    });

    listEl.innerHTML = permIds.map(id => {
        const p = permMap[id];
        return p
            ? `<span class="rp-badge rp-badge--muted" title="${escHtml(p.codename)}">${escHtml(p.name)}</span>`
            : `<span class="rp-badge rp-badge--muted">Perm #${id}</span>`;
    }).join('');
}

function renderActions(u) {
    const el = document.getElementById('action-buttons');
    const activateBtn = u.is_active
        ? `<button class="btn btn-sm btn-outline-warning w-100" id="toggle-status-btn">
               <i class="bi bi-slash-circle me-1"></i>Deactivate user
           </button>`
        : `<button class="btn btn-sm btn-outline-success w-100" id="toggle-status-btn">
               <i class="bi bi-check-circle me-1"></i>Activate user
           </button>`;

    el.innerHTML = `
        ${activateBtn}
        <button class="btn btn-sm btn-outline-secondary w-100" id="reset-pwd-btn">
            <i class="bi bi-key me-1"></i>Reset password
        </button>`;

    document.getElementById('toggle-status-btn').addEventListener('click', () => {
        const activate = !u.is_active;
        const title = document.getElementById('status-modal-title');
        const body  = document.getElementById('status-modal-body');
        const btn   = document.getElementById('status-confirm-btn');
        title.textContent = activate ? 'Activate user?' : 'Deactivate user?';
        body.innerHTML = activate
            ? `<strong>${escHtml(u.email)}</strong> will be able to sign in again.`
            : `<strong>${escHtml(u.email)}</strong> will no longer be able to sign in.`;
        btn.className = activate ? 'btn btn-sm btn-success' : 'btn btn-sm btn-warning';
        btn.textContent = activate ? 'Activate' : 'Deactivate';
        btn.onclick = async () => {
            _statusModal.hide();
            try {
                const endpoint = activate ? 'activate' : 'deactivate';
                _user = await apiFetch(`/api/v1/users/${u.id}/${endpoint}/`, { method: 'POST' });
                renderUser(_user);
                showFlash(`User ${activate ? 'activated' : 'deactivated'}.`, 'success');
            } catch (err) {
                showFlash(err?.data?.error || 'Action failed.', 'error');
            }
        };
        _statusModal.show();
    });

    document.getElementById('reset-pwd-btn').addEventListener('click', () => {
        document.getElementById('reset-pwd-input').value = '';
        document.getElementById('reset-pwd-error').textContent = '';
        document.getElementById('reset-pwd-input').classList.remove('is-invalid');
        document.getElementById('reset-pwd-confirm-btn').onclick = async () => {
            const pwd = document.getElementById('reset-pwd-input').value;
            if (!pwd) {
                document.getElementById('reset-pwd-input').classList.add('is-invalid');
                document.getElementById('reset-pwd-error').textContent = 'Password is required.';
                return;
            }
            try {
                await apiFetch(`/api/v1/users/${u.id}/reset_password/`, {
                    method: 'POST',
                    body: JSON.stringify({ new_password: pwd }),
                });
                _resetPwdModal.hide();
                showFlash('Password reset successfully.', 'success');
            } catch (err) {
                const detail = err?.data?.details?.new_password;
                document.getElementById('reset-pwd-error').textContent =
                    detail ? detail[0] : (err?.data?.error || 'Reset failed.');
                document.getElementById('reset-pwd-input').classList.add('is-invalid');
            }
        };
        _resetPwdModal.show();
    });
}

async function loadAllGroups() {
    try {
        const data = await apiFetch('/api/v1/user-groups/');
        _allGroups = Array.isArray(data) ? data : (data.results || []);
        if (_user) renderGroupBadges(_user.group_ids || []);
    } catch (_) {}
}

async function loadAllPermissions() {
    try {
        _allPermissions = await apiFetch('/api/v1/permissions/');
        if (_user) renderPermBadges(_user.explicit_permission_ids || []);
    } catch (_) {}
}

function wireButtons(pk) {
    // Manage groups
    document.getElementById('manage-groups-btn').addEventListener('click', () => {
        openGroupsModal();
    });

    document.getElementById('save-groups-btn').addEventListener('click', async () => {
        const selected = [...document.querySelectorAll('.group-pick-check:checked')]
            .map(cb => Number(cb.value));
        try {
            _user = await apiFetch(`/api/v1/users/${pk}/set_groups/`, {
                method: 'POST',
                body: JSON.stringify({ group_ids: selected }),
            });
            _groupsModal.hide();
            renderGroupBadges(_user.group_ids || []);
            showFlash('Group membership updated.', 'success');
        } catch (err) {
            showFlash(err?.data?.error || 'Could not update groups.', 'error');
        }
    });

    // Manage permissions
    document.getElementById('manage-perms-btn').addEventListener('click', () => {
        openPermsModal();
    });

    document.getElementById('save-perms-btn').addEventListener('click', async () => {
        const selected = [...document.querySelectorAll('.perm-pick-check:checked')]
            .map(cb => Number(cb.value));
        try {
            _user = await apiFetch(`/api/v1/users/${pk}/set_permissions/`, {
                method: 'POST',
                body: JSON.stringify({ permission_ids: selected }),
            });
            _permsModal.hide();
            renderPermBadges(_user.explicit_permission_ids || []);
            showFlash('Permissions updated.', 'success');
        } catch (err) {
            showFlash(err?.data?.error || 'Could not update permissions.', 'error');
        }
    });
}

function openGroupsModal() {
    const loadingEl = document.getElementById('group-pick-loading');
    const listEl    = document.getElementById('group-pick-list');

    loadingEl.classList.remove('d-none');
    listEl.innerHTML = '';

    const currentGroupIds = new Set(_user?.group_ids || []);

    if (_allGroups.length) {
        loadingEl.classList.add('d-none');
        listEl.innerHTML = _allGroups.map(g => `
            <div class="form-check">
                <input class="form-check-input group-pick-check" type="checkbox"
                       value="${g.id}" id="gp-${g.id}"
                       ${currentGroupIds.has(g.id) ? 'checked' : ''}>
                <label class="form-check-label" for="gp-${g.id}">
                    <span class="fw-500">${escHtml(g.name)}</span>
                    ${g.is_admin_group ? '<span class="rp-badge rp-badge--warning ms-1">Admin</span>' : ''}
                    ${g.description ? `<span class="text-secondary small ms-1">— ${escHtml(g.description)}</span>` : ''}
                </label>
            </div>`).join('');
    } else {
        listEl.innerHTML = '<p class="text-secondary small">No groups available.</p>';
        loadingEl.classList.add('d-none');
    }

    _groupsModal.show();
}

function openPermsModal() {
    const loadingEl   = document.getElementById('perm-pick-loading');
    const accordionEl = document.getElementById('perm-pick-accordion');

    loadingEl.classList.remove('d-none');
    accordionEl.innerHTML = '';

    const currentPermIds = new Set(_user?.explicit_permission_ids || []);

    if (_allPermissions.length) {
        loadingEl.classList.add('d-none');
        accordionEl.innerHTML = _allPermissions.map((mod, i) => {
            const checked = mod.permissions.filter(p => currentPermIds.has(p.id)).length;
            return `
            <div class="accordion-item border-0 border-bottom">
                <h2 class="accordion-header">
                    <button class="accordion-button collapsed py-2 px-0 bg-transparent shadow-none fw-500"
                            type="button" data-bs-toggle="collapse"
                            data-bs-target="#pp-body-${i}">
                        ${escHtml(mod.label)}
                        <span class="ms-2 text-secondary small" id="pp-count-${i}">
                            (${checked} / ${mod.permissions.length})
                        </span>
                    </button>
                </h2>
                <div id="pp-body-${i}" class="accordion-collapse collapse">
                    <div class="accordion-body px-0 pb-2 pt-1">
                        ${mod.permissions.map(p => `
                            <div class="form-check mb-1">
                                <input class="form-check-input perm-pick-check"
                                       type="checkbox" value="${p.id}"
                                       id="pp-${p.id}" data-mod-idx="${i}"
                                       ${currentPermIds.has(p.id) ? 'checked' : ''}
                                       onchange="updatePpCount(${i})">
                                <label class="form-check-label small" for="pp-${p.id}">
                                    ${escHtml(p.name)}
                                </label>
                            </div>`).join('')}
                    </div>
                </div>
            </div>`;
        }).join('');
    } else {
        accordionEl.innerHTML = '<p class="text-secondary small">No permissions available.</p>';
        loadingEl.classList.add('d-none');
    }

    _permsModal.show();
}

window.updatePpCount = (idx) => {
    const mod = _allPermissions[idx];
    if (!mod) return;
    const n = document.querySelectorAll(`.perm-pick-check[data-mod-idx="${idx}"]:checked`).length;
    const el = document.getElementById(`pp-count-${idx}`);
    if (el) el.textContent = `(${n} / ${mod.permissions.length})`;
};
