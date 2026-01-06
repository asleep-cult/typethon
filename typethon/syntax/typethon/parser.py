import typing
import time
import logging
import inspect
from pathlib import Path

from .tokens import (
    TokenKind,
    KeywordKind,
    Token,
    TOKENS,
    KEYWORDS,
    create_scanner,
)
from . import ast
from ..tokens import IdentifierToken

from ...grammar import (
    FrozenParserTable,
    Transformer,
    ParserAutomaton,
    ParserTableGenerator,
    NodeItem as NodeItemT,
    OptionNode,
    SequenceNode,
)

NodeItem = NodeItemT[TokenKind, KeywordKind]
TransformCallbackT = typing.Callable[..., NodeItem]

logger = logging.getLogger(__name__)

GRAMMAR_PATH = './typethon.gram'


class ASTParser:
    tables: typing.ClassVar[
        typing.Optional[typing.Dict[str, FrozenParserTable[TokenKind, KeywordKind]]]
    ] = None

    def __init__(
        self,
        source: str,
        entrypoint: str,
        *,
        transformer_wrapper: typing.Optional[
            typing.Callable[[TransformCallbackT], TransformCallbackT]
        ] = None,
    ) -> None:
        self.scanner = create_scanner(source)

        transformers: typing.List[Transformer[TokenKind, KeywordKind]] = []
        def is_transformer(member: typing.Any) -> bool:
            return inspect.ismethod(member) and member.__name__.startswith('create_')
        
        for _, function in inspect.getmembers(self, is_transformer):
            if transformer_wrapper is not None:
                function = transformer_wrapper(function).__get__(self)

            transformers.append(Transformer[TokenKind, KeywordKind].from_function(function))

        if self.tables is None:
            raise ValueError('Call ASTParser.load_parser_tables()')

        self.parser = ParserAutomaton(
            self.scanner,
            self.tables[entrypoint],
            transformers,
        )

    @classmethod
    def load_parser_tables(cls) -> None:
        path = Path(__file__).parent / GRAMMAR_PATH
        with open(path, 'r') as fp:
            grammar = fp.read()

        start = time.perf_counter()
        cls.tables = ParserTableGenerator[TokenKind, KeywordKind].generate_from_grammar(
            grammar, TOKENS, KEYWORDS
        )
        end = time.perf_counter()

        difference = end - start
        logger.debug(f'Generated tables after {difference:.2f} seconds')

    def create_pass_statement(self, span: typing.Tuple[int, int]) -> ast.PassNode:
        return ast.PassNode(start=span[0], end=span[1])

    def create_break_statement(self, span: typing.Tuple[int, int]) -> ast.BreakNode:
        return ast.BreakNode(start=span[0], end=span[1])

    def create_continue_statement(self, span: typing.Tuple[int, int]) -> ast.ContinueNode:
        return ast.ContinueNode(start=span[0], end=span[1])

    def create_expr_statement(
        self,
        span: typing.Tuple[int, int],
        expression: ast.ExpressionNode
    ) -> ast.ExprNode:
        return ast.ExprNode(
            start=span[0],
            end=span[1],
            expr=expression,
        )

    def create_single_parameter(
        self,
        span: typing.Tuple[int, int],
        name: IdentifierToken,
        annotation: ast.TypeExpressionNode,
        default: OptionNode[ast.ExpressionNode],
    ) -> NodeItem:
        return ast.FunctionParameterNode(
            start=span[0],
            end=span[1],
            name=name.content,
            kind=ast.ParameterKind.ARG,
            annotation=annotation,
            default=default.item,
        )

    def create_function(
        self,
        span: typing.Tuple[int, int],
        decorators: OptionNode[SequenceNode[ast.ExpressionNode]],
        name: IdentifierToken,
        parameters: OptionNode[SequenceNode[ast.FunctionParameterNode]],
        returns: ast.ExpressionNode,
        body: OptionNode[SequenceNode[ast.StatementNode]],
    ) -> ast.FunctionDefNode:
        return ast.FunctionDefNode(
            start=span[0],
            end=span[1],
            name=name.content,
            parameters=parameters.sequence().items,
            body=body.map(lambda flatten: flatten.items),
            decorators=decorators.sequence().items,
            returns=returns,
        )

    def create_if_statement(
        self,
        span: typing.Tuple[int, int],
        condition: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
        else_statement: OptionNode[SequenceNode[ast.StatementNode]],
    ) -> ast.IfNode:
        return ast.IfNode(
            start=span[0],
            end=span[1],
            condition=condition,
            body=body.items,
            else_body=else_statement.sequence().items,
        )

    def create_elif_statement(
        self,
        span: typing.Tuple[int, int],
        condition: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
        else_statement: OptionNode[SequenceNode[ast.StatementNode]],
    ) -> SequenceNode[ast.StatementNode]:
        node = ast.IfNode(
            start=span[0],
            end=span[1],
            condition=condition,
            body=body.items,
            else_body=else_statement.sequence().items,
        )
        return SequenceNode(start=span[0], end=span[1], items=[node])

    def create_while_statement(
        self,
        span: typing.Tuple[int, int],
        condition: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
    ) -> ast.WhileNode:
        return ast.WhileNode(
            start=span[0],
            end=span[1],
            condition=condition,
            body=body.items,
        )

    def create_disjunction(
        self,
        span: typing.Tuple[int, int],
        expression: ast.ExpressionNode,
        operands: SequenceNode[ast.ExpressionNode],
    ) -> ast.BoolOpNode:
        sequence = self.parser.transform_prepend(span, expression, operands)
        return ast.BoolOpNode(
            start=span[0],
            end=span[1],
            op=ast.BoolOperatorKind.OR,
            values=sequence.items,
        )

    def create_conjunction(
        self,
        span: typing.Tuple[int, int],
        expression: ast.ExpressionNode,
        operands: SequenceNode[ast.ExpressionNode],
    ) -> ast.BoolOpNode:
        sequence = self.parser.transform_prepend(span, expression, operands)
        return ast.BoolOpNode(
            start=span[0],
            end=span[1],
            op=ast.BoolOperatorKind.AND,
            values=sequence.items,
        )

    def create_inversion(
        self,
        span: typing.Tuple[int, int],
        operand: ast.ExpressionNode,
    ) -> ast.UnaryOpNode:
        return ast.UnaryOpNode(
            start=span[0],
            end=span[1],
            op=ast.UnaryOperatorKind.NOT,
            operand=operand,
        )

    def create_comparison(
        self,
        span: typing.Tuple[int, int],
        left: ast.ExpressionNode,
        comparators: SequenceNode[ast.ComparatorNode],
    ) -> ast.CompareNode:
        return ast.CompareNode(
            start=span[0],
            end=span[1],
            left=left,
            comparators=comparators.items,
        )

    def create_eq_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.EQ,
            value=value,
        )

    def create_noteq_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.NOTEQ,
            value=value,
        )

    def create_lthaneq_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.LTE,
            value=value,
        )

    def create_lthan_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.LT,
            value=value,
        )

    def create_gthaneq_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.GTE,
            value=value,
        )

    def create_gthan_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.GT,
            value=value,
        )

    def create_notin_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.NOTIN,
            value=value,
        )

    def create_in_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.IN,
            value=value,
        )

    def create_isnot_comparator(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=ast.CmpOperatorKind.ISNOT,
            value=value,
        )

    def create_binary_operator(
        self,
        span: typing.Tuple[int, int],
        left: ast.ExpressionNode,
        operator: Token,
        right: ast.ExpressionNode,
    ) -> ast.BinaryOpNode:
        match operator.kind:
            case TokenKind.VERTICALBAR:
                op = ast.OperatorKind.BITOR
            case TokenKind.CIRCUMFLEX:
                op = ast.OperatorKind.BITXOR
            case TokenKind.AMPERSAND:
                op = ast.OperatorKind.BITAND
            case TokenKind.DOUBLELTHAN:
                op = ast.OperatorKind.LSHIFT
            case TokenKind.DOUBLEGTHAN:
                op = ast.OperatorKind.RSHIFT
            case TokenKind.PLUS:
                op = ast.OperatorKind.ADD
            case TokenKind.MINUS:
                op = ast.OperatorKind.SUB
            case TokenKind.STAR:
                op = ast.OperatorKind.MULT
            case TokenKind.SLASH:
                op = ast.OperatorKind.DIV
            case TokenKind.DOUBLESLASH:
                op = ast.OperatorKind.FLOORDIV
            case TokenKind.PERCENT:
                op = ast.OperatorKind.MOD
            case TokenKind.AT:
                op = ast.OperatorKind.MATMULT
            case TokenKind.DOUBLESTAR:
                op = ast.OperatorKind.POW
            case _:
                assert False, 'Unreachable'

        return ast.BinaryOpNode(
            start=span[0],
            end=span[1],
            left=left,
            op=op,
            right=right,
        )

    def create_unary_operator(
        self,
        span: typing.Tuple[int, int],
        operator: Token,
        operand: ast.ExpressionNode,
    ) -> ast.ExpressionNode:
        match operator.kind:
            case TokenKind.PLUS:
                op = ast.UnaryOperatorKind.UADD
            case TokenKind.MINUS:
                op = ast.UnaryOperatorKind.USUB
            case TokenKind.TILDE:
                op = ast.UnaryOperatorKind.INVERT
            case _:
                assert False, 'Unreachable'

        return ast.UnaryOpNode(
            start=span[0],
            end=span[1],
            op=op,
            operand=operand,
        )

    def create_slice(
        self,
        span: typing.Tuple[int, int],
        start: ast.ExpressionNode,
        stop: ast.ExpressionNode,
        step: OptionNode[ast.ExpressionNode],
    ) -> ast.SliceNode:
        return ast.SliceNode(
            start=span[0],
            end=span[1],
            start_index=start,
            stop_index=stop,
            step_index=step.item,
        )

    def create_attribute(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
        attribute: IdentifierToken,
    ) -> ast.AttributeNode:
        return ast.AttributeNode(
            start=span[0],
            end=span[1],
            value=value,
            attr=attribute.content,
        )

    def create_subscript(
        self,
        span: typing.Tuple[int, int],
        value: ast.ExpressionNode,
        slices: SequenceNode[ast.ExpressionNode],
    ) -> ast.SubscriptNode:
        return ast.SubscriptNode(
            start=span[0],
            end=span[1],
            value=value,
            slices=slices.items,
        )

    def create_constant(
        self,
        span: typing.Tuple[int, int],
        token: Token,
    ) -> ast.ConstantNode:
        match token.kind:
            case KeywordKind.TRUE:
                return ast.ConstantNode(
                    start=span[0],
                    end=span[1],
                    kind=ast.ConstantKind.TRUE
                )
            case KeywordKind.FALSE:
                return ast.ConstantNode(
                    start=span[0],
                    end=span[1],
                    kind=ast.ConstantKind.FALSE,
                )

    def create_name(
        self,
        span: typing.Tuple[int, int],
        identifier: IdentifierToken,
    ) -> ast.NameNode:
        return ast.NameNode(start=span[0], end=span[1], value=identifier.content)

    def parse(self) -> NodeItem:
        return self.parser.parse()
