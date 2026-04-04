'use strict';

import {
    apiFetch, showFlash, formatDateTime, setPageTitle, escHtml, escAttr,
    getPkFromUrl, isSubPathUrl, clearErrors, setSubmitting,
    showBanner, applyErrors
} from './../main.js';
import { URLS, API_URLS } from './../urls.js';
import { initFetch } from './../list/fetch.js';
import { initSorting } from './../list/sort.js';
import { initRenderer } from './../list/render.js';
import { exportToCsv, exportToPdf } from './../export.js';

let fetcher       = null;
let _teamOptions  = [];   // cached for move-team modal
let _currentMember = null; // cached for detail view move-team

const memberPk = getPkFromUrl('team-members');
const isEdit   = isSubPathUrl('team-members', 'edit');

document.addEventListener('DOMContentLoaded', () => {
    const membersTable = document.getElementById('team-members-table');
    if (membersTable) {
        initListView();
        return;
    }

    const detailRoot = document.getElementById('detail-root');
    if (detailRoot) {
        initDetailView();
        return;
    }

    const formEl = document.getElementById('member-form');
    if (formEl) {
        formEl.addEventListener('submit', handleCreateEditSubmit);
        if (isEdit) {
            initEditView();
        } else {
            initCreateView();
        }
    }
});

/* =========================================================
 * List View
 * ========================================================= */
function initListView() {
    setPageTitle('Team Members');
    renderStatistics();
    renderStatusFilterOptions();
    renderRoleFilterOptions();
    renderLocationFilterOptions();
    renderEmploymentTypeFilterOptions();
    renderTeamFilterOptions();
    _loadTeamOptions();

    const renderer = initRenderer({
        tbodyId:    'team-members-tbody',
        colspan:    8,
        itemLabel:  'team members',
        rowTemplate: renderMemberRow,
        emptyState: {
            message: 'No team members yet.',
            link:    { href: URLS.team_members.new, label: 'Add the first one' },
        },
        filterEmptyState: {
            message: 'No team members match your filters.',
            link:    { href: URLS.team_members.new, label: 'Add a new member' },
        },
        paginationBarId:      'pagination-bar',
        paginationInfoId:     'pagination-info',
        paginationControlsId: 'pagination-controls',
        onPageChange: page => fetcher.goToPage(page),
    });

    fetcher = initFetch({
        apiUrl:        API_URLS.team_members.list.href,
        pageSize:      20,
        searchInputId: 'member-search',
        filters: [
            { id: 'status-filter', param: 'is_active' },
            { id: 'role-filter', param: 'role_id' },
            { id: 'location-filter', param: 'location_id' },
            { id: 'employment-type-filter', param: 'employment_type_id' },
            { id: 'team-filter', param: 'team_id' },
        ],
        onLoadStart: () => renderer.renderLoading('Loading team members...'),
        onSuccess: ({ results, pagination, state }) => {
            const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
            renderer.renderRows(results, hasFilters);
            renderer.renderPagination(pagination);
        },
        onError: () => renderer.renderError('Failed to load team members. Please refresh the page.'),
    });

    initSorting({ tableId: 'team-members-table', fetcher });
    fetcher.refresh();

    document.getElementById('export-csv').addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf').addEventListener('click', () => runListExport('pdf'));
}

async function renderStatistics() {
    try {
        const { method, href } = API_URLS.team_members.stats;
        const stats = await apiFetch(href, { method });
        document.getElementById('stat-total-members').textContent      = stats.total_members      ?? '-';
        document.getElementById('stat-active-members').textContent     = stats.active_members     ?? '-';
        document.getElementById('stat-inactive-members').textContent   = stats.inactive_members   ?? '-';
        document.getElementById('stat-unassigned-members').textContent = stats.unassigned_members ?? '-';
    } catch (err) {
        console.error('[renderStatistics]', err);
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.team_members.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('status-filter');
        (options?.is_active ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions]', err);
    }
}

