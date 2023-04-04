from __future__ import annotations

import typing

import attr

from .. import ast
from ..atomize import atoms


@attr.s(kw_only=True, slots=True)
class AtomFlow:
    startpos: int = attr.ib()
    endpos: int = attr.ib()
    atom: atoms.Atom = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionFlow(AtomFlow):
    decorators: typing.List[AtomFlow] = attr.ib()
    body: typing.List[AtomFlow] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ReturnFlow(AtomFlow):
    value: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class ExprFlow(AtomFlow):
    expression: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class BoolOpFlow(AtomFlow):
    op: ast.BoolOperator = attr.ib()
    operands: typing.List[AtomFlow] = attr.ib()


@attr.s(kw_only=True, slots=True)
class BinaryOpFlow(AtomFlow):
    left: AtomFlow = attr.ib()
    op: ast.Operator = attr.ib()
    right: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class UnaryOpFlow(AtomFlow):
    op: ast.UnaryOperator = attr.ib()
    operand: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class IfExpFlow(AtomFlow):
    condition: AtomFlow = attr.ib()
    body: AtomFlow = attr.ib()
    else_body: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictElt:
    key: typing.Optional[AtomFlow] = attr.ib()
    value: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictFlow(AtomFlow):
    atom: atoms.DictAtom = attr.ib()
    elts: typing.List[DictElt] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SetFlow(AtomFlow):
    atom: atoms.SetAtom = attr.ib()
    elts: typing.List[AtomFlow] = attr.ib()


@attr.s(kw_only=True, slots=True)
class Comparator:
    op: ast.CmpOperator = attr.ib()
    operand: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class CompareFlow(AtomFlow):
    left: AtomFlow = attr.ib()
    comparators: typing.List[Comparator] = attr.ib()


@attr.s(kw_only=True, slots=True)
class KeywordArgument:
    name: typing.Optional[str] = attr.ib()
    value: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class CallFlow(AtomFlow):
    function: AtomFlow = attr.ib()
    arguments: typing.List[AtomFlow] = attr.ib()
    keywords: typing.List[KeywordArgument] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AttributeFlow(AtomFlow):
    value: AtomFlow = attr.ib()
    attribute: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class SubscriptFlow(AtomFlow):
    value: AtomFlow = attr.ib()
    slice: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class StarredFlow(AtomFlow):
    value: AtomFlow = attr.ib()


@attr.s(kw_only=True, slots=True)
class NameFlow(AtomFlow):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class ListFlow(AtomFlow):
    atom: atoms.ListAtom = attr.ib()
    values: typing.List[AtomFlow] = attr.ib()


StatementFlow = typing.Union[
    FunctionFlow,
    ExprFlow,
]

ExpressionFlow = typing.Union[
    BoolOpFlow,
    BinaryOpFlow,
    UnaryOpFlow,
    IfExpFlow,
    DictFlow,
    SetFlow,
    CompareFlow,
    CallFlow,
    AttributeFlow,
    SubscriptFlow,
    StarredFlow,
    NameFlow,
    ListFlow,
]
