from __future__ import annotations

import contextlib
import io
import typing

import attr

from . import ast
from ..tokens import (
    TokenKind,
    Token as TokenT,
    StringTokenFlags,
    NumberTokenFlags,
)
from .keywords import KEYWORDS, KeywordKind
from ..scanner import Scanner

__all__ = ('Parser',)

ReturnT = typing.TypeVar('ReturnT')

Token = TokenT[KeywordKind]

# TODO: Find a better way to implement the parser. I am probably
# going to add some sort of grammar interpreter.
# Remove the Typethon specific syntax and move it into another module
# Add missing Python syntax (lambda, assignment expression,
# pattern matching, + whatever junk they decided to add)

# I want to maintain a complete parser for Python syntax so we
# can compile it down to the same IR. Compiled Python would be
# heavily reliant on a runtime like CPython and I am unsure how
# that would look at the moment.


class TokenStream:
    def __init__(self, scanner: Scanner[KeywordKind]) -> None:
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
        return TokenStreamView(self, 0)


class TokenStreamView:
    def __init__(self, stream: TokenStream, position: int) -> None:
        self.stream = stream
        self.position = position

    @property
    def scanner(self) -> Scanner[KeywordKind]:
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
        del self.stream.cache[: self.position]

    def view(self) -> TokenStreamView:
        return TokenStreamView(self.stream, self.position)


class AlternativeRejectedError(Exception):
    def __str__(self) -> str:
        return 'The alternative was rejected.'


@attr.s(slots=True)
class Alternative:
    accepted: bool = attr.ib(init=False, default=False)
    exception: typing.Optional[Exception] = attr.ib(init=False, default=None)

    def reject(self) -> None:
        raise AlternativeRejectedError()


