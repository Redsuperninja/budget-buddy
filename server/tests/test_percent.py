"""Basis-point helpers: whole numbers only, halves rounded away from zero."""

import pytest

from app.percent import percent_bp, share_of


@pytest.mark.parametrize(
    ("cents", "bp", "expected"),
    [
        (400_000, 1_500, 60_000),  # 15% of $4,000
        (100, 1, 0),  # 0.01% of $1 is a hundredth of a cent
        (5_000, 1, 1),  # exactly half a cent rounds up
        (333_333, 3_333, 111_100),
        (0, 5_000, 0),
        (123_457, 10_000, 123_457),  # 100%
    ],
)
def test_share_of(cents, bp, expected):
    assert share_of(cents, bp) == expected


@pytest.mark.parametrize(
    ("part", "whole", "expected"),
    [
        (50_000, 100_000, 5_000),
        (1, 3, 3_333),
        (2, 3, 6_667),
        (-1, 3, -3_333),  # refunds bigger than spending
        (150_000, 100_000, 15_000),  # more than 100%
        (5, 0, None),
        (5, -10, None),
    ],
)
def test_percent_bp(part, whole, expected):
    assert percent_bp(part, whole) == expected
