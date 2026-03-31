"""
Thuật toán chính: tái hiện khung Algorithm 1 (MCG-VRP greedy) và Algorithm 2 (binary search trên B) theo paper.

Oracle kèm theo là heuristic (xem k_tsp_oracle); bảo đảm xấp xỉ của paper không áp dụng nguyên văn.
MIP trong repo chỉ phục vụ so sánh.

Trace / log: truyền `observer` (xem `vrpcc.approx_observer`, `vrpcc.approx_observer_logging`).
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Callable

from vrpcc.approx_observer import NULL_OBSERVER, ApproxObserver

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance

# OracleFn(Y, B, vehicle): Y = tập khách, B = ngân sách, vehicle = xe → (tuyến khép kín, tập khách đã thăm).
OracleFn = Callable[[set[int], float, int], tuple[list[int], set[int]]]


def _concat_depot_tours(a: list[int], b: list[int]) -> list[int]:
    """
    Nối hai tuyến khép kín qua depot thành một chuỗi đỉnh duy nhất cho cùng một xe.

    Tham số:
        a, b: chuỗi đỉnh (thường bắt đầu/kết thúc bằng 0). Nếu a kết thúc bằng 0 và b bắt đầu bằng 0,
        bỏ một depot ở giữa để tránh lặp; gộp các depot liên tiếp còn lại.

    Trả về: một tuyến liên tục (dùng khi Algorithm 2 ghép nhiều lần gọi Algorithm 1).
    """
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
    """
    Algorithm 1 (MCG-VRP greedy theo bài báo): lần lượt với mỗi xe i, gọi oracle lên tập khách
    còn lại khả thi với xe đó, trừ những khách đã được “phủ” bởi tuyến oracle.

    Tham số:
        inst: instance VRPCC (số xe, u[k,j], khoảng cách).
        X: tập chỉ số khách hàng cần phục vụ trong vòng lặp ngoài (subset của khách).
        budget: giá trị B (ngân sách chi phí cho mỗi lần gọi oracle, so với beta ở oracle).
        oracle: hàm O(Y, B, vehicle) → (tuyến khép kín, tập khách thăm trên tuyến).
        observer: hooks trace (mặc định không làm gì).

    Trả về:
        - routes: dict xe → tuyến (danh sách đỉnh) trong lần gọi này.
        - covered: tập khách thuộc X đã được ít nhất một xe thăm qua oracle trong lần gọi này.
    """
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
            vehicle=veh,
            y=y,
            tour=tour,
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
    *,
    observer: ApproxObserver = NULL_OBSERVER,
) -> tuple[list[list[int]], float]:
    """
    Algorithm 2: tìm ngưỡng B nhỏ nhất (gần đúng) sao cho lặp Algorithm 1 luôn phủ ít nhất một nửa
    tập khách còn lại mỗi vòng, cho đến khi hết khách; nhị phân trên B với độ rộng khoảng ≤ eps.

    Tham số:
        inst: instance VRPCC.
        oracle: O(Y, B, k) như trong Algorithm 1.
        eps: ngưỡng dừng binary search (upper − lower).
        observer: hooks trace (mặc định không làm gì).

    Trả về:
        - tuyến đầy đủ cho xe 0..m−1 (đã ghép nhiều “đợt” Algorithm 1);
        - B: cận trên khả thi sau nhị phân (upper), sai số tới mức tối thiểu B so với eps.
    """
    x_full = set(inst.customer_indices())
    sum_e = inst.sum_all_edge_costs()
    upper = 2.0 * sum_e
    lower = 0.0
    best_routes: list[list[int]] = [[] for _ in range(inst.m)]

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
            if len(covered) < nx / 2.0 - 1e-9:
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
        else:
            observer.binary_step_infeasible(step=bin_step, b=b)
            lower = b

    observer.binary_search_done(upper=upper, lower=lower, width=upper - lower)

    return best_routes, upper
