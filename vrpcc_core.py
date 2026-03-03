#!/usr/bin/env python3
"""
Phần lời giải cốt lõi cho bài toán VRPCC theo bài báo:
"An Approximation Algorithm for Vehicle Routing with Compatibility Constraints".

Mục tiêu của module này là dễ hiểu và đúng cho instance nhỏ:
- Algorithm 1 (greedy MCG-VRP)
- Algorithm 2 (tìm kiếm nhị phân trên ngân sách + lặp giảm một nửa tập chưa phủ)
- Oracle exact (độ phức tạp hàm mũ) phù hợp cho demo nhỏ
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
import math
from typing import Dict, Iterable, List, Sequence, Set, Tuple


Node = int
Route = List[Node]


@dataclass
class VRPCCInstance:
    dist: List[List[float]]
    compatible: List[Set[Node]]
    points: List[Tuple[float, float]] | None = None

    @property
    def n_customers(self) -> int:
        return len(self.dist) - 1

    @property
    def n_vehicles(self) -> int:
        return len(self.compatible)

    @property
    def vehicles(self) -> List[int]:
        return list(range(self.n_vehicles))

    @property
    def customers(self) -> Set[Node]:
        return set(range(1, len(self.dist)))

    def validate(self) -> None:
        n = len(self.dist)
        if n == 0:
            raise ValueError("Ma trận khoảng cách không được rỗng.")
        if any(len(row) != n for row in self.dist):
            raise ValueError("Ma trận khoảng cách phải là ma trận vuông.")
        if self.n_vehicles == 0:
            raise ValueError("Cần ít nhất 1 xe.")

        valid_nodes = self.customers
        for k, nodes in enumerate(self.compatible):
            unknown = set(nodes) - valid_nodes
            if unknown:
                raise ValueError(f"Xe {k} có ID khách hàng không hợp lệ: {sorted(unknown)}")

        serviceable = set().union(*self.compatible)
        missing = valid_nodes - serviceable
        if missing:
            raise ValueError(
                f"Instance không khả thi: các khách hàng không xe nào phục vụ được: {sorted(missing)}"
            )


@dataclass
class RoundLog:
    round_idx: int
    budget: float
    uncovered_before: List[int]
    covered_this_round: List[int]
    uncovered_after: List[int]
    routes: Dict[int, Route]


@dataclass
class SearchLog:
    iteration: int
    lower: float
    upper: float
    guess_budget: float
    solved: bool
    rounds_used: int


@dataclass
class VRPCCSolution:
    tours_by_vehicle: Dict[int, List[Route]]
    makespan: float
    makespan_before_local_search: float
    chosen_budget: float
    lower_bound: float
    upper_bound: float
    search_iterations: int
    local_search_applied: bool
    local_search_moves: int
    round_logs: List[RoundLog]
    search_logs: List[SearchLog]


def euclidean_distance_matrix(points: Sequence[Tuple[float, float]]) -> List[List[float]]:
    n = len(points)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = points[i]
        for j in range(n):
            xj, yj = points[j]
            dist[i][j] = math.hypot(xi - xj, yi - yj)
    return dist


def route_cost(dist: List[List[float]], route: Sequence[Node]) -> float:
    if not route:
        return 0.0
    total = dist[0][route[0]]
    for i in range(len(route) - 1):
        total += dist[route[i]][route[i + 1]]
    total += dist[route[-1]][0]
    return total


def _merge_rounds(rounds: List[Route]) -> Route:
    merged: Route = []
    for r in rounds:
        merged.extend(r)
    return merged


def _two_opt_route(dist: List[List[float]], route: Route) -> Route:
    """
    2-opt cải thiện thứ tự thăm khách cho một route.
    Route chỉ chứa khách, depot được ngầm định ở đầu/cuối.
    """
    if len(route) <= 2:
        return list(route)

    best = list(route)
    best_cost = route_cost(dist, best)
    improved = True

    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + list(reversed(best[i : j + 1])) + best[j + 1 :]
                c = route_cost(dist, candidate)
                if c + 1e-9 < best_cost:
                    best = candidate
                    best_cost = c
                    improved = True
                    break
            if improved:
                break
    return best


def _best_insertion_route(dist: List[List[float]], route: Route, node: Node) -> Route:
    """
    Chèn node vào route tại vị trí có chi phí nhỏ nhất.
    """
    if not route:
        return [node]

    best_route: Route = []
    best_cost = math.inf
    for pos in range(len(route) + 1):
        candidate = route[:pos] + [node] + route[pos:]
        c = route_cost(dist, candidate)
        if c < best_cost:
            best_cost = c
            best_route = candidate
    return best_route


def _local_search_two_opt_and_relocation(
    instance: VRPCCInstance,
    tours_by_vehicle: Dict[int, List[Route]],
    max_moves: int = 500,
) -> Tuple[Dict[int, List[Route]], float, int]:
    """
    Hậu xử lý theo phần thực nghiệm của paper:
    - 2-opt trên từng xe.
    - Relocation nhắm makespan:
      luôn lấy xe có tuyến dài nhất, thử chuyển từng khách sang xe tương thích khác
      (chèn vị trí tốt nhất), nhận move nếu makespan giảm.
    Lặp cho tới khi makespan không giảm thêm.
    """
    dist = instance.dist
    routes: Dict[int, Route] = {k: _merge_rounds(tours_by_vehicle[k]) for k in instance.vehicles}

    # 2-opt ban đầu cho từng tuyến.
    for k in instance.vehicles:
        routes[k] = _two_opt_route(dist, routes[k])

    costs: Dict[int, float] = {k: route_cost(dist, routes[k]) for k in instance.vehicles}
    moves = 0

    while moves < max_moves:
        donor = max(instance.vehicles, key=lambda k: costs[k])
        donor_route = routes[donor]
        current_makespan = costs[donor]
        if not donor_route:
            break

        best_new_makespan = current_makespan
        best_new_total = sum(costs.values())
        best_move: Tuple[int, int, Route, Route, float, float] | None = None

        for node in list(donor_route):
            donor_removed = list(donor_route)
            donor_removed.remove(node)
            donor_removed = _two_opt_route(dist, donor_removed)
            donor_cost = route_cost(dist, donor_removed)

            for receiver in instance.vehicles:
                if receiver == donor:
                    continue
                if node not in instance.compatible[receiver]:
                    continue

                receiver_inserted = _best_insertion_route(dist, routes[receiver], node)
                receiver_inserted = _two_opt_route(dist, receiver_inserted)
                receiver_cost = route_cost(dist, receiver_inserted)

                new_costs = dict(costs)
                new_costs[donor] = donor_cost
                new_costs[receiver] = receiver_cost
                new_makespan = max(new_costs.values())
                new_total = sum(new_costs.values())

                better_makespan = new_makespan + 1e-9 < best_new_makespan
                tie_break = abs(new_makespan - best_new_makespan) <= 1e-9 and new_total + 1e-9 < best_new_total
                if better_makespan or tie_break:
                    best_new_makespan = new_makespan
                    best_new_total = new_total
                    best_move = (
                        donor,
                        receiver,
                        donor_removed,
                        receiver_inserted,
                        donor_cost,
                        receiver_cost,
                    )

        if best_move is None:
            break

        donor, receiver, donor_new, receiver_new, donor_cost, receiver_cost = best_move
        routes[donor] = donor_new
        routes[receiver] = receiver_new
        costs[donor] = donor_cost
        costs[receiver] = receiver_cost
        moves += 1

    improved_tours: Dict[int, List[Route]] = {}
    for k in instance.vehicles:
        improved_tours[k] = [routes[k]] if routes[k] else []

    improved_makespan = max(costs.values()) if costs else 0.0
    return improved_tours, improved_makespan, moves


def _best_tour_for_subset(dist: List[List[float]], subset: Sequence[Node]) -> Tuple[float, Route]:
    """
    Giải TSP exact trên tập con (đi từ depot và quay về depot) bằng Held-Karp.
    Trả về chi phí nhỏ nhất và thứ tự thăm.
    """
    if not subset:
        return 0.0, []

    nodes = list(subset)
    size = len(nodes)
    dp: Dict[Tuple[int, int], float] = {}
    parent: Dict[Tuple[int, int], int] = {}

    for j in range(size):
        mask = 1 << j
        dp[(mask, j)] = dist[0][nodes[j]]
        parent[(mask, j)] = -1

    for mask in range(1, 1 << size):
        for j in range(size):
            if not (mask & (1 << j)):
                continue
            cur_key = (mask, j)
            if cur_key not in dp:
                continue
            for nxt in range(size):
                if mask & (1 << nxt):
                    continue
                nmask = mask | (1 << nxt)
                candidate = dp[cur_key] + dist[nodes[j]][nodes[nxt]]
                nxt_key = (nmask, nxt)
                if nxt_key not in dp or candidate < dp[nxt_key]:
                    dp[nxt_key] = candidate
                    parent[nxt_key] = j

    full = (1 << size) - 1
    best_cost = math.inf
    best_last = -1
    for j in range(size):
        cost = dp[(full, j)] + dist[nodes[j]][0]
        if cost < best_cost:
            best_cost = cost
            best_last = j

    order_idx: List[int] = []
    mask = full
    j = best_last
    while j != -1:
        order_idx.append(j)
        prev = parent[(mask, j)]
        mask ^= 1 << j
        j = prev
    order_idx.reverse()
    return best_cost, [nodes[idx] for idx in order_idx]


def oracle_orienteering_exact(
    instance: VRPCCInstance,
    candidates: Set[Node],
    vehicle: int,
    budget: float,
    beta: float = 1.0,
) -> Route:
    """
    Oracle exact (hàm mũ), dùng cho instance nhỏ.
    Mục tiêu: tối đa số node được phủ với ràng buộc route_cost <= beta * budget.
    """
    allowed = sorted(candidates & instance.compatible[vehicle])
    if not allowed:
        return []

    limit = beta * budget + 1e-9
    best_route: Route = []
    best_cost = math.inf

    for subset_size in range(len(allowed), 0, -1):
        found_any = False
        for subset in combinations(allowed, subset_size):
            c, tour = _best_tour_for_subset(instance.dist, subset)
            if c <= limit:
                found_any = True
                if c < best_cost:
                    best_cost = c
                    best_route = tour
        if found_any:
            break

    return best_route


def algorithm1_mcg_vrp(
    instance: VRPCCInstance,
    uncovered: Set[Node],
    budget: float,
    beta: float,
) -> Dict[int, Route]:
    """Algorithm 1 trong bài báo."""
    remaining = set(uncovered)
    routes: Dict[int, Route] = {}
    for vehicle in instance.vehicles:
        route = oracle_orienteering_exact(instance, remaining, vehicle, budget, beta=beta)
        routes[vehicle] = route
        remaining -= set(route)
    return routes


def _all_pair_undirected_sum(dist: List[List[float]]) -> float:
    total = 0.0
    n = len(dist)
    for i in range(n):
        for j in range(i + 1, n):
            total += dist[i][j]
    return total


def solve_vrpcc_approx(
    instance: VRPCCInstance,
    eps: float = 1e-2,
    beta: float = 1.0,
    apply_local_search: bool = True,
) -> VRPCCSolution:
    """Algorithm 2 trong bài báo."""
    instance.validate()
    if eps <= 0:
        raise ValueError("eps phải > 0.")
    if beta < 1.0:
        raise ValueError("beta phải >= 1.")

    def try_budget(B: float) -> Tuple[bool, Dict[int, List[Route]], List[RoundLog]]:
        uncovered = set(instance.customers)
        tours: Dict[int, List[Route]] = {k: [] for k in instance.vehicles}
        logs: List[RoundLog] = []
        round_idx = 0

        while uncovered:
            round_idx += 1
            before = sorted(uncovered)
            routes = algorithm1_mcg_vrp(instance, uncovered, B, beta=beta)
            covered = set().union(*(set(r) for r in routes.values()))

            if len(covered) < len(uncovered) / 2.0:
                logs.append(
                    RoundLog(
                        round_idx=round_idx,
                        budget=B,
                        uncovered_before=before,
                        covered_this_round=sorted(covered),
                        uncovered_after=before,
                        routes=routes,
                    )
                )
                return False, {}, logs

            uncovered -= covered
            after = sorted(uncovered)
            for k, route in routes.items():
                if route:
                    tours[k].append(route)

            logs.append(
                RoundLog(
                    round_idx=round_idx,
                    budget=B,
                    uncovered_before=before,
                    covered_this_round=sorted(covered),
                    uncovered_after=after,
                    routes=routes,
                )
            )

        return True, tours, logs

    lower = 0.0
    upper = 2.0 * _all_pair_undirected_sum(instance.dist)

    best_tours: Dict[int, List[Route]] = {k: [] for k in instance.vehicles}
    best_round_logs: List[RoundLog] = []
    search_logs: List[SearchLog] = []
    iteration = 0

    while upper - lower >= eps:
        iteration += 1
        guess = (lower + upper) / 2.0
        solved, candidate_tours, candidate_round_logs = try_budget(guess)
        search_logs.append(
            SearchLog(
                iteration=iteration,
                lower=lower,
                upper=upper,
                guess_budget=guess,
                solved=solved,
                rounds_used=len(candidate_round_logs),
            )
        )
        if solved:
            upper = guess
            best_tours = candidate_tours
            best_round_logs = candidate_round_logs
        else:
            lower = guess

    if not any(best_tours.values()):
        solved, candidate_tours, candidate_round_logs = try_budget(upper)
        if solved:
            best_tours = candidate_tours
            best_round_logs = candidate_round_logs

    makespan = 0.0
    for k in instance.vehicles:
        total = sum(route_cost(instance.dist, route) for route in best_tours[k])
        makespan = max(makespan, total)
    makespan_before_local_search = makespan

    local_search_moves = 0
    if apply_local_search:
        best_tours, makespan, local_search_moves = _local_search_two_opt_and_relocation(
            instance,
            best_tours,
        )

    return VRPCCSolution(
        tours_by_vehicle=best_tours,
        makespan=makespan,
        makespan_before_local_search=makespan_before_local_search,
        chosen_budget=upper,
        lower_bound=lower,
        upper_bound=upper,
        search_iterations=iteration,
        local_search_applied=apply_local_search,
        local_search_moves=local_search_moves,
        round_logs=best_round_logs,
        search_logs=search_logs,
    )


def build_demo_instance() -> VRPCCInstance:
    points = [
        (0.0, 0.0),   # depot (node 0)
        (1.0, 2.0),
        (2.0, 1.0),
        (3.0, 2.0),
        # Dời node 4 xuống thấp hơn để nhãn nhà 2 và 4 không đè lên nhau trên bản đồ.
        (5.0, 0.1),
        (-1.0, 3.0),
        (-2.0, 1.0),
        (-3.0, 2.0),
        (0.0, 4.0),
    ]
    compatible = [
        {1, 2, 3, 4, 8},
        {3, 4, 5, 6},
        {1, 5, 6, 7, 8},
    ]
    instance = VRPCCInstance(
        dist=euclidean_distance_matrix(points),
        compatible=compatible,
        points=points,
    )
    instance.validate()
    return instance


def instance_to_json_dict(instance: VRPCCInstance) -> dict:
    payload = {
        "dist": instance.dist,
        "compatible": [sorted(list(nodes)) for nodes in instance.compatible],
    }
    if instance.points is not None:
        payload["points"] = [list(p) for p in instance.points]
    return payload


def instance_from_json_str(raw: str) -> VRPCCInstance:
    data = json.loads(raw)
    if "compatible" not in data:
        raise ValueError("JSON bắt buộc có trường 'compatible'.")

    compatible = [set(map(int, nodes)) for nodes in data["compatible"]]
    points = None

    if "dist" in data:
        dist = [[float(v) for v in row] for row in data["dist"]]
    elif "points" in data:
        points = [tuple(map(float, p)) for p in data["points"]]
        dist = euclidean_distance_matrix(points)
    else:
        raise ValueError("JSON bắt buộc có 'dist' hoặc 'points'.")

    if "points" in data:
        points = [tuple(map(float, p)) for p in data["points"]]

    instance = VRPCCInstance(dist=dist, compatible=compatible, points=points)
    instance.validate()
    return instance


def format_solution(solution: VRPCCSolution, instance: VRPCCInstance) -> str:
    lines: List[str] = []
    lines.append("=== Xấp xỉ VRPCC (Algorithm 1 + 2) ===")
    lines.append(f"Số khách hàng: {instance.n_customers}, Số xe: {instance.n_vehicles}")
    lines.append(f"Độ dài lớn nhất (makespan): {solution.makespan:.4f}")
    if solution.local_search_applied:
        lines.append(
            "Hậu xử lý (2-opt + relocation): "
            f"{solution.makespan_before_local_search:.4f} -> {solution.makespan:.4f}, "
            f"số_lần_relocation={solution.local_search_moves}"
        )
    lines.append(f"Ngân sách B được chọn (cận trên sau binary-search): {solution.chosen_budget:.4f}")
    lines.append(f"Số vòng binary-search: {solution.search_iterations}")
    lines.append("")

    for k in instance.vehicles:
        total = sum(route_cost(instance.dist, route) for route in solution.tours_by_vehicle[k])
        lines.append(f"Xe {k}: tổng = {total:.4f}")
        if not solution.tours_by_vehicle[k]:
            lines.append("  [không có tuyến]")
            continue
        for ridx, route in enumerate(solution.tours_by_vehicle[k], 1):
            c = route_cost(instance.dist, route)
            lines.append(f"  Vòng {ridx}: {route} | chi_phí={c:.4f}")
        lines.append("")

    lines.append("Nhật ký binary-search:")
    for s in solution.search_logs:
        status = "ĐẠT" if s.solved else "KHÔNG ĐẠT"
        lines.append(
            f"  iter={s.iteration:02d} "
            f"[l={s.lower:.4f}, u={s.upper:.4f}] "
            f"B={s.guess_budget:.4f} -> {status}, số_vòng={s.rounds_used}"
        )

    lines.append("")
    lines.append("Mức độ bao phủ từng vòng với B cuối cùng được chấp nhận:")
    for r in solution.round_logs:
        lines.append(
            f"  vòng={r.round_idx} B={r.budget:.4f} "
            f"đã_phủ={r.covered_this_round} "
            f"còn_lại={r.uncovered_after}"
        )

    return "\n".join(lines)


__all__ = [
    "VRPCCInstance",
    "VRPCCSolution",
    "RoundLog",
    "SearchLog",
    "build_demo_instance",
    "euclidean_distance_matrix",
    "route_cost",
    "solve_vrpcc_approx",
    "instance_to_json_dict",
    "instance_from_json_str",
    "format_solution",
]
