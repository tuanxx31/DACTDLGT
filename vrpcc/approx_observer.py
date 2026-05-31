
from __future__ import annotations


class ApproxObserver:

    def on_run_start(self, instance_name: str) -> None:
        pass

    def binary_search_init(
        self, *, sum_edge_costs: float, upper_init: float, eps: float
    ) -> None:
        pass

    def binary_step_start(
        self, *, step: int, b: float, lower: float, upper: float
    ) -> None:
        pass

    def greedy_wave_start(self, *, wave: int, n_x: int, need_half: float) -> None:
        pass

    def algo1_start(self, *, n_x: int, budget: float, m_vehicles: int) -> None:
        pass

    def algo1_vehicle(
        self,
        *,
        vehicle: int,
        y: set[int],
        tour: list[int],
        visited_customers: set[int],
        tour_cost: float,
        x_prime_remaining: set[int],
    ) -> None:
        pass

    def algo1_done(self, *, covered: set[int], n_covered: int) -> None:
        pass

    def greedy_wave_fail(
        self, *, b: float, n_covered: int, need_half: float
    ) -> None:
        pass

    def greedy_wave_ok(
        self, *, covered: set[int], n_covered: int, x_remaining: int
    ) -> None:
        pass

    def binary_step_feasible(self, *, step: int, b: float) -> None:
        pass

    def binary_step_infeasible(self, *, step: int, b: float) -> None:
        pass

    def binary_search_done(self, *, upper: float, lower: float, width: float) -> None:
        pass



NULL_OBSERVER = ApproxObserver()
