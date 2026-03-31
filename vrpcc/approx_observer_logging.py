"""
Quan sát Algorithm 1–2 và ghi log (tiếng Việt) — tách khỏi `approx_algorithm`.

Logger tên cố định `vrpcc.approx_trace`: chỉ ghi file khi gọi `configure_approx_trace_file`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vrpcc.approx_observer import ApproxObserver

# Logger riêng để không lẫn với thư viện khác; handler gắn qua configure_approx_trace_file.
LOGGER_NAME = "vrpcc.approx_trace"
_log = logging.getLogger(LOGGER_NAME)


def configure_approx_trace_file(
    path: Path | str,
    *,
    mode: str = "w",
) -> Path:
    """
    Gắn một FileHandler UTF-8 cho trace thuật toán (chỉ logger này, không propagate).

    Tham số:
        path: file log (thư mục cha được tạo nếu cần).
        mode: 'w' ghi mới mỗi lần chạy; 'a' nối thêm.

    Trả về: path đã resolve.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(LOGGER_NAME)
    lg.handlers.clear()
    lg.setLevel(logging.INFO)
    lg.propagate = False
    fh = logging.FileHandler(p, encoding="utf-8", mode=mode)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(message)s"))
    lg.addHandler(fh)
    return p.resolve()


def _fmt_vertices(s: set[int]) -> str:
    if not s:
        return "∅"
    return "{" + ",".join(str(v) for v in sorted(s)) + "}"


def _sep() -> None:
    _log.info("%s", "-" * 72)


class LoggingApproxObserver(ApproxObserver):
    """Ghi log chi tiết nhị phân B, lượt tham lam, Algorithm 1 (định dạng từng khối)."""

    def on_run_start(self, instance_name: str) -> None:
        _sep()
        _log.info("INSTANCE: %s", instance_name or "instance")
        _sep()

    def binary_search_init(
        self, *, sum_edge_costs: float, upper_init: float, eps: float
    ) -> None:
        _log.info("")
        _log.info("NHỊ PHÂN TRÊN B")
        _log.info("  Tổng Σ c_ij (i<j) = %.6g", sum_edge_costs)
        _log.info("  Upper ban đầu      = 2× tổng = %.6g", upper_init)
        _log.info("  eps dừng           = %g", eps)
        _log.info("")

    def binary_step_start(
        self, *, step: int, b: float, lower: float, upper: float
    ) -> None:
        _log.info("  ── Bước nhị phân %d ──", step)
        _log.info("     Thử B = %.6g", b)
        _log.info("     Khoảng [lower, upper] = [%.6g , %.6g]   (rộng %.6g)", lower, upper, upper - lower)

    def greedy_wave_start(self, *, wave: int, n_x: int, need_half: float) -> None:
        _log.info("")
        _log.info("    Lượt tham lam %d", wave)
        _log.info("      |X| hiện tại     = %d", n_x)
        _log.info("      Cần |phủ| tối thiểu = %.6g (một nửa |X|)", need_half)

    def algo1_start(self, *, n_x: int, budget: float, m_vehicles: int) -> None:
        _log.info("      Algorithm 1 (một vòng qua %d xe), B = %.6g, |X| = %d", m_vehicles, budget, n_x)

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
        _log.info("        xe %d:", vehicle)
        _log.info("          Y (khách khả thi ∩ X′) = %s", _fmt_vertices(y))
        _log.info("          Tuyến                      = %s", tour)
        _log.info("          Phủ (trong X′)           = %s", _fmt_vertices(visited_customers))
        _log.info("          Chi phí tuyến            = %.4f", tour_cost)
        _log.info("          X′ sau xe này            = %s", _fmt_vertices(x_prime_remaining))

    def algo1_done(self, *, covered: set[int], n_covered: int) -> None:
        _log.info("      → Tổng phủ trong X: %s  (%d khách)", _fmt_vertices(covered), n_covered)

    def greedy_wave_fail(
        self, *, b: float, n_covered: int, need_half: float
    ) -> None:
        _log.info("    KẾT: không đạt — |phủ|=%d < %.6g → B = %.6g không khả thi", n_covered, need_half, b)
        _log.info("")

    def greedy_wave_ok(
        self, *, covered: set[int], n_covered: int, x_remaining: int
    ) -> None:
        _log.info("    KẾT: phủ %s (%d khách), |X| còn = %d", _fmt_vertices(covered), n_covered, x_remaining)

    def binary_step_feasible(self, *, step: int, b: float) -> None:
        _log.info("  → Bước %d: KHẢ THI  →  upper := %.6g", step, b)
        _log.info("")

    def binary_step_infeasible(self, *, step: int, b: float) -> None:
        _log.info("  → Bước %d: KHÔNG khả thi  →  lower := %.6g", step, b)
        _log.info("")

    def binary_search_done(self, *, upper: float, lower: float, width: float) -> None:
        _log.info("KẾT THÚC NHỊ PHÂN")
        _log.info("  B (upper) ≈ %.6g", upper)
        _log.info("  Độ rộng khoảng [lower, upper] = %.6g", width)
        _sep()
        _log.info("")
