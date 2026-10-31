# AutoClap — Chrome extension

Chạy trên Chrome Windows và macOS. Dùng phiên **Telegram WebK** đã đăng nhập, không cần đăng ký API ID/Hash và không cần chạy ứng dụng Python.

## Cài đặt

1. Giải nén `AutoClap-Chrome.zip` vào một thư mục cố định.
2. Gõ `chrome://extensions` vào thanh địa chỉ Chrome.
3. Bật **Developer mode / Chế độ dành cho nhà phát triển** ở góc phải.
4. Bấm **Load unpacked / Tải tiện ích đã giải nén** và chọn thư mục `AutoClap-Chrome` chứa `manifest.json`. Không chọn file ZIP.
5. Mở **https://web.telegram.org/k/**. Nếu đã mở sẵn, tải lại trang sau khi cài extension.
6. Đăng nhập bằng QR qua Telegram trên điện thoại → Settings / Cài đặt → Devices / Thiết bị → Link Desktop Device / Liên kết thiết bị. Bạn cũng có thể dùng cách đăng nhập khác do Telegram Web cung cấp.
7. Mở nhóm/kênh muốn theo dõi. Bấm biểu tượng mảnh ghép trên thanh công cụ Chrome, ghim **AutoClap** rồi mở popup.
8. Giữ từ khóa `care`, có thể bật **Chạy thử**, rồi bấm **Bắt đầu**. Đóng popup không dừng theo dõi. Bấm **Dừng** khi cần.

Muốn tự thả thật, tắt Chạy thử trước khi bấm Bắt đầu. Ví dụ `0901234567 HD care gửi ảnh` khớp; `0901234567 zalo` không khớp. Nút Kiểm tra một tin nhắn chỉ chạy bộ lọc tại máy.

## Phạm vi hoạt động

- Mỗi tab theo dõi đúng **một nhóm/kênh đang mở**. Đổi nhóm, đổi tài khoản, đăng xuất, tải lại hoặc đóng tab sẽ dừng. Mở nhiều tab, mỗi tab một nhóm, rồi bấm Bắt đầu ở từng tab để theo dõi nhiều nhóm. Không theo dõi tin nhắn cá nhân.
- Dùng **WebK `/k/`**, chưa hỗ trợ WebA `/a/`. Chrome từ phiên bản 120 trở lên. Extension chỉ xin quyền chạy trên `web.telegram.org/k/*`, lưu cấu hình cục bộ và thao tác với tab bạn mở popup.
- Chỉ nhận sự kiện tin mới từ lúc Bắt đầu, không quét lịch sử hay chỉnh sửa tin cũ. Không đọc số điện thoại trong ảnh. Số di động VN có dạng `03/05/07/08/09` + 8 chữ số hoặc mã quốc gia `+84/84/0084`; hỗ trợ dấu cách, chấm, gạch nối và ngoặc. Từ khóa đứng riêng, không phân biệt hoa/thường.
- Đọc lại tin trước khi gửi; giữ nguyên reaction do chính bạn đã chọn. Nhóm cần cho phép 👏. Không cần 👏 là reaction mặc định của Telegram.
- Gửi nối tiếp và chờ khi Telegram báo FloodWait. Khóa chung giữa các tab cùng tài khoản và xác nhận đã gửi giúp tránh xử lý trùng. Dừng hủy được hàng đợi và thời gian chờ; một yêu cầu đã gửi lên máy chủ vẫn có thể hoàn tất sau khi bấm Dừng.
- Cần giữ Chrome và tab hoạt động, máy có mạng và không ngủ. Chrome có thể đóng băng hoặc loại bỏ tab nền để tiết kiệm bộ nhớ; lúc đó không bảo đảm nhận tin liên tục hay xử lý bù. Nếu cần, cấu hình Chrome Performance → Always keep these sites active cho `web.telegram.org`; việc này không bảo đảm chạy 24/7. Dùng bản desktop/API khi cần theo dõi ổn định liên tục.
- Bộ nối dùng các đối tượng đang có của ứng dụng WebK (`appImManager`, `rootScope`, các manager của phiên hiện tại), không lấy hoặc xuất khóa đăng nhập. Đây là giao diện nội bộ, có thể cần cập nhật extension khi Telegram đổi mã nguồn. Nếu báo chưa tương thích dù đã đăng nhập, tải lại trang; không có đường dự phòng dùng tài khoản khác hay API ID công khai.

## Dữ liệu lưu

Từ khóa, khoảng cách và tùy chọn chạy thử nằm trong `chrome.storage.local`. ID tài khoản/nhóm/tin đã xử lý (tối đa 5.000) và thời điểm gửi gần nhất nằm trong các khóa `autoclap:*` của localStorage trang Telegram. Không lưu nội dung tin nhắn, số điện thoại người gửi, mã OTP hoặc mật khẩu. Không gửi dữ liệu đến dịch vụ ngoài; các lệnh reaction đi qua phiên Telegram Web hiện tại đến Telegram. Nhật ký popup chỉ nằm trong bộ nhớ của tab.

Sau khi cập nhật extension, bấm Reload ở `chrome://extensions` và tải lại các tab Telegram WebK. Mọi lượt theo dõi cần bấm Bắt đầu lại.

## Kiểm thử mã nguồn

Ở thư mục gốc dự án, dùng Node.js 20 trở lên:

```bash
node --test extension-tests/*.test.cjs
```

Các test dùng Telegram giả lập; cần đăng nhập Telegram thật để kiểm tra gửi/nhận thực tế.

Tài liệu nền tảng: [nạp extension](https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world#load-unpacked), [content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts), [mã nguồn Telegram WebK](https://github.com/morethanwords/tweb).
