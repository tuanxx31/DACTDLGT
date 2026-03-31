"""
Hình vẽ báo cáo (không logic giải).

Cột/trục ưu tiên: thuật toán bài báo (approx); MIP là baseline so sánh.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from vrpcc.instance import VRPCCInstance


def plot_objective_time_bars(
    labels: list[str],
    approx_times: list[float],
    mip_times: list[float],
    approx_objs: list[float],
    mip_objs: list[float | None],
    out_path: str | Path,
    title: str = "VRPCC: thuật toán bài báo (chính) vs MIP (so sánh)",
) -> None:
    """Grouped bars: approx bên trái (ưu tiên), MIP bên phải (tham chiếu)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(labels))
    w = 0.35
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax1.bar(x - w / 2, approx_times, width=w, label="Bài báo (approx), thời gian (s)")
    ax1.bar(x + w / 2, mip_times, width=w, label="MIP tham chiếu, thời gian (s)")
    ax1.set_ylabel("Seconds")
    ax1.legend()
    ax1.set_title(title)

    mip_plot = [v if v is not None else float("nan") for v in mip_objs]
    ax2.bar(x - w / 2, approx_objs, width=w, label="Bài báo (approx), makespan")
    ax2.bar(x + w / 2, mip_plot, width=w, label="MIP tham chiếu, makespan")
    ax2.set_ylabel("Makespan")
    ax2.legend()
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_approx_only_bars(
    labels: list[str],
    approx_times: list[float],
    approx_objs: list[float],
    out_path: str | Path,
    title: str = "VRPCC: thuật toán bài báo (chưa chạy MIP)",
) -> None:
    """Chỉ thời gian + makespan của approx — dùng khi --skip-mip."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(labels))
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax1.bar(x, approx_times, width=0.5, label="Thời gian (s)")
    ax1.set_ylabel("Seconds")
    ax1.legend()
    ax1.set_title(title)
    ax2.bar(x, approx_objs, width=0.5, label="Makespan")
    ax2.set_ylabel("Makespan")
    ax2.legend()
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_routes_map(
    inst: VRPCCInstance,
    routes: list[list[int]],
    out_path: str | Path,
    title: str = "Routes",
) -> None:
    """Vẽ tuyến 2D nếu instance có coords."""
    if inst.coords is None:
        return
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    xy = inst.coords
    ax.scatter(xy[0, 0], xy[0, 1], c="black", s=120, marker="s", label="Depot")
    ax.scatter(xy[1:, 0], xy[1:, 1], c="gray", s=40, label="Customers")
    cmap = plt.colormaps["tab10"]
    for k, route in enumerate(routes):
        pts = [xy[i] for i in route if i < len(xy)]
        if len(pts) < 2:
            continue
        arr = np.array(pts)
        ax.plot(arr[:, 0], arr[:, 1], "-o", color=cmap(k % 10), linewidth=1.5, markersize=4, label=f"Veh {k}")
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_from_results_list(
    results: list[dict[str, Any]],
    out_dir: str | Path,
    *,
    include_mip: bool = True,
) -> None:
    """results từ run_comparison; include_mip=False khi chỉ chạy thuật toán bài báo."""
    out_dir = Path(out_dir)
    labels = [str(r.get("name", "")) for r in results]
    if not include_mip:
        plot_approx_only_bars(
            labels,
            [float(r["approx_time"]) for r in results],
            [float(r["approx_obj"]) for r in results],
            out_dir / "approx_bars.png",
        )
        return
    plot_objective_time_bars(
        labels,
        [float(r["approx_time"]) for r in results],
        [float(r["mip_time"]) for r in results],
        [float(r["approx_obj"]) for r in results],
        [r.get("mip_obj") for r in results],
        out_dir / "compare_bars.png",
    )
