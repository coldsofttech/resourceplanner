/* CSRF Token Helper */
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.getAttribute('content');
  const cookie = document.cookie.split(';')
    .find(c => c.trim().startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1].trim() : '';
}

/* API Fetch - used across all the modules */
async function apiFetch(url, options = {}) {
  const defaults = {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
  };
  const config = {
    ...defaults,
    ...options,
    headers: { ...defaults.headers, ...(options.headers || {}) },
  };
  const res = await fetch(url, config);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw { status: res.status, data: body };
  }
  if (res.status === 204) return null;
  return res.json();
}

/* Flash Message Helper - used across all the modules */
function showFlash(message, type = 'success') {
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
  }, 4000);
}