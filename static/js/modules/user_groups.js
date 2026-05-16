'use strict';

import { apiFetch, showFlash, formatDateTime, escHtml } from './../main.js';

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('groups-tbody')) {
        initListView();
    } else if (document.getElementById('group-form')) {
        initFormView();
    } else if (document.getElementById('members-tbody')) {
        initDetailView();
    }
});

// ── List view ─────────────────────────────────────────────────────────────────

function initListView() {
    loadListStats();
    loadGroups();

    document.getElementById('group-search').addEventListener('input', () => {
        const q = document.getElementById('group-search').value.trim().toLowerCase();
        filterGroupRows(q);
    });

    wireDeleteModal();
}

async function loadListStats() {
    try {
        const s = await apiFetch('/api/v1/user-groups/stats/');
        document.getElementById('stat-total').textContent = s.total ?? '—';
        document.getElementById('stat-admin').textContent = s.admin ?? '—';
    } catch (_) {}
}

let _allGroups = [];

async function loadGroups() {
    const tbody = document.getElementById('groups-tbody');
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary py-4">Loading…</td></tr>';
    try {
        const data = await apiFetch('/api/v1/user-groups/');
        _allGroups = Array.isArray(data) ? data : (data.results || []);
        renderGroupRows(_allGroups, tbody);
    } catch (_) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-4">Failed to load groups. Please refresh.</td></tr>';
    }
}

function renderGroupRows(groups, tbody) {
    if (!groups.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary py-4">No groups found.</td></tr>';
        return;
    }
    tbody.innerHTML = groups.map(renderGroupRow).join('');
}

function renderGroupRow(g) {
    const typeBadge = g.is_admin_group
        ? `<span class="rp-badge rp-badge--warning">Admin</span>`
        : `<span class="rp-badge rp-badge--muted">Standard</span>`;
    const sysBadge = g.is_system
        ? `<span class="rp-badge rp-badge--info ms-1">System</span>`
        : '';
    const deleteBtn = g.is_system
        ? `<button class="btn btn-ghost-icon text-danger" title="Delete" disabled>
               <i class="bi bi-trash3"></i></button>`
        : `<button class="btn btn-ghost-icon text-danger" title="Delete"
               onclick="showDeleteGroupModal(${g.id}, '${escHtml(g.name)}')">
               <i class="bi bi-trash3"></i></button>`;

    return `
        <tr>
            <td>
                <a href="/user-groups/${g.id}/" class="fw-500 rp-link">${escHtml(g.name)}</a>
            </td>
            <td>${typeBadge}${sysBadge}</td>
            <td>${g.member_count ?? '—'}</td>
            <td class="text-secondary small">${escHtml(g.description || '—')}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="/user-groups/${g.id}/" class="btn btn-ghost-icon" title="View">
                        <i class="bi bi-eye"></i>
                    </a>
                    ${g.is_system
                        ? `<button class="btn btn-ghost-icon" title="Edit" disabled><i class="bi bi-pencil"></i></button>`
                        : `<a href="/user-groups/${g.id}/edit/" class="btn btn-ghost-icon" title="Edit"><i class="bi bi-pencil"></i></a>`}
                    ${deleteBtn}
                </div>
            </td>
        </tr>`;
}

function filterGroupRows(q) {
    if (!q) {
        renderGroupRows(_allGroups, document.getElementById('groups-tbody'));
        return;
    }
    const filtered = _allGroups.filter(g =>
        g.name.toLowerCase().includes(q) ||
        (g.description || '').toLowerCase().includes(q)
    );
    renderGroupRows(filtered, document.getElementById('groups-tbody'));
}

function wireDeleteModal() {
    const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
    window.showDeleteGroupModal = (groupId, name) => {
        document.getElementById('delete-group-name').textContent = name;
        document.getElementById('confirm-delete-btn').onclick = async () => {
            modal.hide();
            try {
                await apiFetch(`/api/v1/user-groups/${groupId}/`, { method: 'DELETE' });
                showFlash('Group deleted.', 'success');
                _allGroups = _allGroups.filter(g => g.id !== groupId);
                renderGroupRows(_allGroups, document.getElementById('groups-tbody'));
                loadListStats();
            } catch (err) {
                showFlash(err?.data?.error || 'Could not delete group.', 'error');
            }
        };
        modal.show();
    };
}

