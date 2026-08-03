from __future__ import annotations

import attr

from itertools import count

from .. import asg

TYPE_ID = count()


@attr.s(kw_only=True, slots=True)
class TypeContext:
    asg_ctx: asg.AsgContext = attr.ib()
    # Mapping from asg id to Type
    types: dict[int, Type] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class Type:
    asg_id: int = attr.ib()
    id: int = attr.ib(factory=lambda: next(TYPE_ID))

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return False


@attr.s(kw_only=True, slots=True)
class TypeParameter(Type):
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
        return result.id == type_parameter.id


@attr.s(kw_only=True, slots=True)
class ListType(Type):
    elt: Type = attr.ib()

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return self.elt.has_type_parameter(type_parameter, substitutions)


@attr.s(kw_only=True, slots=True)
class PolymorphicType(Type):
    parent: PolymorphicType | None = attr.ib(default=None)
    parameters: dict[str, Type] = attr.ib(factory=dict)

    def get_parent_id(self):
        if self.parent is not None:
            return self.parent.id

        return self.id

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return any(
            parameter.has_type_parameter(type_parameter, substitutions)
            for parameter in self.parameters.values()
        )


@attr.s(kw_only=True, slots=True)
class FunctionType(PolymorphicType):
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
class ClassType(PolymorphicType):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class StructType(PolymorphicType):
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    fields: dict[str, Type] = attr.ib(factory=list)

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return any(
            field.has_type_parameter(type_parameter, substitutions)
            for field in self.fields.values()
        )


@attr.s(kw_only=True, slots=True)
class TupleType(PolymorphicType):
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    elts: list[Type] = attr.ib(factory=list)

    def has_type_parameter(self, type_parameter: TypeParameter, substitutions: dict[int, Type]) -> bool:
        return any(elt.has_type_parameter(type_parameter, substitutions) for elt in self.elts)
