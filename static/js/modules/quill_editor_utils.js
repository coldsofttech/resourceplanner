'use strict';

// ── Constants ──────────────────────────────────────────────────────────────────
export const FONTS = ['Arial', 'Courier New', 'Georgia', 'Times New Roman', 'Trebuchet MS', 'Verdana'];
export const SIZES = ['10px', '11px', '12px', '13px', '14px', '16px', '18px', '20px', '24px', '28px', '32px'];

// ── Register Quill formats (runs once at module load) ─────────────────────────
const FontAttr = Quill.import('attributors/style/font');
FontAttr.whitelist = FONTS;
Quill.register(FontAttr, true);

const SizeAttr = Quill.import('attributors/style/size');
SizeAttr.whitelist = SIZES;
Quill.register(SizeAttr, true);

// Double-strikethrough blot
const Inline = Quill.import('blots/inline');
class DoubleStrikeBlot extends Inline {
    static create() { return super.create(); }
    static formats() { return true; }
}
DoubleStrikeBlot.blotName = 'double-strike';
DoubleStrikeBlot.tagName  = 'span';
DoubleStrikeBlot.className = 'ql-double-strike';
Quill.register(DoubleStrikeBlot);

// ── Toolbar container ─────────────────────────────────────────────────────────
export const TOOLBAR_CONTAINER = [
    [{ font: FONTS }, { size: SIZES }],
    [{ header: [1, 2, 3, false] }],
    ['bold', 'italic', 'underline', 'strike', 'double-strike'],
    [{ script: 'sub' }, { script: 'super' }],
    [{ color: [] }, { background: [] }],
    [{ align: [] }],
    [{ list: 'ordered' }, { list: 'bullet' }, { indent: '-1' }, { indent: '+1' }],
    ['blockquote', 'code-block', 'code'],
    ['link', 'image', 'table', 'bi-icon'],
    ['clean'],
];

// ── Tooltip map ───────────────────────────────────────────────────────────────
export const TOOLBAR_TIPS = {
    'ql-bold':          'Bold (Ctrl+B)',
    'ql-italic':        'Italic (Ctrl+I)',
    'ql-underline':     'Underline (Ctrl+U)',
    'ql-strike':        'Strikethrough',
    'ql-double-strike': 'Double Strikethrough',
    'ql-blockquote':    'Block Quote',
    'ql-code-block':    'Code Block',
    'ql-code':          'Inline Code',
    'ql-link':          'Insert Link',
    'ql-image':         'Insert Image',
    'ql-table':         'Insert Table',
    'ql-bi-icon':       'Insert Bootstrap Icon',
    'ql-clean':         'Clear Formatting',
    'script-sub':       'Subscript',
    'script-super':     'Superscript',
    'list-ordered':     'Numbered List',
    'list-bullet':      'Bullet List',
    'indent--1':        'Decrease Indent',
    'indent-+1':        'Increase Indent',
    'header-1':         'Heading 1',
    'header-2':         'Heading 2',
    'header-3':         'Heading 3',
    'header-false':     'Normal Text',
    'align-':           'Align Left',
    'align-center':     'Align Centre',
    'align-right':      'Align Right',
    'align-justify':    'Justify',
    'picker-ql-font':       'Font Family',
    'picker-ql-size':       'Font Size',
    'picker-ql-header':     'Heading Style',
    'picker-ql-align':      'Text Alignment',
    'picker-ql-color':      'Text Color',
    'picker-ql-background': 'Highlight Color',
};

