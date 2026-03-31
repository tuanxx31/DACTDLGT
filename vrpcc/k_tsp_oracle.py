"""
Oracle O(Y, B, vehicle) cho MCG-VRP (mục 3 bài báo) — mô phỏng oracle bicriteria k-TSP/orienteering.

Khung giống paper (tối đa hoá |cover| với cost ≤ beta·B, binary search theo k), nhưng cài đặt là
heuristic: instance nhỏ brute-force subset + TSP exact; lớn k khách gần depot + nearest neighbor + 2-opt.
Đây không phải oracle 2-approx k-TSP đúng nghĩa [20]; beta=2.0 chỉ bám tham số lý thuyết của paper,
không mang theo bảo đảm xấp xỉ như khi dùng oracle gốc.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Callable

import numpy as np

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance

Tour = list[int]


def _tour_cost(inst: VRPCCInstance, tour: Tour) -> float:
    """
    Tổng chi phí cạnh dọc theo chuỗi đỉnh `tour` (không kiểm tra u — chỉ dùng dist).

    Tham số:
        inst: instance (lấy ma trận dist).
        tour: [v0, v1, ..., vk]. Nếu v0==0 (xuất phát kho) và vk!=0, cộng thêm cạnh vk→0.

    Trả về: tổng dist[vi, vi+1] (+ đoạn về kho nếu cần); tour ngắn → 0.
    """
    if len(tour) < 2:
        return 0.0
    s = float(sum(inst.dist[tour[i], tour[i + 1]] for i in range(len(tour) - 1)))
    if tour[0] == 0 and tour[-1] != 0:
        s += float(inst.dist[tour[-1], 0])
    return s


def _exact_best_tour_on_subset(inst: VRPCCInstance, vehicle: int, subset: list[int]) -> tuple[Tour, float]:
    """
    TSP nhỏ exact: tuyến khép kín tối ưu 0 → thăm đủ mọi đỉnh trong subset (một hoán vị) → 0.

    Tham số:
        inst: khoảng cách metric.
        vehicle: chỉ xét hoán vị thỏa u[vehicle, j]=1 cho mọi j trên tuyến.
        subset: danh sách khách (không gồm depot).

    Trả về: (tuyến tốt nhất, chi phí). subset rỗng → [0,0], cost 0.
    """
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
    """
    Chọn đúng k khách trong W và tìm tuyến khép kín qua depot có chi phí nhỏ nhất (duyệt tổ hợp + TSP con).

    Tham số:
        inst, vehicle: như trên.
        W: tập khách ứng viên (đã lọc khả thi với xe).
        k: số khách phải thăm (0 → [0,0]).

    Trả về: (tuyến, chi phí).
    """
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
    """
    Heuristic Nearest Neighbor: xuất phát từ depot, mỗi bước chọn khách khả thi (u) gần đỉnh hiện tại nhất.

    Tham số:
        inst: khoảng cách.
        vehicle: ràng buộc u.
        nodes: tập đỉnh khách cần ghép vào tuyến (chỉ dùng các đỉnh thỏa u).

    Trả về: tuyến khép kín [0, ..., 0].
    """
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
    """
    Cải thiện tuyến bằng 2-opt trên phần giữa (giữ cố định depot đầu/cuối), lặp đến khi không cải thiện.

    Tham số:
        inst: ma trận dist.
        tour: [0, v1, ..., vk, 0].

    Trả về: tuyến sau 2-opt (cùng tập đỉnh, thứ tự có thể đổi).
    """
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
    """
    Tạo tuyến thăm k khách trong W: instance nhỏ thì exact + 2-opt; lớn thì chọn k khách gần depot rồi NN + 2-opt.

    Tham số:
        inst, vehicle: instance và xe.
        W: ứng viên khách.
        k: số khách cần phủ trên tuyến (capped bởi |W|).

    Trả về: (tuyến khép kín, chi phí theo dist).
    """
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
    beta: float = 2.0,
    exact_max_w: int = 12,
) -> tuple[Tour, set[int]]:
    """
    Oracle bicriteria (khung như paper): tối đa hoá số khách trong Y mà xe được phép thăm,
    với chi phí tuyến ≤ beta × budget (binary search theo k). Nếu không có k nào thỏa, trả [0,0] và ∅.

    Tham số:
        inst: VRPCC.
        Y: tập chỉ số khách đang xét.
        budget: B (ngân sách chi phí).
        vehicle: chỉ số xe.
        beta: hệ số bicriteria (paper lý thuyết dùng beta=2 với k-TSP [20]; oracle thực tế ở đây là heuristic).
        exact_max_w: nếu |W| nhỏ và k nhỏ thì dùng exact subset.

    Trả về:
        - tuyến khép kín từ depot;
        - tập khách thực sự nằm trên tuyến (không gồm 0).
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
    if not best_vis:
        return [0, 0], set()
    return best_tour, best_vis


def make_oracle(
    inst: VRPCCInstance,
    *,
    beta: float = 2.0,
) -> Callable[[set[int], float, int], tuple[Tour, set[int]]]:
    """
    Đóng gói `oracle_k_tsp` với instance và beta cố định thành hàm một dòng dùng cho Algorithm 1.

    Tham số:
        inst: VRPCC cố định.
        beta: hệ số bicriteria truyền vào mọi lần gọi oracle.

    Trả về: callable (Y, B, vehicle) → (tuyến, tập khách đã thăm), signature khớp `OracleFn` trong approx_algorithm.
    """
    return lambda Y, B, veh: oracle_k_tsp(inst, Y, B, veh, beta=beta)
