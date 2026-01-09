import enum
from ..tokens import Token as TokenT
from ..tokens import TokenMap
from ..scanner import Scanner


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
    TICK = enum.auto()

    DOUBLECOLON = enum.auto()
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
    ('\'', TokenKind.TICK),

    ('::', TokenKind.DOUBLECOLON),
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


class KeywordKind(enum.Enum):
    SELF = enum.auto()
    TRUE = enum.auto()
    FALSE = enum.auto()
    AND = enum.auto()
    BREAK = enum.auto()
    CLASS = enum.auto()
    CONTINUE = enum.auto()
    DEF = enum.auto()
    ELIF = enum.auto()
    ELSE = enum.auto()
    FOR = enum.auto()
    FROM = enum.auto()
    IF = enum.auto()
    IMPORT = enum.auto()
    IN = enum.auto()
    IS = enum.auto()
    NOT = enum.auto()
    OR = enum.auto()
    PASS = enum.auto()
    RETURN = enum.auto()
    WHILE = enum.auto()


KEYWORDS = (
    ('Self', KeywordKind.SELF),
    ('True', KeywordKind.TRUE),
    ('False', KeywordKind.FALSE),
    ('and', KeywordKind.AND),
    ('break', KeywordKind.BREAK),
    ('class', KeywordKind.CLASS),
    ('continue', KeywordKind.CONTINUE),
    ('def', KeywordKind.DEF),
    ('elif', KeywordKind.ELIF),
    ('else', KeywordKind.ELSE),
    ('for', KeywordKind.FOR),
    ('from', KeywordKind.FROM),
    ('if', KeywordKind.IF),
    ('import', KeywordKind.IMPORT),
    ('in', KeywordKind.IN),
    ('is', KeywordKind.IS),
    ('not', KeywordKind.NOT),
    ('or', KeywordKind.OR),
    ('pass', KeywordKind.PASS),
    ('return', KeywordKind.RETURN),
    ('while', KeywordKind.WHILE),
)

Token = TokenT[TokenKind, KeywordKind]

MATCHED_TOKENS = {
    TokenKind.OPENPAREN: TokenKind.CLOSEPAREN,
    TokenKind.OPENBRACKET: TokenKind.CLOSEBRACKET,
    TokenKind.OPENBRACE: TokenKind.CLOSEBRACE,
}


def create_scanner(source: str) -> Scanner[TokenKind, KeywordKind]:
    return Scanner(
        source,
        tokens=TOKENS,
        keywords=KEYWORDS,
        matched_tokens=MATCHED_TOKENS,
    )
