from __future__ import annotations

import attr
import typing

from . import types


@attr.s(kw_only=True, slots=True)
class TypeInstance:
    type: types.ConcreteType = attr.ib()


class Scope:
    def __init__(self, *, parent: typing.Optional[Scope] = None) -> None:
        self.parent_scope = parent
        self.symbols: typing.Dict[str, Symbol] = {}
        self.type_parameters: typing.Dict[str, types.TypeParameter] = {}

    def get_symbol(self, name: str) -> typing.Optional[Symbol]:
        symbol = self.symbols.get(name)
        if symbol is None and self.parent_scope is not None:
            return self.parent_scope.get_symbol(name)

        return symbol

    def add_symbol(self, name: str, symbol: Symbol) -> None:
        self.symbols[name] = symbol

    def get_type_parameter(self, name: str) -> typing.Optional[types.TypeParameter]:
        parameter = self.type_parameters.get(name)
        if parameter is None and self.parent_scope is not None:
            return self.parent_scope.get_type_parameter(name)

        return parameter

    def add_type_parameter(self, parameter: types.TypeParameter) -> None:
        self.type_parameters[parameter.name] = parameter

    def create_child_scope(self) -> Scope:
        return Scope(parent=self)


Symbol = typing.Union[types.Type, TypeInstance]
