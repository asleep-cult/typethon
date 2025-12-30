import enum
import typing

from . import ast
from ..syntax.tokens import TokenKind, IdentifierToken, StringToken, Token
from ..syntax.scanner import Scanner

KeywordT = typing.TypeVar('KeywordT', bound=enum.IntEnum)


class UnitEnum(enum.IntEnum):
    ...


class Parser(typing.Generic[KeywordT]):
    def __init__(self, source: str, keywords: typing.Dict[str, KeywordT]) -> None:
        self.source = source
        self.keywords = keywords

        self.scanner: Scanner[UnitEnum] = Scanner(source, {})
        self.buffer: typing.List[Token[UnitEnum]] = []

    def parse_identifier(self, token: IdentifierToken) -> ast.ExpressionNode[KeywordT]:
        if token.content == 'IDENTIFIER':
            kind = TokenKind.IDENTIFIER
        elif token.content == 'NUMBER':
            kind = TokenKind.NUMBER
        elif token.content == 'STRING':
            kind = TokenKind.STRING
        elif token.content == 'INDENT':
            kind = TokenKind.INDENT
        elif token.content == 'DEDENT':
            kind = TokenKind.DEDENT
        elif token.content == 'NEWLINE':
            kind = TokenKind.NEWLINE
        elif token.content == 'DIRECTIVE':
            kind = TokenKind.DIRECTIVE
        elif token.content == 'EOF':
            kind = TokenKind.EOF
        else:
            return ast.NameNode(startpos=token.start, endpos=token.end, value=token.content)

        return ast.TokenNode(startpos=token.start, endpos=token.end, kind=kind)

    def parse_string(self, token: StringToken) -> ast.ExpressionNode[KeywordT]:
        if token.content in self.keywords:
            keyword = self.keywords[token.content]
            return ast.KeywordNode(startpos=token.start, endpos=token.end, keyword=keyword)

        self.scanner.position -= len(token.content) + 1
        kind = self.scanner.token()
        if kind is TokenKind.EINVALID:
            raise ValueError(f'Invalid grammar token {token.content!r}')

        self.scanner.position += 1
        return ast.TokenNode(startpos=token.start, endpos=token.end, kind=kind)

    def scan_no_whitespace(self) -> Token[UnitEnum]:
        while True:
            token = self.scanner.scan()
            if token.kind in (TokenKind.INDENT, TokenKind.DEDENT):
                continue

            return token

    def scan_token(self, *, skip_newline: bool = False) -> Token[UnitEnum]:
        while True:
            if self.buffer:
                token = self.buffer.pop(0)
            else:
                token = self.scan_no_whitespace()

            if token.kind is not TokenKind.NEWLINE:
                return token
            elif not skip_newline:
                return token

    def peek_token(self, index: int = 1) -> Token[UnitEnum]:
        while len(self.buffer) < index:
            self.buffer.append(self.scan_no_whitespace())

        return self.buffer[index - 1]

    def parse_rules(self) -> typing.List[ast.RuleNode[KeywordT]]:
        rules: typing.List[ast.RuleNode[KeywordT]] = []
        while not self.scanner.is_eof():
            rules.append(self.parse_rule())

        return rules

    def parse_rule(self) -> ast.RuleNode[KeywordT]:
        token = self.scan_token(skip_newline=True)
        if token.kind is TokenKind.AT:
            entrypoint = True
            token = self.scan_token()
        else:
            entrypoint = False

        if token.kind is not TokenKind.IDENTIFIER:
            raise ValueError(f'Expected rule name, not {token!r}')

        startpos = token.start
        name = token.content

        token = self.scan_token()
        if token.kind is not TokenKind.COLON:
            raise ValueError(f'Expected colon after rule name, not {token!r}')

        token = self.peek_token()
        if token.kind is TokenKind.NEWLINE:
            self.scan_token()
            token = self.peek_token()

        if token.kind is TokenKind.VERTICALBAR:
            self.scan_token()

        items: typing.List[ast.RuleItemNode[KeywordT]] = []

        while True:
            expression = self.parse_expression()

            item = ast.RuleItemNode(
                startpos=token.start,
                endpos=expression.endpos,
                expression=expression,
            )
            items.append(item)

            token = self.peek_token()
            if token.kind is TokenKind.NEWLINE:
                self.scan_token()
                token = self.peek_token()

            if token.kind is not TokenKind.VERTICALBAR:
                return ast.RuleNode(
                    name=name,
                    entrypoint=entrypoint,
                    startpos=startpos,
                    endpos=items[-1].endpos,
                    items=items,
                )

            self.scan_token()

    def parse_expression(self) -> ast.ExpressionNode[KeywordT]:
        expression = self.parse_expression_group()

        token = self.peek_token()
        if token.kind is TokenKind.VERTICALBAR:
            self.scan_token()

            rhs = self.parse_expression()
            return ast.AlternativeNode(
                startpos=expression.startpos,
                endpos=rhs.endpos,
                lhs=expression,
                rhs=rhs,
            )

        return expression

    def parse_expression_group(self) -> ast.ExpressionNode[KeywordT]:
        expressions: typing.List[ast.ExpressionNode[KeywordT]] = []

        token = self.peek_token()
        while token.kind in (
            TokenKind.OPENPAREN,
            TokenKind.IDENTIFIER,
            TokenKind.STRING,
        ):
            if token.kind is TokenKind.OPENPAREN:
                self.scan_token()
                expression = self.parse_expression()

                token = self.scan_token()
                if token.kind is not TokenKind.CLOSEPAREN:
                    raise ValueError(f'Expected close parenthesis, got {token!r}')

                expression = self.parse_expression_suffix(expression)
                expressions.append(expression)

            elif token.kind in (TokenKind.IDENTIFIER, TokenKind.STRING):
                expressions.append(self.parse_atom())

            token = self.peek_token()

        if not expressions:
            raise ValueError(f'Invalid grammar: {token!r}')
        elif len(expressions) == 1:
            return expressions[0]

        return ast.GroupNode(
            startpos=expressions[0].startpos,
            endpos=expressions[-1].endpos,
            expressions=expressions,
        )

    def parse_expression_suffix(
        self, expression: ast.ExpressionNode[KeywordT]
    ) -> ast.ExpressionNode[KeywordT]:
        suffix = self.peek_token()

        if suffix.kind is TokenKind.STAR:
            self.scan_token()
            return ast.StarNode(
                startpos=expression.startpos,
                endpos=suffix.end,
                expression=expression,
            )
        elif suffix.kind is TokenKind.PLUS:
            self.scan_token()
            return ast.PlusNode(
                startpos=expression.startpos,
                endpos=suffix.end,
                expression=expression,
            )
        elif suffix.kind is TokenKind.QUESTION:
            self.scan_token()
            return ast.OptionalNode(
                startpos=expression.startpos,
                endpos=suffix.end,
                expression=expression,
            )

        return expression

    def parse_atom(self) -> ast.ExpressionNode[KeywordT]:
        token = self.scan_token()

        if token.kind is TokenKind.IDENTIFIER:
            expression = self.parse_identifier(token)
        elif token.kind is TokenKind.STRING:
            expression = self.parse_string(token)
        else:
            raise ValueError(f'Invalid grammar: {token!r}')

        return self.parse_expression_suffix(expression)
