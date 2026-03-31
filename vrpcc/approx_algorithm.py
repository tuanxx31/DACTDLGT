"""
Thuật toán chính theo bài báo: Algorithm 1 (MCG-VRP greedy) và Algorithm 2 (binary search trên B).

MIP trong repo chỉ phục vụ so sánh; phần cốt lõi báo cáo nên tập trung vào module này + oracle k-TSP.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance

OracleFn = Callable[[set[int], float, int], tuple[list[int], set[int]]]


def _concat_depot_tours(a: list[int], b: list[int]) -> list[int]:
    if not a:
        return b[:]
    if not b:
        return a[:]
    if a[-1] == 0 and b[0] == 0:
        out = a[:-1] + b
    else:
        out = a + b
    # collapse repeated depots from concatenation
    slim: list[int] = []
    for v in out:
        if v == 0 and slim and slim[-1] == 0:
            continue
        slim.append(v)
    return slim


def algorithm_1_mcg_vrp(
    inst: VRPCCInstance,
    X: set[int],
    budget: float,
    oracle: OracleFn,
) -> tuple[dict[int, list[int]], set[int]]:
    """
    Algorithm 1: for each vehicle i in K, Ai <- O(X' ∩ Vi, B, i), X' <- X' \\ Ai.
    Returns (routes per vehicle, nodes of X covered in this call).
    """
    x_init = set(X)
    x_prime = set(X)
    routes: dict[int, list[int]] = {}
    n = inst.n_nodes
    for veh in range(inst.m):
        vi = {j for j in range(1, n) if inst.u[veh, j] == 1}
        y = x_prime & vi
        tour, _vis = oracle(y, budget, veh)
        if len(tour) < 2:
            tour = [0, 0]
        visited_customers = (set(tour) - {0}) & x_prime
        x_prime -= visited_customers
        routes[veh] = tour
    covered = x_init - x_prime
    return routes, covered


def algorithm_2_vrpcc(
    inst: VRPCCInstance,
    oracle: OracleFn,
    eps: float = 1e-3,
) -> list[list[int]]:
    """
    Algorithm 2: binary search on B; inner loop applies Algorithm 1 until X empty
    or coverage < |X|/2.
    Returns per-vehicle concatenated closed tours.
    """
    x_full = set(inst.customer_indices())
    upper = 2.0 * inst.sum_all_edge_costs()
    lower = 0.0
    best_routes: list[list[int]] = [[] for _ in range(inst.m)]

    while upper - lower >= eps:
        b = 0.5 * (upper + lower)
        solve = True
        x = set(x_full)
        tau: list[list[int]] = [[] for _ in range(inst.m)]

        while x:
            a, covered = algorithm_1_mcg_vrp(inst, x, b, oracle)
            if len(covered) < len(x) / 2.0 - 1e-9:
                solve = False
                break
            x -= covered
            for veh in range(inst.m):
                tau[veh] = _concat_depot_tours(tau[veh], a.get(veh, [0, 0]))

        if solve:
            upper = b
            best_routes = copy.deepcopy(tau)
        else:
            lower = b

    return best_routes
