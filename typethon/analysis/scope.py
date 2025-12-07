from __future__ import annotations

import attr
import typing

from .types import AnalyzedType, UNKNOWN


@attr.s(kw_only=True, slots=True)
class Symbol:
    # TODO: Should symbols keep a reference to the scope they were defined in?
    name: str = attr.ib()
    type: AnalyzedType = attr.ib()


class Scope:
    def __init__(self, *, parent: typing.Optional[Scope] = None) -> None:
        self.parent_scope = parent
        self.symbols: typing.Dict[str, Symbol] = {}

        self.child_scopes: typing.Dict[str, Scope] = {}

    def get_symbol(self, name: str) -> Symbol:
        symbol = self.symbols.get(name, UNRESOLVED)
        if symbol is UNRESOLVED and self.parent_scope is not None:
            return self.parent_scope.get_symbol(name)

        return symbol

    def add_symbol(self, symbol: Symbol) -> None:
        self.symbols[symbol.name] = symbol

    def create_child_scope(self, name: str) -> Scope:
        child_scope = Scope(parent=self)
        self.child_scopes[name] = child_scope
        return child_scope

    def get_child_scope(self, name: str) -> Scope:
        return self.child_scopes[name]


UNRESOLVED = Symbol(name='<unresolved symbol>', type=UNKNOWN)
