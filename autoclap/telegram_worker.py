"""All Telegram networking and SQLite receipts live on a dedicated asyncio thread."""

import asyncio
import re
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from telethon import TelegramClient, errors, events, functions, types

from .engine import Candidate, RateLimited, ReactionEngine, RunConfig, UserFacingError
from .storage import History


def friendly_error(error: Exception) -> str:
    names = {
        "ApiIdInvalidError": "API ID hoặc API Hash không đúng. Kiểm tra tại my.telegram.org.",
        "PhoneNumberInvalidError": "Số điện thoại không hợp lệ. Hãy dùng dạng +84…",
        "PhoneNumberBannedError": "Telegram không cho phép đăng nhập số điện thoại này.",
        "PhoneCodeInvalidError": "Mã đăng nhập chưa đúng. Hãy nhập lại.",
        "PhoneCodeExpiredError": "Mã đăng nhập đã hết hạn. Hãy kết nối lại để lấy mã mới.",
        "PasswordHashInvalidError": "Mật khẩu xác minh hai bước chưa đúng.",
        "SessionRevokedError": "Phiên Telegram đã bị thu hồi. Hãy đăng nhập lại.",
        "AuthKeyUnregisteredError": "Phiên Telegram đã hết hiệu lực. Hãy đăng nhập lại.",
        "AuthKeyDuplicatedError": "Phiên Telegram được dùng ở nơi khác. Hãy đăng xuất rồi đăng nhập lại.",
        "ReactionInvalidError": "Nhóm không cho phép reaction 👏 hoặc đã đạt giới hạn reaction.",
        "ChatWriteForbiddenError": "Tài khoản không có quyền thả reaction trong nhóm này.",
        "ChatAdminRequiredError": "Telegram yêu cầu quyền quản trị cho thao tác này.",
        "ChannelPrivateError": "Tài khoản không còn quyền truy cập nhóm/kênh này.",
        "UserBannedInChannelError": "Tài khoản đã bị hạn chế trong nhóm này.",
        "ReactionsTooManyError": "Tin nhắn đã đạt giới hạn số loại reaction.",
    }
    if isinstance(error, errors.FloodWaitError):
        return f"Telegram yêu cầu chờ {error.seconds} giây. Hãy thử lại sau thời gian này."
    if isinstance(error, (ValueError, UserFacingError)):
        return str(error)
    if isinstance(error, (OSError, asyncio.TimeoutError)):
        return "Không kết nối được Telegram. Kiểm tra mạng rồi thử lại."
    return names.get(type(error).__name__, f"Telegram trả về lỗi {type(error).__name__}.")


