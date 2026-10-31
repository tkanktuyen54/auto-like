import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from autoclap.storage import Settings, load_settings, save_settings
from autoclap.ui import MainWindow, PreviewDialog, STYLE


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        save_settings(self.directory, Settings(chat_ids=[-10]))
        self.window = MainWindow(self.directory)
        self.window.show()
        self.wait_for(lambda: self.window.worker_ready)

    def tearDown(self):
        self.window.close()
        self.wait_for(lambda: self.window.can_close)
        self.app.processEvents()
        self.window.deleteLater()
        self.app.processEvents()
        self.temporary.cleanup()

    def wait_for(self, condition):
        deadline = time.monotonic() + 5
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(condition(), "Qt/worker event did not finish")

    def authorize_ui(self):
        self.window._state(dict(phase="connected", name="Test", account_id=1))
        self.window._dialogs([
            dict(id=-10, name="Nhóm A", kind="Nhóm"),
            dict(id=-20, name="Nhóm B", kind="Nhóm"),
        ])

    def test_initial_controls_require_authentication(self):
        self.assertTrue(self.window.connect_button.isEnabled())
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.stop_button.isEnabled())
        self.assertEqual(self.window.api_hash.echoMode(), self.window.api_hash.EchoMode.Password)

    def test_chat_selection_is_restored_and_search_preserves_it(self):
        self.authorize_ui()
        self.assertEqual(self.window._checked_ids(), [-10])
        self.assertTrue(self.window.start_button.isEnabled())
        self.window.search.setText("Nhóm B")
        self.assertTrue(self.window.group_list.item(0).isHidden())
        self.assertEqual(self.window._checked_ids(), [-10])

    def test_running_locks_config_and_exposes_stop(self):
        self.authorize_ui()
        self.window._running(True)
        self.assertFalse(self.window.keyword.isEnabled())
        self.assertFalse(self.window.group_list.isEnabled())
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertTrue(self.window.stop_button.isEnabled())
        self.window._running(False)

    def test_authentication_stages_and_secrets(self):
        self.window._state(dict(phase="code"))
        self.assertFalse(self.window.verify_area.isHidden())
        self.window.secret.setText("12345")
        self.window._state(dict(phase="password"))
        self.assertEqual(self.window.secret.text(), "")
        self.assertEqual(self.window.secret.echoMode(), self.window.secret.EchoMode.Password)

    def test_selected_groups_are_saved_on_close(self):
        self.authorize_ui()
        self.window.group_list.item(1).setCheckState(Qt.CheckState.Checked)
        self.window._save()
        self.assertEqual(load_settings(self.directory).chat_ids, [-20, -10])

    def test_preview_uses_same_filter_without_telegram(self):
        dialog = PreviewDialog("care", self.window)
        self.assertIn("✓", dialog.result.text())
        dialog.text.setPlainText("0901234567 zalo")
        self.assertIn("○", dialog.result.text())
        dialog.close()
