/* Roadmap detail — Gantt + summary views */

const roadmapPk = document.getElementById('roadmap-pk')?.value;
let _roadmap = null;
let _sprints = [];
let _teams = [];
let _programmes = [];
let _users = [];
let _editingItemId = null;
let _milestoneItemId = null;
let _taskItemId = null;
let _editingTaskId = null;
let _selectedImport = new Set();
let _groupBy = 'none';
let _fyFilter = '';
let _viewMode = 'gantt';

function getCsrf() {
    return document.cookie.split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}
function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Data Loading ─────────────────────────────────────────────────────────────

async function loadAll() {
    const [roadmapRes, sprintsRes, teamsRes, programmesRes, fyRes, usersRes] = await Promise.all([
        fetch(`/api/v1/roadmaps/${roadmapPk}/`),
        fetch('/api/v1/sprints/?page_size=200'),
        fetch('/api/v1/delivery-teams/?page_size=200'),
        fetch('/api/v1/programmes/?page_size=200'),
        fetch('/api/v1/fy/?page_size=50'),
        fetch('/api/v1/users/?page_size=200'),
    ]);

    _roadmap = await roadmapRes.json();
    const sprintData = await sprintsRes.json();
    _sprints = (sprintData.results || sprintData).sort((a, b) =>
        new Date(a.start_date) - new Date(b.start_date));
    const teamData = await teamsRes.json();
    _teams = teamData.results || teamData;
    const progData = await programmesRes.json();
    _programmes = progData.results || progData;
    const fyData = await fyRes.json();
    const fys = fyData.results || fyData;
    const userData = await usersRes.json();
    _users = (userData.results || userData).sort((a, b) =>
        (a.full_name || a.username || '').localeCompare(b.full_name || b.username || ''));

    document.getElementById('roadmap-title').textContent = _roadmap.name;
    document.getElementById('roadmap-desc').textContent = _roadmap.description || '';

    // Populate FY filter
    const fySelect = document.getElementById('rm-fy-filter');
    fys.forEach(fy => {
        const opt = document.createElement('option');
        opt.value = fy.id;
        opt.textContent = fy.label || fy.name || `FY ${fy.id}`;
        fySelect.appendChild(opt);
    });

    // Populate modal dropdowns
    populateSelect('item-team', _teams, t => t.name);
    populateSelect('item-programme', _programmes, p => p.name);
    populateSelect('item-start-sprint', _sprints, s => `${s.sprint_name} (${s.start_date})`);
    populateSelect('item-end-sprint', _sprints, s => `${s.sprint_name} (${s.end_date})`);
    populateSelect('ms-sprint', _sprints, s => `${s.sprint_name} (${s.start_date})`);
    populateSelect('task-assignee', _users, u => u.full_name || u.username || u.email);
    populateSelect('task-start-sprint', _sprints, s => `${s.sprint_name} (${s.start_date})`);
    populateSelect('task-end-sprint', _sprints, s => `${s.sprint_name} (${s.end_date})`);

    renderView();
}

function populateSelect(id, items, labelFn) {
    const sel = document.getElementById(id);
    if (!sel) return;
    const current = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.id;
        opt.textContent = labelFn(item);
        sel.appendChild(opt);
    });
    if (current) sel.value = current;
}

// ── View Dispatcher ──────────────────────────────────────────────────────────

function renderView() {
    const ganttControls = document.getElementById('rm-gantt-controls');
    const legend = document.getElementById('rm-legend');

    if (_viewMode === 'gantt') {
        ganttControls.classList.remove('d-none');
        legend.classList.remove('d-none');
        renderGantt();
    } else {
        ganttControls.classList.add('d-none');
        legend.classList.add('d-none');
        renderSummary(_viewMode);
    }
}

// ── Gantt Rendering ──────────────────────────────────────────────────────────

function getVisibleSprints() {
    if (!_fyFilter) return _sprints;
    return _sprints.filter(s => String(s.financial_year) === String(_fyFilter));
}

