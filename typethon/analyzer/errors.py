from __future__ import annotations

import enum


class ErrorCategory(enum.Enum):
    SYNTAX_ERROR = enum.auto()
    TYPE_ERROR = enum.auto
