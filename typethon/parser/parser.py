from __future__ import annotations

import io
from typing import Optional

from .keywords import KeywordType
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

    def peek_keyword(self, offset: int = 0) -> Optional[KeywordType]:
        token = self.peek(offset)
        if token.type is TokenType.IDENTIFIER:
            return token.keyword

    def advance(self, by: int = 1) -> int:
        self.position += by
        return self.position

    def at_type(self, type: TokenType, offset: int = 0) -> bool:
        return self.peek_type(offset) is type

    def at_keyword(self, type: KeywordType, offset: int = 0) -> bool:
        return self.peek_keyword(offset) is type

    def expect_type(self, type: TokenType) -> bool:
        if self.at_type(type):
            self.advance()
            return True
        return False

    def expect_keyword(self, type: KeywordType) -> bool:
        if self.at_keyword(type):
            self.advance()
            return True
        return False

    def consume(self, type: TokenType) -> Token:
        token = self.peek()
        assert token.type is type
        self.advance()
        return token

    def consume_keyword(self, type: KeywordType) -> Token:
        token = self.consume(TokenType.IDENTIFIER)
        assert token.keyword is type
        return token


class Parser:
    def __init__(self, source: io.TextIOBase) -> None:
        self.source = source

        self._tokens = None

    def _parse_compound_statement(self) -> Optional[ast.StatementNode]:
        if self._tokens.at_keyword(KeywordType.ASYNC):
            return self._parse_async_statement()

        if self._tokens.at_keyword(KeywordType.CLASS):
            return self._parse_class_def()

        if self._tokens.at_keyword(KeywordType.DEF):
            return self._parse_function_def()

        if self._tokens.at_keyword(KeywordType.FOR):
            return self._parse_for_statement()

        if self._tokens.at_keyword(KeywordType.IF):
            return self._parse_if_statement()

        if self._tokens.at_keyword(KeywordType.TRY):
            return self._parse_try_statement()

        if self._tokens.at_keyword(KeywordType.WHILE):
            return self._parse_while_statement()

        if self._tokens.at_keyword(KeywordType.WITH):
            return self._parse_with_statement()

        if self._tokens.at_type(TokenType.AT):
            return self._parse_decorated_statement()

    def _parse_simple_statement(self) -> Optional[ast.StatementNode]:
        if self._tokens.at_keyword(KeywordType.ASSERT):
            return self._parse_assert_statement()

        if self._tokens.at_keyword(KeywordType.BREAK):
            return self._parse_break_statement()

        if self._tokens.at_keyword(KeywordType.CONTINUE):
            return self._parse_continue_statement()

        if self._tokens.at_keyword(KeywordType.DEL):
            return self._parse_del_statement()

        if (self._tokens.at_keyword(KeywordType.FROM)
                or self._tokens.at_keyword(KeywordType.IMPORT)):
            return self._parse_import_statement()

        if self._tokens.at_keyword(KeywordType.GLOBAL):
            return self._parse_global_statement()

        if self._tokens.at_keyword(KeywordType.NONLOCAL):
            return self._parse_nonlocal_statement()

        if self._tokens.at_keyword(KeywordType.PASS):
            return self._parse_pass_statement()

        if self._tokens.at_keyword(KeywordType.RAISE):
            return self._parse_raise_statement()

        if self._tokens.at_keyword(KeywordType.RETURN):
            return self._parse_return_statement()

    def _parse_async_statement(self) -> Optional[ast.StatementNode]:
        if self._tokens.at_keyword(KeywordType.DEF):
            return self._parse_class_def()

        if self._tokens.at_keyword(KeywordType.FOR):
            return self._parse_for_statement()

        if self._tokens.at_keyword(KeywordType.WITH):
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
        self._tokens.consume_keyword(KeywordType.BREAK)
        return ast.BreakNode()

    def _parse_continue_statement(self) -> ast.ContinueNode:
        self._tokens.consume_keyword(KeywordType.CONTINUE)
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
        self._tokens.consume_keyword(KeywordType.PASS)
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
        if self._tokens.at_keyword(KeywordType.LAMBDA):
            return self._parse_lambda_expression()

        expr = self._parse_disjunction()
        if not self._tokens.expect_keyword(KeywordType.IF):
            return expr

        condexpr = self._parse_disjunction()

        if not self._tokens.expect_keyword(KeywordType.ELSE):
            assert False

        elseexpr = self._parse_expression()
        return ast.IfExpNode(body=expr, condition=condexpr, elsebody=elseexpr)

    def _parse_lambda_expression(self) -> ast.LambdaNode:
        pass

    def _parse_disjunction(self):
        left_expr = self._parse_conjunction()
        if not self._tokens.at_keyword(KeywordType.OR):
            return left_expr

        expr = ast.BoolOpNode(op=ast.BoolOperator.OR)
        expr.values.append(left_expr)

        while self._tokens.expect_keyword(KeywordType.OR):
            expr.values.append(self._parse_conjunction())

        return expr

    def _parse_conjunction(self):
        left_expr = self._parse_inversion()
        if not self._tokens.at_keyword(KeywordType.AND):
            return left_expr

        expr = ast.BoolOpNode(op=ast.BoolOperator.AND)
        expr.values.append(left_expr)

        while self._tokens.expect_keyword(KeywordType.AND):
            expr.values.append(self._parse_inversion())

        return expr

    def _parse_inversion(self):
        if self._tokens.expect_keyword(KeywordType.NOT):
            expr = self._parse_inversion()
            return ast.UnaryOpNode(op=ast.UnaryOperator.NOT, operand=expr)

        return self._parse_comparison()

    def _parse_comparison(self):
        pass

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
        awaited = self._tokens.expect_keyword(KeywordType.AWAIT)
        left_expr = self._parse_primary_expression()

        while True:
            if self._tokens.expect_type(TokenType.DOT):
                token = self._tokens.peek()
                if token.type is TokenType.IDENTIFIER:
                    self._tokens.advance()
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
        token = self._tokens.peek()

        if token.type is TokenType.IDENTIFIER:
            self._tokens.advance()
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
            self._tokens.advance()
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
        self._tokens = _TokenStream(scan(self.source))
