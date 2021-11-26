from __future__ import annotations

import enum
from typing import Optional, Union

from .textrange import TextRange


class BaseNode:
    __slots__ = ('range',)

    def __init__(self, range: TextRange) -> None:
        self.range = range.copy()

    def __repr__(self):
        attrs = ', '.join(
            f'{name}={getattr(self, name)!r}'
            for name in self.__class__.__slots__ if name not in BaseNode.__slots__
        )
        if not attrs:
            return f'{self.__class__.__name__}()'
        return f'<{self.__class__.__name__} {attrs}>'


class StatementList(BaseNode):
    __slots__ = ('statements',)

    def __init__(self, range: TextRange) -> None:
        super().__init__(range)
        self.statements = []


class ModuleNode(BaseNode):
    __slots__ = ('body',)

    def __init__(self, range: TextRange, *, body: list[StatementNode]) -> None:
        super().__init__(range)
        self.body = body


class FunctionDefNode(BaseNode):
    __slots__ = ('is_async', 'name', 'parameters', 'body', 'decorators', 'returns')

    def __init__(
        self,
        range: TextRange,
        *,
        is_async: bool,
        name: str,
        parameters: list[ParameterNode],
        body: list[StatementNode],
        decorators: list[ExpressionNode],
        returns: Optional[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.is_async = is_async
        self.name = name
        self.parameters = parameters
        self.body = body
        self.decorators = decorators
        self.returns = returns


class ClassDefNode(BaseNode):
    __slots__ = ('name', 'bases', 'kwargs', 'body', 'decorators')

    def __init__(
        self,
        range: TextRange,
        *,
        name: str,
        bases: list[ExpressionNode],
        kwargs: list[KeywordArgumentNode],
        body: list[StatementNode],
        decorators: list[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.name = name
        self.bases = bases
        self.kwargs = kwargs
        self.body = body
        self.decorators = decorators


class ReturnNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: Optional[ExpressionNode]) -> None:
        super().__init__(range)
        self.value = value


class DeleteNode(BaseNode):
    __slots__ = ('targets',)

    def __init__(self, range: TextRange, *, targets: list[ExpressionNode]) -> None:
        super().__init__(range)
        self.targets = targets


class AssignNode(BaseNode):
    __slots__ = ('targets', 'value')

    def __init__(
        self,
        range: TextRange,
        *,
        targets: list[ExpressionNode],
        value: ExpressionNode,
    ) -> None:
        super().__init__(range)
        self.targets = targets
        self.value = value


class AugAssignNode(BaseNode):
    __slots__ = ('target', 'op', 'value')

    def __init__(
        self,
        range: TextRange,
        *,
        target: ExpressionNode,
        op: Operator,
        value: ExpressionNode,
    ) -> None:
        super().__init__(range)
        self.target = target
        self.op = op
        self.value = value


class AnnAssignNode(BaseNode):
    __sltos__ = ('target', 'annotation', 'value')

    def __init__(
        self,
        *,
        target: ExpressionNode,
        annotation: ExpressionNode,
        value: Optional[ExpressionNode],
    ) -> None:
        self.target = target
        self.annotation = annotation
        self.value = value


class ForNode(BaseNode):
    __slots__ = ('is_async', 'target', 'iterator', 'body', 'else_body')

    def __init__(
        self,
        range: TextRange,
        *,
        is_async: bool,
        target: ExpressionNode,
        iterator: ExpressionNode,
        body: list[ExpressionNode],
        else_body: list[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.is_async = is_async
        self.target = target
        self.iterator = iterator
        self.body = body
        self.else_body = else_body


class WhileNode(BaseNode):
    __slots__ = ('condition', 'body', 'else_body')

    def __init__(
        self,
        range: TextRange,
        *,
        condition: ExpressionNode,
        body: list[StatementNode],
        else_body: list[StatementNode],
    ) -> None:
        super().__init__(range)
        self.condition = condition
        self.body = body
        self.else_body = else_body


class IfNode(BaseNode):
    __slots__ = ('condition', 'body', 'else_body')

    def __init__(
        self,
        range: TextRange,
        *,
        condition: ExpressionNode,
        body: list[StatementNode],
        else_body: list[StatementNode],
    ) -> None:
        super().__init__(range)
        self.condition = condition
        self.body = body
        self.else_body = else_body


class WithNode(BaseNode):
    __slots__ = ('is_async', 'items', 'body')

    def __init__(
        self,
        range: TextRange,
        *,
        is_async: bool,
        items: list[WithItemNode],
        body: list[StatementNode],
    ) -> None:
        super().__init__(range)
        self.is_async = is_async
        self.items = items
        self.body = body


class RaiseNode(BaseNode):
    __slots__ = ('exc', 'cause')

    def __init__(
        self,
        range: TextRange,
        *,
        exc: Optional[ExpressionNode],
        cause: Optional[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.exc = exc
        self.cause = cause


class TryNode(BaseNode):
    __slots__ = ('body', 'handlers', 'else_body', 'final_body')

    def __init__(
        self,
        range: TextRange,
        *,
        body: list[StatementNode],
        handlers: list[ExceptHandlerNode],
        else_body: list[StatementNode],
        final_body: list[StatementNode],
    ) -> None:
        super().__init__(range)
        self.body = body
        self.handlers = handlers
        self.else_body = else_body
        self.final_body = final_body


class AssertNode(BaseNode):
    __slots__ = ('condition', 'message')

    def __init__(
        self,
        range: TextRange,
        *,
        condition: ExpressionNode,
        message: Optional[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.condition = condition
        self.message = message


class ImportNode(BaseNode):
    __slots__ = ('names',)

    def __init__(self, range: TextRange, *, names: list[AliasNode]) -> None:
        super().__init__(range)
        self.names = names


class ImportFromNode(BaseNode):
    __slots__ = ('module', 'names', 'level')

    def __init__(
        self,
        range: TextRange,
        *,
        module: Optional[str],
        names: list[AliasNode],
        level: Optional[int],
    ) -> None:
        super().__init__(range)
        self.module = module
        self.names = names
        self.level = level


class GlobalNode(BaseNode):
    __slots__ = ('names',)

    def __init__(self, range: TextRange, *, names: list[str]) -> None:
        super().__init__(range)
        self.names = names


class NonlocalNode(BaseNode):
    __slots__ = ('names',)

    def __init__(self, range: TextRange, *, names: list[str]) -> None:
        super().__init__(range)
        self.names = names


class ExprNode(BaseNode):
    __slots__ = ('expr',)

    def __init__(self, range: TextRange, *, expr: ExpressionNode) -> None:
        super().__init__(range)
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

    def __init__(
        self,
        range: TextRange,
        *,
        op: BoolOperator,
        values: list[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.op = op
        self.values = values


class BinaryOpNode(BaseNode):
    __slots__ = ('left', 'op', 'right')

    def __init__(
        self,
        range: TextRange,
        *,
        left: ExpressionNode,
        op: Operator,
        right: ExpressionNode
    ) -> None:
        super().__init__(range)
        self.left = left
        self.op = op
        self.right = right


class UnaryOpNode(BaseNode):
    __slots__ = ('op', 'operand')

    def __init__(
        self,
        range: TextRange,
        *,
        op: UnaryOperator,
        operand: ExpressionNode
    ) -> None:
        super().__init__(range)
        self.op = op
        self.operand = operand


class LambdaNode(BaseNode):
    __slots__ = ('parameters', 'body')

    def __init__(
        self,
        range: TextRange,
        *,
        parameters: list[ParameterNode],
        body: list[StatementNode]
    ) -> None:
        super().__init__(range)
        self.parameters = parameters
        self.body = body


class IfExpNode(BaseNode):
    __slots__ = ('condition', 'body', 'else_body')

    def __init__(
        self,
        range: TextRange,
        *,
        body: ExpressionNode,
        condition: ExpressionNode,
        else_body: ExpressionNode,
    ) -> None:
        super().__init__(range)
        self.body = body
        self.condition = condition
        self.else_body = else_body


class DictNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self, range: TextRange, *, elts: list[ExpressionNode]) -> None:
        super().__init__(range)
        self.elts = elts


class SetNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self, range: TextRange, *, elts: list[SetNode]) -> None:
        super().__init__(range)
        self.elts = elts


class ListCompNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(
        self,
        range: TextRange,
        *,
        elt: ExpressionNode,
        comprehensions: list[ComprehensionNode]
    ) -> None:
        super().__init__(range)
        self.elt = elt
        self.comprehensions = comprehensions


class SetCompNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(
        self,
        range: TextRange,
        *,
        elt: ExpressionNode,
        comprehensions: list[ComprehensionNode],
    ) -> None:
        super().__init__(range)
        self.elt = elt
        self.comprehensions = comprehensions


class DictCompNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(
        self,
        range: TextRange,
        *,
        elt: DictElt,
        comprehensions: list[ComprehensionNode],
    ) -> None:
        super().__init__(range)
        self.elt = elt
        self.comprehensions = comprehensions


class GeneratorExpNode(BaseNode):
    __slots__ = ('elt', 'comprehensions')

    def __init__(
        self,
        range: TextRange,
        *,
        elt: DictElt,
        comprehensions: list[ComprehensionNode],
    ) -> None:
        super().__init__(range)
        self.elt = elt
        self.comprehensions = comprehensions


class AwaitNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: ExpressionNode) -> None:
        super().__init__(range)
        self.value = value


class YieldNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: Optional[ExpressionNode]) -> None:
        super().__init__(range)
        self.value = value


class YieldFromNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: ExpressionNode) -> None:
        super().__init__(range)
        self.value = value


class CompareNode(BaseNode):
    __slots__ = ('left', 'comparators')

    def __init__(
        self,
        range: TextRange,
        *,
        left: ExpressionNode,
        comparators: list[ComparatorNode]
    ) -> None:
        super().__init__(range)
        self.left = left
        self.comparators = comparators


class ComparatorNode(BaseNode):
    __slots__ = ('op', 'value')

    def __init__(
        self,
        range: TextRange,
        *,
        op: CmpOperator,
        value: ExpressionNode,
    ) -> None:
        super().__init__(range)
        self.op = op
        self.value = value


class CallNode(BaseNode):
    __slots__ = ('func', 'args', 'kwargs')

    def __init__(
        self,
        range: TextRange,
        *,
        func: ExpressionNode,
        args: list[ExpressionNode],
        kwargs: list[KeywordArgumentNode],
    ) -> None:
        super().__init__(range)
        self.func = func
        self.args = args
        self.kwargs = kwargs


class FormattedValueNode(BaseNode):
    __slots__ = ('value', 'conversion', 'spec')

    def __init__(
        self,
        range: TextRange,
        *,
        value: ExpressionNode,
        conversion: Optional[int],
        spec: Optional[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.value = value
        self.conversion = conversion
        self.spec = spec


class ConstantNode(BaseNode):
    __slots__ = ('type',)

    def __init__(self, range: TextRange, *, type: ConstantType) -> None:
        super().__init__(range)
        self.type = type


class IntegerNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: int) -> None:
        super().__init__(range, type=ConstantType.INTEGER)
        self.value = value


class FloatNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: float) -> None:
        super().__init__(range, type=ConstantType.FLOAT)
        self.value = value


class ComplexNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: complex) -> None:
        super().__init__(range, type=ConstantType.COMPLEX)
        self.value = value


class StringNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: str) -> None:
        super().__init__(range, type=ConstantType.STRING)
        self.value = value


class BytesNode(ConstantNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, * value: bytes) -> None:
        super().__init__(range, type=ConstantType.BYTES)
        self.value = value


class AttributeNode(BaseNode):
    __slots__ = ('value', 'attr',)

    def __init__(self, range: TextRange, *, value: ExpressionNode, attr: str) -> None:
        super().__init__(range)
        self.value = value
        self.attr = attr


class SubscriptNode(BaseNode):
    __slots__ = ('value', 'slice',)

    def __init__(self, range: TextRange, *, value: ExpressionNode, slice: ExpressionNode) -> None:
        super().__init__(range)
        self.value = value
        self.slice = slice


class StarredNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: ExpressionNode) -> None:
        super().__init__(range)
        self.value = value


class NameNode(BaseNode):
    __slots__ = ('value',)

    def __init__(self, range: TextRange, *, value: str) -> None:
        super().__init__(range)
        self.value = value


class ListNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self, range: TextRange, *, elts: list[ExpressionNode]) -> None:
        super().__init__(range)
        self.elts = elts


class TupleNode(BaseNode):
    __slots__ = ('elts',)

    def __init__(self, range: TextRange, *, elts: list[ExpressionNode]) -> None:
        super().__init__(range)
        self.elts = elts


class SliceNode(BaseNode):
    __slots__ = ('start', 'stop', 'step')

    def __init__(
        self,
        range: TextRange,
        *,
        start: Optional[int],
        stop: Optional[int],
        step: Optional[int]
    ) -> None:
        super().__init__(range)
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
    __slots__ = ('name', 'type', 'annotation', 'default')

    def __init__(
        self,
        range: TextRange,
        *,
        name: str,
        type: ParameterType,
        annotation: Optional[ExpressionNode],
        default: Optional[ExpressionNode],
    ) -> None:
        super().__init__(range)
        self.name = name
        self.type = type
        self.annotation = annotation
        self.default = default


class KeywordArgumentNode(BaseNode):
    __slots__ = ('name', 'value')

    def __init__(self, range: TextRange, *, name: Optional[str], value: ExpressionNode) -> None:
        super().__init__(range)
        self.name = name
        self.value = value


class WithItemNode(BaseNode):
    __slots__ = ('contextmanager', 'targets')

    def __init__(
        self,
        range: TextRange,
        contextmanager: ExpressionNode,
        targets: list[ExpressionNode]
    ) -> None:
        super().__init__(range)
        self.contextmanager = contextmanager
        self.targets = targets


class ExceptHandlerNode(BaseNode):
    __slots__ = ('type', 'target', 'body')

    def __init__(
        self,
        range: TextRange,
        *,
        type: Optional[ExpressionNode],
        target: Optional[str],
        body: list[StatementNode],
    ) -> None:
        super().__init__(range)
        self.type = type
        self.target = target
        self.body = body


class ComprehensionNode(BaseNode):
    __slots__ = ('is_async', 'target', 'iterator', 'ifs')

    def __init__(
        self,
        range: TextRange,
        *,
        is_async: bool,
        target: ExpressionNode,
        iterator: ExpressionNode,
    ) -> None:
        super().__init__(range)
        self.is_async = is_async
        self.target = target
        self.iterator = iterator


class AliasNode(BaseNode):
    __slots__ = ('name', 'asname')

    def __init__(self, range: TextRange, *, name: str, asname: str) -> None:
        super().__init__(range)
        self.name = name
        self.asname = asname


class DictElt:
    __slots__ = ('key', 'value')

    def __init__(self, range: TextRange, *, key: ExpressionNode, value: ExpressionNode) -> None:
        super().__init__(range)
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