function renderGantt() {
    const gantt = document.getElementById('rm-gantt');
    const items = _roadmap.items || [];
    const sprints = getVisibleSprints();

    if (!sprints.length) {
        gantt.innerHTML = '<div class="text-secondary p-4">No sprints found for the selected period.</div>';
        return;
    }

    const grouped = groupItems(items, _groupBy);
    const COL_W = 80;
    const LABEL_W = 240;

    let html = `<table class="rm-gantt-table" style="min-width:${LABEL_W + sprints.length * COL_W}px">`;

    // Header
    html += `<thead><tr>
        <th class="rm-gantt-label-th" style="width:${LABEL_W}px;min-width:${LABEL_W}px">Item</th>`;
    sprints.forEach(s => {
        const isActive = s.is_active;
        html += `<th class="rm-gantt-sprint-th${isActive ? ' rm-gantt-sprint-active' : ''}"
                     style="width:${COL_W}px;min-width:${COL_W}px"
                     title="${s.start_date} → ${s.end_date}">
            <span class="rm-sprint-label">${esc(s.sprint_name)}</span>
        </th>`;
    });
    html += '</tr></thead><tbody>';

    grouped.forEach(({ groupLabel, items: groupItems }) => {
        if (_groupBy !== 'none' && groupLabel) {
            html += `<tr class="rm-gantt-group-row">
                <td colspan="${sprints.length + 1}" class="rm-gantt-group-label">${esc(groupLabel)}</td>
            </tr>`;
        }

        groupItems.forEach(item => {
            const startIdx = item.start_sprint ? sprints.findIndex(s => s.id === item.start_sprint) : -1;
            const endIdx = item.end_sprint ? sprints.findIndex(s => s.id === item.end_sprint) : startIdx;
            const color = item.color || typeColor(item.item_type);
            const taskCount = (item.tasks || []).length;
            const blockerCount = (item.tasks || []).filter(t => t.is_blocker && !t.is_complete).length;

            html += `<tr class="rm-gantt-row" data-item-id="${item.id}">
                <td class="rm-gantt-label-td">
                    <div class="rm-item-label" title="${esc(item.name)}">
                        <span class="rm-type-dot" style="background:${color}"></span>
                        <span class="rm-item-name">${esc(item.name)}</span>
                        ${blockerCount ? `<span class="badge bg-danger ms-1" style="font-size:9px" title="${blockerCount} blocker(s)">!</span>` : ''}
                        <div class="rm-item-actions ms-auto d-flex gap-1">
                            <button class="btn btn-ghost-icon rm-manage-tasks" data-id="${item.id}"
                                    style="width:20px;height:20px;font-size:11px" title="Tasks (${taskCount})">
                                <i class="bi bi-list-task"></i>
                            </button>
                            <button class="btn btn-ghost-icon rm-edit-item" data-id="${item.id}"
                                    style="width:20px;height:20px;font-size:11px" title="Edit item">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-ghost-icon rm-add-milestone" data-id="${item.id}"
                                    style="width:20px;height:20px;font-size:11px" title="Add gantt milestone">
                                <i class="bi bi-flag"></i>
                            </button>
                        </div>
                    </div>
                </td>`;

            sprints.forEach((s, idx) => {
                const inRange = startIdx >= 0 && idx >= startIdx && idx <= Math.max(startIdx, endIdx);
                const isStart = idx === startIdx;
                const isEnd = idx === Math.max(startIdx, endIdx);
                const milestone = item.milestones?.find(m => m.sprint === s.id);
                let cellContent = '';

                if (inRange) {
                    let barCls = 'rm-bar';
                    if (isStart) barCls += ' rm-bar-start';
                    if (isEnd) barCls += ' rm-bar-end';
                    cellContent += `<div class="${barCls}" style="background:${color}"></div>`;
                }
                if (milestone) {
                    const doneCls = milestone.is_complete ? ' rm-ms-done' : '';
                    cellContent += `<div class="rm-milestone${doneCls}" title="${esc(milestone.name)}"></div>`;
                }

                html += `<td class="rm-gantt-cell${inRange ? ' rm-cell-filled' : ''}">${cellContent}</td>`;
            });

            html += '</tr>';
        });
    });

    html += '</tbody></table>';
    gantt.innerHTML = html;

    gantt.querySelectorAll('.rm-edit-item').forEach(btn => {
        btn.addEventListener('click', e => { e.stopPropagation(); openEditModal(parseInt(btn.dataset.id)); });
    });
    gantt.querySelectorAll('.rm-add-milestone').forEach(btn => {
        btn.addEventListener('click', e => { e.stopPropagation(); openMilestoneModal(parseInt(btn.dataset.id)); });
    });
    gantt.querySelectorAll('.rm-manage-tasks').forEach(btn => {
        btn.addEventListener('click', e => { e.stopPropagation(); openTaskModal(parseInt(btn.dataset.id)); });
    });
}

function typeColor(type) {
    const map = { project: '#6366f1', milestone: '#f59e0b', placeholder: '#94a3b8' };
    return map[type] || '#6366f1';
}

function groupItems(items, groupBy) {
    if (groupBy === 'none') return [{ groupLabel: null, items }];

    const groups = new Map();
    items.forEach(item => {
        let key = '(Unassigned)';
        if (groupBy === 'team') key = item.assigned_team_name || '(No team)';
        else if (groupBy === 'programme') key = item.programme_name || '(No programme)';
        else if (groupBy === 'category') key = item.category || '(No category)';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(item);
    });

    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))
        .map(([groupLabel, items]) => ({ groupLabel, items }));
}

// ── Summary Views ─────────────────────────────────────────────────────────────

function renderSummary(mode) {
    const gantt = document.getElementById('rm-gantt');
    const items = _roadmap.items || [];
    const sprints = getVisibleSprints();

    if (mode === 'tasks') {
        renderTasksView(gantt, items);
    } else if (mode === 'projects') {
        renderProjectsGantt(gantt, items, sprints);
    } else if (mode === 'programme') {
        renderAggregateGantt(gantt, items, sprints, 'programme');
    } else if (mode === 'custom') {
        renderAggregateGantt(gantt, items, sprints, 'category');
    }
}

