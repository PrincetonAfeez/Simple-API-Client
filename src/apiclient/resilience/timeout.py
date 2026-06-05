"""Timeout policy objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeoutConfig:
    connect: float = 5.0
    read: float = 10.0
    total: float | None = None

    @classmethod
    def from_single_value(cls, value: float | None) -> "TimeoutConfig":
        if value is None:
            return cls()
        return cls(connect=value, read=value, total=value)
