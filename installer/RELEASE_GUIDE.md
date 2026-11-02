# BlockHouse 2 — Web + Desktop local

Một tài khoản quản trị, toàn quyền. Web và WPF Desktop mới dùng cùng `/api/web`, cùng giá/hoa hồng/snapshot/đơn hàng và cùng SQLite. Desktop là WPF + WebView2 với React được **đóng gói tại máy**, không mở website Vercel bên trong iframe. Không cần Internet để mở Desktop hoặc bán hàng sau khi cài đầy đủ. Web cần hosting hoạt động để tải giao diện.

## Bộ cài

`installer/output/BlockHouse-Setup-2.0.19-x64.exe` cài WPF self-contained .NET, BE, giao diện offline và bộ cài WebView2 x64 offline chính thức của Microsoft. Không đóng gói DB, tài khoản mẫu hoặc mật khẩu vào bộ cài. Máy đích không cần Python/Node/.NET SDK.

- Windows x64; cài cho tài khoản Windows hiện tại, không yêu cầu quyền quản trị.
- Chương trình: `%LOCALAPPDATA%\Programs\BlockHouse`.
- Dữ liệu: `%LOCALAPPDATA%\BlockHouse\data\BlockHouse.db`.
- Cấu hình: `%LOCALAPPDATA%\BlockHouse\data\backend-config.json`.
- Backup: mặc định `data\backups`; log có xoay vòng: `data\logs`.
- Profile WebView2: `data\WebView2`; không dùng chung phiên đăng nhập với Chrome/Edge.
- Tùy chọn tự khởi động bật mặc định. Registry HKCU Run gọi `BlockHouse.exe --backend` khi đăng nhập Windows; launcher chạy ẩn, khởi động lại BE khi BE lỗi. Không phải Windows Service, không chạy khi người dùng đã đăng xuất.
- Đóng Desktop không tắt BE. Shortcut “Dừng BE để bảo trì” dừng launcher/BE. Hoàn tất đơn đang nhập trước khi dừng/nâng cấp; yêu cầu đang xử lý được chờ hoàn tất, nếu quá thời gian launcher buộc dừng và SQLite rollback giao dịch chưa commit. Khi phản hồi thanh toán bị gián đoạn, kiểm tra lịch sử trước khi tạo đơn khác.
- Gỡ cài đặt giữ DB, backup, profile và cấu hình. Nâng cấp không ghi đè chúng. Không tự đăng ký mở cổng firewall.

## Cài lần đầu và chuyển dữ liệu

1. Hoàn tất thanh toán, đóng WPF cũ để lấy bản sao DB nhất quán. BE 2.0 dùng cổng 5050, BE cũ cổng 5000 có thể chạy riêng. Không dùng WPF cũ với BE mới: API dữ liệu `/api/v1` đã tắt để tránh bỏ qua xác thực/snapshot.
2. Giữ một bản sao DB cũ ngoài máy trước khi chuyển. Xác minh đúng file đang dùng; đường dẫn dev cũ có thể là `D:\Release_BlackHouse\BlockHouse.db`.
3. Chạy Setup. Trang dữ liệu cho chọn **file DB cũ** để nhập. Bỏ trống nghĩa là tạo shop mới, không phải tự tìm/nhập DB cũ. Nếu DB đích đã tồn tại, bộ cài giữ nguyên và bỏ qua nhập.
4. Nhập đúng origin HTTPS của website, không có `/` cuối hoặc đường dẫn; có thể bỏ trống để dùng Desktop trước. Không dùng wildcard. Cài nâng cấp giữ cấu hình domain cũ; muốn đổi domain thì sửa file cấu hình rồi restart BE.
5. Mở BlockHouse. DB mới yêu cầu tạo tài khoản đầu tiên. Nếu nhập DB có tài khoản thì dùng tài khoản đó; dữ liệu seed phải đổi mật khẩu trước vận hành thật tại **Tài khoản & sao lưu**.
6. Kiểm tra nhân viên, dịch vụ, đơn, quy tắc hoa hồng và tổng báo cáo với DB cũ trước khi giao shop. Đơn WPF cũ chưa có snapshot hoa hồng giữ tổng gốc và mặc định hoa hồng 100% tổng tiền đã lưu, gán cho nhân viên lưu trên đơn. Hoa hồng đã ghi nhận (kể cả 0) giữ nguyên.

