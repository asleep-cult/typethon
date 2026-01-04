import enum
import typing

from . import ast
from .tokens import (
    GrammarToken,
    GrammarScanner,
    GrammarTokenKind,
    GRAMMAR_TOKENS,
)
from ..syntax.tokens import (
    StdTokenKind,
    IdentifierToken,
    StringToken,
    TokenMap,
    KeywordMap,
)

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)


class GrammarParser(typing.Generic[TokenKindT, KeywordKindT]):
    def __init__(
        self,
        source: str,
        tokens: TokenMap[TokenKindT],
        keywords: KeywordMap[KeywordKindT],
    ) -> None:
        self.source = source
        self.tokens = dict(tokens)
        self.keywords = dict(keywords)

        self.scanner = GrammarScanner(
            source,
            tokens=GRAMMAR_TOKENS,
            keywords=(),
            matched_tokens={GrammarTokenKind.OPENPAREN: GrammarTokenKind.CLOSEPAREN},
        )
        self.buffer: typing.List[GrammarToken] = []

    def parse_identifier(self, token: IdentifierToken) -> ast.ExpressionNode[TokenKindT, KeywordKindT]:
        if token.content == 'IDENTIFIER':
            kind = StdTokenKind.IDENTIFIER
        elif token.content == 'NUMBER':
            kind = StdTokenKind.NUMBER
        elif token.content == 'STRING':
            kind = StdTokenKind.STRING
        elif token.content == 'INDENT':
            kind = StdTokenKind.INDENT
        elif token.content == 'DEDENT':
            kind = StdTokenKind.DEDENT
        elif token.content == 'NEWLINE':
            kind = StdTokenKind.NEWLINE
        elif token.content == 'DIRECTIVE':
            kind = StdTokenKind.DIRECTIVE
        elif token.content == 'EOF':
            kind = StdTokenKind.EOF
        else:
            return ast.NameNode(start=token.start, end=token.end, value=token.content)

        return ast.TokenNode(start=token.start, end=token.end, kind=kind)

    def parse_string(self, token: StringToken) -> ast.ExpressionNode[TokenKindT, KeywordKindT]:
        if token.content in self.keywords:
            keyword = self.keywords[token.content]
            return ast.KeywordNode(start=token.start, end=token.end, keyword=keyword)

        kind = self.tokens.get(token.content)
        if kind is None:
            raise ValueError(f'Invalid grammar token {token.content!r}')

        return ast.TokenNode(start=token.start, end=token.end, kind=kind)

    def scan_no_whitespace(self) -> GrammarToken:
        while True:
            token = self.scanner.scan()
            if token.kind in (StdTokenKind.INDENT, StdTokenKind.DEDENT):
                continue

            return token

    def scan_token(self, *, skip_newline: bool = False) -> GrammarToken:
        while True:
            if self.buffer:
                token = self.buffer.pop(0)
            else:
                token = self.scan_no_whitespace()

            if token.kind is not StdTokenKind.NEWLINE:
                return token
            elif not skip_newline:
                return token

    def peek_token(self, index: int = 1) -> GrammarToken:
        while len(self.buffer) < index:
            self.buffer.append(self.scan_no_whitespace())

        return self.buffer[index - 1]

    def parse_rules(self) -> typing.List[ast.RuleNode[TokenKindT, KeywordKindT]]:
        rules: typing.List[ast.RuleNode[TokenKindT, KeywordKindT]] = []
        while not self.scanner.is_eof():
            rules.append(self.parse_rule())

        return rules

    def parse_rule(self) -> ast.RuleNode[TokenKindT, KeywordKindT]:
        token = self.scan_token(skip_newline=True)
        if token.kind is GrammarTokenKind.AT:
            entrypoint = True
            token = self.scan_token()
        else:
            entrypoint = False

        if token.kind is not StdTokenKind.IDENTIFIER:
            raise ValueError(f'Expected rule name, not {token!r}')

        start = token.start
        name = token.content

        token = self.scan_token()
        if token.kind is not GrammarTokenKind.COLON:
            raise ValueError(f'Expected colon after rule name, not {token!r}')

        token = self.peek_token()
        if token.kind is StdTokenKind.NEWLINE:
            self.scan_token()

        token = self.peek_token()
        if token.kind is GrammarTokenKind.VERTICALBAR:
            self.scan_token()
            action = None
        else:
            action = self.parse_rule_action()

            token = self.peek_token()
            if token.kind is GrammarTokenKind.VERTICALBAR:
                self.scan_token()

        items: typing.List[ast.RuleItemNode[TokenKindT, KeywordKindT]] = []

        expression = self.parse_expression()
        item = ast.RuleItemNode(
            start=token.start,
            end=expression.end,
            action=action,
            expression=expression
        )
        items.append(item)

        token = self.peek_token()
        if token.kind is StdTokenKind.NEWLINE:
            self.scan_token()   

        while True:
            action = self.parse_rule_action()

            token = self.peek_token()
            if token.kind is not GrammarTokenKind.VERTICALBAR:
                if action is not None:
                    raise ValueError(f'Invalid grammar: {token!r}')

                return ast.RuleNode(
                    name=name,
                    entrypoint=entrypoint,
                    start=start,
                    end=items[-1].end,
                    items=items,
                )

            self.scan_token()
            expression = self.parse_expression()

            item = ast.RuleItemNode(
                start=token.start,
                end=expression.end,
                action=action,
                expression=expression,
            )
            items.append(item)

            token = self.peek_token()
            if token.kind is StdTokenKind.NEWLINE:
                self.scan_token()               

    def parse_rule_action(self) -> typing.Optional[str]:
        token = self.peek_token()
        if token.kind is not StdTokenKind.DIRECTIVE:
            return

        self.scan_token()
        return token.content.strip()

    def parse_expression(self) -> ast.ExpressionNode[TokenKindT, KeywordKindT]:
        expression = self.parse_expression_group()

        token = self.peek_token()
        if token.kind is GrammarTokenKind.VERTICALBAR:
            self.scan_token()

            rhs = self.parse_expression()
            return ast.AlternativeNode(
                start=expression.start,
                end=rhs.end,
                lhs=expression,
                rhs=rhs,
            )

        return expression

    def parse_expression_group(self) -> ast.ExpressionNode[TokenKindT, KeywordKindT]:
        expressions: typing.List[ast.ExpressionNode[TokenKindT, KeywordKindT]] = []

        token = self.peek_token()
        while token.kind in (
            GrammarTokenKind.EXCLAMATION,
            GrammarTokenKind.OPENPAREN,
            StdTokenKind.IDENTIFIER,
            StdTokenKind.STRING,
        ):
            expressions.append(self.parse_expression_group_item())
            token = self.peek_token()

        if not expressions:
            raise ValueError(f'Invalid grammar: {token!r}')
        elif len(expressions) == 1:
            return expressions[0]

        return ast.GroupNode(
            start=expressions[0].start,
            end=expressions[-1].end,
            expressions=expressions,
        )

    def parse_expression_group_item(self) -> ast.ExpressionNode[TokenKindT, KeywordKindT]:
        token = self.peek_token()

        if token.kind is GrammarTokenKind.EXCLAMATION:
            self.scan_token()
            expression = self.parse_expression_group_item()

            expression = ast.CaptureNode(
                start=expression.start,
                end=expression.end,
                expression=expression,
            )
        elif token.kind is GrammarTokenKind.OPENPAREN:
            self.scan_token()
            expression = self.parse_expression()

            token = self.scan_token()
            if token.kind is not GrammarTokenKind.CLOSEPAREN:
                raise ValueError(f'Expected close parenthesis, got {token!r}')

            expression = self.parse_expression_suffix(expression)

        elif token.kind in (StdTokenKind.IDENTIFIER, StdTokenKind.STRING):
            expression = self.parse_atom()

        else:
            raise ValueError(f'Invalid grammar: {token!r}')

        return self.parse_expression_suffix(expression)

    def parse_expression_suffix(
        self, expression: ast.ExpressionNode[TokenKindT, KeywordKindT]
    ) -> ast.ExpressionNode[TokenKindT, KeywordKindT]:
        suffix = self.peek_token()

        if suffix.kind is GrammarTokenKind.STAR:
            self.scan_token()
            return ast.StarNode(
                start=expression.start,
                end=suffix.end,
                expression=expression,
            )
        elif suffix.kind is GrammarTokenKind.PLUS:
            self.scan_token()
            return ast.PlusNode(
                start=expression.start,
                end=suffix.end,
                expression=expression,
            )
        elif suffix.kind is GrammarTokenKind.QUESTION:
            self.scan_token()
            return ast.OptionalNode(
                start=expression.start,
                end=suffix.end,
                expression=expression,
            )

        return expression

    def parse_atom(self) -> ast.ExpressionNode[TokenKindT, KeywordKindT]:
        token = self.scan_token()

        if token.kind is StdTokenKind.IDENTIFIER:
            return self.parse_identifier(token)
        elif token.kind is StdTokenKind.STRING:
            return self.parse_string(token)
        else:
            raise ValueError(f'Invalid grammar: {token!r}')

    @classmethod
    def parse_from_source(
        cls,
        source: str,
        tokens: TokenMap[TokenKindT],
        keywords: KeywordMap[KeywordKindT],
    ) -> typing.List[ast.RuleNode[TokenKindT, KeywordKindT]]:
        instance = cls(source, tokens, keywords)
        return instance.parse_rules()
