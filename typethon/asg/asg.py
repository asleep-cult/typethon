from __future__ import annotations

import attr
import enum
import typing
from itertools import count

from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast

if typing.TYPE_CHECKING:
    from .resolution import ResolvedSymbol

ASG_ID_COUNT = count()


# This is the abstract semantic graph.
# It is inspired by the Rust compiler.

# The ASG is very similar to the AST, but all symbols are defined
# and resolved. Every attribute access that isn't on a local definition
# gets resolved as well.

type DefinitionId = int


class Singleton(enum.Enum):
    INFERRED = enum.auto()

INFERRED = Singleton.INFERRED


@attr.s(kw_only=True, slots=True)
class Definition:
    def_id: DefinitionId = attr.ib(factory=lambda: next(ASG_ID_COUNT))


@attr.s(kw_only=True, slots=True)
class AsgContext:
    # A container that primarily keeps tracks of all definitions lowered
    # regardless of where they are located in the code.
    # A definition is any one of the following:
    #   xx.tpy: ModuleDef
    #   type XX = ...: StructDef/TupleDef/AliasDef/SumDef
    #   def xx(...) -> ...: FunctionDef
    #   use XX [for YY]: UseDef
    diagnostics: DiagnosticReporter = attr.ib()
    definitions: dict[DefinitionId, AsgDefinition] = attr.ib(factory=dict)
    # A mapping of field id to Generics instances. Types, functions,
    # and use blocks can all have one.
    generics: dict[DefinitionId, Generics] = attr.ib(factory=dict)
    definition_parents: dict[DefinitionId, DefinitionId] = attr.ib(factory=dict)
    definition_nodes: dict[DefinitionId, int] = attr.ib(factory=dict)

    def add_definition(self, parent_id: DefinitionId | None, node_id: int, definition: AsgDefinition) -> None:
        self.definitions[node_id] = definition
        self.definition_nodes[definition.def_id] = node_id
        if parent_id is not None:
            self.definition_parents[definition.def_id] = parent_id

    def parent(self, def_id: DefinitionId) -> DefinitionId | None:
        if def_id in self.definition_parents:
            return self.definition_parents[def_id]

    def record_parent(self, def_id: DefinitionId, parent_id: DefinitionId) -> None:
        self.definition_parents[def_id] = parent_id

    def definition(self, def_id: int) -> AsgDefinition:
        node_id = self.definition_nodes[def_id]
        return self.definitions[node_id]


@attr.s(kw_only=True, slots=True)
class ModuleDef(Definition):
    types: dict[str, TypeDefinition] = attr.ib(factory=dict)
    classes: dict[str, ClassDef] = attr.ib(factory=dict)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)
    body: AsgBody | None = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class Generics:
    # Similar to a scope that keeps track of type paramters by name.
    def_id: DefinitionId = attr.ib()
    parent: Generics | None = attr.ib(default=None)
    parameters: dict[str, TypeParameter] = attr.ib(factory=dict)

    def has_parameter_named(self, name: str) -> bool:
        if name in self.parameters:
            return True

        if self.parent is not None:
            return self.parent.has_parameter_named(name)

        return False

    def walk_type_parameters(self) -> typing.Iterator[TypeParameter]:
        yield from self.parameters.values()
        if self.parent is not None:
            yield from self.parent.walk_type_parameters()


@attr.s(kw_only=True, slots=True)
class StructField(Definition):
    name: str = attr.ib()
    type: AsgType = attr.ib()


@attr.s(kw_only=True, slots=True)
class StructDef(Definition):
    name: str = attr.ib()
    is_definition: bool = attr.ib()
    fields: dict[str, StructField] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TupleElt(Definition):
    index: int = attr.ib()
    type: AsgType = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleDef(Definition):
    name: str = attr.ib()
    is_definition: bool = attr.ib()
    elts: list[TupleElt] = attr.ib(factory=list)


UNIT = TupleDef(name="unit", is_definition=False, elts=[])
INVALID = TupleDef(name="invalid", is_definition=True, elts=[])


