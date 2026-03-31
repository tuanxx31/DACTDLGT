"""
Oracle O(Y, B, vehicle) cho MCG-VRP (mục 3 bài báo) — thành phần cốt lõi của thuật toán xấp xỉ.

Tuyến gốc 0, tối đa hoá số đỉnh trong Y ∩ V_i trong ngân sách (bicriteria).
Binary search theo k (k-TSP / orienteering); TSP nhỏ exact, lớn NN + 2-opt nhẹ.
Bicriteria: cost <= beta * B (beta=2 [20]; [19] 3-approx — PDF có chỗ ghi không nhất quán).
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Callable

import numpy as np

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance

Tour = list[int]


def _tour_cost(inst: VRPCCInstance, tour: Tour) -> float:
    if len(tour) < 2:
        return 0.0
    return float(sum(inst.dist[tour[i], tour[i + 1]] for i in range(len(tour) - 1)))


def _exact_best_tour_on_subset(inst: VRPCCInstance, vehicle: int, subset: list[int]) -> tuple[Tour, float]:
    """Minimum closed tour 0 -> permutation(subset) -> 0 (metric, full visits)."""
    if not subset:
        return [0, 0], 0.0
    customers = list(subset)
    d = inst.dist
    best_c = np.inf
    best_tour: Tour = [0, customers[0], 0]
    for perm in itertools.permutations(customers):
        ok = all(inst.u[vehicle, p] == 1 for p in perm)
        if not ok:
            continue
        seq: Tour = [0] + list(perm) + [0]
        c = _tour_cost(inst, seq)
        if c < best_c:
            best_c = c
            best_tour = seq
    return best_tour, float(best_c)


def _choose_best_k_subset_exact(inst: VRPCCInstance, vehicle: int, W: list[int], k: int) -> tuple[Tour, float]:
    """Min-cost tour visiting exactly k customers from W (brute force)."""
    if k <= 0:
        return [0, 0], 0.0
    best_c = np.inf
    best_tour: Tour = [0, 0]
    for comb in itertools.combinations(W, k):
        t, c = _exact_best_tour_on_subset(inst, vehicle, list(comb))
        if c < best_c:
            best_c = c
            best_tour = t
    return best_tour, float(best_c)


def _nearest_neighbor_tour(inst: VRPCCInstance, vehicle: int, nodes: list[int]) -> Tour:
    """Depot-rooted NN on given node set."""
    if not nodes:
        return [0, 0]
    remaining = {v for v in nodes if inst.u[vehicle, v] == 1}
    if not remaining:
        return [0, 0]
    tour: Tour = [0]
    cur = 0
    while remaining:
        nxt = min(remaining, key=lambda v: inst.dist[cur, v])
        tour.append(nxt)
        remaining.remove(nxt)
        cur = nxt
    tour.append(0)
    return tour


def _two_opt_once(inst: VRPCCInstance, tour: Tour) -> Tour:
    """2-opt on open path excluding fixed endpoints 0 at start and end."""
    if len(tour) < 5:
        return tour
    best = tour[:]
    best_c = _tour_cost(inst, best)
    inner = tour[1:-1]
    n = len(inner)
    improved = True
    while improved:
        improved = False
        for i in range(n):
            for j in range(i + 1, n):
                cand_inner = inner[:i] + list(reversed(inner[i : j + 1])) + inner[j + 1 :]
                cand = [0] + cand_inner + [0]
                c = _tour_cost(inst, cand)
                if c + 1e-9 < best_c:
                    best_c = c
                    best = cand
                    inner = cand_inner
                    improved = True
                    break
            if improved:
                break
    return best


def _heuristic_tour_covering_k(inst: VRPCCInstance, vehicle: int, W: list[int], k: int) -> tuple[Tour, float]:
    W = [v for v in W if v >= 1 and inst.u[vehicle, v] == 1]
    if k <= 0 or not W:
        return [0, 0], 0.0
    k = min(k, len(W))
    if len(W) <= 12 and k <= 8:
        t, c = _choose_best_k_subset_exact(inst, vehicle, W, k)
        t = _two_opt_once(inst, t)
        return t, _tour_cost(inst, t)
    # Greedy subset: k nearest to depot
    dep = 0
    sorted_w = sorted(W, key=lambda v: inst.dist[dep, v])[:k]
    t = _nearest_neighbor_tour(inst, vehicle, sorted_w)
    t = _two_opt_once(inst, t)
    return t, _tour_cost(inst, t)


def oracle_k_tsp(
    inst: VRPCCInstance,
    Y: set[int],
    budget: float,
    vehicle: int,
    *,
    beta: float = 3.0,
    exact_max_w: int = 12,
) -> tuple[Tour, set[int]]:
    """
    Bicriteria oracle: maximize |tour ∩ Y ∩ V_vehicle| subject to cost <= beta * budget.
    Returns (closed tour from depot, set of customers visited on that tour).
    """
    W = sorted(j for j in Y if j >= 1 and inst.u[vehicle, j] == 1)
    if not W or budget <= 0:
        return [0, 0], set()

    def solve_k(k: int) -> tuple[Tour, float]:
        if len(W) <= exact_max_w and k <= min(8, len(W)):
            return _choose_best_k_subset_exact(inst, vehicle, W, k)
        return _heuristic_tour_covering_k(inst, vehicle, W, k)

    lo, hi = 1, len(W)
    best_tour: Tour = [0, 0]
    best_vis: set[int] = set()
    while lo <= hi:
        mid = (lo + hi) // 2
        tour, cost = solve_k(mid)
        if cost <= beta * budget + 1e-9:
            best_tour = tour
            best_vis = set(tour) - {0}
            lo = mid + 1
        else:
            hi = mid - 1
    if not best_vis and W:
        t, _ = solve_k(1)
        return t, set(t) - {0}
    return best_tour, best_vis


def make_oracle(
    inst: VRPCCInstance,
    *,
    beta: float = 3.0,
) -> Callable[[set[int], float, int], tuple[Tour, set[int]]]:
    return lambda Y, B, veh: oracle_k_tsp(inst, Y, B, veh, beta=beta)
