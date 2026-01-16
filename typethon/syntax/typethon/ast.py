from __future__ import annotations

import attr
import typing
import enum
from ..ast import (
    ParameterKind,
    BoolOperatorKind,
    OperatorKind,
    UnaryOperatorKind,
    CmpOperatorKind,
    StringFlags,
    Node,
)

# TODO: Seperate LHS expression,
# Rename *Type enums to *Kind


class ConstantKind(enum.IntEnum):
    TRUE = enum.auto()
    FALSE = enum.auto()
    ELLIPSIS = enum.auto()
    INTEGER = enum.auto()
    FLOAT = enum.auto()
    COMPLEX = enum.auto()
    STRING = enum.auto()
    BYTES = enum.auto()


@attr.s(kw_only=True, slots=True)
class ModuleNode(Node):
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDefNode(Node):
    name: str = attr.ib()
    parameters: typing.List[FunctionParameterNode] = attr.ib()
    body: typing.Optional[typing.List[StatementNode]] = attr.ib()
    decorators: typing.List[ExpressionNode] = attr.ib()
    returns: TypeExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class ClassDefNode(Node):
    name: str = attr.ib()
    parameters: typing.List[TypeParameterNode] = attr.ib()
    body: typing.List[StatementNode] = attr.ib()
    decorators: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class UseNode(Node):
    type: TypeExpressionNode = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class UseForNode(Node):
    type_class: TypeExpressionNode = attr.ib()
    type: TypeExpressionNode = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ReturnNode(Node):
    value: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AssignNode(Node):
    targets: typing.List[ExpressionNode] = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class AugAssignNode(Node):
    target: ExpressionNode = attr.ib()
    op: OperatorKind = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class AnnAssignNode(Node):
    target: ExpressionNode = attr.ib()
    annotation: TypeExpressionNode = attr.ib()
    value: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ForNode(Node):
    target: ExpressionNode = attr.ib()
    iterator: ExpressionNode = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class WhileNode(Node):
    condition: ExpressionNode = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class IfNode(Node):
    condition: ExpressionNode = attr.ib()
    body: typing.List[StatementNode] = attr.ib()
    else_body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportNode(Node):
    names: typing.List[AliasNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportFromNode(Node):
    module: typing.Optional[str] = attr.ib()
    names: typing.List[AliasNode] = attr.ib()
    level: typing.Optional[int] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ExprNode(Node):
    expr: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class PassNode(Node):
    ...


@attr.s(kw_only=True, slots=True)
class BreakNode(Node):
    ...


@attr.s(kw_only=True, slots=True)
class ContinueNode(Node):
    ...


@attr.s(kw_only=True, slots=True)
class LambdaParameterNode(Node):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class ExpressionLambdaNode(Node):
    parameters: typing.List[LambdaParameterNode] = attr.ib()
    body: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class BlockLambdaNode(Node):
    parameters: typing.List[LambdaParameterNode] = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class BoolOpNode(Node):
    op: BoolOperatorKind = attr.ib()
    values: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class BinaryOpNode(Node):
    left: ExpressionNode = attr.ib()
    op: OperatorKind = attr.ib()
    right: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class UnaryOpNode(Node):
    op: UnaryOperatorKind = attr.ib()
    operand: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictNode(Node):
    elts: typing.List[DictElt] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SetNode(Node):
    elts: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class CompareNode(Node):
    left: ExpressionNode = attr.ib()
    comparators: typing.List[ComparatorNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComparatorNode(Node):
    op: CmpOperatorKind = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class CallNode(Node):
    callee: ExpressionNode = attr.ib()
    args: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FormattedValueNode(Node):
    value: ExpressionNode = attr.ib()
    conversion: typing.Optional[int] = attr.ib()
    spec: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ConstantNode(Node):
    kind: typing.Any = attr.ib()  # fix this


@attr.s(kw_only=True, slots=True)
class IntegerNode(ConstantNode):
    kind: typing.Literal[ConstantKind.INTEGER] = attr.ib(init=False, default=ConstantKind.INTEGER)
    value: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class FloatNode(ConstantNode):
    kind: typing.Literal[ConstantKind.FLOAT] = attr.ib(init=False, default=ConstantKind.FLOAT)
    value: float = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComplexNode(ConstantNode):
    kind: typing.Literal[ConstantKind.COMPLEX] = attr.ib(init=False, default=ConstantKind.COMPLEX)
    value: complex = attr.ib()


@attr.s(kw_only=True, slots=True)
class StringNode(ConstantNode):
    kind: typing.Literal[ConstantKind.STRING] = attr.ib(init=False, default=ConstantKind.STRING)
    value: str = attr.ib()
    flags: StringFlags = attr.ib()


@attr.s(kw_only=True, slots=True)
class AttributeNode(Node):
    value: ExpressionNode = attr.ib()
    attr: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class SubscriptNode(Node):
    value: ExpressionNode = attr.ib()
    slices: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class NameNode(Node):
    value: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class ListNode(Node):
    elts: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleNode(Node):
    elts: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SliceNode(Node):
    start_index: typing.Optional[ExpressionNode] = attr.ib()
    stop_index: typing.Optional[ExpressionNode] = attr.ib()
    step_index: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionParameterNode(Node):
    name: str = attr.ib()
    kind: ParameterKind = attr.ib()
    annotation: TypeExpressionNode = attr.ib()
    default: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AliasNode(Node):
    name: typing.Optional[str] = attr.ib()
    asname: typing.Optional[str] = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictElt(Node):
    key: typing.Optional[ExpressionNode] = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeParameterNode(Node):
    name: str = attr.ib()
    constraint: typing.Optional[TypeExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SelfTypeNode(Node):
    ...


@attr.s(kw_only=True, slots=True)
class TypeCallNode(Node):
    type: TypeExpressionNode = attr.ib()
    args: typing.List[TypeExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeAttributeNode(Node):
    value: TypeExpressionNode = attr.ib()
    attr: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class ListTypeNode(Node):
    elt: TypeExpressionNode = attr.ib()
    # size: typing.Optional[int] = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class StructFieldNode(Node):
    name: str = attr.ib()
    type: TypeExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class StructTypeNode(Node):
    name: str = attr.ib()
    fields: typing.List[StructFieldNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleTypeNode(Node):
    name: str = attr.ib()
    elts: typing.List[TypeExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class UnionTypeNode(Node):
    name: str = attr.ib()
    types: typing.List[TypeStatementNode] = attr.ib()


StatementNode = typing.Union[
    FunctionDefNode,
    ClassDefNode,
    ReturnNode,
    AssignNode,
    AugAssignNode,
    AnnAssignNode,
    ForNode,
    WhileNode,
    IfNode,
    ImportNode,
    ImportFromNode,
    ExprNode,
    PassNode,
    BreakNode,
    ContinueNode,
    StructTypeNode,
    TupleTypeNode,
    UseNode,
    UseForNode,
]

ExpressionNode = typing.Union[
    ExpressionLambdaNode,
    BlockLambdaNode,
    BoolOpNode,
    BinaryOpNode,
    UnaryOpNode,
    DictNode,
    SetNode,
    CompareNode,
    CallNode,
    FormattedValueNode,
    ConstantNode,
    AttributeNode,
    SubscriptNode,
    NameNode,
    ListNode,
    TupleNode,
    SliceNode,
]

TypeStatementNode = typing.Union[
    StructTypeNode,
    TupleTypeNode,
    UnionTypeNode,
]

TypeExpressionNode = typing.Union[
    NameNode,
    SelfTypeNode,
    TypeParameterNode,
    TypeCallNode,
    TypeAttributeNode,
    ListTypeNode,
]
