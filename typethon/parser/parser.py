from __future__ import annotations

import io
from typing import Optional

from .scanner import Token, TokenType, scan
from .. import ast


class _TokenStream:
    def __init__(self, tokens: list[Token]) -> None:
        self.position = 0
        self.tokens = tokens

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[self.position + offset]

    def peek_type(self, offset: int = 0) -> Token:
        return self.peek(offset).type

    def advance(self, by: int = 1) -> int:
        self.position += by
        return self.position

    def at_type(self, type: TokenType, offset: int = 0) -> bool:
        return self.peek_type(offset) is type

    def at_expr(self, offset: int = 0) -> bool:
        return self.peek_type(offset) in (
            TokenType.LAMBDA, TokenType.NOT, TokenType.AWAIT,
            TokenType.TRUE, TokenType.FALSE, TokenType.NONE,
            TokenType.IDENTIFIER, TokenType.NUMBER, TokenType.STRING,
            TokenType.ELLIPSIS, TokenType.PLUS, TokenType.MINUS, TokenType.TILDE,
            TokenType.LPAREN, TokenType.LBRACKET, TokenType.LBRACE)

    def expect_type(self, type: TokenType) -> bool:
        if self.at_type(type):
            self.advance()
            return True
        return False

    def consume(self, type: TokenType) -> Token:
        token = self.peek()
        assert token.type is type
        self.advance()
        return token


