from __future__ import annotations

import io
from typing import Optional

from .stringreader import EOF, StringReader
from .tokens import (
    IdentifierToken,
    KEYWORDS,
    NumberToken,
    NumberTokenFlags,
    StringToken,
    StringTokenFlags,
    Token,
    TokenType,
)
from ..textrange import TextRange


class TokenFactory:
    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner

    def create_token(self, type: TokenType, length: int) -> Token:
        position = self.scanner._position()
        lineno = self.scanner._lineno()
        range = TextRange(position - length, position, lineno, lineno)
        return Token(type, range)

    def create_identifier(self, content: str) -> IdentifierToken:
        position = self.scanner._position()
        lineno = self.scanner._lineno()
        range = TextRange(position - len(content), position, lineno, lineno)
        return IdentifierToken(range, content)

    def create_number(self, flags: NumberTokenFlags, content: str) -> NumberToken:
        position = self.scanner._position()
        lineno = self.scanner._lineno()
        range = TextRange(position - len(content), position, lineno, lineno)
        return NumberToken(range, flags, content)

    def create_string(self, range: TextRange, flags: StringTokenFlags, content: str) -> StringToken:
        return StringToken(range, flags, content)


class Scanner:
    def __init__(
        self, source: io.TextIOBase, *, factory: type[TokenFactory] = TokenFactory
    ) -> None:
        self.source = source
        self.factory = factory(self)

        self._newline = False
        self._reader = None

        self._linestarts = []
        self._parenstack = []
        self._indentstack = []

    def _parenstack_push(self, type: TokenType) -> None:
        self._parenstack.append(type)

    def _parenstack_pop(self) -> None:
        self._parenstack.pop()

    def _parenstack_back(self) -> Optional[TokenType]:
        try:
            return self._parenstack[-1]
        except IndexError:
            return None

    def _readline(self) -> None:
        self._linestarts.append(self.source.tell())
        self._reader = StringReader(self.source.readline())

    def _position(self) -> int:
        assert self._reader is not None
        return self._reader.tell()

    def _lineno(self) -> int:
        return len(self._linestarts)

    def _scan_identifier(self) -> IdentifierToken:
        assert StringReader.is_identifier_start(self._reader.peek())
        self._reader.advance()

        startpos = self._reader.tell()
        while StringReader.is_identifier(self._reader.peek()):
            self._reader.advance()

        endpos = self._reader.tell()
        return self.factory.create_identifier(self._reader.source[startpos:endpos])

    def _scan_number(self) -> NumberToken:
        pass

    def _scan_string(self, *, prefixes: Optional[str] = None) -> StringToken:
        pass

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
            if self._parenstack_push() is not TokenType.OPENBRACE:
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
        while True:
            if self._reader is None:
                self._readline()
            else:
                self._reader.skip_whitespaces(newlines=True)

            char = self._reader.peek()
            if StringReader.is_identifier_start(char):
                token = self._scan_identifier()

                char = self._reader.peek()
                if StringReader.is_terminator(char):
                    return self._scan_string(prefixes=token.content)

                try:
                    keyword = KEYWORDS[token.content]
                except KeyError:
                    return token
                else:
                    return self.factory.create_token(keyword, len(token.content))
            elif StringReader.is_digit(char):
                return self._scan_number()
            elif StringReader.is_escape(char):
                self._reader.advance()

                if not self._reader.expect(EOF):
                    length = len(self._reader.source) - self._reader.tell()
                    return self.factory.create_token(TokenType.ERROR, length)

                self._reader = None
                continue
