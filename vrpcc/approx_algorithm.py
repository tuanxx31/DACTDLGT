
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

def algorithm_1_mcg_vrp(
    inst: VRPCCInstance,
    X: set[int],
    budget: float,
    oracle: OracleFn,
    *,
    observer: ApproxObserver = NULL_OBSERVER,
) -> tuple[dict[int, list[int]], set[int]]:
    x_init = set(X)
    x_prime = set(X)
    routes: dict[int, list[int]] = {}
    n = inst.n_nodes

    observer.algo1_start(n_x=len(X), budget=budget, m_vehicles=inst.m)

    for veh in range(inst.m):
        vi = {j for j in range(1, n) if inst.u[veh, j] == 1}
        y = x_prime & vi
        tour, vis = oracle(y, budget, veh)
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
        x_prime -= visited_customers
        routes[veh] = tour

    covered = x_init - x_prime
    observer.algo1_done(covered=covered, n_covered=len(covered))
    return routes, covered

def algorithm_2_vrpcc(
    inst: VRPCCInstance,
    oracle: OracleFn,
    eps: float = 1e-3,
    beta: float = 5.0,
    *,
    observer: ApproxObserver = NULL_OBSERVER,
) -> VRPCCResult:
    t_start = time.perf_counter()

    n_cust = inst.n_customers
    x_full = set(inst.customer_indices())

    sum_e = inst.sum_all_edge_costs()
    upper = 2.0 * sum_e
    lower = 0.0
    upper_init = upper

    best_routes: list[list[int]] = [[0, 0] for _ in range(inst.m)]
    best_waves = 0

    observer.binary_search_init(sum_edge_costs=sum_e, upper_init=upper, eps=eps)

    bin_step = 0

    while upper - lower >= eps:
        bin_step += 1
        b = 0.5 * (upper + lower)
        solve = True
        x = set(x_full)
        tau: list[list[int]] = [[] for _ in range(inst.m)]

        observer.binary_step_start(step=bin_step, b=b, lower=lower, upper=upper)

        wave = 0


        while x:
            wave += 1
            nx = len(x)
            need = nx / 2.0
            observer.greedy_wave_start(wave=wave, n_x=nx, need_half=need)
            a, covered = algorithm_1_mcg_vrp(inst, x, b, oracle, observer=observer)
            if len(covered) < need:
                observer.greedy_wave_fail(b=b, n_covered=len(covered), need_half=need)
                solve = False
                break

            observer.greedy_wave_ok(
                covered=covered,
                n_covered=len(covered),
                x_remaining=nx - len(covered),
            )

            x -= covered
            for veh in range(inst.m):
                tau[veh] = _concat_depot_tours(tau[veh], a.get(veh, [0, 0]))


        if solve:
            observer.binary_step_feasible(step=bin_step, b=b)
            upper = b
            best_routes = copy.deepcopy(tau)
            best_waves = wave
        else:
            observer.binary_step_infeasible(step=bin_step, b=b)
            lower = b

    observer.binary_search_done(upper=upper, lower=lower, width=upper - lower)

    elapsed = time.perf_counter() - t_start


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
