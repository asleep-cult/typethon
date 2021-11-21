from __future__ import annotations

import io
from typing import Optional

from .keywords import KeywordType
from .scanner import Token, TokenType, scan
from .. import ast


class Parser:
    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._tokens = None
        self._postition = 0

    def _advance(self, by: int = 1) -> int:
        self._postition += by
        return self._postition

    def _peek(self, offset: int = 0) -> Token:
        return self._tokens[self._postition + offset]

    def _peek_type(self, offset: int = 0) -> Token:
        return self._peek(offset).type

    def _peek_keyword(self, offset: int = 0) -> Optional[KeywordType]:
        token = self._peek(offset)
        if token.type is TokenType.IDENTIFIER:
            return token.keyword

    def _expect_token(self, type: TokenType) -> bool:
        if self._peek_type() is type:
            self._advance()
            return True
        return False

    def _expect_keyword(self, type: KeywordType) -> bool:
        if self._peek_keyword() is type:
            self._advance()
            return True
        return False

    def _next_token(self) -> Token:
        try:
            return self._peek()
        finally:
            self._advance()

    def _parse_compound_statement(self) -> Optional[ast.StatementNode]:
        match self._peek_keyword():
            case KeywordType.ASYNC:
                return self._parse_async_statement()

            case KeywordType.CLASS:
                return self._parse_class_def()

            case KeywordType.DEF:
                return self._parse_function_def()

            case KeywordType.FOR:
                return self._parse_for_statement()

            case KeywordType.IF:
                return self._parse_if_statement()

            case KeywordType.TRY:
                return self._parse_try_statement()

            case KeywordType.WHILE:
                return self._parse_while_statement()

            case KeywordType.WITH:
                return self._parse_with_statement()

        if self._expect_token(TokenType.AT):
            return self._parse_decorated_statement()

    def _parse_simple_statement(self) -> Optional[ast.StatementNode]:
        match self._peek_keyword():
            case KeywordType.ASSERT:
                return self._parse_assert_statement()

            case KeywordType.BREAK:
                return self._parse_break_statement()

            case KeywordType.CONTINUE:
                return self._parse_continue_statement()

            case KeywordType.DEL:
                return self._parse_del_statement()

            case KeywordType.FROM | KeywordType.IMPORT:
                return self._parse_import_statement()

            case KeywordType.GLOBAL:
                return self._parse_global_statement()

            case KeywordType.NONLOCAL:
                return self._parse_nonlocal_statement()

            case KeywordType.PASS:
                return self._parse_pass_statement()

            case KeywordType.RAISE:
                return self._parse_raise_statement()

            case KeywordType.RETURN:
                return self._parse_return_statement()

    def _parse_async_statement(self) -> Optional[ast.StatementNode]:
        match self._peek_keyword():
            case KeywordType.DEF:
                return self._parse_function_def()

            case KeywordType.FOR:
                return self._parse_for_statement()

            case KeywordType.WITH:
                return self._parse_with_statement()

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

    def _parse_assert_statement(self):
        pass

    def _parse_break_statement(self) -> ast.BreakNode:
        return ast.BreakNode().set_loc(self._next_token())

    def _parse_continue_statement(self) -> ast.ContinueNode:
        return ast.ContinueNode().set_loc(self._next_token())

    def _parse_del_statement(self):
        pass

    def _parse_import_statement(self):
        pass

    def _parse_global_statement(self):
        pass

    def _parse_nonlocal_statement(self):
        pass

    def _parse_pass_statement(self) -> ast.PassNode:
        return ast.PassNode().set_loc(self._next_token())

    def _parse_raise_statement(self):
        pass

    def _parse_return_statement(self):
        pass

    def _parse_star_expressions(self):
        pass

    def parse(self):
        self._tokens = scan(self.source)
