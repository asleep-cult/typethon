from __future__ import annotations

import copy
import typing
import types
import enum

import attr

from .. import ast

if typing.TYPE_CHECKING:
    from typing_extensions import Self, TypeGuard

    from .scope import Scope


class TypeKind(enum.Enum):
    TYPE = enum.auto()
    OBJECT = enum.auto()
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

    MODULE = enum.auto()
    CLASS = enum.auto()
    FUNCTION = enum.auto()
    METHOD = enum.auto()

    UNION = enum.auto()
    UNKNOWN = enum.auto()


class TypeFlags(enum.IntFlag):
    NONE = 0
    TYPE = enum.auto()
    IMPLICIT = enum.auto()


@attr.s(kw_only=True, slots=True)
class Type:
    kind: TypeKind = attr.ib()
    flags: TypeFlags = attr.ib(default=TypeFlags.NONE)

    def __str__(self) -> str:
        if self.is_instance():
            return self.to_string()

        return f'type{{{self.to_string()}}}'

    def to_string(self) -> str:
        return repr(self)

    def is_instance(self) -> bool:
        return self.flags & TypeFlags.TYPE == 0

    def to_instance(self) -> Self:
        type = copy.copy(self)
        type.flags &= ~TypeFlags.TYPE
        return self

    def to_type(self) -> Self:
        type = copy.copy(self)
        type.flags |= TypeFlags.TYPE
        return self


@attr.s(kw_only=True, slots=True)
class TypeInstance(Type):
    kind: typing.Literal[TypeKind.TYPE] = attr.ib(init=False, default=TypeKind.TYPE)
    value: typing.Optional[Type] = attr.ib(default=None)

    def to_string(self) -> str:
        if self.value is None:
            return 'type'

        return f'type{{{self.value}}}'


@attr.s(kw_only=True, slots=True)
class ObjectType(Type):
    kind: typing.Literal[TypeKind.OBJECT] = attr.ib(init=False, default=TypeKind.OBJECT)
    value: typing.Optional[Type] = attr.ib(default=None)

    def get_value(self) -> Type:
        if self.value is None:
            raise RuntimeError('object is missing value')

        return self.value

    def to_string(self) -> str:
        return 'object'


@attr.s(kw_only=True, slots=True)
class BoolType(Type):
    kind: typing.Literal[TypeKind.BOOL] = attr.ib(init=False, default=TypeKind.BOOL)
    value: typing.Optional[bool] = attr.ib(default=None)

    @classmethod
    def with_value(cls, value: bool) -> BoolType:
        return cls(value=value)

    def to_string(self) -> str:
        if self.value is None:
            return 'bool'

        return f'bool({self.value})'


@attr.s(kw_only=True, slots=True)
class NoneType(Type):
    kind: typing.Literal[TypeKind.NONE] = attr.ib(init=False, default=TypeKind.NONE)
    value: None = attr.ib(init=False, default=None)

    def to_string(self) -> str:
        return 'None'


@attr.s(kw_only=True, slots=True)
class EllipsisType(Type):
    kind: typing.Literal[TypeKind.ELLIPSIS] = attr.ib(init=False, default=TypeKind.ELLIPSIS)
    value: types.EllipsisType = attr.ib(init=False, default=Ellipsis)

    def to_string(self) -> str:
        return 'ellipsis'


@attr.s(kw_only=True, slots=True)
class StringType(Type):
    kind: typing.Literal[TypeKind.STRING] = attr.ib(init=False, default=TypeKind.STRING)
    value: typing.Optional[str] = attr.ib(default=None)

    @classmethod
    def with_value(cls, value: str) -> StringType:
        return cls(value=value)

    def to_string(self):
        if self.value is None:
            return 'str'

        return f'str({self.value!r})'


@attr.s(kw_only=True, slots=True)
class IntegerType(Type):
    kind: typing.Literal[TypeKind.INTEGER] = attr.ib(init=False, default=TypeKind.INTEGER)
    value: typing.Optional[int] = attr.ib(default=None)

    @classmethod
    def with_value(cls, value: int) -> IntegerType:
        return cls(value=value)

    def to_string(self) -> str:
        if self.value is None:
            return 'int'

        return f'int({self.value})'


@attr.s(kw_only=True, slots=True)
class FloatType(Type):
    kind: typing.Literal[TypeKind.FLOAT] = attr.ib(init=False, default=TypeKind.FLOAT)
    value: typing.Optional[float] = attr.ib(default=None)

    @classmethod
    def with_value(cls, value: float) -> FloatType:
        return cls(value=value)

    def to_string(self) -> str:
        if self.value is None:
            return 'float'

        return f'float({self.value})'


@attr.s(kw_only=True, slots=True)
class ComplexType(Type):
    kind: typing.Literal[TypeKind.COMPLEX] = attr.ib(init=False, default=TypeKind.COMPLEX)
    value: typing.Optional[complex] = attr.ib(default=None)

    @classmethod
    def with_value(cls, value: complex) -> ComplexType:
        return cls(value=value)

    def to_string(self) -> str:
        if self.value is None:
            return 'complex'

        return f'complex({self.value.real}, {self.value.imag})'


