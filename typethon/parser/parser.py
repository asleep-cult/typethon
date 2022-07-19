from __future__ import annotations

import contextlib
import typing

import attr

from .. import ast
from .scanner import Scanner
from ..tokens import (
    Token,
    TokenType,
    IdentifierToken,
)


class TokenStream:
    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner
        self.cache: typing.List[Token] = []

    def peek_token(self, index: int = 0) -> Token:
        while len(self.cache) <= index:
            token = self.scanner.scan()
            self.cache.append(token)

        return self.cache[index]

    def consume_token(self) -> Token:
        if self.cache:
            return self.cache.pop(0)

        return self.scanner.scan()

    def view(self) -> TokenStreamView:
        return TokenStreamView(self)


class TokenStreamView:
    def __init__(self, stream: typing.Union[TokenStream, TokenStreamView]) -> None:
        self.stream = stream
        self.position = 0

    @property
    def scanner(self) -> Scanner:
        return self.stream.scanner

    @property
    def cache(self) -> typing.List[Token]:
        return self.stream.cache

    def peek_token(self, index: int = 0) -> Token:
        while len(self.cache) <= self.position + index:
            token = self.scanner.scan()
            self.cache.append(token)

        return self.cache[self.position + index]

    def consume_token(self) -> Token:
        token = self.peek_token()
        self.position += 1
        return token

    def accept(self) -> None:
        del self.stream.cache[:self.position]

    def view(self) -> TokenStreamView:
        return self.stream.view()


@attr.s(slots=True)
class Alternative:
    accepted: bool = attr.ib(init=False, default=False)