Import sử dụng SQLite backup API và kiểm tra integrity/schema, giữ nguyên nguồn và từ chối ghi đè DB đích. Để tránh mở nhầm DB, launcher luôn truyền `--data-dir`; BE chạy tay không có tham số vẫn giữ cách chọn DB cũ dành cho dev.

## Backup và khôi phục

BE tạo backup nhất quán lúc khởi động và mỗi 6 giờ khi đang chạy, mặc định giữ 30 bản; kiểm tra `PRAGMA quick_check` trước khi coi là thành công. Có nút **Sao lưu ngay**, trạng thái lần gần nhất và thư mục tại **Tài khoản & sao lưu**.

Có thể đặt thư mục backup trên ổ khác bằng cấu hình (đường dẫn tuyệt đối, dấu `\\` trong JSON):

```json
{"allowed_origins":["https://blockhouse.example.com"],"allowed_hosts":[],"backup":{"directory":"E:\\BlockHouseBackups","interval_hours":6,"keep":30}}
```

Chỉ bản trên cùng ổ không chống hỏng ổ/mất máy. Giữ thêm bản ngoài máy; không tự gửi DB lên dịch vụ cloud nào. File DB và backup **chưa mã hóa ở cấp ứng dụng**: giới hạn quyền Windows, bảo vệ tài khoản máy, và cân nhắc BitLocker/device encryption. Người có quyền Windows của shop hoặc admin vẫn có thể đọc DB. Không đặt dữ liệu trong thư mục public, Git hoặc thư mục chia sẻ cho mọi người.

Khôi phục có chủ đích: dừng cả BE/Desktop, giữ nguyên toàn bộ thư mục dữ liệu hiện tại dưới tên khác để có thể quay lại; tạo lại thư mục dữ liệu và nhập **bản backup đã chọn** bằng `BE.exe --data-dir "<thư mục dữ liệu>" --import-db "<backup>"`, chép cấu hình cũ rồi chạy lại. Không chép đè `.db` khi BE đang chạy. Backup phục hồi cả tài khoản/mật khẩu tại thời điểm đó; đổi mật khẩu sau restore để thu hồi các phiên được phục hồi. Nghiệm thu tổng doanh thu và một đơn mẫu trước khi bán tiếp.

## Bảo mật đã triển khai

- Chỉ listen loopback mặc định; launcher chỉ gọi `127.0.0.1:5050`.
- API cũ trả 410 ngay cả request không có Origin. Health không tiết lộ dữ liệu shop.
- Password hash, token ngẫu nhiên 12 giờ (hash lưu DB), thu hồi logout, CSRF, Origin/Host allowlist, giới hạn request và đăng nhập; đổi mật khẩu yêu cầu mật khẩu cũ, giới hạn thử và thu hồi toàn bộ phiên cũ.
- Không thêm role. Mọi tài khoản đăng nhập được phép quản trị theo yêu cầu.
- Desktop chỉ cho tải tài nguyên UI đã đóng gói và gọi API loopback; chặn điều hướng/tab mới/remote resources, chỉ có cầu nối nhớ tài khoản cho trang bundle nội bộ, không cung cấp truy cập file tùy ý; hỗ trợ lưu mật khẩu qua kho WebView2 khi người dùng đồng ý, không lưu mật khẩu trong dữ liệu website.
- CSV vẫn tải qua API có xác thực. Web/desktop giữ logic BE tính lại quote trước khi thanh toán và chống gửi đơn trùng.
- `vercel.json` và `_headers` khai báo CSP/nosniff/deny framing/referrer policy. Desktop bundle có CSP meta tương ứng. CSP cho inline **style attributes** của React/popover nhưng không cho inline script. Cấu hình hiện chỉ cho API loopback cổng 5050; LAN cần thiết kế HTTPS/firewall/CSP riêng, không tự mở rộng cho mọi IP.

