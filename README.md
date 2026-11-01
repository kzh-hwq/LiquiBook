# LiquiBook

Giám sát thanh khoản và áp lực sổ lệnh trên HOSE, dùng **NEO API của VPBankS** (kênh WebSocket `stockInfo`, sổ lệnh 3 mức giá).

> **Công cụ học thuật, không phải khuyến nghị đầu tư.** Chương trình chỉ đọc dữ liệu thị trường, không gửi lệnh giao dịch thật.

Đồ án cá nhân cuối kỳ, môn Gói phần mềm ứng dụng cho tài chính 1.

## Chức năng

- Thu thập dữ liệu thị trường theo thời gian thực qua WebSocket, lưu nguyên văn (JSONL, giờ UTC+7).
- Tính chỉ báo từ 3 mức giá mua/bán: spread, độ sâu, mất cân bằng sổ lệnh.
- Z-score cuộn để cảnh báo spread giãn rộng và áp lực mua/bán bất thường.
- Xếp hạng thanh khoản giữa các mã (điểm 0–100, trọng số chỉnh được).
- Kiểm chứng: tương quan hạng (Spearman) và tỷ lệ đúng hướng giữa mất cân bằng và lợi suất ngắn hạn.
- Giao diện Streamlit: chỉ số tổng hợp, biểu đồ, bộ lọc, bảng cảnh báo, trạng thái cập nhật.

## Cấu trúc

| Tệp | Vai trò |
|---|---|
| `neo_auth.py` | Đăng nhập, lấy và làm mới token JWT |
| `collector.py` | Thu thập dữ liệu WebSocket, ghi `data/raw_YYYY-MM-DD.jsonl` |
| `metrics.py` | Chỉ báo sổ lệnh cho một bản ghi (spread, độ sâu, mất cân bằng) |
| `parse_raw.py` | Đọc dữ liệu thô thành bảng pandas, lọc phiên khớp lệnh liên tục |
| `analysis.py` | Gộp theo phút, z-score, cảnh báo, xếp hạng, kiểm chứng |
| `app.py` | Giao diện Streamlit |
| `make_sample.py` | Sinh dữ liệu giả để chạy thử khi chưa có dữ liệu thật |
| `diag_ws.py` | Công cụ chẩn đoán kết nối WebSocket |
| `test_*.py` | Kiểm thử (pytest) |

## Cài đặt

Yêu cầu: Python 3.10 trở lên và lệnh `curl` (có sẵn trên macOS, Linux và Windows 10+).

```bash
python3 -m pip install -r requirements.txt
```

## Cấu hình

1. Sao chép `.env.example` thành `.env`.
2. Điền thông tin (không có khoảng trắng quanh dấu `=`):
   - `NEO_USERNAME`: **số lưu ký** của tài khoản chứng khoán VPBankS.
   - `NEO_PASSWORD`: mật khẩu đăng nhập.
   - `NEO_SYMBOLS`: danh sách mã cần theo dõi, cách nhau dấu phẩy.
3. Đăng ký NEO API trên NEO Invest Web và **khai báo đúng địa chỉ IP** sẽ dùng để chạy. NEO API chỉ chấp nhận IP đã đăng ký.

Không bao giờ đưa tệp `.env` hay thư mục `data/` lên kho mã (đã có trong `.gitignore`).

## Cách chạy

Thử nhanh, không cần API:

```bash
python3 make_sample.py             # tạo dữ liệu giả vào data_sample/
python3 analysis.py data_sample    # xem xếp hạng, cảnh báo, kiểm chứng
python3 -m streamlit run app.py    # giao diện (tự dùng dữ liệu mẫu nếu data/ còn trống)
python3 -m pytest -q               # kiểm thử
```

Với dữ liệu thật (trong giờ giao dịch, từ đúng IP đã đăng ký):

```bash
python3 neo_auth.py        # kiểm tra đăng nhập
python3 collector.py       # thu thập dữ liệu, để chạy suốt phiên (Ctrl+C để dừng)
python3 analysis.py        # phân tích dữ liệu trong data/
python3 -m streamlit run app.py
```

Trên macOS, dùng `caffeinate -i python3 collector.py` để máy không tự ngủ giữa phiên.

## Phương pháp (tóm tắt)

```
spread_pct  = (ask1 − bid1) / mid × 100
imbalance   = (KL mua top3 − KL bán top3) / (KL mua top3 + KL bán top3)    trong [−1, +1]
z-score     = (x_t − trung bình w khung trước) / độ lệch chuẩn w khung trước
điểm        = 100 × (w_spread·r_spread + w_depth·r_depth + w_turnover·r_turnover)
```

`r_*` là thứ hạng tương đối giữa các mã (0 đến 1). Phiên ATO/ATC và sổ lệnh không hợp lệ bị loại. Chi tiết xem tài liệu cơ sở lý thuyết trong báo cáo.

## Hạn chế

- Dữ liệu chỉ có **3 mức giá** mỗi phía, nên đây là áp lực ở đỉnh sổ lệnh.
- Mất cân bằng là bản chụp tĩnh, lệnh chờ có thể bị hủy, nên không bảo đảm hướng giá.
- Bước giá lớn làm spread tương đối của cổ phiếu thanh khoản cao ít biến thiên.
- Số phiên dữ liệu ít, kết quả kiểm chứng mang tính mô tả.
- Trọng số điểm thanh khoản do tác giả chọn.

## Kết quả

_(Điền sau khi thu thập đủ dữ liệu: số phiên, danh sách mã, xếp hạng, kết quả kiểm chứng.)_

## Ghi chú kỹ thuật

- `neo_auth.py` gọi `curl` thay cho thư viện `requests` vì tường lửa của máy chủ chặn kết nối từ `requests` (HTTP 403) nhưng chấp nhận `curl`.
- `collector.py` dùng `certifi` để xác thực chứng chỉ SSL trên Python cài từ python.org (macOS).
- Dữ liệu thô lưu nguyên văn để có thể tính lại chỉ báo mà không cần thu thập lại.
