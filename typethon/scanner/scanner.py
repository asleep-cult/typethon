from __future__ import annotations

import codecs
import enum
import io

from .exceptions import BadEncodingDeclaration
from .stringreader import EOF, StringReader

TABSIZE = 8
ALTTABSIZE = 1


class EncodingDetector:
    def __init__(self, buffer: io.IOBase, *, default='utf-8'):
        self.buffer = buffer
        self.default = default

    def readline(self):
        line = self.buffer.readline()
        if not isinstance(line, bytes):
            raise BadEncodingDeclaration(
                f'readline should return a byte string, got {line.__class__.__name__}')
        return line

    def parse_declaration(self, line: bytes, *, bom: bool = False) -> str:
        try:
            line = line.decode('utf-8')
        except UnicodeDecodeError:
            raise BadEncodingDeclaration('The encoding declaration is not a valid UTF-8 sequence')

        reader = StringReader(line)
        reader.skipws()
        if (not reader.expect('#')
                or not reader.skipfind('coding')
                or not reader.expect((':', '='))):
            return None

        reader.skipspaces()
        encoding = self.normalize_encoding(
            reader.accumulate(
                lambda char: (char.isalnum() or char == '_'
                              or char == '-' or char == '.')))

        try:
            codec = codecs.lookup(encoding)
        except LookupError:
            raise BadEncodingDeclaration(
                f'The encoding declaration refers to an unknown encoding: {encoding!r}')
        else:
            if not getattr(codec, '_is_text_encoding', True):
                raise BadEncodingDeclaration(
                    f'The encoding declaration refers to a non-text encoding: {encoding!r}')

        if bom:
            if encoding != 'utf-8':
                raise BadEncodingDeclaration(
                    f'Encoding mismatch for file with UTF-8 BOM: {encoding!r}')
            encoding = 'utf-8-sig'

        return encoding

    def normalize_encoding(self, endocing):
        # https://github.com/python/cpython/blob/main/Lib/tokenize.py#L286

        sanitized = endocing[:12].lower().replace('_', '-')
        if sanitized == 'utf-8' or sanitized.startswith('utf-8-'):
            return 'utf-8'
        else:
            encodings = ('latin-1', 'iso-8859-1', 'iso-latin-1')
            if sanitized in encodings or sanitized.startswith(encodings):
                return 'iso-8859-1'

        return endocing

    def detect(self) -> str:
        line = self.readline()
        if line.startswith(codecs.BOM_UTF8):
            line = line[len(codecs.BOM_UTF8):]
            default = 'utf-8-sig'
        else:
            default = self.default

        if not line:
            return default

        encoding = self.parse_declaration(line)
        if encoding is not None:
            return encoding

        if line.strip() != b'#':
            return default

        line = self.readline()
        if not line:
            return default

        encoding = self.parse_declaration(line)
        if encoding is not None:
            return encoding

        return default

    @classmethod
    def open(cls, file, **kwargs) -> io.TextIOWrapper:
        fp = open(file, 'rb')
        encoding = cls(fp, default=kwargs.pop('encoding', 'utf-8')).detect()
        fp.seek(0)
        return io.TextIOWrapper(fp, encoding=encoding, **kwargs)


def _is_identifier_start(char: str) -> bool:
    return ('a' <= char <= 'z'
            or 'A' <= char <= 'Z'
            or char == '_'
            or char >= '\x80')


def _is_identifier(char: str) -> bool:
    return ('a' <= char <= 'z'
            or 'A' <= char <= 'Z'
            or '0' <= char <= '9'
            or char == '_'
            or char >= '\x80')


def _is_digit(char: str) -> bool:
    return '0' <= char <= '9'


def _is_terminal(char: str) -> bool:
    return char == '\'' or char == '"'


def _is_eof(char: str) -> bool:
    return char is EOF


def _is_blank(char: str) -> bool:
    return char == '#' or char == '\n' or char == '\\'