// ── Bootstrap Icons list ──────────────────────────────────────────────────────
export const BI_ICONS = [
    // Arrows & navigation
    'arrow-left','arrow-right','arrow-up','arrow-down',
    'arrow-left-circle','arrow-right-circle','arrow-up-circle','arrow-down-circle',
    'arrow-left-circle-fill','arrow-right-circle-fill','arrow-up-circle-fill','arrow-down-circle-fill',
    'arrow-clockwise','arrow-counterclockwise','arrow-repeat','arrows','arrows-collapse','arrows-expand',
    'arrow-bar-left','arrow-bar-right','arrow-bar-up','arrow-bar-down',
    'chevron-left','chevron-right','chevron-up','chevron-down',
    'chevron-double-left','chevron-double-right','chevron-double-up','chevron-double-down',
    'caret-left','caret-right','caret-up','caret-down',
    'caret-left-fill','caret-right-fill','caret-up-fill','caret-down-fill',
    // Status & alerts
    'check','check-lg','check2','check2-all','check2-circle','check2-square',
    'check-circle','check-circle-fill','check-square','check-square-fill',
    'x','x-lg','x-circle','x-circle-fill','x-square','x-square-fill','x-octagon','x-octagon-fill',
    'exclamation','exclamation-lg','exclamation-circle','exclamation-circle-fill',
    'exclamation-triangle','exclamation-triangle-fill','exclamation-diamond','exclamation-diamond-fill',
    'exclamation-octagon','exclamation-octagon-fill','exclamation-square','exclamation-square-fill',
    'info','info-lg','info-circle','info-circle-fill','info-square','info-square-fill',
    'question','question-lg','question-circle','question-circle-fill',
    'question-diamond','question-diamond-fill','question-octagon','question-octagon-fill',
    // Interface
    'plus','plus-lg','plus-circle','plus-circle-fill','plus-square','plus-square-fill',
    'dash','dash-lg','dash-circle','dash-circle-fill','dash-square','dash-square-fill',
    'three-dots','three-dots-vertical',
    'grid','grid-fill','grid-3x3','grid-3x3-gap','grid-3x3-gap-fill',
    'list','list-ul','list-ol','list-check','list-task','list-nested','list-stars',
    'search','zoom-in','zoom-out',
    'filter','filter-circle','filter-left','funnel','funnel-fill',
    'sort-down','sort-up','sort-alpha-down','sort-alpha-up','sort-numeric-down','sort-numeric-up',
    'toggles','toggles2','toggle-on','toggle-off',
    'sliders','sliders2','sliders2-vertical',
    'gear','gear-fill','gear-wide','gear-wide-connected',
    'wrench','wrench-adjustable','tools',
    'cursor','cursor-fill','cursor-text','input-cursor','input-cursor-text',
    // Communication
    'envelope','envelope-fill','envelope-open','envelope-open-fill',
    'envelope-check','envelope-check-fill','envelope-plus','envelope-plus-fill',
    'envelope-x','envelope-x-fill','envelope-paper','envelope-paper-fill',
    'chat','chat-fill','chat-dots','chat-dots-fill',
    'chat-left','chat-left-fill','chat-left-text','chat-left-text-fill',
    'chat-right','chat-right-fill','chat-right-text','chat-right-text-fill',
    'chat-square','chat-square-fill','chat-square-text','chat-square-text-fill',
    'send','send-fill','send-check','send-check-fill','send-plus','send-plus-fill',
    'telephone','telephone-fill','telephone-forward','telephone-inbound','telephone-outbound',
    'phone','phone-fill','phone-vibrate',
    'megaphone','megaphone-fill',
    'bell','bell-fill','bell-slash','bell-slash-fill',
    'at','hash','rss','rss-fill',
    // People
    'person','person-fill','person-circle','person-badge','person-badge-fill',
    'person-check','person-check-fill','person-dash','person-dash-fill',
    'person-plus','person-plus-fill','person-x','person-x-fill',
    'person-gear','person-lock','person-heart','person-lines-fill',
    'people','people-fill',
    // Files & documents
    'file','file-fill','file-text','file-text-fill','file-code','file-code-fill',
    'file-image','file-image-fill','file-pdf','file-pdf-fill',
    'file-earmark','file-earmark-fill','file-earmark-text','file-earmark-text-fill',
    'file-earmark-code','file-earmark-code-fill','file-earmark-image','file-earmark-image-fill',
    'file-earmark-pdf','file-earmark-pdf-fill','file-earmark-excel','file-earmark-excel-fill',
    'file-earmark-word','file-earmark-word-fill','file-earmark-ppt','file-earmark-ppt-fill',
    'file-earmark-zip','file-earmark-zip-fill','file-earmark-check','file-earmark-check-fill',
    'file-earmark-plus','file-earmark-plus-fill','file-earmark-minus','file-earmark-minus-fill',
    'file-earmark-x','file-earmark-x-fill','file-earmark-lock','file-earmark-lock-fill',
    'folder','folder-fill','folder2','folder2-open',
    'folder-plus','folder-minus','folder-check','folder-x',
    'clipboard','clipboard-fill','clipboard-check','clipboard-check-fill',
    'clipboard-data','clipboard-plus','clipboard-minus','clipboard-x',
    // Media
    'image','image-fill','image-alt',
    'camera','camera-fill','camera-video','camera-video-fill',
    'play','play-fill','play-circle','play-circle-fill','play-btn','play-btn-fill',
    'pause','pause-fill','pause-circle','pause-circle-fill',
    'stop','stop-fill','stop-circle','stop-circle-fill',
    'skip-forward','skip-forward-fill','skip-backward','skip-backward-fill',
    'record','record-fill','record2','record2-fill',
    'volume-up','volume-down','volume-mute','volume-off',
    'music-note','music-note-beamed','music-note-list',
    'mic','mic-fill','mic-mute','mic-mute-fill',
    'headphones','headset','speaker','speaker-fill',
    // Layout
    'layout-sidebar','layout-sidebar-reverse',
    'layout-text-sidebar','layout-text-window','layout-text-window-reverse',
    'layout-three-columns','columns','columns-gap',
    'table','border','border-all','fullscreen','fullscreen-exit',
    // Business & finance
    'briefcase','briefcase-fill','building','bank',
    'currency-dollar','currency-euro','currency-pound','currency-bitcoin','currency-exchange',
    'cash','cash-coin','cash-stack','wallet','wallet-fill','wallet2',
    'credit-card','credit-card-fill','credit-card-2-front','credit-card-2-back',
    'receipt','bag','bag-fill','bag-check','bag-check-fill',
    'cart','cart-fill','cart-check','cart-plus','shop','shop-window',
    'bar-chart','bar-chart-fill','bar-chart-line','bar-chart-line-fill',
    'pie-chart','pie-chart-fill','graph-up','graph-down','graph-up-arrow','graph-down-arrow',
    // Calendar & time
    'calendar','calendar-fill','calendar-date','calendar-check','calendar-event',
    'calendar-minus','calendar-plus','calendar-range','calendar-week',
    'clock','clock-fill','clock-history','alarm','alarm-fill',
    'stopwatch','stopwatch-fill','hourglass','hourglass-split',
    // Location
    'map','map-fill','geo','geo-fill','geo-alt','geo-alt-fill','compass','compass-fill',
    'pin','pin-fill','pin-map','pin-map-fill',
    'house','house-fill','house-door','house-door-fill',
    // Tech & devices
    'laptop','laptop-fill','display','display-fill','tv','tv-fill',
    'phone-landscape','phone-landscape-fill','smartwatch',
    'keyboard','keyboard-fill','mouse','mouse-fill','printer','printer-fill',
    'server','database','database-fill','hdd','hdd-fill','hdd-network','hdd-stack',
    'cpu','cpu-fill','memory','router','router-fill',
    'wifi','wifi-off','wifi-1','wifi-2','bluetooth',
    // Security
    'shield','shield-fill','shield-check','shield-exclamation','shield-lock','shield-lock-fill',
    'shield-plus','shield-minus','shield-x','shield-slash','shield-shaded',
    'lock','lock-fill','unlock','unlock-fill',
    'key','key-fill','fingerprint',
    'eye','eye-fill','eye-slash','eye-slash-fill',
    // Editing & text
    'pencil','pencil-fill','pencil-square','pen','pen-fill',
    'type','type-bold','type-italic','type-underline','type-strikethrough',
    'type-h1','type-h2','type-h3',
    'fonts','text-paragraph','text-center','text-left','text-right',
    'text-indent-left','text-indent-right',
    'eraser','eraser-fill','scissors','paperclip','link','link-45deg',
    'code','code-slash','code-square','braces','braces-asterisk',
    'markdown','markdown-fill',
    // Actions
    'download','upload','save','save-fill','save2','save2-fill',
    'share','share-fill','forward','forward-fill',
    'reply','reply-fill','reply-all','reply-all-fill',
    'trash','trash-fill','trash2','trash2-fill','trash3','trash3-fill',
    'archive','archive-fill','power','download','upload',
    // Social & misc
    'heart','heart-fill','heart-half','heart-pulse','heart-pulse-fill',
    'star','star-fill','star-half','stars',
    'bookmark','bookmark-fill','bookmark-plus','bookmark-check','bookmark-star','bookmark-x',
    'tag','tag-fill','tags','tags-fill','flag','flag-fill',
    'trophy','trophy-fill','award','gem','gift','gift-fill',
    'emoji-smile','emoji-frown','emoji-angry','emoji-laughing',
    'emoji-heart-eyes','emoji-neutral','emoji-wink','emoji-sunglasses',
    'robot','bug','bug-fill','globe','globe2',
    'sun','sun-fill','moon','moon-fill','moon-stars','moon-stars-fill',
    'cloud','cloud-fill','cloud-download','cloud-upload','cloud-check',
    'lightning','lightning-fill','lightning-charge','lightning-charge-fill',
    'tree','tree-fill','palette','palette-fill','palette2','brush','brush-fill',
    'journal','journal-text','journal-code','journals',
    'newspaper','book','book-fill','bookmarks','bookmarks-fill',
    'collection','collection-fill','collection-play',
    'github','gitlab','slack','google','twitter','twitter-x','youtube','linkedin','paypal',
    'lightbulb','lightbulb-fill','lightbulb-off','lightbulb-off-fill',
    'magic','patch-check','patch-check-fill','patch-exclamation','patch-exclamation-fill',
    'circle','circle-fill','square','square-fill','triangle','triangle-fill',
    'diamond','diamond-fill','hexagon','hexagon-fill','octagon','octagon-fill',
    'cup','cup-fill','cup-hot','cup-hot-fill',
];

