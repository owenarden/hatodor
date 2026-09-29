import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clarifier import notify


class TokenTests(unittest.TestCase):
    def test_reads_s6_container_environment(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "SUPERVISOR_TOKEN").write_text("abc\n")
            with mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(notify, "S6_ENV", Path(d)):
                self.assertEqual(notify.supervisor_token(), "abc")

    def test_process_environment_wins(self):
        with mock.patch.dict(os.environ, {"SUPERVISOR_TOKEN": "env"}):
            self.assertEqual(notify.supervisor_token(), "env")

    def test_missing_everywhere(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(notify, "S6_ENV", Path("/nonexistent")):
            self.assertIsNone(notify.supervisor_token())


if __name__ == "__main__":
    unittest.main()
