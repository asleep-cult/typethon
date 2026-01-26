from __future__ import annotations

import attr
import enum
import typing
from itertools import count

from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast

HIR_ID_COUNT = count()


# This is the abstract semantic graph.
# It is inspired by the Rust compiler.

# The ASG is very similar to the AST, but all symbols are defined
# and resolved. Every attribute access that isn't on a local declaration
# gets resolved as well.


class Singleton(enum.Enum):
    INFERRED = enum.auto()
    NOTYPE = enum.auto()

INFERRED = Singleton.INFERRED
NOTYPE = Singleton.NOTYPE


@attr.s(kw_only=True, slots=True)
class DefId:
    id: int = attr.ib(factory=lambda: next(HIR_ID_COUNT))


@attr.s(kw_only=True, slots=True)
class AsgContext:
    diagnostics: DiagnosticReporter = attr.ib()
    fields: dict[int, AsgField] = attr.ib(factory=dict)
    generics: dict[int, Generics] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class ModuleDef(DefId):
    types: dict[str, TypeDeclaration] = attr.ib(factory=dict)
    classes: dict[str, ClassDef] = attr.ib(factory=dict)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)
    body: AsgBody | None = attr.ib(default=None)


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
    fields: dict[str, AsgType] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TupleDef(DefId):
    name: str = attr.ib()
    is_declaration: bool = attr.ib()
    elts: list[AsgType] = attr.ib(factory=list)


UNIT = TupleDef(name="unit", is_declaration=False, elts=[])
INVALID = TupleDef(name="invalid", is_declaration=True, elts=[])


@attr.s(kw_only=True, slots=True)
class SumDef(DefId):
    name: str = attr.ib()
    types: dict[str, AsgType | typing.Literal[NOTYPE]] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class AliasDef(DefId):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDef(DefId):
    name: str = attr.ib()
    parameters: dict[str, AsgType | Singleton] = attr.ib(factory=dict)
    returns: AsgType | Singleton = attr.ib(default=UNIT)
    body: AsgBody | None = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class ClassDef(DefId):
    name: str = attr.ib()
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class UseDef(DefId):
    type: AsgType = attr.ib(default=UNIT)
    type_class: AsgType = attr.ib(default=UNIT)
    functions: dict[str, FunctionDef] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeParameter(DefId):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class LocalDeclaration(DefId):
    name: str = attr.ib()
    node_id: int = attr.ib()


type AsgField = (
    ModuleDef | StructDef | TupleDef | SumDef | AliasDef | FunctionDef | ClassDef | UseDef
)

type TypeDeclaration = (
    StructDef | TupleDef | SumDef
    # AliasDef,
)


@attr.s(kw_only=True, slots=True)
class PathSegment:
    name: str = attr.ib()
    result: AsgPathResult = attr.ib()
    arguments: list[AsgType] = attr.ib(factory=list)


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

    def get_result(self) -> AsgPathResult:
        return self.segments[-1].result


@attr.s(kw_only=True, slots=True)
class ListType:
    elt: AsgType = attr.ib()


@attr.s(kw_only=True, slots=True)
class AsgError:
    node: ast.Node = attr.ib()


type AsgType = Path | ClassDef | TypeParameter | ListType | TypeDeclaration | AsgError

type AsgPathResult = (
    LocalDeclaration | FunctionDef | ClassDef | TypeParameter | ListType | TypeDeclaration | AsgField | AsgError
)


@attr.s(kw_only=True, slots=True)
class AsgCode:
    node_id: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class AsgBody:
    statements: list[Statement] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class Declaration(AsgCode):
    local_declaration: LocalDeclaration = attr.ib()
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
class CoPath(AsgCode):
    path: Path = attr.ib()


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
    callee: Expression = attr.ib()
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
    CoPath
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
    Declaration
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