class Parser:
    def __init__(self, scanner: Scanner[KeywordKind]) -> None:
        self.scanner = scanner

        self.root_stream = TokenStream(scanner)
        self.stream: typing.Union[TokenStream, TokenStreamView] = self.root_stream

    @classmethod
    def from_source(cls, source: str) -> Parser:
        scanner = Scanner(source, KEYWORDS)
        return cls(scanner)

    @classmethod
    def parse_module(cls, source: str) -> ast.ModuleNode:
        return cls.from_source(source).module()

    @classmethod
    def parse_expressions(cls, source: str) -> ast.ExpressionNode:
        parser = cls.from_source(source)
        expressions = parser.expressions()

        while True:
            token = parser.stream.peek_token()
            if token.kind is TokenKind.NEWLINE:
                parser.stream.consume_token()
            elif token.kind is TokenKind.EOF:
                return expressions
            else:
                assert False, '<Expected (NEWLINE, EOF)>'

    @contextlib.contextmanager
    def alternative(self) -> typing.Iterator[Alternative]:
        stream = self.stream
        self.stream = stream.view()

        alternative = Alternative()

        try:
            yield alternative

            if stream is self.root_stream:
                self.stream.accept()
            else:
                assert isinstance(stream, TokenStreamView)
                stream.position = self.stream.position

            alternative.accepted = True
        except (AssertionError, AlternativeRejectedError) as exc:
            alternative.exception = exc
        finally:
            self.stream = stream

    @contextlib.contextmanager
    def lookahead(self, *kinds: TokenKind, negative: bool = False) -> typing.Iterator[Alternative]:
        with self.alternative() as alternative:
            yield alternative

            token = self.stream.peek_token()
            result = token.kind in kinds

            if result if negative else not result:
                alternative.reject()

    def optional(self, function: typing.Callable[[], ReturnT]) -> typing.Optional[ReturnT]:
        with self.alternative():
            return function()

    def optional_lookahead(
        self,
        function: typing.Callable[[], ReturnT],
        *kinds: TokenKind,
        negative: bool = False,
    ) -> typing.Optional[ReturnT]:
        result = None

        with self.lookahead(*kinds, negative=negative) as alternative:
            result = function()

        if alternative.accepted:
            return result

    def module(self) -> ast.ModuleNode:
        statements: typing.List[ast.StatementNode] = []

        with self.alternative():
            body = self.statements()
            statements.extend(body)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.EOF:
            assert False, '<Expected EOF>'

        self.stream.consume_token()
        return ast.ModuleNode(
            startpos=statements[0].startpos if statements else 0,
            endpos=statements[-1].endpos if statements else 0,
            body=statements,
        )

    def statements(self) -> typing.List[ast.StatementNode]:
        statements: typing.List[ast.StatementNode] = []

        statement = self.statement()
        if isinstance(statement, list):
            statements.extend(statement)
        else:
            statements.append(statement)

        while True:
            with self.alternative() as alternative:
                statement = self.statement()
                if isinstance(statement, list):
                    statements.extend(statement)
                else:
                    statements.append(statement)

            if not alternative.accepted:
                return statements

    def statement(
        self,
    ) -> typing.Union[ast.StatementNode, typing.List[ast.StatementNode]]:
        token = self.stream.peek_token()

        if token.kind is TokenKind.KEYWORD:
            match token.keyword:
                case KeywordKind.ASYNC:
                    return self.async_statement()
                case KeywordKind.CLASS:
                    return self.class_def()
                case KeywordKind.DEF:
                    return self.function_def()
                case KeywordKind.FOR:
                    return self.for_statement()
                case KeywordKind.IF:
                    return self.if_statement()
                case KeywordKind.TRY:
                    return self.try_statement()
                case KeywordKind.WHILE:
                    return self.while_statement()
                case KeywordKind.WITH:
                    return self.with_statement()

        elif token.kind is TokenKind.AT:
            return self.decorated_statement()

        return self.simple_statements()

    def block(self) -> typing.List[ast.StatementNode]:
        token = self.stream.peek_token()
        if token.kind is TokenKind.NEWLINE:
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.INDENT:
                assert False, '<Expected INDENT>'

            self.stream.consume_token()
            statements = self.statements()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.DEDENT:
                assert False, '<Expected DEDENT>'

            self.stream.consume_token()
            return statements

        return self.simple_statements()

    def async_statement(
        self,
        *,
        decorators: typing.Optional[typing.List[ast.ExpressionNode]] = None,
    ) -> ast.StatementNode:
        async_token = self.stream.consume_token()
        assert async_token.is_keyword(KeywordKind.ASYNC)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.KEYWORD:
            assert False, '<Expected Keyword After Async>'

        if decorators is not None:
            if token.keyword is not KeywordKind.DEF:
                assert False, '<Can Only Decorate Async Function>'

        match token.keyword:
            case KeywordKind.DEF:
                return self.function_def(async_token=async_token)
            case KeywordKind.FOR:
                return self.for_statement(async_token=async_token)
            case KeywordKind.WITH:
                return self.with_statement(async_token=async_token)

        assert False, '<Unexpected Token>'

    def class_def(
        self,
        *,
        decorators: typing.Optional[typing.List[ast.ExpressionNode]] = None,
    ) -> ast.ClassDefNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.CLASS)

        if decorators is not None:
            startpos = decorators[-1].startpos
        else:
            decorators = []
            startpos = token.start

        token = self.stream.peek_token()
        if token.kind is not TokenKind.IDENTIFIER:
            assert False, '<Expected IDENTIFIER>'

        self.stream.consume_token()
        content = token.content
        #expression = None

        # token = self.stream.peek_token() class X from Y
        #if token.type is TokenType.FROM:
        #    self.stream.consume_token()
        #    expression = self.expression()

        expressions: typing.List[ast.ExpressionNode] = []
        arguments: typing.List[ast.KeywordArgumentNode] = []

        token = self.stream.peek_token()
        if token.kind is TokenKind.OPENPAREN:
            self.stream.consume_token()

            args = self.arguments()
            kwargs = self.keyword_args()

            expressions.extend(args)
            arguments.extend(kwargs)

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEPAREN:
                assert False, '<Expected CLOSEPAREN>'

            self.stream.consume_token()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()

        statements = self.block()
        return ast.ClassDefNode(
            startpos=startpos,
            endpos=statements[-1].endpos,
            name=content,
            bases=expressions,
            kwargs=arguments,
            #meta=expression,
            body=statements,
            decorators=decorators,
        )

    def function_def(
        self,
        *,
        decorators: typing.Optional[typing.List[ast.ExpressionNode]] = None,
        async_token: typing.Optional[Token] = None,
    ) -> ast.FunctionDefNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.DEF)

        if decorators is not None:
            startpos = decorators[-1].startpos
        else:
            startpos = async_token.start if async_token is not None else token.start
            decorators = []

        expression = None

        token = self.stream.peek_token()
        if token.kind is not TokenKind.IDENTIFIER:
            assert False, '<Expected IDENTIFIER>'

        self.stream.consume_token()
        content = token.content

        token = self.stream.peek_token()
        if token.kind is not TokenKind.OPENPAREN:
            assert False, '<Expected OPENPAREN>'

        self.stream.consume_token()
        parameters = self.parameters()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEPAREN:
            assert False, '<Expected CLOSEPAREN>'

        self.stream.consume_token()
        endpos = token.end

        token = self.stream.peek_token()
        if token.kind is TokenKind.RARROW:
            self.stream.consume_token()
            expression = self.type_expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            return ast.FunctionDefNode(
                startpos=startpos,
                endpos=expression.endpos if expression is not None else endpos,
                is_async=async_token is not None,
                name=content,
                parameters=parameters,
                body=None,
                decorators=decorators,
                returns=expression,
            )

        self.stream.consume_token()

        statements = self.block()
        return ast.FunctionDefNode(
            startpos=startpos,
            endpos=statements[-1].endpos,
            is_async=async_token is not None,
            name=content,
            parameters=parameters,
            body=statements,
            decorators=decorators,
            returns=expression,
        )

    def parameters(self) -> typing.List[ast.FunctionParameterNode]:
        parameters: typing.List[ast.FunctionParameterNode] = []

        encountered_default = False
        encountered_posonly = False
        encountered_kwonly = False

        encountered_vararg = False
        encountered_varkwarg = False
        encountered_kwarg = False

        while True:
            token = self.stream.peek_token()
            if token.kind is TokenKind.SLASH:
                if not parameters or encountered_posonly:
                    assert False, '<Slash Not Permitted>'

                self.stream.consume_token()
                encountered_posonly = True

                for parameter in parameters:
                    parameter.kind = ast.ParameterKind.POSONLY

                token = self.stream.peek_token()
                if token.kind is not TokenKind.COMMA:
                    assert False, '<Expected Comma>'

                self.stream.consume_token()
            elif token.kind is TokenKind.STAR:
                token = self.stream.peek_token(1)

                if token.kind is TokenKind.COMMA:
                    self.stream.consume_token()

                    if encountered_kwonly or encountered_varkwarg:
                        assert False, '<Star Not Permitted>'

                    self.stream.consume_token()
                    encountered_kwonly = True

            with self.alternative() as alternative:
                parameter = self.parameter()

                if parameter.kind is ast.ParameterKind.VARARG:
                    encountered_vararg = True
                elif parameter.kind is ast.ParameterKind.VARKWARG:
                    encountered_varkwarg = True
                elif encountered_vararg or encountered_kwonly or encountered_varkwarg:
                    parameter.kind = ast.ParameterKind.KWONLY
                    encountered_kwarg = True
                else:
                    if parameter.default is not None:
                        encountered_default = True
                    elif encountered_default:
                        assert False, '<Expected Default>'

                parameters.append(parameter)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                kwonly_permitted = encountered_kwarg or encountered_varkwarg

                if encountered_kwonly and not kwonly_permitted:
                    assert False, '<Argument Must Follow *>'

                return parameters

            self.stream.consume_token()

    def parameter(self) -> ast.FunctionParameterNode:
        token = self.stream.peek_token()
        startpos = token.start
        endpos = token.end

        if token.kind is TokenKind.IDENTIFIER:
            self.stream.consume_token()

            kind = ast.ParameterKind.ARG
            content = token.content
        elif token.kind is TokenKind.STAR:
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected IDENTIFIER>'

            self.stream.consume_token()

            kind = ast.ParameterKind.VARARG
            content = token.content
        elif token.kind is TokenKind.DOUBLESTAR:
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected IDENTIFIER>'

            self.stream.consume_token()

            kind = ast.ParameterKind.VARKWARG
            content = token.content
        else:
            assert False, '<Unexpected Token>'

        expression = None
        default = None

        token = self.stream.peek_token()
        if token.kind is TokenKind.COLON:
            self.stream.consume_token()
            expression = self.type_expression()

        token = self.stream.peek_token()
        if token.kind is TokenKind.EQUAL:
            self.stream.consume_token()
            default = self.expression()

        if default is not None:
            endpos = default.endpos
        elif expression is not None:
            endpos = expression.endpos

        return ast.FunctionParameterNode(
            startpos=startpos,
            endpos=endpos,
            name=content,
            kind=kind,
            annotation=expression,
            default=default,
        )

    def for_statement(self, *, async_token: typing.Optional[Token] = None) -> ast.ForNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.FOR)

        startpos = async_token.start if async_token is not None else token.start
        expression = self.star_targets()

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.IN):
            assert False, '<Expected IN>'

        self.stream.consume_token()
        iterator = self.star_expressions()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()

        body = self.block()
        statements: typing.List[ast.StatementNode] = []

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.ELSE):
            else_body = self.else_statement()
            statements.extend(else_body)

        return ast.ForNode(
            startpos=startpos,
            endpos=statements[-1].endpos if statements else body[-1].endpos,
            is_async=async_token is not None,
            target=expression,
            iterator=iterator,
            body=body,
            else_body=statements,
        )

    def if_statement(self) -> ast.IfNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.IF)

        startpos = token.start
        expression = self.expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()

        body = self.block()
        else_body: typing.List[ast.StatementNode] = []

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.ELIF):
            statement = self.elif_statement()
            else_body.append(statement)

        elif token.is_keyword(KeywordKind.ELSE):
            statements = self.else_statement()
            else_body.extend(statements)

        return ast.IfNode(
            startpos=startpos,
            endpos=else_body[-1].endpos if else_body else body[-1].endpos,
            condition=expression,
            body=body,
            else_body=else_body,
        )

    def elif_statement(self) -> ast.IfNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.ELIF)

        startpos = token.start
        expression = self.expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()

        body = self.block()
        statements: typing.List[ast.StatementNode] = []

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.ELIF):
            else_block = self.elif_statement()
            statements.append(else_block)

        elif token.is_keyword(KeywordKind.ELSE):
            else_block = self.else_statement()
            statements.extend(else_block)

        return ast.IfNode(
            startpos=startpos,
            endpos=statements[-1].endpos if statements else body[-1].endpos,
            condition=expression,
            body=body,
            else_body=statements,
        )

    def else_statement(self) -> typing.List[ast.StatementNode]:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.ELSE)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()
        return self.block()

    def try_statement(self) -> ast.TryNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.TRY)

        startpos = token.start

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()

        block = self.block()
        handlers = self.except_handlers()

        else_body: typing.List[ast.StatementNode] = []
        finally_body: typing.List[ast.StatementNode] = []

        token = self.stream.peek_token()
        if handlers and token.is_keyword(KeywordKind.ELSE):
            statements = self.else_statement()
            else_body.extend(statements)

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.FINALLY):
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.COLON:
                assert False, '<Expected COLON>'

            self.stream.consume_token()

            statements = self.block()
            finally_body.extend(statements)

        if not handlers and not finally_body:
            assert False, '<Must Have Except Or Finally>'

        if finally_body:
            endpos = finally_body[-1].endpos
        elif else_body:
            endpos = else_body[-1].endpos
        else:
            endpos = handlers[-1].endpos

        return ast.TryNode(
            startpos=startpos,
            endpos=endpos,
            body=block,
            handlers=handlers,
            else_body=else_body,
            final_body=finally_body,
        )

    def except_handlers(self) -> typing.List[ast.ExceptHandlerNode]:
        handlers: typing.List[ast.ExceptHandlerNode] = []

        while True:
            token = self.stream.peek_token()
            if token.is_keyword(KeywordKind.EXCEPT):
                return handlers

            handler = self.except_handler()
            handlers.append(handler)

    def except_handler(self) -> ast.ExceptHandlerNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.EXCEPT)

        startpos = token.start

        expression = self.optional(self.expression)
        target = None

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.AS):
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected IDENTIFIER>'

            self.stream.consume_token()
            target = token.content

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()
        statements = self.block()

        return ast.ExceptHandlerNode(
            startpos=startpos,
            endpos=statements[-1].endpos,
            type=expression,
            target=target,
            body=statements,
        )

    def while_statement(self) -> ast.WhileNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.WHILE)

        startpos = token.start
        expression = self.expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()

        body = self.block()
        statements: typing.List[ast.StatementNode] = []

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.ELSE):
            else_block = self.else_statement()
            statements.extend(else_block)

        return ast.WhileNode(
            startpos=startpos,
            endpos=statements[-1].endpos if statements else body[-1].endpos,
            condition=expression,
            body=body,
            else_body=statements,
        )

    def with_statement(self, *, async_token: typing.Optional[Token] = None) -> ast.WithNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.WITH)

        startpos = async_token.start if async_token is not None else token.start

        token = self.stream.peek_token()
        if token.kind is TokenKind.OPENPAREN:
            self.stream.consume_token()

            items = self.with_items()

            token = self.stream.peek_token()
            if token.kind is TokenKind.COMMA:
                self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEPAREN:
                assert False, '<Expected CLOSEPAREN>'

            self.stream.consume_token()
        else:
            items = self.with_items()

            token = self.stream.peek_token()
            if token.kind is TokenKind.COMMA:
                assert False, '<Trailing Comma Not Premitted>'

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()
        statements = self.block()

        return ast.WithNode(
            startpos=startpos,
            endpos=statements[-1].endpos,
            is_async=async_token is not None,
            items=items,
            body=statements,
        )

    def with_items(self) -> typing.List[ast.WithItemNode]:
        items: typing.List[ast.WithItemNode] = []

        item = self.with_item()
        items.append(item)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return items

        self.stream.consume_token()

        while True:
            with self.alternative() as alternative:
                item = self.with_item()
                items.append(item)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                return items

            self.stream.consume_token()

    def with_item(self) -> ast.WithItemNode:
        expression = self.expression()

        token = self.stream.peek_token()
        if not token.is_keyword(KeywordKind.AS):
            return ast.WithItemNode(
                startpos=expression.startpos,
                endpos=expression.endpos,
                contextmanager=expression,
                target=None,
            )

        self.stream.consume_token()

        target = self.star_target()
        return ast.WithItemNode(
            startpos=expression.startpos,
            endpos=target.endpos,
            contextmanager=expression,
            target=target,
        )

    def decorated_statement(self) -> ast.StatementNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.AT

        expressions: typing.List[ast.ExpressionNode] = []

        expression = self.expression()
        expressions.append(expression)

        while True:
            token = self.stream.peek_token()
            if token.kind is not TokenKind.NEWLINE:
                assert False, '<Expected NEWLINE>'

            self.stream.consume_token()
            token = self.stream.peek_token()

            if token.kind is TokenKind.AT:
                self.stream.consume_token()

                expression = self.expression()
                expressions.append(expression)
            elif token.is_keyword(KeywordKind.ASYNC):
                return self.async_statement(decorators=expressions)
            elif token.is_keyword(KeywordKind.DEF):
                return self.function_def(decorators=expressions)
            elif token.is_keyword(KeywordKind.CLASS):
                return self.class_def(decorators=expressions)

            assert False, '<Unexpected Token>'

    def simple_statements(self) -> typing.List[ast.StatementNode]:
        statements: typing.List[ast.StatementNode] = []

        while True:
            statement = self.simple_statement()
            statements.append(statement)

            token = self.stream.peek_token()
            if token.kind is TokenKind.SEMICOLON:
                self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind in (TokenKind.NEWLINE, TokenKind.EOF):
                self.stream.consume_token()
                return statements

            assert False, f'<Expected (NEWLINE, EOF): {token!r}>'

    def assignment(self) -> ast.StatementNode:
        token = self.stream.peek_token()

        if token.kind is TokenKind.IDENTIFIER:
            with self.alternative():
                self.stream.consume_token()
                expression = ast.NameNode(
                    startpos=token.start, endpos=token.end, value=token.content
                )

                return self.annassign(expression)
        elif token.kind is TokenKind.OPENPAREN:
            with self.alternative():
                self.stream.consume_token()
                expression = self.optional(self.single_target)

                if expression is None:
                    expression = self.optional(self.single_subscript_attribute_target)

                token = self.stream.peek_token()
                if token.kind is not TokenKind.CLOSEPAREN:
                    assert False, '<Expected CLOSEPAREN>'

                assert expression is not None
                return self.annassign(expression)

        with self.alternative():
            expression = self.single_subscript_attribute_target()
            return self.annassign(expression)

        with self.alternative():
            expressions: typing.List[ast.ExpressionNode] = []

            expression = self.star_targets()
            expressions.append(expression)

            token = self.stream.peek_token()
            if token.kind is not TokenKind.EQUAL:
                assert False, '<Expected EQUAL>'

            self.stream.consume_token()

            while True:
                with self.lookahead(TokenKind.EQUAL) as alternative:
                    expression = self.star_targets()

                if alternative.accepted:
                    expressions.append(expression)
                else:
                    expression = self.yield_or_star_expressions()
                    return ast.AssignNode(
                        startpos=expressions[0].startpos,
                        endpos=expressions[-1].endpos,
                        targets=expressions,
                        value=expression,
                    )

                self.stream.consume_token()

        with self.alternative():
            expression = self.single_target()
            return self.augassign(expression)

        assert False, '<Invalid Assignment>'

    def annassign(self, target: ast.ExpressionNode) -> ast.AnnAssignNode:
        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()
        annotation = self.type_expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.EQUAL:
            if not isinstance(target, ast.NameNode):
                assert False, '<Expected NAME>'

            return ast.AnnAssignNode(
                startpos=target.startpos,
                endpos=annotation.endpos,
                target=target,
                annotation=annotation,
                value=None,
            )

        self.stream.consume_token()

        expression = self.yield_or_star_expressions()
        return ast.AnnAssignNode(
            startpos=target.startpos,
            endpos=expression.endpos,
            target=target,
            annotation=annotation,
            value=expression,
        )

    def augassign(self, target: ast.ExpressionNode) -> ast.AugAssignNode:
        token = self.stream.peek_token()

        if token.kind is TokenKind.PLUSEQUAL:
            operator = ast.Operator.ADD
        elif token.kind is TokenKind.MINUSEQUAL:
            operator = ast.Operator.SUB
        elif token.kind is TokenKind.STAREQUAL:
            operator = ast.Operator.MULT
        elif token.kind is TokenKind.ATEQUAL:
            operator = ast.Operator.MATMULT
        elif token.kind is TokenKind.SLASHEQUAL:
            operator = ast.Operator.DIV
        elif token.kind is TokenKind.PERCENTEQUAL:
            operator = ast.Operator.MOD
        elif token.kind is TokenKind.AMPERSANDEQUAL:
            operator = ast.Operator.BITAND
        elif token.kind is TokenKind.VERTICALBAREQUAL:
            operator = ast.Operator.BITOR
        elif token.kind is TokenKind.CIRCUMFLEXEQUAL:
            operator = ast.Operator.BITXOR
        elif token.kind is TokenKind.DOUBLELTHANEQUAL:
            operator = ast.Operator.LSHIFT
        elif token.kind is TokenKind.DOUBLEGTHANEQUAL:
            operator = ast.Operator.RSHIFT
        elif token.kind is TokenKind.DOUBLESTAREQUAL:
            operator = ast.Operator.POW
        elif token.kind is TokenKind.DOUBLESLASHEQUAL:
            operator = ast.Operator.FLOORDIV
        else:
            assert False, '<Expected Operator>'

        self.stream.consume_token()

        expression = self.yield_or_star_expressions()
        return ast.AugAssignNode(
            startpos=target.startpos,
            endpos=expression.endpos,
            target=target,
            op=operator,
            value=expression,
        )

    def yield_or_star_expressions(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.YIELD):
            return self.yield_expression()

        return self.star_expressions()

    def simple_statement(self) -> ast.StatementNode:
        token = self.stream.peek_token()

        if token.kind is TokenKind.KEYWORD:
            match token.keyword:
                case KeywordKind.ASSERT:
                    return self.assert_statement()
                case KeywordKind.BREAK:
                    return self.break_statement()
                case KeywordKind.CONTINUE:
                    return self.continue_statement()
                case KeywordKind.DEL:
                    return self.del_statement()
                case KeywordKind.FROM:
                    return self.import_from_statement()
                case KeywordKind.GLOBAL:
                    return self.global_statement()
                case KeywordKind.IMPORT:
                    return self.import_statement()
                case KeywordKind.NONLOCAL:
                    return self.nonlocal_statement()
                case KeywordKind.PASS:
                    return self.pass_statement()
                case KeywordKind.RAISE:
                    return self.raise_statement()
                case KeywordKind.RETURN:
                    return self.return_statement()
                case KeywordKind.YIELD:
                    return self.yield_statement()

        with self.alternative():
            return self.assignment()

        expression = self.star_expressions()
        return ast.ExprNode(
            startpos=expression.startpos,
            endpos=expression.endpos,
            expr=expression,
        )

    def assert_statement(self) -> ast.AssertNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.ASSERT)

        startpos = token.start

        expression = self.expression()
        message = None

        token = self.stream.peek_token()
        if token.kind is TokenKind.COMMA:
            self.stream.consume_token()
            message = self.expression()

        return ast.AssertNode(
            startpos=startpos,
            endpos=message.endpos if message is not None else expression.endpos,
            condition=expression,
            message=message,
        )

    def break_statement(self) -> ast.BreakNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.BREAK)

        return ast.BreakNode(startpos=token.start, endpos=token.end)

    def continue_statement(self) -> ast.ContinueNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.CONTINUE)

        return ast.ContinueNode(startpos=token.start, endpos=token.end)

    def del_statement(self) -> ast.DeleteNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.DEL)

        expressions = self.del_targets()
        return ast.DeleteNode(
            startpos=token.start,
            endpos=expressions[-1].endpos,
            targets=expressions,
        )

    def yield_statement(self) -> ast.ExprNode:
        expression = self.yield_expression()
        return ast.ExprNode(
            startpos=expression.startpos,
            endpos=expression.endpos,
            expr=expression,
        )

    def global_statement(self) -> ast.GlobalNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.GLOBAL)

        startpos = token.start
        endpos = token.end

        names: typing.List[str] = []

        while True:
            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected Identifier>'

            self.stream.consume_token()

            names.append(token.content)
            endpos = token.end

            token = self.stream.peek_token()
            if token.kind is not TokenKind.COMMA:
                return ast.GlobalNode(startpos=startpos, endpos=endpos, names=names)

            self.stream.consume_token()

    def import_from_statement(self) -> ast.ImportFromNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.FROM)

        startpos = token.start

        level = self.import_from_level()
        if level == 0:
            name = self.dotted_name()
        else:
            name = self.optional(self.dotted_name)

        token = self.stream.peek_token()
        if not token.is_keyword(KeywordKind.IMPORT):
            assert False, '<Expected IMPORT>'

        self.stream.consume_token()
        targets = self.import_from_targets()

        return ast.ImportFromNode(
            startpos=startpos,
            endpos=targets[-1].endpos,
            module=name,
            names=targets,
            level=level,
        )

    def import_statement(self) -> ast.ImportNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.IMPORT)

        names = self.dotted_as_names()
        return ast.ImportNode(
            startpos=token.start,
            endpos=names[-1].endpos,
            names=names,
        )

    def import_from_level(self) -> int:
        level = 0

        while True:
            token = self.stream.peek_token()
            if token.kind is TokenKind.DOT:
                level += 1
            elif token.kind is TokenKind.ELLIPSIS:
                level += 3
            else:
                return level

            self.stream.consume_token()

    def import_from_targets(self) -> typing.List[ast.AliasNode]:
        aliases: typing.List[ast.AliasNode] = []

        token = self.stream.peek_token()
        if token.kind is TokenKind.OPENPAREN:
            self.stream.consume_token()

            names = self.import_from_as_names()
            aliases.extend(names)

            token = self.stream.peek_token()
            if token.kind is TokenKind.COMMA:
                self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEPAREN:
                assert False, '<Expected CLOSEPAREN>'

            self.stream.consume_token()
        elif token.kind is TokenKind.STAR:
            name = ast.AliasNode(
                startpos=token.start,
                endpos=token.end,
                name=None,
                asname=None,
            )
            aliases.append(name)
        else:
            names = self.import_from_as_names()
            aliases.extend(names)

            token = self.stream.peek_token()
            if token.kind is TokenKind.COMMA:
                assert False, '<Trailing Comma Not Permitted>'

        return aliases

    def import_from_as_names(self) -> typing.List[ast.AliasNode]:
        aliases: typing.List[ast.AliasNode] = []

        name = self.import_from_as_name()
        aliases.append(name)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return aliases

        self.stream.consume_token()

        while True:
            with self.alternative() as alternative:
                name = self.import_from_as_name()
                aliases.append(name)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                return aliases

            self.stream.consume_token()

    def import_from_as_name(self) -> ast.AliasNode:
        token = self.stream.peek_token()
        if token.kind is not TokenKind.IDENTIFIER:
            assert False, '<Expected IDENTIFIER>'

        self.stream.consume_token()

        startpos = token.start
        content = token.content

        asname = None

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.AS):
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected IDENTIFIER>'

            self.stream.consume_token()
            asname = token.content

        return ast.AliasNode(startpos=startpos, endpos=-1, name=content, asname=asname)

    def dotted_as_names(self) -> typing.List[ast.AliasNode]:
        aliases: typing.List[ast.AliasNode] = []

        while True:
            name = self.dotted_as_name()
            aliases.append(name)

            token = self.stream.peek_token()
            if token.kind is not TokenKind.COMMA:
                return aliases

            self.stream.consume_token()

    def dotted_as_name(self) -> ast.AliasNode:
        name = self.dotted_name()
        asname = None

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.AS):
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected IDENTIFIER>'

            self.stream.consume_token()
            asname = token.content

        return ast.AliasNode(startpos=-1, endpos=-1, name=name, asname=asname)

    def dotted_name(self) -> str:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.IDENTIFIER
        content = token.content

        token = self.stream.peek_token()
        if token.kind is not TokenKind.DOT:
            return content

        names: typing.List[str] = []
        names.append(content)

        self.stream.consume_token()

        while True:
            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected IDENTIFIER>'

            self.stream.consume_token()
            names.append(token.content)

            token = self.stream.peek_token()
            if token.kind is not TokenKind.DOT:
                return '.'.join(names)

            self.stream.consume_token()

    def nonlocal_statement(self) -> ast.NonlocalNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.NONLOCAL)

        startpos = token.start
        endpos = token.end

        names: typing.List[str] = []

        while True:
            token = self.stream.peek_token()
            if token.kind is not TokenKind.IDENTIFIER:
                assert False, '<Expected Identifier>'

            self.stream.consume_token()
            names.append(token.content)
            endpos = token.end

            token = self.stream.peek_token()
            if token.kind is not TokenKind.COMMA:
                return ast.NonlocalNode(startpos=startpos, endpos=endpos, names=names)

            self.stream.consume_token()

    def pass_statement(self) -> ast.PassNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.PASS)

        return ast.PassNode(startpos=token.start, endpos=token.end)

    def raise_statement(self) -> ast.RaiseNode:
        token = self.stream.consume_token()
        assert token.is_keyword(KeywordKind.RAISE)

        startpos = token.start
        endpos = token.end

        expression = self.optional(self.expression)
        cause = None

        if expression is not None:
            from_token = self.stream.peek_token()

            if from_token.is_keyword(KeywordKind.FROM):
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
        assert token.is_keyword(KeywordKind.RETURN)

        expressions = self.optional(self.star_expressions)
        return ast.ReturnNode(
            startpos=token.start,
            endpos=expressions.endpos if expressions is not None else token.end,
            value=expressions,
        )

    def type_expression(self) -> ast.TypeExpressionNode:
        return self.type_primary()

    def type_primary(self) -> ast.TypeExpressionNode:
        atom = self.type_atom()

        while True:
            token = self.stream.peek_token()

            if token.kind is TokenKind.DOT:
                self.stream.consume_token()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.IDENTIFIER:
                    assert False, '<Expected IDENTIFIER>'
                
                self.stream.consume_token()
                atom = ast.TypeAttributeNode(
                    startpos=atom.startpos,
                    endpos=token.end,
                    value=atom,
                    attr=token.content
                )
            elif token.kind is TokenKind.OPENPAREN:
                self.stream.consume_token()
                expressions = self.type_arguments()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.CLOSEPAREN:
                    assert False, '<Expected CLOSEPAREN>'
                
                self.stream.consume_token()
                atom = ast.TypeCallNode(
                    startpos=atom.startpos,
                    endpos=token.end,
                    type=atom,
                    args=expressions,
                )
            else:
                return atom

    def type_arguments(self) -> typing.List[ast.TypeExpressionNode]:
        expressions: typing.List[ast.TypeExpressionNode] = []
        expression = None

        while True:
            with self.alternative() as alternative:
                expression = self.type_expression()

            if alternative.accepted:
                assert expression is not None
                expressions.append(expression)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                return expressions

            self.stream.consume_token()

    def type_atom(self) -> ast.TypeExpressionNode:
        token = self.stream.peek_token()

        if token.kind is TokenKind.IDENTIFIER:
            self.stream.consume_token()
            return ast.TypeNameNode(
                startpos=token.start,
                endpos=token.end,
                value=token.content,
            )

        elif token.kind is TokenKind.VERTICALBAR:
            with self.alternative():
                return self.type_parameter()

        elif token.kind is TokenKind.OPENBRACKET:
            with self.alternative():
                return self.list_type()
        
        elif token.kind is TokenKind.OPENBRACE:
            with self.alternative():
                return self.dict_type()
            
            with self.alternative():
                return self.set_type()

        assert False, f'<Unexpected token {token!r}>'

    def type_parameter(self) -> ast.TypeParameterNode:
        token = self.stream.peek_token()
        assert token.kind is TokenKind.VERTICALBAR

        startpos = token.start
        self.stream.consume_token()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.IDENTIFIER:
            assert False, '<Expected IDENTIFIER>'

        self.stream.consume_token()

        content = token.content
        constraint = None

        token = self.stream.peek_token()
        if token.kind is TokenKind.COLON:
            self.stream.consume_token()
            constraint = self.type_expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.VERTICALBAR:
            assert False, '<Expected VERTICALBAR>'

        self.stream.consume_token()
        return ast.TypeParameterNode(
            startpos=startpos,
            endpos=token.end,
            name=content,
            constraint=constraint,
        )

    def list_type(self) -> ast.ListTypeNode:
        token = self.stream.peek_token()
        if token.kind is not TokenKind.OPENBRACKET:
            assert False, '<Expected OPENBRACKET>'

        startpos = token.start
        self.stream.consume_token()

        elt = self.type_expression()
        # size = None

        token = self.stream.peek_token()
        #if token.type is TokenType.COMMA: TODO: Sized Lists
        #    self.stream.consume_token()
        #
        #    token = self.stream.peek_token()
        #    if token.type is not TokenType.NUMBER:
        #        assert False, '<Expected NUMBER>'
        #
        #    assert isinstance(token, NumberToken)
        #    size = token.content

        #    self.stream.consume_token()

        #token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACKET:
            assert False, '<Expected CLOSEBRACKET>'

        self.stream.consume_token()
        return ast.ListTypeNode(
            startpos=startpos,
            endpos=token.end,
            elt=elt,
            # size=size,
        )

    def dict_type(self) -> ast.DictTypeNode:
        token = self.stream.peek_token()
        if token.kind is not TokenKind.OPENBRACE:
            assert False, '<Expected OPENBRACE>'

        startpos = token.start
        self.stream.consume_token()

        key = self.type_expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()
        value = self.type_expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACE:
            assert False, '<Expected CLOSEBRACE>'

        self.stream.consume_token()
        return ast.DictTypeNode(
            startpos=startpos,
            endpos=token.end,
            key=key,
            value=value,
        )

    def set_type(self) -> ast.SetTypeNode:
        token = self.stream.peek_token()
        if token.kind is not TokenKind.OPENBRACE:
            assert False, '<Expected OPENBRACE>'

        startpos = token.start
        self.stream.consume_token()

        elt = self.type_expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACE:
            assert False, '<Expected CLOSEBRACE>'

        self.stream.consume_token()
        return ast.SetTypeNode(startpos=startpos, endpos=token.end, elt=elt)

    def expression_list(
        self, function: typing.Callable[[], ast.ExpressionNode]
    ) -> ast.ExpressionNode:
        expression = function()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return expression

        expressions: typing.List[ast.ExpressionNode] = []
        expressions.append(expression)

        self.stream.consume_token()
        endpos = token.end

        while True:
            with self.alternative() as alternative:
                expression = function()
                expressions.append(expression)

            token = self.stream.peek_token()

            if not alternative.accepted:
                return ast.TupleNode(
                    startpos=expressions[0].startpos,
                    endpos=endpos,
                    elts=expressions,
                )
            elif token.kind is not TokenKind.COMMA:
                return ast.TupleNode(
                    startpos=expressions[0].startpos,
                    endpos=expressions[-1].endpos,
                    elts=expressions,
                )

            self.stream.consume_token()
            endpos = token.end

    def expressions(self) -> ast.ExpressionNode:
        return self.expression_list(self.expression)

    def expression(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.LAMBDA):
            return self.lambdef()

        expression = self.disjunction()

        token = self.stream.peek_token()
        if not token.is_keyword(KeywordKind.IF):
            return expression

        self.stream.consume_token()
        condition = self.disjunction()

        token = self.stream.peek_token()
        if not token.is_keyword(KeywordKind.ELSE):
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

    def star_expressions(self) -> ast.ExpressionNode:
        return self.expression_list(self.star_expression)

    def star_expression(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.kind is TokenKind.STAR:
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
        assert token.is_keyword(KeywordKind.YIELD)

        startpos = token.start
        endpos = token.end

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.FROM):
            self.stream.consume_token()

            expression = self.expression()
            return ast.YieldFromNode(
                startpos=startpos,
                endpos=expression.endpos,
                value=expression,
            )

        expression = self.optional(self.expression)
        return ast.YieldNode(
            startpos=startpos,
            endpos=expression.endpos if expression is not None else endpos,
            value=expression,
        )

    def disjunction(self) -> ast.ExpressionNode:
        expression = self.conjunction()

        token = self.stream.peek_token()
        if not token.is_keyword(KeywordKind.OR):
            return expression

        self.stream.consume_token()

        expressions: typing.List[ast.ExpressionNode] = []
        expressions.append(expression)

        while True:
            expression = self.expression()
            expressions.append(expression)

            token = self.stream.peek_token()
            if not token.is_keyword(KeywordKind.OR):
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
        if not token.is_keyword(KeywordKind.AND):
            return expression

        self.stream.consume_token()

        expressions: typing.List[ast.ExpressionNode] = []
        expressions.append(expression)

        while True:
            expression = self.expression()
            expressions.append(expression)

            token = self.stream.peek_token()
            if not token.is_keyword(KeywordKind.AND):
                return ast.BoolOpNode(
                    startpos=expressions[0].startpos,
                    endpos=expressions[-1].endpos,
                    op=ast.BoolOperator.AND,
                    values=expressions,
                )

    def inversion(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.NOT):
            self.stream.consume_token()

            expression = self.inversion()
            return ast.UnaryOpNode(
                startpos=token.start,
                endpos=expression.endpos,
                op=ast.UnaryOperator.NOT,
                operand=expression,
            )

        return self.comparison()

    def comparison(self) -> ast.ExpressionNode:
        expression = self.bitwise_or()

        token = self.stream.peek_token()
        if token.kind not in (
            TokenKind.EQEQUAL,
            TokenKind.NOTEQUAL,
            TokenKind.LTHANEQ,
            TokenKind.LTHAN,
            TokenKind.GTHANEQ,
            TokenKind.GTHAN,
        ) and not token.is_keyword(
            KeywordKind.IN,
            KeywordKind.NOT,
            KeywordKind.IS,
        ):
            return expression

        comparators: typing.List[ast.ComparatorNode] = []

        while True:
            token = self.stream.peek_token()
            operator = None

            if token.kind is TokenKind.EQEQUAL:
                operator = ast.CmpOperator.EQ
            elif token.kind is TokenKind.NOTEQUAL:
                operator = ast.CmpOperator.NOTEQ
            elif token.kind is TokenKind.LTHANEQ:
                operator = ast.CmpOperator.LTE
            elif token.kind is TokenKind.LTHAN:
                operator = ast.CmpOperator.LT
            elif token.kind is TokenKind.GTHANEQ:
                operator = ast.CmpOperator.GTE
            elif token.kind is TokenKind.GTHAN:
                operator = ast.CmpOperator.GT
            elif token.is_keyword(KeywordKind.IN):
                operator = ast.CmpOperator.IN

            if operator is not None:
                self.stream.consume_token()

            elif token.is_keyword(KeywordKind.NOT):
                token = self.stream.peek_token(1)

                if token.is_keyword(KeywordKind.IN):
                    self.stream.consume_token()
                    self.stream.consume_token()
                    operator = ast.CmpOperator.NOTIN

            elif token.is_keyword(KeywordKind.IS):
                token = self.stream.peek_token(1)

                if token.is_keyword(KeywordKind.NOT):
                    self.stream.consume_token()
                    self.stream.consume_token()
                    operator = ast.CmpOperator.ISNOT
                else:
                    self.stream.consume_token()
                    operator = ast.CmpOperator.IS

            if operator is None:
                if not comparators:
                    return expression

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
            if token.kind is not TokenKind.VERTICALBAR:
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
            if token.kind is not TokenKind.CIRCUMFLEX:
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
            if token.kind is not TokenKind.AMPERSAND:
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

            if token.kind is TokenKind.DOUBLELTHAN:
                operator = ast.Operator.LSHIFT
            elif token.kind is TokenKind.DOUBLEGTHAN:
                operator = ast.Operator.RSHIFT
            else:
                return expression

            self.stream.consume_token()

            operand = self.sum()
            expression = ast.BinaryOpNode(
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

            if token.kind is TokenKind.PLUS:
                operator = ast.Operator.ADD
            elif token.kind is TokenKind.MINUS:
                operator = ast.Operator.SUB
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

    def term(self) -> ast.ExpressionNode:
        expression = self.factor()

        while True:
            token = self.stream.peek_token()

            if token.kind is TokenKind.STAR:
                operator = ast.Operator.MULT
            elif token.kind is TokenKind.SLASH:
                operator = ast.Operator.DIV
            elif token.kind is TokenKind.DOUBLESLASH:
                operator = ast.Operator.FLOORDIV
            elif token.kind is TokenKind.PERCENT:
                operator = ast.Operator.MOD
            elif token.kind is TokenKind.AT:
                operator = ast.Operator.MATMULT
            else:
                return expression

            self.stream.consume_token()

            operand = self.factor()
            expression = ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=operator,
                right=operand,
            )

    def factor(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()

        if token.kind is TokenKind.PLUS:
            operator = ast.UnaryOperator.UADD
        elif token.kind is TokenKind.MINUS:
            operator = ast.UnaryOperator.USUB
        elif token.kind is TokenKind.TILDE:
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
        if token.kind is TokenKind.DOUBLESTAR:
            self.stream.consume_token()

            operand = self.factor()
            return ast.BinaryOpNode(
                startpos=expression.startpos,
                endpos=operand.endpos,
                left=expression,
                op=ast.Operator.POW,
                right=operand,
            )

        return expression

    def await_primary(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.AWAIT):
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

            if token.kind is TokenKind.DOT:
                self.stream.consume_token()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.IDENTIFIER:
                    assert False, '<Expected IDENTIFIER>'

                self.stream.consume_token()

                expression = ast.AttributeNode(
                    startpos=expression.startpos,
                    endpos=token.end,
                    value=expression,
                    attr=token.content,
                )
            elif token.kind is TokenKind.OPENPAREN:
                expressions: typing.List[ast.ExpressionNode] = []
                arguments: typing.List[ast.KeywordArgumentNode] = []

                with self.alternative() as alternative:
                    argument = self.genexp()
                    expressions.append(argument)

                if not alternative.accepted:
                    self.stream.consume_token()

                    args = self.arguments()
                    kwargs = self.keyword_args()

                    expressions.extend(args)
                    arguments.extend(kwargs)

                    token = self.stream.peek_token()
                    if token.kind is not TokenKind.CLOSEPAREN:
                        assert False, '<Expected CLOSEPAREN>'

                    self.stream.consume_token()
                    endpos = token.end
                else:
                    endpos = expressions[-1].endpos

                expression = ast.CallNode(
                    startpos=expression.startpos,
                    endpos=endpos,
                    func=expression,
                    args=expressions,
                    kwargs=arguments,
                )
            elif token.kind is TokenKind.OPENBRACKET:
                self.stream.consume_token()

                slice = self.slices()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.CLOSEBRACKET:
                    assert False, '<Expected CLOSEBRACKET>'

                self.stream.consume_token()
                expression = ast.SubscriptNode(
                    startpos=expression.startpos,
                    endpos=expression.endpos,
                    value=expression,
                    slice=slice,
                )
            else:
                return expression

    def slices(self) -> ast.ExpressionNode:
        expression = self.slice()
        startpos = expression.startpos

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return expression

        self.stream.consume_token()
        endpos = token.end

        expressions: typing.List[ast.ExpressionNode] = []
        expressions.append(expression)

        while True:
            with self.alternative() as alternative:
                expression = self.slice()
                expressions.append(expression)

            token = self.stream.peek_token()

            if not alternative.accepted:
                return ast.TupleNode(
                    startpos=startpos,
                    endpos=expressions[-1].endpos,
                    elts=expressions,
                )
            elif token.kind is not TokenKind.COMMA:
                return ast.TupleNode(
                    startpos=startpos,
                    endpos=endpos,
                    elts=expressions,
                )

            self.stream.consume_token()
            endpos = token.end

    def slice(self) -> ast.ExpressionNode:
        expression = self.optional(self.expression)

        token = self.stream.peek_token()
        startpos = expression.startpos if expression is not None else token.start
        endpos = token.end

        if token.kind is not TokenKind.COLON:
            if expression is None:
                assert False, '<Missing Slice>'

            return expression

        self.stream.consume_token()
        stop = self.optional(self.expression)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            return ast.SliceNode(
                startpos=startpos,
                endpos=stop.endpos if stop is not None else endpos,
                start=expression,
                stop=stop,
                step=None,
            )

        self.stream.consume_token()
        step = self.optional(self.expression)

        return ast.SliceNode(
            startpos=startpos,
            endpos=step.endpos if step is not None else token.end,
            start=expression,
            stop=stop,
            step=step,
        )

    def atom(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()

        if token.kind is TokenKind.IDENTIFIER:
            self.stream.consume_token()
            return ast.NameNode(
                startpos=token.start,
                endpos=token.end,
                value=token.content,
            )
        elif token.is_keyword(KeywordKind.TRUE):
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.TRUE,
            )
        elif token.is_keyword(KeywordKind.FALSE):
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.FALSE,
            )
        elif token.is_keyword(KeywordKind.NONE):
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.NONE,
            )
        elif token.kind is TokenKind.STRING:
            return self.strings()
        elif token.kind is TokenKind.NUMBER:
            self.stream.consume_token()

            if token.flags & NumberTokenFlags.BINARY:
                radix = 2
            elif token.flags & NumberTokenFlags.OCTAL:
                radix = 8
            elif token.flags & NumberTokenFlags.HEXADECIMAL:
                radix = 16
            else:
                radix = -1

            if radix != -1:
                return ast.IntegerNode(
                    startpos=token.start,
                    endpos=token.end,
                    value=int(token.content, radix),
                )

            if token.flags & NumberTokenFlags.IMAGINARY:
                return ast.ComplexNode(
                    startpos=token.start,
                    endpos=token.end,
                    value=complex(token.content),
                )

            if token.flags & NumberTokenFlags.FLOAT:
                return ast.FloatNode(
                    startpos=token.start,
                    endpos=token.end,
                    value=float(token.content),
                )

            return ast.IntegerNode(
                startpos=token.start,
                endpos=token.end,
                value=int(token.content),
            )
        elif token.kind is TokenKind.OPENPAREN:
            with self.alternative():
                return self.tuple()

            with self.alternative():
                return self.group()

            with self.alternative():
                return self.genexp()
        elif token.kind is TokenKind.OPENBRACKET:
            with self.alternative():
                return self.list()

            with self.alternative():
                return self.listcomp()
        elif token.kind is TokenKind.OPENBRACE:
            with self.alternative():
                return self.dict()

            with self.alternative():
                return self.set()

            with self.alternative():
                return self.dictcomp()

            with self.alternative():
                return self.setcomp()
        elif token.kind is TokenKind.ELLIPSIS:
            self.stream.consume_token()

            return ast.ConstantNode(
                startpos=token.start,
                endpos=token.end,
                type=ast.ConstantType.ELLIPSIS,
            )

        assert False, f'<Unexpected Token: {token!r}>'

    def group(self) -> ast.ExpressionNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENPAREN

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.YIELD):
            expression = self.yield_expression()
        else:
            expression = self.expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEPAREN:
            assert False, '<Expected CLOSEPAREN>'

        self.stream.consume_token()
        return expression

    def lambdef(self) -> ast.LambdaNode:
        assert False

    def strings(self) -> ast.StringNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.STRING

        buffer = io.StringIO()
        buffer.write(token.content)

        startpos = token.start
        endpos = token.end

        flags = ast.StringFlags(
            ast.StringFlags.RAW * token.flags & StringTokenFlags.RAW
            | ast.StringFlags.BYTES * token.flags & StringTokenFlags.BYTES
            | ast.StringFlags.FORMAT * token.flags & StringTokenFlags.FORMAT
        )

        while True:
            token = self.stream.peek_token()
            if token.kind is TokenKind.STRING:
                self.stream.consume_token()

                buffer.write(token.content)
                endpos = token.end
            else:
                return ast.StringNode(
                    startpos=startpos,
                    endpos=endpos,
                    value=buffer.getvalue(),
                    flags=flags,
                )

    def list(self) -> ast.ListNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENBRACKET

        startpos = token.start
        expressions: typing.List[ast.ExpressionNode] = []

        with self.alternative():
            expression = self.star_expressions()
            if isinstance(expression, ast.TupleNode):
                expressions.extend(expression.elts)
            else:
                expressions.append(expression)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACKET:
            assert False, '<Expected CLOSEPAREN>'

        self.stream.consume_token()
        return ast.ListNode(startpos=startpos, endpos=token.end, elts=expressions)

    def tuple(self) -> ast.TupleNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENPAREN

        startpos = token.start
        expressions: typing.List[ast.ExpressionNode] = []

        with self.alternative() as alternative:
            expression = self.star_expressions()
            if isinstance(expression, ast.TupleNode):
                expressions.extend(expression.elts)
            else:
                expressions.append(expression)

        if alternative.accepted:
            token = self.stream.peek_token()
            if token.kind is not TokenKind.COMMA:
                assert False, '<Expected COMMA>'

            self.stream.consume_token()

            with self.alternative():
                expression = self.star_expressions()
                if isinstance(expression, ast.TupleNode):
                    expressions.extend(expression.elts)
                else:
                    expressions.append(expression)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEPAREN:
            assert False, '<Expected CLOSEPAREN>'

        self.stream.consume_token()
        return ast.TupleNode(startpos=startpos, endpos=token.end, elts=expressions)

    def set(self) -> ast.SetNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENBRACE

        startpos = token.start
        expressions: typing.List[ast.ExpressionNode] = []

        with self.alternative():
            expression = self.star_expressions()
            if isinstance(expression, ast.TupleNode):
                expressions.extend(expression.elts)
            else:
                expressions.append(expression)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACE:
            assert False, '<Expected CLOSEBRACE>'

        self.stream.consume_token()
        return ast.SetNode(startpos=startpos, endpos=token.end, elts=expressions)

    def dict(self) -> ast.DictNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENBRACE

        startpos = token.start
        elts: typing.List[ast.DictElt] = []

        with self.alternative():
            elts.extend(self.star_kvpairs())

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACE:
            assert False, '<Expected CLOSEBRACE>'

        self.stream.consume_token()
        return ast.DictNode(startpos=startpos, endpos=token.end, elts=elts)

    def star_kvpairs(self) -> typing.List[ast.DictElt]:
        elts: typing.List[ast.DictElt] = []

        elt = self.star_kvpair()
        elts.append(elt)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return elts

        self.stream.consume_token()

        while True:
            with self.alternative() as alternative:
                elt = self.star_kvpair()
                elts.append(elt)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                return elts

            self.stream.consume_token()

    def star_kvpair(self) -> ast.DictElt:
        token = self.stream.peek_token()
        if token.kind is TokenKind.DOUBLESTAR:
            self.stream.consume_token()

            expression = self.bitwise_or()
            return ast.DictElt(
                startpos=token.start,
                endpos=expression.endpos,
                key=None,
                value=expression,
            )

        return self.kvpair()

    def kvpair(self) -> ast.DictElt:
        expression = self.expression()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COLON:
            assert False, '<Expected COLON>'

        self.stream.consume_token()

        value = self.expression()
        return ast.DictElt(
            startpos=expression.startpos,
            endpos=value.endpos,
            key=expression,
            value=value,
        )

    def for_if_clauses(self) -> typing.List[ast.ComprehensionNode]:
        comprehensions: typing.List[ast.ComprehensionNode] = []

        comprehension = self.for_if_clause()
        comprehensions.append(comprehension)

        while True:
            with self.alternative() as alternative:
                comprehension = self.for_if_clause()
                comprehensions.append(comprehension)

            if not alternative.accepted:
                return comprehensions

    def for_if_clause(self) -> ast.ComprehensionNode:
        token = self.stream.peek_token()
        is_async = False
        startpos = token.start

        if token.is_keyword(KeywordKind.ASYNC):
            self.stream.consume_token()

            is_async = True
            token = self.stream.peek_token()

        if not token.is_keyword(KeywordKind.FOR):
            assert False, '<Expected FOR>'

        self.stream.consume_token()
        target = self.star_targets()

        token = self.stream.peek_token()
        if token.is_keyword(KeywordKind.IN):
            assert False, '<Expected IN>'

        self.stream.consume_token()
        iterator = self.disjunction()

        expressions: typing.List[ast.ExpressionNode] = []

        while True:
            token = self.stream.peek_token()
            if (
                token.kind is not TokenKind.KEYWORD
                or token.keyword is not KeywordKind.IF
            ):
                return ast.ComprehensionNode(
                    startpos=startpos,
                    endpos=expressions[-1].endpos if expressions else iterator.endpos,
                    is_async=is_async,
                    target=target,
                    iterator=iterator,
                    conditions=expressions,
                )

            self.stream.consume_token()

            expression = self.disjunction()
            expressions.append(expression)

    def listcomp(self) -> ast.ListCompNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENBRACKET

        startpos = token.start

        expression = self.expression()
        comprehensions = self.for_if_clauses()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACKET:
            assert False, '<Expected CLOSEBRACKER>'

        self.stream.consume_token()
        return ast.ListCompNode(
            startpos=startpos,
            endpos=token.end,
            elt=expression,
            comprehensions=comprehensions,
        )

    def setcomp(self) -> ast.SetCompNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENBRACE

        startpos = token.start

        expression = self.expression()
        comprehensions = self.for_if_clauses()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEBRACE:
            assert False, '<Expected CLOSEBRACE>'

        self.stream.consume_token()
        return ast.SetCompNode(
            startpos=startpos,
            endpos=token.end,
            elt=expression,
            comprehensions=comprehensions,
        )

    def genexp(self) -> ast.GeneratorExpNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENPAREN

        startpos = token.start

        expression = self.expression()
        comprehensions = self.for_if_clauses()

        token = self.stream.peek_token()
        if token.kind is not TokenKind.CLOSEPAREN:
            assert False, '<Expected CLOSEPAREN>'

        self.stream.consume_token()
        return ast.GeneratorExpNode(
            startpos=startpos,
            endpos=token.end,
            elt=expression,
            comprehensions=comprehensions,
        )

    def dictcomp(self) -> ast.DictCompNode:
        token = self.stream.consume_token()
        assert token.kind is TokenKind.OPENBRACE

        startpos = token.start

        elt = self.kvpair()
        comprehensions = self.for_if_clauses()

        self.stream.consume_token()
        return ast.DictCompNode(
            startpos=startpos,
            endpos=token.end,
            elt=elt,
            comprehensions=comprehensions,
        )

    def arguments(self) -> typing.List[ast.ExpressionNode]:
        expressions: typing.List[ast.ExpressionNode] = []
        expression = None

        while True:
            with self.lookahead(TokenKind.EQUAL, negative=True) as alternative:
                expression = self.star_expression()

            if alternative.accepted:
                assert expression is not None
                expressions.append(expression)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                return expressions

            self.stream.consume_token()

    def keyword_args(self) -> typing.List[ast.KeywordArgumentNode]:
        arguments: typing.List[ast.KeywordArgumentNode] = []

        while True:
            with self.alternative() as alternative:
                argument = self.keyword_arg()
                arguments.append(argument)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                return arguments

            self.stream.consume_token()

    def keyword_arg(self) -> ast.KeywordArgumentNode:
        token = self.stream.peek_token()
        startpos = token.start

        if token.kind is TokenKind.DOUBLESTAR:
            self.stream.consume_token()

            expression = self.expression()
            return ast.KeywordArgumentNode(
                startpos=startpos,
                endpos=token.end,
                name=None,
                value=expression,
            )
        elif token.kind is TokenKind.IDENTIFIER:
            self.stream.consume_token()
            content = token.content

            token = self.stream.peek_token()
            if token.kind is not TokenKind.EQUAL:
                assert False, '<Expected EQUAL>'

            self.stream.consume_token()

            expression = self.expression()
            return ast.KeywordArgumentNode(
                startpos=startpos,
                endpos=expression.endpos,
                name=content,
                value=expression,
            )

        assert False, '<Unexpected Token>'

    def star_targets(self) -> ast.ExpressionNode:
        expression = self.star_target()
        startpos = expression.startpos

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return expression

        self.stream.consume_token()
        endpos = token.end

        expressions: typing.List[ast.ExpressionNode] = []
        expressions.append(expression)

        while True:
            with self.alternative() as alternative:
                expression = self.star_target()
                expressions.append(expression)

            token = self.stream.peek_token()

            if not alternative.accepted:
                return ast.TupleNode(
                    startpos=expression.startpos,
                    endpos=endpos,
                    elts=expressions,
                )
            elif token.kind is not TokenKind.COMMA:
                return ast.TupleNode(
                    startpos=startpos,
                    endpos=expressions[-1].endpos,
                    elts=expressions,
                )

            self.stream.consume_token()
            endpos = token.end

    def star_target(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        startpos = token.start

        if token.kind is TokenKind.STAR:
            self.stream.consume_token()

            token = self.stream.peek_token()
            if token.kind is TokenKind.STAR:
                assert False, '<Unexpected STAR>'

            expression = self.star_target()
            return ast.StarredNode(
                startpos=startpos,
                endpos=expression.endpos,
                value=expression,
            )

        return self.target_with_star_atom()

    def star_targets_list(self) -> ast.ListNode:
        expressions: typing.List[ast.ExpressionNode] = []

        expression = self.star_target()
        expressions.append(expression)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return ast.ListNode(
                startpos=expression.startpos,
                endpos=expression.endpos,
                elts=expressions,
            )

        endpos = token.end
        self.stream.consume_token()

        while True:
            with self.alternative() as alternative:
                expression = self.star_target()
                expressions.append(expression)

            token = self.stream.peek_token()

            if not alternative.accepted:
                return ast.ListNode(
                    startpos=expressions[0].startpos,
                    endpos=endpos,
                    elts=expressions,
                )
            elif token.kind is not TokenKind.COMMA:
                return ast.ListNode(
                    startpos=expressions[0].startpos,
                    endpos=expressions[-1].endpos,
                    elts=expressions,
                )

            self.stream.consume_token()
            endpos = token.end

    def star_targets_tuple(self) -> ast.TupleNode:
        expressions: typing.List[ast.ExpressionNode] = []

        expression = self.star_target()
        expressions.append(expression)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return ast.TupleNode(
                startpos=expression.startpos,
                endpos=expression.endpos,
                elts=expressions,
            )

        endpos = token.end
        self.stream.consume_token()

        while True:
            with self.alternative() as alternative:
                expression = self.star_target()
                expressions.append(expression)

            token = self.stream.peek_token()

            if not alternative.accepted:
                return ast.TupleNode(
                    startpos=expressions[0].startpos,
                    endpos=endpos,
                    elts=expressions,
                )
            elif token.kind is not TokenKind.COMMA:
                return ast.TupleNode(
                    startpos=expressions[0].startpos,
                    endpos=expressions[-1].endpos,
                    elts=expressions,
                )

            self.stream.consume_token()
            endpos = token.end

    def target_with_star_atom(self) -> ast.ExpressionNode:
        with self.lookahead(
            TokenKind.DOT, TokenKind.OPENBRACKET, TokenKind.OPENPAREN, negative=True
        ):
            expression = self.target_primary()

            token = self.stream.peek_token()
            if token.kind is TokenKind.DOT:
                self.stream.consume_token()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.IDENTIFIER:
                    assert False, '<Expected IDENTIFIER>'

                self.stream.consume_token()

                return ast.AttributeNode(
                    startpos=expression.startpos,
                    endpos=token.end,
                    value=expression,
                    attr=token.content,
                )
            elif token.kind is TokenKind.OPENBRACKET:
                self.stream.consume_token()

                slice = self.slices()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.CLOSEBRACKET:
                    assert False, '<Expected CLOSEBRACKET>'

                self.stream.consume_token()
                return ast.SubscriptNode(
                    startpos=expression.startpos,
                    endpos=expression.endpos,
                    value=expression,
                    slice=slice,
                )

            assert False, '<Expected (DOT, OPENBRACKET)>'

        return self.star_atom()

    def star_atom(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        if token.kind is TokenKind.IDENTIFIER:
            self.stream.consume_token()

            return ast.NameNode(
                startpos=token.start,
                endpos=token.end,
                value=token.content,
            )
        elif token.kind is TokenKind.OPENPAREN:
            self.stream.consume_token()
            startpos = token.start

            expressions: typing.List[ast.ExpressionNode] = []

            with self.alternative() as alternative:
                expression = self.target_with_star_atom()
                expressions.append(expression)

            if not alternative.accepted:
                with self.alternative():
                    expression = self.star_targets_tuple()
                    expressions.extend(expression.elts)

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEPAREN:
                assert False, '<Expected CLOSEPAREN>'

            self.stream.consume_token()
            return ast.TupleNode(
                startpos=startpos,
                endpos=token.end,
                elts=expressions,
            )
        elif token.kind is TokenKind.OPENBRACKET:
            self.stream.consume_token()
            startpos = token.start

            expressions: typing.List[ast.ExpressionNode] = []

            with self.alternative():
                expression = self.star_targets_list()
                expressions.extend(expression.elts)

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEBRACKET:
                assert False, '<Expected CLOSEBRACKET>'

            self.stream.consume_token()
            return ast.ListNode(
                startpos=startpos,
                endpos=token.end,
                elts=expressions,
            )

        assert False, '<Unexpected Token>'

    def single_target(self) -> ast.ExpressionNode:
        with self.alternative():
            return self.single_subscript_attribute_target()

        token = self.stream.peek_token()
        if token.kind is TokenKind.IDENTIFIER:
            self.stream.consume_token()

            return ast.NameNode(
                startpos=token.start,
                endpos=token.end,
                value=token.content,
            )
        elif token.kind is TokenKind.OPENPAREN:
            self.stream.consume_token()

            expression = self.single_target()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEPAREN:
                assert False, '<Expected CLOSEPAREN>'

            self.stream.consume_token()
            return expression

        assert False, '<Unexpected Token>'

    def single_subscript_attribute_target(self) -> ast.ExpressionNode:
        expression = self.target_primary()

        with self.lookahead(
            TokenKind.DOT, TokenKind.OPENBRACKET, TokenKind.OPENPAREN, negative=True
        ) as alternative:
            token = self.stream.peek_token()

            if token.kind is TokenKind.DOT:
                self.stream.consume_token()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.IDENTIFIER:
                    assert False, '<Expected IDENTIFIER>'

                self.stream.consume_token()

                expression = ast.AttributeNode(
                    startpos=expression.startpos,
                    endpos=token.end,
                    value=expression,
                    attr=token.content,
                )
            elif token.kind is TokenKind.OPENBRACKET:
                self.stream.consume_token()

                slice = self.slices()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.CLOSEBRACKET:
                    assert False, '<Expected CLOSEBRACKET>'

                self.stream.consume_token()
                expression = ast.SubscriptNode(
                    startpos=expression.startpos,
                    endpos=slice.endpos,
                    value=expression,
                    slice=slice,
                )

        if not alternative.accepted:
            assert False, '<Expected !(DOT, OPENBRACKET, OPENPAREN)>'

        return expression

    def target_primary(self) -> ast.ExpressionNode:
        expression = self.optional_lookahead(
            self.atom, TokenKind.DOT, TokenKind.OPENBRACKET, TokenKind.OPENPAREN
        )
        if expression is None:
            assert False, '<Expected <atom> (DOT, OPENBRACKET, OPENPAREN)>'

        expr = None

        while True:
            token = self.stream.peek_token()

            with self.lookahead(
                TokenKind.DOT, TokenKind.OPENBRACKET, TokenKind.OPENPAREN
            ) as alternative:
                if token.kind is TokenKind.DOT:
                    self.stream.consume_token()

                    token = self.stream.peek_token()
                    if token.kind is not TokenKind.IDENTIFIER:
                        assert False, '<Expected IDENTIFIER>'

                    self.stream.consume_token()

                    expr = ast.AttributeNode(
                        startpos=expression.startpos,
                        endpos=token.end,
                        value=expression,
                        attr=token.content,
                    )
                elif token.kind is TokenKind.OPENBRACKET:
                    self.stream.consume_token()

                    slice = self.slices()

                    token = self.stream.peek_token()
                    if token.kind is not TokenKind.CLOSEBRACKET:
                        assert False, '<Expected CLOSEBRACKET>'

                    self.stream.consume_token()
                    expr = ast.SubscriptNode(
                        startpos=expression.startpos,
                        endpos=slice.endpos,
                        value=expression,
                        slice=slice,
                    )
                elif token.kind is TokenKind.OPENPAREN:
                    expressions: typing.List[ast.ExpressionNode] = []
                    arguments: typing.List[ast.KeywordArgumentNode] = []

                    with self.alternative() as alternative:
                        argument = self.genexp()
                        endpos = argument.endpos

                        expressions.append(argument)

                    if not alternative.accepted:
                        self.stream.consume_token()

                        args = self.arguments()
                        expressions.extend(args)

                        kwargs = self.keyword_args()
                        arguments.extend(kwargs)

                        token = self.stream.peek_token()
                        if token.kind is not TokenKind.CLOSEPAREN:
                            assert False, '<Expected CLOSEPAREN>'

                        self.stream.consume_token()
                        endpos = token.end
                    else:
                        endpos = expressions[-1].endpos

                    expr = ast.CallNode(
                        startpos=expression.startpos,
                        endpos=endpos,
                        func=expression,
                        args=expressions,
                        kwargs=arguments,
                    )
                else:
                    return expression

            if not alternative.accepted:
                return expression

            assert expr is not None
            expression = expr

    def del_targets(self) -> typing.List[ast.ExpressionNode]:
        expressions: typing.List[ast.ExpressionNode] = []

        expression = self.del_target()
        expressions.append(expression)

        token = self.stream.peek_token()
        if token.kind is not TokenKind.COMMA:
            return expressions

        self.stream.consume_token()

        while True:
            with self.alternative() as alternative:
                expression = self.del_target()
                expressions.append(expression)

            token = self.stream.peek_token()
            is_comma = token.kind is TokenKind.COMMA

            if not alternative.accepted or not is_comma:
                return expressions

            self.stream.consume_token()

    def del_target(self) -> ast.ExpressionNode:
        with self.lookahead(
            TokenKind.DOT, TokenKind.OPENBRACKET, TokenKind.OPENPAREN, negative=True
        ):
            expression = self.target_primary()

            token = self.stream.peek_token()
            if token.kind is TokenKind.DOT:
                self.stream.consume_token()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.IDENTIFIER:
                    assert False, '<Expected IDENTIFIER>'

                self.stream.consume_token()

                return ast.AttributeNode(
                    startpos=expression.startpos,
                    endpos=token.end,
                    value=expression,
                    attr=token.content,
                )
            elif token.kind is TokenKind.OPENBRACKET:
                self.stream.consume_token()

                slice = self.slices()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.CLOSEBRACKET:
                    assert False, '<Expected CLOSEBRACKET>'

                self.stream.consume_token()
                return ast.SubscriptNode(
                    startpos=expression.startpos,
                    endpos=expression.endpos,
                    value=expression,
                    slice=slice,
                )

            assert False, '<Expected (DOT, OPENBRACKET)>'

        return self.del_target_atom()

    def del_target_atom(self) -> ast.ExpressionNode:
        token = self.stream.peek_token()
        startpos = token.start

        if token.kind is TokenKind.IDENTIFIER:
            self.stream.consume_token()
            return ast.NameNode(
                startpos=token.start,
                endpos=token.end,
                value=token.content,
            )
        elif token.kind is TokenKind.OPENPAREN:
            self.stream.consume_token()

            with self.alternative() as alternative:
                expression = self.del_target()

                token = self.stream.peek_token()
                if token.kind is not TokenKind.CLOSEPAREN:
                    alternative.reject()

                self.stream.consume_token()
                return expression

            expressions = self.del_targets()

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEPAREN:
                assert False, '<Expected CLOSEPAREN>'

            self.stream.consume_token()
            return ast.TupleNode(
                startpos=startpos,
                endpos=token.end,
                elts=expressions,
            )
        elif token.kind is TokenKind.OPENBRACKET:
            self.stream.consume_token()

            expressions: typing.List[ast.ExpressionNode] = []

            with self.alternative():
                targets = self.del_targets()
                expressions.extend(targets)

            token = self.stream.peek_token()
            if token.kind is not TokenKind.CLOSEBRACKET:
                assert False, 'Expected CLOSEBRACKET'

            self.stream.consume_token()
            return ast.ListNode(
                startpos=startpos,
                endpos=token.end,
                elts=expressions,
            )

        assert False, '<Unexpected Token>'
