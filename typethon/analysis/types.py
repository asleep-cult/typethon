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
    UNIT = enum.auto()
    UNKNOWN = enum.auto()

    def substitute_type_parameters(self, type_map: typing.Dict[TypeParameter, ConcreteType]) -> ConcreteType:
        return self


@attr.s(kw_only=True, slots=True)
class TypeAlias:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    type: ConcreteType = attr.ib(default=SingletonType.UNKNOWN)

    def substitute_type_parameters(self, type_map: typing.Dict[TypeParameter, ConcreteType]) -> ConcreteType:
        return self.type.substitute_type_parameters(type_map)


@attr.s(kw_only=True, slots=True)
class StructField:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()


@attr.s(kw_only=True, slots=True)
class StructType:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    fields: typing.Dict[str, StructField] = attr.ib(factory=dict)

    def substitute_type_parameters(self, type_map: typing.Dict[TypeParameter, ConcreteType]) -> StructType:
        fields: typing.Dict[str, StructField] = {}

        for field in self.fields.values():
            fields[field.name] = StructField(
                name=field.name,
                type=field.type.substitute_type_parameters(type_map),
            )

        return StructType(name=self.name, scope=self.scope, fields=fields)


@attr.s(kw_only=True, slots=True)
class TupleType:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    fields: typing.List[ConcreteType] = attr.ib(factory=list)

    def substitute_type_parameters(self, type_map: typing.Dict[TypeParameter, ConcreteType]) -> TupleType:
        fields: typing.List[ConcreteType] = []

        for field in self.fields:
            fields.append(field.substitute_type_parameters(type_map))

        return TupleType(name=self.name, scope=self.scope, fields=fields)


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: ConcreteType = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionType:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    parameters: typing.Dict[str, FunctionParameter] = attr.ib(factory=dict)
    returns: ConcreteType = attr.ib(default=SingletonType.UNIT)

    def substitute_type_parameters(self, type_map: typing.Dict[TypeParameter, ConcreteType]) -> FunctionType:
        parameters: typing.Dict[str, FunctionParameter] = {}

        for parameter in self.parameters.values():
            parameters[parameter.name] = FunctionParameter(
                name=parameter.name,
                type=parameter.type.substitute_type_parameters(type_map),
            )

        returns = self.returns.substitute_type_parameters(type_map)
        return FunctionType(name=self.name, scope=self.scope, parameters=parameters, returns=returns)


@attr.s(kw_only=True, slots=True)
class TypeClass:
    name: str = attr.ib()
    scope: Scope = attr.ib()
    functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict)

    def substitute_type_parameters(self, type_map: typing.Dict[TypeParameter, ConcreteType]) -> TypeClass:
        functions: typing.Dict[str, FunctionType] = {}

        for function in self.functions.values():
            functions[function.name] = function.substitute_type_parameters(type_map)

        return TypeClass(name=self.name, scope=self.scope, functions=functions)


@attr.s(kw_only=True, slots=True, hash=True)
class TypeParameter:
    id: int = attr.ib(init=False, hash=True, factory=lambda: next(TYPE_PARAMETER_COUNT))
    name: str = attr.ib(hash=False)

    def substitute_type_parameters(self, type_map: typing.Dict[TypeParameter, ConcreteType]) -> typing.Self:
        if self in type_map:
            return type_map[self]
    
        return self


@attr.s(kw_only=True, slots=True)
class PolymorphicType:
    type: ConcreteType = attr.ib()
    parameters: typing.List[TypeParameter] = attr.ib(factory=list)

    def with_parameters(self, parameters: typing.List[ConcreteType]) -> ConcreteType:
        if len(self.parameters) != len(parameters):
            raise ValueError(f'{self} requires {len(self.parameters)}, got {len(parameters)}')

        type_map = dict(zip(self.parameters, parameters))
        return self.type.substitute_type_parameters(type_map)


ConcreteType = typing.Union[
    SingletonType,
    TypeAlias,
    StructType,
    TupleType,
    FunctionType,
    TypeClass,
    TypeParameter,
]
Type = typing.Union[
    ConcreteType,
    PolymorphicType,
]
