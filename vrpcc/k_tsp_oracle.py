
from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Callable

import numpy as np

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance

Tour = list[int]
EXACT_THRESHOLD = 8


def _close_tour(tour: Tour) -> Tour:
    if not tour:
        return [0, 0]
    t = tour[:]
    if t[0] != 0:
        t = [0] + t
    if t[-1] != 0:
        t = t + [0]
    return t


def _closed_tour_cost(inst: VRPCCInstance, vehicle: int, tour: Tour) -> float:
    t = _close_tour(tour)
    if len(t) < 2:
        return 0.0
    return float(inst.tour_length(t, vehicle))




def _exact_best_tour(
    inst: VRPCCInstance, vehicle: int, subset: list[int],
) -> tuple[Tour, float]:
    if not subset:
        return [0, 0], 0.0
    best_c = np.inf
    best_tour: Tour = [0, subset[0], 0]
    for perm in itertools.permutations(subset):
        if not all(inst.u[vehicle, p] == 1 for p in perm):
            continue
        seq: Tour = [0] + list(perm) + [0]
        c = _closed_tour_cost(inst, vehicle, seq)
        if c < best_c:
            best_c = c
            best_tour = seq
    return best_tour, float(best_c)


def _exact_k_subset(
    inst: VRPCCInstance, vehicle: int, W: list[int], k: int,
) -> tuple[Tour, float]:
    if k <= 0:
        return [0, 0], 0.0
    best_c = np.inf
    best_tour: Tour = [0, 0]
    for comb in itertools.combinations(W, k):
        t, c = _exact_best_tour(inst, vehicle, list(comb))
        if c < best_c:
            best_c = c
            best_tour = t
    return best_tour, float(best_c)





def _greedy_min_increment_tour(
    inst: VRPCCInstance,
    vehicle: int,
    W: list[int],
    threshold: float,
) -> Tour:
    d = inst.dist
    remaining = set(W)
    tour: Tour = [0]
    cur = 0
    path_cost = 0.0

    while remaining:
        best_j: int | None = None
        best_delta = float("inf")
        for j in sorted(remaining):
            if inst.u[vehicle, j] != 1:
                continue
            c_cur_j = float(d[cur, j])
            c_j0 = float(d[j, 0])
            c_cur0 = float(d[cur, 0])
            closed = path_cost + c_cur_j + c_j0
            if closed > threshold:
                continue
            delta = c_cur_j + c_j0 - c_cur0
            if delta < best_delta:
                best_delta = delta
                best_j = j

        if best_j is None:
            break

        tour.append(best_j)
        path_cost += float(d[cur, best_j])
        cur = best_j
        remaining.remove(best_j)

    tour.append(0)
    return tour if len(tour) >= 2 else [0, 0]




def _two_opt(inst: VRPCCInstance, vehicle: int, tour: Tour) -> Tour:
    tour = _close_tour(tour)
    if len(tour) < 5:
        return tour
    best = tour[:]
    best_c = _closed_tour_cost(inst, vehicle, best)
    inner = tour[1:-1]
    n = len(inner)
    improved = True
    while improved:
        improved = False
        for i in range(n):
            for j in range(i + 1, n):
                cand_inner = inner[:i] + list(reversed(inner[i : j + 1])) + inner[j + 1 :]
                cand = [0] + cand_inner + [0]
                c = _closed_tour_cost(inst, vehicle, cand)
                if c + 1e-9 < best_c:
                    best_c = c
                    best = cand
                    inner = cand_inner
                    improved = True
                    break
            if improved:
                break
    return best






def oracle_k_tsp(
    inst: VRPCCInstance,
    Y: set[int],
    budget: float,
    vehicle: int,
    *,
    beta: float = 5.0,
) -> tuple[Tour, set[int]]:
    W = sorted(j for j in Y if j >= 1 and inst.u[vehicle, j] == 1)
    if not W or budget <= 0:
        return [0, 0], set()

    threshold = beta * budget


    if len(W) <= EXACT_THRESHOLD:
        for k in range(len(W), 0, -1):
            t, c = _exact_k_subset(inst, vehicle, W, k)
            t = _two_opt(inst, vehicle, t)
            c = _closed_tour_cost(inst, vehicle, t)
            if c <= threshold:
                return _close_tour(t), set(t) - {0}
        return [0, 0], set()


    tour = _greedy_min_increment_tour(inst, vehicle, W, threshold)
    tour = _two_opt(inst, vehicle, tour)
    cost = _closed_tour_cost(inst, vehicle, tour)
    if cost <= threshold:
        return _close_tour(tour), set(tour) - {0}
    return [0, 0], set()


def make_oracle(
    inst: VRPCCInstance,
    *,
    beta: float = 5.0,
) -> Callable[[set[int], float, int], tuple[Tour, set[int]]]:
    return lambda Y, B, veh: oracle_k_tsp(inst, Y, B, veh, beta=beta)
