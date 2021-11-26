from __future__ import annotations

from io import TextIOBase
from typing import Callable, Optional, TypeVar

from .scanner import Scanner
from .tokens import Token, TokenType
from .. import ast

T = TypeVar('T')


class TokenStream:
    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner
        self._tokencache = []

    def next(self) -> Token:
        try:
            token = self._tokencache.pop(0)
        except IndexError:
            token = self.scanner.scan()

        return token

    def peek(self) -> Token:
        try:
            token = self._tokencache[0]
        except IndexError:
            token = self.scanner.scan()
            self._tokencache.append(token)

        return token

    def lookahead(self, func: Callable[[Token], bool]) -> Optional[Token]:
        if func(self.peek()):
            return self.next()

    def expect(self, type: TokenType) -> Optional[Token]:
        if self.peek().type is type:
            return self.next()

    def view(self) -> TokenStreamView:
        return TokenStreamView(self)


class TokenStreamView:
    # A view onto a TokenStream that only removes tokens from the cache
    # when commit() is called. This allows for infinite backtracking with
    # only a small segment of tokens in-memory at once.

    def __init__(self, stream: TokenStream) -> None:
        self.stream = stream
        self._position = 0

    def next(self):
        try:
            return self.peek()
        finally:
            self._position += 1

    def peek(self) -> Token:
        try:
            token = self.stream._tokencache[self._position]
        except IndexError:
            token = self.stream.scanner.scan()
            self.stream._tokencache.append(token)

        return token

    def lookahead(self, func: Callable[[Token], bool]) -> Optional[Token]:
        if func(self.peek()):
            return self.next()

    def expect(self, type: TokenType) -> Optional[Token]:
        if self.peek().type is type:
            return self.next()

    def commit(self) -> None:
        del self.stream._tokencache[:self._position]

    def view(self):
        raise self.stream.view()