def _is_comment(char: str) -> bool:
    return char == '#'


class TokenType(enum.IntEnum):
    ERROR = enum.auto()
    EOF = enum.auto()
    NEWLINE = enum.auto()
    INDENT = enum.auto()
    DEDENT = enum.auto()
    IDENTIFIER = enum.auto()
    STRING = enum.auto()
    NUMBER = enum.auto()

    LPAREN = enum.auto()
    RPAREN = enum.auto()
    LBARACKET = enum.auto()
    RBRACKET = enum.auto()
    LBRACE = enum.auto()
    RBRACE = enum.auto()
    COLON = enum.auto()
    COMMA = enum.auto()
    SEMICOLON = enum.auto()
    DOT = enum.auto()
    PLUS = enum.auto()
    MINUS = enum.auto()
    STAR = enum.auto()
    AT = enum.auto()
    SLASH = enum.auto()
    DOUBLESLASH = enum.auto()
    VBAR = enum.auto()
    AMPERSAND = enum.auto()
    LTHAN = enum.auto()
    GTHAN = enum.auto()
    EQUAL = enum.auto()
    PERCENT = enum.auto()
    TILDE = enum.auto()
    CIRCUMFLEX = enum.auto()
    EQEQUAL = enum.auto()
    NOTEQUAL = enum.auto()
    LTHANEQ = enum.auto()
    GTHANEQ = enum.auto()
    LSHIFT = enum.auto()
    RSHIFT = enum.auto()
    DOUBLESTAR = enum.auto()
    PLUSEQUAL = enum.auto()
    MINUSEQUAL = enum.auto()
    STAREQUAL = enum.auto()
    SLASHEQUAL = enum.auto()
    PERCENTEQUAL = enum.auto()
    AMPERSANDEQUAL = enum.auto()
    VBAREQUAL = enum.auto()
    CIRCUMFLEXEQUAL = enum.auto()
    LSHIFTEQUAL = enum.auto()
    RSHIFTEQUAL = enum.auto()
    DOUBLESTARQEUAL = enum.auto()
    DOUBLESLASHEQUAL = enum.auto()
    ATEQUAL = enum.auto()
    RARROW = enum.auto()
    ELLIPSIS = enum.auto()


_PARENMAP = {
    TokenType.LPAREN: TokenType.RPAREN,
    TokenType.LBARACKET: TokenType.RBRACKET,
    TokenType.LBRACE: TokenType.RBRACE,
}


class Token:
    __slots__ = ('scanner', 'type', 'startpos', 'endpos', 'lineno')

    def __init__(self, scanner: Scanner, type: TokenType,
                 startpos: int, endpos: int, lineno: int) -> None:
        self.scanner = scanner
        self.type = type
        self.startpos = startpos
        self.endpos = endpos
        self.lineno = lineno

    def __repr__(self):
        return (f'<{self.__class__.__name__} type={self.type!r}'
                f' ({self.lineno}:{self.startpos}-{self.endpos})>')

    def span(self):
        start = self.scanner._linespans[self.lineno][0]
        return start + self.startpos, start + self.endpos


class IdentifierToken(Token):
    __slots__ = ('content',)

    def __init__(self, scanner: Scanner, startpos: int, endpos: int,
                 lineno: int, content: str) -> None:
        super().__init__(scanner, TokenType.IDENTIFIER, startpos, endpos, lineno)
        self.content = content

    def __repr__(self):
        return (f'<{self.__class__.__name__} type={self.type!r}'
                f' {self.content!r} ({self.lineno}:{self.startpos}-{self.endpos})>')


class StringTokenFlags(enum.IntFlag):
    RAW = 1 << 0
    BYTES = 1 << 1
    FORMAT = 1 << 2


