from __future__ import annotations

import attr
import typing
import enum

from ..syntax import tokens

TokenKindT = typing.TypeVar("TokenKindT", bound=enum.Enum)
KeywordKindT = typing.TypeVar("KeywordKindT", bound=enum.Enum)


@attr.s(kw_only=True, slots=True)
class Node:
    start: int = attr.ib()
    end: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class RuleNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    name: str = attr.ib()
    entrypoint: bool = attr.ib()
    items: list[RuleItemNode[TokenKindT, KeywordKindT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class RuleItemNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()
    action: str | None = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class StarNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class PlusNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class OptionalNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class CaptureNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    expression: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AlternativeNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    lhs: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()
    rhs: ExpressionNode[TokenKindT, KeywordKindT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class GroupNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum](Node):
    expressions: list[ExpressionNode[TokenKindT, KeywordKindT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TokenNode(typing.Generic[TokenKindT], Node):
    kind: TokenKindT = attr.ib()


@attr.s(kw_only=True, slots=True)
class KeywordNode(typing.Generic[KeywordKindT], Node):
    keyword: KeywordKindT = attr.ib()


@attr.s(kw_only=True, slots=True)
class NameNode(Node):
    value: str = attr.ib()


type ExpressionNode[TokenKindT: enum.Enum, KeywordKindT: enum.Enum] = (
    StarNode[TokenKindT, KeywordKindT]
    | PlusNode[TokenKindT, KeywordKindT]
    | OptionalNode[TokenKindT, KeywordKindT]
    | CaptureNode[TokenKindT, KeywordKindT]
    | AlternativeNode[TokenKindT, KeywordKindT]
    | GroupNode[TokenKindT, KeywordKindT]
    | KeywordNode[KeywordKindT]
    | TokenNode[TokenKindT]
    | TokenNode[tokens.StdTokenKind]
    | NameNode
)