Đây không phải chứng nhận “an toàn tuyệt đối”. Chưa có mã hóa DB, MFA, audit log mọi thay đổi, hoặc giải pháp xem báo cáo ngoài shop. Máy tắt/ngủ hoặc BE hỏng thì cả web/Desktop đều không gọi được dữ liệu. Desktop chỉ loại bỏ phụ thuộc Vercel/Internet cho giao diện, không phải BE/DB dự phòng thứ hai.

## Build lại

Từ source WPF:

```powershell
.\build-desktop.ps1 -IsccPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' -RuntimeInstaller '<MicrosoftEdgeWebView2RuntimeInstallerX64.exe>'
```

Project mặc định target .NET 8 để mở/build bằng Visual Studio hiện có. Script phát hành chọn `net10.0-windows` bằng thuộc tính `-p:BlockHouseRelease=true` qua CLI, không cần nâng Visual Studio. Build bộ cài yêu cầu .NET 10 LTS SDK, Node/npm và backend venv đã có requirements + PyInstaller. Hai source BE/Web mặc định là thư mục sibling; có tham số `-WebSource`, `-BackendSource`, `-NodeExe`, `-NpmCli`, `-DotnetExe`. `-SkipInstaller` chỉ build payload tự chứa trong `publish/win-x64`. Compiler Inno 6.7+ và WebView2 standalone x64 tải từ nhà phát hành; script xác minh chữ ký Microsoft của runtime. Không tải runtime hay compiler khi khách đang dùng offline.

Script chạy tests Web/BE, build React, chép bundle local sạch, build BE sang `installer/artifacts/backend` (không ghi đè BE.exe dev đang chạy), publish WPF và từ chối payload có DB. Source giao diện WPF cũ giữ để tham chiếu nhưng không biên dịch hoặc chạy trong app mới.

Trước giao shop cần thử cài/nâng cấp/gỡ trên Windows sạch, reboot đăng nhập, mất Internet, đổi mật khẩu ở cả web/Desktop, tải CSV, restore backup, và đối soát đơn giữa hai ứng dụng. Setup/BE/desktop hiện chưa có chứng thư code signing của dự án; Windows/SmartScreen có thể cảnh báo nhà phát hành chưa xác minh.

Vercel Hobby giới hạn mục đích cá nhân/phi thương mại. Chọn gói phù hợp hoặc một static host khác khi vận hành shop; bản build React không phụ thuộc Vercel. Sau deploy phải kiểm tra header thực tế và quyền local-network trên Chrome/Edge của máy shop.

## Kiểm tra trên máy phát triển

- Frontend: build production thành công, 17 tests đạt.
- Backend: 21 tests đạt (bao gồm số tiền/hoa hồng, snapshot, hủy, xác thực, mật khẩu, backup/WAL/retention/import và startup/shutdown tiến trình Windows thực).
- WPF publish self-contained .NET 10 thành công, runtime 10.0.13; bỏ BinaryFormatter và dependencies UI cũ khỏi bản chạy.
- Bộ cài x64 biên dịch thành công, gồm WebView2 standalone có chữ ký Microsoft hợp lệ; payload không có DB.
- Chưa cài/gỡ/nâng cấp thật trên Windows sạch, chưa kiểm tra giao diện WPF trực tiếp hoặc cắt Internet thực tế, chưa deploy/kiểm tra headers trên hosting.
- Database hiện tại trên máy không bị chuyển/xóa/reset. File BlockHouse.db trong source BE đã bỏ theo dõi Git và được giữ nguyên trên ổ; lịch sử Git cũ vẫn có dữ liệu seed.

## Bản 2.0.1

- Báo cáo nhân viên bao gồm doanh thu và số lượng dịch vụ đã lưu trong đơn WPF cũ. Không tính lại giá hoặc hoa hồng quá khứ bằng cấu hình hiện tại; hoa hồng thiếu dữ liệu được ghi chưa xác định.
- Doanh thu tháng có tab Theo ngày và CSV tương ứng. Đơn hủy ghi giảm ở ngày hủy.
- Dropdown tự giới hạn trong vùng hiển thị, gồm phần thanh cuộn cửa sổ.
- Đóng BlockHouse và dừng BE bằng lệnh --stop-backend theo hướng dẫn trước khi cài nâng cấp. Giữ nguyên thư mục dữ liệu đang dùng; không nhập lại hoặc chép đè DB.
- Khi file BE build cũ đang chạy, có thể truyền -BackendOutput với thư mục artifact riêng vào build-desktop.ps1.

