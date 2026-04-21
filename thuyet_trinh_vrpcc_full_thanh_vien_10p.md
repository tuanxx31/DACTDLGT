# Kịch Bản Thuyết Trình VRPCC Full Thành Viên (10 phút)

## Mục tiêu
- Dùng cho phần trình bày nhóm đủ 4 thành viên.
- Tổng thời lượng mục tiêu: 10 phút.
- Lời thoại gần nguyên văn, có chỉ rõ người nói và mốc thời gian.

---

## Chuẩn nhiệm vụ đối chiếu (theo phân công chốt)
Ghi chú: mục này dùng để đối chiếu với giáo viên, không cần đọc nguyên văn khi quay.

### Nguyễn Đình Tuấn
- Thuật toán chính: ý tưởng, thiết kế, hiện thực và luồng chạy thuật toán xấp xỉ VRPCC.

### Tô Thị Thủy
- MIP: mô hình toán, cách giải, ràng buộc subtour và vai trò LB/UB.

### Nguyễn Thị Tươi
- Chuẩn bị dữ liệu: nguồn Solomon, cách sinh instance, mức tương thích và pipeline tạo dữ liệu chạy.

### Hồ Quang Việt
- Đánh giá kết quả: đọc bảng thực nghiệm, so sánh chỉ số và rút ra nhận xét.

---

## Kịch bản theo mốc thời gian (10:00)

### [00:00 - 03:20] Nguyễn Đình Tuấn
Kính chào cô và các bạn. Nhóm chúng em trình bày đồ án về bài toán định tuyến nhiều phương tiện với ràng buộc tương thích, viết tắt là VRPCC, dựa trên bài báo của Yu, Nagarajan và Shen.

Bối cảnh ngắn gọn như sau: với VRP cổ điển, mục tiêu thường là giảm tổng chi phí di chuyển. Nhưng trong nhiều bối cảnh thực tế như y tế tại nhà hoặc giao hàng có chuyên môn, mục tiêu cân bằng tải lại quan trọng hơn, tức là giảm makespan - tuyến dài nhất trong đội xe.

VRPCC mở rộng VRP bằng cách thêm ràng buộc tương thích: mỗi xe chỉ phục vụ được một tập con khách hàng phù hợp. Vì vậy, bài toán phải đồng thời xử lý gán khách cho xe, thứ tự phục vụ và mục tiêu min-max.

Về phần thuật toán xấp xỉ mà em phụ trách, lõi hiện thực nằm ở `vrpcc/approx_algorithm.py`.  
Algorithm 1 hiện thực greedy cho MCG-VRP: đi lần lượt từng xe, gọi oracle trên tập khách còn lại tương thích, rồi trừ khách đã phủ.  
Algorithm 2 chạy binary search trên ngân sách B; nếu một wave không phủ được tối thiểu một nửa tập khách còn lại thì xem B chưa khả thi, nếu khả thi thì ghép tuyến và tiếp tục cho đến khi phủ hết.

Sau đó nhóm dùng `vrpcc/local_search.py` để cải thiện nghiệm bằng 2-opt và relocation nhằm giảm makespan thực tế. Chi tiết kỹ thuật quan trọng là chi phí luôn tính theo closed tour, có cạnh quay về depot, để thống nhất khi so sánh Obj với LB/UB từ MIP.

Ngoài ra trong quá trình cài đặt, nhóm tách rõ phần quan sát thuật toán bằng log để theo dõi từng bước nhị phân trên B, số wave greedy và mức phủ khách ở mỗi vòng. Cách này giúp kiểm tra đúng hành vi của thuật toán, thay vì chỉ nhìn kết quả cuối cùng.

Về thao tác thực nghiệm, nhóm dùng script `scripts/run_comparison.py` để chạy thống nhất trên nhiều instance, tự động xuất bảng so sánh và lưu kết quả trung gian. Nhờ vậy quá trình chạy batch ổn định hơn, dễ resume khi gặp lỗi hoặc khi một instance MIP chạy quá lâu. Phần đọc và đánh giá chi tiết số liệu sẽ do bạn Việt trình bày ở phần cuối.

**Gợi ý slide:** tiêu đề đề tài -> VRP vs VRPCC -> luồng `approx_algorithm.py` + `local_search.py` -> bảng tight/relaxed.

---

### [03:20 - 06:30] Tô Thị Thủy
Em trình bày phần MIP.

Trong mô hình MIP cho VRPCC, depot là nút 0, khách là các nút còn lại, và biến nhị phân x biểu diễn xe k đi từ i đến j. Hàm mục tiêu là tối thiểu hóa tau, tức chi phí tuyến lớn nhất giữa các xe.

Các ràng buộc chính gồm:
- Chi phí mỗi xe không vượt tau.
- Cân bằng luồng tại các nút.
- Mỗi khách được phục vụ đúng một lần.
- Xe chỉ đi tới khách tương thích.

Khó khăn lớn nhất là ràng buộc subtour vì số lượng rất lớn. Nhóm giải bằng cơ chế sinh ràng buộc động trong `MIP/vrpcc_mip.py`: giải mô hình, phát hiện subtour, thêm lazy constraints, rồi tối ưu lại.

