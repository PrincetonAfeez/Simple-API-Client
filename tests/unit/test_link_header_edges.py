"""Tests for the link header edges."""

from __future__ import annotations

import unittest

from apiclient.pagination import parse_link_header


class LinkHeaderEdgeTests(unittest.TestCase):
    def test_multi_token_rel_exposes_each_relation(self) -> None:
        result = parse_link_header('<http://example.test/u>; rel="next prev"')
        self.assertEqual(result.get("next"), "http://example.test/u")
        self.assertEqual(result.get("prev"), "http://example.test/u")

    def test_comma_inside_angle_brackets_is_not_a_separator(self) -> None:
        link = '<http://example.test/x,y>; rel="next", <http://example.test/z>; rel="last"'
        result = parse_link_header(link)
        self.assertEqual(result.get("next"), "http://example.test/x,y")
        self.assertEqual(result.get("last"), "http://example.test/z")


if __name__ == "__main__":
    unittest.main()
