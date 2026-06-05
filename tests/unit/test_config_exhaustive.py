"""Additional config module tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock
from tempfile import TemporaryDirectory

from apiclient.config import load_config, parse_status_csv
from apiclient.exceptions import ConfigError


class ConfigExhaustiveTests(unittest.TestCase):
    def test_load_config_oserror(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text("[profiles.default]\n", encoding="utf-8")
            with mock.patch.object(
                Path, "read_text", side_effect=OSError("permission denied")
            ):
                with self.assertRaises(ConfigError):
                    load_config(path=path)

    def test_load_config_invalid_toml(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.toml"
            path.write_text("not = [valid", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path=path)

    def test_unknown_profile_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text("[profiles.default]\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config("missing", path=path)

    def test_parse_status_csv_empty_returns_none(self) -> None:
        self.assertIsNone(parse_status_csv(None))
        self.assertIsNone(parse_status_csv("  "))

    def test_parse_status_csv_invalid_code(self) -> None:
        with self.assertRaises(ConfigError):
            parse_status_csv("200,not-a-code")

    def test_parse_status_csv_skips_empty_parts(self) -> None:
        codes = parse_status_csv("500, ,502")
        self.assertEqual(codes, frozenset({500, 502}))

    def test_read_data_oserror_via_get(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text("[profiles.dev]\nretries = 1\n", encoding="utf-8")
            from apiclient.config import get_config_value

            with mock.patch.object(Path, "read_text", side_effect=OSError("denied")):
                with self.assertRaises(ConfigError):
                    get_config_value("dev.retries", path=path)

    def test_split_key_invalid(self) -> None:
        from apiclient.config import set_config_value

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            with self.assertRaises(ConfigError):
                set_config_value("nodot", "x", path=path)


if __name__ == "__main__":
    unittest.main()
