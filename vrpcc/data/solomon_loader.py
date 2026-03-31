"""Load coordinates from Solomon-style VRP text files (NODE_COORD_SECTION)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np


def _parse_coord_lines(lines: list[str]) -> tuple[list[int], np.ndarray]:
    ids: list[int] = []
    pts: list[tuple[float, float]] = []
    for line in lines:
        line = line.strip()
        if not line or line.upper().startswith("DEPOT") or line.upper().startswith("EOF"):
            break
        parts = re.split(r"\s+", line)
        if len(parts) < 3:
            continue
        try:
            nid = int(parts[0])
            x = float(parts[1])
            y = float(parts[2])
        except ValueError:
            continue
        ids.append(nid)
        pts.append((x, y))
    if not pts:
        raise ValueError("No coordinates parsed")
    return ids, np.array(pts, dtype=np.float64)


def load_solomon_coords(path: str | Path) -> np.ndarray:
    """
    Returns coords array shape (N, 2) in file order (row 0 = depot in standard files).
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    upper = text.upper()
    if "NODE_COORD_SECTION" in upper:
        idx = upper.index("NODE_COORD_SECTION")
        rest = text[idx:].split("\n", 1)[1]
        # stop at next SECTION
        block_lines: list[str] = []
        for line in rest.splitlines():
            lu = line.strip().upper()
            if lu.endswith("_SECTION") and not lu.startswith("NODE"):
                break
            block_lines.append(line)
        _, xy = _parse_coord_lines(block_lines)
        return xy
    # Fallback: lines of "id x y"
    lines = [ln for ln in text.splitlines() if ln.strip()]
    _, xy = _parse_coord_lines(lines)
    return xy


def euclidean_dist_matrix(coords: np.ndarray) -> np.ndarray:
    """Full symmetric matrix; c_ij = Euclidean distance (float)."""
    diff = coords[:, None, :] - coords[None, :, :]
    d = np.sqrt((diff**2).sum(axis=2))
    return d.astype(np.float64)


def sample_instance_coords(
    solomon_path: str | Path | None,
    n_customers: int,
    seed: int,
    start_index: int = 0,
) -> np.ndarray:
    """
    Take depot + n_customers points from Solomon file in order (or shuffle with seed).
    If solomon_path is None, raises - caller should use synthetic generator.
    """
    xy = load_solomon_coords(solomon_path)
    need = n_customers + 1
    if xy.shape[0] < need + start_index:
        raise ValueError(f"Need at least {need + start_index} nodes in Solomon file")
    return xy[start_index : start_index + need].copy()
