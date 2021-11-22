from __future__ import annotations

import enum
from typing import Optional, Union

from .parser.scanner import Token


class BaseNode:
    __slots__ = ('startpos', 'endpos', 'startlineno', 'endlineno', 'linespans')

    def __new__(cls, *args, **kwargs):
        self = object.__new__(cls)

        self.startpos = -1
        self.endpos = -1
        self.startlineno = -1
        self.endlineno = -1

        return self

    def set_loc(self, starttok: Token, endtok: Optional[Token] = None) -> None:
        if endtok is None:
            endtok = starttok

        self.startpos = starttok.startpos
        self.endpos = endtok.endpos
        self.startlineno = starttok.startlineno
        self.endlineno = endtok.endlineno

        return self

    def __repr__(self):
        attrs = ', '.join(f'{name}={getattr(self, name)}' for name in self.__class__.__slots__
                          if name not in BaseNode.__slots__)
        if not attrs:
            return f'<{self.__class__.__name__}>'
        return f'<{self.__class__.__name__} {attrs}>'


class ModuleNode(BaseNode):
    __slots__ = ('body',)

    def __init__(self) -> None:
        self.body: list[StatementNode] = []


class StatementList(BaseNode):
    __slots__ = ('statements',)

    def __init__(self) -> None:
        self.statements: list[StatementNode] = []


class FunctionDefNode(BaseNode):
    __slots__ = ('is_async', 'name', 'parameters', 'suite', 'decorators', 'returns')

    def __init__(self, *, name: str) -> None:
        self.is_async = False
        self.name: str = name
        self.parameters: list[ParameterNode] = []
        self.suite: list[StatementNode] = []
        self.decorators: list[ExpressionNode] = []
        self.returns: Optional[ExpressionNode] = None


class ClassDefNode(BaseNode):
    __slots__ = ('name', 'bases', 'kwargs', 'suite', 'decorators')

    def __init__(self, *, name: str) -> None:
        self.name: str = name
        self.bases: list[ExpressionNode] = []
        self.kwargs: list[KeywordArgumentNode] = []
        self.suite: list[StatementNode] = []
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
    __slots__ = ('is_async', 'target', 'iterator', 'suite', 'elsesuite')

    def __init__(self, *, target: ExpressionNode, iterator: ExpressionNode) -> None:
        self.is_async = False
        self.target = target
        self.iterator = iterator
        self.suite: list[ExpressionNode] = []
        self.elsesuite: list[ExpressionNode] = []


class WhileNode(BaseNode):
    __slots__ = ('condition', 'suite')

    def __init__(self, *, condition: ExpressionNode) -> None:
        self.condition = condition
        self.suite: list[StatementNode] = []
        self.elsesuite: list[StatementNode] = []


class IfNode(BaseNode):
    __slots__ = ('condition', 'suite', 'elsesuite')

    def __init__(self, *, condition: ExpressionNode) -> None:
        self.condition = condition
        self.suite: list[StatementNode] = []
        self.elsesuite: list[StatementNode] = []


class WithNode(BaseNode):
    __slots__ = ('is_async', 'items', 'suite')

    def __init__(self) -> None:
        self.is_async = False
        self.items: list[WithItemNode] = []
        self.suite: list[StatementNode] = []


class RaiseNode(BaseNode):
    __slots__ = ('exc', 'cause')

    def __init__(self) -> None:
        self.exc: Optional[ExpressionNode] = None
        self.cause: Optional[ExpressionNode] = None


class TryNode(BaseNode):
    __slots__ = ('suite', 'handlers', 'elsesuite', 'finalsuite')

    def __init__(self) -> None:
        self.suite: list[StatementNode] = []
        self.handlers: list[ExceptHandlerNode] = []
        self.elsesuite: list[StatementNode] = []
        self.finalsuite: list[StatementNode] = []


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


class PassNode(BaseNode):
    pass


class BreakNode(BaseNode):
    pass


class ContinueNode(BaseNode):
    pass


StatementNode = Union[
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
]


class BoolOpNode(BaseNode):
    __slots__ = ('op', 'values')

    def __init__(self, *, op: BoolOperator) -> None:
        self.op = op
        self.values: list[ExpressionNode] = []


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
    __slots__ = ('parameters', 'suite')

    def __init__(self) -> None:
        self.parameters: list[ParameterNode] = []
        self.suite: list[StatementNode] = []


class IfExpNode(BaseNode):
    __slots__ = ('condition', 'body', 'elsebody')

    def __init__(self, *, body: ExpressionNode, condition: ExpressionNode,
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

    def __init__(self, *, left: ExpressionNode) -> None:
        self.left = left
        self.comparators: list[ComparatorNode] = []


class ComparatorNode(BaseNode):
    __slots__ = ('op', 'value')

    def __init__(self, *, op: CmpOperator, value: ExpressionNode) -> None:
        self.op = op
        self.value = value


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
    __slots__ = ('type',)

    def __init__(self, *, type: ConstantType) -> None:
        self.type = type


class IntegerNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, *, value: int) -> None:
        super().__init__(type=ConstantType.INTEGER)
        self.value = value


class FloatNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, *, value: float) -> None:
        super().__init__(type=ConstantType.FLOAT)
        self.value = value


class ComplexNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, *, value: complex) -> None:
        super().__init__(type=ConstantType.COMPLEX)
        self.value = value


class StringNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, *, value: str) -> None:
        super().__init__(type=ConstantType.STRING)
        self.value = value


class BytesNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, *, value: bytes) -> None:
        super().__init__(type=ConstantType.BYTES)
        self.value = value


class AttributeNode(BaseNode):
    __slots__ = ('value', 'attr',)

    def __init__(self, *, value: ExpressionNode, attr: str) -> None:
        self.value = value
        self.attr = attr


class SubscriptNode(BaseNode):
    __slots__ = ('value', 'slice',)

    def __init__(self, *, value: ExpressionNode, slice: ExpressionNode) -> None:
        self.value = value
        self.slice = slice


class StarredNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, *, value: ExpressionNode) -> None:
        self.value = value


class NameNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, *, value: str) -> None:
        self.value = value


class ListNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self) -> None:
        self.elts: list[ExpressionNode] = []
        self.ctx = ExprContext.LOAD


class TupleNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self):
        self.elts: list[ExpressionNode] = []
        self.ctx = ExprContext.LOAD


class SliceNode(BaseNode):
    __slots__ = ('start', 'stop', 'step')

    def __init__(self, *, start: Optional[int], stop: Optional[int], step: Optional[int]) -> None:
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
    __slots__ = ('type', 'target', 'suite')

    def __init__(self) -> None:
        self.type: Optional[ExpressionNode] = None
        self.target: Optional[str] = None
        self.suite: list[StatementNode] = []


class ComprehensionNode(BaseNode):
    __slots__ = ('is_async', 'target', 'iterator', 'ifs')

    def __init__(self, *, target: ExpressionNode, iterator: ExpressionNode) -> None:
        self.is_async = False
        self.target = target
        self.iterator = iterator
        self.ifs: list[ExpressionNode] = []


class AliasNode(BaseNode):
    __slots__ = ('name', 'asname')

    def __init__(self, *, name: str, asname: str) -> None:
        self.name = name
        self.asname = asname


class DictElt:
    __slots__ = ('key', 'value')

    def __init__(self, *, key: ExpressionNode, value: ExpressionNode) -> None:
        self.key = key
        self.value = value


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
