'use strict';

import { apiFetch, showFlash, formatDateTime, setPageTitle, escHtml } from './../main.js';

let _user = null;
let _allGroups = [];
let _allCategories = [];      // all PermissionCategories (with module_label)
let _allPermissions = [];     // grouped by module [{app_label, label, permissions:[...]}]
let _groupsModal   = null;
let _permsModal    = null;
let _statusModal   = null;
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
    loadAllCategories();
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

    // Explicit permission categories
    renderExplicitCategoryBadges(u.explicit_category_ids || []);

    // Effective permissions (aggregated)
    renderEffectivePerms(u.effective_permission_ids || []);

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

function renderExplicitCategoryBadges(catIds) {
    const listEl  = document.getElementById('perms-list');
    const emptyEl = document.getElementById('perms-empty');

    if (!catIds.length) {
        emptyEl.classList.remove('d-none');
        listEl.innerHTML = '';
        return;
    }
    emptyEl.classList.add('d-none');

    const catMap = {};
    _allCategories.forEach(c => { catMap[c.id] = c; });

    listEl.innerHTML = catIds.map(id => {
        const c = catMap[id];
        return c
            ? `<span class="rp-badge rp-badge--muted" title="${escHtml(c.description || '')}">
                   <i class="bi bi-collection me-1"></i>${escHtml(c.name)}
               </span>`
            : `<span class="rp-badge rp-badge--muted">Category #${id}</span>`;
    }).join('');
}

