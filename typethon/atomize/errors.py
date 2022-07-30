from __future__ import annotations

import enum
import typing

import attr

if typing.TYPE_CHECKING:
    from .. import ast

__all__ = ('ErrorCategory', 'AnalyzationError')


class ErrorCategory(enum.IntEnum):
    SYNTAX_ERROR = enum.auto()
    TYPE_ERROR = enum.auto()


@attr.s(kw_only=True, slots=True)
class AnalyzationError:
    category: ErrorCategory = attr.ib()
    message: str = attr.ib()
    node: typing.Optional[ast.Node] = attr.ib(default=None)

    def with_node(self, node: ast.Node) -> AnalyzationError:
        return AnalyzationError(category=self.category, message=self.message, node=node)
