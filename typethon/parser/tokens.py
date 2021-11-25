from __future__ import annotations

import enum

from ..textrange import TextRange


class TokenType(enum.IntEnum):
    ERROR = enum.auto()
    EOF = enum.auto()
    NEWLINE = enum.auto()
    INDENT = enum.auto()
    DEDENT = enum.auto()
    IDENTIFIER = enum.auto()
    STRING = enum.auto()
    NUMBER = enum.auto()

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
    VERTICELBAR = enum.auto()
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


KEYWORDS = {
    'False': TokenType.FALSE,
    'None': TokenType.NONE,
    'True': TokenType.TRUE,
    'and': TokenType.AND,
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


class Token(TextRange):
    __slots__ = ('type', 'range')

    def __init__(self, type: TokenType, range: TextRange) -> None:
        self.type = type
        self.range = range

    def __repr__(self):
        return f'<{self.__class__.__name__} type={self.type!r} {self.range!r}>'

    def is_identifier(self) -> bool:
        return self.type is TokenType.IDENTIFIER

    def is_string(self) -> bool:
        return self.type is TokenType.STRING

    def is_number(self) -> bool:
        return self.type is TokenType.NUMBER


class IdentifierToken(Token):
    __slots__ = ('content',)

    def __init__(self, range: TextRange, content: str) -> None:
        super().__init__(TokenType.IDENTIFIER, range)
        self.content = content

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.content!r} {self.range!r}>'


class NumberTokenFlags(enum.IntFlag):
    NONE = 0

    BINARY = enum.auto()
    OCTAL = enum.auto()
    HEXADECIMAL = enum.auto()

    INTEGER = enum.auto()
    FLOAT = enum.auto()

    IMAGINARY = enum.auto()

    # Exceptional
    EMPTY = enum.auto()
    LEADING_ZERO = enum.auto()
    CONSECUTIVE_UNDERSCORES = enum.auto()
    TRAILING_UNDERSCORE = enum.auto()
    INVALID_EXPONENT = enum.auto()


class NumberToken(Token):
    __slots__ = ('flags', 'content')

    def __init__(self, range: TextRange, flags: StringTokenFlags, content: str) -> None:
        super().__init__(TokenType.NUMBER, range)
        self.flags = flags
        self.content = content

    def __repr__(self):
        return f'<{self.__class__.__name__} flags={self.flags!r} {self.content!r} {self.range!r}>'


class StringTokenFlags(enum.IntFlag):
    NONE = 0

    RAW = enum.auto()
    BYTES = enum.auto()
    FORMAT = enum.auto()

    # Exceptional
    UNTERMINATED = enum.auto()
    INVALID_PREFIX = enum.auto()


class StringToken(Token):
    __slots__ = ('flags', 'content',)

    def __init__(self, range: TextRange, flags: StringTokenFlags, content: str) -> None:
        super().__init__(TokenType.STRING, range)
        self.flags = flags
        self.content = content

    def __repr__(self):
        return f'<{self.__class__.__name__} flags={self.flags!r} {self.content!r} {self.range!r}>'


class IndentToken(Token):
    __slots__ = ('inconsistent',)

    def __init__(self, range: TextRange, inconsistent: bool) -> None:
        super().__init__(TokenType.INDENT, range)
        self.inconsistent = inconsistent

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} inconsistent={self.inconsistent} {self.range!r}>'


class DedentToken(Token):
    __slots__ = ('inconsistent', 'diverges')

    def __init__(self, range: TextRange, inconsistent: bool, diverges: bool) -> None:
        super().__init__(TokenType.DEDENT, range)
        self.inconsistent = inconsistent
        self.diverges = diverges

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} inconsistent={self.inconsistent}'
            f' diverges={self.diverges} {self.range!r}>'
        )