// ── Init toolbar tooltips ─────────────────────────────────────────────────────
export function initToolbarTooltips(quill) {
    const tb = quill.container.previousElementSibling;
    if (!tb?.classList?.contains('ql-toolbar')) return;

    tb.querySelectorAll('button').forEach(btn => {
        const cls = [...btn.classList].find(c => c.startsWith('ql-') && c !== 'ql-active');
        if (!cls) return;
        const val = btn.getAttribute('value') ?? '';
        const key = cls.replace('ql-', '');
        const tip = TOOLBAR_TIPS[`${key}-${val}`] ?? TOOLBAR_TIPS[cls];
        if (tip) btn.setAttribute('title', tip);
    });

    tb.querySelectorAll('.ql-picker').forEach(picker => {
        const cls = [...picker.classList].find(
            c => c.startsWith('ql-') && !['ql-picker','ql-expanded','ql-active','ql-color-picker','ql-icon-picker'].includes(c)
        );
        const label = picker.querySelector('.ql-picker-label');
        if (label && cls) label.setAttribute('title', TOOLBAR_TIPS[`picker-${cls}`] ?? '');
    });
}

// ── Inject Bootstrap Icon HTML into custom toolbar buttons ────────────────────
export function injectCustomButtonIcons(quill) {
    const tb = quill.container.previousElementSibling;
    if (!tb) return;
    const ds  = tb.querySelector('.ql-double-strike');
    const tbl = tb.querySelector('.ql-table');
    const bi  = tb.querySelector('.ql-bi-icon');
    if (ds)  ds.innerHTML  = '<s style="text-decoration-style:double;font-style:normal">S</s>';
    if (tbl) tbl.innerHTML = '<i class="bi bi-table"></i>';
    if (bi)  bi.innerHTML  = '<i class="bi bi-bootstrap"></i>';
}

