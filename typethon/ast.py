from __future__ import annotations

import enum
import typing

import attr


class ConstantType(enum.Enum):
    TRUE = enum.auto()
    FALSE = enum.auto()
    NONE = enum.auto()
    ELLIPSIS = enum.auto()
    INTEGER = enum.auto()
    FLOAT = enum.auto()
    COMPLEX = enum.auto()
    STRING = enum.auto()
    BYTES = enum.auto()


class ParameterType(enum.IntEnum):
    ARG = enum.auto()
    VARARG = enum.auto()
    VARKWARG = enum.auto()


class ExprContext(enum.IntEnum):
    LOAD = enum.auto()
    STORE = enum.auto()
    DELETE = enum.auto()


class BoolOperator(enum.IntEnum):
    AND = enum.auto()
    OR = enum.auto()


class Operator(enum.IntEnum):
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


class UnaryOperator(enum.IntEnum):
    INVERT = enum.auto()
    NOT = enum.auto()
    UADD = enum.auto()
    USUB = enum.auto()


class CmpOperator(enum.IntEnum):
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


@attr.s(kw_only=True, slots=True)
class Node:
    startpos: int = attr.ib()
    endpos: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class StatementList(Node):
    statements: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ModuleNode(Node):
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FunctionDefNode(Node):
    is_async: bool = attr.ib()
    name: str = attr.ib()
    parameters: typing.List[ParameterNode] = attr.ib()
    body: typing.List[StatementNode] = attr.ib()
    decorators: typing.List[ExpressionNode] = attr.ib()
    returns: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ClassDefNode(Node):
    name: str = attr.ib()
    bases: typing.List[ExpressionNode] = attr.ib()
    kwargs: typing.List[KeywordArgumentNode] = attr.ib()
    decorators: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ReturnNode(Node):
    value: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class DeleteNode(Node):
    targets: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AssignNode(Node):
    targets: typing.List[ExpressionNode] = attr.ib()
    value: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AugAssignNode(Node):
    target: ExpressionNode = attr.ib()
    op: Operator = attr.ib()
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
    body: typing.List[StatementNode] = attr.ib()
    else_body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class WhileNode(Node):
    condition: ExpressionNode = attr.ib()
    body: typing.List[StatementNode] = attr.ib()
    else_body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class IfNode(Node):
    condition: ExpressionNode
    body: typing.List[StatementNode]
    else_body: typing.List[StatementNode]


