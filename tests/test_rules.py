import unittest

from autoclap.rules import Rule


class RuleTests(unittest.TestCase):
    def test_matching_mobile_formats_and_cases(self):
        for text in (
            "0982829666 TH care 18pro 256 bạc", "0973552006 CARE gửi ảnh",
            "0363704915 HD Care 17prm 256", "+84901234567 care",
            "84 901 234 567 care", "0084 901 234 567 care",
            "090 123 4567 care", "0901.234.567 care", "(090) 123-4567 care",
            "care: 0901234567", "0901234567\ncare", "0901234567 #care",
        ):
            with self.subTest(text=text):
                self.assertTrue(Rule().evaluate(text).matched)

    def test_rejects_missing_or_invalid_phone_and_substrings(self):
        for text in (
            "care gửi ảnh", "0901234567 zalo", "0901234567 healthcare",
            "0901234567 careless", "0901234567 skincare", "0901234567 care_foo",
            "090123456 care", "09012345678 care", "+849012345678 care",
            "0123456789 care", "1901234567 care", "abc0901234567 care",
            "0901234567xyz care", "0901234567 8 care", "09012\n34567 care", "",
        ):
            with self.subTest(text=text):
                self.assertFalse(Rule().evaluate(text).matched)

    def test_keyword_is_literal_and_supports_phrases(self):
        self.assertTrue(Rule("gửi ảnh").evaluate("0901234567 GỬI   ẢNH").matched)
        self.assertTrue(Rule("care+").evaluate("0901234567 care+").matched)
        self.assertFalse(Rule("care+").evaluate("0901234567 careee").matched)

    def test_empty_and_oversized_keywords_are_rejected(self):
        for keyword in ("", "   ", "x" * 101):
            with self.assertRaises(ValueError):
                Rule(keyword)
