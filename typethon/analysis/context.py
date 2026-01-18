from __future__ import annotations

import attr
import typing
import enum

from . import types


@attr.s(kw_only=True, slots=True)
class TypeInstance:
    type: types.ConcreteType = attr.ib()


class AnalysisFlags(enum.Flag):
    NONE = 0
    ALLOW_RETURN = enum.auto()
    ALLOW_BREAK = enum.auto()
    ALLOW_CONTINUE = enum.auto()


class AnalysisContext:
    def __init__(
        self,
        *,
        parent: typing.Optional[AnalysisContext] = None,
        flags: AnalysisFlags = AnalysisFlags.NONE,
        returnable_type: types.ConcreteType = types.SingletonType.UNIT,
    ) -> None:
        self.parent_context = parent
        self.flags = flags
        self.returnable_type = returnable_type
        self.symbols: typing.Dict[str, Symbol] = {}
        self.type_parameters: typing.Dict[str, types.TypeParameter] = {}
        self.children_context: typing.Dict[int, AnalysisContext] = {}

    def get_symbol(self, name: str) -> typing.Optional[Symbol]:
        symbol = self.symbols.get(name)
        if symbol is None and self.parent_context is not None:
            return self.parent_context.get_symbol(name)

        return symbol

    def add_symbol(self, name: str, symbol: Symbol) -> None:
        self.symbols[name] = symbol

    def get_type_parameter(self, name: str) -> typing.Optional[types.TypeParameter]:
        parameter = self.type_parameters.get(name)
        if parameter is None and self.parent_context is not None:
            return self.parent_context.get_type_parameter(name)

        return parameter

    def add_type_parameter(self, parameter: types.TypeParameter) -> None:
        self.type_parameters[parameter.name] = parameter

    def create_child_context(
        self,
        index: int,
        *,
        flags: AnalysisFlags,
        returnable_type: types.ConcreteType,
    ) -> AnalysisContext:
        ctx = AnalysisContext(parent=self, flags=flags, returnable_type=returnable_type)
        self.children_context[index] = ctx
        return ctx

    def get_child_context(self, index: int) -> AnalysisContext:
        return self.children_context[index]


Symbol = typing.Union[types.Type, TypeInstance]
