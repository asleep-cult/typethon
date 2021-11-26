from __future__ import annotations

import io
from typing import Callable, Optional

from .stringreader import StringReader
from .tokens import (
    DedentToken,
    IdentifierToken,
    IndentToken,
    KEYWORDS,
    NumberToken,
    NumberTokenFlags,
    StringToken,
    StringTokenFlags,
    Token,
    TokenType,
)
from ..textrange import TextRange


TABSIZE = 8
ALTTABSIZE = 1


class TokenFactory:
    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner

    def create_range(self, length: int) -> TextRange:
        position = self.scanner._position()
        lineno = self.scanner._lineno()
        return TextRange(position - length, position, lineno, lineno)

    def create_token(self, type: TokenType, length: int) -> Token:
        return Token(type, self.create_range(length))

    def create_identifier(self, content: str) -> IdentifierToken:
        return IdentifierToken(self.create_range(len(content)), content)

    def create_number(self, flags: NumberTokenFlags, content: str) -> NumberToken:
        return NumberToken(self.create_range(len(content)), flags, content)

    def create_string(
        self, range: TextRange, flags: StringTokenFlags, content: Optional[str] = None
    ) -> StringToken:
        if content is None:
            content = ''
        return StringToken(range, flags, content)

    def create_indent(self, *, inconsistent: bool = False) -> IndentToken:
        return IndentToken(self.create_range(self.scanner._position()), inconsistent)

    def create_dedent(self, *, inconsistent: bool = False, diverges: bool = False) -> DedentToken:
        return DedentToken(self.create_range(self.scanner._position()), inconsistent, diverges)

    def create_comment(self, content: str) -> None:
        return None


