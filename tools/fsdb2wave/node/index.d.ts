export interface Fsdb2WaveArgs {
    file: string;
    signals: string[];
    clock: string;
    cycles: number;
    /** '1200ns' or '@15' (15th clock edge, 0-based) */
    start?: string;
    edge?: 'pos' | 'neg';
    sample?: 'mid' | 'pre';
    radix?: 'hex' | 'bin' | 'dec' | 'sdec';
    color?: 'none' | 'value' | 'signal';
    groupByScope?: boolean;
    stripPrefix?: string;
    maxSignals?: number;
    maxCycles?: number;
    truncate?: boolean;
    markGlitch?: boolean;
    hscale?: 1 | 2 | 3;
    backend?: 'auto' | 'ffr' | 'fsdb2vcd' | 'vcd';
    fsdb2vcdArgs?: string;
}

export interface Fsdb2WaveWarning {
    kind: string;
    [key: string]: unknown;
}

export type WaveJSON = {
    signal: unknown[];
    head?: {text?: string; tick?: number};
    config?: {hscale?: number};
    meta?: Record<string, unknown> & {warnings?: Fsdb2WaveWarning[]};
};

export type Fsdb2WaveResult =
    | {ok: true; wave: WaveJSON; warnings: Fsdb2WaveWarning[]}
    /** 1 input / arguments, 2 limits exceeded, 3 path not found (see candidates), 4 backend unavailable */
    | {ok: false; code: 1 | 2 | 3 | 4; message: string; candidates: string[]};

export interface Fsdb2WaveOptions {
    /** default ['python3', '-m', 'fsdb2wave'] */
    command?: string[];
    cwd?: string;
    env?: NodeJS.ProcessEnv;
    /** milliseconds */
    timeout?: number;
}

export declare function fsdb2wave(args: Fsdb2WaveArgs, options?: Fsdb2WaveOptions): Promise<Fsdb2WaveResult>;
export declare function toArgv(args: Fsdb2WaveArgs): string[];