Trên máy shop: đóng cửa sổ BlockHouse, mở PowerShell và chạy:

```powershell
& "$env:LOCALAPPDATA\Programs\BlockHouse\BlockHouse.exe" --stop-backend
```

Sau đó chạy `BlockHouse-Setup-2.0.14-x64.exe` bằng đúng tài khoản Windows đã cài bản trước. Bản nâng cấp giữ DB, cấu hình và backup tại vị trí cũ. Chỉ import DB khi cài mới lần đầu. Sau nâng cấp, đối chiếu một tháng có đơn WPF cũ ở tab Theo nhân viên và tổng tháng ở tab Theo ngày.

## Bản 2.0.2: web local

Sau khi cài và BE đã chạy, mở `http://127.0.0.1:8080` bằng Chrome/Edge. Không cần Node.js, npm, Internet hoặc nhập HTTPS trong setup. Desktop dùng cùng UI và DB. Cổng 5050 vẫn là API có xác thực; cổng 8080 chỉ phục vụ index/assets của bản web đóng gói, chỉ lắng nghe 127.0.0.1.

Tắt cửa sổ Desktop không dừng BE/web; `BlockHouse.exe --stop-backend` dừng cả API và web local. Khởi động Windows sẽ chạy lại BE/web theo cấu hình autostart hiện có. Khi cổng 8080 đang bị chương trình khác chiếm, API/Desktop vẫn chạy và lỗi web local được ghi tại `data/logs/backend.log`.

Máy dev đang chạy Vite cổng 8080: dừng Vite trước khi thử web đóng gói, hoặc chạy BE với `--web-port 0` để giữ Vite. Không bật hai web server cùng cổng. BE chạy từ source cần thư mục `web` do build-desktop.ps1 tạo; bản setup đã có sẵn.
## Bản 2.0.3

Báo cáo Theo ngày có thêm Lượt dịch vụ thuần và Hoa hồng phát sinh, gồm tổng tháng và CSV. Số lượt/hoa hồng đơn hủy ghi giảm vào ngày hủy. Hoa hồng đơn WPF cũ thiếu dữ liệu hiển thị chưa xác định; các ngày có cả đơn mới và cũ ghi chú phần chưa bao gồm. Không thay đổi dữ liệu lịch sử.

## Bản 2.0.4

Các bảng đơn hàng, doanh thu nhân viên/ngày/năm và danh mục có sắp xếp/lọc tại header. Bấm tên cột để đổi tăng dần, giảm dần, thứ tự gốc. Nút phễu lọc bằng từ khóa, khoảng số hoặc lựa chọn trạng thái/thanh toán. Có thể kết hợp nhiều cột, xóa lọc riêng hoặc toàn bảng. Lọc/sắp xếp trước phân trang (mặc định 10); báo cáo ngày/năm hiển thị tổng các dòng đang lọc. Xuất CSV vẫn xuất toàn bộ báo cáo trong kỳ.

## Bản 2.0.5

Mỗi cột có đúng một thao tác: cột số tiền/số đơn/lượt dịch vụ/hoa hồng chỉ sắp xếp; cột tên/ngày/tháng/số điện thoại/trạng thái/thanh toán chỉ lọc. Không hiển thị cả sort và filter trên cùng cột. Các thao tác vẫn xử lý trước phân trang, tổng hiển thị cập nhật theo lọc; CSV xuất toàn bộ kỳ.

## Bản 2.0.6

