import enum


class KeywordKind(enum.Enum):
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


KEYWORDS = (
    ('False', KeywordKind.FALSE),
    ('None', KeywordKind.NONE),
    ('True', KeywordKind.TRUE),
    ('and', KeywordKind.AND),
    ('as', KeywordKind.AS),
    ('assert', KeywordKind.ASSERT),
    ('async', KeywordKind.ASYNC),
    ('await', KeywordKind.AWAIT),
    ('break', KeywordKind.BREAK),
    ('class', KeywordKind.CLASS),
    ('continue', KeywordKind.CONTINUE),
    ('def', KeywordKind.DEF),
    ('del', KeywordKind.DEL),
    ('elif', KeywordKind.ELIF),
    ('else', KeywordKind.ELSE),
    ('except', KeywordKind.EXCEPT),
    ('finally', KeywordKind.FINALLY),
    ('for', KeywordKind.FOR),
    ('from', KeywordKind.FROM),
    ('global', KeywordKind.GLOBAL),
    ('if', KeywordKind.IF),
    ('import', KeywordKind.IMPORT),
    ('in', KeywordKind.IN),
    ('is', KeywordKind.IS),
    ('lambda', KeywordKind.LAMBDA),
    ('nonlocal', KeywordKind.NONLOCAL),
    ('not', KeywordKind.NOT),
    ('or', KeywordKind.OR),
    ('pass', KeywordKind.PASS),
    ('raise', KeywordKind.RAISE),
    ('return', KeywordKind.RETURN),
    ('try', KeywordKind.TRY),
    ('while', KeywordKind.WHILE),
    ('with', KeywordKind.WITH),
    ('yield', KeywordKind.YIELD),
)
