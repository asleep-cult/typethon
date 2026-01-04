import typing
import enum
from pathlib import Path
import prettyprinter

from . import tokens
from . import ast
from ..tokens import StdTokenKind
from ...grammar import (
    FlagMap,
    ParserTable,
    ParserAutomaton,
    ParserTableGenerator,
    NodeItem as NodeItemT
)

NodeItem = NodeItemT[tokens.TokenKind, tokens.KeywordKind, ast.Node]

GRAMMAR_PATH = './typethon.gram'


class ParserFlags(enum.IntFlag):
    DECORATORS = enum.auto()


FLAGS: FlagMap = {
    'TRUE': ast.ConstantKind.TRUE,
    'FALSE': ast.ConstantKind.FALSE,
    'NONE': ast.ConstantKind.NONE,
    'ELLIPSIS': ast.ConstantKind.ELLIPSIS,
    'DECORATORS': ParserFlags.DECORATORS,
}


def load_parser_tables() -> typing.Dict[str, ParserTable[tokens.TokenKind, tokens.KeywordKind]]:
    path = Path(__file__).parent / GRAMMAR_PATH
    with open(path, 'r') as fp:
        grammar = fp.read()

    return ParserTableGenerator[tokens.TokenKind, tokens.KeywordKind].generate_from_grammar(
        grammar,
        tokens.TOKENS,
        tokens.KEYWORDS,
        FLAGS,
    )


class ASTParser:
    tables = load_parser_tables()

    def __init__(
        self,
        source: str,
        entrypoint: str,
    ) -> None:
        self.scanner = tokens.create_scanner(source)
        transformers = {
            'create_parameters': self.create_parameters,
            'create_function': self.create_function,
            'create_constant': self.create_constant,
            'create_function': self.create_function,
            'create_name': self.create_name,
        }

        self.parser = ParserAutomaton(
            self.scanner,
            self.tables[entrypoint],
            transformers
        )

    def create_module(self, items: typing.List[NodeItem], flags: int) -> NodeItem:
        prettyprinter.cpprint(items)
        assert False, 'Not Implemented'

    def create_parameters(self, items: typing.List[NodeItem], flags: int) -> NodeItem:
        prettyprinter.cpprint(items)
        assert False, 'Not Implemented'

    def create_function(self, items: typing.List[NodeItem], flags: int) -> NodeItem:
        prettyprinter.cpprint(items)
        assert False, 'Not Implemented'

    def create_constant(self, items: typing.List[NodeItem], flags: int) -> NodeItem:
        start, end = self.parser.get_item_span(items)
        return ast.ConstantNode(
            start=start,
            end=end,
            kind=ast.ConstantKind(flags),
        )

    def create_name(self, items: typing.List[NodeItem], flags: int) -> NodeItem:
        assert len(items) == 1
        item = items[0]
        start, end = self.parser.get_item_span(items)

        assert item.kind is StdTokenKind.IDENTIFIER
        return ast.NameNode(start=start, end=end, value=item.content)

    def parse(self) -> NodeItem:
        return self.parser.parse()