@attr.s(kw_only=True, slots=True)
class WithNode(Node):
    is_async: bool = attr.ib()
    items: typing.List[WithItemNode] = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class RaiseNode(Node):
    exc: typing.Optional[ExpressionNode] = attr.ib()
    cause: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TryNode(Node):
    body: typing.List[StatementNode] = attr.ib()
    handlers: typing.List[ExceptHandlerNode] = attr.ib()
    else_body: typing.List[StatementNode] = attr.ib()
    final_body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AssertNode(Node):
    condition: ExpressionNode = attr.ib()
    message: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportNode(Node):
    names: typing.List[AliasNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ImportFromNode(Node):
    module: typing.Optional[str] = attr.ib()
    names: typing.List[AliasNode] = attr.ib()
    level: typing.Optional[int] = attr.ib()


@attr.s(kw_only=True, slots=True)
class GlobalNode(Node):
    names: typing.List[str] = attr.ib()


@attr.s(kw_only=True, slots=True)
class NonlocalNode(Node):
    names: typing.List[str] = attr.ib()


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
class BoolOpNode(Node):
    op: BoolOperator = attr.ib()
    values: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class BinaryOpNode(Node):
    left: ExpressionNode = attr.ib()
    op: Operator = attr.ib()
    right: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class UnaryOpNode(Node):
    op: UnaryOperator = attr.ib()
    operand: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class LambdaNode(Node):
    parameters: typing.List[ParameterNode] = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class IfExpNode(Node):
    body: ExpressionNode = attr.ib()
    condition: ExpressionNode = attr.ib()
    else_body: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictNode(Node):
    elts: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SetNode(Node):
    elts: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ListCompNode(Node):
    elt: ExpressionNode = attr.ib()
    comprehensions: typing.List[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SetCompNode(Node):
    elt: ExpressionNode = attr.ib()
    comprehensions: typing.List[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictCompNode(Node):
    elt: DictElt = attr.ib()
    comprehensions: typing.List[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class GeneratorExpNode(Node):
    elt: DictElt = attr.ib()
    comprehensions: typing.List[ComprehensionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AwaitNode(Node):
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class YieldNode(Node):
    value: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class YieldFromNode(Node):
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class CompareNode(Node):
    left: ExpressionNode = attr.ib()
    comparators: typing.List[ComparatorNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComparatorNode(Node):
    op: CmpOperator = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class CallNode(Node):
    func: ExpressionNode = attr.ib()
    args: typing.List[ExpressionNode] = attr.ib()
    kwargs: typing.List[KeywordArgumentNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class FormattedValueNode(Node):
    value: ExpressionNode = attr.ib()
    conversion: typing.Optional[int] = attr.ib()
    spec: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ConstantNode(Node):
    type: ConstantType = attr.ib()


@attr.s(kw_only=True, slots=True)
class IntegerNode(ConstantNode):
    type: typing.Literal[ConstantType.INTEGER] = attr.ib(init=False, default=ConstantType.INTEGER)
    value: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class FloatNode(ConstantNode):
    type: typing.Literal[ConstantType.FLOAT] = attr.ib(init=False, default=ConstantType.FLOAT)
    value: float = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComplexNode(ConstantNode):
    type: typing.Literal[ConstantType.FLOAT] = attr.ib(init=False, default=ConstantType.COMPLEX)
    value: complex = attr.ib()


@attr.s(kw_only=True, slots=True)
class StringNode(ConstantNode):
    type: typing.Literal[ConstantType.STRING] = attr.ib(init=False, default=ConstantType.STRING)
    value: str = attr.ib()


@attr.s(kw_only=True, slots=True)
class BytesNode(ConstantNode):
    type: typing.Literal[ConstantType.BYTES] = attr.ib(init=False, default=ConstantType.BYTES)
    value: bytes = attr.ib()


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
    elts: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TupleNode(Node):
    elts: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class SliceNode(Node):
    start: typing.Optional[int] = attr.ib()
    stop: typing.Optional[int] = attr.ib()
    step: typing.Optional[int] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ParameterNode(Node):
    name: str = attr.ib()
    type: ParameterType = attr.ib()
    annotation: typing.Optional[ExpressionNode] = attr.ib()
    default: typing.Optional[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class KeywordArgumentNode(Node):
    name: typing.Optional[str] = attr.ib()
    value: ExpressionNode = attr.ib()


@attr.s(kw_only=True, slots=True)
class WithItemNode(Node):
    contextmanager: ExpressionNode = attr.ib()
    targets: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ExceptHandlerNode(Node):
    type: typing.Optional[ExpressionNode] = attr.ib()
    target: typing.Optional[str] = attr.ib()
    body: typing.List[StatementNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComprehensionNode(Node):
    is_async: bool = attr.ib()
    target: ExpressionNode = attr.ib()
    iterator: ExpressionNode = attr.ib()
    conditions: typing.List[ExpressionNode] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AliasNode(Node):
    name: str = attr.ib()
    asname: typing.Optional[str] = attr.ib()


@attr.s(kw_only=True, slots=True)
class DictElt(Node):
    key: ExpressionNode = attr.ib()
    value: ExpressionNode = attr.ib()


StatementNode = typing.Union[
    StatementList,
    FunctionDefNode,
    ClassDefNode,
    ReturnNode,
    DeleteNode,
    AssignNode,
    AugAssignNode,
    AnnAssignNode,
    ForNode,
    WhileNode,
    IfNode,
    WithNode,
    RaiseNode,
    TryNode,
    AssertNode,
    ImportNode,
    ImportFromNode,
    GlobalNode,
    NonlocalNode,
    ExprNode,
    PassNode,
    BreakNode,
    ContinueNode,
]

ExpressionNode = typing.Union[
    BoolOpNode,
    BinaryOpNode,
    UnaryOpNode,
    LambdaNode,
    IfExpNode,
    DictNode,
    SetNode,
    ListCompNode,
    SetCompNode,
    DictCompNode,
    GeneratorExpNode,
    AwaitNode,
    YieldNode,
    YieldFromNode,
    CompareNode,
    CallNode,
    FormattedValueNode,
    ConstantNode,
    AttributeNode,
    SubscriptNode,
    StarredNode,
    NameNode,
    ListNode,
    TupleNode,
    SliceNode,
]
