/* Roadmaps list page */

async function loadRoadmaps() {
    const grid = document.getElementById('roadmaps-grid');
    try {
        const res = await fetch('/api/v1/roadmaps/');
        if (!res.ok) throw new Error('Failed to load roadmaps');
        const data = await res.json();
        const roadmaps = data.results || [];
        if (!roadmaps.length) {
            grid.innerHTML = `
                <div class="col-12 text-center py-5 text-secondary">
                    <i class="bi bi-map" style="font-size:48px;opacity:.3"></i>
                    <p class="mt-3 mb-1 fw-500">No roadmaps yet</p>
                    <p class="small">Create a roadmap to plan your project delivery timeline.</p>
                    <button class="btn btn-sm btn-primary mt-2" id="new-roadmap-btn-empty">
                        <i class="bi bi-plus-lg me-1"></i>New Roadmap
                    </button>
                </div>`;
            document.getElementById('new-roadmap-btn-empty')?.addEventListener('click', openNewModal);
            return;
        }
        grid.innerHTML = roadmaps.map(r => `
            <div class="col-12 col-md-6 col-lg-4">
                <div class="rp-card h-100 p-4 d-flex flex-column gap-2">
                    <div class="d-flex align-items-start justify-content-between">
                        <a href="/roadmaps/${r.id}/" class="fw-600 text-decoration-none" style="font-size:15px">
                            <i class="bi bi-map me-2 text-primary"></i>${escHtml(r.name)}
                        </a>
                        <div class="dropdown">
                            <button class="btn btn-ghost-icon" data-bs-toggle="dropdown" style="width:28px;height:28px;font-size:13px">
                                <i class="bi bi-three-dots-vertical"></i>
                            </button>
                            <ul class="dropdown-menu dropdown-menu-end">
                                <li><a class="dropdown-item" href="/roadmaps/${r.id}/">
                                    <i class="bi bi-pencil me-2"></i>Open
                                </a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item text-danger rm-delete-btn" href="#"
                                       data-id="${r.id}" data-name="${escHtml(r.name)}">
                                    <i class="bi bi-trash me-2"></i>Delete
                                </a></li>
                            </ul>
                        </div>
                    </div>
                    ${r.description ? `<p class="text-secondary small mb-0">${escHtml(r.description)}</p>` : ''}
                    <div class="d-flex align-items-center gap-3 mt-auto pt-2 border-top" style="font-size:12px;color:var(--color-text-3)">
                        <span><i class="bi bi-layers me-1"></i>${r.item_count} item${r.item_count !== 1 ? 's' : ''}</span>
                        <span class="ms-auto"><i class="bi bi-clock me-1"></i>${fmtDate(r.updated_at)}</span>
                    </div>
                </div>
            </div>`).join('');

        grid.querySelectorAll('.rm-delete-btn').forEach(btn => {
            btn.addEventListener('click', e => {
                e.preventDefault();
                if (confirm(`Delete roadmap "${btn.dataset.name}"? This cannot be undone.`)) {
                    deleteRoadmap(btn.dataset.id);
                }
            });
        });
    } catch (err) {
        grid.innerHTML = `<div class="col-12 text-danger">${err.message}</div>`;
    }
}

async function deleteRoadmap(id) {
    const res = await fetch(`/api/v1/roadmaps/${id}/`, { method: 'DELETE' });
    if (res.ok) loadRoadmaps();
}

function openNewModal() {
    document.getElementById('rm-name').value = '';
    document.getElementById('rm-desc').value = '';
    document.getElementById('rm-error').classList.add('d-none');
    const modal = new bootstrap.Modal(document.getElementById('new-roadmap-modal'));
    modal.show();
}

function escHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

document.addEventListener('DOMContentLoaded', () => {
    loadRoadmaps();

    document.getElementById('new-roadmap-btn')?.addEventListener('click', openNewModal);

    document.getElementById('rm-save-btn')?.addEventListener('click', async () => {
        const name = document.getElementById('rm-name').value.trim();
        const desc = document.getElementById('rm-desc').value.trim();
        const errEl = document.getElementById('rm-error');
        if (!name) { errEl.textContent = 'Name is required.'; errEl.classList.remove('d-none'); return; }
        errEl.classList.add('d-none');

        const res = await fetch('/api/v1/roadmaps/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ name, description: desc }),
        });
        if (res.ok) {
            const data = await res.json();
            bootstrap.Modal.getInstance(document.getElementById('new-roadmap-modal'))?.hide();
            window.location.href = `/roadmaps/${data.id}/`;
        } else {
            const data = await res.json().catch(() => ({}));
            errEl.textContent = data.name?.[0] || data.error || 'Failed to create roadmap.';
            errEl.classList.remove('d-none');
        }
    });
});

function getCsrf() {
    return document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}
