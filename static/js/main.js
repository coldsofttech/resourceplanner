'use strict';

const APP_SUFFIX = 'Resource Planner';

/* CSRF Token Helper */
export function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const cookie = document.cookie.split(';')
        .find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1].trim() : '';
}

/* API Fetch - used across all the modules */
export async function apiFetch(url, options = {}) {
    const defaults = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
    };
    const config = {
        ...defaults,
        ...options,
        headers: {
            ...defaults.headers,
            ...(options.headers || {})
        },
    };
    const res = await fetch(url, config);
    if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
            window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
            return;
        }
        const body = await res.json().catch(() => ({}));
        throw { status: res.status, data: body };
    }
    if (res.status === 204) return null;
    return res.json();
}

/* Flash Message Helper - used across all the modules */
export function showFlash(message, type = 'success') {
    const container = document.querySelector('.rp-messages')
        || (() => {
            const el = document.createElement('div');
            el.className = 'rp-messages px-4 pt-3';
            document.querySelector('.rp-main')?.prepend(el);
            return el;
        })();

    const alertClass = {
        success: 'alert-success',
        error:   'alert-danger',
        warning: 'alert-warning',
        info:    'alert-info',
    }[type] || 'alert-info';

    const alert = document.createElement('div');
    alert.classList.remove('d-none');
    alert.className = `alert ${alertClass} alert-dismissible fade show`;
    alert.setAttribute('role', 'alert');
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    container.appendChild(alert);

    // Auto-dismiss after 4s
    setTimeout(() => {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        bsAlert?.close();
        container.classList.add('d-none');
    }, 4000);
}

/* Format Date Helper */
export function formatDate(isoString) {
    if (!isoString) return '-';
    try {
        return new Date(isoString).toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric',
        });
    } catch {
        return isoString;
    }
}

/* Format Date Time Helper */
export function formatDateTime(isoString) {
    if (!isoString) return '—';
    try {
        return new Date(isoString).toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch {
        return isoString;
    }
}

/* Format Bytes Helper */
export function formatBytes(bytes) {
    if (bytes < 1024)        return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* Page Title Helper */
export function setPageTitle(pageTitle) {
    document.title = pageTitle
        ? `${pageTitle} - ${APP_SUFFIX}`
        : APP_SUFFIX;
}

export function escHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function escAttr(s) {
    return String(s).replace(/'/g, "\\'");
}

/**
 * Extract a numeric PK from the current URL path.
 * @param {string} pattern - URL segment prefix, e.g. 'delivery-teams'
 * @returns {string|null}
 */
export function getPkFromUrl(pattern) {
    const regex = new RegExp(`\\/${pattern}\\/(\\d+)\\/`);
    const match = window.location.pathname.match(regex);
    return match ? match[1] : null;
}

/**
 * Test whether the current URL matches a specific sub-path under a pattern.
 * @param {string} pattern - URL segment prefix, e.g. 'delivery-teams'
 * @param {string} [subPath='edit'] - trailing segment to test for
 * @returns {boolean}
 */
export function isSubPathUrl(pattern, subPath = 'edit') {
    const regex = new RegExp(`\\/${pattern}\\/\\d+\\/${subPath}\\/`);
    return regex.test(window.location.pathname);
}

/**
 * Clear inline field errors and the form error banner.
 * @param {string[]} fields - field names matching id_<field> / <field>-error conventions
 * @param {string} [bannerId='form-error-banner']
 */
export function clearErrors(fields, bannerId = 'form-error-banner') {
    for (const field of fields) {
        document.getElementById(`id_${field}`)?.classList.remove('is-invalid');
        const errEl = document.getElementById(`${field}-error`);
        if (errEl) errEl.textContent = '';
    }
    const banner = document.getElementById(bannerId);
    if (banner) {
        banner.textContent = '';
        banner.classList.add('d-none');
    }
}

/**
 * Toggle a submit button between its normal and loading state.
 * @param {boolean} loading
 * @param {string} [btnId='submit-btn']
 * @param {string} [labelId='submit-label']
 * @param {string} [loadingText='Saving…']
 */
export function setSubmitting(loading, btnId = 'submit-btn', labelId = 'submit-label', loadingText = 'Saving…') {
    const btn   = document.getElementById(btnId);
    const label = document.getElementById(labelId);
    btn.disabled      = loading;
    label.textContent = loading ? loadingText : btn.dataset.originalLabel;
}

/**
 * Flatten a DRF error field value to a single string.
 * @param {string|string[]} value
 * @returns {string}
 */
export function extractFieldMessage(value) {
    if (Array.isArray(value)) {
        return value.map(v => String(v)).join(' ');
    }
    return String(value);
}

/**
 * Show a message in the form error banner.
 * @param {string} msg
 * @param {string} [bannerId='form-error-banner']
 */
export function showBanner(msg, bannerId = 'form-error-banner') {
    const banner = document.getElementById(bannerId);
    if (banner) {
        banner.textContent = msg;
        banner.classList.remove('d-none');
    }
}

/**
 * Apply DRF error response to inline field errors and/or the banner.
 * @param {Object} data - DRF error response body
 * @param {string[]} fields - known field names for this form
 * @param {string} [bannerId='form-error-banner']
 */
export function applyErrors(data, fields, bannerId = 'form-error-banner') {
    let hasFieldError = false;
    const details = data.details;

    if (details && typeof details === 'object' && !Array.isArray(details)) {
        for (const field of fields) {
            if (field in details) {
                const msg = extractFieldMessage(details[field]);
                document.getElementById(`id_${field}`)?.classList.add('is-invalid');
                const errEl = document.getElementById(`${field}-error`);
                if (errEl) errEl.textContent = msg;
                hasFieldError = true;
            }
        }

        if (!hasFieldError) {
            const unhandledMsgs = Object.entries(details)
                .filter(([key]) => !fields.includes(key))
                .map(([, value]) => extractFieldMessage(value));
            if (unhandledMsgs.length) {
                showBanner(unhandledMsgs.join(' '), bannerId);
                return;
            }
        }

        return;
    }

    if (details) {
        const msg = Array.isArray(details)
            ? details.map(v => String(v)).join(' ')
            : String(details);
        showBanner(msg, bannerId);
        return;
    }

    if (data.error) {
        showBanner(String(data.error), bannerId);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (!document.title.includes(APP_SUFFIX)) {
        document.title = document.title
            ? `${document.title} - ${APP_SUFFIX}`
            : APP_SUFFIX;
    }
});