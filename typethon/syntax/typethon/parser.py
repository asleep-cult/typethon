import typing
from pathlib import Path
import prettyprinter

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
    ParserTable,
    Transformer,
    ParserAutomaton,
    ParserTableGenerator,
    NodeItem as NodeItemT,
    OptionNode,
    FlattenNode,
)

NodeItem = NodeItemT[TokenKind, KeywordKind]
TransformCallbackT = typing.Callable[..., NodeItem]

GRAMMAR_PATH = './typethon.gram'


def load_parser_tables() -> typing.Dict[str, ParserTable[TokenKind, KeywordKind]]:
    path = Path(__file__).parent / GRAMMAR_PATH
    with open(path, 'r') as fp:
        grammar = fp.read()

    return ParserTableGenerator[TokenKind, KeywordKind].generate_from_grammar(
        grammar, TOKENS, KEYWORDS
    )


class ASTParser:
    tables = load_parser_tables()

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
        for function in (
            self.create_single_parameter,
            self.create_parameters,
            self.create_function,
            self.create_constant,
            self.create_name,
        ):
            if transformer_wrapper is not None:
                function = transformer_wrapper(function).__get__(self)

            transformers.append(Transformer[TokenKind, KeywordKind].from_function(function))

        self.parser = ParserAutomaton(
            self.scanner,
            self.tables[entrypoint],
            transformers,
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

    def create_parameters(
        self,
        span: typing.Tuple[int, int],
        first_parameter: ast.FunctionParameterNode,
        remaning_parameters: FlattenNode[ast.FunctionParameterNode],
    ) -> FlattenNode[ast.FunctionParameterNode]:
        # parameter, parameters*
        # TODO: should probably just add a builtin @prepend transformer
        remaning_parameters.items.insert(0, first_parameter)
        return remaning_parameters

    def create_function(
        self,
        span: typing.Tuple[int, int],
        decorators: OptionNode[FlattenNode[ast.ExpressionNode]],
        name: IdentifierToken,
        parameters: OptionNode[FlattenNode[ast.FunctionParameterNode]],
        returns: ast.ExpressionNode,
        body: OptionNode[FlattenNode[ast.StatementNode]],
    ) -> ast.FunctionDefNode:
        return ast.FunctionDefNode(
            start=span[0],
            end=span[1],
            name=name.content,
            parameters=parameters.flatten().items,
            body=body.map(lambda flatten: flatten.items),
            decorators=decorators.flatten().items,
            returns=returns,
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
