// Types for the themeable <wave-view> element (lib/wave-view.js).

export type WaveJSON = Record<string, unknown>;

/** --wd-* theme values, keys with or without the "--wd-" prefix. */
export type WaveTheme = Partial<Record<
    | 'fg' | 'bg' | 'grid' | 'line-width' | 'line-width-thin'
    | 'font-family' | 'font-size' | 'arc'
    | 'muted' | 'info' | 'warning' | 'error' | 'success'
    | 'data-2' | 'data-3' | 'data-4' | 'data-5' | 'data-6' | 'data-7' | 'data-8' | 'data-9',
    string
>> | Record<string, string>;

export declare class WaveView extends HTMLElement {
    /** WaveJSON object or JSON5 text; setting it re-renders on the next frame. */
    source: WaveJSON | string | undefined;
    /** The rendered diagram, if any. */
    readonly svg: SVGSVGElement | null;
    /** Standalone SVG with bricks copied in and --wd-* values frozen. */
    toSVG(): string;
    render(): void;
    /** Make another skin geometry (narrow, lowkey, ...) usable via skin="name". */
    static registerSkin(name: string, skin: unknown): void;
}

/** Registers the custom element (default tag: wave-view) and returns the class. */
export declare function define(tagName?: string): typeof WaveView;

export declare function exportSvg(svg: SVGSVGElement): string;

declare global {
    interface HTMLElementTagNameMap {
        'wave-view': WaveView;
    }
    interface HTMLElementEventMap {
        'wave-render': CustomEvent<{source: WaveJSON}>;
        'wave-error': CustomEvent<Error>;
    }
}
