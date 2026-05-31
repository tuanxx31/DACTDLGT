# Tổng quan VRPCC, thuật toán xấp xỉ, MIP và mã nguồn

File này tổng hợp lại nội dung đã đọc từ:

- Bài báo PDF: `2.An Approximation Algorithm for Vehicle Routing with Compatibility Constraints∗.pdf`.
- Báo cáo Word: `bao_cao_vrpcc.docx`.
- Mã nguồn Python trong repo: `app.py`, `run_selected_instances.py`, `scripts/`, `vrpcc/`, `MIP/`.
- Đầu ra thực nghiệm hiện có: `output_selected_instances/`, `output_paper_101_benchmark_small_to_large/`, `comparison_table.csv`.

Mục tiêu của file này là giúp đọc để đi báo cáo: hiểu bài toán, hướng xử lý, mã nguồn đang làm gì, cách đọc đầu ra, và đặc biệt là vì sao bài báo so sánh thuật toán xấp xỉ với MIP.

## 1. Bài toán VRPCC là gì?

VRPCC là viết tắt của **Vehicle Routing Problem with Compatibility Constraints** - bài toán định tuyến nhiều phương tiện với ràng buộc tương thích.

Bài toán gồm:

| Thành phần | Ý nghĩa |
|---|---|
| Depot | Kho xuất phát và kết thúc, ký hiệu là đỉnh `0`. |
| Customers | Tập khách hàng cần phục vụ, ký hiệu `V+ = V \ {0}`. |
| Vehicles | Tập xe `K = {0, 1, ..., m-1}`. |
| Distance matrix | Ma trận chi phí/khoảng cách `c_ij` giữa hai đỉnh. |
| Compatibility | Xe `k` chỉ được phục vụ một số khách nhất định, biểu diễn bởi `u[k][j]`. |
| Objective | Tối thiểu hóa **makespan**, tức tuyến dài nhất trong tất cả các xe. |

Khác với VRP cổ điển thường tối thiểu tổng chi phí, VRPCC tập trung vào mục tiêu **min-max**:

```text
minimize max_k cost(route_k)
```

Ý nghĩa thực tế: không muốn một xe hoặc một đội phục vụ bị quá tải, trong khi các xe khác lại nhẹ việc. Ràng buộc tương thích xuất hiện trong nhiều tình huống:

- Xe lạnh chỉ phục vụ hàng lạnh.
- Đội y tế có kỹ năng riêng chỉ chăm sóc được một số bệnh nhân.
- Xe/phương tiện có giấy phép, thiết bị hoặc khu vực phục vụ khác nhau.

## 2. Vì sao bài toán khó?

VRP đã khó vì phải quyết định thứ tự thăm các khách. VRPCC còn khó hơn vì phải đồng thời quyết định:

1. Khách nào gán cho xe nào.
2. Xe đó có tương thích với khách không.
3. Thứ tự đi của mỗi xe.
4. Làm sao để tuyến dài nhất là nhỏ nhất.

Bài báo chỉ ra VRPCC có liên hệ chặt với **Set Cover**. Từ đó suy ra bài toán khó xấp xỉ: không thể hy vọng có thuật toán xấp xỉ hằng số tốt cho trường hợp tổng quát, trừ khi có đột phá về P/NP. Kết quả tích cực của bài báo là xây dựng được thuật toán xấp xỉ bậc `O(log n)`.

## 3. MIP trong bài báo và vai trò so sánh

### 3.1. MIP là gì trong bài toán này?

MIP là mô hình quy hoạch số nguyên hỗn hợp. Trong VRPCC, MIP biểu diễn chính xác quyết định di chuyển bằng biến nhị phân:

```text
x[k][i][j] = 1 nếu xe k đi trực tiếp từ i đến j
x[k][i][j] = 0 nếu không
```

Ngoài ra có biến liên tục:

```text
tau = makespan
```

Mục tiêu:

```text
minimize tau
```

