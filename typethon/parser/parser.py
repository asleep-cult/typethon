from __future__ import annotations

from io import TextIOBase
from typing import Callable, Optional, TYPE_CHECKING, TypeVar

from .scanner import Scanner
from .tokens import Token, TokenType
from .. import ast

T = TypeVar('T')

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    P = ParamSpec('P')


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

        self._unaryop_table = {
            TokenType.PLUS: ast.UnaryOperator.UADD,
            TokenType.MINUS: ast.UnaryOperator.USUB,
            TokenType.TILDE: ast.UnaryOperator.INVERT,
        }

        self._sum_table = {
            TokenType.PLUS: ast.Operator.ADD,
            TokenType.MINUS: ast.Operator.SUB,
        }

        self._term_table = {
            TokenType.STAR: ast.Operator.MULT,
            TokenType.SLASH: ast.Operator.DIV,
            TokenType.DOUBLESLASH: ast.Operator.FLOORDIV,
            TokenType.PERCENT: ast.Operator.MOD,
            TokenType.AT: ast.Operator.MATMULT,
        }

        self._shift_table = {
            TokenType.DOUBLELTHAN: ast.Operator.LSHIFT,
            TokenType.DOUBLEGTHAN: ast.Operator.RSHIFT,
        }

        self._augassign_table = {
            TokenType.PLUSEQUAL: ast.Operator.ADD,
            TokenType.MINUSEQUAL: ast.Operator.SUB,
            TokenType.STAREQUAL: ast.Operator.MULT,
            TokenType.ATEQUAL: ast.Operator.MATMULT,
            TokenType.SLASHEQUAL: ast.Operator.DIV,
            TokenType.DOUBLESLASHEQUAL: ast.Operator.FLOORDIV,
            TokenType.PERCENTEQUAL: ast.Operator.MOD,
            TokenType.AMPERSANDEQUAL: ast.Operator.BITAND,
            TokenType.VERTICALBAREQUAL: ast.Operator.BITOR,
            TokenType.CIRCUMFLEXEQUAL: ast.Operator.BITXOR,
            TokenType.DOUBLELTHANEQUAL: ast.Operator.LSHIFT,
            TokenType.DOUBLEGTHANEQUAL: ast.Operator.RSHIFT,
            TokenType.DOUBLESTAREQUAL: ast.Operator.POW,
        }

    def _alternative(self, rule: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Optional[T]:
        stream = self._stream
        self._stream = self._stream.view()
        try:
            value = rule(*args, **kwargs)
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
                token.type is TokenType.NEWLINE
                or token.type is TokenType.EOF
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
        token = self._stream.expect(TokenType.RETURN)
        assert token is not None

        expression = self._alternative(self._parse_expression_list, starred=True)

        return ast.ReturnNode(token.range, value=expression)

    def _parse_expression(self, *, starred=False):
        """
        expression(starred=true):
            | '*' bitwise_or
            | expression(starred=false)

        expression(starred=false):
            | disjunction
            | disjunction 'if' disjunction 'else' expression
            | lambda_expression
        """
        if starred:
            token = self._stream.expect(TokenType.STAR)
            if token is not None:
                value = self._parse_bitwise_or()

                expression = ast.StarredNode(value.range, value=value)
                expression.range.extend(value.range)

                return expression

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

    def _parse_expression_list(self, *, starred=False):
        """
        expressions(starred):
            | expression(starred)
            | expression(starred) (',' expression(starred))* [',']
        """
        expression = self._parse_expression(starred=starred)
        if self._stream.expect(TokenType.COMMA) is None:
            return expression

        expression = ast.TupleNode(expression.range, elts=[expression])

        while True:
            expr = self._alternative(self._parse_expression, starred=True)
            if expr is not None:
                expression.elts.append(expr)
                expression.range.extend(expr.range)
            else:
                break

            token = self._stream.expect(TokenType.COMMA)
            if token is not None:
                expression.range.extend(token.range)
            else:
                break

        return expression

    def _parse_lambda_expression(self):
        pass

    def _parse_disjunction(self):
        """
        disjunction:
            | conjunction
            | conjunction ('or' conjunction)+
        """
        expression = self._parse_conjunction()

        token = self._stream.peek()
        if token.type is not TokenType.OR:
            return expression

        expression = ast.BoolOpNode(expression.range, op=ast.BoolOperator.OR, values=[])

        while True:
            token = self._stream.expect(TokenType.OR)
            if token is not None:
                value = self._parse_conjunction()

                expression.values.append(value)
                expression.range.extend(value.range)
            else:
                break

        return expression

    def _parse_conjunction(self):
        """
        conjunction:
            | inversion
            | inversion ('or' inversion)+
        """
        expression = self._parse_inversion()

        token = self._stream.peek()
        if token.type is not TokenType.OR:
            return expression

        expression = ast.BoolOpNode(expression.range, op=ast.BoolOperator.OR, values=[])

        while True:
            token = self._stream.expect(TokenType.OR)
            if token is not None:
                value = self._parse_inversion()

                expression.values.append(value)
                expression.range.extend(value.range)
            else:
                break

        return expression

    def _parse_inversion(self):
        """
        conjunction:
            | 'not' inversion
            | comparison
        """
        token = self._stream.expect(TokenType.NOT)
        if token is not None:
            operand = self._parse_inversion()
            return ast.UnaryOpNode(token.range, operator=ast.UnaryOperator.NOT, operand=operand)

        return self._parse_comparison()

    def _parse_comparison(self):
        pass

    def _parse_bitwise_or(self):
        """
        bitwise_or:
            | bitwise_xor
            | bitwise_or '|' bitwise_xor
        """
        expression = self._parse_bitwise_xor()

        while True:
            token = self._stream.expect(TokenType.VERTICALBAR)
            if token is None:
                break

            right = self._parse_bitwise_xor()
            expression = ast.BinaryOpNode(
                expression.range, left=expression, op=ast.Operator.BITOR, right=right
            )

        return expression

    def _parse_bitwise_xor(self):
        """
        bitwise_xor:
            | bitwise_and
            | bitwise_xor '^' bitwise_and
        """
        expression = self._parse_bitwise_and()

        while True:
            token = self._stream.expect(TokenType.CIRCUMFLEX)
            if token is None:
                break

            right = self._parse_bitwise_and()
            expression = ast.BinaryOpNode(
                expression.range, left=expression, op=ast.Operator.BITXOR, right=right
            )

        return expression

    def _parse_bitwise_and(self):
        """
        bitwise_and:
            | bitwise_shift
            | bitwise_and '&' bitwise_shift
        """
        expression = self._parse_bitwise_shift()

        while True:
            token = self._stream.expect(TokenType.AMPERSAND)
            if token is None:
                break

            right = self._parse_bitwise_shift()
            expression = ast.BinaryOpNode(
                expression.range, left=expression, op=ast.Operator.BITAND, right=right
            )

        return expression

    def _parse_bitwise_shift(self):
        """
        bitwise_shift:
            | arithmetic_sum
            | bitwise_shift '<<' arithmetic_sum
            | bitwise_shift '>>' arithmetic_sum
        """
        expression = self._parse_arithmetic_sum()

        while True:
            token = self._stream.peek()
            try:
                operator = self._shift_table[token.type]
            except KeyError:
                break

            right = self._parse_arithmetic_sum()
            expression = ast.BinaryOpNode(
                expression.range, left=expression, op=operator, right=right
            )

            self._stream.next()

        return expression

    def _parse_arithmetic_sum(self):
        """
        arithmetic_sum:
            | term
            | arithmetic_sum '+' term
            | arithmetic_cum '-' term
        """
        expression = self._parse_arithmetic_term()

        while True:
            token = self._stream.peek()
            try:
                operator = self._term_table[token.type]
            except KeyError:
                break

            right = self._parse_arithmetic_term()
            expression = ast.BinaryOpNode(
                expression.range, left=expression, op=operator, right=right
            )

        return expression

    def _parse_arithmetic_term(self):
        """
        arithmetic_term:
            | factor
            | arithmetic_term '*' factor
            | arithmetic_term '/' factor
            | arithmetic_term '//' factor
            | arithmetic_term '%' factor
            | arithmetic_term '@' factor
        """
        expression = self._parse_arithmetic_factor()

        while True:
            token = self._stream.peek()
            try:
                operator = self._term_table[token.type]
            except KeyError:
                break

            right = self._parse_arithmetic_factor()
            expression = ast.BinaryOpNode(
                expression.range, left=expression, op=operator, right=right
            )

        return expression

    def _parse_arithmetic_factor(self):
        """
        arithmeic_factor:
            | arithmetic_power
            | '+' arithmetic_factor
            | '-' arithmetic_factor
            | '~' arithmetic_factor
        """
        token = self._stream.peek()
        try:
            operator = self._unaryop_table[token.type]
        except KeyError:
            return self._parse_arithmetic_power()
        else:
            expression = self._parse_arithmetic_factor()
            return ast.UnaryOpNode(token.range, op=operator, operand=expression)

    def _parse_arithmetic_power(self):
        """
        arithmetic_power:
            | primary
            | ['await'] primary '**' factor
        """
        await_token = self._stream.expect(TokenType.AWAIT)

        expression = self._parse_primary_expression()

        if self._stream.expect(TokenType.DOUBLESTAR) is not None:
            right = self._parse_arithmetic_factor()
            expression = ast.BinaryOpNode(
                expression.range, left=expression, op=ast.Operator.POW, right=right
            )

        if await_token is not None:
            expression = ast.AwaitNode(await_token.range, value=expression)

        return expression

    def _parse_primary_expression(self):
        expression = self._parse_atom_expression()

        while True:
            token = self._stream.peek()
            if token.type is TokenType.DOT:
                self._stream.next()
                token = self._stream.expect(TokenType.IDENTIFIER)
                if token is not None:
                    expression = ast.AttributeNode(
                        expression.range, value=expression, attr=token.content
                    )
                else:
                    assert False, '<Expected Identifier>'
            elif token.type is TokenType.OPENPAREN:
                assert False, '<Call Function>'
            elif token.type is TokenType.OPENBRACKET:
                assert False, '<Subscript>'
            else:
                break

        return expression

    def _parse_slice_expressions(self):
        pass

    def _parse_slice_expression(self):
        pass

    def _parse_atom_expression(self):
        token = self._stream.next()

        if token.type is TokenType.TRUE:
            return ast.ConstantNode(token.range, type=ast.ConstantType.TRUE)

        if token.type is TokenType.FALSE:
            return ast.ConstantNode(token.range, type=ast.ConstantType.FALSE)

        if token.type is TokenType.NONE:
            return ast.ConstantNode(token.range, type=ast.ConstantType.NONE)

        if token.type is TokenType.ELLIPSIS:
            return ast.ConstantNode(token.range, type=ast.ConstantType.ELLIPSIS)

        if token.type is TokenType.OPENPAREN:
            assert False, '<Tuple/Group>'

        if token.type is TokenType.OPENBRACKET:
            assert False, '<List>'

        if token.type is TokenType.OPENBRACE:
            assert False, '<Dict/Set>'

    def _parse_group_expression(self):
        pass

    def parse(self) -> ast.BaseNode:
        self._stream = TokenStream(Scanner(self.source))
