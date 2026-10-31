# BlockHouse 2 — local Web + Desktop

Hướng dẫn hiện hành: **installer/RELEASE_GUIDE.md**. API dữ liệu WPF cũ bên dưới không còn mở; bản Desktop mới dùng `/api/web` có đăng nhập và giao diện offline đóng gói sẵn. Build/cài theo hướng dẫn mới, không đóng gói DB.

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
