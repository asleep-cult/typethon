from __future__ import annotations

from io import TextIOBase
from typing import Callable, Optional

from .scanner import Scanner
from .tokens import Token, TokenType
from .. import ast


class TokenStream:
    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner
        self._tokencache = []

    def next_token(self) -> Token:
        return self._tokencache.pop(0)

    def peek_token(self) -> Token:
        try:
            token = self._tokencache[0]
        except IndexError:
            token = self.scanner.scan()
            self._tokencache.append(token)

        return token

    def lookahead(self, func: Callable[[Token], bool]) -> Optional[Token]:
        if func(self.peek_token()):
            return self.next_token()

    def expect(self, type: TokenType) -> Optional[Token]:
        if self.peek_token().type is type:
            return self.next_token()

    def view(self) -> TokenStreamView:
        return TokenStreamView(self)


class TokenStreamView:
    # A view onto a TokenStream that only removes tokens from the cache
    # when commit() is called. This allows for infinite backtracking with
    # only a small segment of tokens in-memory at once.

    def __init__(self, stream: TokenStream) -> None:
        self.stream = stream
        self._position = 0

    def next_token(self):
        try:
            return self.peek_token()
        finally:
            self._position += 1

    def peek_token(self) -> Token:
        try:
            token = self.stream._tokencache[self._position]
        except IndexError:
            token = self.stream.scanner.scan()
            self.stream._tokencache.append(token)

        return token

    def lookahead(self, func: Callable[[Token], bool]) -> Optional[Token]:
        if func(self.peek_token()):
            return self.next_token()

    def expect(self, type: TokenType) -> Optional[Token]:
        if self.peek_token().type is type:
            return self.next_token()

    def commit(self) -> None:
        del self.stream._tokencache[:self._position]


class Parser:
    def __init__(self, source: TextIOBase) -> None:
        self.source = source
        self._stream = None

    def _parse_compound_statement(self) -> ast.StatementNode:
        token = self._stream.peek_token()

        # &'async': async_statement
        if token.type is TokenType.ASYNC:
            return self._parse_async_statement()

        # &'class': class_def
        if token.type is TokenType.CLASS:
            return self._parse_class_def()

        # &'for': for_statement
        if token.type is TokenType.FOR:
            return self._parse_for_statement()

        # &'if': for_statement
        if token.type is TokenType.IF:
            return self._parse_if_statement()

        # &'try': try_statement
        if token.type is TokenType.TRY:
            return self._parse_if_statement()

        # &'while': while_statement
        if token.type is TokenType.WHILE:
            return self._parse_while_statement()

        # &'with': with_statement
        if token.type is TokenType.WITH:
            return self._parse_with_statement()

        # &'@': decorated_statement
        if token.type is TokenType.AT:
            return self._parse_decorated_statement()

    def _parse_async_statement(self):
        pass

    def _parse_class_def(self):
        pass

    def _parse_for_statement(self):
        pass

    def _parse_if_statement(self):
        pass

    def _parse_try_statement(self):
        pass

    def _parse_while_statement(self):
        pass

    def _parse_with_statement(self):
        pass

    def _parse_decorated_statement(self):
        pass

    def parse(self) -> ast.BaseNode:
        self._stream = TokenStream(Scanner(self.source))
