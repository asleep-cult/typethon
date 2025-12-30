from __future__ import annotations

import enum
import typing

import attr

TokenKindT = typing.TypeVar('TokenKindT')
KeywordT = typing.TypeVar('KeywordT', bound=enum.IntEnum)


class TokenKind(enum.IntEnum):
    EOF = enum.auto()

    KEYWORD = enum.auto()
    INDENT = enum.auto()
    DEDENT = enum.auto()
    IDENTIFIER = enum.auto()
    STRING = enum.auto()
    NUMBER = enum.auto()
    DIRECTIVE = enum.auto()

    NEWLINE = enum.auto()

    OPENPAREN = enum.auto()
    CLOSEPAREN = enum.auto()
    OPENBRACKET = enum.auto()
    CLOSEBRACKET = enum.auto()
    OPENBRACE = enum.auto()
    CLOSEBRACE = enum.auto()
    COLON = enum.auto()
    COMMA = enum.auto()
    SEMICOLON = enum.auto()
    DOT = enum.auto()
    PLUS = enum.auto()
    MINUS = enum.auto()
    STAR = enum.auto()
    AT = enum.auto()
    SLASH = enum.auto()
    VERTICALBAR = enum.auto()
    AMPERSAND = enum.auto()
    LTHAN = enum.auto()
    GTHAN = enum.auto()
    EQUAL = enum.auto()
    PERCENT = enum.auto()
    TILDE = enum.auto()
    CIRCUMFLEX = enum.auto()
    QUESTION = enum.auto()

    DOUBLESLASH = enum.auto()
    EQEQUAL = enum.auto()
    NOTEQUAL = enum.auto()
    LTHANEQ = enum.auto()
    GTHANEQ = enum.auto()
    DOUBLELTHAN = enum.auto()
    DOUBLEGTHAN = enum.auto()
    DOUBLESTAR = enum.auto()
    PLUSEQUAL = enum.auto()
    MINUSEQUAL = enum.auto()
    STAREQUAL = enum.auto()
    SLASHEQUAL = enum.auto()
    ATEQUAL = enum.auto()
    PERCENTEQUAL = enum.auto()
    AMPERSANDEQUAL = enum.auto()
    VERTICALBAREQUAL = enum.auto()
    CIRCUMFLEXEQUAL = enum.auto()
    COLONEQUAL = enum.auto()
    RARROW = enum.auto()

    DOUBLELTHANEQUAL = enum.auto()
    DOUBLEGTHANEQUAL = enum.auto()
    DOUBLESTAREQUAL = enum.auto()
    DOUBLESLASHEQUAL = enum.auto()
    ELLIPSIS = enum.auto()


    EUNMATCHED = enum.auto()
    EINVALID = enum.auto()


class NumberTokenFlags(enum.IntFlag):
    NONE = 0

    BINARY = enum.auto()
    OCTAL = enum.auto()
    HEXADECIMAL = enum.auto()

    INTEGER = enum.auto()
    FLOAT = enum.auto()

    IMAGINARY = enum.auto()

    EMPTY = enum.auto()
    LEADING_ZERO = enum.auto()
    CONSECUTIVE_UNDERSCORES = enum.auto()
    TRAILING_UNDERSCORE = enum.auto()
    INVALID_EXPONENT = enum.auto()


class StringTokenFlags(enum.IntFlag):
    NONE = 0

    RAW = enum.auto()
    BYTES = enum.auto()
    FORMAT = enum.auto()

    UNTERMINATED = enum.auto()
    DUPLICATE_PREFIX = enum.auto()


@attr.s(kw_only=True, slots=True)
class TokenData(typing.Generic[TokenKindT]):
    kind: TokenKindT = attr.ib(eq=True)
    start: int = attr.ib(eq=False)
    end: int = attr.ib(eq=False)

    def is_keyword(self, *kinds: typing.Any) -> bool:
        return False


@attr.s(kw_only=True, slots=True)
class KeywordToken(typing.Generic[KeywordT], TokenData[TokenKind.KEYWORD]):
    kind: typing.Literal[TokenKind.KEYWORD] = attr.ib(init=False, default=TokenKind.KEYWORD)
    keyword: KeywordT = attr.ib()

    def is_keyword(self, *kinds: KeywordT) -> bool:
        return self.keyword in kinds


