# AutoClap

Ứng dụng desktop tự thả **👏** bằng tài khoản Telegram cá nhân khi tin nhắn mới trong nhóm/kênh đã chọn có **cả số di động Việt Nam và từ khóa `care`**. Chạy trên Windows và macOS, không cần server.

## Bản Chrome không cần API ID/Hash

Có thêm [Chrome extension](chrome-extension/README.md), dùng phiên Telegram WebK đăng nhập bằng QR, chạy trên Chrome Windows/macOS. Giải nén `dist/AutoClap-Chrome.zip`, vào `chrome://extensions` → Developer mode → Load unpacked rồi chọn thư mục chứa manifest.json. Sau khi tải lại Telegram WebK, mở nhóm và bấm Bắt đầu trong extension. Mỗi tab theo dõi một nhóm; cần giữ tab hoạt động. Đóng gói bằng `python3 scripts/package_extension.py`; chạy bộ test extension bằng `npm ci && npm run test:extension`.

## Dùng ứng dụng đã đóng gói

- **macOS:** mở `dist/AutoClap.app`, hoặc giải nén `AutoClap-macOS-*.zip` rồi mở ứng dụng bên trong. Có thể kéo vào Applications. Bản build cục bộ chưa ký Developer ID/notarize; nếu Gatekeeper chặn, dùng System Settings → Privacy & Security → Open Anyway cho bản bạn tự build.
- **Windows:** giải nén toàn bộ `AutoClap-Windows.zip`, mở `AutoClap/AutoClap.exe`. Giữ nguyên thư mục `_internal` đi kèm.

Bản macOS và Windows phải được build riêng trên đúng hệ điều hành. Bản Mac Intel và Apple Silicon cũng cần build bằng Python theo kiến trúc tương ứng. Workflow GitHub Actions đi kèm tạo bộ cài cho Windows và kiến trúc của runner macOS; bản Intel có thể build tại máy Intel.

## Thiết lập Telegram lần đầu

