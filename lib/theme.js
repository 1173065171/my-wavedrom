'use strict';

// Themeable skins: geometry comes from a regular skin, colors / fonts / line
// widths come from CSS custom properties (--wd-*), so the host page can match
// its own design tokens and switch light / dark without re-rendering.

const defaults = {
    'fg':              '#000',
    'bg':              '#fff',
    'grid':            '#888',
    'line-width':      '1',
    'line-width-thin': '0.5',
    'font-family':     'Helvetica, Arial, sans-serif',
    'font-size':       '11pt',
    'arc':             '#0041c4',
    'muted':           '#aaa',
    'info':            '#0041c4',
    'warning':         '#f6b900',
    'error':           '#f60000',
    'success':         '#00ab00',
    'data-2':          'var(--wd-bg, #fff)', // plain '=' cells follow the background
    'data-3':          '#ffffb4',
    'data-4':          '#ffe0b9',
    'data-5':          '#b9e0ff',
    'data-6':          '#ccfdfe',
    'data-7':          '#cdfdc5',
    'data-8':          '#f0c1fb',
    'data-9':          '#f5c2c0'
};

const v = (name) => 'var(--wd-' + name + ', ' + defaults[name] + ')';

const rules = () => {
    const line = 'fill:none;stroke-linecap:round;stroke-linejoin:miter;';
    const res = {
        'text': 'fill:' + v('fg') + ';font-family:' + v('font-family') + ';font-size:' + v('font-size') + ';font-style:normal;font-weight:normal;text-align:center',
        '.h1': 'font-size:33pt;font-weight:bold',
        '.h2': 'font-size:27pt;font-weight:bold',
        '.h3': 'font-size:20pt;font-weight:bold',
        '.h4': 'font-size:14pt;font-weight:bold',
        '.h5': 'font-size:11pt;font-weight:bold',
        '.h6': 'font-size:8pt;font-weight:bold',
        '.muted': 'fill:' + v('muted'),
        '.warning': 'fill:' + v('warning'),
        '.error': 'fill:' + v('error'),
        '.info': 'fill:' + v('info'),
        '.success': 'fill:' + v('success'),
        '.wd-line': line + 'stroke:' + v('fg') + ';stroke-width:' + v('line-width'),
        '.wd-line-thin': line + 'stroke:' + v('fg') + ';stroke-width:' + v('line-width-thin'),
        '.wd-line-dotted': line + 'stroke:' + v('fg') + ';stroke-width:' + v('line-width') + ';stroke-dasharray:1,3',
        '.wd-fg-fill': 'fill:' + v('fg') + ';stroke:none',
        '.wd-bg': 'fill:' + v('bg') + ';stroke:none',
        '.wd-gap-bg': 'fill:' + v('bg') + ';fill-opacity:0.8;stroke:none',
        '.wd-label-bg': 'fill:' + v('bg') + ';stroke:none',
        '.wd-grid': 'stroke:' + v('grid') + ';stroke-width:0.5;stroke-dasharray:1,3',
        '.wd-group': 'fill:none;stroke:' + v('info') + ';stroke-width:' + v('line-width'),
        '.wd-arc': 'fill:none;stroke:' + v('arc') + ';stroke-width:' + v('line-width'),
        '.wd-arc-fill': 'fill:' + v('arc') + ';stroke:none',
        '.wd-arc-tee': 'stroke:' + v('arc') + ';stroke-width:2',
        '.wd-arc-error': 'fill:none;stroke:' + v('error') + ';stroke-width:' + v('line-width')
    };
    for (let i = 2; i <= 9; i++) {
        res['.wd-data-' + i] = 'fill:' + v('data-' + i) + ';stroke:none';
    }
    return res;
};

const normalizeVars = (vars) => Object.keys(vars || {}).reduce((res, key) => {
    res[key.replace(/^--wd-/, '')] = String(vars[key]);
    return res;
}, {});

// CSS for themeable diagrams. All selectors are scoped under .wd-root, so the
// stylesheet can live in the page without touching anything else.
// opts.resolve: substitute var() with concrete values (for standalone SVG files)
function themeCss (vars, opts) {
    const theme = normalizeVars(vars);
    const resolve = opts && opts.resolve;
    const r = rules();
    let css = Object.keys(r).map(sel => '.wd-root ' + sel + '{' + r[sel] + '}').join('');
    const custom = Object.keys(theme).filter(key => defaults[key] !== undefined);
    if (resolve) {
        const re = /var\(--wd-([\w-]+), [^;}]*?\)(?=[;}])/g;
        // defaults may point at other variables, so resolve until stable
        while (re.test(css)) {
            css = css.replace(re, (m, name) =>
                (theme[name] !== undefined) ? theme[name] : defaults[name]);
        }
    } else if (custom.length) {
        css = '.wd-root{' + custom.map(key => '--wd-' + key + ':' + theme[key]).join(';') + '}' + css;
    }
    return css;
}

