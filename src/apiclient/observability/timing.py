"""Small timing helpers for protocol trace output."""

from __future__ import annotations


def ms(seconds: float) -> str:
    """Render a duration as a human-readable millisecond string."""

    return f"{seconds * 1000:.1f}ms"