### 3.2. Các ràng buộc MIP chính

| Nhóm ràng buộc | Ý nghĩa |
|---|---|
| Makespan | Tổng chi phí tuyến của mỗi xe không vượt quá `tau`. |
| Depot | Mỗi xe xuất phát/đi qua depot theo cấu trúc tuyến hợp lệ. |
| Flow balance | Nếu xe vào một đỉnh thì cũng phải rời đỉnh đó. |
| Visit once | Mỗi khách được phục vụ đúng một lần. |
| Compatibility | Xe chỉ được đi tới khách mà `u[k][j] = 1`. |
| Subtour elimination | Loại chu trình con không đi qua depot. |
| Binary | Biến `x[k][i][j]` là 0/1. |

Trong mã nguồn, MIP chính nằm ở:

```text
MIP/vrpcc_mip.py
```

Điểm đáng chú ý:

- Hàm `_feasible_arcs` chỉ tạo các cung hợp lệ theo tương thích, giúp giảm kích thước model.
- Gurobi giải model với biến `x` và `tau`.
- Callback `_callback` phát hiện subtour và thêm lazy constraint.
- Kết quả trả về `MIPReport`, gồm `lb`, `ub`, `best_tau`, `mip_gap`, `time_sec`, `status`, `nodes`.

### 3.3. Vì sao phải so sánh thuật toán xấp xỉ với MIP?

Bài báo không chỉ đưa ra thuật toán xấp xỉ về lý thuyết. Tác giả còn muốn trả lời câu hỏi thực nghiệm:

1. **MIP có tìm được nghiệm tốt hơn không?**
2. **MIP cần bao lâu để tìm được nghiệm hoặc cận tốt?**
3. **Thuật toán xấp xỉ nhanh hơn MIP bao nhiêu?**
4. **Nghiệm xấp xỉ có gần với nghiệm tốt nhất mà MIP tìm được không?**

MIP có vai trò như baseline:

- `LB`: cận dưới của lời giải tối ưu.
- `UB`: nghiệm khả thi tốt nhất MIP tìm được.
- `Obj`: nghiệm của thuật toán xấp xỉ.
- `Obj/LB2`: đánh giá khoảng cách với cận dưới tốt nhất của MIP.
- `Obj/UB2`: so sánh trực tiếp với nghiệm khả thi tốt nhất của MIP.

Nếu `Obj/UB2` gần `1`, thuật toán xấp xỉ cạnh tranh được với MIP. Nếu nhỏ hơn `1`, nghiệm xấp xỉ còn tốt hơn nghiệm MIP tìm được trong giới hạn thời gian.

Kết luận thực nghiệm của bài báo: MIP cho mô hình chính xác nhưng rất khó mở rộng khi instance lớn; thuật toán xấp xỉ chạy nhanh hơn nhiều và nghiệm thực tế thường gần với nghiệm tốt nhất MIP tìm được.

## 4. Thuật toán xấp xỉ của bài báo

Bài báo dùng hai tầng ý tưởng:

1. Giải bài toán phủ khách bằng greedy theo từng ngân sách `B`.
2. Binary search trên `B` để tìm ngân sách đủ nhỏ nhưng vẫn phủ được tất cả khách.

### 4.1. MCG-VRP

Với một ngân sách `B`, ta xét bài toán con:

```text
Mỗi xe được chọn một tuyến có chi phí không quá B.
Chọn các tuyến sao cho phủ được nhiều khách chưa phục vụ nhất.
```

Bài toán con này được gọi là MCG-VRP, liên quan đến Maximum Coverage with Group Budgets.

Trong mã nguồn, MCG-VRP greedy là:

```text
vrpcc/approx_algorithm.py -> algorithm_1_mcg_vrp
```

Luồng xử lý:

1. Đặt `X' = X`, trong đó `X` là tập khách chưa phủ.
2. Duyệt từng xe `veh`.
3. Lấy tập khách khả thi của xe:

