from __future__ import annotations

import attr
import enum
import typing
from itertools import count

from ..diagnostics import DiagnosticReporter

HIR_ID_COUNT = count()

"""
This is the high level intermediate representation.
It is inspired by the Rust compiler.

The HIR is very similar to the AST, but all symbols are defined
and resolved. Every attribute access that isn't on a local declaration
gets resolved as well.
"""

@attr.s(kw_only=True, slots=True)
class HirContext:
    diagnostics: DiagnosticReporter = attr.ib()
    fields: dict[int, HirField] = attr.ib(factory=dict)
    generics: dict[int, Generics] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class ModuleDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    types: dict[str, TypeDeclaration] = attr.ib(factory=dict)
    classes: dict[str, ClassDef] = attr.ib(factory=dict)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class Generics:
    owner: typing.Optional[Generics] = attr.ib(default=None)
    parameters: dict[str, TypeParameter] = attr.ib(factory=dict)

    def has_parameter_named(self, name: str) -> bool:
        if name in self.parameters:
            return True

        if self.owner is not None:
            return self.owner.has_parameter_named(name)

        return False


@attr.s(kw_only=True, slots=True)
class StructDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    fields: dict[str, MaybeUnboundType] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TupleDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    elts: list[MaybeUnboundType] = attr.ib(factory=list)

UNIT = TupleDef(name='unit', is_declaration=False, elts=[])
INVALID = TupleDef(name='invalid', is_declaration=True, elts=[])


@attr.s(kw_only=True, slots=True)
class SumDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()
    types: dict[str, typing.Optional[DataType]] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class AliasDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()
    parameters: dict[str, MaybeUnboundType] = attr.ib(factory=dict)
    returns: MaybeUnboundType = attr.ib(default=UNIT)


@attr.s(kw_only=True, slots=True)
class ClassDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class UseDef:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    type: Type = attr.ib(default=UNIT)
    type_class: Type = attr.ib(default=UNIT)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeParameter:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class LocalDeclaration:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))
    name: str = attr.ib()
    node_id: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class UnboundType:
    type: Type = attr.ib()


Type = typing.Union[
    StructDef,
    TupleDef,
    SumDef,
    AliasDef,
    ClassDef,
    TypeParameter,
]

HirField = typing.Union[
    Type,
    ModuleDef,
    FunctionDef,
    UseDef,
]

MaybeUnboundType = typing.Union[
    Type,
    UnboundType,
]

TypeWithGenerics = typing.Union[
    StructDef,
    TupleDef,
    SumDef,
    FunctionDef,
    ClassDef,
]

DataType = typing.Union[
    StructDef,
    TupleDef,
]

TypeDeclaration = typing.Union[
    StructDef,
    TupleDef,
    SumDef,
    AliasDef,
]