@attr.s(kw_only=True, slots=True)
class DictFields:
    key: Type = attr.ib()
    value: Type = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictType(Type):
    kind: typing.Literal[TypeKind.DICT] = attr.ib(init=False, default=TypeKind.DICT)
    fields: typing.Optional[DictFields] = attr.ib(default=None)

    def get_fields(self) -> DictFields:
        if self.fields is None:
            raise RuntimeError('dict is missing fields')

        return self.fields

    def to_string(self) -> str:
        if self.fields is None:
            return 'dict'

        return f'{{{self.fields.key}: {self.fields.value}}}'


@attr.s(kw_only=True, slots=True)
class SetType(Type):
    kind: typing.Literal[TypeKind.SET] = attr.ib(init=False, default=TypeKind.SET)
    value: typing.Optional[Type] = attr.ib(default=None)

    def to_string(self) -> str:
        if self.value is None:
            return '{}'

        return f'{{{self.value}}}'


@attr.s(kw_only=True, slots=True)
class TupleType(Type):
    kind: typing.Literal[TypeKind.TUPLE] = attr.ib(init=False, default=TypeKind.TUPLE)
    values: typing.Optional[typing.List[Type]] = attr.ib(default=None)

    def to_string(self) -> str:
        if self.values is None:
            return 'tuple'

        values = ', '.join(str(value) for value in self.values)

        if len(self.values) == 1:
            return f'({values},)'

        return f'({values})'


@attr.s(kw_only=True, slots=True)
class ListType(Type):
    kind: typing.Literal[TypeKind.LIST] = attr.ib(init=False, default=TypeKind.LIST)
    value: typing.Optional[Type] = attr.ib(default=None)
    size: typing.Optional[int] = attr.ib(default=None)

    def to_string(self) -> str:
        if self.value is None:
            return 'list'

        if self.size is None:
            return f'[{self.value}]'

        return f'[{self.value}, {self.size}]'


@attr.s(kw_only=True, slots=True)
class SliceType(Type):
    kind: typing.Literal[TypeKind.SLICE] = attr.ib(init=False, default=TypeKind.SLICE)
    start: typing.Optional[Type] = attr.ib(default=None)
    stop: typing.Optional[Type] = attr.ib(default=None)
    step: typing.Optional[Type] = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class ModuleType(Type):
    kind: typing.Literal[TypeKind.MODULE] = attr.ib(init=False, default=TypeKind.MODULE)
    scope: Scope = attr.ib()


@attr.s(kw_only=True, slots=True)
class ClassFields:
    bases: typing.List[Type] = attr.ib()
    scope: Scope = attr.ib()


@attr.s(kw_only=True, slots=True)
class ClassType(Type):
    kind: typing.Literal[TypeKind.CLASS] = attr.ib(init=False, default=TypeKind.CLASS)
    fields: typing.Optional[ClassFields] = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: Type = attr.ib()
    kind: ast.ParameterKind = attr.ib()
    default: typing.Optional[Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionFields:
    name: str = attr.ib()
    parameters: typing.List[FunctionParameter] = attr.ib()
    returns: Type = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionType(Type):
    kind: typing.Literal[TypeKind.FUNCTION] = attr.ib(init=False, default=TypeKind.FUNCTION)
    fields: typing.Optional[FunctionFields] = attr.ib(default=None)

    def get_fields(self) -> FunctionFields:
        if self.fields is None:
            raise RuntimeError('function fields is missing')

        return self.fields


@attr.s(kw_only=True, slots=True)
class BuiltinFunctionType(FunctionType):
    function: typing.Callable[..., Type] = attr.ib()


@attr.s(kw_only=True, slots=True)
class MethodFields:
    instance: Type = attr.ib()
    function: FunctionType = attr.ib()


@attr.s(kw_only=True, slots=True)
class MethodType(Type):
    kind: typing.Literal[TypeKind.METHOD] = attr.ib(init=False, default=TypeKind.METHOD)
    fields: typing.Optional[MethodFields] = attr.ib(default=None)

    def get_fields(self) -> MethodFields:
        if self.fields is None:
            raise RuntimeError('method fields is missing')

        return self.fields


@attr.s(slots=True)
class UnionType(Type):
    kind: typing.Literal[TypeKind.UNION] = attr.ib(init=False, default=TypeKind.UNION)
    types: typing.List[Type] = attr.ib()

    def to_string(self) -> str:
        return ' | '.join(str(type) for type in self.types)


@attr.s(kw_only=True, slots=True)
class UnknownType(Type):
    kind: typing.Literal[TypeKind.UNKNOWN] = attr.ib(init=False, default=TypeKind.UNKNOWN)

    def to_string(self) -> str:
        return 'unknown'


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


def union(types: typing.Iterable[Type]) -> Type:
    flattened: typing.List[Type] = []

    for type in types:
        if isinstance(type, UnionType):
            for type in type.types:
                if type not in flattened:
                    flattened.append(type)
        else:
            if type not in flattened:
                flattened.append(type)

    if len(flattened) == 1:
        return flattened[0]

    return UnionType(types=flattened)


def is_unknown(type: Type) -> TypeGuard[UnknownType]:
    return type.kind is TypeKind.UNKNOWN
