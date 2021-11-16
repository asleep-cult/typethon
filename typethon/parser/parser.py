import io

from .keywords import KeywordType
from .scanner import TokenType, scan
from .tokenstream import TokenStream
from .. import ast


class Parser:
    __slits__ = ('_tokenstream',)

    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._tokenstream = None

    def _parse_statement(self) -> ast.Statement:
        if self._tokenstream.expectkw(KeywordType.ASYNC):
            return self._parse_async_statement()
        elif self._tokenstream.expectkw(KeywordType.CLASS):
            return self._parse_class_def()
        elif self._tokenstream.expectkw(KeywordType.DEF):
            return self._parse_function_def()
        elif self._tokenstream.expectkw(KeywordType.FOR):
            return self._parse_for_statement()
        elif self._tokenstream.expectkw(KeywordType.IF):
            return self._parse_if_statement()
        elif self._tokenstream.expectkw(KeywordType.TRY):
            return self._parse_try_statement()
        elif self._tokenstream.expectkw(KeywordType.WHILE):
            return self._parse_while_statement()
        elif self._tokenstream.expectkw(KeywordType.WITH):
            return self._parse_with_statement()

        if self._tokenstream.expect(TokenType.AT):
            return self._parse_decorated_statement()

        return self._parse_simple_statement()

    def _parse_async_statement(self):
        pass

    def _parse_class_def(self):
        pass

    def _parse_function_def(self):
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

    def _parse_simple_statement(self):
        pass

    def parse(self):
        self._tokenstream = TokenStream(scan(self.source))
