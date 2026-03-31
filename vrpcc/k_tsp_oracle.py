"""
Oracle O(Y, B, vehicle) cho MCG-VRP — thuật toán xấp xỉ k-TSP.

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
 │         depot) thoả cost(tour) ≤ β·B                     │
 │  vis  : tập khách thực sự nằm trên tuyến                 │
 └───────────────────────────────────────────────────────────┘

 ┌─ Method ──────────────────────────────────────────────────┐
 │  Bicriteria k-TSP:                                       │
 │    "Tối đa hoá k (số khách) sao cho cost ≤ β·B"         │
 │                                                          │
 │  Paper mục 4 dùng β = 5 (5-approx k-TSP từ [19]).       │
 │                                                          │
 │  Cài đặt:                                                │
 │    |W| ≤ 8 : exact (tổ hợp + hoán vị)                   │
 │    |W| > 8 : Prim MST → tree DP (k-subtree tối ưu)      │
 │              → DFS shortcut → 2-opt                      │
 │                                                          │
 │  Binary search trên tree cost (đơn điệu) để tìm nhanh   │
 │  k lớn nhất, rồi kiểm tra tour cost thực tế quanh đó.   │
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


def _tour_cost(inst: VRPCCInstance, tour: Tour) -> float:
    t = _close_tour(tour)
    if len(t) < 2:
        return 0.0
    return float(sum(inst.dist[t[i], t[i + 1]] for i in range(len(t) - 1)))


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
        c = _tour_cost(inst, seq)
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

def _two_opt(inst: VRPCCInstance, tour: Tour) -> Tour:
    tour = _close_tour(tour)
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
      max |coverage| subject to cost(tour) ≤ β·B.

    Binary search trên tree cost (đơn điệu) để tìm k lớn nhất nhanh,
    rồi xác nhận bằng tour cost thực tế.
    """
    W = sorted(j for j in Y if j >= 1 and inst.u[vehicle, j] == 1)
    if not W or budget <= 0:
        return [0, 0], set()

    threshold = beta * budget + 1e-9

    # ── Small: exact brute-force ──
    if len(W) <= EXACT_THRESHOLD:
        for k in range(len(W), 0, -1):
            t, c = _exact_k_subset(inst, vehicle, W, k)
            t = _two_opt(inst, t)
            c = _tour_cost(inst, t)
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
        cost = _tour_cost(inst, tour)
        if cost <= threshold:
            tour = _two_opt(inst, tour)
            return _close_tour(tour), set(tour) - {0}
        if cost <= 2.0 * threshold:
            tour = _two_opt(inst, tour)
            cost = _tour_cost(inst, tour)
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
