"""Vietnamese Qt desktop interface."""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDoubleSpinBox, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .rules import Rule
from .storage import Settings, load_settings, save_settings
from .telegram_worker import TelegramWorker


STYLE = """
QWidget { color: #223d3a; font-size: 13px; }
QMainWindow, QDialog { background: #f4f7f5; }
QLabel { background: transparent; }
QLabel#eyebrow { color: #6a837b; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#title { color: #163e34; font-size: 30px; font-weight: 700; }
QLabel#muted { color: #75877f; font-size: 12px; }
QLabel#section { color: #214b40; font-weight: 700; font-size: 15px; }
QLabel#badge { background: #e6ece8; color: #65786f; border-radius: 13px; padding: 7px 12px; font-weight: 600; }
QLabel#brand { background: #13765c; color: white; border-radius: 14px; font-size: 23px; font-weight: 700; }
QFrame#card { background: white; border: 1px solid #e1e9e3; border-radius: 14px; }
QFrame#stat { background: #edf3ee; border: none; border-radius: 10px; }
QLabel#statNumber { color: #176348; font-size: 25px; font-weight: 700; }
QLineEdit, QTextEdit, QDoubleSpinBox { background: #f8faf8; border: 1px solid #dce6de; border-radius: 7px; padding: 8px 10px; selection-background-color: #b1e3cc; }
QLineEdit:focus, QTextEdit:focus, QDoubleSpinBox:focus { border: 1px solid #25896a; background: white; }
QLineEdit:disabled { color: #7a8b82; background: #f1f5f1; }
QPushButton { background: #eef4ef; border: 1px solid #dce7de; border-radius: 7px; padding: 9px 13px; font-weight: 600; }
QPushButton:hover { background: #e2eee4; border-color: #bfd4c6; }
QPushButton:pressed { background: #cfdfd2; }
QPushButton:disabled { color: #a0ada5; background: #f3f6f3; border-color: #e9eeea; }
QPushButton#primary { background: #147859; border: 1px solid #147859; color: white; }
QPushButton#primary:hover { background: #0d6349; }
QPushButton#primary:disabled { background: #abc5b6; border-color: #abc5b6; color: #f4f8f5; }
QPushButton#link { border: none; background: transparent; color: #218164; padding: 3px 0; text-align: left; }
QPushButton#stop { color: #a3503f; background: #fbf3ef; border-color: #eddad1; }
QPushButton#stop:disabled { color: #c3b3aa; background: #f8f5f3; border-color: #eee8e3; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QListWidget, QTreeWidget { background: white; border: none; outline: none; }
QListWidget::item { padding: 9px 8px; border-radius: 6px; margin: 1px 0; }
QListWidget::item:hover { background: #f1f6f0; }
QListWidget::item:selected { background: #e5f1e7; color: #204c3b; }
QTreeWidget::item { padding: 8px 3px; border-bottom: 1px solid #f0f4f0; }
QTreeWidget::item:selected { background: #ebf3ec; color: #223d3a; }
QHeaderView::section { background: #f6f8f5; color: #7b8b80; border: none; padding: 8px 5px; font-size: 11px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 7px; background: transparent; }
QScrollBar::handle:vertical { background: #d8e1d9; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: transparent; }
QToolTip { background: #173e32; color: white; border: none; padding: 5px; }
"""


def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if role:
        widget.setObjectName(role)
    return widget


def card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 17, 18, 17)
    layout.setSpacing(11)
    layout.addWidget(label(title, "section"))
    if subtitle:
        layout.addWidget(label(subtitle, "muted", True))
    return frame, layout


def app_icon() -> QIcon:
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#147859"))
    painter.drawRoundedRect(0, 0, 128, 128, 29, 29)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Arial", 45, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "ac")
    painter.end()
    return QIcon(pixmap)