class StringToken(Token):
    __slots__ = ('content', 'flags')

    def __init__(self, scanner: Scanner, startpos: int, endpos: int, lineno: int,
                 content: str, flags: StringTokenFlags) -> None:
        super().__init__(scanner, TokenType.STRING, startpos, endpos, lineno)
        self.content = content
        self.flags = flags

    def __repr__(self):
        return (f'<{self.__class__.__name__} type={self.type!r}'
                f' {self.content!r} ({self.lineno}:{self.startpos}-{self.endpos})>')


class NumericTokenFlags(enum.IntFlag):
    BINARY = 1 << 0
    OCTAL = 1 << 1
    HEXADECIMAL = 1 << 2
    INTEGER = 1 << 3
    FLOAT = 1 << 4
    IMAGINARY = 1 << 5


class NumericToken(Token):
    __slots__ = ('content', 'flags')

    def __init__(self, scanner: Scanner, startpos: int, endpos: int, lineno: int,
                 content: str, flags: NumericTokenFlags) -> None:
        super().__init__(scanner, TokenType.NUMBER, startpos, endpos, lineno)
        self.content = content
        self.flags = flags

    def __repr__(self):
        return (f'<{self.__class__.__name__} type={self.type!r}'
                f' {self.content!r} ({self.lineno}:{self.startpos}-{self.endpos})>')


class ErrorTokenErrno(enum.Enum):
    E_TOKEN = enum.auto()
    E_PAREN = enum.auto()
    E_TABSPACE = enum.auto()
    E_DEDENT = enum.auto()
    E_LINECONT = enum.auto()


class ErrorToken(Token):
    __slots__ = ('errno',)

    def __init__(self, scanner: Scanner, startpos: int, endpos: int,
                 lineno: int, errno: ErrorTokenErrno) -> None:
        super().__init__(scanner, TokenType.ERROR, startpos, endpos, lineno)
        self.errno = errno

    def __repr__(self):
        return (f'<{self.__class__.__name__} type={self.type!r}'
                f' {self.errno!r} ({self.lineno}:{self.startpos}-{self.endpos})>')