// ── Add custom format handlers after Quill creation ───────────────────────────
export function addCustomHandlers(quill) {
    quill.getModule('toolbar').addHandler('double-strike', () => {
        const fmt = quill.getFormat();
        quill.format('double-strike', !fmt['double-strike'], 'user');
    });
}

// ── Table picker ──────────────────────────────────────────────────────────────
const TP_ROWS = 8, TP_COLS = 8;
let _tablePicker = null;

function _ensureTablePicker() {
    if (_tablePicker) return _tablePicker;

    _tablePicker = document.createElement('div');
    _tablePicker.className = 'ql-table-picker';
    _tablePicker.style.cssText =
        'position:fixed;z-index:9999;background:#fff;border:1px solid var(--rp-border-color,#e5e7eb);' +
        'border-radius:8px;padding:10px;box-shadow:0 4px 16px rgba(0,0,0,.12);display:none;';

    const grid  = document.createElement('div');
    grid.id     = 'ql-tp-grid';
    grid.style.cssText = `display:grid;grid-template-columns:repeat(${TP_COLS},22px);gap:2px;`;

    const label = document.createElement('div');
    label.id    = 'ql-tp-label';
    label.style.cssText = 'text-align:center;font-size:11px;color:var(--rp-text-muted);margin-top:6px;';
    label.textContent = 'Hover to select';

    for (let r = 1; r <= TP_ROWS; r++) {
        for (let c = 1; c <= TP_COLS; c++) {
            const cell = document.createElement('div');
            cell.dataset.r = r; cell.dataset.c = c;
            cell.style.cssText = 'width:20px;height:20px;border:1px solid #dee2e6;border-radius:2px;cursor:pointer;';
            cell.addEventListener('mouseenter', () => {
                const nr = +cell.dataset.r, nc = +cell.dataset.c;
                grid.querySelectorAll('[data-r]').forEach(cl => {
                    const ir = +cl.dataset.r, ic = +cl.dataset.c;
                    cl.style.background = ir <= nr && ic <= nc ? 'rgba(99,102,241,.25)' : '';
                    cl.style.borderColor = ir <= nr && ic <= nc ? '#818cf8' : '#dee2e6';
                });
                label.textContent = `${nr} × ${nc} table`;
            });
            cell.addEventListener('click', () => {
                _insertTable(_tablePicker._quill, +cell.dataset.r, +cell.dataset.c);
                _tablePicker.style.display = 'none';
            });
            grid.appendChild(cell);
        }
    }

    _tablePicker.appendChild(grid);
    _tablePicker.appendChild(label);
    document.body.appendChild(_tablePicker);

    document.addEventListener('click', e => {
        if (_tablePicker.style.display !== 'none' && !_tablePicker.contains(e.target)) {
            _tablePicker.style.display = 'none';
        }
    }, true);

    return _tablePicker;
}

