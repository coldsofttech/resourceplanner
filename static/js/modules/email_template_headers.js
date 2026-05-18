'use strict';

import { apiFetch, showFlash } from '../main.js';
import { API_URLS } from '../urls.js';
import {
    TOOLBAR_CONTAINER, initToolbarTooltips, injectCustomButtonIcons,
    addCustomHandlers, setupTablePicker, setupIconPicker, SourceModeManager,
} from './quill_editor_utils.js';

let modalQuill  = null;
let sourceMgr   = null;
let editingId   = null;
let bsModal     = null;
let allItems    = [];

document.addEventListener('DOMContentLoaded', () => {
    bsModal = new bootstrap.Modal(document.getElementById('headerModal'));

    modalQuill = new Quill('#modal-editor', {
        theme: 'snow',
        modules: { toolbar: TOOLBAR_CONTAINER },
        placeholder: 'Enter header HTML content…',
    });
    initToolbarTooltips(modalQuill);
    injectCustomButtonIcons(modalQuill);
    addCustomHandlers(modalQuill);
    setupTablePicker(modalQuill);
    setupIconPicker(modalQuill);

    sourceMgr = new SourceModeManager({
        quill:  modalQuill,
        richEl: document.getElementById('modal-editor'),
        htmlEl: document.getElementById('modal-html-source'),
        mdEl:   document.getElementById('modal-markdown-source'),
        tabsEl: document.getElementById('modal-mode-tabs'),
    });

    document.getElementById('new-header-btn').addEventListener('click', () => openModal(null));
    document.getElementById('new-header-btn-empty')?.addEventListener('click', () => openModal(null));
    document.getElementById('modal-save-btn').addEventListener('click', saveItem);
    document.getElementById('modal-delete-btn').addEventListener('click', deleteItem);

    // Clear edit state when modal closes
    document.getElementById('headerModal').addEventListener('hidden.bs.modal', resetModal);

    loadItems();
});

async function loadItems() {
    const loading = document.getElementById('headers-loading');
    const empty   = document.getElementById('headers-empty');
    const grid    = document.getElementById('headers-grid');

    let data;
    try {
        data = await apiFetch(API_URLS.email_template_headers.list.href, { method: 'GET' });
        // Handle paginated or plain array
        allItems = Array.isArray(data) ? data : (data.results ?? []);
    } catch {
        loading.classList.add('d-none');
        showFlash('Could not load headers. Please refresh.', 'danger');
        return;
    }

    loading.classList.add('d-none');
    if (!allItems.length) {
        empty.classList.remove('d-none');
        return;
    }
    empty.classList.add('d-none');
    grid.classList.remove('d-none');
    grid.innerHTML = allItems.map(item => _renderCard(item)).join('');
    grid.querySelectorAll('[data-edit-id]').forEach(btn => {
        btn.addEventListener('click', () => openModal(Number(btn.dataset.editId)));
    });
}

function _renderCard(item) {
    const preview = _stripHtml(item.content).slice(0, 120) || '(empty)';
    return `
    <div class="col-md-6 col-lg-4">
        <div class="et-block-card">
            <div class="et-block-card-header">
                <i class="bi bi-layout-text-window text-secondary" style="font-size:1.2rem;flex-shrink:0"></i>
                <div class="flex-fill min-width-0">
                    <div class="et-block-name">${_esc(item.name)}</div>
                    <div style="font-size:11px;color:var(--rp-text-muted)">
                        Updated ${_relativeTime(item.updated_at)}
                    </div>
                </div>
            </div>
            <div class="et-block-preview">${_esc(preview)}</div>
            <div class="et-block-actions">
                <button class="btn btn-sm btn-outline-secondary" data-edit-id="${item.id}">
                    <i class="bi bi-pencil me-1"></i>Edit
                </button>
            </div>
        </div>
    </div>`;
}

function openModal(id) {
    editingId = id;
    resetModal();

    const titleEl = document.getElementById('modal-title');
    const deleteBtn = document.getElementById('modal-delete-btn');

    if (id) {
        const item = allItems.find(i => i.id === id);
        if (!item) return;
        titleEl.innerHTML = '<i class="bi bi-layout-text-window me-2"></i>Edit Header';
        document.getElementById('modal-name').value = item.name;
        modalQuill.root.innerHTML = item.content || '';
        deleteBtn.classList.remove('d-none');
    } else {
        titleEl.innerHTML = '<i class="bi bi-layout-text-window me-2"></i>New Header';
        deleteBtn.classList.add('d-none');
    }
    bsModal.show();
}

function resetModal() {
    editingId = null;
    document.getElementById('modal-name').value = '';
    document.getElementById('modal-name-error').classList.add('d-none');
    modalQuill.root.innerHTML = '';
    document.getElementById('modal-html-source').value = '';
    const mdEl = document.getElementById('modal-markdown-source');
    if (mdEl) mdEl.value = '';
    // Reset to rich mode
    if (sourceMgr) {
        document.getElementById('modal-editor').classList.remove('d-none');
        document.getElementById('modal-html-source').classList.add('d-none');
        if (mdEl) mdEl.classList.add('d-none');
        sourceMgr.mode = 'rich';
        sourceMgr._syncTabs();
    }
}

function _getModalContent() {
    return sourceMgr ? sourceMgr.getContent() : modalQuill.root.innerHTML;
}

async function saveItem() {
    const name    = document.getElementById('modal-name').value.trim();
    const nameErr = document.getElementById('modal-name-error');
    if (!name) {
        nameErr.textContent = 'Name is required.';
        nameErr.classList.remove('d-none');
        return;
    }
    nameErr.classList.add('d-none');

    const saveBtn = document.getElementById('modal-save-btn');
    const orig    = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving…';

    const payload = { name, content: _getModalContent() };
    try {
        if (editingId) {
            await apiFetch(API_URLS.email_template_headers.update(editingId).href, {
                method: 'PATCH',
                body: JSON.stringify(payload),
            });
        } else {
            await apiFetch(API_URLS.email_template_headers.create.href, {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        }
        bsModal.hide();
        showFlash('Header saved.', 'success');
        _refreshList();
    } catch (err) {
        const msg = err?.data?.name?.[0] || err?.data?.error || 'Save failed.';
        nameErr.textContent = msg;
        nameErr.classList.remove('d-none');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = orig;
    }
}

async function deleteItem() {
    if (!editingId) return;
    if (!confirm('Delete this header? It will be detached from any templates using it.')) return;
    try {
        await apiFetch(API_URLS.email_template_headers.delete(editingId).href, { method: 'DELETE' });
        bsModal.hide();
        showFlash('Header deleted.', 'success');
        _refreshList();
    } catch {
        showFlash('Delete failed. Please try again.', 'danger');
    }
}

async function _refreshList() {
    document.getElementById('headers-grid').innerHTML = '';
    document.getElementById('headers-grid').classList.add('d-none');
    document.getElementById('headers-empty').classList.add('d-none');
    document.getElementById('headers-loading').classList.remove('d-none');
    await loadItems();
}

function _stripHtml(html) {
    const d = document.createElement('div');
    d.innerHTML = html || '';
    return d.textContent || d.innerText || '';
}

function _esc(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _relativeTime(iso) {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60)    return 'just now';
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return new Date(iso).toLocaleDateString();
}
