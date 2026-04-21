# Kịch Bản Thuyết Trình VRPCC (8-10 phút) - Nguyễn Đình Tuấn

## Mục tiêu video
- Trình bày ngắn gọn bối cảnh bài toán VRPCC và vai trò của phần em phụ trách.
- Giải thích rõ ý tưởng thuật toán xấp xỉ, cách em hiện thực trong code, và kết quả thực nghiệm chính.
- Chốt lại giá trị thực tiễn: chạy nhanh, có bảo đảm lý thuyết, và cạnh tranh tốt với MIP ở nhiều instance.

---

## Kịch bản theo mốc thời gian (đọc gần nguyên văn)

### [00:00 - 00:55] Mở đầu và định vị phần cá nhân
Xin chào cô và các bạn. Em là Nguyễn Đình Tuấn. Trong đề tài VRPCC, phần em phụ trách gồm: ý tưởng thuật toán xấp xỉ, thuật toán greedy cho MCG-VRP, và cài đặt thực nghiệm để phân tích kết quả.

Bối cảnh rất ngắn gọn như sau: VRPCC là bài toán định tuyến nhiều xe với ràng buộc tương thích xe-khách, và mục tiêu tối ưu ở đây là makespan, tức là giảm độ dài tuyến lớn nhất trong đội xe, chứ không phải giảm tổng quãng đường. Vì vậy, bài toán mang bản chất min-max và khó hơn khá nhiều so với các mô hình VRP cơ bản. [2], [4]

**Gợi ý hiển thị slide:** tiêu đề đề tài + bảng phân công, highlight dòng của Nguyễn Đình Tuấn.

---

### [00:55 - 02:20] Ý tưởng thuật toán xấp xỉ theo bài báo
Ý tưởng lõi của bài báo là không giải trực tiếp toàn bộ VRPCC bằng MIP cho mọi quy mô, mà chuyển sang quy trình xấp xỉ có kiểm soát. Cụ thể, ta đoán một ngân sách tuyến B, rồi kiểm tra khả năng phủ dần toàn bộ khách hàng.

Bài toán con tại mỗi vòng là MCG-VRP: với tập khách chưa phục vụ X, chọn cho mỗi xe một tuyến hợp lệ để phủ nhiều khách mới nhất trong ngân sách B.

Sau đó, thuật toán tổng thể dùng tìm kiếm nhị phân trên B. Nếu B đủ lớn thì cập nhật cận trên, nếu B quá nhỏ thì cập nhật cận dưới, lặp lại đến khi khoảng cận đủ nhỏ. Điểm mạnh là vừa có trực giác thực tế, vừa có bảo đảm lý thuyết cấp O(log n). [2]

**Gợi ý hiển thị slide:** sơ đồ luồng 3 bước: đoán B -> giải MCG-VRP -> nhị phân cập nhật cận.

---

### [02:20 - 04:35] Thuật toán greedy MCG-VRP và Oracle
Trong phần em phụ trách, thuật toán greedy cho MCG-VRP đi lần lượt từng xe; với mỗi xe gọi oracle trên tập khách còn lại mà xe đó tương thích; sau đó loại khách đã phủ khỏi tập X hiện hành.

Oracle trong bài toán này là điểm quan trọng. Theo khung bài báo, oracle là bicriteria: kiểm soát tốt số khách phủ được, nhưng có thể nới chi phí bởi hệ số beta. Trong cài đặt của em, beta đặt là 5.0 để bám cấu hình thực nghiệm của bài báo. [2]

Trong code, các thành phần này nằm ở:
- `vrpcc/approx_algorithm.py`: hiện thực Algorithm 1 và Algorithm 2.
- `vrpcc/k_tsp_oracle.py`: hiện thực oracle theo hướng k-TSP bicriteria, gồm nhánh exact cho tập nhỏ và greedy + 2-opt cho tập lớn.

