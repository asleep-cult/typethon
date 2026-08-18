import inspect
import io
import logging
import time
import typing
from itertools import count
from pathlib import Path
from types import FunctionType

from ...grammar import (
    FrozenParserTable,
    FrozenSymbolTable,
    OptionNode,
    ParserAutomaton,
    ParserTableGenerator,
    SequenceNode,
)
from ...grammar import (
    NodeItem as NodeItemT,
)
from ..tokens import (
    STD_TOKENS,
    IdentifierToken,
    NumberToken,
    NumberTokenFlags,
    StringToken,
    StringTokenFlags,
)
from . import ast
from .tokens import (
    KEYWORDS,
    TOKENS,
    KeywordKind,
    Token,
    TokenKind,
    create_scanner,
)

type NodeItem = NodeItemT[TokenKind, KeywordKind]
type TransformCallbackT = FunctionType[..., NodeItem]

logger = logging.getLogger(__name__)

GRAMMAR_PATH = "./typethon.gram"
GRAMMAR_CACHE_PATH = "./parsertables.bin"


class ASTParser:
    # The grammar is written in a way that constrains type expressions
    # to a subset of expressions that are valid as types; but this is not reflected
    # in the AST. I tried to unify types and expressions in the grammar, but this created
    # ambiguity for type definition statements and exploded the parser table to 10,000
    # states. The reason I don't properly represent the grammar in the AST is because
    # I would need to expressions generic over their subexpression type and I would
    # end up with something like TypeExpressionNode = TupleNode[TypeExpression] | ...
    # and ExpressionNode = TupleNode[TypeExpressionNode | ExpressionNode] | ...
    # And I do not want to make the entire expression AST generic.

    symbol_table: typing.ClassVar[FrozenSymbolTable | None] = None
    parse_tables: typing.ClassVar[
        dict[str, FrozenParserTable[TokenKind, KeywordKind]] | None
    ] = None

    def __init__(
        self,
        source: str,
        entrypoint: str,
        *,
        transformer_wrapper: typing.Callable[[TransformCallbackT], TransformCallbackT]
        | None = None,
    ) -> None:
        self.node_id_counter = count()
        self.scanner = create_scanner(source)

        transformers = []

        def is_transformer(member: typing.Any) -> bool:
            return inspect.ismethod(member) and (
                member.__name__.startswith("create_")
                or member.__name__
                in (
                    "add_function_body",
                    "add_simple_statement_to_lambda",
                    "add_statements_to_lambda",
                    "stop_nested_indentation",
                )
            )

        for _, function in inspect.getmembers(self, is_transformer):
            if transformer_wrapper is not None:
                function = transformer_wrapper(function).__get__(self)

            transformers.append(function)

        if self.parse_tables is None:
            raise ValueError("Call ASTParser.load_parser_tables()")

        self.parser = ParserAutomaton(
            self.scanner,
            self.parse_tables[entrypoint],
            transformers,
        )

    @classmethod
    def load_parser_tables(cls, *, regenrate: bool = False, test: bool = False) -> None:
        cache_path = Path(__file__).parent / GRAMMAR_CACHE_PATH

        if not regenrate:
            with open(cache_path, "rb") as fp:
                start = time.perf_counter()
                tokens = []
                tokens.extend(kind for _, kind in STD_TOKENS)
                tokens.extend(kind for _, kind in TOKENS)
                tokens.extend(kind for _, kind in KEYWORDS)
                cls.symbol_table = FrozenSymbolTable.from_bytes(tokens, fp)
                table = FrozenParserTable.from_bytes(cls.symbol_table, fp)
                cls.parse_tables = {"module": table}
                end = time.perf_counter()

                difference = end - start
                logger.info(f"Loaded my tables after {difference * 1000:.2f} ms")
                return

        grammar_path = Path(__file__).parent / GRAMMAR_PATH
        with open(grammar_path, "r") as fp:
            grammar = fp.read()

        start = time.perf_counter()
        cls.symbol_table, cls.parse_tables = ParserTableGenerator.generate_from_grammar(
            grammar, TOKENS, KEYWORDS
        )
        end = time.perf_counter()

        with open(cache_path, "wb") as fp:
            cls.symbol_table.to_bytes(fp)
            cls.parse_tables["module"].to_bytes(fp)

        difference = end - start
        logger.info(f"Generated tables after {difference:.2f} seconds")

    def node_id(self) -> ast.NodeId:
        return ast.NodeId(next(self.node_id_counter))

    def create_module(
        self,
        span: tuple[int, int],
        body: SequenceNode[ast.StatementNode],
    ) -> typing.Any:
        body = self.parser.transform_flatten(span, body)
        return ast.ModuleNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            body=body.items,
        )

    def create_break_statement(self, span: tuple[int, int]) -> ast.BreakNode:
        return ast.BreakNode(id=self.node_id(), start=span[0], end=span[1])

    def create_continue_statement(self, span: tuple[int, int]) -> ast.ContinueNode:
        return ast.ContinueNode(id=self.node_id(), start=span[0], end=span[1])

    def create_return_statement(
        self,
        span: tuple[int, int],
        value: OptionNode[ast.ExpressionNode],
    ) -> ast.ReturnNode:
        return ast.ReturnNode(
            id=self.node_id(), start=span[0], end=span[1], value=value.item
        )

    def create_expr_statement(
        self, span: tuple[int, int], expression: ast.ExpressionNode
    ) -> ast.ExprNode | ast.AssignNode:
        return ast.ExprNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            expr=expression,
        )

    def create_function_parameter(
        self,
        span: tuple[int, int],
        name: IdentifierToken,
        type: ast.ExpressionNode,
        default: OptionNode[ast.ExpressionNode],
    ) -> NodeItem:
        return ast.FunctionParameterNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
            type=type,
            default=default.item,
        )

    def create_function_prototype(
        self,
        span: tuple[int, int],
        decorators: OptionNode[SequenceNode[ast.ExpressionNode]],
        name: IdentifierToken,
        parameters: OptionNode[SequenceNode[ast.FunctionParameterNode]],
        returns: ast.ExpressionNode,
    ) -> ast.FunctionDefNode:
        return ast.FunctionDefNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
            parameters=parameters.sequence().items,
            body=None,
            decorators=decorators.sequence().items,
            returns=returns,
        )

    def add_function_body(
        self,
        span: tuple[int, int],
        function: ast.FunctionDefNode,
        body: SequenceNode[ast.StatementNode],
    ) -> ast.FunctionDefNode:
        function.body = body.items
        return function

    def create_class(
        self,
        span: tuple[int, int],
        decorators: OptionNode[SequenceNode[ast.ExpressionNode]],
        name: IdentifierToken,
        parameters: OptionNode[SequenceNode[ast.TypeParameterNode]],
        body: SequenceNode[ast.StatementNode],
    ) -> ast.ClassDefNode:
        return ast.ClassDefNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
            parameters=parameters.sequence().items,
            body=body.items,
            decorators=decorators.sequence().items,
        )

    def create_use_statement(
        self,
        span: tuple[int, int],
        type: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
    ) -> ast.UseNode:
        return ast.UseNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            type=type,
            body=body.items,
        )

    def create_use_as_statement(
        self,
        span: tuple[int, int],
        type: ast.ExpressionNode,
        type_class: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
    ) -> ast.UseAsNode:
        return ast.UseAsNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            type_class=type_class,
            type=type,
            body=body.items,
        )

    def create_if_statement(
        self,
        span: tuple[int, int],
        condition: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
        else_statement: OptionNode[ast.ElseNode],
    ) -> ast.IfNode:
        return ast.IfNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            condition=condition,
            body=body.items,
            else_statement=else_statement.item,
        )

    def create_elif_statement(
        self,
        span: tuple[int, int],
        condition: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
        else_statement: OptionNode[ast.ElseNode],
    ) -> ast.ElseNode:
        node = ast.IfNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            condition=condition,
            body=body.items,
            else_statement=else_statement.item,
        )
        return ast.ElseNode(id=self.node_id(), start=span[0], end=span[1], body=[node])

    def create_else_statement(
        self,
        span: tuple[int, int],
        body: SequenceNode[ast.StatementNode],
    ) -> ast.ElseNode:
        return ast.ElseNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            body=body.items,
        )

    def create_while_statement(
        self,
        span: tuple[int, int],
        condition: ast.ExpressionNode,
        body: SequenceNode[ast.StatementNode],
    ) -> ast.WhileNode:
        return ast.WhileNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            condition=condition,
            body=body.items,
        )

    def create_annotated_expression(
        self,
        span: tuple[int, int],
        value: ast.ExpressionNode,
        type: ast.ExpressionNode,
    ) -> ast.AnnotatedNode:
        return ast.AnnotatedNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            value=value,
            type=type,
        )

    def create_disjunction(
        self,
        span: tuple[int, int],
        expression: ast.ExpressionNode,
        operands: SequenceNode[ast.ExpressionNode],
    ) -> ast.BoolOpNode:
        sequence = self.parser.transform_prepend(span, expression, operands)
        return ast.BoolOpNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            op=ast.BoolOperatorKind.OR,
            values=sequence.items,
        )

    def create_assignment(
        self,
        span: tuple[int, int],
        target: ast.ExpressionNode,
        value: ast.ExpressionNode,
    ) -> ast.AssignNode:
        return ast.AssignNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            target=target,
            value=value,
        )

    def create_conjunction(
        self,
        span: tuple[int, int],
        expression: ast.ExpressionNode,
        operands: SequenceNode[ast.ExpressionNode],
    ) -> ast.BoolOpNode:
        sequence = self.parser.transform_prepend(span, expression, operands)
        return ast.BoolOpNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            op=ast.BoolOperatorKind.AND,
            values=sequence.items,
        )

    def create_inversion(
        self,
        span: tuple[int, int],
        operand: ast.ExpressionNode,
    ) -> ast.UnaryOpNode:
        return ast.UnaryOpNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            op=ast.UnaryOperatorKind.NOT,
            operand=operand,
        )

    def create_comparison(
        self,
        span: tuple[int, int],
        left: ast.ExpressionNode,
        comparators: SequenceNode[ast.ComparatorNode],
    ) -> ast.CompareNode:
        return ast.CompareNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            left=left,
            comparators=comparators.items,
        )

    def create_comparator_one(
        self,
        span: tuple[int, int],
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
            case KeywordKind.IS:
                op = ast.CmpOperatorKind.IS
            case _:
                assert False, "Unreachable"

        return ast.ComparatorNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            op=op,
            value=value,
        )

    def create_comparator_two(
        self,
        span: tuple[int, int],
        operator1: Token,
        operator2: Token,
        value: ast.ExpressionNode,
    ) -> ast.ComparatorNode:
        op: ast.CmpOperatorKind | None = None

        if operator1.kind is KeywordKind.IS:
            if operator2.kind is KeywordKind.NOT:
                op = ast.CmpOperatorKind.ISNOT

        elif operator1.kind is KeywordKind.NOT:
            if operator2.kind is KeywordKind.IN:
                op = ast.CmpOperatorKind.NOTIN

        if op is None:
            assert False, "Unreachable"

        return ast.ComparatorNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            op=op,
            value=value,
        )

    def create_binary_operator(
        self,
        span: tuple[int, int],
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
                assert False, "Unreachable"

        return ast.BinaryOpNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            left=left,
            op=op,
            right=right,
        )

    def create_unary_operator(
        self,
        span: tuple[int, int],
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
                assert False, "Unreachable"

        return ast.UnaryOpNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            op=op,
            operand=operand,
        )

    def create_call(
        self,
        span: tuple[int, int],
        callee: ast.ExpressionNode,
        args: OptionNode[SequenceNode[ast.ExpressionNode]],
    ) -> ast.CallNode:
        return ast.CallNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            callable=callee,
            args=args.sequence().items,
        )

    def create_slice(
        self,
        span: tuple[int, int],
        start: ast.ExpressionNode,
        stop: ast.ExpressionNode,
        step: OptionNode[ast.ExpressionNode],
    ) -> ast.SliceNode:
        return ast.SliceNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            start_index=start,
            stop_index=stop,
            step_index=step.item,
        )

    def create_attribute(
        self,
        span: tuple[int, int],
        value: ast.ExpressionNode,
        attribute: IdentifierToken,
    ) -> ast.AttributeNode:
        return ast.AttributeNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            value=value,
            attr=attribute.content,
        )

    def create_subscript(
        self,
        span: tuple[int, int],
        value: ast.ExpressionNode,
        slices: SequenceNode[ast.ExpressionNode],
    ) -> ast.SubscriptNode:
        return ast.SubscriptNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            value=value,
            slices=slices.items,
        )

    def create_constant(
        self,
        span: tuple[int, int],
        token: Token,
    ) -> ast.ConstantNode:
        assert False, "Not Implemented"

    def create_number(
        self,
        span: tuple[int, int],
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
                id=self.node_id(),
                start=span[0],
                end=span[1],
                value=int(token.content, radix),
            )

        if token.flags & NumberTokenFlags.IMAGINARY:
            return ast.ComplexNode(
                id=self.node_id(),
                start=span[0],
                end=span[1],
                value=complex(token.content),
            )

        if token.flags & NumberTokenFlags.FLOAT:
            return ast.FloatNode(
                id=self.node_id(),
                start=span[0],
                end=span[1],
                value=float(token.content),
            )

        return ast.IntegerNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            value=int(token.content),
        )

    def create_string(
        self,
        span: tuple[int, int],
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
            id=self.node_id(),
            start=span[0],
            end=span[1],
            value=writer.getvalue(),
            flags=flags,
        )

    def create_name(
        self,
        span: tuple[int, int],
        identifier: IdentifierToken,
    ) -> ast.NameNode:
        return ast.NameNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            value=identifier.content,
        )

    def create_record(
        self,
        span: tuple[int, int],
        fields: OptionNode[SequenceNode[ast.RecordFieldNode]],
    ) -> ast.RecordNode:
        return ast.RecordNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            fields=fields.sequence().items,
        )

    def create_record_field(
        self,
        span: tuple[int, int],
        name: IdentifierToken,
        value: ast.ExpressionNode,
    ) -> ast.RecordFieldNode:
        return ast.RecordFieldNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
            value=value,
        )

    def create_tuple(
        self,
        span: tuple[int, int],
        elts: OptionNode[SequenceNode[ast.ExpressionNode]],
    ) -> ast.TupleNode:
        elt_nodes: list[ast.TupleEltNode] = []
        for i, elt in enumerate(elts.sequence().items):
            elt_node = ast.TupleEltNode(
                id=self.node_id(), start=elt.start, end=elt.end, index=i, value=elt
            )
            elt_nodes.append(elt_node)

        return ast.TupleNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            elts=elt_nodes,
        )

    def create_lambda_parameter(
        self,
        span: tuple[int, int],
        name: IdentifierToken,
        type: OptionNode[ast.ExpressionNode],
    ) -> ast.LambdaParameterNode:
        return ast.LambdaParameterNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
            type=type.item,
        )

    def create_lambda(
        self,
        span: tuple[int, int],
        parameters: OptionNode[SequenceNode[ast.LambdaParameterNode]],
        returns: OptionNode[ast.ExpressionNode],
    ) -> ast.LambdaNode:
        self.scanner.start_nested_indentation()
        return ast.LambdaNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            parameters=parameters.sequence().items,
            returns=returns.item,
            body=[],
        )

    def stop_nested_indentation(
        self, span: tuple[int, int], expression: ast.LambdaNode
    ) -> ast.LambdaNode:
        self.scanner.stop_nested_indentation()
        return expression

    def add_simple_statement_to_lambda(
        self,
        span: tuple[int, int],
        expression: ast.LambdaNode,
        statement: ast.StatementNode,
    ) -> ast.LambdaNode:
        expression.body.append(statement)
        return expression

    def add_statements_to_lambda(
        self,
        span: tuple[int, int],
        expression: ast.LambdaNode,
        statements: SequenceNode[ast.StatementNode],
    ) -> ast.LambdaNode:
        self.scanner.stop_nested_indentation()
        expression.body.extend(statements.items)
        return expression

    def create_self_type(
        self,
        span: tuple[int, int],
    ) -> ast.SelfTypeNode:
        return ast.SelfTypeNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
        )

    def create_type_definition(
        self,
        span: tuple[int, int],
        name: IdentifierToken,
        types: SequenceNode[ast.ExpressionNode | ast.SumTypeVariantNode],
    ) -> ast.TypeDefinitionNode | ast.SumTypeNode:
        if len(types.items) > 1:
            variants: list[ast.SumTypeVariantNode] = []
            for type in types.items:
                match type:
                    case ast.SumTypeVariantNode():
                        variants.append(type)
                    case ast.NameNode():
                        variant = ast.SumTypeVariantNode(
                            id=type.id,
                            start=type.start,
                            end=type.end,
                            name=type.value,
                            type=None,
                        )
                        variants.append(variant)
                    case _:
                        assert False, f"{type} cannot appear in sum type field"

            return ast.SumTypeNode(
                id=self.node_id(),
                start=span[0],
                end=span[1],
                name=name.content,
                variants=variants,
            )
        else:
            type = types.items[0]
            if isinstance(type, ast.SumTypeVariantNode):
                return ast.SumTypeNode(
                    id=self.node_id(),
                    start=span[0],
                    end=span[1],
                    name=name.content,
                    variants=[type],
                )

            assert not isinstance(type, ast.SumTypeVariantNode)
            return ast.TypeDefinitionNode(
                id=self.node_id(),
                start=span[0],
                end=span[1],
                name=name.content,
                type=type,
            )

    def create_struct_type(
        self,
        span: tuple[int, int],
        fields: SequenceNode[ast.StructTypeFieldNode],
    ) -> ast.StructTypeNode:
        return ast.StructTypeNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            fields=fields.items,
        )

    def create_struct_type_field(
        self,
        span: tuple[int, int],
        name: IdentifierToken,
        type: ast.ExpressionNode,
    ) -> ast.StructTypeFieldNode:
        return ast.StructTypeFieldNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
            type=type,
        )

    def create_sum_field(
        self,
        span: tuple[int, int],
        name: IdentifierToken,
        type: ast.ExpressionNode,
    ) -> ast.SumTypeVariantNode:
        return ast.SumTypeVariantNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
            type=type,
        )

    def create_type_parameter(
        self,
        span: tuple[int, int],
        name: IdentifierToken,
    ) -> ast.TypeParameterNode:
        return ast.TypeParameterNode(
            id=self.node_id(),
            start=span[0],
            end=span[1],
            name=name.content,
        )

    def parse(self) -> NodeItem:
        return self.parser.parse()