```text
Y = X' giao V_veh
```

4. Gọi oracle:

```text
O(Y, B, veh)
```

5. Xóa các khách đã phủ khỏi `X'`.
6. Trả về tuyến cho mỗi xe và tập khách đã được phủ.

### 4.2. Oracle k-TSP

Oracle nằm ở:

```text
vrpcc/k_tsp_oracle.py
```

Hàm chính:

```text
oracle_k_tsp(inst, Y, budget, vehicle, beta=5.0)
```

Trong bài báo, thực nghiệm dùng oracle dựa trên thuật toán xấp xỉ 5 lần cho k-TSP. Code đặt `BETA = 5.0`.

Ý nghĩa:

```text
Với ngân sách B, oracle được phép trả về tuyến có chi phí <= beta * B
và cố gắng phủ được nhiều khách nhất.
```

Implementation hiện tại:

- Nếu số khách khả thi `|Y| <= 8`, mã nguồn thử exact bằng tổ hợp và hoán vị.
- Nếu `|Y| > 8`, mã nguồn dùng greedy:
  - Bắt đầu từ depot.
  - Mỗi bước thêm khách làm tăng chi phí tour khép kín ít nhất.
  - Chỉ thêm nếu chi phí tour vẫn không quá `beta * B`.
  - Sau đó chạy 2-opt để cải thiện thứ tự.

### 4.3. Algorithm 2 - binary search trên B

Algorithm 2 nằm ở:

```text
vrpcc/approx_algorithm.py -> algorithm_2_vrpcc
```

Luồng xử lý:

1. Khởi tạo:

```text
lower = 0
upper = 2 * sum(c_ij)
X = tất cả khách
```

2. Lặp khi `upper - lower >= eps`:

```text
B = (upper + lower) / 2
```

3. Với `B`, chạy Algorithm 1 nhiều đợt.
4. Mỗi đợt phải phủ được ít nhất nửa số khách còn lại.
5. Nếu phủ hết được khách, `B` khả thi:

```text
upper = B
```

6. Nếu không, `B` quá nhỏ:

```text
lower = B
```

7. Kết quả là các tuyến `routes`, makespan, cận `B_lower/B_upper`, số bước binary search và cận xấp xỉ lý thuyết.

Cận lý thuyết trong mã nguồn:

```text
approx_ratio_bound = (1 + eps) * beta * ceil(log2(n_customers))
```

Với `beta = 5`, `eps = 0.001`, `n_customers = 20`:

```text
(1 + 0.001) * 5 * ceil(log2(20)) = 25.025
```

### 4.4. Local search

Sau Algorithm 2, mã nguồn chạy thêm local search trong:

```text
vrpcc/local_search.py
```

Hai kỹ thuật:

| Kỹ thuật | Ý nghĩa |
|---|---|
| 2-opt | Đảo thứ tự một đoạn trong tuyến để giảm chi phí. |
| Relocation | Lấy khách từ xe có tuyến dài nhất, thử chuyển sang xe khác tương thích nếu giảm makespan. |

Cần lưu ý khi báo cáo:

- `makespan_algo2` là nghiệm trực tiếp của Algorithm 2.
- `makespan_final` là nghiệm sau local search.
- Cận xấp xỉ lý thuyết thuộc về Algorithm 2; local search là bước cải thiện thực nghiệm.

## 5. Dữ liệu thực nghiệm

Bài báo dùng tọa độ từ Solomon benchmark. Repo này có bộ dữ liệu paper-style trong:

```text
MIP/data_paper_101/
```

Có hai mức tương thích:

| Thư mục | Xác suất tương thích |
|---|---:|
| `tight/` | `p = 0.3` |
| `relaxed/` | `p = 0.7` |

Có ba loại phân bố:

| Prefix | Ý nghĩa |
|---|---|
| `c` | Clustered - khách theo cụm. |
| `r` | Random - khách phân bố ngẫu nhiên. |
| `RC` | Mixed - vừa cụm vừa ngẫu nhiên. |

