from __future__ import annotations

import enum
import typing

import attr

NodeId = typing.NewType("NodeId", int)


class BoolOperatorKind(enum.IntEnum):
    AND = enum.auto()
    OR = enum.auto()


class OperatorKind(enum.IntEnum):
    ADD = enum.auto()
    SUB = enum.auto()
    MULT = enum.auto()
    MATMULT = enum.auto()
    DIV = enum.auto()
    MOD = enum.auto()
    POW = enum.auto()
    LSHIFT = enum.auto()
    RSHIFT = enum.auto()
    BITOR = enum.auto()
    BITXOR = enum.auto()
    BITAND = enum.auto()
    FLOORDIV = enum.auto()


class UnaryOperatorKind(enum.IntEnum):
    INVERT = enum.auto()
    NOT = enum.auto()
    UADD = enum.auto()
    USUB = enum.auto()


class CmpOperatorKind(enum.IntEnum):
    EQ = enum.auto()
    NOTEQ = enum.auto()
    LT = enum.auto()
    LTE = enum.auto()
    GT = enum.auto()
    GTE = enum.auto()
    IS = enum.auto()
    ISNOT = enum.auto()
    IN = enum.auto()
    NOTIN = enum.auto()


class StringFlags(enum.IntFlag):
    NONE = 0
    RAW = enum.auto()
    BYTES = enum.auto()
    FORMAT = enum.auto()