class Parser:
    def __init__(self, scanner: Scanner) -> None:
        self.scanner = scanner
        self.stream: typing.Union[TokenStream, TokenStreamView] = TokenStream(scanner)

    @contextlib.contextmanager
    def alternative(self) -> typing.Iterator[Alternative]:
        stream = self.stream
        self.stream = TokenStreamView(stream)

        alternative = Alternative()

        try:
            yield alternative

            self.stream.accept()
            alternative.accepted = True
        except Exception:
            alternative.accepted = False
        finally:
            self.stream = stream

    def statements(self) -> ast.StatementNode:
        statements: typing.List[ast.StatementNode] = []

        statement = self.statement()
        if isinstance(statement, ast.StatementList):
            statements.extend(statement.statements)
        else:
            statements.append(statement)

        while True:
            with self.alternative() as alternative:
                statement = self.statement()
                if isinstance(statement, ast.StatementList):
                    statements.extend(statement.statements)
                else:
                    statements.append(statement)

            if not alternative.accepted:
                return ast.StatementList(
                    startpos=statements[0].startpos,
                    endpos=statements[-1].endpos,
                    statements=statements,
                )

    def statement(self) -> ast.StatementNode:
        token = self.stream.peek_token()

        if token.type is TokenType.ASYNC:
            return self.async_statement()

        elif token.type is TokenType.CLASS:
            return self.class_def()

        elif token.type is TokenType.DEF:
            return self.function_def()

        elif token.type is TokenType.FOR:
            return self.for_statement()

        elif token.type is TokenType.IF:
            return self.if_statement()

        elif token.type is TokenType.TRY:
            return self.try_statement()

        elif token.type is TokenType.WHILE:
            return self.while_statement()

        elif token.type is TokenType.WITH:
            return self.with_statement()

        elif token.type is TokenType.AT:
            return self.decorated_statement()

        return self.simple_statements()

    def async_statement(self) -> ast.StatementNode:
        assert False

    def class_def(self) -> ast.ClassDefNode:
        assert False

    def function_def(self) -> ast.FunctionDefNode:
        assert False

    def for_statement(self) -> ast.ForNode:
        assert False

    def if_statement(self) -> ast.IfNode:
        assert False

    def try_statement(self) -> ast.TryNode:
        assert False

    def while_statement(self) -> ast.WhileNode:
        assert False

    def with_statement(self) -> ast.WithNode:
        assert False

    def decorated_statement(self) -> typing.Union[ast.ClassDefNode, ast.FunctionDefNode]:
        assert False

    def simple_statements(self) -> ast.StatementNode:
        statements: typing.List[ast.StatementNode] = []

        while True:
            statement = self.simple_statement()
            statements.append(statement)

            token = self.stream.peek_token()
            if token.type is TokenType.SEMICOLON:
                self.stream.consume_token()

            token = self.stream.peek_token()
            if token.type in (TokenType.NEWLINE, TokenType.EOF):
                return ast.StatementList(
                    startpos=statements[0].startpos,
                    endpos=statements[-1].endpos,
                    statements=statements,
                )
            else:
                assert False, '<Expected (NEWLINE, EOF)>'

    def simple_statement(self) -> ast.StatementNode:
        token = self.stream.peek_token()

        if token.type is TokenType.ASSERT:
            return self.assert_statement()

        elif token.type is TokenType.BREAK:
            return self.break_statement()

        elif token.type is TokenType.CONTINUE:
            return self.continue_statement()

        elif token.type is TokenType.DEL:
            return self.del_statement()

        elif token.type is TokenType.FROM:
            return self.from_statement()

        elif token.type is TokenType.GLOBAL:
            return self.global_statement()

        elif token.type is TokenType.IMPORT:
            return self.import_statement()

        elif token.type is TokenType.NONLOCAL:
            return self.nonlocal_statement()

        elif token.type is TokenType.PASS:
            return self.pass_statement()

        elif token.type is TokenType.RAISE:
            return self.raise_statement()

        elif token.type is TokenType.RETURN:
            return self.return_statement()

        expression = self.star_expressions()
        return ast.ExprNode(
            startpos=expression.startpos,
            endpos=expression.endpos,
            expr=expression,
        )

    def assert_statement(self) -> ast.AssertNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.ASSERT

        startpos = token.start

        expression = self.expression()
        message = None

        token = self.stream.peek_token()

        if token.type is TokenType.COMMA:
            self.stream.consume_token()
            message = self.expression()

        if message is not None:
            endpos = message.endpos
        else:
            endpos = expression.endpos

        return ast.AssertNode(
            startpos=startpos,
            endpos=endpos,
            condition=expression,
            message=message,
        )

    def break_statement(self) -> ast.BreakNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.BREAK

        return ast.BreakNode(startpos=token.start, endpos=token.end)

    def continue_statement(self) -> ast.ContinueNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.CONTINUE

        return ast.ContinueNode(startpos=token.start, endpos=token.end)

    def del_statement(self) -> ast.DeleteNode:
        assert False

    def yield_statement(self) -> ast.ExprNode:
        expression = self.yield_expression()
        return ast.ExprNode(
            startpos=expression.startpos,
            endpos=expression.endpos,
            expr=expression,
        )

    def from_statement(self) -> ast.ImportFromNode:
        assert False

    def global_statement(self) -> ast.GlobalNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.GLOBAL

        startpos = token.start
        endpos = -1

        names: typing.List[str] = []

        while True:
            token = self.stream.peek_token()
            if token.type is TokenType.IDENTIFIER:
                self.stream.consume_token()
                assert isinstance(token, IdentifierToken)

                names.append(token.content)
                endpos = token.end
            else:
                assert False, '<Expected Identifier>'

            token = self.stream.peek_token()
            if token.type is not TokenType.COMMA:
                return ast.GlobalNode(
                    startpos=startpos,
                    endpos=endpos,
                    names=names,
                )

            self.stream.consume_token()

    def import_statement(self) -> ast.ImportNode:
        assert False

    def nonlocal_statement(self) -> ast.NonlocalNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.NONLOCAL

        startpos = token.start
        endpos = -1

        names: typing.List[str] = []

        while True:
            token = self.stream.peek_token()
            if token.type is TokenType.IDENTIFIER:
                self.stream.consume_token()
                assert isinstance(token, IdentifierToken)

                names.append(token.content)
                endpos = token.end
            else:
                assert False, '<Expected Identifier>'

            token = self.stream.peek_token()
            if token.type is not TokenType.COMMA:
                return ast.NonlocalNode(
                    startpos=startpos,
                    endpos=endpos,
                    names=names,
                )

            self.stream.consume_token()

    def pass_statement(self) -> ast.PassNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.PASS

        return ast.PassNode(startpos=token.start, endpos=token.end)

    def raise_statement(self) -> ast.RaiseNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.RAISE

        startpos = token.start
        endpos = token.end

        expression = None
        cause = None

        with self.alternative():
            expression = self.expression()

        if expression is not None:
            from_token = self.stream.peek_token()

            if from_token.type is TokenType.FROM:
                self.stream.consume_token()
                cause = self.expression()

        if cause is not None:
            endpos = cause.endpos
        elif expression is not None:
            endpos = expression.endpos

        return ast.RaiseNode(
            startpos=startpos,
            endpos=endpos,
            exc=expression,
            cause=cause,
        )

    def return_statement(self) -> ast.ReturnNode:
        token = self.stream.consume_token()
        assert token.type is TokenType.RETURN

        expressions = None

        with self.alternative():
            expressions = self.star_expressions()

        return ast.ReturnNode(
            startpos=token.start,
            endpos=expressions.endpos if expressions is not None else token.end,
            value=expressions,
        )

    def expression_list(self, function: typing.Callable[[], ast.ExpressionNode]) -> ast.TupleNode:
        expressions: typing.List[ast.ExpressionNode] = []

        expression = function()
        expressions.append(expression)

        token = self.stream.peek_token()
        if token.type is not TokenType.COMMA:
            return ast.TupleNode(
                startpos=expression.startpos,
                endpos=expression.endpos,
                elts=expressions,
            )

        self.stream.consume_token()
        trailing_comma = False

        while True:
            with self.alternative() as alternative:
                expression = function()
                expressions.append(expression)

            token = self.stream.peek_token()

            if not alternative.accepted:
                return ast.TupleNode(
                    startpos=expressions[0].startpos,
                    endpos=expressions[-1].endpos,
                    elts=expressions,
                )
            elif token.type is not TokenType.COMMA:
                return ast.TupleNode(
                    startpos=expressions[0].startpos,
                    endpos=token.end if trailing_comma else expressions[-1].endpos,
                    elts=expressions,
                )

            trailing_comma = token.type is TokenType.COMMA
            self.stream.consume_token()

    def expressions(self) -> ast.TupleNode:
        return self.expression_list(self.expression)

    def expression(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.type is TokenType.LAMBDA:
            return self.lambdef()

        expression = self.disjunction()

        token = self.stream.peek_token()
        if token.type is not TokenType.IF:
            return expression

        self.stream.consume_token()
        condition = self.disjunction()

        token = self.stream.peek_token()
        if token.type is not TokenType.ELSE:
            assert False, '<Expected ELSE>'

        self.stream.consume_token()
        else_body = self.expression()

        return ast.IfExpNode(
            startpos=expression.startpos,
            endpos=else_body.endpos,
            body=expression,
            condition=condition,
            else_body=else_body,
        )

    def star_expressions(self) -> ast.TupleNode:
        return self.expression_list(self.star_expression)

    def star_expression(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.type is TokenType.STAR:
            self.stream.consume_token()

            expression = self.bitwise_or()
            return ast.StarredNode(
                startpos=token.start,
                endpos=expression.endpos,
                value=expression,
            )

        return self.expression()

    def yield_expression(self) -> typing.Union[ast.YieldNode, ast.YieldFromNode]:
        token = self.stream.consume_token()
        assert token.type is TokenType.YIELD

        startpos = token.start
        endpos = token.end

        token = self.stream.peek_token()
        if token.type is TokenType.FROM:
            self.stream.consume_token()

            expression = self.expression()
            return ast.YieldFromNode(
                startpos=startpos,
                endpos=expression.endpos,
                value=expression,
            )

        expression = None

        with self.alternative():
            expression = self.expression()

        return ast.YieldNode(
            startpos=startpos,
            endpos=expression.endpos if expression is not None else endpos,
            value=expression,
        )

    def disjunction(self) -> ast.ExpressionNode:
        expression = self.conjunction()

        token = self.stream.peek_token()
        if token.type is not TokenType.OR:
            return expression

        self.stream.consume_token()

        expressions: typing.List[ast.ExpressionNode] = []
        expressions.append(expression)

        while True:
            expression = self.expression()
            expressions.append(expression)

            token = self.stream.peek_token()
            if token.type is not TokenType.OR:
                return ast.BoolOpNode(
                    startpos=expressions[0].startpos,
                    endpos=expressions[-1].endpos,
                    op=ast.BoolOperator.OR,
                    values=expressions,
                )

            self.stream.consume_token()

    def conjunction(self) -> ast.ExpressionNode:
        expression = self.inversion()

        token = self.stream.peek_token()
        if token.type is not TokenType.AND:
            return expression

        self.stream.consume_token()

        expressions: typing.List[ast.ExpressionNode] = []
        expressions.append(expression)

        while True:
            expression = self.expression()
            expressions.append(expression)

            token = self.stream.peek_token()
            if token.type is not TokenType.AND:
                return ast.BoolOpNode(
                    startpos=expressions[0].startpos,
                    endpos=expressions[-1].endpos,
                    op=ast.BoolOperator.AND,
                    values=expressions,
                )

    def inversion(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.type is TokenType.NOT:
            self.stream.consume_token()

            expression = self.inversion()
            return ast.UnaryOpNode(
                startpos=token.start,
                endpos=expression.endpos,
                op=ast.UnaryOperator.NOT,
                operand=expression,
            )

        return self.comparison()

    def comparison(self) -> ast.CompareNode:
        expression = self.bitwise_or()
        comparators: typing.List[ast.ComparatorNode] = []

        while True:
            token = self.stream.peek_token()
            operator = None

            if token.type is TokenType.EQEQUAL:
                operator = ast.CmpOperator.EQ
            elif token.type is TokenType.NOTEQUAL:
                operator = ast.CmpOperator.NOTEQ
            elif token.type is TokenType.LTHANEQ:
                operator = ast.CmpOperator.LTE
            elif token.type is TokenType.LTHAN:
                operator = ast.CmpOperator.LT
            elif token.type is TokenType.GTHANEQ:
                operator = ast.CmpOperator.GTE
            elif token.type is TokenType.GTHAN:
                operator = ast.CmpOperator.GT
            elif token.type is TokenType.IN:
                operator = ast.CmpOperator.IN

            if operator is not None:
                self.stream.consume_token()

            elif token.type is TokenType.NOT:
                token = self.stream.peek_token(1)

                if token.type is TokenType.IN:
                    self.stream.consume_token()
                    operator = ast.CmpOperator.NOTIN

            elif token.type is TokenType.IS:
                token = self.stream.peek_token(1)

                if token.type is TokenType.NOT:
                    self.stream.consume_token()
                    operator = ast.CmpOperator.ISNOT

            if operator is None:
                return ast.CompareNode(
                    startpos=expression.startpos,
                    endpos=comparators[-1].endpos,
                    left=expression,
                    comparators=comparators,
                )

            operand = self.bitwise_or()
            comparator = ast.ComparatorNode(
                startpos=token.start,
                endpos=operand.endpos,
                op=operator,
                value=operand,
            )

            comparators.append(comparator)

    def bitwise_or(self) -> ast.ExpressionNode:
        expression = self.bitwise_xor()

        while True:
            token = self.stream.peek_token()
            if token.type is not TokenType.VERTICALBAR:
                return expression

            self.stream.consume_token()

            operand = self.bitwise_xor()
            expression = ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=ast.Operator.BITOR,
                right=operand,
            )

    def bitwise_xor(self) -> ast.ExpressionNode:
        expression = self.bitwise_and()

        while True:
            token = self.stream.peek_token()
            if token.type is not TokenType.CIRCUMFLEX:
                return expression

            self.stream.consume_token()

            operand = self.bitwise_and()
            expression = ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=ast.Operator.BITXOR,
                right=operand,
            )

    def bitwise_and(self) -> ast.ExpressionNode:
        expression = self.shift()

        while True:
            token = self.stream.peek_token()
            if token.type is not TokenType.AMPERSAND:
                return expression

            self.stream.consume_token()

            operand = self.shift()
            expression = ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=ast.Operator.BITAND,
                right=operand,
            )

    def shift(self) -> ast.ExpressionNode:
        expression = self.sum()

        while True:
            token = self.stream.peek_token()

            if token.type is TokenType.DOUBLELTHAN:
                operator = ast.Operator.LSHIFT
            elif token.type is TokenType.DOUBLEGTHAN:
                operator = ast.Operator.RSHIFT
            else:
                return expression

            self.stream.consume_token()

            operand = self.sum()
            return ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=operator,
                right=operand,
            )

    def sum(self) -> ast.ExpressionNode:
        expression = self.term()

        while True:
            token = self.stream.peek_token()

            if token.type is TokenType.PLUS:
                operator = ast.Operator.ADD
            elif token.type is TokenType.MINUS:
                operator = ast.Operator.SUB
            else:
                return expression

            self.stream.consume_token()

            operand = self.term()
            return ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=operand,
                op=operator,
                right=operand,
            )

    def term(self) -> ast.ExpressionNode:
        expression = self.factor()

        while True:
            token = self.stream.peek_token()

            if token.type is TokenType.STAR:
                operator = ast.Operator.MULT
            elif token.type is TokenType.SLASH:
                operator = ast.Operator.DIV
            elif token.type is TokenType.DOUBLESLASH:
                operator = ast.Operator.FLOORDIV
            elif token.type is TokenType.PERCENT:
                operator = ast.Operator.MOD
            elif token.type is TokenType.AT:
                operator = ast.Operator.MATMULT
            else:
                return expression

            self.stream.consume_token()

            operand = self.term()
            expression = ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=operator,
                right=operand,
            )

    def factor(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()

        if token.type is TokenType.PLUS:
            operator = ast.UnaryOperator.UADD
        elif token.type is TokenType.MINUS:
            operator = ast.UnaryOperator.USUB
        elif token.type is TokenType.TILDE:
            operator = ast.UnaryOperator.INVERT
        else:
            return self.power()

        self.stream.consume_token()

        operand = self.factor()
        return ast.UnaryOpNode(
            startpos=token.start,
            endpos=operand.endpos,
            op=operator,
            operand=operand,
        )

    def power(self) -> ast.ExpressionNode:
        expression = self.await_primary()

        token = self.stream.peek_token()
        if token.type is TokenType.DOUBLESTAR:
            self.stream.consume_token()

            operand = self.factor()
            return ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=ast.Operator.POW,
                right=operand
            )

        return expression

    def await_primary(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.type is TokenType.AWAIT:
            self.stream.consume_token()

            expression = self.primary()
            return ast.AwaitNode(
                startpos=token.start,
                endpos=expression.endpos,
                value=expression,
            )

        return self.primary()

    def primary(self) -> ast.ExpressionNode:
        expression = self.atom()

        while True:
            token = self.stream.peek_token()

            if token.type is TokenType.IDENTIFIER:
                self.stream.consume_token()
                assert isinstance(token, IdentifierToken)

                expression = ast.AttributeNode(
                    startpos=expression.startpos,
                    endpos=token.end,
                    value=expression,
                    attr=token.content,
                )
            elif token.type is TokenType.OPENPAREN:
                assert False, '<Function Call>'
            elif token.type is TokenType.OPENBRACKET:
                self.stream.consume_token()

                slice = self.slices()
                expression = ast.SubscriptNode(
                    startpos=expression.startpos,
                    endpos=expression.endpos,
                    value=expression,
                    slice=slice,
                )
            else:
                return expression

    def slices(self) -> ast.ExpressionNode:
        assert False

    def slice(self) -> ast.ExpressionNode:
        assert False

    def atom(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()

        if token.type is TokenType.IDENTIFIER:
            self.stream.consume_token()
            assert isinstance(token, IdentifierToken)

            return ast.NameNode(
                startpos=token.start,
                endpos=token.end,
                value=token.content,
            )
        elif token.type is TokenType.TRUE:
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.TRUE,
            )
        elif token.type is TokenType.FALSE:
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.FALSE,
            )
        elif token.type is TokenType.NONE:
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.NONE,
            )
        # STRING, NUMBER, DICT, SET, LIST, TUPLE
        elif token.type is TokenType.ELLIPSIS:
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.ELLIPSIS,
            )

        assert False, '<Unexpected Token>'

    def lambdef(self) -> ast.LambdaNode:
        assert False