// ── Form view (create / edit) ─────────────────────────────────────────────────

let _allPermissions = [];     // [{app_label, label, permissions:[{id,codename,name}]}]
let _allCategories  = [];     // [{id, name, permission_ids:[...]}]
let _groupIsSystem  = false;

function initFormView() {
    const form = document.getElementById('group-form');
    const groupPk = form.dataset.groupPk ? Number(form.dataset.groupPk) : null;

    loadCategoriesSection();
    loadPermissionsAccordion(groupPk);

    if (groupPk) {
        loadGroupForEdit(groupPk);
    }

    form.addEventListener('submit', async e => {
        e.preventDefault();
        await submitGroupForm(groupPk);
    });
}

async function loadCategoriesSection() {
    const loadingEl = document.getElementById('categories-loading');
    const listEl    = document.getElementById('categories-list');
    if (!listEl) return;

    try {
        _allCategories = await apiFetch('/api/v1/permission-categories/');
    } catch (_) {
        if (loadingEl) loadingEl.textContent = 'Could not load categories.';
        return;
    }

    if (loadingEl) loadingEl.classList.add('d-none');

    if (!_allCategories.length) {
        listEl.innerHTML = '<p class="text-secondary small mb-0">No categories configured yet. <a href="/permission-categories/" class="rp-link">Create one</a>.</p>';
        return;
    }

    listEl.innerHTML = _allCategories.map(cat => `
        <div class="form-check">
            <input class="form-check-input cat-check" type="checkbox"
                   value="${cat.id}" id="cat-${cat.id}"
                   data-perm-ids="${escHtml(JSON.stringify(cat.permission_ids))}"
                   onchange="onCategoryToggle(this)">
            <label class="form-check-label" for="cat-${cat.id}">
                <span class="fw-500">${escHtml(cat.name)}</span>
                ${cat.description ? `<span class="text-secondary small ms-1">— ${escHtml(cat.description)}</span>` : ''}
                <span class="rp-badge rp-badge--muted ms-1">${cat.permission_count} perms</span>
            </label>
        </div>`).join('');
}

window.onCategoryToggle = (checkbox) => {
    const permIds = JSON.parse(checkbox.dataset.permIds || '[]');
    permIds.forEach(id => {
        const cb = document.getElementById(`perm-${id}`);
        if (cb && !cb.disabled) {
            cb.checked = checkbox.checked;
        }
    });
    // Refresh all module counts
    _allPermissions.forEach((_, i) => updatePermCount(i));
};

function _getSelectedCategoryIds() {
    return [...document.querySelectorAll('.cat-check:checked')].map(cb => Number(cb.value));
}

function _applyGroupCategories(catIds) {
    const idSet = new Set(catIds);
    document.querySelectorAll('.cat-check').forEach(cb => {
        cb.checked = idSet.has(Number(cb.value));
    });
    // Auto-select permissions from checked categories
    catIds.forEach(catId => {
        const cat = _allCategories.find(c => c.id === catId);
        if (!cat) return;
        cat.permission_ids.forEach(pid => {
            const cb = document.getElementById(`perm-${pid}`);
            if (cb && !cb.disabled) cb.checked = true;
        });
    });
    _allPermissions.forEach((_, i) => updatePermCount(i));
}

async function loadPermissionsAccordion(groupPk) {
    const loadingEl = document.getElementById('permissions-loading');
    const accordionEl = document.getElementById('permissions-accordion');

    try {
        _allPermissions = await apiFetch('/api/v1/permissions/');
    } catch (_) {
        if (loadingEl) loadingEl.textContent = 'Could not load permissions.';
        return;
    }

    if (loadingEl) loadingEl.classList.add('d-none');

    if (!_allPermissions.length) {
        if (accordionEl) accordionEl.innerHTML = '<p class="text-secondary small">No permissions configured.</p>';
        return;
    }

    accordionEl.innerHTML = _allPermissions.map((mod, i) => `
        <div class="accordion-item border-0 border-bottom">
            <h2 class="accordion-header" id="perm-head-${i}">
                <button class="accordion-button collapsed py-2 px-0 bg-transparent shadow-none fw-500"
                        type="button" data-bs-toggle="collapse"
                        data-bs-target="#perm-body-${i}" aria-expanded="false">
                    ${escHtml(mod.label)}
                    <span class="ms-2 text-secondary small" id="perm-count-${i}">
                        (0 / ${mod.permissions.length})
                    </span>
                </button>
            </h2>
            <div id="perm-body-${i}" class="accordion-collapse collapse"
                 data-bs-parent="">
                <div class="accordion-body px-0 pb-2 pt-1">
                    ${mod.permissions.map(p => `
                        <div class="form-check mb-1">
                            <input class="form-check-input perm-check"
                                   type="checkbox" value="${p.id}"
                                   id="perm-${p.id}"
                                   data-module-index="${i}"
                                   onchange="updatePermCount(${i})">
                            <label class="form-check-label small" for="perm-${p.id}">
                                ${escHtml(p.name)}
                            </label>
                        </div>`).join('')}
                </div>
            </div>
        </div>`).join('');
}

