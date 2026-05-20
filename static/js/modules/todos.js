'use strict';

import { apiFetch, escHtml, formatDate, formatDateTime, showFlash } from './../main.js';
import { API_URLS } from './../urls.js';

const isDetail = typeof window.TODO_PK !== 'undefined';

document.addEventListener('DOMContentLoaded', () => {
    if (isDetail) initDetailPage();
    else          initListPage();
});

// ─────────────────────────────────────────────────────────────────────────────
// SHARED HELPERS
// ─────────────────────────────────────────────────────────────────────────────

const PRIORITY_BADGE = {
    urgent: 'bg-danger',
    high:   'bg-warning text-dark',
    medium: 'bg-info text-dark',
    low:    'bg-secondary',
};

const STATUS_BADGE = {
    open:        'bg-secondary',
    in_progress: 'bg-primary',
    done:        'bg-success',
};

function priorityBadge(p, label) {
    return `<span class="badge ${PRIORITY_BADGE[p] || 'bg-secondary'}">${escHtml(label || p)}</span>`;
}

function statusBadge(s, label) {
    return `<span class="badge ${STATUS_BADGE[s] || 'bg-secondary'}">${escHtml(label || s)}</span>`;
}

async function loadUsers(selectEl, selectedId = null) {
    try {
        const users = await apiFetch('/api/v1/users/?page_size=200', { method: 'GET' });
        const list  = Array.isArray(users) ? users : (users.results || []);
        selectEl.innerHTML = '<option value="">Unassigned</option>';
        for (const u of list) {
            const name = escHtml(u.full_name || u.email);
            const sel  = (selectedId && String(u.id) === String(selectedId)) ? ' selected' : '';
            selectEl.innerHTML += `<option value="${u.id}"${sel}>${name}</option>`;
        }
    } catch { /* non-fatal */ }
}

// ─────────────────────────────────────────────────────────────────────────────
// LIST PAGE
// ─────────────────────────────────────────────────────────────────────────────

let _scope    = 'mine';
let _status   = '';
let _priority = '';
let _due      = '';
let _search   = '';
let _page     = 1;
let _deleteId = null;

async function initListPage() {
    loadTodos();

    // scope tabs
    document.querySelectorAll('#scope-tabs button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#scope-tabs button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _scope = btn.dataset.scope;
            _page  = 1;
            loadTodos();
        });
    });

    document.getElementById('filter-status')?.addEventListener('change', e => {
        _status = e.target.value; _page = 1; loadTodos();
    });
    document.getElementById('filter-priority')?.addEventListener('change', e => {
        _priority = e.target.value; _page = 1; loadTodos();
    });
    document.getElementById('filter-due')?.addEventListener('change', e => {
        _due = e.target.value; _page = 1; loadTodos();
    });

    let searchTimer;
    document.getElementById('filter-search')?.addEventListener('input', e => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { _search = e.target.value; _page = 1; loadTodos(); }, 300);
    });

    document.getElementById('btn-new-todo')?.addEventListener('click', openNewModal);
    document.getElementById('btn-save-todo')?.addEventListener('click', saveTodo);
    document.getElementById('todo-is-recurring')?.addEventListener('change', e => {
        document.getElementById('recurrence-fields').classList.toggle('d-none', !e.target.checked);
    });

    await loadUsers(document.getElementById('todo-assigned'));
}

async function loadTodos() {
    const params = new URLSearchParams({
        scope:      _scope,
        page:       _page,
        page_size:  25,
    });
    if (_status)   params.set('status',     _status);
    if (_priority) params.set('priority',   _priority);
    if (_due)      params.set('due_filter', _due);
    if (_search)   params.set('search',     _search);

    const container = document.getElementById('todo-list-container');
    container.innerHTML = '<p class="text-secondary small">Loading…</p>';

    try {
        const data = await apiFetch(`/api/v1/todos/?${params}`, { method: 'GET' });
        renderTodoList(data.results, container);
        renderPagination(data.pagination, document.getElementById('todo-pagination'));
    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">Failed to load tasks.</div>`;
    }
}

