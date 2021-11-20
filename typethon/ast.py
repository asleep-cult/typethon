from __future__ import annotations

import enum
from typing import Iterable, Optional, Union

from .parser.scanner import Token


class BaseNode:
    __slots__ = ('startpos', 'endpos', 'startlineno', 'endlineno', 'linespans')

    def __new__(cls):
        self = object.__new__(cls)

        self.startpos = -1
        self.endpos = -1
        self.startlineno = -1
        self.endlineno = -1

        return self

    def set_loc(self, starttok: Token, endtok: Token) -> None:
        self.startpos = starttok.startpos
        self.endpos = endtok.endpos
        self.startlineno = starttok.startlineno
        self.endlineno = endtok.endlineno


class ModuleNode(BaseNode):
    __slots__ = ('body',)

    def __init__(self) -> None:
        self.body: list[StatementNode] = []


class FunctionDefNode(BaseNode):
    __slots__ = ('is_async', 'name', 'parameters', 'body', 'decorators', 'returns')

    def __init__(self, *, name: str) -> None:
        self.is_async = False
        self.name: str = name
        self.parameters: list[ParameterNode] = []
        self.body: list[StatementNode] = []
        self.decorators: list[ExpressionNode] = []
        self.returns: Optional[ExpressionNode] = None


class ClassDefNode(BaseNode):
    __slots__ = ('name', 'bases', 'kwargs', 'body', 'decorators')

    def __init__(self, *, name: str) -> None:
        self.name: str = name
        self.bases: list[ExpressionNode] = []
        self.kwargs: list[KeywordArgumentNode] = []
        self.body: list[StatementNode] = []
        self.decorators: list[ExpressionNode] = []


class ReturnNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self) -> None:
        self.value: Optional[ExpressionNode] = None


class DeleteNode(BaseNode):
    __slots__ = ('targets',)

    def __init__(self) -> None:
        self.targets: list[ExpressionNode] = []


class AssignNode(BaseNode):
    __slots__ = ('targets', 'value')

    def __init__(self, *, targets: list[ExpressionNode], value: ExpressionNode) -> None:
        self.targets = targets
        self.value = value


class AugAssignNode(BaseNode):
    __slots__ = ('target', 'op', 'value')

    def __init__(self, *, target: ExpressionNode, op: Operator, value: ExpressionNode) -> None:
        self.target = target
        self.op = op
        self.value = value


class AnnAssignNode(BaseNode):
    __sltos__ = ('target', 'annotation', 'value')

    def __init__(self, *, target: ExpressionNode, annotation: ExpressionNode,
                 value: ExpressionNode) -> None:
        self.target = target
        self.annotation = annotation
        self.value = value


class ForNode(BaseNode):
    __slots__ = ('is_async', 'target', 'iterator', 'body', 'elsebody')

    def __init__(self, *, target: ExpressionNode, iterator: ExpressionNode) -> None:
        self.is_async = False
        self.target = target
        self.iterator = iterator
        self.body: list[ExpressionNode] = []
        self.elsebody: list[ExpressionNode] = []


class WhileNode(BaseNode):
    __slots__ = ('condition', 'body')

    def __init__(self, *, condition: ExpressionNode) -> None:
        self.condition = condition
        self.body: list[StatementNode] = []
        self.elsebody: list[StatementNode] = []


class IfNode(BaseNode):
    __slots__ = ('condition', 'body', 'elsebody')

    def __init__(self, *, condition: ExpressionNode) -> None:
        self.condition = condition
        self.body: list[StatementNode] = []
        self.elsebody: list[StatementNode] = []


class WithNode(BaseNode):
    __slots__ = ('is_async', 'items', 'body')

    def __init__(self) -> None:
        self.is_async = False
        self.items: list[WithItemNode] = []
        self.body: list[StatementNode] = []


class RaiseNode(BaseNode):
    __slots__ = ('exc', 'cause')

    def __init__(self, *, exc: ExpressionNode, cause: ExpressionNode) -> None:
        self.exc = exc
        self.cause = cause