// Tasks view — flat table: project row + indented task sub-rows
function renderTasksView(container, items) {
    if (!items.length) {
        container.innerHTML = '<div class="text-secondary p-4">No items in this roadmap.</div>';
        return;
    }

    let html = `<table class="table table-sm mb-0" style="font-size:13px">
        <thead class="table-light">
            <tr>
                <th style="min-width:220px">Name</th>
                <th style="min-width:80px">Type</th>
                <th style="min-width:140px">Assignee</th>
                <th style="min-width:110px">Start Sprint</th>
                <th style="min-width:110px">End Sprint</th>
                <th style="min-width:80px">Jira</th>
                <th style="min-width:60px">Status</th>
                <th style="width:60px"></th>
            </tr>
        </thead><tbody>`;

    items.forEach(item => {
        const color = item.color || typeColor(item.item_type);
        const tasks = item.tasks || [];
        html += `<tr class="rm-tasks-item-row">
            <td colspan="7">
                <div class="d-flex align-items-center gap-2 fw-600" style="font-size:13px">
                    <span class="rm-type-dot" style="background:${color}"></span>
                    ${esc(item.name)}
                    ${item.programme_name ? `<span class="text-secondary" style="font-size:11px">· ${esc(item.programme_name)}</span>` : ''}
                </div>
            </td>
            <td>
                <button class="btn btn-ghost-icon rm-manage-tasks-summary" data-id="${item.id}"
                        style="font-size:11px;padding:2px 6px" title="Manage tasks">
                    <i class="bi bi-plus-lg"></i>
                </button>
            </td>
        </tr>`;

        if (!tasks.length) {
            html += `<tr class="rm-tasks-sub-row text-secondary">
                <td colspan="8" style="padding-left:36px;font-size:12px;font-style:italic">No tasks yet</td>
            </tr>`;
        }

        tasks.forEach(task => {
            const isMilestone = task.task_type === 'milestone';
            const blockerBadge = task.is_blocker && !task.is_complete
                ? `<span class="badge bg-danger ms-1" style="font-size:9px">BLOCKER</span>` : '';
            const completedCls = task.is_complete ? 'text-decoration-line-through text-secondary' : '';
            const jiraHtml = task.jira_id
                ? `<span class="badge bg-secondary bg-opacity-15 text-secondary" style="font-size:10px">${esc(task.jira_id)}</span>` : '—';

            html += `<tr class="rm-tasks-sub-row" data-task-id="${task.id}">
                <td style="padding-left:36px">
                    <span class="${completedCls}">
                        ${isMilestone ? '<i class="bi bi-diamond-fill text-warning me-1" style="font-size:10px"></i>' : '<i class="bi bi-check2-square text-secondary me-1" style="font-size:10px"></i>'}
                        ${esc(task.name)}
                    </span>
                    ${blockerBadge}
                </td>
                <td><span class="badge ${isMilestone ? 'bg-warning text-dark' : 'bg-secondary bg-opacity-20 text-secondary'}" style="font-size:10px">${esc(task.task_type_display)}</span></td>
                <td>${task.assignee_name ? `<span class="rp-avatar-chip">${esc(task.assignee_name)}</span>` : '<span class="text-secondary">—</span>'}</td>
                <td>${task.start_sprint_name ? esc(task.start_sprint_name) : '<span class="text-secondary">—</span>'}</td>
                <td>${task.end_sprint_name ? esc(task.end_sprint_name) : '<span class="text-secondary">—</span>'}</td>
                <td>${jiraHtml}</td>
                <td>${task.is_complete ? '<span class="text-success"><i class="bi bi-check-circle-fill"></i></span>' : '<span class="text-secondary">—</span>'}</td>
                <td>
                    <button class="btn btn-ghost-icon rm-edit-task" data-item-id="${item.id}" data-task-id="${task.id}"
                            style="font-size:11px;padding:2px 6px" title="Edit task">
                        <i class="bi bi-pencil"></i>
                    </button>
                </td>
            </tr>`;
        });
    });

    html += '</tbody></table>';
    container.innerHTML = html;

    container.querySelectorAll('.rm-manage-tasks-summary').forEach(btn => {
        btn.addEventListener('click', () => openTaskModal(parseInt(btn.dataset.id)));
    });
    container.querySelectorAll('.rm-edit-task').forEach(btn => {
        btn.addEventListener('click', () => openTaskModalEdit(parseInt(btn.dataset.itemId), parseInt(btn.dataset.taskId)));
    });
}

