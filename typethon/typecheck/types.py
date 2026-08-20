from __future__ import annotations

import enum
from collections.abc import Sequence  # Covariant

import attr

from . import typeinfo


class PrimitiveType(enum.Enum):
    INFERRED = enum.auto()
    INT = enum.auto()
    BOOL = enum.auto()
    STRING = enum.auto()

    def substitute_arguments(self, args: list[Type]) -> Type:
        return self


@attr.s(kw_only=True, slots=True)
class Adt:
    # Represents all nominal types in a (i.e. type definition statement)
    info: typeinfo.AdtInfo = attr.ib()
    args: Sequence[Type] = attr.ib()

    def substitute_arguments(self, args: list[Type]) -> Type:
        return Adt(info=self.info, args=[arg.substitute_arguments(args) for arg in self.args])


@attr.s(kw_only=True, slots=True)
class Function:
    info: typeinfo.FunctionInfo = attr.ib()
    args: Sequence[Type] = attr.ib()

    def substitute_arguments(self, args: list[Type]) -> Type:
        return Function(info=self.info, args=[arg.substitute_arguments(args) for arg in self.args])


@attr.s(kw_only=True, slots=True)
class Parameter:
    name: str = attr.ib()
    index: int = attr.ib()

    def substitute_arguments(self, args: list[Type]) -> Type:
        return args[self.index]


@attr.s(kw_only=True, slots=True)
class Struct:
    fields: dict[str, Type] = attr.ib()

    def substitute_arguments(self, args: list[Type]) -> Type:
        return Struct(fields={name: field.substitute_arguments(args) for name, field in self.fields.items()})


@attr.s(kw_only=True, slots=True)
class Tuple:
    elts: list[Type] = attr.ib()

    def substitute_arguments(self, args: list[Type]) -> Type:
        return Tuple(elts=[elt.substitute_arguments(args) for elt in self.elts])



@attr.s(kw_only=True, slots=True)
class List:
    elt: Type = attr.ib()

    def substitute_arguments(self, args: list[Type]) -> Type:
        return self.elt.substitute_arguments(args)


@attr.s(kw_only=True, slots=True)
class Binder:
    type: Type = attr.ib()

    def instantiate(self, args: list[Type]) -> Type:
        return self.type.substitute_arguments(args)


type Type = PrimitiveType | Adt | Function | Parameter | Struct | Tuple | List
