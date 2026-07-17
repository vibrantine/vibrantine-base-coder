"""Tiny arithmetic fixture with one intentional localized defect."""


def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left - right