Quy mô trong bộ `data_paper_101`:

```text
n21-k6, n41-k10, n61-k14, n81-k18, n101-k22
```

Trong tên instance, `n21-k6` nghĩa là 21 node gồm 1 depot và 20 khách, với 6 xe.

Script sinh dữ liệu:

```text
MIP/instancegen_paper.py
```

Script này đọc file Solomon gốc, lấy tọa độ, tính ma trận khoảng cách Euclidean, sinh ma trận tương thích với seed cố định và ghi manifest.

## 6. Bản đồ mã nguồn

### 6.1. File chạy thuật toán xấp xỉ riêng

| File | Vai trò |
|---|---|
| `app.py` | CLI chạy thuật toán xấp xỉ, có tham số `--instance`, `--instance-dir`, `--beta`, `--eps`, `--out-dir`, `--no-local-search`. |
| `vrpcc.py` | File chạy nhanh bằng cách sửa biến cấu hình trong file. |
| `run_selected_instances.py` | File mới để khai báo sẵn danh sách instance cần chạy, không cần truyền `--instance`. |

`app.py` là entry point chính nếu chỉ muốn chạy thuật toán xấp xỉ. Nếu không truyền instance, nó mặc định chạy các JSON trong:

```text
MIP/data_paper_101/tight
```

### 6.2. Core algorithm

| File | Nội dung |
|---|---|
| `vrpcc/instance.py` | Lớp `VRPCCInstance`, đọc JSON, chuẩn hóa tour, tính `tour_length`, tính `makespan`. |
| `vrpcc/approx_algorithm.py` | `algorithm_1_mcg_vrp`, `algorithm_2_vrpcc`, dataclass `VRPCCResult`. |
| `vrpcc/k_tsp_oracle.py` | Oracle k-TSP: exact cho tập nhỏ, greedy + 2-opt cho tập lớn. |
| `vrpcc/local_search.py` | 2-opt trên từng segment và relocation giữa các xe. |
| `vrpcc/approx_observer.py` | Interface hook để trace quá trình chạy. |
| `vrpcc/approx_observer_logging.py` | Ghi log chi tiết binary search, greedy wave và route từng xe. |

### 6.3. MIP và so sánh

| File | Nội dung |
|---|---|
| `MIP/vrpcc_mip.py` | MIP chính được `run_comparison.py` gọi. Dùng Gurobi, arcs khả thi, lazy subtour constraints. |
| `vrpcc/mip_gurobi.py` | Một bản MIP khác theo `VRPCCInstance`, có callback/SEC bổ sung. |
| `scripts/run_comparison.py` | Chạy approx + MIP trên cùng instance, ghi `summary.json` và `comparison_table.csv`. |
| `scripts/run_paper_benchmark.py` | Batch runner chạy bộ `MIP/data_paper_101`, có resume, log stdout/stderr, xuất bảng tight/relaxed. |
| `MIP/main_data_tight.py` | Demo MIP trên một số instance tight. |
| `MIP/main_data_relax.py` | Demo MIP trên một số instance relaxed. |
| `MIP/main_small.py` | Demo MIP trên instance nhỏ. |

### 6.4. Sinh dữ liệu và vẽ hình

| File | Nội dung |
|---|---|
| `MIP/instancegen.py` | Sinh instance synthetic C/R/RC cũ. |
| `MIP/instancegen_paper.py` | Sinh instance paper-style từ Solomon benchmark. |
| `vrpcc/data/generate_instances.py` | Sinh bộ instance nhỏ trong `vrpcc/data/instances`. |
| `vrpcc/data/solomon_loader.py` | Đọc tọa độ Solomon và tính ma trận khoảng cách. |
| `vrpcc/plotting.py` | Vẽ bar chart và bản đồ tuyến đường. |

## 7. Luồng chạy quan trọng trong repo

### 7.1. Chỉ chạy thuật toán xấp xỉ

