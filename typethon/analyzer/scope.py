from __future__ import annotations

import typing
import enum

from .symbol import Symbol

if typing.TYPE_CHECKING:
    from .types import FunctionType


class ScopeType(enum.Enum):
    GLOBAL = enum.auto()
    CLASS = enum.auto()
    FUNCTION = enum.auto()


class Scope:
    symbols: typing.Dict[str, Symbol]

    def __init__(
        self,
        type: ScopeType,
        *,
        parent: typing.Optional[Scope] = None,
        function: typing.Optional[FunctionType] = None,
    ) -> None:
        self.symbols = {}
        self.type = type
        self.parent = parent
        self.function = function

    def is_global_scope(self) -> bool:
        return self.type is ScopeType.GLOBAL

    def is_class_scope(self) -> bool:
        return self.type is ScopeType.CLASS

    def is_function_scope(self) -> bool:
        return self.type is ScopeType.FUNCTION

    def get_function(self) -> FunctionType:
        if self.function is None:
            raise TypeError('the scope has no function')

        return self.function

    def get_symbol(self, name: str) -> typing.Optional[Symbol]:
        symbol = self.symbols.get(name)
        if symbol is not None or self.parent is None:
            return symbol

        return self.parent.get_symbol(name)
