from __future__ import annotations

import attr
import enum
from collections.abc import Sequence  # Covariant
from . import typeinfo


class PrimitiveType(enum.Enum):
    INFERRED = enum.auto()
    INT = enum.auto()
    BOOL = enum.auto()
    STRING = enum.auto()


@attr.s(kw_only=True, slots=True)
class Adt:
    info: typeinfo.AdtInfo = attr.ib()
    structural: bool = attr.ib()
    args: Sequence[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Function:
    info: typeinfo.FunctionInfo = attr.ib()
    args: Sequence[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Parameter:
    name: str = attr.ib()
    index: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class List:
    elt: Type = attr.ib()


@attr.s(kw_only=True, slots=True)
class Constructor:
    type: Type = attr.ib()

    def instantiate(self, args: list[Type]) -> Type:
        ...


type Type = (
    PrimitiveType
    | Adt
    | Function
    | Parameter
    | List
)
