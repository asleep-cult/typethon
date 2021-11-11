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
    LBRACKET = enum.auto()
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
    RAW = enum.auto()
    BYTES = enum.auto()
    FORMAT = enum.auto()


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
    BINARY = enum.auto()
    OCTAL = enum.auto()
    HEXADECIMAL = enum.auto()
    INTEGER = enum.auto()
    FLOAT = enum.auto()
    IMAGINARY = enum.auto()


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
        self.startpos = self.reader.tell()
        self.lineno = self.scanner.lineno()

    def create_token(self, type: TokenType) -> None:
        self.scanner._tokens.append(
            Token(self.scanner, type, self.startpos, self.reader.tell(), self.lineno))

    def create_identifier_token(self, content: str) -> None:
        self.scanner._tokens.append(
            IdentifierToken(self.scanner, self.startpos, self.reader.tell(), self.lineno, content))

    def create_string_token(self, content: str, flags: StringTokenFlags) -> None:
        self.scanner._tokens.append(
            StringToken(self.scanner, self.startpos, self.reader.tell(),
                        self.lineno, content, flags))

    def create_numeric_token(self, content: str, flags: NumericTokenFlags) -> None:
        self.scanner._tokens.append(
            NumericToken(self.scanner, self.startpos, self.reader.tell(),
                         self.lineno, content, flags))

    def create_error_token(self, errno: ErrorTokenErrno) -> None:
        self.scanner._tokens.append(
            ErrorToken(self.scanner, self.startpos, self.reader.tell(), self.lineno, errno))


class _IndentScanner:
    __slots__ = ('scanner', 'stack', 'altstack')

    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner
        self.stack = [(0, 0)]

    def back(self) -> int:
        return self.stack[-1][0]

    def altback(self) -> int:
        return self.altstack[-1][1]

    def feed(self, reader: StringReader) -> None:
        token = Token(self.scanner, TokenType.NEWLINE,
                      reader.tell() - 1, reader.tell(), self.scanner.lineno())
        ctx = self.scanner.create_context(reader)

        indent = 0
        altindent = 0
        while True:
            if reader.expect(('#', '\n', '\\')):
                return
            elif reader.expect(' '):
                indent += 1
                altindent += 1
            elif reader.expect('\t'):
                indent += ((indent / TABSIZE) + 1) * TABSIZE
                altindent += ((indent / ALTTABSIZE) + 1) * ALTTABSIZE
            else:
                self.scanner._tokens.append(token)
                break

        if indent == self.back():
            if altindent != self.altback():
                return ctx.create_error_token(ErrorTokenErrno.E_TABSPACE)
        elif indent > self.back():
            if altindent <= self.back():
                return ctx.create_error_token(ErrorTokenErrno.E_TABSPACE)

            self.stack.append((indent, altindent))
            ctx.create_token(TokenType.INDENT)
        else:
            while self.stack and indent < self.back:
                self.stack.pop()
                ctx.create_token(TokenType.DEDENT)

            if indent != self.back():
                return ctx.create_error_token(ErrorTokenErrno.E_DEDENT)

            if altindent != self.altback():
                return ctx.create_error_token(ErrorTokenErrno.E_TABSPACE)