// Helper: compute task-based sprint range for an item
function itemTaskRange(item, sprints) {
    const tasks = item.tasks || [];
    if (!tasks.length) return { startIdx: -1, endIdx: -1, milestoneIdxs: [] };

    let minIdx = Infinity, maxIdx = -1;
    const milestoneIdxs = [];

    tasks.forEach(task => {
        const si = task.start_sprint ? sprints.findIndex(s => s.id === task.start_sprint) : -1;
        const ei = task.end_sprint ? sprints.findIndex(s => s.id === task.end_sprint) : si;
        if (si >= 0 && si < minIdx) minIdx = si;
        if (ei >= 0 && ei > maxIdx) maxIdx = ei;
        if (task.task_type === 'milestone') {
            const mi = task.end_sprint ? sprints.findIndex(s => s.id === task.end_sprint) : -1;
            if (mi >= 0) milestoneIdxs.push(mi);
        }
    });

    return {
        startIdx: minIdx === Infinity ? -1 : minIdx,
        endIdx: maxIdx,
        milestoneIdxs,
    };
}

// Projects gantt — one row per item, bar from task range
function renderProjectsGantt(container, items, sprints) {
    if (!sprints.length) {
        container.innerHTML = '<div class="text-secondary p-4">No sprints for selected period.</div>';
        return;
    }

    const COL_W = 80;
    const LABEL_W = 240;

    let html = `<table class="rm-gantt-table" style="min-width:${LABEL_W + sprints.length * COL_W}px">
        <thead><tr>
            <th class="rm-gantt-label-th" style="width:${LABEL_W}px;min-width:${LABEL_W}px">Project</th>`;
    sprints.forEach(s => {
        html += `<th class="rm-gantt-sprint-th${s.is_active ? ' rm-gantt-sprint-active' : ''}"
                     style="width:${COL_W}px;min-width:${COL_W}px" title="${s.start_date} → ${s.end_date}">
            <span class="rm-sprint-label">${esc(s.sprint_name)}</span></th>`;
    });
    html += '</tr></thead><tbody>';

    items.forEach(item => {
        const color = item.color || typeColor(item.item_type);
        const { startIdx, endIdx, milestoneIdxs } = itemTaskRange(item, sprints);
        const msSet = new Set(milestoneIdxs);
        const blockers = (item.tasks || []).filter(t => t.is_blocker && !t.is_complete).length;

        html += `<tr class="rm-gantt-row">
            <td class="rm-gantt-label-td">
                <div class="rm-item-label">
                    <span class="rm-type-dot" style="background:${color}"></span>
                    <span class="rm-item-name">${esc(item.name)}</span>
                    ${blockers ? `<span class="badge bg-danger ms-1" style="font-size:9px">!</span>` : ''}
                    <div class="rm-item-actions ms-auto">
                        <button class="btn btn-ghost-icon rm-manage-tasks" data-id="${item.id}"
                                style="width:20px;height:20px;font-size:11px">
                            <i class="bi bi-list-task"></i>
                        </button>
                    </div>
                </div>
            </td>`;

        sprints.forEach((s, idx) => {
            const inRange = startIdx >= 0 && idx >= startIdx && idx <= endIdx;
            const isStart = idx === startIdx;
            const isEnd = idx === endIdx;
            let cell = '';
            if (inRange) {
                let cls = 'rm-bar';
                if (isStart) cls += ' rm-bar-start';
                if (isEnd) cls += ' rm-bar-end';
                cell += `<div class="${cls}" style="background:${color}"></div>`;
            }
            if (msSet.has(idx)) {
                cell += `<div class="rm-milestone" title="Milestone"></div>`;
            }
            html += `<td class="rm-gantt-cell${inRange ? ' rm-cell-filled' : ''}">${cell}</td>`;
        });

        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;

    container.querySelectorAll('.rm-manage-tasks').forEach(btn => {
        btn.addEventListener('click', () => openTaskModal(parseInt(btn.dataset.id)));
    });
}

// Aggregate gantt — one row per group (programme or category)
function renderAggregateGantt(container, items, sprints, groupField) {
    if (!sprints.length) {
        container.innerHTML = '<div class="text-secondary p-4">No sprints for selected period.</div>';
        return;
    }

    const groups = new Map();
    items.forEach(item => {
        const key = groupField === 'programme'
            ? (item.programme_name || '(No programme)')
            : (item.category || '(No category)');
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(item);
    });

    const COL_W = 80;
    const LABEL_W = 240;

    let html = `<table class="rm-gantt-table" style="min-width:${LABEL_W + sprints.length * COL_W}px">
        <thead><tr>
            <th class="rm-gantt-label-th" style="width:${LABEL_W}px;min-width:${LABEL_W}px">
                ${groupField === 'programme' ? 'Programme' : 'Category'}
            </th>`;
    sprints.forEach(s => {
        html += `<th class="rm-gantt-sprint-th${s.is_active ? ' rm-gantt-sprint-active' : ''}"
                     style="width:${COL_W}px;min-width:${COL_W}px" title="${s.start_date} → ${s.end_date}">
            <span class="rm-sprint-label">${esc(s.sprint_name)}</span></th>`;
    });
    html += '</tr></thead><tbody>';

    [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0])).forEach(([groupKey, groupItems]) => {
        // Aggregate sprint range across all items' tasks
        let minIdx = Infinity, maxIdx = -1;
        const msSet = new Set();
        let totalBlockers = 0;
        let totalTasks = 0;

        groupItems.forEach(item => {
            const { startIdx, endIdx, milestoneIdxs } = itemTaskRange(item, sprints);
            if (startIdx >= 0 && startIdx < minIdx) minIdx = startIdx;
            if (endIdx > maxIdx) maxIdx = endIdx;
            milestoneIdxs.forEach(i => msSet.add(i));
            totalBlockers += (item.tasks || []).filter(t => t.is_blocker && !t.is_complete).length;
            totalTasks += (item.tasks || []).length;
        });

        const startIdx = minIdx === Infinity ? -1 : minIdx;
        const COLOR = '#6366f1';

        // Group header row
        html += `<tr class="rm-gantt-group-row">
            <td class="rm-gantt-group-label">
                ${esc(groupKey)}
                <span class="text-secondary ms-2" style="font-size:11px;font-weight:400">${groupItems.length} project(s), ${totalTasks} task(s)</span>
                ${totalBlockers ? `<span class="badge bg-danger ms-2" style="font-size:9px">${totalBlockers} blocker(s)</span>` : ''}
            </td>
            ${sprints.map((s, idx) => {
                const inRange = startIdx >= 0 && idx >= startIdx && idx <= maxIdx;
                const isStart = idx === startIdx;
                const isEnd = idx === maxIdx;
                let cell = '';
                if (inRange) {
                    let cls = 'rm-bar';
                    if (isStart) cls += ' rm-bar-start';
                    if (isEnd) cls += ' rm-bar-end';
                    cell += `<div class="${cls}" style="background:${COLOR};opacity:0.6"></div>`;
                }
                if (msSet.has(idx)) cell += `<div class="rm-milestone" title="Milestone"></div>`;
                return `<td class="rm-gantt-cell${inRange ? ' rm-cell-filled' : ''}">${cell}</td>`;
            }).join('')}
        </tr>`;

        // Sub-rows per project
        groupItems.forEach(item => {
            const color = item.color || typeColor(item.item_type);
            const { startIdx: si, endIdx: ei, milestoneIdxs } = itemTaskRange(item, sprints);
            const itemMsSet = new Set(milestoneIdxs);

            html += `<tr class="rm-gantt-row" style="opacity:0.85">
                <td class="rm-gantt-label-td" style="padding-left:28px">
                    <div class="rm-item-label">
                        <span class="rm-type-dot" style="background:${color};width:8px;height:8px"></span>
                        <span class="rm-item-name" style="font-size:12px">${esc(item.name)}</span>
                        <div class="rm-item-actions ms-auto">
                            <button class="btn btn-ghost-icon rm-manage-tasks" data-id="${item.id}"
                                    style="width:18px;height:18px;font-size:10px">
                                <i class="bi bi-list-task"></i>
                            </button>
                        </div>
                    </div>
                </td>`;

            sprints.forEach((s, idx) => {
                const inRange = si >= 0 && idx >= si && idx <= ei;
                const isStart = idx === si;
                const isEnd = idx === ei;
                let cell = '';
                if (inRange) {
                    let cls = 'rm-bar';
                    if (isStart) cls += ' rm-bar-start';
                    if (isEnd) cls += ' rm-bar-end';
                    cell += `<div class="${cls}" style="background:${color};height:6px;margin-top:5px"></div>`;
                }
                if (itemMsSet.has(idx)) cell += `<div class="rm-milestone" style="width:8px;height:8px" title="Milestone"></div>`;
                html += `<td class="rm-gantt-cell${inRange ? ' rm-cell-filled' : ''}">${cell}</td>`;
            });

            html += '</tr>';
        });
    });

    html += '</tbody></table>';
    container.innerHTML = html;

    container.querySelectorAll('.rm-manage-tasks').forEach(btn => {
        btn.addEventListener('click', () => openTaskModal(parseInt(btn.dataset.id)));
    });
}

