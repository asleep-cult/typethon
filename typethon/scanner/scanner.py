from __future__ import annotations

import array
import codecs
import enum
import io

from .exceptions import BadEncodingDeclaration
from .stringreader import StringReader


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


class Token:
    __slots__ = ('scanner', 'type', 'startpos', 'endpos', 'startlineno', 'endlineno')

    def __init__(self, scanner: Scanner, type: TokenType, startpos: int, endpos: int,
                 startlineno: int, endlineno: int) -> None:
        self.scanner = scanner
        self.type = type
        self.startpos = startpos
        self.endpos = endpos
        self.startlineno = startlineno
        self.endlineno = endlineno

    def __repr__(self):
        span = f'[{self.startpos}:{self.endpos}]'
        return f'<{self.__class__.__name__} type={self.type} {span}>'

    def span(self):
        lower = self.scanner._linespans[self.startlineno][0] + self.startpos
        upper = self.scanner._linespans[self.endlineno][1] - self.endpos
        return lower, upper


class _TokenContext:
    def __init__(self, scanner: Scanner, reader: StringReader) -> None:
        self.scanner = scanner
        self.reader = reader
        self.type = None
        self.startpos = None
        self.endpos = None
        self.startlineno = None
        self.endlineno = None

    def set_type(self, type: TokenType) -> None:
        self.type = type

    def create_token(self, index=-1) -> Token:
        token = Token(self.scanner, self.type, self.startpos,
                      self.endpos, self.startlineno, self.endlineno)
        self.scanner._tokens.insert(index, token)
        raise token

    def __enter__(self) -> _TokenContext:
        self.startpos = self.reader.tell()
        self.startlineno = len(self.scanner._linespans)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.endpos = self.reader.tell()
        self.endlineno = len(self.scanner._linespans)


class Scanner:
    __slots__ = ('source', '_linespans', '_tokens', '_parenstack')

    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._parenstack = array.array('B')
        self._linespans = []
        self._tokens = []

    def _add_paren(self, type: TokenType):
        self._parenstack.append(type.value)

    def _pop_paren(self) -> TokenType:
        return TokenType(self._parenstack.pop())

    def readline(self) -> StringReader:
        lower = self.source.tell()
        line = self.source.readline()
        upper = self.source.tell()
        self._linespans.append((lower, upper))
        return StringReader(line)

    def create_ctx(self, *, reader=None) -> _TokenContext:
        if reader is None:
            reader = self.readline()
        return _TokenContext(self, reader)

    def _scan_identifier(self, ctx: _TokenContext) -> None:
        ctx.reader.nextwhile(_is_identifier)
        if _is_terminal(ctx.reader.peek(0)):
            self._scan_number(ctx)
        else:
            ctx.set_type(TokenType.IDENTIFIER)

    def _scan_number(self, ctx: _TokenContext) -> None:
        ctx.set_type(TokenType.NUMBER)

    def _scan_string(self, ctx: _TokenContext) -> None:
        ctx.set_type(TokenType.STRING)

    def _get_type(self, ctx: _TokenContext) -> TokenType:
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
            self._add_paren(TokenType.LPAREN)
            return TokenType.LPAREN
        elif ctx.reader.expect(')'):
            return TokenType.RPAREN
        elif ctx.reader.expect('['):
            self._add_paren(TokenType.LBARACKET)
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

    def scan(self):
        with self.create_ctx() as ctx:
            char = ctx.reader.peek(0)
            if _is_identifier_start(char):
                self._scan_identifier(ctx)
            elif _is_digit(char):
                self._scan_number(ctx)
            elif _is_terminal(char):
                self._scan_string(ctx)
            else:
                ctx.set_type(self._get_type(ctx))

            ctx.create_token()