const parseDecls = (body) => body.split(';').reduce((res, decl) => {
    const idx = decl.indexOf(':');
    if (idx > 0) {
        res[decl.slice(0, idx).trim()] = decl.slice(idx + 1).trim();
    }
    return res;
}, {});

function parseSkinClasses (css) {
    const res = {};
    const re = /\.(s\d+)\{([^}]*)\}/g;
    let m;
    while ((m = re.exec(css)) !== null) {
        res[m[1]] = parseDecls(m[2]);
    }
    return res;
}

const isNone = (val) => (val === undefined) || (val === 'none');

// map one legacy sN class to a semantic class, using the def group it lives in
function classify (decls, groupId) {
    const dataMatch = groupId.match(/-([2-9])$/);
    if (!isNone(decls.fill)) {
        if (dataMatch) { return 'wd-data-' + dataMatch[1]; }
        if (groupId === 'gap') { return 'wd-bg'; }
        if (groupId.match(/^arrow/)) { return 'wd-arc-fill'; }
        return 'wd-fg-fill';
    }
    if (groupId.match(/^arrow/)) { return 'wd-arc'; }
    if (!isNone(decls['stroke-dasharray'])) { return 'wd-line-dotted'; }
    if (parseFloat(decls['stroke-width']) <= 0.5) { return 'wd-line-thin'; }
    return 'wd-line';
}

function themeNode (node, groupId, classes) {
    if (!Array.isArray(node)) {
        return node;
    }
    const res = node.map(el => el);
    const attr = res[1];
    if (attr && typeof attr === 'object' && !Array.isArray(attr)) {
        const a = Object.assign({}, attr);
        if (a.class && classes[a.class]) {
            a.class = classify(classes[a.class], groupId);
        }
        if (groupId === 'socket') {
            delete a.style; // geometry probe only, never drawn
        }
        if (res[0] === 'marker') {
            delete a.style;
            a.class = 'wd-arc-fill';
        } else if (a.style && a.style.match(/stroke:#0041c4/)) {
            delete a.style;
            a.class = 'wd-arc-tee';
        }
        res[1] = a;
    }
    for (let i = 1; i < res.length; i++) {
        if (Array.isArray(res[i])) {
            res[i] = themeNode(res[i], groupId, classes);
        }
    }
    return res;
}

const themeCache = new WeakMap();

// Convert a regular skin (JsonML) into a themeable one: semantic classes in
// <defs>, scoped CSS with --wd-* variables, root marked with class wd-root.
function makeThemeable (skin, vars) {
    const cached = vars ? undefined : themeCache.get(skin);
    if (cached) {
        return cached;
    }
    const classes = parseSkinClasses(skin[2][2] || '');
    const defs = skin[3].map((group, i) => {
        if (i === 0) {
            return group;
        }
        const groupId = (group[1] && group[1].id) || '';
        return themeNode(group, groupId, classes);
    });
    const res = [
        skin[0],
        Object.assign({}, skin[1], {class: 'wd-root'}),
        ['style', {type: 'text/css'}, themeCss(vars)],
        defs
    ].concat(skin.slice(4));
    if (!vars) {
        themeCache.set(skin, res);
    }
    return res;
}

const prefixCache = new WeakMap();

// prefix every id inside <defs> (references are prefixed by the renderers)
function prefixDefs (defs, prefix) {
    if (!prefix) {
        return defs;
    }
    let byPrefix = prefixCache.get(defs);
    if (byPrefix === undefined) {
        byPrefix = {};
        prefixCache.set(defs, byPrefix);
    }
    if (byPrefix[prefix]) {
        return byPrefix[prefix];
    }
    const walk = (node) => {
        if (!Array.isArray(node)) {
            return node;
        }
        return node.map((el, i) => {
            if (i === 1 && el && typeof el === 'object' && !Array.isArray(el) && el.id !== undefined) {
                return Object.assign({}, el, {id: prefix + el.id});
            }
            return walk(el);
        });
    };
    byPrefix[prefix] = walk(defs);
    return byPrefix[prefix];
}

// Hidden <svg> carrying the stylesheet and all brick definitions once per
// page; diagrams rendered with {defs: 'sprite'} reference it.
function renderSprite (skin, opts) {
    const options = opts || {};
    const themed = makeThemeable(skin, options.vars);
    return ['svg', {
        class: 'wd-root wd-sprite',
        xmlns: 'http://www.w3.org/2000/svg',
        'xmlns:xlink': 'http://www.w3.org/1999/xlink',
        'aria-hidden': 'true',
        width: 0,
        height: 0,
        style: 'position:absolute;width:0;height:0;overflow:hidden'
    },
    themed[2],
    prefixDefs(themed[3], options.idPrefix || '')
    ];
}

module.exports = {
    defaults: defaults,
    themeCss: themeCss,
    makeThemeable: makeThemeable,
    prefixDefs: prefixDefs,
    renderSprite: renderSprite
};
