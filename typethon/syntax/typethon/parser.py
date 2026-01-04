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
from ..tokens import (
    StdTokenKind,
    IdentifierToken,
)
from ...grammar import (
    ParserTable,
    Transformer,
    ParserAutomaton,
    ParserTableGenerator,
    NodeItem as NodeItemT,
    OptionNode,
)

NodeItem = NodeItemT[TokenKind, KeywordKind]

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
            transformers.append(Transformer[TokenKind, KeywordKind].from_function(function))

        self.parser = ParserAutomaton(
            self.scanner,
            self.tables[entrypoint],
            transformers,
        )

    def create_module(self, items: typing.List[NodeItem], flags: int) -> NodeItem:
        prettyprinter.cpprint(items)
        assert False, 'Not Implemented'

    def create_single_parameter(
        self,
        span: typing.Tuple[int, int],
        identifier: IdentifierToken,
        annotation: ast.TypeExpressionNode,
        default: OptionNode[ast.ExpressionNode],
    ) -> ast.Node:
        return ast.FunctionParameterNode(
            start=span[0],
            end=span[1],
            name=identifier.content,
            kind=ast.ParameterKind.ARG,
            annotation=annotation,
            default=default.item,
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

    def create_parameters(self, *args):
        # parameter, parameters*
        prettyprinter.cpprint(args)
        assert False, 'Not Implemented'

    def create_function(self, *args):
        prettyprinter.cpprint(items)
        assert False, 'Not Implemented'

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
