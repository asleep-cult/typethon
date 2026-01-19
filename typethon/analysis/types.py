from __future__ import annotations

import enum
import attr
import typing
from itertools import count

TYPE_COUNT = count()

def next_type_id() -> int:
    return next(TYPE_COUNT)


class SingletonType(enum.Enum):
    UNDECLARED = enum.auto()
    UNIT = enum.auto()
    UNKNOWN = enum.auto()
    SELF = enum.auto()

    BOOL = enum.auto()
    INT = enum.auto()
    FLOAT = enum.auto()
    COMPLEX = enum.auto()
    STR = enum.auto()
    # LIST, DICT, SET?
    # I think dict and set need to be in the std library
    # with no special syntax

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TypeAlias:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    name: str = attr.ib(hash=False)
    type: ConcreteType = attr.ib(default=SingletonType.UNKNOWN, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class StructField:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()

    def to_string(self) -> str:
        return f'{self.name}: {self.type.to_string()}'


@attr.s(kw_only=True, slots=True, hash=True)
class StructType:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    name: str = attr.ib(hash=False)
    fields: typing.Dict[str, StructField] = attr.ib(factory=dict, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TupleType:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    name: str = attr.ib(hash=False)
    fields: typing.List[ConcreteType] = attr.ib(factory=list, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()

    def to_string(self) -> str:
        return f'{self.name}: {self.type.to_string()}'


@attr.s(kw_only=True, slots=True, hash=True)
class FunctionType:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    name: str = attr.ib(hash=False)
    parameters: typing.Dict[str, FunctionParameter] = attr.ib(factory=dict, hash=False)
    returns: ConcreteType = attr.ib(default=SingletonType.UNIT, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TypeClass:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    name: str = attr.ib(hash=False)
    functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict, hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True, hash=True)
class TypeParameter:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    name: str = attr.ib(hash=False)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class PolymorphicType:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    type: NonParameterizedConcreteType = attr.ib(hash=False)
    parameters: typing.List[TypeParameter] = attr.ib(factory=list, hash=False)

    def to_string(self) -> str:
        parameters = ', '.join(parameter.to_string() for parameter in self.parameters)
        return f'polmorohic({self.type.to_string()}, {parameters})'

    def with_parameters(self, parameters: typing.List[ConcreteType]) -> ConcreteType:
        if len(self.parameters) != len(parameters):
            raise ValueError(f'{self} requires {len(self.parameters)}, got {len(parameters)}')

        parameter_map = dict(zip(self.parameters, parameters))
        return ParameterizedType(type=self.type, parameter_map=parameter_map)


@attr.s(kw_only=True, slots=True)
class ParameterizedType:
    type: NonParameterizedConcreteType = attr.ib()
    parameter_map: typing.Dict[TypeParameter, ConcreteType] = attr.ib()

    def to_string(self) -> str:
        parameters = ', '.join(
            f'{param1.to_string()} -> {param2.to_string()}'
            for param1, param2 in self.parameter_map.items()
        )
        return f'parameterized({self.type.to_string()}, {parameters})'


@attr.s(kw_only=True, slots=True)
class SumType:
    id: int = attr.ib(init=False, factory=next_type_id, hash=True)
    name: str = attr.ib()
    fields: typing.Dict[str, SumField] = attr.ib(factory=dict)

    def to_string(self) -> str:
        return self.name


@attr.s(kw_only=True, slots=True)
class SumField(SumType):
    name: str = attr.ib()
    data: typing.Optional[DataType] = attr.ib()


NonParameterizedConcreteType = typing.Union[
    SingletonType,
    TypeAlias,
    StructType,
    TupleType,
    FunctionType,
    TypeClass,
    SumType,
    TypeParameter,
]

ConcreteType = typing.Union[
    NonParameterizedConcreteType,
    ParameterizedType,
]

Type = typing.Union[
    ConcreteType,
    PolymorphicType,
]

DataType = typing.Union[
    StructType,
    TupleType,
]
