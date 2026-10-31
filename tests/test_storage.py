import json
import os
from pathlib import Path
import tempfile
import unittest

from autoclap.storage import History, Settings, load_settings, save_settings


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_config_round_trip_with_private_permissions(self):
        settings = Settings("123", "a" * 32, "+84901234567", "care", [-10], 2.0, True)
        save_settings(self.path, settings)
        self.assertEqual(load_settings(self.path), settings)
        if os.name != "nt":
            self.assertEqual((self.path / "settings.json").stat().st_mode & 0o777, 0o600)

    def test_missing_and_corrupt_config_fall_back(self):
        self.assertEqual(load_settings(self.path), Settings())
        for text in ("{broken", "[]", "null"):
            (self.path / "settings.json").write_text(text)
            self.assertEqual(load_settings(self.path), Settings())

    def test_config_types_are_validated(self):
        (self.path / "settings.json").write_text(json.dumps({
            "api_id": 123, "chat_ids": [True, -123, "x"], "interval": "nan", "dry_run": "true",
        }))
        actual = load_settings(self.path)
        self.assertEqual(actual.api_id, "")
        self.assertEqual(actual.chat_ids, [-123])
        self.assertEqual(actual.interval, 1.5)
        self.assertFalse(actual.dry_run)

    def test_receipts_are_persistent_and_account_scoped(self):
        database = self.path / "history.sqlite"
        history = History(database)
        history.record(1, -10, 5, "sent")
        history.record(1, -10, 5, "existing")
        self.assertTrue(history.contains(1, -10, 5))
        self.assertFalse(history.contains(2, -10, 5))
        self.assertFalse(history.contains(1, -11, 5))
        history.close()
        history = History(database)
        self.assertTrue(history.contains(1, -10, 5))
        history.close()
