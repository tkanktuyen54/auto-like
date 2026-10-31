import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from autoclap.engine import Candidate, RateLimited, ReactionEngine, RunConfig, UserFacingError
from autoclap.storage import History


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.history = History(Path(self.temporary.name) / "history.sqlite")
        self.config = RunConfig(1, {-10: "Nhóm A"})
        self.item = Candidate(-10, 123, "0901234567 care gửi ảnh", datetime.now(timezone.utc))
        self.logs, self.stats, self.engines = [], [], []

    async def asyncTearDown(self):
        for engine in self.engines:
            await engine.stop()
        self.history.close()
        self.temporary.cleanup()

    def engine(self, sender=None, config=None, **kwargs):
        instance = ReactionEngine(config or self.config, self.history, sender or AsyncMock(return_value="sent"),
                                  self.logs.append, self.stats.append, **kwargs)
        instance.start()
        self.engines.append(instance)
        return instance

    async def drain(self, engine):
        await asyncio.wait_for(engine.queue.join(), timeout=1)

    async def test_only_new_incoming_matching_messages_in_selected_chats(self):
        sender = AsyncMock(return_value="sent")
        engine = self.engine(sender)
        for item in (
            replace(self.item, outgoing=True), replace(self.item, chat_id=-20),
            replace(self.item, text="0901234567 zalo"),
            replace(self.item, date=self.config.started_at - timedelta(seconds=1)),
        ):
            self.assertFalse(engine.submit(item))
        self.assertTrue(engine.submit(self.item))
        await self.drain(engine)
        sender.assert_awaited_once_with(self.item)
        self.assertEqual(engine.counts["sent"], 1)

    async def test_duplicates_pending_and_persisted_are_ignored(self):
        engine = self.engine()
        self.assertTrue(engine.submit(self.item))
        self.assertFalse(engine.submit(self.item))
        await self.drain(engine)
        self.assertFalse(engine.submit(self.item))
        another = self.engine()
        self.assertFalse(another.submit(self.item))

    async def test_message_in_start_second_is_not_lost(self):
        engine = self.engine()
        self.assertTrue(engine.submit(replace(self.item, date=self.config.started_at)))
        await self.drain(engine)
        self.assertEqual(engine.counts["sent"], 1)

    async def test_preview_never_sends_and_does_not_block_later_live_run(self):
        sender = AsyncMock(return_value="sent")
        preview = self.engine(sender, replace(self.config, dry_run=True))
        preview.submit(self.item)
        await self.drain(preview)
        sender.assert_not_awaited()
        self.assertFalse(self.history.contains(1, -10, 123))
        self.assertFalse(preview.submit(self.item))
        live = self.engine(sender)
        self.assertTrue(live.submit(self.item))
        await self.drain(live)
        sender.assert_awaited_once()

    async def test_flood_wait_retries_same_message_after_server_delay(self):
        sender = AsyncMock(side_effect=[RateLimited(20), "sent"])
        sleep = AsyncMock()
        engine = self.engine(sender, sleeper=sleep, monotonic=lambda: 100)
        engine.submit(self.item)
        await self.drain(engine)
        self.assertEqual(sender.await_count, 2)
        self.assertEqual(sleep.await_args_list[0].args[0], 21)
        self.assertTrue(self.history.contains(1, -10, 123))

    async def test_stop_cancels_server_wait_and_discards_pending_messages(self):
        waiting = asyncio.Event()
        async def sleep(_seconds):
            waiting.set()
            await asyncio.Event().wait()
        sender = AsyncMock(side_effect=RateLimited(3600))
        engine = self.engine(sender, sleeper=sleep)
        engine.submit(self.item)
        engine.submit(replace(self.item, message_id=124))
        await asyncio.wait_for(waiting.wait(), 1)
        await asyncio.wait_for(engine.stop(), 1)
        self.assertEqual(sender.await_count, 1)
        self.assertFalse(engine.submit(replace(self.item, message_id=125)))
        self.assertFalse(engine.pending)
        self.assertTrue(engine.queue.empty())
        self.assertFalse(self.history.contains(1, -10, 123))

    async def test_interval_is_global_across_groups(self):
        sender = AsyncMock(return_value="sent")
        sleep = AsyncMock()
        engine = self.engine(sender, replace(self.config, chats={-10: "A", -20: "B"}),
                             sleeper=sleep, monotonic=lambda: 100)
        engine.submit(self.item)
        engine.submit(replace(self.item, chat_id=-20, message_id=124))
        await self.drain(engine)
        self.assertEqual(sender.await_count, 2)
        sleep.assert_awaited_once_with(1.5)

    async def test_errors_leave_no_success_receipt_and_allow_retry(self):
        sender = AsyncMock(side_effect=[UserFacingError("Nhóm chưa bật 👏"), "sent"])
        engine = self.engine(sender, sleeper=AsyncMock())
        engine.submit(self.item)
        await self.drain(engine)
        self.assertFalse(self.history.contains(1, -10, 123))
        self.assertEqual(engine.counts["failed"], 1)
        self.assertTrue(engine.submit(self.item))
        await self.drain(engine)
        self.assertTrue(self.history.contains(1, -10, 123))

    async def test_network_failures_retry_at_most_three_times(self):
        sender = AsyncMock(side_effect=OSError("network"))
        sleep = AsyncMock()
        engine = self.engine(sender, sleeper=sleep)
        engine.submit(self.item)
        await self.drain(engine)
        self.assertEqual(sender.await_count, 3)
        self.assertEqual(engine.counts["failed"], 1)
        self.assertFalse(self.history.contains(1, -10, 123))

    async def test_existing_reaction_is_recorded_as_skipped(self):
        engine = self.engine(AsyncMock(return_value="existing"))
        engine.submit(self.item)
        await self.drain(engine)
        self.assertEqual(engine.counts["skipped"], 1)
        self.assertEqual(engine.counts["sent"], 0)
        self.assertTrue(self.history.contains(1, -10, 123))

    async def test_edited_and_deleted_messages_are_not_marked_successful(self):
        for status in ("changed", "missing"):
            engine = self.engine(AsyncMock(return_value=status))
            engine.submit(self.item)
            await self.drain(engine)
            self.assertFalse(self.history.contains(1, -10, 123))
            self.assertEqual(engine.counts["skipped"], 1)

    async def test_history_does_not_leak_between_accounts(self):
        self.history.record(2, -10, 123, "sent")
        engine = self.engine()
        self.assertTrue(engine.submit(self.item))
        await self.drain(engine)
        self.assertEqual(engine.counts["sent"], 1)

    async def test_queue_capacity_is_bounded(self):
        engine = self.engine()
        for message_id in range(1000):
            self.assertTrue(engine.submit(replace(self.item, message_id=message_id)))
        self.assertFalse(engine.submit(replace(self.item, message_id=1001)))
        self.assertEqual(engine.counts["failed"], 1)


class RunConfigTests(unittest.TestCase):
    def test_requires_explicit_chats_and_valid_interval(self):
        for args in ({"chats": {}}, {"chats": {-10: "A"}, "interval": 0},
                     {"chats": {-10: "A"}, "keyword": " "}):
            with self.assertRaises(ValueError):
                RunConfig(account_id=1, **args)
