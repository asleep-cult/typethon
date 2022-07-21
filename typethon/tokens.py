from __future__ import annotations

import enum
import typing

import attr


class TokenType(enum.IntEnum):
    EOF = enum.auto()
    NEWLINE = enum.auto()
    INDENT = enum.auto()
    DEDENT = enum.auto()
    IDENTIFIER = enum.auto()
    STRING = enum.auto()
    NUMBER = enum.auto()
    DIRECTIVE = enum.auto()

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

    FALSE = enum.auto()
    NONE = enum.auto()
    TRUE = enum.auto()
    AND = enum.auto()
    AS = enum.auto()
    ASSERT = enum.auto()
    ASYNC = enum.auto()
    AWAIT = enum.auto()
    BREAK = enum.auto()
    CLASS = enum.auto()
    CONTINUE = enum.auto()
    DEF = enum.auto()
    DEL = enum.auto()
    ELIF = enum.auto()
    ELSE = enum.auto()
    EXCEPT = enum.auto()
    FINALLY = enum.auto()
    FOR = enum.auto()
    FROM = enum.auto()
    GLOBAL = enum.auto()
    IF = enum.auto()
    IMPORT = enum.auto()
    IN = enum.auto()
    IS = enum.auto()
    LAMBDA = enum.auto()
    NONLOCAL = enum.auto()
    NOT = enum.auto()
    OR = enum.auto()
    PASS = enum.auto()
    RAISE = enum.auto()
    RETURN = enum.auto()
    TRY = enum.auto()
    WHILE = enum.auto()
    WITH = enum.auto()
    YIELD = enum.auto()

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


KEYWORDS = {
    'False': TokenType.FALSE,
    'None': TokenType.NONE,
    'True': TokenType.TRUE,
    'and': TokenType.AND,
    'as': TokenType.AS,
    'assert': TokenType.ASSERT,
    'async': TokenType.ASYNC,
    'await': TokenType.AWAIT,
    'break': TokenType.BREAK,
    'class': TokenType.CLASS,
    'continue': TokenType.CONTINUE,
    'def': TokenType.DEF,
    'del': TokenType.DEL,
    'elif': TokenType.ELIF,
    'else': TokenType.ELSE,
    'except': TokenType.EXCEPT,
    'finally': TokenType.FINALLY,
    'for': TokenType.FOR,
    'from': TokenType.FROM,
    'global': TokenType.GLOBAL,
    'if': TokenType.IF,
    'import': TokenType.IMPORT,
    'in': TokenType.IN,
    'is': TokenType.IS,
    'lambda': TokenType.LAMBDA,
    'nonlocal': TokenType.NONLOCAL,
    'not': TokenType.NOT,
    'or': TokenType.OR,
    'pass': TokenType.PASS,
    'raise': TokenType.RAISE,
    'return': TokenType.RETURN,
    'try': TokenType.TRY,
    'while': TokenType.WHILE,
    'with': TokenType.WITH,
    'yield': TokenType.YIELD,
}


@attr.s(kw_only=True, slots=True)
class Token:
    type: TokenType = attr.ib(eq=True)
    start: int = attr.ib(eq=False)
    end: int = attr.ib(eq=False)


@attr.s(kw_only=True, slots=True)
class IdentifierToken(Token):
    type: typing.Literal[TokenType.IDENTIFIER] = attr.ib(init=False, default=TokenType.IDENTIFIER)
    content: str = attr.ib(eq=True)

    def get_keyword(self) -> typing.Optional[TokenType]:
        return KEYWORDS.get(self.content)


@attr.s(kw_only=True, slots=True)
class NumberToken(Token):
    type: typing.Literal[TokenType.NUMBER] = attr.ib(init=False, default=TokenType.NUMBER)
    content: str = attr.ib(eq=True)
    flags: NumberTokenFlags = attr.ib(eq=False)


@attr.s(kw_only=True, slots=True)
class StringToken(Token):
    type: typing.Literal[TokenType.STRING] = attr.ib(init=False, default=TokenType.STRING)
    content: str = attr.ib(eq=True)
    flags: StringTokenFlags = attr.ib(eq=False)


@attr.s(kw_only=True, slots=True)
class IndentToken(Token):
    type: typing.Literal[TokenType.INDENT] = attr.ib(init=False, default=TokenType.INDENT)
    inconsistent: bool = attr.ib(default=False, eq=False)


@attr.s(kw_only=True, slots=True)
class DedentToken(Token):
    type: typing.Literal[TokenType.DEDENT] = attr.ib(init=False, default=TokenType.DEDENT)
    inconsistent: bool = attr.ib(default=False, eq=False)
    diverges: bool = attr.ib(default=False, eq=False)


@attr.s(kw_only=True, slots=True)
class DirectiveToken(Token):
    type: typing.Literal[TokenType.DIRECTIVE] = attr.ib(init=False, default=TokenType.DIRECTIVE)
    content: str = attr.ib(eq=False)