Chi tiết kỹ thuật em nhấn mạnh là toàn bộ chi phí đều tính theo closed tour, tức có đoạn quay về depot, để bảo đảm nhất quán khi đo makespan.

**Gợi ý hiển thị slide:** pseudocode Algorithm 1, sau đó zoom vào 1 đoạn code chính trong `approx_algorithm.py`.

---

### [04:35 - 06:20] Hiện thực Algorithm 2 và bước cải thiện nghiệm
Với Algorithm 2, code thực hiện đúng tinh thần bài báo: khởi tạo cận trên bằng 2 lần tổng chi phí cạnh, cận dưới bằng 0, rồi binary search trên B.

Ở mỗi giá trị B, ta lặp greedy theo nhiều wave. Nếu một wave không phủ được ít nhất một nửa số khách còn lại thì xem B chưa khả thi. Nếu đạt điều kiện phủ thì ghép tuyến theo xe và tiếp tục đến khi phủ hết khách.

Sau khi có nghiệm từ Algorithm 2, em có bước cải thiện bằng local search trong `vrpcc/local_search.py`, gồm:
- 2-opt theo từng đoạn tuyến.
- relocation: lấy khách từ tuyến dài nhất, thử chèn sang xe tương thích khác nếu làm giảm makespan.

Bước này không thay đổi khung lý thuyết chính, nhưng giúp nghiệm thực tế tốt hơn ở nhiều instance.

**Gợi ý hiển thị slide:** 2 khối "Binary Search on B" và "Local Search (2-opt + relocation)".

---

### [06:20 - 07:15] Quy trình chạy benchmark và xuất báo cáo
Để thực nghiệm, em dùng script `scripts/run_comparison.py` chạy song song hai hướng: thuật toán xấp xỉ và MIP làm mốc so sánh.

Script xuất ra các artifact chính:
- `summary.json` để lưu đầy đủ từng instance.
- `comparison_table.csv` để tổng hợp trực tiếp các cột LB, UB, Obj, thời gian và tỷ lệ so sánh.
- log thuật toán để truy vết quá trình binary search và greedy.

Trong video này em dùng trực tiếp kết quả đã có ở `output_report_tight_v2` và `output_report_relaxed_v2`.

**Gợi ý hiển thị slide:** ảnh cây thư mục output + 1 screenshot bảng CSV.

---

### [07:15 - 09:15] Kết quả thực nghiệm tiêu biểu (có số cụ thể)
Em tóm tắt theo đúng hai nhóm compatibility.

Với nhóm tight:
- Tỷ lệ Obj trên LB2 dao động từ khoảng 1.0044 đến 1.2353, trung bình khoảng 1.1236.
- Thời gian thuật toán xấp xỉ dao động từ 0.1877 giây đến 7.0697 giây, trung bình khoảng 2.43 giây.
- Một ví dụ rất tốt là `r-n23-k6`: Obj/LB2 khoảng 1.0044, tức rất sát cận dưới.
- Trường hợp khó hơn là `c-n41-k10`: Obj/LB2 khoảng 1.2353.
- Với `RC-n41-k10`, MIP trong bản chạy này gặp giới hạn license nên không lấy được LB/UB; nhưng thuật toán xấp xỉ vẫn cho nghiệm và hoàn tất nhanh.

Với nhóm relaxed:
- Tỷ lệ Obj/LB2 nằm trong khoảng khoảng 1.0119 đến 1.5292, trung bình khoảng 1.1980.
- Thời gian thuật toán xấp xỉ khoảng 0.83 đến 2.12 giây, trung bình khoảng 1.23 giây.
- `RC-n21-k6` cho tỷ lệ tốt, khoảng 1.0119.
- `r-n21-k6` là trường hợp chênh lớn hơn, khoảng 1.5292.

Từ các số liệu này, em rút ra hai ý: tốc độ thuật toán xấp xỉ rất nhanh và ổn định; chất lượng nghiệm ở nhiều instance khá sát mốc MIP, đặc biệt trong nhóm tight.

