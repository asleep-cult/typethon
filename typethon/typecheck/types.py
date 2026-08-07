from __future__ import annotations

import attr

from itertools import count

from .. import asg

TYPE_ID = count()


@attr.s(kw_only=True, slots=True)
class TypeContext:
    asg_ctx: asg.AsgContext = attr.ib()
    # Mapping from asg id to Type
    types: dict[int, Type | ConstructedType] = attr.ib(factory=dict)
    general_constructors: dict[int, ConstructedType] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeId:
    id: int = attr.ib(factory=lambda: next(TYPE_ID))


@attr.s(kw_only=True, slots=True)
class PrimitiveType(TypeId):
    name: str = attr.ib()

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return False


@attr.s(kw_only=True, slots=True)
class TypeParameter(TypeId):
    name: str = attr.ib()

    def resolve(self, substitutions: dict[int, Type]) -> Type:
        if self.id in substitutions:
            result = substitutions[self.id]
            if isinstance(result, TypeParameter):
                result = result.resolve(substitutions)
            
            return result
        return self

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        result = self.resolve(substitutions)
        if result is not self:
            return result.has_type_parameter(type_parameter, substitutions)
        return result.id == type_parameter.id


@attr.s(kw_only=True, slots=True)
class ConstructedType(TypeId):
    body: ConstructableType = attr.ib()
    arguments: list[Type] = attr.ib(factory=list)
    parameter_map: dict[int, Type] | None = attr.ib(default=None)

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return any(
            argument.has_type_parameter(type_parameter, substitutions)
            for argument in self.arguments
        )

    def apply_substitution(self, type: Type) -> Type:
        if self.parameter_map is None:
            return type

        if isinstance(type, TypeParameter):
            if type.id in self.parameter_map:
                return self.apply_substitution(self.parameter_map[type.id])

        elif isinstance(type, ConstructedType):
            return ConstructedType(
                body=type.body,
                arguments=[self.apply_substitution(argument) for argument in type.arguments],
                parameter_map=type.parameter_map,
            )

        elif isinstance(type, FunctionType):
            parameters: dict[str, Type | None] = {}
            for name, parameter_type in type.parameters.items():
                if parameter_type is not None:
                    parameter_type = self.apply_substitution(parameter_type)

                parameters[name] = parameter_type

            return_type = None
            if type.returns is not None:
                return_type = self.apply_substitution(type.returns)

            return FunctionType(name=type.name, parameters=parameters, returns=return_type)

        return type 


@attr.s(kw_only=True, slots=True)
class FunctionType(TypeId):
    name: str = attr.ib()
    parameters: dict[str, Type | None] = attr.ib(factory=dict)
    returns: Type | None = attr.ib(default=None)

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        result = any(
            parameter.has_type_parameter(type_parameter, substitutions)
            for parameter in self.parameters.values() if parameter is not None
        )
        if not result and self.returns is not None:
            result = self.returns.has_type_parameter(type_parameter, substitutions)

        return result


@attr.s(kw_only=True, slots=True)
class ClassType(TypeId):
    name: str = attr.ib()
    functions: dict[str, FunctionType | ConstructedType] = attr.ib(factory=dict)

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return any(function.has_type_parameter(type_parameter, substitutions) for function in self.functions.values()) 


@attr.s(kw_only=True, slots=True)
class StructType(TypeId):
    name: str = attr.ib()
    structural: bool = attr.ib()
    fields: dict[str, Type] = attr.ib(factory=dict)

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return any(
            field.has_type_parameter(type_parameter, substitutions)
            for field in self.fields.values()
        )


@attr.s(kw_only=True, slots=True)
class TupleType(TypeId):
    name: str = attr.ib()
    structural: bool = attr.ib()
    elts: list[Type] = attr.ib(factory=list)

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return any(elt.has_type_parameter(type_parameter, substitutions) for elt in self.elts)


LIST = ConstructedType(
    arguments=[TypeParameter(name='T')],
    body=TupleType(name='list', elts=[], structural=False),
)

ConstructableType = (
    FunctionType
    | ClassType
    | StructType
    | TupleType
)

type Type = (
    ConstructableType
    | ConstructedType
    | PrimitiveType
    | TypeParameter
)
