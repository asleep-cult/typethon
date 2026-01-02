import enum
from ..tokens import TokenMap


class TokenKind(enum.Enum):
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


TOKENS: TokenMap[TokenKind] = (
    ('(', TokenKind.OPENPAREN),
    (')', TokenKind.CLOSEPAREN),
    ('[', TokenKind.OPENBRACKET),
    (']', TokenKind.CLOSEBRACKET),
    ('{', TokenKind.OPENBRACE),
    ('}', TokenKind.CLOSEBRACE),
    (':', TokenKind.COLON),
    (',', TokenKind.COMMA),
    (';', TokenKind.SEMICOLON),
    ('.', TokenKind.DOT),
    ('+', TokenKind.PLUS),
    ('-', TokenKind.MINUS),
    ('*', TokenKind.STAR),
    ('@', TokenKind.AT),
    ('/', TokenKind.SLASH),
    ('|', TokenKind.VERTICALBAR),
    ('&', TokenKind.AMPERSAND),
    ('<', TokenKind.LTHAN),
    ('>', TokenKind.GTHAN),
    ('=', TokenKind.EQUAL),
    ('%', TokenKind.PERCENT),
    ('~', TokenKind.TILDE),
    ('^', TokenKind.CIRCUMFLEX),

    ('//', TokenKind.DOUBLESLASH),
    ('==', TokenKind.EQEQUAL),
    ('!=', TokenKind.NOTEQUAL),
    ('<=', TokenKind.LTHANEQ),
    ('>=', TokenKind.GTHANEQ),
    ('<<', TokenKind.DOUBLELTHAN),
    ('>>', TokenKind.DOUBLEGTHAN),
    ('**', TokenKind.DOUBLESTAR),
    ('+=', TokenKind.PLUSEQUAL),
    ('-=', TokenKind.MINUSEQUAL),
    ('*=', TokenKind.STAREQUAL),
    ('/=', TokenKind.SLASHEQUAL),
    ('@=', TokenKind.ATEQUAL),
    ('%=', TokenKind.PERCENTEQUAL),
    ('&=', TokenKind.AMPERSANDEQUAL),
    ('|=', TokenKind.VERTICALBAREQUAL),
    ('^=', TokenKind.CIRCUMFLEXEQUAL),
    (':=', TokenKind.COLONEQUAL),
    ('->', TokenKind.RARROW),

    ('<<=', TokenKind.DOUBLELTHANEQUAL),
    ('>>=', TokenKind.DOUBLEGTHANEQUAL),
    ('**=', TokenKind.DOUBLESTAREQUAL),
    ('//=', TokenKind.DOUBLESLASHEQUAL),
    ('...', TokenKind.ELLIPSIS),
)
