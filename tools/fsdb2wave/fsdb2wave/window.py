"""Cut a window of N reference-clock cycles out of a change stream.

Changes are processed one timestamp at a time, so a clock edge and the
data changes recorded at the same time always land on the same side of the
window start regardless of their order in the file. Reading stops as soon as
the closing edge of the last cycle has been seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import Fsdb2WaveError, INPUT


@dataclass
class Window:
    edges: list[int]                                   # e[0] .. e[N], ticks
    start_index: int                                   # index of e[0] among all clock edges
    init: dict[str, str] = field(default_factory=dict)  # value just before e[0]
    changes: dict[str, list[tuple[int, str]]] = field(default_factory=dict)  # e[0] <= t < e[N]
    eof: bool = False


def is_edge(prev: str | None, value: str, edge: str) -> bool:
    if prev is None:
        return False
    target = '1' if edge == 'pos' else '0'
    return value == target and prev != target


def collect(source, clock_code: str, codes: list[str], edge: str,
            start_time: int | None, start_cycle: int | None, cycles: int) -> Window:
    want = set(codes) | {clock_code}
    last: dict[str, str] = {}
    post: dict[str, list[tuple[int, str]]] = {c: [] for c in want}
    edges: list[int] = []
    state = {'edge_idx': -1, 'started': False, 'start_index': -1, 'prev_clk': None, 'done': False}
    need = cycles + 1

    def matches_start(idx: int, t: int) -> bool:
        if start_cycle is not None:
            return idx == start_cycle
        if start_time is not None:
            return t >= start_time
        return True

    def flush(t: int, group: list[tuple[str, str]]) -> None:
        edge_here = False
        for code, value in group:
            if code == clock_code:
                if is_edge(state['prev_clk'], value, edge):
                    edge_here = True
                state['prev_clk'] = value
        if edge_here:
            state['edge_idx'] += 1
            if not state['started'] and matches_start(state['edge_idx'], t):
                state['started'] = True
                state['start_index'] = state['edge_idx']
            if state['started']:
                edges.append(t)
        if state['started'] and len(edges) >= need:
            state['done'] = True     # changes at e[N] belong to the next cycle
            return
        for code, value in group:
            if state['started']:
                post[code].append((t, value))
            else:
                last[code] = value

    stream = source.changes(want)
    group_t = None
    group: list[tuple[str, str]] = []
    eof = True
    try:
        for t, code, value in stream:
            if t != group_t:
                if group:
                    flush(group_t, group)
                    if state['done']:
                        eof = False
                        break
                if group_t is not None and t < group_t:
                    raise Fsdb2WaveError(INPUT, 'timestamps go backwards at %d' % t)
                group_t = t
                group = []
            group.append((code, value))
        else:
            if group:
                flush(group_t, group)
    finally:
        close = getattr(stream, 'close', None)
        if close:
            close()

    return Window(edges=edges, start_index=state['start_index'], init=last, changes=post, eof=eof)
