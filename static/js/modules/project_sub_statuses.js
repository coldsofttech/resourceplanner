'use strict';

import { initFetch } from "./../list/fetch.js";
import { initRenderer } from "./../list/render.js";
import { initSorting } from "./../list/sort.js";
import { apiFetch, escAttr, escHtml, setPageTitle, showFlash, hasPerm } from "./../main.js";
import { API_URLS, URLS } from "./../urls.js";
import { exportToCsv, exportToPdf } from "../export.js";

let MAIN_STATUSES = {};
const FETCHERS = {};

const LIST_EXPORT_COLUMNS = [
    { key: 'id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'main_status', label: 'Main Status' },
    { key: 'order', label: 'Order' },
    { key: 'is_active', label: 'Active' },
];

document.addEventListener('DOMContentLoaded', () => {
    initListView();
});

async function initListView() {
    setPageTitle("Project Sub-statuses");

    await initMainStatuses();
    renderStatusFilterOptions();
    renderMainStatusDropDownOptions();
    bindToolbarEvents();
    bindAddEditModalEvents();
    renderAllAccordionPanels();
    renderPanels();
}

function bindToolbarEvents() {
    document.getElementById('add-sub-status-btn')?.addEventListener('click', () => openAddModal());
    document.getElementById('export-csv').addEventListener('click', () => runListExport('csv'));
    document.getElementById('export-pdf').addEventListener('click', () => runListExport('pdf'));
}

function bindAddEditModalEvents() {
    document.getElementById('pssModal')?.addEventListener('hidden.bs.modal', resetAddEditModal);
    document.getElementById('pss-modal-save')?.addEventListener('click', handleModalSave);
    document.getElementById('confirm-active-btn')?.addEventListener('click', handleModalActive);
    document.getElementById('confirm-delete-btn')?.addEventListener('click', handleModalDelete);
}

function openAddModal(prefillStatus = "") {
    resetAddEditModal();
    document.getElementById('pss-modal-title').textContent = "Add Sub-status";
    document.getElementById('pss-modal-save').dataset.mode = 'add';
    delete document.getElementById('pss-modal-save').dataset.id;
    delete document.getElementById('pss-modal-save').dataset.mainStatus;

    document.getElementById('pss-modal-status-wrap').classList.remove('d-none');
    if (prefillStatus) {
        document.getElementById('pss-modal-status').value = prefillStatus;
    }

    bootstrap.Modal
        .getOrCreateInstance(document.getElementById('pssModal'))
        .show();
    setTimeout(() => document.getElementById('pss-modal-name').focus(), 300);
}

function openEditModal(id, name, mainStatus) {
    resetAddEditModal();
    document.getElementById('pss-modal-title').textContent = "Edit Sub-status";
    document.getElementById('pss-modal-name').value = name;
    document.getElementById('pss-modal-save').dataset.mode = 'edit';
    document.getElementById('pss-modal-save').dataset.id = id;
    document.getElementById('pss-modal-status').value = mainStatus;

    document.getElementById('pss-modal-status-wrap').classList.add('d-none');

    bootstrap.Modal
        .getOrCreateInstance(document.getElementById('pssModal'))
        .show();
    setTimeout(() => document.getElementById('pss-modal-name').focus(), 300);
}

function openActiveModal(statusId, statusName, statusIsActive, mainStatus) {
    const titleEl = document.getElementById('pss-active-modal-title');
    const confirmBtn = document.getElementById('confirm-active-btn');
    const messageEl = document.getElementById('pss-active-message');

    const activateButton = (active) => {
        if (active) {
            confirmBtn.classList.remove("btn-success");
            confirmBtn.classList.add("btn-danger");
        } else {
            confirmBtn.classList.remove("btn-danger");
            confirmBtn.classList.add("btn-success");
        }
    };

    const message = `<strong>${escHtml(statusName)}</strong> will be ${
        statusIsActive ? "deactivated" : "activated"
    }. Do you want to proceed?`;

    titleEl.textContent = statusIsActive ? "Deactivate" : "Activate";
    confirmBtn.textContent = statusIsActive ? "Deactivate" : "Activate";
    confirmBtn.dataset.id = statusId;
    confirmBtn.dataset.name = statusName;
    confirmBtn.dataset.isActive = statusIsActive;
    confirmBtn.dataset.mainStatus = mainStatus;

    activateButton(statusIsActive);
    messageEl.innerHTML = message;

    bootstrap.Modal
        .getOrCreateInstance(document.getElementById('pssActiveModal'))
        .show();
}

function openDeleteModal(statusId, statusName, mainStatus) {
    const nameEl = document.getElementById('pss-delete-name');
    const confirmBtn = document.getElementById('confirm-delete-btn');

    nameEl.textContent = statusName;
    confirmBtn.dataset.id = statusId;
    confirmBtn.dataset.name = statusName;
    confirmBtn.dataset.mainStatus = mainStatus;

    bootstrap.Modal
        .getOrCreateInstance(document.getElementById('pssDeleteModal'))
        .show();
}

function resetAddEditModal() {
    document.getElementById('pss-modal-name').value = "";
    document.getElementById('pss-modal-save').value = "";
    document.getElementById('pss-modal-status').value = "";
    clearAddEditModalErrors();
}

function clearAddEditModalErrors() {
    document.getElementById('pss-modal-banner').classList.add('d-none');
    ['pss-modal-name', 'pss-modal-status'].forEach((fieldId) => {
        document.getElementById(fieldId)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${fieldId}-error`);
        if (errEl) errEl.textContent = "";
    });
}

function setModalFieldError(fieldId, message) {
    document.getElementById(fieldId)?.classList.add('is-invalid');
    const errEl = document.getElementById(`${fieldId}-error`);
    if (errEl) errEl.textContent = message;
}

function showAddEditModalBanner(message) {
    const bannerEl = document.getElementById('pss-modal-banner');
    bannerEl.textContent = message;
    bannerEl.classList.remove("d-none");
}

function showActiveModalBanner(message) {
    const bannerEl = document.getElementById('pss-active-modal-banner');
    bannerEl.textContent = message;
    bannerEl.classList.remove("d-none");
}

function showDeleteModalBanner(message) {
    const bannerEl = document.getElementById('pss-delete-modal-banner');
    bannerEl.textContent = message;
    bannerEl.classList.remove("d-none");
}

async function handleModalSave() {
    const saveBtn = document.getElementById('pss-modal-save');
    const mode = saveBtn.dataset.mode;
    const id = saveBtn.dataset.id;
    const name = document.getElementById('pss-modal-name').value.trim();
    const mainStatus = document.getElementById('pss-modal-status').value;

    clearAddEditModalErrors();

    let hasError = false;
    if (!name) {
        setModalFieldError('pss-modal-name', 'Name is required.');
        hasError = true;
    }
    if (mode === "add" && !mainStatus) {
        setModalFieldError('pss-modal-status', 'Status group is required.');
        hasError = true;
    }
    if (hasError) return;

    const prevText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving...";

    try {
        if (mode === "add") {
            const { method, href } = API_URLS.project_sub_statuses.new;
            await apiFetch(href, {
                method: method,
                body: JSON.stringify({ name, main_status: mainStatus }),
            });
            showFlash(`${name} sub-status added successfully.`, 'success');
            bootstrap.Modal.getInstance(document.getElementById('pssModal'))?.hide();
            refreshPanel(mainStatus);
        } else {
            const { method, href } = API_URLS.project_sub_statuses.partial_edit(id);
            await apiFetch(href, {
                method: method,
                body: JSON.stringify({ name }),
            });
            showFlash(`${name} sub-status updated successfully.`, 'success');
            bootstrap.Modal.getInstance(document.getElementById('pssModal'))?.hide();
            refreshPanel(mainStatus);
        }
    } catch (err) {
        if (err?.status === 400) {
            const data = err.data ?? {};
            if (data.name) setModalFieldError('pss-modal-name', data.name[0]);
            if (data.main_status) setModalFieldError('pss-modal-status', data.main_status[0]);
            if (data.detail) showAddEditModalBanner(data.detail);
            return;
        }
        showAddEditModalBanner('Save failed. Please try again.');
        console.error('[handleModalSave] Save failed. Please try again.', err);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prevText;
    }
}

async function handleModalActive() {
    const confirmBtn = document.getElementById('confirm-active-btn');
    const id = confirmBtn.dataset.id;
    const name = confirmBtn.dataset.name;
    const newIsActive = !confirmBtn.dataset.isActive;
    const mainStatus = confirmBtn.dataset.mainStatus;

    const prevText = confirmBtn.textContent;
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Updating...";

    try {
        const { method, href } = API_URLS.project_sub_statuses.partial_edit(id);
        await apiFetch(href, {
            method: method,
            body: JSON.stringify({ is_active: newIsActive })
        });
        showFlash(`${name} sub-status updated successfully.`, 'success');
        bootstrap.Modal.getInstance(document.getElementById('pssActiveModal'))?.hide();
        refreshPanel(mainStatus);
    } catch (err) {
        showActiveModalBanner('Update failed. Please try again.');
        console.error('[handleModalActive] Update failed. Please try again.', err);
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = prevText;
    }
}

async function handleModalDelete() {
    const confirmBtn = document.getElementById('confirm-delete-btn');
    const id = confirmBtn.dataset.id;
    const name = confirmBtn.dataset.name;
    const mainStatus = confirmBtn.dataset.mainStatus;

    const prevText = confirmBtn.textContent;
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Deleting...";

    try {
        const { method, href } = API_URLS.project_sub_statuses.delete(id);
        await apiFetch(href, { method });
        showFlash(`${name} sub-status deleted successfully.`, 'success');
        bootstrap.Modal.getInstance(document.getElementById('pssDeleteModal'))?.hide();
        refreshPanel(mainStatus);
    } catch (err) {
        showDeleteModalBanner('Delete failed. Please try again.');
        console.error('[handleModalDelete] Delete failed. Please try again.', err);
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = prevText;
    }
}

async function renderStatusFilterOptions() {
    try {
        const { method, href } = API_URLS.project_sub_statuses.options;
        const options = await apiFetch(href, { method });
        const statuses = options?.is_active ?? [];

        const select = document.getElementById('status-filter');
        statuses.forEach(({ value, label }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('[renderStatusFilterOptions] Failed to load status filter options.', err);
    }
}

function renderMainStatusDropDownOptions() {
    const dropDownEl = document.getElementById('pss-modal-status');
    if (!dropDownEl) return;

    Object.values(MAIN_STATUSES).forEach((s) => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        dropDownEl.appendChild(opt);
    });
}

function formatMainStatusName(statusKey) {
    return statusKey
        .toLowerCase()
        .split("_")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

async function initMainStatuses() {
    try {
        const { method, href } = API_URLS.project_sub_statuses.options;
        const res = await apiFetch(href, { method });
        const statuses = res.main_status;

        MAIN_STATUSES = {};
        Object.keys(statuses).forEach((s) => {
            MAIN_STATUSES[s] = {
                id: s,
                name: formatMainStatusName(s),
            }
        });
    } catch (err) {
        console.error('[initMainStatuses] Failed to load main statuses.', err);
    }
}

function renderAllAccordionPanels() {
    const root = document.getElementById('pss-root');
    if (!root) return;

    root.innerHTML = '';

    Object.values(MAIN_STATUSES).forEach((s, idx) => {
        const card = document.createElement("div");
        card.id = `panel-${s.id}`;
        card.classList.add("rp-card", "p-0", "mb-3");

        const isFirst = idx === 0;
        const collapseClass = isFirst ? 'collapse show' : 'collapse';
        const ariaExpanded = isFirst ? 'true' : 'false';

        card.innerHTML = `
            <button class="rp-accordion-btn-sm w-100 d-flex align-items-center justify-content-between px-4 py-3"
                    type="button"
                    data-bs-toggle="collapse"
                    data-bs-target="#collapse-${s.id}"
                    aria-expanded="${ariaExpanded}"
                    aria-controls="collapse-${s.id}">
                <span class="d-flex align-items-center gap-2">
                    <i class="bi bi-tags text-secondary" style="font-size:14px;"></i>
                    <span class="fw-500">${s.name}</span>
                </span>
                <i class="bi bi-chevron-down rp-accordion-chevron"></i>
            </button>

            <div id="collapse-${s.id}" class="${collapseClass}" data-bs-parent="#pss-root">
                <div class="rp-table-wrap px-0 pb-0 m-2">
                    <table class="table rp-table mb-0" id="pss-table-${s.id}">
                        <thead>
                            <tr>
                                <th style="width: 20px;"></th>
                                <th>Name</th>
                                <th class="text-center" style="width:100px;">Status</th>
                                <th class="text-center" style="width:120px;">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="pss-tbody-${s.id}">
                            <tr>
                                <td colspan="4" class="text-center text-secondary py-4">
                                    <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                                    Loading...
                                </td>
                            </tr>
                        </tbody>
                    </table>

                    <div class="rp-pagination-bar d-flex align-items-center justify-content-between px-1 pt-3 flex-wrap gap-2" id="pss-pagination-bar-${s.id}" style="display: none;">
                        <span class="rp-pagination-info text-secondary small" id="pss-pagination-info-${s.id}"></span>
                        <nav>
                            <ul class="rp-pagination-controls pagination pagination-sm mb-0" id="pss-pagination-controls-${s.id}"></ul>
                        </nav>
                    </div>
                </div>
            </div>
        `;

        root.appendChild(card);
    });
}

function renderPanels() {
    try {
        Object.values(MAIN_STATUSES).forEach((s) => {
            const { method, href } = API_URLS.project_sub_statuses.list;
            const updatedHref = `${href}${s.id}`;

            const renderer = initRenderer({
                tbodyId: `pss-tbody-${s.id}`,
                colspan: 4,
                itemLabel: "sub-statuses",
                rowTemplate: renderStatusRow,
                emptyState: {
                    message: "No sub-statuses yet.",
                    link: {
                        href: `${URLS.project_sub_statuses.new}?main_status=${s.id}`,
                        label: "Create the first one",
                    },
                },
                filterEmptyState: {
                    message: "No sub-statuses match your filters.",
                    link: {
                        href: `${URLS.project_sub_statuses.new}?main_status=${s.id}`,
                        label: "Create a new sub-status",
                    },
                },
                paginationBarId: `pss-pagination-bar-${s.id}`,
                paginationInfoId: `pss-pagination-info-${s.id}`,
                paginationControlsId: `pss-pagination-controls-${s.id}`,
                onPageChange: page => FETCHERS[s.id].goToPage(page),
            });

            const fetcher = initFetch({
                apiUrl: updatedHref,
                pageSize: 20,
                searchInputId: "status-search",
                filters: [
                    {
                        id: "status-filter",
                        param: "is_active",
                    },
                ],
                onLoadStart: () => renderer.renderLoading("Loading sub-statuses..."),
                onSuccess: ({ results, pagination, state }) => {
                    const hasFilters = !!state.search || Object.keys(state.filters).length > 0;
                    renderer.renderRows(results, hasFilters);
                    renderer.renderPagination(pagination);
                },
                onError: () => renderer.renderError("Failed to load sub-statuses. Please refresh the page."),
            });

            FETCHERS[s.id] = fetcher;

            initSorting({
                tableId: `pss-table-${s.id}`,
                fetcher,
            });

            fetcher.refresh();
        });
    } catch (err) {
        console.error('[renderPanels] Failed to render panels.', err);
    }
}

function renderStatusRow(status) {
    const activateBtnTitle = status.is_active ? "Deactivate sub-status" : "Activate sub-status";
    const activateBtnClass = status.is_active ? "btn-ghost-icon--danger" : "btn-ghost-icon--success";

    return `
        <tr data-status-id="${status.id}">
            <td style="width:36px; padding: 0 8px;">
                <div class="d-flex flex-column align-items-center" style="gap:1px;">
                    ${hasPerm('project_sub_statuses.change_projectsubstatus') ? `
                    <button class="btn btn-ghost-icon btn-sm p-0"
                            style="height:16px; min-height:unset; line-height:1;"
                            title="Move up" onclick="moveUp(${status.id}, '${escAttr(status.name)}', '${escAttr(status.main_status)}')">
                        <i class="bi bi-chevron-up" style="font-size:11px;"></i>
                    </button>
                    <button class="btn btn-ghost-icon btn-sm p-0"
                            style="height:16px; min-height:unset; line-height:1;"
                            title="Move down" onclick="moveDown(${status.id}, '${escAttr(status.name)}', '${escAttr(status.main_status)}')">
                        <i class="bi bi-chevron-down" style="font-size:11px;"></i>
                    </button>` : ''}
                </div>
            </td>
            <td>
                ${escHtml(status.name)}
            </td>
            <td class="text-center">
                ${status.is_active
                    ? '<span class="rp-badge rp-badge--success">Active</span>'
                    : '<span class="rp-badge rp-badge--muted">Inactive</span>'
                }
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    ${hasPerm('project_sub_statuses.change_projectsubstatus') ? `
                    <button class="btn btn-ghost-icon" title="Edit sub-status"
                            onclick="openEditModal(${status.id}, '${escAttr(status.name)}', '${escAttr(status.main_status)}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-ghost-icon ${activateBtnClass}" title="${activateBtnTitle}"
                            onclick="openActiveModal(${status.id}, '${escAttr(status.name)}', ${status.is_active}, '${escAttr(status.main_status)}')">
                        <i class="bi bi-check-circle"></i>
                    </button>` : ''}
                    ${hasPerm('project_sub_statuses.delete_projectsubstatus') ? `
                    <button class="btn btn-ghost-icon btn-ghost-icon--danger" title="Delete sub-status"
                            onclick="openDeleteModal(${status.id}, '${escAttr(status.name)}', '${escAttr(status.main_status)}')">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `;
}

function refreshPanel(mainStatusKey) {
    FETCHERS[mainStatusKey].refresh();
}

async function moveUp(statusId, statusName, mainStatus) {
    try {
        const { method, href } = API_URLS.project_sub_statuses.reorder(statusId);
        await apiFetch(href, {
            method: method,
            body: JSON.stringify({
                direction: "up"
            })
        });
        renderPanels(mainStatus);
    } catch (err) {
        showFlash(`${statusName} reorder failed. Please try again.`, 'danger');
        console.error('[moveUp] Reorder failed. Please try again.', err);
    }
}

async function moveDown(statusId, statusName, mainStatus) {
    try {
        const { method, href } = API_URLS.project_sub_statuses.reorder(statusId);
        await apiFetch(href, {
            method: method,
            body: JSON.stringify({
                direction: "down"
            })
        });
        renderPanels(mainStatus);
    } catch (err) {
        showFlash(`${statusName} reorder failed. Please try again.`, 'danger');
        console.error('[moveDown] Reorder failed. Please try again.', err);
    }
}

async function runListExport(format) {
    const btn = document.getElementById('export-dropdown-btn');
    bootstrap.Dropdown.getInstance(btn)?.hide();

    if (btn) {
        btn.disabled  = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Exporting…';
    }

    try {
        const { method, href } = API_URLS.project_sub_statuses.export;
        const res = await apiFetch(href, { method });
        const date = new Date().toISOString().slice(0, 10);
        const filename = `project_sub_statuses-${date}`;

        if (format === 'csv') {
            exportToCsv(res.results, LIST_EXPORT_COLUMNS, filename);
        } else {
            exportToPdf(res.results, LIST_EXPORT_COLUMNS, 'Project Sub-statuses', filename);
        }
    } catch (err) {
        showFlash('Export failed. Please try again.', 'error');
        console.error('[runListExport] Export failed. Please try again.', err);
    } finally {
        if (btn) {
            btn.disabled  = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i>Export';
        }
    }
}

window.openEditModal = openEditModal;
window.openActiveModal = openActiveModal;
window.openDeleteModal = openDeleteModal;
window.moveUp = moveUp;
window.moveDown = moveDown;