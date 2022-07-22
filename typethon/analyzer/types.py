from __future__ import annotations

import typing
import types
import enum

import attr

from .errors import ErrorCategory
from .. import ast

if typing.TYPE_CHECKING:
    from typing_extensions import TypeGuard


class TypeKind(enum.Enum):
    BOOL = enum.auto()
    NONE = enum.auto()
    ELLIPSIS = enum.auto()

    STRING = enum.auto()
    BYTES = enum.auto()
    INTEGER = enum.auto()
    FLOAT = enum.auto()
    COMPLEX = enum.auto()

    DICT = enum.auto()
    SET = enum.auto()
    TUPLE = enum.auto()
    LIST = enum.auto()

    SLICE = enum.auto()

    FUNCTION = enum.auto()
    CLASS = enum.auto()

    UNION = enum.auto()
    UNKNOWN = enum.auto()
    ERROR = enum.auto()


@attr.s(kw_only=True, slots=True)
class Type:
    kind: TypeKind = attr.ib()

    def compatible_with(self, other: Type) -> bool:
        return self.kind is other.kind


@attr.s(kw_only=True, slots=True)
class BoolType(Type):
    kind: typing.Literal[TypeKind.BOOL] = attr.ib(init=False, default=TypeKind.BOOL)
    value: typing.Optional[bool] = attr.ib(default=None)
    implicit: bool = attr.ib(default=False)

    @classmethod
    def with_value(cls, value: bool) -> BoolType:
        return cls(value=value)

    def __str__(self) -> str:
        if self.value is None:
            return 'bool'

        return str(self.value)


@attr.s(kw_only=True, slots=True)
class NoneType(Type):
    kind: typing.Literal[TypeKind.NONE] = attr.ib(init=False, default=TypeKind.NONE)
    value: None = attr.ib(init=False, default=None)

    def __str__(self) -> str:
        return 'None'


@attr.s(kw_only=True, slots=True)
class EllipsisType(Type):
    kind: typing.Literal[TypeKind.ELLIPSIS] = attr.ib(init=False, default=TypeKind.ELLIPSIS)
    value: types.EllipsisType = attr.ib(init=False, default=Ellipsis)

    def __str__(self) -> str:
        return 'ellipsis'


@attr.s(kw_only=True, slots=True)
class StringType(Type):
    kind: typing.Literal[TypeKind.STRING] = attr.ib(init=False, default=TypeKind.STRING)
    value: typing.Optional[str] = attr.ib(default=None)
    implicit: bool = attr.ib(default=False)

    @classmethod
    def with_value(cls, value: str) -> StringType:
        return cls(value=value)

    def __str__(self):
        if self.value is None:
            return 'str'

        return repr(self.value)


@attr.s(kw_only=True, slots=True)
class IntegerType(Type):
    kind: typing.Literal[TypeKind.INTEGER] = attr.ib(init=False, default=TypeKind.INTEGER)
    value: typing.Optional[int] = attr.ib(default=None)
    implicit: bool = attr.ib(default=False)

    @classmethod
    def with_value(cls, value: int) -> IntegerType:
        return cls(value=value)

    def __str__(self) -> str:
        if self.value is None:
            return 'int'

        return str(self.value)


@attr.s(kw_only=True, slots=True)
class FloatType(Type):
    kind: typing.Literal[TypeKind.FLOAT] = attr.ib(init=False, default=TypeKind.FLOAT)
    value: typing.Optional[float] = attr.ib(default=None)
    implicit: bool = attr.ib(default=False)

    @classmethod
    def with_value(cls, value: float) -> FloatType:
        return cls(value=value)

    def __str__(self) -> str:
        if self.value is None:
            return 'float'

        return str(self.value)


@attr.s(kw_only=True, slots=True)
class ComplexType(Type):
    kind: typing.Literal[TypeKind.COMPLEX] = attr.ib(init=False, default=TypeKind.COMPLEX)
    value: typing.Optional[complex] = attr.ib(default=None)
    implicit: bool = attr.ib(default=False)

    @classmethod
    def with_value(cls, value: complex) -> ComplexType:
        return cls(value=value)

    def __str__(self) -> str:
        if self.value is None:
            return 'complex'

        return str(self.value)


