'use strict';

// Browser bundle entry: registers <wave-view> and exposes window.WaveDromView.

const waveView = require('./wave-view.js');
const theme = require('./theme.js');
const narrow = require('../skins/narrow.js');
const lowkey = require('../skins/lowkey.js');

waveView.WaveView.registerSkin('narrow', narrow.narrow);
waveView.WaveView.registerSkin('lowkey', lowkey.lowkey);
waveView.define();

window.WaveDromView = {
    WaveView: waveView.WaveView,
    registerSkin: waveView.WaveView.registerSkin,
    exportSvg: waveView.exportSvg,
    theme: theme
};

/* eslint-env browser */
