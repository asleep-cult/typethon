import enum
import typing

from ..syntax.scanner import Scanner
from ..syntax.tokens import (
    TokenMap,
    Token,
)


class GrammarTokenKind(enum.Enum):
    AT = enum.auto()
    COLON = enum.auto()
    VERTICALBAR = enum.auto()
    OPENPAREN = enum.auto()
    CLOSEPAREN = enum.auto()
    STAR = enum.auto()
    PLUS = enum.auto()
    QUESTION = enum.auto()
    EXCLAMATION = enum.auto()


class UnitEnum(enum.Enum):
    NOTHING = enum.auto()


SimpleTokenKind = typing.Literal[
    GrammarTokenKind.AT,
    GrammarTokenKind.COLON,
    GrammarTokenKind.VERTICALBAR,
    GrammarTokenKind.OPENPAREN,
    GrammarTokenKind.CLOSEPAREN,
    GrammarTokenKind.STAR,
    GrammarTokenKind.PLUS,
    GrammarTokenKind.QUESTION,
    GrammarTokenKind.EXCLAMATION,
]
GrammarToken = Token[SimpleTokenKind, typing.Literal[UnitEnum.NOTHING]]
GrammarScanner = Scanner[SimpleTokenKind, typing.Literal[UnitEnum.NOTHING]]


GRAMMAR_TOKENS: TokenMap[SimpleTokenKind] = (
    ('@', GrammarTokenKind.AT),
    (':', GrammarTokenKind.COLON),
    ('|', GrammarTokenKind.VERTICALBAR),
    ('(', GrammarTokenKind.OPENPAREN),
    (')', GrammarTokenKind.CLOSEPAREN),
    ('*', GrammarTokenKind.STAR),
    ('+', GrammarTokenKind.PLUS),
    ('?', GrammarTokenKind.QUESTION),
    ('!', GrammarTokenKind.EXCLAMATION),
)
