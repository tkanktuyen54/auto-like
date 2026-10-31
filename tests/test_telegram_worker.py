from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from telethon import errors, functions, types

from autoclap.engine import Candidate, RateLimited, UserFacingError
from autoclap.rules import Rule
from autoclap.telegram_worker import TelegramWorker


class TelegramWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.worker = TelegramWorker(Path(self.temporary.name))
        self.worker.engine = SimpleNamespace(rule=Rule())
        self.worker.client = AsyncMock()
        self.item = Candidate(-10, 123, "0901234567 care", datetime.now(timezone.utc), peer=types.InputPeerChat(10))
        self.message = SimpleNamespace(raw_text=self.item.text, reactions=None)
        self.worker.client.get_messages.return_value = self.message

    async def asyncTearDown(self):
        self.temporary.cleanup()

    async def test_sends_clap_using_actual_telethon_request(self):
        self.assertEqual(await self.worker._send_reaction(self.item), "sent")
        request = self.worker.client.await_args.args[0]
        self.assertIsInstance(request, functions.messages.SendReactionRequest)
        self.assertEqual(request.msg_id, 123)
        self.assertEqual(request.reaction[0].emoticon, "👏")

    async def test_chosen_order_zero_is_an_existing_reaction(self):
        self.message.reactions = SimpleNamespace(results=[SimpleNamespace(chosen_order=0)])
        self.assertEqual(await self.worker._send_reaction(self.item), "existing")
        self.worker.client.assert_not_awaited()

    async def test_other_peoples_reactions_do_not_block_clap(self):
        self.message.reactions = SimpleNamespace(results=[SimpleNamespace(chosen_order=None)])
        self.assertEqual(await self.worker._send_reaction(self.item), "sent")

    async def test_content_is_checked_again_before_mutation(self):
        self.message.raw_text = "0901234567 zalo"
        self.assertEqual(await self.worker._send_reaction(self.item), "changed")
        self.worker.client.assert_not_awaited()

    async def test_deleted_message_does_not_send(self):
        for message in (None, types.MessageEmpty(id=123, peer_id=types.PeerChat(10))):
            self.worker.client.get_messages.return_value = message
            self.assertEqual(await self.worker._send_reaction(self.item), "missing")
        self.worker.client.assert_not_awaited()

    async def test_flood_wait_is_returned_to_cancellable_queue(self):
        self.worker.client.side_effect = errors.FloodWaitError(request=None, capture=42)
        with self.assertRaises(RateLimited) as result:
            await self.worker._send_reaction(self.item)
        self.assertEqual(result.exception.seconds, 42)

    async def test_reaction_permission_failure_is_human_readable(self):
        self.worker.client.side_effect = errors.ReactionInvalidError(request=None)
        with self.assertRaisesRegex(UserFacingError, "không cho phép"):
            await self.worker._send_reaction(self.item)

    async def test_credentials_are_validated_before_connecting(self):
        with patch("autoclap.telegram_worker.TelegramClient") as client:
            for values in (("x", "a" * 32, "+84901234567"),
                           ("123", "bad", "+84901234567"),
                           ("123", "a" * 32, "0901234567")):
                with self.assertRaises(ValueError):
                    await self.worker._connect(*values)
            client.assert_not_called()

    async def test_invalid_code_does_not_call_telegram(self):
        self.worker.phone_code_hash = "test"
        with self.assertRaises(ValueError):
            await self.worker._verify_code("invalid")
        self.worker.client.sign_in.assert_not_awaited()

    async def test_two_factor_auth_transitions_to_password_stage(self):
        self.worker.phone_code_hash = "test"
        self.worker.client.sign_in.side_effect = errors.SessionPasswordNeededError(request=None)
        await self.worker._verify_code("12345")
        self.assertEqual(self.worker.phase, "password")
