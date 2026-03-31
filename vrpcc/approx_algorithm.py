"""
Thuật toán xấp xỉ VRPCC — Algorithm 1 & Algorithm 2.

Theo bài báo: Yu, Nagarajan, Shen (2018).
"An Approximation Algorithm for Vehicle Routing with Compatibility Constraints"

Algorithm 2 nhị phân trên B để tìm ngân sách nhỏ nhất sao cho Algorithm 1
(greedy MCG-VRP) luôn phủ ≥ |X|/2 khách mỗi lượt. Khi upper - lower < ε,
B ≈ upper là ngân sách tốt nhất tìm được.

Đảm bảo xấp xỉ (Lemma 5): makespan ≤ (1+ε) · β · ⌈log₂ n⌉ · OPT
"""

from __future__ import annotations

import copy
import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from vrpcc.approx_observer import NULL_OBSERVER, ApproxObserver

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance

OracleFn = Callable[[set[int], float, int], tuple[list[int], set[int]]]


@dataclass
class VRPCCResult:
    """Kết quả đầy đủ của Algorithm 2."""

    routes: list[list[int]]
    makespan: float
    B_upper: float
    B_lower: float
    B_init_upper: float
    eps: float
    beta: float
    n_binary_steps: int
    n_waves_last_feasible: int
    elapsed_sec: float
    n_customers: int
    n_vehicles: int
    approx_ratio_bound: float
    route_costs: list[float]


def _concat_depot_tours(a: list[int], b: list[int]) -> list[int]:
    """Nối hai tuyến khép kín qua depot: τ_k ← τ_k ∘ A_k (paper line 8)."""
    if not a:
        return b[:]
    if not b:
        return a[:]
    if a[-1] == 0 and b[0] == 0:
        out = a[:-1] + b
    else:
        out = a + b
    slim: list[int] = []
    for v in out:
        if v == 0 and slim and slim[-1] == 0:
            continue
        slim.append(v)
    return slim


# ══════════════════════════════════════════════════════════════
# Algorithm 1 — MCG-VRP Greedy (paper trang 6)
# ══════════════════════════════════════════════════════════════
#
#   Input : fleet K, subset X ⊂ V, budget B
#   Output: routes {A_i : i ∈ K}
#
#   1  X' ← X
#   2  for i ∈ K do
#   3      A_i = O(X' ∩ V_i, B, i)
#   4      X' ← X' \ A_i
#   5  end
#   6  return H = {A_i : i ∈ K}
# ══════════════════════════════════════════════════════════════

def algorithm_1_mcg_vrp(
    inst: VRPCCInstance,
    X: set[int],
    budget: float,
    oracle: OracleFn,
    *,
    observer: ApproxObserver = NULL_OBSERVER,
) -> tuple[dict[int, list[int]], set[int]]:
    """
    Algorithm 1: lần lượt mỗi xe gọi oracle trên tập khách còn lại khả thi,
    rồi trừ những khách đã phủ.

    Returns (routes_per_vehicle, covered_customers).
    """
    x_init = set(X)
    x_prime = set(X)                                     # line 1
    routes: dict[int, list[int]] = {}
    n = inst.n_nodes

    observer.algo1_start(n_x=len(X), budget=budget, m_vehicles=inst.m)

    for veh in range(inst.m):                            # line 2
        vi = {j for j in range(1, n) if inst.u[veh, j] == 1}
        y = x_prime & vi                                 # X' ∩ V_i
        tour, vis = oracle(y, budget, veh)               # line 3: O(X'∩V_i, B, i)
        if len(tour) < 2:
            tour = [0, 0]
        visited_customers = vis & x_prime
        try:
            c_veh = inst.tour_length(tour, veh) if len(tour) >= 2 else 0.0
        except ValueError:
            c_veh = float("nan")
        observer.algo1_vehicle(
            vehicle=veh, y=y, tour=tour,
            visited_customers=visited_customers,
            tour_cost=c_veh,
            x_prime_remaining=x_prime - visited_customers,
        )
        x_prime -= visited_customers                     # line 4: X' ← X' \ A_i
        routes[veh] = tour

    covered = x_init - x_prime
    observer.algo1_done(covered=covered, n_covered=len(covered))
    return routes, covered


# ══════════════════════════════════════════════════════════════
# Algorithm 2 — Binary search trên B (paper trang 7)
# ══════════════════════════════════════════════════════════════
#
#   1   Initialize τ_i = ∅ ∀i, X ← V+
#   2   u = 2·Σ c_ij, l = 0, ε
#   3   while u − l ≥ ε do
#   4       B ← (u+l)/2, Solve ← true
#   5       while X ≠ ∅ do
#   6           {A_i} = Algorithm 1(K, X, B)
#   7           if |∪ A_i ∩ X| < |X|/2: Solve ← false, break
#   8           X ← X\(∪A_i), τ_k ← τ_k ∘ A_k ∀k
#   9       end
#   10      if Solve then u ← B
#   11      else l ← B
#   12  end
#   13  return τ
# ══════════════════════════════════════════════════════════════