Nếu nhìn theo độ phức tạp thực tế, khi số khách tăng thì không gian nghiệm bùng nổ rất nhanh, dẫn đến branch-and-bound phải mở rộng nhiều nhánh. Vì vậy MIP có ưu điểm mạnh về tính chặt chẽ và chất lượng cận, nhưng lại nhạy với giới hạn thời gian và tài nguyên tính toán.

Về thực nghiệm, MIP cho cận dưới LB và cận trên UB, đây là nền tảng để phần đánh giá cuối so sánh khách quan với thuật toán xấp xỉ.

**Gợi ý slide:** mô hình MIP (2.1)-(2.8) -> lazy constraints -> bảng LB/UB.

---

### [06:30 - 08:00] Nguyễn Thị Tươi
Em trình bày phần chuẩn bị dữ liệu thực nghiệm.

Dữ liệu thực nghiệm của nhóm dựa trên Solomon benchmark, gồm ba kiểu phân bố C, R, RC và hai mức tương thích: tight 30%, relaxed 70%.

Các instance được chuẩn hóa theo định dạng JSON để hai nhánh MIP và thuật toán xấp xỉ cùng đọc chung dữ liệu. Nhóm cũng kiểm tra tính hợp lệ của ma trận tương thích để mỗi khách đều có ít nhất một xe phục vụ.

Pipeline chạy dùng `scripts/run_comparison.py`: chạy MIP để lấy LB/UB, chạy thuật toán xấp xỉ để lấy Obj/thời gian, rồi xuất `summary.json` và `comparison_table.csv`.

**Gợi ý slide:** flowchart thuật toán + pipeline dữ liệu/thực nghiệm.

---

### [08:00 - 10:00] Hồ Quang Việt
Em trình bày phần đánh giá kết quả.

Nhóm dùng hai nhóm chỉ số để đánh giá:
- Chỉ số chất lượng nghiệm: `Obj/LB2`, `Obj/UB2`.
- Chỉ số hiệu năng: thời gian chạy của thuật toán xấp xỉ và mức hội tụ của MIP.

Kết quả tiêu biểu từ `output_report_tight_v2/comparison_table.csv`:
- `Obj/LB2` dao động từ 1.0044 đến 1.2353, trung bình khoảng 1.1236.
- Thời gian thuật toán xấp xỉ từ 0.1877 giây đến 7.0697 giây, trung bình khoảng 2.43 giây.
- Instance `r-n23-k6` là trường hợp rất sát cận dưới.

Kết quả từ `output_report_relaxed_v2/comparison_table.csv`:
- `Obj/LB2` dao động từ 1.0119 đến 1.5292, trung bình khoảng 1.1980.
- Thời gian thuật toán xấp xỉ từ 0.83 giây đến 2.12 giây, trung bình khoảng 1.23 giây.

Ngoài ra có instance `RC-n41-k10` mà MIP bị giới hạn license, nhưng thuật toán xấp xỉ vẫn trả nghiệm. Đây là điểm cho thấy tính thực dụng khi triển khai ở điều kiện tính toán giới hạn.

Từ toàn bộ bảng kết quả, nhóm rút ra ba nhận xét chính:
- Thuật toán xấp xỉ chạy nhanh và ổn định.
- Chất lượng nghiệm cạnh tranh ở nhiều instance so với mốc MIP.
- Với quy mô lớn, xấp xỉ là phương án phù hợp để có nghiệm tốt trong thời gian chấp nhận được.

Nhóm em xin cảm ơn cô và các bạn đã lắng nghe.

**Gợi ý slide:** bảng tight/relaxed -> biểu đồ thời gian -> kết luận 3 ý.

---

## Câu hỏi phản biện nhanh (gợi ý trả lời)

### 1) Vì sao nhóm không chỉ dùng MIP?
Vì MIP cho chất lượng cao nhưng thời gian tăng mạnh khi kích thước tăng. Thuật toán xấp xỉ giúp giữ thời gian thấp hơn và vẫn cho nghiệm cạnh tranh.

### 2) Vì sao kết quả không trùng hoàn toàn bài báo?
Do khác môi trường chạy, phiên bản solver, seed sinh dữ liệu và cấu hình máy. Tuy nhiên xu hướng chung vẫn khớp: approx nhanh, MIP mạnh nhưng tốn thời gian.

### 3) Local search có mâu thuẫn với lý thuyết xấp xỉ không?
Không. Bảo đảm lý thuyết nằm ở lõi thuật toán xấp xỉ. Local search là bước hậu xử lý để cải thiện nghiệm thực nghiệm.

### 4) Đóng góp kỹ thuật nổi bật nhất của nhóm là gì?
Là hiện thực đầy đủ pipeline từ tạo dữ liệu, oracle, thuật toán xấp xỉ, local search đến benchmark và bảng so sánh MIP-approx để đánh giá định lượng.

---

## Tài liệu tham khảo chính khi thuyết trình
- [2] M. Yu, V. Nagarajan, S. Shen, *An Approximation Algorithm for Vehicle Routing with Compatibility Constraints*, 2019.
- [3] M. M. Solomon, *Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints*, 1987.
- [4] P. Toth, D. Vigo, *Vehicle Routing: Problems, Methods, and Applications*, 2014.
- [11] E. M. Arkin, R. Hassin, A. Levin, *Approximations for Minimum and Min-Max Vehicle Routing Problems*, 2006.