class TryNode(BaseNode):
    __slots__ = ('body', 'handlers', 'elsebody', 'finalbody')

    def __init__(self) -> None:
        self.body: list[StatementNode] = []
        self.handlers: list[ExceptHandlerNode] = []
        self.elsebody: list[StatementNode] = []
        self.finalbody: list[StatementNode] = []


class AssertNode(BaseNode):
    __slots__ = ('condition', 'message')

    def __init__(self, *, condition: ExpressionNode, message: Optional[str]) -> None:
        self.condition = condition
        self.message = message


class ImportNode(BaseNode):
    __slots__ = ('names',)

    def __init__(self) -> None:
        self.names: list[AliasNode] = []


class ImportFromNode(BaseNode):
    __slots__ = ('module', 'names', 'level')

    def __init__(self) -> None:
        self.module: Optional[str] = None
        self.names: list[AliasNode] = None
        self.level: Optional[int] = None


class GlobalNode(BaseNode):
    __slots__ = ('names',)

    def __init__(self) -> None:
        self.names: list[str] = []


class NonlocalNode(BaseNode):
    __slots__ = ('names',)

    def __init__(self) -> None:
        self.names: list[str] = []


class ExprNode(BaseNode):
    __slots__ = ('expr',)

    def __init__(self, *, expr: ExpressionNode) -> None:
        self.expr = expr


StatementNode = Union[
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
]


class BoolOpNode(BaseNode):
    __slots__ = ('op', 'values')

    def __init__(self, *, op: BoolOperator, values: list[ExpressionNode]) -> None:
        self.op = op
        self.values = values


class BinaryOpNode(BaseNode):
    __slots__ = ('left', 'op', 'right')

    def __init__(self, *, left: ExpressionNode, op: Operator, right: ExpressionNode) -> None:
        self.left = left
        self.op = op
        self.right = right


class UnaryOpNode(BaseNode):
    __slots__ = ('op', 'operand')

    def __init__(self, *, op: UnaryOperator, operand: ExpressionNode) -> None:
        self.op = op
        self.operand = operand


class LambdaNode(BaseNode):
    __slots__ = ('parameters', 'body')

    def __init__(self) -> None:
        self.parameters: list[ParameterNode] = []
        self.body: list[StatementNode] = []


class IfExpNode(BaseNode):
    __slots__ = ('condition', 'body', 'elsebody')

    def __init__(self, *, condition: ExpressionNode, body: ExpressionNode,
                 elsebody: ExpressionNode) -> None:
        self.condition = condition
        self.body = body
        self.elsebody = elsebody


class DictNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self) -> None:
        self.elts: list[DictElt] = []


class SetNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self) -> None:
        self.elts: list[ExpressionNode] = []


class ListCompNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(self, *, elt: ExpressionNode) -> None:
        self.elt = elt
        self.comprehensions: list[ComprehensionNode] = []


class SetCompNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(self, *, elt: ExpressionNode) -> None:
        self.elt = elt
        self.comprehensions: list[ComprehensionNode] = []


class DictCompNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(self, *, elt: DictElt) -> None:
        self.elt = elt
        self.comprehensions: list[ComprehensionNode] = []


class GeneratorExpNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(self, *, elt: DictElt) -> None:
        self.elt = elt
        self.comprehensions: list[ComprehensionNode] = []


class AwaitNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, *, value: ExpressionNode) -> None:
        self.value = value


class YieldNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self) -> None:
        self.value: Optional[ExpressionNode] = None


class YieldFromNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, *, value: ExpressionNode) -> None:
        self.value = value


class CompareNode(BaseNode):
    __slots__ = ('left', 'ops', 'comparators')

    def __init__(self, *, left: ExpressionNode, ops: list[CmpOperator],
                 comparators: list[ExpressionNode]) -> None:
        self.left = left
        self.ops = ops
        self.comparators = comparators


class CallNode(BaseNode):
    __slots__ = ('func', 'args', 'kwargs')

    def __init__(self, *, func: ExpressionNode) -> None:
        self.func = func
        self.args: list[ExpressionNode] = []
        self.kwargs: list[KeywordArgumentNode] = []