// ── Item Modal ────────────────────────────────────────────────────────────────

function openAddModal() {
    _editingItemId = null;
    document.getElementById('item-modal-title').textContent = 'Add Item';
    document.getElementById('item-type').value = 'project';
    document.getElementById('item-name').value = '';
    document.getElementById('item-team').value = '';
    document.getElementById('item-programme').value = '';
    document.getElementById('item-start-sprint').value = '';
    document.getElementById('item-end-sprint').value = '';
    document.getElementById('item-category').value = '';
    document.getElementById('item-color').value = '#6366f1';
    document.getElementById('item-notes').value = '';
    document.getElementById('item-error').classList.add('d-none');
    document.getElementById('item-delete-btn').classList.add('d-none');
    new bootstrap.Modal(document.getElementById('item-modal')).show();
}

function openEditModal(itemId) {
    _editingItemId = itemId;
    const item = _roadmap.items.find(i => i.id === itemId);
    if (!item) return;
    document.getElementById('item-modal-title').textContent = 'Edit Item';
    document.getElementById('item-type').value = item.item_type;
    document.getElementById('item-name').value = item.name;
    document.getElementById('item-team').value = item.assigned_team || '';
    document.getElementById('item-programme').value = item.programme || '';
    document.getElementById('item-start-sprint').value = item.start_sprint || '';
    document.getElementById('item-end-sprint').value = item.end_sprint || '';
    document.getElementById('item-category').value = item.category || '';
    document.getElementById('item-color').value = item.color || '#6366f1';
    document.getElementById('item-notes').value = item.notes || '';
    document.getElementById('item-error').classList.add('d-none');
    document.getElementById('item-delete-btn').classList.remove('d-none');
    new bootstrap.Modal(document.getElementById('item-modal')).show();
}

