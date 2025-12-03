from __future__ import annotations

import attr
import typing

from .types import AnalyzedType


@attr.s(kw_only=True, slots=True)
class Symbol:
    name: str = attr.ib()
    type: AnalyzedType = attr.ib()


class Scope:
    def __init__(self, *, parent: typing.Optional[Scope] = None) -> None:
        self.parent_scope = parent
        self.symbols: typing.Dict[str, Symbol] = {}

    def get_symbol(self, name: str) -> typing.Optional[Symbol]:
        symbol = self.symbols.get(name)
        if symbol is not None or self.parent_scope is None:
            return symbol

        return self.parent_scope.get_symbol(name)

    def add_symbol(self, symbol: Symbol) -> None:
        self.symbols[symbol.name] = symbol

    def create_child_scope(self) -> Scope:
        return Scope(parent=self)
