"""Message filtering, independent of Telegram and the desktop UI."""

from dataclasses import dataclass
import re
import unicodedata


# Vietnamese mobile numbers: 0xxxxxxxxx, +84xxxxxxxxx, 84xxxxxxxxx or 0084xxxxxxxxx.
# Spaces, dots, parentheses and hyphens are accepted; newlines cannot join digits.
_SEP = r"[ .()\-]*"
_PHONE = re.compile(
    rf"(?<![\w+])(?:0{_SEP}[35789]|(?:\+?84|0084){_SEP}[35789])"
    rf"(?:{_SEP}[0-9]){{8}}(?!\w)(?!{_SEP}[0-9])"
)


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    reason: str
    phones: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rule:
    keyword: str = "care"

    def __post_init__(self) -> None:
        if not self.keyword.strip():
            raise ValueError("Hãy nhập từ khóa cần tìm.")
        if len(self.keyword) > 100:
            raise ValueError("Từ khóa tối đa 100 ký tự.")

    def evaluate(self, text: str) -> MatchResult:
        normalized = unicodedata.normalize("NFC", text or "")
        words = re.split(r"\s+", unicodedata.normalize("NFC", self.keyword.strip()))
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in words) + r"(?!\w)"
        if not re.search(pattern, normalized, re.IGNORECASE):
            return MatchResult(False, f'Không có từ khóa "{self.keyword.strip()}" đứng riêng.')
        phones = tuple(match.group() for match in _PHONE.finditer(normalized))
        if not phones:
            return MatchResult(False, "Chưa tìm thấy số di động Việt Nam hợp lệ (0… hoặc +84…).")
        return MatchResult(True, "Có số điện thoại và từ khóa: tin nhắn này sẽ được thả 👏.", phones)
