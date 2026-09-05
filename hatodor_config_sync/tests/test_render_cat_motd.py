import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image


MODULE_PATH = (
    Path(__file__).parents[1] / "managed" / "hatodor" / "render_cat_motd.py"
)
SPEC = importlib.util.spec_from_file_location("render_cat_motd", MODULE_PATH)
RENDERER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RENDERER)


class RenderCatMotdTests(unittest.TestCase):
    def test_loads_every_nonempty_tone(self):
        sayings_path = MODULE_PATH.with_name("cat_sayings.json")
        pools = RENDERER.load_sayings(sayings_path)
        self.assertEqual(
            set(pools), {"dry", "chaotic", "encouraging", "tiny_dictator"}
        )
        self.assertTrue(all(pools.values()))

    def test_daily_selection_is_stable_and_supports_mixed(self):
        pools = {"dry": ["One", "Two"], "chaotic": ["Three", "Four"]}
        first = RENDERER.select_saying(pools, "Mixed", "2026-09-05")
        second = RENDERER.select_saying(pools, "Mixed", "2026-09-05")
        self.assertEqual(first, second)
        self.assertIn(first, {"One", "Two", "Three", "Four"})

    def test_builds_fresh_cataas_says_url(self):
        url = RENDERER.build_cataas_says_url(
            "https://cataas.com/cat/cute?brightness=2",
            "The plant started it.",
            "revision-123",
        )
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.hostname, "cataas.com")
        self.assertEqual(
            unquote(parsed.path), "/cat/cute/says/The plant started it."
        )
        self.assertEqual(query["width"], ["800"])
        self.assertEqual(query["height"], ["480"])
        self.assertEqual(query["fit"], ["cover"])
        self.assertEqual(query["filter"], ["mono"])
        self.assertEqual(query["hatodor"], ["revision-123"])
        self.assertEqual(query["brightness"], ["2"])

    def test_rejects_non_cataas_urls(self):
        with self.assertRaisesRegex(ValueError, "cataas.com"):
            RENDERER.build_cataas_says_url(
                "https://example.com/cat.jpg", "Hello", "revision"
            )

    def test_crops_dithers_and_writes_png(self):
        source = Image.new("RGB", (1200, 400), "gray")
        payload = io.BytesIO()
        source.save(payload, format="JPEG")

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "motd.png"
            RENDERER.render_image(payload.getvalue(), destination)
            with Image.open(destination) as rendered:
                self.assertEqual(rendered.format, "PNG")
                self.assertEqual(rendered.size, (800, 480))
                self.assertEqual(rendered.mode, "1")


if __name__ == "__main__":
    unittest.main()
