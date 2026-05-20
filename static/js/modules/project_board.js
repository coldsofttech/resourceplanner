/**
 * Project Board View — Kanban columns by status.
 * Requires SortableJS (loaded via CDN in the template).
 * Card field settings loaded from /api/v1/configurations/?module=board_cards
 */

const VIEW_STORAGE_KEY = 'rp_proj_view';
const COL_COLLAPSE_KEY = 'rp_board_collapsed';

const STATUS_COLUMNS = [
    { key: 'NEW',         label: 'New',         icon: 'bi-circle',             bg: '#f0f9ff', border: '#bae6fd', accent: '#0ea5e9' },
    { key: 'IN_PROGRESS', label: 'In Progress',  icon: 'bi-arrow-right-circle', bg: '#f5f3ff', border: '#ddd6fe', accent: '#7c3aed' },
    { key: 'ON_HOLD',     label: 'On Hold',      icon: 'bi-pause-circle',       bg: '#fffbeb', border: '#fde68a', accent: '#d97706' },
    { key: 'COMPLETED',   label: 'Completed',    icon: 'bi-check-circle',       bg: '#f0fdf4', border: '#bbf7d0', accent: '#16a34a' },
    { key: 'CANCELLED',   label: 'Cancelled',    icon: 'bi-x-circle',           bg: '#fef2f2', border: '#fecaca', accent: '#dc2626' },
];

// All possible card fields — order respected for display
const ALL_CARD_FIELDS = [
    { key: 'show_programme',  label: 'Programme',   icon: 'bi-collection',    code: 'BOARD_CARD_SHOW_PROGRAMME' },
    { key: 'show_team',       label: 'Team',         icon: 'bi-people',        code: 'BOARD_CARD_SHOW_TEAM' },
    { key: 'show_priority',   label: 'Priority',     icon: 'bi-flag',          code: 'BOARD_CARD_SHOW_PRIORITY' },
    { key: 'show_type',       label: 'Type',         icon: 'bi-tag',           code: 'BOARD_CARD_SHOW_TYPE' },
    { key: 'show_tags',       label: 'Tags',         icon: 'bi-hash',          code: 'BOARD_CARD_SHOW_TAGS' },
    { key: 'show_code',       label: 'Code',         icon: 'bi-upc',           code: 'BOARD_CARD_SHOW_CODE' },
    { key: 'show_substatus',  label: 'Sub-status',   icon: 'bi-layers',        code: 'BOARD_CARD_SHOW_SUBSTATUS' },
    { key: 'show_confidence', label: 'Confidence',   icon: 'bi-speedometer2',  code: 'BOARD_CARD_SHOW_CONFIDENCE' },
    { key: 'show_dates',      label: 'Dates',        icon: 'bi-calendar3',     code: 'BOARD_CARD_SHOW_DATES' },
];

const PRIORITY_COLORS = {
    LOW: '#94a3b8', MEDIUM: '#f59e0b', HIGH: '#ef4444', VERY_HIGH: '#7c3aed'
};

let _cardConfig = {};
let _fieldOrder = ALL_CARD_FIELDS.map(f => f.key);
let _allProjects = [];
let _currentView = localStorage.getItem(VIEW_STORAGE_KEY) || 'table';
let _collapsed = {};

// Load collapsed state from localStorage
try { _collapsed = JSON.parse(localStorage.getItem(COL_COLLAPSE_KEY) || '{}'); } catch { _collapsed = {}; }

function getCsrf() {
    return document.cookie.split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}
function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Card config loading ───────────────────────────────────────────────────────

export async function loadCardConfig() {
    // Defaults — all on
    ALL_CARD_FIELDS.forEach(f => { _cardConfig[f.key] = true; });
    try {
        const res = await fetch('/api/v1/configurations/?module=board_cards&page_size=50');
        if (!res.ok) return;
        const data = await res.json();
        const configs = data.results || data;
        configs.forEach(c => {
            // BOARD_CARD_SHOW_TEAM -> show_team
            const key = c.code.toLowerCase().replace('board_card_', '');
            if (key in _cardConfig) {
                _cardConfig[key] = !(c.value === 'false' || c.value === '0');
            }
            // field order stored as BOARD_CARD_FIELD_ORDER = "show_team,show_priority,..."
            if (c.code === 'BOARD_CARD_FIELD_ORDER' && c.value) {
                const order = c.value.split(',').map(s => s.trim()).filter(Boolean);
                if (order.length) _fieldOrder = order;
            }
        });
    } catch { /* use defaults */ }
}

// ── Card rendering ────────────────────────────────────────────────────────────