- Tách Mã đơn (lọc mã) và Ngày giờ (sắp xếp thời điểm) trong bảng đơn hàng/đơn gần đây.
- Theo nhân viên có hai chế độ Theo tháng / Theo ngày; ngày được chọn trong tháng hiện tại trên báo cáo. CSV xuất đúng ngày. Hủy đơn ghi giảm vào ngày hủy; hoa hồng đơn cũ không đủ dữ liệu vẫn ghi chưa xác định.
- Cần cập nhật BE cùng UI. UI sẽ cảnh báo khi BE cũ chưa hỗ trợ báo cáo ngày; không lấy nhầm báo cáo tháng.

## Bản 2.0.7

Nhãn Chọn ngày được đặt bên trái ô chọn ngày, cùng hàng với hai nút chọn chế độ ở desktop/tablet để không đẩy bảng xuống. Các nhãn báo cáo, tạo đơn, cài đặt hoa hồng, kết nối và sao lưu được viết lại ngắn gọn, CSV đồng bộ tên cột. Không đổi công thức hoặc dữ liệu nghiệp vụ. Đã kiểm tra bố cục desktop/tablet/mobile và đối chiếu dữ liệu trước/sau khi cập nhật dist BE.exe.

Bản 2.0.8: Tạo đơn bỏ chọn phương thức thanh toán và giảm giá; mặc định không theo dõi phương thức, không giảm giá. Bỏ cột cách thanh toán trong bảng doanh thu và đơn gần đây, giữ dữ liệu lịch sử. Tắt BE qua sự kiện Windows được xử lý trên luồng I/O của Waitress để tránh lỗi đóng socket đồng thời.

Bản 2.0.9: Nhớ mật khẩu sử dụng kho mật khẩu trình duyệt/WebView2; chọn Nhớ mật khẩu trên máy này khi đăng nhập và chấp nhận hộp thoại Lưu nếu có. Lần sau dùng gợi ý tên đăng nhập hoặc Điền tài khoản đã lưu, sau đó bấm Đăng nhập. Không kéo dài phiên API 12 giờ, không lưu mật khẩu hoặc bearer token dài hạn trong localStorage. Web và Desktop có kho riêng; trình duyệt không hỗ trợ Credential Management API dùng autocomplete chuẩn. Chức năng API cần HTTPS hoặc loopback localhost/127.0.0.1. Mật khẩu đã lưu được quản lý/xóa bằng trình quản lý mật khẩu của môi trường đó.

Bản 2.0.10: Đơn WPF cũ chưa có snapshot được tính hoa hồng mặc định 100% tổng tiền đã lưu, đồng bộ đơn hàng, chi tiết, báo cáo ngày/tháng/năm và CSV. Đây là quy ước mặc định khi đọc lịch sử, không phải mức hoa hồng đã từng được chi trả. Không thay giá dịch vụ, doanh thu gốc hoặc snapshot hoa hồng đã có. Chọn DB cũ ở Setup vẫn sao chép bằng SQLite backup API, giữ nguồn; khi BE mở bản sao sẽ cập nhật view báo cáo trong một giao dịch. DB đã nhập ở bản trước cũng được áp dụng, không cần nhập lại. Đơn mới tiếp tục dùng quy tắc hoa hồng hiện hành.

Bản 2.0.11: API 2.0 mặc định tại http://127.0.0.1:5050; cổng 8080 vẫn phục vụ giao diện web local. Web tự chuyển địa chỉ đã lưu ở cổng 5000 sang 5050, không sao chép token phiên giữa hai cổng. Launcher và WebView2/CSP dùng 5050. Không thay cổng, DB hay tiến trình của bản BE cũ tại shop.

Bản 2.0.12: Chạy tay BE.exe trong terminal hiện API/Web và lỗi khởi động; terminal không trả prompt khi BE vẫn đang chạy. Launcher WPF/Startup vẫn ẩn console bằng CreateNoWindow. BE giữ độc quyền cổng API trên Windows, từ chối bản chạy trùng kể cả khác thư mục dữ liệu, không mở DB của bản thứ hai.

