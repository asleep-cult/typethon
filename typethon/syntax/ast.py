from __future__ import annotations

import enum

import attr


class BoolOperatorKind(enum.IntEnum):
    AND = enum.auto()
    OR = enum.auto()


class OperatorKind(enum.IntEnum):
    ADD = enum.auto()
    SUB = enum.auto()
    MULT = enum.auto()
    MATMULT = enum.auto()
    DIV = enum.auto()
    MOD = enum.auto()
    POW = enum.auto()
    LSHIFT = enum.auto()
    RSHIFT = enum.auto()
    BITOR = enum.auto()
    BITXOR = enum.auto()
    BITAND = enum.auto()
    FLOORDIV = enum.auto()


class UnaryOperatorKind(enum.IntEnum):
    INVERT = enum.auto()
    NOT = enum.auto()
    UADD = enum.auto()
    USUB = enum.auto()


class CmpOperatorKind(enum.IntEnum):
    EQ = enum.auto()
    NOTEQ = enum.auto()
    LT = enum.auto()
    LTE = enum.auto()
    GT = enum.auto()
    GTE = enum.auto()
    IS = enum.auto()
    ISNOT = enum.auto()
    IN = enum.auto()
    NOTIN = enum.auto()


class StringFlags(enum.IntFlag):
    NONE = 0
    RAW = enum.auto()
    BYTES = enum.auto()
    FORMAT = enum.auto()


@attr.s(kw_only=True, slots=True)
class Node:
    start: int = attr.ib()
    end: int = attr.ib()