export function buildCard(project) {
    const priorityColor = PRIORITY_COLORS[project.priority] || '#94a3b8';
    const lines = [];

    _fieldOrder.forEach(key => {
        if (!_cardConfig[key]) return;
        switch (key) {
            case 'show_code':
                if (project.code) lines.push(`<div class="rp-board-card-meta"><i class="bi bi-upc me-1"></i>${esc(project.code)}</div>`);
                break;
            case 'show_type':
                if (project.project_type_name) lines.push(`<div class="rp-board-card-meta"><i class="bi bi-tag me-1"></i>${esc(project.project_type_name)}</div>`);
                break;
            case 'show_programme':
                if (project.programme_name) lines.push(`<div class="rp-board-card-meta"><i class="bi bi-collection me-1"></i>${esc(project.programme_name)}</div>`);
                break;
            case 'show_team':
                if (project.assigned_team_name) lines.push(`<div class="rp-board-card-meta"><i class="bi bi-people me-1"></i>${esc(project.assigned_team_name)}</div>`);
                break;
            case 'show_substatus':
                if (project.sub_status_name) lines.push(`<div class="rp-board-card-meta"><i class="bi bi-layers me-1"></i>${esc(project.sub_status_name)}</div>`);
                break;
            case 'show_confidence':
                if (project.confidence_display) lines.push(`<div class="rp-board-card-meta"><i class="bi bi-speedometer2 me-1"></i>${esc(project.confidence_display)}</div>`);
                break;
            case 'show_dates':
                if (project.tentative_start_date || project.tentative_end_date) {
                    const from = project.tentative_start_date ? fmtDate(project.tentative_start_date) : '?';
                    const to   = project.tentative_end_date   ? fmtDate(project.tentative_end_date)   : '?';
                    lines.push(`<div class="rp-board-card-meta"><i class="bi bi-calendar3 me-1"></i>${from} → ${to}</div>`);
                }
                break;
            case 'show_tags':
                if (project.tags?.length) {
                    const tags = project.tags.slice(0, 3)
                        .map(t => `<span class="rp-board-tag">${esc(t.name || t)}</span>`).join('');
                    lines.push(`<div class="rp-board-card-tags">${tags}</div>`);
                }
                break;
            case 'show_priority':
                if (project.priority_display) {
                    lines.push(`<div class="rp-board-card-footer">
                        <span class="rp-board-priority-badge" style="background:${priorityColor}22;color:${priorityColor}">
                            ${esc(project.priority_display)}
                        </span>
                    </div>`);
                }
                break;
        }
    });

    return `
        <div class="rp-board-card" data-id="${project.id}" data-status="${project.status}">
            <div class="rp-board-card-priority-bar" style="background:${priorityColor}"></div>
            <div class="rp-board-card-body">
                <div class="rp-board-card-name">
                    <a href="/projects/${project.id}/" class="text-decoration-none">${esc(project.name)}</a>
                </div>
                ${lines.join('')}
            </div>
        </div>`;
}

function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

// ── Board rendering ───────────────────────────────────────────────────────────

export function renderBoard(searchQuery = '') {
    const boardEl = document.getElementById('proj-board');
    if (!boardEl) return;

    const inner = boardEl.querySelector('.rp-board-columns');
    if (!inner) return;

    const q = searchQuery.toLowerCase();
    const projects = _allProjects.filter(p =>
        !q || p.name.toLowerCase().includes(q) ||
        (p.programme_name || '').toLowerCase().includes(q) ||
        (p.code || '').toLowerCase().includes(q)
    );

    STATUS_COLUMNS.forEach(col => {
        const colEl = document.getElementById(`board-col-${col.key}`);
        const countEl = document.getElementById(`board-count-${col.key}`);
        const bodyEl = document.getElementById(`board-body-${col.key}`);
        if (!colEl) return;

        const colProjects = projects.filter(p => p.status === col.key);
        if (countEl) countEl.textContent = colProjects.length;

        if (!bodyEl) return;
        if (!colProjects.length) {
            bodyEl.innerHTML = `<div class="rp-board-empty">No projects</div>`;
        } else {
            bodyEl.innerHTML = colProjects.map(p => buildCard(p)).join('');
        }

        // Init / reinit SortableJS on this column
        if (typeof Sortable !== 'undefined') {
            if (bodyEl._sortable) bodyEl._sortable.destroy();
            bodyEl._sortable = new Sortable(bodyEl, {
                group: 'board',
                animation: 150,
                ghostClass: 'rp-board-ghost',
                chosenClass: 'rp-board-chosen',
                dragClass: 'rp-board-dragging',
                onEnd(evt) {
                    const cardEl = evt.item;
                    const newStatus = evt.to.closest('[data-status-col]')?.dataset.statusCol;
                    const projectId = cardEl.dataset.id;
                    if (newStatus && newStatus !== cardEl.dataset.status) {
                        patchProjectStatus(projectId, newStatus);
                        cardEl.dataset.status = newStatus;
                        // Update count badges
                        const fromCol = STATUS_COLUMNS.find(c => c.key === evt.from.closest('[data-status-col]')?.dataset.statusCol);
                        const toCol   = STATUS_COLUMNS.find(c => c.key === newStatus);
                        updateCountBadge(fromCol?.key);
                        updateCountBadge(toCol?.key);
                        // Update in-memory list
                        const proj = _allProjects.find(p => String(p.id) === String(projectId));
                        if (proj) proj.status = newStatus;
                    }
                },
            });
        }
    });
}

