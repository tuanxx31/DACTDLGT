"""
Thuật toán chính: tái hiện khung Algorithm 1 (MCG-VRP greedy) và Algorithm 2 (binary search trên B) theo paper.

Oracle kèm theo là heuristic (xem k_tsp_oracle); bảo đảm xấp xỉ của paper không áp dụng nguyên văn.
MIP trong repo chỉ phục vụ so sánh.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Callable

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
    Algorithm 1 (MCG-VRP greedy theo bài báo): lần lượt với mỗi xe i, gọi oracle lên tập khách
    còn lại khả thi với xe đó, trừ những khách đã được “phủ” bởi tuyến oracle.

    Tham số:
        inst: instance VRPCC (số xe, u[k,j], khoảng cách).
        X: tập chỉ số khách hàng cần phục vụ trong vòng lặp ngoài (subset của khách).
        budget: giá trị B (ngân sách chi phí cho mỗi lần gọi oracle, so với beta ở oracle).
        oracle: hàm O(Y, B, vehicle) → (tuyến khép kín, tập khách thăm trên tuyến).

    Trả về:
        - routes: dict xe → tuyến (danh sách đỉnh) trong lần gọi này.
        - covered: tập khách thuộc X đã được ít nhất một xe thăm qua oracle trong lần gọi này.
    """
    x_init = set(X)
    x_prime = set(X)
    routes: dict[int, list[int]] = {}
    n = inst.n_nodes
    for veh in range(inst.m):
        vi = {j for j in range(1, n) if inst.u[veh, j] == 1}
        y = x_prime & vi
        tour, vis = oracle(y, budget, veh)
        if len(tour) < 2:
            tour = [0, 0]
        visited_customers = vis & x_prime
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
    Algorithm 2: tìm ngưỡng B nhỏ nhất (gần đúng) sao cho lặp Algorithm 1 luôn phủ ít nhất một nửa
    tập khách còn lại mỗi vòng, cho đến khi hết khách; nhị phân trên B với độ rộng khoảng ≤ eps.

    Tham số:
        inst: instance VRPCC.
        oracle: O(Y, B, k) như trong Algorithm 1.
        eps: ngưỡng dừng binary search (upper − lower).

    Trả về: list gồm m phần tử — tuyến đầy đủ (đã ghép nhiều “đợt” Algorithm 1) cho xe 0..m−1.
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
