'use strict';

const tt = require('onml/tt.js');

const w3 = require('./w3.js');
const theme = require('./theme.js');

function insertSVGTemplate (index, source, lane, waveSkin, content, lanes, groups, notFirstSignal, options) {
    const opts = options || {};
    const waveSkinNames = Object.keys(waveSkin);

    let skin = waveSkin.default || waveSkin[waveSkinNames[0]];

    if (source && source.config && source.config.skin && waveSkin[source.config.skin]) {
        skin = waveSkin[source.config.skin];
    }

    // never mutate the shared skin: copy the root, reuse <style> / <defs> as is
    const e = (notFirstSignal || opts.defs === 'sprite')
        ? ['svg', {id: 'svg', xmlns: w3.svg, 'xmlns:xlink': w3.xlink}, ['g']]
        : [skin[0], Object.assign({}, skin[1])]
            .concat(skin.slice(2, -1).map(el =>
                (el[0] === 'defs') ? theme.prefixDefs(el, lane.idPrefix) : el
            ))
            .concat([['g']]);

    const width = (lane.xg + (lane.xs * (lane.xmax + 1)));
    const height = (content.length * lane.yo + lane.yh0 + lane.yh1 + lane.yf0 + lane.yf1);

    const body = e[e.length - 1];

    body[1] = {id: 'waves_'  + index};

    body[2] = ['rect', {width: width, height: height, class: 'wd-bg', fill: 'white', stroke: 'none'}];

    body[3] = ['g', tt(
        lane.xg + 0.5,
        lane.yh0 + lane.yh1 + 0.5,
        {id: 'lanes_'  + index}
    )].concat(lanes);

    body[4] = ['g', {
        id: 'groups_' + index
    }, groups];

    const head = e[1];

    head.id = 'svgcontent_' + index;
    head.xmlns = w3.svg;
    head['xmlns:xlink'] = w3.xlink;
    head.height = height;
    head.width = width;
    head.viewBox = '0 0 ' + width + ' ' + height;
    head.overflow = 'hidden';
    if (skin[1] && skin[1].class) {
        head.class = skin[1].class;
    }

    return e;
}

module.exports = insertSVGTemplate;