function updateCountBadge(statusKey) {
    if (!statusKey) return;
    const bodyEl = document.getElementById(`board-body-${statusKey}`);
    const countEl = document.getElementById(`board-count-${statusKey}`);
    if (bodyEl && countEl) countEl.textContent = bodyEl.querySelectorAll('.rp-board-card').length;
}

async function patchProjectStatus(projectId, newStatus) {
    try {
        await fetch(`/api/v1/projects/${projectId}/`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ status: newStatus }),
        });
    } catch { /* status update best-effort */ }
}

// ── Board scaffold ────────────────────────────────────────────────────────────

function buildBoardScaffold() {
    const boardEl = document.getElementById('proj-board');
    if (!boardEl) return;

    let colsWrap = boardEl.querySelector('.rp-board-columns');
    if (!colsWrap) {
        colsWrap = document.createElement('div');
        colsWrap.className = 'rp-board-columns';
        boardEl.appendChild(colsWrap);
    }

    colsWrap.innerHTML = STATUS_COLUMNS.map(col => {
        const isCollapsed = !!_collapsed[col.key];
        return `
        <div class="rp-board-col${isCollapsed ? ' rp-board-col--collapsed' : ''}"
             id="board-col-${col.key}"
             data-status-col="${col.key}"
             style="--col-bg:${col.bg};--col-border:${col.border};--col-accent:${col.accent}">
            <div class="rp-board-col-header" data-col="${col.key}">
                <i class="bi ${col.icon} rp-board-col-icon"></i>
                <span class="rp-board-col-label">${col.label}</span>
                <span class="badge rp-board-col-count ms-2" id="board-count-${col.key}">0</span>
                <button class="rp-board-col-toggle ms-auto" title="${isCollapsed ? 'Expand' : 'Collapse'}" data-col="${col.key}">
                    <i class="bi ${isCollapsed ? 'bi-chevron-right' : 'bi-chevron-left'}"></i>
                </button>
            </div>
            <div class="rp-board-col-body" id="board-body-${col.key}">
                <div class="rp-board-empty">Loading…</div>
            </div>
        </div>`;
    }).join('');

    // Collapse toggle handlers
    colsWrap.querySelectorAll('.rp-board-col-toggle').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            toggleColumn(btn.dataset.col);
        });
    });

    // Click on collapsed header expands
    colsWrap.querySelectorAll('.rp-board-col-header').forEach(hdr => {
        hdr.addEventListener('click', () => {
            const colEl = document.getElementById(`board-col-${hdr.dataset.col}`);
            if (colEl?.classList.contains('rp-board-col--collapsed')) {
                toggleColumn(hdr.dataset.col);
            }
        });
    });
}

function toggleColumn(statusKey) {
    const colEl = document.getElementById(`board-col-${statusKey}`);
    const btn = colEl?.querySelector('.rp-board-col-toggle');
    const icon = btn?.querySelector('i');
    if (!colEl) return;

    const isNowCollapsed = !colEl.classList.contains('rp-board-col--collapsed');
    colEl.classList.toggle('rp-board-col--collapsed', isNowCollapsed);
    _collapsed[statusKey] = isNowCollapsed;
    localStorage.setItem(COL_COLLAPSE_KEY, JSON.stringify(_collapsed));

    if (btn) btn.title = isNowCollapsed ? 'Expand' : 'Collapse';
    if (icon) {
        icon.className = isNowCollapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
    }
}

// ── View toggle ───────────────────────────────────────────────────────────────

export function setView(view) {
    _currentView = view;
    localStorage.setItem(VIEW_STORAGE_KEY, view);

    const tableWrap   = document.getElementById('proj-table-wrap');
    const boardEl     = document.getElementById('proj-board');
    const colPickerWrap = document.getElementById('col-picker-wrap');
    const tableBtn    = document.getElementById('view-table-btn');
    const boardBtn    = document.getElementById('view-board-btn');

    if (view === 'board') {
        tableWrap?.classList.add('d-none');
        boardEl?.classList.remove('d-none');
        colPickerWrap?.classList.add('d-none');
        tableBtn?.classList.remove('active');
        boardBtn?.classList.add('active');
        renderBoard(document.getElementById('proj-search')?.value || '');
    } else {
        tableWrap?.classList.remove('d-none');
        boardEl?.classList.add('d-none');
        colPickerWrap?.classList.remove('d-none');
        tableBtn?.classList.add('active');
        boardBtn?.classList.remove('active');
    }
}

// ── Fetch ─────────────────────────────────────────────────────────────────────

export async function fetchAllProjects() {
    const res = await fetch('/api/v1/projects/?page_size=500');
    if (!res.ok) throw new Error('Failed to load projects');
    const data = await res.json();
    return data.results || data;
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    buildBoardScaffold();

    await Promise.all([
        loadCardConfig(),
        fetchAllProjects().then(p => { _allProjects = p; }),
    ]);

    document.getElementById('view-table-btn')?.addEventListener('click', () => setView('table'));
    document.getElementById('view-board-btn')?.addEventListener('click', () => setView('board'));

    document.getElementById('proj-search')?.addEventListener('input', e => {
        if (_currentView === 'board') renderBoard(e.target.value);
    });

    setView(_currentView);
});
