'use strict';

// <wave-view> custom element: live, themeable WaveDrom diagrams for host apps.
//
//   <wave-view source='{signal:[{name:"clk",wave:"p..."}]}'></wave-view>
//   el.source = {signal: [...]};       // object or JSON5 string, re-renders
//
// Colors / fonts come from --wd-* CSS variables (see lib/theme.js). Brick
// definitions live once per page in a hidden sprite shared by all instances.

const json5 = require('json5');

const renderAny = require('./render-any.js');
const createElement = require('./create-element.js');
const theme = require('./theme.js');
const def = require('../skins/default.js');

const skins = {default: def.default};
const sprites = {}; // skin name -> {el, refs}
let counter = 0;

const spritePrefix = (name) => 'wd-' + name + '-';

function acquireSprite (doc, name) {
    let entry = sprites[name];
    if (entry === undefined) {
        entry = sprites[name] = {el: null, refs: 0};
    }
    if (!entry.el || !entry.el.isConnected) {
        entry.el = createElement(theme.renderSprite(skins[name], {idPrefix: spritePrefix(name)}));
        entry.el.setAttribute('data-wd-sprite', name);
        doc.body.appendChild(entry.el);
    }
    entry.refs += 1;
}

function releaseSprite (name) {
    const entry = sprites[name];
    if (entry === undefined) {
        return;
    }
    entry.refs -= 1;
    if (entry.refs <= 0) {
        if (entry.el) {
            entry.el.remove();
        }
        delete sprites[name];
    }
}

const schedule = (typeof requestAnimationFrame === 'function')
    ? requestAnimationFrame
    : (cb) => setTimeout(cb, 16);

// Standalone SVG string from a rendered diagram: copies the referenced bricks
// from the sprite and freezes --wd-* variables into plain values.
function exportSvg (svg) {
    const doc = svg.ownerDocument;
    const clone = svg.cloneNode(true);
    const ids = {};
    clone.querySelectorAll('use').forEach(u => {
        const href = u.getAttribute('href') || u.getAttribute('xlink:href') || '';
        ids[href.replace(/^#/, '')] = true;
    });
    clone.querySelectorAll('[marker-start],[marker-end]').forEach(p => {
        ['marker-start', 'marker-end'].forEach(attr => {
            const m = (p.getAttribute(attr) || '').match(/url\(#([^)]+)\)/);
            if (m) { ids[m[1]] = true; }
        });
    });
    const defs = doc.createElementNS(svg.namespaceURI, 'defs');
    Object.keys(ids).forEach(id => {
        const el = doc.getElementById(id);
        if (el) { defs.appendChild(el.cloneNode(true)); }
    });

    const computed = getComputedStyle(svg);
    const vars = Object.keys(theme.defaults).reduce((res, key) => {
        const val = computed.getPropertyValue('--wd-' + key).trim();
        if (val) { res[key] = val; }
        return res;
    }, {});
    const style = doc.createElementNS(svg.namespaceURI, 'style');
    style.textContent = theme.themeCss(vars, {resolve: true});

    clone.insertBefore(defs, clone.firstChild);
    clone.insertBefore(style, clone.firstChild);
    return new XMLSerializer().serializeToString(clone);
}

const Base = (typeof HTMLElement === 'function') ? HTMLElement : class {};

class WaveView extends Base {

    static get observedAttributes () { return ['source', 'skin']; }

    // make another skin geometry (narrow, lowkey, ...) available by name
    static registerSkin (name, skin) {
        skins[name] = skin;
    }

    constructor () {
        super();
        this._index = counter++;
        this._source = undefined;
        this._pending = false;
        this._skinName = null;
    }

    get source () { return this._source; }

    set source (val) {
        this._source = val;
        this._schedule();
    }

    get svg () { return this.querySelector('svg.wd-root'); }

    toSVG () {
        const svg = this.svg;
        return svg ? exportSvg(svg) : '';
    }

    attributeChangedCallback (name, oldVal, newVal) {
        if (name === 'source') {
            this.source = newVal;
        } else if (name === 'skin' && this.isConnected) {
            this._useSkin(newVal || 'default');
            this._schedule();
        }
    }

    connectedCallback () {
        this._useSkin(this.getAttribute('skin') || 'default');
        this._schedule();
    }

    disconnectedCallback () {
        if (this._skinName) {
            releaseSprite(this._skinName);
            this._skinName = null;
        }
    }

    _useSkin (name) {
        const next = skins[name] ? name : 'default';
        if (next === this._skinName) { return; }
        acquireSprite(this.ownerDocument, next);
        if (this._skinName) { releaseSprite(this._skinName); }
        this._skinName = next;
    }

    _schedule () {
        if (this._pending || !this.isConnected) { return; }
        this._pending = true;
        schedule(() => {
            this._pending = false;
            this.render();
        });
    }

    render () {
        // inline JSON5 text; read late because children may not be parsed
        // yet when the element is upgraded during page load
        if (this._source === undefined && !this.hasAttribute('source')) {
            const text = this.textContent.trim();
            if (text) { this._source = text; }
        }
        if (!this._skinName || this._source === undefined || this._source === null) {
            return;
        }
        try {
            const source = (typeof this._source === 'string')
                ? json5.parse(this._source)
                : this._source;
            const themed = theme.makeThemeable(skins[this._skinName]);
            const res = renderAny(this._index, source, {[this._skinName]: themed}, false, {
                defs: 'sprite',
                idPrefix: spritePrefix(this._skinName)
            });
            this.replaceChildren(createElement(res));
            this.dispatchEvent(new CustomEvent('wave-render', {detail: {source: source}}));
        } catch (err) {
            const box = this.ownerDocument.createElement('div');
            box.className = 'wd-error';
            box.textContent = String(err && err.message || err);
            this.replaceChildren(box);
            this.dispatchEvent(new CustomEvent('wave-error', {detail: err}));
        }
    }
}

function define (tagName) {
    const name = tagName || 'wave-view';
    if (typeof customElements !== 'undefined' && !customElements.get(name)) {
        customElements.define(name, WaveView);
    }
    return WaveView;
}

module.exports = {
    WaveView: WaveView,
    define: define,
    exportSvg: exportSvg
};

/* eslint-env browser */
