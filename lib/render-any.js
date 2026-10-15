'use strict';

const renderAssign = require('logidrom/lib/render-assign.js');

const renderReg = require('./render-reg.js');
const renderSignal = require('./render-signal.js');
const w3 = require('./w3.js');

// options (optional): {
//   idPrefix: prefix for every <defs> id and reference, to keep several
//             diagrams / skins apart on one page
//   defs:     'inline' (default) or 'sprite' to omit <style>/<defs> and rely on
//             the hidden sprite from theme.renderSprite()
// }
function renderAny (index, source, waveSkin, notFirstSignal, options) {
    const res = source.signal
        ? renderSignal(index, source, waveSkin, notFirstSignal, options)
        : source.assign
            ? renderAssign(index, source)
            : source.reg
                ? renderReg(index, source)
                : ['div', {}];

    if (res[0] === 'svg') {
        res[1].xmlns = w3.svg;
        res[1]['xmlns:xlink'] = w3.xlink;
    }
    res[1].class = res[1].class ? ('WaveDrom ' + res[1].class) : 'WaveDrom';
    return res;
}

module.exports = renderAny;
