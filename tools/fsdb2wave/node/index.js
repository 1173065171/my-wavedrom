'use strict';

// Thin Node wrapper around the fsdb2wave CLI for agent tools.
// Resolves to {ok: true, wave, warnings} or {ok: false, code, message, candidates}.

const {spawn} = require('child_process');

const flag = (name, value) => (value === undefined || value === null || value === false)
    ? []
    : (value === true ? ['--' + name] : ['--' + name, String(value)]);

function toArgv (args) {
    if (!args || !args.file || !args.clock || !args.cycles || !Array.isArray(args.signals)) {
        throw new TypeError('fsdb2wave: file, clock, cycles and signals[] are required');
    }
    return [args.file, '-c', args.clock, '-n', String(args.cycles)]
        .concat(...args.signals.map(s => ['-s', s]))
        .concat(
            flag('start', args.start),
            flag('edge', args.edge),
            flag('sample', args.sample),
            flag('radix', args.radix),
            flag('color', args.color),
            flag('group-by-scope', args.groupByScope),
            flag('strip-prefix', args.stripPrefix),
            flag('max-signals', args.maxSignals),
            flag('max-cycles', args.maxCycles),
            flag('truncate', args.truncate),
            flag('mark-glitch', args.markGlitch),
            flag('hscale', args.hscale),
            flag('backend', args.backend),
            flag('fsdb2vcd-args', args.fsdb2vcdArgs)
        );
}

function fsdb2wave (args, options) {
    const opts = options || {};
    const command = opts.command || ['python3', '-m', 'fsdb2wave'];
    const argv = toArgv(args);
    return new Promise((resolve, reject) => {
        const child = spawn(command[0], command.slice(1).concat(argv), {
            cwd: opts.cwd,
            env: opts.env || process.env
        });
        let out = '';
        let err = '';
        let timer;
        if (opts.timeout) {
            timer = setTimeout(() => child.kill('SIGKILL'), opts.timeout);
        }
        child.stdout.on('data', d => { out += d; });
        child.stderr.on('data', d => { err += d; });
        child.on('error', reject);
        child.on('close', code => {
            clearTimeout(timer);
            if (code === 0) {
                const wave = JSON.parse(out);
                resolve({ok: true, wave: wave, warnings: (wave.meta && wave.meta.warnings) || []});
                return;
            }
            let detail;
            try {
                detail = JSON.parse(err.trim().split('\n').pop());
            } catch {
                detail = {code: code === null ? 1 : code, message: err.trim() || 'fsdb2wave was killed'};
            }
            resolve({ok: false, code: detail.code, message: detail.message, candidates: detail.candidates || []});
        });
    });
}

module.exports = {fsdb2wave: fsdb2wave, toArgv: toArgv};