async function renderRoleFilterOptions() {
    try {
        const { method, href } = API_URLS.team_members.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('role-filter');
        (options?.roles ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions]', err);
    }
}

async function renderLocationFilterOptions() {
    try {
        const { method, href } = API_URLS.team_members.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('location-filter');
        (options?.locations ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions]', err);
    }
}

async function renderEmploymentTypeFilterOptions() {
    try {
        const { method, href } = API_URLS.team_members.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('employment-type-filter');
        (options?.employment_types ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions]', err);
    }
}

async function renderTeamFilterOptions() {
    try {
        const { method, href } = API_URLS.team_members.options;
        const options = await apiFetch(href, { method });
        const select  = document.getElementById('team-filter');
        (options?.teams ?? []).forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions]', err);
    }
}

function renderMemberRow(member) {
    const locDisplay  = member.location
        ? escHtml(`${member.location.city}, ${member.location.country}`)
        : '—';
    const teamDisplay = member.team
        ? escHtml(member.team.name)
        : '<span class="text-secondary">—</span>';
    const skillBadges = (member.skills || []).length
        ? member.skills.map(s =>
              `<span class="rp-badge rp-badge--info me-1">${escHtml(s.skill)}</span>`
          ).join('')
        : '<span class="text-secondary small">—</span>';
    const statusBadge = member.is_active
        ? '<span class="rp-badge rp-badge--success">Active</span>'
        : '<span class="rp-badge rp-badge--muted">Inactive</span>';

    const currentTeamId   = member.team ? member.team.id   : null;
    const currentTeamName = member.team ? member.team.name : '';

    return `
        <tr data-member-id="${member.id}">
            <td>
                <a href="${URLS.team_members.detail(member.id)}" class="rp-link">
                    ${escHtml(member.display_name)}
                </a>
            </td>
            <td>${escHtml(member.email_address)}</td>
            <td>${member.role ? escHtml(member.role.role) : '—'}</td>
            <td>${locDisplay}</td>
            <td>${member.employment_type ? escHtml(member.employment_type.name) : '—'}</td>
            <td>${teamDisplay}</td>
            <td>${statusBadge}</td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <a href="${URLS.team_members.detail(member.id)}"
                       class="btn btn-ghost-icon" title="View member">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="${URLS.team_members.edit(member.id)}"
                       class="btn btn-ghost-icon" title="Edit member">
                        <i class="bi bi-pencil"></i>
                    </a>
                    <button class="btn btn-ghost-icon" title="Move team"
                            onclick="confirmMoveTeam(${member.id}, '${escAttr(member.display_name)}', ${JSON.stringify(currentTeamId)}, '${escAttr(currentTeamName)}', onMoveFromList)">
                        <i class="bi bi-arrow-left-right"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger" title="Delete member"
                            onclick="confirmDelete(${member.id}, '${escAttr(member.display_name)}', onDeleteFromList)">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function onMoveFromList(id, toTeamName) {
    showFlash(`Member moved to ${toTeamName || 'no team'} successfully.`, 'success');
    fetcher?.refresh();
    renderStatistics();
}

function onDeleteFromList(id, name) {
    showFlash(`Team member "${name}" was deleted successfully.`, 'success');
    document.querySelector(`tr[data-member-id="${id}"]`)?.remove();
    fetcher?.refresh();
    renderStatistics();
}

/* =========================================================
 * Create & Edit View
 * ========================================================= */
async function initCreateView() {
    setPageTitle('New Team Member');
    document.getElementById('page-title').textContent    = 'New Team Member';
    document.getElementById('page-subtitle').textContent = 'Add a new member to your organisation';
    document.getElementById('submit-label').textContent  = 'Create member';
    document.getElementById('submit-btn').dataset.originalLabel = 'Create member';
    await loadFormOptions(null);
}

async function initEditView() {
    setPageTitle('Edit Team Member');
    const submitBtn = document.getElementById('submit-btn');
    document.getElementById('page-title').textContent    = 'Edit Team Member';
    document.getElementById('page-subtitle').textContent = 'Loading…';
    document.getElementById('submit-label').textContent  = 'Save changes';
    submitBtn.dataset.originalLabel = 'Save changes';
    submitBtn.disabled = true;

    await loadFormOptions(null);

    try {
        const { method, href } = API_URLS.team_members.get(memberPk);
        const res = await apiFetch(href, { method });
        populateForm(res);
        submitBtn.disabled = false;
    } catch (err) {
        document.getElementById('page-subtitle').textContent = '';
        submitBtn.disabled = true;
        if (err?.status === 404) {
            showFlash('This team member no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.team_members.list; }, 3000);
            return;
        }
        showFlash(err.data?.error || 'Could not load member data. Please try again.', 'danger');
    }

    submitBtn.disabled = false;
}

async function getDefaultHolidays() {
    try {
        const { method, href } = API_URLS.configurations.by_code('DEFAULT_HOLIDAYS');
        const res = await apiFetch(href, { method });
        return res.value ?? '0';
    } catch (err) {
        console.error('[getDefaultHolidays]', err);
        showFlash('Could not load DEFAULT_HOLIDAYS. Please refresh.', 'danger');
    }
}

async function loadFormOptions(currentSkillIds) {
    try {
        const { method, href } = API_URLS.team_members.options;
        const options = await apiFetch(href, { method });
        const default_holidays = await getDefaultHolidays();

        _populateSelect('id_role',            options.roles ?? [],            'is_default');
        _populateSelect('id_employment_type', options.employment_types ?? [], 'is_default');
        _populateSelect('id_location',        options.locations ?? [],        'is_default');
        _populateSelect('id_team',            options.teams ?? [],            null);
        _renderSkillsCheckboxes(options.skills ?? [], currentSkillIds);
        _teamOptions = options.teams ?? [];
        document.getElementById('id_default_holidays').value = default_holidays;
    } catch (err) {
        console.error('[loadFormOptions]', err);
        showFlash('Could not load form options. Please refresh.', 'danger');
    }
}

function _populateSelect(selectId, items, defaultKey) {
    const select = document.getElementById(selectId);
    if (!select) return;
    items.forEach(item => {
        const opt = document.createElement('option');
        opt.value       = item.value;
        opt.textContent = item.label;
        if (defaultKey && item[defaultKey]) opt.selected = true;
        select.appendChild(opt);
    });
}

function _renderSkillsCheckboxes(skills, selectedIds) {
    const container = document.getElementById('skills-select-container');
    if (!container) return;
    container.innerHTML = '';
    if (!skills.length) {
        container.innerHTML = '<p class="text-secondary small mb-0">No active skills available.</p>';
        return;
    }
    const selected = new Set(selectedIds ?? []);
    skills.forEach(({ value, label }) => {
        const div = document.createElement('div');
        div.className = 'form-check';
        div.innerHTML = `
            <input class="form-check-input skill-checkbox" type="checkbox"
                   id="skill_${value}" value="${value}"
                   ${selected.has(value) ? 'checked' : ''} />
            <label class="form-check-label small" for="skill_${value}">${escHtml(label)}</label>
        `;
        container.appendChild(div);
    });
}

async function handleCreateEditSubmit(e) {
    e.preventDefault();
    clearErrors(['first_name', 'last_name', 'email_address', 'role', 'location',
                 'employment_type', 'start_date', 'end_date', 'default_holidays']);

    const firstName = document.getElementById('id_first_name').value.trim();
    const lastName  = document.getElementById('id_last_name').value.trim();
    const email     = document.getElementById('id_email_address').value.trim();
    const role      = document.getElementById('id_role').value;
    const location  = document.getElementById('id_location').value;
    const empType   = document.getElementById('id_employment_type').value;
    const startDate = document.getElementById('id_start_date').value;

    let valid = true;
    if (!firstName) { _fieldError('id_first_name',    'first_name-error',    'First name is required.');      valid = false; }
    if (!lastName)  { _fieldError('id_last_name',     'last_name-error',     'Last name is required.');       valid = false; }
    if (!email)     { _fieldError('id_email_address', 'email_address-error', 'Email address is required.');   valid = false; }
    if (!role)      { _fieldError('id_role',          'role-error',          'Role is required.');             valid = false; }
    if (!location)  { _fieldError('id_location',      'location-error',      'Office location is required.'); valid = false; }
    if (!empType)   { _fieldError('id_employment_type', 'employment_type-error', 'Employment type is required.'); valid = false; }
    if (!startDate) { _fieldError('id_start_date',    'start_date-error',    'Start date is required.');      valid = false; }
    if (!valid) return;

    const skillIds    = Array.from(document.querySelectorAll('.skill-checkbox:checked'))
                            .map(cb => parseInt(cb.value));
    const teamVal     = document.getElementById('id_team').value;
    const displayName = document.getElementById('id_display_name').value.trim();
    const endDate     = document.getElementById('id_end_date').value || null;
    const defHolidays = parseInt(document.getElementById('id_default_holidays').value) || 0;
    const isActive    = document.getElementById('id_is_active').checked;

    const payload = {
        first_name:       firstName,
        last_name:        lastName,
        display_name:     displayName,
        email_address:    email,
        role:             parseInt(role),
        location:         parseInt(location),
        employment_type:  parseInt(empType),
        team:             teamVal ? parseInt(teamVal) : null,
        start_date:       startDate,
        end_date:         endDate,
        default_holidays: defHolidays,
        skills:           skillIds,
        is_active:        isActive,
    };

    const { method, href } = isEdit
        ? API_URLS.team_members.partial_edit(memberPk)
        : API_URLS.team_members.new;

    setSubmitting(true);
    try {
        await apiFetch(href, { method, body: JSON.stringify(payload) });
        window.location.href = URLS.team_members.list;
    } catch (err) {
        if (err?.status === 400) {
            applyErrors(err.data ?? {}, ['first_name', 'last_name', 'email_address', 'role',
                                          'location', 'employment_type', 'start_date', 'default_holidays']);
            return;
        }
        if (err?.status === 404) {
            showFlash('This team member no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.team_members.list; }, 3000);
            return;
        }
        showFlash(err.data?.error || 'Could not save. Please try again.', 'danger');
    } finally {
        setSubmitting(false);
    }
}

function _fieldError(inputId, errorId, message) {
    document.getElementById(inputId)?.classList.add('is-invalid');
    const el = document.getElementById(errorId);
    if (el) el.textContent = message;
}

function populateForm(member) {
    document.getElementById('id_first_name').value     = member.first_name     ?? '';
    document.getElementById('id_last_name').value      = member.last_name      ?? '';
    document.getElementById('id_display_name').value   = member.display_name   ?? '';
    document.getElementById('id_email_address').value  = member.email_address  ?? '';
    document.getElementById('id_start_date').value     = member.start_date     ?? '';
    document.getElementById('id_end_date').value       = member.end_date       ?? '';
    document.getElementById('id_default_holidays').value = member.default_holidays ?? 0;
    document.getElementById('id_is_active').checked    = member.is_active      ?? true;

    if (member.role)            document.getElementById('id_role').value            = member.role.id;
    if (member.location)        document.getElementById('id_location').value        = member.location.id;
    if (member.employment_type) document.getElementById('id_employment_type').value = member.employment_type.id;
    if (member.team)            document.getElementById('id_team').value            = member.team.id;

    // Tick correct skill checkboxes
    const selectedIds = new Set((member.skills || []).map(s => s.id));
    document.querySelectorAll('.skill-checkbox').forEach(cb => {
        cb.checked = selectedIds.has(parseInt(cb.value));
    });

    document.getElementById('page-subtitle').innerHTML =
        `Updating <strong>${escHtml(member.display_name)}</strong>`;
    document.getElementById('meta-created').textContent = formatDateTime(member.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(member.updated_at);
    document.getElementById('metadata-card').classList.remove('d-none');

    document.getElementById('delete-btn-slot').innerHTML = `
        <button type="button" class="btn btn-outline-danger" id="delete-member-btn">
            <i class="bi bi-trash me-1"></i> Delete
        </button>`;
    document.getElementById('delete-member-btn')
        .addEventListener('click', () => confirmDelete(member.id, member.display_name, onDeleteFromEdit));
}

function onDeleteFromEdit() {
    window.location.href = URLS.team_members.list;
}

/* =========================================================
 * Detail View
 * ========================================================= */
async function initDetailView() {
    if (!memberPk) return;
    setPageTitle('Team Member');

    try {
        const { method, href } = API_URLS.team_members.detail(memberPk);
        const data = await apiFetch(href, { method });
        _currentMember = data;
        renderDetailTitle(data);
        renderMemberDetails(data);
        _setupDetailMoveBtn(data);
        _loadTeamOptions();
    } catch (err) {
        if (err?.status === 404) {
            showFlash('This team member no longer exists. Redirecting to the list…', 'warning');
            setTimeout(() => { window.location.href = URLS.team_members.list; }, 3000);
            return;
        }
        showFlash(err?.data?.error || 'Could not load member details. Please refresh.', 'danger');
    }

    loadHistoryTimeline();
}

function renderDetailTitle(member) {
    document.getElementById('member-name').textContent = member.display_name;
    const statusEl = document.getElementById('member-status');
    statusEl.textContent = member.is_active ? 'Active' : 'Inactive';
    statusEl.classList.add(member.is_active ? 'rp-badge--success' : 'rp-badge--muted');

    const parts = [
        member.role     ? member.role.role : null,
        member.location ? `${member.location.city}, ${member.location.country}` : null,
    ].filter(Boolean);
    document.getElementById('member-role-location').textContent = parts.join(' · ');
    document.getElementById('edit-member-btn').href = URLS.team_members.edit(memberPk);
}

function renderMemberDetails(member) {
    document.getElementById('member-first-name').textContent = member.first_name ?? '—';
    document.getElementById('member-last-name').textContent = member.last_name ?? '—';
    document.getElementById('member-email').textContent =
        member.email_address ?? '—';
    document.getElementById('member-role').textContent =
        member.role ? member.role.role : '—';
    document.getElementById('member-location').textContent =
        member.location ? `${member.location.city}, ${member.location.country}` : '—';
    document.getElementById('member-employment-type').textContent =
        member.employment_type ? member.employment_type.name : '—';
    document.getElementById('member-team').textContent =
        member.team ? member.team.name : '—';
    document.getElementById('member-start-date').textContent = member.start_date ?? '—';
    document.getElementById('member-end-date').textContent   = member.end_date   ?? '—';
    document.getElementById('member-holidays').textContent   =
        member.default_holidays != null ? `${member.default_holidays} days` : '—';

    const skillsEl = document.getElementById('member-skills-badges');
    if (member.skills?.length) {
        skillsEl.innerHTML = member.skills
            .map(s => `<span class="rp-badge rp-badge--info me-1 mb-1">${escHtml(s.skill)}</span>`)
            .join('');
    } else {
        skillsEl.innerHTML = '<span class="text-secondary small">No skills assigned.</span>';
    }

    document.getElementById('meta-created').textContent = formatDateTime(member.created_at);
    document.getElementById('meta-updated').textContent = formatDateTime(member.updated_at);
}

function _setupDetailMoveBtn(member) {
    document.getElementById('move-team-btn')?.addEventListener('click', () => {
        confirmMoveTeam(
            member.id,
            member.display_name,
            member.team ? member.team.id   : null,
            member.team ? member.team.name : '',
            onMoveFromDetail,
        );
    });
}

function onDeleteFromDetail() {
    window.location.href = URLS.team_members.list;
}

async function onMoveFromDetail(id, toTeamName) {
    showFlash(`Moved to ${toTeamName || 'no team'} successfully.`, 'success');
    // Reload the page to reflect updated team + new history entry
    setTimeout(() => window.location.reload(), 800);
}

/* =========================================================
 * History Timeline
 * ========================================================= */
async function loadHistoryTimeline() {
    const el = document.getElementById('history-timeline');
    try {
        const { method, href } = API_URLS.team_members.history(memberPk);
        const data = await apiFetch(href, { method });
        const entries = data.results ?? [];
        document.getElementById('history-count').textContent =
            entries.length ? `${entries.length} record${entries.length !== 1 ? 's' : ''}` : '';
        renderHistoryTimeline(entries);
    } catch (_err) {
        el.innerHTML = '<p class="text-secondary small">Could not load history.</p>';
    }
}

function renderHistoryTimeline(entries) {
    const el = document.getElementById('history-timeline');
    if (!entries.length) {
        el.innerHTML = `
            <div class="text-center py-4 text-secondary">
                <i class="bi bi-clock-history fs-3 d-block mb-2 opacity-50"></i>
                <span class="small">No team history recorded yet.</span>
            </div>`;
        return;
    }

    const items = entries.map((entry, i) => {
        const fromName = entry.from_team
            ? `<strong>${escHtml(entry.from_team.name)}</strong>`
            : '<span class="text-secondary fst-italic">No team</span>';
        const toName = entry.to_team
            ? `<strong>${escHtml(entry.to_team.name)}</strong>`
            : '<span class="text-secondary fst-italic">Unassigned</span>';
        const note   = entry.note
            ? `<p class="text-secondary small mb-0 mt-1">${escHtml(entry.note)}</p>`
            : '';
        const isLatest = i === 0;
        const dotClass = isLatest ? 'rp-timeline-dot--success' : 'rp-timeline-dot--muted';

        return `
            <div class="rp-timeline-item">
                <div class="rp-timeline-marker">
                    <div class="rp-timeline-dot ${dotClass}"></div>
                    ${i < entries.length - 1 ? '<div class="rp-timeline-line"></div>' : ''}
                </div>
                <div class="rp-timeline-body pb-4">
                    <div class="rp-timeline-meta">
                        <i class="bi bi-calendar3"></i> ${escHtml(entry.moved_on)}
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        ${fromName}
                        <i class="bi bi-arrow-right text-secondary small"></i>
                        ${toName}
                        ${isLatest ? '<span class="rp-badge rp-badge--info ms-1">Current</span>' : ''}
                    </div>
                    ${note}
                </div>
            </div>
        `;
    }).join('');

    el.innerHTML = `<div class="rp-timeline d-flex flex-column">${items}</div>`;
}

/* =========================================================
 * Move Team Modal – shared between list and detail
 * ========================================================= */
async function _loadTeamOptions() {
    if (_teamOptions.length) return;
    try {
        const { method, href } = API_URLS.team_members.options;
        const opts = await apiFetch(href, { method });
        _teamOptions = opts.teams ?? [];
    } catch (err) {
        console.error('[_loadTeamOptions]', err);
    }
}

function confirmMoveTeam(memberId, memberName, currentTeamId, currentTeamName, onSuccess) {
    const modal  = document.getElementById('moveTeamModal');
    const moveBtn = document.getElementById('confirm-move-btn');
    if (!modal || !moveBtn) return;

    document.getElementById('move-member-name').textContent  = memberName;
    document.getElementById('move-current-team').textContent = currentTeamName || '—';
    document.getElementById('move-note').value = '';

    const select = document.getElementById('move-to-team');
    select.innerHTML = '<option value="">— Unassign from team —</option>';
    _teamOptions.forEach(({ value, label }) => {
        if (value == currentTeamId) return;   // skip current team
        const opt = document.createElement('option');
        opt.value       = value;
        opt.textContent = label;
        select.appendChild(opt);
    });

    const newBtn = moveBtn.cloneNode(true);
    moveBtn.parentNode.replaceChild(newBtn, moveBtn);

    newBtn.addEventListener('click', async () => {
        newBtn.disabled    = true;
        newBtn.innerHTML   = '<span class="spinner-border spinner-border-sm me-1"></span>Moving…';
        const toTeamVal = document.getElementById('move-to-team').value;
        const note      = document.getElementById('move-note').value.trim();
        try {
            const { method, href } = API_URLS.team_members.move_team(memberId);
            await apiFetch(href, {
                method,
                body: JSON.stringify({
                    from_team: currentTeamId  ? parseInt(currentTeamId)  : null,
                    to_team:   toTeamVal      ? parseInt(toTeamVal)       : null,
                    note,
                }),
            });
            bootstrap.Modal.getInstance(modal)?.hide();
            const toName = _teamOptions.find(t => t.value == parseInt(toTeamVal))?.label ?? '';
            if (onSuccess) onSuccess(memberId, toName);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            showFlash(
                err?.data?.error || err?.data?.details?.[0] || `Failed to move "${memberName}". Please try again.`,
                'danger'
            );
        } finally {
            newBtn.disabled  = false;
            newBtn.innerHTML = '<i class="bi bi-arrows-move me-1"></i>Move';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

/* =========================================================
 * Delete Modal – shared
 * ========================================================= */
function confirmDelete(id, name, onSuccess) {
    const modal  = document.getElementById('deleteModal');
    const nameEl = document.getElementById('delete-member-name');
    const btn    = document.getElementById('confirm-delete-btn');
    if (!modal || !btn) return;

    nameEl.textContent = name;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    const { method, href } = API_URLS.team_members.delete(id);

    newBtn.addEventListener('click', async () => {
        try {
            newBtn.disabled    = true;
            newBtn.textContent = 'Deleting...';
            await apiFetch(href, { method });
            bootstrap.Modal.getInstance(modal)?.hide();
            onSuccess(id, name);
        } catch (err) {
            bootstrap.Modal.getInstance(modal)?.hide();
            if (err?.status === 404) {
                showFlash(`"${name}" was not found — it may have already been deleted.`, 'warning');
                document.querySelector(`tr[data-member-id="${id}"]`)?.remove();
                fetcher?.refresh();
                renderStatistics();
                return;
            }
            showFlash(
                err?.data?.detail || `Failed to delete "${name}". Please try again.`,
                'error'
            );
        } finally {
            newBtn.disabled    = false;
            newBtn.textContent = 'Delete';
        }
    });

    bootstrap.Modal.getOrCreateInstance(modal).show();
}

/* =========================================================
 * Export
 * ========================================================= */
const LIST_EXPORT_COLUMNS = [
    { key: 'id',              label: 'ID' },
    { key: 'first_name',      label: 'First Name' },
    { key: 'last_name',       label: 'Last Name' },
    { key: 'display_name',    label: 'Display Name' },
    { key: 'email_address',   label: 'Email' },
    { key: 'role',            label: 'Role' },
    { key: 'location',        label: 'Location' },
    { key: 'employment_type', label: 'Employment Type' },
    { key: 'team',            label: 'Team' },
    { key: 'skills',          label: 'Skills' },
    { key: 'start_date',      label: 'Start Date' },
    { key: 'end_date',        label: 'End Date' },
    { key: 'default_holidays', label: 'Default Holidays' },
    { key: 'is_active',       label: 'Active' },
];

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();
    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }
    try {
        const { method, href } = API_URLS.team_members.export;
        const res  = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, `team-members-${date}`);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Team Members', `team-members-${date}`);
        }
    } catch (_err) {
        showFlash('Export failed. Please try again.', 'error');
    } finally {
        if (btn) {
            btn.disabled  = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

/* =========================================================
 * Window Exports
 * ========================================================= */
window.confirmDelete   = confirmDelete;
window.confirmMoveTeam = confirmMoveTeam;
window.onDeleteFromList = onDeleteFromList;
window.onMoveFromList   = onMoveFromList;