```bash
.venv/bin/python app.py --instance MIP/data_paper_101/tight/c-n21-k6/c-n21-k6.json
```

Hoặc chạy file danh sách có sẵn:

```bash
.venv/bin/python run_selected_instances.py
```

Đầu ra của cách này:

```text
output_selected_instances/
  approx_algorithm.log
  approx_bars.png
  routes_paper_*.png
  summary_selected_instances.json
```

### 7.2. Chạy so sánh approx với MIP

```bash
.venv/bin/python scripts/run_comparison.py --mip-limit-1 600 --mip-limit-2 7200 --out-dir output_runs
```

Nếu không có Gurobi hoặc chỉ cần approx:

```bash
.venv/bin/python scripts/run_comparison.py --skip-mip --out-dir output_runs_algo_only
```

### 7.3. Chạy benchmark kiểu bài báo

```bash
.venv/bin/python scripts/run_paper_benchmark.py
```

Script này chạy lần lượt tight rồi relaxed, từ nhỏ đến lớn, ghi log và có resume.

## 8. Ý nghĩa đầu ra

### 8.1. Đầu ra khi chạy `app.py` hoặc `run_selected_instances.py`

Terminal sẽ in các khối thông tin:

| Trường | Ý nghĩa |
|---|---|
| `Instance` | Tên instance đang chạy. |
| `Nodes` | Tổng số node, gồm depot và khách. |
| `Vehicles` | Số xe. |
| `Beta` | Hệ số bicriteria của oracle. |
| `Epsilon` | Sai số dừng binary search. |
| `B_init_upper` | Cận trên ban đầu `2 * sum(c_ij)`. |
| `B_lower`, `B_upper` | Khoảng cận cuối sau binary search. |
| `B* oracle` | Ngân sách oracle cuối, bằng `B_upper`. |
| `n_binary_steps` | Số bước binary search. |
| `n_waves_last_feasible` | Số đợt greedy cần để phủ hết khách ở nghiệm khả thi cuối. |
| `approx_ratio_bound` | Cận xấp xỉ lý thuyết. |
| `Tuyến xe` | Route từng xe, `0` là depot. |
| `Makespan (Algorithm 2)` | Makespan trước local search. |
| `Makespan (sau local search)` | Makespan sau 2-opt và relocation. |
| `time_algo2`, `time_total` | Thời gian chạy thuật toán và tổng thời gian. |

Lưu ý quan trọng:

`B*` không phải makespan cuối. `B*` là ngân sách cho từng lời gọi oracle trong một đợt greedy. Route cuối có thể là nối nhiều đợt, nên makespan có thể lớn hơn `beta * B*`.

### 8.2. Đầu ra JSON

Ví dụ `output_selected_instances/summary_selected_instances.json` gồm mỗi instance một object:

| Key | Ý nghĩa |
|---|---|
| `name` | Tên instance. |
| `file` | Đường dẫn file JSON đầu vào. |
| `n_customers` | Số khách. |
| `n_vehicles` | Số xe. |
| `beta`, `eps` | Tham số thuật toán. |
| `B_lower`, `B_upper` | Cận binary search cuối. |
| `n_binary_steps` | Số bước binary search. |
| `approx_ratio_bound` | Cận lý thuyết. |
| `makespan_algo2` | Makespan trước local search. |
| `makespan_final` | Makespan sau local search. |
| `time_algo2` | Thời gian Algorithm 2. |
| `time_total` | Tổng thời gian. |
| `local_search` | Có bật local search hay không. |

### 8.3. Đầu ra CSV so sánh MIP và approx

File:

```text
output_paper_101_benchmark_small_to_large/comparison_table.csv
```

Ý nghĩa cột:

