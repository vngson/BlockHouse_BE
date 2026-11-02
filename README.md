# BlockHouse 2 — local Web + Desktop

Hướng dẫn hiện hành: **installer/RELEASE_GUIDE.md**. API dữ liệu WPF cũ bên dưới không còn mở; bản Desktop mới dùng `/api/web` có đăng nhập và giao diện offline đóng gói sẵn. Build/cài theo hướng dẫn mới, không đóng gói DB.

## Bản 2.0.17

Báo cáo nhân viên theo ngày hoặc tháng và Doanh thu từng ngày có nút **Xem dịch vụ**, gồm Dịch vụ / Số lượng / Đơn giá / Tổng tiền / Hoa hồng. Số lượng tính theo ngày tạo đơn, không tính đơn đã hủy và không trừ lượt hủy của ngày khác. Giá, tổng tiền và hoa hồng lấy theo lịch sử đơn; dữ liệu cũ thiếu thông tin tiền theo dịch vụ hiển thị —. Nhiều mức giá hiển thị khoảng đơn giá. Cột Xem dịch vụ thu gọn và căn phải đồng nhất. Nâng cấp giữ database và cấu hình hiện tại.


## Bản 2.0.18 — mặc định hoa hồng 100%

Không có quy tắc đang hiệu lực áp dụng cho dòng dịch vụ thì hoa hồng bằng 100% số tiền dòng sau giảm giá. Thứ tự ưu tiên quy tắc không đổi; mức đã cấu hình, kể cả 0%, vẫn được giữ theo snapshot thanh toán.

Khi khởi động BE mới, chỉ các dòng có snapshot chính xác `Chưa cấu hình · 0đ` và hoa hồng 0 được đổi sang 100% tiền đã lưu. BE tạo bản sao SQLite nhất quán cạnh DB, tên `BlockHouse.db.before-default-commission-100-<mã>.bak`, trước khi cập nhật trong một giao dịch; nếu backup thất bại thì không sửa dữ liệu. Tổng hoa hồng đơn được cộng lại từ các dòng để chi tiết, báo cáo, CSV và điều chỉnh hủy khớp nhau. Không thay giá, số lượng, tổng tiền hoặc các mức hoa hồng đã cấu hình. Chạy lại không cập nhật trùng. Bộ cài 2.0.18 có thay đổi này; bản 2.0.17 trước đó chưa có.

---

# BlockHouse BE

Backend API cho hệ thống quản lý salon/barber shop, xây dựng bằng Flask.

## Tech Stack

- **Python 3** + **Flask**
- **Flask-SQLAlchemy** (SQLite)
- **Marshmallow** (validation & serialization)
- **Flask-CORS**

## Cấu trúc dự án

```
BlockHouse_BE/
├── app.py                  # Entry point, Flask app factory
├── config.py               # Cấu hình database
├── settings.py             # Cài đặt (PAGE_SIZE)
├── requirements.txt
├── controllers/            # Route handlers
│   ├── health_controller.py
│   ├── employee_controller.py
│   ├── service_controller.py
│   ├── order_controller.py
│   └── dashboard_controller.py
├── services/               # Business logic
├── models/                 # SQLAlchemy models
├── requests/               # Marshmallow request schemas
├── responses/              # Marshmallow response schemas
├── helpers/
│   └── format_response.py  # Standardized JSON response
└── utils/
    └── logger.py
```

## Cài đặt & Chạy

```bash
# Tạo virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# Cài dependencies
pip install -r requirements.txt

# Chạy server
python app.py
```

Server chạy tại `http://localhost:5050`.

## API Endpoints

Base URL: `/api/v1`

Response format chuẩn:

```json
{
  "data": "<dữ liệu>",
  "message": "<thông báo>",
  "status": 200
}
```

### Health Check

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/v1/health/` | Kiểm tra server |

### Employees

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/v1/employees/` | Danh sách nhân viên (phân trang, filter) |
| GET | `/api/v1/employees/{id}` | Chi tiết nhân viên |
| POST | `/api/v1/employees/create_employee` | Tạo nhân viên |
| PUT | `/api/v1/employees/{id}` | Cập nhật nhân viên |
| DELETE | `/api/v1/employees/{id}` | Xóa nhân viên |

**Query params (GET /):** `page`, `page_size`, `date_from`, `date_to`, `keyword`

### Services

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/v1/services/` | Danh sách dịch vụ (phân trang) |
| GET | `/api/v1/services/all` | Tất cả dịch vụ (không phân trang) |
| GET | `/api/v1/services/{id}` | Chi tiết dịch vụ |
| POST | `/api/v1/services/` | Tạo dịch vụ |
| PUT | `/api/v1/services/{id}` | Cập nhật dịch vụ |

**Query params (GET /):** `page`, `page_size`, `keyword`

### Orders

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/v1/orders/` | Danh sách đơn hàng |
| GET | `/api/v1/orders/{id}` | Chi tiết đơn hàng |
| POST | `/api/v1/orders/create` | Tạo đơn hàng |
| PUT | `/api/v1/orders/{id}` | Cập nhật đơn hàng |
| DELETE | `/api/v1/orders/{id}` | Xóa đơn hàng |
| POST | `/api/v1/orders/by_date` | Đơn hàng nhóm theo ngày |
| POST | `/api/v1/orders/revenue_by_employee` | Doanh thu theo nhân viên |
| POST | `/api/v1/orders/for_one_date` | Đơn hàng theo 1 ngày |
| POST | `/api/v1/orders/by_date_and_employee` | Lọc theo ngày + nhân viên |

**Query params (GET /):** `page`, `page_size`, `date_from`, `date_to`, `keyword`

### Dashboard

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/v1/dashboard/` | Dữ liệu dashboard |

**Query params:** `month` (1-12), `year` (>= 2000)

Chi tiết đầy đủ: [API_DOCS.md](API_DOCS.md)

## License

Private

Bản 2.0.18: Cài đặt hoa hồng có nút Xóa kèm xác nhận, xóa được cả mức đang áp dụng và đã ngừng. Chỉ xóa cấu hình; snapshot hoa hồng đơn cũ giữ nguyên. Đơn mới dùng mức còn lại hoặc mặc định 100% nếu không có mức phù hợp. Quote đang chờ thanh toán được kiểm tra lại trước khi lưu.

## Bản 2.0.19

Doanh thu năm: cột Tháng dùng sắp xếp thay vì bộ lọc. Mặc định tháng 01 đến 12; nhấn tiêu đề Tháng để đảo chiều. Giữ nguyên số liệu, tổng năm, tính hoa hồng và bản sửa dữ liệu của 2.0.18.
