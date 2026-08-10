from __future__ import annotations

import attr

from . import types
from .. import asg


@attr.s(kw_only=True, slots=True)
class AdtInfo:
    def_id: asg.DefinitionId = attr.ib()
    variants: list[AdtVariant] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class AdtVariant:
    def_id: asg.DefinitionId = attr.ib()
    name: str = attr.ib()
    fields: list[VariantField] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class VariantField:
    def_id: asg.DefinitionId = attr.ib()
    name: str | None = attr.ib()


@attr.s(kw_only=True, slots=True)
class ParameterInfo:
    def_id: int = attr.ib()
    name: str = attr.ib()
    index: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class GenericsInfo:
    def_id: asg.DefinitionId = attr.ib()
    parent_id: asg.DefinitionId | None = attr.ib()
    parent_count: int = attr.ib()
    parameters: list[ParameterInfo] = attr.ib()
    index_map: dict[asg.DefinitionId, int] = attr.ib()

    def get_count(self) -> int:
        return self.parent_count + len(self.parameters)


@attr.s(kw_only=True, slots=True)
class FunctionInfo:
    def_id: int = attr.ib()
    parameters: dict[str, types.Type] = attr.ib()
    returns: types.Type = attr.ib()
