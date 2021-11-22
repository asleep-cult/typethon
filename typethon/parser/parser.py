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

    def _peek_token(self, offset: int = 0) -> Token:
        return self._tokens[self._postition + offset]

    def _peek_type(self, offset: int = 0) -> Token:
        return self._peek_token(offset).type

    def _peek_keyword(self, offset: int = 0) -> Optional[KeywordType]:
        token = self._peek_token(offset)
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
            return self._peek_token()
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
        self._advance()
        return ast.BreakNode()

    def _parse_continue_statement(self) -> ast.ContinueNode:
        self._advance()
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
        self._advance()
        return ast.PassNode()

    def _parse_raise_statement(self):
        pass

    def _parse_return_statement(self):
        pass

    def _parse_expression(self):
        if self._peek_keyword() is KeywordType.LAMBDA:
            return self._parse_lambda_expression()

        expr = self._parse_disjunction()
        if self._peek_keyword() is KeywordType.IF:
            return self._parse_if_expression(expr)

        return expr

    def _parse_lambda_expression(self) -> ast.LambdaNode:
        pass

    def _parse_if_expression(self, body: ast.ExpressionNode) -> ast.IfExpNode:
        pass

    def _parse_disjunction(self):
        left_expr = self._parse_conjunction()
        if self._peek_keyword() is not KeywordType.OR:
            return left_expr

        expr = ast.BoolOpNode(op=ast.BoolOperator.OR)
        expr.values.append(left_expr)

        while self._expect_keyword(KeywordType.OR):
            expr.values.append(self._parse_conjunction())

        return expr

    def _parse_conjunction(self):
        left_expr = self._parse_inversion()
        if self._peek_keyword() is not KeywordType.AND:
            return left_expr

        expr = ast.BoolOpNode(op=ast.BoolOperator.AND)
        expr.values.append(left_expr)

        while self._expect_keyword(KeywordType.AND):
            expr.values.append(self._parse_inversion())

        return expr

    def _parse_inversion(self):
        if self._expect_keyword(KeywordType.NOT):
            expr = self._parse_inversion()
            return ast.UnaryOpNode(op=ast.UnaryOperator.NOT, operand=expr)

        return self._parse_comparison()

    def _parse_comparison(self):
        pass

    def _parse_bitwise_or(self):
        left_expr = self._parse_bitwise_xor()

        while self._expect_token(TokenType.VBAR):
            right_expr = self._parse_bitwise_or()
            left_expr = ast.BinaryOpNode(left=left_expr, op=ast.Operator.BITOR, right=right_expr)

        return left_expr

    def _parse_bitwise_xor(self):
        left_expr = self._parse_bitwise_and()

        while self._expect_token(TokenType.CIRCUMFLEX):
            right_expr = self._parse_bitwise_xor()
            left_expr = ast.BinaryOpNode(left=left_expr, op=ast.Operator.BITXOR, right=right_expr)

        return left_expr

    def _parse_bitwise_and(self):
        left_expr = self._parse_shift_expression()

        while self._expect_token(TokenType.AMPERSAND):
            right_expr = self._parse_bitwise_and()
            left_expr = ast.BinaryOpNode(left=left_expr, op=ast.Operator.BITAND, right=right_expr)

        return left_expr

    def _parse_shift_expression(self):
        left_expr = self._parse_arithmetic_sum()

        while True:
            if self._expect_token(TokenType.LSHIFT):
                operator = ast.Operator.LSHIFT
            elif self._expect_token(TokenType.RSHIFT):
                operator = ast.Operator.RSHIFT
            else:
                return left_expr

            right_expr = self._parse_shift_expression()
            left_expr = ast.BinaryOpNode(left=left_expr, op=operator, right=right_expr)

    def _parse_arithmetic_sum(self):
        left_expr = self._parse_arithmetic_term()

        while True:
            if self._expect_token(TokenType.PLUS):
                operator = ast.Operator.ADD
            elif self._expect_token(TokenType.MINUS):
                operator = ast.Operator.SUB
            else:
                return left_expr

            right_expr = self._parse_arithmetic_sum()
            left_expr = ast.BinaryOpNode(left=left_expr, op=operator, right_expr=right_expr)

    def _parse_arithmetic_term(self):
        left_expr = self._parse_arithmetic_factor()

        while True:
            if self._expect_token(TokenType.STAR):
                operator = ast.Operator.MULT
            elif self._expect_token(TokenType.SLASH):
                operator = ast.Operator.DIV
            elif self._expect_token(TokenType.DOUBLESLASH):
                operator = ast.Operator.FLOORDIV
            elif self._expect_token(TokenType.PERCENT):
                operator = ast.Operator.MOD
            elif self._expect_token(TokenType.AT):
                operator = ast.Operator.MATMULT
            else:
                return left_expr

            right_expr = self._parse_arithmetic_term()
            left_expr = ast.BinaryOpNode(left=left_expr, op=operator, right=right_expr)

    def _parse_arithmetic_factor(self):
        if self._expect_token(TokenType.PLUS):
            operator = ast.UnaryOperator.UADD
        elif self._expect_token(TokenType.MINUS):
            operator = ast.UnaryOperator.USUB
        elif self._expect_token(TokenType.TILDE):
            operator = ast.UnaryOperator.INVERT
        else:
            return self._parse_arithmetic_power()

        expr = self._parse_arithmetic_factor()
        return ast.UnaryOpNode(op=operator, operand=expr)

    def _parse_arithmetic_power(self):
        pass

    def _parse_primary_expression(self):
        awaited = self._expect_keyword(KeywordType.AWAIT)
        left_expr = self._parse_primary_expression()

        while True:
            if self._expect_token(TokenType.DOT):
                token = self._next_token()
                if token.type is TokenType.IDENTIFIER:
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
        token = self._peek_token()

        if token.type is TokenType.IDENTIFIER:
            self._advance()
            if token.keyword is not None:
                return ast.NameNode(value=token.content)
            elif token.keyword is KeywordType.TRUE:
                return ast.ConstantNode(type=ast.ConstantType.TRUE)
            elif token.keyword is KeywordType.FALSE:
                return ast.ConstantType(type=ast.ConstantType.FALSE)
            elif token.keyword is KeywordType.NONE:
                return ast.ConstantType(type=ast.ConstantType.NONE)
        elif token.type is TokenType.NUMBER:
            assert False
        elif token.type is TokenType.STRING:
            assert False
        elif token.type is TokenType.ELLIPSIS:
            self._advance()
            return ast.ConstantNode(type=ast.ConstantType.ELLIPSIS)
        elif token.type is TokenType.LPAREN:
            assert False
        elif token.type is TokenType.LBRACKET:
            assert False
        elif token.type is TokenType.LBRACE:
            assert False

    def _parse_slices(self):
        pass

    def parse(self):
        self._tokens = scan(self.source)