class Parser:
    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._tokens = None

    def _parse_compound_statement(self) -> Optional[ast.StatementNode]:
        if self._tokens.at_type(TokenType.ASYNC):
            return self._parse_async_statement()

        if self._tokens.at_type(TokenType.CLASS):
            return self._parse_class_def()

        if self._tokens.at_type(TokenType.DEF):
            return self._parse_function_def()

        if self._tokens.at_type(TokenType.FOR):
            return self._parse_for_statement()

        if self._tokens.at_type(TokenType.IF):
            return self._parse_if_statement()

        if self._tokens.at_type(TokenType.TRY):
            return self._parse_try_statement()

        if self._tokens.at_type(TokenType.WHILE):
            return self._parse_while_statement()

        if self._tokens.at_type(TokenType.WITH):
            return self._parse_with_statement()

        if self._tokens.at_type(TokenType.AT):
            return self._parse_decorated_statement()

    def _parse_simple_statement(self) -> Optional[ast.StatementNode]:
        if self._tokens.at_type(TokenType.ASSERT):
            return self._parse_assert_statement()

        if self._tokens.at_type(TokenType.BREAK):
            return self._parse_break_statement()

        if self._tokens.at_type(TokenType.CONTINUE):
            return self._parse_continue_statement()

        if self._tokens.at_type(TokenType.DEL):
            return self._parse_del_statement()

        if (self._tokens.at_type(TokenType.FROM)
                or self._tokens.at_type(TokenType.IMPORT)):
            return self._parse_import_statement()

        if self._tokens.at_type(TokenType.GLOBAL):
            return self._parse_global_statement()

        if self._tokens.at_type(TokenType.NONLOCAL):
            return self._parse_nonlocal_statement()

        if self._tokens.at_type(TokenType.PASS):
            return self._parse_pass_statement()

        if self._tokens.at_type(TokenType.RAISE):
            return self._parse_raise_statement()

        if self._tokens.at_type(TokenType.RETURN):
            return self._parse_return_statement()

    def _parse_async_statement(self) -> Optional[ast.StatementNode]:
        if self._tokens.at_type(TokenType.DEF):
            return self._parse_class_def()

        if self._tokens.at_type(TokenType.FOR):
            return self._parse_for_statement()

        if self._tokens.at_type(TokenType.WITH):
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
        self._tokens.consume(TokenType.BREAK)
        return ast.BreakNode()

    def _parse_continue_statement(self) -> ast.ContinueNode:
        self._tokens.consume(TokenType.CONTINUE)
        return ast.ContinueNode()

    def _parse_del_statement(self):
        pass

    def _parse_import_statement(self):
        pass

    def _parse_global_statement(self):
        pass

    def _parse_nonlocal_statement(self):
        pass

    def _parse_pass_statement(self) -> ast.PassNode:
        self._tokens.consume(TokenType.PASS)
        return ast.PassNode()

    def _parse_raise_statement(self):
        pass

    def _parse_return_statement(self):
        pass

    def _parse_expressions(self):
        left_expr = self._parse_expression()
        if not self._tokens.at_type(TokenType.COMMA):
            return left_expr

        expr = ast.TupleNode()
        expr.elts.append(left_expr)

        while self._tokens.expect_type(TokenType.COMMA):
            pass

    def _parse_expression(self):
        if self._tokens.at_type(TokenType.LAMBDA):
            return self._parse_lambda_expression()

        expr = self._parse_disjunction()
        if not self._tokens.expect_type(TokenType.IF):
            return expr

        condexpr = self._parse_disjunction()

        if not self._tokens.expect_type(TokenType.ELSE):
            assert False

        elseexpr = self._parse_expression()
        return ast.IfExpNode(body=expr, condition=condexpr, elsebody=elseexpr)

    def _parse_lambda_expression(self) -> ast.LambdaNode:
        pass

    def _parse_disjunction(self):
        left_expr = self._parse_conjunction()
        if not self._tokens.at_type(TokenType.OR):
            return left_expr

        expr = ast.BoolOpNode(op=ast.BoolOperator.OR)
        expr.values.append(left_expr)

        while self._tokens.expect_type(TokenType.OR):
            expr.values.append(self._parse_conjunction())

        return expr

    def _parse_conjunction(self):
        left_expr = self._parse_inversion()
        if not self._tokens.at_type(TokenType.AND):
            return left_expr

        expr = ast.BoolOpNode(op=ast.BoolOperator.AND)
        expr.values.append(left_expr)

        while self._tokens.expect_type(TokenType.AND):
            expr.values.append(self._parse_inversion())

        return expr

    def _parse_inversion(self):
        if self._tokens.expect_type(TokenType.NOT):
            expr = self._parse_inversion()
            return ast.UnaryOpNode(op=ast.UnaryOperator.NOT, operand=expr)

        return self._parse_comparison()

    def _parse_comparison(self):
        left_expr = self._parse_bitwise_or()

        expr = ast.CompareNode(left=left_expr)

        while True:
            if self._tokens.expect_type(TokenType.EQEQUAL):
                operator = ast.CmpOperator.EQ
            elif self._tokens.expect_type(TokenType.NOTEQUAL):
                operator = ast.CmpOperator.NOTEQ
            elif self._tokens.expect_type(TokenType.LTHANEQ):
                operator = ast.CmpOperator.LTE
            elif self._tokens.expect_type(TokenType.LTHAN):
                operator = ast.CmpOperator.LT
            elif self._tokens.expect_type(TokenType.GTHANEQ):
                operator = ast.CmpOperator.GTE
            elif self._tokens.expect_type(TokenType.GTHAN):
                operator = ast.CmpOperator.GT
            elif self._tokens.expect_type(TokenType.IN):
                operator = ast.CmpOperator.IN
            elif (self._tokens.at_type(TokenType.NOT)
                    and self._tokens.at_type(TokenType.IN, 1)):
                self._tokens.advance(2)
                operator = ast.CmpOperator.NOTIN
            elif self._tokens.expect_type(TokenType.IS):
                operator = ast.CmpOperator.IS
            elif (self._tokens.at_type(TokenType.NOT)
                    and self._tokens.at_type(TokenType.IN, 1)):
                self._tokens.at_type(2)
                operator = ast.CmpOperator.NOTIN
            else:
                if not expr.comparators:
                    assert False

                return expr

            right_expr = self._parse_bitwise_or()
            expr.comparators.append(ast.ComparatorNode(op=operator, value=right_expr))

    def _parse_bitwise_or(self):
        left_expr = self._parse_bitwise_xor()

        while self._tokens.expect_type(TokenType.VBAR):
            right_expr = self._parse_bitwise_or()
            left_expr = ast.BinaryOpNode(left=left_expr, op=ast.Operator.BITOR, right=right_expr)

        return left_expr

    def _parse_bitwise_xor(self):
        left_expr = self._parse_bitwise_and()

        while self._tokens.expect_type(TokenType.CIRCUMFLEX):
            right_expr = self._parse_bitwise_xor()
            left_expr = ast.BinaryOpNode(left=left_expr, op=ast.Operator.BITXOR, right=right_expr)

        return left_expr

    def _parse_bitwise_and(self):
        left_expr = self._parse_shift_expression()

        while self._tokens.expect_type(TokenType.AMPERSAND):
            right_expr = self._parse_bitwise_and()
            left_expr = ast.BinaryOpNode(left=left_expr, op=ast.Operator.BITAND, right=right_expr)

        return left_expr

    def _parse_shift_expression(self):
        left_expr = self._parse_arithmetic_sum()

        while True:
            if self._tokens.expect_type(TokenType.LSHIFT):
                operator = ast.Operator.LSHIFT
            elif self._tokens.expect_type(TokenType.RSHIFT):
                operator = ast.Operator.RSHIFT
            else:
                return left_expr

            right_expr = self._parse_shift_expression()
            left_expr = ast.BinaryOpNode(left=left_expr, op=operator, right=right_expr)

    def _parse_arithmetic_sum(self):
        left_expr = self._parse_arithmetic_term()

        while True:
            if self._tokens.expect_type(TokenType.PLUS):
                operator = ast.Operator.ADD
            elif self._tokens.expect_type(TokenType.MINUS):
                operator = ast.Operator.SUB
            else:
                return left_expr

            right_expr = self._parse_arithmetic_sum()
            left_expr = ast.BinaryOpNode(left=left_expr, op=operator, right_expr=right_expr)

    def _parse_arithmetic_term(self):
        left_expr = self._parse_arithmetic_factor()

        while True:
            if self._tokens.expect_type(TokenType.STAR):
                operator = ast.Operator.MULT
            elif self._tokens.expect_type(TokenType.SLASH):
                operator = ast.Operator.DIV
            elif self._tokens.expect_type(TokenType.DOUBLESLASH):
                operator = ast.Operator.FLOORDIV
            elif self._tokens.expect_type(TokenType.PERCENT):
                operator = ast.Operator.MOD
            elif self._tokens.expect_type(TokenType.AT):
                operator = ast.Operator.MATMULT
            else:
                return left_expr

            right_expr = self._parse_arithmetic_term()
            left_expr = ast.BinaryOpNode(left=left_expr, op=operator, right=right_expr)

    def _parse_arithmetic_factor(self):
        if self._tokens.expect_type(TokenType.PLUS):
            operator = ast.UnaryOperator.UADD
        elif self._tokens.expect_type(TokenType.MINUS):
            operator = ast.UnaryOperator.USUB
        elif self._tokens.expect_type(TokenType.TILDE):
            operator = ast.UnaryOperator.INVERT
        else:
            return self._parse_arithmetic_power()

        expr = self._parse_arithmetic_factor()
        return ast.UnaryOpNode(op=operator, operand=expr)

    def _parse_arithmetic_power(self):
        pass

    def _parse_primary_expression(self):
        awaited = self._tokens.expect_type(TokenType.AWAIT)
        left_expr = self._parse_atom_expression()

        while True:
            if self._tokens.expect_type(TokenType.DOT):
                if self._tokens.at_type(TokenType.IDENTIFIER):
                    token = self._tokens.consume(TokenType.IDENTIFIER)
                    left_expr = ast.AttributeNode(value=left_expr, attr=token.content)
                else:
                    assert False
            else:
                # ast.CallNode
                # ast.SliceNode
                break

        if awaited:
            left_expr = ast.AwaitNode(value=left_expr)

        return left_expr

    def _parse_atom_expression(self):
        if self._tokens.at_type(TokenType.TRUE):
            self._tokens.consume(TokenType.TRUE)
            return ast.ConstantNode(type=ast.ConstantType.TRUE)

        if self._tokens.at_type(TokenType.FALSE):
            self._tokens.consume(TokenType.FALSE)
            return ast.ConstantNode(type=ast.ConstantType.FALSE)

        if self._tokens.at_type(TokenType.NONE):
            self._tokens.consume(TokenType.NONE)
            return ast.ConstantNode(type=ast.ConstantType.NONE)

        if self._tokens.at_type(TokenType.IDENTIFIER):
            token = self._tokens.consume(TokenType.IDENTIFIER)
            return ast.NameNode(value=token.content)

        if self._tokens.at_type(TokenType.NUMBER):
            assert False

        if self._tokens.at_type(TokenType.STRING):
            assert False

        if self._tokens.at_type(TokenType.ELLIPSIS):
            return ast.ConstantNode(type=ast.ConstantType.ELLIPSIS)

        if self._tokens.at_type(TokenType.LPAREN):
            assert False

        if self._tokens.at_type(TokenType.LBRACKET):
            assert False

        if self._tokens.at_type(TokenType.LBRACE):
            assert False

    def _parse_slices(self):
        pass

    def parse(self):
        self._tokens = _TokenStream(scan(self.source))
