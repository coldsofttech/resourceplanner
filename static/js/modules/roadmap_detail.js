/* Roadmap detail — Gantt chart view */

const roadmapPk = document.getElementById('roadmap-pk')?.value;
let _roadmap = null;
let _sprints = [];
let _teams = [];
let _programmes = [];
let _editingItemId = null;
let _milestoneItemId = null;
let _selectedImport = new Set();
let _groupBy = 'none';
let _fyFilter = '';

function getCsrf() {
    return document.cookie.split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}
function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Data Loading ─────────────────────────────────────────────────────────────

async function loadAll() {
    const [roadmapRes, sprintsRes, teamsRes, programmesRes, fyRes] = await Promise.all([
        fetch(`/api/v1/roadmaps/${roadmapPk}/`),
        fetch('/api/v1/sprints/?page_size=200'),
        fetch('/api/v1/delivery-teams/?page_size=200'),
        fetch('/api/v1/programmes/?page_size=200'),
        fetch('/api/v1/fy/?page_size=50'),
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

    renderGantt();
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
    const COL_W = 80;   // px per sprint column
    const ROW_H = 44;   // px per item row
    const LABEL_W = 220; // px for label column

    let html = `<table class="rm-gantt-table" style="min-width:${LABEL_W + sprints.length * COL_W}px">`;

    // Header row — sprint names
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

            html += `<tr class="rm-gantt-row" data-item-id="${item.id}">
                <td class="rm-gantt-label-td">
                    <div class="rm-item-label" title="${esc(item.name)}">
                        <span class="rm-type-dot" style="background:${color}"></span>
                        <span class="rm-item-name">${esc(item.name)}</span>
                        <div class="rm-item-actions ms-auto d-flex gap-1">
                            <button class="btn btn-ghost-icon rm-edit-item" data-id="${item.id}"
                                    style="width:20px;height:20px;font-size:11px" title="Edit">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-ghost-icon rm-add-milestone" data-id="${item.id}"
                                    style="width:20px;height:20px;font-size:11px" title="Add milestone">
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

    // Bind edit / milestone buttons
    gantt.querySelectorAll('.rm-edit-item').forEach(btn => {
        btn.addEventListener('click', e => { e.stopPropagation(); openEditModal(parseInt(btn.dataset.id)); });
    });
    gantt.querySelectorAll('.rm-add-milestone').forEach(btn => {
        btn.addEventListener('click', e => { e.stopPropagation(); openMilestoneModal(parseInt(btn.dataset.id)); });
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
    if (!confirm('Delete this item?')) return;
    const res = await fetch(`/api/v1/roadmap-items/${_editingItemId}/`, {
        method: 'DELETE', headers: { 'X-CSRFToken': getCsrf() },
    });
    if (res.ok) {
        bootstrap.Modal.getInstance(document.getElementById('item-modal'))?.hide();
        await reload();
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

    // Filter out already-imported projects
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
    renderGantt();
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    if (!roadmapPk) return;

    loadAll();

    document.getElementById('add-item-btn')?.addEventListener('click', openAddModal);
    document.getElementById('item-save-btn')?.addEventListener('click', saveItem);
    document.getElementById('item-delete-btn')?.addEventListener('click', deleteItem);
    document.getElementById('ms-save-btn')?.addEventListener('click', saveMilestone);
    document.getElementById('import-projects-btn')?.addEventListener('click', openImportModal);
    document.getElementById('import-confirm-btn')?.addEventListener('click', confirmImport);

    document.getElementById('rm-group-by')?.addEventListener('change', e => {
        _groupBy = e.target.value;
        renderGantt();
    });

    document.getElementById('rm-fy-filter')?.addEventListener('change', e => {
        _fyFilter = e.target.value;
        renderGantt();
    });
});
