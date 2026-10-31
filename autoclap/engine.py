"""A cancellable serial queue; dry runs never create live reaction receipts."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Awaitable, Callable

from .rules import Rule
from .storage import History


class RateLimited(Exception):
    def __init__(self, seconds: int):
        self.seconds = max(1, seconds)
        super().__init__(f"Wait {self.seconds} seconds")


@dataclass(frozen=True)
class Candidate:
    chat_id: int
    message_id: int
    text: str
    date: datetime
    outgoing: bool = False
    peer: object = None


@dataclass(frozen=True)
class RunConfig:
    account_id: int
    chats: dict[int, str]
    keyword: str = "care"
    interval: float = 1.5
    dry_run: bool = False
    # Telegram timestamps have one-second precision. Do not discard a new message
    # merely because it arrives during the same second as the Start click.
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0))

    def __post_init__(self) -> None:
        Rule(self.keyword)
        if not self.chats:
            raise ValueError("Hãy chọn ít nhất một nhóm.")
        if not 0.5 <= self.interval <= 60:
            raise ValueError("Khoảng cách xử lý phải từ 0,5 đến 60 giây.")


class ReactionEngine:
    def __init__(
        self,
        config: RunConfig,
        history: History,
        sender: Callable[[Candidate], Awaitable[str]],
        emit: Callable[[dict], None],
        stats: Callable[[dict], None],
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.config, self.history, self.sender = config, history, sender
        self.emit, self.on_stats = emit, stats
        self.sleep, self.monotonic = sleeper, monotonic
        self.rule = Rule(config.keyword)
        self.queue: asyncio.Queue[Candidate] = asyncio.Queue(maxsize=1000)
        self.pending: set[tuple[int, int]] = set()
        self.previewed: set[tuple[int, int]] = set()
        self.counts = dict(matched=0, sent=0, skipped=0, failed=0, preview=0, queued=0)
        self.task: asyncio.Task | None = None
        self.active = False
        self.last_attempt: float | None = None

    def start(self) -> None:
        self.active = True
        self.task = asyncio.create_task(self._consume())
        self.on_stats(dict(self.counts))

    def _stats(self) -> None:
        self.counts["queued"] = len(self.pending)
        self.on_stats(dict(self.counts))

    def _log(self, level: str, message: str, item: Candidate) -> None:
        self.emit(dict(level=level, message=message, chat=self.config.chats[item.chat_id],
                       message_id=item.message_id))

    def submit(self, item: Candidate) -> bool:
        if (not self.active or item.outgoing or item.chat_id not in self.config.chats
                or item.date < self.config.started_at):
            return False
        if not self.rule.evaluate(item.text).matched:
            return False
        key = (item.chat_id, item.message_id)
        if key in self.pending or key in self.previewed:
            return False
        if not self.config.dry_run and self.history.contains(self.config.account_id, *key):
            return False
        if self.queue.full():
            self.counts["failed"] += 1
            self._log("error", "Hàng đợi đầy; tin này chưa được xử lý.", item)
            self._stats()
            return False
        self.pending.add(key)
        self.counts["matched"] += 1
        self.queue.put_nowait(item)
        self._stats()
        return True

    async def _consume(self) -> None:
        while True:
            item = await self.queue.get()
            key = (item.chat_id, item.message_id)
            try:
                if self.config.dry_run:
                    self.previewed.add(key)
                    self.counts["preview"] += 1
                    self._log("preview", "Khớp bộ lọc · chế độ thử, chưa gửi 👏.", item)
                    continue
                failures = 0
                while self.active:
                    try:
                        if self.last_attempt is not None:
                            delay = self.config.interval - (self.monotonic() - self.last_attempt)
                            if delay > 0:
                                await self.sleep(delay)
                        self.last_attempt = self.monotonic()
                        status = await self.sender(item)
                        if status not in {"sent", "existing", "changed", "missing"}:
                            raise ValueError("Trạng thái xử lý không hợp lệ.")
                        if status in {"sent", "existing"}:
                            self.history.record(self.config.account_id, *key, status)
                        if status == "sent":
                            self.counts["sent"] += 1
                            self._log("success", "Đã thả 👏", item)
                        else:
                            self.counts["skipped"] += 1
                            descriptions = {
                                "existing": "Bạn đã có reaction; giữ nguyên lựa chọn hiện tại.",
                                "changed": "Nội dung đã đổi và không còn khớp bộ lọc.",
                                "missing": "Tin nhắn đã bị xóa hoặc không còn truy cập được.",
                            }
                            self._log("info", descriptions[status], item)
                        break
                    except RateLimited as error:
                        self._log("waiting", f"Telegram yêu cầu chờ {error.seconds} giây; sẽ tự tiếp tục.", item)
                        await self.sleep(error.seconds + 1)
                    except (OSError, asyncio.TimeoutError):
                        failures += 1
                        if failures >= 3:
                            raise
                        self._log("waiting", "Mất kết nối; đang thử lại…", item)
                        await self.sleep(2 ** failures)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.counts["failed"] += 1
                # The worker translates RPC errors to safe, useful Vietnamese messages.
                detail = str(error) if isinstance(error, UserFacingError) else type(error).__name__
                self._log("error", f"Chưa gửi được reaction: {detail}", item)
            finally:
                self.pending.discard(key)
                self.queue.task_done()
                self._stats()

    async def stop(self) -> None:
        self.active = False
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        while not self.queue.empty():
            self.queue.get_nowait()
            self.queue.task_done()
        self.pending.clear()
        self._stats()


class UserFacingError(Exception):
    """Text intended for the UI; never include credentials or message bodies."""
