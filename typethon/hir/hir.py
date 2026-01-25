from __future__ import annotations

import attr
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
class DefId:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))


@attr.s(kw_only=True, slots=True)
class HirContext:
    diagnostics: DiagnosticReporter = attr.ib()
    fields: dict[int, HirField] = attr.ib(factory=dict)
    generics: dict[int, Generics] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class ModuleDef(DefId):
    types: dict[str, TypeDeclaration] = attr.ib(factory=dict)
    classes: dict[str, ClassDef] = attr.ib(factory=dict)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class Generics:
    owner: Generics | None = attr.ib(default=None)
    parameters: dict[str, TypeParameter] = attr.ib(factory=dict)

    def has_parameter_named(self, name: str) -> bool:
        if name in self.parameters:
            return True

        if self.owner is not None:
            return self.owner.has_parameter_named(name)

        return False


@attr.s(kw_only=True, slots=True)
class StructDef(DefId):
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    fields: dict[str, HirType] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TupleDef(DefId):
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    elts: list[HirType] = attr.ib(factory=list)


UNIT = TupleDef(name="unit", is_declaration=False, elts=[])
INVALID = TupleDef(name="invalid", is_declaration=True, elts=[])


@attr.s(kw_only=True, slots=True)
class SumDef(DefId):
    name: str = attr.ib()
    types: dict[str, StructDef | TupleDef | None] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class AliasDef(DefId):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDef(DefId):
    name: str = attr.ib()
    parameters: dict[str, HirType] = attr.ib(factory=dict)
    returns: HirType = attr.ib(default=UNIT)


@attr.s(kw_only=True, slots=True)
class ClassDef(DefId):
    name: str = attr.ib()
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class UseDef(DefId):
    type: HirType = attr.ib(default=UNIT)
    type_class: HirType = attr.ib(default=UNIT)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeParameter(DefId):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class LocalDeclaration(DefId):
    name: str = attr.ib()
    node_id: int = attr.ib()


type HirField = (
    ModuleDef | StructDef | TupleDef | SumDef | AliasDef | FunctionDef | ClassDef | UseDef
)

type TypeDeclaration = (
    StructDef | TupleDef | SumDef
    # AliasDef,
)


@attr.s(kw_only=True, slots=True)
class PathSegment:
    name: str = attr.ib()
    result: HirPathResult = attr.ib()
    arguments: list[HirType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class Path:
    # Xyz.Abc('t).foo might be represented as
    # Path(segments=[
    #   PathSegment(name='Xyz', result=ModuleDef),
    #   PathSegment(name='abc', result=ClassDef, arguments=TypeParameter)
    #   PathSegment(name='foo', result=FunctionDef)
    # ])
    # Anything in the program written as a name `x` is resolved to a path.
    # Anything in a program written as `x.y` where x is not a local declaration
    # is resolved to a path.
    #   When y is not a local declaration, it is only valid in an executable code block,
    #   and it is resolved to AttributeLookup (or whetever I decide to call it)
    # When there are arguments after non-local declaration `y`, the result of the arguments
    # are resolved and added to the segment's arguments.
    segments: list[PathSegment] = attr.ib(factory=list)

    def get_result(self) -> HirPathResult:
        return self.segments[-1].result


@attr.s(kw_only=True, slots=True)
class ListType:
    elt: HirType = attr.ib()


type HirType = Path | ClassDef | TypeParameter | ListType | TypeDeclaration

type HirPathResult = (
    # HirType, bit without type parameters
    ClassDef | TypeParameter | ListType | TypeDeclaration | HirField
)
