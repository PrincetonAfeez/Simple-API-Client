"""Package entry points and public exports."""

from __future__ import annotations

import runpy
import unittest
from unittest.mock import patch

import apiclient


class PackageEntryTests(unittest.TestCase):
    def test_public_exports_are_importable(self) -> None:
        self.assertTrue(hasattr(apiclient, "ApiClient"))
        self.assertTrue(hasattr(apiclient, "BearerTokenAuth"))

    def test_main_module_exits_with_code(self) -> None:
        with patch("apiclient.cli.main.main", return_value=0):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_module("apiclient.__main__", run_name="__main__")
            self.assertEqual(ctx.exception.code, 0)

if __name__ == "__main__":
    unittest.main()