function renderEffectivePerms(permIds) {
    const accordionEl = document.getElementById('effective-perms-accordion');
    const emptyEl     = document.getElementById('effective-perms-empty');

    if (!permIds.length) {
        emptyEl.classList.remove('d-none');
        accordionEl.innerHTML = '';
        return;
    }
    emptyEl.classList.add('d-none');

    if (!_allPermissions.length) {
        accordionEl.innerHTML = '<p class="text-secondary small">Loading permissions…</p>';
        return;
    }

    const idSet = new Set(permIds);
    const modulesWithPerms = _allPermissions.filter(mod =>
        mod.permissions.some(p => idSet.has(p.id))
    );

    if (!modulesWithPerms.length) {
        emptyEl.classList.remove('d-none');
        return;
    }

    accordionEl.innerHTML = modulesWithPerms.map((mod, i) => {
        const myPerms = mod.permissions.filter(p => idSet.has(p.id));
        return `
        <div class="accordion-item border-0 border-bottom">
            <h2 class="accordion-header">
                <button class="accordion-button collapsed py-2 px-0 bg-transparent shadow-none fw-500"
                        type="button" data-bs-toggle="collapse"
                        data-bs-target="#ep-body-${i}">
                    ${escHtml(mod.label)}
                    <span class="ms-2 text-secondary small">(${myPerms.length})</span>
                </button>
            </h2>
            <div id="ep-body-${i}" class="accordion-collapse collapse">
                <div class="accordion-body px-0 pb-2 pt-1">
                    ${myPerms.map(p => `
                        <div class="small text-secondary py-1">
                            <i class="bi bi-check-circle-fill text-success me-1"></i>${escHtml(p.name)}
                        </div>`).join('')}
                </div>
            </div>
        </div>`;
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

async function loadAllCategories() {
    try {
        _allCategories = await apiFetch('/api/v1/permission-categories/');
        if (_user) renderExplicitCategoryBadges(_user.explicit_category_ids || []);
    } catch (_) {}
}

async function loadAllPermissions() {
    try {
        _allPermissions = await apiFetch('/api/v1/permissions/');
        if (_user) renderEffectivePerms(_user.effective_permission_ids || []);
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
            renderEffectivePerms(_user.effective_permission_ids || []);
            showFlash('Group membership updated.', 'success');
        } catch (err) {
            showFlash(err?.data?.error || 'Could not update groups.', 'error');
        }
    });

    // Manage permission categories
    document.getElementById('manage-perms-btn').addEventListener('click', () => {
        openCategoriesModal();
    });

    document.getElementById('save-perms-btn').addEventListener('click', async () => {
        const selected = [...document.querySelectorAll('.cat-pick-check:checked')]
            .map(cb => Number(cb.value));
        try {
            _user = await apiFetch(`/api/v1/users/${pk}/set_permission_categories/`, {
                method: 'POST',
                body: JSON.stringify({ category_ids: selected }),
            });
            _permsModal.hide();
            renderExplicitCategoryBadges(_user.explicit_category_ids || []);
            renderEffectivePerms(_user.effective_permission_ids || []);
            showFlash('Permission categories updated.', 'success');
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

function openCategoriesModal() {
    const loadingEl   = document.getElementById('perm-pick-loading');
    const accordionEl = document.getElementById('perm-pick-accordion');

    loadingEl.classList.remove('d-none');
    accordionEl.innerHTML = '';

    const currentCatIds = new Set(_user?.explicit_category_ids || []);

    if (_allCategories.length) {
        loadingEl.classList.add('d-none');

        // Group by module
        const byModule = {};
        const noModule = [];
        _allCategories.forEach(cat => {
            if (cat.module) {
                if (!byModule[cat.module]) byModule[cat.module] = { label: cat.module_label || cat.module, cats: [] };
                byModule[cat.module].cats.push(cat);
            } else {
                noModule.push(cat);
            }
        });

        const moduleOrder = [
            'delivery_teams','team_members','member_leaves','financial_years',
            'sprints','sprint_capacity','resource_plans','projects','programmes',
            'contacts','skills','team_roles','office_locations','employment_types',
            'project_types','project_sub_statuses','public_holidays',
        ];

        const sections = [];
        moduleOrder.forEach(m => {
            if (byModule[m]) sections.push({ key: m, label: byModule[m].label, cats: byModule[m].cats });
        });
        if (noModule.length) sections.push({ key: '__other__', label: 'Other', cats: noModule });

        accordionEl.innerHTML = sections.map((sec, i) => {
            const checked = sec.cats.filter(c => currentCatIds.has(c.id)).length;
            return `
            <div class="accordion-item border-0 border-bottom">
                <h2 class="accordion-header">
                    <button class="accordion-button collapsed py-2 px-0 bg-transparent shadow-none fw-500"
                            type="button" data-bs-toggle="collapse"
                            data-bs-target="#cp-ud-${i}">
                        ${escHtml(sec.label)}
                        <span class="ms-2 text-secondary small" id="cp-ud-count-${i}">
                            (${checked} / ${sec.cats.length})
                        </span>
                    </button>
                </h2>
                <div id="cp-ud-${i}" class="accordion-collapse collapse">
                    <div class="accordion-body px-0 pb-2 pt-1">
                        ${sec.cats.map(cat => `
                            <div class="form-check mb-1">
                                <input class="form-check-input cat-pick-check"
                                       type="checkbox" value="${cat.id}"
                                       id="cp-ud-cat-${cat.id}" data-sec-idx="${i}"
                                       ${currentCatIds.has(cat.id) ? 'checked' : ''}
                                       onchange="updateCpUdCount(${i}, ${sec.cats.length})">
                                <label class="form-check-label small" for="cp-ud-cat-${cat.id}">
                                    <span class="fw-500">${escHtml(cat.name)}</span>
                                    ${cat.description ? `<span class="text-secondary ms-1">— ${escHtml(cat.description)}</span>` : ''}
                                    <span class="rp-badge rp-badge--muted ms-1">${cat.permission_count} perms</span>
                                </label>
                            </div>`).join('')}
                    </div>
                </div>
            </div>`;
        }).join('');
    } else {
        accordionEl.innerHTML = '<p class="text-secondary small">No permission categories available.</p>';
        loadingEl.classList.add('d-none');
    }

    _permsModal.show();
}

window.updateCpUdCount = (secIdx, total) => {
    const checked = document.querySelectorAll(`.cat-pick-check[data-sec-idx="${secIdx}"]:checked`).length;
    const el = document.getElementById(`cp-ud-count-${secIdx}`);
    if (el) el.textContent = `(${checked} / ${total})`;
};
