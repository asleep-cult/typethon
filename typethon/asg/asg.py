from __future__ import annotations

import typing
from itertools import count

import attr

from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast
from .indexing import DefIndex, DefIndexing
from .resolution import DefKind, DefResult, LocalResult, ResolvedSymbol, SymbolResolver

# This is the abstract semantic graph.
# It is inspired by the Rust compiler.

# The ASG is very similar to the AST, but all symbols are defined
# and resolved. Every attribute access that isn't on a local definition
# gets resolved as well.

DefinitionId = typing.NewType("DefinitionId", int)


@attr.s(kw_only=True, slots=True)
class Definition:
    def_id: DefinitionId = attr.ib()


@attr.s()
class AsgContext:
    # A container that primarily keeps tracks of all definitions lowered
    # regardless of where they are located in the code.
    # A definition is any one of the following:
    #   xx.tpy: ModuleDef
    #   type XX = ...: StructDef/TupleDef/AliasDef/SumDef
    #   def xx(...) -> ...: FunctionDef
    #   use XX [for YY]: UseDef

    diagnostics: DiagnosticReporter = attr.ib()
    def_id_counter: count[int] = attr.ib(factory=count)
    def_index: DefIndexing = attr.ib(init=False)
    root_index: DefIndex = attr.ib(init=False)
    defs: dict[DefinitionId, AsgDefinition] = attr.ib(factory=dict)
    def_parents: dict[DefinitionId, DefinitionId] = attr.ib(factory=dict)
    def_nodes: dict[ast.NodeId, DefinitionId] = attr.ib(factory=dict)
    node_defs: dict[DefinitionId, ast.Node] = attr.ib(factory=dict, repr=False)
    sym_resolver: SymbolResolver = attr.ib(init=False)
    syms_resolved: dict[ast.NodeId, ResolvedSymbol] = attr.ib(factory=dict)

    def __attrs_post_init__(self) -> None:
        self.def_index = DefIndexing(asg_ctx=self)
        self.sym_resolver = SymbolResolver(asg_ctx=self)

    def initialize(self, module: ast.ModuleNode) -> None:
        def_id = self.def_id(module)

        self.root_index = DefIndex(parent=None, def_id=def_id, node_id=module.id)
        self.def_index.def_kinds[def_id] = DefKind.MODULE
        self.def_index.index_block(self.root_index, module.body)

        self.sym_resolver.resolve_symbols_for_module(module)

    def def_id(self, node: ast.Node) -> DefinitionId:
        if node.id in self.def_nodes:
            return self.def_nodes[node.id]

        def_id = DefinitionId(next(self.def_id_counter))
        self.def_nodes[node.id] = def_id
        self.node_defs[def_id] = node
        return def_id

    def def_kind(self, def_id: DefinitionId) -> DefKind:
        return self.def_index.def_kinds[def_id]

    def def_id_for_node_id(self, node_id: ast.NodeId) -> DefinitionId:
        return self.def_nodes[node_id]

    def node_for_def_id(self, def_id: DefinitionId) -> ast.Node:
        return self.node_defs[def_id]

    def definition_for_node(self, node_id: ast.NodeId) -> AsgDefinition:
        def_id = self.def_nodes[node_id]
        return self.defs[def_id]

    def parent_id(self, def_id: DefinitionId) -> DefinitionId | None:
        if def_id in self.def_parents:
            return self.def_parents[def_id]

    def parent_definition(self, def_id: DefinitionId) -> AsgDefinition | None:
        parent_id = self.parent_id(def_id)
        if parent_id is not None:
            return self.definition(parent_id)

    def record_parent(self, def_id: DefinitionId, parent_id: DefinitionId) -> None:
        self.def_parents[def_id] = parent_id

    def record_node(self, def_id: DefinitionId, node_id: ast.NodeId) -> None:
        self.def_nodes[node_id] = def_id

    def definition(self, def_id: DefinitionId) -> AsgDefinition:
        return self.defs[def_id]


@attr.s(kw_only=True, slots=True)
class ModuleDef(Definition):
    types: dict[str, TypeDefinition] = attr.ib(factory=dict)
    classes: dict[str, ClassDef] = attr.ib(factory=dict)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)
    body: AsgBody | None = attr.ib(default=None)


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


@attr.s(kw_only=True, slots=True)
class SumVariant(Definition):
    name: str = attr.ib()
    type: StructDef | TupleDef | AliasDef | None = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class SumDef(Definition):
    name: str = attr.ib()
    variants: dict[str, SumVariant] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class AliasDef(Definition):
    name: str = attr.ib()
    type: AsgType | None = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: AsgType | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDef(Definition):
    name: str = attr.ib()
    parameters: dict[str, FunctionParameter] = attr.ib(factory=dict)
    returns: AsgType | None = attr.ib()
    body: AsgBody | None = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class ClassDef(Definition):
    name: str = attr.ib()
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class UseDef(Definition):
    type: AsgType = attr.ib()
    type_class: AsgType | None = attr.ib()
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeParameterDef(Definition):
    name: str = attr.ib()


type AsgDefinition = (
    ModuleDef
    | StructField
    | StructDef
    | TupleElt
    | TupleDef
    | SumDef
    | SumVariant
    | TypeParameterDef
    | AliasDef
    | FunctionDef
    | ClassDef
    | UseDef
)

type TypeDefinition = StructDef | TupleDef | SumDef | AliasDef


@attr.s(kw_only=True, slots=True)
class PathSegment:
    name: str = attr.ib()
    result: DefResult = attr.ib()
    arguments: list[AsgType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class DynamicPathSegment:
    name: str = attr.ib()
    arguments: list[AsgType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class ExprPathSegment:
    expression: TypeParameterDef | ListType | StructDef | TupleDef = attr.ib()
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
    segments: list[PathSegment | DynamicPathSegment | ExprPathSegment] = attr.ib(
        factory=list
    )


@attr.s(kw_only=True, slots=True)
class ListType:
    elt: AsgType = attr.ib()


@attr.s(kw_only=True, slots=True)
class AsgError:
    node: ast.Node = attr.ib()


type AsgType = Path | ListType | StructDef | TupleDef | TypeParameterDef


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
    local_definition: LocalResult = attr.ib()
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