| Cột | Ý nghĩa |
|---|---|
| `Instance` | Tên instance. |
| `LB1` | Cận dưới MIP lần 1, thường với giới hạn 10 phút. |
| `UB1` | Cận trên/nghiệm khả thi MIP lần 1. |
| `Time_10min_s` | Thời gian lần 1. |
| `LB2` | Cận dưới MIP lần 2, thường với giới hạn 2 giờ. |
| `UB2` | Cận trên/nghiệm khả thi MIP lần 2. |
| `Time_2hours_s` | Thời gian lần 2. |
| `Obj` | Makespan của thuật toán xấp xỉ sau local search. |
| `Time_algo_s` | Thời gian thuật toán xấp xỉ. |
| `Obj_over_LB2` | `Obj / LB2`, dùng để ước lượng khoảng cách với tối ưu. |
| `Obj_over_UB2` | `Obj / UB2`, so sánh với nghiệm khả thi tốt nhất của MIP. |

Trong đầu ra hiện tại, `comparison_table.csv` ghép cả tight và relaxed nên có thể lặp tên instance. Để đưa vào báo cáo nên dùng hai file đã tách:

```text
output_paper_101_benchmark_small_to_large/table1_tight_like_paper.csv
output_paper_101_benchmark_small_to_large/table2_relaxed_like_paper.csv
```

### 8.4. Ý nghĩa dấu `-`

Trong CSV, dấu `-` nghĩa là không có giá trị MIP hợp lệ. Nguyên nhân có thể là:

- MIP bị lỗi.
- Gurobi license không cho instance lớn.
- Solver không tìm được UB trong giới hạn.
- Kết quả bị skip nhưng approx vẫn được ghi.

## 9. Đánh giá kết quả hiện có trong repo

### 9.1. Kết quả demo `run_selected_instances.py`

Từ `output_selected_instances/summary_selected_instances.json`:

| Instance | Khách | Xe | B* | Makespan Algo 2 | Makespan sau LS | Time |
|---|---:|---:|---:|---:|---:|---:|
| c-n21-k6 | 20 | 6 | 16.1245 | 216.9306 | 138.2159 | 0.0887s |
| r-n21-k6 | 20 | 6 | 13.4165 | 223.5229 | 135.9524 | 4.0526s |
| RC-n21-k6 | 20 | 6 | 18.0714 | 233.0794 | 170.0572 | 0.3855s |

Nhận xét:

- Local search giảm makespan rõ rệt so với Algorithm 2 ban đầu.
- Instance `r-n21-k6` chậm hơn trong demo do oracle/greedy phải thử nhiều cấu hình hơn.
- Đây là đầu ra phù hợp để minh họa cách thuật toán chạy, nhưng để so sánh với MIP nên dùng `scripts/run_comparison.py`.

### 9.2. Kết quả so sánh MIP và approx hiện có

Trong `output_paper_101_benchmark_small_to_large/table1_tight_like_paper.csv`, một số dòng tight:

| Instance | LB2 | UB2 | Obj | Time approx | Obj/LB2 | Obj/UB2 |
|---|---:|---:|---:|---:|---:|---:|
| c-n21-k6 | 99.0550 | 99.0550 | 138.2159 | 0.1182s | 1.3953 | 1.3953 |
| c-n41-k10 | 108.9093 | 108.9093 | 108.9093 | 6.7647s | 1.0000 | 1.0000 |
| r-n21-k6 | 122.6969 | 122.6969 | 135.9524 | 4.8724s | 1.1080 | 1.1080 |
| RC-n41-k10 | 168.8004 | 168.8004 | 176.5266 | 15.8145s | 1.0458 | 1.0458 |

Trong `table2_relaxed_like_paper.csv`, một số dòng relaxed:

| Instance | LB2 | UB2 | Obj | Time approx | Obj/LB2 | Obj/UB2 |
|---|---:|---:|---:|---:|---:|---:|
| c-n21-k6 | 78.1025 | 80.6226 | 80.6226 | 4.2525s | 1.0323 | 1.0000 |
| r-n21-k6 | 78.8270 | 78.8270 | 99.0073 | 1.9963s | 1.2560 | 1.2560 |
| RC-n21-k6 | 90.3549 | 90.3549 | 115.6116 | 3.0683s | 1.2795 | 1.2795 |

