
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class VRPCCInstance:

    dist: np.ndarray
    u: np.ndarray
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    coords: np.ndarray | None = None

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
        d = self.dist
        n = self.n_nodes
        return float(sum(d[i, j] for i in range(n) for j in range(i + 1, n)))

    def normalize_closed_tour(self, tour: list[int]) -> list[int]:
        if not tour:
            return [0, 0]
        t = tour[:]
        if t[0] != 0:
            t = [0] + t
        if t[-1] != 0:
            t = t + [0]
        return t

    def tour_length(self, tour: list[int], vehicle: int) -> float:
        if len(tour) < 2:
            return 0.0
        s = 0.0
        for a, b in zip(tour[:-1], tour[1:]):
            if self.u[vehicle, b] == 0 and b != 0:
                raise ValueError(f"vehicle {vehicle} cannot visit {b}")
            s += float(self.dist[a, b])
        if tour[0] == 0 and tour[-1] != 0:
            s += float(self.dist[tour[-1], 0])
        return s

    def makespan(self, routes: list[list[int]]) -> float:
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
        dist_key = "dist" if "dist" in d else "c"
        coords = d.get("coords")
        if coords is None and "coordinates" in d:
            coords = d["coordinates"]

        if dist_key not in d or "u" not in d:
            raise ValueError("instance dict must contain ('dist' or 'c') and 'u'")


        dist_raw = np.array(d[dist_key], dtype=np.float64)
        u_raw = np.array(d["u"], dtype=np.int8)
        n_meta = d.get("n")
        m_meta = d.get("m")
        if n_meta is not None and int(n_meta) != int(dist_raw.shape[0]):
            raise ValueError(f"n mismatch: meta n={n_meta}, dist size={dist_raw.shape[0]}")
        if m_meta is not None and int(m_meta) != int(u_raw.shape[0]):
            raise ValueError(f"m mismatch: meta m={m_meta}, u rows={u_raw.shape[0]}")

        return cls(
            dist=dist_raw,
            u=u_raw,
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
