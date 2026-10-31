"""Per-user configuration and account-scoped reaction receipts."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from platformdirs import user_data_path


def data_directory() -> Path:
    path = user_data_path("AutoClap", appauthor=False, roaming=False)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        path.chmod(0o700)
    return path


@dataclass
class Settings:
    api_id: str = ""
    api_hash: str = ""
    phone: str = ""
    keyword: str = "care"
    chat_ids: list[int] = field(default_factory=list)
    interval: float = 1.5
    dry_run: bool = False


def load_settings(directory: Path) -> Settings:
    try:
        raw = json.loads((directory / "settings.json").read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return Settings()
        settings = Settings()
        for key in ("api_id", "api_hash", "phone", "keyword"):
            if isinstance(raw.get(key), str):
                setattr(settings, key, raw[key])
        if isinstance(raw.get("chat_ids"), list):
            settings.chat_ids = [x for x in raw["chat_ids"] if type(x) is int]
        interval = raw.get("interval")
        if isinstance(interval, (int, float)) and 0.5 <= interval <= 60:
            settings.interval = float(interval)
        if isinstance(raw.get("dry_run"), bool):
            settings.dry_run = raw["dry_run"]
        return settings
    except (OSError, ValueError, TypeError):
        return Settings()


def save_settings(directory: Path, settings: Settings) -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, filename = tempfile.mkstemp(prefix=".settings-", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(filename, directory / "settings.json")
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


class History:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS reactions ("
            "account_id INTEGER, chat_id INTEGER, message_id INTEGER, "
            "status TEXT NOT NULL, created_at TEXT NOT NULL, "
            "PRIMARY KEY(account_id, chat_id, message_id))"
        )
        self.connection.commit()
        if os.name != "nt":
            path.chmod(0o600)

    def contains(self, account_id: int, chat_id: int, message_id: int) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM reactions WHERE account_id=? AND chat_id=? AND message_id=?",
            (account_id, chat_id, message_id),
        ).fetchone() is not None

    def record(self, account_id: int, chat_id: int, message_id: int, status: str) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO reactions VALUES (?, ?, ?, ?, ?)",
            (account_id, chat_id, message_id, status, datetime.now(timezone.utc).isoformat()),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
