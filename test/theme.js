'use strict';

var renderAny = require('../lib/render-any.js');
var theme = require('../lib/theme.js');
var onml = require('onml');
var chai = require('chai');
var expect = chai.expect;

var skinNames = ['default', 'narrow', 'narrower', 'narrowerer', 'dark', 'lowkey'];

var source = function () {
    return {
        signal: [
            {name: 'clk',  wave: 'p.....|...'},
            {name: 'data', wave: 'x.345x|=.x', data: ['head', 'body', 'tail', 'data'], node: '.a........'},
            ['grp', {name: 'req', wave: '0.1..0|1.0', node: '....b.....'}]
        ],
        edge: ['a~>b t1', 'a<->b', 'a+b', 'a?b']
    };
};

var collect = function (ml) {
    var ids = {};
    var refs = [];
    onml.traverse(ml, {
        enter: function (node) {
            var attr = node.attr || {};
            if (attr.id !== undefined) { ids[attr.id] = true; }
            if (attr['xlink:href']) { refs.push(attr['xlink:href'].slice(1)); }
            ['marker-start', 'marker-end'].forEach(function (key) {
                var m = (attr[key] || '').match(/url\(#([^)]+)\)/);
                if (m) { refs.push(m[1]); }
            });
        }
    });
    return {ids: ids, refs: refs};
};

describe('theme', function () {
    skinNames.forEach(function (name) {
        it('makeThemeable ' + name + ': semantic classes, no hard-coded colors', function () {
            var skin = require('../skins/' + name + '.js')[name];
            var themed = theme.makeThemeable(skin);
            var defs = JSON.stringify(themed[3]);
            expect(defs).to.not.match(/"s\d+"/);
            expect(defs).to.not.match(/#[0-9a-fA-F]{3,6}/);
            expect(defs).to.not.match(/"style"/);
            expect(themed[1].class).to.equal('wd-root');
            expect(themed[2][2]).to.match(/^\.wd-root text\{/);
        });
    });

    it('does not mutate the skin', function () {
        var skin = require('../skins/default.js');
        var before = JSON.stringify(skin);
        renderAny(0, source(), skin);
        renderAny(1, source(), skin, false, {idPrefix: 'p-'});
        expect(JSON.stringify(skin)).to.equal(before);
    });

    it('idPrefix: every reference points to a prefixed definition', function () {
        var skin = {default: theme.makeThemeable(require('../skins/default.js').default)};
        var res = renderAny(3, source(), skin, false, {idPrefix: 'x1-'});
        var c = collect(res);
        expect(c.refs.length).to.be.above(10);
        c.refs.forEach(function (ref) {
            expect(ref).to.match(/^x1-/);
            expect(c.ids[ref], ref).to.equal(true);
        });
        expect(res[1].class).to.equal('WaveDrom wd-root');
    });

    it('sprite mode omits <style> and <defs>; sprite provides the targets', function () {
        var skin = require('../skins/default.js').default;
        var res = renderAny(4, source(), {default: theme.makeThemeable(skin)}, false, {defs: 'sprite', idPrefix: 'wd-'});
        var str = onml.stringify(res);
        expect(str).to.not.contain('<defs');
        expect(str).to.not.contain('<style');
        var sprite = collect(theme.renderSprite(skin, {idPrefix: 'wd-'}));
        collect(res).refs.forEach(function (ref) {
            expect(sprite.ids[ref], ref).to.equal(true);
        });
    });

    it('renderers use classes instead of inline colors', function () {
        var str = onml.stringify(renderAny(5, source(), require('../skins/default.js')));
        expect(str).to.contain('class="wd-arc"');
        expect(str).to.contain('class="wd-arc-error"');
        expect(str).to.contain('class="wd-grid"');
        expect(str).to.contain('class="wd-bg"');
        expect(str).to.contain('class="wd-label-bg"');
        // legacy skins keep their own <defs>; the renderers must not add inline colors
        expect(str.replace(/<defs>.*<\/defs>/, '')).to.not.match(/style="[^"]*#/);
    });

    it('themeCss: custom values, resolve to plain values', function () {
        var css = theme.themeCss({'--wd-fg': '#eee', bg: '#111'});
        expect(css).to.match(/^\.wd-root\{--wd-fg:#eee;--wd-bg:#111\}/);
        var flat = theme.themeCss({fg: '#eee', bg: '#111'}, {resolve: true});
        expect(flat).to.not.contain('var(');
        expect(flat).to.contain('.wd-root .wd-line{fill:none;stroke-linecap:round;stroke-linejoin:miter;stroke:#eee;');
        expect(flat).to.contain('.wd-root .wd-data-2{fill:#111;');
        expect(flat).to.contain('.wd-root .wd-data-3{fill:#ffffb4;');
    });
});

/* eslint-env mocha */