window.updatePermCount = (moduleIdx) => {
    const mod = _allPermissions[moduleIdx];
    if (!mod) return;
    const checked = document.querySelectorAll(`.perm-check[data-module-index="${moduleIdx}"]:checked`).length;
    const countEl = document.getElementById(`perm-count-${moduleIdx}`);
    if (countEl) countEl.textContent = `(${checked} / ${mod.permissions.length})`;
};

function _getSelectedPermissionIds() {
    return [...document.querySelectorAll('.perm-check:checked')].map(cb => Number(cb.value));
}

function _applyGroupPermissions(permIds) {
    const idSet = new Set(permIds);
    document.querySelectorAll('.perm-check').forEach(cb => {
        cb.checked = idSet.has(Number(cb.value));
    });
    _allPermissions.forEach((_, i) => updatePermCount(i));
}

function _disablePermissions() {
    document.querySelectorAll('.perm-check').forEach(cb => { cb.disabled = true; });
    const badge = document.getElementById('permissions-system-badge');
    const hint  = document.getElementById('permissions-hint');
    if (badge) badge.classList.remove('d-none');
    if (hint) hint.textContent = 'Permissions for system groups cannot be modified.';
}

async function loadGroupForEdit(pk) {
    try {
        const g = await apiFetch(`/api/v1/user-groups/${pk}/`);

        document.getElementById('id_name').value         = g.name || '';
        document.getElementById('id_description').value  = g.description || '';
        document.getElementById('id_is_admin_group').checked = !!g.is_admin_group;

        _groupIsSystem = !!g.is_system;

        const metaCard = document.getElementById('metadata-card');
        if (metaCard) {
            document.getElementById('meta-created').textContent = formatDateTime(g.created_at);
            document.getElementById('meta-updated').textContent = formatDateTime(g.updated_at);
            metaCard.classList.remove('d-none');
        }

        if (g.is_system) {
            document.getElementById('id_name').disabled         = true;
            document.getElementById('id_is_admin_group').disabled = true;
        }

        // Pre-check categories then permissions
        if (g.category_ids && g.category_ids.length) {
            _applyGroupCategories(g.category_ids);
        }
        if (g.permission_ids) {
            _applyGroupPermissions(g.permission_ids);
        }
        if (g.is_system) {
            _disablePermissions();
            document.querySelectorAll('.cat-check').forEach(cb => { cb.disabled = true; });
        }
    } catch (_) {
        showFlash('Failed to load group data.', 'error');
    }
}