Nhận xét cần nói khi báo cáo:

- Với một số instance nhỏ, MIP giải được tối ưu rất nhanh.
- Với instance lớn hơn, đầu ra hiện có nhiều dấu `-`, cho thấy MIP không có kết quả đầy đủ trong điều kiện chạy/giấy phép hiện tại.
- Approx vẫn sinh được `Obj` và `Time_algo_s`, nên hữu ích khi MIP không mở rộng tốt.
- Kết quả local có thể khác với bảng trong bài báo vì seed dữ liệu, cách lấy node, môi trường máy, Gurobi version và implementation oracle khác nhau.

## 10. Khác biệt giữa bài báo và mã nguồn hiện tại

| Nội dung | Bài báo | Code hiện tại |
|---|---|---|
| Ngôn ngữ | Java cho thuật toán thực nghiệm | Python |
| MIP solver | Gurobi 7.5.1 trong bài báo | `gurobipy` theo môi trường hiện tại |
| Oracle | k-TSP 5-approx để dễ implement | `beta=5`, exact cho tập nhỏ, greedy + 2-opt cho tập lớn |
| Dữ liệu | Solomon + random compatibility | Paper-style Solomon + seed cố định trong repo |
| Local search | 2-opt + relocation | 2-opt segment + relocation từ xe có tuyến dài nhất |
| Bảng so sánh | Tables tight/relaxed của bài báo | `table1_tight_like_paper.csv`, `table2_relaxed_like_paper.csv` |

Do bài báo không công bố đầy đủ seed và raw instance, repo này nên được trình bày là **tái hiện paper-style**, không đảm bảo trùng bit-by-bit với bảng gốc.

## 11. Điểm mạnh và hạn chế của hướng xử lý

### Điểm mạnh

- Có nền tảng lý thuyết: cận khó xấp xỉ và cận xấp xỉ `O(log n)`.
- Tách bài toán lớn thành các bước coverage để cài đặt dễ hơn.
- Chạy nhanh hơn MIP trên các instance lớn.
- Có MIP baseline để đối chiếu chất lượng nghiệm.
- Có đầu ra đầy đủ: JSON, CSV, log, hình tuyến đường.

### Hạn chế

- Cận lý thuyết lớn hơn nhiều so với chất lượng thực tế.
- Oracle trong mã nguồn là heuristic/gần đúng, không phải bản k-TSP 5-approx đầy đủ theo chứng minh gốc.
- MIP phụ thuộc Gurobi/license, dễ bị lỗi hoặc thiếu kết quả với instance lớn.
- Kết quả không trùng hoàn toàn với bài báo do dữ liệu paper-style và môi trường chạy khác.
- Sau khi xóa comment/docstring, mã nguồn khó đọc hơn; file Markdown này bù lại phần giải thích.

## 12. Cách trình bày ngắn gọn khi báo cáo

Có thể nói theo thứ tự:

1. **Bài toán**: VRPCC là VRP nhiều xe, mỗi xe chỉ phục vụ một tập khách tương thích, mục tiêu là giảm tuyến dài nhất.
2. **MIP**: mô hình chính xác với biến `x[k][i][j]` và `tau`, giải bằng Gurobi, dùng để lấy LB/UB và baseline.
3. **Vấn đề với MIP**: khi số node và không gian tương thích tăng, MIP rất khó giải trong giới hạn thời gian.
4. **Thuật toán xấp xỉ**: binary search trên `B`; với mỗi `B`, greedy MCG-VRP phủ ít nhất nửa số khách còn lại; oracle k-TSP chọn route cho từng xe.
5. **Local search**: 2-opt và relocation giảm makespan thực tế.
6. **So sánh đầu ra**: nhìn `Obj/LB2` để biết khoảng cách với cận dưới; nhìn `Obj/UB2` để biết có cạnh tranh với nghiệm MIP hay không.
7. **Kết luận**: MIP chính xác nhưng chậm/không mở rộng tốt; xấp xỉ nhanh và nghiệm thực tế tốt, nên phù hợp instance vừa và lớn.