def algorithm_2_vrpcc(
    inst: VRPCCInstance,
    oracle: OracleFn,
    eps: float = 1e-3,
    beta: float = 5.0,
    *,
    observer: ApproxObserver = NULL_OBSERVER,
) -> VRPCCResult:
    """
    Algorithm 2: nhị phân trên B, lặp Algorithm 1 cho đến khi phủ hết khách.

    Returns VRPCCResult chứa routes, bounds, makespan, thời gian, cận xấp xỉ.

    Mỗi tuyến trong `routes` là closed tour [0,…,0]; `route_costs` / makespan
    dùng `tour_length` (có cạnh quay về kho).
    """
    t_start = time.perf_counter()

    n_cust = inst.n_customers
    x_full = set(inst.customer_indices())

    # ═══ Line 2: khởi tạo ═══
    sum_e = inst.sum_all_edge_costs()
    upper = 2.0 * sum_e                                  # u = 2·Σ c_ij
    lower = 0.0                                           # l = 0
    upper_init = upper

    best_routes: list[list[int]] = [[0, 0] for _ in range(inst.m)]
    best_waves = 0

    observer.binary_search_init(sum_edge_costs=sum_e, upper_init=upper, eps=eps)

    bin_step = 0

    # ═══ Line 3: while u − l ≥ ε ═══
    while upper - lower >= eps:
        bin_step += 1
        b = 0.5 * (upper + lower)                        # line 4: B ← (u+l)/2
        solve = True                                      # Solve ← true
        x = set(x_full)                                   # X ← V+ (reset)
        tau: list[list[int]] = [[] for _ in range(inst.m)]

        observer.binary_step_start(step=bin_step, b=b, lower=lower, upper=upper)

        wave = 0

        # ═══ Line 5: while X ≠ ∅ ═══
        while x:
            wave += 1
            nx = len(x)
            need = nx / 2.0
            observer.greedy_wave_start(wave=wave, n_x=nx, need_half=need)

            # line 6
            a, covered = algorithm_1_mcg_vrp(inst, x, b, oracle, observer=observer)

            # line 7: if |∪A_i ∩ X| < |X|/2 → Solve ← false, break
            if len(covered) < need - 1e-9:
                observer.greedy_wave_fail(b=b, n_covered=len(covered), need_half=need)
                solve = False
                break

            observer.greedy_wave_ok(
                covered=covered,
                n_covered=len(covered),
                x_remaining=nx - len(covered),
            )

            # line 8: X ← X\(∪A_i), τ_k ← τ_k ∘ A_k
            x -= covered
            for veh in range(inst.m):
                tau[veh] = _concat_depot_tours(tau[veh], a.get(veh, [0, 0]))

        # ═══ Line 10-11: cập nhật cận ═══
        if solve:
            observer.binary_step_feasible(step=bin_step, b=b)
            upper = b                                     # u ← B
            best_routes = copy.deepcopy(tau)
            best_waves = wave
        else:
            observer.binary_step_infeasible(step=bin_step, b=b)
            lower = b                                     # l ← B

    observer.binary_search_done(upper=upper, lower=lower, width=upper - lower)

    elapsed = time.perf_counter() - t_start

    # Chuẩn hoá [0,…,0] và tính chi phí closed tour (gồm cạnh về depot)
    norm_routes: list[list[int]] = []
    for k in range(inst.m):
        r = best_routes[k] if k < len(best_routes) else [0, 0]
        if not r or len(r) < 2:
            r = [0, 0]
        norm_routes.append(inst.normalize_closed_tour(r))
    best_routes = norm_routes

    route_costs: list[float] = []
    for k in range(inst.m):
        try:
            route_costs.append(inst.tour_length(best_routes[k], k))
        except ValueError:
            route_costs.append(0.0)
    makespan = max(route_costs) if route_costs else 0.0

    log2n = math.ceil(math.log2(max(n_cust, 2)))
    approx_bound = (1 + eps) * beta * log2n

    return VRPCCResult(
        routes=best_routes,
        makespan=makespan,
        B_upper=upper,
        B_lower=lower,
        B_init_upper=upper_init,
        eps=eps,
        beta=beta,
        n_binary_steps=bin_step,
        n_waves_last_feasible=best_waves,
        elapsed_sec=elapsed,
        n_customers=n_cust,
        n_vehicles=inst.m,
        approx_ratio_bound=approx_bound,
        route_costs=route_costs,
    )