function _insertTable(quill, rows, cols) {
    let html = '<table style="border-collapse:collapse;width:100%;margin:8px 0"><tbody>';
    for (let r = 0; r < rows; r++) {
        html += '<tr>';
        for (let c = 0; c < cols; c++) {
            html += '<td style="border:1px solid #dee2e6;padding:6px 10px;min-width:60px">&nbsp;</td>';
        }
        html += '</tr>';
    }
    html += '</tbody></table><p><br></p>';
    const idx = (quill.getSelection(true) || { index: quill.getLength() }).index;
    quill.clipboard.dangerouslyPasteHTML(idx, html);
}

export function setupTablePicker(quill) {
    const picker = _ensureTablePicker();
    const tb     = quill.container.previousElementSibling;
    const btn    = tb?.querySelector('.ql-table');
    if (!btn) return;

    quill.getModule('toolbar').addHandler('table', () => {
        picker._quill = quill;
        const rect = btn.getBoundingClientRect();
        picker.style.left = `${rect.left}px`;
        picker.style.top  = `${rect.bottom + 4}px`;
        // reset highlight
        picker.querySelectorAll('[data-r]').forEach(cl => {
            cl.style.background = ''; cl.style.borderColor = '#dee2e6';
        });
        picker.querySelector('#ql-tp-label').textContent = 'Hover to select';
        picker.style.display = picker.style.display === 'none' ? 'block' : 'none';
    });
}

// ── Bootstrap Icon picker ─────────────────────────────────────────────────────
let _iconPicker = null;

function _ensureIconPicker() {
    if (_iconPicker) return _iconPicker;

    _iconPicker = document.createElement('div');
    _iconPicker.style.cssText =
        'position:fixed;z-index:9999;background:#fff;border:1px solid var(--rp-border-color,#e5e7eb);' +
        'border-radius:10px;padding:12px;box-shadow:0 4px 20px rgba(0,0,0,.14);display:none;' +
        'width:320px;max-height:360px;display:none;flex-direction:column;gap:8px;';

    const searchWrap = document.createElement('div');
    searchWrap.style.cssText = 'position:relative;';
    const searchInput = document.createElement('input');
    searchInput.type = 'search';
    searchInput.placeholder = 'Search icons…';
    searchInput.style.cssText = 'width:100%;padding:6px 10px 6px 28px;border:1px solid var(--rp-border-color,#e5e7eb);border-radius:6px;font-size:12px;outline:none;';
    const searchIcon = document.createElement('i');
    searchIcon.className = 'bi bi-search';
    searchIcon.style.cssText = 'position:absolute;left:8px;top:50%;transform:translateY(-50%);color:var(--rp-text-muted);font-size:12px;pointer-events:none;';
    searchWrap.appendChild(searchIcon);
    searchWrap.appendChild(searchInput);

    const grid = document.createElement('div');
    grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(36px,1fr));gap:4px;overflow-y:auto;flex:1;padding-right:2px;';

    function renderIcons(filter) {
        const filtered = filter
            ? BI_ICONS.filter(n => n.includes(filter.toLowerCase()))
            : BI_ICONS;
        grid.innerHTML = '';
        filtered.slice(0, 200).forEach(name => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.title = name;
            btn.style.cssText =
                'width:36px;height:36px;border:1px solid transparent;border-radius:6px;background:none;' +
                'cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px;transition:.1s;';
            btn.innerHTML = `<i class="bi bi-${name}"></i>`;
            btn.addEventListener('mouseenter', () => { btn.style.background = 'var(--rp-row-hover,#f0f4ff)'; btn.style.borderColor = '#a5b4fc'; });
            btn.addEventListener('mouseleave', () => { btn.style.background = ''; btn.style.borderColor = 'transparent'; });
            btn.addEventListener('click', () => {
                const q = _iconPicker._quill;
                if (!q) return;
                const idx = (q.getSelection(true) || { index: q.getLength() }).index;
                q.clipboard.dangerouslyPasteHTML(idx, `<i class="bi bi-${name}"></i>`);
                _iconPicker.style.display = 'none';
            });
            grid.appendChild(btn);
        });
        if (!filtered.length) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--rp-text-muted);font-size:12px;padding:16px 0">No icons found</div>';
        }
    }

    searchInput.addEventListener('input', () => renderIcons(searchInput.value));
    renderIcons('');

    _iconPicker.appendChild(searchWrap);
    _iconPicker.appendChild(grid);
    document.body.appendChild(_iconPicker);

    document.addEventListener('click', e => {
        if (_iconPicker.style.display !== 'none' && !_iconPicker.contains(e.target)) {
            _iconPicker.style.display = 'none';
        }
    }, true);

    return _iconPicker;
}

