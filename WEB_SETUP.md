# BlockHouse 2 — cập nhật

Xem **installer/RELEASE_GUIDE.md** để cài Web + Desktop offline, nhập dữ liệu, backup và khôi phục. API dữ liệu `/api/v1` cũ đã khóa; chỉ health còn dùng được. Không chạy WPF cũ với BE mới. Một quyền quản trị, không triển khai nhiều role.

# API local cho BlockHouse Web

Frontend nằm riêng ở D:\source\BLH_website. Source này mở rộng BE Flask hiện tại và dùng lại database gốc.

## Chạy

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item backend-config.example.json backend-config.json
.\venv\Scripts\python.exe app.py
```

API web: http://127.0.0.1:5050/api/web. Endpoint dữ liệu /api/v1 cũ đã tắt, WPF Desktop mới dùng chung /api/web. Tạo tài khoản quản trị lần đầu bằng website trên máy BE; không có mật khẩu mặc định.

Thêm đúng domain HTTPS frontend vào allowed_origins trong backend-config.json, rồi restart BE. Không dùng wildcard. File ví dụ có http://127.0.0.1:8080 và http://localhost:8080 để preview.

Phiên dùng token hạn 12 giờ, hash token lưu SQLite và thu hồi khi logout. Có kiểm tra Origin/Host, CSRF, giới hạn đăng nhập theo máy khách và CORS preflight. Không phụ thuộc cookie bên thứ ba.

## Database

Giữ logic chọn DB hiện có trong config.py. BLOCKHOUSE_DB_PATH cho phép chỉ định đường dẫn tuyệt đối. Xác minh đúng DB và backup ngoài máy trước khi vận hành thật.

Nhân viên/dịch vụ/đơn vẫn dùng NhanVien, DichVu, DonHang, DonHang_DichVu. Bảng web_* bổ sung tài khoản, phiên, quy tắc và snapshot. Views/triggers cung cấp tên trường ổn định cho API; không đổi tên/xóa cột hoặc bảng WPF.

Lần đầu khởi tạo mở rộng, tạo backup nhất quán <database>.before-web.bak nếu chưa có rồi thêm bảng/views/triggers. Ngoài bản trước migration, BE thường tự backup lúc khởi động và mỗi 6 giờ; xem mục Tài khoản & sao lưu.

Đơn cũ lấy TongTien đã lưu, hoa hồng chưa xác định. Báo cáo nhân viên/hoa hồng chỉ gồm dòng web có snapshot; không tính lại giá cũ từ giá danh mục hiện tại. Không hủy đơn cũ qua web khi chưa đối soát.

Không dùng WPF/web sửa cùng đơn song song. API/báo cáo WPF cũ chưa hiểu snapshot nhiều nhân viên và trạng thái hủy mới.

## Demo và đóng gói

```powershell
.\venv\Scripts\python.exe app.py --demo
.\venv\Scripts\python.exe -m pip install pyinstaller
.\venv\Scripts\python.exe -m PyInstaller --clean --noconfirm BE.spec
```

Demo chỉ listen loopback, dùng demo-web.sqlite3 riêng, tự đăng nhập dữ liệu giả lập. Dừng demo trước khi chạy chế độ thường cùng cổng.

EXE: dist/BE.exe. Copy backend-config.json cạnh EXE và cung cấp DB đã đối soát. BE.spec mới không đóng gói DB thật vào EXE; không dùng spec cũ có kèm BlockHouse.db.

## Tests

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -p test_web_api.py -v
```

Tests dùng DB tạm, không mở production. Kiểm tra tính tiền, quy tắc, snapshot, gửi trùng, báo giá đổi, hủy khác tháng, xác thực, CSRF, CORS và legacy.

## LAN và giới hạn

Mặc định chỉ listen 127.0.0.1. Nếu cần hai máy: chọn IP LAN bằng --host, thêm IP vào allowed_hosts và giới hạn firewall trong mạng riêng. Hai máy gọi chung một BE. Không tự mở cổng Internet.

HTTPS website → HTTP LAN cần thử Chrome/Edge và quyền mạng local trên máy shop. HTTP LAN không mã hóa mật khẩu/token: chỉ dùng mạng tin cậy hoặc thêm HTTPS local trước khi mở rộng.

Có backup tự động và launcher chạy khi đăng nhập Windows. Không triển khai nhiều role theo yêu cầu. Chưa chốt/chi hoa hồng hoặc hoàn một phần; chưa nghiệm thu trên máy shop.

## Seed đầy đủ trong chế độ BE bình thường

Dữ liệu DB hiện tại được chủ dự án xác nhận là seed. Bộ seed đầy đủ được tạo bằng:

```powershell
.\venv\Scripts\python.exe seed_web.py --reset
.\dist\BE.exe
```

Lệnh seed thay dữ liệu mẫu trong DB mà Config đang chọn, tạo backup trước seed, thêm 6 nhân viên, 12 dịch vụ, 7 quy tắc và đơn trong 3 tháng gần nhất. Seed tự kiểm tra tổng dòng/tổng đơn, hoa hồng và khóa ngoại. Không dùng --demo để chạy bộ dữ liệu này.

Tài khoản seed: admin / BlockHouse@123. Đây chỉ là tài khoản dữ liệu thử, không phải tài khoản mặc định của phần mềm khi cài mới. Có thể truyền --username và --password vào script seed. Không chạy seed --reset với dữ liệu vận hành cần giữ.

## Web local (bộ cài 2.0.2 trở lên)

Bộ cài chứa sẵn thư mục `web` cạnh BE.exe. Khi BE chạy, mở `http://127.0.0.1:8080` để dùng bằng trình duyệt; không cần chạy npm, Internet hay khai báo domain HTTPS. API vẫn chạy cổng 5050, dùng chung dữ liệu với Desktop và tự cho phép origin của web local. Web chỉ lắng nghe trên 127.0.0.1.

Nếu cổng 8080 đang bị chiếm, BE ghi lỗi vào log và giữ API/Desktop hoạt động. Máy dev có thể dùng `--web-port 0` để tắt web đóng gói và tiếp tục dùng Vite. Thư mục `web` cho source BE được tạo bằng build-desktop.ps1. Dừng cả API và web bằng `BlockHouse.exe --stop-backend` của bản cài.


## Tránh chạy nhầm EXE cũ khi dùng VS Code

Terminal VS Code chạy `dist\BE.exe` sẽ dùng binary đã build, không tự nạp sửa đổi trong Python. `build-desktop.ps1` đồng bộ BE và web mới vào `dist` sau khi đóng gói. Nếu BE ở dist đang chạy và khóa file, script báo cảnh báo rõ ràng; dừng tiến trình đó rồi build lại trước khi chạy lại `dist\BE.exe`.

Khi phát triển trực tiếp với Vite ở cổng 8080, chạy source mới bằng:

```powershell
$env:BLOCKHOUSE_ALLOWED_ORIGINS="http://127.0.0.1:8080"
.\venv\Scripts\python.exe app.py --web-port 0
```

Chỉ chạy một BE giữ cổng 5050. Nếu trước đó đang chạy EXE, dừng EXE trước khi chạy Python. Không reset hay seed lại DB để sửa lỗi phiên bản.
