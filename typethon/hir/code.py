from __future__ import annotations

import attr

from . import hir
from ..syntax.typethon import ast

# This is the representation for executable code in the HIR. 
# It is similar to the AST but much simpler


@attr.s(kw_only=True, slots=True)
class HirCode:
    node_id: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class HirBody:
    statements: list[Statement] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class Declaration(HirCode):
    local_declaration: hir.LocalDeclaration = attr.ib()
    type: hir.HirType | None = attr.ib()
    value: Expression | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class For(HirCode):
    target: Expression = attr.ib()
    iterator: Expression = attr.ib()
    body: HirBody = attr.ib()


@attr.s(kw_only=True, slots=True)
class While(HirCode):
    condition: Expression = attr.ib()
    body: HirBody = attr.ib()


@attr.s(kw_only=True, slots=True)
class If(HirCode):
    condition: Expression = attr.ib()
    body: HirBody = attr.ib()
    else_body: HirBody


@attr.s(kw_only=True, slots=True)
class Return(HirCode):
    value: Expression | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class Break(HirCode): ...


@attr.s(kw_only=True, slots=True)
class Continue(HirCode): ...


@attr.s(kw_only=True, slots=True)
class Expr(HirCode):
    expr: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class Assignment(HirCode):
    target: Expression = attr.ib()
    value: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class AugAssignment(HirCode):
    target: Expression = attr.ib()
    op: ast.OperatorKind = attr.ib()
    value: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class BoolOp(HirCode):
    op: ast.BoolOperatorKind = attr.ib()
    values: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class BinaryOp(HirCode):
    left: Expression = attr.ib()
    op: ast.OperatorKind = attr.ib()
    right: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class UnaryOp(HirCode):
    op: ast.UnaryOperatorKind = attr.ib()
    operand: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class Compare(HirCode):
    left: Expression = attr.ib()
    comparators: list[Comparator] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Comparator(HirCode):
    op: ast.CmpOperatorKind = attr.ib()
    value: Expression = attr.ib()


@attr.s(kw_only=True, slots=True)
class Call(HirCode):
    callee: Expression = attr.ib()
    args: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Integer(HirCode):
    value: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class Float(HirCode):
    value: float = attr.ib()


@attr.s(kw_only=True, slots=True)
class Complex(HirCode):
    value: complex = attr.ib()


@attr.s(kw_only=True, slots=True)
class String(HirCode):
    value: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class Attribute(HirCode):
    value: Expression = attr.ib()
    attr: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class Subscript(HirCode):
    value: Expression = attr.ib()
    slices: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class List(HirCode):
    elts: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Tuple(HirCode):
    elts: list[Expression] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Slice(HirCode):
    start_index: Expression | None = attr.ib()
    stop_index: Expression | None = attr.ib()
    step_index: Expression | None = attr.ib()


type Expression = (
    BoolOp
    | BinaryOp
    | UnaryOp
    | Comparator
    | Call
    | Integer
    | Float
    | Complex
    | String
    | Attribute
    | Subscript
    | List
    | Tuple
    | Slice
    | hir.Path
)

type Statement = (
    Declaration
    | For
    | While
    | If
    | Return
    | Break
    | Continue
    | Expr
)
