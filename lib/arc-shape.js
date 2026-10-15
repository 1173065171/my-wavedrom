'use strict';

const arrow = (prefix, both) => {
    const res = {class: 'wd-arc', fill: 'none', stroke: '#0041c4', 'stroke-width': 1, 'marker-end': 'url(#' + prefix + 'arrowhead)'};
    if (both) {
        res['marker-start'] = 'url(#' + prefix + 'arrowtail)';
    }
    return res;
};

function arcShape (Edge, from, to, idPrefix) {
    const prefix = idPrefix || '';
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    let lx = ((from.x + to.x) / 2);
    const ly = ((from.y + to.y) / 2);
    let d;
    let style;
    switch (Edge.shape) {
    case '-'  : {
        break;
    }
    case '~'  : {
        d = ('M ' + from.x + ',' + from.y + ' c ' + (0.7 * dx) + ', 0 ' + (0.3 * dx) + ', ' + dy + ' ' + dx + ', ' + dy);
        break;
    }
    case '-~' : {
        d = ('M ' + from.x + ',' + from.y + ' c ' + (0.7 * dx) + ', 0 ' +         dx + ', ' + dy + ' ' + dx + ', ' + dy);
        if (Edge.label) { lx = (from.x + (to.x - from.x) * 0.75); }
        break;
    }
    case '~-' : {
        d = ('M ' + from.x + ',' + from.y + ' c ' + 0          + ', 0 ' + (0.3 * dx) + ', ' + dy + ' ' + dx + ', ' + dy);
        if (Edge.label) { lx = (from.x + (to.x - from.x) * 0.25); }
        break;
    }
    case '-|' : {
        d = ('m ' + from.x + ',' + from.y + ' ' + dx + ',0 0,' + dy);
        if (Edge.label) { lx = to.x; }
        break;
    }
    case '|-' : {
        d = ('m ' + from.x + ',' + from.y + ' 0,' + dy + ' ' + dx + ',0');
        if (Edge.label) { lx = from.x; }
        break;
    }
    case '-|-': {
        d = ('m ' + from.x + ',' + from.y + ' ' + (dx / 2) + ',0 0,' + dy + ' ' + (dx / 2) + ',0');
        break;
    }
    case '->' : {
        style = arrow(prefix);
        break;
    }
    case '~>' : {
        style = arrow(prefix);
        d = ('M ' + from.x + ',' + from.y + ' ' + 'c ' + (0.7 * dx) + ', 0 ' + 0.3 * dx + ', ' + dy + ' ' + dx + ', ' + dy);
        break;
    }
    case '-~>': {
        style = arrow(prefix);
        d = ('M ' + from.x + ',' + from.y + ' ' + 'c ' + (0.7 * dx) + ', 0 ' +     dx + ', ' + dy + ' ' + dx + ', ' + dy);
        if (Edge.label) { lx = (from.x + (to.x - from.x) * 0.75); }
        break;
    }
    case '~->': {
        style = arrow(prefix);
        d = ('M ' + from.x + ',' + from.y + ' ' + 'c ' + 0      + ', 0 ' + (0.3 * dx) + ', ' + dy + ' ' + dx + ', ' + dy);
        if (Edge.label) { lx = (from.x + (to.x - from.x) * 0.25); }
        break;
    }
    case '-|>' : {
        style = arrow(prefix);
        d = ('m ' + from.x + ',' + from.y + ' ' + dx + ',0 0,' + dy);
        if (Edge.label) { lx = to.x; }
        break;
    }
    case '|->' : {
        style = arrow(prefix);
        d = ('m ' + from.x + ',' + from.y + ' 0,' + dy + ' ' + dx + ',0');
        if (Edge.label) { lx = from.x; }
        break;
    }
    case '-|->': {
        style = arrow(prefix);
        d = ('m ' + from.x + ',' + from.y + ' ' + (dx / 2) + ',0 0,' + dy + ' ' + (dx / 2) + ',0');
        break;
    }
    case '<->' : {
        style = arrow(prefix, true);
        break;
    }
    case '<~>' : {
        style = arrow(prefix, true);
        d = ('M ' + from.x + ',' + from.y + ' ' + 'c ' + (0.7 * dx) + ', 0 ' + (0.3 * dx) + ', ' + dy + ' ' + dx + ', ' + dy);
        break;
    }
    case '<-~>': {
        style = arrow(prefix, true);
        d = ('M ' + from.x + ',' + from.y + ' ' + 'c ' + (0.7 * dx) + ', 0 ' +     dx + ', ' + dy + ' ' + dx + ', ' + dy);
        if (Edge.label) { lx = (from.x + (to.x - from.x) * 0.75); }
        break;
    }
    case '<-|>' : {
        style = arrow(prefix, true);
        d = ('m ' + from.x + ',' + from.y + ' ' + dx + ',0 0,' + dy);
        if (Edge.label) { lx = to.x; }
        break;
    }
    case '<-|->': {
        style = arrow(prefix, true);
        d = ('m ' + from.x + ',' + from.y + ' ' + (dx / 2) + ',0 0,' + dy + ' ' + (dx / 2) + ',0');
        break;
    }
    case '+':   { style = {class: 'wd-arc', fill: 'none', stroke: '#00F', 'stroke-width': 1, 'marker-end': 'url(#' + prefix + 'tee)', 'marker-start': 'url(#' + prefix + 'tee)'}; break; }
    default   : { style = {class: 'wd-arc-error', fill: 'none', stroke: '#F00', 'stroke-width': 1}; }
    }
    return {
        lx: lx,
        ly: ly,
        d: d,
        style: style
    };
} /* eslint complexity: [1, 40] */

module.exports = arcShape;
