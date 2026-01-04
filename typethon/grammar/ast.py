from __future__ import annotations

import attr
import typing
import enum

from ..syntax import tokens

TokenKindT = typing.TypeVar('TokenKindT', bound=enum.Enum)
KeywordKindT = typing.TypeVar('KeywordKindT', bound=enum.Enum)


@attr.s(kw_only=True, slots=True)
class Node:
    startpos: int = attr.ib()
    endpos: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class RuleNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    name: str = attr.ib()
    entrypoint: bool = attr.ib()
    items: typing.List[RuleItemNode[TokenKindT, KeywordKindT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class RuleItemNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()
    action: typing.Optional[str] = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class StarNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class PlusNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class OptionalNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class CaptureNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AlternativeNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    lhs: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()
    rhs: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class GroupNode(typing.Generic[TokenKindT, KeywordKindT], Node):
    expressions: typing.List[ExpressionNode[TokenKindT, KeywordKindT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TokenNode(typing.Generic[TokenKindT], Node):
    kind: TokenKindT = attr.ib()


@attr.s(kw_only=True, slots=True)
class KeywordNode(typing.Generic[KeywordKindT], Node):
    keyword: KeywordKindT = attr.ib()


@attr.s(kw_only=True, slots=True)
class NameNode(Node):
    value: str = attr.ib()


ExpressionNode = typing.Union[
    StarNode[TokenKindT, KeywordKindT],
    PlusNode[TokenKindT, KeywordKindT],
    OptionalNode[TokenKindT, KeywordKindT],
    CaptureNode[TokenKindT, KeywordKindT],
    AlternativeNode[TokenKindT, KeywordKindT],
    GroupNode[TokenKindT, KeywordKindT],
    KeywordNode[KeywordKindT],
    TokenNode[TokenKindT],
    TokenNode[tokens.StdTokenKind],
    NameNode,
]