async function saveItem() {
    const name = document.getElementById('item-name').value.trim();
    const errEl = document.getElementById('item-error');
    if (!name) { errEl.textContent = 'Name is required.'; errEl.classList.remove('d-none'); return; }
    errEl.classList.add('d-none');

    const payload = {
        roadmap: parseInt(roadmapPk),
        item_type: document.getElementById('item-type').value,
        name,
        assigned_team: document.getElementById('item-team').value || null,
        programme: document.getElementById('item-programme').value || null,
        start_sprint: document.getElementById('item-start-sprint').value || null,
        end_sprint: document.getElementById('item-end-sprint').value || null,
        category: document.getElementById('item-category').value,
        color: document.getElementById('item-color').value,
        notes: document.getElementById('item-notes').value,
    };

    const url = _editingItemId ? `/api/v1/roadmap-items/${_editingItemId}/` : '/api/v1/roadmap-items/';
    const method = _editingItemId ? 'PATCH' : 'POST';

    const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify(payload),
    });
    if (res.ok) {
        bootstrap.Modal.getInstance(document.getElementById('item-modal'))?.hide();
        await reload();
    } else {
        const data = await res.json().catch(() => ({}));
        errEl.textContent = data.name?.[0] || data.error || 'Failed to save.';
        errEl.classList.remove('d-none');
    }
}

async function deleteItem() {
    if (!_editingItemId) return;
    if (!confirm('Delete this item and all its tasks?')) return;
    const res = await fetch(`/api/v1/roadmap-items/${_editingItemId}/`, {
        method: 'DELETE', headers: { 'X-CSRFToken': getCsrf() },
    });
    if (res.ok) {
        bootstrap.Modal.getInstance(document.getElementById('item-modal'))?.hide();
        await reload();
    }
}

// ── Task Modal ────────────────────────────────────────────────────────────────

function openTaskModal(itemId) {
    _taskItemId = itemId;
    _editingTaskId = null;
    const item = _roadmap.items.find(i => i.id === itemId);
    document.getElementById('task-modal-title').textContent = `Tasks — ${item?.name || ''}`;
    document.getElementById('task-form-wrap').classList.add('d-none');
    renderTaskList(item?.tasks || []);
    new bootstrap.Modal(document.getElementById('task-modal')).show();
}

function openTaskModalEdit(itemId, taskId) {
    openTaskModal(itemId);
    setTimeout(() => editTask(taskId), 100);
}

function renderTaskList(tasks) {
    const wrap = document.getElementById('task-list-wrap');
    if (!tasks.length) {
        wrap.innerHTML = '<p class="text-secondary small">No tasks yet. Add one below.</p>';
        return;
    }

    wrap.innerHTML = `<table class="table table-sm" style="font-size:13px">
        <thead class="table-light">
            <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Assignee</th>
                <th>Sprints</th>
                <th>Jira</th>
                <th style="width:80px"></th>
            </tr>
        </thead><tbody>
        ${tasks.map(t => {
            const blockerBadge = t.is_blocker && !t.is_complete
                ? `<span class="badge bg-danger ms-1" style="font-size:9px">BLOCKER</span>` : '';
            const doneCls = t.is_complete ? 'text-decoration-line-through text-secondary' : '';
            return `<tr>
                <td><span class="${doneCls}">${esc(t.name)}</span>${blockerBadge}</td>
                <td><span class="badge ${t.task_type === 'milestone' ? 'bg-warning text-dark' : 'bg-secondary bg-opacity-20 text-secondary'}" style="font-size:10px">${esc(t.task_type_display)}</span></td>
                <td>${t.assignee_name ? esc(t.assignee_name) : '—'}</td>
                <td style="font-size:11px">${t.start_sprint_name ? esc(t.start_sprint_name) : '—'} ${t.end_sprint_name && t.end_sprint !== t.start_sprint ? '→ ' + esc(t.end_sprint_name) : ''}</td>
                <td>${t.jira_id ? `<span class="badge bg-secondary bg-opacity-15 text-secondary" style="font-size:10px">${esc(t.jira_id)}</span>` : '—'}</td>
                <td>
                    ${t.is_complete ? '<i class="bi bi-check-circle-fill text-success me-1"></i>' : ''}
                    <button class="btn btn-ghost-icon rm-task-edit-btn" data-task-id="${t.id}"
                            style="font-size:11px;padding:2px 6px"><i class="bi bi-pencil"></i></button>
                </td>
            </tr>`;
        }).join('')}
        </tbody></table>`;

    wrap.querySelectorAll('.rm-task-edit-btn').forEach(btn => {
        btn.addEventListener('click', () => editTask(parseInt(btn.dataset.taskId)));
    });
}