1. Vào [my.telegram.org/apps](https://my.telegram.org/apps), đăng nhập bằng số Telegram, chọn **API development tools** và tạo ứng dụng để lấy **API ID** và **API Hash**. Điền App title, Short name và chọn Desktop nếu được hỏi platform. Đây là thông tin của ứng dụng, không phải bot token.
2. Mở AutoClap, nhập API ID, API Hash và số điện thoại theo dạng quốc tế, ví dụ `+84901234567`. Bấm **Kết nối Telegram**.
3. Nhập mã đăng nhập Telegram gửi qua kênh được Telegram lựa chọn (thường trong ứng dụng Telegram). Nếu tài khoản có xác minh hai bước, nhập mật khẩu 2FA ở bước tiếp theo. Ứng dụng không lưu mã đăng nhập hoặc mật khẩu 2FA.
4. Chọn một hay nhiều nhóm/kênh cần theo dõi. Mặc định từ khóa là `care`, khoảng cách xử lý là 1,5 giây.
5. Bấm **Kiểm tra một tin nhắn** để thử bộ lọc ngay trên máy. Có thể bật **Chạy thử** để quan sát tin mới khớp điều kiện mà chưa gửi reaction.
6. Tắt Chạy thử và bấm **Bắt đầu** để tự thả 👏. Bấm **Dừng** để ngừng nhận tin và hủy hàng đợi. Muốn đổi cấu hình, dừng rồi bắt đầu lượt mới.

Lần mở sau, cấu hình và phiên đăng nhập vẫn còn; bấm Kết nối Telegram rồi Bắt đầu. Không cần mở Telegram Desktop. AutoClap cần tiếp tục mở và máy có mạng, không ngủ. Đóng cửa sổ sẽ dừng ứng dụng.

## Quy tắc xử lý

- Chỉ tin nhắn **đến**, trong các nhóm/kênh đã chọn, có thời điểm gửi từ lúc bấm Bắt đầu. Không quét tin cũ; tin gửi trong lúc app đóng, dừng hoặc máy ngủ không được xử lý bù. Không theo dõi chỉnh sửa tin nhắn.
- Số di động VN 10 chữ số bắt đầu bằng `03`, `05`, `07`, `08`, `09`; chấp nhận mã quốc gia `+84`, `84`, `0084` và dấu cách, chấm, gạch nối, ngoặc. Không xác minh số có thực sự được cấp phát. Không nhận số điện thoại nằm trong ảnh, tệp đính kèm, số bàn hoặc số nước khác.
- Từ khóa phải đứng riêng và không phân biệt hoa/thường: `CARE` khớp, `healthcare` không khớp. Có thể đổi thành một cụm từ. Cùng một tin phải có cả số điện thoại lẫn từ khóa; chú thích ảnh cũng được xét.
- Nhóm cần bật reaction 👏 và tài khoản cần có quyền sử dụng. Nếu tin đã có reaction do **chính bạn** chọn, ứng dụng giữ nguyên. Reaction của người khác không chặn việc thả 👏.
- Đọc lại nội dung trước khi thả; bỏ qua tin đã xóa hoặc sửa thành không khớp. Từng tin được xử lý nối tiếp, có khoảng cách tối thiểu đã chọn. Khi Telegram trả FloodWait, chờ đúng thời gian được yêu cầu rồi tự tiếp tục; Dừng hủy được thời gian chờ.
- Lưu xác nhận xử lý theo tài khoản + nhóm + ID tin để tránh gửi trùng sau khi khởi động lại. Chế độ thử không lưu xác nhận reaction thật. Không thể bảo đảm giao dịch exactly-once giữa mạng và ổ đĩa, nhưng việc đặt reaction qua API là idempotent và ứng dụng kiểm tra reaction hiện tại trước khi gửi lại.
- Thống kê là theo lượt chạy. Nhật ký giao diện giữ tối đa 300 dòng và không lưu nội dung tin nhắn hay số điện thoại của người gửi. Hàng đợi tối đa 1.000 tin khớp; khi đầy, tin mới sẽ được bỏ qua kèm dòng lỗi.

Ví dụ:

```text
0901234567 HD care gửi ảnh   → 👏
+84901234567 CARE 17prm      → 👏
0901234567 HD zalo          → bỏ qua
care gửi ảnh               → bỏ qua
0901234567 healthcare       → bỏ qua
```

## Chạy từ mã nguồn

Cần Python **3.11 trở lên**, khuyên dùng 3.12. Chỉ dùng Qt Core/Gui/Widgets qua PySide6-Essentials để giảm dung lượng phụ thuộc.

macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m autoclap
```

Cũng có thể mở `start.command`; script tự tạo môi trường và cài phụ thuộc ở lần đầu khi máy đã có Python phù hợp.

Windows (Command Prompt):

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m autoclap
```

Hoặc nhấp đúp `start.bat`. Lần cài đầu cần mạng để tải thư viện.

Nếu dùng [uv](https://docs.astral.sh/uv/), `uv sync --locked --extra build` cài đúng các phiên bản trong `uv.lock` rồi `uv run python -m autoclap`.

## Đóng gói và kiểm thử

Trong môi trường Python của ứng dụng, trên đúng hệ điều hành đích:

```bash
python -m pip install -e ".[build]"
python -m unittest discover -v
python scripts/build.py
```

File kết quả nằm trong `dist/`. Workflow `.github/workflows/build.yml` chạy kiểm thử và build trên Windows/macOS khi chạy thủ công, mở pull request hoặc đẩy tag `v*`. Chưa có bước ký ứng dụng hay xuất bản. Không cần cấu hình Telegram thật để chạy test; các cuộc gọi API trong test được mô phỏng.

## Dữ liệu trên máy

Bấm **Mở thư mục dữ liệu** ở góc dưới ứng dụng:

- macOS: `~/Library/Application Support/AutoClap/`
- Windows: `%LOCALAPPDATA%\AutoClap\`

`settings.json` chứa cấu hình, số đăng nhập và API ID/Hash. `telegram.session` chứa phiên đăng nhập Telethon; `history.sqlite` chỉ chứa ID tài khoản/nhóm/tin, trạng thái xử lý và thời điểm. Không mã hóa các file này; dùng quyền thư mục của người dùng hệ điều hành, và giới hạn quyền `0700`/`0600` trên macOS. Không chia sẻ file session hoặc thư mục dữ liệu. Bấm **Đăng xuất** để thu hồi và xóa phiên tại máy; cũng có thể thu hồi tại Telegram → Settings → Devices.

## Tài liệu nền tảng

- [Telethon đăng nhập](https://docs.telethon.dev/en/stable/basic/signing-in.html)
- [Telegram reaction API](https://core.telegram.org/api/reactions)
- [PyInstaller](https://pyinstaller.org/en/stable/)
