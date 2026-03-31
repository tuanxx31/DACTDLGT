"""
VRPCC (Yu, Nagarajan, Shen): min makespan + ràng buộc tương thích.

Trọng tâm mã nguồn: thuật toán xấp xỉ (Algorithms 1–2, oracle k-TSP, local search mục 4 — mặc định trong run_comparison).
MIP Gurobi chỉ là baseline để so sánh giá trị / bound / thời gian.
"""

from vrpcc.instance import VRPCCInstance

__all__ = ["VRPCCInstance"]