class FormattedValueNode(BaseNode):
    __slots__ = ('value', 'conversion', 'spec')

    def __init__(self, *, value: ExpressionNode) -> None:
        self.value = value
        self.conversion: Optional[int] = None
        self.spec: Optional[ExpressionNode] = None


class JoinedStrNode(BaseNode):
    __slots__ = ('values',)

    def __init__(self, *, values: list[ExpressionNode]) -> None:
        self.values = values


class ConstantNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, *, value: ConstantValueT) -> None:
        self.value = value


ConstantValueT = Union[
    None,
    Ellipsis,
    int,
    float,
    complex,
    bool,
    str,
    bytes,
    Iterable['ConstantValueT'],
]


class AttributeNode(BaseNode):
    __slots__ = ('value', 'attr', 'ctx')

    def __init__(self, *, value: ExpressionNode, attr: str, ctx: ExprContext) -> None:
        self.value = value
        self.attr = attr
        self.ctx = ctx


class SubscriptNode(BaseNode):
    __slots__ = ('value', 'slice', 'ctx')

    def __init__(self, *, value: ExpressionNode, slice: ExpressionNode, ctx: ExprContext) -> None:
        self.value = value
        self.slice = slice
        self.ctx = ctx


class StarredNode(BaseNode):
    __slots__ = ('value', 'ctx')

    def __init__(self, *, value: ExpressionNode, ctx: ExprContext) -> None:
        self.value = value
        self.ctx = ctx


class NameNode(BaseNode):
    __slots__ = ('id', 'ctx')

    def __init__(self, *, id: str, ctx: ExprContext) -> None:
        self.id = id
        self.ctx = ctx


class ListNode(BaseNode):
    __slots__ = ('elts', 'ctx')

    def __init__(self) -> None:
        self.elts: list[ExpressionNode] = []
        self.ctx = ExprContext.LOAD


class TupleNode(BaseNode):
    __slots__ = ('elts', 'ctx')

    def __init__(self):
        self.elts: list[ExpressionNode] = []
        self.ctx = ExprContext.LOAD


class SliceNode(BaseNode):
    __slots__ = ('start', 'stop', 'step')

    def __init__(self, start: Optional[int], stop: Optional[int], step: Optional[int]) -> None:
        self.start = start
        self.stop = stop
        self.step = step


ExpressionNode = Union[
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
    JoinedStrNode,
    ConstantNode,
    AttributeNode,
    SubscriptNode,
    StarredNode,
    NameNode,
    ListNode,
    TupleNode,
    SliceNode,
]


class ParameterNode(BaseNode):
    __slots__ = ('type', 'name', 'annotation', 'default')

    def __init__(self, *, type: ParameterType, name: str) -> None:
        self.type = type
        self.name = name
        self.annotation: Optional[ExpressionNode] = None
        self.default: Optional[ExpressionNode] = None


class KeywordArgumentNode(BaseNode):
    __slots__ = ('name', 'value')

    def __init__(self, *, name: Optional[str], value: ExpressionNode) -> None:
        self.name = name
        self.value = value


class WithItemNode(BaseNode):
    __slots__ = ('contextmanager', 'targets')

    def __init__(self, contextmanager: ExpressionNode) -> None:
        self.contextmanager = contextmanager
        self.targets: list[ExpressionNode] = []


class ExceptHandlerNode(BaseNode):
    __slots__ = ('type', 'target', 'body')

    def __init__(self) -> None:
        self.type: Optional[ExpressionNode] = None
        self.target: Optional[str] = None
        self.body: list[StatementNode] = []


class ComprehensionNode(BaseNode):
    __slots__ = ('is_async', 'target', 'iterator', 'ifs')

    def __init__(self, target: ExpressionNode, iterator: ExpressionNode) -> None:
        self.is_async = False
        self.target = target
        self.iterator = iterator
        self.ifs: list[ExpressionNode] = []


class AliasNode(BaseNode):
    __slots__ = ('name', 'asname')

    def __init__(self, name: str, asname: str) -> None:
        self.name = name
        self.asname = asname


class DictElt:
    __slots__ = ('key', 'value')

    def __init__(self, key: ExpressionNode, value: ExpressionNode) -> None:
        self.key = key
        self.value = value


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
