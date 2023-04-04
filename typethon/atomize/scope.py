from __future__ import annotations

import enum
import typing

import attr

from . import atoms

if typing.TYPE_CHECKING:
    from typing_extensions import Self


@attr.s(slots=True)
class Symbol:
    name: str = attr.ib()
    atom: atoms.Atom = attr.ib()


class ScopeType(enum.Enum):
    GLOBAL = enum.auto()
    CLASS = enum.auto()
    FUNCTION = enum.auto()


class Scope:
    def __init__(
        self,
        type: ScopeType,
        *,
        parent: typing.Optional[Scope] = None,
    ) -> None:
        self.symbols: typing.Dict[str, Symbol] = {}
        self.type = type
        self.parent = parent

    @classmethod
    def create_global_scope(cls) -> Self:
        scope = cls(ScopeType.GLOBAL)

        scope.add_symbol('None', atoms.NONE)
        scope.add_symbol('Ellipsis', atoms.ELLIPSIS)
        scope.add_symbol('type', atoms.get_type(atoms.TYPE))
        scope.add_symbol('bool', atoms.get_type(atoms.BOOL))
        scope.add_symbol('str', atoms.get_type(atoms.STRING))
        scope.add_symbol('int', atoms.get_type(atoms.INTEGER))
        scope.add_symbol('float', atoms.get_type(atoms.FLOAT))
        scope.add_symbol('complex', atoms.get_type(atoms.COMPLEX))

        return scope

    def create_function_scope(self) -> Self:
        return Scope(ScopeType.FUNCTION, parent=self)

    def is_global_scope(self) -> bool:
        return self.type is ScopeType.GLOBAL

    def is_class_scope(self) -> bool:
        return self.type is ScopeType.CLASS

    def is_function_scope(self) -> bool:
        return self.type is ScopeType.FUNCTION

    def get_parent(self) -> Self:
        if self.parent is None:
            raise ValueError('scope does not have parent')

        return self.parent

    def add_symbol(self, name: str, atom: atoms.Atom) -> None:
        self.symbols[name] = Symbol(name, atom)

    def get_symbol(self, name: str) -> typing.Optional[Symbol]:
        symbol = self.symbols.get(name)
        if symbol is not None or self.parent is None:
            return symbol

        return self.parent.get_symbol(name)