class TelegramWorker(QThread):
    ready = Signal()
    state_changed = Signal(object)
    dialogs_loaded = Signal(object)
    activity = Signal(object)
    stats_changed = Signal(object)
    running_changed = Signal(bool)
    connection_changed = Signal(bool)
    error = Signal(str)
    command_finished = Signal(str)

    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        self.loop: asyncio.AbstractEventLoop | None = None
        self.client: TelegramClient | None = None
        self.engine: ReactionEngine | None = None
        self.history: History | None = None
        self.user_id: int | None = None
        self.phone = ""
        self.phone_code_hash: str | None = None
        self.dialogs: dict[int, object] = {}
        self.dialog_names: dict[int, str] = {}
        self.connected_state = False
        self.closing = False
        self.phase = "disconnected"
        self.commands: set[asyncio.Task] = set()

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.command_lock = asyncio.Lock()
        try:
            self.history = History(self.directory / "history.sqlite")
        except Exception:
            self.error.emit("Không mở được dữ liệu ứng dụng. Kiểm tra quyền ghi thư mục dữ liệu.")
            self.loop.close()
            return
        self.health_task = self.loop.create_task(self._health())
        self.loop.call_soon(self.ready.emit)
        try:
            self.loop.run_forever()
        finally:
            tasks = asyncio.all_tasks(self.loop)
            for task in tasks:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.history.close()
            self.loop.close()

    def submit(self, action: str, **arguments) -> None:
        if not self.loop or not self.loop.is_running() or self.closing:
            return
        coroutine = self._request_shutdown() if action == "shutdown" else self._execute(action, arguments)
        asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def _state(self, phase: str, **details) -> None:
        self.phase = phase
        self.state_changed.emit(dict(phase=phase, **details))

    async def _execute(self, action: str, arguments: dict) -> None:
        task = asyncio.current_task()
        self.commands.add(task)
        try:
            async with self.command_lock:
                if self.closing:
                    return
                try:
                    commands = {
                        "connect": self._connect,
                        "code": self._verify_code,
                        "password": self._verify_password,
                        "dialogs": self._load_dialogs,
                        "start": self._start,
                        "stop": self._stop,
                        "logout": self._logout,
                    }
                    await commands[action](**arguments)
                except Exception as error:
                    if action == "connect":
                        if self.client:
                            await self.client.disconnect()
                        self._state("disconnected")
                    self.error.emit(friendly_error(error))
                finally:
                    self.command_finished.emit(action)
        finally:
            self.commands.discard(task)

    async def _connect(self, api_id: str, api_hash: str, phone: str) -> None:
        if not api_id.isdigit() or int(api_id) <= 0:
            raise ValueError("API ID phải là một số nguyên dương.")
        if not re.fullmatch(r"[a-fA-F0-9]{32}", api_hash):
            raise ValueError("API Hash phải gồm đúng 32 ký tự, lấy từ my.telegram.org.")
        cleaned_phone = re.sub(r"[\s().-]", "", phone)
        if not re.fullmatch(r"\+[1-9][0-9]{6,14}", cleaned_phone):
            raise ValueError("Nhập số đăng nhập theo dạng quốc tế, ví dụ +84901234567.")
        await self._stop()
        if self.client:
            await self.client.disconnect()
        self.user_id = None
        self.dialogs.clear()
        self.dialog_names.clear()
        self._state("connecting")
        self.phone, self.phone_code_hash = cleaned_phone, None
        self.client = TelegramClient(
            str(self.directory / "telegram"), int(api_id), api_hash,
            device_model="AutoClap Desktop", app_version="1.0.0",
            lang_code="vi", system_lang_code="vi", flood_sleep_threshold=0,
            timeout=15, request_retries=2, connection_retries=5,
            auto_reconnect=True, catch_up=False,
        )
        self.client.add_event_handler(self._on_message, events.NewMessage(incoming=True))
        async with asyncio.timeout(45):
            await self.client.connect()
            if await self.client.is_user_authorized():
                await self._authorized()
            else:
                sent = await self.client.send_code_request(self.phone)
                self.phone_code_hash = sent.phone_code_hash
                self._state("code")

    async def _verify_code(self, code: str) -> None:
        if not self.client or not self.phone_code_hash:
            raise ValueError("Hãy kết nối để nhận mã đăng nhập trước.")
        if not re.fullmatch(r"[0-9]{4,8}", code):
            raise ValueError("Nhập mã đăng nhập do Telegram gửi cho bạn.")
        try:
            async with asyncio.timeout(45):
                await self.client.sign_in(self.phone, code, phone_code_hash=self.phone_code_hash)
        except errors.SessionPasswordNeededError:
            self._state("password")
            return
        await self._authorized()

    async def _verify_password(self, password: str) -> None:
        if not self.client or self.phase != "password":
            raise ValueError("Hãy xác nhận mã đăng nhập trước.")
        if not password:
            raise ValueError("Hãy nhập mật khẩu xác minh hai bước của Telegram.")
        async with asyncio.timeout(45):
            await self.client.sign_in(password=password)
        await self._authorized()

    async def _authorized(self) -> None:
        me = await self.client.get_me()
        if me is None or getattr(me, "bot", False):
            raise ValueError("Hãy đăng nhập bằng tài khoản Telegram cá nhân.")
        self.user_id = me.id
        self.phone_code_hash = None
        name = " ".join(x for x in (me.first_name, me.last_name) if x) or "Tài khoản Telegram"
        self._state("connected", name=name, username=me.username or "", account_id=me.id)
        self.activity.emit(dict(level="info", message=f"Đã kết nối tài khoản {name}.", chat="", message_id=None))
        await self._load_dialogs()

    async def _load_dialogs(self) -> None:
        if not self.client or not self.user_id:
            raise ValueError("Hãy đăng nhập Telegram trước.")
        dialogs, peers, names = [], {}, {}
        async with asyncio.timeout(120):
            async for dialog in self.client.iter_dialogs():
                if not (dialog.is_group or dialog.is_channel):
                    continue
                peers[dialog.id], names[dialog.id] = dialog.input_entity, dialog.name or "Không có tên"
                dialogs.append(dict(id=dialog.id, name=names[dialog.id],
                                    kind="Nhóm" if dialog.is_group else "Kênh"))
        self.dialogs, self.dialog_names = peers, names
        self.dialogs_loaded.emit(sorted(dialogs, key=lambda item: item["name"].casefold()))

    async def _start(self, chat_ids: list[int], keyword: str, interval: float, dry_run: bool) -> None:
        async with asyncio.timeout(30):
            if not self.client or not self.user_id or not await self.client.is_user_authorized():
                raise ValueError("Hãy đăng nhập Telegram trước khi bắt đầu.")
        if any(chat_id not in self.dialogs for chat_id in chat_ids):
            raise ValueError("Danh sách nhóm đã thay đổi. Hãy tải lại và chọn nhóm.")
        config = RunConfig(self.user_id, {key: self.dialog_names[key] for key in chat_ids},
                           keyword.strip(), interval, dry_run)
        await self._stop()
        self.engine = ReactionEngine(config, self.history, self._send_reaction,
                                     self.activity.emit, self.stats_changed.emit)
        self.engine.start()
        self.running_changed.emit(True)
        mode = "Chạy thử" if dry_run else "Tự thả 👏"
        self.activity.emit(dict(level="info", message=f"{mode} · theo dõi {len(chat_ids)} nhóm/kênh, chỉ tin mới.",
                                chat="", message_id=None))

    async def _on_message(self, event) -> None:
        if not self.engine:
            return
        try:
            self.engine.submit(Candidate(event.chat_id, event.id, event.raw_text or "",
                                         event.date, bool(event.out), self.dialogs.get(event.chat_id)))
        except Exception as error:
            self.error.emit(f"Không đưa được tin nhắn vào hàng đợi: {type(error).__name__}.")

    async def _send_reaction(self, item: Candidate) -> str:
        try:
            async with asyncio.timeout(40):
                message = await self.client.get_messages(item.peer, ids=item.message_id)
                if not message or isinstance(message, types.MessageEmpty):
                    return "missing"
                if not self.engine.rule.evaluate(message.raw_text or "").matched:
                    return "changed"
                reactions = getattr(message, "reactions", None)
                if reactions and any(getattr(reaction, "chosen_order", None) is not None
                                     for reaction in reactions.results):
                    return "existing"
                await self.client(functions.messages.SendReactionRequest(
                    peer=item.peer, msg_id=item.message_id,
                    reaction=[types.ReactionEmoji(emoticon="👏")],
                ))
                return "sent"
        except errors.FloodWaitError as error:
            raise RateLimited(error.seconds) from error
        except errors.RPCError as error:
            raise UserFacingError(friendly_error(error)) from error

    async def _stop(self) -> None:
        if self.engine:
            await self.engine.stop()
            self.engine = None
            self.activity.emit(dict(level="info", message="Đã dừng theo dõi; hàng đợi đã được hủy.",
                                    chat="", message_id=None))
        self.running_changed.emit(False)

    async def _logout(self) -> None:
        await self._stop()
        if self.client:
            async with asyncio.timeout(40):
                if not await self.client.is_user_authorized():
                    await self.client.disconnect()
                    self.client.session.delete()
                else:
                    await self.client.log_out()
            self.client = None
        self.user_id = None
        self.dialogs.clear()
        self.dialog_names.clear()
        self.dialogs_loaded.emit([])
        self._state("disconnected")
        self.activity.emit(dict(level="info", message="Đã đăng xuất và xóa phiên Telegram trên máy.",
                                chat="", message_id=None))

    async def _health(self) -> None:
        while True:
            connected = bool(self.client and self.user_id and self.client.is_connected())
            if connected != self.connected_state:
                self.connected_state = connected
                self.connection_changed.emit(connected)
            await asyncio.sleep(2)

    async def _shutdown(self) -> None:
        self.closing = True
        await self._stop()
        try:
            if self.client:
                await asyncio.wait_for(self.client.disconnect(), timeout=10)
        finally:
            self.loop.call_soon(self.loop.stop)

    async def _request_shutdown(self) -> None:
        # Closing must interrupt a stalled login/dialog request, not wait behind it.
        self.closing = True
        for task in list(self.commands):
            task.cancel()
        await asyncio.gather(*list(self.commands), return_exceptions=True)
        await self._shutdown()