class _TokenScanner:
    __slots__ = ('scanner', 'parenstack')

    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner
        self.parenstack = []

    def feed(self, reader: StringReader) -> None:
        ctx = self.scanner.create_context(reader)

        if reader.expect('.'):
            if reader.expect('.', 2):
                ctx.create_token(TokenType.ELLIPSIS)
            else:
                ctx.create_token(TokenType.DOT)
        elif reader.expect('+'):
            if reader.expect('='):
                ctx.create_token(TokenType.PLUSEQUAL)
            else:
                ctx.create_token(TokenType.PLUS)
        elif reader.expect('-'):
            if reader.expect('>'):
                ctx.create_token(TokenType.RARROW)
            elif reader.expect('='):
                ctx.create_token(TokenType.MINUSEQUAL)
            else:
                ctx.create_token(TokenType.MINUS)
        elif reader.expect('*'):
            if reader.expect('*'):
                if reader.expect('='):
                    ctx.create_token(TokenType.DOUBLESTARQEUAL)
                else:
                    ctx.create_token(TokenType.DOUBLESTAR)
            elif reader.expect('='):
                ctx.create_token(TokenType.STAREQUAL)
        elif reader.expect('@'):
            if reader.expect('='):
                ctx.create_token(TokenType.ATEQUAL)
            else:
                ctx.create_token(TokenType.AT)
        elif reader.expect('/'):
            if reader.expect('/'):
                if reader.expect('='):
                    ctx.create_token(TokenType.DOUBLESLASHEQUAL)
                else:
                    ctx.create_token(TokenType.DOUBLESLASH)
            elif reader.expect('='):
                ctx.create_token(TokenType.SLASHEQUAL)
        elif reader.expect('|'):
            if reader.expect('='):
                ctx.create_token(TokenType.VBAREQUAL)
            else:
                ctx.create_token(TokenType.VBAR)
        elif reader.expect('&'):
            if reader.expect('='):
                ctx.create_token(TokenType.AMPERSANDEQUAL)
            else:
                ctx.create_token(TokenType.AMPERSAND)
        elif reader.expect('<'):
            if reader.expect('<'):
                if reader.expect('='):
                    ctx.create_token(TokenType.LSHIFTEQUAL)
                else:
                    ctx.create_token(TokenType.LSHIFT)
            elif reader.expect('='):
                ctx.create_token(TokenType.LTHANEQ)
            else:
                ctx.create_token(TokenType.LTHAN)
        elif reader.expect('>'):
            if reader.expect('>'):
                if reader.expect('='):
                    ctx.create_token(TokenType.RSHIFTEQUAL)
                else:
                    ctx.create_token(TokenType.RSHIFT)
            elif reader.expect('='):
                ctx.create_token(TokenType.GTHANEQ)
            else:
                ctx.create_token(TokenType.GTHAN)
        elif reader.expect('='):
            if reader.expect('='):
                ctx.create_token(TokenType.EQEQUAL)
            else:
                ctx.create_token(TokenType.EQUAL)
        elif reader.expect('!'):
            if reader.expect('='):
                ctx.create_token(TokenType.NOTEQUAL)
        elif reader.expect('%'):
            if reader.expect('='):
                ctx.create_token(TokenType.PERCENTEQUAL)
            else:
                ctx.create_token(TokenType.PERCENT)
        elif reader.expect('^'):
            if reader.expect('='):
                ctx.create_token(TokenType.CIRCUMFLEXEQUAL)
            else:
                ctx.create_token(TokenType.CIRCUMFLEX)
        elif reader.expect('('):
            self.parenstack.append(TokenType.LPAREN)
            ctx.create_token(TokenType.LPAREN)
        elif reader.expect(')'):
            if self.parenstack.pop() is not TokenType.LPAREN:
                ctx.create_error_token(ErrorTokenErrno.E_PAREN)
            else:
                ctx.create_token(TokenType.RPAREN)
        elif reader.expect('['):
            self.parenstack.append(TokenType.LBRACKET)
            ctx.create_token(TokenType.LBRACKET)
        elif reader.expect(']'):
            if self.parenstack.pop() is not TokenType.LBRACKET:
                ctx.create_error_token(ErrorTokenErrno.E_PAREN)
            else:
                ctx.create_token(TokenType.RBRACKET)
        elif reader.expect('{'):
            self.parenstack.append(TokenType.LBRACE)
            ctx.create_token(TokenType.LBRACE)
        elif reader.expect('}'):
            if self.parenstack.pop() is not TokenType.LBRACE:
                ctx.create_error_token(ErrorTokenErrno.E_PAREN)
            else:
                ctx.create_token(TokenType.RBRACE)
        elif reader.expect(':'):
            ctx.create_token(TokenType.COLON)
        elif reader.expect(';'):
            ctx.create_token(TokenType.SEMICOLON)
        elif reader.expect(','):
            ctx.create_token(TokenType.COMMA)
        elif reader.expect('~'):
            ctx.create_token(TokenType.TILDE)


class Scanner:
    __slots__ = ('source', '_indentscanner', '_tokenscanner', '_linespans')

    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._indentscanner = _IndentScanner()
        self._tokenscanner = _TokenScanner()
        self._linespans = []
        self._tokens = []

    def lineno(self) -> int:
        return len(self._linespans)

    def readline(self) -> StringReader:
        lower = self.source.tell()
        line = self.source.readline()
        upper = self.source.tell()
        self._linespans.append((lower, upper))
        return StringReader(line)

    def create_context(self, reader: StringReader) -> _TokenContext:
        return _TokenContext(self, reader)

    def _scan_identifier(self) -> None:
        pass

    def _scan_number(self) -> None:
        pass

    def _scan_string(self) -> None:
        pass

    def _scan_linecont(self) -> None:
        pass

    def scan(self):
        reader = None
        while True:
            if reader is None:
                reader = self.readline()
                newline = not self._tokenscanner.parenstack
            else:
                newline = False

            if newline:
                try:
                    type = self._tokens[-1].type
                except IndexError:
                    type = None

                if type is not TokenType.NEWLINE:
                    self._indentscanner.feed(reader)

            reader.skipws(newlines=True)

            if _is_identifier_start(reader.peek(0)):
                self._scan_identifier()
            elif _is_identifier_start(reader.peek(0)):
                self._scan_number()
            elif reader.expect(('\'', '"')):
                self._scan_string()
            elif reader.expect('\\'):
                self._scan_linecont()
            elif reader.expect('#'):
                reader = None
            elif reader.expect(EOF):
                if reader.tell() == 0:
                    self._tokens.append(Token(self, TokenType.EOF, 0, 0, self.lineno()))
            else:
                self._tokenscanner.feed(reader)