Bản 2.0.13: WPF bỏ nút Điền tài khoản đã lưu, dùng remembered-login.json tại thư mục data AppData. Chỉ lưu sau khi đăng nhập thành công và tick Nhớ tài khoản; cả tên và mật khẩu nằm trong payload DPAPI CurrentUser, JSON không chứa mật khẩu rõ. Vào màn hình đăng nhập sẽ tự điền; đăng xuất vẫn giữ lựa chọn nhớ; bỏ tick rồi đăng nhập thành công sẽ xóa file. Đổi mật khẩu cập nhật thông tin nhớ nếu đúng tài khoản đang lưu. JSON lỗi/không giải mã được không ngăn đăng nhập thủ công. Cầu nối WebView2 chỉ nhận trang https://blockhouse.desktop/index.html và API 127.0.0.1:5050, chỉ thao tác một đường dẫn JSON cố định. Web thông thường dùng autocomplete Chrome/Edge, không truy cập JSON của WPF. Đã sửa nền vùng gutter để bỏ dải đen nhưng giữ chỗ scrollbar; icon tiêu đề dùng logo màu có nền sáng.

Bản 2.0.14: Thanh tiêu đề WPF riêng cao 40 DIP, logo và font Bebas Neue có sẵn được đóng gói offline; nút thu nhỏ/phóng to-thu về/đóng theo style BlockHouse. WindowChrome giữ thao tác kéo, nhấp đúp và resize native. Theme nhận qua kênh blockhouse-theme chỉ từ trang index.html của origin nội bộ, không nhận lệnh điều khiển cửa sổ từ JavaScript. Nút đóng vẫn chỉ đóng Desktop, không dừng BE. Đã render XAML thật ở sáng/tối, 360/1200px và kiểm tra ba nút có tên truy cập, không tràn. Cần kiểm tra tương tác native và taskbar trên máy đích.

## Bản 2.0.17

Báo cáo nhân viên theo ngày hoặc tháng và Doanh thu từng ngày có nút **Xem dịch vụ**, gồm Dịch vụ / Số lượng / Đơn giá / Tổng tiền / Hoa hồng. Số lượng tính theo ngày tạo đơn, không tính đơn đã hủy và không trừ lượt hủy của ngày khác. Giá, tổng tiền và hoa hồng lấy theo lịch sử đơn; dữ liệu cũ thiếu thông tin tiền theo dịch vụ hiển thị —. Nhiều mức giá hiển thị khoảng đơn giá. Cột Xem dịch vụ thu gọn và căn phải đồng nhất. Nâng cấp giữ database và cấu hình hiện tại.

## Bản 2.0.18

- Không có quy tắc đang hiệu lực áp dụng thì hoa hồng mặc định bằng 100% tiền dịch vụ sau giảm giá. Quy tắc đã đặt, kể cả 0%, giữ nguyên theo snapshot lúc thanh toán.
- BE tự sửa các dòng cũ có snapshot chính xác `Chưa cấu hình · 0đ` và hoa hồng 0 khi khởi động. Trước khi sửa, tạo backup SQLite nhất quán cạnh DB: `BlockHouse.db.before-default-commission-100-<mã>.bak`. Không sửa nếu backup thất bại; cập nhật các dòng và tổng hoa hồng đơn trong một giao dịch. Không đổi doanh thu, giá, số lượng hoặc các mức hoa hồng đã cấu hình. Chạy lại không sửa trùng.
- Cài đặt hoa hồng có nút Xóa kèm xác nhận; xóa được mức đang áp dụng hoặc đã ngừng, không thay hoa hồng đơn cũ. Đơn mới dùng mức còn lại hoặc mặc định 100%. Quote cũ được kiểm tra lại trước thanh toán.
- Nâng cấp trên cùng tài khoản Windows giữ DB và cấu hình AppData. Không cần nhập lại DB. Khi BE mới khởi động, bước sửa trên tự chạy; có thể dừng/chạy BE bằng `BlockHouse.exe --stop-backend` / `BlockHouse.exe --backend`.

## Bản 2.0.19

Doanh thu năm: cột Tháng dùng sắp xếp thay vì bộ lọc. Mặc định tháng 01 đến 12; nhấn tiêu đề Tháng để đảo chiều. Giữ nguyên số liệu, tổng năm, tính hoa hồng và bản sửa dữ liệu của 2.0.18.
