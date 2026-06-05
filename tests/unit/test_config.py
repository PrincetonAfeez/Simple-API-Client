"""Tests for the config."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apiclient.config import (
    get_config_value,
    list_profiles,
    load_config,
    set_config_value,
    unset_config_value,
)
from apiclient.exceptions import ConfigError


class ConfigTests(unittest.TestCase):
    def test_default_profile_is_auto_applied(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text(
                "[profiles.default]\nbase_url = \"http://default-host\"\n",
                encoding="utf-8",
            )
            config = load_config(None, path=path)
            self.assertEqual(config.base_url, "http://default-host")

    def test_profile_overrides_default(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text(
                (
                    "[profiles.default]\nbase_url = \"http://default-host\"\n\n"
                    "[profiles.dev]\nbase_url = \"http://dev-host\"\n"
                ),
                encoding="utf-8",
            )
            config = load_config("dev", path=path)
            self.assertEqual(config.base_url, "http://dev-host")

    def test_env_var_overrides_config_file(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text(
                "[profiles.default]\nretries = 1\n",
                encoding="utf-8",
            )
            os.environ["APICLIENT_RETRIES"] = "5"
            try:
                config = load_config(None, path=path)
            finally:
                del os.environ["APICLIENT_RETRIES"]
            self.assertEqual(config.retries, 5)

    def test_set_config_value_preserves_unrelated_tables(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text(
                (
                    "[telemetry]\nendpoint = \"https://metrics.example\"\n\n"
                    "[profiles.dev]\nbase_url = \"http://dev\"\n"
                ),
                encoding="utf-8",
            )
            set_config_value("dev.retries", "3", path=path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("[telemetry]", text)
            self.assertIn("endpoint", text)
            self.assertIn("retries = 3", text)

    def test_set_value_round_trips_string_with_backslashes(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            set_config_value("dev.base_url", r"C:\Users\demo", path=path)
            self.assertEqual(
                get_config_value("dev.base_url", path=path),
                r"C:\Users\demo",
            )

    def test_unset_removes_setting_and_empty_profile(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            set_config_value("dev.base_url", "http://dev", path=path)
            unset_config_value("dev.base_url", path=path)
            self.assertIsNone(get_config_value("dev.base_url", path=path))
            self.assertNotIn("dev", list_profiles(path=path))

    def test_invalid_key_raises_config_error(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            with self.assertRaises(ConfigError):
                set_config_value("nodot", "value", path=path)


if __name__ == "__main__":
    unittest.main()