@attr.s(kw_only=True, slots=True)
class IdentifierToken(TokenData[TokenKind.IDENTIFIER]):
    kind: typing.Literal[TokenKind.IDENTIFIER] = attr.ib(init=False, default=TokenKind.IDENTIFIER)
    content: str = attr.ib(eq=True)


@attr.s(kw_only=True, slots=True)
class NumberToken(TokenData[TokenKind.NUMBER]):
    kind: typing.Literal[TokenKind.NUMBER] = attr.ib(init=False, default=TokenKind.NUMBER)
    content: str = attr.ib(eq=True)
    flags: NumberTokenFlags = attr.ib(eq=False)


@attr.s(kw_only=True, slots=True)
class StringToken(TokenData[TokenKind.STRING]):
    kind: typing.Literal[TokenKind.STRING] = attr.ib(init=False, default=TokenKind.STRING)
    content: str = attr.ib(eq=True)
    flags: StringTokenFlags = attr.ib(eq=False)


@attr.s(kw_only=True, slots=True)
class IndentToken(TokenData[TokenKind.INDENT]):
    kind: typing.Literal[TokenKind.INDENT] = attr.ib(init=False, default=TokenKind.INDENT)
    inconsistent: bool = attr.ib(default=False, eq=False)


@attr.s(kw_only=True, slots=True)
class DedentToken(TokenData[TokenKind.DEDENT]):
    kind: typing.Literal[TokenKind.DEDENT] = attr.ib(init=False, default=TokenKind.DEDENT)
    inconsistent: bool = attr.ib(default=False, eq=False)
    diverges: bool = attr.ib(default=False, eq=False)


@attr.s(kw_only=True, slots=True)
class DirectiveToken(TokenData[TokenKind.DIRECTIVE]):
    kind: typing.Literal[TokenKind.DIRECTIVE] = attr.ib(init=False, default=TokenKind.DIRECTIVE)
    content: str = attr.ib(eq=False)


SimpleTokenKind = typing.Literal[
    TokenKind.EOF,
    TokenKind.NEWLINE,

    TokenKind.OPENPAREN,
    TokenKind.CLOSEPAREN,
    TokenKind.OPENBRACKET,
    TokenKind.CLOSEBRACKET,
    TokenKind.OPENBRACE,
    TokenKind.CLOSEBRACE,
    TokenKind.COLON,
    TokenKind.COMMA,
    TokenKind.SEMICOLON,
    TokenKind.DOT,
    TokenKind.PLUS,
    TokenKind.MINUS,
    TokenKind.STAR,
    TokenKind.AT,
    TokenKind.SLASH,
    TokenKind.VERTICALBAR,
    TokenKind.AMPERSAND,
    TokenKind.LTHAN,
    TokenKind.GTHAN,
    TokenKind.EQUAL,
    TokenKind.PERCENT,
    TokenKind.TILDE,
    TokenKind.CIRCUMFLEX,
    TokenKind.QUESTION,

    TokenKind.DOUBLESLASH,
    TokenKind.EQEQUAL,
    TokenKind.NOTEQUAL,
    TokenKind.LTHANEQ,
    TokenKind.GTHANEQ,
    TokenKind.DOUBLELTHAN,
    TokenKind.DOUBLEGTHAN,
    TokenKind.DOUBLESTAR,
    TokenKind.PLUSEQUAL,
    TokenKind.MINUSEQUAL,
    TokenKind.STAREQUAL,
    TokenKind.SLASHEQUAL,
    TokenKind.ATEQUAL,
    TokenKind.PERCENTEQUAL,
    TokenKind.AMPERSANDEQUAL,
    TokenKind.VERTICALBAREQUAL,
    TokenKind.CIRCUMFLEXEQUAL,
    TokenKind.COLONEQUAL,
    TokenKind.RARROW,

    TokenKind.DOUBLELTHANEQUAL,
    TokenKind.DOUBLEGTHANEQUAL,
    TokenKind.DOUBLESTAREQUAL,
    TokenKind.DOUBLESLASHEQUAL,
    TokenKind.ELLIPSIS,

    TokenKind.EUNMATCHED,
    TokenKind.EINVALID,
]

Token = typing.Union[
    TokenData[SimpleTokenKind],
    KeywordToken[KeywordT],
    IdentifierToken,
    NumberToken,
    StringToken,
    IndentToken,
    DedentToken,
    DirectiveToken,
]
