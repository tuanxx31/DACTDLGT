"""
Oracle O(Y, B, vehicle) cho MCG-VRP — bicriteria k-TSP (mục 3 bài báo).

══════════════════════════════════════════════════════════════
 ORACLE — THEO MỤC 3 BÀI BÁO (Corollary 4)
══════════════════════════════════════════════════════════════

 ┌─ Input ───────────────────────────────────────────────────┐
 │  Y       : tập khách hàng cần xét (= X' ∩ V_i)          │
 │  B       : ngân sách chi phí (giá trị B trong Algo 2)    │
 │  vehicle : chỉ số xe i                                   │
 └───────────────────────────────────────────────────────────┘

 ┌─ Output ──────────────────────────────────────────────────┐
 │  tour : tuyến khép kín [0, v1, …, vk, 0] (depot → … →   │
 │         depot). Chi phí = tổng cạnh **kể cả về kho**.    │
 │  vis  : tập khách thực sự nằm trên tuyến                 │
 └───────────────────────────────────────────────────────────┘

 ┌─ Method (theo paper mục 4 / Corollary 4) ─────────────────┐
 │  Bicriteria k-TSP: tối đa hoá |coverage| sao cho         │
 │    cost(closed tour) ≤ β·B, với β = 5.                   │
 │                                                          │
 │  Bài báo viết: dùng thuật toán xấp xỉ k-TSP hệ số 5 từ   │
 │  [19] làm oracle O. Tham chiếu [19] là Garg (FOCS’96):   │
 │  xấp xỉ **k-MST** (cây nhỏ nhất phủ k đỉnh). Trong       │
 │  thực nghiệm, khung chuẩn là: cây (MST) → tour (shortcut │
 │  kiểu double-tree/DFS) + tối ưu cục bộ; **β=5** là hệ   │
 │  số bicriteria như bài báo.                              │
 │                                                          │
 │  Cài đặt:                                                │
 │    |W| ≤ 8 : exact (tổ hợp + hoán vị), cost = tour khép  │
 │    |W| > 8 : greedy từ depot — mỗi bước thêm khách j sao  │
 │              cho tăng chi phí tour khép kín (kể cả về    │
 │              kho) là nhỏ nhất, dừng khi không còn j    │
 │              nào thỏa cost ≤ β·B; sau đó 2-opt.          │
 └───────────────────────────────────────────────────────────┘
"""

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
    """Chi phí closed tour (depot → … → depot), thống nhất với `VRPCCInstance.tour_length`."""
    t = _close_tour(tour)
    if len(t) < 2:
        return 0.0
    return float(inst.tour_length(t, vehicle))


# ── Exact brute-force (|W| ≤ 8) ──────────────────────────────

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


# ── Greedy (|W| lớn): depot → thêm khách tăng cost khép kín ít nhất ──


def _greedy_min_increment_tour(
    inst: VRPCCInstance,
    vehicle: int,
    W: list[int],
    threshold: float,
) -> Tour:
    """
    Bắt đầu tại depot (0). Lặp: trong các khách còn lại (thỏa u), chọn j
    sao cho **tăng** chi phí tour khép kín là nhỏ nhất:

        Δ(j) = c(cur,j) + c(j,0) − c(cur,0)

    (so với việc đi thẳng từ cur về kho). Chỉ thêm j nếu chi phí tour đầy đủ
    0 → … → j → 0 không vượt `threshold` (đã gồm cạnh về depot).

    Dừng khi không còn j nào thỏa ngân sách.
    """
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
            if closed > threshold + 1e-9:
                continue
            delta = c_cur_j + c_j0 - c_cur0
            if delta < best_delta - 1e-12:
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


# ── 2-opt ─────────────────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════════
# Main oracle
# ══════════════════════════════════════════════════════════════

def oracle_k_tsp(
    inst: VRPCCInstance,
    Y: set[int],
    budget: float,
    vehicle: int,
    *,
    beta: float = 5.0,
) -> tuple[Tour, set[int]]:
    """
    Oracle bicriteria (mục 3):
      max |coverage| subject to cost(closed tour) ≤ β·B.

    `cost` luôn là chi phí tour khép kín qua depot (xem `VRPCCInstance.tour_length`).
    Với |W| lớn: greedy từ depot, mỗi bước kiểm tra ngân sách **kể cả về kho**.
    """
    W = sorted(j for j in Y if j >= 1 and inst.u[vehicle, j] == 1)
    if not W or budget <= 0:
        return [0, 0], set()

    threshold = beta * budget + 1e-9

    # ── Small: exact brute-force ──
    if len(W) <= EXACT_THRESHOLD:
        for k in range(len(W), 0, -1):
            t, c = _exact_k_subset(inst, vehicle, W, k)
            t = _two_opt(inst, vehicle, t)
            c = _closed_tour_cost(inst, vehicle, t)
            if c <= threshold:
                return _close_tour(t), set(t) - {0}
        return [0, 0], set()

    # ── Large: greedy (min tăng cost tour khép kín) + 2-opt ──
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
    """Đóng gói oracle theo signature O(Y, B, vehicle) cho Algorithm 1."""
    return lambda Y, B, veh: oracle_k_tsp(inst, Y, B, veh, beta=beta)
