from __future__ import annotations

import enum
import typing

import attr

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)


class StdTokenKind(enum.Enum):
    EOF = enum.auto()

    INDENT = enum.auto()
    DEDENT = enum.auto()
    IDENTIFIER = enum.auto()
    STRING = enum.auto()
    NUMBER = enum.auto()
    DIRECTIVE = enum.auto()

    NEWLINE = enum.auto()

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
    CHARACTER = enum.auto()

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


@attr.s(kw_only=True, slots=True)
class IdentifierToken(TokenData[StdTokenKind.IDENTIFIER]):
    kind: typing.Literal[StdTokenKind.IDENTIFIER] = attr.ib(init=False, default=StdTokenKind.IDENTIFIER)
    content: str = attr.ib(eq=True)


@attr.s(kw_only=True, slots=True)
class NumberToken(TokenData[StdTokenKind.NUMBER]):
    kind: typing.Literal[StdTokenKind.NUMBER] = attr.ib(init=False, default=StdTokenKind.NUMBER)
    content: str = attr.ib(eq=True)
    flags: NumberTokenFlags = attr.ib(eq=False)


@attr.s(kw_only=True, slots=True)
class StringToken(TokenData[StdTokenKind.STRING]):
    kind: typing.Literal[StdTokenKind.STRING] = attr.ib(init=False, default=StdTokenKind.STRING)
    content: str = attr.ib(eq=True)
    flags: StringTokenFlags = attr.ib(eq=False)


@attr.s(kw_only=True, slots=True)
class IndentToken(TokenData[StdTokenKind.INDENT]):
    kind: typing.Literal[StdTokenKind.INDENT] = attr.ib(init=False, default=StdTokenKind.INDENT)
    inconsistent: bool = attr.ib(default=False, eq=False)


@attr.s(kw_only=True, slots=True)
class DedentToken(TokenData[StdTokenKind.DEDENT]):
    kind: typing.Literal[StdTokenKind.DEDENT] = attr.ib(init=False, default=StdTokenKind.DEDENT)
    inconsistent: bool = attr.ib(default=False, eq=False)
    diverges: bool = attr.ib(default=False, eq=False)


@attr.s(kw_only=True, slots=True)
class DirectiveToken(TokenData[StdTokenKind.DIRECTIVE]):
    kind: typing.Literal[StdTokenKind.DIRECTIVE] = attr.ib(init=False, default=StdTokenKind.DIRECTIVE)
    content: str = attr.ib(eq=False)


SimpleTokenKind = typing.Literal[
    StdTokenKind.EOF,
    StdTokenKind.NEWLINE,
    StdTokenKind.INDENT,
    StdTokenKind.DEDENT,
    StdTokenKind.EUNMATCHED,
    StdTokenKind.EINVALID,
]

Token = typing.Union[
    TokenData[SimpleTokenKind],
    TokenData[TokenKindT],
    TokenData[KeywordKindT],
    IdentifierToken,
    NumberToken,
    StringToken,
    IndentToken,
    DedentToken,
    DirectiveToken,
]

TokenMap = typing.Tuple[typing.Tuple[str, TokenKindT], ...]
KeywordMap = typing.Tuple[typing.Tuple[str, KeywordKindT], ...]


STD_TOKENS: TokenMap[StdTokenKind] = (
    ('EOF', StdTokenKind.EOF),

    ('INDENT', StdTokenKind.INDENT),
    ('DEDENT', StdTokenKind.DEDENT),
    ('IDENTIFIER', StdTokenKind.IDENTIFIER),
    ('STRING', StdTokenKind.STRING),
    ('NUMBER', StdTokenKind.NUMBER),
    ('DIRECTIVE', StdTokenKind.DIRECTIVE),

    ('NEWLINE', StdTokenKind.NEWLINE),

    ('EUNMATCHED', StdTokenKind.EUNMATCHED),
    ('EINVALID', StdTokenKind.EINVALID),
)