class Scanner:
    def __init__(
        self, source: io.TextIOBase, *, factory: type[TokenFactory] = TokenFactory
    ) -> None:
        self.source = source
        self.factory = factory(self)

        self._reader = None

        self._newline = False
        self._scannedindents = False

        self._linestarts = []
        self._parenstack = []

        self._indentstack = []
        self._altindentstack = []
        self._indents = []

        self._add_indent(0, 0)

    def _parenstack_push(self, type: TokenType) -> None:
        self._parenstack.append(type)

    def _parenstack_pop(self) -> None:
        self._parenstack.pop()

    def _parenstack_back(self) -> Optional[TokenType]:
        try:
            return self._parenstack[-1]
        except KeyError:
            return None

    def _add_indent(self, indent: int, altindent: int) -> None:
        self._indentstack.append(indent)
        self._altindentstack.append(altindent)

    def _remove_indent(self) -> None:
        self._indentstack.pop()
        self._altindentstack.pop()

    def _get_indent(self, index) -> int:
        return self._indentstack[index]

    def _get_altindent(self, index) -> int:
        return self._altindentstack[index]

    def _readline(self) -> StringReader:
        self._linestarts.append(self.source.tell())
        return StringReader(self.source.readline())

    def _position(self) -> int:
        assert self._reader is not None
        return self._reader.tell()

    def _lineno(self) -> int:
        return len(self._linestarts)

    def _get_identifier(self) -> str:
        startpos = self._reader.tell()
        assert StringReader.is_identifier_start(self._reader.peek())
        self._reader.advance()

        while StringReader.is_identifier(self._reader.peek()):
            self._reader.advance()

        endpos = self._reader.tell()
        return self._reader.source[startpos:endpos]

    def _scan_indents(self) -> None:
        indent = altindent = 0
        while StringReader.is_indent(self._reader.peek()):
            if self._reader.expect(' '):
                indent += 1
                altindent += 1
            elif self._reader.expect('\t'):
                indent += ((indent // TABSIZE) + 1) * TABSIZE
                altindent += ((indent // ALTTABSIZE) + 1) * ALTTABSIZE

        if StringReader.is_blank(self._reader.peek()):
            return

        lastindent = self._get_indent(-1)
        lastaltindent = self._get_altindent(-1)

        if indent == lastindent:
            if altindent != lastaltindent:
                self._indents.append(self.factory.create_indent(inconsistent=True))
        elif indent > lastindent:
            if altindent <= lastaltindent:
                self._indents.append(self.factory.create_indent(inconsistent=True))
            else:
                self._add_indent(indent, altindent)
                self._indents.append(self.factory.create_indent())
        else:
            while indent < self._get_indent(-2):
                self._remove_indent()
                self._indents.append(self.factory.create_dedent())

            self._remove_indent()

            lastindent = self._get_indent(-1)
            lastaltindent = self._get_altindent(-1)

            if indent == lastindent:
                if altindent != lastaltindent:
                    self._indents.append(self.factory.create_dedent(inconsistent=True))
                else:
                    self._indents.append(self.factory.create_dedent())
            else:
                inconsistent = (
                    indent == lastindent and altindent != lastaltindent
                )
                self._indents.append(
                    self.factory.create_dedent(inconsistent=inconsistent, diverges=True)
                )

        self._scannedindents = True
        self._newline = False

    def _is_at_number(self) -> bool:
        char = self._reader.peek()
        if char == '.':
            char = self._reader.peek(1)
            if char in ('E' 'e'):
                char = self._reader.peek(2)
                if char in ('+' '-'):
                    char = self._reader.peek(3)

        return StringReader.is_digit(char)

    def _get_number_flags(self, func: Callable[[str], bool]) -> None:
        flags = NumberTokenFlags.NONE

        while (
            func(self._reader.peek())
            or self._reader.peek() == '_'
        ):
            if self._reader.expect('_'):
                if self._reader.expect('_'):
                    flags |= NumberTokenFlags.CONSECUTIVE_UNDERSCORES
            else:
                self._reader.advance()

        if self._reader.peek(-1) == '_':
            flags |= NumberTokenFlags.TRAILING_UNDERSCORE

        return flags

    def _scan_number(self) -> NumberToken:
        assert self._is_at_number()

        flags = NumberTokenFlags.NONE
        leading_zero = False

        startpos = self._reader.tell()

        if self._reader.expect('0'):
            if self._reader.expect('X' 'x'):
                flags |= (
                    NumberTokenFlags.HEXADECIMAL
                    | self._get_number_flags(StringReader.is_hexadecimal)
                )
            elif self._reader.expect('O' 'o'):
                flags |= (
                    NumberTokenFlags.OCTAL
                    | self._get_number_flags(StringReader.is_octal)
                )
            elif self._reader.expect('B' 'b'):
                flags |= (
                    NumberTokenFlags.BINARY
                    | self._get_number_flags(StringReader.is_binary)
                )

            if flags != 0:
                endpos = self._reader.tell()
                if endpos <= startpos + 2:
                    flags |= NumberTokenFlags.EMPTY

                return self.factory.create_number(flags, self._reader.source[startpos:endpos])

            leading_zero = True

        while (
            StringReader.is_digit(self._reader.peek())
            or self._reader.peek() == '_'
        ):
            if self._reader.expect('_'):
                if self._reader.expect('_'):
                    flags |= NumberTokenFlags.CONSECUTIVE_UNDERSCORES
            else:
                if leading_zero:
                    if self._reader.peek() != '0':
                        # We set the LEADING_ZERO flag because the number started
                        # with a zero but contained at least 1 non-zero character
                        flags |= NumberTokenFlags.LEADING_ZERO

                self._reader.advance()

        if self._reader.peek(-1) == '_':
            flags |= NumberTokenFlags.TRAILING_UNDERSCORE

        if self._reader.expect('.'):
            flags |= (
                NumberTokenFlags.FLOAT | self._get_number_flags(StringReader.is_digit)
            )

        if self._reader.expect('E' 'e'):
            flags |= NumberTokenFlags.FLOAT

            self._reader.skip('+' '-')

            if not StringReader.is_digit(self._reader.peek()):
                flags |= NumberTokenFlags.INVALID_EXPONENT

            flags |= self._get_number_flags(StringReader.is_digit)

        if self._reader.expect('J' 'j'):
            flags |= NumberTokenFlags.IMAGINARY

        endpos = self._reader.tell()
        return self.factory.create_number(flags, self._reader.source[startpos:endpos])

    def _scan_string(self, *, prefixes: Optional[str] = None) -> StringToken:
        startlineno = self._lineno()
        startpos = self._reader.tell()

        flags = StringTokenFlags.NONE

        if prefixes is not None:
            for char in prefixes.lower():
                if char == 'r':
                    flag = StringTokenFlags.RAW
                elif char == 'b':
                    flag = StringTokenFlags.BYTES
                elif char == 'f':
                    flag = StringTokenFlags.FORMAT
                else:
                    flags |= StringTokenFlags.INVALID_PREFIX
                    continue

                if flags & flag:
                    flags |= StringTokenFlags.DUPLICATE_PREFIX
                else:
                    flags |= flag

            startpos -= len(prefixes)

        terminator = self._reader.peek()
        assert StringReader.is_terminator(terminator)
        self._reader.advance()

        termsize = 1

        if self._reader.expect(terminator):
            if self._reader.expect(terminator):
                termsize = 3
            else:
                return self.factory.create_string(
                    TextRange(startpos, startpos + 1, startlineno, startlineno), flags
                )

        content = io.StringIO()
        contentstart = self._reader.tell()

        terminated = False

        while True:
            if self._reader.at_eof():
                if self._reader.tell() == 0:
                    # Immediate EOF from reader -- we've reached the end of the file
                    flags |= StringTokenFlags.UNTERMINATED
                else:
                    self._reader = self._readline()
                    contentstart = 0

            char = self._reader.peek()
            if StringReader.is_newline(char):
                if termsize == 3:
                    contentend = self._reader.skip_to_eof()
                else:
                    contentend = self._reader.tell()
                    flags |= StringTokenFlags.UNTERMINATED

            elif StringReader.is_escape(char):
                if StringReader.is_newline(self._reader.peek(1)):
                    contentend = self._reader.skip_to_eof()
                else:
                    self._reader.advance(2)
                    continue

            elif char == terminator:
                contentend = self._reader.tell()
                if self._reader.expect(terminator, termsize):
                    terminated = True
                else:
                    self._reader.advance(1)
                    continue

            else:
                self._reader.advance(1)
                continue

            content.write(self._reader.source[contentstart:contentend])

            if flags & StringTokenFlags.UNTERMINATED or terminated:
                break

        endlineno = self._lineno()
        endpos = self._reader.tell()

        return self.factory.create_string(
            TextRange(startpos, endpos, startlineno, endlineno), flags, content.getvalue()
        )

    def _scan_token(self) -> Optional[Token]:
        if self._reader.expect('('):
            self._parenstack_push(TokenType.OPENPAREN)
            return self.factory.create_token(TokenType.OPENPAREN, 1)

        elif self._reader.expect(')'):
            if self._parenstack_back() is not TokenType.OPENPAREN:
                return self.factory.create_token(TokenType.ERROR, 1)

            self._parenstack_pop()
            return self.factory.create_token(TokenType.CLOSEPAREN, 1)

        elif self._reader.expect('['):
            self._parenstack_push(TokenType.OPENBRACKET)
            return self.factory.create_token(TokenType.OPENBRACKET, 1)

        elif self._reader.expect(']'):
            if self._parenstack_back() is not TokenType.OPENBRACKET:
                return self.factory.create_token(TokenType.ERROR, 1)

            self._parenstack_pop()
            return self.factory.create_token(TokenType.CLOSEBRACKET, 1)

        elif self._reader.expect('{'):
            self._parenstack_push(TokenType.OPENBRACE)
            return self.factory.create_token(TokenType.OPENBRACE, 1)

        elif self._reader.expect('}'):
            if self._parenstack_back() is not TokenType.OPENBRACE:
                return self.factory.create_token(TokenType.ERROR, 1)

            self._parenstack_pop()
            return self.factory.create_token(TokenType.CLOSEBRACE, 1)

        elif self._reader.expect(':'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.COLONEQUAL, 2)

            return self.factory.create_token(TokenType.COLON, 1)

        elif self._reader.expect(','):
            return self.factory.create_token(TokenType.COMMA, 1)

        elif self._reader.expect(';'):
            return self.factory.create_token(TokenType.SEMICOLON, 1)

        elif self._reader.expect('.'):
            if self._reader.expect('.', 2):
                return self.factory.create_token(TokenType.ELLIPSIS, 3)

            return self.factory.create_token(TokenType.DOT, 1)

        elif self._reader.expect('+'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.PLUSEQUAL, 2)

            return self.factory.create_token(TokenType.PLUS, 1)

        elif self._reader.expect('-'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.MINUSEQUAL, 2)

            elif self._reader.expect('>'):
                return self.factory.create_token(TokenType.RARROW, 2)

            return self.factory.create_token(TokenType.MINUS, 1)

        elif self._reader.expect('*'):
            if self._reader.expect('*'):
                if self._reader.expect('='):
                    return self.factory.create_token(TokenType.DOUBLESTAREQUAL, 3)

                return self.factory.create_token(TokenType.DOUBLESTAR, 2)

            elif self._reader.expect('='):
                return self.factory.create_token(TokenType.STAREQUAL, 2)

            return self.factory.create_token(TokenType.STAR, 1)

        elif self._reader.expect('@'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.ATEQUAL, 2)

            return self.factory.create_token(TokenType.AT, 1)

        elif self._reader.expect('/'):
            if self._reader.expect('/'):
                if self._reader.expect('='):
                    return self.factory.create_token(TokenType.DOUBLESLASHEQUAL, 3)

                return self.factory.create_token(TokenType.DOUBLESLASH, 2)

            elif self._reader.expect('='):
                return self.factory.create_token(TokenType.SLASHEQUAL, 2)

            return self.factory.create_token(TokenType.SLASH, 1)

        elif self._reader.expect('|'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.VERTICALBAREQUAL, 1)

            return self.factory.create_token(TokenType.VERTICELBAR, 1)

        elif self._reader.expect('&'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.AMPERSANDEQUAL, 2)

            return self.factory.create_token(TokenType.AMPERSAND, 1)

        elif self._reader.expect('<'):
            if self._reader.expect('<'):
                if self._reader.expect('='):
                    return self.factory.create_token(TokenType.DOUBLELTHANEQUAL, 3)

                return self.factory.create_token(TokenType.DOUBLELTHAN, 2)

            elif self._reader.expect('='):
                return self.factory.create_token(TokenType.LTHANEQ, 2)

            return self.factory.create_token(TokenType.LTHAN, 1)

        elif self._reader.expect('>'):
            if self._reader.expect('>'):
                if self._reader.expect('='):
                    return self.factory.create_token(TokenType.DOUBLEGTHANEQUAL, 3)

                return self.factory.create_token(TokenType.DOUBLEGTHAN, 2)

            elif self._reader.expect('='):
                return self.factory.create_token(TokenType.GTHANEQ, 1)

            return self.factory.create_token(TokenType.GTHAN, 1)

        elif self._reader.expect('='):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.EQEQUAL, 2)

            return self.factory.create_token(TokenType.EQUAL, 1)

        elif self._reader.expect('!'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.NOTEQUAL, 2)

        elif self._reader.expect('%'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.PERCENTEQUAL, 2)

            return self.factory.create_token(TokenType.PERCENT)

        elif self._reader.expect('~'):
            return self.factory.create_token(TokenType.TILDE, 1)

        elif self._reader.expect('^'):
            if self._reader.expect('='):
                return self.factory.create_token(TokenType.CIRCUMFLEXEQUAL, 2)

            return self.factory.create_token(TokenType.CIRCUMFLEX, 1)

    def scan(self) -> Token:
        if self._reader is None:
            self._reader = self._readline()

        while True:
            if self._reader.at_eof():
                if self._reader.tell() == 0:
                    # Immediate EOF from reader -- we've reached the end of the file
                    return self.factory.create_token(TokenType.EOF, 0)

                self._reader = self._readline()
                if not self._scannedindents:
                    self._scan_indents()

            if self._indents:
                return self._indents.pop(0)

            self._reader.skip_whitespace()
            if self._reader.at_eof():
                continue

            if self._is_at_number():
                return self._scan_number()

            char = self._reader.peek()
            if StringReader.is_identifier_start(char):
                content = self._get_identifier()

                if StringReader.is_terminator(self._reader.peek()):
                    return self._scan_string(prefixes=content)

                keyword = KEYWORDS.get(content)
                if keyword is not None:
                    return self.factory.create_token(keyword, len(content))
                else:
                    return self.factory.create_identifier(content)

            if StringReader.is_terminator(char):
                return self._scan_string()

            if StringReader.is_newline(char):
                self._reader.advance()

                if self._parenstack or self._newline:
                    continue

                self._newline = True
                self._scannedindents = False
                return self.factory.create_token(TokenType.NEWLINE, 1)

            if StringReader.is_escape(char):
                self._reader.advance()

                if self._reader.at_eof():
                    continue

                startpos = self._reader.tell()
                return self.factory.create_token(
                    TokenType.ERROR, self._reader.skip_to_eof() - startpos
                )

            if StringReader.is_comment(char):
                startpos, endpos = self._reader.tell(), self._reader.skip_to_eof()
                self.factory.create_comment(self._reader.source[startpos:endpos])

                continue

            token = self._scan_token()
            if token is not None:
                return token

            # If we reach this point then the character is not a valid token.
            # We recover by skipping to a whitespace character and returning and ERROR token.
            startpos = self._reader.tell()
            while (
                not self._reader.at_eof()
                and not StringReader.is_whitespace(self._reader.peek())
            ):
                self._reader.advance()

            endpos = self._reader.tell()
            return self.factory.create_token(TokenType.ERROR, endpos - startpos)
