from __future__ import annotations

import typing
import enum

import attr


from . import atoms


class ScopeType(enum.Enum):
    GLOBAL = enum.auto()
    CLASS = enum.auto()
    FUNCTION = enum.auto()


@attr.s(slots=True)
class Symbol:
    name: str = attr.ib()
    atom: atoms.Atom = attr.ib()


class Scope:
    def __init__(
        self,
        type: ScopeType,
        *,
        parent: typing.Optional[Scope] = None,
        function: typing.Optional[atoms.FunctionAtom] = None,
    ) -> None:
        self.symbols: typing.Dict[str, Symbol] = {}
        self.type = type
        self.parent = parent
        self.function = function

    def is_global_scope(self) -> bool:
        return self.type is ScopeType.GLOBAL

    def is_class_scope(self) -> bool:
        return self.type is ScopeType.CLASS

    def is_function_scope(self) -> bool:
        return self.type is ScopeType.FUNCTION

    def get_function(self) -> atoms.FunctionAtom:
        if self.function is None:
            raise TypeError('the scope has no function')

        return self.function

    def add_symbol(self, name: str, atom: atoms.Atom) -> None:
        self.symbols[name] = Symbol(name, atom)

    def get_symbol(self, name: str) -> typing.Optional[Symbol]:
        symbol = self.symbols.get(name)
        if symbol is not None or self.parent is None:
            return symbol

        return self.parent.get_symbol(name)
