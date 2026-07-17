"""Evaluator-owned regression tests for the localized defect fixture."""

import unittest

from calculator import add


class AddTests(unittest.TestCase):
    def test_adds_positive_integers(self) -> None:
        self.assertEqual(add(7, 5), 12)

    def test_adds_a_negative_integer(self) -> None:
        self.assertEqual(add(-3, 8), 5)


if __name__ == "__main__":
    unittest.main()
