import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__).parents[1] / "managed" / "hatodor" / "fetch_zenquote.py"
)
SPEC = importlib.util.spec_from_file_location("fetch_zenquote", MODULE_PATH)
ZENQUOTE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ZENQUOTE)


class FetchZenquoteTests(unittest.TestCase):
    def test_parses_quote(self):
        payload = json.dumps([{"q": "Begin gently.", "a": "Someone"}]).encode()
        self.assertEqual(
            ZENQUOTE.parse_quote(payload), ("Begin gently.", "Someone")
        )

    def test_rejects_incomplete_quote(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            ZENQUOTE.parse_quote(json.dumps([{"q": "", "a": "Someone"}]).encode())

    def test_formats_greeting_quote_author_and_attribution(self):
        message = ZENQUOTE.format_message("Begin gently.", "Someone")
        self.assertIn("Good morning, Maggie!", message)
        self.assertIn('"Begin gently."', message)
        self.assertIn("- Someone", message)
        self.assertTrue(message.endswith("zenquotes.io"))
        self.assertLessEqual(len(message), 255)

    def test_truncates_long_quote_at_word_boundary(self):
        message = ZENQUOTE.format_message("patience " * 80, "Someone")
        self.assertLessEqual(len(message), 255)
        self.assertIn('..."\n- Someone', message)

    def test_reuses_same_day_cache_without_fetching(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            ZENQUOTE.write_cache("2026-09-05", "Cached quote", "Cached author", cache)
            with patch.object(ZENQUOTE, "fetch_quote") as fetch:
                result = ZENQUOTE.get_daily_quote("2026-09-05", cache)
            self.assertEqual(result, ("Cached quote", "Cached author"))
            fetch.assert_not_called()

    def test_uses_stale_cache_when_service_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            ZENQUOTE.write_cache("2026-09-04", "Cached quote", "Cached author", cache)
            with patch.object(ZENQUOTE, "fetch_quote", side_effect=OSError("offline")):
                result = ZENQUOTE.get_daily_quote("2026-09-05", cache)
            self.assertEqual(result, ("Cached quote", "Cached author"))


if __name__ == "__main__":
    unittest.main()
