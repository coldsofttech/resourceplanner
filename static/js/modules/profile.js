'use strict';

import {
    apiFetch, showFlash, setPageTitle, escHtml,
    clearErrors, setSubmitting, applyErrors
} from './../main.js';

document.addEventListener('DOMContentLoaded', () => {
    setPageTitle('My Profile');
    initProfileForm();
    initPasswordForm();
    initAvatarUpload();
});

function initProfileForm() {
    const form = document.getElementById('profile-form');
    if (!form) return;

    form.addEventListener('submit', async e => {
        e.preventDefault();
        clearErrors(['first_name', 'last_name'], 'profile-error-banner');
        document.getElementById('profile-success-banner')?.classList.add('d-none');

        const payload = {
            first_name: form.querySelector('[name="first_name"]')?.value?.trim() || '',
            last_name:  form.querySelector('[name="last_name"]')?.value?.trim()  || '',
        };

        const btn   = document.getElementById('profile-submit-btn');
        const label = document.getElementById('profile-submit-label');
        if (btn) { btn.disabled = true; label.textContent = 'Saving…'; }

        try {
            const data = await apiFetch('/api/v1/users/me/update/', {
                method: 'PATCH',
                body: JSON.stringify(payload),
            });
            document.getElementById('profile-success-banner').textContent = 'Profile updated.';
            document.getElementById('profile-success-banner').classList.remove('d-none');
            // Update navbar display name if present
            const navName = document.querySelector('.rp-navbar .nav-link.dropdown-toggle');
            if (navName && data.full_name) {
                navName.childNodes.forEach(n => {
                    if (n.nodeType === Node.TEXT_NODE) n.remove?.();
                });
            }
        } catch (err) {
            if (err?.status === 400) {
                applyErrors(err.data ?? {}, ['first_name', 'last_name'], 'profile-error-banner');
            } else {
                document.getElementById('profile-error-banner').textContent =
                    err?.data?.error || 'Could not save profile.';
                document.getElementById('profile-error-banner').classList.remove('d-none');
            }
        } finally {
            if (btn) { btn.disabled = false; label.textContent = 'Save changes'; }
        }
    });
}

function initPasswordForm() {
    const form = document.getElementById('pwd-form');
    if (!form) return;

    form.addEventListener('submit', async e => {
        e.preventDefault();
        clearErrors(['current_password', 'new_password1', 'new_password2'], 'pwd-error-banner');
        document.getElementById('pwd-success-banner')?.classList.add('d-none');

        const payload = {
            current_password: form.querySelector('[name="current_password"]')?.value || '',
            new_password:     form.querySelector('[name="new_password1"]')?.value   || '',
        };

        const confirm = form.querySelector('[name="new_password2"]')?.value || '';
        if (payload.new_password !== confirm) {
            document.getElementById('new_password2-error').textContent = 'Passwords do not match.';
            document.getElementById('id_new_password2')?.classList.add('is-invalid');
            return;
        }

        const btn   = document.getElementById('pwd-submit-btn');
        const label = document.getElementById('pwd-submit-label');
        if (btn) { btn.disabled = true; label.textContent = 'Updating…'; }

        try {
            await apiFetch('/api/v1/users/me/change_password/', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            document.getElementById('pwd-success-banner').textContent = 'Password updated successfully.';
            document.getElementById('pwd-success-banner').classList.remove('d-none');
            form.reset();
        } catch (err) {
            if (err?.status === 400) {
                const details = err.data?.details || {};
                if (details.new_password) {
                    document.getElementById('new_password1-error').textContent =
                        Array.isArray(details.new_password) ? details.new_password[0] : details.new_password;
                    document.getElementById('id_new_password1')?.classList.add('is-invalid');
                } else {
                    document.getElementById('pwd-error-banner').textContent =
                        err.data?.error || 'Validation failed.';
                    document.getElementById('pwd-error-banner').classList.remove('d-none');
                }
            } else {
                document.getElementById('pwd-error-banner').textContent =
                    err?.data?.error || 'Could not update password.';
                document.getElementById('pwd-error-banner').classList.remove('d-none');
            }
        } finally {
            if (btn) { btn.disabled = false; label.textContent = 'Update password'; }
        }
    });
}

function initAvatarUpload() {
    const fileInput   = document.getElementById('avatar-file');
    const removeBtn   = document.getElementById('remove-avatar-btn');
    const errorEl     = document.getElementById('avatar-error');
    const imgWrap     = document.getElementById('avatar-img-wrap');

    if (!fileInput) return;

    // Show remove button if avatar exists
    const existingImg = imgWrap?.querySelector('.rp-avatar-img');
    if (existingImg) removeBtn?.classList.remove('d-none');

    fileInput.addEventListener('change', async () => {
        const file = fileInput.files[0];
        if (!file) return;

        if (!file.type.startsWith('image/')) {
            if (errorEl) errorEl.textContent = 'Only image files are accepted.';
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            if (errorEl) errorEl.textContent = 'Image must be smaller than 5 MB.';
            return;
        }
        if (errorEl) errorEl.textContent = '';

        const formData = new FormData();
        formData.append('avatar', file);

        try {
            const data = await fetch('/api/v1/users/me/upload_avatar/', {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': getCsrfToken() },
            }).then(r => r.json());

            const newUrl = data.avatar_display;
            if (newUrl && imgWrap) {
                imgWrap.innerHTML = `<img src="${escHtml(newUrl)}" alt="Avatar" class="rp-avatar-img" id="avatar-img">`;
                removeBtn?.classList.remove('d-none');
            }
        } catch (_) {
            if (errorEl) errorEl.textContent = 'Upload failed. Please try again.';
        }
    });

    removeBtn?.addEventListener('click', async () => {
        try {
            const data = await apiFetch('/api/v1/users/me/remove_avatar/', { method: 'DELETE' }).catch(() => ({}));
            // Show initials placeholder
            const initials = document.createElement('div');
            initials.className = 'rp-avatar-initials';
            initials.id = 'avatar-initials';
            initials.textContent = (data.first_name?.[0] || data.email?.[0] || '?').toUpperCase();
            if (imgWrap) {
                imgWrap.innerHTML = '';
                imgWrap.appendChild(initials);
            }
            removeBtn.classList.add('d-none');
        } catch (_) {
            if (errorEl) errorEl.textContent = 'Could not remove avatar.';
        }
    });
}

function getCsrfToken() {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1].trim() : '';
}
