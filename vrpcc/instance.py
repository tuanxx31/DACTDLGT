"""VRPCC instance: metric distances and per-vehicle compatibility (paper u^k_i)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class VRPCCInstance:
    """
    Mô hình instance VRPCC (theo bài báo): đồ thị metric + ràng buộc tương thích theo xe.

    Thuộc tính:
        dist[i,j] = c_ij: khoảng cách đối xứng, không âm, thỏa bất đẳng thức tam giác.
        u[k,j]: 1 nếu xe k được phép đi qua đỉnh j (thường u[k,0]=1 cho mọi k; depot là 0).
        coords (tuỳ chọn): tọa độ 2D để vẽ, không dùng trong lõi thuật toán.

    Đỉnh: 0 = kho, 1..n-1 = khách. Xe: chỉ số 0..m-1 (property `m`).
    """

    dist: np.ndarray  # shape (n_nodes, n_nodes), float
    u: np.ndarray  # shape (m, n_nodes), int/bool; u[k,0] should be 1
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    coords: np.ndarray | None = None  # optional shape (n_nodes, 2) for plotting

    def __post_init__(self) -> None:
        """Kiểm tra kích thước ma trận, dist đối xứng không âm, coords (nếu có) đúng shape."""
        self.dist = np.asarray(self.dist, dtype=np.float64)
        self.u = np.asarray(self.u, dtype=np.int8)
        n_nodes = self.dist.shape[0]
        if self.dist.shape[1] != n_nodes:
            raise ValueError("dist must be square")
        if self.u.shape[1] != n_nodes:
            raise ValueError("u second dim must match n_nodes")
        m = self.u.shape[0]
        if np.any(self.dist < 0):
            raise ValueError("dist must be non-negative")
        if not np.allclose(self.dist, self.dist.T, atol=1e-9):
            raise ValueError("dist must be symmetric")
        if self.coords is not None:
            self.coords = np.asarray(self.coords, dtype=np.float64)
            if self.coords.shape != (n_nodes, 2):
                raise ValueError("coords must be (n_nodes, 2)")

    @property
    def n_nodes(self) -> int:
        """Số đỉnh (gồm depot)."""
        return int(self.dist.shape[0])

    @property
    def n_customers(self) -> int:
        """Số khách (= n_nodes - 1)."""
        return self.n_nodes - 1

    @property
    def m(self) -> int:
        """Số xe (số hàng của ma trận u)."""
        return int(self.u.shape[0])

    def customer_indices(self) -> list[int]:
        """Danh sách chỉ số khách [1, 2, ..., n-1] — dùng trong Algorithm 2 (tập X đầy đủ)."""
        return list(range(1, self.n_nodes))

    def sum_all_edge_costs(self) -> float:
        """
        Tổng c_ij trên mọi cặp i<j — cận phụ trợ; bài báo dùng 2× giá trị này làm cận trên cho binary search B.

        Tham số: không (đọc từ self.dist).

        Trả về: float.
        """
        d = self.dist
        n = self.n_nodes
        return float(sum(d[i, j] for i in range(n) for j in range(i + 1, n)))

    def tour_length(self, tour: list[int], vehicle: int) -> float:
        """
        Chi phí tuyến của một xe: tổng dist trên các cạnh liên tiếp; mỗi bước tới khách j phải thỏa u[vehicle,j].

        Tham số:
            tour: chuỗi đỉnh, thường khép kín qua depot, ví dụ [0, a, b, 0].
            vehicle: chỉ số xe (áp dụng ma trận tương thích u).

        Trả về: tổng chi phí; tour ngắn hơn 2 đỉnh → 0.

        Ngoại lệ: ValueError nếu tuyến đi tới khách mà xe không được phép thăm.
        """
        if len(tour) < 2:
            return 0.0
        s = 0.0
        for a, b in zip(tour[:-1], tour[1:]):
            if self.u[vehicle, b] == 0 and b != 0:
                raise ValueError(f"vehicle {vehicle} cannot visit {b}")
            s += float(self.dist[a, b])
        return s

    def makespan(self, routes: list[list[int]]) -> float:
        """
        Mục tiêu VRPCC: max theo xe của chi phí tuyến (makespan).

        Tham số:
            routes: list độ dài m; routes[k] là tuyến xe k (chuỗi đỉnh qua depot).

        Trả về: giá trị max_k tour_length(routes[k], k); list rỗng → 0.
        """
        costs = [self.tour_length(r, k) for k, r in enumerate(routes)]
        return max(costs) if costs else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Chuyển instance sang dict (list lồng) để ghi JSON."""
        out: dict[str, Any] = {
            "dist": self.dist.tolist(),
            "u": self.u.tolist(),
            "name": self.name,
            "metadata": dict(self.metadata),
        }
        if self.coords is not None:
            out["coords"] = self.coords.tolist()
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VRPCCInstance:
        """
        Tạo instance từ dict (định dạng giống file JSON trong repo).

        Tham số:
            d: phải có khóa "dist", "u"; tuỳ chọn "name", "metadata", "coords".

        Trả về: VRPCCInstance.
        """
        coords = d.get("coords")
        return cls(
            dist=np.array(d["dist"], dtype=np.float64),
            u=np.array(d["u"], dtype=np.int8),
            name=str(d.get("name", "")),
            metadata=dict(d.get("metadata", {})),
            coords=np.array(coords, dtype=np.float64) if coords is not None else None,
        )

    def save_json(self, path: str | Path) -> None:
        """Ghi instance ra file JSON tại `path`."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> VRPCCInstance:
        """Đọc file JSON và trả về VRPCCInstance (dùng cho app.py / scripts)."""
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(d)