async function submitGroupForm(groupPk) {
    const submitBtn   = document.getElementById('submit-btn');
    const submitLabel = document.getElementById('submit-label');
    const errorBanner = document.getElementById('form-error-banner');

    clearFormErrors();
    errorBanner.classList.add('d-none');

    const payload = {
        name:           document.getElementById('id_name').value.trim(),
        description:    document.getElementById('id_description').value.trim(),
        is_admin_group: document.getElementById('id_is_admin_group').checked,
        permission_ids: _groupIsSystem ? undefined : _getSelectedPermissionIds(),
        category_ids:   _groupIsSystem ? undefined : _getSelectedCategoryIds(),
    };
    if (payload.permission_ids === undefined) delete payload.permission_ids;
    if (payload.category_ids === undefined) delete payload.category_ids;

    const origLabel = submitBtn.dataset.originalLabel || submitLabel.textContent;
    submitBtn.disabled   = true;
    submitLabel.textContent = 'Saving…';

    try {
        if (groupPk) {
            await apiFetch(`/api/v1/user-groups/${groupPk}/`, {
                method: 'PATCH',
                body: JSON.stringify(payload),
            });
        } else {
            await apiFetch('/api/v1/user-groups/', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        }
        window.location.href = '/user-groups/';
    } catch (err) {
        submitBtn.disabled      = false;
        submitLabel.textContent = origLabel;

        const data = err?.data || {};
        let hasFieldErr = false;
        if (data.name)        { showFieldError('id_name', 'name-error', data.name[0]);               hasFieldErr = true; }
        if (data.description) { showFieldError('id_description', 'description-error', data.description[0]); hasFieldErr = true; }
        if (!hasFieldErr) {
            errorBanner.textContent = data.error || data.detail || 'Save failed. Please check the form.';
            errorBanner.classList.remove('d-none');
        }
    }
}

function showFieldError(inputId, errId, msg) {
    const input = document.getElementById(inputId);
    const errEl = document.getElementById(errId);
    if (input) input.classList.add('is-invalid');
    if (errEl) errEl.textContent = msg;
}

function clearFormErrors() {
    document.querySelectorAll('.form-control.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    document.querySelectorAll('.invalid-feedback').forEach(el => { el.textContent = ''; });
}

// ── Detail view ───────────────────────────────────────────────────────────────

let _members      = [];
let _selectedPks  = new Set();
let _addModal     = null;
let _removeModal  = null;
let _deleteGrpModal = null;
let _removePk     = null;

function initDetailView() {
    const pk = window.GROUP_PK;
    if (!pk) return;

    _addModal       = new bootstrap.Modal(document.getElementById('addMembersModal'));
    _removeModal    = new bootstrap.Modal(document.getElementById('removeMemberModal'));
    _deleteGrpModal = new bootstrap.Modal(document.getElementById('deleteGroupModal'));

    loadGroupDetail(pk);
    loadMembers(pk);

    document.getElementById('member-search').addEventListener('input', () => {
        filterMemberRows(document.getElementById('member-search').value.trim().toLowerCase());
    });

    wireDetailButtons(pk);
}

async function loadGroupDetail(pk) {
    try {
        const g = await apiFetch(`/api/v1/user-groups/${pk}/`);

        // Page title
        const titleEl = document.getElementById('page-group-name');
        if (titleEl) titleEl.textContent = g.name;
        document.title = `${g.name} — User Groups — Resource Planner`;

        // Subtitle badges
        const subtitleEl = document.getElementById('page-group-subtitle');
        if (subtitleEl) {
            let badges = '';
            if (g.is_admin_group) badges += '<span class="rp-badge rp-badge--warning me-2">Admin Group</span>';
            if (g.is_system)      badges += '<span class="rp-badge rp-badge--info me-2">System</span>';
            const countEl = document.getElementById('member-count-subtitle');
            subtitleEl.innerHTML = badges;
            if (countEl) subtitleEl.appendChild(countEl);
        }

        // Header action buttons (edit / delete) — hidden for system groups
        const actionsEl = document.getElementById('header-actions');
        if (actionsEl) {
            if (!g.is_system) {
                actionsEl.innerHTML = `
                    <a href="/user-groups/${g.id}/edit/" class="btn btn-outline-secondary btn-sm">
                        <i class="bi bi-pencil me-1"></i>Edit
                    </a>
                    <button class="btn btn-danger btn-sm" id="delete-group-btn">
                        <i class="bi bi-trash me-1"></i>Delete
                    </button>`;

                document.getElementById('delete-group-btn')
                    ?.addEventListener('click', () => _deleteGrpModal.show());
            }
        }

        // Delete modal group name
        const deleteNameEl = document.getElementById('delete-group-name-modal');
        if (deleteNameEl) deleteNameEl.textContent = g.name;

        // Group info card
        document.getElementById('info-type').innerHTML = g.is_admin_group
            ? '<span class="rp-badge rp-badge--warning">Admin</span>'
            : '<span class="rp-badge rp-badge--muted">Standard</span>';
        document.getElementById('info-description').textContent = g.description || '—';
        document.getElementById('meta-created').textContent = formatDateTime(g.created_at);
        document.getElementById('meta-updated').textContent = formatDateTime(g.updated_at);
    } catch (_) {}
}

async function loadMembers(pk) {
    const tbody    = document.getElementById('members-tbody');
    const tableWrap = document.getElementById('members-table-wrap');
    const emptyEl  = document.getElementById('members-empty');

    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary py-4">Loading…</td></tr>';

    try {
        const data = await apiFetch(`/api/v1/user-groups/${pk}/members/`);
        _members = Array.isArray(data) ? data : (data.results || []);
        renderMemberRows(_members);

        const countEl = document.getElementById('member-count-subtitle');
        if (countEl) countEl.textContent = `${_members.length} member${_members.length !== 1 ? 's' : ''}`;
    } catch (_) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-4">Failed to load members.</td></tr>';
    }
}

function renderMemberRows(members) {
    const tbody    = document.getElementById('members-tbody');
    const tableWrap = document.getElementById('members-table-wrap');
    const emptyEl  = document.getElementById('members-empty');

    if (!members.length) {
        tableWrap.classList.add('d-none');
        emptyEl.classList.remove('d-none');
        return;
    }

    tableWrap.classList.remove('d-none');
    emptyEl.classList.add('d-none');
    tbody.innerHTML = members.map(m => renderMemberRow(m)).join('');
}

function renderMemberRow(m) {
    const name = m.full_name || m.email;
    const avatar = m.avatar_display
        ? `<img src="${escHtml(m.avatar_display)}" class="rp-avatar-sm me-2" alt="">`
        : `<span class="rp-avatar-sm-initials me-2">${escHtml((m.first_name || m.email || '?')[0].toUpperCase())}</span>`;

    return `
        <tr data-member-id="${m.id}">
            <td>
                <div class="d-flex align-items-center">
                    ${avatar}
                    <span class="fw-500">${escHtml(name)}</span>
                </div>
            </td>
            <td class="text-secondary small">${escHtml(m.email)}</td>
            <td class="text-secondary small">${formatDateTime(m.joined_at || null)}</td>
            <td class="text-center">
                <button class="btn btn-ghost-icon text-danger" title="Remove"
                        onclick="showRemoveMemberModal(${m.id}, '${escHtml(name)}')">
                    <i class="bi bi-x-lg"></i>
                </button>
            </td>
        </tr>`;
}

function filterMemberRows(q) {
    if (!q) { renderMemberRows(_members); return; }
    renderMemberRows(_members.filter(m =>
        (m.full_name || '').toLowerCase().includes(q) ||
        (m.email || '').toLowerCase().includes(q)
    ));
}

function wireDetailButtons(pk) {
    // Delete group
    document.getElementById('confirm-delete-group-btn').addEventListener('click', async () => {
        _deleteGrpModal.hide();
        try {
            await apiFetch(`/api/v1/user-groups/${pk}/`, { method: 'DELETE' });
            window.location.href = '/user-groups/';
        } catch (err) {
            showFlash(err?.data?.error || 'Could not delete group.', 'error');
        }
    });

    // Remove member modal
    window.showRemoveMemberModal = (userId, name) => {
        _removePk = userId;
        document.getElementById('remove-member-name').textContent = name;
        _removeModal.show();
    };

    document.getElementById('confirm-remove-btn').addEventListener('click', async () => {
        _removeModal.hide();
        try {
            await apiFetch(`/api/v1/user-groups/${pk}/remove_members/`, {
                method: 'POST',
                body: JSON.stringify({ user_ids: [_removePk] }),
            });
            showFlash('Member removed.', 'success');
            _members = _members.filter(m => m.id !== _removePk);
            renderMemberRows(_members);
            const countEl = document.getElementById('member-count-subtitle');
            if (countEl) countEl.textContent = `${_members.length} member${_members.length !== 1 ? 's' : ''}`;
        } catch (err) {
            showFlash(err?.data?.error || 'Could not remove member.', 'error');
        }
    });

    // Add members
    document.getElementById('add-member-btn').addEventListener('click', () => {
        _selectedPks.clear();
        document.getElementById('user-search-input').value = '';
        document.getElementById('user-search-results').innerHTML = '';
        renderSelectedChips();
        _addModal.show();
        setTimeout(() => document.getElementById('user-search-input').focus(), 300);
    });

    let _searchTimer = null;
    document.getElementById('user-search-input').addEventListener('input', () => {
        clearTimeout(_searchTimer);
        _searchTimer = setTimeout(() => searchUsers(), 300);
    });

    document.getElementById('confirm-add-btn').addEventListener('click', async () => {
        if (!_selectedPks.size) return;
        _addModal.hide();
        try {
            await apiFetch(`/api/v1/user-groups/${pk}/add_members/`, {
                method: 'POST',
                body: JSON.stringify({ user_ids: [..._selectedPks] }),
            });
            showFlash('Members added.', 'success');
            await loadMembers(pk);
        } catch (err) {
            showFlash(err?.data?.error || 'Could not add members.', 'error');
        }
    });
}

async function searchUsers() {
    const q = document.getElementById('user-search-input').value.trim();
    const resultsEl = document.getElementById('user-search-results');

    if (!q) { resultsEl.innerHTML = ''; return; }

    resultsEl.innerHTML = '<span class="text-secondary small">Searching…</span>';
    try {
        const existingIds = new Set(_members.map(m => m.id));
        const data = await apiFetch(`/api/v1/users/?search=${encodeURIComponent(q)}&page_size=20`);
        const users = Array.isArray(data) ? data : (data.results || []);

        if (!users.length) {
            resultsEl.innerHTML = '<span class="text-secondary small">No users found.</span>';
            return;
        }

        resultsEl.innerHTML = users.map(u => {
            const name = u.full_name || u.email;
            const alreadyMember = existingIds.has(u.id);
            const selected = _selectedPks.has(u.id);
            const disabled = alreadyMember ? 'disabled' : '';
            const checkedAttr = (selected || alreadyMember) ? 'checked' : '';
            const memberNote = alreadyMember ? '<span class="text-secondary small ms-2">Already a member</span>' : '';
            const avatar = u.avatar_display
                ? `<img src="${escHtml(u.avatar_display)}" class="rp-avatar-sm me-2" alt="">`
                : `<span class="rp-avatar-sm-initials me-2">${escHtml((u.first_name || u.email || '?')[0].toUpperCase())}</span>`;

            return `
                <div class="d-flex align-items-center gap-2 py-1 px-2 rounded ${selected ? 'bg-light' : ''}">
                    <input type="checkbox" class="form-check-input user-pick-check" ${checkedAttr} ${disabled}
                           data-user-id="${u.id}" data-user-name="${escHtml(name)}" id="pick-${u.id}">
                    <label class="d-flex align-items-center flex-grow-1 gap-2 mb-0 cursor-pointer" for="pick-${u.id}">
                        ${avatar}
                        <span>${escHtml(name)}</span>
                        <span class="text-secondary small">${escHtml(u.email)}</span>
                        ${memberNote}
                    </label>
                </div>`;
        }).join('');

        resultsEl.querySelectorAll('.user-pick-check').forEach(cb => {
            cb.addEventListener('change', () => {
                const uid  = Number(cb.dataset.userId);
                const name = cb.dataset.userName;
                if (cb.checked) { _selectedPks.add(uid); }
                else            { _selectedPks.delete(uid); }
                renderSelectedChips();
            });
        });
    } catch (_) {
        resultsEl.innerHTML = '<span class="text-danger small">Search failed.</span>';
    }
}

function renderSelectedChips() {
    const section   = document.getElementById('selected-users-section');
    const list      = document.getElementById('selected-users-list');
    const countEl   = document.getElementById('selected-count');
    const addBtn    = document.getElementById('confirm-add-btn');

    countEl.textContent = _selectedPks.size;
    addBtn.disabled     = _selectedPks.size === 0;

    if (!_selectedPks.size) {
        section.classList.add('d-none');
        list.innerHTML = '';
        return;
    }

    section.classList.remove('d-none');

    const picked = [];
    document.querySelectorAll('.user-pick-check:checked').forEach(cb => {
        if (_selectedPks.has(Number(cb.dataset.userId))) {
            picked.push({ id: Number(cb.dataset.userId), name: cb.dataset.userName });
        }
    });

    list.innerHTML = picked.map(p => `
        <span class="rp-badge rp-badge--muted d-flex align-items-center gap-1">
            ${escHtml(p.name)}
            <button type="button" class="btn-close btn-close-sm" style="font-size:9px"
                    onclick="removeSelected(${p.id})"></button>
        </span>`).join('');
}

window.removeSelected = (uid) => {
    _selectedPks.delete(uid);
    const cb = document.querySelector(`.user-pick-check[data-user-id="${uid}"]`);
    if (cb) cb.checked = false;
    renderSelectedChips();
};
