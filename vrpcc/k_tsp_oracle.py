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
 │    |W| > 8 : Prim MST → tree DP (k-subtree) → DFS       │
 │              shortcut → 2-opt; mọi cost qua tour_length  │
 │                                                          │
 │  Binary search trên tree cost; kiểm tra tour thực tế     │
 │  (gồm cạnh về depot).                                    │
 └───────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import heapq
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


# ── Prim MST ─────────────────────────────────────────────────

def _prim_mst(
    dist: np.ndarray, root: int, nodes: list[int],
) -> dict[int, int]:
    all_nodes = [root] + [v for v in nodes if v != root]
    if len(all_nodes) <= 1:
        return {}
    in_tree = {root}
    parent: dict[int, int] = {}
    pq: list[tuple[float, int, int]] = []
    for v in all_nodes:
        if v != root:
            heapq.heappush(pq, (float(dist[root, v]), v, root))
    while pq and len(in_tree) < len(all_nodes):
        cost, v, p = heapq.heappop(pq)
        if v in in_tree:
            continue
        in_tree.add(v)
        parent[v] = p
        for w in all_nodes:
            if w not in in_tree:
                heapq.heappush(pq, (float(dist[v, w]), w, v))
    return parent


def _build_children(
    parent: dict[int, int], root: int, dist: np.ndarray,
) -> dict[int, list[int]]:
    all_nodes = {root} | set(parent.keys())
    children: dict[int, list[int]] = {v: [] for v in all_nodes}
    for v, p in parent.items():
        children[p].append(v)
    for v in all_nodes:
        children[v].sort(key=lambda c: dist[v, c])
    return children


# ── Tree DP ───────────────────────────────────────────────────

def _tree_dp(
    dist: np.ndarray, root: int, children: dict[int, list[int]],
) -> dict[int, dict[int, float]]:
    """dp[v][j] = chi phí cạnh nhỏ nhất cây con j đỉnh rooted tại v."""
    dp: dict[int, dict[int, float]] = {}
    post_order: list[int] = []
    stack: list[tuple[int, bool]] = [(root, False)]
    while stack:
        v, done = stack.pop()
        if done:
            post_order.append(v)
        else:
            stack.append((v, True))
            for c in reversed(children[v]):
                stack.append((c, False))
    for v in post_order:
        cur: dict[int, float] = {1: 0.0}
        for c in children[v]:
            ec = float(dist[v, c])
            merged: dict[int, float] = {}
            for j1, c1 in cur.items():
                if j1 not in merged or c1 < merged[j1]:
                    merged[j1] = c1
                for j2, c2 in dp[c].items():
                    j = j1 + j2
                    total = c1 + c2 + ec
                    if j not in merged or total < merged[j]:
                        merged[j] = total
            cur = merged
        dp[v] = cur
    return dp


# ── Reconstruct k-subtree ────────────────────────────────────

def _reconstruct(
    dist: np.ndarray, root: int,
    children: dict[int, list[int]],
    dp: dict[int, dict[int, float]],
    target_j: int,
) -> set[int]:
    def _find(v: int, j: int) -> set[int]:
        if j <= 0:
            return set()
        if j == 1:
            return {v}
        result = {v}
        ch = children[v]
        if not ch:
            return result
        partial: list[dict[int, float]] = [{0: 0.0}]
        for idx, c in enumerate(ch):
            ec = float(dist[v, c])
            prev = partial[idx]
            new_p: dict[int, float] = {}
            for j1, c1 in prev.items():
                if j1 not in new_p or c1 < new_p[j1]:
                    new_p[j1] = c1
                for j2, c2 in dp[c].items():
                    jj = j1 + j2
                    tt = c1 + c2 + ec
                    if jj not in new_p or tt < new_p[jj]:
                        new_p[jj] = tt
            partial.append(new_p)
        remaining = j - 1
        for idx in range(len(ch) - 1, -1, -1):
            c = ch[idx]
            ec = float(dist[v, c])
            target_cost = partial[idx + 1].get(remaining, float("inf"))
            skip_cost = partial[idx].get(remaining, float("inf"))
            if abs(skip_cost - target_cost) < 1e-9:
                continue
            for j2 in sorted(dp[c].keys(), reverse=True):
                j1 = remaining - j2
                if j1 < 0:
                    continue
                prev_cost = partial[idx].get(j1, float("inf"))
                total = prev_cost + dp[c][j2] + ec
                if abs(total - target_cost) < 1e-9:
                    result.update(_find(c, j2))
                    remaining = j1
                    break
        return result

    return _find(root, target_j)


# ── DFS shortcut → tour ──────────────────────────────────────

def _subtree_tour(
    root: int, included: set[int],
    children: dict[int, list[int]],
) -> Tour:
    has_inc: dict[int, bool] = {}

    def _mark(v: int) -> bool:
        r = v in included
        for c in children[v]:
            if _mark(c):
                r = True
        has_inc[v] = r
        return r

    _mark(root)
    tour: list[int] = []

    def _dfs(v: int) -> None:
        if v in included:
            tour.append(v)
        for c in children[v]:
            if has_inc.get(c, False):
                _dfs(c)

    _dfs(root)
    if not tour:
        return [0, 0]
    if tour[0] != 0:
        tour.insert(0, 0)
    if tour[-1] != 0:
        tour.append(0)
    return tour


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
    Binary search trên tree cost (đơn điệu) để tìm k lớn nhất nhanh,
    rồi xác nhận bằng tour cost thực tế (gồm cạnh về kho).
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

    # ── Large: MST + tree DP ──
    parent = _prim_mst(inst.dist, 0, W)
    children = _build_children(parent, 0, inst.dist)
    dp = _tree_dp(inst.dist, 0, children)

    # Phase 1: binary search trên tree cost (đơn điệu tăng theo k)
    lo_k, hi_k = 0, len(W)
    while lo_k < hi_k:
        mid = (lo_k + hi_k + 1) // 2
        j = mid + 1
        if j in dp[0] and dp[0][j] <= threshold:
            lo_k = mid
        else:
            hi_k = mid - 1
    k_tree_max = lo_k

    if k_tree_max == 0:
        return [0, 0], set()

    # Phase 2: kiểm tra tour cost thực tế quanh k_tree_max
    search_hi = min(len(W), k_tree_max + 3)
    for k in range(search_hi, 0, -1):
        j = k + 1
        if j not in dp[0]:
            continue
        nodes = _reconstruct(inst.dist, 0, children, dp, j)
        tour = _subtree_tour(0, nodes, children)
        cost = _closed_tour_cost(inst, vehicle, tour)
        if cost <= threshold:
            tour = _two_opt(inst, vehicle, tour)
            return _close_tour(tour), set(tour) - {0}
        if cost <= 2.0 * threshold:
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