class Parser:
    def __init__(self, source: TextIOBase) -> None:
        self.source = source
        self._stream = None

        self._compound_statement_table = {
            TokenType.ASYNC: self._parse_async_statement,
            TokenType.CLASS: self._parse_class_def,
            TokenType.DEF: self._parse_function_def,
            TokenType.FOR: self._parse_for_statement,
            TokenType.IF: self._parse_if_statement,
            TokenType.TRY: self._parse_try_statement,
            TokenType.WHILE: self._parse_while_statement,
            TokenType.WITH: self._parse_with_statement,
            TokenType.AT: self._parse_decorated_statement,
        }

        self._simple_statement_table = {
            TokenType.ASSERT: self._parse_assert_statement,
            TokenType.BREAK: self._parse_break_statement,
            TokenType.CONTINUE: self._parse_continue_statement,
            TokenType.DEL: self._parse_delete_statement,
            TokenType.FROM: self._parse_import_statement,
            TokenType.GLOBAL: self._parse_global_statement,
            TokenType.IMPORT: self._parse_import_statement,
            TokenType.NONLOCAL: self._parse_nonlocal_statement,
            TokenType.PASS: self._parse_pass_statement,
            TokenType.RAISE: self._parse_raise_statement,
            TokenType.RETURN: self._parse_return_statement,
        }

    def _alternative(self, rule: Callable[[], T]) -> Optional[T]:
        stream = self._stream
        self._stream = self._stream.view()
        try:
            value = rule()
            self._stream.commit()
            return value
        finally:
            self._stream = stream

    def _parse_statement(self) -> ast.StatementNode:
        """
        compound_statement:
            | async_statement | class_def | function_def | for_statement | if_statement
            | try_statement | while_statement | with_statement | decorated_statement

        statement: compound_statement | simple_statements
        """
        token = self._stream.peek()
        try:
            return self._compound_statement_table[token.type]()
        except KeyError:
            return self._parse_simple_statements()

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

    def _parse_simple_statement(self) -> ast.StatementNode:
        """
        simple_statement:
            | assignment | star_expressions | assert_statement | break_statement
            | continue_statement | delete_statement | global_statement | import_statement
            | nonlocal_statement | pass_statement | raise_statement | return_statement
        """
        token = self._stream.peek()
        try:
            return self._simple_statement_table[token.type]()
        except KeyError:
            pass

    def _parse_simple_statements(self) -> ast.StatementNode:
        """
        simple_statement:
            | assignment | star_expressions | assert_statement | break_statement
            | continue_statement | delete_statement | global_statement | import_statement
            | nonlocal_statement | pass_statement | raise_statement | return_statement

        simple_statements:
            | simple_statement (';' simple_statement)* [';'] NEWLINE
        """
        token = self._stream.peek()
        statement = ast.StatementList(token.range)

        while True:
            statement.statements.append(self._parse_simple_statement())

            if self._stream.expect(TokenType.SEMICOLON) is None:
                break

            token = self._stream.peek()
            if (
                token.type == TokenType.NEWLINE
                or token.type == TokenType.EOF
            ):
                break

        token = self._stream.expect(TokenType.NEWLINE)
        if token is not None:
            statement.range.extend(token.range)
        else:
            assert False, '<Missing Newline>'

        return statement

    def _parse_assert_statement(self):
        pass

    def _parse_break_statement(self):
        pass

    def _parse_continue_statement(self):
        pass

    def _parse_delete_statement(self):
        pass

    def _parse_import_statement(self):
        pass

    def _parse_global_statement(self):
        pass

    def _parse_nonlocal_statement(self):
        pass

    def _parse_pass_statement(self):
        pass

    def _parse_raise_statement(self):
        pass

    def _parse_return_statement(self):
        pass

    def _parse_expression(self):
        """
        expression:
            | disjunction
            | disjunction 'if' disjunction 'else' expression
            | lambda_expression
        """
        token = self._stream.peek()
        if token.type is TokenType.LAMBDA:
            return self._parse_lambda_expression()

        expression = self._parse_disjunction()
        if self._stream.expect(TokenType.IF) is None:
            raise expression

        condition = self._parse_disjunction()

        if self._stream.expect(TokenType.ELSE) is None:
            assert False, '<Missing Else>'

        body = self._parse_expression()

        expression = ast.IfExpNode(
            range=token.range, body=expression, condition=condition, else_body=body
        )
        expression.range.extend(body.range)

        return expression

    def _parse_expressions(self):
        """
        expressions:
            | expression
            | expression (',' expression)* [',']
        """
        expression = self._parse_expression()
        if self._stream.expect(TokenType.COMMA) is None:
            return expression

        expression = ast.TupleNode(expression.range, elts=[expression])

        while True:
            expr = self._alternative(self._parse_expression)
            if expr is not None:
                expression.elts.append(expr)
            else:
                break

            token = self._stream.expect(TokenType.COMMA)
            if token is not None:
                expression.range.extend(token.range)
            else:
                break

        return expression

    def _parse_star_expression(self):
        """
        star_expression:
            | '*' bitwise_or
            | expression
        """
        token = self._stream.expect(TokenType.STAR)
        if token is not None:
            value = self._parse_bitwise_or()

            expression = ast.StarredNode(token.range, value=value)
            expression.range.extend(value.range)

            return expression

        return self._parse_expression()

    def _parse_star_expressions(self):
        """
        star_expressions:
            | star_expression
            | star_expression (',' star_expression)* [';']
        """
        expression = self._parse_expression()
        if self._stream.expect(TokenType.COMMA) is None:
            return expression

        expression = ast.TupleNode(expression.range, [expression])

        while True:
            expr = self._alternative(self._parse_star_expression)
            if expr is not None:
                expression.elts.append(expr)
            else:
                break

            token = self._stream.expect(TokenType.COMMA)
            if token is not None:
                expr.range.extend(token.range)
            else:
                break

        return expression

    def _parse_lambda_expression(self):
        pass

    def _parse_disjunction(self):
        pass

    def _parse_conjunction(self):
        pass

    def _parse_bitwise_or(self):
        pass

    def parse(self) -> ast.BaseNode:
        self._stream = TokenStream(Scanner(self.source))
