from __future__ import annotations

import enum
import typing

import attr


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
    start: int = attr.ib()
    end: int = attr.ib()


class ConstandKind(enum.IntEnum):
    TRUE = enum.auto()
    FALSE = enum.auto()
    NONE = enum.auto()
    ELLIPSIS = enum.auto()
    INTEGER = enum.auto()
    FLOAT = enum.auto()
    COMPLEX = enum.auto()
    STRING = enum.auto()
    BYTES = enum.auto()


class ParameterKind(enum.IntEnum):
    ARG = enum.auto()
    VARARG = enum.auto()
    VARKWARG = enum.auto()
    POSONLY = enum.auto()
    KWONLY = enum.auto()


@attr.s(kw_only=True, slots=True)
class FunctionDefNode(Node):
    is_async: bool = attr.ib()
    name: str = attr.ib()
    parameters: list[FunctionParameterNode] = attr.ib()
    body: typing.Optional[list[StatementNode]] = attr.ib()
    decorators: list[ExpressionNode] = attr.ib()
    returns: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ClassDefNode(Node):
    name: str = attr.ib()
    bases: list[ExpressionNode] = attr.ib()
    kwargs: list[KeywordArgumentNode] = attr.ib()
    # meta: typing.Optional[ExpressionNode] = attr.ib()
    body: list[StatementNode] = attr.ib()
    decorators: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ReturnNode(Node):
    value: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class DeleteNode(Node):
    targets: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AssignNode(Node):
    targets: list[ExpressionNode] = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class AugAssignNode(Node):
    target: ExpressionNode = attr.ib()
    op: OperatorKind = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class AnnAssignNode(Node):
    target: ExpressionNode = attr.ib()
    annotation: ExpressionNode = attr.ib()
    value: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ForNode(Node):
    is_async: bool = attr.ib()
    target: ExpressionNode = attr.ib()
    iterator: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()
    else_body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class WhileNode(Node):
    condition: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()
    else_body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class IfNode(Node):
    condition: ExpressionNode = attr.ib()
    body: list[StatementNode] = attr.ib()
    else_body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class WithNode(Node):
    is_async: bool = attr.ib()
    items: list[WithItemNode] = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class RaiseNode(Node):
    exc: ExpressionNode | None = attr.ib()
    cause: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class TryNode(Node):
    body: list[StatementNode] = attr.ib()
    handlers: list[ExceptHandlerNode] = attr.ib()
    else_body: list[StatementNode] = attr.ib()
    final_body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AssertNode(Node):
    condition: ExpressionNode = attr.ib()
    message: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportNode(Node):
    names: list[AliasNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportFromNode(Node):
    module: str | None = attr.ib()
    names: list[AliasNode] = attr.ib()
    level: int | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class GlobalNode(Node):
    names: list[str] = attr.ib()


@attr.s(kw_only=True, slots=True)
class NonlocalNode(Node):
    names: list[str] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ExprNode(Node):
    expr: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class PassNode(Node): ...


@attr.s(kw_only=True, slots=True)
class BreakNode(Node): ...


@attr.s(kw_only=True, slots=True)
class ContinueNode(Node): ...


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
class LambdaNode(Node):
    parameters: list[FunctionParameterNode] = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class IfExpNode(Node):
    body: ExpressionNode = attr.ib()
    condition: ExpressionNode = attr.ib()
    else_body: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictNode(Node):
    elts: list[DictElt] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SetNode(Node):
    elts: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ListCompNode(Node):
    elt: ExpressionNode = attr.ib()
    comprehensions: list[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SetCompNode(Node):
    elt: ExpressionNode = attr.ib()
    comprehensions: list[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictCompNode(Node):
    elt: DictElt = attr.ib()
    comprehensions: list[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class GeneratorExpNode(Node):
    elt: ExpressionNode = attr.ib()
    comprehensions: list[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AwaitNode(Node):
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class YieldNode(Node):
    value: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class YieldFromNode(Node):
    value: ExpressionNode = attr.ib()


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
    func: ExpressionNode = attr.ib()
    args: list[ExpressionNode] = attr.ib()
    kwargs: list[KeywordArgumentNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FormattedValueNode(Node):
    value: ExpressionNode = attr.ib()
    conversion: int | None = attr.ib()
    spec: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class ConstantNode(Node):
    type: typing.Any = attr.ib()  # fix this


@attr.s(kw_only=True, slots=True)
class IntegerNode(ConstantNode):
    type: typing.Literal[ConstandKind.INTEGER] = attr.ib(
        init=False, default=ConstandKind.INTEGER
    )
    value: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class FloatNode(ConstantNode):
    type: typing.Literal[ConstandKind.FLOAT] = attr.ib(
        init=False, default=ConstandKind.FLOAT
    )
    value: float = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComplexNode(ConstantNode):
    type: typing.Literal[ConstandKind.COMPLEX] = attr.ib(
        init=False, default=ConstandKind.COMPLEX
    )
    value: complex = attr.ib()


@attr.s(kw_only=True, slots=True)
class StringNode(ConstantNode):
    type: typing.Literal[ConstandKind.STRING] = attr.ib(
        init=False, default=ConstandKind.STRING
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
    slice: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class StarredNode(Node):
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class NameNode(Node):
    value: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class ListNode(Node):
    elts: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleNode(Node):
    elts: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SliceNode(Node):
    start_index: ExpressionNode | None = attr.ib()
    stop_index: ExpressionNode | None = attr.ib()
    step_index: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionParameterNode(Node):
    name: str = attr.ib()
    kind: ParameterKind = attr.ib()
    annotation: ExpressionNode | None = attr.ib()
    default: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class KeywordArgumentNode(Node):
    name: str | None = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class WithItemNode(Node):
    contextmanager: ExpressionNode = attr.ib()
    target: ExpressionNode | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class ExceptHandlerNode(Node):
    type: ExpressionNode | None = attr.ib()
    target: str | None = attr.ib()
    body: list[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComprehensionNode(Node):
    is_async: bool = attr.ib()
    target: ExpressionNode = attr.ib()
    iterator: ExpressionNode = attr.ib()
    conditions: list[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AliasNode(Node):
    name: str | None = attr.ib()
    asname: str | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictElt(Node):
    key: ExpressionNode | None = attr.ib()
    value: ExpressionNode = attr.ib()


type StatementNode = (
    FunctionDefNode
    | ClassDefNode
    | ReturnNode
    | DeleteNode
    | AssignNode
    | AugAssignNode
    | AnnAssignNode
    | ForNode
    | WhileNode
    | IfNode
    | WithNode
    | RaiseNode
    | TryNode  # RETAIN?
    | AssertNode  # RETAIN?
    | ImportNode
    | ImportFromNode
    | GlobalNode  # RETAIN?
    | NonlocalNode  # RETAIN?
    | ExprNode
    | PassNode
    | BreakNode
    | ContinueNode
)

type ExpressionNode = (
    BoolOpNode
    | BinaryOpNode
    | UnaryOpNode
    | LambdaNode
    | IfExpNode
    | DictNode
    | SetNode
    | ListCompNode
    | SetCompNode
    | DictCompNode
    | GeneratorExpNode
    | AwaitNode
    | YieldNode
    | YieldFromNode
    | CompareNode
    | CallNode
    | FormattedValueNode
    | ConstantNode
    | AttributeNode
    | SubscriptNode
    | StarredNode
    | NameNode
    | ListNode
    | TupleNode
    | SliceNode
)