@attr.s(kw_only=True, slots=True)
class SumDef(Definition):
    name: str = attr.ib()
    types: dict[str, StructDef | TupleDef | AliasDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class AliasDef(Definition):
    name: str = attr.ib()
    type: AsgType | None = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: AsgType | Singleton | None = attr.ib()
    definition: LocalDef = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDef(Definition):
    name: str = attr.ib()
    parameters: dict[str, FunctionParameter] = attr.ib(factory=dict)
    returns: AsgType | Singleton = attr.ib(default=UNIT)
    body: AsgBody | None = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class ClassDef(Definition):
    name: str = attr.ib()
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class UseDef(Definition):
    type: AsgType = attr.ib(default=UNIT)
    type_class: AsgType = attr.ib(default=UNIT)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeParameter(Definition):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class LocalDef(Definition):
    name: str = attr.ib()
    node_id: int = attr.ib()


type AsgDefinition = (
    ModuleDef
    | StructField
    | StructDef
    | TupleElt
    | TupleDef
    | SumDef
    | AliasDef
    | FunctionDef
    | ClassDef
    | UseDef
)

type TypeDefinition = (
    StructDef | TupleDef | SumDef | AliasDef
)


@attr.s(kw_only=True, slots=True)
class PathSegment:
    name: str = attr.ib()
    result: AsgPathResult = attr.ib()
    arguments: list[AsgType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class DynamicPathSegment:
    name: str = attr.ib()
    arguments: list[AsgType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class Path:
    # Xyz.Abc('t).foo might be represented as
    # Path(segments=[
    #   PathSegment(name='Xyz', result=ModuleDef),
    #   PathSegment(name='Abc', result=ClassDef, arguments=TypeParameter(name='t'))
    #   PathSegment(name='foo', result=FunctionDef)
    # ])
    # Anything in the program written as a name `x` is resolved to a path.
    # Anything in a program written as `x.y` where x is not a local definition
    # is resolved to a path.
    #   When y is not a local definition, it is only valid in an executable code block,
    #   and it is resolved to Attribute (or whetever I decide to call it)
    # When there are arguments after non-local definition `y`, the result of the arguments
    # are resolved and added to the segment's arguments.
    segments: list[PathSegment | DynamicPathSegment] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class ListType:
    elt: AsgType = attr.ib()


@attr.s(kw_only=True, slots=True)
class AsgError:
    node: ast.Node = attr.ib()


type AsgType = Path | TypeParameter | ListType | StructDef | TupleDef | AsgError

type AsgPathResult = (
    LocalDef | FunctionDef | ClassDef | TypeParameter | ListType | TypeDefinition | AsgError
)


@attr.s(kw_only=True, slots=True)
class AsgCode:
    node_id: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class AsgBody:
    statements: list[Statement] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class Resolved:
    name: str = attr.ib()
    result: ResolvedSymbol | AsgError = attr.ib()


@attr.s(kw_only=True, slots=True)
class Local(AsgCode):
    local_definition: LocalDef = attr.ib()
    type: AsgType | None = attr.ib()
    value: Expression | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class For(AsgCode):
    target: Expression = attr.ib()
    iterator: Expression = attr.ib()
    body: AsgBody = attr.ib()


@attr.s(kw_only=True, slots=True)
class While(AsgCode):
    condition: Expression = attr.ib()
    body: AsgBody = attr.ib()


@attr.s(kw_only=True, slots=True)
class If(AsgCode):
    condition: Expression = attr.ib()
    body: AsgBody = attr.ib()
    else_body: AsgBody = attr.ib()


@attr.s(kw_only=True, slots=True)
class Assignment(AsgCode):
    target: Expression = attr.ib()
    type: AsgType | None = attr.ib()
    value: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class AugAssignment(AsgCode):
    target: Expression = attr.ib()
    op: ast.OperatorKind = attr.ib()
    value: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class Return(AsgCode):
    value: Expression | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class Break(AsgCode): ...


@attr.s(kw_only=True, slots=True)
class Continue(AsgCode): ...


@attr.s(kw_only=True, slots=True)
class Expr(AsgCode):
    expr: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class Lambda(AsgCode):
    function_def: FunctionDef = attr.ib()


@attr.s(kw_only=True, slots=True)
class Annotated(AsgCode):
    value: Expression = attr.ib()
    type: AsgType = attr.ib()


@attr.s(kw_only=True, slots=True)
class BoolOp(AsgCode):
    op: ast.BoolOperatorKind = attr.ib()
    values: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class BinaryOp(AsgCode):
    left: Expression = attr.ib()
    op: ast.OperatorKind = attr.ib()
    right: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class UnaryOp(AsgCode):
    op: ast.UnaryOperatorKind = attr.ib()
    operand: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class Compare(AsgCode):
    left: Expression = attr.ib()
    comparators: list[Comparator] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Comparator(AsgCode):
    op: ast.CmpOperatorKind = attr.ib()
    value: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class Call(AsgCode):
    callable: Expression = attr.ib()
    args: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Integer(AsgCode):
    value: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class Float(AsgCode):
    value: float = attr.ib()


@attr.s(kw_only=True, slots=True)
class Complex(AsgCode):
    value: complex = attr.ib()


@attr.s(kw_only=True, slots=True)
class String(AsgCode):
    value: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class Constant(AsgCode):
    kind: ast.ConstantKind = attr.ib()


@attr.s(kw_only=True, slots=True)
class Attribute(AsgCode):
    value: Expression = attr.ib()
    attr: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class Subscript(AsgCode):
    value: Expression = attr.ib()
    slices: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Struct(AsgCode):
    fields: dict[str, Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Tuple(AsgCode):
    elts: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class List(AsgCode):
    elts: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Slice(AsgCode):
    start: Expression | None = attr.ib()
    stop: Expression | None = attr.ib()
    step: Expression | None = attr.ib()


type Expression = (
    Resolved
    | Lambda
    | Annotated
    | BoolOp
    | BinaryOp
    | UnaryOp
    | Compare
    | Call
    | Integer
    | Float
    | Complex
    | String
    | Constant
    | Attribute
    | Subscript
    | Struct
    | Tuple
    | List
    | Slice
)

type Statement = (
    Local
    | For
    | While
    | If
    | Assignment
    | AugAssignment
    | Return
    | Break
    | Continue
    | Expr
)