function renderTodoList(todos, container) {
    if (!todos.length) {
        container.innerHTML = '<p class="text-secondary small mt-2">No tasks found.</p>';
        return;
    }

    const rows = todos.map(t => {
        const overdueCls = t.is_overdue ? 'text-danger fw-500' : '';
        const dueTxt     = t.due_date   ? `<span class="${overdueCls}">${formatDate(t.due_date)}</span>` : '—';
        const assignee   = t.assigned_to_name ? escHtml(t.assigned_to_name) : '<span class="text-secondary">—</span>';
        const recurring  = t.is_recurring ? '<i class="bi bi-arrow-repeat text-info ms-1" title="Recurring"></i>' : '';
        return `
        <tr>
            <td>
                <a href="/todos/${t.id}/" class="fw-500 text-decoration-none">${escHtml(t.title)}</a>${recurring}
                ${t.description ? `<div class="text-secondary" style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:320px">${escHtml(t.description.substring(0,80))}</div>` : ''}
            </td>
            <td>${statusBadge(t.status, t.status_display)}</td>
            <td>${priorityBadge(t.priority, t.priority_display)}</td>
            <td>${dueTxt}</td>
            <td>${assignee}</td>
            <td>
                <div class="d-flex gap-1">
                    ${t.status !== 'done'
                        ? `<button class="btn btn-sm btn-outline-success py-0 px-1" data-action="complete" data-id="${t.id}" title="Complete"><i class="bi bi-check-lg"></i></button>`
                        : `<button class="btn btn-sm btn-outline-secondary py-0 px-1" data-action="reopen" data-id="${t.id}" title="Reopen"><i class="bi bi-arrow-counterclockwise"></i></button>`
                    }
                    <button class="btn btn-sm btn-outline-primary py-0 px-1" data-action="edit" data-id="${t.id}" data-todo='${JSON.stringify(t).replace(/'/g,"&#39;")}' title="Edit"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger py-0 px-1" data-action="delete" data-id="${t.id}" data-title="${escHtml(t.title)}" title="Delete"><i class="bi bi-trash"></i></button>
                </div>
            </td>
        </tr>`;
    }).join('');

    container.innerHTML = `
    <div class="table-responsive">
        <table class="table table-hover rp-table align-middle mb-0">
            <thead>
                <tr>
                    <th>Task</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Due</th>
                    <th>Assigned to</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    </div>`;

    container.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', onListAction);
    });
}

async function onListAction(e) {
    const btn    = e.currentTarget;
    const action = btn.dataset.action;
    const id     = btn.dataset.id;

    if (action === 'complete') {
        try {
            await apiFetch(`/api/v1/todos/${id}/complete/`, { method: 'POST' });
            showFlash('Task completed.', 'success');
            loadTodos();
        } catch { showFlash('Could not complete task.', 'error'); }
    } else if (action === 'reopen') {
        try {
            await apiFetch(`/api/v1/todos/${id}/reopen/`, { method: 'POST' });
            showFlash('Task reopened.', 'success');
            loadTodos();
        } catch { showFlash('Could not reopen task.', 'error'); }
    } else if (action === 'edit') {
        const todo = JSON.parse(btn.dataset.todo);
        openEditModalFromList(todo);
    } else if (action === 'delete') {
        _deleteId = id;
        document.getElementById('delete-todo-title').textContent = btn.dataset.title;
        bootstrap.Modal.getOrCreateInstance(document.getElementById('deleteTodoModal')).show();
    }
}

// Confirm delete
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btn-confirm-delete')?.addEventListener('click', async () => {
        if (!_deleteId) return;
        try {
            await apiFetch(`/api/v1/todos/${_deleteId}/`, { method: 'DELETE' });
            bootstrap.Modal.getInstance(document.getElementById('deleteTodoModal'))?.hide();
            showFlash('Task deleted.', 'success');
            _deleteId = null;
            loadTodos();
        } catch { showFlash('Could not delete task.', 'error'); }
    });
});

function renderPagination(pagination, container) {
    if (!pagination || pagination.total_pages <= 1) { container.innerHTML = ''; return; }
    const { current_page, total_pages } = pagination;
    let html = '<nav><ul class="pagination pagination-sm justify-content-center">';
    html += `<li class="page-item${current_page <= 1 ? ' disabled' : ''}">
        <button class="page-link" data-pg="${current_page - 1}">&laquo;</button></li>`;
    for (let p = 1; p <= total_pages; p++) {
        html += `<li class="page-item${p === current_page ? ' active' : ''}">
            <button class="page-link" data-pg="${p}">${p}</button></li>`;
    }
    html += `<li class="page-item${current_page >= total_pages ? ' disabled' : ''}">
        <button class="page-link" data-pg="${current_page + 1}">&raquo;</button></li>`;
    html += '</ul></nav>';
    container.innerHTML = html;
    container.querySelectorAll('[data-pg]').forEach(btn => {
        btn.addEventListener('click', () => { _page = parseInt(btn.dataset.pg); loadTodos(); });
    });
}

// ── New todo modal ────────────────────────────────────────────────────────────

function openNewModal() {
    document.getElementById('todo-edit-id').value      = '';
    document.getElementById('todo-title').value        = '';
    document.getElementById('todo-description').value  = '';
    document.getElementById('todo-priority').value     = 'medium';
    document.getElementById('todo-due-date').value     = '';
    document.getElementById('todo-reminder-at').value  = '';
    document.getElementById('todo-is-recurring').checked = false;
    document.getElementById('recurrence-fields').classList.add('d-none');
    document.getElementById('todo-recurrence-interval').value   = 1;
    document.getElementById('todo-recurrence-rule').value       = 'weekly';
    document.getElementById('todo-recurrence-end-date').value   = '';
    document.getElementById('todo-assigned').value     = '';
    document.getElementById('todo-modal-title').innerHTML = '<i class="bi bi-plus-circle me-2"></i>New Task';
    document.getElementById('todo-modal-banner').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('todoModal')).show();
}

function openEditModalFromList(todo) {
    document.getElementById('todo-edit-id').value     = todo.id;
    document.getElementById('todo-title').value       = todo.title;
    document.getElementById('todo-description').value = todo.description || '';
    document.getElementById('todo-priority').value    = todo.priority;
    document.getElementById('todo-due-date').value    = todo.due_date || '';
    document.getElementById('todo-reminder-at').value = todo.reminder_at
        ? todo.reminder_at.substring(0, 16) : '';
    document.getElementById('todo-is-recurring').checked = todo.is_recurring;
    document.getElementById('recurrence-fields').classList.toggle('d-none', !todo.is_recurring);
    document.getElementById('todo-recurrence-interval').value  = todo.recurrence_interval || 1;
    document.getElementById('todo-recurrence-rule').value      = todo.recurrence_rule || 'weekly';
    document.getElementById('todo-recurrence-end-date').value  = todo.recurrence_end_date || '';
    // set assigned
    const sel = document.getElementById('todo-assigned');
    if (sel && todo.assigned_to) {
        const opt = sel.querySelector(`option[value="${todo.assigned_to}"]`);
        if (opt) opt.selected = true;
    }
    document.getElementById('todo-modal-title').innerHTML = '<i class="bi bi-pencil me-2"></i>Edit Task';
    document.getElementById('todo-modal-banner').classList.add('d-none');
    bootstrap.Modal.getOrCreateInstance(document.getElementById('todoModal')).show();
}

async function saveTodo() {
    const editId    = document.getElementById('todo-edit-id').value;
    const title     = document.getElementById('todo-title').value.trim();
    const banner    = document.getElementById('todo-modal-banner');

    if (!title) {
        banner.textContent = 'Title is required.';
        banner.classList.remove('d-none');
        return;
    }
    banner.classList.add('d-none');

    const isRecurring = document.getElementById('todo-is-recurring').checked;
    const payload = {
        title,
        description:         document.getElementById('todo-description').value,
        priority:            document.getElementById('todo-priority').value,
        due_date:            document.getElementById('todo-due-date').value || null,
        reminder_at:         document.getElementById('todo-reminder-at').value || null,
        assigned_to:         document.getElementById('todo-assigned').value || null,
        is_recurring:        isRecurring,
        recurrence_rule:     isRecurring ? document.getElementById('todo-recurrence-rule').value : '',
        recurrence_interval: isRecurring ? parseInt(document.getElementById('todo-recurrence-interval').value) : 1,
        recurrence_end_date: isRecurring ? (document.getElementById('todo-recurrence-end-date').value || null) : null,
    };

    try {
        if (editId) {
            await apiFetch(`/api/v1/todos/${editId}/`, { method: 'PATCH', body: JSON.stringify(payload) });
            showFlash('Task updated.', 'success');
        } else {
            await apiFetch('/api/v1/todos/', { method: 'POST', body: JSON.stringify(payload) });
            showFlash('Task created.', 'success');
        }
        bootstrap.Modal.getInstance(document.getElementById('todoModal'))?.hide();
        loadTodos();
    } catch (err) {
        const msg = err.data ? Object.values(err.data).flat().join(' ') : 'Error saving task.';
        banner.textContent = msg;
        banner.classList.remove('d-none');
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// DETAIL PAGE
// ─────────────────────────────────────────────────────────────────────────────

async function initDetailPage() {
    await loadTodoDetail();
    await loadComments();

    document.getElementById('btn-add-comment')?.addEventListener('click', addComment);
    initMentionAutocomplete();

    // Edit modal save
    document.getElementById('btn-save-edit')?.addEventListener('click', saveEditDetail);
}

async function loadTodoDetail() {
    try {
        const todo = await apiFetch(`/api/v1/todos/${window.TODO_PK}/`, { method: 'GET' });
        renderDetail(todo);
        renderMeta(todo);
        if (todo.is_recurring) loadRecurrenceChildren(todo);
    } catch {
        document.getElementById('todo-detail-body').innerHTML =
            '<div class="alert alert-danger">Could not load task.</div>';
    }
}

function renderDetail(todo) {
    document.title = `${todo.title} — Resource Planner`;
    document.getElementById('todo-detail-title').textContent = todo.title;

    // Action buttons
    const actionsEl = document.getElementById('todo-actions');
    actionsEl.innerHTML = '';
    if (todo.status !== 'done') {
        const completeBtn = document.createElement('button');
        completeBtn.className = 'btn btn-success btn-sm';
        completeBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Complete';
        completeBtn.addEventListener('click', () => completeTodo(todo.id));
        actionsEl.appendChild(completeBtn);
    } else {
        const reopenBtn = document.createElement('button');
        reopenBtn.className = 'btn btn-outline-secondary btn-sm';
        reopenBtn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Reopen';
        reopenBtn.addEventListener('click', () => reopenTodo(todo.id));
        actionsEl.appendChild(reopenBtn);
    }

    const editBtn = document.createElement('button');
    editBtn.className = 'btn btn-outline-primary btn-sm';
    editBtn.innerHTML = '<i class="bi bi-pencil me-1"></i>Edit';
    editBtn.addEventListener('click', () => openDetailEditModal(todo));
    actionsEl.appendChild(editBtn);

    // Body
    const descHtml = todo.description
        ? `<p class="mb-0 text-secondary">${escHtml(todo.description).replace(/\n/g, '<br>')}</p>`
        : '<p class="text-muted fst-italic small mb-0">No description.</p>';

    document.getElementById('todo-detail-body').innerHTML = `
        <div class="d-flex flex-wrap gap-2 mb-3">
            ${statusBadge(todo.status, todo.status_display)}
            ${priorityBadge(todo.priority, todo.priority_display)}
            ${todo.is_overdue ? '<span class="badge bg-danger">Overdue</span>' : ''}
            ${todo.is_recurring ? '<span class="badge bg-info text-dark"><i class="bi bi-arrow-repeat me-1"></i>Recurring</span>' : ''}
        </div>
        ${descHtml}`;
}

function renderMeta(todo) {
    const rows = [
        ['Created by',   todo.created_by_name || '—'],
        ['Assigned to',  todo.assigned_to_name || 'Unassigned'],
        ['Due date',     todo.due_date ? formatDate(todo.due_date) : '—'],
        ['Reminder',     todo.reminder_at ? formatDateTime(todo.reminder_at) : '—'],
        ['Completed',    todo.completed_at ? formatDateTime(todo.completed_at) : '—'],
        ['Created',      formatDateTime(todo.created_at)],
        ['Updated',      formatDateTime(todo.updated_at)],
    ];
    if (todo.is_recurring) {
        rows.push(['Recurs every', `${todo.recurrence_interval} ${todo.recurrence_rule}(s)`]);
        if (todo.recurrence_end_date) rows.push(['Recurrence ends', formatDate(todo.recurrence_end_date)]);
    }

    document.getElementById('todo-meta-body').innerHTML = rows.map(([label, val]) => `
        <div class="d-flex justify-content-between align-items-start py-1 border-bottom" style="font-size:13px">
            <span class="text-secondary">${escHtml(label)}</span>
            <span class="text-end ms-3">${val}</span>
        </div>`).join('');
}

async function loadRecurrenceChildren(todo) {
    const card = document.getElementById('recurring-card');
    const list = document.getElementById('recurring-list');
    card.classList.remove('d-none');
    try {
        const data = await apiFetch(`/api/v1/todos/?scope=all&page_size=50&parent_todo=${todo.parent_todo || todo.id}`, { method: 'GET' });
        const children = (data.results || []).filter(t => t.id !== todo.id);
        if (!children.length) {
            list.innerHTML = '<p class="text-secondary small">No prior instances.</p>';
            return;
        }
        list.innerHTML = children.map(t => `
            <div class="d-flex justify-content-between align-items-center py-1 border-bottom" style="font-size:13px">
                <a href="/todos/${t.id}/" class="text-decoration-none">${formatDate(t.due_date || t.created_at)}</a>
                ${statusBadge(t.status, t.status_display)}
            </div>`).join('');
    } catch {
        card.classList.add('d-none');
    }
}

async function completeTodo(id) {
    try {
        await apiFetch(`/api/v1/todos/${id}/complete/`, { method: 'POST' });
        showFlash('Task completed.', 'success');
        loadTodoDetail();
    } catch { showFlash('Could not complete task.', 'error'); }
}

async function reopenTodo(id) {
    try {
        await apiFetch(`/api/v1/todos/${id}/reopen/`, { method: 'POST' });
        showFlash('Task reopened.', 'success');
        loadTodoDetail();
    } catch { showFlash('Could not reopen task.', 'error'); }
}

// ── Edit modal (detail page) ──────────────────────────────────────────────────

async function openDetailEditModal(todo) {
    document.getElementById('edit-todo-title').value        = todo.title;
    document.getElementById('edit-todo-description').value  = todo.description || '';
    document.getElementById('edit-todo-priority').value     = todo.priority;
    document.getElementById('edit-todo-status').value       = todo.status;
    document.getElementById('edit-todo-due-date').value     = todo.due_date || '';
    document.getElementById('edit-todo-reminder-at').value  = todo.reminder_at
        ? todo.reminder_at.substring(0, 16) : '';
    document.getElementById('edit-modal-banner').classList.add('d-none');

    const sel = document.getElementById('edit-todo-assigned');
    await loadUsers(sel, todo.assigned_to);

    bootstrap.Modal.getOrCreateInstance(document.getElementById('todoEditModal')).show();
}

async function saveEditDetail() {
    const title  = document.getElementById('edit-todo-title').value.trim();
    const banner = document.getElementById('edit-modal-banner');

    if (!title) {
        banner.textContent = 'Title is required.';
        banner.classList.remove('d-none');
        return;
    }
    banner.classList.add('d-none');

    const payload = {
        title,
        description:  document.getElementById('edit-todo-description').value,
        priority:     document.getElementById('edit-todo-priority').value,
        status:       document.getElementById('edit-todo-status').value,
        due_date:     document.getElementById('edit-todo-due-date').value || null,
        reminder_at:  document.getElementById('edit-todo-reminder-at').value || null,
        assigned_to:  document.getElementById('edit-todo-assigned').value || null,
    };

    try {
        await apiFetch(`/api/v1/todos/${window.TODO_PK}/`, { method: 'PATCH', body: JSON.stringify(payload) });
        bootstrap.Modal.getInstance(document.getElementById('todoEditModal'))?.hide();
        showFlash('Task updated.', 'success');
        loadTodoDetail();
    } catch (err) {
        const msg = err.data ? Object.values(err.data).flat().join(' ') : 'Error saving.';
        banner.textContent = msg;
        banner.classList.remove('d-none');
    }
}

// ── Comments ──────────────────────────────────────────────────────────────────

async function loadComments() {
    const container = document.getElementById('comments-list');
    try {
        const comments = await apiFetch(`/api/v1/todos/${window.TODO_PK}/comments/`, { method: 'GET' });
        if (!comments.length) {
            container.innerHTML = '<p class="text-secondary small">No comments yet.</p>';
            return;
        }
        container.innerHTML = comments.map(c => renderComment(c)).join('');
        container.querySelectorAll('[data-comment-delete]').forEach(btn => {
            btn.addEventListener('click', () => deleteComment(btn.dataset.commentDelete));
        });
    } catch {
        container.innerHTML = '<p class="text-danger small">Could not load comments.</p>';
    }
}

function renderComment(c) {
    const body = escHtml(c.content).replace(
        /@([\w.+-]+)/g,
        '<strong class="text-primary">@$1</strong>',
    ).replace(/\n/g, '<br>');
    return `
    <div class="d-flex gap-3 py-3 border-bottom" id="comment-${c.id}">
        <div class="flex-shrink-0">
            <div class="rounded-circle bg-secondary d-flex align-items-center justify-content-center text-white fw-500"
                 style="width:32px;height:32px;font-size:13px">
                ${escHtml((c.created_by_name || '?').substring(0, 1).toUpperCase())}
            </div>
        </div>
        <div class="flex-grow-1">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-500 small">${escHtml(c.created_by_name || 'Unknown')}</span>
                <span class="text-secondary" style="font-size:11px">${formatDateTime(c.created_at)}</span>
            </div>
            <div style="font-size:14px">${body}</div>
        </div>
        <button class="btn btn-ghost-icon btn-sm text-secondary align-self-start"
                data-comment-delete="${c.id}" title="Delete comment">
            <i class="bi bi-x-lg"></i>
        </button>
    </div>`;
}

async function addComment() {
    const textarea = document.getElementById('new-comment-content');
    const content  = textarea.value.trim();
    if (!content) return;

    try {
        await apiFetch(`/api/v1/todos/${window.TODO_PK}/comments/`, {
            method: 'POST',
            body: JSON.stringify({ content }),
        });
        textarea.value = '';
        hideMentionDropdown();
        loadComments();
    } catch { showFlash('Could not post comment.', 'error'); }
}

async function deleteComment(commentId) {
    try {
        await apiFetch(`/api/v1/todos/${window.TODO_PK}/comments/${commentId}/`, { method: 'DELETE' });
        document.getElementById(`comment-${commentId}`)?.remove();
        const container = document.getElementById('comments-list');
        if (!container.querySelector('.d-flex')) {
            container.innerHTML = '<p class="text-secondary small">No comments yet.</p>';
        }
    } catch { showFlash('Could not delete comment.', 'error'); }
}

// ── @mention autocomplete ─────────────────────────────────────────────────────

function initMentionAutocomplete() {
    const textarea = document.getElementById('new-comment-content');
    const dropdown = document.getElementById('mention-dropdown');
    if (!textarea || !dropdown) return;

    let mentionStart = -1;
    let mentionTimer;

    textarea.addEventListener('keyup', async (e) => {
        const val   = textarea.value;
        const pos   = textarea.selectionStart;
        const chunk = val.substring(0, pos);
        const match = chunk.match(/@([\w.]*)$/);

        if (!match) {
            hideMentionDropdown();
            mentionStart = -1;
            return;
        }

        const query = match[1];
        mentionStart = pos - query.length - 1; // position of @

        clearTimeout(mentionTimer);
        mentionTimer = setTimeout(async () => {
            if (query.length < 1) { hideMentionDropdown(); return; }
            try {
                const users = await apiFetch(`/api/v1/todos/mention-users/?q=${encodeURIComponent(query)}`, { method: 'GET' });
                showMentionDropdown(users, textarea, dropdown, query);
            } catch { hideMentionDropdown(); }
        }, 200);
    });

    textarea.addEventListener('keydown', e => {
        if (dropdown.style.display === 'none') return;
        const items = dropdown.querySelectorAll('.dropdown-item');
        const active = dropdown.querySelector('.dropdown-item.active');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (!active) items[0]?.classList.add('active');
            else {
                active.classList.remove('active');
                const next = active.nextElementSibling;
                if (next) next.classList.add('active');
                else items[0]?.classList.add('active');
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (!active) items[items.length - 1]?.classList.add('active');
            else {
                active.classList.remove('active');
                const prev = active.previousElementSibling;
                if (prev) prev.classList.add('active');
                else items[items.length - 1]?.classList.add('active');
            }
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            if (active) {
                e.preventDefault();
                insertMention(textarea, active.dataset.handle, mentionStart);
                hideMentionDropdown();
            }
        } else if (e.key === 'Escape') {
            hideMentionDropdown();
        }
    });

    document.addEventListener('click', e => {
        if (!dropdown.contains(e.target) && e.target !== textarea) hideMentionDropdown();
    });
}

function showMentionDropdown(users, textarea, dropdown, query) {
    if (!users.length) { hideMentionDropdown(); return; }
    dropdown.innerHTML = users.map(u => {
        const handle = u.email.split('@')[0];
        return `<button class="dropdown-item" type="button"
                        data-handle="${escHtml(handle)}" style="font-size:13px">
            <strong>@${escHtml(handle)}</strong>
            <span class="text-secondary ms-2">${escHtml(u.name)}</span>
        </button>`;
    }).join('');

    dropdown.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            const pos = textarea.value.lastIndexOf('@', textarea.selectionStart - 1);
            insertMention(textarea, item.dataset.handle, pos);
            hideMentionDropdown();
        });
    });

    dropdown.style.display = 'block';
}

function hideMentionDropdown() {
    const dropdown = document.getElementById('mention-dropdown');
    if (dropdown) dropdown.style.display = 'none';
}

function insertMention(textarea, handle, atPos) {
    const val   = textarea.value;
    const pos   = textarea.selectionStart;
    const before = val.substring(0, atPos);
    const after  = val.substring(pos);
    textarea.value = `${before}@${handle} ${after}`;
    textarea.selectionStart = textarea.selectionEnd = atPos + handle.length + 2;
    textarea.focus();
}
