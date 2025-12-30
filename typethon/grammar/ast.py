from __future__ import annotations

import attr
import typing
import enum

from ..syntax import tokens

KeywordT = typing.TypeVar('KeywordT', bound=enum.IntEnum)


@attr.s(kw_only=True, slots=True)
class Node:
    startpos: int = attr.ib()
    endpos: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class RuleNode(typing.Generic[KeywordT], Node):
    name: str = attr.ib()
    entrypoint: bool = attr.ib()
    items: typing.List[RuleItemNode[KeywordT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class RuleItemNode(typing.Generic[KeywordT], Node):
    expression: ExpressionNode[KeywordT] = attr.ib()
    action: typing.Optional[str] = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class StarNode(typing.Generic[KeywordT], Node):
    expression: ExpressionNode[KeywordT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class PlusNode(typing.Generic[KeywordT], Node):
    expression: ExpressionNode[KeywordT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class OptionalNode(typing.Generic[KeywordT], Node):
    expression: ExpressionNode[KeywordT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class AlternativeNode(typing.Generic[KeywordT], Node):
    lhs: ExpressionNode[KeywordT] = attr.ib()
    rhs: ExpressionNode[KeywordT] = attr.ib()


@attr.s(kw_only=True, slots=True)
class GroupNode(typing.Generic[KeywordT], Node):
    expressions: typing.List[ExpressionNode[KeywordT]] = attr.ib()


@attr.s(kw_only=True, slots=True)
class TokenNode(Node):
    kind: tokens.TokenKind = attr.ib()


@attr.s(kw_only=True, slots=True)
class KeywordNode(typing.Generic[KeywordT], Node):
    keyword: KeywordT = attr.ib()


@attr.s(kw_only=True, slots=True)
class NameNode(Node):
    value: str = attr.ib()


ExpressionNode = typing.Union[
    StarNode[KeywordT],
    PlusNode[KeywordT],
    OptionalNode[KeywordT],
    AlternativeNode[KeywordT],
    GroupNode[KeywordT],
    KeywordNode[KeywordT],
    TokenNode,
    NameNode,
]
