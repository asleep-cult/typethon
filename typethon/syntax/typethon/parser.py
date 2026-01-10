import typing
import time
import io
import logging
import inspect
import pickle
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
from ..tokens import (
    IdentifierToken,
    NumberToken,
    NumberTokenFlags,
    StringToken,
    StringTokenFlags,
)

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
GRAMMAR_CACHE_PATH = './parsertables.bin'
EXPERIMENTAL_LAMBDAS = True
"""
The syntax for experimental lambdas is as follows:
(args...) :: expr

(args...) ::
    block
::

Since this syntax introduces a REDUCE/REDUCE conflict,
the grammar for tuple/group and lambda are combined and disambiguated
later.

This can probably be avoided entirely with a different syntax
for the argument list, such as |x, y, z| (as in Rust).
|x, y, z| ::
    print(x, y, z)
::
The delimiter at the end of the block is unavoidable
because a dedent that can be followed by an expression
is a very bad idea.

Without them, something like this would be actually call
the lambda:
(a, b) ::
    print(a, b)
(1, 2)

I also preliminarily added tuples, retaining Python's
no-parenthesis syntax slop.

Aside from the ambiguity issue, the lambda has another
problem as well. When the scanner is in any sort of
parenthesis, it skips all newlines and indentation.
So, for the block lambda to work, it has "trick"
the scanner into thinking there are no parenthesis.
The way I did this was by a new stack bottom that the
scanner uses to determine whether to use whitespace.
So, at the star, something like this ((x) :: * would have
a stack like this [`(`], suggesting the scanner should
skip newlines. However, in the parameter list we use a lookahead
to determine whether to give a sequence of parameters or a
tuple/group. If the next token is a double colon, it returns
the parameter list and sets the bottom of the stack to 1.
I initially tried to implement this as a transformer for the
:: token, but the parser will already scan the next token
before we can a chance to update the stack bottom. 

The parser generator slowed down quite significantly baceuse this
added 1000 new states. (Everytime I think it's fast enough
it get slower.)

I have also realized that the assignment syntax will
be ambiguous as well. I think I will just make assignments
an expression.
"""


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
            return inspect.ismethod(member) and (
                member.__name__.startswith('create_')
                or member.__name__ == 'add_lambda_parameters'
            )
        
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
    def load_parser_tables(cls, *, regenrate: bool = False) -> None:
        cache_path = Path(__file__).parent / GRAMMAR_CACHE_PATH

        if not regenrate:
            with open(cache_path, 'rb') as fp:
                start = time.perf_counter()
                cls.tables = pickle.load(fp)
                end = time.perf_counter()
                
                difference = end - start
                logger.info(f'Loaded cached tables after {difference:.2f} seconds')
                return

        grammar_path = Path(__file__).parent / GRAMMAR_PATH
        with open(grammar_path, 'r') as fp:
            grammar = fp.read()

        start = time.perf_counter()
        cls.tables = ParserTableGenerator[TokenKind, KeywordKind].generate_from_grammar(
            grammar, TOKENS, KEYWORDS
        )
        end = time.perf_counter()

        with open(cache_path, 'wb') as fp:
            pickle.dump(cls.tables, fp)

        difference = end - start
        logger.info(f'Generated tables after {difference:.2f} seconds')

    def create_module(
        self,
        span: typing.Tuple[int, int],
        body: SequenceNode[ast.StatementNode],
    ) -> typing.Any:
        body = self.parser.transform_flatten(span, body)
        return ast.ModuleNode(
            start=span[0],
            end=span[1],
            body=body.items,
        )

    def create_pass_statement(self, span: typing.Tuple[int, int]) -> ast.PassNode:
        return ast.PassNode(start=span[0], end=span[1])

    def create_break_statement(self, span: typing.Tuple[int, int]) -> ast.BreakNode:
        return ast.BreakNode(start=span[0], end=span[1])

    def create_continue_statement(self, span: typing.Tuple[int, int]) -> ast.ContinueNode:
        return ast.ContinueNode(start=span[0], end=span[1])

    def create_return_statement(
        self,
        span: typing.Tuple[int, int],
        value: OptionNode[ast.ExpressionNode],
    ) -> ast.ReturnNode:
        return ast.ReturnNode(start=span[0], end=span[1], value=value.item)

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

    def create_function_parameter(
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
        returns: ast.TypeExpressionNode,
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

    def create_comparator_one(
        self,
        span: typing.Tuple[int, int],
        operator: Token,
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        match operator.kind:
            case TokenKind.EQEQUAL:
                op = ast.CmpOperatorKind.EQ
            case TokenKind.NOTEQUAL:
                op = ast.CmpOperatorKind.NOTEQ
            case TokenKind.LTHANEQ:
                op = ast.CmpOperatorKind.LTE
            case TokenKind.LTHAN:
                op = ast.CmpOperatorKind.LT
            case TokenKind.GTHANEQ:
                op = ast.CmpOperatorKind.GTE
            case TokenKind.GTHAN:
                op = ast.CmpOperatorKind.GT
            case KeywordKind.IN:
                op = ast.CmpOperatorKind.IN
            case _:
                # What is the point of this accepting arguments
                # but no type checks works
                typing.assert_never(operator.kind)

        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=op,
            value=value,
        )

    def create_comparator_two(
        self,
        span: typing.Tuple[int, int],
        operator1: Token,
        operator2: Token,
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        op: typing.Optional[ast.CmpOperatorKind] = None

        if operator1.kind is KeywordKind.IS:
            if operator2.kind is KeywordKind.NOT:
                op = ast.CmpOperatorKind.ISNOT

        elif operator1.kind is KeywordKind.NOT:
            if operator2.kind is KeywordKind.IN:
                op = ast.CmpOperatorKind.NOTIN

        if op is None:
            assert False, 'Unreachable'

        return ast.ComparatorNode(
            start=span[0],
            end=span[1],
            op=op,
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

    def create_number(
        self,
        span: typing.Tuple[int, int],
        token: NumberToken,
    ) -> ast.ConstantNode:
        if token.flags & NumberTokenFlags.BINARY:
            radix = 2
        elif token.flags & NumberTokenFlags.OCTAL:
            radix = 8
        elif token.flags & NumberTokenFlags.HEXADECIMAL:
            radix = 16
        else:
            radix = -1

        if radix != -1:
            return ast.IntegerNode(
                start=span[0],
                end=span[1],
                value=int(token.content, radix),
            )

        if token.flags & NumberTokenFlags.IMAGINARY:
            return ast.ComplexNode(
                start=span[0],
                end=span[1],
                value=complex(token.content),
            )

        if token.flags & NumberTokenFlags.FLOAT:
            return ast.FloatNode(
                start=span[0],
                end=span[1],
                value=float(token.content),
            )

        return ast.IntegerNode(
            start=span[0],
            end=span[1],
            value=int(token.content),
        )

    def create_string(
        self,
        span: typing.Tuple[int, int],
        string_tokens: SequenceNode[StringToken],
    ) -> ast.StringNode:
        writer = io.StringIO()
        flags = ast.StringFlags.NONE

        for token in string_tokens.items:
            writer.write(token.content)
            # TODO: What is a T-String?
            # We actually need to check to make sure bytes and we
            # cant actually just combine the flags like this 

            if (token.flags & StringTokenFlags.RAW) != 0:
                flags |= ast.StringFlags.RAW

            if (token.flags & StringTokenFlags.BYTES) != 0:
                flags |= ast.StringFlags.BYTES

            if (token.flags & StringTokenFlags.FORMAT) != 0:
                flags |= ast.StringFlags.FORMAT

        return ast.StringNode(
            start=span[0],
            end=span[1],
            value=writer.getvalue(),
            flags=flags,
        )

    def create_name(
        self,
        span: typing.Tuple[int, int],
        identifier: IdentifierToken,
    ) -> ast.NameNode:
        return ast.NameNode(
            start=span[0],
            end=span[1],
            value=identifier.content,
        )

    def create_tuple(
        self,
        span: typing.Tuple[int, int],
        elts: SequenceNode[ast.ExpressionNode],
    ) -> ast.TupleNode:
        # Unparenthesized
        return ast.TupleNode(
            start=span[0],
            end=span[1],
            elts=elts.items,
        )

    def create_tuple_or_lambda_parameters(
        self,
        span: typing.Tuple[int, int],
        elts: OptionNode[SequenceNode[ast.ExpressionNode]],
    ) -> typing.Union[ast.TupleNode, SequenceNode[ast.LambdaParameterNode]]:
        token = self.parser.peek_token(1)
        if token.kind is not TokenKind.DOUBLECOLON:
            return ast.TupleNode(
                start=span[0],
                end=span[1],
                elts=elts.sequence().items,
            )

        parameters: typing.List[ast.LambdaParameterNode] = []
        for elt in elts.sequence().items:
            if not isinstance(elt, ast.NameNode):
                assert False, 'Invalid lambda parameter'

            parameter = ast.LambdaParameterNode(
                start=elt.start,
                end=elt.end,
                name=elt.value,
            )
            parameters.append(parameter)

        self.scanner.enter_nested_stack()
        return SequenceNode(
            start=span[0],
            end=span[1],
            items=parameters,
        )

    def create_group_or_lambda_parameters(
        self,
        span: typing.Tuple[int, int],
        expression: ast.ExpressionNode,
    ) -> typing.Union[ast.ExpressionNode, SequenceNode[ast.LambdaParameterNode]]:
        token = self.parser.peek_token(1)
        if token.kind is not TokenKind.DOUBLECOLON:
            return expression

        if not isinstance(expression, ast.NameNode):
            assert False, 'Non-name lambda parameter'

        parameter = ast.LambdaParameterNode(
            start=expression.start,
            end=expression.end,
            name=expression.value,
        )

        self.scanner.enter_nested_stack()
        return SequenceNode(
            start=span[0],
            end=span[1],
            items=[parameter],
        )

    def create_block_lambda(
        self,
        span: typing.Tuple[int, int],
        body: SequenceNode[ast.StatementNode],
    ) -> ast.BlockLambdaNode:
        self.scanner.exit_nested_stack()
        return ast.BlockLambdaNode(
            start=span[0],
            end=span[1],
            parameters=[],
            body=body.items,
        )

    def create_expression_lambda(
        self,
        span: typing.Tuple[int, int],
        body: ast.ExpressionNode,
    ) -> ast.ExpressionNode:
        self.scanner.exit_nested_stack()
        return ast.ExpressionLambdaNode(
            start=span[0],
            end=span[1],
            parameters=[],
            body=body,
        )

    def add_lambda_parameters(
        self,
        span: typing.Tuple[int, int],
        parameters: SequenceNode[ast.LambdaParameterNode],
        lambdef: typing.Union[ast.ExpressionLambdaNode, ast.BlockLambdaNode],
    ) -> typing.Union[ast.ExpressionLambdaNode, ast.BlockLambdaNode]:
        for parameter in parameters.items:
            lambdef.parameters.append(parameter)

        return lambdef

    def create_type_assignment(
        self,
        span: typing.Tuple[int, int],
        name: IdentifierToken,
        type: ast.TypeExpressionNode,
    ) -> ast.TypeAssignmentNode:
        return ast.TypeAssignmentNode(
            start=span[0],
            end=span[1],
            name=name.content,
            type=type,
        )

    def create_struct_type(
        self,
        span: typing.Tuple[int, int],
        fields: SequenceNode[ast.StructFieldNode],
    ) -> ast.StructTypeNode:
        return ast.StructTypeNode(
            start=span[0],
            end=span[1],
            fields=fields.items,
        )

    def create_struct_field(
        self,
        span: typing.Tuple[int, int],
        name: IdentifierToken,
        type: ast.TypeExpressionNode,
    ) -> ast.StructFieldNode:
        return ast.StructFieldNode(
            start=span[0],
            end=span[1],
            name=name.content,
            type=type,
        )

    def create_type_parameter(
        self,
        span: typing.Tuple[int, int],
        name: IdentifierToken,
    ) -> ast.TypeParameterNode:
        return ast.TypeParameterNode(
            start=span[0],
            end=span[1],
            name=name.content,
            constraint=None,
        )

    def parse(self) -> NodeItem:
        return self.parser.parse()