class _TokenContext:
    def __init__(self, scanner: Scanner, reader: StringReader) -> None:
        self.scanner = scanner
        self.reader = reader
        self.startpos = None
        self.lineno = None

    def create_token(self, type: TokenType) -> Token:
        token = Token(self.scanner, type, self.startpos, self.reader.tell(), self.lineno)
        self.scanner._tokens.append(token)
        return token

    def create_identifier_token(self, content: str) -> IdentifierToken:
        token = IdentifierToken(self.scanner, self.startpos, self.reader.tell(),
                                self.lineno, content)
        self.scanner._tokens.append(token)
        return token

    def create_string_token(self, content: str, flags: StringTokenFlags) -> StringToken:
        token = StringToken(self.scanner, self.startpos, self.reader.tell(),
                            self.lineno, content, flags)
        self.scanner._tokens.append(token)
        return token

    def create_numeric_token(self, content: str, flags: NumericTokenFlags) -> NumericToken:
        token = NumericToken(self.scanner, self.startpos, self.reader.tell(),
                             self.lineno, content, flags)
        self.scanner._tokens.append(token)
        return token

    def create_error_token(self, errno: ErrorTokenErrno) -> ErrorTokenErrno:
        token = ErrorToken(self.scanner, self.startpos, self.reader.tell(),
                           self.lineno, errno)
        self.scanner._tokens.append(token)
        return token

    def __enter__(self) -> _TokenContext:
        self.startpos = self.reader.tell()
        self.lineno = len(self.scanner._linespans)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class Scanner:
    __slots__ = ('source', '_indentstack', '_parenstack', '_linespans', '_tokens',)

    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._indentstack = [(0, 0)]
        self._parenstack = []
        self._linespans = []
        self._tokens = []

    def _get_indent(self):
        return self._indentstack[-1][0]

    def _get_altindent(self):
        return self._indentstack[-1][1]

    def _add_paren(self, type: TokenType):
        self._parenstack.append(type)

    def _pop_paren(self) -> TokenType:
        return self._parenstack.pop()

    def readline(self) -> StringReader:
        lower = self.source.tell()
        line = self.source.readline()
        upper = self.source.tell()
        self._linespans.append((lower, upper))
        return StringReader(line)

    def create_ctx(self, reader) -> _TokenContext:
        return _TokenContext(self, reader)

    def _scan_indents(self, ctx: _TokenContext) -> bool:
        indent = 0
        altindent = 0
        while True:
            char = ctx.reader.peek(0)
            if _is_blank(char):
                if self._tokens:
                    self._tokens.pop(-1)
                return
            elif char == ' ':
                indent += 1
                altindent += 1
                ctx.reader.advance()
            elif char == '\t':
                indent += ((indent / TABSIZE) + 1) * TABSIZE
                altindent += ((indent / ALTTABSIZE) + 1) * ALTTABSIZE
                ctx.reader.advance()
            else:
                break

        if indent == self._get_indent():
            if altindent != self._get_altindent():
                ctx.create_error_token(ErrorTokenErrno.E_TABSPACE)
                return False
        elif indent > self._get_indent():
            if altindent <= self._get_altindent():
                ctx.create_error_token(ErrorTokenErrno.E_TABSPACE)
                return False

            self._indentstack.append((indent, altindent))
            ctx.create_token(TokenType.INDENT)
        else:
            while self._indentstack:
                if indent < self._get_altindent():
                    self._indentstack.pop()
                    ctx.create_token(TokenType.DEDENT)
                else:
                    break

            if indent != self._get_indent():
                ctx.create_error_token(ErrorTokenErrno.E_DEDENT)
                return False

            if altindent != self._get_altindent():
                ctx.create_error_token(ErrorTokenErrno.E_TABSPACE)
                return False

        return True

    def _scan_identifier(self, ctx: _TokenContext) -> None:
        content = ctx.reader.accumulate(_is_identifier)
        if _is_terminal(ctx.reader.peek(0)):
            self._scan_string(ctx, prefixes=content)
        else:
            ctx.create_identifier_token(content)

    def _scan_number(self, ctx: _TokenContext) -> None:
        pass

    def _scan_string(self, ctx: _TokenContext, *, prefixes=None) -> None:
        pass

    def _get_token(self, ctx: _TokenContext) -> TokenType:
        if ctx.reader.expect('.'):
            if ctx.reader.expect('.', 2):
                return TokenType.ELLIPSIS
            else:
                return TokenType.DOT
        elif ctx.reader.expect('+'):
            if ctx.reader.expect('='):
                return TokenType.PLUSEQUAL
            else:
                return TokenType.PLUS
        elif ctx.reader.expect('-'):
            if ctx.reader.expect('>'):
                return TokenType.RARROW
            elif ctx.reader.expect('='):
                return TokenType.MINUSEQUAL
            else:
                return TokenType.MINUS
        elif ctx.reader.expect('*'):
            if ctx.reader.expect('*'):
                if ctx.reader.expect('='):
                    return TokenType.DOUBLESTARQEUAL
                else:
                    return TokenType.DOUBLESTAR
            elif ctx.reader.expect('='):
                return TokenType.STAREQUAL
        elif ctx.reader.expect('@'):
            if ctx.reader.expect('='):
                return TokenType.ATEQUAL
            else:
                return TokenType.AT
        elif ctx.reader.expect('/'):
            if ctx.reader.expect('/'):
                if ctx.reader.expect('='):
                    return TokenType.DOUBLESLASHEQUAL
                else:
                    return TokenType.DOUBLESLASH
            elif ctx.reader.expect('='):
                return TokenType.SLASHEQUAL
        elif ctx.reader.expect('|'):
            if ctx.reader.expect('='):
                return TokenType.VBAREQUAL
            else:
                return TokenType.VBAR
        elif ctx.reader.expect('&'):
            if ctx.reader.expect('='):
                return TokenType.AMPERSANDEQUAL
            else:
                return TokenType.AMPERSAND
        elif ctx.reader.expect('<'):
            if ctx.reader.expect('<'):
                if ctx.reader.expect('='):
                    return TokenType.LSHIFTEQUAL
                else:
                    return TokenType.LSHIFT
            elif ctx.reader.expect('='):
                return TokenType.LTHANEQ
            else:
                return TokenType.LTHAN
        elif ctx.reader.expect('>'):
            if ctx.reader.expect('>'):
                if ctx.reader.expect('='):
                    return TokenType.RSHIFTEQUAL
                else:
                    return TokenType.RSHIFT
            elif ctx.reader.expect('='):
                return TokenType.GTHANEQ
            else:
                return TokenType.GTHAN
        elif ctx.reader.expect('='):
            if ctx.reader.expect('='):
                return TokenType.EQEQUAL
            else:
                return TokenType.EQUAL
        elif ctx.reader.expect('!'):
            if ctx.reader.expect('='):
                return TokenType.NOTEQUAL
        elif ctx.reader.expect('%'):
            if ctx.reader.expect('='):
                return TokenType.PERCENTEQUAL
            else:
                return TokenType.PERCENT
        elif ctx.reader.expect('^'):
            if ctx.reader.expect('='):
                return TokenType.CIRCUMFLEXEQUAL
            else:
                return TokenType.CIRCUMFLEX
        elif ctx.reader.expect('('):
            return TokenType.LPAREN
        elif ctx.reader.expect(')'):
            return TokenType.RPAREN
        elif ctx.reader.expect('['):
            return TokenType.LBARACKET
        elif ctx.reader.expect(']'):
            return TokenType.RBRACKET
        elif ctx.reader.expect('{'):
            self._add_paren(TokenType.LBRACE)
            return TokenType.LBRACE
        elif ctx.reader.expect('}'):
            return TokenType.RBRACE
        elif ctx.reader.expect(':'):
            return TokenType.COLON
        elif ctx.reader.expect(';'):
            return TokenType.SEMICOLON
        elif ctx.reader.expect(','):
            return TokenType.COMMA
        elif ctx.reader.expect('~'):
            return TokenType.TILDE

    def _scan_token(self, ctx: _TokenContext) -> bool:
        type = self._get_token(ctx)
        if type is not None:
            if type in _PARENMAP.keys():
                self._add_paren(type)
            elif type in _PARENMAP.values():
                if (not self._parenstack
                        or type is not _PARENMAP[self._pop_paren()]):
                    ctx.create_error_token(ErrorTokenErrno.E_PAREN)
                    return False

            ctx.create_token(type)
            return True

        ctx.create_error_token(ErrorTokenErrno.E_TOKEN)
        return False

    def scan(self):
        reader = None
        while True:
            if reader is None or reader.eof():
                reader = self.readline()
                newline = True
            else:
                newline = False

            with self.create_ctx(reader) as ctx:
                if newline and not self._parenstack:
                    try:
                        type = self._tokens[-1].type
                    except IndexError:
                        type = None

                    if type is not TokenType.NEWLINE:
                        if self._tokens:
                            ctx.create_token(TokenType.NEWLINE)

                        if not self._scan_indents(ctx):
                            break

                ctx.reader.skipws(newlines=True)
                char = ctx.reader.peek(0)

                if _is_identifier_start(char):
                    self._scan_identifier(ctx)
                elif _is_digit(char):
                    self._scan_number(ctx)
                elif _is_terminal(char):
                    self._scan_string(ctx)
                elif _is_comment(char):
                    reader = None
                elif _is_eof(char):
                    if ctx.reader.tell() == 0:
                        ctx.create_token(TokenType.EOF)
                        break
                else:
                    if not self._scan_token(ctx):
                        break

        return self._tokens
