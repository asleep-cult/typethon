from __future__ import annotations

import attr
import enum
import typing


class SingletonType(enum.Enum):
    INVALID = enum.auto()
    INFERRED = enum.auto()
    UNDECLARED = enum.auto()

    SELF = enum.auto()
    BOOL = enum.auto()


@attr.s(kw_only=True, slots=True)
class StructType:
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    fields: typing.Dict[str, Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleType:
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    elts: typing.List[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SumType:
    name: str = attr.ib()
    types: typing.Dict[str, typing.Optional[DataType]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionType:
    name: str = attr.ib()
    parameters: typing.Dict[str, Type] = attr.ib()
    returns: Type = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeClass:
    name: str = attr.ib()
    functions: typing.Dict[str, FunctionType] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeParameter:
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeInstance:
    type: Type = attr.ib()


def to_instance(type: Type) -> TypeInstance:
    return TypeInstance(type=type)


UNIT = TupleType(name='unit', is_declaration=False, elts=[])

Type = typing.Union[
    SingletonType,
    StructType,
    TupleType,
    SumType,
    FunctionType,
    TypeClass,
    TypeParameter,
]

DataType = typing.Union[
    StructType,
    TupleType,
]