function showTaskForm(task = null) {
    _editingTaskId = task ? task.id : null;
    document.getElementById('task-type').value = task?.task_type || 'task';
    document.getElementById('task-name').value = task?.name || '';
    document.getElementById('task-assignee').value = task?.assignee || '';
    document.getElementById('task-jira-id').value = task?.jira_id || '';
    document.getElementById('task-start-sprint').value = task?.start_sprint || '';
    document.getElementById('task-end-sprint').value = task?.end_sprint || '';
    document.getElementById('task-is-blocker').checked = task?.is_blocker || false;
    document.getElementById('task-is-complete').checked = task?.is_complete || false;
    document.getElementById('task-notes').value = task?.notes || '';
    document.getElementById('task-error').classList.add('d-none');
    const delBtn = document.getElementById('task-delete-btn');
    if (task) delBtn.classList.remove('d-none'); else delBtn.classList.add('d-none');
    document.getElementById('task-form-wrap').classList.remove('d-none');
    document.getElementById('task-name').focus();
}

function editTask(taskId) {
    const item = _roadmap.items.find(i => i.id === _taskItemId);
    const task = item?.tasks?.find(t => t.id === taskId);
    if (task) showTaskForm(task);
}

async function saveTask() {
    const name = document.getElementById('task-name').value.trim();
    const errEl = document.getElementById('task-error');
    if (!name) { errEl.textContent = 'Name is required.'; errEl.classList.remove('d-none'); return; }
    errEl.classList.add('d-none');

    const payload = {
        roadmap_item: _taskItemId,
        task_type: document.getElementById('task-type').value,
        name,
        assignee: document.getElementById('task-assignee').value || null,
        jira_id: document.getElementById('task-jira-id').value.trim(),
        start_sprint: document.getElementById('task-start-sprint').value || null,
        end_sprint: document.getElementById('task-end-sprint').value || null,
        is_blocker: document.getElementById('task-is-blocker').checked,
        is_complete: document.getElementById('task-is-complete').checked,
        notes: document.getElementById('task-notes').value,
    };

    const url = _editingTaskId ? `/api/v1/roadmap-tasks/${_editingTaskId}/` : '/api/v1/roadmap-tasks/';
    const method = _editingTaskId ? 'PATCH' : 'POST';

    const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify(payload),
    });

    if (res.ok) {
        document.getElementById('task-form-wrap').classList.add('d-none');
        await reload();
        // Re-render task list in modal
        const item = _roadmap.items.find(i => i.id === _taskItemId);
        renderTaskList(item?.tasks || []);
    } else {
        errEl.textContent = 'Failed to save task.';
        errEl.classList.remove('d-none');
    }
}

async function deleteTask() {
    if (!_editingTaskId) return;
    if (!confirm('Delete this task?')) return;
    const res = await fetch(`/api/v1/roadmap-tasks/${_editingTaskId}/`, {
        method: 'DELETE', headers: { 'X-CSRFToken': getCsrf() },
    });
    if (res.ok) {
        document.getElementById('task-form-wrap').classList.add('d-none');
        _editingTaskId = null;
        await reload();
        const item = _roadmap.items.find(i => i.id === _taskItemId);
        renderTaskList(item?.tasks || []);
    }
}

// ── Milestone Modal ───────────────────────────────────────────────────────────

function openMilestoneModal(itemId) {
    _milestoneItemId = itemId;
    document.getElementById('ms-name').value = '';
    document.getElementById('ms-sprint').value = '';
    document.getElementById('ms-error').classList.add('d-none');
    new bootstrap.Modal(document.getElementById('milestone-modal')).show();
}

async function saveMilestone() {
    const name = document.getElementById('ms-name').value.trim();
    const errEl = document.getElementById('ms-error');
    if (!name) { errEl.textContent = 'Name is required.'; errEl.classList.remove('d-none'); return; }
    errEl.classList.add('d-none');

    const res = await fetch('/api/v1/roadmap-milestones/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({
            roadmap_item: _milestoneItemId,
            name,
            sprint: document.getElementById('ms-sprint').value || null,
        }),
    });
    if (res.ok) {
        bootstrap.Modal.getInstance(document.getElementById('milestone-modal'))?.hide();
        await reload();
    } else {
        errEl.textContent = 'Failed to add milestone.';
        errEl.classList.remove('d-none');
    }
}

