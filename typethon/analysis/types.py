from __future__ import annotations

import enum
import attr
import typing
from itertools import count

TYPE_PARAMETER_COUNT = count()

if typing.TYPE_CHECKING:
    from .scope import Scope


# TODO: Stop creating copies on substitution it doesnt work well
# There needs to be an id for everything and a single data structure

class SingletonType(enum.Enum):
    UNDECLARED = enum.auto()
    UNIT = enum.auto()
    UNKNOWN = enum.auto()
    SELF = enum.auto()

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class TypeAlias:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    type: ConcreteType = attr.ib(default=SingletonType.UNKNOWN)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class StructField:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()

    def to_string(self) -> str:
        return f'{self.name}: {self.type.to_string()}'


@attr.s(kw_only=True, slots=True)
class StructType:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    fields: typing.Dict[str, StructField] = attr.ib(factory=dict)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class TupleType:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    fields: typing.List[ConcreteType] = attr.ib(factory=list)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()

    def to_string(self) -> str:
        return f'{self.name}: {self.type.to_string()}'


@attr.s(kw_only=True, slots=True)
class FunctionType:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    parameters: typing.Dict[str, FunctionParameter] = attr.ib(factory=dict)
    returns: ConcreteType = attr.ib(default=SingletonType.UNIT)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class TypeClass:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TypeParameter:
    id: int = attr.ib(init=False, hash=True, factory=lambda: next(TYPE_PARAMETER_COUNT))
    name: str = attr.ib(hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class PolymorphicType:
    type: ConcreteType = attr.ib()
    parameters: typing.List[TypeParameter] = attr.ib(factory=list)

    def to_string(self) -> str:
        parameters = ', '.join(parameter.to_string() for parameter in self.parameters)
        return f'polmorohic({self.type.to_string()}, {parameters})'

    def with_parameters(self, parameters: typing.List[ConcreteType]) -> ConcreteType:
        if len(self.parameters) != len(parameters):
            raise ValueError(f'{self} requires {len(self.parameters)}, got {len(parameters)}')

        type_map = dict(zip(self.parameters, parameters))
        return ParameterizedType(type=self.type, type_map=type_map)


@attr.s(kw_only=True, slots=True)
class ParameterizedType:
    type: ConcreteType = attr.ib()
    type_map: typing.Dict[TypeParameter, ConcreteType] = attr.ib()

    def to_string(self) -> str:
        parameters = ', '.join(
            f'{param1.to_string()} -> {param2.to_string()}'
            for param1, param2 in self.type_map.items()
        )
        return f'parameterized({self.type.to_string()}, {parameters})'


ConcreteType = typing.Union[
    SingletonType,
    TypeAlias,
    StructType,
    TupleType,
    FunctionType,
    TypeClass,
    TypeParameter,
    ParameterizedType,
]
Type = typing.Union[
    ConcreteType,
    PolymorphicType,
]