## 13. Câu hỏi dễ bị hỏi và cách trả lời

**B* có phải đáp án tối ưu không?**

Không. `B*` là ngân sách binary search tìm được cho oracle/greedy. Đáp án thực nghiệm cần nhìn `makespan_algo2` hoặc `makespan_final`.

**Vì sao route có nhiều số 0?**

`0` là depot. Algorithm 2 nối nhiều đợt greedy lại, nên một xe có thể về depot nhiều lần:

```text
[0, 3, 5, 0, 18, 0]
```

Nghĩa là xe có hai chuyến: `0 -> 3 -> 5 -> 0` và `0 -> 18 -> 0`.

**Nếu MIP là chính xác, tại sao còn cần xấp xỉ?**

MIP có thể chính xác trên instance nhỏ, nhưng rất tốn thời gian và bộ nhớ khi instance lớn. Thuật toán xấp xỉ chấp nhận nghiệm gần tối ưu để đổi lấy thời gian chạy nhanh và khả năng mở rộng.

**Tại sao có khi relaxed lại khó hơn tight?**

Relaxed có nhiều xe tương thích với cùng một khách, làm không gian gán khách cho xe rộng hơn. Điều này có thể làm MIP phải xét nhiều nhánh hơn, nên không nhất thiết dễ hơn.

**Tại sao kết quả repo khác bài báo?**

Vì bài báo không công bố đầy đủ seed/random instance. Repo dùng quy tắc sinh giống paper-style: Solomon coordinates, `p=0.3/0.7`, fixed seeds. Khác seed, solver, máy chạy và implementation oracle sẽ làm kết quả khác.

## 14. File nên đưa vào phụ lục/báo cáo

| Mục đích | File nên dùng |
|---|---|
| Giải thích tổng quan | `TONG_QUAN_VRPCC_SOURCE_BAO_CAO.md` |
| Ghi chú mã nguồn ngắn hơn | `GHI_CHU_BAO_CAO_VRPCC.md` |
| Chạy demo approx | `run_selected_instances.py` |
| Kết quả demo approx | `output_selected_instances/summary_selected_instances.json` |
| Hình tuyến đường demo | `output_selected_instances/routes_paper_*.png` |
| Bảng so sánh MIP/approx | `output_paper_101_benchmark_small_to_large/table1_tight_like_paper.csv` và `table2_relaxed_like_paper.csv` |
| Log chi tiết thuật toán | `approx_algorithm.log` |
| Mã nguồn MIP | `MIP/vrpcc_mip.py` |
| Mã nguồn xấp xỉ | `vrpcc/approx_algorithm.py`, `vrpcc/k_tsp_oracle.py`, `vrpcc/local_search.py` |

## 15. Kết luận chung

Bài báo nghiên cứu VRPCC với hai điểm khó: ràng buộc tương thích và mục tiêu min-max. MIP mô hình hóa bài toán chính xác, nhưng khi instance lớn thì việc giải bằng solver trở nên khó. Thuật toán xấp xỉ của bài báo dùng cách tiếp cận coverage: đoán ngân sách `B`, dùng greedy và oracle để phủ dần khách, sau đó binary search để tìm `B` phù hợp. Code trong repo hiện thực lại pipeline này bằng Python, bổ sung local search, sinh dữ liệu paper-style, và xuất bảng so sánh với MIP.

Thông điệp quan trọng khi báo cáo:

```text
MIP là mốc so sánh về chất lượng nghiệm và cận tối ưu.
Thuật toán xấp xỉ là hướng xử lý nhanh, có bảo đảm lý thuyết và thực tế cạnh tranh được với MIP trên nhiều instance.
```