class PreviewDialog(QDialog):
    def __init__(self, keyword: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kiểm tra bộ lọc")
        self.resize(500, 350)
        self.rule = Rule(keyword)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(label("Thử một tin nhắn", "section"))
        layout.addWidget(label(f'Tìm số di động Việt Nam và từ "{keyword}" trong cùng một tin.', "muted", True))
        self.text = QTextEdit()
        self.text.setAcceptRichText(False)
        self.text.setPlainText("0901234567 HD care gửi ảnh")
        self.text.setPlaceholderText("Dán nội dung tin nhắn để kiểm tra…")
        layout.addWidget(self.text)
        self.result = label("", wrap=True)
        self.result.setMinimumHeight(48)
        layout.addWidget(self.result)
        layout.addWidget(label("Kiểm tra tại máy · không gửi gì lên Telegram", "muted"))
        close = QPushButton("Đóng")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.text.textChanged.connect(self.update_result)
        self.update_result()

    def update_result(self) -> None:
        result = self.rule.evaluate(self.text.toPlainText())
        self.result.setText(("✓  " if result.matched else "○  ") + result.reason)
        self.result.setStyleSheet("color: #147859;" if result.matched else "color: #9b7240;")


class MainWindow(QMainWindow):
    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        self.settings = load_settings(directory)
        self.worker = TelegramWorker(directory)
        self.phase, self.busy, self.running = "disconnected", False, False
        self.worker_ready, self.closing, self.can_close = False, False, False
        self.network_online = False
        self.selected_ids = set(self.settings.chat_ids)
        self.setWindowTitle("AutoClap · Telegram")
        self.setWindowIcon(app_icon())
        self.resize(1160, 850)
        self.setMinimumSize(960, 700)
        self._build()
        self.worker.ready.connect(self._ready)
        self.worker.state_changed.connect(self._state)
        self.worker.dialogs_loaded.connect(self._dialogs)
        self.worker.activity.connect(self._activity)
        self.worker.stats_changed.connect(self._stats)
        self.worker.running_changed.connect(self._running)
        self.worker.connection_changed.connect(self._connection)
        self.worker.error.connect(self._error)
        self.worker.command_finished.connect(self._finished)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()
        self._refresh_controls()

    def _build(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 24, 26, 18)
        outer.setSpacing(18)
        header = QHBoxLayout()
        header.setSpacing(14)
        brand = label("ac", "brand")
        brand.setFixedSize(56, 56)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(brand)
        headings = QVBoxLayout()
        headings.setSpacing(1)
        headings.addWidget(label("TELEGRAM ASSISTANT", "eyebrow"))
        headings.addWidget(label("AutoClap", "title"))
        header.addLayout(headings)
        header.addStretch()
        self.badge = label("●  Chưa kết nối", "badge")
        header.addWidget(self.badge)
        outer.addLayout(header)
        outer.addWidget(label("Một tràng vỗ tay, đúng tin nhắn.", "muted"))

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        outer.addWidget(split, 1)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(325)
        left = QWidget()
        left_scroll.setWidget(left)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 5, 0)
        left_layout.setSpacing(14)
        split.addWidget(left_scroll)

        auth_card, auth = card("01   Kết nối Telegram", "Dùng tài khoản cá nhân của bạn.")
        self.api_id = QLineEdit(self.settings.api_id)
        self.api_id.setPlaceholderText("API ID")
        self.api_id.setMaxLength(12)
        self.api_hash = QLineEdit(self.settings.api_hash)
        self.api_hash.setPlaceholderText("API Hash")
        self.api_hash.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_hash.setMaxLength(32)
        self.phone = QLineEdit(self.settings.phone)
        self.phone.setPlaceholderText("Số điện thoại · +84901234567")
        self.phone.setMaxLength(25)
        credentials = QGridLayout()
        credentials.setHorizontalSpacing(10)
        credentials.setVerticalSpacing(8)
        credentials.addWidget(label("API ID", "muted"), 0, 0)
        credentials.addWidget(label("API Hash", "muted"), 0, 1)
        credentials.addWidget(self.api_id, 1, 0)
        credentials.addWidget(self.api_hash, 1, 1)
        credentials.setColumnStretch(0, 1)
        credentials.setColumnStretch(1, 2)
        self.api_id.setMinimumWidth(65)
        self.api_hash.setMinimumWidth(110)
        auth.addLayout(credentials)
        auth.addWidget(label("Số điện thoại", "muted"))
        auth.addWidget(self.phone)
        self.api_help = QPushButton("Lấy API ID & Hash tại my.telegram.org ↗")
        self.api_help.setObjectName("link")
        self.api_help.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://my.telegram.org/apps")))
        auth.addWidget(self.api_help)
        self.auth_note = label("Phiên đăng nhập được lưu riêng trên máy này.", "muted", True)
        auth.addWidget(self.auth_note)
        self.connect_button = QPushButton("Kết nối Telegram")
        self.connect_button.clicked.connect(self._connect)
        self.connect_button.setObjectName("primary")
        auth.addWidget(self.connect_button)
        self.verify_area = QWidget()
        verify = QVBoxLayout(self.verify_area)
        verify.setContentsMargins(0, 0, 0, 0)
        verify.setSpacing(9)
        self.verify_hint = label("", "muted", True)
        verify.addWidget(self.verify_hint)
        self.secret = QLineEdit()
        self.secret.setMaxLength(256)
        self.secret.returnPressed.connect(self._verify)
        verify.addWidget(self.secret)
        self.verify_button = QPushButton("Xác nhận")
        self.verify_button.clicked.connect(self._verify)
        verify.addWidget(self.verify_button)
        self.verify_area.hide()
        auth.addWidget(self.verify_area)
        self.logout_button = QPushButton("Đăng xuất")
        self.logout_button.setObjectName("link")
        self.logout_button.clicked.connect(lambda: self._command("logout"))
        auth.addWidget(self.logout_button)
        left_layout.addWidget(auth_card)

        self.rule_card, rule = card("03   Điều kiện thả 👏", "Tin nhắn phải có đủ cả hai điều kiện.")
        rule.addWidget(label("✓  Số di động Việt Nam (0… / +84…)", wrap=True))
        rule.addWidget(label("✓  Từ khóa đứng riêng, không phân biệt hoa/thường", "muted", True))
        self.keyword = QLineEdit(self.settings.keyword)
        self.keyword.setPlaceholderText("care")
        self.keyword.setMaxLength(100)
        rule.addWidget(self.keyword)
        interval_row = QHBoxLayout()
        interval_row.addWidget(label("Khoảng cách xử lý", "muted"))
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.5, 60)
        self.interval.setSingleStep(0.5)
        self.interval.setDecimals(1)
        self.interval.setSuffix(" giây")
        self.interval.setValue(self.settings.interval)
        self.interval.setFixedWidth(114)
        interval_row.addWidget(self.interval)
        rule.addLayout(interval_row)
        self.dry_run = QCheckBox("Chạy thử · chỉ ghi nhận, chưa thả icon")
        self.dry_run.setChecked(self.settings.dry_run)
        rule.addWidget(self.dry_run)
        self.preview_button = QPushButton("Kiểm tra một tin nhắn")
        self.preview_button.clicked.connect(self._preview)
        rule.addWidget(self.preview_button)
        left_layout.addWidget(self.rule_card)
        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(14)
        split.addWidget(right)
        split.setSizes([340, 750])
        group_card, groups = card("02   Chọn nhóm theo dõi")
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm tên nhóm hoặc kênh…")
        self.search.textChanged.connect(self._filter_groups)
        toolbar.addWidget(self.search, 1)
        self.reload_button = QPushButton("Tải lại")
        self.reload_button.clicked.connect(lambda: self._command("dialogs"))
        toolbar.addWidget(self.reload_button)
        groups.addLayout(toolbar)
        self.group_list = QListWidget()
        self.group_list.setMinimumHeight(110)
        self.group_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.group_list.itemChanged.connect(self._selection_changed)
        groups.addWidget(self.group_list, 1)
        self.empty_groups = label("Đăng nhập Telegram để xem danh sách nhóm và kênh.", "muted", True)
        self.empty_groups.setAlignment(Qt.AlignmentFlag.AlignCenter)
        groups.addWidget(self.empty_groups)
        group_footer = QHBoxLayout()
        self.group_count = label("Chưa chọn nhóm", "muted")
        group_footer.addWidget(self.group_count)
        group_footer.addStretch()
        self.clear_groups = QPushButton("Bỏ chọn tất cả")
        self.clear_groups.setObjectName("link")
        self.clear_groups.clicked.connect(self._clear_groups)
        group_footer.addWidget(self.clear_groups)
        groups.addLayout(group_footer)
        right_layout.addWidget(group_card, 4)

        self.stat_values = {}
        stat_row = QHBoxLayout()
        stat_row.setSpacing(10)
        for key, caption in (("matched", "Khớp bộ lọc"), ("sent", "Đã thả 👏"), ("preview", "Chạy thử"), ("failed", "Lỗi")):
            frame = QFrame()
            frame.setObjectName("stat")
            column = QVBoxLayout(frame)
            column.setContentsMargins(14, 11, 14, 11)
            column.setSpacing(3)
            value = label("0", "statNumber")
            self.stat_values[key] = value
            column.addWidget(value)
            column.addWidget(label(caption, "muted"))
            stat_row.addWidget(frame, 1)
        right_layout.addLayout(stat_row)

        activity_card, activity = card("Hoạt động gần đây")
        self.log = QTreeWidget()
        self.log.setHeaderLabels(["THỜI GIAN", "HOẠT ĐỘNG", "NHÓM / TIN"])
        self.log.setRootIsDecorated(False)
        self.log.setIndentation(0)
        self.log.setWordWrap(True)
        self.log.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.log.setMinimumHeight(105)
        self.log.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.log.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.log.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.log.setColumnWidth(2, 150)
        activity.addWidget(self.log, 1)
        self.queue_note = label("Chờ bắt đầu · chỉ thống kê trong lượt chạy hiện tại", "muted", True)
        activity.addWidget(self.queue_note)
        right_layout.addWidget(activity_card, 4)

        actions = QHBoxLayout()
        self.run_note = label("Chọn nhóm rồi bấm Bắt đầu.", "muted", True)
        actions.addWidget(self.run_note, 1)
        self.stop_button = QPushButton("Dừng")
        self.stop_button.setObjectName("stop")
        self.stop_button.setMinimumWidth(95)
        self.stop_button.clicked.connect(lambda: self._command("stop"))
        actions.addWidget(self.stop_button)
        self.start_button = QPushButton("▶  Bắt đầu")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumWidth(145)
        self.start_button.clicked.connect(self._start)
        actions.addWidget(self.start_button)
        right_layout.addLayout(actions)
        footer = QHBoxLayout()
        footer.addWidget(label("●  Chỉ tin mới từ lúc Bắt đầu · giữ nguyên reaction bạn đã thả", "muted"))
        footer.addStretch()
        data_button = QPushButton("Mở thư mục dữ liệu ↗")
        data_button.setObjectName("link")
        data_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.directory))))
        footer.addWidget(data_button)
        outer.addLayout(footer)

    def _ready(self) -> None:
        self.worker_ready = True
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        idle = self.worker_ready and not self.busy and not self.closing
        authorized = self.phase == "connected"
        for field in (self.api_id, self.api_hash, self.phone):
            field.setEnabled(idle and not authorized)
        self.connect_button.setEnabled(idle and not authorized)
        self.connect_button.setText("Đã kết nối" if authorized else "Kết nối lại / gửi mã mới" if self.phase in {"code", "password"} else "Kết nối Telegram")
        self.verify_button.setEnabled(idle)
        self.secret.setEnabled(idle)
        has_session = (self.directory / "telegram.session").exists()
        self.logout_button.setVisible(authorized or has_session)
        self.logout_button.setText("Đăng xuất" if authorized else "Xóa phiên đăng nhập")
        self.logout_button.setEnabled(idle)
        for widget in (self.group_list, self.search, self.reload_button, self.clear_groups):
            widget.setEnabled(idle and authorized and not self.running)
        for widget in (self.keyword, self.interval, self.dry_run):
            widget.setEnabled(idle and not self.running)
        self.start_button.setEnabled(idle and authorized and not self.running and bool(self._checked_ids()))
        self.stop_button.setEnabled(idle and self.running)
        self._update_badge()

    def _update_badge(self) -> None:
        if self.closing:
            text, color, background = "●  Đang đóng…", "#6a786d", "#e8eee7"
        elif self.running and not self.network_online:
            text, color, background = "●  Đang nối lại mạng…", "#a17126", "#faf0d9"
        elif self.running:
            text = "●  Đang chạy thử" if self.dry_run.isChecked() else "●  Đang theo dõi"
            color, background = "#167452", "#ddf0df"
        elif self.phase == "connected":
            text, color, background = "●  Đã kết nối" if self.network_online else "●  Đang nối lại mạng…", "#167452", "#e5f0e5"
        else:
            text = {"connecting": "●  Đang kết nối…", "code": "●  Chờ mã đăng nhập", "password": "●  Chờ mật khẩu 2FA"}.get(self.phase, "●  Chưa kết nối")
            color, background = "#65786f", "#e6ece8"
        self.badge.setText(text)
        self.badge.setStyleSheet(f"color: {color}; background: {background};")

    def _command(self, action: str, **arguments) -> None:
        if self.busy or not self.worker_ready or self.closing:
            return
        self.busy = True
        self._refresh_controls()
        self.worker.submit(action, **arguments)

    def _save(self) -> None:
        self.settings = Settings(
            self.api_id.text().strip(), self.api_hash.text().strip(), self.phone.text().strip(),
            self.keyword.text().strip(), sorted(self.selected_ids), self.interval.value(), self.dry_run.isChecked(),
        )
        save_settings(self.directory, self.settings)

    def _connect(self) -> None:
        try:
            self._save()
        except OSError:
            self._error("Không lưu được cấu hình vào thư mục dữ liệu.")
            return
        self.secret.clear()
        self._command("connect", api_id=self.api_id.text().strip(), api_hash=self.api_hash.text().strip(),
                      phone=self.phone.text().strip())

    def _verify(self) -> None:
        action = "password" if self.phase == "password" else "code"
        value = self.secret.text() if action == "password" else self.secret.text().strip().replace(" ", "")
        self._command(action, **{action: value})
        if action == "password":
            self.secret.clear()

    def _state(self, state: dict) -> None:
        self.phase = state["phase"]
        self.verify_area.setVisible(self.phase in {"code", "password"})
        if self.phase in {"code", "password"}:
            self.secret.clear()
            password = self.phase == "password"
            self.secret.setEchoMode(QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal)
            self.secret.setPlaceholderText("Mật khẩu xác minh hai bước" if password else "Mã đăng nhập Telegram")
            self.verify_hint.setText("Nhập mật khẩu xác minh hai bước của tài khoản." if password else "Xem mã Telegram gửi trong ứng dụng Telegram hoặc kênh nhận mã của tài khoản.")
        if self.phase == "connected":
            self.secret.clear()
            self.network_online = True
            self.auth_note.setText(f"✓  {state['name']} · đã đăng nhập")
            self.run_note.setText("Chọn nhóm rồi bấm Bắt đầu.")
        elif self.phase == "disconnected":
            self.network_online = False
            self.auth_note.setText("Phiên đăng nhập được lưu riêng trên máy này.")
        self._refresh_controls()

    def _dialogs(self, dialogs: list) -> None:
        self.group_list.blockSignals(True)
        self.group_list.clear()
        available = {item["id"] for item in dialogs}
        self.selected_ids.intersection_update(available)
        for entry in dialogs:
            item = QListWidgetItem(f"{entry['name']}   ·   {entry['kind']}")
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            item.setToolTip(f"{entry['name']}\nID: {entry['id']}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if entry["id"] in self.selected_ids else Qt.CheckState.Unchecked)
            self.group_list.addItem(item)
        self.group_list.blockSignals(False)
        self.empty_groups.setVisible(not dialogs)
        self.empty_groups.setText("Tài khoản chưa có nhóm/kênh nào." if self.phase == "connected" else "Đăng nhập Telegram để xem danh sách nhóm và kênh.")
        self.group_list.setVisible(bool(dialogs))
        self._filter_groups(self.search.text())
        self._selection_changed()

    def _checked_ids(self) -> list[int]:
        return [self.group_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.group_list.count())
                if self.group_list.item(i).checkState() == Qt.CheckState.Checked]

    def _selection_changed(self, _item=None) -> None:
        self.selected_ids = set(self._checked_ids())
        self.group_count.setText(f"Đã chọn {len(self.selected_ids)} / {self.group_list.count()} nhóm, kênh")
        self._refresh_controls()

    def _filter_groups(self, text: str) -> None:
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())

    def _clear_groups(self) -> None:
        for i in range(self.group_list.count()):
            self.group_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _start(self) -> None:
        try:
            Rule(self.keyword.text())
            self._save()
        except (ValueError, OSError) as error:
            self._error(str(error))
            return
        self._command("start", chat_ids=self._checked_ids(), keyword=self.keyword.text().strip(),
                      interval=self.interval.value(), dry_run=self.dry_run.isChecked())

    def _preview(self) -> None:
        try:
            PreviewDialog(self.keyword.text().strip(), self).exec()
        except ValueError as error:
            self._error(str(error))

    def _running(self, running: bool) -> None:
        self.running = running
        self.run_note.setText("Đang chạy thử · chưa gửi reaction." if running and self.dry_run.isChecked()
                              else "Đang lắng nghe tin nhắn mới…" if running else "Đã dừng. Bạn có thể đổi cấu hình.")
        self._refresh_controls()

    def _connection(self, connected: bool) -> None:
        self.network_online = connected
        self._update_badge()

    def _stats(self, stats: dict) -> None:
        for key, value in self.stat_values.items():
            value.setText(str(stats.get(key, 0)))
        self.queue_note.setText(f"Hàng đợi: {stats.get('queued', 0)} tin  ·  Bỏ qua: {stats.get('skipped', 0)}  ·  Lượt chạy hiện tại")

    def _activity(self, event: dict) -> None:
        prefix = {"success": "✓", "error": "!", "waiting": "◷", "preview": "◇"}.get(event["level"], "·")
        where = event.get("chat", "")
        if event.get("message_id") is not None:
            where += f"  #{event['message_id']}"
        row = QTreeWidgetItem([datetime.now().strftime("%H:%M:%S"), f"{prefix}  {event['message']}", where])
        row.setToolTip(1, event["message"])
        row.setToolTip(2, where)
        color = {"success": "#168158", "error": "#b55746", "waiting": "#a17531", "preview": "#4b7f98"}.get(event["level"], "#6e8074")
        row.setForeground(1, QColor(color))
        self.log.insertTopLevelItem(0, row)
        while self.log.topLevelItemCount() > 300:
            self.log.takeTopLevelItem(self.log.topLevelItemCount() - 1)

    def _error(self, message: str) -> None:
        self._activity(dict(level="error", message=message, chat="", message_id=None))
        if not self.closing:
            QMessageBox.warning(self, "AutoClap", message)

    def _finished(self, action: str) -> None:
        self.busy = False
        self._refresh_controls()
        if action in {"connect", "code"} and self.phase in {"code", "password"}:
            self.secret.setFocus()

    def closeEvent(self, event) -> None:
        if self.can_close:
            event.accept()
            return
        event.ignore()
        if self.closing:
            return
        try:
            self._save()
        except OSError:
            pass
        self.closing = True
        self._refresh_controls()
        if self.worker_ready:
            self.worker.submit("shutdown")
        else:
            self.worker.ready.connect(lambda: self.worker.submit("shutdown"))

    def _worker_finished(self) -> None:
        self.can_close = True
        QTimer.singleShot(0, self.close)
