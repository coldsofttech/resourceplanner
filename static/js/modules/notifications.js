'use strict';

const API_BASE = `${location.origin}/api/v1/notifications/`;
const POLL_INTERVAL_MS = 60_000;

let _page = 1;
let _totalPages = 1;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const bell      = document.getElementById('rp-notif-bell');
const badge     = document.getElementById('rp-notif-badge');
const pane      = document.getElementById('rp-notif-pane');
const backdrop  = document.getElementById('rp-notif-backdrop');
const list      = document.getElementById('rp-notif-list');
const markAllBtn = document.getElementById('rp-notif-mark-all');
const closeBtn  = document.getElementById('rp-notif-close');
const prevBtn   = document.getElementById('rp-notif-prev');
const nextBtn   = document.getElementById('rp-notif-next');
const pageInfo  = document.getElementById('rp-notif-page-info');

if (!bell) throw new Error('Notifications bell not found');

// ── helpers ───────────────────────────────────────────────────────────────────

function _csrfToken() {
    return document.cookie.split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))?.split('=')[1] ?? '';
}

function _escHtml(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _timeAgo(isoDate) {
    const diff = Date.now() - new Date(isoDate).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
}

const TYPE_ICONS = {
    comment_mention:   'bi-at',
    project_approved:  'bi-check-circle-fill',
    recharge_forecast: 'bi-receipt',
    recharge_actuals:  'bi-receipt-cutoff',
    project_follow:    'bi-bookmark-heart',
};

async function _apiFetch(url, opts = {}) {
    const resp = await fetch(url, {
        ...opts,
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': _csrfToken(),
            ...(opts.headers ?? {}),
        },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    if (resp.status === 204) return null;
    return resp.json();
}

// ── render ────────────────────────────────────────────────────────────────────

function _renderItem(n) {
    const icon = TYPE_ICONS[n.notification_type] ?? 'bi-bell';
    const readCls = n.is_read ? 'opacity-50' : '';
    const bg = n.is_read ? '' : 'background:var(--rp-row-hover,#f0f4ff);';

    return `
    <div class="rp-notif-item" data-id="${n.id}" style="padding:10px 18px;border-bottom:1px solid var(--rp-border-color,#f0f0f0);cursor:pointer;${bg}"
         onmouseenter="this.style.background='var(--rp-row-hover,#f0f4ff)'"
         onmouseleave="this.style.background='${n.is_read ? '' : 'var(--rp-row-hover,#f0f4ff)'}'">
        <div style="display:flex;gap:10px;align-items:flex-start;">
            <span class="${readCls}" style="flex-shrink:0;font-size:18px;margin-top:2px">
                <i class="bi ${icon}"></i>
            </span>
            <div style="flex:1;min-width:0;">
                <div style="font-size:13px;font-weight:${n.is_read ? '400' : '600'};
                             color:var(--rp-text,#1e293b);word-break:break-word;">
                    ${_escHtml(n.title)}
                </div>
                ${n.body ? `<div style="font-size:12px;color:var(--rp-text-muted);margin-top:2px;word-break:break-word;">${_escHtml(n.body)}</div>` : ''}
                <div style="font-size:11px;color:var(--rp-text-muted);margin-top:3px;">${_timeAgo(n.created_at)}</div>
            </div>
            <button class="btn btn-ghost-icon btn-sm rp-notif-dismiss" data-id="${n.id}"
                    title="Dismiss" style="flex-shrink:0;margin-top:-4px"
                    onclick="event.stopPropagation()">
                <i class="bi bi-x" style="font-size:14px"></i>
            </button>
        </div>
    </div>`;
}

async function loadNotifications(page = 1) {
    _page = page;
    list.innerHTML = '<p class="text-muted small text-center py-4">Loading…</p>';

    try {
        const data = await _apiFetch(`${API_BASE}?page=${page}&page_size=15`);
        _totalPages = data.total_pages ?? 1;
        _updateBadge(data.unread_count ?? 0);

        if (!data.results.length) {
            list.innerHTML = '<p class="text-muted small text-center py-4">No notifications.</p>';
        } else {
            list.innerHTML = data.results.map(_renderItem).join('');
            // click to mark read + navigate
            list.querySelectorAll('.rp-notif-item').forEach(el => {
                el.addEventListener('click', async () => {
                    const id = el.dataset.id;
                    await _apiFetch(`${API_BASE}${id}/`, {
                        method: 'PATCH', body: JSON.stringify({ is_read: true }),
                    }).catch(() => {});
                    const link = el.querySelector('[data-link]')?.dataset.link;
                    const n = data.results.find(r => String(r.id) === id);
                    if (n?.link) { window.location.href = n.link; return; }
                    el.style.background = '';
                    el.querySelector('div[style*="font-weight"]')?.style.setProperty('font-weight', '400');
                    _updateBadge(Math.max(0, (_badgeCount() - 1)));
                });
            });
            // dismiss buttons
            list.querySelectorAll('.rp-notif-dismiss').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.dataset.id;
                    await _apiFetch(`${API_BASE}${id}/`, {
                        method: 'PATCH', body: JSON.stringify({ is_dismissed: true }),
                    }).catch(() => {});
                    btn.closest('.rp-notif-item')?.remove();
                    if (!list.querySelector('.rp-notif-item')) {
                        list.innerHTML = '<p class="text-muted small text-center py-4">No notifications.</p>';
                    }
                    _updateBadge(Math.max(0, (_badgeCount() - 1)));
                });
            });
        }

        prevBtn.disabled = (_page <= 1);
        nextBtn.disabled = (_page >= _totalPages);
        pageInfo.textContent = _totalPages > 1 ? `${_page} / ${_totalPages}` : '';
    } catch {
        list.innerHTML = '<p class="text-muted small text-center py-4">Failed to load.</p>';
    }
}

function _badgeCount() { return parseInt(badge.textContent || '0', 10); }

function _updateBadge(count) {
    if (count > 0) {
        badge.textContent = count > 99 ? '99+' : count;
        badge.classList.remove('d-none');
    } else {
        badge.classList.add('d-none');
    }
}

// ── pane open/close ───────────────────────────────────────────────────────────

function openPane() {
    pane.style.right = '0';
    backdrop.style.display = 'block';
    loadNotifications(1);
}

function closePane() {
    pane.style.right = '-380px';
    backdrop.style.display = 'none';
}

bell.addEventListener('click', () => {
    const isOpen = pane.style.right === '0px';
    isOpen ? closePane() : openPane();
});
closeBtn.addEventListener('click', closePane);
backdrop.addEventListener('click', closePane);

markAllBtn.addEventListener('click', async () => {
    await _apiFetch(`${API_BASE}mark-all-read/`, { method: 'POST' }).catch(() => {});
    _updateBadge(0);
    loadNotifications(_page);
});

prevBtn.addEventListener('click', () => { if (_page > 1) loadNotifications(_page - 1); });
nextBtn.addEventListener('click', () => { if (_page < _totalPages) loadNotifications(_page + 1); });

// ── initial unread count + poll ───────────────────────────────────────────────

async function _pollUnreadCount() {
    try {
        const data = await _apiFetch(`${API_BASE}unread-count/`);
        _updateBadge(data.unread_count ?? 0);
    } catch { /* silent */ }
}

_pollUnreadCount();
setInterval(_pollUnreadCount, POLL_INTERVAL_MS);
