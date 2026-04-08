# Tái hiện VRPCC (Vehicle Routing với ràng buộc tương thích)

## Hướng dẫn chạy (đọc phần này trước)

### 1. Chuẩn bị môi trường

**macOS / Linux:** (từ thư mục gốc của repo)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Windows (PowerShell):** (từ thư mục gốc của repo)

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Kiểm tra Gurobi:

```bash
python -c "import gurobipy as gp; print(gp.gurobi.version())"
```

### 2. Chạy so sánh MIP + thuật toán xấp xỉ (mặc định bộ nhỏ n21-k6)

```bash
python scripts/run_comparison.py --mip-limit-1 600 --mip-limit-2 7200 --out-dir output_runs
```

Kết quả chính: thư mục `output_runs/` gồm `comparison_table.csv`, `summary.json`, `approx_algorithm.log`.

### 3. Chỉ chạy thuật toán (bỏ qua MIP)

```bash
python scripts/run_comparison.py --skip-mip --out-dir output_runs_algo_only
```

### 4. Chạy một bộ instance cụ thể (ví dụ n41-k10, tight)

```bash
python scripts/run_comparison.py \
  --instance "MIP/data/c-n41-k10/c-n41-k10.json" \
  --instance "MIP/data/r-n41-k10/r-n41-k10.json" \
  --instance "MIP/data/RC-n41-k10/RC-n41-k10.json" \
  --mip-limit-1 600 --mip-limit-2 7200 \
  --out-dir output_runs_n41k10
```

*(Trên Windows PowerShell có thể dùng dấu `` ` `` thay cho `\` để xuống dòng.)*

---

## Bảng: ý nghĩa các cột trong `comparison_table.csv`

File này do `scripts/run_comparison.py` ghi ra trong thư mục `--out-dir`.

| Cột | Ý nghĩa |
|-----|---------|
| `Instance` | Tên instance (ví dụ `c-n21-k6`, layout `c` / `r` / `RC`) |
| `LB1` | Cận dưới MIP — lần chạy thứ nhất (giới hạn thời gian ngắn) |
| `UB1` | Cận trên MIP — lần chạy thứ nhất |
| `Time_10min_s` | Thời gian chạy MIP lần 1 (giây); thường tương ứng `--mip-limit-1` (ví dụ 600 s) |
| `LB2` | Cận dưới MIP — lần chạy thứ hai (giới hạn dài hơn) |
| `UB2` | Cận trên MIP — lần chạy thứ hai |
| `Time_2hours_s` | Thời gian chạy MIP lần 2 (giây); thường tương ứng `--mip-limit-2` (ví dụ 7200 s) |
| `Obj` | Giá trị mục tiêu của thuật toán xấp xỉ (= `max(route_costs)`) |
| `Time_algo_s` | Thời gian chạy thuật toán xấp xỉ (giây) |
| `Obj_over_LB2` | Tỉ số đối chiếu `Obj / LB2` (theo tinh thần so sánh trong bài báo) |
| `Obj_over_UB2` | Tỉ số đối chiếu `Obj / UB2` |

Nếu MIP lỗi hoặc bị giới hạn license, các ô MIP có thể là `-`.

---

## Tạo instance MIP theo kích thước tùy ý

Script: `MIP/instancegen.py`

**Một kích thước (ví dụ n41-k10):**

```bash
python MIP/instancegen.py --size 41:10
```

**Nhiều kích thước cùng lúc:**

```bash
python MIP/instancegen.py --size 21:6 --size 41:10 --size 61:14 --size 81:18 --size 101:22
```

- Định dạng `--size`: `n_khách:n_xe` (ví dụ `41:10` → `n41-k10`).
- Dữ liệu ghi vào:
  - `MIP/data/...` — tương thích **chặt** (tight), `p = 0.3`
  - `MIP/data2/...` — tương thích **nới** (relaxed), `p = 0.7`
- Mỗi kích thước có đủ 3 layout: `c`, `r`, `RC`.

---

## Giấy phép Gurobi

- Một số instance lớn (thường `RC` ở cỡ cao) có thể vượt giới hạn license dạng size-limited.
- Script xử lý lỗi từng instance: batch vẫn chạy tiếp, CSV vẫn được ghi.
- Khi bị chặn license, các cột MIP của instance đó sẽ là `-`.

---

## Các file output quan trọng

| File / thư mục | Mô tả |
|----------------|--------|
| `OUT_DIR/summary.json` | Dữ liệu đầy đủ theo từng instance |
| `OUT_DIR/comparison_table.csv` | Bảng tổng hợp để đưa vào báo cáo / đối chiếu bài báo |
| `OUT_DIR/approx_algorithm.log` | Trace quá trình thuật toán xấp xỉ |

`OUT_DIR` là giá trị bạn truyền cho `--out-dir` khi chạy `scripts/run_comparison.py`.