**Gợi ý hiển thị slide:** 2 bảng nhỏ "tight" và "relaxed", bôi màu min/max của Obj/LB2.

---

### [09:15 - 09:55] Kết luận và thông điệp cá nhân
Tóm lại, phần em phụ trách cho thấy cách tiếp cận xấp xỉ trong bài báo có thể triển khai rõ ràng trong code, từ Algorithm 1, Algorithm 2, oracle đến local search, và cho ra kết quả thực nghiệm cụ thể để đối chiếu.

Thông điệp em muốn nhấn mạnh là: với các bài toán min-max có ràng buộc tương thích như VRPCC, hướng xấp xỉ là một lựa chọn thực tế, cân bằng giữa nền tảng lý thuyết và khả năng chạy được trên dữ liệu có quy mô tăng dần.

Em xin cảm ơn cô và các bạn đã lắng nghe.

**Gợi ý hiển thị slide:** slide kết luận 3 ý chính + lời cảm ơn.

---

## Câu hỏi phản biện thường gặp (gợi ý trả lời ngắn)

### 1) Vì sao không chỉ dùng MIP mà phải dùng thuật toán xấp xỉ?
Vì khi kích thước tăng, MIP tốn thời gian rất nhanh và có thể bị giới hạn tài nguyên hoặc license. Thuật toán xấp xỉ cho thời gian chạy ngắn, dễ mở rộng batch lớn, và vẫn giữ chất lượng nghiệm cạnh tranh ở nhiều instance.

### 2) Vì sao đặt beta = 5 mà không dùng hằng số tốt hơn?
Trong lý thuyết có mốc tốt hơn cho một số bài toán liên quan, nhưng lựa chọn beta = 5 trong bài báo và trong cài đặt ưu tiên tính đơn giản, dễ hiện thực, và vẫn đạt chất lượng thực nghiệm tốt.

### 3) Local search có làm mất bảo đảm lý thuyết không?
Bảo đảm lý thuyết gắn với khung thuật toán xấp xỉ trước local search. Local search là bước hậu xử lý thực nghiệm để cải thiện nghiệm, không phải phần dùng để chứng minh cận.

### 4) Tại sao kết quả nhóm không trùng tuyệt đối với bài báo?
Do khác môi trường chạy, phiên bản solver, cấu hình máy, và đặc biệt là dữ liệu được sinh ngẫu nhiên theo xác suất tương thích nên seed khác sẽ cho kết quả khác.

### 5) Phần đóng góp chính của em trong code là gì?
Em tập trung vào luồng thuật toán xấp xỉ: thiết kế và hiện thực greedy MCG-VRP, binary search trên B, tích hợp oracle k-TSP và bước local search, sau đó chạy benchmark và phân tích các chỉ số Obj/LB2 cùng thời gian.

---

## Tài liệu tham khảo dùng khi trình bày
- [1] G. B. Dantzig and J. H. Ramser, *The Truck Dispatching Problem*, 1959.
- [2] M. Yu, V. Nagarajan, S. Shen, *An Approximation Algorithm for Vehicle Routing with Compatibility Constraints*, 2019.
- [3] M. M. Solomon, *Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints*, 1987.
- [4] P. Toth, D. Vigo, *Vehicle Routing: Problems, Methods, and Applications*, 2014.
- [11] E. M. Arkin, R. Hassin, A. Levin, *Approximations for Minimum and Min-Max Vehicle Routing Problems*, 2006.

---

## Ghi chú luyện quay (không đọc trong video)
- Tốc độ nói mục tiêu: khoảng 125-140 từ/phút.
- Khi nói số liệu, dừng nhịp ngắn trước và sau mỗi con số chính để người nghe kịp theo dõi.
- Ưu tiên nhìn camera ở câu mở đoạn và câu kết đoạn; phần số liệu có thể nhìn slide.
