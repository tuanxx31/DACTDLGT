"""
Mục 4 bài báo: 2-opt theo đoạn depot + relocation sau Algorithm 2.

`scripts/run_comparison.py` gọi module này mặc định; `--no-local-search` để chỉ chạy tới mục 3.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance


def _split_segments(route: list[int]) -> list[list[int]]:
    if not route:
        return [[0, 0]]
    segs: list[list[int]] = []
    cur: list[int] = []
    for node in route:
        cur.append(node)
        if node == 0 and len(cur) > 1:
            segs.append(cur)
            cur = [0]
    if len(cur) > 1:
        segs.append(cur)
    return segs if segs else [[0, 0]]


def _merge_segments(segs: list[list[int]]) -> list[int]:
    if not segs:
        return [0, 0]
    out = segs[0][:]
    for s in segs[1:]:
        if out and s and out[-1] == 0 and s[0] == 0:
            out = out[:-1] + s
        else:
            out.extend(s)
    return out


def _two_opt_segment(inst: VRPCCInstance, vehicle: int, seg: list[int]) -> list[int]:
    if len(seg) < 5:
        return seg
    inner = seg[1:-1]
    n = len(inner)
    best_c = inst.tour_length([0] + inner + [0], vehicle)
    improved = True
    while improved:
        improved = False
        for i in range(n):
            for j in range(i + 1, n):
                cand_inner = inner[:i] + list(reversed(inner[i : j + 1])) + inner[j + 1 :]
                cand = [0] + cand_inner + [0]
                c = inst.tour_length(cand, vehicle)
                if c + 1e-9 < best_c:
                    best_c = c
                    inner = cand_inner
                    improved = True
                    break
            if improved:
                break
    return [0] + inner + [0]


def _remove_customer(route: list[int], cust: int) -> list[int]:
    r = [x for x in route if x != cust]
    out: list[int] = []
    for x in r:
        if x == 0 and out and out[-1] == 0:
            continue
        out.append(x)
    if not out:
        return [0, 0]
    if out[0] != 0:
        out.insert(0, 0)
    if out[-1] != 0:
        out.append(0)
    return out


def _best_insertion(inst: VRPCCInstance, veh: int, route: list[int], cust: int) -> list[int] | None:
    nodes = [x for x in route if x != 0]
    if cust in nodes or inst.u[veh, cust] == 0:
        return None
    best: list[int] | None = None
    best_c = float("inf")
    for pos in range(len(nodes) + 1):
        new_nodes = nodes[:pos] + [cust] + nodes[pos:]
        cand = [0] + new_nodes + [0]
        c = inst.tour_length(cand, veh)
        if c < best_c:
            best_c = c
            best = cand
    return best


def _makespan(inst: VRPCCInstance, routes: list[list[int]]) -> float:
    return max(inst.tour_length(routes[k], k) for k in range(inst.m))


def local_search(
    inst: VRPCCInstance,
    routes: list[list[int]],
    *,
    max_passes: int = 30,
) -> list[list[int]]:
    routes = copy.deepcopy(routes)
    m = inst.m
    for _ in range(max_passes):
        for k in range(m):
            segs = _split_segments(routes[k])
            routes[k] = _merge_segments([_two_opt_segment(inst, k, s) for s in segs])

        ms0 = _makespan(inst, routes)
        k_long = max(range(m), key=lambda i: inst.tour_length(routes[i], i))
        customers = [x for x in routes[k_long] if x != 0]
        if not customers:
            break
        best_ms = ms0
        best_routes = routes
        for cust in customers:
            for other in range(m):
                if other == k_long:
                    continue
                if inst.u[other, cust] == 0:
                    continue
                trial = copy.deepcopy(routes)
                trial[k_long] = _remove_customer(trial[k_long], cust)
                ins = _best_insertion(inst, other, trial[other], cust)
                if ins is None:
                    continue
                trial[other] = ins
                ms = _makespan(inst, trial)
                if ms + 1e-9 < best_ms:
                    best_ms = ms
                    best_routes = trial
        if best_ms + 1e-9 < ms0:
            routes = best_routes
        else:
            break
    return routes
