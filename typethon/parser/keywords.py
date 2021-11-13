import enum


class KeywordType:
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
    'False': KeywordType.FALSE,
    'None': KeywordType.NONE,
    'True': KeywordType.TRUE,
    'and': KeywordType.AND,
    'assert': KeywordType.ASSERT,
    'async': KeywordType.ASYNC,
    'await': KeywordType.AWAIT,
    'break': KeywordType.BREAK,
    'class': KeywordType.CLASS,
    'continue': KeywordType.CONTINUE,
    'def': KeywordType.DEF,
    'del': KeywordType.DEL,
    'elif': KeywordType.ELIF,
    'else': KeywordType.ELSE,
    'except': KeywordType.EXCEPT,
    'finally': KeywordType.FINALLY,
    'for': KeywordType.FOR,
    'from': KeywordType.FROM,
    'global': KeywordType.GLOBAL,
    'if': KeywordType.IF,
    'import': KeywordType.IMPORT,
    'in': KeywordType.IN,
    'is': KeywordType.IS,
    'lambda': KeywordType.LAMBDA,
    'nonlocal': KeywordType.NONLOCAL,
    'not': KeywordType.NOT,
    'or': KeywordType.OR,
    'pass': KeywordType.PASS,
    'raise': KeywordType.RAISE,
    'return': KeywordType.RETURN,
    'try': KeywordType.TRY,
    'while': KeywordType.WHILE,
    'with': KeywordType.WITH,
    'yield': KeywordType.YIELD,
}
