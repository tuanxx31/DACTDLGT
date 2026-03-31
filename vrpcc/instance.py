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
    Nodes: 0 = depot, 1..n = customers (|V+| = n).
    Vehicles: indices 0..m-1.
    c[i,j]: symmetric non-negative distances, triangle inequality.
    u[k,j]: 1 if vehicle k may visit node j (typically u[k,0]=1 for all k).
    """

    dist: np.ndarray  # shape (n_nodes, n_nodes), float
    u: np.ndarray  # shape (m, n_nodes), int/bool; u[k,0] should be 1
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    coords: np.ndarray | None = None  # optional shape (n_nodes, 2) for plotting

    def __post_init__(self) -> None:
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
        return int(self.dist.shape[0])

    @property
    def n_customers(self) -> int:
        return self.n_nodes - 1

    @property
    def m(self) -> int:
        return int(self.u.shape[0])

    def customer_indices(self) -> list[int]:
        return list(range(1, self.n_nodes))

    def sum_all_edge_costs(self) -> float:
        """Upper bound helper: sum_{i<j} c_ij (paper uses 2 * this for u)."""
        d = self.dist
        n = self.n_nodes
        return float(sum(d[i, j] for i in range(n) for j in range(i + 1, n)))

    def tour_length(self, tour: list[int], vehicle: int) -> float:
        """Tour as node sequence including depot start/end, e.g. [0,a,b,0]."""
        if len(tour) < 2:
            return 0.0
        s = 0.0
        for a, b in zip(tour[:-1], tour[1:]):
            if self.u[vehicle, b] == 0 and b != 0:
                raise ValueError(f"vehicle {vehicle} cannot visit {b}")
            s += float(self.dist[a, b])
        return s

    def makespan(self, routes: list[list[int]]) -> float:
        """Max per-vehicle route cost; each route is closed tour from depot."""
        costs = [self.tour_length(r, k) for k, r in enumerate(routes)]
        return max(costs) if costs else 0.0

    def to_dict(self) -> dict[str, Any]:
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
        coords = d.get("coords")
        return cls(
            dist=np.array(d["dist"], dtype=np.float64),
            u=np.array(d["u"], dtype=np.int8),
            name=str(d.get("name", "")),
            metadata=dict(d.get("metadata", {})),
            coords=np.array(coords, dtype=np.float64) if coords is not None else None,
        )

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> VRPCCInstance:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(d)