@attr.s(kw_only=True, slots=True)
class DictType(Type):
    kind: typing.Literal[TypeKind.DICT] = attr.ib(init=False, default=TypeKind.DICT)

    key: Type = attr.ib()
    value: Type = attr.ib()

    def __str__(self) -> str:
        return f'{{{self.key}: {self.value}}}'


@attr.s(kw_only=True, slots=True)
class SetType(Type):
    kind: typing.Literal[TypeKind.SET] = attr.ib(init=False, default=TypeKind.SET)
    value: Type = attr.ib()

    def __str__(self) -> str:
        return f'{{{self.value}}}'


@attr.s(kw_only=True, slots=True)
class TupleType(Type):
    kind: typing.Literal[TypeKind.TUPLE] = attr.ib(init=False, default=TypeKind.TUPLE)
    values: typing.List[Type] = attr.ib()

    def __str__(self) -> str:
        values = ', '.join(str(value) for value in self.values)
        return f'({values})'


@attr.s(kw_only=True, slots=True)
class ListType(Type):
    kind: typing.Literal[TypeKind.LIST] = attr.ib(init=False, default=TypeKind.LIST)
    value: Type = attr.ib()
    size: typing.Optional[int] = attr.ib(default=None)

    def __str__(self) -> str:
        if self.size is None:
            return f'[{self.value}]'

        return f'[{self.value}, {self.size}]'


@attr.s(kw_only=True, slots=True)
class SliceType(Type):
    kind: typing.Literal[TypeKind.SLICE] = attr.ib(init=False, default=TypeKind.SLICE)
    start: typing.Optional[Type] = attr.ib()
    stop: typing.Optional[Type] = attr.ib()
    step: typing.Optional[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: Type = attr.ib()
    kind: ast.ParameterKind = attr.ib()
    default: typing.Optional[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionType(Type):
    kind: typing.Literal[TypeKind.FUNCTION] = attr.ib(init=False, default=TypeKind.FUNCTION)
    parameters: typing.List[FunctionParameter] = attr.ib()
    returns: Type = attr.ib()


@attr.s(kw_only=True, slots=True)
class ClassType(Type):
    kind: typing.Literal[TypeKind.CLASS] = attr.ib(init=False, default=TypeKind.CLASS)
    bases: typing.List[Type] = attr.ib()


@attr.s(slots=True)
class UnionType(Type):
    kind: typing.Literal[TypeKind.UNION] = attr.ib(init=False, default=TypeKind.UNION)
    types: typing.List[Type] = attr.ib()

    def __str__(self) -> str:
        return ' | '.join(str(type) for type in self.types)


@attr.s(kw_only=True, slots=True)
class UnknownType(Type):
    kind: typing.Literal[TypeKind.UNKNOWN] = attr.ib(init=False, default=TypeKind.UNKNOWN)

    def __str__(self) -> str:
        return 'unknown'


@attr.s(kw_only=True, slots=True)
class ErrorType(Type):
    kind: typing.Literal[TypeKind.ERROR] = attr.ib(init=False, default=TypeKind.ERROR)
    category: ErrorCategory = attr.ib()
    message: str = attr.ib()
    node: typing.Optional[ast.Node] = attr.ib(default=None)

    def set_node(self, node: ast.Node) -> ErrorType:
        return ErrorType(category=self.category, message=self.message, node=node)


ConstantType = typing.Union[
    BoolType,
    NoneType,
    EllipsisType,
    StringType,
    IntegerType,
    FloatType,
    ComplexType,
]

LiteralType = typing.Union[
    BoolType,
    StringType,
    IntegerType,
    FloatType,
    ComplexType,
]


def union(types: typing.Iterable[Type]) -> UnionType:
    flattened: typing.List[Type] = []

    for type in types:
        if isinstance(type, UnionType):
            flattened.extend(type for type in type.types if type not in flattened)
        else:
            if type not in flattened:
                flattened.append(type)

    return UnionType(types=flattened)


def is_valid(type: Type) -> bool:
    return not is_unknown(type) and not is_error(type)


def is_unknown(type: Type) -> TypeGuard[UnknownType]:
    return type.kind is TypeKind.UNKNOWN


def is_error(type: Type) -> TypeGuard[ErrorType]:
    return type.kind is TypeKind.ERROR
