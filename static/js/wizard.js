'use strict';

/**
 * createWizard({ steps, progressId, backId, nextId, saveId, onValidate, onSave })
 *
 * steps:       [{ id: 'step-1', title: 'Step 1' }, ...]
 * progressId:  id of the progress container element
 * backId/nextId/saveId: button element ids
 * onValidate:  (stepIndex) => bool  — return false to block advance
 * onSave:      async () => void     — called when Save is clicked
 */
export function createWizard({ steps, progressId, backId, nextId, saveId, onValidate, onSave }) {
    let current = 0;

    const progressEl = document.getElementById(progressId);
    const backBtn    = document.getElementById(backId);
    const nextBtn    = document.getElementById(nextId);
    const saveBtn    = document.getElementById(saveId);

    function renderProgress() {
        if (!progressEl) return;
        progressEl.innerHTML = steps.map((s, i) => {
            const done   = i < current;
            const active = i === current;
            const cls    = active ? 'active' : done ? 'done' : '';
            const icon   = done ? '<i class="bi bi-check-lg"></i>' : String(i + 1);
            const connector = i < steps.length - 1
                ? '<div class="wizard-step-connector"></div>'
                : '';
            return `
                <div class="wizard-step-indicator ${cls}">
                    <div class="wizard-step-circle">${icon}</div>
                    <span class="wizard-step-label">${s.title}</span>
                </div>${connector}`;
        }).join('');
    }

    function renderPanels() {
        steps.forEach((s, i) => {
            document.getElementById(s.id)?.classList.toggle('d-none', i !== current);
        });
    }

    function renderButtons() {
        backBtn?.classList.toggle('d-none', current === 0);
        nextBtn?.classList.toggle('d-none', current === steps.length - 1);
        saveBtn?.classList.toggle('d-none', current !== steps.length - 1);
    }

    function render() {
        renderProgress();
        renderPanels();
        renderButtons();
    }

    backBtn?.addEventListener('click', () => {
        if (current > 0) { current--; render(); }
    });

    nextBtn?.addEventListener('click', () => {
        if (onValidate && !onValidate(current)) return;
        if (current < steps.length - 1) { current++; render(); }
    });

    saveBtn?.addEventListener('click', () => {
        if (onValidate && !onValidate(current)) return;
        onSave?.();
    });

    return {
        goTo(index) { current = Math.max(0, Math.min(index, steps.length - 1)); render(); },
        get current() { return current; },
        render,
    };
}

/**
 * renderField(container, cfg, inputId)
 *
 * Renders an appropriate form control into container based on config data type.
 * cfg: { label, value, data_type, is_secret, description }
 */
export function renderField(container, cfg, inputId) {
    const { value = '', data_type, is_secret } = cfg;

    if (is_secret) {
        container.innerHTML = `
            <div class="input-group">
                <input type="password"
                       id="${inputId}"
                       class="form-control rp-input"
                       autocomplete="new-password"
                       placeholder="${value ? 'Leave blank to keep existing secret' : 'Enter secret value'}">
                <button class="btn btn-outline-secondary"
                        type="button"
                        data-toggle-secret="${inputId}"
                        title="Show / hide value">
                    <i class="bi bi-eye"></i>
                </button>
            </div>
            <div class="invalid-feedback" id="${inputId}-err"></div>`;
        container.querySelector('[data-toggle-secret]').addEventListener('click', () => {
            const inp  = document.getElementById(inputId);
            const icon = container.querySelector('[data-toggle-secret] i');
            const show = inp.type === 'password';
            inp.type       = show ? 'text' : 'password';
            icon.className = show ? 'bi bi-eye-slash' : 'bi bi-eye';
        });
    } else if (data_type === 'boolean') {
        const cur = value === 'true' ? 'true' : 'false';
        container.innerHTML = `
            <select id="${inputId}" class="form-select rp-input" style="max-width:200px;">
                <option value="true"  ${cur === 'true'  ? 'selected' : ''}>Enabled</option>
                <option value="false" ${cur === 'false' ? 'selected' : ''}>Disabled</option>
            </select>
            <div class="invalid-feedback" id="${inputId}-err"></div>`;
    } else if (data_type === 'integer') {
        container.innerHTML = `
            <input type="number" id="${inputId}"
                   class="form-control rp-input" style="max-width:240px;"
                   step="1" value="${escAttr(value)}" autocomplete="off">
            <div class="invalid-feedback" id="${inputId}-err"></div>`;
    } else if (data_type === 'float') {
        container.innerHTML = `
            <input type="number" id="${inputId}"
                   class="form-control rp-input" style="max-width:240px;"
                   step="any" value="${escAttr(value)}" autocomplete="off">
            <div class="invalid-feedback" id="${inputId}-err"></div>`;
    } else {
        container.innerHTML = `
            <input type="text" id="${inputId}"
                   class="form-control rp-input"
                   value="${escAttr(value)}" autocomplete="off">
            <div class="invalid-feedback" id="${inputId}-err"></div>`;
    }
}

export function getFieldValue(inputId, cfg) {
    const el = document.getElementById(inputId);
    return el ? el.value : '';
}

export function setFieldError(inputId, message) {
    const el  = document.getElementById(inputId);
    const err = document.getElementById(`${inputId}-err`);
    el?.classList.toggle('is-invalid', !!message);
    if (err) err.textContent = message ?? '';
}

export function clearFieldError(inputId) {
    setFieldError(inputId, '');
}

function escAttr(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