// ── Import Projects ───────────────────────────────────────────────────────────

async function openImportModal() {
    _selectedImport.clear();
    document.getElementById('import-count').textContent = '0';
    document.getElementById('import-search').value = '';
    document.getElementById('import-error').classList.add('d-none');
    new bootstrap.Modal(document.getElementById('import-modal')).show();

    const listEl = document.getElementById('import-project-list');
    listEl.innerHTML = '<div class="text-secondary small py-2">Loading…</div>';

    const res = await fetch('/api/v1/roadmaps/import-projects/');
    if (!res.ok) { listEl.innerHTML = '<div class="text-danger">Failed to load projects.</div>'; return; }
    const data = await res.json();
    const projects = data.results || [];

    const existingProjectIds = new Set(
        (_roadmap.items || []).filter(i => i.project).map(i => i.project)
    );

    renderImportList(projects.filter(p => !existingProjectIds.has(p.id)));

    document.getElementById('import-search').addEventListener('input', e => {
        const q = e.target.value.toLowerCase();
        const filtered = projects.filter(p =>
            !existingProjectIds.has(p.id) &&
            (p.name.toLowerCase().includes(q) || (p.programme_name || '').toLowerCase().includes(q))
        );
        renderImportList(filtered);
    });
}

function renderImportList(projects) {
    const listEl = document.getElementById('import-project-list');
    if (!projects.length) {
        listEl.innerHTML = '<div class="text-secondary small py-2">No projects found.</div>';
        return;
    }
    listEl.innerHTML = projects.map(p => `
        <label class="d-flex align-items-center gap-2 py-2 border-bottom import-project-row"
               style="cursor:pointer;font-size:13px">
            <input type="checkbox" class="form-check-input" value="${p.id}"
                   ${_selectedImport.has(p.id) ? 'checked' : ''}>
            <span class="fw-500">${esc(p.name)}</span>
            ${p.programme_name ? `<span class="text-secondary ms-1">${esc(p.programme_name)}</span>` : ''}
            <span class="badge bg-secondary bg-opacity-25 text-secondary ms-auto" style="font-size:10px">
                ${esc(p.status_display || p.status)}
            </span>
        </label>`).join('');

    listEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
        cb.addEventListener('change', () => {
            if (cb.checked) _selectedImport.add(parseInt(cb.value));
            else _selectedImport.delete(parseInt(cb.value));
            document.getElementById('import-count').textContent = _selectedImport.size;
        });
    });
}

async function confirmImport() {
    if (!_selectedImport.size) return;
    const errEl = document.getElementById('import-error');
    errEl.classList.add('d-none');

    const res = await fetch('/api/v1/roadmaps/import-projects/');
    const data = await res.json();
    const projects = (data.results || []).filter(p => _selectedImport.has(p.id));

    const existingOrder = (_roadmap.items || []).length;
    let order = existingOrder;

    for (const p of projects) {
        await fetch('/api/v1/roadmap-items/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({
                roadmap: parseInt(roadmapPk),
                item_type: 'project',
                name: p.name,
                project: p.id,
                programme: p.programme || null,
                assigned_team: p.assigned_team || null,
                color: '#6366f1',
                display_order: order++,
            }),
        });
    }

    bootstrap.Modal.getInstance(document.getElementById('import-modal'))?.hide();
    await reload();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function reload() {
    const res = await fetch(`/api/v1/roadmaps/${roadmapPk}/`);
    _roadmap = await res.json();
    renderView();
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    if (!roadmapPk) return;

    loadAll();

    // View toggle
    document.getElementById('rm-view-toggle')?.querySelectorAll('[data-view]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#rm-view-toggle [data-view]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _viewMode = btn.dataset.view;
            renderView();
        });
    });

    document.getElementById('add-item-btn')?.addEventListener('click', openAddModal);
    document.getElementById('item-save-btn')?.addEventListener('click', saveItem);
    document.getElementById('item-delete-btn')?.addEventListener('click', deleteItem);
    document.getElementById('ms-save-btn')?.addEventListener('click', saveMilestone);
    document.getElementById('import-projects-btn')?.addEventListener('click', openImportModal);
    document.getElementById('import-confirm-btn')?.addEventListener('click', confirmImport);

    // Task modal
    document.getElementById('task-add-new-btn')?.addEventListener('click', () => showTaskForm());
    document.getElementById('task-save-btn')?.addEventListener('click', saveTask);
    document.getElementById('task-delete-btn')?.addEventListener('click', deleteTask);
    document.getElementById('task-cancel-btn')?.addEventListener('click', () => {
        document.getElementById('task-form-wrap').classList.add('d-none');
    });

    document.getElementById('rm-group-by')?.addEventListener('change', e => {
        _groupBy = e.target.value;
        renderView();
    });

    document.getElementById('rm-fy-filter')?.addEventListener('change', e => {
        _fyFilter = e.target.value;
        renderView();
    });
});