export function setupIconPicker(quill) {
    const picker = _ensureIconPicker();
    const tb     = quill.container.previousElementSibling;
    const btn    = tb?.querySelector('.ql-bi-icon');
    if (!btn) return;

    quill.getModule('toolbar').addHandler('bi-icon', () => {
        picker._quill = quill;
        const rect = btn.getBoundingClientRect();
        const isHidden = picker.style.display === 'none' || picker.style.display === '';
        picker.style.display = isHidden ? 'flex' : 'none';
        if (isHidden) {
            picker.style.left = `${Math.max(4, rect.right - 320)}px`;
            picker.style.top  = `${rect.bottom + 4}px`;
        }
    });
}

// ── Source mode manager (Rich | HTML | Markdown) ──────────────────────────────
export class SourceModeManager {
    constructor({ quill, richEl, htmlEl, mdEl, tabsEl }) {
        this.quill  = quill;
        this.richEl = richEl;
        this.htmlEl = htmlEl;
        this.mdEl   = mdEl;
        this.mode   = 'rich';

        if (tabsEl) {
            tabsEl.querySelectorAll('[data-mode]').forEach(btn => {
                btn.addEventListener('click', () => this.switchTo(btn.dataset.mode));
            });
        }
    }

    switchTo(newMode) {
        if (newMode === this.mode) return;

        // Capture current HTML before switching away
        const html = this.getContent();

        // Hide all panels
        this.richEl.classList.add('d-none');
        this.htmlEl.classList.add('d-none');
        this.mdEl?.classList.add('d-none');

        if (newMode === 'rich') {
            this.quill.root.innerHTML = html;
            this.richEl.classList.remove('d-none');

        } else if (newMode === 'html') {
            this.htmlEl.value = html;
            this.htmlEl.classList.remove('d-none');
            this.htmlEl.focus();

        } else if (newMode === 'markdown') {
            if (this.mdEl) {
                // HTML → Markdown via TurndownService (CDN) if available
                if (window.TurndownService) {
                    const td = new TurndownService({
                        headingStyle: 'atx',
                        bulletListMarker: '-',
                        codeBlockStyle: 'fenced',
                    });
                    this.mdEl.value = td.turndown(html);
                } else {
                    this.mdEl.value = html;
                }
                this.mdEl.classList.remove('d-none');
                this.mdEl.focus();
            }
        }

        this.mode = newMode;
        this._syncTabs();
    }

    _syncTabs() {
        document.querySelectorAll('[data-mode]').forEach(btn => {
            const isActive = btn.dataset.mode === this.mode;
            btn.classList.toggle('active', isActive);
            // Bootstrap btn-outline: swap active state
            if (isActive) {
                btn.classList.remove('btn-outline-secondary');
                btn.classList.add('btn-secondary');
            } else {
                btn.classList.remove('btn-secondary');
                btn.classList.add('btn-outline-secondary');
            }
        });
    }

    getContent() {
        if (this.mode === 'rich') return this.quill.root.innerHTML;
        if (this.mode === 'html') return this.htmlEl.value;
        if (this.mode === 'markdown') {
            if (this.mdEl && window.marked) {
                return window.marked.parse(this.mdEl.value || '');
            }
            return this.mdEl?.value || '';
        }
        return '';
    }
}
