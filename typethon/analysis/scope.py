from __future__ import annotations

import attr
import typing

from . import types


@attr.s(kw_only=True, slots=True)
class Symbol:
    # TODO: Should symbols keep a reference to the scope they were defined in?
    name: str = attr.ib()
    content: types.AnalysisUnit = attr.ib()


class Scope:
    def __init__(self, *, parent: typing.Optional[Scope] = None) -> None:
        self.parent_scope = parent
        self.symbols: typing.Dict[str, Symbol] = {}

        self.child_scopes: typing.Dict[str, Scope] = {}

    def has_symbol(self, name: str) -> bool:
        return name in self.symbols

    def get_symbol(self, name: str) -> Symbol:
        symbol = self.symbols.get(name, UNRESOLVED)
        if symbol is UNRESOLVED and self.parent_scope is not None:
            return self.parent_scope.get_symbol(name)

        return symbol

    def get_type(self, name: str) -> types.AnalyzedType:
        symbol = self.get_symbol(name)
        if not isinstance(symbol.content, types.AnalyzedType):
            return types.UNKNOWN

        return symbol.content

    def get_instance(self, name: str) -> types.InstanceOfType:
        symbol = self.get_symbol(name)
        if not isinstance(symbol.content, types.InstanceOfType):
            return types.UNKNOWN.to_instance()

        return symbol.content

    def add_symbol(self, symbol: Symbol) -> None:
        self.symbols[symbol.name] = symbol

    def create_child_scope(self, name: str) -> Scope:
        child_scope = Scope(parent=self)
        self.child_scopes[name] = child_scope
        return child_scope

    def get_child_scope(self, name: str) -> Scope:
        return self.child_scopes[name]


UNRESOLVED = Symbol(name='<unresolved symbol>', content=types.UNKNOWN)
