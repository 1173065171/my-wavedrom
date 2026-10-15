#!/usr/bin/env node
'use strict';

const fs = require('fs');
const json5 = require('json5');
const onml = require('onml');

const pkg = require('../package.json');
const lib = require('../lib');
const def = require('../skins/default.js');
const narrow = require('../skins/narrow.js');
const lowkey = require('../skins/lowkey.js');
const dark = require('../skins/dark.js');

const skins = Object.assign({}, def, narrow, lowkey, dark);

const argv = {
    input: undefined,
    indent: undefined,
    skin: undefined,
    theme: undefined,
    themeable: false
};

const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '-i' || arg === '--input') {
        argv.input = args[++i];
    } else if (arg === '-t' || arg === '--indent') {
        argv.indent = args[++i];
    } else if (arg === '-s' || arg === '--skin') {
        argv.skin = args[++i];
    } else if (arg === '--theme') {
        argv.theme = args[++i];
        argv.themeable = true;
    } else if (arg === '--themeable') {
        argv.themeable = true;
    } else if (arg === '-h' || arg === '--help') {
        console.log([
            'Usage: wavedrom --input <path> [options]',
            '  -t, --indent <indent>  pretty-print the SVG',
            '  -s, --skin <name>      ' + Object.keys(skins).join(' | ') + ' (overrides config.skin)',
            '      --themeable        semantic classes + --wd-* CSS variables (scoped under .wd-root)',
            '      --theme <file>     JSON5 map of --wd-* values, baked into a standalone SVG'
        ].join('\n'));
        process.exit(0);
    } else if (arg === '-v' || arg === '--version') {
        console.log(pkg.version);
        process.exit(0);
    }
}

if (argv.skin && !skins[argv.skin]) {
    console.error('Error: unknown skin "' + argv.skin + '", expected one of: ' + Object.keys(skins).join(', '));
    process.exit(1);
}

if (!argv.input) {
    console.error('Error: --input <path> is required');
    process.exit(1);
}

const fileName = argv.input;
fs.readFile(fileName, (err, body) => {
    if (err) { throw err; }
    const source = json5.parse(body);
    let skinSet = skins;
    if (argv.skin) {
        source.config = Object.assign({}, source.config, {skin: argv.skin});
    }
    if (argv.themeable) {
        const vars = argv.theme ? json5.parse(fs.readFileSync(argv.theme, 'utf8')) : undefined;
        const name = (source.config && skins[source.config.skin]) ? source.config.skin : 'default';
        const themed = lib.theme.makeThemeable(skins[name]);
        // a theme file is resolved into plain values so the SVG renders anywhere
        const css = vars ? lib.theme.themeCss(vars, {resolve: true}) : themed[2][2];
        skinSet = {[name]: [themed[0], themed[1], ['style', {type: 'text/css'}, css]].concat(themed.slice(3))};
    }
    const res = lib.renderAny(0, source, skinSet);
    const svg = onml.stringify(res, argv.indent);
    console.log(svg);
});
/* eslint no-console: 0 */