@attr.s(kw_only=True, slots=True)
class Node:
    id: NodeId = attr.ib()
    start: int = attr.ib()
    end: int = attr.ib()


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
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDefNode(Node):
    name: str = attr.ib()
    parameters: list[FunctionParameterNode] = attr.ib()
    body: list[StatementNode] | None = attr.ib()
    decorators: list[ExpressionNode] = attr.ib()
    returns: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class ClassDefNode(Node):
    name: str = attr.ib()
    parameters: list[TypeParameterNode] = attr.ib()
    body: list[StatementNode] = attr.ib()
    decorators: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class UseNode(Node):
    type: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class UseAsNode(Node):
    type: ExpressionNode = attr.ib()
    type_class: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ReturnNode(Node):
    value: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class AssignNode(Node):
    target: ExpressionNode = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class AugAssignNode(Node):
    target: ExpressionNode = attr.ib()
    op: OperatorKind = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class ForNode(Node):
    target: ExpressionNode = attr.ib()
    iterator: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class WhileNode(Node):
    condition: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class IfNode(Node):
    condition: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()
    else_statement: ElseNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class ElseNode(Node):
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportNode(Node):
    names: list[AliasNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportFromNode(Node):
    module: str | None = attr.ib()
    names: list[AliasNode] = attr.ib()
    level: int | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class ExprNode(Node):
    expr: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class BreakNode(Node): ...


@attr.s(kw_only=True, slots=True)
class ContinueNode(Node): ...


@attr.s(kw_only=True, slots=True)
class LambdaParameterNode(Node):
    name: str = attr.ib()
    type: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class LambdaNode(Node):
    parameters: list[LambdaParameterNode] = attr.ib()
    returns: ExpressionNode | None = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AnnotatedNode(Node):
    value: ExpressionNode = attr.ib()
    type: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class BoolOpNode(Node):
    op: BoolOperatorKind = attr.ib()
    values: list[ExpressionNode] = attr.ib()


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
class CompareNode(Node):
    left: ExpressionNode = attr.ib()
    comparators: list[ComparatorNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComparatorNode(Node):
    op: CmpOperatorKind = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class CallNode(Node):
    callable: ExpressionNode = attr.ib()
    args: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ConstantNode(Node):
    kind: typing.Any = attr.ib()  # fix this


@attr.s(kw_only=True, slots=True)
class IntegerNode(ConstantNode):
    kind: typing.Literal[ConstantKind.INTEGER] = attr.ib(
        init=False, default=ConstantKind.INTEGER
    )
    value: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class FloatNode(ConstantNode):
    kind: typing.Literal[ConstantKind.FLOAT] = attr.ib(
        init=False, default=ConstantKind.FLOAT
    )
    value: float = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComplexNode(ConstantNode):
    kind: typing.Literal[ConstantKind.COMPLEX] = attr.ib(
        init=False, default=ConstantKind.COMPLEX
    )
    value: complex = attr.ib()


@attr.s(kw_only=True, slots=True)
class StringNode(ConstantNode):
    kind: typing.Literal[ConstantKind.STRING] = attr.ib(
        init=False, default=ConstantKind.STRING
    )
    value: str = attr.ib()
    flags: StringFlags = attr.ib()


@attr.s(kw_only=True, slots=True)
class AttributeNode(Node):
    value: ExpressionNode = attr.ib()
    attr: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class SubscriptNode(Node):
    value: ExpressionNode = attr.ib()
    slices: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class NameNode(Node):
    value: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class RecordNode(Node):
    fields: list[RecordFieldNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class RecordFieldNode(Node):
    name: str = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class ListNode(Node):
    elts: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SliceNode(Node):
    start_index: ExpressionNode | None = attr.ib()
    stop_index: ExpressionNode | None = attr.ib()
    step_index: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionParameterNode(Node):
    name: str = attr.ib()
    type: ExpressionNode = attr.ib()
    default: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class AliasNode(Node):
    name: str | None = attr.ib()
    asname: str | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class TypeParameterNode(Node):
    name: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class SelfTypeNode(Node): ...


@attr.s(kw_only=True, slots=True)
class TypeDefinitionNode(Node):
    name: str = attr.ib()
    type: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class SumTypeNode(Node):
    name: str = attr.ib()
    variants: list[SumTypeVariantNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SumTypeVariantNode(Node):
    name: str = attr.ib()
    type: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class StructTypeFieldNode(Node):
    name: str = attr.ib()
    type: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class StructTypeNode(Node):
    fields: list[StructTypeFieldNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleEltNode(Node):
    index: int = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleNode(Node):
    elts: list[TupleEltNode] = attr.ib()


type StatementNode = (
    FunctionDefNode
    | ClassDefNode
    | ForNode
    | WhileNode
    | IfNode
    | ImportNode
    | ImportFromNode
    | AssignNode
    | AugAssignNode
    | ReturnNode
    | BreakNode
    | ContinueNode
    | ExprNode
    | TypeDefinitionNode
    | SumTypeNode
    | UseNode
    | UseAsNode
)

type ExpressionNode = (
    LambdaNode
    | AnnotatedNode
    | BoolOpNode
    | BinaryOpNode
    | UnaryOpNode
    | CompareNode
    | CallNode
    | ConstantNode
    | AttributeNode
    | SubscriptNode
    | NameNode
    | RecordNode
    | TupleNode
    | ListNode
    | SliceNode
    | SelfTypeNode
    | TypeParameterNode
    | StructTypeNode
)


def walk_expressions(
    expression: ExpressionNode,
    *,
    no_recurse: tuple[type[ExpressionNode], ...] = (),
) -> typing.Generator[ExpressionNode]:
    # NOTE: This omits everything within lambda nodes because calling code
    # generally needs to run some statement handler on it, which will then
    # call this function again
    yield expression

    if type(expression) in no_recurse:
        return

    match expression:
        case AnnotatedNode():
            yield from walk_expressions(expression.value)
            yield from walk_expressions(expression.type)
        case BoolOpNode():
            for value in expression.values:
                yield from walk_expressions(value)
        case BinaryOpNode():
            yield from walk_expressions(expression.left)
            yield from walk_expressions(expression.right)
        case UnaryOpNode():
            yield from walk_expressions(expression.operand)
        case CompareNode():
            yield from walk_expressions(expression.left)
            for comparator in expression.comparators:
                yield from walk_expressions(comparator.value)
        case CallNode():
            yield from walk_expressions(expression.callable)
            for argument in expression.args:
                yield from walk_expressions(argument)
        case AttributeNode():
            yield from walk_expressions(expression.value)
        case SubscriptNode():
            yield from walk_expressions(expression.value)
            for slice in expression.slices:
                yield from walk_expressions(slice)
        case ListNode():
            for elt in expression.elts:
                yield from walk_expressions(elt)
        case TupleNode():
            for elt in expression.elts:
                yield from walk_expressions(elt.value)
        case SliceNode():
            if expression.start_index is not None:
                yield from walk_expressions(expression.start_index)

            if expression.stop_index is not None:
                yield from walk_expressions(expression.stop_index)

            if expression.step_index is not None:
                yield from walk_expressions(expression.step_index)
        case RecordNode():
            for field in expression.fields:
                yield from walk_expressions(field.value)
        case StructTypeNode():
            for field in expression.fields:
                yield from walk_expressions(field.type)
